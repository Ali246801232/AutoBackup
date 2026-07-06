(function() {
    var driveAuthenticated = false;

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
        lucide.createIcons();

        var items = container.querySelectorAll(".drive-child-item");
        for (var i = 0; i < items.length; i++) {
            items[i].addEventListener("click", function() {
                var id = this.getAttribute("data-id");
                var name = this.getAttribute("data-name");
                fetchDriveFolder(id);
            });
        }

        document.getElementById("drive-up-btn").addEventListener("click", function() {
            apiCall("/api/drive/up", "POST")
                .then(function(data) {
                    showDriveBrowser(data.folder_id, data.folder_name, data.children);
                })
                .catch(function(e) {
                    showErrorModal("Navigation failed: " + e.message);
                });
        });

        document.getElementById("drive-select-btn").addEventListener("click", function() {
            selectDriveFolder(folderId, folderName);
        });

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

        var body = folderId ? { folder_id: folderId } : {};

        apiCall("/api/drive/browse", "POST", body)
            .then(function(data) {
                showDriveBrowser(data.folder_id, data.folder_name, data.children);
            })
            .catch(function(e) {
                showErrorModal("Failed to browse Drive: " + e.message);
            });
    }

    function selectDriveFolder(id, name) {
        document.getElementById("drive-folder-id").value = id;
        document.getElementById("drive-folder-name").value = name;
        var label = document.getElementById("drive-folder-label");
        label.innerHTML = escapeHtml(name) + ' <span class="drive-folder-id">(ID: ' + escapeHtml(id) + ')</span>';
        label.className = "drive-folder-name";
        document.getElementById("modal-container").hidden = true;
    }

    window.openDriveBrowser = function() {
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
            lucide.createIcons();

            document.getElementById("drive-auth-btn").addEventListener("click", function() {
                var btn = this;
                btn.disabled = true;
                btn.textContent = "Authenticating...";
                apiCall("/api/drive/auth", "POST")
                    .then(function() {
                        driveAuthenticated = true;
                        fetchDriveFolder(null);
                    })
                    .catch(function(e) {
                        btn.disabled = false;
                        btn.innerHTML = '<i data-lucide="key" style="width:16px;height:16px"></i> Authenticate with Google Drive';
                        lucide.createIcons();
                        showErrorModal("Authentication failed: " + e.message);
                    });
            });
            return;
        }

        fetchDriveFolder(null);
    };
})();
