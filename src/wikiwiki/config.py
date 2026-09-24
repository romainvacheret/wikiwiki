from __future__ import annotations

import json
from pathlib import Path


CONFIG_FILE = Path(".wikiwiki.json")


def load_or_prompt() -> Path:
    if CONFIG_FILE.exists():
        data = json.loads(CONFIG_FILE.read_text())
        path = Path(data["calibre_library"])
        if path.exists():
            return path

    while True:
        value = input("Path to your Calibre library: ").strip()
        path = Path(value).expanduser()
        if (path / "metadata.db").exists():
            CONFIG_FILE.write_text(json.dumps({"calibre_library": str(path.resolve())}, indent=2) + "\n")
            return path
        print("That directory does not contain metadata.db. Please try again.")

