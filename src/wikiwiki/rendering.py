from __future__ import annotations

from rich.console import Console, Group
from rich.markdown import Markdown
from rich.markup import escape
from rich.panel import Panel
from rich.text import Text

from .index import BookResult, PageMatch
from .llama import Answer


def show_topic_prompt(console: Console) -> None:
    console.print(
        Panel(
            "Enter a topic, or press Ctrl-D to exit.",
            title="[bold cyan]Wikiwiki[/]",
            border_style="cyan",
        )
    )


def ask_topic(console: Console) -> str | None:
    try:
        return console.input(Text("Topic > ", style="bold cyan")).strip()
    except EOFError:
        console.print()
        return None


def show_results(console: Console, results: list[BookResult]) -> None:
    for number, result in enumerate(results, start=1):
        content = []
        chapters: dict[str, list[PageMatch]] = {}
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


def show_answer(console: Console, answer: Answer) -> None:
    console.print(
        Panel(
            Markdown(answer.text),
            title="[bold green]Answer[/]",
            border_style="green",
            padding=(1, 2),
        )
    )
    sources = [Text(source.label(), style="dim") for source in answer.sources]
    console.print(Panel(Group(*sources), title="[bold]Sources[/]", border_style="yellow"))


def show_error(console: Console, message: str) -> None:
    console.print(
        Panel(
            message,
            title="[bold red]Error[/]",
            border_style="red",
        )
    )


def show_warning(console: Console, message: str) -> None:
    console.print(Panel(message, border_style="yellow"))
