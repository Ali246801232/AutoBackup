"""AutoBackup/__main__.py"""
import argparse

from dashboard import run_app


def main():
    parser = argparse.ArgumentParser(description="Automated backup tool with web dashboard")
    parser.add_argument("--configs-dir", type=str, help="Directory containing backup config files", default=None)
    args = parser.parse_args()

    run_app(args.configs_dir)


if __name__ == "__main__":
    main()