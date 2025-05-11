import socket
import threading
from SocketCalls import SocketCalls


class DataAnalysisSystem:
    def __init__(self):
        self.__address = SocketCalls.DATA_ANALYSIS_SYSTEM_ADDRESS
        self.__port = SocketCalls.DATA_ANALYSIS_SYSTEM_PORT

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
            if method_name == "": #TODO
                if parameters:
                    response = f"Для метода {method_name} параметры не требуются"
                    print(response)
                else:
                    response = self.__() #TODO
            elif method_name == "": #TODO
                if len(parameters) != 1:
                    response = f"Метод {method_name} требует 1 параметр"
                    print(response)
                else:
                    offset = int(parameters[0])
                    response = self.__(offset) #TODO
            else:
                response = f"Неизвестный метод {method_name}"
                print(response)
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
        print("Сервер системы анализа данных для построения модели питания GPU запущен и ожидает подключения клиентов...")
        while True:
            client_socket, addr = server.accept()
            print(f"Подключен клиент: {addr}")
            client_handler = threading.Thread(target=self.__handle_client, args=(client_socket,))
            client_handler.start()


system = DataAnalysisSystem()
system.run()