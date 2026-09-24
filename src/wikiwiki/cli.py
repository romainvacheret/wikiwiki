from __future__ import annotations

import argparse
from pathlib import Path

from .config import load_or_prompt
from .index import rebuild, search


def main() -> None:
    parser = argparse.ArgumentParser(prog="wikiwiki")
    parser.add_argument("command", nargs="?", choices=["index"], help="manually rebuild the index")
    args = parser.parse_args()

    library = load_or_prompt()
    index_path = Path(".wikiwiki/index.sqlite3")
    print("Indexing PDFs...")
    indexed = rebuild(library, index_path)
    print(f"Indexed {indexed} book(s).")

    if args.command == "index":
        return

    print("Enter a topic, or press Ctrl-D to exit.")
    while True:
        try:
            topic = input("> ").strip()
        except EOFError:
            print()
            return
        if not topic:
            continue
        results = search(index_path, topic)
        if not results:
            print("No matching books found.")
            continue
        for number, (title, authors) in enumerate(results, start=1):
            suffix = f" — {authors}" if authors else ""
            print(f"{number}. {title}{suffix}")

