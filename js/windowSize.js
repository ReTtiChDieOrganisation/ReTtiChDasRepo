// windowSize.js
"use strict"

const sidebar = document.getElementById('sidebar');
let mediaQuery = window.matchMedia("(min-width: 1000px)");
let sidebarExtended = true;


rettich_update_elements_to_fit_display(mediaQuery)

// Füge einen Event Listener hinzu, um auf Änderungen der Abfrage zu reagieren
mediaQuery.addListener(function (event) {
    rettich_update_elements_to_fit_display(event)
});

function rettich_update_elements_to_fit_display(event) {
    if (event.matches) {
        // Die Bildschirmbreite hat sich auf mindestens 500px geändert
        // Hier kannst du JavaScript-Code für diese Bedingung ausführen

        layerControl.setPosition('bottomleft');
        document.getElementById('buttonContainer').style.bottom = '80px';
        if (sidebarExtended === true) {
            sidebar.style.right = '0px';
            document.getElementById('toggleSidebarIcon').src = './frontend/icons/control/ArrowRight.png';
            document.getElementById('buttonContainer').style.left = 'calc(50% - 250px)';
        } else {
            sidebar.style.right =  `calc(0px - var(--sidebar-width))`;
            document.getElementById('toggleSidebarIcon').src = './frontend/icons/control/ArrowLeft.png';
            document.getElementById('buttonContainer').style.left = '50%';
        }
    } else {
        // Die Bildschirmbreite hat sich auf weniger als 500px geändert
        // Hier kannst du JavaScript-Code für diese Bedingung ausführen

        layerControl.setPosition('topright');
        document.getElementById('buttonContainer').style.left = '50%';
        if (sidebarExtended === true) {
            // Sidebar expanded
            sidebar.style.bottom = '0px';
            document.getElementById('buttonContainer').style.bottom = 'calc(35% + 80px)';
            document.getElementById('toggleSidebarIcon').src = './frontend/icons/control/ArrowDown.png';
        } else {
            // Sidebar collapsed
            sidebar.style.bottom =  `calc(0px - 35%)`;
            document.getElementById('buttonContainer').style.bottom = '80px';
            document.getElementById('toggleSidebarIcon').src = './frontend/icons/control/ArrowUp.png';
        }
    }
};