# CFS Preferred IFR Routes

A service that fetches, parses, and serves the Canadian CFS Mandatory IFR Routes for Canadian VATSIM controllers.

It works by first calculating the current airac string, and if it isn't present in the database, fetches it in PDF format from a source which serves them with 
the following URL format: `{PDF_BASE_URL}/CFSPREFERREDIFRROUTES_{MM-DD-YYYY}.PDF` and inserts the parsed results into the database. Old AIRAC is kept.

Once data is available, it can be queried through a minimalistic web UI, or through the API.


> **Disclaimer:** This project was developed with heavy use of AI assistance (Claude). Every line of generated code was reviewed and edited as necessary by me before being committed.

## Quick start

```bash
pip install -r requirements.txt
uvicorn cfs_routes.main:app --reload
```

Open http://localhost:8000

## Configuration

Copy `.env.example` to `.env` and adjust:

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `sqlite+aiosqlite:///cfs_routes.db` | SQLAlchemy async URL |
| `AIRPORTS_CSV_PATH` | `data/airports.csv` | Airport data (icao, name, lat, lon, …) |
| `LOG_LEVEL` | `INFO` | |
| `FETCH_RETRY_DAYS_BEFORE` | `7` | Start fetching this many days before cycle effective date |
| `FETCH_RETRY_DAYS_AFTER` | `3` | Give up this many days after effective date |
| `SCHEDULER_ENABLED` | `true` | Automatically fetch new data around AIRAC day |
| `PDF_BASE_URL` | _(required)_ | Base URL for fetching CFS PDF documents |
| `API_PUBLIC` | `false` | Set to `true` to allow cross-origin requests from all origins (`*`) |

> **Note on `PDF_BASE_URL`:** You will need to configure a PDF source that serves CFS Preferred IFR Routes with this URL format. The source I used is not included in this repository.

## Docker

```bash
docker compose up
```

## API

| Endpoint | Description |
|---|---|
| `GET /api/routes?from=CYOW&to=CYTZ` | Routes between two airports |
| `GET /api/routes?airport=CYUL` | All routes for an airport |
| `GET /api/routes?from=CYHZ&direction=NE` | DEP routes in a cardinal direction |
| `GET /api/airports` | All airports with routes, grouped by FIR |
| `GET /api/cycles` | All ingested cycles |

### Fallback behaviour

When `?from=ICAO&to=ICAO` returns no routes, the API automatically falls back to returning
all **DEP TO {cardinal direction}** routes for the `from` airport (the closest cardinal
direction toward the destination), and sets `fallback: true` in the response. The UI
displays a notice explaining the fallback.

## Vendored assets

The following third-party libraries are bundled in `cfs_routes/web/static/vendor/` and served
locally — no CDN required.

| Library | Version | License |
|---|---|---|
| [Bootstrap](https://getbootstrap.com/) | 5.3.3 | MIT |
| [Bootstrap Icons](https://icons.getbootstrap.com/) | 1.11.3 | MIT |
| [Choices.js](https://github.com/Choices-js/Choices) | 11.1.0 | MIT |

To update them, replace the files under `cfs_routes/web/static/vendor/` with newer releases
and update the version numbers above.

## Architecture

```
cfs_routes/
├── airac.py        AIRAC 56-day cycle math
├── config.py       Pydantic Settings
├── database.py     SQLAlchemy async engine
├── models.py       ORM models
├── fetcher.py      PDF download
├── parser.py       PDF text → route records
├── ingest.py       Fetch + parse + persist pipeline
├── scheduler.py    APScheduler (daily + startup check)
├── airports.py     airports.csv loader
├── main.py         FastAPI app + lifespan
├── api/
│   ├── routes.py   REST endpoints
│   └── schemas.py  Pydantic response models
└── web/
    ├── views.py
    ├── templates/index.html
    └── static/vendor/
        ├── bootstrap/              Bootstrap 5.3.3 CSS + JS bundle
        ├── bootstrap-icons/        Bootstrap Icons 1.11.3 CSS + fonts
        └── choices/                Choices.js 11.1.0 CSS + JS
```
