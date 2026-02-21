import streamlit as st
from database import get_location_by_zip
from datetime import datetime

# NWS Graphics URLs by forecast office
# These are the standard winter weather graphics published by each office
NWS_GRAPHICS = {
    'BOX': {  # Boston/Norton
        'office_name': 'Boston/Norton, MA',
        'base_url': 'https://www.weather.gov/images/box',
        'products': {
            'Probabilistic Snowfall - 90%': 'winter/StormTotalSnowWeb1.png',
            'Probabilistic Snowfall - 50% (Official)': 'winter/StormTotalSnowWeb2.png',
            'Probabilistic Snowfall - 10%': 'winter/StormTotalSnowWeb3.png',
            'Snow Exceedance 2"': 'winter/Winter_Headline1.png',
            'Snow Exceedance 4"': 'winter/Winter_Headline2.png',
            'Snow Exceedance 6"': 'winter/Winter_Headline3.png',
            'Snow Exceedance 12"': 'winter/Winter_Headline4.png',
            'Ice Accumulation - 90%': 'winter/StormTotalIceWeb1.png',
            'Ice Accumulation - 50%': 'winter/StormTotalIceWeb2.png',
            'Ice Accumulation - 10%': 'winter/StormTotalIceWeb3.png',
            'Winter Storm Severity Index': 'winter/WinterSeverity.png',
        },
        'animations': {
            '6-Hour Snowfall Animation': 'winter/txtstorm_12_animated.gif',
            'Snow Character Animation': 'winter/txtptype_12_animated.gif',
            'Snowfall Rate Animation': 'winter/txtsn01_9_animated.gif',
        }
    },
    'GYX': {  # Gray/Portland, ME
        'office_name': 'Gray/Portland, ME',
        'base_url': 'https://www.weather.gov/images/gyx',
        'products': {
            'Probabilistic Snowfall - 90%': 'winter/StormTotalSnowWeb1.png',
            'Probabilistic Snowfall - 50% (Official)': 'winter/StormTotalSnowWeb2.png',
            'Probabilistic Snowfall - 10%': 'winter/StormTotalSnowWeb3.png',
            'Ice Accumulation - 90%': 'winter/StormTotalIceWeb1.png',
            'Ice Accumulation - 50%': 'winter/StormTotalIceWeb2.png',
            'Ice Accumulation - 10%': 'winter/StormTotalIceWeb3.png',
        },
        'animations': {
            '6-Hour Snowfall Animation': 'winter/txtstorm_12_animated.gif',
        }
    },
    'ALY': {  # Albany, NY
        'office_name': 'Albany, NY',
        'base_url': 'https://www.weather.gov/images/aly',
        'products': {
            'Probabilistic Snowfall - 90%': 'winter/StormTotalSnowWeb1.png',
            'Probabilistic Snowfall - 50% (Official)': 'winter/StormTotalSnowWeb2.png',
            'Probabilistic Snowfall - 10%': 'winter/StormTotalSnowWeb3.png',
            'Ice Accumulation - 90%': 'winter/StormTotalIceWeb1.png',
            'Ice Accumulation - 50%': 'winter/StormTotalIceWeb2.png',
            'Ice Accumulation - 10%': 'winter/StormTotalIceWeb3.png',
        },
        'animations': {}
    },
    'CAR': {  # Caribou, ME
        'office_name': 'Caribou, ME',
        'base_url': 'https://www.weather.gov/images/car',
        'products': {
            'Probabilistic Snowfall - 90%': 'winter/StormTotalSnowWeb1.png',
            'Probabilistic Snowfall - 50% (Official)': 'winter/StormTotalSnowWeb2.png',
            'Probabilistic Snowfall - 10%': 'winter/StormTotalSnowWeb3.png',
        },
        'animations': {}
    },
    'BTV': {  # Burlington, VT
        'office_name': 'Burlington, VT',
        'base_url': 'https://www.weather.gov/images/btv',
        'products': {
            'Probabilistic Snowfall - 90%': 'winter/StormTotalSnowWeb1.png',
            'Probabilistic Snowfall - 50% (Official)': 'winter/StormTotalSnowWeb2.png',
            'Probabilistic Snowfall - 10%': 'winter/StormTotalSnowWeb3.png',
        },
        'animations': {}
    },
    'OKX': {  # New York/Upton
        'office_name': 'New York/Upton',
        'base_url': 'https://www.weather.gov/images/okx',
        'products': {
            'Probabilistic Snowfall - 90%': 'winter/StormTotalSnowWeb1.png',
            'Probabilistic Snowfall - 50% (Official)': 'winter/StormTotalSnowWeb2.png',
            'Probabilistic Snowfall - 10%': 'winter/StormTotalSnowWeb3.png',
        },
        'animations': {}
    }
}

def show():
    st.title("NWS Winter Weather Graphics")

    # Check if location is set
    if "current_zip" not in st.session_state:
        st.warning("Please set up your location first in the 'Setup & Fetch Data' page.")
        return

    location = get_location_by_zip(st.session_state.current_zip)
    if not location:
        st.error("Location not found. Please set up your location again.")
        return

    forecast_office = location['forecast_office']

    st.markdown(f"### 📍 {location['city']}, {location['state']}")
    st.markdown(f"**Forecast Office:** {forecast_office}")

    # Check if we have graphics for this office
    if forecast_office not in NWS_GRAPHICS:
        st.warning(f"""
        Graphics configuration not available for forecast office **{forecast_office}**.

        Configured offices: {', '.join(NWS_GRAPHICS.keys())}

        You can still view graphics by visiting:
        https://www.weather.gov/{forecast_office.lower()}/winter
        """)
        return

    office_data = NWS_GRAPHICS[forecast_office]
    st.info(f"Displaying official graphics from **{office_data['office_name']}**")

    st.markdown("""
    These are official National Weather Service graphics. Images are updated by NWS meteorologists
    during active winter weather events. If no winter weather is expected, some graphics may not be available.
    """)

    # Tabs for different graphic types
    tab1, tab2, tab3 = st.tabs(["Probabilistic Snow/Ice Maps", "Animated Forecasts", "Additional Resources"])

    with tab1:
        st.markdown("### Probabilistic Snowfall Forecasts")
        st.caption("""
        These maps show three scenarios:
        - **90% chance**: Conservative estimate (9 in 10 chance of higher amounts)
        - **50% chance**: Official NWS forecast (most likely scenario)
        - **10% chance**: High-end estimate (only 1 in 10 chance of higher amounts)
        """)

        # Display snowfall maps
        snow_products = {k: v for k, v in office_data['products'].items() if 'Snowfall' in k}
        for product_name, product_path in snow_products.items():
            url = f"{office_data['base_url']}/{product_path}"

            with st.expander(product_name, expanded=True):
                try:
                    st.image(url, use_container_width=True)
                    st.caption(f"Last updated: Check timestamp on image | [Direct Link]({url})")
                except:
                    st.warning(f"Image not currently available. May not be an active winter weather event.")
                    st.markdown(f"[Try direct link]({url})")

        st.markdown("---")
        st.markdown("### Exceedance Probability Maps")
        st.caption("Probability that snowfall will exceed specific thresholds")

        # Display exceedance maps
        exceed_products = {k: v for k, v in office_data['products'].items() if 'Exceedance' in k}
        if exceed_products:
            for product_name, product_path in exceed_products.items():
                url = f"{office_data['base_url']}/{product_path}"

                with st.expander(product_name):
                    try:
                        st.image(url, use_container_width=True)
                        st.caption(f"[Direct Link]({url})")
                    except:
                        st.warning(f"Image not currently available.")

        st.markdown("---")
        st.markdown("### Ice Accumulation Forecasts")

        # Display ice maps
        ice_products = {k: v for k, v in office_data['products'].items() if 'Ice' in k}
        for product_name, product_path in ice_products.items():
            url = f"{office_data['base_url']}/{product_path}"

            with st.expander(product_name):
                try:
                    st.image(url, use_container_width=True)
                    st.caption(f"[Direct Link]({url})")
                except:
                    st.warning(f"Image not currently available.")

        # Winter Storm Severity Index if available
        if 'Winter Storm Severity Index' in office_data['products']:
            st.markdown("---")
            st.markdown("### Winter Storm Severity Index")
            url = f"{office_data['base_url']}/{office_data['products']['Winter Storm Severity Index']}"
            try:
                st.image(url, use_container_width=True)
                st.caption(f"[Direct Link]({url})")
            except:
                st.warning("WSSI graphic not currently available.")

    with tab2:
        st.markdown("### Animated Forecast Products")
        st.caption("These animations show how snowfall and precipitation evolve over time")

        if office_data['animations']:
            for anim_name, anim_path in office_data['animations'].items():
                url = f"{office_data['base_url']}/{anim_path}"

                with st.expander(anim_name, expanded=True):
                    try:
                        st.image(url, use_container_width=True)
                        st.caption(f"Animation updates automatically | [Direct Link]({url})")
                    except:
                        st.warning(f"Animation not currently available.")
                        st.markdown(f"[Try direct link]({url})")
        else:
            st.info(f"No animated products configured for {forecast_office}. Check the office website directly.")

    with tab3:
        st.markdown("### Additional Resources")

        office_lower = forecast_office.lower()

        st.markdown(f"""
        **Official NWS {office_data['office_name']} Pages:**

        - [Winter Weather Page](https://www.weather.gov/{office_lower}/winter)
        - [Forecast Office Homepage](https://www.weather.gov/{office_lower})
        - [Hazardous Weather Outlook](https://www.weather.gov/{office_lower}/HWO)
        - [Local Conditions & Radar](https://www.weather.gov/{office_lower})

        **National Products:**

        - [National Snow Analysis](https://www.nohrsc.noaa.gov/interactive/html/map.html)
        - [Winter Weather Warnings & Watches](https://www.weather.gov/winter)
        - [Climate Prediction Center](https://www.cpc.ncep.noaa.gov/)
        """)

        st.markdown("---")
        st.markdown("### Refresh Graphics")

        if st.button("Reload All Graphics", type="primary"):
            st.rerun()

        st.caption("""
        Graphics are loaded directly from NWS servers in real-time.
        Click 'Reload All Graphics' to fetch the latest versions.
        NWS typically updates graphics every 6-12 hours during active weather.
        """)
