from .backup import Backup

class Scheduler:
    def __init__(self, backup: Backup):
        self.backup: Backup = backup
