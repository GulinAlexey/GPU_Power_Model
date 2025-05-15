import subprocess
import os
import sys
import threading
from datetime import datetime
import time
import psutil


class RunAllSystems:
    # !!! Замените на ваш путь до python, если нужно
    PYTHON_PATH = os.path.dirname(sys.executable) + r'\python.exe'
    sw_minimize = 6  # Значение константы SW_MINIMIZE (в Windows)

    # Запись потока вывода в файл
    @staticmethod
    def log_stream(stream, log_file):
        with open(log_file, 'a', encoding='utf-8', errors='replace') as log:
            for line in iter(stream.readline, b''):
                try:
                    # Попытка декодировать как UTF-8
                    log_str = line.decode('utf-8').rstrip('\n') # Убрать лишний перевод строки, UTF-8
                except UnicodeDecodeError:
                    try:
                        # Если UTF-8 не сработал, использовать другую кодировку
                        log_str = line.decode('cp1251').rstrip('\n')  # Убрать лишний перевод строки, Windows-1251
                    except UnicodeDecodeError:
                        # Если ничего не помогло, сохранить как есть с заменой нечитаемых символов
                        log_str = line.decode('utf-8', errors='replace').rstrip('\n')
                log.write(log_str)
                print(log_str)
        stream.close()

    @staticmethod
    def run_all_systems(python_path, app_names):
        processes = []  # Список для хранения всех запущенных процессов
        for app_name in app_names:
            log_file = f'{os.path.splitext(app_name)[0]}.log'  # Лог-файл для каждого приложения
            # Открыть лог-файл для записи времени начала работы
            with open(log_file, 'a', encoding='utf-8') as log:
                start_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                log.write(f"[Начало логирования: {start_time}]\n")
            # Параметры для свёрнутого окна
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags = subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = RunAllSystems.sw_minimize  # Окно запускается свёрнутым
            # Запустить приложение со свёрнутым окном, перенаправляя stdout и stderr
            process = subprocess.Popen(
                ['cmd', '/c', f'title {app_name} && {python_path} {app_name}'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NEW_CONSOLE,  # Открыть новое окно консоли
                startupinfo=startupinfo
            )
            # Создать отдельные потоки для логирования stdout и stderr
            stdout_thread = threading.Thread(target=RunAllSystems.log_stream, args=(process.stdout, log_file))
            stderr_thread = threading.Thread(target=RunAllSystems.log_stream, args=(process.stderr, log_file))
            # Запустить потоки
            stdout_thread.start()
            stderr_thread.start()
            print(f"Запущено приложение: {app_name}")
            processes.append(process)
        return processes

    # Ждать завершения главного процесса и остановить все остальные процессы
    @staticmethod
    def wait_and_terminate(processes, main_process_name):
        main_proc = None
        # Найти главный процесс
        for proc in processes:
            cmdline = ' '.join(proc.args)  # Получить командную строку процесса
            if main_process_name in cmdline:
                main_proc = proc
                break
        if not main_proc:
            print(f"Главный процесс {main_process_name} не найден!")
            return False
        print(f"Ожидание завершения {main_process_name}...")
        main_proc.wait()  # Ждать завершения главного процесса
        print(f"Главный процесс завершён. Остановка остальных процессов...")
        for proc in processes:
            if proc != main_proc and proc.poll() is None:  # Если процесс еще работает
                print(f"Завершение процесса: {' '.join(proc.args)}")
                # Завершить процесс и все его дочерние процессы
                parent = psutil.Process(proc.pid)
                for child in parent.children(recursive=True):
                    child.terminate()
                proc.terminate()
                proc.wait()
        print("Все процессы завершены.")
        return True
