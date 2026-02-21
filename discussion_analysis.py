"""
Discussion Analysis Module.

Extracts relevant portions of NWS Area Forecast Discussions for detected
snow events and generates AI-powered summaries.
"""

import re
import os
from datetime import datetime, date
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

from database import get_discussions_for_location


@dataclass
class DiscussionInsight:
    """AI-generated insight from forecast discussion."""
    event_dates: str
    summary: str
    confidence_assessment: str
    key_factors: List[str]
    meteorologist_concerns: List[str]
    timing_details: str
    amount_details: str
    raw_excerpt: str
    generated_at: str


def get_latest_discussion(location_id: int) -> Optional[Dict]:
    """Get the most recent forecast discussion for a location."""
    discussions = get_discussions_for_location(location_id, days_back=3)
    if discussions:
        return discussions[0]
    return None


def extract_relevant_sections(
    discussion_text: str,
    event_start: date,
    event_end: date
) -> str:
    """
    Extract sections of the discussion relevant to the event dates.

    NWS discussions typically have sections like:
    - .SHORT TERM... (Days 1-2)
    - .LONG TERM... (Days 3-7)
    - .AVIATION...
    - .MARINE...

    We want the weather-relevant sections that cover our event dates.
    """
    if not discussion_text:
        return ""

    # Calculate which section(s) we need
    today = datetime.now().date()
    days_until_start = (event_start - today).days
    days_until_end = (event_end - today).days

    relevant_text = []

    # Common section headers in NWS discussions
    sections = [
        (r'\.SHORT TERM.*?(?=\.[A-Z]|\Z)', 0, 2),      # Days 0-2
        (r'\.LONG TERM.*?(?=\.[A-Z]|\Z)', 3, 7),       # Days 3-7
        (r'\.NEAR TERM.*?(?=\.[A-Z]|\Z)', 0, 1),       # Days 0-1
        (r'\.EXTENDED.*?(?=\.[A-Z]|\Z)', 4, 7),        # Days 4-7
        (r'\.DAYS [3-7].*?(?=\.[A-Z]|\Z)', 3, 7),      # Days 3-7
        (r'\.UPDATE.*?(?=\.[A-Z]|\Z)', 0, 2),          # Updates (usually near-term)
    ]

    for pattern, section_start_day, section_end_day in sections:
        # Check if event overlaps with this section's time range
        if days_until_start <= section_end_day and days_until_end >= section_start_day:
            matches = re.findall(pattern, discussion_text, re.DOTALL | re.IGNORECASE)
            for match in matches:
                if match.strip() and len(match) > 50:  # Skip tiny matches
                    relevant_text.append(match.strip())

    # If no sections found, try to find any mention of snow/winter weather
    if not relevant_text:
        # Look for paragraphs mentioning snow
        paragraphs = discussion_text.split('\n\n')
        for para in paragraphs:
            if any(word in para.lower() for word in ['snow', 'winter', 'storm', 'accumul', 'inch']):
                if len(para) > 100:
                    relevant_text.append(para.strip())

    # Combine and limit length
    combined = '\n\n'.join(relevant_text)

    # Limit to ~3000 characters to keep API costs reasonable
    if len(combined) > 3000:
        combined = combined[:3000] + "..."

    return combined


def build_analysis_prompt(
    discussion_excerpt: str,
    event_start: date,
    event_end: date,
    snow_low: float,
    snow_high: float
) -> tuple[str, str]:
    """Build the analysis prompt and date string."""
    if event_start == event_end:
        date_str = event_start.strftime('%A, %B %d')
    else:
        date_str = f"{event_start.strftime('%A, %B %d')} through {event_end.strftime('%A, %B %d')}"

    prompt = f"""Analyze this NWS Area Forecast Discussion excerpt for a snow event expected {date_str}.
Current forecast shows {snow_low:.0f}-{snow_high:.0f} inches of snow.

DISCUSSION EXCERPT:
{discussion_excerpt}

Provide a concise analysis in this exact format:

SUMMARY: (2-3 sentences summarizing what meteorologists are saying about this event)

CONFIDENCE: (One sentence on how confident forecasters seem - are they using hedging language like "could", "may", "potential" or confident language like "will", "expected"?)

KEY FACTORS: (Bullet list of 2-4 factors that will determine the storm's impact - e.g., storm track, temperature profile, timing)

CONCERNS: (Bullet list of any concerns or uncertainties meteorologists mention)

TIMING: (One sentence on when snow is expected to start/end if mentioned)

AMOUNTS: (One sentence on snowfall amounts or accumulation mentioned, noting any ranges or uncertainty)

Keep each section brief and focused. Use plain language, not meteorological jargon."""

    return prompt, date_str


def generate_ai_summary_gemini(
    discussion_excerpt: str,
    event_start: date,
    event_end: date,
    snow_low: float,
    snow_high: float
) -> Optional[DiscussionInsight]:
    """Generate AI summary using Google Gemini."""
    api_key = os.environ.get('GEMINI_API_KEY') or os.environ.get('GOOGLE_API_KEY')
    if not api_key:
        return None

    try:
        from google import genai
    except ImportError:
        return None

    prompt, date_str = build_analysis_prompt(
        discussion_excerpt, event_start, event_end, snow_low, snow_high
    )

    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt
        )
        return parse_ai_response(response.text, date_str, discussion_excerpt)

    except Exception as e:
        print(f"Error generating Gemini summary: {e}")
        return None


def generate_ai_summary_anthropic(
    discussion_excerpt: str,
    event_start: date,
    event_end: date,
    snow_low: float,
    snow_high: float
) -> Optional[DiscussionInsight]:
    """Generate AI summary using Anthropic Claude."""
    api_key = os.environ.get('ANTHROPIC_API_KEY')
    if not api_key:
        return None

    try:
        import anthropic
    except ImportError:
        return None

    prompt, date_str = build_analysis_prompt(
        discussion_excerpt, event_start, event_end, snow_low, snow_high
    )

    try:
        client = anthropic.Anthropic(api_key=api_key)

        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )

        response_text = message.content[0].text
        return parse_ai_response(response_text, date_str, discussion_excerpt)

    except Exception as e:
        print(f"Error generating Anthropic summary: {e}")
        return None


def generate_ai_summary(
    discussion_excerpt: str,
    event_start: date,
    event_end: date,
    snow_low: float,
    snow_high: float
) -> Optional[DiscussionInsight]:
    """
    Generate an AI summary of the discussion for this specific event.

    Uses Google Gemini (free tier). Set GEMINI_API_KEY in .env.

    Returns None if no API is available or call fails.
    """
    # Use Gemini (free)
    return generate_ai_summary_gemini(
        discussion_excerpt, event_start, event_end, snow_low, snow_high
    )


def parse_ai_response(response: str, event_dates: str, raw_excerpt: str) -> DiscussionInsight:
    """Parse the AI response into structured data."""

    def extract_section(text: str, header: str) -> str:
        pattern = rf'{header}:\s*(.+?)(?=\n[A-Z]+:|$)'
        match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
        if match:
            return match.group(1).strip()
        return ""

    def extract_bullets(text: str, header: str) -> List[str]:
        section = extract_section(text, header)
        if not section:
            return []
        # Extract bullet points
        bullets = re.findall(r'[•\-\*]\s*(.+)', section)
        if bullets:
            return [b.strip() for b in bullets]
        # If no bullets, split by newlines
        lines = [line.strip() for line in section.split('\n') if line.strip()]
        return lines

    return DiscussionInsight(
        event_dates=event_dates,
        summary=extract_section(response, 'SUMMARY'),
        confidence_assessment=extract_section(response, 'CONFIDENCE'),
        key_factors=extract_bullets(response, 'KEY FACTORS'),
        meteorologist_concerns=extract_bullets(response, 'CONCERNS'),
        timing_details=extract_section(response, 'TIMING'),
        amount_details=extract_section(response, 'AMOUNTS'),
        raw_excerpt=raw_excerpt[:1000] if raw_excerpt else "",
        generated_at=datetime.now().isoformat()
    )


def get_event_discussion_insight(
    location_id: int,
    event_start: date,
    event_end: date,
    snow_low: float,
    snow_high: float
) -> Optional[DiscussionInsight]:
    """
    Get AI-generated insight for a specific snow event.

    Returns None if:
    - No discussion available
    - No API key configured
    - API call fails
    """
    # Get latest discussion
    discussion = get_latest_discussion(location_id)
    if not discussion:
        return None

    discussion_text = discussion.get('discussion_text', '')
    if not discussion_text:
        return None

    # Extract relevant sections
    excerpt = extract_relevant_sections(discussion_text, event_start, event_end)
    if not excerpt or len(excerpt) < 100:
        # Not enough relevant text found
        return None

    # Generate AI summary
    return generate_ai_summary(excerpt, event_start, event_end, snow_low, snow_high)


def get_discussion_excerpt_only(
    location_id: int,
    event_start: date,
    event_end: date
) -> Optional[str]:
    """
    Get just the relevant discussion excerpt without AI summarization.
    Useful as a fallback when API is not available.
    """
    discussion = get_latest_discussion(location_id)
    if not discussion:
        return None

    discussion_text = discussion.get('discussion_text', '')
    if not discussion_text:
        return None

    return extract_relevant_sections(discussion_text, event_start, event_end)


def highlight_winter_terms(text: str) -> str:
    """Add markdown highlighting to winter weather terms."""
    terms = [
        'snow', 'snowfall', 'accumulation', 'accumulating', 'inches',
        'heavy', 'moderate', 'light', 'blizzard', 'winter storm',
        'ice', 'freezing rain', 'sleet', 'mixed precipitation',
        'wind', 'gusts', 'visibility', 'travel', 'hazardous',
        'advisory', 'warning', 'watch'
    ]

    result = text
    for term in terms:
        # Case-insensitive replacement with bold
        pattern = re.compile(re.escape(term), re.IGNORECASE)
        result = pattern.sub(lambda m: f"**{m.group()}**", result)

    return result
