import os
from SocketCalls import SocketCalls


class MainApplyOptimalParameters:
    def __init__(self):
        # Путь сохранённых оптимальных значений параметров работы GPU из DataAnalysisSystem
        self.__optimal_params_file_path = "optimal_params.txt"
        self.__optimal_params = {}

    def __read_params_from_file(self):
        if not os.path.exists(self.__optimal_params_file_path):
            print(f"Файл {self.__optimal_params_file_path} не найден")
            return False
        with open(self.__optimal_params_file_path, 'r') as file:
            lines = file.read().splitlines()
        if len(lines) != 3:
            print(f"Файл {self.__optimal_params_file_path} должен содержать ровно 3 строки")
            return False
        try:
            # Извлечь числовые значения из строк (удалить префиксы и преобразовать в float)
            self.__optimal_params['power_limit_w'] = float(lines[0].split(': ')[1])
            self.__optimal_params['gpu_clock_offset_mhz'] = int(lines[1].split(': ')[1])
            self.__optimal_params['memory_clock_offset_mhz'] = int(lines[2].split(': ')[1])
        except (IndexError, ValueError) as e:
            print(f"Ошибка при чтении файла: {e}. Проверьте формат данных.")
            return False
        print("\n".join([
            "Значения сохранённых оптимальных параметров GPU:",
            f"  Лимит мощности (Вт): {self.__optimal_params['power_limit_w']:.3f}",
            f"  Смещение частоты GPU (МГц): {self.__optimal_params['gpu_clock_offset_mhz']}",
            f"  Смещение частоты памяти (МГц): {self.__optimal_params['memory_clock_offset_mhz']}",
            ""
        ]))
        return True

    def __apply_params(self):
        # Установить значение Power Limit GPU в мВт (1 Вт = 1000 мВт)
        current_power_limit = SocketCalls.call_method_of_undervolting_gpu_system("set_tdp",
                                                                                 round(self.__optimal_params[
                                                                                           'power_limit_w'] * 1000))
        # Вернуть значение смещения частоты GPU
        current_gpu_clock_offset, _ = SocketCalls.call_method_of_undervolting_gpu_system("set_gpu_clock_offset",
                                                                                         round(self.__optimal_params[
                                                                                                   'gpu_clock_offset_mhz']))
        # Вернуть значение смещения частоты памяти
        current_mem_clock_offset = SocketCalls.call_method_of_undervolting_gpu_system("set_mem_clock_offset",
                                                                                      round(self.__optimal_params[
                                                                                                'memory_clock_offset_mhz']))
        print("\n".join([
            "Результат применения параметров GPU:",
            f"  Текущий лимит мощности (Вт): {current_power_limit / 1000}",
            f"  Текущее смещение частоты GPU (МГц): {current_gpu_clock_offset}",
            f"  Текущее смещение частоты памяти (МГц): {current_mem_clock_offset}",
            ""
        ]))

    def main_loop(self):
        print("Применение оптимальных параметров работы GPU")
        if not self.__read_params_from_file():
            print("Не удалось получить значения оптимальных параметров из файла. Дальнейшая работа невозможна")
            return
        self.__apply_params()


main = MainApplyOptimalParameters()
main.main_loop()
