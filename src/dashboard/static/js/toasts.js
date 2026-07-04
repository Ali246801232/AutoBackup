(function() {
    function showToast(type, message) {
        type = type || "info";

        if (!document.hasFocus()) {
            sendNotification("AutoBackup", message);
            return;
        }

        var container = document.getElementById("toast-container");

        var toast = document.createElement("div");
        toast.className = "toast toast-" + type;

        var iconMap = { info: "info", success: "check-circle", error: "alert-circle" };
        var iconName = iconMap[type] || "info";
        var iconSvg = '<i data-lucide="' + iconName + '" style="width:18px;height:18px"></i>';

        toast.innerHTML = iconSvg +
            '<span class="toast-message">' + escapeHtml(message) + '</span>' +
            '<button class="toast-close" onclick="this.parentElement.classList.add(\'toast-out\');setTimeout(function(){this.parentElement.remove()}.bind(this),300)"><i data-lucide="x" style="width:16px;height:16px"></i></button>';

        container.appendChild(toast);
        lucide.createIcons();

        setTimeout(function() {
            toast.classList.add("toast-out");
            setTimeout(function() { toast.remove(); }, 300);
        }, 5000);
    }

    function sendNotification(title, message) {
        apiCall("/api/notify", "POST", { title: title, message: message }).catch(function(e) {
            console.error(e);
        });
    }

    function handleEvents(events_queue) {
        for (const item of events_queue) {
            showToast(item.type, item.message);
        }
    }

    function pollEventsQueue() {
        apiCall("/api/backups/events_queue", "GET")
            .then(function(data) {
                handleEvents(data);
            })
            .catch(function(e) {
                console.error(e);
            });
    }

    pollEventsQueue();
    setInterval(pollEventsQueue, 3000);
})();
