"""
National Blend of Models (NBM) data integration.
Provides access to blended model forecasts.

Source: https://blend.mdl.nws.noaa.gov/
Data: https://nomads.ncep.noaa.gov/
"""

import requests
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime, timedelta

USER_AGENT = "WinterWeatherTracker/1.0 (Educational Project)"

# NBM visualization tools
NBM_DASHBOARD_URL = "https://blend.mdl.nws.noaa.gov/nbm-dashboard"
NBM_VIEWER_URL = "https://digital.weather.gov/"


@dataclass
class NBMProduct:
    """Represents an NBM forecast product."""
    name: str
    description: str
    url: str
    element: str
    forecast_hour: int


def get_nbm_snow_graphics() -> List[Dict[str, str]]:
    """
    Get URLs for NBM snow forecast graphics.

    Returns:
        List of dictionaries with product info and URLs
    """
    # These are from the NWS Digital Forecast Viewer which displays NBM data
    base_url = "https://digital.weather.gov"

    products = [
        {
            "name": "NBM Snow Amount (24hr)",
            "description": "Expected snowfall accumulation from National Blend of Models",
            "url": f"{base_url}/?zoom=4&lat=42&lon=-74&layers=F000BTTTFTT&region=0&element=SnowAmt&mession=",
            "type": "interactive"
        },
        {
            "name": "NBM Probability of Snow",
            "description": "Probability of measurable snowfall",
            "url": f"{base_url}/?zoom=4&lat=42&lon=-74&layers=F000BTTTFTT&region=0&element=PoP12&mession=",
            "type": "interactive"
        },
        {
            "name": "NBM Snow Level",
            "description": "Elevation where snow begins (feet MSL)",
            "url": "https://www.weather.gov/aprfc/snowlvl",
            "type": "page"
        }
    ]

    return products


def get_model_comparison_urls() -> Dict[str, Dict[str, str]]:
    """
    Get URLs for comparing different model forecasts.

    Returns:
        Dictionary of model names to their viewer URLs
    """
    return {
        "NBM": {
            "name": "National Blend of Models",
            "description": "Blended guidance from multiple models",
            "dashboard": NBM_DASHBOARD_URL,
            "viewer": "https://digital.weather.gov/",
            "data_info": "https://vlab.noaa.gov/web/mdl/nbm"
        },
        "GFS": {
            "name": "Global Forecast System",
            "description": "NOAA's global deterministic model",
            "viewer": "https://www.tropicaltidbits.com/analysis/models/?model=gfs",
            "data_info": "https://www.emc.ncep.noaa.gov/emc/pages/numerical_forecast_systems/gfs.php"
        },
        "NAM": {
            "name": "North American Mesoscale",
            "description": "Regional model for North America",
            "viewer": "https://www.tropicaltidbits.com/analysis/models/?model=nam",
            "data_info": "https://www.emc.ncep.noaa.gov/emc/pages/numerical_forecast_systems/nam.php"
        },
        "HRRR": {
            "name": "High-Resolution Rapid Refresh",
            "description": "High-res model updated hourly, best for timing",
            "viewer": "https://www.tropicaltidbits.com/analysis/models/?model=hrrr",
            "data_info": "https://rapidrefresh.noaa.gov/hrrr/"
        },
        "ECMWF": {
            "name": "European Centre Model",
            "description": "Often most accurate for major storms",
            "viewer": "https://www.tropicaltidbits.com/analysis/models/?model=ecmwf",
            "data_info": "https://www.ecmwf.int/en/forecasts"
        }
    }


def get_nbm_point_forecast(lat: float, lon: float) -> Optional[Dict[str, Any]]:
    """
    Get NBM point forecast data from NWS API.
    The NWS gridpoint data includes NBM elements.

    Args:
        lat: Latitude
        lon: Longitude

    Returns:
        Dictionary with NBM forecast elements, or None if unavailable
    """
    # First get the grid point
    points_url = f"https://api.weather.gov/points/{lat},{lon}"

    try:
        response = requests.get(points_url, headers={"User-Agent": USER_AGENT}, timeout=10)
        response.raise_for_status()
        data = response.json()

        properties = data.get("properties", {})
        forecast_grid_data = properties.get("forecastGridData")

        if not forecast_grid_data:
            return None

        # Fetch the gridpoint data which includes probabilistic elements
        grid_response = requests.get(forecast_grid_data, headers={"User-Agent": USER_AGENT}, timeout=10)
        grid_response.raise_for_status()
        grid_data = grid_response.json()

        props = grid_data.get("properties", {})

        # Extract NBM-derived elements
        nbm_data = {
            "snowfall_amount": extract_values(props.get("snowfallAmount", {})),
            "ice_accumulation": extract_values(props.get("iceAccumulation", {})),
            "probability_of_precipitation": extract_values(props.get("probabilityOfPrecipitation", {})),
            "wind_chill": extract_values(props.get("windChill", {})),
            "temperature": extract_values(props.get("temperature", {})),
            "quantitative_precipitation": extract_values(props.get("quantitativePrecipitation", {}))
        }

        return nbm_data

    except requests.RequestException as e:
        print(f"Error fetching NBM point forecast: {e}")
        return None


def extract_values(element_data: Dict) -> List[Dict]:
    """Extract time-value pairs from NWS gridpoint element."""
    values = element_data.get("values", [])
    result = []

    for v in values[:48]:  # First 48 periods
        result.append({
            "valid_time": v.get("validTime", ""),
            "value": v.get("value")
        })

    return result


def get_ensemble_spread_info() -> Dict[str, str]:
    """
    Get information about ensemble model spread for uncertainty.

    Returns:
        Dictionary with ensemble info and URLs
    """
    return {
        "description": "Ensemble models run multiple simulations with slightly different "
                       "initial conditions to show forecast uncertainty. Larger spread = more uncertainty.",
        "products": {
            "GEFS": {
                "name": "Global Ensemble Forecast System",
                "members": 31,
                "url": "https://www.tropicaltidbits.com/analysis/models/?model=gfs-ens"
            },
            "NAEFS": {
                "name": "North American Ensemble Forecast System",
                "members": "Combined US + Canadian ensembles",
                "url": "https://weather.gc.ca/ensemble/naefs/index_e.html"
            },
            "NBM_Spread": {
                "name": "NBM Uncertainty",
                "description": "NBM provides percentile forecasts showing range of outcomes",
                "url": NBM_DASHBOARD_URL
            }
        }
    }


def get_precipitation_type_info() -> Dict[str, Any]:
    """
    Get information about precipitation type forecasting.

    Returns:
        Dictionary with ptype info and resources
    """
    return {
        "description": "Precipitation type (rain/snow/ice/mix) depends on the temperature "
                       "profile through the atmosphere. Key levels are surface temp, "
                       "warm layer aloft, and freezing level.",
        "resources": [
            {
                "name": "NWS Precipitation Type Forecast",
                "url": "https://www.wpc.ncep.noaa.gov/wwd/",
                "description": "Official NWS winter weather forecasts"
            },
            {
                "name": "Sounding Analysis",
                "url": "https://www.spc.noaa.gov/exper/soundings/",
                "description": "Atmospheric profiles showing temperature layers"
            }
        ],
        "key_thresholds": {
            "all_snow": "Entire column below freezing",
            "rain_to_snow": "Warm layer aloft transitions to cold",
            "freezing_rain": "Warm layer aloft, surface below freezing",
            "sleet": "Warm layer aloft, deep cold layer near surface"
        }
    }
