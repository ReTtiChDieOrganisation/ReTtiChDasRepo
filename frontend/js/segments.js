/* ReTtiCh Segments Module — Segment comparison mode */

const RettichSegments = (function () {
    let activitiesData = [];
    let ridersData = {};
    let sharedSegments = [];
    let selectedSegmentId = null;

    // Segment playback state
    let isPlaying = false;
    let animationFrame = null;
    let lastFrameTime = null;
    let currentTime = 0;
    let maxDuration = 0;
    let speedMultiplier = 5;
    const SPEEDS = [1, 2, 5, 10, 30, 60];
    let speedIndex = 2; // index of 5

    let segmentRiderData = []; // processed segment data per rider

    // DOM
    let elSelect, elInfo, elTable, elPanel;
    let elSegPlay, elSegTimeline, elSegCurrent, elSegEnd, elSegSpeed, elSegPlayback;

    function init() {
        elSelect = document.getElementById('segment-select');
        elInfo = document.getElementById('segment-info');
        elTable = document.getElementById('segment-table');
        elPanel = document.getElementById('segment-panel');
        elSegPlay = document.getElementById('seg-pb-play');
        elSegTimeline = document.getElementById('seg-pb-timeline');
        elSegCurrent = document.getElementById('seg-pb-current-time');
        elSegEnd = document.getElementById('seg-pb-end-time');
        elSegSpeed = document.getElementById('seg-pb-speed-btn');
        elSegPlayback = document.getElementById('segment-playback');

        elSelect.addEventListener('change', onSegmentChange);
        elSegPlay.addEventListener('click', toggleSegPlay);
        elSegTimeline.addEventListener('input', onSegSeek);
        elSegSpeed.addEventListener('click', cycleSegSpeed);
        elSegSpeed.textContent = speedMultiplier + '×';
    }

    function load(activities, riders, segments) {
        stopSegPlay();
        activitiesData = activities;
        ridersData = riders;
        sharedSegments = segments || [];
        selectedSegmentId = null;

        // Populate dropdown
        elSelect.innerHTML = '<option value="">Choose a segment...</option>';
        sharedSegments.forEach(seg => {
            const opt = document.createElement('option');
            opt.value = seg.segment_id;
            opt.textContent = `${seg.segment_name} (${seg.ride_count} riders)`;
            elSelect.appendChild(opt);
        });

        elInfo.innerHTML = '';
        elTable.innerHTML = '';
        elSegPlayback.style.display = 'none';
    }

    function onSegmentChange() {
        const segId = parseInt(elSelect.value);
        if (!segId) {
            selectedSegmentId = null;
            elInfo.innerHTML = '';
            elTable.innerHTML = '';
            elSegPlayback.style.display = 'none';
            stopSegPlay();
            // Redraw map for full group
            if (typeof RettichApp !== 'undefined') RettichApp.refreshMap();
            return;
        }

        selectedSegmentId = segId;
        const seg = sharedSegments.find(s => s.segment_id === segId);
        if (!seg) return;

        // Show segment info
        const dist = seg.distance ? (seg.distance / 1000).toFixed(2) : '?';
        const grade = seg.avg_grade != null ? seg.avg_grade.toFixed(1) : '?';
        elInfo.innerHTML = `
            <div class="seg-stat">
                <div class="seg-stat-value">${dist} km</div>
                <div class="seg-stat-label">Distance</div>
            </div>
            <div class="seg-stat">
                <div class="seg-stat-value">${grade}%</div>
                <div class="seg-stat-label">Avg Grade</div>
            </div>
            <div class="seg-stat">
                <div class="seg-stat-value">${seg.ride_count}</div>
                <div class="seg-stat-label">Riders</div>
            </div>
        `;

        // Find efforts for this segment across activities
        segmentRiderData = [];

        activitiesData.forEach(act => {
            if (!act.segment_efforts || !act.streams) return;
            const effort = act.segment_efforts.find(e => e.segment_id === segId);
            if (!effort) return;

            const rider = ridersData[act.rider_name] || {};
            const startIdx = effort.start_index || 0;
            const endIdx = effort.end_index || (act.streams.latlng ? act.streams.latlng.length - 1 : 0);

            // Extract segment portion of streams
            let segLatlng = [], segTime = [], segDist = [];
            if (act.streams.latlng) {
                segLatlng = act.streams.latlng.slice(startIdx, endIdx + 1);
            }
            if (act.streams.time) {
                const rawTime = act.streams.time.slice(startIdx, endIdx + 1);
                const t0 = rawTime[0] || 0;
                segTime = rawTime.map(t => t - t0);
            }
            if (act.streams.distance) {
                const rawDist = act.streams.distance.slice(startIdx, endIdx + 1);
                const d0 = rawDist[0] || 0;
                segDist = rawDist.map(d => d - d0);
            }

            const avgSpeed = effort.distance && effort.elapsed_time
                ? (effort.distance / effort.elapsed_time * 3.6).toFixed(1)
                : '—';

            segmentRiderData.push({
                rider_name: act.rider_name,
                activity_id: act.id,
                elapsed_time: effort.elapsed_time,
                distance: effort.distance,
                average_watts: effort.average_watts,
                avg_speed: avgSpeed,
                latlng: segLatlng,
                time: segTime,
                rider: rider,
            });
        });

        // Sort by elapsed time (fastest first)
        segmentRiderData.sort((a, b) => a.elapsed_time - b.elapsed_time);

        // Build table
        let tableHtml = '<table><thead><tr><th>Rider</th><th>Time</th><th>Avg Speed</th><th>Power</th></tr></thead><tbody>';
        segmentRiderData.forEach((d, i) => {
            const medal = i === 0 ? '🥇 ' : i === 1 ? '🥈 ' : i === 2 ? '🥉 ' : '';
            const watts = d.average_watts ? d.average_watts.toFixed(0) + 'W' : '—';
            tableHtml += `<tr>
                <td>${medal}${d.rider_name}</td>
                <td>${formatTimeMM(d.elapsed_time)}</td>
                <td>${d.avg_speed} km/h</td>
                <td>${watts}</td>
            </tr>`;
        });
        tableHtml += '</tbody></table>';
        elTable.innerHTML = tableHtml;

        // Setup segment playback
        maxDuration = Math.max(...segmentRiderData.map(d => d.elapsed_time), 1);
        currentTime = 0;
        elSegEnd.textContent = formatTimeMM(maxDuration);
        elSegCurrent.textContent = formatTimeMM(0);
        elSegTimeline.value = 0;
        elSegPlayback.style.display = 'flex';

        // Draw segment routes on map
        drawSegmentOnMap();
    }

    function drawSegmentOnMap() {
        RettichMap.clearAll();

        const allBounds = [];
        segmentRiderData.forEach(d => {
            if (d.latlng && d.latlng.length > 1) {
                const color = getRiderColor(d.rider);
                RettichMap.drawRoute(d.latlng, color, 3, 0.7);
                allBounds.push(...d.latlng);
            }
        });

        if (allBounds.length > 0) {
            RettichMap.fitBounds(L.latLngBounds(allBounds), [60, 60]);
        }

        updateSegPositions();
    }

    // --- Segment playback ---

    function toggleSegPlay() {
        if (isPlaying) stopSegPlay();
        else startSegPlay();
    }

    function startSegPlay() {
        if (maxDuration <= 0) return;
        if (currentTime >= maxDuration) currentTime = 0;
        isPlaying = true;
        elSegPlay.textContent = '⏸';
        elSegPlay.classList.add('playing');
        lastFrameTime = performance.now();
        tickSeg();
    }

    function stopSegPlay() {
        isPlaying = false;
        elSegPlay.textContent = '▶';
        elSegPlay.classList.remove('playing');
        if (animationFrame) {
            cancelAnimationFrame(animationFrame);
            animationFrame = null;
        }
    }

    function tickSeg() {
        if (!isPlaying) return;
        const now = performance.now();
        const dt = (now - lastFrameTime) / 1000;
        lastFrameTime = now;

        currentTime += dt * speedMultiplier;
        if (currentTime >= maxDuration) {
            currentTime = maxDuration;
            stopSegPlay();
        }

        updateSegUI();
        updateSegPositions();

        if (isPlaying) {
            animationFrame = requestAnimationFrame(tickSeg);
        }
    }

    function onSegSeek() {
        const frac = parseInt(elSegTimeline.value) / 1000;
        currentTime = frac * maxDuration;
        updateSegUI();
        updateSegPositions();
    }

    function cycleSegSpeed() {
        speedIndex = (speedIndex + 1) % SPEEDS.length;
        speedMultiplier = SPEEDS[speedIndex];
        elSegSpeed.textContent = speedMultiplier + '×';
    }

    function updateSegUI() {
        elSegCurrent.textContent = formatTimeMM(currentTime);
        if (maxDuration > 0) {
            elSegTimeline.value = Math.round((currentTime / maxDuration) * 1000);
        }
    }

    function updateSegPositions() {
        RettichMap.clearRiderMarkers();

        segmentRiderData.forEach(d => {
            if (!d.latlng || !d.time || d.time.length === 0) return;

            // All start at t=0
            if (currentTime > d.time[d.time.length - 1]) {
                // Finished — show at end
                RettichMap.setRiderPosition(d.rider_name + '_seg', d.latlng[d.latlng.length - 1], {
                    ...d.rider,
                    name: d.rider_name
                });
                return;
            }

            if (currentTime < 0) return;

            const pos = interpolatePos(d.time, d.latlng, currentTime);
            if (pos) {
                RettichMap.setRiderPosition(d.rider_name + '_seg', pos, {
                    ...d.rider,
                    name: d.rider_name
                });
            }
        });
    }

    function interpolatePos(times, latlngs, target) {
        if (!times || !latlngs || times.length === 0) return null;
        let lo = 0, hi = times.length - 1;
        while (lo < hi - 1) {
            const mid = (lo + hi) >> 1;
            if (times[mid] <= target) lo = mid;
            else hi = mid;
        }
        if (lo === hi || times[lo] === times[hi]) return latlngs[lo];
        const frac = (target - times[lo]) / (times[hi] - times[lo]);
        return [
            latlngs[lo][0] + frac * (latlngs[hi][0] - latlngs[lo][0]),
            latlngs[lo][1] + frac * (latlngs[hi][1] - latlngs[lo][1]),
        ];
    }

    function formatTimeMM(seconds) {
        seconds = Math.max(0, Math.round(seconds));
        const m = Math.floor(seconds / 60);
        const s = seconds % 60;
        return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
    }

    function destroy() {
        stopSegPlay();
        segmentRiderData = [];
        selectedSegmentId = null;
    }

    function getSelectedSegmentId() {
        return selectedSegmentId;
    }

    return {
        init,
        load,
        destroy,
        getSelectedSegmentId,
    };
})();
