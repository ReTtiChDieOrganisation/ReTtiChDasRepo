if (typeof ALL_STATS=='string'){
    ALL_STATS = JSON.parse(ALL_STATS) // i have no idea why i have to parse it here again
}


let myTable = document.getElementById("stats_table");

function rettich_getComboGroup(selectObject) { 
   value = selectObject.value; 
   key = selectObject;
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
function rettich_getComboSegment(selectObject) {
   value = selectObject.value; 
   key = selectObject;

   
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