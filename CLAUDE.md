# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

PyPI-published CLI tool that auto-updates a JetBrains YouTrack Docker container. It checks Docker Hub for the latest tag, compares against the tag in `docker-compose.yml`, updates the file, and restarts the service via `docker compose`.

## Setup & Run

```bash
# install for development
pip install -e .

# or run directly
python youtrack_updater.py

# after PyPI install
youtrack-updater
youtrack-updater --compose-file /path/to/docker-compose.yml
```

## Architecture

- **`youtrack_updater.py`** — entire application, single `YoutrackUpdater` class:
  - Reads current image tag from `docker-compose.yml` via regex
  - Fetches latest tag from Docker Hub API
  - Compares versions as tuples
  - Pre-pulls new image, runs `docker compose down`, rewrites compose file, runs `docker compose up -d`
  - Streams logs to detect `wizard_token` URL
  - Cleans up old image via `docker rmi`

## Packaging

- **Build backend:** hatchling
- **Entry point:** `youtrack_updater:main` → `youtrack-updater` CLI command
- **Dependencies defined in:** `pyproject.toml`
- **Version:** kept in both `pyproject.toml` and `__version__` in `youtrack_updater.py`

## Key Dependencies

- `requests` — Docker Hub API calls
- `colorama` — colored terminal output

## Conventions

- Python 3.10+
- No test suite exists
- CLI args via `argparse`: `--compose-file`, `--version`
