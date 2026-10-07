from __future__ import annotations

import argparse
from pathlib import Path

from rich.console import Console

from .config import load_or_prompt
from .index import rebuild
from .workflow import run_chat


def main() -> None:
    console = Console()
    parser = argparse.ArgumentParser(prog="wikiwiki")
    parser.add_argument("command", nargs="?", choices=["index"], help="manually rebuild the index")
    args = parser.parse_args()

    library = load_or_prompt()
    index_path = Path(".wikiwiki/index.sqlite3")
    with console.status("[bold green]Indexing PDFs...[/]", spinner="dots"):
        indexed = rebuild(library, index_path)
    console.print(f"[green]Indexed {indexed} book(s).[/]")

    if args.command == "index":
        return

    run_chat(console, index_path)
