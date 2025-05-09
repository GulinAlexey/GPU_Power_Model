import pymongo
import pandas as pd
import statsmodels.api as sm
import numpy as np
import lightgbm as lgb
import optuna
from sklearn.model_selection import train_test_split
from sklearn.metrics import r2_score, mean_absolute_error
from sklearn.preprocessing import MinMaxScaler
import plotly.graph_objects as go
from sklearn.preprocessing import LabelEncoder
from datetime import datetime
import os
from ParameterOptimizer import ParameterOptimizer
import SocketCalls
optuna.logging.set_verbosity(optuna.logging.WARNING)  # Отключить INFO-сообщения


class MainAnalyseData:
    def __init__(self):
        # Список типов тестов бенчмарка для запуска и сбора данных (выполняются по очереди)
        self.__benchmark_tests = ["gltessyspherex32", "glpbrdonut", "glphongdonut", "glmsi01", "glfurrytorus",
                                  "glfurrymsi",
                                  "glmsi02gpumedium"]
        # Название БД с данными для сравнения производительности исходной и с найденными оптимальными параметрами
        self.__db_name_for_comparison_tests = "gpu_benchmark_comparison"
        # Имя коллекции БД с оптимальными параметрами
        self.__found_params_collection_name = "gpu_data_found_params"
        # Имена коллекций БД с параметрами по умолчанию
        self.__default_params_collection_name = "gpu_data_default_params"
        self.__default_params_and_min_power_limit_collection_name = "gpu_data_default_params_and_min_power_limit"
        # Имя файла с именами коллекций, чтобы не собирать повторно
        self.__collection_names_file_path = "comparison_collection_names_for_analysis.txt"
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
        # Параметры запуска тестов для сравнения производительности по умолчанию и производительности с оптимальными параметрами
        # Параметры времени теста (в секундах)
        self.__time_before_start_test = 5
        self.__time_test_running = 30
        self.__time_after_finish_test = 10
        # Параметры уменьшения power limit для достижения минимального значения (для сбора данных и дальнейшего сравнения с оптим.)
        watt_reducing_value = 5  # Величина уменьшения Power Limit за один тест (в W)
        self.__milliwatt_reducing_value = watt_reducing_value * 1000

    # Определить коэффициент корреляции между FPS и изменяемыми параметрами работы GPU
    @staticmethod
    def __correlation_coefficient(df, method='pearson'):
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
        print("=" * 50)
        print("Коэффициент корреляции " + method)
        for benchmark, correlation in correlations.items():
            print(f"Тип теста бенчмарка: {benchmark}")
            for param, corr_value in correlation.items():
                print(f"  {param}: {corr_value:.4f}")

    @staticmethod
    def __regression_analysis(df):
        columns = ["Benchmark test type", "Power Limit [W]",
                   "GPU Clock Frequency Offset [MHz]", "Memory Clock Offset [MHz]", "FPS"]
        benchmark_types = df["Benchmark test type"].unique()
        results = {}
        for benchmark in benchmark_types:
            # Фильтрация данных по типу теста бенчмарка
            subset = df[df["Benchmark test type"] == benchmark]
            # Убрать строки с пропущенными значениями
            subset = subset.dropna(subset=columns)
            # Определить зависимую и независимые переменные
            x = subset[["Power Limit [W]", "GPU Clock Frequency Offset [MHz]", "Memory Clock Offset [MHz]"]]
            y = subset["FPS"]
            # Добавить константу для линейной регрессии
            x = sm.add_constant(x)
            # Построить модель
            model = sm.OLS(y, x).fit() # Модель линейной регрессии с использованием метода наименьших квадратов (OLS)
            # Сохранить результаты
            results[benchmark] = model.summary()
        # Вывести результаты для каждого типа бенчмарка
        for benchmark, summary in results.items():
            print(f"Результаты для типа теста бенчмарка '{benchmark}':\n{summary}\n")

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
        train_data = lgb.Dataset(
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
        model = lgb.train(params, train_data)
        # Оценка
        prediction = model.predict(x_test)
        r2 = r2_score(y_test, prediction)
        mae = mean_absolute_error(y_test, prediction)

        return model, {'r2': r2, 'mae': mae}

    # Анализ важности признаков
    @staticmethod
    def __plot_feature_importance(model):
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
        fig.show()

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

    def __gpu_power_model(self, data):
        # Предобработка
        df = self.__preprocess_data(data)
        # Обучение модели
        model, metrics = self.__train_fps_model(df)
        print(f"Метрики модели: R2={metrics['r2']:.3f}, MAE={metrics['mae']:.1f}")
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
                print(f"Ошибка для теста {test_type_str}: {str(e)}")
                continue
        # Получить минимальные и максимальные значения параметров
        param_ranges = {
            'power_limit_w': (self.__scaler.data_min_[0], self.__scaler.data_max_[0]),
            'gpu_clock_offset_mhz': (self.__scaler.data_min_[1], self.__scaler.data_max_[1]),
            'memory_clock_offset_mhz': (self.__scaler.data_min_[2], self.__scaler.data_max_[2])
        }
        print("\nДиапазоны параметров:")
        print(f"  Лимит мощности: {param_ranges['power_limit_w'][0]:.0f}-{param_ranges['power_limit_w'][1]:.0f} Вт")
        print(
            f"  Смещение частоты GPU: {param_ranges['gpu_clock_offset_mhz'][0]:.0f}-{param_ranges['gpu_clock_offset_mhz'][1]:.0f} МГц")
        print(
            f"  Смещение частоты памяти: {param_ranges['memory_clock_offset_mhz'][0]:.0f}-{param_ranges['memory_clock_offset_mhz'][1]:.0f} МГц")
        print("\nОптимальные параметры:")
        for test_type, params in results.items():
            # Преобразовать параметры в оригинальный диапазон
            original_params = self.__denormalize_params(params)
            print(f"\nТест: {test_type}")
            print(f"  Лимит мощности (Вт): {original_params['power_limit_w']:.3f}")
            print(f"  Смещение частоты GPU (МГц): {original_params['gpu_clock_offset_mhz']:.0f}")
            print(f"  Смещение частоты памяти (МГц): {original_params['memory_clock_offset_mhz']:.0f}")
        # Добавлен вывод усредненных параметров для всех тестов
        avg_original_params = self.__find_optimal_for_all_tests(results)
        if avg_original_params:
            print("\nУсредненные оптимальные параметры для всех тестов:")
            print(f"  Лимит мощности (Вт): {avg_original_params['power_limit_w']:.3f}")
            print(f"  Смещение частоты GPU (МГц): {avg_original_params['gpu_clock_offset_mhz']:.0f}")
            print(f"  Смещение частоты памяти (МГц): {avg_original_params['memory_clock_offset_mhz']:.0f}")
        return model, results, avg_original_params

    # Записать имена коллекций с тестами параметров GPU по умолчанию (чтобы не собирать повторно)
    def __write_collection_names(self):
        # Записать имена коллекций в файл (предварительно очищая его)
        with open(self.__collection_names_file_path, 'w') as file:
            file.write(f"{self.__default_params_collection_name}\n")
            file.write(f"{self.__default_params_and_min_power_limit_collection_name}\n")
        print(f"Имена коллекций записаны в {self.__collection_names_file_path}")

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
    def __run_test_with_default_params(self):
        print("Запущен сбор данных для GPU с параметрами работы по умолчанию")
        # Вернуть значение Power Limit GPU по умолчанию
        _ = SocketCalls.call_method_of_undervolting_gpu_system("set_tdp_to_default")
        # Вернуть значение смещения частоты GPU по умолчанию
        _, _ = SocketCalls.call_method_of_undervolting_gpu_system("set_gpu_clock_offset_to_default")
        # Вернуть значение смещения частоты памяти по умолчанию
        _ = SocketCalls.call_method_of_undervolting_gpu_system("set_mem_clock_offset_to_default")
        self.__default_params_collection_name = self.__default_params_collection_name + " " + datetime.now().strftime("%Y-%m-%d %H:%M:%S")
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
                print("Работа теста бенчмарка типа " + benchmark_test_type + " была остановлена. Данные параметры работы GPU являются нестабильными")
            # Запись FPS из файла лога MSI Kombustor (и эффективность [FPS/W]) в соответствующие документы коллекции MongoDB
            SocketCalls.call_method_of_benchmark_test_system("update_fps_and_efficiency_in_collection",
                                                             self.__default_params_collection_name, self.__db_name_for_comparison_tests)
        print("Данные для тестов бенчмарка с параметрами по умолчанию успешно собраны в БД " +
              self.__db_name_for_comparison_tests + " в коллекции " + self.__default_params_collection_name)

    # Запуск тестов бенчмарка с параметрами по умолчанию (и min power limit) для дальнейшего сравнения
    def __run_test_with_default_params_and_min_power_limit(self):
        print("Запущен сбор данных для GPU с параметрами работы по умолчанию и минимальным Power Limit")
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
                print(
                    f"Минимальное значение Power Limit: {current_power_limit / 1000} W достигнуто")
                break
        self.__default_params_and_min_power_limit_collection_name = (self.__default_params_and_min_power_limit_collection_name
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
                print("Работа теста бенчмарка типа " + benchmark_test_type
                      + " была остановлена. Данные параметры работы GPU являются нестабильными")
            # Запись FPS из файла лога MSI Kombustor (и эффективность [FPS/W]) в соответствующие документы коллекции MongoDB
            SocketCalls.call_method_of_benchmark_test_system("update_fps_and_efficiency_in_collection",
                                                             self.__default_params_and_min_power_limit_collection_name,
                                                             self.__db_name_for_comparison_tests)
        print(f"Данные для тестов бенчмарка с параметрами по умолчанию (и минимальным Power Limit: {
            current_power_limit / 1000} W) успешно собраны в БД {self.__db_name_for_comparison_tests} в коллекции {
            self.__default_params_and_min_power_limit_collection_name}")

    # Запуск тестов бенчмарка с найденными оптимальными параметрами для дальнейшего сравнения
    def __run_test_with_found_params(self, optimal_params):
        print("Запущен сбор данных для GPU с оптимальными параметрами:")
        print(f"  Лимит мощности (Вт): {optimal_params['power_limit_w']:.3f}")
        print(f"  Смещение частоты GPU (МГц): {optimal_params['gpu_clock_offset_mhz']:.0f}")
        print(f"  Смещение частоты памяти (МГц): {optimal_params['memory_clock_offset_mhz']:.0f}")
        print("")
        # Установить значение Power Limit GPU в мВт (1 Вт = 1000 мВт)
        current_power_limit = SocketCalls.call_method_of_undervolting_gpu_system("set_tdp",
                                                                                 round(optimal_params['power_limit_w'] * 1000))
        # Вернуть значение смещения частоты GPU по умолчанию
        current_gpu_clock_offset, _ = SocketCalls.call_method_of_undervolting_gpu_system("set_gpu_clock_offset",
                                                                                         round(optimal_params['gpu_clock_offset_mhz']))
        # Вернуть значение смещения частоты памяти по умолчанию
        current_mem_clock_offset = SocketCalls.call_method_of_undervolting_gpu_system("set_mem_clock_offset",
                                                                                      round(optimal_params['memory_clock_offset_mhz']))
        print("Результат применения параметров GPU:")
        print(f"  Текущий лимит мощности (Вт): {current_power_limit / 1000}")
        print(f"  Текущее смещение частоты GPU (МГц): {current_gpu_clock_offset}")
        print(f"  Текущее смещение частоты памяти (МГц): {current_mem_clock_offset}")
        print("")
        self.__found_params_collection_name = self.__found_params_collection_name + " " + datetime.now().strftime("%Y-%m-%d %H:%M:%S")
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
                print("Работа теста бенчмарка типа " + benchmark_test_type
                      + " была остановлена. Данные параметры работы GPU являются нестабильными")
            # Запись FPS из файла лога MSI Kombustor (и эффективность [FPS/W]) в соответствующие документы коллекции MongoDB
            SocketCalls.call_method_of_benchmark_test_system("update_fps_and_efficiency_in_collection",
                                                             self.__found_params_collection_name, self.__db_name_for_comparison_tests)
        print(f"Данные для тестов бенчмарка с оптимальными параметрами по умолчанию успешно собраны в БД {
            self.__db_name_for_comparison_tests} в коллекции {
            self.__found_params_collection_name}")

    # Сравнение производительности по умолчанию (и при min Power Limit) и производительности с найденными оптимальными параметрами
    def __calculate_difference_between_original_and_optimal_performance(self):
        # Список коллекций и их описаний
        collections = [
            (self.__default_params_collection_name, "параметрами по умолчанию"),
            (self.__default_params_and_min_power_limit_collection_name,
             "параметрами по умолчанию и минимальным Power Limit"),
            (self.__found_params_collection_name, "найденными оптимальными параметрами")
        ]
        # Загрузка и проверка данных
        dataframes = {}
        for collection, description in collections:
            df = pd.DataFrame(list(self.__client[self.__db_name_for_comparison_tests][collection].find()))
            print(f"Всего {len(df)} документов в коллекции данных с сенсоров при работе GPU с {description}")
            if len(df) == 0 or (df := df[df["FPS"].notna()]).empty:
                print(f"Нет данных в коллекции {collection} для анализа и сравнения")
                return False
            print(f"Всего {len(df)} документов с FPS в коллекции данных с сенсоров при работе GPU с {description}")
            dataframes[collection] = df
        # Распаковка результатов
        default_params_df = dataframes[self.__default_params_collection_name]
        default_params_and_min_power_limit_df = dataframes[self.__default_params_and_min_power_limit_collection_name]
        found_params_df = dataframes[self.__found_params_collection_name]
        # Анализ и сравнение
        for default_df, description in [(default_params_df,
                                         "с параметрами по умолчанию"),
                                        (default_params_and_min_power_limit_df,
                                         "с параметрами по умолчанию и минимальным Power Limit")]:
            print("=" * 50)
            print(f"Сравнение данных работы GPU с оптимальными параметрами и работы GPU {description}.")
            # Общее сравнение (все типы тестов вместе)
            fps_change = (found_params_df['FPS'].mean() / default_df['FPS'].mean() - 1) * 100
            power_change = (found_params_df['Board Power Draw [W]'].mean() / default_df[
                'Board Power Draw [W]'].mean() - 1) * 100
            print(f"Общие результаты (в среднем):")
            print(f"  Изменение FPS: {fps_change:+.2f}%")
            print(f"  Изменение энергопотребления: {power_change:+.2f}%")
            # Сравнение по каждому типу теста
            print("Результаты по типам тестов (в среднем):")
            for benchmark_type in found_params_df['Benchmark test type'].unique():
                benchmark_found = found_params_df[found_params_df['Benchmark test type'] == benchmark_type]
                benchmark_default = default_df[default_df['Benchmark test type'] == benchmark_type]
                if len(benchmark_default) == 0:
                    continue
                fps_diff = (benchmark_found['FPS'].mean() / benchmark_default['FPS'].mean() - 1) * 100
                power_diff = (benchmark_found['Board Power Draw [W]'].mean() / benchmark_default[
                    'Board Power Draw [W]'].mean() - 1) * 100
                print(f"{benchmark_type}:")
                print(f"  Изменение FPS: {fps_diff:+.2f}%")
                print(f"  Изменение энергопотребления: {power_diff:+.2f}%")
            print("=" * 50)
        return True

    def main_loop(self):
        # Получить все документы из коллекции
        all_documents = []
        for collection in self.__collections:
            documents = list(collection.find())
            all_documents.extend(documents)  # Добавить документы в общий список
        # Преобразовать данные в DataFrame
        df = pd.DataFrame(all_documents)
        print(f"Всего {len(df)} документов")
        # Оставить только те документы, где FPS не пустой (и не None)
        df = df[df["FPS"].notna()]
        print(f"Всего {len(df)} документов с FPS")
        # self.__correlation_coefficient(df, 'pearson')
        # self.__correlation_coefficient(df, 'kendall')
        # self.__correlation_coefficient(df, 'spearman')
        # self.__regression_analysis(df)
        # Построить модель и предсказать оптимальные параметры
        model, results, optimal_params = self.__gpu_power_model(df)
        # Флаг, что повторно собирать коллекции с параметрами по умолчанию не нужно
        comparison_collections_already_existed = self.__read_and_verify_collection_names()
        if comparison_collections_already_existed:
            print("Сбор данных о производительности GPU по умолчанию не требуется, коллекции были собраны ранее")
        else:
            print("Начат сбор данных о производительности GPU по умолчанию")
            self.__run_test_with_default_params()
            self.__run_test_with_default_params_and_min_power_limit()
            self.__write_collection_names() # Сохранить значения имён коллекций в файл
        # Собрать данные работы GPU с найденными оптимальными параметрами
        self.__run_test_with_found_params(optimal_params)
        # Сравнение производительности по умолчанию (и при min Power Limit) и производительности с найденными оптимальными параметрами
        if not self.__calculate_difference_between_original_and_optimal_performance():
            print("Отсутствуют данные в коллекциях для анализа и сравнения")


main = MainAnalyseData()
main.main_loop()
