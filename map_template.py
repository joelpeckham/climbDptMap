MAP_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Climbing Gyms &amp; DPT Programs</title>
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; }}
    html, body {{ margin: 0; padding: 0; height: 100%; font-family: system-ui, sans-serif; }}
    body {{ display: flex; }}

    #sidebar {{
      width: 270px;
      min-width: 270px;
      padding: 16px;
      background: #f5f5f5;
      border-right: 1px solid #ddd;
      overflow-y: auto;
      display: flex;
      flex-direction: column;
      gap: 14px;
    }}
    #map {{ flex: 1; }}

    h1 {{ margin: 0; font-size: 1rem; font-weight: 700; line-height: 1.3; }}

    .control-group {{ display: flex; flex-direction: column; gap: 6px; }}
    .control-group > label {{ font-size: 0.8rem; font-weight: 600; color: #555; text-transform: uppercase; letter-spacing: .04em; }}

    .layer-toggle {{
      display: flex;
      align-items: center;
      gap: 8px;
      cursor: pointer;
      font-size: 0.9rem;
      padding: 4px 0;
    }}
    .layer-toggle input {{ cursor: pointer; accent-color: #333; }}

    .dot {{
      width: 13px; height: 13px;
      border-radius: 50%;
      border: 2px solid #fff;
      box-shadow: 0 1px 3px rgba(0,0,0,.35);
      flex-shrink: 0;
    }}
    .dot-blue  {{ background: #2563eb; }}
    .dot-red   {{ background: #dc2626; }}
    .dot-green {{ background: #16a34a; }}

    select, input[type="text"] {{
      width: 100%;
      padding: 6px 8px;
      border: 1px solid #ccc;
      border-radius: 5px;
      font-size: 0.88rem;
      background: #fff;
    }}
    select:focus, input[type="text"]:focus {{
      outline: 2px solid #2563eb;
      outline-offset: 1px;
    }}

    #result-count {{
      font-size: 0.8rem;
      color: #666;
      padding: 4px 0;
    }}

    .legend {{
      font-size: 0.78rem;
      color: #777;
      border-top: 1px solid #ddd;
      padding-top: 10px;
      line-height: 1.6;
    }}
  </style>
</head>
<body>
  <div id="sidebar">
    <h1>Climbing Gyms &amp;<br>DPT Programs</h1>

    <div class="control-group">
      <label>Layers</label>
      <span class="layer-toggle">
        <input type="checkbox" id="toggle-gyms" checked>
        <span class="dot dot-blue"></span>
        Climbing Gyms
      </span>
      <span class="layer-toggle">
        <input type="checkbox" id="toggle-dpt" checked>
        <span class="dot dot-red"></span>
        DPT Programs
      </span>
      <span class="layer-toggle">
        <input type="checkbox" id="toggle-osm" checked>
        <span class="dot dot-green"></span>
        OSM Gyms
      </span>
    </div>

    <div class="control-group">
      <label for="state-filter">Filter by State</label>
      <select id="state-filter">
        <option value="">All States</option>
      </select>
    </div>

    <div class="control-group">
      <label for="search-box">Search by Name</label>
      <input type="text" id="search-box" placeholder="e.g. Movement, NYU…">
    </div>

    <div id="result-count"></div>

    <div class="legend">
      Data: <a href="https://www.mountainproject.com/gyms" target="_blank">Mountain Project</a>,
      <a href="https://acapt.org/maps/institution-map.html" target="_blank">ACAPT</a>
      &amp; <a href="https://www.openstreetmap.org" target="_blank">OpenStreetMap</a>.
    </div>
  </div>

  <div id="map"></div>

  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>

  <script>
    const ALL_DATA = {data_json};

    // --- Map init ---
    const map = L.map('map').setView([39.5, -98.35], 5);
    L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
      maxZoom: 19
    }}).addTo(map);

    // --- Marker icons ---
    function makeIcon(color) {{
      return L.divIcon({{
        className: '',
        html: `<div style="width:13px;height:13px;border-radius:50%;background:${{color}};border:2px solid #fff;box-shadow:0 1px 3px rgba(0,0,0,.4)"></div>`,
        iconSize: [13, 13],
        iconAnchor: [6, 6],
        popupAnchor: [0, -8]
      }});
    }}
    const GYM_ICON = makeIcon('#2563eb');
    const DPT_ICON = makeIcon('#dc2626');
    const OSM_ICON = makeIcon('#16a34a');

    // --- Popup builder ---
    function buildPopup(d) {{
      const addrParts = [d.street, d.city, d.state, d.zip].filter(Boolean);
      const addr = addrParts.length ? `<div style="color:#555;font-size:.85em">${{addrParts.join(', ')}}</div>` : '';
      const phone = d.phone ? `<div style="font-size:.85em">&#128222; ${{d.phone}}</div>` : '';
      const hours = d.opening_hours ? `<div style="font-size:.8em;color:#666">&#128337; ${{d.opening_hours}}</div>` : '';
      const contact = d.contact_name ? `<div style="font-size:.85em">&#128100; ${{d.contact_name}}</div>` : '';
      const email = d.email ? `<div style="font-size:.85em">&#9993; <a href="mailto:${{d.email}}">${{d.email}}</a></div>` : '';
      const site = d.website
        ? `<div style="margin-top:4px"><a href="${{d.website.startsWith('http') ? d.website : 'https://' + d.website}}" target="_blank" rel="noopener">Website &#8599;</a></div>`
        : '';
      const mpLink = d.url
        ? `<div style="margin-top:2px"><a href="${{d.url}}" target="_blank" rel="noopener">Mountain Project &#8599;</a></div>`
        : '';
      const typeLabel = d.type === 'climbing_gym'
        ? '<span style="font-size:.75em;background:#dbeafe;color:#1d4ed8;padding:1px 6px;border-radius:3px">Climbing Gym</span>'
        : d.type === 'osm_gym'
        ? '<span style="font-size:.75em;background:#dcfce7;color:#166534;padding:1px 6px;border-radius:3px">OSM Gym</span>'
        : '<span style="font-size:.75em;background:#fee2e2;color:#991b1b;padding:1px 6px;border-radius:3px">DPT Program</span>';

      return `<div style="min-width:180px;max-width:260px">
        <div style="font-weight:600;margin-bottom:4px">${{d.name}}</div>
        ${{typeLabel}}
        ${{addr}}${{phone}}${{hours}}${{contact}}${{email}}${{site}}${{mpLink}}
      </div>`;
    }}

    // --- Build all markers once ---
    const allMarkers = ALL_DATA.map(d => {{
      const icon = d.type === 'climbing_gym' ? GYM_ICON
                 : d.type === 'osm_gym'      ? OSM_ICON
                 : DPT_ICON;
      const m = L.marker([d.lat, d.lon], {{ icon }}).bindPopup(buildPopup(d));
      m._data = d;
      return m;
    }});

    // Layer groups
    const gymLayer = L.layerGroup().addTo(map);
    const dptLayer = L.layerGroup().addTo(map);
    const osmLayer = L.layerGroup().addTo(map);

    // --- Populate state dropdown ---
    const states = [...new Set(ALL_DATA.map(d => d.state).filter(Boolean))].sort();
    const stateSelect = document.getElementById('state-filter');
    states.forEach(s => {{
      const opt = document.createElement('option');
      opt.value = s;
      opt.textContent = s;
      stateSelect.appendChild(opt);
    }});

    // --- Filter logic ---
    function applyFilters() {{
      gymLayer.clearLayers();
      dptLayer.clearLayers();
      osmLayer.clearLayers();

      const showGyms = document.getElementById('toggle-gyms').checked;
      const showDpt  = document.getElementById('toggle-dpt').checked;
      const showOsm  = document.getElementById('toggle-osm').checked;
      const state    = stateSelect.value;
      const query    = document.getElementById('search-box').value.toLowerCase().trim();

      let count = 0;
      allMarkers.forEach(m => {{
        const d = m._data;
        if (state && d.state !== state) return;
        if (query && !d.name.toLowerCase().includes(query)) return;

        if (d.type === 'climbing_gym' && showGyms) {{
          gymLayer.addLayer(m);
          count++;
        }} else if (d.type === 'dpt_program' && showDpt) {{
          dptLayer.addLayer(m);
          count++;
        }} else if (d.type === 'osm_gym' && showOsm) {{
          osmLayer.addLayer(m);
          count++;
        }}
      }});

      const total = allMarkers.length;
      document.getElementById('result-count').textContent =
        `${{count}} of ${{total}} locations shown`;
    }}

    // Wire remaining controls
    document.getElementById('toggle-gyms').addEventListener('change', applyFilters);
    document.getElementById('toggle-dpt').addEventListener('change', applyFilters);
    document.getElementById('toggle-osm').addEventListener('change', applyFilters);
    stateSelect.addEventListener('change', applyFilters);
    document.getElementById('search-box').addEventListener('input', applyFilters);

    applyFilters();
  </script>
</body>
</html>
"""
