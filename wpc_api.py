"""
Weather Prediction Center (WPC) data integration.
Provides access to probabilistic winter weather forecasts.

Source: https://www.wpc.ncep.noaa.gov/wwd/winter_wx.shtml
"""

import requests
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum

USER_AGENT = "WinterWeatherTracker/1.0 (Educational Project)"
WPC_BASE_URL = "https://www.wpc.ncep.noaa.gov"


class SnowThreshold(Enum):
    """Snow accumulation thresholds for probability maps."""
    ONE_INCH = "01"
    TWO_INCH = "02"
    FOUR_INCH = "04"
    SIX_INCH = "06"
    EIGHT_INCH = "08"
    TWELVE_INCH = "12"
    EIGHTEEN_INCH = "18"


class ForecastDay(Enum):
    """Forecast day periods."""
    DAY1 = "024"
    DAY2 = "048"
    DAY3 = "072"
    DAY4 = "096"
    DAY5 = "120"
    DAY6 = "144"
    DAY7 = "168"


@dataclass
class WPCProduct:
    """Represents a WPC forecast product."""
    name: str
    description: str
    url: str
    product_type: str  # 'image', 'text', 'data'


def get_snow_probability_url(threshold: SnowThreshold, day: ForecastDay) -> str:
    """
    Get URL for probabilistic snowfall map.

    Args:
        threshold: Snow amount threshold (e.g., 4 inches)
        day: Forecast day (1-3 for detailed, 4-7 for outlook)

    Returns:
        URL to the probability map image
    """
    # Days 1-3 use the pwpf_24hr format
    if day in [ForecastDay.DAY1, ForecastDay.DAY2, ForecastDay.DAY3]:
        return f"{WPC_BASE_URL}/pwpf_24hr/prb_24hsnow_ge{threshold.value}_latestf{day.value}_sm.jpg"
    else:
        # Days 4-7 use different format
        return f"{WPC_BASE_URL}/wwd/pwpf_d47/prb_24hsnow_d{day.value[1]}_sm.gif"


def get_freezing_rain_probability_url(threshold: str, day: ForecastDay) -> str:
    """
    Get URL for freezing rain probability map.

    Args:
        threshold: Ice amount threshold (01, 10, 25, 50 for 0.01, 0.10, 0.25, 0.50 inches)
        day: Forecast day

    Returns:
        URL to the probability map image
    """
    return f"{WPC_BASE_URL}/pwpf_24hr/prb_24hzr_ge{threshold}_latestf{day.value}_sm.jpg"


def get_winter_storm_severity_url() -> str:
    """Get URL for Winter Storm Severity Index map."""
    return f"{WPC_BASE_URL}/wwd/wssi/wssi_fcst_grd.png"


def get_probabilistic_wssi_url() -> str:
    """Get URL for Probabilistic Winter Storm Severity Index."""
    return f"{WPC_BASE_URL}/wwd/pwssi/pwssi_fcst_grd.png"


def get_composite_chart_url(day: ForecastDay) -> str:
    """
    Get URL for composite snow/ice probability chart.
    Shows 4", 8", 12" snow and 0.25" ice probabilities together.
    """
    return f"{WPC_BASE_URL}/pwpf/wwd_composite_4panel_f{day.value}.png"


def get_snow_percentile_url(percentile: int, day: ForecastDay) -> str:
    """
    Get URL for snow amount percentile forecast.

    Args:
        percentile: 10, 25, 50, 75, or 90
        day: Forecast day

    Returns:
        URL to the percentile map image
    """
    return f"{WPC_BASE_URL}/pwpf_24hr/ptl_24hsnow_{percentile}th_latestf{day.value}_sm.jpg"


def get_all_wpc_products() -> List[WPCProduct]:
    """Get a list of all available WPC winter weather products."""
    products = []

    # Snow probability maps - Day 1-3
    for day in [ForecastDay.DAY1, ForecastDay.DAY2, ForecastDay.DAY3]:
        for threshold in [SnowThreshold.FOUR_INCH, SnowThreshold.EIGHT_INCH, SnowThreshold.TWELVE_INCH]:
            day_num = int(day.value) // 24
            products.append(WPCProduct(
                name=f"Day {day_num} Snow ≥{threshold.value}\"",
                description=f"Probability of {threshold.value}+ inches of snow - Day {day_num}",
                url=get_snow_probability_url(threshold, day),
                product_type="image"
            ))

    # Composite charts
    for day in [ForecastDay.DAY1, ForecastDay.DAY2, ForecastDay.DAY3]:
        day_num = int(day.value) // 24
        products.append(WPCProduct(
            name=f"Day {day_num} Composite",
            description=f"Combined snow/ice probability chart - Day {day_num}",
            url=get_composite_chart_url(day),
            product_type="image"
        ))

    # Winter Storm Severity
    products.append(WPCProduct(
        name="Winter Storm Severity Index",
        description="WSSI - Overall winter storm impact assessment",
        url=get_winter_storm_severity_url(),
        product_type="image"
    ))

    products.append(WPCProduct(
        name="Probabilistic WSSI",
        description="Probability-based winter storm severity",
        url=get_probabilistic_wssi_url(),
        product_type="image"
    ))

    # Freezing rain
    for day in [ForecastDay.DAY1, ForecastDay.DAY2, ForecastDay.DAY3]:
        day_num = int(day.value) // 24
        products.append(WPCProduct(
            name=f"Day {day_num} Ice ≥0.25\"",
            description=f"Probability of significant ice accumulation - Day {day_num}",
            url=get_freezing_rain_probability_url("25", day),
            product_type="image"
        ))

    return products


def get_heavy_snow_discussion() -> Optional[Dict[str, str]]:
    """
    Fetch the Heavy Snow and Icing Discussion text product.

    Returns:
        Dictionary with 'text' and 'url' keys, or None if unavailable
    """
    # The discussion is available via NWS products API
    url = "https://www.wpc.ncep.noaa.gov/discussions/hpcdiscussions.php?disc=pmdspd"

    try:
        response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=15)
        response.raise_for_status()

        # Extract text content (basic HTML parsing)
        text = response.text

        # Find the pre tag content which contains the discussion
        import re
        pre_match = re.search(r'<pre[^>]*>(.*?)</pre>', text, re.DOTALL | re.IGNORECASE)

        if pre_match:
            discussion_text = pre_match.group(1).strip()
            # Clean up HTML entities
            discussion_text = discussion_text.replace('&amp;', '&')
            discussion_text = discussion_text.replace('&lt;', '<')
            discussion_text = discussion_text.replace('&gt;', '>')

            return {
                'text': discussion_text,
                'url': url
            }

    except requests.RequestException:
        pass

    return None


def get_extended_forecast_discussion() -> Optional[Dict[str, str]]:
    """
    Fetch the Extended Forecast Discussion (Days 3-7).

    Returns:
        Dictionary with 'text' and 'url' keys, or None if unavailable
    """
    url = "https://www.wpc.ncep.noaa.gov/discussions/hpcdiscussions.php?disc=pmdepd"

    try:
        response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=15)
        response.raise_for_status()

        import re
        pre_match = re.search(r'<pre[^>]*>(.*?)</pre>', response.text, re.DOTALL | re.IGNORECASE)

        if pre_match:
            discussion_text = pre_match.group(1).strip()
            discussion_text = discussion_text.replace('&amp;', '&')

            return {
                'text': discussion_text,
                'url': url
            }

    except requests.RequestException:
        pass

    return None


# NOHRSC Observed Snowfall Analysis URLs
def get_observed_snowfall_url(period: str = "24h") -> str:
    """
    Get URL for observed snowfall analysis from NOHRSC.

    Args:
        period: '24h', '48h', '72h', 'season', or 'storm'

    Returns:
        URL to the observed snowfall map
    """
    base = "https://www.nohrsc.noaa.gov/snowfall_v2"

    period_map = {
        "24h": "us_sf24h",
        "48h": "us_sf48h",
        "72h": "us_sf72h",
        "season": "us_sfseason",
        "storm": "us_sfstorm"
    }

    product = period_map.get(period, "us_sf24h")
    return f"{base}/data/current/{product}.png"


def get_snow_depth_url() -> str:
    """Get URL for current snow depth analysis."""
    return "https://www.nohrsc.noaa.gov/snow_model/images/full/National/nsm_depth/202501/nsm_depth_2025012112_National.png"


def validate_image_url(url: str) -> bool:
    """Check if an image URL is accessible."""
    try:
        response = requests.head(url, headers={"User-Agent": USER_AGENT}, timeout=5)
        return response.status_code == 200
    except requests.RequestException:
        return False
