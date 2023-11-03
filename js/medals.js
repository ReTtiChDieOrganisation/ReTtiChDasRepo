"use strict"

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
    // let medal_chart;
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
    return medal_chart;
}
let medal_chart;

medal_chart = rettich_draw_medals()

$(function() {
    $.each(ALL_STATS, function(i, option) {
        $('#sel_group').append($('<option/>').attr("value", [i]).text(option['group_name']));
    });
})

//--------------- only script function definition below ---------------//
document.getElementById("sel_group").addEventListener("change", rettich_getComboGroup);
function rettich_getComboGroup() {
    let value = document.getElementById("sel_group").value; 
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
            let abcde = [i]
            for (let ride_id of ALL_STATS[CURRENT_GROUP]['ride_ids']){
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