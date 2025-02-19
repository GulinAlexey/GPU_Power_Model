import csv
import matplotlib.pyplot as plt
from pynvraw import api, get_phys_gpu

class Main:
    def __init__(self):
        pass

    def mainLoop(self):
        while True:
            print(api.get_driver_version())
            cuda_dev = 0
            gpu = get_phys_gpu(cuda_dev)
            print(f'{gpu.name}: core={gpu.core_temp} hotspot={gpu.hotspot_temp} vram={gpu.vram_temp}')
            print(f'{gpu.name}: fan={gpu.fan}%')
            pinfo = api.get_power_info(gpu.handle)
            print(f'power info: {pinfo}')
            print(f'Voltage: {api.get_core_voltage(gpu.handle)}V')
            break

main = Main()
main.mainLoop()
