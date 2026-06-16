"""AutoBackup/__main__.py"""
import argparse

import dashboard


def main():
    parser = argparse.ArgumentParser(description="Automated backup tool with web dashboard")
    parser.add_argument("--configs-dir", type=str, help="Directory containing backup config files", default=None)
    args = parser.parse_args()

    dashboard.set_backup_configs_dir(args.configs_dir)
    dashboard.run_app()


if __name__ == "__main__":
    main()