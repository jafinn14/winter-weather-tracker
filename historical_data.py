"""
Historical weather data integration using RCC-ACIS (xmACIS backend).
Provides access to historical snowfall, temperature, and precipitation data.

Source: https://xmacis.rcc-acis.org/
API Documentation: http://www.rcc-acis.org/docs_webservices.html
"""

import requests
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
import json

ACIS_BASE_URL = "https://data.rcc-acis.org"
USER_AGENT = "WinterWeatherTracker/1.0 (Educational Project)"


@dataclass
class StormEvent:
    """Represents a historical storm event."""
    start_date: str
    end_date: str
    total_snow: float
    max_snow_day: float
    min_temp: float
    max_temp: float
    station_name: str
    station_id: str


@dataclass
class DailyObservation:
    """Single day of weather observations."""
    date: str
    max_temp: Optional[float]
    min_temp: Optional[float]
    precipitation: Optional[float]
    snowfall: Optional[float]
    snow_depth: Optional[float]


def find_stations_near_location(lat: float, lon: float, radius_miles: int = 30) -> List[Dict[str, Any]]:
    """
    Find weather stations near a location.

    Args:
        lat: Latitude
        lon: Longitude
        radius_miles: Search radius in miles

    Returns:
        List of station dictionaries with id, name, coordinates
    """
    url = f"{ACIS_BASE_URL}/StnMeta"

    params = {
        "ll": f"{lon},{lat}",
        "radius": radius_miles,
        "elems": "snow,snwd,maxt,mint,pcpn",
        "meta": "name,ll,sids,state,elev",
        "output": "json"
    }

    try:
        response = requests.post(url, json=params, headers={"User-Agent": USER_AGENT}, timeout=15)
        response.raise_for_status()
        data = response.json()

        stations = []
        for meta in data.get("meta", []):
            # Get the primary station ID (prefer COOP or WBAN)
            sids = meta.get("sids", [])
            primary_sid = None
            for sid in sids:
                if " 2" in sid:  # COOP stations
                    primary_sid = sid.split()[0]
                    break
                elif " 1" in sid:  # WBAN stations
                    primary_sid = sid.split()[0]
                    break

            if not primary_sid and sids:
                primary_sid = sids[0].split()[0]

            stations.append({
                "id": primary_sid,
                "name": meta.get("name", "Unknown"),
                "state": meta.get("state", ""),
                "lat": meta.get("ll", [0, 0])[1],
                "lon": meta.get("ll", [0, 0])[0],
                "elevation": meta.get("elev", 0),
                "all_sids": sids
            })

        return stations

    except requests.RequestException as e:
        print(f"Error finding stations: {e}")
        return []


def get_historical_data(
    station_id: str,
    start_date: str,
    end_date: str,
    elements: List[str] = None
) -> List[DailyObservation]:
    """
    Get historical daily data for a station.

    Args:
        station_id: Station identifier (COOP, WBAN, etc.)
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)
        elements: List of elements to fetch (default: snow, snwd, maxt, mint, pcpn)

    Returns:
        List of DailyObservation objects
    """
    if elements is None:
        elements = ["maxt", "mint", "pcpn", "snow", "snwd"]

    url = f"{ACIS_BASE_URL}/StnData"

    params = {
        "sid": station_id,
        "sdate": start_date,
        "edate": end_date,
        "elems": ",".join(elements),
        "output": "json"
    }

    try:
        response = requests.post(url, json=params, headers={"User-Agent": USER_AGENT}, timeout=30)
        response.raise_for_status()
        data = response.json()

        observations = []
        for row in data.get("data", []):
            date = row[0]
            values = row[1:]

            def parse_value(val):
                if val in ["M", "T", "S", "", None]:
                    return None
                try:
                    return float(val)
                except (ValueError, TypeError):
                    return None

            obs = DailyObservation(
                date=date,
                max_temp=parse_value(values[0]) if len(values) > 0 else None,
                min_temp=parse_value(values[1]) if len(values) > 1 else None,
                precipitation=parse_value(values[2]) if len(values) > 2 else None,
                snowfall=parse_value(values[3]) if len(values) > 3 else None,
                snow_depth=parse_value(values[4]) if len(values) > 4 else None
            )
            observations.append(obs)

        return observations

    except requests.RequestException as e:
        print(f"Error fetching historical data: {e}")
        return []


def find_historical_storms(
    station_id: str,
    min_snow_inches: float = 4.0,
    years_back: int = 10
) -> List[StormEvent]:
    """
    Find significant snow storms in historical data.

    Args:
        station_id: Station identifier
        min_snow_inches: Minimum snow total to qualify as a "storm"
        years_back: How many years of history to search

    Returns:
        List of StormEvent objects
    """
    end_date = datetime.now()
    start_date = end_date - timedelta(days=years_back * 365)

    # Fetch all historical data
    observations = get_historical_data(
        station_id,
        start_date.strftime("%Y-%m-%d"),
        end_date.strftime("%Y-%m-%d")
    )

    storms = []
    current_storm = None

    for obs in observations:
        if obs.snowfall and obs.snowfall >= 0.1:  # Snow occurring
            if current_storm is None:
                current_storm = {
                    "start_date": obs.date,
                    "end_date": obs.date,
                    "total_snow": obs.snowfall,
                    "max_snow_day": obs.snowfall,
                    "min_temp": obs.min_temp if obs.min_temp else 999,
                    "max_temp": obs.max_temp if obs.max_temp else -999,
                    "days": [obs]
                }
            else:
                current_storm["end_date"] = obs.date
                current_storm["total_snow"] += obs.snowfall
                current_storm["max_snow_day"] = max(current_storm["max_snow_day"], obs.snowfall)
                if obs.min_temp:
                    current_storm["min_temp"] = min(current_storm["min_temp"], obs.min_temp)
                if obs.max_temp:
                    current_storm["max_temp"] = max(current_storm["max_temp"], obs.max_temp)
                current_storm["days"].append(obs)
        else:
            # No snow - check if we should close out a storm
            if current_storm is not None:
                if current_storm["total_snow"] >= min_snow_inches:
                    storms.append(StormEvent(
                        start_date=current_storm["start_date"],
                        end_date=current_storm["end_date"],
                        total_snow=current_storm["total_snow"],
                        max_snow_day=current_storm["max_snow_day"],
                        min_temp=current_storm["min_temp"] if current_storm["min_temp"] != 999 else None,
                        max_temp=current_storm["max_temp"] if current_storm["max_temp"] != -999 else None,
                        station_name="",
                        station_id=station_id
                    ))
                current_storm = None

    # Sort by total snow descending
    storms.sort(key=lambda x: x.total_snow, reverse=True)

    return storms


def get_climate_normals(station_id: str, month: int) -> Dict[str, float]:
    """
    Get climate normals for a station and month.

    Args:
        station_id: Station identifier
        month: Month number (1-12)

    Returns:
        Dictionary with normal values for the month
    """
    url = f"{ACIS_BASE_URL}/StnData"

    # Get 30-year normals
    params = {
        "sid": station_id,
        "sdate": "por",  # Period of record
        "edate": "por",
        "elems": [
            {"name": "snow", "interval": "mly", "duration": "mly", "reduce": "sum", "normal": "1"},
            {"name": "maxt", "interval": "mly", "duration": "mly", "reduce": "mean", "normal": "1"},
            {"name": "mint", "interval": "mly", "duration": "mly", "reduce": "mean", "normal": "1"}
        ],
        "output": "json"
    }

    try:
        response = requests.post(url, json=params, headers={"User-Agent": USER_AGENT}, timeout=15)
        response.raise_for_status()
        data = response.json()

        # Extract the requested month's normals
        monthly_data = data.get("data", [])
        if len(monthly_data) >= month:
            row = monthly_data[month - 1]
            return {
                "month": month,
                "normal_snow": float(row[1]) if row[1] not in ["M", ""] else None,
                "normal_max_temp": float(row[2]) if row[2] not in ["M", ""] else None,
                "normal_min_temp": float(row[3]) if row[3] not in ["M", ""] else None
            }

    except (requests.RequestException, ValueError, IndexError) as e:
        print(f"Error fetching normals: {e}")

    return {}


def get_seasonal_snowfall(station_id: str, season_start_year: int) -> Dict[str, Any]:
    """
    Get total snowfall for a winter season (July 1 - June 30).

    Args:
        station_id: Station identifier
        season_start_year: Year the season starts (e.g., 2024 for 2024-25 season)

    Returns:
        Dictionary with seasonal snowfall data
    """
    start_date = f"{season_start_year}-07-01"
    end_date = f"{season_start_year + 1}-06-30"

    observations = get_historical_data(station_id, start_date, end_date, ["snow", "snwd"])

    total_snow = 0.0
    max_depth = 0.0
    snow_days = 0

    for obs in observations:
        if obs.snowfall and obs.snowfall > 0:
            total_snow += obs.snowfall
            snow_days += 1
        if obs.snow_depth and obs.snow_depth > max_depth:
            max_depth = obs.snow_depth

    return {
        "season": f"{season_start_year}-{season_start_year + 1}",
        "total_snow": total_snow,
        "max_depth": max_depth,
        "snow_days": snow_days
    }


def compare_to_historical(
    current_forecast_snow: float,
    station_id: str,
    target_date: str
) -> Dict[str, Any]:
    """
    Compare a forecasted snow total to historical data for the same time of year.

    Args:
        current_forecast_snow: Forecasted snow amount in inches
        station_id: Station identifier
        target_date: Date of forecast (YYYY-MM-DD)

    Returns:
        Dictionary with comparison statistics
    """
    target_dt = datetime.strptime(target_date, "%Y-%m-%d")
    month = target_dt.month
    day = target_dt.day

    # Look at same week historically
    comparisons = []

    for years_ago in range(1, 11):  # Last 10 years
        year = target_dt.year - years_ago
        start = datetime(year, month, day) - timedelta(days=3)
        end = datetime(year, month, day) + timedelta(days=3)

        obs = get_historical_data(
            station_id,
            start.strftime("%Y-%m-%d"),
            end.strftime("%Y-%m-%d"),
            ["snow"]
        )

        week_total = sum(o.snowfall for o in obs if o.snowfall)
        comparisons.append({
            "year": year,
            "snow": week_total
        })

    if not comparisons:
        return {}

    all_snow = [c["snow"] for c in comparisons]
    avg_snow = sum(all_snow) / len(all_snow)
    max_snow = max(all_snow)

    # Calculate percentile
    storms_less = sum(1 for s in all_snow if s < current_forecast_snow)
    percentile = (storms_less / len(all_snow)) * 100

    return {
        "forecast_snow": current_forecast_snow,
        "historical_avg": round(avg_snow, 1),
        "historical_max": max_snow,
        "percentile": round(percentile, 0),
        "comparison_years": len(comparisons),
        "comparisons": comparisons
    }


def get_recent_snowfall(station_id: str, days: int = 7) -> Dict[str, Any]:
    """
    Get recent snowfall totals for a station.

    Args:
        station_id: Station identifier
        days: Number of days to look back

    Returns:
        Dictionary with recent snowfall data
    """
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)

    observations = get_historical_data(
        station_id,
        start_date.strftime("%Y-%m-%d"),
        end_date.strftime("%Y-%m-%d")
    )

    daily_totals = []
    for obs in observations:
        daily_totals.append({
            "date": obs.date,
            "snow": obs.snowfall,
            "depth": obs.snow_depth,
            "max_temp": obs.max_temp,
            "min_temp": obs.min_temp
        })

    total_snow = sum(o.snowfall for o in observations if o.snowfall)
    current_depth = observations[-1].snow_depth if observations and observations[-1].snow_depth else 0

    return {
        "period_days": days,
        "total_snow": total_snow,
        "current_depth": current_depth,
        "daily": daily_totals
    }
