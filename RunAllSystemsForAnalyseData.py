from RunAllSystems import RunAllSystems

procs = RunAllSystems.run_all_systems(RunAllSystems.PYTHON_PATH,
                                      [
                                          'DataAnalysisSystem.py',
                                          'SensorDataCollectionSystem.py',
                                          'UndervoltingGpuSystem.py',
                                          'BenchmarkTestSystem.py',
                                          'MainAnalyseData.py'
                                      ])
