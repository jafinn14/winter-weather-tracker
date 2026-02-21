import streamlit as st
from database import get_location_by_zip, get_discussions_for_location
from datetime import datetime
import re

def highlight_winter_terms(text):
    """Highlight winter weather related terms in the discussion text."""
    winter_terms = [
        'snow', 'ice', 'freezing', 'winter storm', 'blizzard',
        'accumulation', 'sleet', 'wind chill', 'cold', 'frost',
        'nor\'easter', 'noreaster', 'coastal storm'
    ]

    highlighted = text
    for term in winter_terms:
        pattern = re.compile(f'({term})', re.IGNORECASE)
        highlighted = pattern.sub(r'**\1**', highlighted)

    return highlighted

def show():
    st.title("Forecast Discussion Archive")

    # Check if location is set
    if "current_zip" not in st.session_state:
        st.warning("Please set up your location first in the 'Setup & Fetch Data' page.")
        return

    location = get_location_by_zip(st.session_state.current_zip)
    if not location:
        st.error("Location not found. Please set up your location again.")
        return

    st.markdown(f"### 📍 {location['city']}, {location['state']}")
    st.markdown(f"Forecast Office: **{location['forecast_office']}**")

    st.markdown("""
    Area Forecast Discussions (AFDs) are detailed narratives written by National Weather Service meteorologists
    explaining their reasoning behind the forecast. These provide valuable insights into forecast uncertainty
    and changing weather patterns.
    """)

    # Get all discussions
    discussions = get_discussions_for_location(location['id'], days_back=30)

    if not discussions:
        st.warning("No forecast discussions available yet. Fetch data from the Setup page to begin collecting discussions.")
        return

    st.success(f"Found {len(discussions)} forecast discussions in the archive")

    # Display options
    highlight_terms = st.checkbox("Highlight winter weather terms", value=True)
    show_full = st.checkbox("Show full discussions (may be long)", value=False)

    # Display discussions
    for idx, discussion in enumerate(discussions):
        fetched_at = datetime.fromisoformat(discussion['fetched_at'])

        issued_str = "Unknown"
        if discussion['issued_at']:
            try:
                issued_at = datetime.fromisoformat(discussion['issued_at'].replace('Z', '+00:00'))
                issued_str = issued_at.strftime('%B %d, %Y at %I:%M %p UTC')
            except:
                issued_str = discussion['issued_at']

        with st.expander(
            f"Discussion #{idx + 1} - Fetched: {fetched_at.strftime('%m/%d/%Y %I:%M %p')}",
            expanded=(idx == 0)
        ):
            st.caption(f"**Issued:** {issued_str}")
            st.caption(f"**Fetched:** {fetched_at.strftime('%B %d, %Y at %I:%M %p')}")

            discussion_text = discussion['discussion_text']

            # Apply highlighting if requested
            if highlight_terms:
                discussion_text = highlight_winter_terms(discussion_text)

            # Truncate if not showing full
            if not show_full and len(discussion_text) > 2000:
                discussion_text = discussion_text[:2000] + "\n\n... (truncated, check 'Show full discussions' to see more)"

            st.markdown(discussion_text)

            # Show character count
            st.caption(f"Length: {len(discussion['discussion_text'])} characters")

    # Discussion comparison
    if len(discussions) >= 2:
        st.markdown("---")
        st.markdown("### Compare Two Discussions")

        col1, col2 = st.columns(2)

        with col1:
            discussion_1_idx = st.selectbox(
                "Select first discussion",
                range(len(discussions)),
                format_func=lambda x: f"Discussion {x + 1} ({datetime.fromisoformat(discussions[x]['fetched_at']).strftime('%m/%d %I:%M %p')})"
            )

        with col2:
            discussion_2_idx = st.selectbox(
                "Select second discussion",
                range(len(discussions)),
                index=min(1, len(discussions) - 1),
                format_func=lambda x: f"Discussion {x + 1} ({datetime.fromisoformat(discussions[x]['fetched_at']).strftime('%m/%d %I:%M %p')})"
            )

        if st.button("Compare Selected Discussions"):
            col_a, col_b = st.columns(2)

            with col_a:
                st.markdown(f"#### Discussion {discussion_1_idx + 1}")
                fetched_1 = datetime.fromisoformat(discussions[discussion_1_idx]['fetched_at'])
                st.caption(fetched_1.strftime('%B %d, %Y at %I:%M %p'))

                text_1 = discussions[discussion_1_idx]['discussion_text']
                if highlight_terms:
                    text_1 = highlight_winter_terms(text_1)

                st.text_area("", text_1, height=400, key="disc_1", disabled=True)

            with col_b:
                st.markdown(f"#### Discussion {discussion_2_idx + 1}")
                fetched_2 = datetime.fromisoformat(discussions[discussion_2_idx]['fetched_at'])
                st.caption(fetched_2.strftime('%B %d, %Y at %I:%M %p'))

                text_2 = discussions[discussion_2_idx]['discussion_text']
                if highlight_terms:
                    text_2 = highlight_winter_terms(text_2)

                st.text_area("", text_2, height=400, key="disc_2", disabled=True)
