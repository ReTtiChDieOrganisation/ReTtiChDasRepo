"use strict"

if (typeof ALL_STATS=='string'){
    ALL_STATS = JSON.parse(ALL_STATS) // i have no idea why i have to parse it here again
}


let myTable = document.getElementById("stats_table");


document.getElementById("sel_segment").addEventListener("change", rettich_getComboSegment);
function rettich_getComboSegment() {
    let value = document.getElementById("sel_segment").value; 

    
    let seperated_values = value.split(',');
    let segment_name = seperated_values[0];
    for (let seqGroup of seqGroups){
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
        

        seqGroups = rettich_motion_draw_segment(segment_name);
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