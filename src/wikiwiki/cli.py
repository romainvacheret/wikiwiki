from __future__ import annotations

import argparse
from pathlib import Path

from rich.console import Console, Group
from rich.markdown import Markdown
from rich.markup import escape
from rich.panel import Panel
from rich.text import Text

from .config import load_or_prompt
from .index import rebuild, search
from .llama import answer
from .selector import select_sources


def display_answer(console: Console, generated) -> None:
    console.print(
        Panel(
            Markdown(generated.text),
            title="[bold green]Answer[/]",
            border_style="green",
            padding=(1, 2),
        )
    )
    sources = [Text(source.label(), style="dim") for source in generated.sources]
    console.print(Panel(Group(*sources), title="[bold]Sources[/]", border_style="yellow"))


def follow_up_loop(console: Console, topic: str, selected_results, generated) -> None:
    history = [(topic, generated.text)]
    while True:
        try:
            follow_up = console.input(
                Text("Follow-up question (or /new) > ", style="bold cyan")
            ).strip()
        except EOFError:
            console.print()
            return
        if not follow_up:
            continue
        if follow_up == "/new":
            return
        try:
            with console.status("[bold green]Generating follow-up answer...[/]", spinner="dots"):
                next_answer = answer(follow_up, selected_results, history)
            display_answer(console, next_answer)
            history.append((follow_up, next_answer.text))
        except RuntimeError as error:
            console.print(
                Panel(
                    f"Unable to generate an answer: {error}",
                    title="[bold red]Error[/]",
                    border_style="red",
                )
            )


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

    while True:
        console.print(
            Panel(
                "Enter a topic, or press Ctrl-D to exit.",
                title="[bold cyan]Wikiwiki[/]",
                border_style="cyan",
            )
        )
        try:
            topic = console.input(Text("Topic > ", style="bold cyan")).strip()
        except EOFError:
            console.print()
            return
        if not topic:
            continue
        results = search(index_path, topic)
        if not results:
            console.print(Panel("No matching books found.", border_style="yellow"))
            continue
        for number, result in enumerate(results, start=1):
            content = []
            chapters = {}
            for match in result.pages:
                chapters.setdefault(match.chapter, []).append(match)
            for chapter, matches in chapters.items():
                pages = ", ".join(str(match.page) for match in matches)
                content.append(Text(f"{chapter}  ·  pages {pages}", style="bold magenta"))
                for match in matches:
                    content.append(Text(f"page {match.page}: {match.snippet}", style="dim"))
            author = f"[italic]{escape(result.authors)}[/]" if result.authors else ""
            console.print(
                Panel(
                    Group(*content),
                    title=f"[bold cyan]{number}. {escape(result.title)}[/]",
                    subtitle=author,
                    border_style="blue",
                    padding=(1, 2),
                )
            )
        try:
            selected_results = select_sources(results)
        except ImportError:
            console.print(Panel("The source selector requires Textual. Run: python3 -m pip install -e .", title="[bold red]Missing dependency[/]", border_style="red"))
            continue
        if selected_results:
            try:
                with console.status("[bold green]Generating answer...[/]", spinner="dots"):
                    generated = answer(topic, selected_results)
                display_answer(console, generated)
                follow_up_loop(console, topic, selected_results, generated)
            except RuntimeError as error:
                console.print(Panel(f"Unable to generate an answer: {error}", title="[bold red]Error[/]", border_style="red"))
        elif selected_results == []:
            console.print(Panel("No sources selected; answer generation skipped.", border_style="yellow"))
        console.print()
