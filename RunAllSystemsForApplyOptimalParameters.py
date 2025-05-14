from RunAllSystems import RunAllSystems

procs = RunAllSystems.run_all_systems(RunAllSystems.PYTHON_PATH,
                                      [
                                          # Запустить и систему сбора данных, так как изменения смещения частоты
                                          # через систему андервольтинга нужно сохранить в ней,
                                          # иначе система андервольтинга выдаст ошибку при попытке подключения к ней
                                          'SensorDataCollectionSystem.py',
                                          'UndervoltingGpuSystem.py',
                                          'MainApplyOptimalParameters.py'
                                      ])

# Ждать завершения главного процесса и остановить остальные процессы
RunAllSystems.wait_and_terminate(procs, 'MainApplyOptimalParameters.py')