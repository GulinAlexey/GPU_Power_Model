from datetime import datetime
import SocketCalls


class MainTestAndCollectData:
    def __init__(self):
        self.__collection_name = "gpu_data" + " " + datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Параметры времени теста (в секундах)
        self.__time_before_start_test = 5
        self.__time_test_running = 30
        self.__time_after_finish_test = 10

        watt_reducing_value = 5  # Величина уменьшения Power Limit за один тест (в W)
        self.__milliwatt_reducing_value = watt_reducing_value * 1000

        # Вручную установленное max значение для смещения частоты GPU (определяется вручную на основе тестов, чтобы избежать повторного отказа видеокарты и перезагрузки при тестах)
        # Если ручное ограничение не нужно, установить custom_max_gpu_clock = float('inf')
        self.__custom_max_gpu_clock_offset = 250

        self.__gpu_megahertz_increasing_value = 50  # Величина увеличения смещения частоты GPU за один тест (в MHz)
        self.__mem_megahertz_increasing_value = 200  # Величина увеличения смещения частоты памяти за один тест (в MHz)

        # Вручную установленное max значение для смещения частоты GPU (определяется вручную на основе тестов, чтобы избежать повторного отказа видеокарты и перезагрузки при тестах)
        # Если ручное ограничение не нужно, установить custom_max_gpu_clock = float('inf')
        self.__custom_max_mem_clock_offset = 650

        # Список типов тестов бенчмарка для запуска и сбора данных (выполняются по очереди)
        self.__benchmark_tests = ["glfurrytorus", "glfurrymsi", "glmsi01", "glmsi02gpumedium", "glphongdonut",
                                  "glpbrdonut",
                                  "gltessyspherex32"]

    def main_loop(self):
        # Сбор данных для нескольких разных типов тестов бенчмарка
        for benchmark_test_type in self.__benchmark_tests:
            SocketCalls.call_method_of_benchmark_test_system("change_benchmark_test_type", benchmark_test_type)
            # Вернуть значение Power Limit GPU по умолчанию
            current_power_limit = SocketCalls.call_method_of_undervolting_gpu_system("set_tdp_to_default")
            previous_power_limit = None
            print(SocketCalls.call_method_of_sensor_data_collection_system("print_tdp_info")) # Вывод данных о TDP и Power Limit

            # Цикл андервольтинга и тестирования
            # Цикл снижения Power Limit
            while True:
                # Вернуть значение смещения частоты GPU по умолчанию
                current_gpu_clock_offset, current_max_gpu_clock = SocketCalls.call_method_of_undervolting_gpu_system("set_gpu_clock_offset_to_default")
                SocketCalls.call_method_of_undervolting_gpu_system("print_gpu_clock_info")
                previous_gpu_clock_offset = current_gpu_clock_offset
                # Цикл повышения частоты GPU
                while True:
                    # Вернуть значение смещения частоты памяти по умолчанию
                    current_mem_clock_offset = SocketCalls.call_method_of_undervolting_gpu_system("set_mem_clock_offset_to_default")
                    # Цикл повышения частоты памяти
                    while True:
                        # Один запуск теста бенчмарка со сбором данных в БД (ограниченный по времени)
                        res = SocketCalls.call_method_of_benchmark_test_system("run_benchmark",
                                                                               self.__collection_name,
                                                                               self.__time_before_start_test,
                                                                               self.__time_test_running,
                                                                               self.__time_after_finish_test)
                        if res is False:
                            print(
                                "Работа теста бенчмарка типа " + benchmark_test_type + " была остановлена. Данные параметры работы GPU являются нестабильными")
                            print(f"Текущее значение Power Limit: {current_power_limit / 1000} W")
                            if previous_power_limit is not None:
                                print(f"Предыдущее значение Power Limit: {previous_power_limit / 1000} W")
                            print(f"Текущее значение смещения частоты GPU: {current_gpu_clock_offset} MHz")
                            print(f"Предыдущее значение смещения частоты GPU: {previous_gpu_clock_offset} MHz")
                            print(f"Значение смещения частоты памяти: {current_mem_clock_offset} MHz")
                            break
                        # Запись FPS из файла лога MSI Kombustor (и эффективность [FPS/W]) в соответствующие документы коллекции MongoDB
                        SocketCalls.call_method_of_benchmark_test_system("update_fps_and_efficiency_in_collection", self.__collection_name)
                        # Увеличить частоту памяти для прохождения следующего теста бенчмарка
                        current_mem_clock_offset = SocketCalls.call_method_of_undervolting_gpu_system("increase_mem_clock_offset", self.__mem_megahertz_increasing_value)
                        if current_mem_clock_offset >= self.__custom_max_mem_clock_offset:
                            print(
                                f"Максимальное значение смещения частоты памяти: {current_mem_clock_offset - self.__mem_megahertz_increasing_value
                                } MHz достигнуто, все возможные тесты типа {benchmark_test_type
                                } для смещения частоты {current_gpu_clock_offset} MHz и Power Limit {current_power_limit} W пройдены")
                            break
                    # Увеличить частоту GPU для прохождения следующего теста бенчмарка
                    previous_gpu_clock_offset = current_gpu_clock_offset
                    previous_max_gpu_clock = current_max_gpu_clock
                    current_gpu_clock_offset, current_max_gpu_clock = SocketCalls.call_method_of_undervolting_gpu_system(
                        "increase_gpu_clock_offset", self.__gpu_megahertz_increasing_value)
                    if current_max_gpu_clock == previous_max_gpu_clock or current_gpu_clock_offset >= self.__custom_max_gpu_clock_offset:
                        print(f"Максимальное значение смещения частоты GPU: {previous_gpu_clock_offset
                        } MHz достигнуто, все возможные тесты типа {benchmark_test_type} для {current_power_limit} W пройдены")
                        break
                # Уменьшить Power Limit GPU для прохождения следующего теста бенчмарка
                previous_power_limit = current_power_limit
                current_power_limit = SocketCalls.call_method_of_undervolting_gpu_system("reduce_tdp", self.__milliwatt_reducing_value)
                if current_power_limit == previous_power_limit:
                    print(
                        f"Минимальное значение Power Limit: {current_power_limit / 1000} W достигнуто, все возможные тесты типа {benchmark_test_type} пройдены")
                    break


main = MainTestAndCollectData()
main.main_loop()
