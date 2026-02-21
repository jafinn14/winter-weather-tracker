import streamlit as st
from nws_api import (
    get_location_from_zip, get_grid_point, get_forecast,
    get_hourly_forecast, get_gridpoint_data, get_area_forecast_discussion,
    NWSAPIError
)
from database import (
    add_location, get_location_by_zip, save_forecast, save_discussion
)
from datetime import datetime

def show():
    st.title("Setup & Fetch Data")
    st.markdown("Enter your zip code and fetch the latest forecast data from the National Weather Service.")

    # Input section
    col1, col2 = st.columns([2, 1])

    with col1:
        zip_code = st.text_input("Enter your zip code:", max_chars=5, placeholder="e.g., 02108")

    with col2:
        st.write("")
        st.write("")
        fetch_button = st.button("Fetch Latest Data", type="primary", use_container_width=True)

    # Display current location if set
    if "current_zip" in st.session_state:
        location = get_location_by_zip(st.session_state.current_zip)
        if location:
            st.info(f"📍 Current location: {location['city']}, {location['state']} ({location['zip_code']})")

    if fetch_button and zip_code:
        if len(zip_code) != 5 or not zip_code.isdigit():
            st.error("Please enter a valid 5-digit zip code.")
            return

        with st.spinner("Fetching data from National Weather Service..."):
            try:
                # Step 1: Get location data
                st.write("1️⃣ Converting zip code to coordinates...")
                lat, lon, city, state = get_location_from_zip(zip_code)
                st.success(f"Found: {city}, {state} ({lat:.4f}, {lon:.4f})")

                # Step 2: Get NWS grid point
                st.write("2️⃣ Getting NWS grid point...")
                grid_id, grid_x, grid_y = get_grid_point(lat, lon)
                st.success(f"Grid point: {grid_id} ({grid_x}, {grid_y})")

                # Step 3: Save location to database
                location_id = add_location(zip_code, lat, lon, grid_x, grid_y, grid_id, city, state)
                st.session_state.current_zip = zip_code
                st.session_state.location_id = location_id

                # Step 4: Fetch forecast data
                st.write("3️⃣ Fetching forecast data...")
                forecast_data = get_forecast(grid_id, grid_x, grid_y)
                hourly_forecast = get_hourly_forecast(grid_id, grid_x, grid_y)
                gridpoint_data = get_gridpoint_data(grid_id, grid_x, grid_y)

                # Combine all forecast data
                combined_forecast = {
                    "forecast": forecast_data,
                    "hourly": hourly_forecast,
                    "gridpoint": gridpoint_data
                }

                save_forecast(location_id, combined_forecast)
                st.success("Forecast data saved!")

                # Step 5: Fetch Area Forecast Discussion
                st.write("4️⃣ Fetching Area Forecast Discussion...")
                try:
                    afd_data = get_area_forecast_discussion(grid_id)
                    save_discussion(location_id, afd_data["text"], afd_data["issued_at"])
                    st.success("Forecast discussion saved!")
                except NWSAPIError as e:
                    st.warning(f"Could not fetch AFD: {str(e)}")

                # Show summary
                st.success("✅ All data fetched successfully!")
                st.balloons()

                # Display quick summary
                with st.expander("View Forecast Summary"):
                    periods = forecast_data.get("properties", {}).get("periods", [])
                    if periods:
                        for period in periods[:4]:  # Show first 4 periods
                            st.markdown(f"**{period['name']}**: {period['shortForecast']}")
                            st.markdown(f"🌡️ {period['temperature']}°{period['temperatureUnit']}")
                            st.markdown("---")

            except NWSAPIError as e:
                st.error(f"Error: {str(e)}")
            except Exception as e:
                st.error(f"Unexpected error: {str(e)}")

    elif fetch_button:
        st.warning("Please enter a zip code first.")

    # Instructions
    st.markdown("---")
    st.markdown("""
    ### How to use this app:

    1. **Enter your zip code** and click "Fetch Latest Data"
    2. **Fetch data regularly** (daily or multiple times per day during active weather) to track forecast changes
    3. View the **Current Forecast** page to see the latest predictions
    4. Check **Forecast Evolution** to see how predictions have changed over time
    5. Read the **Discussion Archive** to understand meteorologist reasoning

    Data is automatically kept for 30 days.
    """)
