import click

from config import get_config, initialize_config

cfg = get_config()


@click.group()
def cli():
    pass


@cli.command()
def health():
    from health import Health

    h = Health(cfg)
    try:
        res = h.get_health()
        if res:
            click.secho("OK", fg="green")
        else:
            click.secho("ERROR", fg="red", err=True)
    except Exception as e:
        click.secho(f"ERROR: {e}", fg="red", err=True)


@cli.group()
@click.argument("id", required=False)
def jobs(id: int | None):
    from jobs import Jobs

    j = Jobs(cfg)
    if id:
        job = j.get_job_by_id(id)
        click.echo(job)
    else:
        jobs = j.get_jobs()
        click.echo(jobs)


@cli.command()
@click.argument("id")
def restart(id: int):
    from jobs import Jobs

    j = Jobs(cfg)
    jobs = j.restart_by_id(id)
    click.echo(jobs)


@cli.group()
def config():
    pass


@config.command()
def init():
    initialize_config()
