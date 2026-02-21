import streamlit as st
from datetime import datetime, timedelta
import pandas as pd
from database import (
    get_location_by_zip, get_observations_for_location,
    save_observation, delete_observation, get_forecasts_for_location
)


def show():
    st.title("My Observations")
    st.markdown("Log your own snow measurements to compare with forecasts.")

    # Check if location is set
    if "current_zip" not in st.session_state:
        st.warning("Please set up a location first on the Setup page.")
        return

    location = get_location_by_zip(st.session_state.current_zip)
    if not location:
        st.warning("Location not found. Please set up a location on the Setup page.")
        return

    st.info(f"Recording observations for: {location['city']}, {location['state']}")

    # Tabs for entry and history
    tab1, tab2, tab3 = st.tabs(["Log Observation", "History", "Verification"])

    with tab1:
        show_entry_form(location)

    with tab2:
        show_observation_history(location)

    with tab3:
        show_verification(location)


def show_entry_form(location: dict):
    """Display the observation entry form."""
    st.subheader("Record a Measurement")

    with st.form("observation_form"):
        col1, col2 = st.columns(2)

        with col1:
            obs_date = st.date_input(
                "Date",
                value=datetime.now().date(),
                max_value=datetime.now().date()
            )
            obs_time = st.time_input(
                "Time",
                value=datetime.now().time()
            )

        with col2:
            snow_depth = st.number_input(
                "Total Snow Depth (inches)",
                min_value=0.0,
                max_value=100.0,
                step=0.5,
                help="Total depth of snow on the ground"
            )
            new_snow = st.number_input(
                "New Snow Since Last Observation (inches)",
                min_value=0.0,
                max_value=50.0,
                step=0.1,
                help="Amount of new snow since your last measurement"
            )

        temperature = st.number_input(
            "Temperature (°F)",
            min_value=-50.0,
            max_value=120.0,
            step=1.0,
            value=32.0,
            help="Current temperature reading"
        )

        conditions = st.text_area(
            "Notes",
            placeholder="e.g., Heavy snow falling, drifting, ice underneath, snow character (light/wet/heavy)",
            help="Any additional observations about conditions"
        )

        submitted = st.form_submit_button("Save Observation", type="primary", use_container_width=True)

        if submitted:
            # Combine date and time
            observed_at = datetime.combine(obs_date, obs_time).isoformat()

            # Save to database
            obs_id = save_observation(
                location_id=location['id'],
                observed_at=observed_at,
                snow_depth_inches=snow_depth if snow_depth > 0 else None,
                new_snow_inches=new_snow if new_snow > 0 else None,
                temperature_f=temperature,
                conditions_notes=conditions if conditions else None
            )

            st.success(f"Observation saved! (ID: {obs_id})")
            st.rerun()


def show_observation_history(location: dict):
    """Display observation history with option to delete."""
    st.subheader("Observation History")

    # Get observations
    observations = get_observations_for_location(location['id'], days_back=90)

    if not observations:
        st.info("No observations recorded yet. Use the 'Log Observation' tab to add your first measurement.")
        return

    # Convert to DataFrame for display
    df = pd.DataFrame(observations)
    df['observed_at'] = pd.to_datetime(df['observed_at'])
    df = df.sort_values('observed_at', ascending=False)

    # Summary stats
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Observations", len(df))
    with col2:
        max_depth = df['snow_depth_inches'].max()
        if pd.notna(max_depth):
            st.metric("Max Snow Depth", f"{max_depth:.1f}\"")
    with col3:
        total_new = df['new_snow_inches'].sum()
        if pd.notna(total_new):
            st.metric("Total New Snow", f"{total_new:.1f}\"")

    st.markdown("---")

    # Display each observation
    for _, row in df.iterrows():
        with st.container():
            col1, col2, col3 = st.columns([3, 2, 1])

            with col1:
                obs_time = row['observed_at'].strftime("%Y-%m-%d %I:%M %p")
                st.markdown(f"**{obs_time}**")

                details = []
                if pd.notna(row['snow_depth_inches']):
                    details.append(f"Depth: {row['snow_depth_inches']:.1f}\"")
                if pd.notna(row['new_snow_inches']):
                    details.append(f"New: {row['new_snow_inches']:.1f}\"")
                if pd.notna(row['temperature_f']):
                    details.append(f"Temp: {row['temperature_f']:.0f}°F")

                st.markdown(" | ".join(details))

            with col2:
                if row['conditions_notes']:
                    st.caption(row['conditions_notes'][:100])

            with col3:
                if st.button("Delete", key=f"del_{row['id']}", type="secondary"):
                    delete_observation(row['id'])
                    st.rerun()

            st.markdown("---")


def show_verification(location: dict):
    """Compare observations with forecasts."""
    st.subheader("Forecast vs Actual")

    observations = get_observations_for_location(location['id'], days_back=30)
    forecasts = get_forecasts_for_location(location['id'], days_back=30)

    if not observations:
        st.info("No observations recorded. Log measurements during a storm to verify forecast accuracy.")
        return

    if not forecasts:
        st.info("No forecast data available. Fetch forecasts to compare.")
        return

    # Build observation summary by date
    obs_df = pd.DataFrame(observations)
    obs_df['observed_at'] = pd.to_datetime(obs_df['observed_at'])
    obs_df['date'] = obs_df['observed_at'].dt.date

    # Sum new snow by date
    daily_obs = obs_df.groupby('date').agg({
        'new_snow_inches': 'sum',
        'snow_depth_inches': 'max',
        'temperature_f': 'mean'
    }).reset_index()

    st.markdown("### Daily Observed Snowfall")

    # Display comparison table
    comparison_data = []
    for _, row in daily_obs.iterrows():
        date_str = row['date'].strftime("%Y-%m-%d")

        # Find forecast made before this date
        forecast_snow = find_forecast_for_date(forecasts, row['date'])

        comparison_data.append({
            'Date': date_str,
            'Observed Snow': f"{row['new_snow_inches']:.1f}\"" if pd.notna(row['new_snow_inches']) else "N/A",
            'Forecast Snow': f"{forecast_snow:.1f}\"" if forecast_snow else "N/A",
            'Max Depth': f"{row['snow_depth_inches']:.1f}\"" if pd.notna(row['snow_depth_inches']) else "N/A",
            'Avg Temp': f"{row['temperature_f']:.0f}°F" if pd.notna(row['temperature_f']) else "N/A"
        })

    if comparison_data:
        st.dataframe(
            pd.DataFrame(comparison_data),
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("Not enough data for comparison.")

    # Verification summary
    st.markdown("### Verification Summary")
    st.markdown("""
    *Coming soon: This section will calculate forecast accuracy metrics like:*
    - Mean Absolute Error (MAE) for snow amounts
    - Bias (tendency to over/under predict)
    - Hit rate for exceeding thresholds (2", 4", 6", etc.)
    """)


def find_forecast_for_date(forecasts: list, target_date) -> float:
    """
    Find the forecast snow amount for a specific date.
    Uses the most recent forecast made before the target date.
    """
    import re
    from datetime import datetime

    # Convert target_date to datetime if needed
    if hasattr(target_date, 'isoformat'):
        target_dt = datetime.combine(target_date, datetime.min.time())
    else:
        target_dt = target_date

    # Find forecasts made before the target date
    valid_forecasts = []
    for f in forecasts:
        fetched_at = datetime.fromisoformat(f['fetched_at'].replace('Z', '+00:00'))
        if fetched_at.replace(tzinfo=None) < target_dt:
            valid_forecasts.append(f)

    if not valid_forecasts:
        return None

    # Get the most recent forecast before the date
    latest = max(valid_forecasts, key=lambda x: x['fetched_at'])

    # Try to extract snow amount from gridpoint data
    try:
        gridpoint = latest['forecast_data'].get('gridpoint', {})
        properties = gridpoint.get('properties', {})
        snow_amount = properties.get('snowfallAmount', {})
        values = snow_amount.get('values', [])

        total_snow = 0
        for entry in values:
            valid_time = entry.get('validTime', '')
            value = entry.get('value', 0)

            # Check if this time period matches target date
            if target_date.isoformat() in valid_time and value:
                total_snow += value / 25.4  # Convert mm to inches

        return total_snow if total_snow > 0 else None
    except (KeyError, TypeError, AttributeError):
        return None
