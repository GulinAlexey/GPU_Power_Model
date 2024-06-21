import csv

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

            print(f"Наименьшее значение мощности GPU: {gpuPowerMin} Вт")
            print("Показания сенсоров при минимальной мощности GPU:")
            i = 0
            for param in gpuPowerMinLine:
                if len(param) > 0:
                    print(f"{paramNamesLine[i].strip()}: {param.strip()}")
                i = i + 1
            break


main = Main()
main.mainLoop()
