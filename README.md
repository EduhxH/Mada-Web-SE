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


</div>

---

> [!WARNING]
> **This project is still under active development.**
> It is an educational vertical search engine: it indexes a controlled collection of documents. It will never call Google, Meta or Bing search APIs — every index entry and every ranking score is computed by code in this repository.

> [!NOTE]
> **Scope:** Madalena is a vertical search engine for one school. Every component — crawler, tokenizer, inverted index, ranking, query processing — is implemented from scratch, and every design decision is backed by a measurement on the real corpus.

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

**Current corpus: 1,761 documents, 18,095 unique terms** — 1,010 pages and PDFs crawled from the school site plus 751 documents synced from Moodle across 10 course subjects. Queries run in single-digit milliseconds.

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
| 🔤 **Tokenizer** | camelCase splitting (`FichaRevisoes` → `ficha revisoes`, but never `3D` → `3`), lowercasing, Unicode NFKD accent stripping, ordinal reduction (`10º` → `10`), digits kept whatever their length, and an explicit stop-word list — applied identically at index time and query time. | ✅ Done |
| 📚 **Inverted Index** | `term → {doc_id: frequency}` built in a single O(T) pass with `collections.Counter`. | ✅ Done |
| 🗄️ **SQLite Persistence** | Relational schema (`documents`, `terms`, `postings`) written transactionally; B-tree lookup on terms. | ✅ Done |
| 🔎 **Boolean AND Search** | Posting-list intersection starting from the smallest list; never rescans documents. | ✅ Done |
| 🎯 **Discipline Filter** | Restrict results to one discipline — another set intersection, applied between search and ranking. CLI `--disciplina`, dropdown on the web UI. | ✅ Done |
| ✍️ **Spelling Suggestions** | Levenshtein distance over the index vocabulary: unknown query terms get a "did you mean" suggestion, tie-broken by document frequency. Solves singular/plural without lossy stemming. | ✅ Done |
| 👁️ **Result Preview** | Hover (desktop) or tap "prever" (touch) shows metadata — discipline, type, page, word count, source file — plus a 4x longer highlighted excerpt. Lazy-loaded with a 350ms delay and client-side cache. | ✅ Done |
| 🔗 **Click to Open** | Results link straight to the source file, served by the engine — PDFs open at the exact page, files inside ZIPs are read in memory. Lookup is by document id, never by user-supplied path. | ✅ Done |
| 🪜 **Graceful Relaxation** | Three levels — all terms, then a quorum of `max(2, ⌈0.6q⌉)`, then any term — stepping down only until results appear. One counting pass yields every level. | ✅ Done |
| ✅ **Auto-correction** | Typos at edit distance 1 whose correction is backed by 3+ documents are applied automatically, with a one-click escape back to the literal query. | ✅ Done |
| 🛡️ **Hardened for Exposure** | Rate limiting (120/min, 5 login attempts per 15 min) keyed on the real client IP behind a tunnel, connection timeouts, security headers, filename sanitisation against header injection, and admin-only access to identifying statistics. Forged proxy headers are ignored unless the connection is genuinely local. | ✅ Done |
| 🌍 **Public Access via Tunnel** | Cloudflare Tunnel exposes the engine without opening a single router port — the app stays bound to `127.0.0.1` and `cloudflared` makes the outbound connection. Session cookies gain the `Secure` flag only when the request actually arrived over HTTPS, so local-network testing keeps working. | ✅ Done |
| 🔗 **Stable Public Link** | `scripts/publicar_tunel.py` starts the tunnel, captures the freshly assigned address and republishes a redirect page to GitHub Pages, so the address handed to students never changes even though the tunnel's own name does. | ✅ Done |
| 🎓 **Moodle Connector** | Authenticated session against the school's Moodle (credentials from a git-ignored `.env`), syncing 751 documents across 12 enrolled courses — resources, folders, pages and books only, never forums, quizzes or submissions. Ships with a `--diagnostico` mode that inspects real folder pages instead of guessing their HTML. | ✅ Done |
| 🔔 **New-material Detection** | `moodle --verificar` polls one page per course — about 14 requests and 13 seconds, against the hundreds of a full sync — compares the modules on offer against what is already held, and downloads only what is genuinely new. Modules that yield nothing are remembered as examined, so barren folders are not re-announced every day. | ✅ Done |
| 📰 **What's New** | Detected material surfaces in the interface as a discreet line on the search page and a dated listing at `/novidades`, each entry linking to a search for it. | ✅ Done |
| 🔄 **One-command Update** | `python main.py atualizar` crawls the site, reindexes everything and reports what changed — new, modified, removed, unchanged. The crawler writes to a staging folder and swaps atomically, so an interrupted run never damages a working corpus. | ✅ Done |
| 🔑 **Stable Document Ids** | Ids are derived from the document's origin, not from read order, so reindexing after new material arrives never shifts them — the recorded click history keeps pointing at the right documents. | ✅ Done |
| 🔁 **Morphological Expansion** | Singular/plural variants and both sides of the 1990 orthographic reform (`adotados` ↔ `adoptados`) are added to the query — rules propose, the index vocabulary decides, so nothing is ever invented. 94 spelling pairs coexist in this corpus, school documents predating the reform and students not. A length floor keeps `apto` from collapsing into `ato`. | ✅ Done |
| ⬆️ **Title Boost** | A hit in the title outweighs one in the body — the title says what a document *is*, the body only what it mentions. The weight was not chosen but swept from 0 to 10 against the evaluation set: the gain grows to 3.0 and plateaus, with no query regressing. Applied after ranking, at no extra I/O cost. | ✅ Done |
| 📊 **TF-IDF Ranking** | TF = freq / doc length, IDF = log(N / df); rare terms weigh more, long documents don't win by length alone. | ✅ Done |
| 🧪 **Oracle-verified Tests** | 402 pytest tests; the integration suite proves the index returns exactly what the naive search returns. | ✅ Done |
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
| 📏 **Measured Search Quality** | An evaluation set of 33 real queries — taken from the usage log, not invented — with ground truth pinned to a fragment of each document's origin, since origins survive reindexing and the old click history did not. `scripts/avaliar_busca.py` reports recall@1/3/10, MRR, and a per-query diff against a saved baseline, because an average that rises can hide queries that fell. Every ranking change in this project is swept and measured against it before it stays. | ✅ Done |
| 🧠 **Query Understanding** | The discipline written in the question becomes a filter ("sebenta de física" → Física-Química), words like "última" become an ordering, and both are removed from the search terms. Eleven disciplines, matched longest-alias-first so "educação física" is never read as "física". | ✅ Done |
| 🗣️ **School Vocabulary** | Students write "ficha"; the file is called "Guião de Trabalho". A hand-written synonym map bridges the gap, capped by document frequency so a rare term never expands into one covering half the collection. Only active when a discipline filter is: measured, always-on synonyms pushed "sebenta" from 1st to 8th. | ✅ Done |
| 📅 **Publication Dates** | The connector reads `Last-Modified` on every download, so "última ficha de português" can order by when material was actually published. 751 documents carry a real date; those without one sort last rather than being guessed at. | ✅ Done |
| 📑 **One Result per File** | Page-level indexing points to the exact page but made a terrible list: 54% of top-10 slots were repeated pages of one file, and for "regulamento interno" a single PDF filled all ten. Files now appear once, by their best page, with "and 60 more pages in this document" underneath. Identical content published in several places collapses too. | ✅ Done |
| 🔢 **Numbers Kept** | The minimum token length existed for stray letters; a stray digit means something here, where everything is organised by module. "módulo 3" used to lose the 3. Ordinals reduce to their number so "10 ano" matches "10º ano". | ✅ Done |
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
| requests + BeautifulSoup | HTTP fetching, HTML parsing and the Moodle session |
| numpy + fastembed | Embeddings — optional, off by default (see Known Limitations) |
| hmac / hashlib (stdlib) | Hashed invite codes, signed sessions, stable document ids |
| Cloudflare Tunnel | Public access with no inbound port open on the network |
| GitHub Pages | Stable redirect page in front of the tunnel's changing address |
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
 School website          Moodle courses           Course material
 (crawler: queue +       (authenticated sync:      (.pdf .docx .pptx .txt
  visited set +           resources, folders,       .cs .md, also inside
  robots.txt + depth)     pages, books)             .zip)
      │                        │                          │
      └────────────────────────┼──────────────────────────┘
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
      │              (web UI closed behind per-participant invite codes,
      │               every search and click logged for analytics)
      ▼
 Cloudflare Tunnel  ──  outbound only; no router port is ever opened
      │
      ▼
 GitHub Pages  ──  stable link that survives the tunnel being renamed
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
.venv\Scripts\python main.py indexar data/raw
```

Point it at `data/raw`, never at `data` — the parent holds the signing key and
the participant file, and the loader refuses them by name, but the narrower
path is the real guard.

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

**7. Publish it** (optional — needs [`cloudflared`](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/))

```bash
winget install --id Cloudflare.cloudflared -e
```

With the web UI already running on port 8080, in a second terminal:

```bash
.venv\Scripts\python scripts\publicar_tunel.py
```

This opens a Cloudflare Tunnel, reads back the address it was assigned, and
pushes a redirect page to the `gh-pages` branch. No router port is ever
opened: the app stays on `127.0.0.1` and `cloudflared` dials out.

Accounts-less tunnels get a **new random address on every start**, which is
why the redirect page exists — participants keep one bookmark, the script
repoints it. Enable GitHub Pages once (*Settings → Pages → Deploy from a
branch → `gh-pages` → `/ (root)`*) and the stable address is
`https://<user>.github.io/<repo>/`.

Pass `--sem-publicar` to open the tunnel without touching GitHub. Note that
Cloudflare offers **no uptime guarantee** on accountless tunnels; a named
tunnel bound to your own domain is the durable option.

**8. Measure the search before changing it**

```bash
.venv\Scripts\python scriptsvaliar_busca.py --detalhe
```

33 queries taken from the real usage log, each with a known-correct document.
Ground truth is a fragment of the document's *origin*, not its id: origins
survive reindexing, and the click history recorded before ids became stable
did not.

Save a baseline before a change and compare after:

```bash
.venv\Scripts\python scriptsvaliar_busca.py --guardar antes.json
```

```bash
.venv\Scripts\python scriptsvaliar_busca.py --comparar antes.json
```

The comparison lists what moved **per query**, not just the average — an
average that rises can hide queries that fell. Three plausible ideas were
rejected this way: semantic search, always-on synonyms, and indexing the
Moodle folder names. Two were kept after sweeping their parameter rather than
picking one: the title weight and the discipline partition.

**9. Keep the corpus fresh automatically**

Moodle offers no webhook to a student account, so freshness means asking —
the trick is asking cheaply. `--verificar` fetches one page per course and
compares what is on offer against what is already held:

```bash
.venv\Scripts\python main.py moodle --verificar
```

About 14 requests and 13 seconds, versus the hundreds and several minutes of
a full sync. Only genuinely new modules are downloaded.

Modules that yield no file — empty folders, dead links, formats not read —
are recorded as examined so they are not re-announced daily. On this corpus
that is 236 of 305 modules, which is exactly why the record is needed. A
full `moodle` sync still retries them, so a folder filled in later is not
lost.

To run it unattended, point the Windows Task Scheduler at
`scripts\verificar_diario.cmd`, which checks, syncs and reindexes, logging
everything to `data\verificacao.log`:

```bash
schtasks /create /tn "Madalena - verificar Moodle" /tr "%CD%\scripts\verificar_diario.cmd" /sc daily /st 07:30
```

Anything found appears in the web interface, on the search page and at
`/novidades`.

**10. Tests, benchmark and usage stats**

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
│   │   ├── local_source.py      # Local files (txt/md/cs/pdf/docx/pptx/html, zip)
│   │   └── moodle.py            # Authenticated Moodle sync (credentials from .env)
│   ├── indexing/
│   │   ├── tokenizer.py         # Normalization + tokenization rules
│   │   ├── inverted_index.py    # term → {doc_id: freq} builder
│   │   ├── storage.py           # SQLite schema and persistence
│   │   ├── atualizacao.py       # Reindex with new/changed/removed detection
│   │   └── pos.py               # Suffix-rule Portuguese POS tagger
│   ├── search/
│   │   ├── naive.py             # O(n×m) baseline and test oracle
│   │   ├── query.py             # Relaxation, discipline filter, auto-correction
│   │   ├── ranker.py            # TF-IDF + coordination factor
│   │   ├── spelling.py          # Levenshtein distance and suggestions
│   │   ├── morfologia.py        # Number and 1990-spelling variants, vocabulary-checked
│   ├── intencao.py          # Discipline and recency read from the question
│   ├── sinonimos.py         # School jargon: ficha ≈ guião ≈ exercício
│   ├── agrupamento.py       # One result per file, not per page
│   ├── hibrida.py           # Composes the pieces into one search
│   ├── semantica.py         # Embeddings (built, measured, left off - see below)
│   │   ├── seccoes.py           # Result grouping into readable sections
│   │   ├── temas.py             # Discipline-level TF-IDF topic extraction
│   │   ├── sugestoes.py         # Query suggestions (history + popular + vocab)
│   │   └── snippet.py           # Context snippet extraction
│   ├── interface/
│   │   ├── web.py               # HTTP server, routes, session handling
│   │   ├── auth.py              # Invite codes (hashed) and signed sessions
│   │   ├── protecao.py          # Rate limiting, security headers, tunnel detection
│   │   ├── preview.py           # Result preview fragments
│   │   ├── disciplina.py        # Discipline landing page
│   │   └── estatisticas.py      # Analytics page with hand-built SVG charts
│   ├── analytics/
│   │   └── uso.py               # Usage event log and aggregations
│   └── models/
│       ├── document.py          # Immutable Documento record
│       ├── novidades.py         # Record of newly-published material
│       └── classificacao.py     # Shared patterns (breaks an import cycle)
├── avaliacao/
│   ├── consultas.json           # 33 real queries with known answers
│   └── referencia.json          # current measurement, for --comparar
├── data/                        # Corpus, index, secrets — all git-ignored
├── scripts/
│   ├── comparar_busca.py        # Naive vs. indexed benchmark
│   ├── avaliar_busca.py         # Search quality against the evaluation set
│   ├── indexar_semantica.py     # Builds the embedding index
│   ├── publicar_tunel.py        # Tunnel + stable redirect page
│   ├── verificar_diario.cmd     # Scheduled Moodle check + reindex
│   └── pagina_publica.html      # Redirect page template
├── tests/{unit,integration}/    # 402 tests
├── main.py                      # CLI entry point
└── .env.example                 # Signing key and Moodle credentials
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
- [x] Authenticated Moodle connector syncing enrolled courses automatically
- [x] Hardening for public exposure: rate limits, security headers, forged-header rejection
- [x] Self-hosted deployment over Cloudflare Tunnel, with a stable redirect link
- [x] Cheap detection of newly-published Moodle material, surfaced in the interface
- [ ] Named tunnel on an owned domain (no more address churn)
- [x] Evaluation set of real queries, with per-query regression diffs
- [x] Query understanding: discipline, recency and school jargon read from the question
- [x] Publication dates from the Moodle connector
- [x] One result per file instead of one per page
- [ ] Pagination — stop hydrating every result to display twenty
- [ ] Capture the Moodle section name to tell same-named files apart
- [ ] OR queries, exact phrases, stemming
- [ ] Docker image and compose setup
- [ ] Reimplement selected modules in TypeScript and Go for comparison

---

## ⚠️ Known Limitations

- **Teams is not connected yet.** Some teachers post work there, so those
  documents are still missing. Moodle sync is done; Teams is not.
- **Moodle sync runs as one account.** The connector authenticates with the
  developer's own student credentials, kept in a git-ignored `.env`, and can
  therefore only reach the courses that account is enrolled in — the PSI
  syllabus. Extending coverage to other classes means an administrator-issued
  token, not more student passwords.
- **Scanned documents are invisible.** A photographed worksheet has no text
  layer; OCR is out of scope for now.
- **All results are hydrated before paging.** A 265-result query loads 588,000
  characters to display 20. Measured at 20 ms with a warm cache, so it is not
  today a latency problem — but it is wasted work, and pagination is the fix.
- **HTTPS only through the tunnel.** Traffic is encrypted end to end when it
  arrives via Cloudflare, and the session cookie is marked `Secure` on exactly
  those requests. Served directly over a local network with `--host 0.0.0.0`
  it is still plain HTTP, and the access code travels in clear text.
- **The public address is not permanent.** Accountless tunnels are renamed on
  every restart and carry no uptime guarantee. The redirect page hides the
  churn from participants, but a named tunnel on an owned domain is what
  actually makes the address durable.
- **No semantic matching — and embeddings were tried.** A full semantic index
  was built (10,132 fragments, a multilingual model, entirely local) and
  measured against the evaluation set. It scored *worse* than lexical search at
  every similarity threshold (MRR 0.80 vs 0.81) and did not solve the query it
  was built for: for "quando começam as aulas" the calendar does not surface,
  because a 300-character fragment of a 40-entry date table averages out to
  "calendar" rather than "start of classes". The code and the index are kept;
  the hybrid path is off. Two things would be needed to revisit it — line-level
  fragmentation and a model trained for asymmetric retrieval — and neither is
  cheap on a 2012 CPU without AVX2. The one case where it would genuinely win
  is cross-language: "regras da aula de inglês" cannot reach a file called
  "Rules For English Class" by any lexical rule.
- **Files with the same name are hard to tell apart.** Four different
  `FichaRevisoes.pdf` exist, one per module, with different content. The
  publication date now distinguishes most of them; two published the same day
  still look identical. Capturing the Moodle *section* name would fix it.
- **Topic extraction has honest residue.** Imperatives (`crie`), abbreviations
  (`trab`, `ctrl`), PDF extraction artefacts (`passagemde`) and typos in the
  source documents still surface occasionally.
- **No personal data, by design.** Grades, class lists and contacts are
  excluded from the index and always will be.

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
