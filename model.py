"""Modelo estatístico de previsão baseado em tendências reais.

Ideia: previsão = climatologia local (o que costuma acontecer nesta época)
         + anomalia recente (quanto os últimos dias fugiram do normal),
           que vai se dissipando com o horizonte
         + tendência recente (inclinação das anomalias, limitada).
Para chuva, a probabilidade parte da frequência histórica e é ajustada
pela umidade recente.
"""
import math
from datetime import date, datetime, timedelta

WINDOW = 7          # +/- dias do ano usados na climatologia
DECAY = 0.8         # quanto da anomalia persiste a cada dia
WEIGHT_DECAY = 0.85  # peso dos dias recentes
RAIN_DAY_MM = 1.0   # limiar para considerar "dia de chuva"
Z_80 = 1.28         # faixa de ~80%


def _doy(iso):
    return datetime.strptime(iso, "%Y-%m-%d").timetuple().tm_yday


def _dist(a, b):
    d = abs(a - b)
    return min(d, 366 - d)


def _mean(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


def _std(xs):
    xs = [x for x in xs if x is not None]
    if len(xs) < 2:
        return 0.0
    m = sum(xs) / len(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1))


def _clip(x, lo, hi):
    return max(lo, min(hi, x))


class Climatology:
    def __init__(self, history):
        self.history = [(_doy(r["date"]), r) for r in history]
        self._memo = {}

    def at(self, day):
        doy = day.timetuple().tm_yday
        if doy in self._memo:
            return self._memo[doy]
        sel = [r for d, r in self.history if _dist(d, doy) <= WINDOW]
        rains = [r["rain"] for r in sel if r["rain"] is not None]
        wet = [x for x in rains if x >= RAIN_DAY_MM]
        result = {
            "tmax": _mean([r["tmax"] for r in sel]),
            "tmin": _mean([r["tmin"] for r in sel]),
            "tmax_std": _std([r["tmax"] for r in sel]),
            "tmin_std": _std([r["tmin"] for r in sel]),
            "rain_freq": len(wet) / len(rains) if rains else 0.0,
            "rain_wet_mean": _mean(wet) or 0.0,
        }
        self._memo[doy] = result
        return result


def _weighted_anomaly(values):
    """values: anomalias do mais antigo ao mais recente."""
    pairs = [(v, WEIGHT_DECAY ** age) for age, v in enumerate(reversed(values)) if v is not None]
    if not pairs:
        return 0.0
    return sum(v * w for v, w in pairs) / sum(w for _, w in pairs)


def _slope(values):
    pts = [(i, v) for i, v in enumerate(values) if v is not None]
    if len(pts) < 3:
        return 0.0
    n = len(pts)
    mx = sum(i for i, _ in pts) / n
    my = sum(v for _, v in pts) / n
    den = sum((i - mx) ** 2 for i, _ in pts)
    return sum((i - mx) * (v - my) for i, v in pts) / den if den else 0.0


def forecast(recent, history, today=None, days=7):
    today = today or date.today()
    clim = Climatology(history)

    observed = [r for r in recent if r["date"] < today.isoformat()]
    reference = {r["date"]: r for r in recent if r["date"] >= today.isoformat()}
    if len(observed) < 5:
        raise ValueError("Dados recentes insuficientes para este local.")

    anom_max, anom_min, rainy = [], [], []
    for r in observed:
        c = clim.at(datetime.strptime(r["date"], "%Y-%m-%d").date())
        anom_max.append(None if r["tmax"] is None else r["tmax"] - c["tmax"])
        anom_min.append(None if r["tmin"] is None else r["tmin"] - c["tmin"])
        if r["rain"] is not None:
            rainy.append(1.0 if r["rain"] >= RAIN_DAY_MM else 0.0)

    a_max, a_min = _weighted_anomaly(anom_max), _weighted_anomaly(anom_min)
    s_max, s_min = _slope(anom_max), _slope(anom_min)
    recent_rain_freq = _mean(rainy[-7:]) or 0.0

    out = []
    for h in range(1, days + 1):  # h=1 -> hoje (último dia observado foi ontem)
        day = today + timedelta(days=h - 1)
        c = clim.at(day)
        persist = DECAY ** h

        def project(base, anomaly, slope, std):
            value = base + anomaly * persist + _clip(slope * h * 0.5, -2.0, 2.0)
            band = Z_80 * std * (1 - 0.4 * persist)
            return value, band

        tmax, bmax = project(c["tmax"], a_max, s_max, c["tmax_std"])
        tmin, bmin = project(c["tmin"], a_min, s_min, c["tmin_std"])
        tmax = max(tmax, tmin + 0.5)

        prob = _clip(
            c["rain_freq"] + (recent_rain_freq - c["rain_freq"]) * 0.5 * persist,
            0.02, 0.98,
        )
        ref = reference.get(day.isoformat())
        out.append({
            "date": day.isoformat(),
            "tmax": round(tmax, 1), "tmax_band": round(bmax, 1),
            "tmin": round(tmin, 1), "tmin_band": round(bmin, 1),
            "rain_prob": round(prob * 100),
            "rain_mm": round(prob * c["rain_wet_mean"], 1),
            "normal_tmax": round(c["tmax"], 1),
            "normal_tmin": round(c["tmin"], 1),
            "ref_tmax": None if not ref else ref["tmax"],
            "ref_tmin": None if not ref else ref["tmin"],
            "ref_rain": None if not ref else ref["rain"],
        })

    return {
        "forecast": out,
        "diagnostic": {
            "anomalia_tmax": round(a_max, 1),
            "anomalia_tmin": round(a_min, 1),
            "tendencia_tmax_por_dia": round(s_max, 2),
            "dias_chuvosos_ultimos_7": round(recent_rain_freq * 7),
            "anos_historico": round(len(history) / 365),
        },
    }
