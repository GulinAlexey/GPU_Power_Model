import pymongo
import pandas as pd
import statsmodels.api as sm


class MainAnalyseData:
    def __init__(self):
        self.__client = pymongo.MongoClient("mongodb://localhost:27017/")  # Адрес сервера MongoDB
        self.__db = self.__client["gpu_benchmark_monitoring"]  # Название базы данных
        # Список всех коллекций с данными в БД
        self.__collections = []
        for collection_name in self.__db.list_collection_names():
            self.__collections.append(self.__db[collection_name])

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
            X = subset[["Power Limit [W]", "GPU Clock Frequency Offset [MHz]", "Memory Clock Offset [MHz]"]]
            y = subset["FPS"]
            # Добавить константу для линейной регрессии
            X = sm.add_constant(X)
            # Построить модель
            model = sm.OLS(y, X).fit() # Модель линейной регрессии с использованием метода наименьших квадратов (OLS)
            # Сохранить результаты
            results[benchmark] = model.summary()
        # Вывести результаты для каждого типа бенчмарка
        for benchmark, summary in results.items():
            print(f"Результаты для типа теста бенчмарка '{benchmark}':\n{summary}\n")

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
        self.__correlation_coefficient(df, 'pearson')
        self.__correlation_coefficient(df, 'kendall')
        self.__correlation_coefficient(df, 'spearman')
        self.__regression_analysis(df)


main = MainAnalyseData()
main.main_loop()
