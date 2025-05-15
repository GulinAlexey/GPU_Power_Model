import pandas as pd
import optuna


# Байесовская оптимизация параметров
class ParameterOptimizer:
    def __init__(self, model, alpha=0.5):
        self.model = model
        self.alpha = alpha
        self.le = None  # Будет установлен далее

    def __objective(self, trial):
        if self.le is None:
            raise ValueError("LabelEncoder не был установлен")
        # Генерация параметров (исключая benchmark_type)
        params = {}
        for feature in self.model.feature_name():
            if feature == 'benchmark_type':
                continue
            params[feature] = trial.suggest_float(feature, 0.0, 1.0)
        # Расчет среднего FPS по всем типам тестов
        total_fps = 0
        test_types = self.le.classes_ # Закодированный категориальный признак
        for test_type_str in test_types:
            # Преобразование типа теста в числовой формат
            test_type_num = self.le.transform([test_type_str])[0]
            # Создать полный набор параметров
            full_params = params.copy()
            full_params['benchmark_type'] = test_type_num
            # Формирование входных данных
            input_data = pd.DataFrame([full_params])
            input_data = input_data[self.model.feature_name()]
            # Предсказание FPS
            fps = self.model.predict(input_data)[0]
            total_fps += fps
        # Усреднение FPS
        avg_fps = total_fps / len(test_types)
        # Целевая функция с усредненным FPS
        power = params.get('power_limit_w', 0.5)
        return (avg_fps * (1 - self.alpha)) / (power * self.alpha + 1e-9)

    def optimize(self, n_trials=1000):
        study = optuna.create_study(direction='maximize')
        study.optimize(self.__objective, n_trials=n_trials)
        return study.best_params
