"""Ensure host-run scripts remain valid for the Mac's Python 3.9 runtime."""

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TARGETS = [
    ROOT / "scripts" / "import_employee_roster.py",
    ROOT / "scripts" / "update_projects.py",
]


def run() -> None:
    for target in TARGETS:
        source = target.read_text(encoding="utf-8")
        ast.parse(source, filename=str(target), feature_version=(3, 9))
        if target.name == "import_employee_roster.py":
            assert "ALTER COLUMN phone_number DROP NOT NULL" in source
    print("Python 3.9 compatibility checks passed")


if __name__ == "__main__":
    run()
