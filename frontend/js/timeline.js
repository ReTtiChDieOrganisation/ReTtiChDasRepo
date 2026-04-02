/* ReTtiCh Timeline Module — Time-synchronized playback */

const RettichTimeline = (function () {
    let isPlaying = false;
    let animationFrame = null;
    let lastFrameTime = null;

    let globalStartEpoch = 0;
    let globalEndEpoch = 0;
    let globalStartLocalTime = null; // parsed from start_date_local (h, m, s)
    let currentTimeOffset = 0; // seconds from globalStartEpoch
    let totalDuration = 0;

    let speedMultiplier = 60;
    const SPEEDS = [1, 5, 10, 30, 60, 120, 300, 600];
    let speedIndex = 4; // index of 60

    let activitiesData = [];
    let ridersData = {};

    // DOM
    let elPlay, elTimeline, elCurrent, elEnd, elSpeedBtn, elClock;

    function init() {
        elPlay = document.getElementById('pb-play');
        elTimeline = document.getElementById('pb-timeline');
        elCurrent = document.getElementById('pb-current-time');
        elEnd = document.getElementById('pb-end-time');
        elSpeedBtn = document.getElementById('pb-speed-btn');
        elClock = document.getElementById('pb-clock');

        elPlay.addEventListener('click', togglePlay);
        elTimeline.addEventListener('input', onSeek);
        elSpeedBtn.addEventListener('click', cycleSpeed);
        elSpeedBtn.textContent = speedMultiplier + '×';
    }

    function load(activities, riders) {
        stop();
        activitiesData = activities.filter(a => a.streams && a.streams.time && a.streams.latlng);
        ridersData = riders;

        if (activitiesData.length === 0) {
            totalDuration = 0;
            return;
        }

        // Find global time window
        globalStartEpoch = Infinity;
        globalEndEpoch = -Infinity;
        let earliestAct = null;

        activitiesData.forEach(act => {
            const start = act.start_epoch;
            const end = start + (act.streams.time[act.streams.time.length - 1] || act.elapsed_time);
            if (start < globalStartEpoch) {
                globalStartEpoch = start;
                earliestAct = act;
            }
            if (end > globalEndEpoch) globalEndEpoch = end;
        });

        // Parse local start time from start_date_local (e.g. "2025-05-19T07:30:00")
        globalStartLocalTime = null;
        if (earliestAct && earliestAct.start_date_local) {
            const match = earliestAct.start_date_local.match(/(\d{2}):(\d{2}):(\d{2})/);
            if (match) {
                globalStartLocalTime = {
                    h: parseInt(match[1]),
                    m: parseInt(match[2]),
                    s: parseInt(match[3])
                };
            }
        }

        totalDuration = globalEndEpoch - globalStartEpoch;
        currentTimeOffset = 0;

        elEnd.textContent = formatTime(totalDuration);
        elCurrent.textContent = formatTime(0);
        elTimeline.value = 0;

        updateUI();
        updatePositions();
    }

    function togglePlay() {
        if (isPlaying) {
            stop();
        } else {
            play();
        }
    }

    function play() {
        if (totalDuration <= 0) return;
        if (currentTimeOffset >= totalDuration) {
            currentTimeOffset = 0;
        }
        isPlaying = true;
        elPlay.textContent = '⏸';
        elPlay.classList.add('playing');
        lastFrameTime = performance.now();
        tick();
    }

    function stop() {
        isPlaying = false;
        elPlay.textContent = '▶';
        elPlay.classList.remove('playing');
        if (animationFrame) {
            cancelAnimationFrame(animationFrame);
            animationFrame = null;
        }
    }

    function tick() {
        if (!isPlaying) return;

        const now = performance.now();
        const dt = (now - lastFrameTime) / 1000; // real seconds
        lastFrameTime = now;

        currentTimeOffset += dt * speedMultiplier;

        if (currentTimeOffset >= totalDuration) {
            currentTimeOffset = totalDuration;
            stop();
        }

        updateUI();
        updatePositions();

        if (isPlaying) {
            animationFrame = requestAnimationFrame(tick);
        }
    }

    function onSeek() {
        const frac = parseInt(elTimeline.value) / 1000;
        currentTimeOffset = frac * totalDuration;
        updateUI();
        updatePositions();
    }

    function cycleSpeed() {
        speedIndex = (speedIndex + 1) % SPEEDS.length;
        speedMultiplier = SPEEDS[speedIndex];
        elSpeedBtn.textContent = speedMultiplier + '×';
    }

    function updateUI() {
        elCurrent.textContent = formatTime(currentTimeOffset);
        if (totalDuration > 0) {
            elTimeline.value = Math.round((currentTimeOffset / totalDuration) * 1000);
        }
        // Show actual clock time derived from start_date_local + offset
        if (elClock && globalStartLocalTime) {
            const totalSecs = globalStartLocalTime.h * 3600
                + globalStartLocalTime.m * 60
                + globalStartLocalTime.s
                + Math.round(currentTimeOffset);
            const h = Math.floor(totalSecs / 3600) % 24;
            const m = Math.floor((totalSecs % 3600) / 60);
            const s = totalSecs % 60;
            elClock.textContent =
                h.toString().padStart(2, '0') + ':' +
                m.toString().padStart(2, '0') + ':' +
                s.toString().padStart(2, '0');
        }
    }

    function updatePositions() {
        const currentAbsoluteTime = globalStartEpoch + currentTimeOffset;

        activitiesData.forEach(act => {
            const rider = ridersData[act.rider_name] || { frame: 'default' };
            const actStart = act.start_epoch;
            const times = act.streams.time;
            const latlngs = act.streams.latlng;

            const relativeTime = currentAbsoluteTime - actStart;

            if (relativeTime < 0 || relativeTime > times[times.length - 1]) {
                RettichMap.hideRiderMarker(act.rider_name + '_' + act.id);
                return;
            }

            // Binary search for position
            const pos = interpolatePosition(times, latlngs, relativeTime);
            if (pos) {
                RettichMap.setRiderPosition(act.rider_name + '_' + act.id, pos, {
                    ...rider,
                    name: act.rider_name
                });
            }
        });
    }

    function interpolatePosition(times, latlngs, targetTime) {
        if (!times || !latlngs || times.length === 0) return null;

        // Binary search
        let lo = 0, hi = times.length - 1;
        while (lo < hi - 1) {
            const mid = (lo + hi) >> 1;
            if (times[mid] <= targetTime) lo = mid;
            else hi = mid;
        }

        if (lo === hi || times[lo] === times[hi]) {
            return latlngs[lo];
        }

        // Interpolate between lo and hi
        const frac = (targetTime - times[lo]) / (times[hi] - times[lo]);
        const lat = latlngs[lo][0] + frac * (latlngs[hi][0] - latlngs[lo][0]);
        const lng = latlngs[lo][1] + frac * (latlngs[hi][1] - latlngs[lo][1]);
        return [lat, lng];
    }

    function formatTime(seconds) {
        seconds = Math.max(0, Math.round(seconds));
        const h = Math.floor(seconds / 3600);
        const m = Math.floor((seconds % 3600) / 60);
        const s = seconds % 60;
        return `${h.toString().padStart(2, '0')}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
    }

    function destroy() {
        stop();
        activitiesData = [];
    }

    return {
        init,
        load,
        play,
        stop,
        destroy,
        isPlaying: () => isPlaying,
    };
})();
