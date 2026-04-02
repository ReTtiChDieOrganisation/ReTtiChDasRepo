/* ReTtiCh Stats Module — Segment podium statistics */

const RettichStats = (function () {
    let elStatsSection, elStatsContent;

    function init() {
        elStatsSection = document.getElementById('stats-section');
        elStatsContent = document.getElementById('stats-content');
    }

    function computeAndDisplay(activitiesData, ridersData) {
        if (!activitiesData || activitiesData.length < 2) {
            elStatsSection.style.display = 'none';
            return;
        }

        // Collect all segment efforts grouped by segment_id
        const segmentResults = {};

        activitiesData.forEach(act => {
            if (!act.segment_efforts) return;
            act.segment_efforts.forEach(effort => {
                const segId = effort.segment_id;
                if (!segmentResults[segId]) {
                    segmentResults[segId] = [];
                }
                segmentResults[segId].push({
                    rider_name: act.rider_name,
                    elapsed_time: effort.elapsed_time,
                    activity_id: act.id,
                });
            });
        });

        // Only consider segments with ≥2 riders
        const sharedSegments = Object.entries(segmentResults)
            .filter(([_, results]) => {
                const uniqueRiders = new Set(results.map(r => r.rider_name));
                return uniqueRiders.size >= 2;
            });

        if (sharedSegments.length === 0) {
            elStatsSection.style.display = 'none';
            return;
        }

        // Tally medals per rider
        const medals = {}; // rider -> {gold: n, silver: n, bronze: n}

        sharedSegments.forEach(([segId, results]) => {
            // Sort by time, fastest first
            const sorted = [...results].sort((a, b) => a.elapsed_time - b.elapsed_time);

            // Deduplicate: only best effort per rider per segment
            const seen = new Set();
            const unique = sorted.filter(r => {
                if (seen.has(r.rider_name)) return false;
                seen.add(r.rider_name);
                return true;
            });

            unique.forEach((r, i) => {
                if (!medals[r.rider_name]) {
                    medals[r.rider_name] = { gold: 0, silver: 0, bronze: 0 };
                }
                if (i === 0) medals[r.rider_name].gold++;
                else if (i === 1) medals[r.rider_name].silver++;
                else if (i === 2) medals[r.rider_name].bronze++;
            });
        });

        // Sort riders by gold, then silver, then bronze
        const sorted = Object.entries(medals).sort((a, b) => {
            if (b[1].gold !== a[1].gold) return b[1].gold - a[1].gold;
            if (b[1].silver !== a[1].silver) return b[1].silver - a[1].silver;
            return b[1].bronze - a[1].bronze;
        });

        // Build HTML
        let html = `<div class="stats-grid">
            <div class="stat-card">
                <div class="medal">🏅</div>
                <div class="stat-name">Shared Segs</div>
                <div class="stat-count">${sharedSegments.length}</div>
            </div>
            <div class="stat-card">
                <div class="medal">👥</div>
                <div class="stat-name">Riders</div>
                <div class="stat-count">${sorted.length}</div>
            </div>
        </div>`;

        html += '<div class="podium-section">';
        sorted.forEach(([name, m], i) => {
            const rider = ridersData[name] || {};
            const color = getRiderColor(rider);
            const bg = i < 3 ? `background: ${color}15; border: 1px solid ${color}33;` : '';
            html += `<div class="podium-rider" style="${bg}">
                <span class="medal-icon">${i === 0 ? '🥇' : i === 1 ? '🥈' : i === 2 ? '🥉' : '　'}</span>
                <span class="podium-name">${name}</span>
                <span class="podium-counts">
                    <span style="color:var(--gold)">${m.gold}</span> /
                    <span style="color:var(--silver)">${m.silver}</span> /
                    <span style="color:var(--bronze)">${m.bronze}</span>
                </span>
            </div>`;
        });
        html += '</div>';

        elStatsContent.innerHTML = html;
        elStatsSection.style.display = 'block';
    }

    function hide() {
        elStatsSection.style.display = 'none';
    }

    return { init, computeAndDisplay, hide };
})();
