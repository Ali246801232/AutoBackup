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
        apiCall("/api/file_dialog", "POST", { type: type })
            .then(function(data) {
                if (data.path) {
                    list.appendChild(createPathRow(data.path));
                    lucide.createIcons();
                }
            })
            .catch(function(e) {
                console.error("File dialog error:", e);
            });
    }

    function openFileDialog(input, type) {
        var body = { type: type || "folder" };
        if (input.value) body.initial_path = input.value;
        apiCall("/api/file_dialog", "POST", body)
            .then(function(data) {
                if (data.path) input.value = data.path;
            })
            .catch(function(e) {
                console.error("File dialog error:", e);
            });
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

        apiCall(url, "POST", data)
        .then(function() {
            window.location.href = "/";
        })
        .catch(function(e) {
            submitBtn.disabled = false;
            submitBtn.innerHTML = '<i data-lucide="save" style="width:16px;height:16px"></i> ' + (isEdit ? "Save Changes" : "Create Config");
            lucide.createIcons();

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
    lucide.createIcons();
})();
