# ProjectSiluma

Language-learning web app (Flask) with custom levels, practice modes, localization, and Railway deployment.

## Quick start

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # add OPENAI_API_KEY and DB settings
python3 scripts/dev/create_local_user.py
python3 run_local.py
```

Open **http://localhost:5001**

## Repository layout

| Path | Purpose |
|------|---------|
| `app.py` | Flask application |
| `run_local.py` | Local dev server |
| `railway_startup.py` | Production entry (Railway main app) |
| `server/` | Backend services and database layer |
| `static/` | Frontend assets |
| `docs/` | Configuration, deployment, local dev |
| `scripts/deploy/` | Railway and cleanup deploy helpers |
| `scripts/dev/` | Local development utilities |
| `cleanup_service.py` | Separate Railway cleanup worker |

## Documentation

- [Local development](docs/LOCAL_DEV.md)
- [Configuration](docs/CONFIGURATION.md)
- [Deployment & cleanup service](docs/DEPLOYMENT.md)

## GitHub

https://github.com/linuspohlmann-byte/projectsiluma
