"""Deterministic Alternaria leaf blight risk scoring (specification v1.0)."""
from typing import Optional

GROWTH_STAGES = {
    'early vegetative': 0.25,
    'vegetative': 0.50,
    'bud initiation': 0.65,
    'flowering': 0.80,
    'seed filling': 0.70,
    'physiological maturity': 0.30,
}
WEIGHTS = {'temperature': 0.25, 'humidity': 0.25, 'rainfall': 0.15,
           'rainy_day': 0.10, 'disease_severity': 0.15, 'growth_stage': 0.10}

def temperature_score(tmax: float, tmin: float) -> tuple[float, float]:
    mean = (tmax + tmin) / 2.0
    if mean < 13: score = 0.05
    elif mean < 20: score = 0.25
    elif mean < 24: score = 0.60
    elif mean <= 28.0: score = 1.00
    elif mean <= 32.0: score = 0.75
    elif mean <= 35.8: score = 0.40
    else: score = 0.05
    return round(mean, 2), score

def humidity_score(value: float) -> float:
    if value < 60: return 0.10
    if value < 70: return 0.25
    if value < 80: return 0.50
    if value < 90: return 0.75
    return 1.00

def rainfall_score(value: float) -> float:
    if value == 0: return 0.00
    if value <= 5.0: return 0.25
    if value <= 15.0: return 0.60
    return 0.80

def rainy_day_score(value: float) -> float:
    return 0.0 if value < 2.5 else 1.0

def disease_score(pdi: float) -> float:
    if pdi < 5: return 0.10
    if pdi < 15: return 0.40
    if pdi <= 30: return 0.70
    return 1.00

def classify(edps: float) -> str:
    if edps <= 25: return 'LOW'
    if edps <= 50: return 'MODERATE'
    if edps <= 75: return 'HIGH'
    return 'VERY HIGH'

def advisory(risk: str) -> str:
    return {
        'LOW': 'Continue routine crop monitoring.',
        'MODERATE': 'Monitor lower and middle canopy leaves regularly.',
        'HIGH': 'Conduct field scouting and assess early disease symptoms; consider management measures based on field diagnosis.',
        'VERY HIGH': 'Intensify field surveillance, assess disease severity and follow locally validated fungicide recommendations where necessary.'
    }[risk]

def calculate_day(*, tmax: Optional[float], tmin: Optional[float], humidity: Optional[float], rainfall: Optional[float], pdi: Optional[float], growth_stage: Optional[str]):
    required = [tmax, tmin, humidity, rainfall, pdi, growth_stage]
    if any(x is None for x in required):
        return {'status': 'INCOMPLETE_DATA', 'message': 'One or more required inputs are missing; EDPS was not calculated.'}
    if not (0 <= humidity <= 100 and rainfall >= 0 and 0 <= pdi <= 100):
        raise ValueError('Humidity must be 0–100, rainfall must be non-negative, and PDI must be 0–100.')
    stage = growth_stage.strip().lower()
    if stage not in GROWTH_STAGES:
        raise ValueError(f'Unsupported growth stage. Choose one of: {", ".join(GROWTH_STAGES)}')
    mean, ts = temperature_score(tmax, tmin)
    rhs = humidity_score(humidity)
    rs = rainfall_score(rainfall)
    rds = rainy_day_score(rainfall)
    ds = disease_score(pdi)
    gs = GROWTH_STAGES[stage]
    edps = round(100 * (WEIGHTS['temperature']*ts + WEIGHTS['humidity']*rhs + WEIGHTS['rainfall']*rs + WEIGHTS['rainy_day']*rds + WEIGHTS['disease_severity']*ds + WEIGHTS['growth_stage']*gs), 2)
    risk = classify(edps)
    return {'status': 'COMPLETE', 'temperature_mean_c': round(mean, 2), 'temperature_score': ts,
            'humidity_score': rhs, 'rainfall_score': rs, 'rainy_day_score': rds,
            'disease_pressure_score': ds, 'growth_stage_score': gs,
            'edps': edps, 'risk_category': risk, 'advisory': advisory(risk)}
