// main.js — students will add JavaScript here as features are built

// Swap every <i data-lucide="..."> for its SVG. Lucide only walks the DOM
// when asked, so anything inserted later has to call this again.
document.addEventListener("DOMContentLoaded", function () {
    if (window.lucide) {
        window.lucide.createIcons();
    }
});
