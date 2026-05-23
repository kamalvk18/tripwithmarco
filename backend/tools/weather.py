import os
import requests
from datetime import datetime
from dotenv import load_dotenv
from backend.config import REQUEST_TIMEOUT_SECONDS

load_dotenv()


def get_weather_forecast(city: str, country_code: str = "") -> dict:
    """
    Get 5-day weather forecast for a city.
    country_code is optional — improves precision but not required.
    Returns {"error": "..."} on any failure so callers don't need to catch.
    """
    api_key = os.getenv("OPENWEATHER_API_KEY")
    if not api_key:
        return {"error": "OPENWEATHER_API_KEY is not set"}

    try:
        # Step 1 — Get coordinates for the city
        geo_url = "http://api.openweathermap.org/geo/1.0/direct"
        q = f"{city},{country_code}" if country_code else city
        geo_params = {"q": q, "limit": 1, "appid": api_key}

        geo_response = requests.get(geo_url, params=geo_params, timeout=REQUEST_TIMEOUT_SECONDS)
        geo_response.raise_for_status()
        geo_data = geo_response.json()

        if not geo_data:
            return {"error": f"Could not find location: {city}"}

        lat = geo_data[0]["lat"]
        lon = geo_data[0]["lon"]

        # Step 2 — Get 5-day forecast (8 readings/day × 5 days = 40 entries)
        forecast_url = "http://api.openweathermap.org/data/2.5/forecast"
        forecast_params = {
            "lat": lat,
            "lon": lon,
            "appid": api_key,
            "units": "metric",
            "cnt": 40,
        }

        forecast_response = requests.get(forecast_url, params=forecast_params, timeout=REQUEST_TIMEOUT_SECONDS)
        forecast_response.raise_for_status()
        forecast_data = forecast_response.json()

        if forecast_data.get("cod") != "200":
            return {"error": f"OpenWeather API error: {forecast_data.get('message', 'unknown')}"}

        # Step 3 — Summarize by day
        daily_summary: dict = {}

        for item in forecast_data["list"]:
            day = datetime.fromtimestamp(item["dt"]).strftime("%Y-%m-%d")

            if day not in daily_summary:
                daily_summary[day] = {"temps": [], "conditions": [], "rain": False}

            daily_summary[day]["temps"].append(item["main"]["temp"])
            daily_summary[day]["conditions"].append(item["weather"][0]["main"])

            if item.get("rain") or "Rain" in item["weather"][0]["main"]:
                daily_summary[day]["rain"] = True

        # Step 4 — Convert to clean list of day summaries
        forecast_summary = []
        for day, data in daily_summary.items():
            temps = data["temps"]
            dominant_condition = max(set(data["conditions"]), key=data["conditions"].count)
            forecast_summary.append({
                "date": day,
                "avg_temp": round(sum(temps) / len(temps), 1),
                "min_temp": round(min(temps), 1),
                "max_temp": round(max(temps), 1),
                "condition": dominant_condition,
                "rain_expected": data["rain"],
            })

        return {"city": city, "country": country_code, "forecast": forecast_summary}

    except requests.Timeout:
        return {"error": f"Weather request timed out for {city}"}
    except requests.RequestException as e:
        return {"error": f"Weather network error: {e}"}
    except Exception as e:
        print(f"Unexpected weather error for {city}: {e}")
        return {"error": f"Weather lookup failed: {e}"}


def format_weather_for_marco(weather_data: dict) -> str:
    """Format weather data into a string Marco can use in his response."""
    
    if "error" in weather_data:
        return f"Weather data unavailable: {weather_data['error']}"
    
    lines = [f"Weather forecast for {weather_data['city']}:"]
    
    for day in weather_data["forecast"]:
        rain_note = " ☔ Rain expected" if day["rain_expected"] else ""
        lines.append(
            f"  {day['date']}: {day['condition']}, "
            f"{day['min_temp']}°C - {day['max_temp']}°C{rain_note}"
        )
    
    return "\n".join(lines)


if __name__ == "__main__":
    # Quick test
    weather = get_weather_forecast("Amsterdam", "NL")
    print(format_weather_for_marco(weather))