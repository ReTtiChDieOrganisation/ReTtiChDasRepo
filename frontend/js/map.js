/* ReTtiCh Map Module */

const RettichMap = (function () {
    let map = null;
    let routeLayers = [];
    let markerLayers = [];
    let riderMarkers = {};
    let currentBounds = null;

    const TILE_URL = 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png';
    const TILE_ATTR = '&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a> &copy; <a href="https://carto.com/">CARTO</a>';

    function init() {
        map = L.map('map', {
            center: [50.11, 8.68],
            zoom: 13,
            zoomControl: true,
            attributionControl: true,
        });

        L.tileLayer(TILE_URL, {
            attribution: TILE_ATTR,
            subdomains: 'abcd',
            maxZoom: 19,
        }).addTo(map);

        // Fix tiles on resize
        window.addEventListener('resize', () => {
            setTimeout(() => map.invalidateSize(), 100);
        });
    }

    function clearAll() {
        routeLayers.forEach(l => map.removeLayer(l));
        markerLayers.forEach(l => map.removeLayer(l));
        Object.values(riderMarkers).forEach(m => map.removeLayer(m));
        routeLayers = [];
        markerLayers = [];
        riderMarkers = {};
        currentBounds = null;
    }

    function drawRoute(latlngs, color, weight = 3, opacity = 0.7, dashArray = null) {
        const opts = { color, weight, opacity, smoothFactor: 1 };
        if (dashArray) opts.dashArray = dashArray;

        // Background glow
        const glow = L.polyline(latlngs, {
            color: color,
            weight: weight + 4,
            opacity: opacity * 0.2,
            smoothFactor: 1,
        }).addTo(map);
        routeLayers.push(glow);

        const line = L.polyline(latlngs, opts).addTo(map);
        routeLayers.push(line);
        return line;
    }

    function drawRoutes(activitiesData, riders) {
        const allBounds = [];

        activitiesData.forEach(act => {
            if (!act.streams || !act.streams.latlng) return;
            const latlngs = act.streams.latlng;
            if (latlngs.length < 2) return;

            const rider = riders[act.rider_name] || {};
            const color = getRiderColor(rider);
            drawRoute(latlngs, color, 3, 0.65);

            allBounds.push(...latlngs);
        });

        if (allBounds.length > 0) {
            currentBounds = L.latLngBounds(allBounds);
            map.fitBounds(currentBounds, { padding: [40, 40] });
        }
    }

    function setRiderPosition(riderName, latlng, rider) {
        if (!latlng) return;

        if (riderMarkers[riderName]) {
            riderMarkers[riderName].setLatLng(latlng);
        } else {
            const icon = createRiderMarkerIcon(rider, 40);
            const marker = L.marker(latlng, { icon, zIndexOffset: 1000 }).addTo(map);


            riderMarkers[riderName] = marker;
            markerLayers.push(marker);
        }
    }

    function hideRiderMarker(riderName) {
        if (riderMarkers[riderName]) {
            map.removeLayer(riderMarkers[riderName]);
            delete riderMarkers[riderName];
        }
    }

    function clearRiderMarkers() {
        Object.keys(riderMarkers).forEach(name => {
            map.removeLayer(riderMarkers[name]);
        });
        riderMarkers = {};
    }

    function fitBounds(bounds, padding = [40, 40]) {
        if (bounds) {
            map.fitBounds(bounds, { padding });
        }
    }

    function fitToCurrentBounds() {
        if (currentBounds) {
            map.fitBounds(currentBounds, { padding: [40, 40] });
        }
    }

    function drawSegmentHighlight(latlngs, color = '#ffcc00') {
        const line = L.polyline(latlngs, {
            color: color,
            weight: 5,
            opacity: 0.9,
            dashArray: '8 6',
        }).addTo(map);
        routeLayers.push(line);

        if (latlngs.length > 0) {
            // Start/end markers
            const startIcon = L.divIcon({
                className: '',
                html: `<div style="width:10px;height:10px;background:#34d399;border:2px solid #fff;border-radius:50%;box-shadow:0 0 4px #34d399;"></div>`,
                iconSize: [10, 10],
                iconAnchor: [5, 5],
            });
            const endIcon = L.divIcon({
                className: '',
                html: `<div style="width:10px;height:10px;background:#f87171;border:2px solid #fff;border-radius:50%;box-shadow:0 0 4px #f87171;"></div>`,
                iconSize: [10, 10],
                iconAnchor: [5, 5],
            });

            const startM = L.marker(latlngs[0], { icon: startIcon }).addTo(map);
            const endM = L.marker(latlngs[latlngs.length - 1], { icon: endIcon }).addTo(map);
            markerLayers.push(startM, endM);
        }

        return line;
    }

    function getMap() { return map; }

    return {
        init,
        clearAll,
        drawRoute,
        drawRoutes,
        setRiderPosition,
        hideRiderMarker,
        clearRiderMarkers,
        fitBounds,
        fitToCurrentBounds,
        drawSegmentHighlight,
        getMap,
    };
})();
