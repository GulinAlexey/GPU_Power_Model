import socket

SENSOR_DATA_COLLECTION_SYSTEM_ADDRESS = "localhost"
SENSOR_DATA_COLLECTION_SYSTEM_PORT = 1234


# Вызвать метод класса одной из систем через сокеты
def call_method(address, port, method_name, *args):
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        client.connect((address, port))
        # Формирование запроса
        request = f"{method_name}," + ",".join(map(str, args))
        client.send(request.encode('utf-8'))
        # Получение ответа
        response = client.recv(4096)
        return response.decode('utf-8')
    except Exception as e:
        print(f"Ошибка при вызове метода: {e}")
        return None
    finally:
        client.close()


def call_method_of_sensor_data_collection_system(function_name, *args):
    return call_method(SENSOR_DATA_COLLECTION_SYSTEM_ADDRESS, SENSOR_DATA_COLLECTION_SYSTEM_PORT, function_name, *args)
