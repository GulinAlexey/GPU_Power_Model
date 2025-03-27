import subprocess
import os
import sys

# !!! Замените на ваш путь до python, если нужно
PYTHON_PATH = os.path.dirname(sys.executable) + r'\python.exe'

def run_all_systems_for_collect_data(python_path):
    app_names = [
        'SensorDataCollectionSystem.py',
        'UndervoltingGpuSystem.py',
        'BenchmarkTestSystem.py',
        'MainTestAndCollectData.py'
    ]

    processes = []  # Список для хранения всех запущенных процессов
    for app_name in app_names:
        log_file = f'{os.path.splitext(app_name)[0]}.log'  # Лог-файл для каждого приложения

        # Открыть лог-файл на запись
        with open(log_file, 'w') as log:
            # Запустить приложение в новой консоли
            process = subprocess.Popen(
                f'start cmd /k "{python_path} {app_name}"',
                stdout=log,                   # Перенаправить стандартный вывод в лог-файл
                stderr=subprocess.STDOUT,     # Перенаправить ошибки в тот же лог-файл
                shell=True                    # Разрешить использование оболочки
            )
            print(f"Запущено приложение: {app_name}")
            processes.append(process)
    return processes

procs = run_all_systems_for_collect_data(PYTHON_PATH)