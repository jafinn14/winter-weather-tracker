"""
Storm detection and analysis module.
Automatically identifies significant winter weather in forecasts and provides
comprehensive analysis including confidence, trends, and historical context.
"""

import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from enum import Enum


class StormConfidence(Enum):
    """Confidence levels based on forecast lead time."""
    VERY_HIGH = "Very High"      # 0-24 hours
    HIGH = "High"                 # 24-48 hours
    MODERATE = "Moderate"         # 48-72 hours
    LOW = "Low"                   # 72-120 hours (3-5 days)
    VERY_LOW = "Very Low"         # 120+ hours (5+ days)


class ImpactLevel(Enum):
    """Storm impact levels based on expected accumulation."""
    MINOR = "Minor"               # 1-3 inches
    MODERATE = "Moderate"         # 4-6 inches
    SIGNIFICANT = "Significant"   # 6-12 inches
    MAJOR = "Major"               # 12-18 inches
    EXTREME = "Extreme"           # 18+ inches


@dataclass
class DetectedStorm:
    """Represents a detected storm in the forecast."""
    start_period: str
    end_period: str
    lead_time_hours: int
    snow_low: float
    snow_high: float
    snow_best_estimate: float
    ice_mentioned: bool
    wind_mentioned: bool
    confidence: StormConfidence
    impact_level: ImpactLevel
    raw_periods: List[Dict]
    key_quote: str


@dataclass
class ForecastTrend:
    """Tracks how a forecast has changed over time."""
    fetch_time: str
    snow_amount: float
    direction: str  # 'up', 'down', 'steady'
    change_amount: float


def get_confidence_for_lead_time(hours: int) -> StormConfidence:
    """
    Determine forecast confidence based on lead time.

    Based on NWS forecast skill research:
    - Days 1-2: High accuracy
    - Days 3-4: Moderate accuracy
    - Days 5-7: Low accuracy, storm existence more reliable than amounts
    """
    if hours <= 24:
        return StormConfidence.VERY_HIGH
    elif hours <= 48:
        return StormConfidence.HIGH
    elif hours <= 72:
        return StormConfidence.MODERATE
    elif hours <= 120:
        return StormConfidence.LOW
    else:
        return StormConfidence.VERY_LOW


def get_confidence_description(confidence: StormConfidence, lead_days: int) -> str:
    """Get a human-readable description of confidence level."""
    descriptions = {
        StormConfidence.VERY_HIGH: "Forecast is highly reliable. Amounts and timing are well-established.",
        StormConfidence.HIGH: "Good confidence in storm occurrence. Amounts may shift by 1-2 inches.",
        StormConfidence.MODERATE: "Storm is likely but details uncertain. Amounts could change significantly.",
        StormConfidence.LOW: f"At {lead_days} days out, the storm signal is present but amounts are unreliable. Focus on whether it happens, not how much.",
        StormConfidence.VERY_LOW: f"At {lead_days}+ days out, this is a storm to WATCH, not plan around. Track trends over next few days."
    }
    return descriptions.get(confidence, "")


def get_impact_level(snow_inches: float) -> ImpactLevel:
    """Determine impact level based on snow amount."""
    if snow_inches >= 18:
        return ImpactLevel.EXTREME
    elif snow_inches >= 12:
        return ImpactLevel.MAJOR
    elif snow_inches >= 6:
        return ImpactLevel.SIGNIFICANT
    elif snow_inches >= 4:
        return ImpactLevel.MODERATE
    else:
        return ImpactLevel.MINOR


def get_impact_description(impact: ImpactLevel) -> Dict[str, str]:
    """Get impact descriptions for different aspects of life."""
    impacts = {
        ImpactLevel.MINOR: {
            "travel": "Minor slippery spots, drive carefully",
            "schools": "Unlikely to close",
            "work": "Normal operations",
            "plowing": "May not require plowing",
            "power": "Unlikely to cause outages"
        },
        ImpactLevel.MODERATE: {
            "travel": "Hazardous travel during storm, slow commute",
            "schools": "Possible delays or early release",
            "work": "Some remote work likely",
            "plowing": "Plowing operations begin",
            "power": "Scattered outages possible if heavy/wet"
        },
        ImpactLevel.SIGNIFICANT: {
            "travel": "Avoid travel during storm, significant delays",
            "schools": "Closures likely",
            "work": "Remote work recommended",
            "plowing": "Full plowing operations, parking bans possible",
            "power": "Outages possible, especially if wet snow"
        },
        ImpactLevel.MAJOR: {
            "travel": "Travel extremely dangerous, avoid completely",
            "schools": "Closures almost certain",
            "work": "Most businesses closed or remote",
            "plowing": "Extended plowing operations, snow emergencies",
            "power": "Widespread outages possible"
        },
        ImpactLevel.EXTREME: {
            "travel": "Life-threatening travel conditions",
            "schools": "Extended closures likely",
            "work": "Widespread closures",
            "plowing": "Multi-day recovery, possible military assistance",
            "power": "Significant outages likely"
        }
    }
    return impacts.get(impact, {})


def extract_snow_amounts_from_text(text: str) -> Tuple[Optional[float], Optional[float]]:
    """
    Extract snow amounts from forecast text.
    Returns (low, high) tuple.
    """
    if not text:
        return None, None

    text = text.lower()

    # Pattern: "X to Y inches"
    range_pattern = r'(\d+(?:\.\d+)?)\s*(?:to|-)\s*(\d+(?:\.\d+)?)\s*(?:inch|")'
    range_match = re.search(range_pattern, text)
    if range_match:
        return float(range_match.group(1)), float(range_match.group(2))

    # Pattern: "around X inches" or "about X inches"
    around_pattern = r'(?:around|about|near)\s*(\d+(?:\.\d+)?)\s*(?:inch|")'
    around_match = re.search(around_pattern, text)
    if around_match:
        amt = float(around_match.group(1))
        return amt - 1, amt + 1

    # Pattern: "X inches"
    single_pattern = r'(\d+(?:\.\d+)?)\s*(?:inch|")'
    single_match = re.search(single_pattern, text)
    if single_match:
        amt = float(single_match.group(1))
        return amt, amt

    return None, None


def extract_snow_from_gridpoint(gridpoint_data: Dict, days_ahead: int = 7) -> Dict[str, Dict]:
    """
    Extract snow accumulation data from NWS gridpoint response.
    Returns dictionary keyed by date with low/mid/high estimates.
    """
    snow_by_date = {}

    try:
        properties = gridpoint_data.get('properties', {})
        snow_amount = properties.get('snowfallAmount', {})
        values = snow_amount.get('values', [])

        for entry in values:
            valid_time = entry.get('validTime', '')
            value = entry.get('value')

            if value is not None and value > 0:
                # Convert mm to inches
                inches = value / 25.4

                # Extract date from validTime (format: 2024-01-25T00:00:00+00:00/PT6H)
                date_match = re.match(r'(\d{4}-\d{2}-\d{2})', valid_time)
                if date_match:
                    date_key = date_match.group(1)
                    if date_key not in snow_by_date:
                        snow_by_date[date_key] = {'total': 0, 'periods': []}
                    snow_by_date[date_key]['total'] += inches
                    snow_by_date[date_key]['periods'].append({
                        'time': valid_time,
                        'amount': inches
                    })

    except (KeyError, TypeError):
        pass

    return snow_by_date


def detect_storms_in_forecast(forecast_data: Dict) -> List[DetectedStorm]:
    """
    Analyze forecast data and detect significant winter storms.

    Args:
        forecast_data: Combined forecast data from database

    Returns:
        List of DetectedStorm objects
    """
    storms = []

    # Get periods from standard forecast
    periods = []
    try:
        periods = forecast_data.get('forecast', {}).get('properties', {}).get('periods', [])
    except (KeyError, TypeError, AttributeError):
        return storms

    # Get gridpoint snow data
    gridpoint = forecast_data.get('gridpoint', {})
    snow_by_date = extract_snow_from_gridpoint(gridpoint)

    # Scan periods for winter weather mentions
    current_storm_periods = []

    for i, period in enumerate(periods):
        detailed = period.get('detailedForecast', '').lower()
        short = period.get('shortForecast', '').lower()
        period_name = period.get('name', '')

        has_snow = any(word in detailed for word in ['snow', 'flurries', 'blizzard', 'wintry'])
        has_ice = any(word in detailed for word in ['ice', 'freezing rain', 'sleet'])
        has_wind = any(word in detailed for word in ['wind', 'gusts', 'blustery'])

        if has_snow or has_ice:
            current_storm_periods.append({
                'period': period,
                'index': i,
                'has_snow': has_snow,
                'has_ice': has_ice,
                'has_wind': has_wind
            })
        elif current_storm_periods:
            # End of a storm sequence - analyze it
            storm = analyze_storm_periods(current_storm_periods, snow_by_date)
            if storm and storm.snow_best_estimate >= 1.0:  # At least 1 inch
                storms.append(storm)
            current_storm_periods = []

    # Check if there's an ongoing storm at the end
    if current_storm_periods:
        storm = analyze_storm_periods(current_storm_periods, snow_by_date)
        if storm and storm.snow_best_estimate >= 1.0:
            storms.append(storm)

    return storms


def analyze_storm_periods(storm_periods: List[Dict], snow_by_date: Dict) -> Optional[DetectedStorm]:
    """Analyze a sequence of storm periods and create a DetectedStorm object."""
    if not storm_periods:
        return None

    first_period = storm_periods[0]['period']
    last_period = storm_periods[-1]['period']

    # Calculate lead time (approximate based on period index)
    # Each period is roughly 12 hours
    lead_time_hours = storm_periods[0]['index'] * 12

    # Extract snow amounts from text
    all_text = ' '.join([sp['period'].get('detailedForecast', '') for sp in storm_periods])
    text_low, text_high = extract_snow_amounts_from_text(all_text)

    # Try to get amounts from gridpoint data
    gridpoint_total = 0
    for sp in storm_periods:
        period_name = sp['period'].get('name', '')
        # Try to match period to date
        for date_key, data in snow_by_date.items():
            gridpoint_total += data.get('total', 0)

    # Determine best estimate
    if text_low and text_high:
        snow_low = text_low
        snow_high = text_high
        snow_best = (text_low + text_high) / 2
    elif gridpoint_total > 0:
        # Use gridpoint data with uncertainty range
        snow_low = gridpoint_total * 0.5
        snow_high = gridpoint_total * 1.5
        snow_best = gridpoint_total
    else:
        # Default for "snow" mention without amounts
        snow_low = 1.0
        snow_high = 4.0
        snow_best = 2.0

    # Check for ice and wind
    ice_mentioned = any(sp['has_ice'] for sp in storm_periods)
    wind_mentioned = any(sp['has_wind'] for sp in storm_periods)

    # Get confidence and impact
    confidence = get_confidence_for_lead_time(lead_time_hours)
    impact = get_impact_level(snow_best)

    # Find key quote (most informative forecast text)
    key_quote = ""
    for sp in storm_periods:
        text = sp['period'].get('detailedForecast', '')
        if 'snow' in text.lower() and len(text) > len(key_quote):
            key_quote = text

    return DetectedStorm(
        start_period=first_period.get('name', ''),
        end_period=last_period.get('name', ''),
        lead_time_hours=lead_time_hours,
        snow_low=snow_low,
        snow_high=snow_high,
        snow_best_estimate=snow_best,
        ice_mentioned=ice_mentioned,
        wind_mentioned=wind_mentioned,
        confidence=confidence,
        impact_level=impact,
        raw_periods=[sp['period'] for sp in storm_periods],
        key_quote=key_quote[:300] if key_quote else ""
    )


def analyze_forecast_trends(forecasts: List[Dict], storm_start_period: str = None) -> List[ForecastTrend]:
    """
    Analyze how forecasts have changed over time.

    Args:
        forecasts: List of forecast snapshots from database (newest first)
        storm_start_period: Optional period name to focus on

    Returns:
        List of ForecastTrend objects showing evolution
    """
    trends = []
    previous_amount = None

    # Process from oldest to newest for proper trend direction
    for forecast in reversed(forecasts):
        fetch_time = forecast.get('fetched_at', '')
        forecast_data = forecast.get('forecast_data', {})

        # Get snow amount for this snapshot
        gridpoint = forecast_data.get('gridpoint', {})
        snow_by_date = extract_snow_from_gridpoint(gridpoint)

        total_snow = sum(d.get('total', 0) for d in snow_by_date.values())

        # Calculate trend
        if previous_amount is not None:
            change = total_snow - previous_amount
            if change > 0.5:
                direction = 'up'
            elif change < -0.5:
                direction = 'down'
            else:
                direction = 'steady'
        else:
            direction = 'steady'
            change = 0

        trends.append(ForecastTrend(
            fetch_time=fetch_time,
            snow_amount=total_snow,
            direction=direction,
            change_amount=change if previous_amount else 0
        ))

        previous_amount = total_snow

    return trends


def get_trend_summary(trends: List[ForecastTrend]) -> Dict[str, Any]:
    """Summarize the overall trend direction."""
    if len(trends) < 2:
        return {'direction': 'insufficient_data', 'message': 'Need more forecast snapshots to show trends'}

    # Look at recent trends
    recent = trends[-3:] if len(trends) >= 3 else trends

    up_count = sum(1 for t in recent if t.direction == 'up')
    down_count = sum(1 for t in recent if t.direction == 'down')

    total_change = trends[-1].snow_amount - trends[0].snow_amount

    if up_count > down_count:
        direction = 'increasing'
        message = f"Forecast trending UP. Snow totals have increased by {abs(total_change):.1f}\" since first forecast."
    elif down_count > up_count:
        direction = 'decreasing'
        message = f"Forecast trending DOWN. Snow totals have decreased by {abs(total_change):.1f}\" since first forecast."
    else:
        direction = 'steady'
        message = "Forecast has been relatively steady."

    return {
        'direction': direction,
        'message': message,
        'total_change': total_change,
        'num_snapshots': len(trends),
        'first_amount': trends[0].snow_amount,
        'latest_amount': trends[-1].snow_amount
    }


def get_key_uncertainties(storm: DetectedStorm) -> List[str]:
    """Identify key uncertainties to watch for this storm."""
    uncertainties = []

    # Lead time uncertainty
    if storm.lead_time_hours >= 120:
        uncertainties.append("Storm track could shift significantly - watch for updates")
        uncertainties.append("Snow totals are unreliable at this range - focus on whether it happens")
    elif storm.lead_time_hours >= 72:
        uncertainties.append("Exact storm track still uncertain - could affect totals by 50%")
        uncertainties.append("Timing may shift by 6-12 hours")

    # Amount range uncertainty
    amount_spread = storm.snow_high - storm.snow_low
    if amount_spread >= 6:
        uncertainties.append(f"Wide range of outcomes possible ({storm.snow_low:.0f}\"-{storm.snow_high:.0f}\")")

    # Mixed precipitation
    if storm.ice_mentioned:
        uncertainties.append("Ice/freezing rain possible - rain/snow line is a key factor")

    # Wind impacts
    if storm.wind_mentioned:
        uncertainties.append("Significant wind expected - blowing/drifting snow possible")

    return uncertainties


def get_what_to_watch(storm: DetectedStorm) -> List[str]:
    """Get guidance on what to monitor in upcoming forecasts."""
    watch_items = []

    if storm.lead_time_hours >= 96:
        watch_items.append("Track model trends over next 2-3 days - are they converging on a solution?")
        watch_items.append("Watch if storm track shifts north (more snow) or south (less snow)")

    if storm.lead_time_hours >= 72:
        watch_items.append("Monitor for changes in timing - when does precip start?")
        watch_items.append("Watch precipitation type forecasts - will it start as rain?")

    watch_items.append("Check NWS Area Forecast Discussion for meteorologist confidence")
    watch_items.append("Compare WPC probabilistic maps to see range of outcomes")

    if storm.ice_mentioned:
        watch_items.append("Monitor temperature forecasts - small changes affect precip type")

    return watch_items


def generate_storm_headline(storm: DetectedStorm) -> str:
    """Generate a headline summarizing the storm."""
    lead_days = storm.lead_time_hours // 24

    impact_text = {
        ImpactLevel.MINOR: "Light snow",
        ImpactLevel.MODERATE: "Moderate snowstorm",
        ImpactLevel.SIGNIFICANT: "Significant snowstorm",
        ImpactLevel.MAJOR: "Major winter storm",
        ImpactLevel.EXTREME: "Potentially historic snowstorm"
    }

    base = impact_text.get(storm.impact_level, "Winter weather")

    if storm.ice_mentioned:
        base += " with ice"

    timing = f"expected {storm.start_period}"

    if lead_days >= 5:
        return f"{base} {timing} ({lead_days} days out - tracking)"
    elif lead_days >= 3:
        return f"{base} {timing} ({lead_days} days out)"
    else:
        return f"{base} {timing}"


def generate_snow_range_text(storm: DetectedStorm) -> str:
    """Generate text describing the expected snow range with confidence context."""
    conf = storm.confidence

    if conf == StormConfidence.VERY_LOW:
        return f"Potential for {storm.snow_low:.0f}-{storm.snow_high:.0f}\" but amounts are highly uncertain at this range"
    elif conf == StormConfidence.LOW:
        return f"Preliminary estimate: {storm.snow_low:.0f}-{storm.snow_high:.0f}\" (expect significant changes)"
    elif conf == StormConfidence.MODERATE:
        return f"Currently forecasting {storm.snow_low:.0f}-{storm.snow_high:.0f}\" (may still change)"
    else:
        return f"Expecting {storm.snow_low:.0f}-{storm.snow_high:.0f}\""
