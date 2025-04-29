import pandas as pd
import optuna


# Байесовская оптимизация параметров
class ParameterOptimizer:
    def __init__(self, model, test_type, alpha=0.5):
        self.model = model
        self.test_type = test_type
        self.alpha = alpha
        self.le = None  # Будет установлен далее

    def __objective(self, trial):
        if self.le is None:
            raise ValueError("LabelEncoder не был установлен")
        # Преобразовать test_type в числовой формат
        test_type_num = self.le.transform([self.test_type])[0]
        # Генерация параметров
        params = {
            'power_limit_w': trial.suggest_float('power_limit_w', 0.0, 1.0),
            'gpu_clock_offset_mhz': trial.suggest_float('gpu_clock_offset_mhz', 0.0, 1.0),
            'memory_clock_offset_mhz': trial.suggest_float('memory_clock_offset_mhz', 0.0, 1.0),
            'benchmark_type': test_type_num
        }
        # Добавить остальные параметры со средними значениями
        for feature in self.model.feature_name():
            if feature not in params and feature != 'benchmark_type':
                params[feature] = 0.5  # Среднее значение для нормализованных параметров
        # Создать DataFrame со всеми признаками в правильном порядке
        input_data = pd.DataFrame([params])
        # Переупорядочить столбцы как при обучении
        input_data = input_data[self.model.feature_name()]
        # Предсказание FPS
        fps = self.model.predict(input_data)[0]
        # Целевая функция: компромисс между FPS и энергопотреблением
        return (fps * (1 - self.alpha)) / (params['power_limit_w'] * self.alpha + 1e-9)

    def optimize(self, n_trials=100):
        study = optuna.create_study(direction='maximize')
        study.optimize(self.__objective, n_trials=n_trials)
        return study.best_params
