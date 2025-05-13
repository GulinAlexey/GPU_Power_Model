import socket
import threading
import pymongo
import pandas as pd
import numpy as np
import lightgbm
import optuna
from sklearn.model_selection import train_test_split
from sklearn.metrics import r2_score, mean_absolute_error
from sklearn.preprocessing import MinMaxScaler
from sklearn.preprocessing import LabelEncoder
import plotly.graph_objects as go
from datetime import datetime
import os
import webbrowser
from ParameterOptimizer import ParameterOptimizer
from SocketCalls import SocketCalls


class DataAnalysisSystem:
    def __init__(self):
        optuna.logging.set_verbosity(optuna.logging.WARNING)  # Отключить INFO-сообщения (для lightgbm.train())
        self.__address = SocketCalls.DATA_ANALYSIS_SYSTEM_ADDRESS
        self.__port = SocketCalls.DATA_ANALYSIS_SYSTEM_PORT
        # Параметры MongoDB
        self.__client = pymongo.MongoClient("mongodb://localhost:27017/")  # Адрес сервера MongoDB
        self.__db = self.__client["gpu_benchmark_monitoring"]  # Название БД с собранными данными для обучения модели
        # Список всех коллекций с данными в БД
        self.__collections = [self.__db[col] for col in self.__db.list_collection_names()]
        self.__label_encoder = LabelEncoder()  # Единый encoder для всего класса
        self.__scaler = None
        # Переименование колонок для LightGBM
        # Иначе будет ошибка lightgbm.basic.LightGBMError: Do not support special JSON characters in feature name
        self.__column_mapping = {
            'Date': 'date',
            'GPU Clock [MHz]': 'gpu_clock_mhz',
            'Memory Clock [MHz]': 'memory_clock_mhz',
            'GPU Temperature [°C]': 'gpu_temp_c',
            'Fan Speed [%]': 'fan_speed_percent',
            'Fan Speed [RPM]': 'fan_speed_rpm',
            'Memory Used [MB]': 'memory_used_mb',
            'GPU Load [%]': 'gpu_load_percent',
            'Memory Controller Load [%]': 'memory_controller_load_percent',
            'Board Power Draw [W]': 'board_power_draw_w',
            'Power Consumption [% TDP]': 'power_consumption_percent_tdp',
            'Power Limit [W]': 'power_limit_w',
            'TDP Limit [%]': 'tdp_limit_percent',
            'Min GPU Clock Frequency [MHz]': 'min_gpu_clock_mhz',
            'Max GPU Clock Frequency [MHz]': 'max_gpu_clock_mhz',
            'GPU Clock Frequency Offset [MHz]': 'gpu_clock_offset_mhz',
            'Memory Clock Offset [MHz]': 'memory_clock_offset_mhz',
            'GPU Voltage [V]': 'gpu_voltage_v',
            'Benchmark test type': 'benchmark_type',
            # 'Efficiency [FPS/W]': 'efficiency_fps_per_watt',
            'FPS': 'fps'
        }
        # Все признаки без категориальных
        self.__numeric_features = [
            'power_limit_w',
            'gpu_clock_offset_mhz',
            'memory_clock_offset_mhz',
            'gpu_temp_c',
            'fan_speed_percent',
            'fan_speed_rpm',
            'memory_used_mb',
            'gpu_load_percent',
            'memory_controller_load_percent',
            'board_power_draw_w',
            'power_consumption_percent_tdp',
            'tdp_limit_percent',
            'min_gpu_clock_mhz',
            'max_gpu_clock_mhz',
            'gpu_voltage_v'
            # 'efficiency_fps_per_watt'
        ]
        self.__current_df = None
        self.__current_model = None
        self.__current_optimal_params = None
        # Имя файла с именами коллекций, чтобы не собирать повторно
        self.__collection_names_file_path = "comparison_collection_names_for_analysis.txt"
        # Список типов тестов бенчмарка для запуска и сбора данных (выполняются по очереди)
        self.__benchmark_tests = ["gltessyspherex32", "glpbrdonut", "glphongdonut", "glmsi01", "glfurrytorus",
                                  "glfurrymsi", "glmsi02gpumedium"]
        # Имена файлов для сохранения plotly-диаграмм
        self.__plot_feature_importance_html_name = "plot_feature_importance.html"
        self.__plot_common_comparison_html_name = "plot_common_comparison.html"
        self.__plot_type_test_comparison_html_name = "plot_type_test_comparison.html"

        ### Параметры запуска тестов для сравнения производительности по умолчанию и производительности с оптимальными параметрами ###
        # Необходимо предварительно установить через передачу значений методам __set_default_time_and_watt_reducing_value_for_tests(),
        # __set_db_name_for_comparison_tests() и методам запуска тестов

        # Параметры времени теста (в секундах)
        self.__time_before_start_test = None
        self.__time_test_running = None
        self.__time_after_finish_test = None
        # Параметр уменьшения power limit для достижения минимального значения (для сбора данных и дальнейшего сравнения с оптим.)
        self.__milliwatt_reducing_value = None  # Величина уменьшения Power Limit за один тест
        # Название БД с данными для сравнения производительности исходной и с найденными оптимальными параметрами
        self.__db_name_for_comparison_tests = None
        # Имя коллекции БД с оптимальными параметрами
        self.__found_params_collection_name = None
        # Имена коллекций БД с параметрами по умолчанию
        self.__default_params_collection_name = None
        self.__default_params_and_min_power_limit_collection_name = None

    # Получить документы из коллекции в dataframe для обработки (в методах построения модели)
    def __get_documents_from_collection_and_set_current_df(self):
        # Получить все документы из коллекции
        all_documents = []
        for collection in self.__collections:
            documents = list(collection.find())
            all_documents.extend(documents)  # Добавить документы в общий список
        # Преобразовать данные в DataFrame
        df = pd.DataFrame(all_documents)
        str_result = ""
        print_str = f"Всего {len(df)} документов"
        str_result = str_result + "\n" + print_str
        print(print_str)
        # Оставить только те документы, где FPS не пустой (и не None)
        df = df[df["FPS"].notna()]
        print_str = f"Всего {len(df)} документов с FPS"
        str_result = str_result + "\n" + print_str
        print(print_str)
        self.__current_df = df
        return str_result

    # Определить коэффициент корреляции между FPS и изменяемыми параметрами работы GPU (обособленный метод)
    def __correlation_coefficient(self, method='pearson', df=None):
        # Работа с текущим dataframe у класса системы анализа, если не передано иное
        if df is None:
            df = self.__current_df
        # Выбрать параметры для анализа
        correlation_columns = ["Power Limit [W]", "GPU Clock Frequency Offset [MHz]", "Memory Clock Offset [MHz]",
                               "FPS"]
        # Оставить только нужные столбцы
        df = df[["Benchmark test type"] + correlation_columns]
        # Определить корреляцию для каждого Benchmark test type
        benchmark_types = df["Benchmark test type"].unique()
        # Итоговый словарь для хранения корреляций
        correlations = {}
        for benchmark in benchmark_types:
            # Отфильтровать данные для текущего теста
            benchmark_data = df[df["Benchmark test type"] == benchmark]
            if len(benchmark_data) > 1:  # Проверить, чтобы было больше 1 значения для расчета корреляции
                # Вычислить корреляцию между FPS и другими столбцами
                correlation_matrix = benchmark_data[correlation_columns].corr(method)
                fps_correlation = correlation_matrix["FPS"]  # Взять корреляции FPS с остальными параметрами
                correlations[benchmark] = fps_correlation.drop("FPS").to_dict()
        # Вывести результаты
        str_result = ""
        print_str = "\n".join([
            "=" * 50,
            "Коэффициент корреляции " + method
            ])
        str_result = str_result + "\n" + print_str
        print(print_str)
        for benchmark, correlation in correlations.items():
            print_str = f"Тип теста бенчмарка: {benchmark}"
            str_result = str_result + "\n" + print_str
            print(print_str)
            for param, corr_value in correlation.items():
                print_str = f"  {param}: {corr_value:.4f}"
                str_result = str_result + "\n" + print_str
                print(print_str)
        return str_result

    ######## Методы модели оптимального энергопотребления ########
    # Предобработка данных
    def __preprocess_data(self, data):
        df = data.copy()
        df = df.rename(columns=self.__column_mapping)
        # Нормализация числовых параметров
        self.__scaler = MinMaxScaler()
        df[self.__numeric_features] = self.__scaler.fit_transform(df[self.__numeric_features])
        # Добавление шума к целевой переменной (15%)
        df['fps'] = df['fps'] * (1 + np.random.normal(0, 0.15, len(df)))
        # Кодирование категориального признака
        self.__label_encoder.fit(df['benchmark_type'].astype(str).unique())
        df['benchmark_type'] = self.__label_encoder.transform(df['benchmark_type'].astype(str))
        return df

    # Построение и оценка модели
    def __train_fps_model(self, df):
        # Выделение признаков и целевой переменной
        x = df[self.__numeric_features + ['benchmark_type']].copy()
        y = df['fps']
        # Разделение на train/test
        x_train, x_test, y_train, y_test = train_test_split(
            x, y, test_size=0.2, random_state=42, stratify=x['benchmark_type']
        )
        # Создание Dataset
        train_data = lightgbm.Dataset(
            x_train,
            label=y_train,
            categorical_feature=['benchmark_type']
        )
        # Параметры модели
        params = {
            'objective': 'regression',
            'metric': 'mae',
            'num_leaves': 63,
            'learning_rate': 0.05,
            'feature_fraction': 0.8,
            'verbose': -1,
            'max_depth': -1  # Автоматическое определение глубины
        }
        # Обучение
        model = lightgbm.train(params, train_data)
        # Оценка
        prediction = model.predict(x_test)
        r2 = r2_score(y_test, prediction)
        mae = mean_absolute_error(y_test, prediction)

        return model, {'r2': r2, 'mae': mae}

    # Анализ важности признаков
    def __plot_feature_importance(self, model):
        feature_imp = pd.DataFrame({
            'Feature': model.feature_name(),
            'Importance': model.feature_importance()
        }).sort_values(by='Importance', ascending=True)
        fig = go.Figure(go.Bar(
            x=feature_imp['Importance'],
            y=feature_imp['Feature'],
            orientation='h'
        ))
        fig.update_layout(
            title='Важность признаков модели',
            xaxis_title='Важность',
            yaxis_title='Признак'
        )
        fig.write_html(self.__plot_feature_importance_html_name)
        webbrowser.open(self.__plot_feature_importance_html_name)

    # Преобразовать нормализованные параметры обратно в оригинальный диапазон
    def __denormalize_params(self, params):
        # Создать полный вектор признаков со средними значениями
        full_params = np.full(len(self.__numeric_features), 0.5)  # Средние значения
        # Заменить нужные параметры
        power_idx = self.__numeric_features.index('power_limit_w')
        gpu_idx = self.__numeric_features.index('gpu_clock_offset_mhz')
        mem_idx = self.__numeric_features.index('memory_clock_offset_mhz')
        full_params[power_idx] = params['power_limit_w']
        full_params[gpu_idx] = params['gpu_clock_offset_mhz']
        full_params[mem_idx] = params['memory_clock_offset_mhz']
        # Обратное преобразование
        original_params = self.__scaler.inverse_transform([full_params])[0]
        return {
            'power_limit_w': original_params[power_idx],
            'gpu_clock_offset_mhz': original_params[gpu_idx],
            'memory_clock_offset_mhz': original_params[mem_idx]
        }

    # Найти усредненные оптимальные параметры для всех типов тестов
    def __find_optimal_for_all_tests(self, results):
        if not results:
            return None
        # Собрать все параметры для денормализации
        all_params = []
        for test_type, params in results.items():
            all_params.append(params)
        # Вычислить средние значения нормализованных параметров
        avg_params = {
            'power_limit_w': np.mean([p['power_limit_w'] for p in all_params]),
            'gpu_clock_offset_mhz': np.mean([p['gpu_clock_offset_mhz'] for p in all_params]),
            'memory_clock_offset_mhz': np.mean([p['memory_clock_offset_mhz'] for p in all_params])
        }
        # Денормализовать усредненные параметры
        return self.__denormalize_params(avg_params)

    def __gpu_power_model(self, data=None):
        # Работа с текущим dataframe у класса системы анализа, если не передано иное
        if data is None:
            data = self.__current_df
        # Предобработка
        df = self.__preprocess_data(data)
        # Обучение модели
        model, metrics = self.__train_fps_model(df)
        str_result = ""
        print_str = f"Метрики модели: R2={metrics['r2']:.3f}, MAE={metrics['mae']:.1f}"
        str_result = str_result + "\n" + print_str
        print(print_str)
        # Визуализация важности признаков
        self.__plot_feature_importance(model)
        results = {}
        for test_type_num in df['benchmark_type'].unique():
            # Преобразовать в строку и декодировать
            test_type_str = self.__label_encoder.inverse_transform([test_type_num])[0]
            optimizer = ParameterOptimizer(model, test_type_str, alpha=0.3)
            optimizer.le = self.__label_encoder  # Передать encoder
            try:
                best_params = optimizer.optimize(n_trials=50)
                results[test_type_str] = best_params
            except Exception as e:
                print_str = f"Ошибка для теста {test_type_str}: {str(e)}"
                str_result = str_result + "\n" + print_str
                print(print_str)
                continue
        # Получить минимальные и максимальные значения параметров
        param_ranges = {
            'power_limit_w': (self.__scaler.data_min_[0], self.__scaler.data_max_[0]),
            'gpu_clock_offset_mhz': (self.__scaler.data_min_[1], self.__scaler.data_max_[1]),
            'memory_clock_offset_mhz': (self.__scaler.data_min_[2], self.__scaler.data_max_[2])
        }
        print_str = "\n".join([
            "\nДиапазоны параметров:",
            f"  Лимит мощности: {param_ranges['power_limit_w'][0]:.0f}-{param_ranges['power_limit_w'][1]:.0f} Вт",
            f"  Смещение частоты GPU: {param_ranges['gpu_clock_offset_mhz'][0]:.0f}-{param_ranges['gpu_clock_offset_mhz'][1]:.0f} МГц",
            f"  Смещение частоты памяти: {param_ranges['memory_clock_offset_mhz'][0]:.0f}-{param_ranges['memory_clock_offset_mhz'][1]:.0f} МГц",
            "\nОптимальные параметры:"
            ])
        str_result = str_result + "\n" + print_str
        print(print_str)
        for test_type, params in results.items():
            # Преобразовать параметры в оригинальный диапазон
            original_params = self.__denormalize_params(params)
            print_str = "\n".join([
                f"\nТест: {test_type}",
                f"  Лимит мощности (Вт): {original_params['power_limit_w']:.3f}",
                f"  Смещение частоты GPU (МГц): {original_params['gpu_clock_offset_mhz']:.0f}",
                f"  Смещение частоты памяти (МГц): {original_params['memory_clock_offset_mhz']:.0f}"
                ])
            str_result = str_result + "\n" + print_str
            print(print_str)
        # Добавлен вывод усредненных параметров для всех тестов
        avg_original_params = self.__find_optimal_for_all_tests(results)
        if avg_original_params:
            print_str = "\n".join([
                "\nУсредненные оптимальные параметры для всех тестов:",
                f"  Лимит мощности (Вт): {avg_original_params['power_limit_w']:.3f}",
                f"  Смещение частоты GPU (МГц): {avg_original_params['gpu_clock_offset_mhz']:.0f}",
                f"  Смещение частоты памяти (МГц): {avg_original_params['memory_clock_offset_mhz']:.0f}"
            ])
            str_result = str_result + "\n" + print_str
            print(print_str)
        self.__current_model = model
        self.__current_optimal_params = avg_original_params
        return str_result

    ######## Методы сравнения производительности GPU с параметрами по умолчанию и производительности с оптимальными параметрами ########
    # Записать имена коллекций с тестами параметров GPU по умолчанию (чтобы не собирать повторно)
    def __write_collection_names(self):
        # Записать имена коллекций в файл (предварительно очищая его)
        with open(self.__collection_names_file_path, 'w') as file:
            file.write(f"{self.__default_params_collection_name}\n")
            file.write(f"{self.__default_params_and_min_power_limit_collection_name}\n")
        str_result = ""
        print_str = f"Имена коллекций записаны в {self.__collection_names_file_path}"
        str_result = str_result + "\n" + print_str
        print(print_str)
        return str_result

    # Задать параметры времени тестов и величины уменьшения Power Limit для сбора данных и анализа (для сравнения default и optimal параметров)
    def __set_default_time_and_watt_reducing_value_for_tests(self, time_before_start_test, time_test_running,
                                                            time_after_finish_test, watt_reducing_value):
        self.__time_before_start_test = time_before_start_test
        self.__time_test_running = time_test_running
        self.__time_after_finish_test = time_after_finish_test
        self.__milliwatt_reducing_value = watt_reducing_value * 1000
        return True

    # Задать название БД с данными для сравнения производительности исходной и с найденными оптимальными параметрами
    def __set_db_name_for_comparison_tests(self, db_name_for_comparison_tests):
        self.__db_name_for_comparison_tests = db_name_for_comparison_tests
        return True

    # Считать имена коллекций с тестами параметров GPU по умолчанию из файла (если он есть)
    def __read_and_verify_collection_names(self):
        if not os.path.exists(self.__collection_names_file_path):
            print(f"Файл {self.__collection_names_file_path} не найден")
            return False
        with open(self.__collection_names_file_path, 'r') as file:
            lines = file.read().splitlines()
        if len(lines) != 2:
            print(f"Файл {self.__collection_names_file_path} должен содержать ровно 2 строки")
            return False
        self.__default_params_collection_name = lines[0]
        self.__default_params_and_min_power_limit_collection_name = lines[1]
        return True

    # Запуск тестов бенчмарка с параметрами по умолчанию для дальнейшего сравнения
    def __run_test_with_default_params(self, default_params_collection_name):
        str_result = ""
        print_str = "Запущен сбор данных для GPU с параметрами работы по умолчанию"
        str_result = str_result + "\n" + print_str
        print(print_str)
        # Вернуть значение Power Limit GPU по умолчанию
        _ = SocketCalls.call_method_of_undervolting_gpu_system("set_tdp_to_default")
        # Вернуть значение смещения частоты GPU по умолчанию
        _, _ = SocketCalls.call_method_of_undervolting_gpu_system("set_gpu_clock_offset_to_default")
        # Вернуть значение смещения частоты памяти по умолчанию
        _ = SocketCalls.call_method_of_undervolting_gpu_system("set_mem_clock_offset_to_default")
        self.__default_params_collection_name = default_params_collection_name + " " + datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S")
        for benchmark_test_type in self.__benchmark_tests:
            SocketCalls.call_method_of_benchmark_test_system("change_benchmark_test_type", benchmark_test_type)
            # Один запуск теста бенчмарка со сбором данных в БД (ограниченный по времени)
            res = SocketCalls.call_method_of_benchmark_test_system("run_benchmark",
                                                                   self.__default_params_collection_name,
                                                                   self.__time_before_start_test,
                                                                   self.__time_test_running,
                                                                   self.__time_after_finish_test,
                                                                   self.__db_name_for_comparison_tests)
            if res is False:
                print_str = "Работа теста бенчмарка типа " + benchmark_test_type + " была остановлена. Данные параметры работы GPU являются нестабильными"
                str_result = str_result + "\n" + print_str
                print(print_str)
            # Запись FPS из файла лога MSI Kombustor (и эффективность [FPS/W]) в соответствующие документы коллекции MongoDB
            SocketCalls.call_method_of_benchmark_test_system("update_fps_and_efficiency_in_collection",
                                                             self.__default_params_collection_name,
                                                             self.__db_name_for_comparison_tests)
        print_str = ("Данные для тестов бенчмарка с параметрами по умолчанию успешно собраны в БД " +
                     self.__db_name_for_comparison_tests + " в коллекции " + self.__default_params_collection_name)
        str_result = str_result + "\n" + print_str
        print(print_str)
        return str_result

    # Запуск тестов бенчмарка с параметрами по умолчанию (и min power limit) для дальнейшего сравнения
    def __run_test_with_default_params_and_min_power_limit(self, default_params_and_min_power_limit_collection_name):
        str_result = ""
        print_str = "Запущен сбор данных для GPU с параметрами работы по умолчанию и минимальным Power Limit"
        str_result = str_result + "\n" + print_str
        print(print_str)
        # Вернуть значение смещения частоты GPU по умолчанию
        _, _ = SocketCalls.call_method_of_undervolting_gpu_system("set_gpu_clock_offset_to_default")
        # Вернуть значение смещения частоты памяти по умолчанию
        _ = SocketCalls.call_method_of_undervolting_gpu_system("set_mem_clock_offset_to_default")
        # Вернуть значение Power Limit GPU по умолчанию
        current_power_limit = SocketCalls.call_method_of_undervolting_gpu_system("set_tdp_to_default")
        while True:
            previous_power_limit = current_power_limit
            current_power_limit = SocketCalls.call_method_of_undervolting_gpu_system("reduce_tdp",
                                                                                     self.__milliwatt_reducing_value)
            if current_power_limit == previous_power_limit:
                print_str = f"Минимальное значение Power Limit: {current_power_limit / 1000} W достигнуто"
                str_result = str_result + "\n" + print_str
                print(print_str)
                break
        self.__default_params_and_min_power_limit_collection_name = (
                    default_params_and_min_power_limit_collection_name
                    + " " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        for benchmark_test_type in self.__benchmark_tests:
            SocketCalls.call_method_of_benchmark_test_system("change_benchmark_test_type", benchmark_test_type)
            # Один запуск теста бенчмарка со сбором данных в БД (ограниченный по времени)
            res = SocketCalls.call_method_of_benchmark_test_system("run_benchmark",
                                                                   self.__default_params_and_min_power_limit_collection_name,
                                                                   self.__time_before_start_test,
                                                                   self.__time_test_running,
                                                                   self.__time_after_finish_test,
                                                                   self.__db_name_for_comparison_tests)
            if res is False:
                print_str = ("Работа теста бенчмарка типа " + benchmark_test_type +
                             " была остановлена. Данные параметры работы GPU являются нестабильными")
                str_result = str_result + "\n" + print_str
                print(print_str)
            # Запись FPS из файла лога MSI Kombustor (и эффективность [FPS/W]) в соответствующие документы коллекции MongoDB
            SocketCalls.call_method_of_benchmark_test_system("update_fps_and_efficiency_in_collection",
                                                             self.__default_params_and_min_power_limit_collection_name,
                                                             self.__db_name_for_comparison_tests)
        print_str = f"Данные для тестов бенчмарка с параметрами по умолчанию (и минимальным Power Limit: {
            current_power_limit / 1000} W) успешно собраны в БД {self.__db_name_for_comparison_tests} в коллекции {
            self.__default_params_and_min_power_limit_collection_name}"
        str_result = str_result + "\n" + print_str
        print(print_str)
        return str_result

    # Запуск тестов бенчмарка с найденными оптимальными параметрами для дальнейшего сравнения
    def __run_test_with_found_params(self, found_params_collection_name, optimal_params=None):
        # Работа с текущими оптимальными параметрами у класса системы анализа (из метода __gpu_power_model()), если не передано иное
        if optimal_params is None:
            optimal_params = self.__current_optimal_params
        str_result = ""
        print_str = "\n".join([
            "Запущен сбор данных для GPU с оптимальными параметрами:",
            f"  Лимит мощности (Вт): {optimal_params['power_limit_w']:.3f}",
            f"  Смещение частоты GPU (МГц): {optimal_params['gpu_clock_offset_mhz']:.0f}",
            f"  Смещение частоты памяти (МГц): {optimal_params['memory_clock_offset_mhz']:.0f}",
            ""
            ])
        str_result = str_result + "\n" + print_str
        print(print_str)
        # Установить значение Power Limit GPU в мВт (1 Вт = 1000 мВт)
        current_power_limit = SocketCalls.call_method_of_undervolting_gpu_system("set_tdp",
                                                                                 round(optimal_params[
                                                                                           'power_limit_w'] * 1000))
        # Вернуть значение смещения частоты GPU по умолчанию
        current_gpu_clock_offset, _ = SocketCalls.call_method_of_undervolting_gpu_system("set_gpu_clock_offset",
                                                                                         round(optimal_params[
                                                                                                   'gpu_clock_offset_mhz']))
        # Вернуть значение смещения частоты памяти по умолчанию
        current_mem_clock_offset = SocketCalls.call_method_of_undervolting_gpu_system("set_mem_clock_offset",
                                                                                      round(optimal_params[
                                                                                                'memory_clock_offset_mhz']))
        print_str = "\n".join([
            "Результат применения параметров GPU:",
            f"  Текущий лимит мощности (Вт): {current_power_limit / 1000}",
            f"  Текущее смещение частоты GPU (МГц): {current_gpu_clock_offset}",
            f"  Текущее смещение частоты памяти (МГц): {current_mem_clock_offset}",
            ""
            ])
        str_result = str_result + "\n" + print_str
        print(print_str)
        self.__found_params_collection_name = found_params_collection_name + " " + datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S")
        for benchmark_test_type in self.__benchmark_tests:
            SocketCalls.call_method_of_benchmark_test_system("change_benchmark_test_type", benchmark_test_type)
            # Один запуск теста бенчмарка со сбором данных в БД (ограниченный по времени)
            res = SocketCalls.call_method_of_benchmark_test_system("run_benchmark",
                                                                   self.__found_params_collection_name,
                                                                   self.__time_before_start_test,
                                                                   self.__time_test_running,
                                                                   self.__time_after_finish_test,
                                                                   self.__db_name_for_comparison_tests)
            if res is False:
                print_str = ("Работа теста бенчмарка типа " + benchmark_test_type +
                             " была остановлена. Данные параметры работы GPU являются нестабильными")
                str_result = str_result + "\n" + print_str
                print(print_str)
            # Запись FPS из файла лога MSI Kombustor (и эффективность [FPS/W]) в соответствующие документы коллекции MongoDB
            SocketCalls.call_method_of_benchmark_test_system("update_fps_and_efficiency_in_collection",
                                                             self.__found_params_collection_name,
                                                             self.__db_name_for_comparison_tests)
        print_str = f"Данные для тестов бенчмарка с оптимальными параметрами по умолчанию успешно собраны в БД {
            self.__db_name_for_comparison_tests} в коллекции {
            self.__found_params_collection_name}"
        str_result = str_result + "\n" + print_str
        print(print_str)
        return str_result

    # Построить две диаграммы для сравнения производительности - общее сравнение FPS и энергопотребления
    # и сравнение по типам тестов
    def __create_comparison_charts(self, found_df, default_dfs):
        # Данные для диаграмм
        general_data = []
        test_type_data = []
        # Собрать данные для общего сравнения
        for default_df, desc in default_dfs:
            # Общие показатели
            fps_change = (found_df['FPS'].mean() / default_df['FPS'].mean() - 1) * 100
            power_change = (found_df['Board Power Draw [W]'].mean() /
                            default_df['Board Power Draw [W]'].mean() - 1) * 100
            general_data.append({
                'description': desc,
                'fps': fps_change,
                'power': power_change
            })
            # Показатели по типам тестов
            for test_type in found_df['Benchmark test type'].unique():
                found_benchmark = found_df[found_df['Benchmark test type'] == test_type]
                default_benchmark = default_df[default_df['Benchmark test type'] == test_type]
                if not default_benchmark.empty:
                    fps_diff = (found_benchmark['FPS'].mean() /
                                default_benchmark['FPS'].mean() - 1) * 100
                    power_diff = (found_benchmark['Board Power Draw [W]'].mean() /
                                  default_benchmark['Board Power Draw [W]'].mean() - 1) * 100

                    test_type_data.append({
                        'test_type': test_type,
                        'description': desc,
                        'fps': fps_diff,
                        'power': power_diff
                    })
        # Диаграмма 1 - общее сравнение
        fig_general = go.Figure()
        colors = ['#1f77b4', '#ff7f0e']  # Цвета для разных конфигураций
        for i, (data, color) in enumerate(zip(general_data, colors)):
            fig_general.add_trace(go.Bar(
                x=['FPS', 'Энергопотребление'],
                y=[data['fps'], data['power']],
                name=data['description'],
                marker_color=color,
                text=[f"{data['fps']:+.1f}%", f"{data['power']:+.1f}%"],
                textposition='auto'
            ))
        fig_general.update_layout(
            title='Общее сравнение производительности',
            barmode='group',
            xaxis_title='Параметр',
            yaxis_title='Изменение, %',
            legend_title="Конфигурация"
        )
        # Диаграмма 2 - сравнение по типам тестов
        fig_tests = go.Figure()
        test_types = found_df['Benchmark test type'].unique()
        for i, test_type in enumerate(test_types):
            for j, (data, color) in enumerate(zip(general_data, colors)):
                test_data = [d for d in test_type_data
                             if d['test_type'] == test_type
                             and d['description'] == data['description']]
                if test_data:
                    fig_tests.add_trace(go.Bar(
                        x=[f"{test_type}<br>FPS", f"{test_type}<br>Питание"],
                        y=[test_data[0]['fps'], test_data[0]['power']],
                        name=f"{data['description']} ({test_type})",
                        marker_color=color,
                        text=[f"{test_data[0]['fps']:+.1f}%", f"{test_data[0]['power']:+.1f}%"],
                        textposition='auto',
                        showlegend=(i == 0)  # Показывать легенду только для первого теста
                    ))
        fig_tests.update_layout(
            title='Сравнение по типам тестов',
            barmode='group',
            xaxis_title='Тип теста и параметр',
            yaxis_title='Изменение, %',
            legend_title="Конфигурация"
        )
        fig_general.write_html(self.__plot_common_comparison_html_name)
        webbrowser.open(self.__plot_common_comparison_html_name)
        fig_tests.write_html(self.__plot_type_test_comparison_html_name)
        webbrowser.open(self.__plot_type_test_comparison_html_name)

    # Сравнение производительности по умолчанию (и при min Power Limit) и производительности с найденными оптимальными параметрами
    def __calculate_difference_between_original_and_optimal_performance(self):
        # Список коллекций и их описаний
        collections = [
            (self.__default_params_collection_name, "параметрами по умолчанию"),
            (self.__default_params_and_min_power_limit_collection_name,
             "параметрами по умолчанию и минимальным Power Limit"),
            (self.__found_params_collection_name, "найденными оптимальными параметрами")
        ]
        str_result = ""
        # Загрузка и проверка данных
        dataframes = {}
        for collection, description in collections:
            df = pd.DataFrame(list(self.__client[self.__db_name_for_comparison_tests][collection].find()))
            print_str = f"Всего {len(df)} документов в коллекции данных с сенсоров при работе GPU с {description}"
            str_result = str_result + "\n" + print_str
            print(print_str)
            if len(df) == 0 or (df := df[df["FPS"].notna()]).empty:
                print_str = f"Нет данных в коллекции {collection} для анализа и сравнения"
                str_result = str_result + "\n" + print_str
                print(print_str)
                return str_result
            print_str = f"Всего {len(df)} документов с FPS в коллекции данных с сенсоров при работе GPU с {description}"
            str_result = str_result + "\n" + print_str
            print(print_str)
            dataframes[collection] = df
        # Распаковка результатов
        default_params_df = dataframes[self.__default_params_collection_name]
        default_params_and_min_power_limit_df = dataframes[
            self.__default_params_and_min_power_limit_collection_name]
        found_params_df = dataframes[self.__found_params_collection_name]
        # Анализ и сравнение
        default_configs = [(default_params_df, "с параметрами по умолчанию"),
                           (default_params_and_min_power_limit_df, "с параметрами по умолчанию и минимальным Power Limit")
        ]
        for default_df, description in default_configs:
            print_str = "\n".join([
                "=" * 50,
                f"Сравнение данных работы GPU с оптимальными параметрами и работы GPU {description}."
                ])
            str_result = str_result + "\n" + print_str
            print(print_str)
            # Общее сравнение (все типы тестов вместе)
            fps_change = (found_params_df['FPS'].mean() / default_df['FPS'].mean() - 1) * 100
            power_change = (found_params_df['Board Power Draw [W]'].mean() / default_df[
                'Board Power Draw [W]'].mean() - 1) * 100
            print_str = "\n".join([
                f"Общие результаты (в среднем):",
                f"  Изменение FPS: {fps_change:+.2f}%",
                f"  Изменение энергопотребления: {power_change:+.2f}%",
                "Результаты по типам тестов (в среднем):"
            ])
            str_result = str_result + "\n" + print_str
            print(print_str)
            # Сравнение по каждому типу теста
            for benchmark_type in found_params_df['Benchmark test type'].unique():
                benchmark_found = found_params_df[found_params_df['Benchmark test type'] == benchmark_type]
                benchmark_default = default_df[default_df['Benchmark test type'] == benchmark_type]
                if len(benchmark_default) == 0:
                    continue
                fps_diff = (benchmark_found['FPS'].mean() / benchmark_default['FPS'].mean() - 1) * 100
                power_diff = (benchmark_found['Board Power Draw [W]'].mean() / benchmark_default[
                    'Board Power Draw [W]'].mean() - 1) * 100
                print_str = "\n".join([
                    f"{benchmark_type}:",
                    f"  Изменение FPS: {fps_diff:+.2f}%",
                    f"  Изменение энергопотребления: {power_diff:+.2f}%"
                ])
                str_result = str_result + "\n" + print_str
                print(print_str)
            print_str = "=" * 50
            str_result = str_result + "\n" + print_str
            print(print_str)
        # Вызов функции построения диаграмм
        self.__create_comparison_charts(found_params_df, default_configs)
        return str_result

    ######## Методы для взаимодействия через сокеты ########
    # Обработка вызова метода через сокеты
    def __handle_client(self, client_socket):
        try:
            # Чтение и декодирование запроса
            request = client_socket.recv(1024).decode('utf-8')
            print(f"Получено: {request}")
            # Разбиение запроса на метод и параметры
            parts = request.split(',')
            method_name = parts[0].strip()
            parameters = [p.strip() for p in parts[1:] if p.strip()]  # Убрать пустые значения и пробелы
            # Вызов соответствующего метода
            if method_name == "get_documents_from_collection_and_set_current_df":
                if parameters:
                    response = f"Для метода {method_name} параметры не требуются"
                    print(response)
                else:
                    response = self.__get_documents_from_collection_and_set_current_df()
            elif method_name == "correlation_coefficient":
                if len(parameters) != 1:
                    response = f"Метод {method_name} требует 1 параметр"
                    print(response)
                else:
                    method = parameters[0]
                    response = self.__correlation_coefficient(method)
            elif method_name == "gpu_power_model":
                if parameters:
                    response = f"Для метода {method_name} параметры не требуются"
                    print(response)
                else:
                    response = self.__gpu_power_model()
            elif method_name == "write_collection_names":
                if parameters:
                    response = f"Для метода {method_name} параметры не требуются"
                    print(response)
                else:
                    response = self.__write_collection_names()
            elif method_name == "set_default_time_and_watt_reducing_value_for_tests":
                if len(parameters) != 4:
                    response = f"Метод {method_name} требует 4 параметра"
                    print(response)
                else:
                    time_before_start_test = int(parameters[0])
                    time_test_running = int(parameters[1])
                    time_after_finish_test = int(parameters[2])
                    watt_reducing_value = int(parameters[3])
                    response = self.__set_default_time_and_watt_reducing_value_for_tests(time_before_start_test, time_test_running,
                                       time_after_finish_test, watt_reducing_value)
            elif method_name == "set_db_name_for_comparison_tests":
                if len(parameters) != 1:
                    response = f"Метод {method_name} требует 1 параметр"
                    print(response)
                else:
                    db_name_for_comparison_tests = parameters[0]
                    response = self.__set_db_name_for_comparison_tests(db_name_for_comparison_tests)
            elif method_name == "read_and_verify_collection_names":
                if parameters:
                    response = f"Для метода {method_name} параметры не требуются"
                    print(response)
                else:
                    response = self.__read_and_verify_collection_names()
            elif method_name == "run_test_with_default_params":
                if len(parameters) != 1:
                    response = f"Метод {method_name} требует 1 параметр"
                    print(response)
                else:
                    default_params_collection_name = parameters[0]
                    response = self.__run_test_with_default_params(default_params_collection_name)
            elif method_name == "run_test_with_default_params_and_min_power_limit":
                if len(parameters) != 1:
                    response = f"Метод {method_name} требует 1 параметр"
                    print(response)
                else:
                    default_params_and_min_power_limit_collection_name = parameters[0]
                    response = self.__run_test_with_default_params_and_min_power_limit(default_params_and_min_power_limit_collection_name)
            elif method_name == "run_test_with_found_params":
                if len(parameters) != 1:
                    response = f"Метод {method_name} требует 1 параметр"
                    print(response)
                else:
                    found_params_collection_name = parameters[0]
                    response = self.__run_test_with_found_params(found_params_collection_name)
            elif method_name == "calculate_difference_between_original_and_optimal_performance":
                if parameters:
                    response = f"Для метода {method_name} параметры не требуются"
                    print(response)
                else:
                    response = self.__calculate_difference_between_original_and_optimal_performance()
            else:
                response = f"Неизвестный метод {method_name}"
                print(response)
            # Преобразование response в строку, если оно является типа bool или int
            if isinstance(response, (bool, int)):
                response = str(response)
            elif isinstance(response, tuple):
                # Преобразовать кортеж в строку
                response = ', '.join(map(str, response))
            elif response is None:
                response = "None"
            # Отправка ответа клиенту
            client_socket.send(response.encode('utf-8'))
        except Exception as e:
            print(f"Ошибка обработки клиента: {e}")
            response = "Ошибка сервера"
            client_socket.send(response.encode('utf-8'))
        finally:
            # Закрытие соединения
            client_socket.close()

    def run(self):
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.bind((self.__address, self.__port))
        server.listen(5)
        print("Сервер системы анализа данных для построения модели питания GPU запущен и ожидает подключения клиентов...")
        while True:
            client_socket, addr = server.accept()
            print(f"Подключен клиент: {addr}")
            client_handler = threading.Thread(target=self.__handle_client, args=(client_socket,))
            client_handler.start()


system = DataAnalysisSystem()
system.run()