# MADALENA

<div align="center">

# im back

<img src="assets/rei.jpg" width="180" alt="Rei Ayanami plush" />

[![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![SQLite](https://img.shields.io/badge/SQLite-003B57?style=for-the-badge&logo=sqlite&logoColor=white)](https://www.sqlite.org/)
[![Pytest](https://img.shields.io/badge/Pytest-0A9EDC?style=for-the-badge&logo=pytest&logoColor=white)](https://docs.pytest.org/)
[![Docker](https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white)](https://www.docker.com/)

*A search engine built from scratch for one school — no Google, no Bing, no third-party search APIs. Real crawler, real inverted index, real TF-IDF ranking, persisted in SQLite and verified against a naive-search oracle.*

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

Madalena is a vertical search engine written in Python, built for the students of one school. School material is scattered across Moodle, Teams, the public site and WhatsApp groups; Madalena puts one search box in front of all of it.

It crawls the school website (respecting `robots.txt`, rate limits and depth), ingests local course material (PDF, DOCX, PPTX, plain text, including files inside ZIP archives), tokenizes and normalizes the text, builds an inverted index with term frequencies, and persists everything to SQLite.

Queries are answered with graceful relaxation — all terms, then a quorum, then any — ranked by TF-IDF with a title boost, expanded across singular/plural variants, and grouped into sections so results stay legible.

**Current corpus: 1,797 documents, 18,135 unique terms** — 1,010 pages and PDFs crawled from the school site plus 787 documents across 11 course subjects. Queries run in single-digit milliseconds.

The engine is a **catalogue, not a repository**: results link back to where the document actually lives. Nothing is republished, and no personal data is ever indexed.

Zero search APIs. Every result is computed here.

---

## ✨ Features

| Component / Feature | Description | Status |
|---|---|---|
| 📄 **Local Document Source** | Loads `.pdf`, `.docx`, `.pptx`, `.txt`, `.md`, `.cs` — including files inside `.zip` archives, read in memory. Each PDF page and each slide becomes its own document, so results point to the exact page/slide. | ✅ Done |
| 🏷️ **Discipline Metadata** | Folder name becomes the `disciplina` field, shown as a badge in results. | ✅ Done |
| 📋 **Ingestion Report** | Per-discipline and per-format counts, plus every skipped file with its reason (unsupported format, no extractable text, build artifact, possible personal data). | ✅ Done |
| 🔒 **Personal-data Guard** | Filenames matching grade patterns (`notas`, `pauta`, `classifica`) are excluded from the index and listed explicitly in the report. | ✅ Done |
| 🔤 **Tokenizer** | camelCase splitting (`FichaRevisoes` → `ficha revisoes`), lowercasing, Unicode NFKD accent stripping, token extraction, minimum token length and an explicit stop-word list — applied identically at index time and query time. | ✅ Done |
| 📚 **Inverted Index** | `term → {doc_id: frequency}` built in a single O(T) pass with `collections.Counter`. | ✅ Done |
| 🗄️ **SQLite Persistence** | Relational schema (`documents`, `terms`, `postings`) written transactionally; B-tree lookup on terms. | ✅ Done |
| 🔎 **Boolean AND Search** | Posting-list intersection starting from the smallest list; never rescans documents. | ✅ Done |
| 🎯 **Discipline Filter** | Restrict results to one discipline — another set intersection, applied between search and ranking. CLI `--disciplina`, dropdown on the web UI. | ✅ Done |
| ✍️ **Spelling Suggestions** | Levenshtein distance over the index vocabulary: unknown query terms get a "did you mean" suggestion, tie-broken by document frequency. Solves singular/plural without lossy stemming. | ✅ Done |
| 👁️ **Result Preview** | Hover (desktop) or tap "prever" (touch) shows metadata — discipline, type, page, word count, source file — plus a 4x longer highlighted excerpt. Lazy-loaded with a 350ms delay and client-side cache. | ✅ Done |
| 🔗 **Click to Open** | Results link straight to the source file, served by the engine — PDFs open at the exact page, files inside ZIPs are read in memory. Lookup is by document id, never by user-supplied path. | ✅ Done |
| 🪜 **Graceful Relaxation** | Three levels — all terms, then a quorum of `max(2, ⌈0.6q⌉)`, then any term — stepping down only until results appear. One counting pass yields every level. | ✅ Done |
| ✅ **Auto-correction** | Typos at edit distance 1 whose correction is backed by 3+ documents are applied automatically, with a one-click escape back to the literal query. | ✅ Done |
| 🔄 **One-command Update** | `python main.py atualizar` crawls the site, reindexes everything and reports what changed — new, modified, removed, unchanged. The crawler writes to a staging folder and swaps atomically, so an interrupted run never damages a working corpus. | ✅ Done |
| 🔑 **Stable Document Ids** | Ids are derived from the document's origin, not from read order, so reindexing after new material arrives never shifts them — the recorded click history keeps pointing at the right documents. | ✅ Done |
| 🔁 **Morphological Expansion** | Singular/plural variants are added to the query — rules propose, the index vocabulary decides, so nothing is ever invented. Fixes 25% of the vocabulary being duplicated by number, without the information loss of stemming. | ✅ Done |
| ⬆️ **Title Boost** | A hit in the title outweighs one in the body — the title says what a document *is*, the body only what it mentions. Applied after ranking, at no extra I/O cost. | ✅ Done |
| 📊 **TF-IDF Ranking** | TF = freq / doc length, IDF = log(N / df); rare terms weigh more, long documents don't win by length alone. | ✅ Done |
| 🧪 **Oracle-verified Tests** | 260 pytest tests; the integration suite proves the index returns exactly what the naive search returns. | ✅ Done |
| ⏱️ **Naive vs. Indexed Benchmark** | `scripts/comparar_busca.py` times both paths on the real corpus and checks they agree. | ✅ Done |
| 💻 **CLI** | `indexar` / `buscar` subcommands plus an interactive prompt with context snippets. | ✅ Done |
| 🖥️ **Local Web UI** | Plain, dependency-free search page (standard-library HTTP server, term highlighting): `python main.py web`. | ✅ Done |
| 🕷️ **Web Crawler** | BFS over an allowed domain: deque frontier, visited set, depth limit, robots.txt (incl. Crawl-delay), rate limiting, sitemap seeding. Saves pages to disk; the original URL survives via an injected meta tag. | ✅ Done |
| 📎 **PDF Capture** | Crawled PDFs are saved too; an `_origens.json` manifest preserves each file's URL (meta tags can't be injected into a PDF), so results link to the real document at the right page. | ✅ Done |
| 🌐 **HTML Parsing** | BeautifulSoup extraction with nav/header/footer/script stripped, real `<title>` as document title. | ✅ Done |
| 🔐 **Invite-code Access** | Per-participant codes exchanged for an HMAC-signed cookie; every route but the login page is closed. Individual codes make usage measurable per person and revocable one at a time. | ✅ Done |
| 📈 **Usage Analytics** | Separate SQLite log of searches, clicks (with result position), previews and accepted suggestions. `/estatisticas` renders hand-built SVG charts — zero libraries, zero data leaving the machine. Pseudonymised: no names, no IPs. | ✅ Done |
| 💡 **Query Suggestions** | Dropdown combining the participant's own history, queries popular across the group, and real index vocabulary completing the last word. Only ever suggests queries that returned results. | ✅ Done |
| 🧭 **Discipline Landing** | Picking a subject with no query shows its characteristic topics (discipline-level TF-IDF, with a coverage ceiling that filters out boilerplate), what the class searched for, and its most-opened documents. | ✅ Done |
| 🧠 **Portuguese POS Tagging** | Suffix-rule tagger that demotes infinitives, gerunds, participles, adverbs and conjugated forms from topic candidates, guarded by exception lists so nouns like *professor*, *calor* or *velocidade* survive. Demotion only affects topic suggestions — never the index or search. | ✅ Done |
| 🗂️ **Result Sections** | Results are grouped into Horários / Fichas e materiais / Regulamentos / Páginas do site, ordered so the section holding the best hit leads. Grouping is skipped when everything falls in one section; each section links to its full listing. | ✅ Done |
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
| requests + BeautifulSoup | HTTP fetching and HTML parsing |
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

A **coordination factor** (`matched terms / query terms`) multiplies the score, so a document matching 3 of 4 terms outranks one matching a single rare term. In AND mode the factor is always 1, so it changes nothing there.

Measured in practice:

| Operation | Cost | Measured |
|---|---|---|
| Indexing (once) | O(T), T = total tokens | seconds; paid once |
| Indexed query | O(q log n + p + k log k) | 3–14 ms |
| Naive query (baseline) | O(n × m), re-reads everything | ~130 ms (**54× slower**) |
| Spelling suggestion | O(V × L²), pruned by length and early abandon | only when a term is unknown |

---

## 🏗️ Architecture Overview

```
 School website                    Course material
 (crawler: queue + visited          (.pdf .docx .pptx .txt
  set + robots.txt + depth)          .cs .md, also inside .zip)
      │                                   │
      └───────────────┬───────────────────┘
                      ▼
 Document source  ──  one Documento per page / slide / web page
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
      │            (falls back to OR when nothing matches everything)
      ▼
 Discipline filter  ──  another set intersection
      │
      ▼
 TF-IDF ranker  ──  score × coordination factor, then sort
      │
      ▼
 CLI  /  Web UI  ──  title, score, snippet, preview, click-through
                     (web UI closed behind per-participant invite codes,
                      every search and click logged for analytics)
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

**3. Crawl the school site** (respects robots.txt and rate limits)

```bash
.venv\Scripts\python main.py rastrear https://www.sefo.pt --max-paginas 300
```

**4. Index everything** (crawled pages + local course material)

```bash
.venv\Scripts\python main.py indexar data
aw
```

**5. Search from the terminal**

```bash
.venv\Scripts\python main.py buscar "criterios de avaliacao" --disciplina Matematica
```

```bash
.venv\Scripts\python main.py disciplinas
```

**6. Create access codes and start the web UI**

```bash
.venv\Scripts\python main.py participantes --criar 8
```

Codes are shown **once** and stored only as an HMAC hash. To replace a lost one:

```bash
.venv\Scripts\python main.py participantes --revogar aluno-03 --criar 1
```

```bash
.venv\Scripts\python main.py web
```

Add `--host 0.0.0.0` to accept connections from other devices. Access is
closed: every route but the login page requires a valid code.

**7. Tests, benchmark and usage stats**

```bash
.venv\Scripts\python -m pytest
```

```bash
.venv\Scripts\python scripts\comparar_busca.py "some query"
```

```bash
.venv\Scripts\python main.py estatisticas
```

---

## 📂 Project Structure

```
Mada-Web-SE/
├── app/
│   ├── crawler/
│   │   ├── web_source.py        # BFS crawler: frontier, robots.txt, sitemap, PDFs
│   │   └── local_source.py      # Local files (txt/md/cs/pdf/docx/pptx/html, zip)
│   ├── indexing/
│   │   ├── tokenizer.py         # Normalization + tokenization rules
│   │   ├── inverted_index.py    # term → {doc_id: freq} builder
│   │   └── storage.py           # SQLite schema and persistence
│   ├── search/
│   │   ├── naive.py             # O(n×m) baseline and test oracle
│   │   ├── query.py             # AND/OR search, discipline filter, suggestions
│   │   ├── ranker.py            # TF-IDF + coordination factor
│   │   ├── spelling.py          # Levenshtein distance and suggestions
│   │   └── snippet.py           # Context snippet extraction
│   ├── interface/
│   │   ├── web.py               # HTTP server, routes, session handling
│   │   ├── auth.py              # Invite codes (hashed) and signed sessions
│   │   ├── preview.py           # Result preview fragments
│   │   └── estatisticas.py      # Analytics page with hand-built SVG charts
│   ├── analytics/
│   │   └── uso.py               # Usage event log and aggregations
│   └── models/
│       └── document.py          # Immutable Documento record
├── data/                        # Corpus, index, secrets — all git-ignored
├── docs/                        # Design and study notes (pt)
├── scripts/comparar_busca.py    # Naive vs. indexed benchmark
├── tests/{unit,integration}/    # 260 tests
├── main.py                      # CLI entry point
└── .env.example                 # MADALENA_SEGREDO for deployment
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
- [x] Multi-format ingestion (docx, pptx, zip) with ingestion report
- [x] Discipline filter + batch document loading (N+1 fixed) + precomputed IDF
- [x] Title and discipline indexed; OR fallback with coordination factor
- [x] Spelling suggestions (Levenshtein) and click-through document serving
- [x] Result preview on hover/tap (metadata + long excerpt, lazy + cached)
- [x] Web crawler (frontier queue, visited set, robots.txt, rate limiting)
- [x] PDF capture from the crawled site (URL preserved via manifest)
- [x] Closed beta: invite codes, signed sessions, usage analytics with charts
- [x] Query suggestions (history + popular + vocabulary) with k-anonymity threshold
- [x] Discipline landing page with characteristic-topic extraction
- [x] POS tagging, topic stop words and lift-based scoring to clean topics
- [x] Corpus-driven noise filters: cross-discipline spread, verb detection by infinitive lookup
- [x] Result sections and readable titles for crawled documents
- [x] Tolerant search: quorum relaxation, auto-correction, title boosting
- [x] Morphological query expansion (singular/plural), validated against the index
- [x] HTML parsing with BeautifulSoup
- [ ] OR queries, exact phrases, stemming
- [ ] Docker image and compose setup
- [ ] Reimplement selected modules in TypeScript and Go for comparison

---

## ⚠️ Known Limitations

- **Moodle and Teams are not connected yet.** Course material is currently
  downloaded by hand, so it goes stale. Automatic sync needs API access
  granted by an administrator — the engine will never automate a student
  login or scrape with someone's credentials.
- **Scanned documents are invisible.** A photographed worksheet has no text
  layer; OCR is out of scope for now.
- **All results are hydrated before paging.** A 167-result query loads every
  document's text to display 20. Harmless at this size; pagination is the fix.
- **Plain HTTP.** Over a local network the access code travels in clear text;
  serving beyond localhost should go through an HTTPS tunnel.
- **No semantic matching.** Paraphrases ("how do I justify an absence") do not
  reach documents phrased differently. Morphological expansion covers number,
  spelling suggestions cover typos, but synonyms and rewording are out of reach
  without embeddings.
- **Topic extraction has honest residue.** Imperatives (`crie`), abbreviations
  (`trab`, `ctrl`), PDF extraction artefacts (`passagemde`) and typos in the
  source documents still surface occasionally.
- **No personal data, by design.** Grades, class lists and contacts are
  excluded from the index and always will be.

---

## 📚 Design Notes

Every stage is written up in `docs/`, in Portuguese, with the measurements that
drove each decision:

| | |
|---|---|
| `01`–`03` | Architecture, data structures, Big O |
| `04`–`05` | Implementation walkthrough, local web UI |
| `06` | Source architecture: site, Moodle, Teams, and the ACL model |
| `07`–`09` | Relevance, spelling correction, result preview |
| `10`–`11` | Web crawler; closed beta access and usage metrics |
| `12`–`13` | Query suggestions, discipline landing page |
| `14` | POS tagging and topic-noise removal (three rounds, with rejected rules) |
| `15`–`17` | Result sections, tolerant search, morphological expansion |
| `18`–`19` | Stable document ids; one-command corpus update |

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
