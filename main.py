import json
import os
import re

import scrape
from map_template import MAP_TEMPLATE

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
GYMS_FILE = os.path.join(DATA_DIR, "climbing_gyms.json")
OSM_GYMS_FILE = os.path.join(DATA_DIR, "osm_gyms_raw.json")
DPT_FILE = os.path.join(DATA_DIR, "dpt_programs.json")
COMBINED_FILE = os.path.join(DATA_DIR, "combined.json")
MAP_FILE = os.path.join(os.path.dirname(__file__), "map.html")

_DEDUP_STOP_WORDS = {"climbing", "gym", "center", "centre", "fitness", "rock", "the", "of", "and", "wall", "bouldering"}


def _name_tokens(name: str) -> set[str]:
    words = re.sub(r"[^\w\s]", " ", name.lower()).split()
    return {w for w in words if w not in _DEDUP_STOP_WORDS and len(w) > 2}


def save_json(path: str, data: list) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"  Saved {len(data)} records -> {path}")


def deduplicate_osm_gyms(osm_gyms: list[dict], mp_gyms: list[dict]) -> list[dict]:
    """Return OSM gyms that have no name-match in the Mountain Project list."""
    # Group MP gyms by state for faster lookup
    mp_by_state: dict[str, list[set]] = {}
    mp_all_tokens: list[set] = []
    for g in mp_gyms:
        tokens = _name_tokens(g["name"])
        if not tokens:
            continue
        state = g.get("state", "")
        mp_by_state.setdefault(state, []).append(tokens)
        mp_all_tokens.append(tokens)

    unique: list[dict] = []
    for osm in osm_gyms:
        osm_tokens = _name_tokens(osm["name"])
        if not osm_tokens:
            unique.append(osm)
            continue

        osm_state = osm.get("state", "")
        # If state is known, only match against same-state MP gyms (avoids cross-state false positives).
        # If state is unknown, check all MP gyms but apply the stricter 2-token minimum.
        candidates = mp_by_state.get(osm_state, []) if osm_state else mp_all_tokens

        is_dup = False
        for mp_tokens in candidates:
            if not mp_tokens:
                continue
            smaller = osm_tokens if len(osm_tokens) <= len(mp_tokens) else mp_tokens
            # Require at least 2 significant tokens to match — single-token names are too generic.
            if len(smaller) >= 2 and (osm_tokens <= mp_tokens or mp_tokens <= osm_tokens):
                is_dup = True
                break

        if not is_dup:
            unique.append(osm)

    return unique


def load_or_fetch_gyms() -> list[dict]:
    if os.path.exists(GYMS_FILE):
        print(f"Loading cached climbing gyms from {GYMS_FILE} ...")
        with open(GYMS_FILE, encoding="utf-8") as f:
            gyms = json.load(f)
        print(f"  Loaded {len(gyms)} records (delete {GYMS_FILE} to re-scrape)")
        return gyms
    print("Fetching climbing gyms from Mountain Project...")
    gyms = scrape.fetch_climbing_gyms()
    save_json(GYMS_FILE, gyms)
    return gyms


def load_or_fetch_osm_gyms() -> list[dict]:
    if os.path.exists(OSM_GYMS_FILE):
        print(f"Loading cached OSM gyms from {OSM_GYMS_FILE} ...")
        with open(OSM_GYMS_FILE, encoding="utf-8") as f:
            gyms = json.load(f)
        print(f"  Loaded {len(gyms)} records (delete {OSM_GYMS_FILE} to re-fetch)")
        return gyms
    print("Fetching climbing gyms from OpenStreetMap...")
    gyms = scrape.fetch_osm_climbing_gyms()
    save_json(OSM_GYMS_FILE, gyms)
    return gyms


def main() -> None:
    os.makedirs(DATA_DIR, exist_ok=True)

    gyms = load_or_fetch_gyms()

    print("Fetching DPT programs from ACAPT...")
    dpt = scrape.fetch_dpt_programs()
    save_json(DPT_FILE, dpt)

    osm_raw = load_or_fetch_osm_gyms()
    print("De-duplicating OSM gyms against Mountain Project data...")
    osm_new = deduplicate_osm_gyms(osm_raw, gyms)
    print(f"  {len(osm_raw)} OSM gyms fetched, {len(osm_new)} unique after de-duplication")

    print("Combining datasets...")
    combined = (
        [{**g, "type": "climbing_gym"} for g in gyms]
        + [{**d, "type": "dpt_program"} for d in dpt]
        + [{**o, "type": "osm_gym"} for o in osm_new]
    )
    save_json(COMBINED_FILE, combined)

    print("Generating map.html...")
    data_json = json.dumps(combined, ensure_ascii=False)
    html = MAP_TEMPLATE.format(data_json=data_json)
    with open(MAP_FILE, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"  Saved map -> {MAP_FILE}")

    print(f"\nDone! {len(gyms)} MP gyms, {len(osm_new)} OSM-only gyms, {len(dpt)} DPT programs.")
    print("Open map.html in your browser to explore the data.")


if __name__ == "__main__":
    main()
