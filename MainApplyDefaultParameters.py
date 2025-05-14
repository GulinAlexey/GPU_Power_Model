from SocketCalls import SocketCalls


class MainApplyDefaultParameters:
    def __apply_default_params(self):
        # Вернуть значение Power Limit GPU по умолчанию
        current_power_limit = SocketCalls.call_method_of_undervolting_gpu_system("set_tdp_to_default")
        # Вернуть значение смещения частоты GPU по умолчанию
        current_gpu_clock_offset, _ = SocketCalls.call_method_of_undervolting_gpu_system("set_gpu_clock_offset_to_default")
        # Вернуть значение смещения частоты памяти по умолчанию
        current_mem_clock_offset = SocketCalls.call_method_of_undervolting_gpu_system("set_mem_clock_offset_to_default")
        print("\n".join([
            "Результат применения параметров GPU:",
            f"  Текущий лимит мощности (Вт): {current_power_limit / 1000}",
            f"  Текущее смещение частоты GPU (МГц): {current_gpu_clock_offset}",
            f"  Текущее смещение частоты памяти (МГц): {current_mem_clock_offset}",
            ""
        ]))


    def main_loop(self):
        print("Применение параметров работы GPU по умолчанию")
        self.__apply_default_params()


main = MainApplyDefaultParameters()
main.main_loop()