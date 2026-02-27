import re
import time
import xml.etree.ElementTree as ET

import requests
from bs4 import BeautifulSoup

MP_BASE = "https://www.mountainproject.com"
OVERPASS_URL = "https://overpass-api.de/api/interpreter"
_CLIMBING_NAME_RE = "[Cc]limb|[Bb]oulder"

OVERPASS_QUERY = f"""
[out:json][timeout:90];
(
  node["sport"="climbing"]["leisure"="sports_centre"](24,-125,50,-66);
  node["sport"="climbing"]["amenity"="gym"](24,-125,50,-66);
  node["sport"="climbing"]["leisure"="fitness_centre"](24,-125,50,-66);
  way["sport"="climbing"]["leisure"="sports_centre"](24,-125,50,-66);
  way["sport"="climbing"]["amenity"="gym"](24,-125,50,-66);
  way["sport"="climbing"]["leisure"="fitness_centre"](24,-125,50,-66);
  relation["sport"="climbing"]["leisure"="sports_centre"](24,-125,50,-66);
  relation["sport"="climbing"]["amenity"="gym"](24,-125,50,-66);
  node["leisure"="fitness_centre"]["name"~"{_CLIMBING_NAME_RE}"](24,-125,50,-66);
  way["leisure"="fitness_centre"]["name"~"{_CLIMBING_NAME_RE}"](24,-125,50,-66);
  relation["leisure"="fitness_centre"]["name"~"{_CLIMBING_NAME_RE}"](24,-125,50,-66);
  node["amenity"="gym"]["name"~"{_CLIMBING_NAME_RE}"](24,-125,50,-66);
  way["amenity"="gym"]["name"~"{_CLIMBING_NAME_RE}"](24,-125,50,-66);
  relation["amenity"="gym"]["name"~"{_CLIMBING_NAME_RE}"](24,-125,50,-66);
);
out center tags;
"""
MP_STATE_PATHS = [
    "/gyms/alabama", "/gyms/alaska", "/gyms/arizona", "/gyms/arkansas",
    "/gyms/california", "/gyms/colorado", "/gyms/connecticut", "/gyms/delaware",
    "/gyms/florida", "/gyms/georgia", "/gyms/hawaii", "/gyms/idaho",
    "/gyms/illinois", "/gyms/indiana", "/gyms/iowa", "/gyms/kansas",
    "/gyms/kentucky", "/gyms/louisiana", "/gyms/maine", "/gyms/maryland",
    "/gyms/massachusetts", "/gyms/michigan", "/gyms/minnesota", "/gyms/mississippi",
    "/gyms/missouri", "/gyms/montana", "/gyms/nebraska", "/gyms/nevada",
    "/gyms/new-hampshire", "/gyms/new-jersey", "/gyms/new-mexico", "/gyms/new-york",
    "/gyms/north-carolina", "/gyms/north-dakota", "/gyms/ohio", "/gyms/oklahoma",
    "/gyms/oregon", "/gyms/pennsylvania", "/gyms/rhode-island", "/gyms/south-carolina",
    "/gyms/south-dakota", "/gyms/tennessee", "/gyms/texas", "/gyms/utah",
    "/gyms/vermont", "/gyms/virginia", "/gyms/washington", "/gyms/washington-dc",
    "/gyms/west-virginia", "/gyms/wisconsin", "/gyms/wyoming",
]

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
ACAPT_URL = "https://acapt.org/maps/institutionprofiles.xml"

# Polite User-Agent required by Nominatim's terms of use
HEADERS = {"User-Agent": "map-scraper/1.0 (personal project, not for redistribution)"}

# Normalize 2-letter state abbreviations (used by ACAPT) to full names (used by Mountain Project)
_STATE_ABBREV = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas",
    "CA": "California", "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware",
    "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho",
    "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas",
    "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
    "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi",
    "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada",
    "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York",
    "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma",
    "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina",
    "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah",
    "VT": "Vermont", "VA": "Virginia", "WA": "Washington", "DC": "Washington Dc",
    "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming",
}


def _normalize_state(raw: str) -> str:
    """Convert a state abbreviation to its full name; pass through if already full."""
    return _STATE_ABBREV.get(raw.strip().upper(), raw.strip())

_GYM_HREF_RE = re.compile(r"mountainproject\.com/gym/\d+/")


def _geocode(city: str, state: str, cache: dict) -> tuple[float | None, float | None]:
    """Look up city+state coordinates via Nominatim, with in-session caching."""
    key = f"{city}, {state}"
    if key in cache:
        return cache[key]

    try:
        resp = requests.get(
            NOMINATIM_URL,
            params={"q": f"{city}, {state}, USA", "format": "json", "limit": 1, "countrycodes": "us"},
            headers=HEADERS,
            timeout=10,
        )
        resp.raise_for_status()
        results = resp.json()
        if results:
            lat, lon = float(results[0]["lat"]), float(results[0]["lon"])
        else:
            lat, lon = None, None
    except Exception:
        lat, lon = None, None

    cache[key] = (lat, lon)
    time.sleep(1.1)  # Nominatim rate limit: max 1 req/sec
    return lat, lon


def fetch_climbing_gyms() -> list[dict]:
    geo_cache: dict[str, tuple] = {}
    gyms: list[dict] = []

    for i, state_path in enumerate(MP_STATE_PATHS):
        state_name = state_path.split("/")[-1].replace("-", " ").title()
        print(f"  [{i + 1}/{len(MP_STATE_PATHS)}] {state_name} ...", end=" ", flush=True)

        try:
            resp = requests.get(MP_BASE + state_path, headers=HEADERS, timeout=20)
            resp.raise_for_status()
        except Exception as e:
            print(f"FAILED ({e})")
            time.sleep(0.5)
            continue

        soup = BeautifulSoup(resp.text, "html.parser")
        gym_links = [a for a in soup.find_all("a", href=True) if _GYM_HREF_RE.search(a["href"])]

        state_gyms = 0
        for link in gym_links:
            name = link.get_text(strip=True)
            if not name:
                continue

            # Each gym is in a <tr> with 3 <td>: name | stars | city
            row = link.find_parent("tr")
            city = ""
            if row:
                cells = row.find_all("td")
                if len(cells) >= 3:
                    city = cells[-1].get_text(strip=True)

            lat, lon = _geocode(city, state_name, geo_cache)
            if lat is None:
                continue

            gyms.append({
                "name": name,
                "lat": lat,
                "lon": lon,
                "city": city,
                "state": state_name,
                "url": link["href"] if link["href"].startswith("http") else MP_BASE + link["href"],
            })
            state_gyms += 1

        print(f"{state_gyms} gyms")
        time.sleep(0.5)  # polite crawl delay between state pages

    return gyms


def fetch_osm_climbing_gyms() -> list[dict]:
    """Fetch climbing gyms from OpenStreetMap via the Overpass API."""
    print("  Querying Overpass API...", end=" ", flush=True)
    resp = requests.post(OVERPASS_URL, data={"data": OVERPASS_QUERY}, headers=HEADERS, timeout=90)
    resp.raise_for_status()
    elements = resp.json().get("elements", [])
    print(f"{len(elements)} elements returned")

    gyms: list[dict] = []
    for el in elements:
        tags = el.get("tags", {})
        name = tags.get("name", "").strip()
        if not name:
            continue

        if el["type"] == "node":
            lat, lon = el.get("lat"), el.get("lon")
        else:
            center = el.get("center", {})
            lat, lon = center.get("lat"), center.get("lon")

        if lat is None or lon is None:
            continue

        state_raw = tags.get("addr:state", "")
        gyms.append({
            "name": name,
            "lat": lat,
            "lon": lon,
            "city": tags.get("addr:city", tags.get("addr:place", "")),
            "state": _normalize_state(state_raw) if state_raw else "",
            "website": tags.get("website", tags.get("contact:website", "")),
            "opening_hours": tags.get("opening_hours", ""),
            "osm_id": el["id"],
            "osm_type": el["type"],
        })

    return gyms


def fetch_dpt_programs() -> list[dict]:
    response = requests.get(ACAPT_URL, timeout=30)
    response.raise_for_status()

    # Use bytes to let ET handle the UTF-8 BOM properly
    root = ET.fromstring(response.content)

    # Detect the record element tag from the first child
    children = list(root)
    if not children:
        print(f"  Warning: XML root <{root.tag}> has no children")
        return []
    record_tag = children[0].tag

    def text(el, tag: str) -> str:
        node = el.find(tag)
        return node.text.strip() if node is not None and node.text else ""

    programs = []
    for item in root.iter(record_tag):
        lat_str = text(item, "lat")
        lon_str = text(item, "lon")
        try:
            lat = float(lat_str)
            lon = float(lon_str)
        except (ValueError, TypeError):
            continue

        programs.append(
            {
                "name": text(item, "title"),
                "organization": text(item, "organization"),
                "street": text(item, "address"),
                "city": text(item, "city"),
                "state": _normalize_state(text(item, "state")),
                "zip": text(item, "zip"),
                "phone": text(item, "phone"),
                "website": text(item, "contactlink"),
                "lat": lat,
                "lon": lon,
                "contact_name": text(item, "firstName"),
                "email": text(item, "email"),
            }
        )

    return programs
