(function() {
    var lastState = {};
    var polling = false;

    var cardsContainer = document.getElementById("backup-cards-container");

    var searchInput = document.getElementById("search-input");
    searchInput.addEventListener("input", function() {
        renderCards(lastState, searchInput.value);
    });

    function showToast(message, type) {
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

    function showDeleteModal(name, onConfirm) {
        var container = document.getElementById("modal-container");
        container.innerHTML =
            '<div class="modal-content">' +
                '<div class="modal-header"><h2>Delete Backup</h2><button class="btn-icon" onclick="document.getElementById(\'modal-container\').hidden=true"><i data-lucide="x" style="width:18px;height:18px"></i></button></div>' +
                '<div class="modal-body"><p>Are you sure you want to delete the backup configuration <strong>' + escapeHtml(name) + '</strong>? This will cancel any ongoing backup and stop the scheduler.</p></div>' +
                '<div class="modal-footer">' +
                    '<button class="btn btn-secondary" onclick="document.getElementById(\'modal-container\').hidden=true">Cancel</button>' +
                    '<button class="btn btn-danger" id="confirm-delete-btn">Delete</button>' +
                '</div>' +
            '</div>';
        container.hidden = false;
        lucide.createIcons();

        document.getElementById("confirm-delete-btn").addEventListener("click", function() {
            container.hidden = true;
            onConfirm();
        });
    }

    function configName(name) {
        return encodeURIComponent(name);
    }

    window._startBackup = function(btn, name) {
        btn.disabled = true;
        apiCall("/api/backups/" + configName(name) + "/start_backup", "POST").catch(function(e) {
            btn.disabled = false;
            showErrorModal("Failed to start backup: " + e.message);
        });
    }

    window._cancelBackup = function(btn, name) {
        btn.disabled = true;
        apiCall("/api/backups/" + configName(name) + "/cancel_backup", "POST").catch(function(e) {
            btn.disabled = false;
            showErrorModal("Failed to cancel backup: " + e.message);
        });
    }

    window._startScheduler = function(btn, name) {
        btn.disabled = true;
        apiCall("/api/backups/" + configName(name) + "/start_scheduler", "POST").catch(function(e) {
            btn.disabled = false;
            showErrorModal("Failed to start scheduler: " + e.message);
        });
    }

    window._stopScheduler = function(btn, name) {
        btn.disabled = true;
        apiCall("/api/backups/" + configName(name) + "/stop_scheduler", "POST").catch(function(e) {
            btn.disabled = false;
            showErrorModal("Failed to stop scheduler: " + e.message);
        });
    }

    window._deleteBackup = function(btn, name) {
        showDeleteModal(name, function() {
            var card = btn.closest('.backup-card');
            var cardBtns = card.querySelectorAll("button");
            for (var i = 0; i < cardBtns.length; i++) { cardBtns[i].disabled = true; }
            apiCall("/api/backups/" + configName(name) + "/delete", "POST").catch(function(e) {
                for (var i = 0; i < cardBtns.length; i++) { cardBtns[i].disabled = false; }
                showErrorModal("Failed to delete backup: " + e.message);
            });
        });
    }

    function renderCard(name, backup) {
        var status = backup.status || {};
        var backupRunning = status.backup_running;
        var backupError = status.backup_error;
        var backupErrorMessage = status.backup_error_message;
        var schedRunning = status.scheduler_running;
        var schedError = status.scheduler_error;
        var schedErrorMessage = status.scheduler_error_message;
        var progress = status.backup_progress;

        var schedBadge, schedClass;
        if (schedRunning) { schedBadge = "Running"; schedClass = "badge-running"; }
        else if (schedError) { schedBadge = "Error"; schedClass = "badge-error"; } 
        else { schedBadge = "Stopped"; schedClass = "badge-stopped"; }

        var schedBadgeHtml = schedRunning
            ? '<span class="badge badge-running"><i data-lucide="clock" style="width:12px;height:12px"></i> Scheduler ' + schedBadge + '</span>'
            : '';
        var errorBadgeHtml = backupError
            ? '<span class="badge badge-error"><i data-lucide="alert-circle" style="width:12px;height:12px"></i> Error</span>'
            : '';

        var barClass = "greyed";
        if (backupRunning) { barClass = progress.percent != null ? "determinate" : "idle"; }
        var barWidth = progress.percent != null ? (progress.percent * 100) + "%" : "100%";
        var barHtml = '<div class="progress-bar-track"><div class="progress-bar-fill ' + barClass + '" style="width:' + barWidth + '"></div></div>';

        var progressMsg = "";
        if (backupRunning && progress.message) { progressMsg = '<div class="progress-message">' + escapeHtml(progress.message) + '</div>'; }

        var backupErrorHtml = (backupError && backupErrorMessage)
            ? '<div class="error-message">' + escapeHtml(backupErrorMessage) + '</div>'
            : '';
        var schedErrorHtml = (schedError && schedErrorMessage)
            ? '<div class="error-message">' + escapeHtml(schedErrorMessage) + '</div>'
            : '';

        var backupBtn;
        if (backupRunning) { backupBtn = '<button class="btn btn-secondary" onclick="window._cancelBackup(this,\'' + escapeHtml(name) + '\')"><i data-lucide="square" style="width:16px;height:16px"></i> Cancel</button>'; }
        else { backupBtn = '<button class="btn btn-primary" onclick="window._startBackup(this,\'' + escapeHtml(name) + '\')"><i data-lucide="play" style="width:16px;height:16px"></i> Backup</button>'; }

        var schedBtn = ''
        if (backup.schedule) {
            if (schedRunning) { schedBtn = '<button class="btn btn-secondary" onclick="window._stopScheduler(this,\'' + escapeHtml(name) + '\')"><i data-lucide="pause" style="width:16px;height:16px"></i> Stop Scheduler</button>'; }
            else { schedBtn = '<button class="btn btn-secondary" onclick="window._startScheduler(this,\'' + escapeHtml(name) + '\')"><i data-lucide="play" style="width:16px;height:16px"></i> Start Scheduler</button>'; }
        }

        var editBtn = '<button class="btn btn-ghost" onclick="window.location.href=\'/edit_backup/' + configName(name) + '\'"><i data-lucide="pen" style="width:16px;height:16px"></i> Edit</button>';
        var deleteBtn = '<button class="btn btn-ghost" onclick="window._deleteBackup(this,\'' + escapeHtml(name) + '\')"><i data-lucide="trash-2" style="width:16px;height:16px"></i> Delete</button>';

        return '<div class="backup-card" data-name="' + escapeHtml(name) + '">' +
            '<div class="card-header">' +
                '<h3 class="card-title">' + escapeHtml(name) + '</h3>' +
                '<div class="card-badges">' +
                    schedBadgeHtml +
                    errorBadgeHtml +
                '</div>' +
            '</div>' +
            '<div class="progress-section">' +
                barHtml +
                progressMsg +
                backupErrorHtml +
                schedErrorHtml +
            '</div>' +
            '<div class="card-actions">' +
                backupBtn +
                schedBtn +
                editBtn +
                deleteBtn +
            '</div>' +
        '</div>';
    }

    function renderCards(backups, filter) {
        var names = Object.keys(backups);
        if (filter) {
            var lower = filter.toLowerCase();
            names = names.filter(function(n) { return n.toLowerCase().indexOf(lower) !== -1; });
        }
        names.sort();

        if (names.length === 0) {
            var msg = (filter && Object.keys(backups).length > 0)
                ? '<div class="empty-state"><p>No backups match "' + escapeHtml(filter) + '"</p></div>'
                : '<div class="empty-state"><i data-lucide="archive" style="width:48px;height:48px;opacity:0.4;display:block;margin:0 auto 16px"></i><h2>No backups yet</h2><p>Create your first backup configuration to get started.</p></div>';
            cardsContainer.innerHTML = msg;
            lucide.createIcons();
            return;
        }

        var html = "";
        for (var i = 0; i < names.length; i++) {
            html += renderCard(names[i], backups[names[i]]);
        }
        cardsContainer.innerHTML = html;

        lucide.createIcons();
    }

    function detectChanges(newData, oldData) {
        for (var name in newData) {
            var old = oldData[name] || { status: {} };
            var cur = newData[name];
            var os = old.status || {};
            var cs = cur.status || {};

            if (!os.backup_error && cs.backup_error) {
                var msg = cs.backup_error_message || 'no error message';
                showToast('Backup "' + name + '" failed: ' + msg, 'error');
            }
            if (!os.backup_running && cs.backup_running) {
                showToast('Backup "' + name + '" started', 'info');
            }
            if (os.backup_running && !cs.backup_running && !cs.backup_error) {
                showToast('Backup "' + name + '" completed', 'success');
            }

            if (!os.scheduler_error && cs.scheduler_error) {
                showToast('Scheduler for "' + name + '" errored', 'error');
            }
            if (!os.scheduler_running && cs.scheduler_running) {
                showToast('Scheduler for "' + name + '" started', 'info');
            }
            if (os.scheduler_running && !cs.scheduler_running && !cs.scheduler_error) {
                showToast('Scheduler for "' + name + '" stopped', 'info');
            }
        }
    }

    function fetchBackups() {
        if (polling) return;
        polling = true;

        apiCall("/api/backups/", "GET")
            .then(function(data) {
                detectChanges(data, lastState);
                renderCards(data, searchInput.value);
                lastState = data;
            })
            .catch(function(e) {
                console.error(e);
            })
            .finally(function() {
                polling = false;
            });
    }

    fetchBackups();
    setInterval(fetchBackups, 3000);

})();
