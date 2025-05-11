from SocketCalls import SocketCalls


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

        # Параметры запуска тестов для сравнения производительности по умолчанию и производительности с оптимальными параметрами
        # Параметры времени теста (в секундах)
        self.__time_before_start_test = 5
        self.__time_test_running = 30
        self.__time_after_finish_test = 10
        # Параметры уменьшения power limit для достижения минимального значения (для сбора данных и дальнейшего сравнения с оптим.)
        watt_reducing_value = 5  # Величина уменьшения Power Limit за один тест (в W)
        self.__milliwatt_reducing_value = watt_reducing_value * 1000

    def main_loop(self):

        # self.__correlation_coefficient(df, 'pearson')
        # self.__correlation_coefficient(df, 'kendall')
        # self.__correlation_coefficient(df, 'spearman')
        # self.__regression_analysis(df)
        # Построить модель и предсказать оптимальные параметры
        model, results, optimal_params = self.__gpu_power_model(df)
        # Флаг, что повторно собирать коллекции с параметрами по умолчанию не нужно
        comparison_collections_already_existed = SocketCalls.call_method_of_data_analysis_system("read_and_verify_collection_names")
        if comparison_collections_already_existed:
            print("Сбор данных о производительности GPU по умолчанию не требуется, коллекции были собраны ранее")
        else:
            print("Начат сбор данных о производительности GPU по умолчанию")
            SocketCalls.call_method_of_data_analysis_system("run_test_with_default_params")
            SocketCalls.call_method_of_data_analysis_system("run_test_with_default_params_and_min_power_limit")
            SocketCalls.call_method_of_data_analysis_system("write_collection_names") # Сохранить значения имён коллекций в файл
        # Собрать данные работы GPU с найденными оптимальными параметрами
        self.__run_test_with_found_params(optimal_params)
        # Сравнение производительности по умолчанию (и при min Power Limit) и производительности с найденными оптимальными параметрами
        if not self.__calculate_difference_between_original_and_optimal_performance():
            print("Отсутствуют данные в коллекциях для анализа и сравнения")


main = MainAnalyseData()
main.main_loop()
