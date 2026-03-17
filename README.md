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

## Deployment as a user service

If you prefer to run Mindloom under your own user account instead of a dedicated system user, you can use the provided `mindloom.user.service` unit file. This expects the repository to live at `~/git/mindloom` and `uv` to be installed at `~/.local/bin/uv`.

### 1. Install the user service

```bash
mkdir -p ~/.config/systemd/user
cp mindloom.user.service ~/.config/systemd/user/mindloom.service
systemctl --user daemon-reload
systemctl --user enable --now mindloom
```

### 2. Check status and logs

```bash
systemctl --user status mindloom
journalctl --user -u mindloom -f
```

### 3. Enable lingering (optional)

By default, user services only run while the user is logged in. To keep the service running after logout:

```bash
sudo loginctl enable-linger $USER
```

### Updating the application

```bash
systemctl --user restart mindloom
```
