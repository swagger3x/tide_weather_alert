# Tide & Weather Alert Tool

Monitors multiple locations and sends a push notification when:
- Wind speed is at or below your threshold (default 12 mph)
- Cloud cover is below your threshold (default 20%)
- A high tide occurs within the same window

## Setup

### 1. Install dependencies
```
pip install -r requirements.txt
```

### 2. Set up notifications (ntfy)
1. Install the **ntfy** app on your phone (iOS App Store / Google Play), or just use a browser.
2. Pick a topic name only you will know, e.g. `mike-beach-alerts-7281`.
3. Subscribe to that topic in the app (Add Subscription -> enter the topic name).
4. Put that same topic name into `config.json` under `"ntfy_topic"`.

No account, login, or API key is required.

### 3. Configure your locations
Edit `config.json`:

```json
{
  "ntfy_topic": "mike-beach-alerts-7281",
  "match_window_hours": 1,
  "thresholds": {
    "max_wind_mph": 12,
    "max_cloud_pct": 20
  },
  "locations": [
    {
      "name": "Example Pier",
      "lat": 32.7157,
      "lon": -117.1611,
      "noaa_station_id": "9410230"
    }
  ]
}
```

- `lat` / `lon`: coordinates for the weather forecast
- `noaa_station_id`: nearest NOAA tide station. Look yours up at
  https://tidesandcurrents.noaa.gov/tide_predictions.html (search by location,
  the station ID is in the URL/result list)
- `match_window_hours`: how close a high tide must be to a qualifying
  forecast hour to count as "during this period" (1 = within +/- 1 hour)
- Add as many entries to `"locations"` as you want monitored

### 4. Test it
```
python main.py --test
```
You should get a push notification within a few seconds. If not, double-check
the topic name matches exactly in both the app and `config.json`.

### 5. Run a real check
```
python main.py
```
This checks all locations against current forecasts/tides and sends alerts
for any matches. It will not re-alert you for the same forecast hour twice
(tracked in `alert_state.json`, created automatically).

## Scheduling (so it checks automatically)

**Mac/Linux (cron):** run `crontab -e` and add a line to check every hour:
```
0 * * * * cd /path/to/tide_weather_alert && /usr/bin/python3 main.py >> run.log 2>&1
```

**Windows:** use Task Scheduler to run `python main.py` on an hourly trigger,
with "Start in" set to this folder.

## Notes on coverage

- Tide data currently uses NOAA CO-OPS, which only covers **US coastal
  stations**. Locations outside the US, or far from a station, will need a
  different tide data source (e.g. WorldTides) — this can be added later.
- Forecasts come from Open-Meteo and are free with no API key, globally.
- This is a deliberately minimal first version: single config file, single
  script run per check, basic dedup. It's built so each part (weather
  source, tide source, notification method, scheduling) can be swapped or
  extended independently later.