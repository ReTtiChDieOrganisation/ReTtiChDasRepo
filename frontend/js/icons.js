/* ReTtiCh frame/icon definitions */

const RETTICH_FRAMES = {
    blue:      { line_color: 'rgba(0, 56, 123, 1)',    hex: '#00387b' },
    green:     { line_color: 'rgba(6, 80, 0, 1)',      hex: '#065000' },
    orbea:     { line_color: 'rgba(207, 181, 59, 1)',   hex: '#cfb53b' },
    ulle:      { line_color: 'rgba(227, 0, 126, 1)',    hex: '#e3007e' },
    cinelli:   { line_color: 'rgba(255, 102, 0, 1)',    hex: '#ff6600' },
    speedster: { line_color: 'rgba(24, 23, 23, 1)',     hex: '#888888' },
    navyblue:  { line_color: 'rgba(32, 56, 100, 1)',    hex: '#203864' },
    neutral:   { line_color: 'rgba(208, 206, 206, 1)',  hex: '#d0cece' },
    purple:    { line_color: 'rgba(112, 48, 160, 1)',   hex: '#7030a0' },
    red:       { line_color: 'rgba(139, 0, 0, 1)',      hex: '#8b0000' },
    orange:    { line_color: 'rgba(132, 60, 12, 1)',    hex: '#843c0c' },
    yellow:    { line_color: 'rgba(255, 238, 21, 1)',   hex: '#ffee15' },
    gold:      { line_color: 'rgba(207, 181, 59, 1)',   hex: '#cfb53b' },
    silver:    { line_color: 'rgba(170, 169, 173, 1)',  hex: '#aaa9ad' },
    bronze:    { line_color: 'rgba(191, 137, 112, 1)',  hex: '#bf8970' },
    black:     { line_color: 'rgba(0, 0, 0, 1)',        hex: '#333333' },
    white:     { line_color: 'rgba(255, 255, 255, 1)',  hex: '#ffffff' },
    default:   { line_color: 'rgba(100, 100, 100, 1)',  hex: '#646464' },
};

// Distinct colors for riders if frame colors collide
const RIDER_COLORS_FALLBACK = [
    '#ff6600', '#3b82f6', '#10b981', '#f59e0b',
    '#ef4444', '#8b5cf6', '#ec4899', '#06b6d4'
];

function getRiderColor(rider) {
    const frame = rider.frame || 'default';
    const frameData = RETTICH_FRAMES[frame] || RETTICH_FRAMES['default'];
    return frameData.hex;
}

function createRiderMarkerIcon(rider, size = 12) {
    const color = getRiderColor(rider);
    return L.divIcon({
        className: 'rider-marker-custom',
        html: `<div style="
            width: ${size}px; height: ${size}px;
            background: ${color};
            border: 2px solid white;
            border-radius: 50%;
            box-shadow: 0 0 6px ${color}, 0 2px 4px rgba(0,0,0,0.4);
        "></div>`,
        iconSize: [size, size],
        iconAnchor: [size / 2, size / 2],
    });
}
