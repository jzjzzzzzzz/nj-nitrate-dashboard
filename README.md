# New Jersey Nitrate Research Dashboard

This is a Flask research dashboard for the precomputed New Jersey nitrate analysis outputs.

The deployed app is intentionally read-only. It does not run the heavy analysis pipeline on startup. `app.py` only serves:

- JSON files from `output/dashboard/`
- HTML maps from `output/maps/`
- PNG figures from `output/figures/`
- proposal files from `output/proposal/`

## Local Run

Install dependencies:

```bash
pip install -r requirements.txt
```

Run with Flask for local development:

```bash
python app.py
```

Run with the production entry point:

```bash
gunicorn app:app
```

## Deploy on Render

Create a new Render Web Service from this project directory/repository.

Use these settings:

- Environment: Python
- Build command: `pip install -r requirements.txt`
- Start command: `gunicorn app:app`

Important deployment notes:

- Commit `app.py`, `templates/`, `requirements.txt`, `README.md`, and the precomputed assets used by the app:
  - `output/dashboard/`
  - `output/maps/`
  - `output/figures/`
  - `output/proposal/`
- Do not commit raw WQP data, external shapefiles, local virtual environments, logs, or intermediate analysis outputs.
- The analysis scripts in `scripts/` are for offline regeneration only and are not run by Render.
