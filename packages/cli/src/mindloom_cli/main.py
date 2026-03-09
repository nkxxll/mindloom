import click


@click.group()
def app():
    """Mindloom CLI — interact with the Mindloom server."""
    pass


@app.command()
@click.option("--host", default="http://localhost:8000", show_default=True, help="Server base URL.")
def ping(host: str):
    """Check if the server is reachable."""
    import httpx

    try:
        response = httpx.get(f"{host}/health")
        if response.status_code == 200:
            click.echo("Server is healthy ✓")
        else:
            click.echo(f"Server returned status {response.status_code}", err=True)
    except httpx.ConnectError:
        click.echo(f"Could not connect to server at {host}", err=True)
        raise SystemExit(1)
