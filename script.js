// script.js
document.addEventListener('DOMContentLoaded', () => {
    const sidebar = document.getElementById('sidebar');
    const toggleSidebarButton = document.getElementById('toggleSidebarButton');
    const restartButton = document.getElementById('restartButton');
    const slowdownButton = document.getElementById('slowdownButton');
    const playPauseButton = document.getElementById('toggleButton');
    const speedupButton = document.getElementById('speedupButton');
    var mediaQuery = window.matchMedia("(min-width: 1000px)");

    // Load all tiles from the server
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

    var layerControl = L.control.layers(baseMaps, null, {position: 'bottomleft'}).addTo(map);


    ALL_STATS = JSON.parse(ALL_STATS)
    ALL_RIDES = JSON.parse(ALL_RIDES)
    RIDERS_PROFILE_INFO = JSON.parse(RIDERS_PROFILE_INFO)
    var ISPAUSED = false;

    
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
    for (name of NAMES){
        //calculate all ids corresponding to this rider
        ride_ids = []
        for (ride_i of Object.keys(ALL_RIDES)){
            if (ALL_RIDES[ride_i].rider==name){
                ride_ids.push(ride_i)
                ALL_RIDES[ride_i]['rider_id'] = id_counter
            }
        }			

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
    for (group_id_i of Object.keys(ALL_STATS)){
        if (ALL_STATS[group_id_i].ride_ids.length>largest_group){
            largest_group = ALL_STATS[group_id_i].ride_ids.length
            GROUP_ID_ALL = group_id_i
        }
        
    } 

    CURRENT_GROUP = GROUP_ID_ALL;
    seqGroups = rettich_motion_draw_groups()
    map.on('click', rettich_onMapClick);

    //--------------- only script function definition below ---------------//
    function rettich_motion_draw_groups(lat_lng_startidx_arr=-1,lat_lng_endidx=-1) {
        // draw all_all starting with the corresponding index. So index_set should be an array of indices with the same size as the group corresponding to CURRENT_GROUP
        ISPAUSED = false;
        if (speedupButton){ //only if toggle button already created
            playPauseButton.title = "Pause";
            document.getElementById("playPauseIcon").src = "./frontend/icons/control/PauseButton.png";
        }
        



        num_rides = ALL_STATS[CURRENT_GROUP].ride_ids.length
        let lat_lngs_rides_arr = [];
        let speed_set = Array(num_rides).fill(0)
        if (lat_lng_startidx_arr==-1){
            lat_lng_startidx_arr= Array(num_rides).fill(0)
        }
        
        for (const [ride_iterator,ride_id] of  ALL_STATS[CURRENT_GROUP].ride_ids.entries()) {
            current_ride_data = ALL_RIDES[ride_id];


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
    
        seqGroups = []
        for (const [ride_iterator,ride_id] of ALL_STATS[CURRENT_GROUP].ride_ids.entries()) {
            current_rider = RIDER_ARR[ALL_RIDES[ride_id]['rider_id']];
            current_ride_lat_lngs = lat_lngs_rides_arr[ride_iterator];
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

            seqGroups.push(L.motion.seq([poly_frame_bg]).addTo(map));
            seqGroups.push(L.motion.seq([poly_profile_pic]).addTo(map));
            seqGroups.push(L.motion.seq([poly_frame_fg]).addTo(map));
        }

        for (seqGroup of seqGroups){
            seqGroup.motionStart();
        }

        return seqGroups
    }
    
    function rettich_get_distance(p,q) {
        return Math.sqrt(Math.pow(p[0] - q[0], 2) + Math.pow(p[1] - q[1], 2))
    }
    
    function rettich_find_closest_index(arrayOP, point){
        // Calculates the index of the array of points for the closest to point, last index not checked
        let dist = 99999999.0; // just some random - for planet earth - high enough value
        let idx = -1;
    
        for (i = 0; i < arrayOP.length-1; i++){
            point_i = arrayOP[i];
            dist_i = rettich_get_distance(point_i,point)
            if (dist_i<dist){
                dist = dist_i;
                idx = i;
            }
        }
        return idx
    }
    
    function rettich_onMapClick(e) {
        lat_lng_startidx_arr = [];
        if (typeof ALL_STATS=='string'){
            ALL_STATS = JSON.parse(ALL_STATS) // i have no idea why i have to parse it here again
        }
        
        for (const [ride_iterator,ride_id] of  ALL_STATS[CURRENT_GROUP]['ride_ids'].entries()) {
            current_ride_data = ALL_RIDES[ride_id];
            idx_temp = rettich_find_closest_index(current_ride_data.latlng.data,[e.latlng.lat, e.latlng.lng]);
            lat_lng_startidx_arr.push(idx_temp);
        }
            
        
        rettich_remove_all_rides_from_map()
        seqGroups = rettich_motion_draw_groups(lat_lng_startidx_arr)
    }
    
    function rettich_remove_all_rides_from_map() { 
        for (seqGroup of seqGroups){
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

    
    function rettich_draw_medals(){
        if (typeof ALL_STATS=='string'){
        ALL_STATS = JSON.parse(ALL_STATS) // i still have no idea why i have to parse it here again
    }


    const ctx = document.getElementById('myChart');
    
    let medal_labels = ALL_STATS[CURRENT_GROUP]['riders']
    let medal_data_gold = []
    let medal_data_silver = []
    let medal_data_bronze = []
    for (const [ride_iterator, ride_id] of  ALL_STATS[CURRENT_GROUP].ride_ids.entries()) {
            medal_data_gold.push(ALL_STATS[CURRENT_GROUP]['medals'][ride_id][0])
            medal_data_silver.push(ALL_STATS[CURRENT_GROUP]['medals'][ride_id][1])
            medal_data_bronze.push(ALL_STATS[CURRENT_GROUP]['medals'][ride_id][2])
    }
    if (typeof medal_chart !== 'undefined') {
        medal_chart.destroy();
    }
    medal_chart = new Chart(ctx,
    {
        type: 'bar',
        data:
        {
            labels: medal_labels,
            datasets: [
            {
                label: 'Gold',
                data: medal_data_gold,
                borderWidth: 1,
                backgroundColor: "rgb(255,215,0)",
                stack: 'Stack 0',
            },
            {
                label: 'Silver',
                data: medal_data_silver,
                borderWidth: 1,
                backgroundColor: "rgb(208,208,208)",
                stack: 'Stack 1',
            },
            {
                label: 'Bronze',
                data: medal_data_bronze,
                borderWidth: 1,
                backgroundColor: "rgb(205,127,50)",
                stack: 'Stack 2',
            },]
        },
        options:
        {
            scales:
            {
                y: 
                {
                    stacked: true,
                    beginAtZero: true
                }
            }
        }
    });
    }
    rettich_draw_medals()

    restartButton.addEventListener('click', () => {
        rettich_motion_keys('restart');
    });

    slowdownButton.addEventListener('click', () => {
        rettich_motion_keys('slowdown');
    });

    playPauseButton.addEventListener('click', () => {
        ISPAUSED = !ISPAUSED;
        if (ISPAUSED) {
            rettich_motion_keys('pause');
            document.getElementById("playPauseIcon").src = "./frontend/icons/control/PlayButton.png";
            playPauseButton.title = 'Play';
        } else {
            rettich_motion_keys('resume');
            playPauseButton.title = 'Pause';
            document.getElementById("playPauseIcon").src = "./frontend/icons/control/PauseButton.png";
        }
    });
    
    speedupButton.addEventListener('click', () => {
        rettich_motion_keys('speedup');
    });



    function rettich_motion_keys(key) {
        for (seqGroup of seqGroups){
            if (key == "stop"){
                seqGroup.motionStop();
            }else if (key == "pause"){
                seqGroup.motionPause();
            }else if (key == "resume"){
                seqGroup.motionResume();
            }else if (key == "toggle"){
                seqGroup.motionToggle();
            }else if (key == "restart"){
                rettich_remove_all_rides_from_map()
                current_segment = $("#sel_segment").val().split(',')
                if (current_segment == ""){
                    rettich_motion_draw_groups()
                }else{
                    rettich_motion_draw_segment(current_segment[0])
                }
            }else if (key == "speedup"){
                seqGroup.getFirstLayer().motionSpeed(seqGroup.getFirstLayer().motionOptions.speed*2);
            }else if (key == "slowdown"){
                seqGroup.getFirstLayer().motionSpeed(seqGroup.getFirstLayer().motionOptions.speed*0.5);
            }
        }
    }
    
    if (typeof ALL_STATS=='string'){
        ALL_STATS = JSON.parse(ALL_STATS) // i have no idea why i have to parse it here again
    }
    

    let myTable = document.getElementById("stats_table");
    

    $(function() {
    $.each(ALL_STATS, function(i, option) {
        $('#sel_group').append($('<option/>').attr("value", [i]).text(option['group_name']));
    });
    })

    //--------------- only script function definition below ---------------//
    document.getElementById("sel_group").addEventListener("change", rettich_getComboGroup);
    function rettich_getComboGroup() {
        value = document.getElementById("sel_group").value; 
        CURRENT_GROUP=value;
        rettich_draw_medals()
        rettich_remove_all_rides_from_map()
        //clear rettich_getComboSegment
        const group_select_segment = document.getElementById('sel_segment');
        group_select_segment.innerHTML = ''; 
        group_select_segment.add(new Option('--Please choose a segment--', ""));
        seqGroups = rettich_motion_draw_groups()

        const all_rides_segment_efforts = ALL_STATS[CURRENT_GROUP]['segments'];
        $(function() {
            $.each(all_rides_segment_efforts, function(i, option) {
                abcde = [i]
                for (ride_id of ALL_STATS[CURRENT_GROUP]['ride_ids']){
                    abcde.push(option[ride_id].time)
                }
                $('#sel_segment').append($('<option/>').attr("value", abcde).text(i));
            });
        })
        
        //Clear table when selecting a new group
        const myTable = document.getElementById('stats_table');
        // Get a reference to the table body (tbody)
        const tbody = myTable.querySelector('tbody');

        // Clear the existing rows in the tbody
        while (tbody.firstChild) {
            tbody.removeChild(tbody.firstChild);
        }

        
        let bounds
        let bounds_temp
        for (const [ride_iterator, ride_id] of  ALL_STATS[CURRENT_GROUP].ride_ids.entries()){
            if (ride_iterator==0){
                bounds = L.latLngBounds(ALL_RIDES[ride_id]['latlng']['data'])
            }else{
                bounds_temp = L.latLngBounds(ALL_RIDES[ride_id]['latlng']['data'])
                bounds.extend(bounds_temp)
            }
        }
        map.fitBounds(bounds)

    }

    
    document.getElementById("sel_segment").addEventListener("change", rettich_getComboSegment);
    function rettich_getComboSegment() {
        value = document.getElementById("sel_segment").value; 

        
        seperated_values = value.split(',');
        segment_name = seperated_values[0];
        for (seqGroup of seqGroups){
            seqGroup.motionStop();
            seqGroup.removeFrom(map);
        
            if (typeof marker_start !== 'undefined'){
                map.removeLayer(marker_start);
            }

            if (typeof marker_finish !== 'undefined'){
                map.removeLayer(marker_finish);
            }
        }
        
        if (seperated_values==""){
            seqGroups = rettich_motion_draw_groups()
            map.setView([50.896537, 7.025585], 12);
        } 
        else {
            const myTable = document.getElementById('stats_table');
            let num_rides_at_current_segment = seperated_values.length-1;
            // Get a reference to the table body (tbody)
            const tbody = myTable.querySelector('tbody');

            // Clear the existing rows in the tbody
            while (tbody.firstChild) {
                tbody.removeChild(tbody.firstChild);
            }

            for (const [ride_iterator, ride_id] of  ALL_STATS[CURRENT_GROUP].ride_ids.entries()) {
                const row = tbody.insertRow();
                let cell = row.insertCell(0);
                cell.textContent = ALL_STATS[CURRENT_GROUP]['riders'][ride_iterator];
                cell = row.insertCell(1);
                cell.textContent = rettich_fancyTimeFormat(seperated_values[ride_iterator+1]);
                cell = row.insertCell(2);
                cell.textContent = Math.round(ALL_STATS[CURRENT_GROUP]['segments'][segment_name][ride_id]['speed']*100)/100;
                cell = row.insertCell(3);

                cell.textContent =  Math.round(ALL_STATS[CURRENT_GROUP]['segments'][segment_name][ride_id]['power']*100)/100;
            }
            

            rettich_motion_draw_segment(segment_name)
        }
    }

    function rettich_fancyTimeFormat(duration) {
        // Hours, minutes and seconds
        const hrs = ~~(duration / 3600);
        const mins = ~~((duration % 3600) / 60);
        const secs = ~~duration % 60;

        // Output like "1:01" or "4:03:59" or "123:03:59"
        let ret = "";

        if (hrs > 0) {
            ret += "" + hrs + ":" + (mins < 10 ? "0" : "");
        }

        ret += "" + mins + ":" + (secs < 10 ? "0" : "");
        ret += "" + secs;

        return ret;
    }

    function rettich_motion_draw_segment(seg_name) {
    
        
        start_idx_set = []
        end_idx_set = []
        for (const [ride_iterator,ride_id] of  ALL_STATS[CURRENT_GROUP].ride_ids.entries()) {
            start_idx_set.push(ALL_STATS[CURRENT_GROUP]['segments'][seg_name][ride_id]['start_index'])
            end_idx_set.push(ALL_STATS[CURRENT_GROUP]['segments'][seg_name][ride_id]['end_index'])
        }

        rettich_motion_draw_groups(start_idx_set,end_idx_set)
        marker_start = rettich_static_draw_marker(ALL_STATS[CURRENT_GROUP]['segments'][seg_name]['Segment']['start_latlng'], rettich_other_icons.start)
        marker_finish = rettich_static_draw_marker(ALL_STATS[CURRENT_GROUP]['segments'][seg_name]['Segment']['end_latlng'], rettich_other_icons.finish)
        
        bounds = L.latLngBounds(marker_start.getLatLng(), marker_finish.getLatLng())

        map.fitBounds(bounds);
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

    toggleSidebarButton.addEventListener('click', () => {
        // Überprüfe, ob die Abfrage übereinstimmt
        if (mediaQuery.matches) {
            // Der Bildschirm hat mindestens 500px Breite
            // Hier kannst du JavaScript-Code für diese Bedingung ausführen
            if (getComputedStyle(sidebar).right === '0px') {
                // Sidebar ausblenden
                sidebar.style.right =  `calc(0px - var(--sidebar-width))`;
                document.getElementById('toggleSidebarIcon').src = './frontend/icons/control/ArrowLeft.png';
                document.getElementById('buttonContainer').style.left = '50%';
            } else {
                // Sidebar einblenden
                sidebar.style.right = '0px';
                document.getElementById('toggleSidebarIcon').src = './frontend/icons/control/ArrowRight.png';
                document.getElementById('buttonContainer').style.left = 'calc(50% - 250px)';
            }
        } else {
            // Der Bildschirm hat weniger als 500px Breite
            // Hier kannst du JavaScript-Code für diese Bedingung ausführen
            if (getComputedStyle(sidebar).bottom === '0px') {
                // Sidebar ausblenden
                sidebar.style.bottom =  `calc(0px - 35%)`;
                // content.style.marginRight = '0';
                document.getElementById('toggleSidebarIcon').src = './frontend/icons/control/ArrowUp.png';
                document.getElementById('buttonContainer').style.bottom = '80px';
                // container1_1.style.marginRight = 'auto';
            } else {
                // Sidebar einblenden
                sidebar.style.bottom = '0px';
                // content.style.marginRight = `-${getComputedStyle(sidebar).getPropertyValue('var(--sidebar-width)')}`;
                // container1_1.style.marginRight = '0 auto';
                document.getElementById('toggleSidebarIcon').src = './frontend/icons/control/ArrowDown.png';
                document.getElementById('buttonContainer').style.bottom = 'calc(35% + 80px)';
                // toggleSidebarButton.querySelector('i').className = 'ti ti-layout-sidebar-right-collapse';
                
                // container1_1.style.left = `calc(500px + var(--sidebar-width))`;
            }
        }
        
    });

    // Füge einen Event Listener hinzu, um auf Änderungen der Abfrage zu reagieren
    mediaQuery.addListener(function (event) {
    if (event.matches) {
      // Die Bildschirmbreite hat sich auf mindestens 500px geändert
      // Hier kannst du JavaScript-Code für diese Bedingung ausführen
      layerControl.setPosition('bottomleft');
      document.getElementById('buttonContainer').style.left = 'calc(50% - 250px)';
      document.getElementById('buttonContainer').style.bottom = '80px';
      if (getComputedStyle(sidebar).right === '0px') {
        document.getElementById('toggleSidebarIcon').src = './frontend/icons/control/ArrowRight.png';
      } else {
        document.getElementById('toggleSidebarIcon').src = './frontend/icons/control/ArrowLeft.png';
      }
    } else {
      // Die Bildschirmbreite hat sich auf weniger als 500px geändert
      // Hier kannst du JavaScript-Code für diese Bedingung ausführen
      layerControl.setPosition('topright');
      
      document.getElementById('buttonContainer').style.left = '50%';
      if (getComputedStyle(sidebar).bottom === '0px') {
        // Sidebar expanded
        document.getElementById('buttonContainer').style.bottom = 'calc(35% + 80px)';
        document.getElementById('toggleSidebarIcon').src = './frontend/icons/control/ArrowDown.png';
      } else {
        // Sidebar collapsed
        document.getElementById('buttonContainer').style.bottom = '80px';
        document.getElementById('toggleSidebarIcon').src = './frontend/icons/control/ArrowUp.png';
      }
    }
  });
});