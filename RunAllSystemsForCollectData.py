from RunAllSystems import RunAllSystems

procs = RunAllSystems.run_all_systems(RunAllSystems.PYTHON_PATH,
                                      [
                                          'SensorDataCollectionSystem.py',
                                          'UndervoltingGpuSystem.py',
                                          'BenchmarkTestSystem.py',
                                          'MainTestAndCollectData.py'
                                      ])

# Ждать завершения главного процесса и остановить остальные процессы
RunAllSystems.wait_and_terminate(procs, 'MainTestAndCollectData.py')