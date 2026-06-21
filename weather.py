"""
Fetches hourly wind speed and cloud cover forecast from Open-Meteo (no API key required).
https://open-meteo.com/
"""

import requests
from datetime import datetime

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"


def get_wind_cloud_forecast(lat, lon, days=2):
    """
    Returns a list of hourly forecast dicts:
        {"time": datetime, "wind_mph": float, "cloud_pct": float}
    covering the next `days` days.
    """
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": "windspeed_10m,cloudcover",
        "wind_speed_unit": "mph",
        "forecast_days": days,
        "timezone": "auto",
    }

    response = requests.get(OPEN_METEO_URL, params=params, timeout=15)
    response.raise_for_status()
    data = response.json()

    hourly = data["hourly"]
    times = hourly["time"]
    winds = hourly["windspeed_10m"]
    clouds = hourly["cloudcover"]

    return [
        {
            "time": datetime.fromisoformat(t),
            "wind_mph": float(w),
            "cloud_pct": float(c),
        }
        for t, w, c in zip(times, winds, clouds)
    ]
