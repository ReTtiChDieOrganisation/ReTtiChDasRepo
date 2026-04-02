/* ReTtiCh App — Main application controller */

const RettichApp = (function () {
    let riders = {};
    let groups = [];
    let activitiesIndex = [];
    let sharedSegments = {};
    let siteConfig = {};

    let selectedGroupId = null;
    let selectedDate = null;
    let currentMode = 'time-sync'; // 'time-sync' | 'segment-compare'
    let groupActivitiesCache = {}; // groupId -> [activity data]

    const DATA_BASE = './data/';

    // --- Initialization ---

    async function init() {
        // Check password gate
        try {
            siteConfig = await fetchJSON(DATA_BASE + 'site_config.json');
        } catch {
            siteConfig = { password_hash: 0 };
        }

        if (siteConfig.password_hash && siteConfig.password_hash !== 0) {
            showPasswordGate();
        } else {
            await startApp();
        }
    }

    function showPasswordGate() {
        const gate = document.getElementById('password-gate');
        gate.classList.remove('hidden');

        const input = document.getElementById('gate-password');
        const btn = document.getElementById('gate-submit');

        const tryPassword = () => {
            const hash = simpleHash(input.value);
            if (hash === siteConfig.password_hash) {
                gate.classList.add('hidden');
                startApp();
            } else {
                input.style.borderColor = 'var(--danger)';
                input.value = '';
                setTimeout(() => { input.style.borderColor = ''; }, 1000);
            }
        };

        btn.addEventListener('click', tryPassword);
        input.addEventListener('keydown', e => { if (e.key === 'Enter') tryPassword(); });
    }

    function simpleHash(s) {
        let h = 0;
        for (let i = 0; i < s.length; i++) {
            h = ((h << 5) - h + s.charCodeAt(i)) & 0xFFFFFFFF;
        }
        return h >>> 0; // unsigned
    }

    async function startApp() {
        // Load data
        try {
            [riders, groups, activitiesIndex] = await Promise.all([
                fetchJSON(DATA_BASE + 'riders.json'),
                fetchJSON(DATA_BASE + 'groups.json'),
                fetchJSON(DATA_BASE + 'activities_index.json'),
            ]);
        } catch (e) {
            console.error('Failed to load data:', e);
            document.getElementById('group-list').innerHTML =
                '<div class="loading" style="color:var(--danger)">Failed to load data. Run build.py first.</div>';
            return;
        }

        try {
            sharedSegments = await fetchJSON(DATA_BASE + 'shared_segments.json');
        } catch {
            sharedSegments = {};
        }

        // Init modules
        RettichMap.init();
        RettichTimeline.init();
        RettichSegments.init();
        RettichStats.init();

        // Render UI
        renderRiders();
        renderDateSelector();
        setupModeToggle();

        // Fix map size after layout
        setTimeout(() => RettichMap.getMap().invalidateSize(), 200);

        // Auto-select newest date that has data
        const dates = getUniqueDates();
        if (dates.length > 0) {
            selectDate(dates[0]); // dates are sorted newest first
        }
    }

    // --- Data fetching ---

    async function fetchJSON(url) {
        // If build.py embedded the data into the HTML, use that directly
        if (window.RETTICH_DATA) {
            if (url.includes('riders.json')) return window.RETTICH_DATA.riders;
            if (url.includes('groups.json')) return window.RETTICH_DATA.groups;
            if (url.includes('activities_index.json')) return window.RETTICH_DATA.activities_index;
            if (url.includes('shared_segments.json')) return window.RETTICH_DATA.shared_segments;
            if (url.includes('site_config.json')) return window.RETTICH_DATA.site_config;
            const match = url.match(/activities\/(\d+)\.json/);
            if (match && window.RETTICH_DATA.activities[match[1]]) {
                return window.RETTICH_DATA.activities[match[1]];
            }
        }
        // Fallback: fetch from server (for Raspberry Pi / http server mode)
        const resp = await fetch(url);
        if (!resp.ok) throw new Error(`HTTP ${resp.status}: ${url}`);
        return resp.json();
    }

    async function loadGroupActivities(groupId) {
        if (groupActivitiesCache[groupId]) return groupActivitiesCache[groupId];

        const group = groups.find(g => g.id === groupId);
        if (!group) return [];

        const promises = group.activity_ids.map(aid =>
            fetchJSON(DATA_BASE + `activities/${aid}.json`).catch(() => null)
        );
        const results = await Promise.all(promises);
        const activities = results.filter(Boolean);

        groupActivitiesCache[groupId] = activities;
        return activities;
    }

    // --- Group selection ---

    async function selectGroup(groupId) {
        selectedGroupId = groupId;

        // Update UI
        document.querySelectorAll('.group-card').forEach(el => {
            el.classList.toggle('active', parseInt(el.dataset.groupId) === groupId);
        });

        // Show mode toggle
        document.getElementById('mode-toggle').style.display = 'flex';

        // Load activities
        const activities = await loadGroupActivities(groupId);
        if (activities.length === 0) return;

        // Show stats
        RettichStats.computeAndDisplay(activities, riders);

        // Load segments for segment mode
        const group = groups.find(g => g.id === groupId);
        const segments = sharedSegments[String(groupId)] || [];

        // Setup current mode
        applyMode(activities, segments);
    }

    function applyMode(activities, segments) {
        RettichMap.clearAll();
        RettichTimeline.destroy();
        RettichSegments.destroy();

        if (!activities) return;

        if (currentMode === 'time-sync') {
            document.getElementById('playback-controls').style.display = 'block';
            document.getElementById('segment-panel').style.display = 'none';

            // Draw all routes
            RettichMap.drawRoutes(activities, riders);

            // Setup timeline
            RettichTimeline.load(activities, riders);
        } else {
            document.getElementById('playback-controls').style.display = 'none';
            document.getElementById('segment-panel').style.display = 'block';

            // Draw all routes first
            RettichMap.drawRoutes(activities, riders);

            // Setup segment comparison
            RettichSegments.load(activities, riders, segments);
        }
    }

    function refreshMap() {
        // Re-apply mode to redraw map without segment selection
        if (!selectedGroupId) return;
        loadGroupActivities(selectedGroupId).then(activities => {
            const group = groups.find(g => g.id === selectedGroupId);
            const segments = sharedSegments[String(selectedGroupId)] || [];
            RettichMap.clearAll();
            RettichMap.drawRoutes(activities, riders);
        });
    }

    // --- UI Rendering ---

    function renderRiders() {
        const el = document.getElementById('riders-list');
        let html = '';
        Object.values(riders).forEach(r => {
            const color = getRiderColor(r);
            html += `<div class="rider-row">
                <div class="rider-color" style="background:${color};"></div>
                <span class="rider-name">${r.name}</span>
                <span class="rider-frame">${r.frame}</span>
            </div>`;
        });
        el.innerHTML = html;
    }

    function getUniqueDates() {
        const dateSet = new Set(groups.map(g => g.date));
        return [...dateSet].sort((a, b) => b.localeCompare(a)); // newest first
    }

    function renderDateSelector() {
        const el = document.getElementById('date-select');
        const dates = getUniqueDates();

        el.innerHTML = '';
        dates.forEach(d => {
            const opt = document.createElement('option');
            opt.value = d;
            // Format nicely: "Mon, 19 May 2025"
            const dt = new Date(d + 'T12:00:00');
            opt.textContent = dt.toLocaleDateString('en-GB', {
                weekday: 'short', day: 'numeric', month: 'short', year: 'numeric'
            });
            el.appendChild(opt);
        });

        el.addEventListener('change', () => selectDate(el.value));
    }

    function selectDate(date) {
        selectedDate = date;
        document.getElementById('date-select').value = date;
        renderGroupsForDate(date);
    }

    function renderGroupsForDate(date) {
        const el = document.getElementById('group-list');
        const dateGroups = groups.filter(g => g.date === date);

        if (dateGroups.length === 0) {
            el.innerHTML = '<div style="padding:12px;color:var(--text-muted);font-size:13px;">No groups for this date</div>';
            return;
        }

        // Sort: segment groups first (by shared_segment_count desc), then daily
        dateGroups.sort((a, b) => {
            if (a.type !== b.type) return a.type === 'segment' ? -1 : 1;
            return b.shared_segment_count - a.shared_segment_count;
        });

        let html = '';
        dateGroups.forEach(g => {
            const isActive = g.id === selectedGroupId ? 'active' : '';
            const badgeClass = g.type === 'segment' ? 'segment' : 'daily';
            const badgeText = g.type === 'segment'
                ? `${g.shared_segment_count} segments`
                : 'all rides';

            // Parse display name: "date — riders (info)"
            const parts = g.name.split(' — ');
            const displayName = parts.length > 1 ? parts[1] : g.name;

            // Highlight groups with many shared segments
            const isHighlighted = g.type === 'segment' && g.shared_segment_count >= 15;
            const highlightClass = isHighlighted ? 'highlighted' : '';

            html += `<div class="group-card ${isActive} ${highlightClass}" data-group-id="${g.id}" onclick="RettichApp.selectGroup(${g.id})">
                <div class="group-name">${displayName}</div>
                <div class="group-meta">
                    <span class="group-badge ${badgeClass}">${badgeText}</span>
                    <span>${g.activity_ids.length} rides</span>
                </div>
            </div>`;
        });
        el.innerHTML = html;

        // Auto-select first segment group for this date, or first group
        const firstSeg = dateGroups.find(g => g.type === 'segment');
        const autoSelect = firstSeg || dateGroups[0];
        if (autoSelect) {
            selectGroup(autoSelect.id);
        }
    }

    function renderGroups() {
        // kept for compatibility — just renders for current date
        if (selectedDate) renderGroupsForDate(selectedDate);
    }

    function setupModeToggle() {
        document.querySelectorAll('.mode-btn').forEach(btn => {
            btn.addEventListener('click', async () => {
                const mode = btn.dataset.mode;
                if (mode === currentMode) return;

                currentMode = mode;
                document.querySelectorAll('.mode-btn').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');

                if (selectedGroupId) {
                    const activities = await loadGroupActivities(selectedGroupId);
                    const segments = sharedSegments[String(selectedGroupId)] || [];
                    applyMode(activities, segments);
                }
            });
        });
    }

    return {
        init,
        selectGroup,
        refreshMap,
    };
})();

// Boot
document.addEventListener('DOMContentLoaded', () => {
    RettichApp.init();
});
