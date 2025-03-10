from pynvraw import api, get_phys_gpu
import pynvml
import time
from datetime import datetime
import pymongo
import subprocess
import pyautogui


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

    def main_loop(self):
        # Подключение к MongoDB
        client = pymongo.MongoClient("mongodb://localhost:27017/")  # Адрес сервера MongoDB
        db = client["gpu_monitoring"]  # Название базы данных
        collection = db["gpu_data" + " " + datetime.now().strftime("%Y-%m-%d %H:%M:%S")]  # Название коллекции
        # Запуск FurMark
        # Путь к исполняемому файлу FurMark
        furmark_path = "C:\\Program Files\\Geeks3D\\FurMark2_x64\\furmark.exe"
        fraps_path = "C:\\Fraps\\fraps.exe"
        # Параметры командной строки для запуска теста
        benchmark_options = "--demo furmark-gl --width 1920 --height 1080 --fullscreen --max-time 20" # Тест на 20 секунд
        # Полная команда для запуска
        command = f'"{furmark_path}" {benchmark_options}'
        benchmark_process = None # Инициализация переменной
        i = 0
        subprocess.Popen(fraps_path)
        while i < 35: # Цикл на 35 секунд
            if i == 5:
                # Запуск FurMark после 5 секунд сбора данных с сенсоров
                benchmark_process = subprocess.Popen(command, shell=True)
            if i == 8 or i == 26:
                pyautogui.press('f11')  # Имитация нажатия клавиши F11
            # Получение данных
            gpu_data = self.__get_gpu_data()
            collection.insert_one(gpu_data)  # Сохранение данных с сенсоров в MongoDB
            # Вывод данных
            self.print_gpu_data(gpu_data)
            # Пауза на 1 секунду
            time.sleep(1)
            i = i + 1
        pynvml.nvmlShutdown()
        benchmark_process.terminate()
        benchmark_process.wait()

main = Main()
main.main_loop()
