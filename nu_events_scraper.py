"""
nu_events_scraper.py

Pulls events from your saved PlanIt Purple JSON feed (Northwestern's
official event calendar) and normalizes them into the shape "The Brief"
website expects (events.json).

SETUP
1. Paste your feed's JSON URL into FEED_URL below (the one you built at
   planitpurple.northwestern.edu -> Dashboard -> Event Feeds).
2. pip install requests
3. python nu_events_scraper.py

This script was rewritten against a REAL sample response from Northwestern's
feed (not a guess), so the field names below should match what you get.
If Northwestern changes their feed format later, this is the part that
would need updating.
"""

import json
import re
from html import unescape

import requests

# ---- REQUIRED: paste your feed's JSON URL here ----
FEED_URL = "https://planitpurple.northwestern.edu/feed/json/2462"

# Only keep events whose category_name matches one of these. Everything
# else (social events, academic-general, arts, etc.) gets filtered out.
# Add to this list if you add calendars whose relevant events use a
# different category.
RELEVANT_CATEGORIES = {
    "Career/Workplace",
    "Business/Economy",
}

# --- Heuristic tagging ---------------------------------------------------
# First matching pattern wins. Applied to title + description, lowercased.
# This is a draft heuristic, not ground truth -- review flagged events,
# especially anything that falls back to the defaults below.
LEVEL_RULES = [
    (r"\b(intern|early talent|entry.level|new grad|rotational program)\b", "Early Talent"),
    (r"\b(young professional|early.career|gennext|next gen|alumni)\b", "Young Professional"),
    (r"\b(career fair|job fair|career trek)\b", "Early Talent"),
]
DEFAULT_LEVEL = "Early Talent"  # Career/Workplace events at NU skew early-career by default

INDUSTRY_RULES = [
    (r"\b(beauty|cpg|consumer packaged goods)\b", "Brand & CPG"),
    (r"\b(advertising|agency|agencies)\b", "Advertising"),
    (r"\b(pr\b|public relations|comms|communications)\b", "PR & Comms"),
    (r"\bretail\b", "Retail"),
    (r"\b(tech|technology|software)\b", "Tech"),
    (r"\b(research|analytics|data)\b", "Research/Analytics"),
]
DEFAULT_INDUSTRY = "Advertising"  # fallback bucket; re-tag manually as needed

SECTOR_RULES = [
    (r"\b(fair)\b", "Career Fair"),
    (r"\bpanel\b", "Panel"),
    (r"\b(mixer|networking|meet.?up|reception)\b", "Networking"),
    (r"\b(workshop|prep|training)\b", "Workshop"),
    (r"\btrade show\b", "Trade Show"),
]
DEFAULT_SECTOR = "Speaker Series"


def strip_html(text):
    return unescape(re.sub("<[^<]+?>", "", text or "")).strip()


def match_rules(text, rules, default):
    text = text.lower()
    for pattern, label in rules:
        if re.search(pattern, text):
            return label
    return default


def normalize_location(ev):
    loc_name = (ev.get("location_name") or "").strip()
    building = (ev.get("building_name") or "").strip()
    if loc_name == "Online":
        return "Online"
    if "chicago" in loc_name.lower() or "chicago" in building.lower() or "wieboldt" in building.lower():
        return "Chicago"
    return "Evanston"


def normalize_cost(ev):
    cost = (ev.get("cost") or "").strip()
    if cost == "" or "free" in cost.lower():
        return True, None
    return False, cost


def normalize_event(ev):
    title = strip_html(ev.get("title", ""))
    description = strip_html(ev.get("description", ""))
    text_for_tagging = f"{title} {description}"

    date_str = ev.get("eventdate")  # "YYYY-MM-DD"
    if not date_str:
        return None
    year, month_num, day = date_str.split("-")
    month_name = ["JAN","FEB","MAR","APR","MAY","JUN","JUL","AUG","SEP","OCT","NOV","DEC"][int(month_num) - 1]

    free, price = normalize_cost(ev)

    venue_parts = [p for p in [ev.get("building_name"), ev.get("address_2")] if p]
    venue = ", ".join(venue_parts) if venue_parts else (ev.get("location_name") or "Northwestern")

    audiences = [a.get("name") for a in ev.get("audiences", [])]

    return {
        "title": title,
        "host": ev.get("calendar_name") or "Northwestern",
        "sector": match_rules(text_for_tagging, SECTOR_RULES, DEFAULT_SECTOR),
        "industry": match_rules(text_for_tagging, INDUSTRY_RULES, DEFAULT_INDUSTRY),
        "level": match_rules(text_for_tagging, LEVEL_RULES, DEFAULT_LEVEL),
        "loc": normalize_location(ev),
        "venue": venue,
        "date": date_str,
        "month": month_name,
        "day": day,
        "time": ev.get("start_time_display_format", ""),
        "free": free,
        "price": price,
        "tags": audiences,
        "source_url": ev.get("web_address") or ev.get("url"),
    }


def main():
    if "PASTE_YOUR" in FEED_URL:
        print("Set FEED_URL at the top of this script to your actual PlanIt Purple JSON feed URL, then rerun.")
        return

    resp = requests.get(FEED_URL, timeout=20)
    resp.raise_for_status()
    raw_events = resp.json()  # top-level list, based on the real sample response

    print(f"Fetched {len(raw_events)} raw events from the feed.")

    kept = []
    skipped_categories = {}
    for ev in raw_events:
        category = ev.get("category_name", "")
        if category not in RELEVANT_CATEGORIES:
            skipped_categories[category] = skipped_categories.get(category, 0) + 1
            continue
        normalized = normalize_event(ev)
        if normalized:
            kept.append(normalized)

    print(f"Kept {len(kept)} events after category filtering.")
    if skipped_categories:
        print("Skipped categories (not in RELEVANT_CATEGORIES):")
        for cat, count in sorted(skipped_categories.items(), key=lambda x: -x[1]):
            print(f"  {cat or '(none)'}: {count}")

    with open("events.json", "w") as f:
        json.dump(kept, f, indent=2)

    print("\nWrote events.json. Review level/industry/sector tags before publishing --")
    print("anything that fell back to a default is a guess, not a confirmed tag.")


if __name__ == "__main__":
    main()
