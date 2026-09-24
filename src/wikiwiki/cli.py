from __future__ import annotations

import argparse
from pathlib import Path

from .config import load_or_prompt
from .index import rebuild, search
from .llama import answer


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
        for number, result in enumerate(results, start=1):
            suffix = f" — {result.authors}" if result.authors else ""
            print(f"{number}. {result.title}{suffix}")
            chapters = {}
            for match in result.pages:
                chapters.setdefault(match.chapter, []).append(match)
            for chapter, matches in chapters.items():
                pages = ", ".join(str(match.page) for match in matches)
                print(f"   {chapter} (pages {pages})")
                for match in matches:
                    print(f"      page {match.page}: {match.snippet}")
        try:
            generate = input("Generate an answer from these excerpts? [y/N] ").strip().lower()
        except EOFError:
            print()
            return
        if generate in {"y", "yes"}:
            print("\nAnswering...\n")
            try:
                generated = answer(topic, results)
                print(generated.text)
                print("\nSources:")
                for source in generated.sources:
                    print(f"  {source.label()}")
            except RuntimeError as error:
                print(f"Unable to generate an answer: {error}")
