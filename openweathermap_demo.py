import os
import sys
import requests

API_KEY = os.getenv("OPENWEATHER_API_KEY")
if not API_KEY:
    print("OPENWEATHER_API_KEY environment variable is not set.")
    print("Set it and re-run, e.g. in PowerShell:\n$env:OPENWEATHER_API_KEY=\"YOUR_KEY\"\npython openweathermap_demo.py")
    sys.exit(1)

city = "Dallas,US"
url = "https://api.openweathermap.org/data/2.5/weather"
params = {"q": city, "appid": API_KEY, "units": "metric"}

try:
    r = requests.get(url, params=params, timeout=10)
    r.raise_for_status()
except Exception as e:
    print("Request error:", e)
    sys.exit(1)

data = r.json()
try:
    temp_c = data['main']['temp']
    temp_f = temp_c * 9/5 + 32
    desc = data['weather'][0]['description']
    print(f"{city}: {temp_c:.1f}°C / {temp_f:.1f}°F — {desc}")
except Exception as e:
    print('Unexpected response structure:', e)
    print(data)
    sys.exit(1)
