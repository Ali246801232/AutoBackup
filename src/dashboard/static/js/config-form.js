(function() {
    var configDataEl = document.getElementById("config-data");
    var editData = configDataEl ? JSON.parse(configDataEl.textContent) : null;

    var form = document.getElementById("config-form");
    var configNameInput = document.getElementById("config-name");
    var originalName = document.getElementById("original-name").value;
    var destinationInput = document.getElementById("destination");
    var scheduleEnabled = document.getElementById("schedule-enabled");
    var scheduleRow = document.getElementById("schedule-row");
    var scheduleCount = document.getElementById("schedule-count");
    var scheduleUnit = document.getElementById("schedule-unit");
    var driveUpload = document.getElementById("drive-upload");
    var driveFolderId = document.getElementById("drive-folder-id");
    var driveFolderName = document.getElementById("drive-folder-name");
    var driveFolderLabel = document.getElementById("drive-folder-label");
    var driveFolderRow = document.getElementById("drive-folder-row");
    var submitBtn = document.getElementById("submit-btn");
    var browseDriveBtn = document.getElementById("browse-drive-btn");

    function escapeHtml(str) {
        var d = document.createElement("div");
        d.appendChild(document.createTextNode(str));
        return d.innerHTML;
    }

    // Path list helpers
    function createPathRow(value) {
        var row = document.createElement("div");
        row.className = "path-row";

        var input = document.createElement("input");
        input.type = "text";
        input.className = "form-input";
        input.placeholder = "Path...";
        if (value) input.value = value;

        var fileBtn = document.createElement("button");
        fileBtn.type = "button";
        fileBtn.className = "btn-icon";
        fileBtn.title = "Browse file";
        fileBtn.innerHTML = '<i data-lucide="file" style="width:16px;height:16px"></i>';
        fileBtn.addEventListener("click", function() {
            openFileDialog(input, "file");
        });

        var folderBtn = document.createElement("button");
        folderBtn.type = "button";
        folderBtn.className = "btn-icon";
        folderBtn.title = "Browse folder";
        folderBtn.innerHTML = '<i data-lucide="folder-open" style="width:16px;height:16px"></i>';
        folderBtn.addEventListener("click", function() {
            openFileDialog(input, "folder");
        });

        var removeBtn = document.createElement("button");
        removeBtn.type = "button";
        removeBtn.className = "btn-icon";
        removeBtn.innerHTML = '<i data-lucide="x" style="width:16px;height:16px"></i>';
        removeBtn.addEventListener("click", function() {
            row.remove();
        });

        row.appendChild(input);
        row.appendChild(fileBtn);
        row.appendChild(folderBtn);
        row.appendChild(removeBtn);
        return row;
    }

    function initPathList(listId, values) {
        var list = document.getElementById(listId);
        list.innerHTML = "";
        if (values && values.length > 0) {
            for (var i = 0; i < values.length; i++) {
                list.appendChild(createPathRow(values[i]));
            }
        }
    }

    function addPathRowFromDialog(listId, type) {
        var list = document.getElementById(listId);
        fetch("/api/file_dialog", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ type: type })
        })
            .then(function(r) { return r.json(); })
            .then(function(data) {
                if (data.path) {
                    list.appendChild(createPathRow(data.path));
                    if (typeof lucide !== "undefined") lucide.createIcons();
                }
            })
            .catch(function(e) {
                console.error("File dialog error:", e);
            });
    }

    function openFileDialog(input, type) {
        var body = { type: type || "folder" };
        if (input.value) body.initial_path = input.value;
        fetch("/api/file_dialog", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body)
        })
            .then(function(r) { return r.json(); })
            .then(function(data) {
                if (data.path) input.value = data.path;
            })
            .catch(function(e) {
                console.error("File dialog error:", e);
            });
    }

    // Drive browser
    var driveAuthenticated = false;

    function openDriveBrowser() {
        var container = document.getElementById("modal-container");

        if (!driveAuthenticated) {
            container.innerHTML =
                '<div class="modal-content">' +
                    '<div class="modal-header"><h2>Google Drive</h2><button class="btn-icon" onclick="document.getElementById(\'modal-container\').hidden=true"><i data-lucide="x" style="width:18px;height:18px"></i></button></div>' +
                    '<div class="modal-body">' +
                        '<p>You need to authenticate with Google Drive to browse folders.</p>' +
                        '<button class="btn btn-primary drive-auth-btn" id="drive-auth-btn"><i data-lucide="key" style="width:16px;height:16px"></i> Authenticate with Google Drive</button>' +
                    '</div>' +
                '</div>';
            container.hidden = false;
            if (typeof lucide !== "undefined") lucide.createIcons();

            document.getElementById("drive-auth-btn").addEventListener("click", function() {
                var btn = this;
                btn.disabled = true;
                btn.textContent = "Authenticating...";
                fetch("/api/drive/auth", { method: "POST" })
                    .then(function(r) { return r.json(); })
                    .then(function(data) {
                        if (data.error) throw new Error(data.error);
                        driveAuthenticated = true;
                        fetchDriveFolder(null);
                    })
                    .catch(function(e) {
                        btn.disabled = false;
                        btn.innerHTML = '<i data-lucide="key" style="width:16px;height:16px"></i> Authenticate with Google Drive';
                        if (typeof lucide !== "undefined") lucide.createIcons();
                        showErrorModal("Authentication failed: " + e.message);
                    });
            });
            return;
        }

        fetchDriveFolder(null);
    }

    function showDriveBrowser(folderId, folderName, children) {
        var container = document.getElementById("modal-container");

        var childrenHtml = "";
        if (children && children.length > 0) {
            for (var i = 0; i < children.length; i++) {
                childrenHtml +=
                    '<button class="drive-child-item" data-id="' + escapeHtml(children[i].id) + '" data-name="' + escapeHtml(children[i].name) + '">' +
                        '<i data-lucide="folder"></i>' +
                        '<span>' + escapeHtml(children[i].name) + '</span>' +
                    '</button>';
            }
        } else {
            childrenHtml = '<div class="drive-loading">This folder is empty</div>';
        }

        container.innerHTML =
            '<div class="modal-content">' +
                '<div class="modal-header"><h2>Google Drive</h2><button class="btn-icon" onclick="document.getElementById(\'modal-container\').hidden=true"><i data-lucide="x" style="width:18px;height:18px"></i></button></div>' +
                '<div class="modal-body">' +
                    '<div class="drive-browser-header">' +
                        '<button class="btn-icon" id="drive-up-btn" title="Go up"><i data-lucide="arrow-up" style="width:18px;height:18px"></i></button>' +
                        '<span class="drive-folder-label">' + escapeHtml(folderName) + '</span>' +
                    '</div>' +
                    '<div class="drive-children">' + childrenHtml + '</div>' +
                '</div>' +
                '<div class="modal-footer">' +
                    '<button class="btn btn-secondary" id="drive-cancel-btn">Cancel</button>' +
                    '<button class="btn btn-primary" id="drive-select-btn">Select this folder</button>' +
                '</div>' +
            '</div>';
        container.hidden = false;
        if (typeof lucide !== "undefined") lucide.createIcons();

        // Navigate into child folder
        var items = container.querySelectorAll(".drive-child-item");
        for (var i = 0; i < items.length; i++) {
            items[i].addEventListener("click", function() {
                var id = this.getAttribute("data-id");
                var name = this.getAttribute("data-name");
                fetchDriveFolder(id, name);
            });
        }

        // Go up
        document.getElementById("drive-up-btn").addEventListener("click", function() {
            fetch("/api/drive/up", { method: "POST" })
                .then(function(r) { return r.json(); })
                .then(function(data) {
                    if (data.error) throw new Error(data.error);
                    showDriveBrowser(data.folder_id, data.folder_name, data.children);
                })
                .catch(function(e) {
                    showErrorModal("Navigation failed: " + e.message);
                });
        });

        // Select folder
        document.getElementById("drive-select-btn").addEventListener("click", function() {
            selectDriveFolder(folderId, folderName);
        });

        // Cancel
        document.getElementById("drive-cancel-btn").addEventListener("click", function() {
            container.hidden = true;
        });
    }

    function fetchDriveFolder(folderId) {
        var container = document.getElementById("modal-container");
        container.innerHTML =
            '<div class="modal-content">' +
                '<div class="modal-header"><h2>Google Drive</h2><button class="btn-icon" onclick="document.getElementById(\'modal-container\').hidden=true"><i data-lucide="x" style="width:18px;height:18px"></i></button></div>' +
                '<div class="modal-body"><div class="drive-loading">Loading...</div></div>' +
            '</div>';
        container.hidden = false;

        var url = folderId ? "/api/drive/browse" : "/api/drive/browse";
        var body = folderId ? { folder_id: folderId } : {};

        fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) })
            .then(function(r) { return r.json(); })
            .then(function(data) {
                if (data.error) throw new Error(data.error);
                showDriveBrowser(data.folder_id, data.folder_name, data.children);
            })
            .catch(function(e) {
                showErrorModal("Failed to browse Drive: " + e.message);
            });
    }

    function selectDriveFolder(id, name) {
        driveFolderId.value = id;
        driveFolderName.value = name;
        driveFolderLabel.innerHTML = escapeHtml(name) + ' <span class="drive-folder-id">(ID: ' + escapeHtml(id) + ')</span>';
        driveFolderLabel.className = "drive-folder-name";
        document.getElementById("modal-container").hidden = true;
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
        if (typeof lucide !== "undefined") lucide.createIcons();
    }

    // Validation
    function clearErrors() {
        var errors = form.querySelectorAll(".form-error");
        for (var i = 0; i < errors.length; i++) {
            errors[i].classList.remove("visible");
        }
        var inputs = form.querySelectorAll(".form-input-error");
        for (var i = 0; i < inputs.length; i++) {
            inputs[i].classList.remove("form-input-error");
        }
    }

    function showFieldError(inputId, errorId) {
        var input = document.getElementById(inputId);
        var error = document.getElementById(errorId);
        if (input) input.classList.add("form-input-error");
        if (error) error.classList.add("visible");
    }

    function validate() {
        clearErrors();
        var valid = true;

        // Config name
        if (!configNameInput.value.trim()) {
            showFieldError("config-name", "error-config-name");
            valid = false;
        }

        // Sources
        var sourceInputs = document.querySelectorAll("#sources-list .form-input");
        var hasSource = false;
        for (var i = 0; i < sourceInputs.length; i++) {
            if (sourceInputs[i].value.trim()) {
                hasSource = true;
                break;
            }
        }
        if (!hasSource) {
            document.getElementById("error-sources").classList.add("visible");
            valid = false;
        }

        // Destination
        if (!destinationInput.value.trim()) {
            showFieldError("destination", "error-destination");
            valid = false;
        }

        // Drive folder
        if (driveUpload.checked && !driveFolderId.value) {
            document.getElementById("error-drive-folder").classList.add("visible");
            valid = false;
        }

        return valid;
    }

    // Submit
    function getPathValues(listId) {
        var inputs = document.querySelectorAll("#" + listId + " .form-input");
        var values = [];
        for (var i = 0; i < inputs.length; i++) {
            var v = inputs[i].value.trim();
            if (v) values.push(v);
        }
        return values;
    }

    function handleSubmit(e) {
        e.preventDefault();
        if (submitBtn.disabled) return;
        if (!validate()) return;

        var schedule = null;
        if (scheduleEnabled.checked) {
            schedule = { count: parseInt(scheduleCount.value, 10), unit: scheduleUnit.value };
        }

        var data = {
            config_name: configNameInput.value.trim(),
            sources: getPathValues("sources-list"),
            destination: destinationInput.value.trim(),
            exclusions: getPathValues("exclusions-list"),
            schedule: schedule,
            drive_upload: driveUpload.checked,
            drive_folder_id: driveUpload.checked ? driveFolderId.value : null,
            drive_folder_name: driveUpload.checked ? driveFolderName.value : null,
            last_scheduled_attempt: null
        };

        submitBtn.disabled = true;
        submitBtn.innerHTML = '<i data-lucide="loader" style="width:16px;height:16px" class="spin"></i> Saving...';

        var isEdit = !!editData;
        var url = isEdit ? "/api/backups/" + encodeURIComponent(originalName) + "/edit" : "/api/backups/new";

        fetch(url, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(data)
        })
        .then(function(r) {
            return r.json().then(function(d) {
                if (!r.ok) throw new Error(d.error || "Request failed");
                return d;
            });
        })
        .then(function() {
            window.location.href = "/";
        })
        .catch(function(e) {
            submitBtn.disabled = false;
            submitBtn.innerHTML = '<i data-lucide="save" style="width:16px;height:16px"></i> ' + (isEdit ? "Save Changes" : "Create Config");
            if (typeof lucide !== "undefined") lucide.createIcons();

            var errorEl = document.getElementById("error-submit");
            errorEl.innerHTML = e.message.replace(/\n/g, "<br>");
            errorEl.classList.add("visible");

        });
    }

    // Event listeners
    document.getElementById("add-source-file-btn").addEventListener("click", function() {
        addPathRowFromDialog("sources-list", "file");
    });
    document.getElementById("add-source-folder-btn").addEventListener("click", function() {
        addPathRowFromDialog("sources-list", "folder");
    });
    document.getElementById("add-exclusion-file-btn").addEventListener("click", function() {
        addPathRowFromDialog("exclusions-list", "file");
    });
    document.getElementById("add-exclusion-folder-btn").addEventListener("click", function() {
        addPathRowFromDialog("exclusions-list", "folder");
    });
    document.getElementById("browse-destination-btn").addEventListener("click", function() {
        openFileDialog(destinationInput);
    });
    document.getElementById("browse-drive-btn").addEventListener("click", function() {
        openDriveBrowser();
    });

    function updateScheduleDisabled() {
        if (scheduleEnabled.checked) {
            scheduleRow.classList.remove("disabled");
            scheduleCount.disabled = false;
            scheduleUnit.disabled = false;
        } else {
            scheduleRow.classList.add("disabled");
            scheduleCount.disabled = true;
            scheduleUnit.disabled = true;
        }
    }
    updateScheduleDisabled();
    scheduleEnabled.addEventListener("change", updateScheduleDisabled);

    function updateDriveFolderDisabled() {
        if (driveUpload.checked) {
            driveFolderRow.classList.remove("disabled");
            browseDriveBtn.disabled = false;
        } else {
            driveFolderRow.classList.add("disabled");
            browseDriveBtn.disabled = true;
        }
    }
    updateDriveFolderDisabled();
    driveUpload.addEventListener("change", updateDriveFolderDisabled);

    form.addEventListener("submit", handleSubmit);

    // Initialize path lists from edit data
    if (editData) {
        initPathList("sources-list", editData.sources);
        initPathList("exclusions-list", editData.exclusions);
        if (editData.drive_folder_id) {
            driveFolderId.value = editData.drive_folder_id;
            driveFolderName.value = editData.drive_folder_name || "";
            var name = editData.drive_folder_name || "Unknown";
            driveFolderLabel.innerHTML = escapeHtml(name) + ' <span class="drive-folder-id">(ID: ' + escapeHtml(editData.drive_folder_id) + ')</span>';
            driveFolderLabel.className = "drive-folder-name";
        }
    }

    // Initialize Lucide
    if (typeof lucide !== "undefined") lucide.createIcons();
})();
