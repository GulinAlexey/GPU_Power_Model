import atexit
import pynvml
from pynvraw import api, get_phys_gpu
import pymongo
from datetime import datetime


class SensorDataCollectionSystem:
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
        self.__db = self.__client["gpu_benchmark_monitoring"]  # Название базы данных

    # Конец работы программы
    @staticmethod
    def __cleanup():
        pynvml.nvmlShutdown()
        print("Работа программы завершена")

        # Получение данных GPU
    def __get_gpu_data(self):
        # Получение информации о GPU
        try:
            util = pynvml.nvmlDeviceGetUtilizationRates(self.__handle)
            memory_info = pynvml.nvmlDeviceGetMemoryInfo(self.__handle)
            temperature = pynvml.nvmlDeviceGetTemperature(self.__handle, pynvml.NVML_TEMPERATURE_GPU)
            fan_speed = pynvml.nvmlDeviceGetFanSpeed(self.__handle)
            clock_info = pynvml.nvmlDeviceGetClockInfo(self.__handle, pynvml.NVML_CLOCK_GRAPHICS)
            memory_clock = pynvml.nvmlDeviceGetClockInfo(self.__handle, pynvml.NVML_CLOCK_MEM) / 2
            power_usage = pynvml.nvmlDeviceGetPowerUsage(self.__handle)
            power_limit = pynvml.nvmlDeviceGetEnforcedPowerLimit(self.__handle)
            power_limit_constraints = pynvml.nvmlDeviceGetPowerManagementLimitConstraints(self.__handle)
            min_gpu_clock, max_gpu_clock = pynvml.nvmlDeviceGetMinMaxClockOfPState(self.__handle,
                                                                                   pynvml.NVML_PSTATE_0,
                                                                                   pynvml.NVML_CLOCK_GRAPHICS)
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
            "Board Power Draw [W]": power_usage / 1000.0,  # В ваттах
            "Power Consumption [% TDP]": (power_usage / power_limit_constraints[1]) * 100,
            "Power Limit [W]": power_limit / 1000.0,  # В ваттах
            "TDP Limit [%]": (power_limit / power_limit_constraints[1]) * 100,
            "Min GPU Clock Frequency [MHz]": min_gpu_clock,
            "Max GPU Clock Frequency [MHz]": max_gpu_clock,
            "GPU Clock Frequency Offset [MHz]": self.__current_gpu_clock_offset,
            "Memory Clock Offset [MHz]": self.__current_mem_clock_offset,
            "GPU Voltage [V]": voltage,
            "Benchmark test type": self.__benchmark_type
        }
        return gpu_data

    # Вывод данных о GPU
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
        print(f"Ограничение мощности: {gpu_data['Power Limit [W]']} W")
        print(f"Ограничение TDP: {gpu_data['TDP Limit [%]']}%")
        print(f"Мин. частота GPU: {gpu_data["Min GPU Clock Frequency [MHz]"]} MHz")
        print(f"Макс. частота GPU: {gpu_data["Max GPU Clock Frequency [MHz]"]} MHz")
        print(f"Смещение частоты GPU: {gpu_data["GPU Clock Frequency Offset [MHz]"]} MHz")
        print(f"Смещение частоты памяти: {gpu_data["Memory Clock Offset [MHz]"]} MHz")
        print(f"Напряжение GPU: {gpu_data['GPU Voltage [V]']} V")
        print(f"Тип теста бенчмарка: {gpu_data['Benchmark test type']}")
        print("=" * 50)

    def run(self):
        pass
