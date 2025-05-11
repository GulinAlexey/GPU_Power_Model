import pyautogui
import re
from datetime import datetime
import subprocess
import contextlib
import time
import socket
import threading
import psutil
from SocketCalls import SocketCalls


class BenchmarkTestSystem:
    def __init__(self):
        self.__address = SocketCalls.BENCHMARK_TEST_SYSTEM_ADDRESS
        self.__port = SocketCalls.BENCHMARK_TEST_SYSTEM_PORT
        pyautogui.FAILSAFE = False  # Убрать исключение при эмуляции клавиши "Esc" (для выхода из бенчмарка), когда курсор - в углу экрана
        # Путь к исполняемому файлу MSI Kombustor
        self.__benchmark_folder = "C:\\Program Files\\Geeks3D\\MSI Kombustor 4 x64\\"
        self.__benchmark_name = "MSI-Kombustor-x64.exe"
        log_filename = "_kombustor_log.txt"
        # Параметры командной строки для запуска теста
        self.__benchmark_type = "glfurrytorus"  # Тип теста бенчмарка
        # Стандартное время теста - 60 секунд (если режим теста "бенчмарк", а не "стресс тест")
        self.__benchmark_options_part1 = "-width=1920 -height=1080 -"
        self.__benchmark_options_part2 = " -benchmark -fullscreen -log_gpu_data -logfile_in_app_folder"
        benchmark_options = self.__benchmark_options_part1 + self.__benchmark_type + self.__benchmark_options_part2
        # Полная команда для запуска
        self.__benchmark_start_command = f'"{self.__benchmark_folder + self.__benchmark_name}" {benchmark_options}'
        self.__benchmark_log_path = self.__benchmark_folder + log_filename

    # Изменить тип теста бенчмарка для запуска
    def __change_benchmark_test_type(self, new_test_type):
        self.__benchmark_type = new_test_type
        SocketCalls.call_method_of_sensor_data_collection_system("set_benchmark_type", new_test_type)
        benchmark_options = self.__benchmark_options_part1 + self.__benchmark_type + self.__benchmark_options_part2
        # Полная команда для запуска
        self.__benchmark_start_command = f'"{self.__benchmark_folder + self.__benchmark_name}" {benchmark_options}'
        print("Тип теста изменён на " + new_test_type)
        return True

    # Запись FPS из файла лога MSI Kombustor (и эффективности [FPS/W]) в соответствующие документы коллекции MongoDB
    def __update_fps_and_efficiency_in_collection(self, collection_name, db_name=None):
        # Регулярное выражение для строки с FPS в логе
        log_pattern = re.compile(r"\((\d{2}:\d{2}:\d{2}).+ - FPS: (\d+)")
        # Текущая дата без времени
        current_date = datetime.now().strftime("%Y-%m-%d")
        # Открыть файл лога
        with open(self.__benchmark_log_path, "r") as file:
            any_match_found = False
            for line in file:
                match = re.search(log_pattern, line)
                if match:
                    any_match_found = True
                    # Извлечь время и FPS из найденной строки
                    log_time = match.group(1)
                    fps = int(match.group(2))
                    # Преобразовать время из строки
                    log_datetime = f"{current_date} {log_time}"
                    # Найти соответствующий документ по дате, записать для него FPS и FPS/W и вывести результат
                    if db_name is None:
                        print(SocketCalls.call_method_of_sensor_data_collection_system("calculate_fps_and_efficiency_in_collection",
                                                                                       collection_name, log_datetime, fps))
                    else:
                        print(SocketCalls.call_method_of_sensor_data_collection_system("calculate_fps_and_efficiency_in_collection",
                                                                                       collection_name, log_datetime, fps, db_name))
            if not any_match_found:
                print("В файле лога не было найдено значений FPS")
                return False
        return True

    # Проверка, что работа бенчмарка была завершена корректно
    def __check_benchmark_log_for_normal_shutdown(self):
        try:
            with open(self.__benchmark_log_path, 'r') as log_file:
                for line in log_file:
                    if "Kombustor shutdown ok." in line:
                        return True
            print("Работа бенчмарка была неожиданно остановлена, запись лога прервалась")
        except Exception as e:
            print(f"Произошла ошибка: {e}")
            return False
        # Проверить, что процесс бенчмарка был завершён и не висит в запущенных процессах,
        # в противном случае принудительно его закрыть
        proc_was_killed = False # Флаг, что процесс бенчмарка был найден и принудительно завершён
        for proc in psutil.process_iter(['pid', 'name']):
            if proc.info['name'].lower() == self.__benchmark_name.lower():
                try:
                    print(f"Найден процесс {self.__benchmark_name} (PID: {proc.info['pid']}). Закрытие...")
                    proc.kill()
                    proc_was_killed = True
                except Exception as e:
                    print(f"Не удалось закрыть процесс: {e}")
                    return False
        if not proc_was_killed:
            print(f"Процесс {self.__benchmark_name} не найден в запущенных, значит, был завершён корректно")
            return True
        else:
            print(f"Процесс {self.__benchmark_name} найден и принудительно закрыт, значит, ранее завис при выполнении")
            return False

    # Запуск теста бенчмарка со сбором данных в MongoDB (ограниченный по времени)
    def __run_benchmark(self, collection_name, time_before_start_test, time_test_running,
                        time_after_finish_test, db_name=None):
        benchmark_process = None  # Инициализация переменной
        total_time = time_before_start_test + time_test_running + time_after_finish_test
        total_time_before_finish_test = time_before_start_test + time_test_running

        # Цикл сбора данных с сенсоров GPU на X секунд
        i = 0
        while i < total_time:
            if i == time_before_start_test:
                # Запуск MSI Kombustor после X секунд сбора данных с сенсоров
                benchmark_process = subprocess.Popen(self.__benchmark_start_command, shell=True)
            if i == total_time_before_finish_test:
                pyautogui.press(
                    'esc')  # Имитация нажатия ESC для остановки теста (окно бенчмарка должно быть активным)
            # Получение данных
            gpu_data = SocketCalls.call_method_of_sensor_data_collection_system("get_gpu_data")
            if gpu_data is None:
                print("Не удалось получить данные с сенсоров GPU. Тест бенчмарка остановлен")
                with contextlib.suppress(Exception):
                    benchmark_process.terminate()
                    benchmark_process.wait()
                return False
            if db_name is None:
                # Сохранение данных с сенсоров в MongoDB (в БД по умолчанию)
                SocketCalls.call_method_of_sensor_data_collection_system("save_gpu_data_to_db", collection_name)
            else:
                # Сохранение данных с сенсоров в MongoDB (в определённую БД)
                SocketCalls.call_method_of_sensor_data_collection_system("save_gpu_data_to_db", collection_name, db_name)
            # Вывод данных
            SocketCalls.call_method_of_sensor_data_collection_system("print_gpu_data")
            # Пауза на 1 секунду
            time.sleep(1)
            i = i + 1
        benchmark_process.terminate()
        benchmark_process.wait()
        if not self.__check_benchmark_log_for_normal_shutdown():  # Проверка, что работа бенчмарка была завершена корректно
            return False

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
            if method_name == "change_benchmark_test_type":
                if len(parameters) != 1:
                    response = f"Метод {method_name} требует 1 параметр"
                    print(response)
                else:
                    new_test_type = parameters[0]
                    response = self.__change_benchmark_test_type(new_test_type)
            elif method_name == "update_fps_and_efficiency_in_collection":
                if len(parameters) < 1 or len(parameters) > 2:
                    response = f"Метод {method_name} требует 1 или 2 параметра"
                    print(response)
                else:
                    collection = parameters[0]
                    if len(parameters) == 1:
                        response = self.__update_fps_and_efficiency_in_collection(collection)
                    else:
                        db_name = parameters[1]
                        response = self.__update_fps_and_efficiency_in_collection(collection, db_name)
            elif method_name == "check_benchmark_log_for_normal_shutdown":
                if parameters:
                    response = f"Для метода {method_name} параметры не требуются"
                    print(response)
                else:
                    response = self.__check_benchmark_log_for_normal_shutdown()
            elif method_name == "run_benchmark":
                if len(parameters) < 4 or len(parameters) > 5:
                    response = f"Метод {method_name} требует 4 или 5 параметров"
                    print(response)
                else:
                    collection_name = parameters[0]
                    time_before_start_test = int(parameters[1])
                    time_test_running = int(parameters[2])
                    time_after_finish_test = int(parameters[3])
                    if len(parameters) == 4:
                        response = self.__run_benchmark(collection_name, time_before_start_test, time_test_running,
                                                    time_after_finish_test)
                    else:
                        db_name = parameters[4]
                        response = self.__run_benchmark(collection_name, time_before_start_test, time_test_running,
                                                        time_after_finish_test, db_name)
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

    # Цикл обработки вызовов методов через сокеты
    def run(self):
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.bind((self.__address, self.__port))
        server.listen(5)
        print("Сервер системы тестов бенчмарка GPU запущен и ожидает подключения клиентов...")
        while True:
            client_socket, addr = server.accept()
            print(f"Подключен клиент: {addr}")
            client_handler = threading.Thread(target=self.__handle_client, args=(client_socket,))
            client_handler.start()


system = BenchmarkTestSystem()
system.run()
