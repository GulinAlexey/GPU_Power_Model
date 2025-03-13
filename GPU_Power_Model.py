from pynvraw import api, get_phys_gpu
import pynvml
import time
from datetime import datetime
import pymongo
import subprocess
import pyautogui
import re
import atexit
import contextlib


class Main:
    def __init__(self):
        # Регистрация метода cleanup для выполнения при завершении программы
        atexit.register(self.__cleanup)
        # Инициализация pynvml
        pynvml.nvmlInit()
        # Получение количества GPU
        device_count = pynvml.nvmlDeviceGetCount()
        if device_count == 0:
            print("Не найдено GPU NVIDIA")
            exit()
        # Получение первого GPU для pynvml
        self.__handle = pynvml.nvmlDeviceGetHandleByIndex(0)
        # Получение первого GPU для pynvraw
        cuda_dev = 0
        gpu = get_phys_gpu(cuda_dev)
        self.__pynvraw_handle = gpu.handle
        # Подключение к MongoDB
        self.__client = pymongo.MongoClient("mongodb://localhost:27017/")  # Адрес сервера MongoDB
        self.__db = self.__client["gpu_monitoring"]  # Название базы данных
        # Путь к исполняемому файлу MSI Kombustor
        benchmark_folder = "C:\\Program Files\\Geeks3D\\MSI Kombustor 4 x64\\"
        benchmark_name = "MSI-Kombustor-x64.exe"
        log_filename = "_kombustor_log.txt"
        # Параметры командной строки для запуска теста
        benchmark_options = "-width=1920 -height=1080 -glfurrytorus -benchmark -fullscreen -log_gpu_data -logfile_in_app_folder"  # Стандартное время теста - 60 секунд
        # Полная команда для запуска
        self.__benchmark_start_command = f'"{benchmark_folder + benchmark_name}" {benchmark_options}'
        self.__benchmark_log_path = benchmark_folder + log_filename

    # Конец работы программы
    @staticmethod
    def __cleanup():
        pynvml.nvmlShutdown()
        print("Работа программы завершена")

    # Метод получения данных GPU
    def __get_gpu_data(self):
        # Получение информации о GPU
        try:
            util = pynvml.nvmlDeviceGetUtilizationRates(self.__handle)
            memory_info = pynvml.nvmlDeviceGetMemoryInfo(self.__handle)
            temperature = pynvml.nvmlDeviceGetTemperature(self.__handle, pynvml.NVML_TEMPERATURE_GPU)
            fan_speed = pynvml.nvmlDeviceGetFanSpeed(self.__handle)
            clock_info = pynvml.nvmlDeviceGetClockInfo(self.__handle, pynvml.NVML_CLOCK_GRAPHICS)
            memory_clock = pynvml.nvmlDeviceGetClockInfo(self.__handle, pynvml.NVML_CLOCK_MEM) / 2
            power_usage = pynvml.nvmlDeviceGetPowerUsage(self.__handle) / 1000.0  # В ваттах
            power_limit = pynvml.nvmlDeviceGetEnforcedPowerLimit(self.__handle) / 1000.0  # В ваттах
        except Exception as e:
            # Обработка любых ошибок
            print(f"Произошло исключение {type(e).__name__}: {e}")  # Вывести название ошибки и сообщение
            return
        try:
            voltage = api.get_core_voltage(self.__pynvraw_handle)  # В вольтах
        except Exception as e:
            # Обработка любых ошибок
            print(f"Произошло исключение: {type(e).__name__}: {e}")  # Вывести название ошибки и сообщение
            return
        # Получение текущей даты и времени
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        # Формирование данных
        gpu_data = {
            "Date": current_time,
            "GPU Clock [MHz]": clock_info,
            "Memory Clock [MHz]": memory_clock,
            "GPU Temperature [°C]": temperature,
            "Fan Speed [%]": fan_speed,
            "Fan Speed [RPM]": fan_speed * 100,  # Примерное значение RPM
            "Memory Used [MB]": memory_info.used / 1024 / 1024,
            "GPU Load [%]": util.gpu,
            "Memory Controller Load [%]": util.memory,
            "Board Power Draw [W]": power_usage,
            "Power Consumption [% TDP]": (power_usage / power_limit) * 100,
            "GPU Voltage [V]": voltage
        }
        return gpu_data

    # Метод вывода данных о GPU
    @staticmethod
    def __print_gpu_data(gpu_data):
        print("=" * 50)
        print(f"Дата: {gpu_data['Date']}")
        print(f"Частота GPU: {gpu_data['GPU Clock [MHz]']} MHz")
        print(f"Частота памяти: {gpu_data['Memory Clock [MHz]']} MHz")
        print(f"Температура GPU: {gpu_data['GPU Temperature [°C]']} °C")
        print(f"Скорость вентилятора: {gpu_data['Fan Speed [%]']}%")
        print(f"Скорость вентилятора (RPM): {gpu_data['Fan Speed [RPM]']} RPM")
        print(f"Используемая память: {gpu_data['Memory Used [MB]']} MB")
        print(f"Загрузка GPU: {gpu_data['GPU Load [%]']}%")
        print(f"Загрузка контроллера памяти: {gpu_data['Memory Controller Load [%]']}%")
        print(f"Потребление платы: {gpu_data['Board Power Draw [W]']} W")
        print(f"Потребление энергии: {gpu_data['Power Consumption [% TDP]']}% TDP")
        print(f"Напряжение GPU: {gpu_data['GPU Voltage [V]']} V")
        print("=" * 50)

    # Метод записи FPS из файла лога MSI Kombustor (и эффективности [FPS/W]) в соответствующие документы коллекции MongoDB
    @staticmethod
    def __update_fps_and_efficiency_in_collection(log_filepath, collection):
        # Регулярное выражение для строки с FPS в логе
        log_pattern = re.compile(r"\((\d{2}:\d{2}:\d{2}).+ - FPS: (\d+)")
        # Текущая дата без времени
        current_date = datetime.now().strftime("%Y-%m-%d")
        # Открыть файл лога
        with open(log_filepath, "r") as file:
            any_match_found = False
            for line in file:
                match = re.search(log_pattern, line)
                if match:
                    any_match_found = True
                    # Извлечь время и FPS из найденной строки
                    log_time = match.group(1)
                    fps = int(match.group(2))
                    # Преобразовать время из строки
                    log_datetime = f"{current_date} {log_time}"
                    # Найти документ в коллекции с полем "Date", совпадающим с log_datetime
                    document = collection.find_one({"Date": log_datetime})
                    if document:
                        # Извлечь "Board Power Draw [W]" из документа
                        board_power_draw = document.get("Board Power Draw [W]", None)
                        if board_power_draw:
                            # Рассчитать "Efficiency [FPS/W]"
                            efficiency = fps / board_power_draw
                            # Обновить (записать) поля "FPS" и "Efficiency [FPS/W]" в найденном документе
                            collection.update_one({"_id": document["_id"]}, {"$set": {"FPS": fps, "Efficiency [FPS/W]": efficiency}})
                            # Вывести инфо о записанных значениях
                            print(f"{log_datetime} FPS: {fps}, Эффективность [FPS/W]: {efficiency}")
                        else:
                            print(f"Поле 'Board Power Draw [W]' отсутствует в документе с датой {log_datetime} в коллекции MongoDB")
                    else:
                        print(f"Не найден документ с датой {log_datetime} в коллекции MongoDB для записи значения FPS")
            if not any_match_found:
                print("В файле лога не было найдено значений FPS")

    # Метод - проверка, что работа бенчмарка была завершена корректно
    def __check_benchmark_log_for_normal_shutdown(self):
        try:
            with open(self.__benchmark_log_path, 'r') as log_file:
                for line in log_file:
                    if "Kombustor shutdown ok." in line:
                        return True
            print("Работа бенчмарка была неожиданно остановлена, запись лога прервалась")
            return False
        except Exception as e:
            print(f"Произошла ошибка: {e}")
            return False

    # Метод - запуск теста бенчмарка со сбором данных в MongoDB (ограниченный по времени)
    def __run_benchmark(self, collection, benchmark_start_command, time_before_start_test, time_test_running, time_after_finish_test):
        benchmark_process = None  # Инициализация переменной
        total_time = time_before_start_test + time_test_running + time_after_finish_test
        total_time_before_finish_test = time_before_start_test + time_test_running

        # Цикл сбора данных с сенсоров GPU на X секунд
        i = 0
        while i < total_time:
            if i == time_before_start_test:
                # Запуск MSI Kombustor после X секунд сбора данных с сенсоров
                benchmark_process = subprocess.Popen(benchmark_start_command, shell=True)
            if i == total_time_before_finish_test:
                pyautogui.press('esc')  # Имитация нажатия ESC для остановки теста (окно бенчмарка должно быть активным)
            # Получение данных
            gpu_data = self.__get_gpu_data()
            if gpu_data is None:
                print("Не удалось получить данные с сенсоров GPU. Тест бенчмарка остановлен")
                with contextlib.suppress(Exception):
                    benchmark_process.terminate()
                    benchmark_process.wait()
                return False
            collection.insert_one(gpu_data)  # Сохранение данных с сенсоров в MongoDB
            # Вывод данных
            self.__print_gpu_data(gpu_data)
            # Пауза на 1 секунду
            time.sleep(1)
            i = i + 1
        benchmark_process.terminate()
        benchmark_process.wait()
        if not self.__check_benchmark_log_for_normal_shutdown(): # Проверка, что работа бенчмарка была завершена корректно
            return False

    def main_loop(self):
        collection = self.__db["gpu_data" + " " + datetime.now().strftime("%Y-%m-%d %H:%M:%S")]  # Название коллекции

        # Параметры времени теста (в секундах)
        time_before_start_test = 5
        time_test_running = 30
        time_after_finish_test = 10

        # Один запуск теста бенчмарка со сбором данных в MongoDB (ограниченный по времени)
        res = self.__run_benchmark(collection, self.__benchmark_start_command, time_before_start_test, time_test_running, time_after_finish_test)
        if res is False:
            print("Работа теста бенчмарка остановлена. Данные параметры работы GPU являются нестабильными")
            return
        # Запись FPS из файла лога MSI Kombustor (и эффективность [FPS/W]) в соответствующие документы коллекции MongoDB
        self.__update_fps_and_efficiency_in_collection(self.__benchmark_log_path, collection)


main = Main()
main.main_loop()
