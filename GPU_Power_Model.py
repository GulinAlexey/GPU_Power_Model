import csv
import matplotlib.pyplot as plt #версия 3.9.0

class Main:
    def __init__(self):
        self.__inputFile = "GPU-Z Sensor Log.csv"

    def mainLoop(self):
        while True:
            file = open(self.__inputFile, mode='r')
            csvFile = csv.reader(file)

            gpuPowerList = []
            gpuPowerMin = float('Inf')
            gpuPowerMinLine = []
            paramNamesLine = []
            print("Значения мощности GPU [W]:")
            for line in csvFile:
                if line[6] != " GPU Power [W] ":
                    currentGpuPower = float(line[6])
                    print(currentGpuPower)

                    gpuPowerList.append(currentGpuPower)
                    if currentGpuPower < gpuPowerMin and currentGpuPower != 0:
                        gpuPowerMin = currentGpuPower
                        gpuPowerMinLine = line
                else:
                    paramNamesLine = line

            if gpuPowerMin == float('Inf') or gpuPowerMin == 0:
                print("Определить наименьшую мощность GPU не удалось")
                break
            print(f"\nНаименьшее значение мощности GPU: {gpuPowerMin} Вт")
            print("Показания сенсоров при минимальной мощности GPU:")
            i = 0
            for param in gpuPowerMinLine:
                if len(param) > 0:
                    print(f"{paramNamesLine[i].strip()}: {param.strip()}")
                i = i + 1
            plt.plot(gpuPowerList)
            plt.show()
            break


main = Main()
main.mainLoop()
