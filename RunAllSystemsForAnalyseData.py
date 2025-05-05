import RunAllSystems

procs = RunAllSystems.run_all_systems(RunAllSystems.PYTHON_PATH,
                                      [
                                          'SensorDataCollectionSystem.py',
                                          'UndervoltingGpuSystem.py',
                                          'BenchmarkTestSystem.py',
                                          'MainAnalyseData.py'
                                      ])
