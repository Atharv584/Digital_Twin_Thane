/**
 * Thane Digital Twin — App Logic
 * Fetches all real data from the FastAPI backend and renders it into the dashboard.
 */

// ── Weather code → label map ───────────────────────────────────────────
const WMO_MAP = {
    0:"Clear",1:"Mostly Clear",2:"Partly Cloudy",3:"Overcast",
    45:"Fog",48:"Icy Fog",51:"Light Drizzle",53:"Drizzle",55:"Heavy Drizzle",
    61:"Light Rain",63:"Rain",65:"Heavy Rain",
    71:"Light Snow",73:"Snow",75:"Heavy Snow",
    77:"Snow Grains",80:"Rain Showers",81:"Showers",82:"Heavy Showers",
    95:"Thunderstorm",96:"Hail Storm",99:"Severe Hail Storm"
};

// ── AQI classification ────────────────────────────────────────────────────────
function aqiMeta(val) {
    if (val === null || val === undefined) return { label:"N/A", cls:"" };
    if (val <= 50)  return { label:"Good",      cls:"aqi-good" };
    if (val <= 100) return { label:"Moderate",   cls:"aqi-moderate" };
    if (val <= 150) return { label:"Unhealthy",  cls:"aqi-unhealthy" };
    return                 { label:"Hazardous",  cls:"aqi-hazardous" };
}

// ── Helpers ───────────────────────────────────────────────────────────────────
const $ = id => document.getElementById(id);
const fmt = (v, dec=1, suffix='') => v !== null && v !== undefined ? `${(+v).toFixed(dec)}${suffix}` : '--';
const fmtInt = v => v !== null && v !== undefined ? Math.round(+v).toLocaleString() : '--';

// ── Init ──────────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    updateClock();
    setInterval(updateClock, 1000);

    initMap();
    fetchAll();
    setInterval(fetchAll, 5 * 60 * 1000);   // refresh every 5 min

    $('refresh-insights').addEventListener('click', () => {
        $('llm-insight').innerHTML = '<div class="loader-text">Regenerating insights...</div>';
        fetchInsights();
    });

    $('refresh-history').addEventListener('click', fetchHistory);

    // Map layer buttons
    document.querySelectorAll('[data-layer]').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('[data-layer]').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            loadLayer(btn.dataset.layer);
        });
    });
});

// ── Clock ─────────────────────────────────────────────────────────────────────
function updateClock() {
    const now = new Date();
    $('live-clock').textContent = now.toLocaleTimeString('en-IN', { hour12: false, timeZone:'Asia/Kolkata' });
    $('live-date').textContent  = now.toLocaleDateString('en-IN', { weekday:'short', year:'numeric', month:'short', day:'numeric', timeZone:'Asia/Kolkata' });
}

// ── Leaflet Map ───────────────────────────────────────────────────────────────
let map, currentLayerGroup;
const THANE = [19.1970, 72.9635];

function initMap() {
    map = L.map('map', { zoomControl: true }).setView(THANE, 12);

    // Light tile layer
    L.tileLayer('https://tiles.stadiamaps.com/tiles/alidade_smooth/{z}/{x}/{y}{r}.png', {
        maxZoom: 20,
        attribution: '&copy; <a href="https://stadiamaps.com/">Stadia Maps</a>, &copy; <a href="https://openmaptiles.org/">OpenMapTiles</a> &copy; <a href="http://openstreetmap.org">OpenStreetMap</a>'
    }).addTo(map);

    // City centre marker
    L.circle(THANE, { radius: 800, color:'#0284c7', fillColor:'#0284c7', fillOpacity:0.05, weight:1 }).addTo(map);
    L.circleMarker(THANE, { radius:6, color:'#0284c7', fillColor:'#0284c7', fillOpacity:1, weight:2 })
        .addTo(map)
        .bindPopup('<b>Thane City Centre</b><br>19.1970°N, 72.9635°E');

    currentLayerGroup = L.layerGroup().addTo(map);
    loadLayer('poi');
}

const LAYER_ICONS = {
    hospital:'•', school:'•', park:'•', transit_station:'•',
    fire_station:'•', police:'•', university:'•', place_of_worship:'•'
};

async function loadLayer(layer) {
    if (currentLayerGroup) currentLayerGroup.clearLayers();

    try {
        if (layer === 'poi') {
            const data = await (await fetch('/api/poi')).json();
            data.slice(0, 300).forEach(poi => {
                if (!poi.latitude || !poi.longitude) return;
                const icon = LAYER_ICONS[poi.category] || '•';
                L.marker([poi.latitude, poi.longitude], {
                    icon: L.divIcon({
                        html: `<span style="font-size:1.5rem;color:#0284c7;line-height:1;">${icon}</span>`,
                        className: '', iconAnchor:[6,12]
                    })
                }).bindPopup(`<b>${poi.name || poi.category}</b><br><small>${poi.category}</small>`)
                  .addTo(currentLayerGroup);
            });

        } else if (layer === 'earthquakes') {
            const data = await (await fetch('/api/earthquakes')).json();
            data.forEach(eq => {
                if (!eq.latitude || !eq.longitude) return;
                const r = Math.max(4, eq.magnitude * 4);
                const c = eq.magnitude >= 5 ? '#dc2626' : eq.magnitude >= 3 ? '#d97706' : '#0284c7';
                L.circleMarker([eq.latitude, eq.longitude], { radius:r, color:c, fillColor:c, fillOpacity:0.4, weight:1.5 })
                    .bindPopup(`<b>Magnitude ${eq.magnitude}</b><br>${eq.place}<br><small>Depth: ${eq.depth_km} km</small>`)
                    .addTo(currentLayerGroup);
            });

        } else if (layer === 'flood') {
            const data = await (await fetch('/api/flood/current')).json();
            if (data && data.river_discharge) {
                L.circle(THANE, { radius: 3000, color:'#2563eb', fillColor:'#2563eb', fillOpacity:0.12, weight:1.5 })
                    .bindPopup(`<b>River Discharge</b><br>${data.river_discharge.toFixed(1)} m³/s`)
                    .addTo(currentLayerGroup);
            }
        }
    } catch(e) { console.warn('Layer load error:', layer, e); }
}

// ── Master fetch ──────────────────────────────────────────────────────────────
async function fetchAll() {
    try {
        const [dashboard] = await Promise.all([
            fetch('/api/dashboard').then(r => r.json()),
        ]);
        renderWeather(dashboard.weather);
        renderAQI(dashboard.aqi);
        renderPop(dashboard.demographics, dashboard.economic, dashboard.exchange);
        renderSolar(dashboard.solar, dashboard.aqi?.uv_index, dashboard.weather?.cloud_cover);
        renderMarine(dashboard.marine);
    } catch(e) { console.error('Dashboard fetch error', e); }

    fetchNews();
    fetchInsights();
    fetchHistory();

    $('last-updated').textContent = 'Last updated: ' + new Date().toLocaleTimeString('en-IN', { hour12:false, timeZone:'Asia/Kolkata' });
}

// ── Weather Card ──────────────────────────────────────────────────────────────
function renderWeather(w) {
    if (!w) return;
    $('weather-temp').textContent    = w.temperature !== null ? (+w.temperature).toFixed(1) : '--';
    $('weather-hum').textContent     = fmt(w.humidity, 0, '%');
    $('weather-wind').textContent    = fmt(w.wind_speed, 0, ' km/h');
    $('weather-precip').textContent  = fmt(w.precipitation, 1, ' mm');
    $('weather-pressure').textContent= fmt(w.pressure, 0, ' hPa');
    $('weather-desc').textContent    = WMO_MAP[w.weather_code] || 'Conditions unknown';
    if (w.timestamp) {
        const ts = new Date(w.timestamp);
        $('weather-ts').textContent  = ts.toLocaleTimeString('en-IN', { hour:'2-digit', minute:'2-digit', timeZone:'Asia/Kolkata' });
    }
}

// ── AQI Card ──────────────────────────────────────────────────────────────────
function renderAQI(aqi) {
    if (!aqi) return;
    const v    = aqi.value !== null ? Math.round(aqi.value) : null;
    const meta = aqiMeta(v);

    $('aqi-val').textContent    = v !== null ? v : '--';
    $('aqi-status').textContent = aqi.dominant ? `Dominant: ${aqi.dominant}` : meta.label;

    const badge = $('aqi-badge');
    badge.textContent  = meta.label;
    badge.className    = `aqi-badge ${meta.cls}`;

    $('aqi-pm25').textContent = fmt(aqi.pm25, 1, ' µg');
    $('aqi-pm10').textContent = fmt(aqi.pm10, 1, ' µg');
    $('aqi-no2').textContent  = fmt(aqi.no2,  1, ' µg');
    $('aqi-o3').textContent   = fmt(aqi.o3,   1, ' µg');
}

// ── Population / Economic Card ────────────────────────────────────────────────
function renderPop(demo, econ, exch) {
    if (demo?.population) {
        const billions = (demo.population / 1e9).toFixed(2);
        $('pop-value').textContent = billions;
    }
    if (econ?.gdp_usd) {
        const t = econ.gdp_usd / 1e12;
        $('pop-gdp').textContent = `$${t.toFixed(2)}T`;
    }
    if (demo?.area_km2) {
        $('pop-area').textContent = `${(demo.area_km2/1000).toFixed(0)}K km²`;
    }
    if (exch?.usd_inr) {
        $('pop-inr').textContent = `₹${(+exch.usd_inr).toFixed(2)}`;
    }
    if (demo?.region) {
        $('pop-region').textContent = demo.region;
    }
}

// ── Solar / Daylight Card ─────────────────────────────────────────────────────
function renderSolar(solar, uv, clouds) {
    if (solar) {
        $('solar-sunrise').textContent = solar.sunrise ? fmtTime12(solar.sunrise) : '--';
        $('solar-sunset').textContent  = solar.sunset  ? fmtTime12(solar.sunset)  : '--';
        $('solar-daylen').textContent  = solar.day_length || '--';
        if (solar.date) $('solar-date').textContent = solar.date;

        // Solar progress bar: % of daylight elapsed
        if (solar.sunrise && solar.sunset) {
            const now  = Date.now();
            const rise = parseTimeToday(solar.sunrise);
            const set  = parseTimeToday(solar.sunset);
            const pct  = Math.min(100, Math.max(0, ((now - rise) / (set - rise)) * 100));
            $('solar-progress').style.width = pct + '%';
        }
    }
    $('solar-uv').textContent     = uv !== null && uv !== undefined ? (+uv).toFixed(1) : '--';
    $('weather-clouds').textContent = clouds !== null && clouds !== undefined ? `${Math.round(clouds)}%` : '--';
}

function fmtTime12(t) {
    // t might be "06:12:00 AM" or "06:12:00"
    if (!t) return '--';
    const parts = t.split(':');
    if (parts.length < 2) return t;
    const h = parseInt(parts[0]);
    const m = parts[1].padStart(2,'0');
    const ampm = h >= 12 ? 'PM' : 'AM';
    const h12  = h % 12 || 12;
    return `${h12}:${m} ${ampm}`;
}

function parseTimeToday(t) {
    if (!t) return Date.now();
    const parts = t.split(':');
    const d = new Date();
    d.setHours(+parts[0], +parts[1], 0, 0);
    return d.getTime();
}

// ── Marine ────────────────────────────────────────────────────────────────────
function renderMarine(marine) {
    if (!marine) return;
    $('marine-wave').textContent = marine.wave_height !== null ? `${(+marine.wave_height).toFixed(1)} m` : '--';
}

// ── News Feed ─────────────────────────────────────────────────────────────────
async function fetchNews() {
    try {
        const data = await (await fetch('/api/news/latest')).json();
        const list = $('news-list');
        list.innerHTML = '';

        if (data && data.length > 0) {
            data.forEach(item => {
                const li = document.createElement('li');
                const date = item.published_at ? new Date(item.published_at).toLocaleDateString('en-IN') : '';
                li.innerHTML = `
                    <div class="news-title"><a href="${item.url}" target="_blank" rel="noopener">${item.title}</a></div>
                    <div class="news-meta">${item.source_name || 'Unknown'} · ${date}</div>
                `;
                list.appendChild(li);
            });
        } else {
            list.innerHTML = '<li style="color:var(--text-dim);font-size:0.85rem">No recent news available.</li>';
        }
    } catch(e) { console.warn('News fetch error', e); }
}

// ── AI Insights ───────────────────────────────────────────────────────────────
async function fetchInsights() {
    try {
        const data = await (await fetch('/api/analyze', { method:'POST' })).json();
        const container = $('llm-insight');

        if (data.result && !data.result.includes('disabled') && !data.result.includes('Failed')) {
            container.innerHTML = data.result
                .split('\n\n')
                .filter(p => p.trim())
                .map(p => `<p>${p.replace(/\n/g, '<br>')}</p>`)
                .join('');
        } else {
            container.innerHTML = `<p style="color:var(--text-dim)">Add <code style="color:var(--cyan)">GROQ_API_KEY</code> to your <code>.env</code> to enable AI insights.</p>`;
        }
    } catch(e) {
        $('llm-insight').innerHTML = '<p style="color:var(--text-dim)">Failed to generate insights.</p>';
    }
}

// ── Historical Table ──────────────────────────────────────────────────────────
async function fetchHistory() {
    try {
        const data = await (await fetch('/api/historical-table')).json();
        const tbody = $('history-table-body');
        tbody.innerHTML = '';

        if (!data || data.length === 0) {
            tbody.innerHTML = '<tr><td colspan="14" class="table-placeholder">No historical data yet. Trigger a fetch first.</td></tr>';
            return;
        }

        data.forEach(row => {
            const aqi  = row.aqi !== null ? Math.round(row.aqi) : null;
            const meta = aqiMeta(aqi);
            const tr   = document.createElement('tr');
            tr.innerHTML = `
                <td>${row.date || '--'}</td>
                <td>${fmt(row.avg_temp, 1)}</td>
                <td>${fmt(row.humidity, 0)}</td>
                <td>${fmt(row.wind_speed, 0)}</td>
                <td>${fmt(row.precipitation, 1)}</td>
                <td>${fmt(row.pressure, 0)}</td>
                <td class="${meta.cls ? 'aqi-cell-' + meta.cls.replace('aqi-','') : ''}">${aqi !== null ? aqi : '--'}</td>
                <td>${fmt(row.pm25, 1)}</td>
                <td>${fmt(row.pm10, 1)}</td>
                <td>${fmt(row.no2, 1)}</td>
                <td>${fmt(row.so2, 1)}</td>
                <td>${fmt(row.o3, 1)}</td>
                <td>${fmt(row.co, 1)}</td>
                <td>${fmt(row.uv_index, 1)}</td>
            `;
            tbody.appendChild(tr);
        });
    } catch(e) {
        console.error('History fetch error', e);
        $('history-table-body').innerHTML = '<tr><td colspan="14" class="table-placeholder">Error loading data.</td></tr>';
    }
}
