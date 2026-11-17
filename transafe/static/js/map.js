// Map backend: Google Maps when GOOGLE_MAPS_API_KEY is set, otherwise Leaflet + OpenStreetMap.
// Both return the same object: { kind, draw(spots) } where each spot is
// { lat, lng, count, color, strong, html }.
const BENGALURU = { lat: 12.9716, lng: 77.5946 };

const DARK_STYLE = [
  { elementType: 'geometry', stylers: [{ color: '#1b2330' }] },
  { elementType: 'labels.text.fill', stylers: [{ color: '#8b97a8' }] },
  { elementType: 'labels.text.stroke', stylers: [{ color: '#151b24' }] },
  { featureType: 'road', elementType: 'geometry', stylers: [{ color: '#2b3546' }] },
  { featureType: 'road.highway', elementType: 'geometry', stylers: [{ color: '#3a4760' }] },
  { featureType: 'water', elementType: 'geometry', stylers: [{ color: '#0f1620' }] },
  { featureType: 'poi', stylers: [{ visibility: 'off' }] },
  { featureType: 'transit', elementType: 'geometry', stylers: [{ color: '#3b6ea8' }] },
];

export async function createMap(el, mapsKey) {
  if (mapsKey) {
    try { return await googleMap(el, mapsKey); } catch (e) { console.warn('Google Maps unavailable, using Leaflet:', e.message); }
  }
  return leafletMap(el);
}

function loadGoogle(key) {
  return new Promise((resolve, reject) => {
    if (window.google && window.google.maps) return resolve();
    window.gm_authFailure = () => reject(new Error('Google rejected the API key (check restrictions / billing)'));
    window.__gmapsReady = resolve;
    const s = document.createElement('script');
    s.src = `https://maps.googleapis.com/maps/api/js?key=${encodeURIComponent(key)}&callback=__gmapsReady&loading=async&v=weekly`;
    s.async = true;
    s.onerror = () => reject(new Error('could not load the Google Maps script'));
    document.head.appendChild(s);
    setTimeout(() => reject(new Error('Google Maps timed out')), 10000);
  });
}

async function googleMap(el, key) {
  await loadGoogle(key);
  const map = new google.maps.Map(el, {
    center: BENGALURU, zoom: 11, styles: DARK_STYLE, clickableIcons: false,
    mapTypeControl: false, streetViewControl: false, fullscreenControl: true,
  });
  // Google's transit layer draws the metro lines and bus/rail stops over Bengaluru
  const transit = new google.maps.TransitLayer();
  transit.setMap(map);
  const toggle = document.getElementById('mapTransitWrap');
  if (toggle) {
    toggle.hidden = false;
    document.getElementById('mapTransit').onchange = (e) => transit.setMap(e.target.checked ? map : null);
  }
  const info = new google.maps.InfoWindow({ disableAutoPan: true });
  let circles = [];
  return {
    kind: 'google',
    draw(spots) {
      circles.forEach((c) => c.setMap(null));
      circles = spots.map((s) => {
        const c = new google.maps.Circle({
          map, center: { lat: s.lat, lng: s.lng }, radius: 500 + Math.sqrt(s.count) * 230,
          strokeColor: s.strong ? '#ffffff' : s.color, strokeWeight: s.strong ? 2 : 1, strokeOpacity: 0.9,
          fillColor: s.color, fillOpacity: 0.5,
        });
        c.addListener('mouseover', () => { info.setContent(`<div style="color:#111">${s.html}</div>`); info.setPosition(c.getCenter()); info.open(map); });
        c.addListener('mouseout', () => info.close());
        return c;
      });
    },
  };
}

function leafletMap(el) {
  const map = L.map(el, { zoomControl: true, attributionControl: true }).setView([BENGALURU.lat, BENGALURU.lng], 11);
  L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 18, attribution: '© OpenStreetMap contributors' }).addTo(map);
  const layer = L.layerGroup().addTo(map);
  return {
    kind: 'leaflet',
    draw(spots) {
      layer.clearLayers();
      for (const s of spots) {
        L.circleMarker([s.lat, s.lng], {
          radius: 7 + Math.sqrt(s.count) * 3.2, color: s.strong ? '#fff' : s.color, weight: s.strong ? 2 : 1,
          fillColor: s.color, fillOpacity: 0.55,
        }).addTo(layer).bindTooltip(s.html);
      }
    },
  };
}
