```
  ___  __  __ _   _ _____ ____   __     _____ ____  _____ _   _ _____
 / _ \|  \/  | \ | | ____/ ___|  \ \   / /_ _|  _ \| ____| \ | |_   _|
| | | | |\/| |  \| |  _| \___ \   \ \ / / | || | | |  _| |  \| | | |
| |_| | |  | | |\  | |___ ___) |   \ V /  | || |_| | |___| |\  | | |
 \___/|_|  |_|_| \_|_____|____/     \_/  |___|____/|_____|_| \_| |_|
```

> **_omnes vident_** — _Latin: "all see."_
> A real-time, AI-refined window into every breaking story on Earth, rendered on a living 3D globe.

`[ Python 3.12 ]` `[ FastAPI ]` `[ React 18 + TypeScript ]` `[ Three.js / R3F ]` `[ Firestore ]` `[ OpenAI GPT-4o-mini ]` `[ Cloud Run ]` `[ Vercel ]`

---

## Table of Contents

1. [What is OmnesVident?](#what-is-omnesvident)
2. [System Architecture](#system-architecture)
3. [The ETL Pipeline](#the-etl-pipeline)
4. [Tech Stack — In Depth](#tech-stack--in-depth)
5. [API Surface](#api-surface)
6. [Use Cases](#use-cases)
7. [Roadmap & Extensibility](#roadmap--extensibility)
8. [Getting Started](#getting-started)
9. [Deployment](#deployment)
10. [Project Layout](#project-layout)

---

## What is OmnesVident?

**OmnesVident** is a distributed, AI-augmented news discovery platform that transforms the firehose of global headlines into a single, navigable, spatial experience.

Most news apps give you an endless feed. OmnesVident gives you the **planet**.

- **A rotating 3D Earth** is the primary interface. Every story is a neon blip pinned to the exact coordinates where it happened.
- **Seven taxonomies** (`World`, `Politics`, `Science & Tech`, `Business`, `Health`, `Entertainment`, `Sports`) let you slice reality by lens.
- **Breaking-news detection** runs every story through an AI urgency model — truly breaking stories (active conflicts, disasters, decisive elections) pulse red and surface into a dedicated carousel.
- **Region-aware queries** let you zoom from `World → US → California` and see only the stories with ground truth in that polygon.
- **Every story is AI-refined**: translated to English when needed, geo-located to a precise lat/lng, classified, and scored — before it ever hits your screen.

The result is not a feed. It is a **geospatial situational-awareness console**, built for people who need to understand _where_ the world is happening right now.

---

## System Architecture

OmnesVident is a **four-layer distributed system**. Each layer has one job and exposes a clean interface to the next.

```
┌────────────────────────────────────────────────────────────────────────────┐
│                            LAYER 4 — Presentation                          │
│   React 18 + TypeScript + Vite + Three.js / R3F + TailwindCSS              │
│   ▸ 3D globe w/ neon blips   ▸ breaking-news carousel   ▸ sidebar filters  │
│                              ▸ hosted on Vercel                            │
└────────────────────────────────────────────────────────────────────────────┘
                                      ▲
                                      │  REST / JSON  (TanStack Query)
                                      │
┌────────────────────────────────────────────────────────────────────────────┐
│                            LAYER 3 — API & Storage                         │
│   FastAPI + Pydantic + Gunicorn/Uvicorn on Cloud Run                       │
│   ▸ /stories  ▸ /regions  ▸ /tasks/ingest  ▸ /tasks/refine-all             │
│   ▸ Firestore (prod)  ▸ SQLite fallback (dev)                              │
└────────────────────────────────────────────────────────────────────────────┘
                                      ▲
                                      │  writes master_news docs
                                      │
┌────────────────────────────────────────────────────────────────────────────┐
│                         LAYER 2 — Intelligence Layer                       │
│   AIRefiner (OpenAI gpt-4o-mini)  ▸  AIGeoRefiner (Vertex AI Gemini)       │
│   ▸ script detection   ▸ batch translation   ▸ geo-resolution              │
│   ▸ fuzzy dedup (thefuzz)   ▸ 7-way classifier   ▸ breaking + heat score   │
└────────────────────────────────────────────────────────────────────────────┘
                                      ▲
                                      │  raw_news_buffer docs
                                      │
┌────────────────────────────────────────────────────────────────────────────┐
│                          LAYER 1 — Ingestion Engine                        │
│   8 async providers, fan-in scheduler, canonical normalizer                │
│   NewsData · GNews · MediaStack · Currents · NewsCatcher · WorldNews       │
│                          · Reddit · RSS                                    │
│                triggered every 15 min by Cloud Scheduler                   │
└────────────────────────────────────────────────────────────────────────────┘
```

---

## The ETL Pipeline

This is the beating heart of OmnesVident. A story's journey from wire to globe:

### 1. `Extract` — Fan-out across 8 providers

Every 15 minutes, Cloud Scheduler hits `POST /tasks/ingest`. The ingestion engine then fans out **concurrently** to:

| Provider | Type | Purpose |
|----------|------|---------|
| `newsdata.io` | REST API | Broad global coverage |
| `GNews` | REST API | Aggregator of mainstream outlets |
| `MediaStack` | REST API | Long-tail international sources |
| `Currents` | REST API | Category-tagged wire feed |
| `NewsCatcher` | REST API | Indexed historical + real-time |
| `WorldNews` | REST API | English-language global |
| `Reddit` | Unauth PRAW | Crowd signal, r/worldnews + regionals |
| `RSS` | feedparser | Outlet-native feeds (BBC, Reuters, etc.) |

Each provider implements a common `BaseProvider` contract (`fetch(region) -> list[RawStoryIn]`), so adding a ninth provider is a single-file change.

### 2. `Transform` — Normalize → Dedupe → Classify → Refine

Incoming payloads have eight different schemas. The **normalizer** maps every provider into a single canonical `RawStoryIn`:

```python
RawStoryIn(
    title: str,
    summary: str | None,
    url: str,
    source: str,
    published_at: datetime,
    country_code: str | None,
    region_code: str | None,
)
```

Then the pipeline applies, in order:

1. **Deduplication** — `thefuzz` token-set ratio across a rolling window of recent titles (threshold 88). Drops reposts and near-identical wire copies.
2. **Classification** — rule-based 7-class classifier with keyword lattices per category. Fallback `WORLD`.
3. **Buffering** — normalized `RawStoryIn` rows are persisted to the `raw_news_buffer` Firestore collection.
4. **AI Refinement** (the expensive pass — runs async after buffering):
   - **Script detection** routes non-Latin titles (CJK, Cyrillic, Arabic, Devanagari) through a **batch translator** call to `gpt-4o-mini`.
   - **Geo-resolution** — a second prompt asks the LLM to output `{lat, lng, confidence}` for the story's dateline. Results are cached in `GeocodingCache` keyed by city+country.
   - **Breaking-news detection** — the refinement prompt also returns `is_breaking: bool` and `heat_score: 1–100` for every story. Thresholds: active conflict, mass casualty, head-of-state action, decisive election, major disaster → `is_breaking=true`.
5. **Promotion** — refined stories become `master_news` docs with the full `extra` envelope: `{latitude, longitude, geo_confidence, geo_source, category, is_breaking, heat_score, original_title}`.

### 3. `Load` — Firestore primary, SQLite fallback

- **Production**: `master_news` is a Firestore collection; all API reads go through `query_master_by_timestamp()` with composite indexes on `(published_at, category, country_code)`.
- **Dev**: the same repository interface transparently falls back to SQLite (`omnesvident.db`) so you can develop offline.

### 4. `Serve` — REST to the globe

The frontend fetches `/stories?region=US-CA&category=POLITICS&start_date=...&end_date=...&limit=1000`. TanStack Query deduplicates and caches; the globe renders blips keyed by `(lat, lng, category)`.

---

## Tech Stack — In Depth

### Backend

| Layer | Tech | Why |
|-------|------|-----|
| Runtime | **Python 3.12** | Modern typing, fast asyncio |
| Web framework | **FastAPI** + **Pydantic v2** | Async-first, OpenAPI out of the box, type-safe |
| ASGI server | **Uvicorn** (dev) / **Gunicorn + UvicornWorker** (prod) | Cloud Run expects a single long-running worker |
| ORM | **SQLModel** | Pydantic + SQLAlchemy unified — one class, two worlds |
| HTTP client | **httpx** (async) | Connection pooling across 8 concurrent provider calls |
| RSS | **feedparser** | Battle-tested Atom/RSS 2.0 parser |
| Fuzzy dedup | **thefuzz\[speedup\]** | C-accelerated Levenshtein |
| Primary store | **Firestore** | Serverless, schemaless, strongly consistent |
| AI — geo + breaking | **OpenAI gpt-4o-mini** | Best cost/quality for structured extraction |
| AI — fallback | **Vertex AI Gemini** | Used by `AIGeoRefiner` path when set up |
| Container | **Docker** → **Cloud Run** (managed) | Scale-to-zero, pay-per-request |
| Scheduler | **Cloud Scheduler** | Cron for `/tasks/ingest` every 15 min |

### Frontend

| Layer | Tech | Why |
|-------|------|-----|
| Framework | **React 18** + **TypeScript** | Strict types across the globe's data paths |
| Bundler | **Vite 5** | <1s HMR, ES module dev server |
| 3D engine | **Three.js 0.163** + **React Three Fiber** + **drei** | Declarative R3F component graph around a WebGL globe |
| Data | **TanStack Query 5** | Stale-while-revalidate cache, automatic dedup |
| Routing | **React Router 6** | `/region/:code` deep links |
| Styling | **TailwindCSS 3** | Design-token-driven; neon category palette |
| Geo data | **world-atlas**, **us-atlas**, **topojson-client** | TopoJSON polygons for country/state outlines |
| Hosting | **Vercel** | Edge CDN, automatic preview deploys |

### Data Sources

8 providers, 20+ countries, ~200 regions tracked in [`ingestion_engine/regions_to_track.json`](ingestion_engine/regions_to_track.json). Every source is pluggable — drop a new file in `providers/` that subclasses `BaseProvider` and the scheduler picks it up.

---

## API Surface

All endpoints are documented live via OpenAPI at `/docs` on your running API.

| Method | Path | Purpose |
|--------|------|---------|
| `GET`  | `/stories` | Paginated master stories, filterable by `region`, `category`, `start_date`, `end_date` |
| `GET`  | `/stories/by-region/{region}` | Region-scoped feed |
| `GET`  | `/regions` | Available region codes and human labels |
| `POST` | `/tasks/ingest` | Trigger ingestion fan-out (requires `X-Ingest-Token`) |
| `POST` | `/tasks/refine-all` | Re-run AI refinement on all `master_news` docs |
| `GET`  | `/health` | Liveness probe |

---

## Use Cases

OmnesVident was built for anyone who needs **spatial awareness of the news**:

- **Journalists & editors** — spot a cluster of blips forming over a region before the rest of the desk does. Use the breaking carousel as a morning triage dashboard.
- **Intelligence & geopolitical analysts** — correlate events across categories (Politics + Business blips over the same coordinate = sanctions story forming).
- **Researchers & academics** — export filtered date-ranged datasets for conflict studies, epidemic tracking, or election monitoring.
- **Disaster-response coordinators** — isolate Health + breaking-news blips in a region during active incidents.
- **Educators** — teach current events in geography, civics, or international-relations classrooms with a live, spinning globe.
- **Curious humans** — step off the algorithmic feed treadmill and browse the world the way a cartographer would.

---

## Roadmap & Extensibility

OmnesVident is built to grow. The seams are deliberate.

### Near-term extensions

- **Sentiment & tone scoring** — extend the AI refinement prompt to emit `sentiment: -1..1` per story; color blips by sentiment heatmap.
- **Entity extraction** — `people`, `orgs`, `events` surfaces for cross-story navigation.
- **WebSocket push** — swap polling for a long-lived socket so the globe blips appear the moment a story lands in `master_news`.
- **Time-lapse playback** — scrub a slider to replay the last 24h of news on the globe.
- **User accounts** — saved regions, watchlists, and breaking-story email/push alerts.
- **Multi-language UI** — the backend already stores `original_title`; expose it when the user's locale matches.

### Platform seams (where to plug in)

| Want to… | Touch this |
|----------|-----------|
| Add a new news provider | `ingestion_engine/providers/` — implement `BaseProvider` |
| Add a new category | `intelligence_layer/classifier.py` + `frontend_portal/.../NewsCard.tsx` `CATEGORY_META` |
| Swap the AI model | `intelligence_layer/refiner.py` — `_OPENAI_MODEL` const |
| Add a new region | `ingestion_engine/regions_to_track.json` |
| Change blip colors | `frontend_portal/src/components/visualizer/Marker.tsx` `CATEGORY_COLORS` |
| Add a new endpoint | `api_storage/routes.py` |

---

## Getting Started

### Prerequisites

- **Python 3.12+**
- **Node 18+** + **npm**
- _(optional)_ Google Cloud SDK (`gcloud`) — only for deploying
- _(optional)_ Firestore credentials — only for production mode; dev defaults to SQLite

### 1. Clone & install

```bash
git clone https://github.com/<you>/OmnesVident.git
cd OmnesVident

make setup            # installs Python + frontend deps in one shot
```

This runs `pip install -r requirements.txt` in `.venv/` and `npm install` in `frontend_portal/`.

### 2. Configure secrets

Create a `.env` in the repo root:

```bash
# Required for real ingestion — each is free-tier eligible
NEWSDATA_API_KEY=...
GNEWS_API=...
MEDIA_STACK_NEWS_API_KEY=...
CURRENTS_NEW_API=...
WORLD_NEWS_API_KEY=...
NEWSCATCHER_API_KEY=...

# AI refinement
OPEN_AI_API_KEY=sk-proj-...

# Protects /tasks/* endpoints
INGEST_SECRET=<long-random-string>
```

Missing keys are fine — each provider fails gracefully and the pipeline skips it.

### 3. Run it

```bash
make run-be           # starts FastAPI on :8000 + runs one ingestion cycle
make run-fe           # starts Vite dev server on :5173
```

Open **http://localhost:5173** and watch the planet fill with blips.

### 4. Tests

```bash
make test                 # full suite
make test-ingestion       # providers + normalizer + dedup
make test-intelligence    # classifier + refiner
make test-api             # FastAPI route contracts
```

---

## Deployment

OmnesVident ships to a hybrid GCP + Vercel stack.

```bash
make deploy-be        # gcloud run deploy → Cloud Run (backend + ingestion)
make deploy-fe        # vercel --prod     → Vercel (frontend)
make refine-all       # kick off a full AI backfill on Firestore
```

Cloud Run auto-scales to zero when idle. Cloud Scheduler handles the 15-minute ingestion cron. Vercel edge-caches the SPA globally.

---

## Project Layout

```
OmnesVident/
├── ingestion_engine/          # Layer 1 — fetch + normalize + dedup
│   ├── providers/             #   one file per news source
│   ├── core/                  #   bundler, scheduler, manager
│   └── regions_to_track.json  #   20 countries × ~10 regions each
│
├── intelligence_layer/        # Layer 2 — AI refinement + classification
│   ├── refiner.py             #   OpenAI batch translate + geo + breaking
│   ├── ai_geo_refiner.py      #   Vertex AI Gemini alternative path
│   ├── classifier.py          #   rule-based 7-way taxonomy
│   ├── deduplicator.py        #   fuzzy-match dedup
│   └── geo_data_cache.json    #   ISO 3166-2 centroid lookup
│
├── api_storage/               # Layer 3 — FastAPI + repositories
│   ├── routes.py              #   /stories, /regions, /tasks/*
│   ├── schemas.py             #   Pydantic wire models
│   └── repository.py          #   Firestore <-> SQLite façade
│
├── database/
│   └── firestore_manager.py   #   typed wrappers around google-cloud-firestore
│
├── tasks/
│   └── refiner.py             #   background-task entry points
│
├── frontend_portal/           # Layer 4 — React + R3F globe
│   └── src/
│       ├── components/
│       │   ├── visualizer/    #   GlobeScene, Marker, HudOverlay, NewsBlips
│       │   ├── BreakingNewsCarousel.tsx
│       │   ├── GlobeControls.tsx
│       │   ├── NewsCard.tsx
│       │   └── Sidebar.tsx
│       ├── hooks/useNews.ts
│       └── services/api.ts
│
├── Dockerfile                 # python:3.12-slim → Cloud Run
├── cloudbuild.yaml            # CI/CD pipeline
├── Makefile                   # make setup | run-be | run-fe | deploy-*
└── requirements.txt
```

---

## License

See [LICENSE](LICENSE).

---

<p align="center">
<em>Built for everyone who refuses to look at the world through a feed.</em>
</p>
