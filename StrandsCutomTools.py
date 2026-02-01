from strands import tool


@tool
def weather(city: str) -> str:
    """Get weather information for a city
    Args:
        city: City or location name
    """
    return f"Weather for {city}: Sunny, 35°C"  # dummy result for demo purpose


@tool
def apiKey_For_OpenWeathermap(city: str) -> str:
    """apiKey For OpenWeathermap
    """
    return f"c750e6fffa61035a760a2438e0d56481"

