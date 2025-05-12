from SocketCalls import SocketCalls


class MainAnalyseData:
    def __init__(self):
        # Название БД с данными для сравнения производительности исходной и с найденными оптимальными параметрами
        self.__db_name_for_comparison_tests = "gpu_benchmark_comparison"
        # Имя коллекции БД с оптимальными параметрами
        self.__found_params_collection_name = "gpu_data_found_params"
        # Имена коллекций БД с параметрами по умолчанию
        self.__default_params_collection_name = "gpu_data_default_params"
        self.__default_params_and_min_power_limit_collection_name = "gpu_data_default_params_and_min_power_limit"
        # Параметры запуска тестов для сравнения производительности по умолчанию и производительности с оптимальными параметрами
        # Параметры времени теста (в секундах)
        self.__time_before_start_test = 5
        self.__time_test_running = 30
        self.__time_after_finish_test = 10
        # Параметр уменьшения power limit для достижения минимального значения (для сбора данных и дальнейшего сравнения с оптим.)
        self.__watt_reducing_value = 5  # Величина уменьшения Power Limit за один тест (в W)

    def main_loop(self):
        print(SocketCalls.call_method_of_data_analysis_system("get_documents_from_collection_and_set_current_df"))
        print(SocketCalls.call_method_of_data_analysis_system("correlation_coefficient", 'pearson'))
        print(SocketCalls.call_method_of_data_analysis_system("correlation_coefficient", 'kendall'))
        print(SocketCalls.call_method_of_data_analysis_system("correlation_coefficient", 'spearman'))
        # Построить модель и предсказать оптимальные параметры
        print(SocketCalls.call_method_of_data_analysis_system("gpu_power_model"))
        # Задать параметры времени тестов и величины уменьшения Power Limit для сбора данных и анализа
        SocketCalls.call_method_of_data_analysis_system("set_default_time_and_watt_reducing_value_for_tests", self.__time_before_start_test,
                                                        self.__time_test_running, self.__time_after_finish_test, self.__watt_reducing_value)
        SocketCalls.call_method_of_data_analysis_system("set_db_name_for_comparison_tests",
                                                        self.__db_name_for_comparison_tests)
        # Флаг, что повторно собирать коллекции с параметрами по умолчанию не нужно
        comparison_collections_already_existed = SocketCalls.call_method_of_data_analysis_system("read_and_verify_collection_names")
        if comparison_collections_already_existed:
            print("Сбор данных о производительности GPU по умолчанию не требуется, коллекции были собраны ранее")
        else:
            print("Начат сбор данных о производительности GPU по умолчанию")
            print(SocketCalls.call_method_of_data_analysis_system("run_test_with_default_params", self.__default_params_collection_name))
            print(SocketCalls.call_method_of_data_analysis_system("run_test_with_default_params_and_min_power_limit", self.__default_params_and_min_power_limit_collection_name))
            print(SocketCalls.call_method_of_data_analysis_system("write_collection_names")) # Сохранить значения имён коллекций в файл
        # Собрать данные работы GPU с найденными оптимальными параметрами
        print(SocketCalls.call_method_of_data_analysis_system("run_test_with_found_params", self.__found_params_collection_name))
        # Сравнение производительности по умолчанию (и при min Power Limit) и производительности с найденными оптимальными параметрами
        print(SocketCalls.call_method_of_data_analysis_system("calculate_difference_between_original_and_optimal_performance"))


main = MainAnalyseData()
main.main_loop()
