import os
import requests

API_KEY = os.getenv('OPENWEATHER_API_KEY')
if not API_KEY:
    print('OPENWEATHER_API_KEY not set')
    raise SystemExit(1)

city = 'Dallas,US'
url = 'https://api.openweathermap.org/data/2.5/weather'
params = {'q': city, 'appid': API_KEY, 'units': 'metric'}

try:
    r = requests.get(url, params=params, timeout=10)
except Exception as e:
    print('request_error:', str(e))
    raise SystemExit(1)

# parse response without showing request URL or key
try:
    data = r.json()
except Exception:
    print('invalid_json_response')
    raise SystemExit(1)

if r.status_code == 200:
    temp_c = data.get('main', {}).get('temp')
    desc = data.get('weather', [{}])[0].get('description')
    if temp_c is not None and desc is not None:
        print(f'{city}: {temp_c:.1f}°C — {desc}')
    else:
        print('unexpected_success_structure')
else:
    # print only the error message returned by API
    print('error:', data.get('message', data))
