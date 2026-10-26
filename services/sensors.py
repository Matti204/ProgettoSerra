"""Punto di estensione per sensori futuri: produzione mai simulata."""


class SensorService:
    def __init__(self, simulated):
        self.simulated = simulated

    def readings(self):
        # Valori dimostrativi fissi, esplicitamente etichettati, senza GPIO.
        return [
            {"id": "temperature", "label": "Temperatura", "value": 24.6 if self.simulated else None,
             "unit": "°C", "status": "simulated" if self.simulated else "unavailable"},
            {"id": "humidity", "label": "Umidità", "value": 62 if self.simulated else None,
             "unit": "%", "status": "simulated" if self.simulated else "unavailable"},
        ]
