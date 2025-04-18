import socket

SENSOR_DATA_COLLECTION_SYSTEM_ADDRESS = "localhost"
SENSOR_DATA_COLLECTION_SYSTEM_PORT = 1234

BENCHMARK_TEST_SYSTEM_ADDRESS = "localhost"
BENCHMARK_TEST_SYSTEM_PORT = 1235

UNDERVOLTING_GPU_SYSTEM_ADDRESS = "localhost"
UNDERVOLTING_GPU_SYSTEM_PORT = 1236

DATA_ANALYSIS_SYSTEM_ADDRESS = "localhost"
DATA_ANALYSIS_SYSTEM_PORT = 1237

TIMEOUT = 120 # Время ожидания ответа на запрос в секундах


# Вызвать метод класса одной из систем через сокеты
def call_method(address, port, method_name, *args):
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        # Установка таймаута ожидания
        client.settimeout(TIMEOUT)
        client.connect((address, port))
        # Формирование запроса
        request = f"{method_name}," + ",".join(map(str, args))
        client.send(request.encode('utf-8'))
        # Получение ответа
        response = client.recv(4096)
        response_str = response.decode('utf-8')
        # Попытка преобразовать строку в кортеж, если это возможно
        try:
            response_tuple = eval(response_str)
            if isinstance(response_tuple, tuple):
                return response_tuple
        except (SyntaxError, NameError):
            # Игнорировать ошибку, если строка не является кортежем
            pass
        # Преобразование response в int или bool, если возможно
        if response_str.isdigit():
            return int(response_str)
        elif response_str.lower() == "true":
            return True
        elif response_str.lower() == "false":
            return False
        elif response_str == "None":
            return None
        else:
            return response_str
    except Exception as e:
        print(f"Ошибка при вызове метода: {e}")
        return None
    finally:
        client.close()


def call_method_of_sensor_data_collection_system(function_name, *args):
    return call_method(SENSOR_DATA_COLLECTION_SYSTEM_ADDRESS, SENSOR_DATA_COLLECTION_SYSTEM_PORT, function_name, *args)


def call_method_of_benchmark_test_system(function_name, *args):
    return call_method(BENCHMARK_TEST_SYSTEM_ADDRESS, BENCHMARK_TEST_SYSTEM_PORT, function_name, *args)


def call_method_of_undervolting_gpu_system(function_name, *args):
    return call_method(UNDERVOLTING_GPU_SYSTEM_ADDRESS, UNDERVOLTING_GPU_SYSTEM_PORT, function_name, *args)


def call_method_of_data_analysis_system(function_name, *args):
    return call_method(DATA_ANALYSIS_SYSTEM_ADDRESS, DATA_ANALYSIS_SYSTEM_PORT, function_name, *args)
