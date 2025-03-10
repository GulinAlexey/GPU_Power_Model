import csv
from datetime import datetime, timedelta
import os
import re

input_filename= 'furmark 2025-03-10 19-51-09-69 fps.csv' # Заменить на новое или сделать входным параметром

def calculate_timestamps(log_file_path):
    # Извлечь имя файла
    filename = os.path.basename(log_file_path)

    # Регулярное выражение для извлечения даты и времени из имени файла
    match = re.search(r'(\d{4})-(\d{2})-(\d{2}) (\d{2})-(\d{2})-(\d{2})', filename)
    if not match:
        raise ValueError("Имя файла не содержит дату и время в ожидаемом формате.")

    # Достать группы из регулярного выражения и форматировать datetime объект
    year, month, day, hour, minute, second = map(int, match.groups())
    start_time = datetime(year, month, day, hour, minute, second)

    timestamps = []

    with open(log_file_path, mode='r', newline='') as file:
        reader = csv.reader(file)
        next(reader)  # Пропуск заголовка

        for index, row in enumerate(reader):
            if row and row[0].isdigit():
                fps_value = int(row[0])
                current_time = start_time + timedelta(seconds=index)
                timestamps.append((current_time.strftime("%Y-%m-%d %H:%M:%S"), fps_value))
            else:
                print(f"Невозможно преобразовать значение '{row[0]}' в целое число.")

    return timestamps


# Полный путь до файла
log_file_path = 'C:\\Fraps\\Benchmarks\\' + input_filename
timestamps = calculate_timestamps(log_file_path)

for time_str, fps in timestamps:
    print(f"Время: {time_str} — FPS: {fps}")