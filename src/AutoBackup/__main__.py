"""AutoBackup/__main__.py"""
import argparse

import dashboard


def main(configs_dir: str = None):
    dashboard.set_backup_configs_dir(configs_dir)
    dashboard.run_app()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Automated backup tool with web dashboard")
    parser.add_argument("--configs_dir", type=str, help="Directory containing backup config files", default=None)
    args = parser.parse_args()

    main(args.configs_dir)