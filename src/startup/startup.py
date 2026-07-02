import time
import platform
import subprocess

from .registry import load_registry


def _build_commands(registry: dict) -> list:
    commands = []
    for configs_dir, python_executable in registry.items():
        commands.append([
            python_executable, "-m", "AutoBackup",
            "--configs-dir", configs_dir,
            "--start-minimized", "--start-schedulers"
        ])
    return commands


def _run_command(command):
    system = platform.system()
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
    elif system in ["Darwin", "Linux"]:
        kwargs["start_new_session"] = True
        kwargs["close_fds"] = True
    else:
        raise NotImplementedError(f"Unsupported OS: {system}")

    process = subprocess.Popen(command, **kwargs)
    return process

def _run_commands(commands):
    processes = []
    for cmd in commands:
        proc = _run_command(cmd)
        processes.append(proc)
    return processes


def main():
    registry = load_registry()
    if not registry:
        return

    time.sleep(300)  # wait 5 minutes after startup

    commands = _build_commands(registry)
    processes = _run_commands(commands)
    for process in processes:
        process.wait()


if __name__ == "__main__":
    main()