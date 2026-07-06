function escapeHtml(str) {
    var div = document.createElement("div");
    div.appendChild(document.createTextNode(str));
    return div.innerHTML;
}

function apiCall(url, method, body) {
    return fetch(url, {
        method: method || "POST",
        headers: body ? {"Content-Type": "application/json"} : {},
        body: body ? JSON.stringify(body) : undefined
    }).then(function(r) {
        if (!r.ok) return r.json().then(function(d) {
            throw new Error(d.error || "Request failed");
        });
        return r.json();
    });
}

function showErrorModal(message) {
    var container = document.getElementById("modal-container");
    container.innerHTML =
        '<div class="modal-content">' +
            '<div class="modal-header"><h2>Error</h2><button class="btn-icon" onclick="document.getElementById(\'modal-container\').hidden=true"><i data-lucide="x" style="width:18px;height:18px"></i></button></div>' +
            '<div class="modal-body"><p>' + escapeHtml(message) + '</p></div>' +
            '<div class="modal-footer"><button class="btn btn-secondary" onclick="document.getElementById(\'modal-container\').hidden=true">OK</button></div>' +
        '</div>';
    container.hidden = false;
    lucide.createIcons();
}

(function() {
    var KEY = "autobackup-theme";
    var toggle = document.getElementById("theme-toggle");
    var prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
    var current = localStorage.getItem(KEY) || (prefersDark ? "dark" : "light");

    function apply(theme) {
        document.documentElement.setAttribute("data-theme", theme);
        var iconName = theme === "dark" ? "sun" : "moon";
        toggle.innerHTML = '<i data-lucide="' + iconName + '"></i> Toggle Theme';
        lucide.createIcons();
        localStorage.setItem(KEY, theme);
        current = theme;
    }

    apply(current);
    toggle.addEventListener("click", function() {
        apply(current === "dark" ? "light" : "dark");
    });
})();
