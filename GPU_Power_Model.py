from pynvraw import api, get_phys_gpu
import pynvml
import time
from datetime import datetime

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

    def mainLoop(self):
        while True:
            # Получение данных
            gpu_data = self.__get_gpu_data()
            # Вывод данных
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
            # Пауза на 1 секунду
            time.sleep(1)


main = Main()
main.mainLoop()
