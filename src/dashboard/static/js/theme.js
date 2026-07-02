(function() {
    var KEY = "autobackup-theme";
    var toggle = document.getElementById("theme-toggle");
    var prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
    var current = localStorage.getItem(KEY) || (prefersDark ? "dark" : "light");

    function apply(theme) {
        document.documentElement.setAttribute("data-theme", theme);
        var iconName = theme === "dark" ? "sun" : "moon";
        toggle.innerHTML = '<i data-lucide="' + iconName + '"></i> Toggle Theme';
        if (typeof lucide !== "undefined") lucide.createIcons();
        localStorage.setItem(KEY, theme);
        current = theme;
    }

    apply(current);
    toggle.addEventListener("click", function() {
        apply(current === "dark" ? "light" : "dark");
    });
})();
