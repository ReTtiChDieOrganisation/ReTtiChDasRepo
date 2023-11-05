"use strict"

// Load all tiles from the server
let currentSpeed = 1.0;

var imagery = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
{attribution: 'Tiles &copy; Esri &mdash; Source: Esri, i-cubed, USDA, USGS, AEX, GeoEye, Getmapping, Aerogrid, IGN, IGP, UPR-EGP, and the GIS User Community', maxZoom:21}
);
var street = L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
    attribution: '© OpenStreetMap'
});
var cyclOSM = L.tileLayer('https://{s}.tile-cyclosm.openstreetmap.fr/cyclosm/{z}/{x}/{y}.png', {
    maxZoom: 19,
    attribution: '© OpenStreetMap'
});

var map = L.map('map', {
    center: [50.896537, 7.025585],
    zoom: 12,
    layers: [imagery, street, cyclOSM]
});

var baseMaps = {
    "cycleOSM": cyclOSM,
    "Imagery": imagery,
    "Street": street,
};

let layerControl = L.control.layers(baseMaps, null, {position: 'bottomleft'}).addTo(map);


ALL_STATS = JSON.parse(ALL_STATS)
ALL_RIDES = JSON.parse(ALL_RIDES)
RIDERS_PROFILE_INFO = JSON.parse(RIDERS_PROFILE_INFO)
var ISPAUSED = false;
let marker_start;
let marker_finish;

let NAMES = Object.keys(RIDERS_PROFILE_INFO)


class rettich_rider {
    // constructor
    constructor(name, ride_ids, profile_picture_url= "./frontend/icons/profile_pictures/default.png", frame=rettich_frames.default) {
        // all data members of rettich riders
        console.log("Construct rider ", name);
        this.name = name;
        this.ride_ids = ride_ids;
        this.profile_picture = {
            picture : profile_picture_url,
            size : [33,44], // 3:4 ratio
            anchor : [33/2,44+22] // picture_size_y + adjust (adjust to center picture in frame)
        };
        this.frame = frame;
    }

    // getter functions
    get_name () {return this.name;}
    get_ride_ids () {return this.ride_ids;}
    get_profile_picture () {return this.profile_picture;}
    get_frame () {return this.frame;}
    
    // setter functions
    set_name (new_name) {this.name = new_name;}
    set_ride_ids (new_ride_ids) {this.ride_ids = new_ride_ids;}
    set_profile_picture (new_profile_picture) {this.profile_picture = new_profile_picture;}
    set_frame (new_frame) {this.frame = new_frame;}
    set_frame_fg (new_foreground) {this.frame.frame_fg = new_foreground;}
    set_frame_bg (new_background) {this.frame.frame_bg = new_background;}
    set_frame_line_color (new_line_color) {this.frame.line_color = new_line_color;}
}

let RIDER_ARR = []
let ride_ids = []

let id_counter = 0;
for (let name of NAMES){
    //calculate all ids corresponding to this rider
    ride_ids = []
    for (let ride_i of Object.keys(ALL_RIDES)){
        if (ALL_RIDES[ride_i].rider==name){
            ride_ids.push(ride_i)
            ALL_RIDES[ride_i]['rider_id'] = id_counter
        }
    }	
    
    let rr;

    // construct riders
    if (RIDERS_PROFILE_INFO[name]['icon_url']=='' || RIDERS_PROFILE_INFO[name]['frame']==''){
        // use default constructor if profile picture or frame info are missing
        rr = new rettich_rider(name, ride_ids)
    }else{
        rr = new rettich_rider(name, ride_ids, RIDERS_PROFILE_INFO[name]['icon_url'], rettich_frames[RIDERS_PROFILE_INFO[name]['frame']])
    }
    RIDER_ARR.push(rr)
    id_counter +=1
}

// find group of all rides
let GROUP_ID_ALL = -1
let largest_group = -1
for (let group_id_i of Object.keys(ALL_STATS)){
    if (ALL_STATS[group_id_i].ride_ids.length>largest_group){
        largest_group = ALL_STATS[group_id_i].ride_ids.length
        GROUP_ID_ALL = group_id_i
    }
    
} 

let CURRENT_GROUP = GROUP_ID_ALL;

let seqGroups = rettich_motion_draw_groups()
map.on('click', rettich_onMapClick);



document.getElementById('restartButton').addEventListener('click', () => {
    document.body.style.cursor = 'wait';
    currentSpeed = 1;
    rettich_change_speed_label();
    rettich_motion_keys('restart');
    document.body.style.cursor = 'default';
});

document.getElementById('slowdownButton').addEventListener('click', () => {
    if (currentSpeed > 0.5) {
        rettich_motion_keys('slowdown');
        currentSpeed *= 0.5;
        rettich_change_speed_label();
    }
});

document.getElementById('toggleButton').addEventListener('click', () => {
    ISPAUSED = !ISPAUSED;
    if (ISPAUSED) {
        rettich_motion_keys('pause');
        document.getElementById("playPauseIcon").src = "./frontend/icons/control/PlayButton.png";
        document.getElementById('toggleButton').title = 'Play';
    } else {
        rettich_motion_keys('resume');
        document.getElementById("playPauseIcon").src = "./frontend/icons/control/PauseButton.png";
        document.getElementById('toggleButton').title = 'Pause';
    }
});

document.getElementById('speedupButton').addEventListener('click', () => {
    rettich_motion_keys('speedup');
    currentSpeed *= 2;
    rettich_change_speed_label();
});



//--------------- only script function definition below ---------------//
function rettich_motion_draw_groups(lat_lng_startidx_arr=-1,lat_lng_endidx=-1) {
    // draw all_all starting with the corresponding index. So index_set should be an array of indices with the same size as the group corresponding to CURRENT_GROUP
    ISPAUSED = false;
    if (document.getElementById('speedupButton')){ //only if toggle button already created
        document.getElementById('toggleButton').title = "Pause";
        document.getElementById("playPauseIcon").src = "./frontend/icons/control/PauseButton.png";
    }


    let num_rides = ALL_STATS[CURRENT_GROUP].ride_ids.length
    let lat_lngs_rides_arr = [];
    let speed_set = Array(num_rides).fill(0)
    if (lat_lng_startidx_arr==-1){
        lat_lng_startidx_arr= Array(num_rides).fill(0)
    }
    
    for (const [ride_iterator,ride_id] of ALL_STATS[CURRENT_GROUP].ride_ids.entries()) {
        let current_ride_data = ALL_RIDES[ride_id];
        let sliced_latlng;
        let et;
        let dist;


        if (lat_lng_endidx==-1) {
            sliced_latlng = current_ride_data.latlng.data.slice(lat_lng_startidx_arr[ride_iterator]);
            et = current_ride_data.time.data.at(-1)-current_ride_data.time.data[lat_lng_startidx_arr[ride_iterator]];
            dist = current_ride_data.distance.data.at(-1)-current_ride_data.distance.data[lat_lng_startidx_arr[ride_iterator]];
            speed_set[ride_iterator] = 3.6*dist/et;
        }
        else {
            sliced_latlng = current_ride_data.latlng.data.slice(lat_lng_startidx_arr[ride_iterator], lat_lng_endidx[ride_iterator]);
            et = current_ride_data.time.data[lat_lng_endidx[ride_iterator]]-current_ride_data.time.data[lat_lng_startidx_arr[ride_iterator]];
            dist = current_ride_data.distance.data[lat_lng_endidx[ride_iterator]]-current_ride_data.distance.data[lat_lng_startidx_arr[ride_iterator]];
            speed_set[ride_iterator] = 3.6*dist/et;
        }

        lat_lngs_rides_arr.push(sliced_latlng.map(([lat, lng]) => ({ lat, lng })));
    }

    let seqGroupsIntern = []
    for (const [ride_iterator,ride_id] of ALL_STATS[CURRENT_GROUP].ride_ids.entries()) {
        let current_rider = RIDER_ARR[ALL_RIDES[ride_id]['rider_id']];
        let current_ride_lat_lngs = lat_lngs_rides_arr[ride_iterator];
        // frame background
        let poly_frame_fg = L.motion.polyline(
            current_ride_lat_lngs, {
            color: current_rider.get_frame().line_color}, {}, {
            icon: L.icon({
                iconUrl: current_rider.get_frame().frame_fg,
                iconAnchor: current_rider.get_frame().anchor, 
                iconSize: current_rider.get_frame().size}
            )}
        )

        // profile picture
        let poly_profile_pic = L.motion.polyline(
            current_ride_lat_lngs, {
            color: current_rider.get_frame().line_color}, {}, {
            icon: L.icon({
                iconUrl: current_rider.get_profile_picture().picture,
                iconAnchor: current_rider.get_profile_picture().anchor, 
                iconSize: current_rider.get_profile_picture().size}
            )}
        )

        //frame foreground
        let poly_frame_bg = L.motion.polyline(
            current_ride_lat_lngs, {
            color: current_rider.get_frame().line_color}, {}, {
            icon: L.icon({
                iconUrl: current_rider.get_frame().frame_bg,
                iconAnchor: current_rider.get_frame().anchor, 
                iconSize: current_rider.get_frame().size}
            )}
        )

        if (speed_set!=-1) {
            poly_frame_bg.motionSpeed(speed_set[ride_iterator]);
            poly_profile_pic.motionSpeed(speed_set[ride_iterator]);
            poly_frame_fg.motionSpeed(speed_set[ride_iterator]);
        }

        seqGroupsIntern.push(L.motion.seq([poly_frame_bg]).addTo(map));
        seqGroupsIntern.push(L.motion.seq([poly_profile_pic]).addTo(map));
        seqGroupsIntern.push(L.motion.seq([poly_frame_fg]).addTo(map));
    }

    for (let seqGroup of seqGroupsIntern){
        seqGroup.motionStart();
    }

    return seqGroupsIntern
}

function rettich_get_distance(p,q) {
    return Math.sqrt(Math.pow(p[0] - q[0], 2) + Math.pow(p[1] - q[1], 2))
}

function rettich_find_closest_index(arrayOP, point){
    // Calculates the index of the array of points for the closest to point, last index not checked
    let dist = 99999999.0; // just some random - for planet earth - high enough value
    let idx = -1;

    for (let i = 0; i < arrayOP.length-1; i++){
        let point_i = arrayOP[i];
        let dist_i = rettich_get_distance(point_i,point)
        if (dist_i<dist){
            dist = dist_i;
            idx = i;
        }
    }
    return idx
}

function rettich_onMapClick(e) {
    let lat_lng_startidx_arr = [];
    if (typeof ALL_STATS=='string'){
        ALL_STATS = JSON.parse(ALL_STATS) // i have no idea why i have to parse it here again
    }
    
    for (const [ride_iterator,ride_id] of  ALL_STATS[CURRENT_GROUP]['ride_ids'].entries()) {
        let current_ride_data = ALL_RIDES[ride_id];
        let idx_temp = rettich_find_closest_index(current_ride_data.latlng.data,[e.latlng.lat, e.latlng.lng]);
        lat_lng_startidx_arr.push(idx_temp);
    }
        
    
    rettich_remove_all_rides_from_map()
    seqGroups = rettich_motion_draw_groups(lat_lng_startidx_arr)
    currentSpeed = 1;
    rettich_change_speed_label();
}

function rettich_remove_all_rides_from_map() { 
    for (let seqGroup of seqGroups){
        seqGroup.motionStop();
        seqGroup.removeFrom(map);
    }

    if (typeof marker_start !== 'undefined'){
        map.removeLayer(marker_start);
    }

    if (typeof marker_finish !== 'undefined'){
        map.removeLayer(marker_finish);
    }
}

function rettich_motion_draw_segment(seg_name) {
    
        
    let start_idx_set = [];
    let end_idx_set = [];
    for (const [ride_iterator,ride_id] of  ALL_STATS[CURRENT_GROUP].ride_ids.entries()) {
        start_idx_set.push(ALL_STATS[CURRENT_GROUP]['segments'][seg_name][ride_id]['start_index'])
        end_idx_set.push(ALL_STATS[CURRENT_GROUP]['segments'][seg_name][ride_id]['end_index'])
    }

    let seqGroupsIntern = rettich_motion_draw_groups(start_idx_set,end_idx_set)
    if (typeof marker_start !== 'undefined'){
        map.removeLayer(marker_start);
    }

    if (typeof marker_finish !== 'undefined'){
        map.removeLayer(marker_finish);
    }
    marker_start = rettich_static_draw_marker(ALL_STATS[CURRENT_GROUP]['segments'][seg_name]['Segment']['start_latlng'], rettich_other_icons.start)
    marker_finish = rettich_static_draw_marker(ALL_STATS[CURRENT_GROUP]['segments'][seg_name]['Segment']['end_latlng'], rettich_other_icons.finish)
    
    let bounds = L.latLngBounds(marker_start.getLatLng(), marker_finish.getLatLng())

    map.fitBounds(bounds);
    return seqGroupsIntern;
}

function rettich_static_draw_marker(latlng, marker_icon) {
    return L.marker(
        latlng, {
        icon: L.icon({
            iconUrl: marker_icon.icon,
            iconAnchor: marker_icon.anchor, 
            iconSize: marker_icon.size})}
    ).addTo(map);
}

function rettich_motion_keys(key) {
    // The restart case is outside the for loop, because inside the rettich_remove_all_rides_from_map there is already an iteration over all seqGroups
    if (key == "restart"){
        rettich_remove_all_rides_from_map()
        let current_segment = $("#sel_segment").val().split(',')
        seqGroups = (current_segment == "") ? rettich_motion_draw_groups() : rettich_motion_draw_segment(current_segment[0]);
    } else {
        for (let seqGroup of seqGroups){
            switch (key) {
            case 'stop':
                seqGroup.motionStop();
                break;
            case "pause":
                seqGroup.motionPause();
                break;
            case "resume":
                seqGroup.motionResume();
                break;
            case "toggle":
                seqGroup.motionToggle();
                break;
            case 'speedup':
                seqGroup.getFirstLayer().motionSpeed(seqGroup.getFirstLayer().motionOptions.speed*2);
                break;
            case "slowdown":
                seqGroup.getFirstLayer().motionSpeed(seqGroup.getFirstLayer().motionOptions.speed*0.5);
                break;
            }
        }
    }
}

function rettich_change_speed_label() {
    document.getElementById('speedLabel').innerText = `x${currentSpeed}`;
}
