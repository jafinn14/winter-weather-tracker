import streamlit as st
from datetime import datetime, timedelta
import pandas as pd

from database import get_location_by_zip, get_forecasts_for_location
from wpc_api import (
    get_all_wpc_products, get_snow_probability_url, get_composite_chart_url,
    get_winter_storm_severity_url, get_observed_snowfall_url,
    get_heavy_snow_discussion, SnowThreshold, ForecastDay
)
from historical_data import (
    find_stations_near_location, get_historical_data, find_historical_storms,
    get_recent_snowfall, compare_to_historical, get_seasonal_snowfall
)
from nbm_api import get_model_comparison_urls, get_nbm_snow_graphics


def show():
    st.title("Extended Data Sources")
    st.markdown("Access additional forecast products, model comparisons, and historical data.")

    # Check if location is set
    if "current_zip" not in st.session_state:
        st.warning("Set up a location on the Setup page to access location-specific data.")
        location = None
    else:
        location = get_location_by_zip(st.session_state.current_zip)
        if location:
            st.info(f"Showing data for: {location['city']}, {location['state']}")

    # Create tabs for different data sources
    tab1, tab2, tab3, tab4 = st.tabs([
        "WPC Products",
        "Model Comparison",
        "Historical Data",
        "Observed Snowfall"
    ])

    with tab1:
        show_wpc_products()

    with tab2:
        show_model_comparison()

    with tab3:
        show_historical_data(location)

    with tab4:
        show_observed_snowfall()


def show_wpc_products():
    """Display WPC winter weather products."""
    st.subheader("Weather Prediction Center Products")
    st.markdown("""
    The [Weather Prediction Center (WPC)](https://www.wpc.ncep.noaa.gov/wwd/winter_wx.shtml)
    provides national probabilistic forecasts for snow and ice accumulation.
    """)

    # Product selector
    product_type = st.selectbox(
        "Select Product Type",
        ["Snow Probability Maps", "Composite Charts", "Severity Index", "Heavy Snow Discussion"]
    )

    if product_type == "Snow Probability Maps":
        col1, col2 = st.columns(2)
        with col1:
            day = st.selectbox("Forecast Day", ["Day 1", "Day 2", "Day 3"])
        with col2:
            threshold = st.selectbox("Snow Threshold", ["4 inches", "8 inches", "12 inches"])

        day_map = {"Day 1": ForecastDay.DAY1, "Day 2": ForecastDay.DAY2, "Day 3": ForecastDay.DAY3}
        thresh_map = {"4 inches": SnowThreshold.FOUR_INCH, "8 inches": SnowThreshold.EIGHT_INCH, "12 inches": SnowThreshold.TWELVE_INCH}

        url = get_snow_probability_url(thresh_map[threshold], day_map[day])

        st.markdown(f"**Probability of ≥{threshold} of snow - {day}**")
        try:
            st.image(url, use_container_width=True)
        except Exception:
            st.error("Could not load image. The product may not be available.")
            st.markdown(f"[View on WPC website]({url})")

    elif product_type == "Composite Charts":
        day = st.selectbox("Forecast Day", ["Day 1", "Day 2", "Day 3"])
        day_map = {"Day 1": ForecastDay.DAY1, "Day 2": ForecastDay.DAY2, "Day 3": ForecastDay.DAY3}

        url = get_composite_chart_url(day_map[day])

        st.markdown(f"**Composite Snow/Ice Probability - {day}**")
        st.caption("Shows probability of 4\", 8\", 12\" snow and 0.25\" ice")
        try:
            st.image(url, use_container_width=True)
        except Exception:
            st.error("Could not load image.")
            st.markdown(f"[View on WPC website]({url})")

    elif product_type == "Severity Index":
        col1, col2 = st.columns(2)

        with col1:
            st.markdown("**Winter Storm Severity Index**")
            try:
                st.image(get_winter_storm_severity_url(), use_container_width=True)
            except Exception:
                st.error("Could not load WSSI image.")

        with col2:
            st.markdown("**WSSI Explanation**")
            st.markdown("""
            The WSSI considers:
            - Snow/ice amounts
            - Wind impacts
            - Ground conditions
            - Temperature

            Categories:
            - **Limited**: Minor impacts
            - **Minor**: Some travel issues
            - **Moderate**: Significant impacts
            - **Major**: Widespread impacts
            - **Extreme**: Life-threatening
            """)

    elif product_type == "Heavy Snow Discussion":
        st.markdown("**Heavy Snow and Icing Discussion**")

        with st.spinner("Fetching discussion..."):
            discussion = get_heavy_snow_discussion()

        if discussion:
            st.text_area("Discussion Text", discussion['text'], height=400)
            st.caption(f"[View on WPC website]({discussion['url']})")
        else:
            st.info("Discussion not available or could not be fetched.")
            st.markdown("[View on WPC website](https://www.wpc.ncep.noaa.gov/discussions/hpcdiscussions.php?disc=pmdspd)")


def show_model_comparison():
    """Display model comparison resources."""
    st.subheader("Weather Model Comparison")
    st.markdown("""
    Different weather models can produce varying forecasts. Comparing models helps
    assess forecast confidence - when models agree, confidence is higher.
    """)

    models = get_model_comparison_urls()

    for model_id, info in models.items():
        with st.expander(f"**{info['name']}** ({model_id})"):
            st.markdown(info['description'])

            cols = st.columns(3)
            if 'viewer' in info:
                with cols[0]:
                    st.markdown(f"[Open Viewer]({info['viewer']})")
            if 'dashboard' in info:
                with cols[1]:
                    st.markdown(f"[Dashboard]({info['dashboard']})")
            if 'data_info' in info:
                with cols[2]:
                    st.markdown(f"[Documentation]({info['data_info']})")

    st.markdown("---")
    st.markdown("### NBM Snow Products")

    nbm_products = get_nbm_snow_graphics()
    for product in nbm_products:
        st.markdown(f"**{product['name']}**: {product['description']}")
        st.markdown(f"[Open Interactive Viewer]({product['url']})")

    st.markdown("---")
    st.markdown("### Model Comparison Tips")
    st.markdown("""
    - **For timing**: Trust HRRR (updates hourly, high resolution)
    - **For storm track 3+ days out**: Watch ECMWF and GFS trends
    - **For official forecast**: NWS uses NBM as starting point
    - **When models disagree**: Expect higher uncertainty
    - **Ensemble spread**: Wider spread = more uncertainty in outcome
    """)


def show_historical_data(location):
    """Display historical weather data and storm comparisons."""
    st.subheader("Historical Data")

    if not location:
        st.warning("Set up a location to access historical data.")
        return

    # Find nearby stations
    with st.spinner("Finding nearby weather stations..."):
        stations = find_stations_near_location(location['lat'], location['lon'])

    if not stations:
        st.error("No weather stations found near your location.")
        return

    # Station selector
    station_options = {f"{s['name']}, {s['state']}": s['id'] for s in stations[:10]}
    selected_station_name = st.selectbox("Select Weather Station", list(station_options.keys()))
    station_id = station_options[selected_station_name]

    # Sub-tabs for historical features
    hist_tab1, hist_tab2, hist_tab3 = st.tabs(["Recent Data", "Historical Storms", "Storm Comparison"])

    with hist_tab1:
        show_recent_data(station_id)

    with hist_tab2:
        show_historical_storms(station_id)

    with hist_tab3:
        show_storm_comparison(station_id, location)


def show_recent_data(station_id):
    """Show recent weather observations."""
    st.markdown("### Recent Observations")

    days_back = st.slider("Days to show", 7, 30, 14)

    with st.spinner("Fetching recent data..."):
        recent = get_recent_snowfall(station_id, days_back)

    if recent and recent['daily']:
        # Summary metrics
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Snow", f"{recent['total_snow']:.1f}\"")
        with col2:
            st.metric("Current Depth", f"{recent['current_depth']:.1f}\"" if recent['current_depth'] else "N/A")
        with col3:
            st.metric("Days Shown", recent['period_days'])

        # Daily data table
        df = pd.DataFrame(recent['daily'])
        df['date'] = pd.to_datetime(df['date'])

        # Format for display
        display_df = df[['date', 'snow', 'depth', 'max_temp', 'min_temp']].copy()
        display_df.columns = ['Date', 'New Snow', 'Depth', 'High', 'Low']
        display_df['Date'] = display_df['Date'].dt.strftime('%Y-%m-%d')

        st.dataframe(display_df, use_container_width=True, hide_index=True)
    else:
        st.info("No recent data available from this station.")


def show_historical_storms(station_id):
    """Show significant historical storms."""
    st.markdown("### Significant Storms")

    col1, col2 = st.columns(2)
    with col1:
        min_snow = st.number_input("Minimum snow (inches)", 2.0, 24.0, 4.0, 1.0)
    with col2:
        years = st.number_input("Years to search", 5, 30, 10, 5)

    if st.button("Find Storms", type="primary"):
        with st.spinner(f"Searching {years} years of data..."):
            storms = find_historical_storms(station_id, min_snow, years)

        if storms:
            st.success(f"Found {len(storms)} storms with {min_snow}\"+ snow")

            # Display as table
            storm_data = []
            for storm in storms[:20]:  # Top 20
                storm_data.append({
                    "Date": storm.start_date,
                    "Total Snow": f"{storm.total_snow:.1f}\"",
                    "Max Daily": f"{storm.max_snow_day:.1f}\"",
                    "Duration": f"{storm.start_date} to {storm.end_date}",
                    "Low Temp": f"{storm.min_temp:.0f}°F" if storm.min_temp else "N/A"
                })

            st.dataframe(pd.DataFrame(storm_data), use_container_width=True, hide_index=True)

            # Summary stats
            st.markdown("### Storm Statistics")
            all_totals = [s.total_snow for s in storms]
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Average Storm", f"{sum(all_totals)/len(all_totals):.1f}\"")
            with col2:
                st.metric("Biggest Storm", f"{max(all_totals):.1f}\"")
            with col3:
                st.metric("Total Storms", len(storms))
            with col4:
                st.metric("Per Year", f"{len(storms)/years:.1f}")
        else:
            st.info(f"No storms found with {min_snow}\"+ in the past {years} years.")


def show_storm_comparison(station_id, location):
    """Compare current forecast to historical data."""
    st.markdown("### Compare to History")
    st.markdown("See how the current forecast compares to similar time periods historically.")

    # Get current forecast snow amount
    forecasts = get_forecasts_for_location(location['id'], days_back=1)

    if not forecasts:
        st.info("Fetch forecast data first to compare with history.")
        return

    # Try to extract snow amount from latest forecast
    latest = forecasts[0]
    forecast_snow = st.number_input(
        "Forecast snow amount (inches)",
        0.0, 50.0, 4.0, 0.5,
        help="Enter the forecasted snow total to compare with history"
    )

    target_date = st.date_input(
        "Forecast date",
        value=datetime.now().date() + timedelta(days=1)
    )

    if st.button("Compare to History"):
        with st.spinner("Analyzing historical data..."):
            comparison = compare_to_historical(
                forecast_snow,
                station_id,
                target_date.strftime("%Y-%m-%d")
            )

        if comparison:
            st.markdown("### Comparison Results")

            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Forecast", f"{comparison['forecast_snow']:.1f}\"")
            with col2:
                st.metric("Historical Average", f"{comparison['historical_avg']:.1f}\"")
            with col3:
                st.metric("Percentile", f"{comparison['percentile']:.0f}%",
                          help="Percent of similar periods with less snow")

            if comparison['percentile'] >= 90:
                st.warning("This would be an unusually large storm for this time of year!")
            elif comparison['percentile'] >= 75:
                st.info("Above average snowfall for this time of year.")
            elif comparison['percentile'] <= 25:
                st.info("Below average snowfall for this time of year.")

            # Show historical comparison
            st.markdown("### Same Week in Previous Years")
            comp_df = pd.DataFrame(comparison['comparisons'])
            comp_df.columns = ['Year', 'Snow (inches)']
            st.dataframe(comp_df, use_container_width=True, hide_index=True)
        else:
            st.error("Could not fetch historical comparison data.")


def show_observed_snowfall():
    """Display observed snowfall analysis from NOHRSC."""
    st.subheader("Observed Snowfall Analysis")
    st.markdown("""
    The [National Operational Hydrologic Remote Sensing Center (NOHRSC)](https://www.nohrsc.noaa.gov/snowfall_v2/)
    provides analyzed snowfall maps based on observations and remote sensing.
    """)

    period = st.selectbox(
        "Select Period",
        ["Last 24 Hours", "Last 48 Hours", "Last 72 Hours", "Season Total"]
    )

    period_map = {
        "Last 24 Hours": "24h",
        "Last 48 Hours": "48h",
        "Last 72 Hours": "72h",
        "Season Total": "season"
    }

    url = get_observed_snowfall_url(period_map[period])

    st.markdown(f"**{period} Snowfall Analysis**")
    try:
        st.image(url, use_container_width=True)
    except Exception:
        st.error("Could not load image.")

    st.markdown(f"[View on NOHRSC website](https://www.nohrsc.noaa.gov/snowfall_v2/)")

    st.markdown("---")
    st.markdown("### Why This Matters")
    st.markdown("""
    Observed snowfall data is essential for:
    - **Verification**: Compare what was forecast vs. what actually fell
    - **Ground truth**: Official measurement of storm totals
    - **Seasonal tracking**: Monitor snowpack and seasonal trends
    - **Historical records**: Document significant storms
    """)
