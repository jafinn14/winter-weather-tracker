import requests
from typing import Optional, Dict, Any, Tuple
import re

USER_AGENT = "WinterWeatherTracker/1.0 (Educational Project)"

class NWSAPIError(Exception):
    """Custom exception for NWS API errors."""
    pass

def get_location_from_zip(zip_code: str) -> Tuple[float, float, str, str]:
    """
    Convert zip code to lat/lon using a geocoding service.
    Returns: (lat, lon, city, state)
    """
    # Using Zippopotam.us API (free, no API key needed, designed for zip codes)
    url = f"https://api.zippopotam.us/us/{zip_code}"

    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()

        if data and "places" in data and len(data["places"]) > 0:
            place = data["places"][0]
            lat = float(place["latitude"])
            lon = float(place["longitude"])
            city = place.get("place name", "")
            state = place.get("state abbreviation", "")

            return lat, lon, city, state
        else:
            raise NWSAPIError(f"Could not find location for zip code: {zip_code}")
    except requests.RequestException as e:
        raise NWSAPIError(f"Error geocoding zip code: {str(e)}")

def get_grid_point(lat: float, lon: float) -> Tuple[str, int, int]:
    """
    Get NWS grid point information from lat/lon.
    Returns: (forecast_office, grid_x, grid_y)
    """
    url = f"https://api.weather.gov/points/{lat},{lon}"
    headers = {"User-Agent": USER_AGENT}

    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()

        properties = data.get("properties", {})
        grid_id = properties.get("gridId")
        grid_x = properties.get("gridX")
        grid_y = properties.get("gridY")

        if not all([grid_id, grid_x, grid_y]):
            raise NWSAPIError("Incomplete grid point data from NWS API")

        return grid_id, grid_x, grid_y
    except requests.RequestException as e:
        raise NWSAPIError(f"Error getting grid point: {str(e)}")

def get_forecast(grid_id: str, grid_x: int, grid_y: int) -> Dict[str, Any]:
    """
    Get the detailed forecast for a grid point.
    Returns the complete forecast data including all periods.
    """
    url = f"https://api.weather.gov/gridpoints/{grid_id}/{grid_x},{grid_y}/forecast"
    headers = {"User-Agent": USER_AGENT}

    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()

        return data
    except requests.RequestException as e:
        raise NWSAPIError(f"Error getting forecast: {str(e)}")

def get_hourly_forecast(grid_id: str, grid_x: int, grid_y: int) -> Dict[str, Any]:
    """
    Get the hourly forecast for a grid point.
    This provides more granular data including snowfall amounts.
    """
    url = f"https://api.weather.gov/gridpoints/{grid_id}/{grid_x},{grid_y}/forecast/hourly"
    headers = {"User-Agent": USER_AGENT}

    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()

        return data
    except requests.RequestException as e:
        raise NWSAPIError(f"Error getting hourly forecast: {str(e)}")

def get_gridpoint_data(grid_id: str, grid_x: int, grid_y: int) -> Dict[str, Any]:
    """
    Get raw gridpoint forecast data which includes quantitative precipitation,
    snowfall amounts, ice accumulation, etc.
    """
    url = f"https://api.weather.gov/gridpoints/{grid_id}/{grid_x},{grid_y}"
    headers = {"User-Agent": USER_AGENT}

    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()

        return data
    except requests.RequestException as e:
        raise NWSAPIError(f"Error getting gridpoint data: {str(e)}")

def get_area_forecast_discussion(forecast_office: str) -> Dict[str, str]:
    """
    Get the Area Forecast Discussion (AFD) for a forecast office.
    Returns: dict with 'text' and 'issued_at' keys
    """
    url = f"https://api.weather.gov/products/types/AFD/locations/{forecast_office}"
    headers = {"User-Agent": USER_AGENT}

    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()

        # Get the most recent AFD
        graph = data.get("@graph", [])
        if not graph:
            raise NWSAPIError(f"No AFD available for office {forecast_office}")

        # Get the product ID of the most recent discussion
        product_id = graph[0].get("id")

        # Fetch the actual discussion text
        product_url = f"https://api.weather.gov/products/{product_id}"
        product_response = requests.get(product_url, headers=headers, timeout=10)
        product_response.raise_for_status()
        product_data = product_response.json()

        text = product_data.get("productText", "")
        issued_at = graph[0].get("issuanceTime")

        return {
            "text": text,
            "issued_at": issued_at
        }
    except requests.RequestException as e:
        raise NWSAPIError(f"Error getting AFD: {str(e)}")

def extract_winter_weather_info(forecast_periods: list) -> Dict[str, Any]:
    """
    Extract winter weather specific information from forecast periods.
    Looks for snow, ice, temperature, wind chill mentions.
    """
    winter_info = {
        "snow_mentions": [],
        "ice_mentions": [],
        "temperature_data": [],
        "wind_chill_data": []
    }

    for period in forecast_periods:
        period_name = period.get("name", "")
        detailed_forecast = period.get("detailedForecast", "")
        temp = period.get("temperature")

        # Look for snow mentions
        snow_pattern = r'(\d+(?:\.\d+)?)\s*(?:to\s*(\d+(?:\.\d+)?))?\s*(?:inch(?:es)?|")\s*(?:of\s*)?snow'
        snow_matches = re.findall(snow_pattern, detailed_forecast, re.IGNORECASE)
        if snow_matches or "snow" in detailed_forecast.lower():
            winter_info["snow_mentions"].append({
                "period": period_name,
                "forecast": detailed_forecast,
                "amounts": snow_matches
            })

        # Look for ice mentions
        if "ice" in detailed_forecast.lower() or "freezing" in detailed_forecast.lower():
            winter_info["ice_mentions"].append({
                "period": period_name,
                "forecast": detailed_forecast
            })

        # Temperature data
        if temp:
            winter_info["temperature_data"].append({
                "period": period_name,
                "temperature": temp,
                "unit": period.get("temperatureUnit", "F")
            })

        # Wind chill
        if "wind chill" in detailed_forecast.lower():
            winter_info["wind_chill_data"].append({
                "period": period_name,
                "forecast": detailed_forecast
            })

    return winter_info
