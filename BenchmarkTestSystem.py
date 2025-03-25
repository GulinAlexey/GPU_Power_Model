import pyautogui
import re
from datetime import datetime
import subprocess
import contextlib
import time


class BenchmarkTestSystem:
    def __init__(self):
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
        benchmark_options = self.__benchmark_options_part1 + self.__benchmark_type + self.__benchmark_options_part2
        # Полная команда для запуска
        self.__benchmark_start_command = f'"{self.__benchmark_folder + self.__benchmark_name}" {benchmark_options}'

    # Запись FPS из файла лога MSI Kombustor (и эффективности [FPS/W]) в соответствующие документы коллекции MongoDB
    @staticmethod
    def __update_fps_and_efficiency_in_collection(log_filepath, collection):
        # Регулярное выражение для строки с FPS в логе
        log_pattern = re.compile(r"\((\d{2}:\d{2}:\d{2}).+ - FPS: (\d+)")
        # Текущая дата без времени
        current_date = datetime.now().strftime("%Y-%m-%d")
        # Открыть файл лога
        with open(log_filepath, "r") as file:
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
                            print(f"{log_datetime} FPS: {fps}, Эффективность [FPS/W]: {efficiency}")
                        else:
                            print(
                                f"Поле 'Board Power Draw [W]' отсутствует в документе с датой {log_datetime} в коллекции MongoDB")
                    else:
                        print(
                            f"Не найден документ с датой {log_datetime} в коллекции MongoDB для записи значения FPS")
            if not any_match_found:
                print("В файле лога не было найдено значений FPS")

    # Проверка, что работа бенчмарка была завершена корректно
    def __check_benchmark_log_for_normal_shutdown(self):
        try:
            with open(self.__benchmark_log_path, 'r') as log_file:
                for line in log_file:
                    if "Kombustor shutdown ok." in line:
                        return True
            print("Работа бенчмарка была неожиданно остановлена, запись лога прервалась")
            return False
        except Exception as e:
            print(f"Произошла ошибка: {e}")
            return False

    # Запуск теста бенчмарка со сбором данных в MongoDB (ограниченный по времени)
    def __run_benchmark(self, collection_name, benchmark_start_command, time_before_start_test, time_test_running,
                        time_after_finish_test):
        collection = self.__db[collection_name]  # Название коллекции
        benchmark_process = None  # Инициализация переменной
        total_time = time_before_start_test + time_test_running + time_after_finish_test
        total_time_before_finish_test = time_before_start_test + time_test_running

        # Цикл сбора данных с сенсоров GPU на X секунд
        i = 0
        while i < total_time:
            if i == time_before_start_test:
                # Запуск MSI Kombustor после X секунд сбора данных с сенсоров
                benchmark_process = subprocess.Popen(benchmark_start_command, shell=True)
            if i == total_time_before_finish_test:
                pyautogui.press(
                    'esc')  # Имитация нажатия ESC для остановки теста (окно бенчмарка должно быть активным)
            # Получение данных
            gpu_data = self.__get_gpu_data()
            if gpu_data is None:
                print("Не удалось получить данные с сенсоров GPU. Тест бенчмарка остановлен")
                with contextlib.suppress(Exception):
                    benchmark_process.terminate()
                    benchmark_process.wait()
                return False
            collection.insert_one(gpu_data)  # Сохранение данных с сенсоров в MongoDB
            # Вывод данных
            self.__print_gpu_data(gpu_data)
            # Пауза на 1 секунду
            time.sleep(1)
            i = i + 1
        benchmark_process.terminate()
        benchmark_process.wait()
        if not self.__check_benchmark_log_for_normal_shutdown():  # Проверка, что работа бенчмарка была завершена корректно
            return False

    def run(self):
        pass
