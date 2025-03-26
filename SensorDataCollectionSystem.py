import atexit
import pynvml
from pynvraw import api, get_phys_gpu
import pymongo
from datetime import datetime
import socket
import threading
import SocketSystem


class SensorDataCollectionSystem:
    def __init__(self):
        self.__address = SocketSystem.SENSOR_DATA_COLLECTION_SYSTEM_ADDRESS
        self.__port = SocketSystem.SENSOR_DATA_COLLECTION_SYSTEM_PORT
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
        self.__gpu_data = None
        self.__current_gpu_clock_offset = 0
        self.__current_mem_clock_offset = 0
        self.__benchmark_type = "Not set"

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
        self.__gpu_data = {
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
        return self.__gpu_data

    # Вывод данных о GPU (последнее полученное в __get_gpu_data() значение)
    def __print_gpu_data(self):
        if self.__gpu_data is None:
            self.__get_gpu_data()
            if self.__gpu_data is None:
                return "Получить данные с сенсоров GPU не удалось"
        gpu_data_str = "\n".join([
            "=" * 50,
            f"Дата: {self.__gpu_data['Date']}",
            f"Частота GPU: {self.__gpu_data['GPU Clock [MHz]']} MHz",
            f"Частота памяти: {self.__gpu_data['Memory Clock [MHz]']} MHz",
            f"Температура GPU: {self.__gpu_data['GPU Temperature [°C]']} °C",
            f"Скорость вентилятора: {self.__gpu_data['Fan Speed [%]']}%",
            f"Скорость вентилятора (RPM): {self.__gpu_data['Fan Speed [RPM]']} RPM",
            f"Используемая память: {self.__gpu_data['Memory Used [MB]']} MB",
            f"Загрузка GPU: {self.__gpu_data['GPU Load [%]']}%",
            f"Загрузка контроллера памяти: {self.__gpu_data['Memory Controller Load [%]']}%",
            f"Потребление платы: {self.__gpu_data['Board Power Draw [W]']} W",
            f"Потребление энергии: {self.__gpu_data['Power Consumption [% TDP]']}% TDP",
            f"Ограничение мощности: {self.__gpu_data['Power Limit [W]']} W",
            f"Ограничение TDP: {self.__gpu_data['TDP Limit [%]']}%",
            f"Мин. частота GPU: {self.__gpu_data['Min GPU Clock Frequency [MHz]']} MHz",
            f"Макс. частота GPU: {self.__gpu_data['Max GPU Clock Frequency [MHz]']} MHz",
            f"Смещение частоты GPU: {self.__gpu_data['GPU Clock Frequency Offset [MHz]']} MHz",
            f"Смещение частоты памяти: {self.__gpu_data['Memory Clock Offset [MHz]']} MHz",
            f"Напряжение GPU: {self.__gpu_data['GPU Voltage [V]']} V",
            f"Тип теста бенчмарка: {self.__gpu_data['Benchmark test type']}",
            "=" * 50
        ])
        print(gpu_data_str)
        return gpu_data_str

    # Запись данных о GPU в БД (последнее полученное в __get_gpu_data() значение)
    def __save_gpu_data_to_db(self, collection_name):
        self.__db[collection_name].insert_one(self.__gpu_data)  # Сохранение данных с сенсоров в MongoDB
        return True

    # Изменить значение смещения частоты GPU
    def __set_gpu_clock_offset(self, offset):
        if isinstance(offset, int):
            self.__current_gpu_clock_offset = offset
            return True
        return False

    # Изменить значение смещения частоты памяти
    def __set_mem_clock_offset(self, offset):
        if isinstance(offset, int):
            self.__current_mem_clock_offset = offset
            return True
        return False

    # Изменить тип теста бенчмарка
    def __set_benchmark_type(self, benchmark_type):
        if isinstance(benchmark_type, str):
            self.__benchmark_type = benchmark_type
            return True
        return False

    def __handle_client(self, client_socket):
        try:
            # Чтение и декодирование запроса
            request = client_socket.recv(1024).decode('utf-8')
            print(f"Получено: {request}")
            # Разбиение запроса на метод и параметры
            parts = request.split(',')
            method_name = parts[0].strip()
            parameters = [p.strip() for p in parts[1:] if p.strip()]  # Убрать пустые значения и пробелы

            # Вызов соответствующего метода
            if method_name == "get_gpu_data":
                if parameters:
                    response = "Для метода get_gpu_data параметры не требуются"
                else:
                    response = self.__get_gpu_data()
            elif method_name == "print_gpu_data":
                if parameters:
                    response = "Для метода print_gpu_data параметры не требуются"
                else:
                    response = self.__print_gpu_data()
            elif method_name == "save_gpu_data_to_db":
                if len(parameters) != 1:
                    response = "Метод save_gpu_data_to_db требует 1 параметр"
                else:
                    collection_name = parameters[0]
                    response = self.__save_gpu_data_to_db(collection_name)
            elif method_name == "set_gpu_clock_offset":
                if len(parameters) != 1 or not parameters[0].isdigit():
                    response = "Метод set_gpu_clock_offset требует 1 числовой параметр"
                else:
                    offset = int(parameters[0])
                    response = self.__set_gpu_clock_offset(offset)
            elif method_name == "set_mem_clock_offset":
                if len(parameters) != 1 or not parameters[0].isdigit():
                    response = "Метод set_mem_clock_offset требует 1 числовой параметр"
                else:
                    offset = int(parameters[0])
                    response = self.__set_mem_clock_offset(offset)
            elif method_name == "set_benchmark_type":
                if len(parameters) != 1:
                    response = "Метод set_benchmark_type требует 1 строковой параметр"
                else:
                    benchmark_type = parameters[0]
                    response = self.__set_benchmark_type(benchmark_type)
            else:
                response = "Неизвестный метод"

            # Преобразование response в строку, если оно является типа bool или int
            if isinstance(response, (bool, int)):
                response = str(response)
            # Отправка ответа клиенту
            client_socket.send(response.encode('utf-8'))
        except Exception as e:
            print(f"Ошибка обработки клиента: {e}")
            response = "Ошибка сервера"
            client_socket.send(response.encode('utf-8'))
        finally:
            # Закрытие соединения
            client_socket.close()

    # Цикл обработки вызовов методов через сокеты
    def run(self):
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.bind((self.__address, self.__port))
        server.listen(5)
        print("Сервер запущен и ожидает подключения клиентов...")
        while True:
            client_socket, addr = server.accept()
            print(f"Подключен клиент: {addr}")
            client_handler = threading.Thread(target=self.__handle_client, args=(client_socket,))
            client_handler.start()

system = SensorDataCollectionSystem()
system.run()