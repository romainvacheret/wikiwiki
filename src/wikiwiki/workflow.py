from __future__ import annotations

from pathlib import Path

from rich.console import Console
from rich.text import Text

from .index import BookResult, search
from .llama import Answer, answer
from .rendering import (
    ask_topic,
    show_answer,
    show_error,
    show_results,
    show_topic_prompt,
    show_warning,
)
from .selector import select_sources


def generate_answer(
    console: Console,
    topic: str,
    sources: list[BookResult],
    history: list[tuple[str, str]] | None = None,
    follow_up: bool = False,
) -> Answer:
    message = "Generating follow-up answer..." if follow_up else "Generating answer..."
    with console.status(f"[bold green]{message}[/]", spinner="dots"):
        return answer(topic, sources, history)


def run_follow_up_loop(
    console: Console,
    topic: str,
    sources: list[BookResult],
    initial_answer: Answer,
) -> None:
    history = [(topic, initial_answer.text)]

    while True:
        try:
            question = console.input(
                Text("Follow-up question (or /new) > ", style="bold cyan")
            ).strip()
        except EOFError:
            console.print()
            return

        if not question:
            continue
        if question == "/new":
            return

        try:
            next_answer = generate_answer(
                console,
                question,
                sources,
                history,
                follow_up=True,
            )
            show_answer(console, next_answer)
            history.append((question, next_answer.text))
        except RuntimeError as error:
            show_error(console, f"Unable to generate an answer: {error}")


def run_topic(console: Console, index_path: Path, topic: str) -> None:
    results = search(index_path, topic)
    if not results:
        show_warning(console, "No matching books found.")
        return

    show_results(console, results)
    selected_sources = select_sources(results)
    if selected_sources is None:
        return
    if not selected_sources:
        show_warning(console, "No sources selected; answer generation skipped.")
        return

    try:
        generated = generate_answer(console, topic, selected_sources)
        show_answer(console, generated)
        run_follow_up_loop(console, topic, selected_sources, generated)
    except RuntimeError as error:
        show_error(console, f"Unable to generate an answer: {error}")


def run_chat(console: Console, index_path: Path) -> None:
    while True:
        show_topic_prompt(console)
        topic = ask_topic(console)
        if topic is None:
            return
        if topic:
            run_topic(console, index_path, topic)
        console.print()
