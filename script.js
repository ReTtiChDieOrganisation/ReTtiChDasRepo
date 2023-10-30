// script.js
document.addEventListener('DOMContentLoaded', () => {
    const sidebar = document.getElementById('sidebar');
    const toggleSidebarButton = document.getElementById('toggleSidebarButton');
    let mediaQuery = window.matchMedia("(min-width: 1000px)");
    let sidebarExtended = true;

    
    rettich_update_elements_to_fit_display(mediaQuery)
    

    toggleSidebarButton.addEventListener('click', () => {
        // Überprüfe, ob die Abfrage übereinstimmt
        if (mediaQuery.matches) {
            // Der Bildschirm hat mindestens 500px Breite
            // Hier kannst du JavaScript-Code für diese Bedingung ausführen
            if (sidebarExtended === true) {
                // Sidebar ausblenden
                sidebarExtended = false;
            } else {
                // Sidebar einblenden
                sidebarExtended = true;
            }
        } else {
            // Der Bildschirm hat weniger als 500px Breite
            // Hier kannst du JavaScript-Code für diese Bedingung ausführen
            if (sidebarExtended === true) {
                // Sidebar ausblenden
                sidebarExtended = false;
            } else {
                // Sidebar einblenden
                sidebarExtended = true;
            }
        }
        rettich_update_elements_to_fit_display(mediaQuery)
        
    });

    // Füge einen Event Listener hinzu, um auf Änderungen der Abfrage zu reagieren
    mediaQuery.addListener(function (event) {
        rettich_update_elements_to_fit_display(event)
    });

    function rettich_update_elements_to_fit_display(event) {
        if (event.matches) {
            // Die Bildschirmbreite hat sich auf mindestens 500px geändert
            // Hier kannst du JavaScript-Code für diese Bedingung ausführen

            // layerControl.setPosition('bottomleft');
            document.getElementById('buttonContainer').style.bottom = '80px';
            if (sidebarExtended === true) {
                sidebar.style.right = '0px';
                document.getElementById('toggleSidebarIcon').src = './frontend/icons/control/ArrowRight.png';
                console.log('Sidebar extended: ', sidebarExtended);
                document.getElementById('buttonContainer').style.left = 'calc(50% - 250px)';
            } else {
                sidebar.style.right =  `calc(0px - var(--sidebar-width))`;
                document.getElementById('toggleSidebarIcon').src = './frontend/icons/control/ArrowLeft.png';
                console.log('Sidebar extended: ', sidebarExtended);
                document.getElementById('buttonContainer').style.left = '50%';
            }
        } else {
            // Die Bildschirmbreite hat sich auf weniger als 500px geändert
            // Hier kannst du JavaScript-Code für diese Bedingung ausführen

            // layerControl.setPosition('topright');
            
            document.getElementById('buttonContainer').style.left = '50%';
            if (sidebarExtended === true) {
                // Sidebar expanded
                sidebar.style.bottom = '0px';
                document.getElementById('buttonContainer').style.bottom = 'calc(35% + 80px)';
                document.getElementById('toggleSidebarIcon').src = './frontend/icons/control/ArrowDown.png';
                console.log('Sidebar extended: ', sidebarExtended);
            } else {
                // Sidebar collapsed
                sidebar.style.bottom =  `calc(0px - 35%)`;
                document.getElementById('buttonContainer').style.bottom = '80px';
                document.getElementById('toggleSidebarIcon').src = './frontend/icons/control/ArrowUp.png';
                console.log('Sidebar extended: ', sidebarExtended);
            }
        }
    };
});