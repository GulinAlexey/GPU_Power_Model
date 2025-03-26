import atexit
import pynvml
from pynvraw import api, get_phys_gpu
import pymongo
from datetime import datetime
import socket
import threading
import SocketCalls


class SensorDataCollectionSystem:
    def __init__(self):
        self.__address = SocketCalls.SENSOR_DATA_COLLECTION_SYSTEM_ADDRESS
        self.__port = SocketCalls.SENSOR_DATA_COLLECTION_SYSTEM_PORT
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
        return True

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

    # Изменить тип теста бенчмарка (для записи в БД)
    def __set_benchmark_type(self, benchmark_type):
        if isinstance(benchmark_type, str):
            self.__benchmark_type = benchmark_type
            return True
        return False

    # Вывод данных о TDP и Power Limit
    def __print_tdp_info(self):
        power_limit = pynvml.nvmlDeviceGetEnforcedPowerLimit(self.__handle)
        power_limit_default = pynvml.nvmlDeviceGetPowerManagementDefaultLimit(self.__handle)
        power_limit_constraints = pynvml.nvmlDeviceGetPowerManagementLimitConstraints(self.__handle)
        tdp_info_str = "\n".join([
            f"Текущий Power Limit: {power_limit / 1000} W",
            f"Текущий TDP Limit: {(power_limit / power_limit_constraints[1]) * 100} %",
            f"Power Limit по умолчанию: {power_limit_default / 1000} W",
            f"Ограничения Power Limit: {power_limit_constraints[0] / 1000} W - {power_limit_constraints[1] / 1000} W",  # max Power Limit = 100% TDP
            f"Ограничения TDP: {(power_limit_constraints[0] / power_limit_constraints[1]) * 100} % - 100 %"
        ])
        print(tdp_info_str)
        return tdp_info_str

    # Вывод данных о min, max частотах GPU и смещении
    def __print_gpu_clock_info(self):
        # Получение частот
        min_gpu_clock, max_gpu_clock = pynvml.nvmlDeviceGetMinMaxClockOfPState(self.__handle, pynvml.NVML_PSTATE_0,
                                                                               pynvml.NVML_CLOCK_GRAPHICS)
        gpu_clock_info = "\n".join([
            f"Мин. частота GPU: {min_gpu_clock} MHz",
            f"Макс. частота GPU: {max_gpu_clock} MHz",
            f"Смещение частоты GPU: {self.__current_gpu_clock_offset} MHz"
        ])
        print(gpu_clock_info)
        return gpu_clock_info

    # Найти по дате документ в коллекции и записать для него FPS и FPS/W
    def __calculate_fps_and_efficiency_in_collection(self, collection_name, log_datetime, fps):
        collection = self.__db[collection_name.replace("['", "").replace("']", "")]
        # Найти документ в коллекции с полем "Date", совпадающим с log_datetime
        document = collection.find_one({"Date": log_datetime})
        if document:
            # Извлечь "Board Power Draw [W]" из документа
            board_power_draw = document.get("Board Power Draw [W]", None)
            if board_power_draw:
                # Рассчитать "Efficiency [FPS/W]"
                efficiency = fps / board_power_draw
                # Обновить (записать) поля "FPS" и "Efficiency [FPS/W]" в найденном документе
                collection.update_one({"_id": document["_id"]},
                                      {"$set": {"FPS": fps, "Efficiency [FPS/W]": efficiency}})
                # Вывести инфо о записанных значениях
                return f"{log_datetime} FPS: {fps}, Эффективность [FPS/W]: {efficiency}"
            else:
                return f"Поле 'Board Power Draw [W]' отсутствует в документе с датой {log_datetime} в коллекции MongoDB"
        else:
            return f"Не найден документ с датой {log_datetime} в коллекции MongoDB для записи значения FPS"

    # Обработка вызова метода через сокеты
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
                if len(parameters) != 1:
                    response = "Метод set_gpu_clock_offset требует 1 параметр"
                else:
                    offset = int(parameters[0])
                    response = self.__set_gpu_clock_offset(offset)
            elif method_name == "set_mem_clock_offset":
                if len(parameters) != 1:
                    response = "Метод set_mem_clock_offset требует 1 параметр"
                else:
                    offset = int(parameters[0])
                    response = self.__set_mem_clock_offset(offset)
            elif method_name == "set_benchmark_type":
                if len(parameters) != 1:
                    response = "Метод set_benchmark_type требует 1 параметр"
                else:
                    benchmark_type = parameters[0]
                    response = self.__set_benchmark_type(benchmark_type)
            elif method_name == "print_tdp_info":
                if parameters:
                    response = "Для метода print_tdp_info параметры не требуются"
                else:
                    response = self.__print_tdp_info()
            elif method_name == "print_gpu_clock_info":
                if parameters:
                    response = "Для метода print_gpu_clock_info параметры не требуются"
                else:
                    response = self.__print_gpu_clock_info()
            elif method_name == "calculate_fps_and_efficiency_in_collection":
                if len(parameters) != 3:
                    response = "Метод calculate_fps_and_efficiency_in_collection требует 3 параметра"
                else:
                    collection_name = parameters[0]
                    log_datetime = parameters[1]
                    fps = int(parameters[2])
                    response = self.__calculate_fps_and_efficiency_in_collection(collection_name, log_datetime, fps)
            else:
                response = "Неизвестный метод"
            # Преобразование response в строку, если оно является типа bool или int
            if isinstance(response, (bool, int)):
                response = str(response)
            elif isinstance(response, tuple):
                # Преобразовать кортеж в строку
                response = ', '.join(map(str, response))
            elif response is None:
                response = "None"
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
        print("Сервер системы сбора данных с сенсоров GPU запущен и ожидает подключения клиентов...")
        while True:
            client_socket, addr = server.accept()
            print(f"Подключен клиент: {addr}")
            client_handler = threading.Thread(target=self.__handle_client, args=(client_socket,))
            client_handler.start()

system = SensorDataCollectionSystem()
system.run()