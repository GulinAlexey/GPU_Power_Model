import atexit
import pynvml
import os
import socket
import threading
import SocketCalls


class UndervoltingGpuSystem:
    def __init__(self):
        self.__address = SocketCalls.UNDERVOLTING_GPU_SYSTEM_ADDRESS
        self.__port = SocketCalls.UNDERVOLTING_GPU_SYSTEM_PORT
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
        # Путь и параметры для NVIDIA Inspector
        nvidia_inspector_folder = "C:\\NVIDIA_Inspector_1.9.8.7_Beta\\"
        nvidia_inspector_name = "nvidiaInspector.exe"
        # Частота GPU
        nvidia_inspector_gpu_clock_offset_options = "-setBaseClockOffset:0,0,"  # Справа этой строки добавлять само значение
        self.__nvidia_inspector_gpu_clock_offset_command = f'"{nvidia_inspector_folder + nvidia_inspector_name}" {nvidia_inspector_gpu_clock_offset_options}'
        self.__default_gpu_clock_offset = 0
        self.__current_gpu_clock_offset = self.__default_gpu_clock_offset
        # Частота памяти
        nvidia_inspector_mem_clock_offset_options = "-setMemoryClockOffset:0,0,"  # Справа этой строки добавлять само значение
        self.__nvidia_inspector_mem_clock_offset_command = f'"{nvidia_inspector_folder + nvidia_inspector_name}" {nvidia_inspector_mem_clock_offset_options}'
        self.__default_mem_clock_offset = 0
        self.__current_mem_clock_offset = self.__default_mem_clock_offset

    # Конец работы программы
    @staticmethod
    def __cleanup():
        pynvml.nvmlShutdown()
        print("Работа программы завершена")

    # Уменьшение Power Limit GPU для прохождения следующего теста бенчмарка
    def __reduce_tdp(self, milliwatt_reducing_value):
        # Получение текущего Power Limit (в абсолютных величинах, а не проценты TDP)
        power_limit = pynvml.nvmlDeviceGetEnforcedPowerLimit(self.__handle)
        power_limit_constraints = pynvml.nvmlDeviceGetPowerManagementLimitConstraints(self.__handle)

        # Уменьшение TDP
        new_power_limit = max(power_limit_constraints[0],
                              power_limit - milliwatt_reducing_value)  # Уменьшить на X мВт
        pynvml.nvmlDeviceSetPowerManagementLimit(self.__handle, new_power_limit)

        power_limit = pynvml.nvmlDeviceGetPowerManagementLimit(self.__handle)
        print(f"Новый Power Limit: {power_limit / 1000} W")
        print(f"Новое ограничение TDP: {(power_limit / power_limit_constraints[1]) * 100} %")
        return power_limit

    # Вернуть значение Power Limit GPU по умолчанию
    def __set_tdp_to_default(self):
        default_power_limit = pynvml.nvmlDeviceGetPowerManagementDefaultLimit(self.__handle)
        pynvml.nvmlDeviceSetPowerManagementLimit(self.__handle, default_power_limit)
        return default_power_limit

    # Увеличение смещения частоты GPU для прохождения следующего теста бенчмарка
    def __increase_gpu_clock_offset(self, megahertz_increasing_value):
        new_clock_offset = self.__current_gpu_clock_offset + megahertz_increasing_value
        os.system(self.__nvidia_inspector_gpu_clock_offset_command + str(new_clock_offset))
        self.__current_gpu_clock_offset = new_clock_offset
        SocketCalls.call_method_of_sensor_data_collection_system("set_gpu_clock_offset", self.__current_gpu_clock_offset)
        # В качестве возвращаемого значения - max частота GPU, по которой можно проверить, что изменения были успешно применены
        min_gpu_clock, max_gpu_clock = pynvml.nvmlDeviceGetMinMaxClockOfPState(self.__handle, pynvml.NVML_PSTATE_0,
                                                                               pynvml.NVML_CLOCK_GRAPHICS)
        return self.__current_gpu_clock_offset, max_gpu_clock

    # Вернуть значение смещения частоты GPU по умолчанию
    def __set_gpu_clock_offset_to_default(self):
        os.system(self.__nvidia_inspector_gpu_clock_offset_command + str(self.__default_gpu_clock_offset))
        self.__current_gpu_clock_offset = self.__default_gpu_clock_offset
        SocketCalls.call_method_of_sensor_data_collection_system("set_gpu_clock_offset",self.__current_gpu_clock_offset)
        # В качестве возвращаемого значения - max частота GPU, по которой можно проверить, что изменения были успешно применены
        min_gpu_clock, max_gpu_clock = pynvml.nvmlDeviceGetMinMaxClockOfPState(self.__handle, pynvml.NVML_PSTATE_0,
                                                                               pynvml.NVML_CLOCK_GRAPHICS)
        return self.__current_gpu_clock_offset, max_gpu_clock

    # Увеличение смещения частоты памяти для прохождения следующего теста бенчмарка
    def __increase_mem_clock_offset(self, megahertz_increasing_value):
        new_clock_offset = self.__current_mem_clock_offset + megahertz_increasing_value
        os.system(self.__nvidia_inspector_mem_clock_offset_command + str(new_clock_offset))
        self.__current_mem_clock_offset = new_clock_offset
        SocketCalls.call_method_of_sensor_data_collection_system("set_mem_clock_offset",self.__current_mem_clock_offset)
        return self.__current_mem_clock_offset

    # Вернуть значение смещения частоты памяти по умолчанию
    def __set_mem_clock_offset_to_default(self):
        os.system(self.__nvidia_inspector_mem_clock_offset_command + str(self.__default_mem_clock_offset))
        self.__current_mem_clock_offset = self.__default_mem_clock_offset
        SocketCalls.call_method_of_sensor_data_collection_system("set_mem_clock_offset",self.__current_mem_clock_offset)
        return self.__current_mem_clock_offset

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
            if method_name == "reduce_tdp":
                if len(parameters) != 1:
                    response = "Метод reduce_tdp требует 1 параметр"
                else:
                    milliwatt_reducing_value = int(parameters[0])
                    response = self.__reduce_tdp(milliwatt_reducing_value)
            elif method_name == "set_tdp_to_default":
                if parameters:
                    response = "Для метода set_tdp_to_default параметры не требуются"
                else:
                    response = self.__set_tdp_to_default()
            elif method_name == "increase_gpu_clock_offset":
                if len(parameters) != 1:
                    response = "Метод increase_gpu_clock_offset требует 1 параметр"
                else:
                    megahertz_increasing_value = int(parameters[0])
                    response = self.__increase_gpu_clock_offset(megahertz_increasing_value)
            elif method_name == "set_gpu_clock_offset_to_default":
                if parameters:
                    response = "Для метода set_gpu_clock_offset_to_default параметры не требуются"
                else:
                    response = self.__set_gpu_clock_offset_to_default()
            elif method_name == "increase_mem_clock_offset":
                if len(parameters) != 1:
                    response = "Метод increase_mem_clock_offset требует 1 параметр"
                else:
                    megahertz_increasing_value = int(parameters[0])
                    response = self.__increase_mem_clock_offset(megahertz_increasing_value)
            elif method_name == "set_mem_clock_offset_to_default":
                if parameters:
                    response = "Для метода set_mem_clock_offset_to_default параметры не требуются"
                else:
                    response = self.__set_mem_clock_offset_to_default()
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

system = UndervoltingGpuSystem()
system.run()