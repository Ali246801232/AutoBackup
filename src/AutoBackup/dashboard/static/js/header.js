(function() {
    var hamburgerBtn = document.getElementById("hamburger-btn");
    var dropdownMenu = document.getElementById("dropdown-menu");
    var hamburgerIcon = hamburgerBtn.querySelector("i[data-lucide]");

    hamburgerBtn.addEventListener("click", function(e) {
        e.stopPropagation();
        var isOpen = !dropdownMenu.hidden;
        dropdownMenu.hidden = isOpen;
        if (hamburgerIcon) {
            hamburgerIcon.setAttribute("data-lucide", isOpen ? "menu" : "x");
            lucide.createIcons();
        }
    });

    document.addEventListener("click", function() {
        if (!dropdownMenu.hidden) {
            dropdownMenu.hidden = true;
            if (hamburgerIcon) {
                hamburgerIcon.setAttribute("data-lucide", "menu");
                lucide.createIcons();
            }
        }
    });

    dropdownMenu.addEventListener("click", function(e) {
        e.stopPropagation();
    });

    var startupBtn = document.getElementById("startup-btn");

    startupBtn.addEventListener("click", function() {
        dropdownMenu.hidden = true;
        if (hamburgerIcon) {
            hamburgerIcon.setAttribute("data-lucide", "menu");
            lucide.createIcons();
        }
        showStartupModal();
    });

    function showStartupModal() {
        var container = document.getElementById("modal-container");
        var configsDir = document.getElementById("configs-dir-hint").textContent;
        container.innerHTML =
            '<div class="modal-content">' +
                '<div class="modal-header"><h2>Startup Settings</h2><button class="btn-icon" onclick="document.getElementById(\'modal-container\').hidden=true"><i data-lucide="x" style="width:18px;height:18px"></i></button></div>' +
                '<div class="modal-body">' +
                    '<p style="margin-bottom:12px">Configure AutoBackup to start automatically when you log in. This registers the current configs directory.</p>' +
                    '<div class="startup-configs-dir">' + escapeHtml(configsDir) + '</div>' +
                    '<div class="startup-status" id="startup-status"><i data-lucide="loader" style="width:18px;height:18px"></i> Checking...</div>' +
                '</div>' +
                '<div class="modal-footer" id="startup-modal-footer">' +
                '</div>' +
            '</div>';
        container.hidden = false;
        lucide.createIcons();

        fetchStartupStatus();
    }

    function fetchStartupStatus() {
        apiCall("/api/startup/status", "GET")
            .then(function(data) {
                updateStartupUI(data.registered, data.configs_dir);
            })
            .catch(function() {
                updateStartupUI(null);
            });
    }

    function updateStartupUI(registered, configsDir) {
        var statusEl = document.getElementById("startup-status");
        var footerEl = document.getElementById("startup-modal-footer");

        if (registered === null) {
            statusEl.className = "startup-status unavailable";
            statusEl.innerHTML = '<i data-lucide="alert-triangle" style="width:18px;height:18px"></i> Startup settings are not available on this platform.';
            footerEl.innerHTML = '<button class="btn btn-secondary" onclick="document.getElementById(\'modal-container\').hidden=true">Close</button>';
        } else if (registered) {
            statusEl.className = "startup-status registered";
            statusEl.innerHTML = '<i data-lucide="check-circle" style="width:18px;height:18px"></i> This configs directory is registered to run at startup.';
            footerEl.innerHTML =
                '<button class="btn btn-secondary" onclick="document.getElementById(\'modal-container\').hidden=true">Close</button>' +
                '<button class="btn btn-danger" id="startup-remove-btn">Remove from Startup</button>';
        } else {
            statusEl.className = "startup-status not-registered";
            statusEl.innerHTML = '<i data-lucide="x-circle" style="width:18px;height:18px"></i> This configs directory is not registered to run at startup.';
            footerEl.innerHTML =
                '<button class="btn btn-secondary" onclick="document.getElementById(\'modal-container\').hidden=true">Close</button>' +
                '<button class="btn btn-primary" id="startup-add-btn">Add to Startup</button>';
        }
        lucide.createIcons();

        var addBtn = document.getElementById("startup-add-btn");
        var removeBtn = document.getElementById("startup-remove-btn");
        if (addBtn) {
            addBtn.addEventListener("click", function() {
                addBtn.disabled = true;
                apiCall("/api/startup/add", "POST")
                    .then(function() {
                        fetchStartupStatus();
                    })
                    .catch(function(e) {
                        addBtn.disabled = false;
                        showErrorModal("Failed to add to startup: " + e.message);
                    });
            });
        }
        if (removeBtn) {
            removeBtn.addEventListener("click", function() {
                removeBtn.disabled = true;
                apiCall("/api/startup/remove", "POST")
                    .then(function() {
                        fetchStartupStatus();
                    })
                    .catch(function(e) {
                        removeBtn.disabled = false;
                        showErrorModal("Failed to remove from startup: " + e.message);
                    });
            });
        }
    }
})();
