import streamlit as st
from database import get_location_by_zip, get_forecasts_for_location, get_discussions_for_location
from nws_api import extract_winter_weather_info
from datetime import datetime
import json

def show():
    st.title("Current Forecast")

    # Check if location is set
    if "current_zip" not in st.session_state:
        st.warning("Please set up your location first in the 'Setup & Fetch Data' page.")
        return

    location = get_location_by_zip(st.session_state.current_zip)
    if not location:
        st.error("Location not found. Please set up your location again.")
        return

    st.markdown(f"### 📍 {location['city']}, {location['state']}")

    # Get latest forecast
    forecasts = get_forecasts_for_location(location['id'], days_back=30)
    if not forecasts:
        st.warning("No forecast data available. Please fetch data from the Setup page.")
        return

    latest_forecast = forecasts[0]
    fetched_time = datetime.fromisoformat(latest_forecast['fetched_at'])

    st.caption(f"Last updated: {fetched_time.strftime('%B %d, %Y at %I:%M %p')}")

    # Extract forecast periods
    forecast_data = latest_forecast['forecast_data'].get('forecast', {})
    periods = forecast_data.get('properties', {}).get('periods', [])

    if not periods:
        st.error("No forecast periods found in data.")
        return

    # Extract winter weather info
    winter_info = extract_winter_weather_info(periods)

    # Show winter weather alerts if any
    if winter_info['snow_mentions'] or winter_info['ice_mentions']:
        st.markdown("### ❄️ Winter Weather Alerts")

        if winter_info['snow_mentions']:
            st.info("**Snow in the forecast:**")
            for mention in winter_info['snow_mentions']:
                st.markdown(f"**{mention['period']}**: {mention['forecast']}")

        if winter_info['ice_mentions']:
            st.warning("**Ice/Freezing conditions in the forecast:**")
            for mention in winter_info['ice_mentions']:
                st.markdown(f"**{mention['period']}**: {mention['forecast']}")

    # Detailed forecast
    st.markdown("### 📅 7-Day Detailed Forecast")

    for i, period in enumerate(periods[:14]):  # Show up to 7 days (14 periods)
        with st.expander(f"{period['name']} - {period['shortForecast']}", expanded=(i < 2)):
            col1, col2 = st.columns([2, 1])

            with col1:
                st.markdown(f"**{period['detailedForecast']}**")

            with col2:
                st.metric("Temperature", f"{period['temperature']}°{period['temperatureUnit']}")
                st.metric("Wind", f"{period['windSpeed']} {period['windDirection']}")
                if period.get('probabilityOfPrecipitation', {}).get('value'):
                    precip_prob = period['probabilityOfPrecipitation']['value']
                    st.metric("Precip Chance", f"{precip_prob}%")

    # Gridpoint data (for detailed winter weather info)
    st.markdown("### 🌨️ Quantitative Winter Weather Data")

    gridpoint_data = latest_forecast['forecast_data'].get('gridpoint', {}).get('properties', {})

    col1, col2, col3 = st.columns(3)

    with col1:
        if 'snowfallAmount' in gridpoint_data:
            st.markdown("**Snowfall Forecast:**")
            snow_data = gridpoint_data['snowfallAmount'].get('values', [])
            if snow_data:
                for item in snow_data[:5]:
                    valid_time = item.get('validTime', 'Unknown')
                    value = item.get('value', 0)
                    if value and value > 0:
                        st.text(f"{value:.1f} inches")
            else:
                st.text("No snow expected")

    with col2:
        if 'iceAccumulation' in gridpoint_data:
            st.markdown("**Ice Accumulation:**")
            ice_data = gridpoint_data['iceAccumulation'].get('values', [])
            if ice_data:
                has_ice = False
                for item in ice_data[:5]:
                    value = item.get('value', 0)
                    if value and value > 0:
                        st.text(f"{value:.2f} inches")
                        has_ice = True
                if not has_ice:
                    st.text("No ice expected")
            else:
                st.text("No ice expected")

    with col3:
        if 'windChill' in gridpoint_data:
            st.markdown("**Wind Chill:**")
            wind_chill_data = gridpoint_data['windChill'].get('values', [])
            if wind_chill_data:
                for item in wind_chill_data[:3]:
                    value = item.get('value')
                    if value is not None:
                        # Convert from Celsius to Fahrenheit
                        temp_f = (value * 9/5) + 32
                        st.text(f"{temp_f:.0f}°F")
            else:
                st.text("Not applicable")

    # Latest discussion snippet
    st.markdown("### 💬 Latest Forecast Discussion")
    discussions = get_discussions_for_location(location['id'], days_back=30)
    if discussions:
        latest_discussion = discussions[0]
        discussion_time = datetime.fromisoformat(latest_discussion['fetched_at'])

        st.caption(f"Fetched: {discussion_time.strftime('%B %d, %Y at %I:%M %p')}")

        # Show first 1000 characters
        discussion_text = latest_discussion['discussion_text']
        preview = discussion_text[:1000]

        st.text_area("Discussion Preview", preview, height=200, disabled=True)
        st.info("View full discussion history in the 'Discussion Archive' page")
    else:
        st.info("No forecast discussions available yet.")
