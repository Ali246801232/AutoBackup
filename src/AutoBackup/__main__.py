"""AutoBackup/__main__.py"""
import argparse

from .logger import cleanup_logs
from AutoBackup.dashboard import run_app


def main():
    parser = argparse.ArgumentParser(description="Automated backup tool with web dashboard")
    parser.add_argument("--configs-dir", type=str, help="Directory containing backup config files", default=None)
    parser.add_argument("--start-schedulers", action="store_true", help="Auto-start all schedulers on launch")
    parser.add_argument("--start-minimized", action="store_true", help="Start with the dashboard window hidden")
    args = parser.parse_args()

    run_app(args.configs_dir, start_minimized=args.start_minimized, start_schedulers=args.start_schedulers)


if __name__ == "__main__":
    cleanup_logs()
    main()
