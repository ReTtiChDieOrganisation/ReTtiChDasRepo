// script.js
document.addEventListener('DOMContentLoaded', () => {
    const sidebar = document.querySelector('.sidebar');
    const map = document.querySelector('.mapContainer');
    const buttons = map.querySelector('.buttons');
    const toggleButton = sidebar.querySelector('button');
    // const playButton = container1_1.querySelectorAll('button');

    toggleButton.addEventListener('click', () => {
        if (sidebar.style.right === '0px') {
            // Sidebar ausblenden
            sidebar.style.right =  `calc(20px - var(--sidebar-width))`;
            // content.style.marginRight = '0';
            toggleButton.innerHTML = '<';
            // container1_1.style.marginRight = 'auto';
        } else {
            // Sidebar einblenden
            sidebar.style.right = '0';
            // content.style.marginRight = `-${getComputedStyle(sidebar).getPropertyValue('var(--sidebar-width)')}`;
            toggleButton.innerHTML = '>';
            // container1_1.style.marginRight = '0 auto';
            // container1_1.style.left = `calc(500px + var(--sidebar-width))`;
        }
    });

    // playButton[2].addEventListener('click', () => {
    //     if (playButton[2].innerText === '>') {
    //         playButton[2].innerHTML = '=';
    //     } else {
    //         playButton[2].innerHTML = '>';
    //     }
    // });


});