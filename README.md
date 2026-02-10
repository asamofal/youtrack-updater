# YouTrack Docker Updater

A CLI tool that checks for new JetBrains YouTrack Docker image versions and automatically updates a running instance managed via Docker Compose.

The tool:
- Reads the current YouTrack version from `docker-compose.yml`
- Compares it with the latest available Docker image tag
- Pre-pulls the new image to minimize downtime
- Updates `docker-compose.yml` and restarts the service

---

## Requirements

- Linux host with Docker installed
- Docker Compose v2 (`docker compose`)
- Python 3.10+
- A `docker-compose.yml` with a `jetbrains/youtrack:<tag>` image

## Installation

### With pipx (recommended)

```bash
pipx install youtrack-updater
```

### With pip

```bash
pip install youtrack-updater
```

## Upgrade

```bash
pipx upgrade youtrack-updater
```

## Usage

```bash
youtrack-updater
```

If a newer YouTrack version is available, you'll be prompted to confirm the update.

### Options

```
--compose-file PATH     Path to docker-compose.yml (default: docker-compose.yml)
--version               Show version and exit
```

### Examples

```bash
# default — looks for ./docker-compose.yml
youtrack-updater

# custom compose file location
youtrack-updater --compose-file /opt/youtrack/docker-compose.yml
```
