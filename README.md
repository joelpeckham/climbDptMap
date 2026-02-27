# climbDptMap

Interactive map of climbing gyms (Mountain Project + OpenStreetMap) and DPT programs (ACAPT) across the continental US.

**Live map:** https://joelpeckham.github.io/climbDptMap/

## Usage

Run `main.py` to re-scrape all sources and regenerate `index.html`:

```bash
uv run main.py
```

Data is cached in `data/` — delete individual JSON files to force re-fetching.
