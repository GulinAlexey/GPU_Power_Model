from datetime import datetime
import SocketSystem
from SensorDataCollectionSystem import SensorDataCollectionSystem
from BenchmarkTestSystem import BenchmarkTestSystem
from UndervoltingGpuSystem import UndervoltingGpuSystem


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
            self.__change_benchmark_test_type(benchmark_test_type)
            # Вернуть параметры работы GPU и памяти по умолчанию
            current_power_limit = self.__set_tdp_to_default()  # Вернуть значение Power Limit GPU по умолчанию
            previous_power_limit = None
            self.__print_tdp_info()  # Вывод данных о TDP и Power Limit
            self.__set_mem_clock_offset_to_default()  # Вернуть значение смещения частоты памяти по умолчанию

            # Цикл андервольтинга и тестирования
            # Цикл снижения Power Limit
            while True:
                current_max_gpu_clock = self.__set_gpu_clock_offset_to_default()  # Вернуть значение смещения частоты GPU по умолчанию
                self.__print_gpu_clock_info()
                previous_gpu_clock_offset = self.__current_gpu_clock_offset
                # Цикл повышения частоты GPU
                while True:
                    self.__set_mem_clock_offset_to_default()  # Вернуть значение смещения частоты памяти по умолчанию
                    # Цикл повышения частоты памяти
                    while True:
                        # Один запуск теста бенчмарка со сбором данных в MongoDB (ограниченный по времени)
                        res = self.__run_benchmark(collection, self.__benchmark_start_command, time_before_start_test,
                                                   time_test_running, time_after_finish_test)
                        if res is False:
                            print(
                                "Работа теста бенчмарка типа " + benchmark_test_type + " была остановлена. Данные параметры работы GPU являются нестабильными")
                            print(f"Текущее значение Power Limit: {current_power_limit / 1000} W")
                            if previous_power_limit is not None:
                                print(f"Предыдущее значение Power Limit: {previous_power_limit / 1000} W")
                            print(f"Текущее значение смещения частоты GPU: {self.__current_gpu_clock_offset} MHz")
                            print(f"Предыдущее значение смещения частоты GPU: {previous_gpu_clock_offset} MHz")
                            print(f"Значение смещения частоты памяти: {self.__current_mem_clock_offset} MHz")
                            break
                        # Запись FPS из файла лога MSI Kombustor (и эффективность [FPS/W]) в соответствующие документы коллекции MongoDB
                        self.__update_fps_and_efficiency_in_collection(self.__benchmark_log_path, collection)
                        # Увеличить частоту памяти для прохождения следующего теста бенчмарка
                        self.__increase_mem_clock_offset(mem_megahertz_increasing_value)
                        if self.__current_mem_clock_offset >= custom_max_mem_clock_offset:
                            print(
                                f"Максимальное значение смещения частоты памяти: {self.__current_mem_clock_offset - mem_megahertz_increasing_value
                                } MHz достигнуто, все возможные тесты типа {benchmark_test_type
                                } для смещения частоты {self.__current_gpu_clock_offset} MHz и Power Limit {current_power_limit} W пройдены")
                            break
                    # Увеличить частоту GPU для прохождения следующего теста бенчмарка
                    previous_gpu_clock_offset = self.__current_gpu_clock_offset
                    previous_max_gpu_clock = current_max_gpu_clock
                    current_max_gpu_clock = self.__increase_gpu_clock_offset(gpu_megahertz_increasing_value)
                    if current_max_gpu_clock == previous_max_gpu_clock or self.__current_gpu_clock_offset >= custom_max_gpu_clock_offset:
                        print(f"Максимальное значение смещения частоты GPU: {previous_gpu_clock_offset
                        } MHz достигнуто, все возможные тесты типа {benchmark_test_type} для {current_power_limit} W пройдены")
                        break
                # Уменьшить Power Limit GPU для прохождения следующего теста бенчмарка
                previous_power_limit = current_power_limit
                current_power_limit = self.__reduce_tdp(milliwatt_reducing_value)
                if current_power_limit == previous_power_limit:
                    print(
                        f"Минимальное значение Power Limit: {current_power_limit / 1000} W достигнуто, все возможные тесты типа {benchmark_test_type} пройдены")
                    break


main = MainTestAndCollectData()
main.main_loop()
