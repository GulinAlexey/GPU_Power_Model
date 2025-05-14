from RunAllSystems import RunAllSystems

procs = RunAllSystems.run_all_systems(RunAllSystems.PYTHON_PATH,
                                      [
                                          'UndervoltingGpuSystem.py',
                                          'MainApplyOptimalParameters.py'
                                      ])
