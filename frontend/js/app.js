/* ReTtiCh App — Main application controller
 *
 * Architecture:
 *   - Metadata (riders, groups, shared_segments) is embedded in index.html (~small)
 *   - Activity data lives in separate .js files (data/activities/12345.js)
 *   - Activities are loaded on demand when a group is selected
 *   - Loading uses <script> tag injection which works with file:// (unlike fetch)
 *   - Loaded activities cache in window.RETTICH_ACT
 */

const RettichApp = (function () {
    let riders = {};
    let groups = [];
    let activitiesIndex = [];
    let sharedSegments = {};
    let siteConfig = {};

    let selectedGroupId = null;
    let selectedDate = null;
    let currentMode = 'time-sync';
    let groupActivitiesCache = {}; // groupId -> [activity data]

    // --- Initialization ---

    async function init() {
        // Metadata is always embedded via window.RETTICH_DATA
        if (!window.RETTICH_DATA) {
            document.getElementById('group-list').innerHTML =
                '<div class="loading" style="color:var(--danger)">No data found. Run build.py first.</div>';
            return;
        }

        siteConfig = window.RETTICH_DATA.site_config || { password_hash: 0 };

        if (siteConfig.password_hash && siteConfig.password_hash !== 0) {
            // Check if already authenticated this session
            if (sessionStorage.getItem('rettich_auth') === String(siteConfig.password_hash)) {
                await startApp();
            } else {
                showPasswordGate();
            }
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
                sessionStorage.setItem('rettich_auth', String(siteConfig.password_hash));
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
        return h >>> 0;
    }

    async function startApp() {
        riders = window.RETTICH_DATA.riders || {};
        groups = window.RETTICH_DATA.groups || [];
        activitiesIndex = window.RETTICH_DATA.activities_index || [];
        sharedSegments = window.RETTICH_DATA.shared_segments || {};

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

        // Auto-select newest date
        const dates = getUniqueDates();
        if (dates.length > 0) {
            selectDate(dates[0]);
        }
    }

    // --- On-demand activity loading via <script> injection ---

    function loadActivityScript(aid) {
        return new Promise((resolve, reject) => {
            // Already loaded?
            if (window.RETTICH_ACT && window.RETTICH_ACT[String(aid)]) {
                resolve(window.RETTICH_ACT[String(aid)]);
                return;
            }

            const script = document.createElement('script');
            script.src = `data/activities/${aid}.js`;
            script.onload = () => {
                const data = window.RETTICH_ACT && window.RETTICH_ACT[String(aid)];
                if (data) {
                    resolve(data);
                } else {
                    reject(new Error(`Activity ${aid} not found after script load`));
                }
            };
            script.onerror = () => reject(new Error(`Failed to load activity ${aid}`));
            document.head.appendChild(script);
        });
    }

    async function loadGroupActivities(groupId) {
        if (groupActivitiesCache[groupId]) return groupActivitiesCache[groupId];

        const group = groups.find(g => g.id === groupId);
        if (!group) return [];

        // Load all activities for this group in parallel
        const promises = group.activity_ids.map(aid =>
            loadActivityScript(aid).catch(err => {
                console.warn(`Could not load activity ${aid}:`, err.message);
                return null;
            })
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

        // Show loading state
        const group = groups.find(g => g.id === groupId);
        const actCount = group ? group.activity_ids.length : 0;
        document.getElementById('group-list').querySelectorAll('.group-card.active .group-meta').forEach(el => {
            el.innerHTML += ' <span class="loading-dots">loading...</span>';
        });

        // Load activities on demand
        const activities = await loadGroupActivities(groupId);

        // Remove loading indicator
        document.querySelectorAll('.loading-dots').forEach(el => el.remove());

        if (activities.length === 0) return;

        // Show stats
        RettichStats.computeAndDisplay(activities, riders);

        // Show per-activity rettiche
        renderActivitiesList(group, activities);

        // Load segments for segment mode
        const segments = sharedSegments[String(groupId)] || [];

        // Apply mode
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

            RettichMap.drawRoutes(activities, riders);
            RettichTimeline.load(activities, riders);
        } else {
            document.getElementById('playback-controls').style.display = 'none';
            document.getElementById('segment-panel').style.display = 'block';

            RettichMap.drawRoutes(activities, riders);
            RettichSegments.load(activities, riders, segments);
        }
    }

    function refreshMap() {
        if (!selectedGroupId) return;
        loadGroupActivities(selectedGroupId).then(activities => {
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
            html += `<div class="rider-row" style="cursor:pointer;" onclick="RettichApp.focusRider('${r.name}')">
                <div class="rider-color" style="background:${color};"></div>
                <span class="rider-name">${r.name}</span>
                <span class="rider-frame">${r.frame}</span>
            </div>`;
        });
        el.innerHTML = html;
    }

    function renderActivitiesList(group, activities) {
        const section = document.getElementById('activities-section');
        const el = document.getElementById('activities-list');
        if (!group || !activities || activities.length === 0) {
            section.style.display = 'none';
            return;
        }

        // Look up tile info from activitiesIndex
        const indexById = {};
        activitiesIndex.forEach(a => { indexById[a.id] = a; });

        // Build list sorted by rettiche score desc
        const items = activities.map(act => {
            const idx = indexById[act.id] || {};
            const rider = riders[act.rider_name] || {};
            const color = getRiderColor(rider);
            const newTiles = idx.new_tiles != null ? idx.new_tiles : 0;
            const totalTiles = idx.total_tiles != null ? idx.total_tiles : 0;
            const retticheScore = idx.rettiche_score != null ? idx.rettiche_score : 0;
            const dist = act.distance ? (act.distance / 1000).toLocaleString(undefined, {minimumFractionDigits: 1, maximumFractionDigits: 1}) : '?';
            return { act, rider, color, newTiles, totalTiles, retticheScore, dist, name: act.rider_name };
        }).sort((a, b) => b.retticheScore - a.retticheScore);

        el.innerHTML = items.map(it => {
            const scoreDisplay = it.retticheScore > 0 ? it.retticheScore.toLocaleString(undefined, {minimumFractionDigits: 1, maximumFractionDigits: 1}) : (0).toLocaleString(undefined, {minimumFractionDigits: 1, maximumFractionDigits: 1});
            return `
            <div class="activity-item" style="cursor:pointer;" onclick="RettichApp.focusRider('${it.name}')">
                <div class="rider-color" style="background:${it.color};width:10px;height:10px;border-radius:50%;flex-shrink:0;"></div>
                <span class="activity-name">${it.name}</span>
                <span class="activity-dist">${it.dist} km</span>
                <span class="activity-rettiche" title="${it.totalTiles} tiles touched, ${it.newTiles} new">🥕 ${scoreDisplay} (${it.newTiles} new / ${it.totalTiles})</span>
            </div>
        `}).join('');

        section.style.display = 'block';
    }

    function getUniqueDates() {
        const dateSet = new Set(groups.map(g => g.date));
        return [...dateSet].sort((a, b) => b.localeCompare(a));
    }

    function renderDateSelector() {
        const el = document.getElementById('date-select');
        const dates = getUniqueDates();

        el.innerHTML = '';
        dates.forEach(d => {
            const opt = document.createElement('option');
            opt.value = d;
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

            const parts = g.name.split(' — ');
            const displayName = parts.length > 1 ? parts[1] : g.name;

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

        // Auto-select best group
        const firstSeg = dateGroups.find(g => g.type === 'segment');
        const autoSelect = firstSeg || dateGroups[0];
        if (autoSelect) {
            selectGroup(autoSelect.id);
        }
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

    async function focusRider(riderName) {
        if (!selectedGroupId) return;
        const activities = await loadGroupActivities(selectedGroupId);
        const riderActs = activities.filter(a =>
            a.rider_name === riderName && a.streams && a.streams.latlng && a.streams.latlng.length > 1
        );
        if (riderActs.length === 0) return;

        const allPoints = [];
        riderActs.forEach(a => allPoints.push(...a.streams.latlng));
        if (allPoints.length > 0) {
            RettichMap.fitBounds(L.latLngBounds(allPoints), [50, 50]);
        }
    }

    return {
        init,
        selectGroup,
        refreshMap,
        focusRider,
    };
})();

// Boot
document.addEventListener('DOMContentLoaded', () => {
    RettichApp.init();
});