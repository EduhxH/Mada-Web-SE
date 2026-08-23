# MADALENA

<div align="center">

# im back

<img src="assets/rei.jpg" width="180" alt="Rei Ayanami plush" />

[![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![SQLite](https://img.shields.io/badge/SQLite-003B57?style=for-the-badge&logo=sqlite&logoColor=white)](https://www.sqlite.org/)
[![Pytest](https://img.shields.io/badge/Pytest-0A9EDC?style=for-the-badge&logo=pytest&logoColor=white)](https://docs.pytest.org/)
[![Docker](https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white)](https://www.docker.com/)

*A search engine built from scratch — no Google, no Bing, no third-party search APIs. Real inverted index, real boolean search, real TF-IDF ranking, persisted in SQLite and verified against a naive-search oracle.*

[![Status](https://img.shields.io/badge/Status-In%20Development-orange?style=for-the-badge)]()

 The name **Madalena** was inspired by the name of my beloved girlfriend.

🇧🇷 The study notes in `docs/` are written in Brazilian Portuguese.

</div>

---

> [!WARNING]
> **This project is still under active development.**
> It is an educational vertical search engine: it indexes a controlled collection of documents. It will never call Google, Meta or Bing search APIs — every index entry and every ranking score is computed by code in this repository.

> [!NOTE]
> **Learning context:** Madalena is being built step by step to learn data structures, algorithms, Big O analysis, Python, SQL/SQLite, HTTP/HTML, crawling, parsing, tokenization, inverted indexes, boolean search, TF-IDF ranking and automated testing. Each stage is documented in `docs/` before and after being implemented.

---

## Table of Contents

- [About](#-about)
- [Features](#-features)
- [Tech Stack](#️-tech-stack)
- [Search Core](#-search-core-the-algorithms)
- [Architecture Overview](#️-architecture-overview)
- [Getting Started](#-getting-started)
- [Project Structure](#-project-structure)
- [Roadmap](#-roadmap)
- [Known Limitations](#️-known-limitations)
- [What I Learned](#-what-i-learned)

---

## 🧩 About

Madalena is a vertical search engine written in Python. It ingests a controlled collection of local documents (PDF, TXT, Markdown), tokenizes and normalizes the text, builds an inverted index with term frequencies, persists everything to SQLite, and answers queries with boolean AND search ranked by TF-IDF — all through a plain command-line interface.

The current test corpus is a 480-page PDF book. Indexing it takes about 40 seconds, paid once; after that every query runs in ~3 ms — about **54× faster** than the naive baseline that rescans the whole collection, and returning **exactly** the same documents (an integration test enforces this equivalence on every run).

Zero search APIs. Every result is computed here.

---

## ✨ Features

| Component / Feature | Description | Status |
|---|---|---|
| 📄 **Local Document Source** | Loads `.pdf`, `.docx`, `.pptx`, `.txt`, `.md`, `.cs` — including files inside `.zip` archives, read in memory. Each PDF page and each slide becomes its own document, so results point to the exact page/slide. | ✅ Done |
| 🏷️ **Discipline Metadata** | Folder name becomes the `disciplina` field, shown as a badge in results. | ✅ Done |
| 📋 **Ingestion Report** | Per-discipline and per-format counts, plus every skipped file with its reason (unsupported format, no extractable text, build artifact, possible personal data). | ✅ Done |
| 🔒 **Personal-data Guard** | Filenames matching grade patterns (`notas`, `pauta`, `classifica`) are excluded from the index and listed explicitly in the report. | ✅ Done |
| 🔤 **Tokenizer** | Lowercasing, Unicode NFKD accent stripping, token extraction, minimum token length and an explicit stop-word list — applied identically at index time and query time. | ✅ Done |
| 📚 **Inverted Index** | `term → {doc_id: frequency}` built in a single O(T) pass with `collections.Counter`. | ✅ Done |
| 🗄️ **SQLite Persistence** | Relational schema (`documents`, `terms`, `postings`) written transactionally; B-tree lookup on terms. | ✅ Done |
| 🔎 **Boolean AND Search** | Posting-list intersection starting from the smallest list; never rescans documents. | ✅ Done |
| 📊 **TF-IDF Ranking** | TF = freq / doc length, IDF = log(N / df); rare terms weigh more, long documents don't win by length alone. | ✅ Done |
| 🧪 **Oracle-verified Tests** | 24 pytest tests; the integration suite proves the index returns exactly what the naive search returns. | ✅ Done |
| ⏱️ **Naive vs. Indexed Benchmark** | `scripts/comparar_busca.py` times both paths on the real corpus and checks they agree. | ✅ Done |
| 💻 **CLI** | `indexar` / `buscar` subcommands plus an interactive prompt with context snippets. | ✅ Done |
| 🖥️ **Local Web UI** | Plain, dependency-free search page (standard-library HTTP server, term highlighting): `python main.py web`. | ✅ Done |
| 🕷️ **Web Crawler** | URL frontier queue, visited set, depth limit, robots.txt compliance, rate limiting. | 🔨 Planned |
| 🐳 **Docker** | Containerized indexing and search. | 🔨 Planned |

---

## 🛠️ Tech Stack

| Technology | Role |
|---|---|
| Python 3.11 | Core language for the whole engine |
| SQLite (stdlib `sqlite3`) | Persistent storage for documents, terms and postings |
| pypdf | PDF text extraction (one document per page) |
| python-docx / python-pptx | Word and PowerPoint text extraction (one document per slide) |
| zipfile (stdlib) | Reads archives in memory — no extraction to disk, no zip-slip risk |
| pytest | Automated unit and integration tests |
| dataclasses / Counter / regex / unicodedata | Standard-library building blocks — no framework |
| requests + BeautifulSoup | HTTP fetching and HTML parsing (crawler stage, planned) |
| Docker | Containerization (planned) |

---

## 🔬 Search Core (The Algorithms)

Ranking uses the classic TF-IDF weighting:

```
score(doc, query) = Σ  TF(t, doc) × IDF(t)      for each term t in query
TF(t, doc)  = freq(t, doc) / length(doc)
IDF(t)      = log(N / df(t))
```

| Variable | Meaning | Source |
|---|---|---|
| `freq(t, doc)` | How many times term `t` appears in the document | `postings` table |
| `length(doc)` | Total tokens of the document (long docs don't win by size) | `documents` table |
| `N` | Total number of documents in the collection | `COUNT(*)` |
| `df(t)` | Number of documents containing `t` (ubiquitous terms → IDF 0) | posting list size |

Measured complexity in practice (480-document corpus):

| Operation | Cost | Measured |
|---|---|---|
| Indexing (once) | O(T), T = total tokens | ~40 s (PDF extraction dominates) |
| Indexed query | O(q log n + p + k log k) | ~3 ms |
| Naive query (baseline) | O(n × m), re-reads everything | ~130 ms |

---

## 🏗️ Architecture Overview

```
Local files (.pdf / .txt / .md)
      │
      ▼
 Document source  ──  one Documento per PDF page
      │
      ▼
 Tokenizer  ──  lowercase → strip accents → tokens → stop words out
      │
      ▼
 Inverted index  ──  term → {doc_id: freq}
      │
      ▼
 SQLite  ──  documents / terms / postings (transactional)
      │
─────────── indexing above · querying below ───────────
      │
      ▼
 Query processor  ──  same tokenizer rules
      │
      ▼
 Boolean AND  ──  posting intersection, smallest list first
      │
      ▼
 TF-IDF ranker  ──  score + sort
      │
      ▼
 CLI  ──  title, score, context snippet
```

---

## 🚀 Getting Started

**1. Clone the repository**

```bash
git clone https://github.com/EduhxH/Mada-Web-SE.git
cd Mada-Web-SE
```

**2. Set up the environment**

```bash
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
```

**3. Index a collection** (a file or a whole folder)

```bash
.venv\Scripts\python main.py indexar data\raw\your-document.pdf
```

**4. Search**

```bash
.venv\Scripts\python main.py buscar "your query here"
```

```bash
.venv\Scripts\python main.py
```

Or open the local web interface at `http://127.0.0.1:8080`:

```bash
.venv\Scripts\python main.py web
```

**5. Run the tests / benchmark**

```bash
.venv\Scripts\python -m pytest
```

```bash
.venv\Scripts\python scripts\comparar_busca.py "some query"
```

---

## 📂 Project Structure

```
Mada-Web-SE/
├── app/
│   ├── crawler/
│   │   └── local_source.py      # Local document source (txt/md/pdf, 1 page = 1 doc)
│   ├── indexing/
│   │   ├── tokenizer.py         # Normalization + tokenization rules
│   │   ├── inverted_index.py    # term → {doc_id: freq} builder
│   │   └── storage.py           # SQLite schema and persistence
│   ├── search/
│   │   ├── naive.py             # O(n×m) baseline and test oracle
│   │   ├── query.py             # Boolean AND over the persisted index
│   │   ├── ranker.py            # TF-IDF scoring and ordering
│   │   └── snippet.py           # Context snippet extraction
│   ├── interface/
│   │   └── web.py               # Local web UI (stdlib HTTP server)
│   └── models/
│       └── document.py          # Immutable Documento record
├── assets/                      # README media
├── data/
│   └── raw/                     # Test corpus (git-ignored)
├── docs/                        # Study notes per stage (pt-BR)
├── scripts/
│   └── comparar_busca.py        # Naive vs. indexed benchmark
├── tests/
│   ├── unit/                    # Tokenizer, naive, index, ranker
│   └── integration/             # Full pipeline + oracle equivalence
├── main.py                      # CLI entry point
├── pytest.ini
├── requirements.txt
├── Dockerfile                   # Placeholder (Docker stage)
└── docker-compose.yml           # Placeholder (Docker stage)
```

---

## 🗺️ Roadmap

- [x] Architecture, data structures and Big O study (docs 01–03)
- [x] Immutable document model
- [x] Tokenizer with Unicode accent stripping and stop words
- [x] Naive search baseline
- [x] In-memory inverted index with frequencies
- [x] SQLite persistence (documents / terms / postings)
- [x] Boolean AND search over the persisted index
- [x] TF-IDF ranking
- [x] CLI with snippets + interactive mode
- [x] Test suite with naive-search oracle (24 tests)
- [x] Real-corpus benchmark (54× speedup measured)
- [x] Local web interface (stdlib HTTP server, no dependencies)
- [ ] Web crawler (frontier queue, visited set, robots.txt, rate limiting)
- [ ] HTML parsing with BeautifulSoup
- [ ] OR queries, exact phrases, stemming
- [ ] Docker image and compose setup
- [ ] Reimplement selected modules in TypeScript and Go for comparison

---

## ⚠️ Known Limitations

- **AND-only queries** — OR, exact phrases and stemming are future work.
- **PDF small-caps artifacts** — decorative headings like "INVERSÃO" extract as "I NVERSÃO", splitting tokens; body text is unaffected.
- **Doc lengths loaded per query** — irrelevant at hundreds of documents, worth optimizing at millions.
- **No web crawler yet** — the source is local files; the crawler stage will respect robots.txt, rate limits and allowed domains, and will never bypass authentication or CAPTCHAs.

---

## 🧠 What I Learned

- **Indexing before searching** — paying O(T) once so every future query avoids rescanning the collection, and proving the payoff with a measured 54× speedup.
- **Choosing data structures by the question they answer** — set for "have I seen this URL?", dict for "which docs contain this term?", queue for BFS crawling, tuples for immutable records, relational tables for durability.
- **Big O in practice** — why hash lookup being O(1) doesn't make the whole query O(1); the real cost follows posting-list sizes through the pipeline.
- **Unicode normalization** — NFKD decomposition and combining-mark stripping so "Programação" and "programacao" meet in the same index entry.
- **TF-IDF** — term frequency normalized by document length, inverse document frequency as a rarity weight, and why a term present everywhere carries zero information.
- **SQLite as a persistence layer** — a relational schema mirroring the in-memory dictionary, transactional writes, and B-tree O(log n) lookups versus hash O(1).
- **Testing with an oracle** — keeping the obviously-correct naive implementation alive so the optimized path can be proven equivalent on every test run.

---

## 🤝 Contributing

This is a personal learning project, but if you spot a bug or want to discuss an idea, open an issue first so we can talk before any code is written.

---

<div align="center">
  Made with 💜 by <a href="https://github.com/EduhxH">EduhxH</a>
</div>
