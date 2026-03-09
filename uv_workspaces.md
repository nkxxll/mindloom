If you already have a **server component** and now want to add a **CLI client**, a good pattern with **`uv` workspaces** is to split your repo into multiple packages that share dependencies but can depend on each other. Workspaces manage them with **one lockfile and one environment**. ([Astral Docs][1])

I’ll show a typical setup for **server + shared lib + CLI**.

---

# 1. Typical workspace layout

A common structure looks like this:

```
myapp/
├── pyproject.toml        # workspace root
├── uv.lock
├── packages/
│   ├── server/
│   │   ├── pyproject.toml
│   │   └── src/server/...
│   ├── cli/
│   │   ├── pyproject.toml
│   │   └── src/cli/...
│   └── core/
│       ├── pyproject.toml
│       └── src/core/...
```

Recommended idea:

| package  | role                               |
| -------- | ---------------------------------- |
| `core`   | shared logic / API client / models |
| `server` | FastAPI / backend                  |
| `cli`    | CLI client                         |

This avoids the CLI importing directly from server code.

---

# 2. Root `pyproject.toml`

Define the workspace members.

```toml
[tool.uv.workspace]
members = ["packages/*"]
```

Every directory in `packages/*` must contain its own `pyproject.toml`. ([Astral Docs][1])

The workspace will produce **one `uv.lock` file for all packages**. ([GitHub][2])

---

# 3. Shared library (`core`)

`packages/core/pyproject.toml`

```toml
[project]
name = "myapp-core"
version = "0.1.0"
dependencies = [
    "pydantic",
    "httpx"
]
```

Example usage:

```
src/core/api.py
```

---

# 4. Server package

`packages/server/pyproject.toml`

```toml
[project]
name = "myapp-server"
version = "0.1.0"
dependencies = [
    "fastapi",
    "uvicorn",
    "myapp-core"
]

[tool.uv.sources]
myapp-core = { workspace = true }
```

`workspace = true` tells uv to **use the local workspace package instead of PyPI**. ([Astral Docs][1])

---

# 5. CLI package

`packages/cli/pyproject.toml`

```toml
[project]
name = "myapp-cli"
version = "0.1.0"
dependencies = [
    "click",
    "httpx",
    "myapp-core"
]

[tool.uv.sources]
myapp-core = { workspace = true }

[project.scripts]
myapp = "cli.main:app"
```

Example CLI:

```
src/cli/main.py
```

```python
import click
from core.api import Client

@click.group()
def app():
    pass

@app.command()
def ping():
    print("pong")
```

---

# 6. Install dependencies

From the workspace root:

```
uv lock
uv sync --all-packages
```

or just:

```
uv sync
```

`uv sync --all-packages` installs dependencies for every workspace member. ([GitHub][2])

---

# 7. Run packages

Run commands inside a specific package:

```
uv run --package myapp-cli myapp ping
```

or server:

```
uv run --package myapp-server uvicorn server.main:app
```

`--package` lets you run commands in a specific workspace member. ([Astral Docs][1])

---

# 8. Adding dependencies

Add dependencies to a specific package:

```
cd packages/cli
uv add click
```

Then update the workspace lockfile:

```
uv lock
uv sync
```

---

# 9. Why this structure works well

Benefits:

* shared code (`core`)
* CLI and server **independent packages**
* single lockfile
* local dependencies resolved automatically
* editable development between packages

This is basically the **Cargo-style monorepo pattern** uv was inspired by. ([Astral Docs][1])

---

💡 **My strong recommendation**

Use **3 packages**:

```
packages/
  core/
  server/
  cli/
```

Instead of CLI depending directly on server.

This keeps the architecture clean.

---

If you want, I can also show a **real-world layout used by large Python repos (FastAPI-style)** that makes CLI + server + SDK extremely clean.

[1]: https://docs.astral.sh/uv/concepts/projects/workspaces/?utm_source=chatgpt.com "Using workspaces | uv"
[2]: https://github.com/fedragon/uv-workspace-example?utm_source=chatgpt.com "GitHub - fedragon/uv-workspace-example: Example of Python workspace using https://github.com/astral-sh/uv"
