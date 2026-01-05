# YouTrack Docker Updater

A small helper script to check for new JetBrains YouTrack Docker image versions and automatically update a running YouTrack instance managed via Docker Compose.

The script:
- Detects the currently running YouTrack version
- Compares it with the latest available Docker image tag
- Updates `docker-compose.yml`
- Restarts the container using modern `docker compose`

---

## Getting started

### Requirements

- Linux host with Docker installed
- Docker Compose v2 (`docker compose`)
- Python 3.10+
- A running YouTrack container named `youtrack`

### Setup

Create a virtual environment and install dependencies:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

Make the script executable:
```bash
chmod +x youtrack-updater.py
```

Ensure the script uses the virtual environment Python in its shebang:
```bash
#!/path/to/repo/.venv/bin/python3
```

### Usage
```bash
./youtrack-updater.py
```

If a newer YouTrack version is available, you’ll be prompted to confirm the update.
If the instance is already up to date, no changes are made.
