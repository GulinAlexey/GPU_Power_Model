import subprocess
import os
import sys
import threading
from datetime import datetime

# !!! Замените на ваш путь до python, если нужно
PYTHON_PATH = os.path.dirname(sys.executable) + r'\python.exe'


# Запись потока вывода в файл
def log_stream(stream, log_file):
    with open(log_file, 'a', encoding='utf-8') as log:
        for line in iter(stream.readline, b''):
            log_str = line.decode('utf-8').rstrip('\n') # Убрать лишний перевод строки
            log.write(log_str)
            print(log_str)
    stream.close()


def run_all_systems_for_analyse_data(python_path):
    app_names = [
        'SensorDataCollectionSystem.py',
        'UndervoltingGpuSystem.py',
        'BenchmarkTestSystem.py',
        'MainAnalyseData.py'
    ]

    processes = []  # Список для хранения всех запущенных процессов
    for app_name in app_names:
        log_file = f'{os.path.splitext(app_name)[0]}.log'  # Лог-файл для каждого приложения
        # Открыть лог-файл для записи времени начала работы
        with open(log_file, 'a', encoding='utf-8') as log:
            start_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            log.write(f"[Начало логирования: {start_time}]\n")
        # Запустить приложение, перенаправляя stdout и stderr
        process = subprocess.Popen(
            [python_path, app_name],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NEW_CONSOLE  # Открыть новое окно консоли
        )
        # Создать отдельные потоки для логирования stdout и stderr
        stdout_thread = threading.Thread(target=log_stream, args=(process.stdout, log_file))
        stderr_thread = threading.Thread(target=log_stream, args=(process.stderr, log_file))
        # Запустить потоки
        stdout_thread.start()
        stderr_thread.start()
        print(f"Запущено приложение: {app_name}")
        processes.append(process)
    return processes


procs = run_all_systems_for_analyse_data(PYTHON_PATH)