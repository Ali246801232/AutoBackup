import time
import platform
import subprocess

from .logger import logger
from .registry import load_registry


WAIT_FOR_STARTUP = 420.69
system = platform.system()


def build_commands(registry: dict) -> list:
    commands = []
    for configs_dir, python_executable in registry.items():
        commands.append([
            python_executable, "-m", "AutoBackup",
            "--configs-dir", configs_dir,
            "--start-minimized", "--start-schedulers"
        ])
    return commands

def run_command(command):
    kwargs = {}

    kwargs["stdin"] = subprocess.DEVNULL
    kwargs["stdout"] = subprocess.DEVNULL
    kwargs["stderr"] = subprocess.DEVNULL
    kwargs["shell"] = False
    
    if system == "Windows":
        try:
            kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS
        except AttributeError:
            kwargs["creationflags"] = 0x08000000
    elif system in ["Linux", "Darwin"]:
        kwargs["start_new_session"] = True
        kwargs["close_fds"] = True
    else:
        raise NotImplementedError(f"Unsupported OS: {system}")

    process = subprocess.Popen(command, **kwargs)
    return process

def run_commands(commands):
    processes = []
    for cmd in commands:
        proc = run_command(cmd)
        processes.append(proc)
    return processes


def main():
    registry = load_registry()
    if not registry:
        return

    logger.debug(f"Loaded registry, waiting {WAIT_FOR_STARTUP} seconds")

    time.sleep(WAIT_FOR_STARTUP)

    commands = build_commands(registry)
    processes = run_commands(commands)

    logger.debug("Started processes, waiting for processes to end")

    for process in processes:
        process.wait()

    logger.debug("All processes ended, quitting")


if __name__ == "__main__":
    main()