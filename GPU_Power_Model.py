from pynvraw import api, get_phys_gpu
import pynvml
import time
from datetime import datetime
import pymongo
import subprocess
import pyautogui
import re


class Main:
    def __init__(self):
        # Инициализация pynvml
        pynvml.nvmlInit()
        # Получение количества GPU
        device_count = pynvml.nvmlDeviceGetCount()
        if device_count == 0:
            print("Не найдено GPU NVIDIA")
            exit()
        # Получение первого GPU
        self.__handle = pynvml.nvmlDeviceGetHandleByIndex(0)

    # Функция для получения данных GPU
    def __get_gpu_data(self):
        # Получение информации о GPU
        util = pynvml.nvmlDeviceGetUtilizationRates(self.__handle)
        memory_info = pynvml.nvmlDeviceGetMemoryInfo(self.__handle)
        temperature = pynvml.nvmlDeviceGetTemperature(self.__handle, pynvml.NVML_TEMPERATURE_GPU)
        fan_speed = pynvml.nvmlDeviceGetFanSpeed(self.__handle)
        clock_info = pynvml.nvmlDeviceGetClockInfo(self.__handle, pynvml.NVML_CLOCK_GRAPHICS)
        memory_clock = pynvml.nvmlDeviceGetClockInfo(self.__handle, pynvml.NVML_CLOCK_MEM) / 2
        power_usage = pynvml.nvmlDeviceGetPowerUsage(self.__handle) / 1000.0  # В ваттах
        power_limit = pynvml.nvmlDeviceGetEnforcedPowerLimit(self.__handle) / 1000.0  # В ваттах
        cuda_dev = 0
        gpu = get_phys_gpu(cuda_dev)
        voltage = api.get_core_voltage(gpu.handle)  # В вольтах
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

    # Функция для вывода данных о GPU
    @staticmethod
    def print_gpu_data(gpu_data):
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

    # Функция для записи FPS из файла лога MSI Kombustor в соответствующие документы коллекции MongoDB
    def __update_fps_in_collection(self, log_filepath, collection):
        # Регулярное выражение для строки с FPS в логе
        log_pattern = re.compile(r"\((\d{2}:\d{2}:\d{2}).+ - FPS: (\d+)")
        # Текущая дата без времени
        current_date = datetime.now().strftime("%Y-%m-%d")
        # Открыть файл лога
        with open(log_filepath, "r") as file:
            for line in file:
                match = re.search(log_pattern, line)
                if match:
                    # Извлечь время и FPS из найденной строки
                    log_time = match.group(1)
                    fps = int(match.group(2))
                    # Преобразовать время из строки
                    log_datetime = f"{current_date} {log_time}"
                    # Найти документ в коллекции с полем "Date", совпадающим с log_datetime
                    document = collection.find_one({"Date": log_datetime})
                    if document:
                        # Обновить поле "FPS" в найденном документе
                        collection.update_one({"_id": document["_id"]}, {"$set": {"FPS": int(fps)}})
                    else:
                        print(f"Не найден документ с датой {log_datetime} в коллекции MongoDB для записи значения FPS")


    def main_loop(self):
        # Подключение к MongoDB
        client = pymongo.MongoClient("mongodb://localhost:27017/")  # Адрес сервера MongoDB
        db = client["gpu_monitoring"]  # Название базы данных
        collection = db["gpu_data" + " " + datetime.now().strftime("%Y-%m-%d %H:%M:%S")]  # Название коллекции
        # Путь к исполняемому файлу MSI Kombustor
        benchmark_folder = "C:\\Program Files\\Geeks3D\\MSI Kombustor 4 x64\\"
        benchmark_name = "MSI-Kombustor-x64.exe"
        log_filename = "_kombustor_log.txt"
        # Параметры командной строки для запуска теста
        benchmark_options = "-width=1920 -height=1080 -glfurrytorus -benchmark -fullscreen -log_gpu_data -logfile_in_app_folder"  # Стандартное время теста - 60 секунд
        # Полная команда для запуска
        benchmark_start_command = f'"{benchmark_folder + benchmark_name}" {benchmark_options}'
        benchmark_process = None  # Инициализация переменной
        # Параметры времени теста (в секундах)
        time_before_start_test = 5
        time_test_running = 25
        time_after_finish_test = 10
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
            collection.insert_one(gpu_data)  # Сохранение данных с сенсоров в MongoDB
            # Вывод данных
            self.print_gpu_data(gpu_data)
            # Пауза на 1 секунду
            time.sleep(1)
            i = i + 1
        benchmark_process.terminate()
        benchmark_process.wait()
        # Запись FPS из файла лога MSI Kombustor в соответствующие документы коллекции MongoDB
        self.__update_fps_in_collection(benchmark_folder + log_filename, collection)
        pynvml.nvmlShutdown()

main = Main()
main.main_loop()
