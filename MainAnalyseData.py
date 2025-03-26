import pymongo
import pandas as pd


class MainAnalyseData:
    def __init__(self):
        self.__client = pymongo.MongoClient("mongodb://localhost:27017/")  # Адрес сервера MongoDB
        self.__db = self.__client["gpu_benchmark_monitoring"]  # Название базы данных
        self.__collection = self.__db["gpu_benchmark_monitoring.gpu_data 2025-03-25 01:01:34"] # TODO пример конкретной коллекции

    def main_loop(self):
        # Получить все документы из коллекции
        documents = list(self.__collection.find())
        # Преобразовать данные в DataFrame
        df = pd.DataFrame(documents)
        print(f"Всего {len(df)} документов")
        # Оставить только те документы, где FPS не пустой (и не None)
        df = df[df["FPS"].notna()]
        print(f"Всего {len(df)} документов с FPS")
        # Выбрать параметры для анализа
        correlation_columns = ["Power Limit [W]", "GPU Clock Frequency Offset [MHz]", "Memory Clock Offset [MHz]", "FPS"]
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
                correlation_matrix = benchmark_data[correlation_columns].corr()
                fps_correlation = correlation_matrix["FPS"]  # Взять корреляции FPS с остальными параметрами
                correlations[benchmark] = fps_correlation.drop("FPS").to_dict()
        # Вывести результаты
        for benchmark, correlation in correlations.items():
            print(f"Benchmark test type: {benchmark}")
            for param, corr_value in correlation.items():
                print(f"  {param}: {corr_value:.4f}")


main = MainAnalyseData()
main.main_loop()
