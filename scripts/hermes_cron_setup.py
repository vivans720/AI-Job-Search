#!/usr/bin/env python3
"""
CLI helper to register or inspect the Hermes morning job hunt scheduled task.

Usage:
    python scripts/hermes_cron_setup.py --list
    python scripts/hermes_cron_setup.py --register [--schedule "0 9 * * *"]
    python scripts/hermes_cron_setup.py --remove
"""

import argparse
import subprocess
import sys
from pathlib import Path

DEFAULT_SCHEDULE = "0 9 * * *"
DEFAULT_JOB_NAME = "morning-job-hunt"
DEFAULT_PROMPT = (
    "Execute morning tech job discovery for India: discover fresh postings (<24h), "
    "score and rank against candidate profile, eliminate previously alerted duplicate postings, "
    "and create the daily job digest briefing."
)


def run_cmd(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True)


def list_cron_jobs():
    print("Checking Hermes cron tasks...")
    res = run_cmd(["hermes", "cron", "list"])
    print(res.stdout if res.stdout else res.stderr)
    return res.returncode


def register_cron_job(schedule: str = DEFAULT_SCHEDULE, name: str = DEFAULT_JOB_NAME, dry_run: bool = False):
    project_dir = str(Path(__file__).resolve().parent.parent)

    cmd = [
        "hermes",
        "cron",
        "create",
        schedule,
        DEFAULT_PROMPT,
        "--name",
        name,
        "--skill",
        "daily-digest",
        "--skill",
        "job-search",
        "--workdir",
        project_dir,
    ]

    print(f"Executing: {' '.join(cmd)}")
    if dry_run:
        print("[Dry Run] Command not executed.")
        return 0

    res = run_cmd(cmd)
    if res.returncode == 0:
        print(f"Successfully registered scheduled task '{name}' for schedule '{schedule}'.")
        print(res.stdout)
    else:
        print(f"Failed to register task (exit code {res.returncode}):")
        print(res.stderr or res.stdout)
    return res.returncode


def remove_cron_job(name: str = DEFAULT_JOB_NAME):
    cmd = ["hermes", "cron", "remove", name]
    print(f"Executing: {' '.join(cmd)}")
    res = run_cmd(cmd)
    print(res.stdout if res.stdout else res.stderr)
    return res.returncode


def main():
    parser = argparse.ArgumentParser(description="Manage Hermes Autonomous Job Hunt Cron")
    parser.add_argument("--list", action="store_true", help="List active cron tasks")
    parser.add_argument("--register", action="store_true", help="Register morning job hunt cron")
    parser.add_argument("--schedule", default=DEFAULT_SCHEDULE, help="Cron schedule expression (default: 0 9 * * *)")
    parser.add_argument("--name", default=DEFAULT_JOB_NAME, help="Job name (default: morning-job-hunt)")
    parser.add_argument("--dry-run", action="store_true", help="Print registration command without running")
    parser.add_argument("--remove", action="store_true", help="Remove morning job hunt cron")

    args = parser.parse_args()

    if args.register:
        sys.exit(register_cron_job(schedule=args.schedule, name=args.name, dry_run=args.dry_run))
    elif args.remove:
        sys.exit(remove_cron_job(name=args.name))
    else:
        sys.exit(list_cron_jobs())


if __name__ == "__main__":
    main()
