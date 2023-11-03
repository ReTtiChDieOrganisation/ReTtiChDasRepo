// sidebar.js

"use strict"

rettich_update_elements_to_fit_display(mediaQuery)


document.getElementById('toggleSidebarButton').addEventListener('click', () => {
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