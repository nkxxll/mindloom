# Mindloom

Mindloom is a FastAPI-based server for AI-assisted writing tasks, backed by Ollama for local LLM inference.

## Prerequisites

- Python 3.14+
- [uv](https://docs.astral.sh/uv/) installed and available in `PATH`
- [Ollama](https://ollama.com/) running locally

## Development

```bash
# Install dependencies
uv sync

# Run the server with hot reload
uv run uvicorn packages/server/src/mindloom/app:app --reload
```

## Cassandra configuration

Mindloom now stores jobs in Cassandra. Copy `.env.example` to `.env` and adjust values for your instance:

```bash
cp .env.example .env
```

Required settings:

- `CASSANDRA_CONTACT_POINTS` (comma-separated hosts)
- `CASSANDRA_PORT`
- `CASSANDRA_KEYSPACE`
- `CASSANDRA_TABLE`
- `CASSANDRA_REPLICATION_FACTOR`

Optional settings:

- `CASSANDRA_USERNAME`
- `CASSANDRA_PASSWORD`

## Deployment (Linux / systemd)

### 1. Install uv

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Make sure `uv` is available system-wide (e.g. in `/usr/local/bin`). Check with:

```bash
which uv
```

If it lives somewhere else, update the `PATH=` line in `mindloom.service` accordingly.

### 2. Create a dedicated user

```bash
sudo useradd -r -s /sbin/nologin mindloom
```

### 3. Deploy the application

```bash
sudo cp -r . /opt/mindloom
sudo chown -R mindloom:mindloom /opt/mindloom
```

### 4. Install and enable the systemd service

```bash
sudo cp mindloom.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now mindloom
```

### 5. Check status and logs

```bash
sudo systemctl status mindloom
journalctl -u mindloom -f
```

### Updating the application

```bash
sudo systemctl stop mindloom
sudo cp -r . /opt/mindloom
sudo chown -R mindloom:mindloom /opt/mindloom
sudo systemctl start mindloom
```
