(function() {
    const KEY = "autobackup-theme";
    const toggle = document.getElementById("theme-toggle");
    const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
    let current = localStorage.getItem(KEY) || (prefersDark ? "dark" : "light");

    function apply(theme) {
        document.documentElement.setAttribute("data-theme", theme);
        toggle.innerHTML = '<i data-lucide="' + (theme === "dark" ? "sun" : "moon") + '"></i>';
        if (typeof lucide !== "undefined") lucide.createIcons();
        localStorage.setItem(KEY, theme);
        current = theme;
    }

    apply(current);
    toggle.addEventListener("click", function() {
        apply(current === "dark" ? "light" : "dark");
    });
})();

document.addEventListener("DOMContentLoaded", function() {
    if (typeof lucide !== "undefined") {
        lucide.createIcons();
    }
});
