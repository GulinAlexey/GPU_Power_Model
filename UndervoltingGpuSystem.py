import atexit
import pynvml
import os


class UndervoltingGpuSystem:
    def __init__(self):
        # Регистрация метода cleanup для выполнения при завершении программы
        atexit.register(self.__cleanup)
        # Инициализация pynvml
        pynvml.nvmlInit()
        # Получение количества GPU
        device_count = pynvml.nvmlDeviceGetCount()
        if device_count == 0:
            print("Не найдено GPU NVIDIA")
            exit()
        # Получение первого GPU для pynvml
        self.__handle = pynvml.nvmlDeviceGetHandleByIndex(0)
        # Путь и параметры для NVIDIA Inspector
        nvidia_inspector_folder = "C:\\NVIDIA_Inspector_1.9.8.7_Beta\\"
        nvidia_inspector_name = "nvidiaInspector.exe"
        # Частота GPU
        nvidia_inspector_gpu_clock_offset_options = "-setBaseClockOffset:0,0,"  # Справа этой строки добавлять само значение
        self.__nvidia_inspector_gpu_clock_offset_command = f'"{nvidia_inspector_folder + nvidia_inspector_name}" {nvidia_inspector_gpu_clock_offset_options}'
        self.__default_gpu_clock_offset = 0
        self.__current_gpu_clock_offset = self.__default_gpu_clock_offset
        # Частота памяти
        nvidia_inspector_mem_clock_offset_options = "-setMemoryClockOffset:0,0,"  # Справа этой строки добавлять само значение
        self.__nvidia_inspector_mem_clock_offset_command = f'"{nvidia_inspector_folder + nvidia_inspector_name}" {nvidia_inspector_mem_clock_offset_options}'
        self.__default_mem_clock_offset = 0
        self.__current_mem_clock_offset = self.__default_mem_clock_offset

    # Конец работы программы
    @staticmethod
    def __cleanup():
        pynvml.nvmlShutdown()
        print("Работа программы завершена")

    # Вывод данных о TDP и Power Limit
    def __print_tdp_info(self):
        power_limit = pynvml.nvmlDeviceGetEnforcedPowerLimit(self.__handle)
        power_limit_default = pynvml.nvmlDeviceGetPowerManagementDefaultLimit(self.__handle)
        power_limit_constraints = pynvml.nvmlDeviceGetPowerManagementLimitConstraints(self.__handle)

        print(f"Текущий Power Limit: {power_limit / 1000} W")
        print(f"Текущий TDP Limit: {(power_limit / power_limit_constraints[1]) * 100} %")
        print(f"Power Limit по умолчанию: {power_limit_default / 1000} W")
        print(
            f"Ограничения Power Limit: {power_limit_constraints[0] / 1000} W - {power_limit_constraints[1] / 1000} W")  # max Power Limit = 100% TDP
        print(f"Ограничения TDP: {(power_limit_constraints[0] / power_limit_constraints[1]) * 100} % - 100 %")

    # Уменьшение Power Limit GPU для прохождения следующего теста бенчмарка
    def __reduce_tdp(self, milliwatt_reducing_value):
        # Получение текущего Power Limit (в абсолютных величинах, а не проценты TDP)
        power_limit = pynvml.nvmlDeviceGetEnforcedPowerLimit(self.__handle)
        power_limit_constraints = pynvml.nvmlDeviceGetPowerManagementLimitConstraints(self.__handle)

        # Уменьшение TDP
        new_power_limit = max(power_limit_constraints[0],
                              power_limit - milliwatt_reducing_value)  # Уменьшить на X мВт
        pynvml.nvmlDeviceSetPowerManagementLimit(self.__handle, new_power_limit)

        power_limit = pynvml.nvmlDeviceGetPowerManagementLimit(self.__handle)
        print(f"Новый Power Limit: {power_limit / 1000} W")
        print(f"Новое ограничение TDP: {(power_limit / power_limit_constraints[1]) * 100} %")
        return power_limit

    # Вернуть значение Power Limit GPU по умолчанию
    def __set_tdp_to_default(self):
        default_power_limit = pynvml.nvmlDeviceGetPowerManagementDefaultLimit(self.__handle)
        pynvml.nvmlDeviceSetPowerManagementLimit(self.__handle, default_power_limit)
        return default_power_limit

    # Вывод данных о min, max частотах GPU и смещении
    def __print_gpu_clock_info(self):
        # Получение частот
        min_gpu_clock, max_gpu_clock = pynvml.nvmlDeviceGetMinMaxClockOfPState(self.__handle, pynvml.NVML_PSTATE_0,
                                                                               pynvml.NVML_CLOCK_GRAPHICS)
        print(f"Мин. частота GPU: {min_gpu_clock} MHz")
        print(f"Макс. частота GPU: {max_gpu_clock} MHz")
        print(f"Смещение частоты GPU: {self.__current_gpu_clock_offset} MHz")

    # Увеличение смещения частоты GPU для прохождения следующего теста бенчмарка
    def __increase_gpu_clock_offset(self, megahertz_increasing_value):
        new_clock_offset = self.__current_gpu_clock_offset + megahertz_increasing_value
        os.system(self.__nvidia_inspector_gpu_clock_offset_command + str(new_clock_offset))
        self.__current_gpu_clock_offset = new_clock_offset
        # В качестве возвращаемого значения - max частота GPU, по которой можно проверить, что изменения были успешно применены
        min_gpu_clock, max_gpu_clock = pynvml.nvmlDeviceGetMinMaxClockOfPState(self.__handle, pynvml.NVML_PSTATE_0,
                                                                               pynvml.NVML_CLOCK_GRAPHICS)
        return max_gpu_clock

    # Вернуть значение смещения частоты GPU по умолчанию
    def __set_gpu_clock_offset_to_default(self):
        os.system(self.__nvidia_inspector_gpu_clock_offset_command + str(self.__default_gpu_clock_offset))
        self.__current_gpu_clock_offset = self.__default_gpu_clock_offset
        # В качестве возвращаемого значения - max частота GPU, по которой можно проверить, что изменения были успешно применены
        min_gpu_clock, max_gpu_clock = pynvml.nvmlDeviceGetMinMaxClockOfPState(self.__handle, pynvml.NVML_PSTATE_0,
                                                                               pynvml.NVML_CLOCK_GRAPHICS)
        return max_gpu_clock

    # Увеличение смещения частоты памяти для прохождения следующего теста бенчмарка
    def __increase_mem_clock_offset(self, megahertz_increasing_value):
        new_clock_offset = self.__current_mem_clock_offset + megahertz_increasing_value
        os.system(self.__nvidia_inspector_mem_clock_offset_command + str(new_clock_offset))
        self.__current_mem_clock_offset = new_clock_offset

    # Вернуть значение смещения частоты памяти по умолчанию
    def __set_mem_clock_offset_to_default(self):
        os.system(self.__nvidia_inspector_mem_clock_offset_command + str(self.__default_mem_clock_offset))
        self.__current_mem_clock_offset = self.__default_mem_clock_offset

    def run(self):
        pass
