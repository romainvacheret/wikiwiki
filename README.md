# Wikiwiki

Wikiwiki is a local AI-powered RAG assistant for exploring PDF libraries. It indexes PDF books, retrieves relevant books, chapters, pages, and excerpts, and uses a local language model to generate source-grounded answers.

The project is designed as an incremental research assistant: retrieval results can be inspected and selected before they are sent to the model.

## Current features

- Calibre library support through its local `metadata.db`.
- PDF-only indexing with page-based text extraction.
- Persistent SQLite index with incremental re-indexing.
- Hybrid semantic and keyword retrieval using local embeddings and SQLite FTS.
- Book, chapter, page, and excerpt retrieval.
- Hierarchical source selection before answer generation.
- Follow-up questions over the selected source context.
- Source IDs and book/chapter/page references in RAG answers.
- Local llama.cpp model integration.
- Rich terminal output and a Textual source-selection interface.

## Requirements

- Python 3.11 or newer.
- SQLite 3 or newer, including the SQLite runtime/library required by Python’s `sqlite3` module.
- A local Calibre library containing PDF books.
- A local llama.cpp installation for answer generation.
- Enough disk space and memory for the embedding model and local language model.

Python dependencies are declared in [`pyproject.toml`](pyproject.toml):

- [PyMuPDF](https://pymupdf.readthedocs.io/) for PDF extraction.
- [sentence-transformers](https://www.sbert.net/) for local semantic embeddings.
- [Rich](https://rich.readthedocs.io/) for terminal rendering.
- [Textual](https://textual.textualize.io/) for interactive source selection.

The application uses Python’s standard-library `sqlite3` bindings, but the SQLite database engine/runtime must also be available on the system. Verify the installation with:

```bash
python3 -c "import sqlite3; print(sqlite3.sqlite_version)"
```

## Installation

From the project root:

```bash
python3 -m pip install -e .
```

The embedding model is downloaded the first time semantic indexing is used and then runs locally.

## Running the application

Start llama.cpp in a separate terminal when answer generation is needed:

```bash
./launch_llama
```

Then start Wikiwiki from the project root:

```bash
wikiwiki
```

On the first run, Wikiwiki asks for the path to the Calibre library. It indexes the PDFs automatically and stores configuration in `.wikiwiki.json` and the search index in `.wikiwiki/index.sqlite3`.

Enter a natural-language topic at the prompt. Wikiwiki displays matching books and excerpts, then opens a source selector where books, chapters, and individual pages can be selected or unselected before generating an answer.

After an answer, follow-up questions reuse the selected sources and conversation context. Enter `/new` to return to a fresh topic.

llama.cpp is only required for answer generation. Book and excerpt retrieval can run without the model server.

## Manual indexing

To manually rebuild the index:

```bash
wikiwiki index
```

Unchanged PDFs are skipped when their existing index data is still valid.

## Model configuration

The default llama.cpp endpoint is:

```text
http://127.0.0.1:8080/v1/chat/completions
```

Override it with:

```bash
WIKIWIKI_LLAMA_URL=http://127.0.0.1:8081/v1/chat/completions wikiwiki
```

The default model name is `ggml-org/gemma-4-E4B-it-GGUF:Q8_0`. Override it with:

```bash
WIKIWIKI_LLAMA_MODEL=your-model-name wikiwiki
```

## Project structure

```
wikiwiki/
├── src/wikiwiki/
│   ├── calibre.py       Calibre metadata and PDF discovery
│   ├── config.py        First-run library configuration
│   ├── embeddings.py    Local semantic embeddings
│   ├── index.py         PDF extraction, indexing, and retrieval
│   ├── llama.py         llama.cpp RAG client
│   ├── selector.py      Hierarchical source selector
│   └── cli.py           Terminal application entry point
├── tests/
├── launch_llama         llama.cpp server launcher
├── pyproject.toml
└── README.md
```

## Testing

Install development tools with:

```bash
python3 -m pip install -e ".[dev]"
```

Run the test suite with:

```bash
python3 -m pytest
```

Format and lint the project with:

```bash
ruff format .
ruff check .
```

The current tests cover SQLite retrieval, source metadata, and RAG context construction.

## Roadmap

- [ ] Improve hybrid semantic and lexical ranking.
- [ ] Add stronger chapter detection for PDFs without bookmarks.
- [ ] Validate generated citations automatically.
- [ ] Add search commands and query history.
- [ ] Support additional ebook formats.
- [ ] Consider a full-screen Textual chat interface.
