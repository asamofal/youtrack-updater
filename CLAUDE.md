# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

Single-file Python script that auto-updates a JetBrains YouTrack Docker container. It checks Docker Hub for the latest tag, compares against the running container, updates `docker-compose.yml`, and restarts the service.

## Setup & Run

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
./youtrack-updater.py
```

## Architecture

- **`youtrack-updater.py`** — entire application, two classes:
  - `YoutrackUpdater` — orchestrates the update flow: detects running version via Docker SDK, fetches latest tag from Docker Hub API, compares versions as tuples, stops/removes container, delegates compose file update, restarts via `docker compose up -d`
  - `DockerComposeUpdater` — reads/writes `docker-compose.yml` to swap the image tag using regex

## Key Dependencies

- `docker` (Python Docker SDK) — container inspection and management
- `requests` — Docker Hub API calls
- `colorama` — colored terminal output

## Conventions

- Python 3.10+
- No test suite exists
- Config constants (`YOUTRACK_CONTAINER_NAME`, `DOCKER_COMPOSE_FILE_NAME`) are module-level globals