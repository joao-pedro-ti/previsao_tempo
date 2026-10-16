"""Acesso aos dados reais (Open-Meteo: gratuito, sem chave de API)."""
import time
from datetime import date, timedelta

import requests

TIMEOUT = 20
CACHE_TTL = 1800  # 30 minutos
DAILY = "temperature_2m_max,temperature_2m_min,precipitation_sum"

_cache = {}


def _get(url, params):
    key = (url, tuple(sorted(params.items())))
    hit = _cache.get(key)
    if hit and time.time() - hit[0] < CACHE_TTL:
        return hit[1]
    resp = requests.get(url, params=params, timeout=TIMEOUT)
    resp.raise_for_status()
    data = resp.json()
    _cache[key] = (time.time(), data)
    return data


def _rows(payload):
    d = payload["daily"]
    return [
        {"date": t, "tmax": a, "tmin": b, "rain": c}
        for t, a, b, c in zip(
            d["time"],
            d["temperature_2m_max"],
            d["temperature_2m_min"],
            d["precipitation_sum"],
        )
    ]


def search_places(query, count=5):
    data = _get(
        "https://geocoding-api.open-meteo.com/v1/search",
        {"name": query, "count": count, "language": "pt"},
    )
    return [
        {
            "name": r["name"],
            "region": r.get("admin1", ""),
            "country": r.get("country", ""),
            "lat": r["latitude"],
            "lon": r["longitude"],
        }
        for r in data.get("results", [])
    ]


def fetch_recent(lat, lon, past_days=14, forecast_days=8):
    """Últimos dias observados + previsão numérica (usada só como referência)."""
    data = _get(
        "https://api.open-meteo.com/v1/forecast",
        {
            "latitude": lat,
            "longitude": lon,
            "daily": DAILY,
            "past_days": past_days,
            "forecast_days": forecast_days,
            "timezone": "auto",
        },
    )
    return _rows(data)


def fetch_history(lat, lon, years=5):
    """Histórico de vários anos para calcular a climatologia local."""
    end = date.today() - timedelta(days=7)
    start = end - timedelta(days=365 * years)
    data = _get(
        "https://archive-api.open-meteo.com/v1/archive",
        {
            "latitude": lat,
            "longitude": lon,
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "daily": DAILY,
            "timezone": "auto",
        },
    )
    return _rows(data)
