import os

import typer

from h3xassist.cli import configure as config
from h3xassist.cli import service, setup
from h3xassist.logging import setup_logging

app = typer.Typer(help="H3xAssist CLI", no_args_is_help=True)


@app.callback()
def _init() -> None:
    setup_logging(os.environ.get("H3XASSIST_LOG", "INFO"))


# Core commands
app.add_typer(config.app, name="config", help="Interactive configuration wizard")
app.add_typer(setup.app, name="setup", help="Setup and configuration utilities")
app.add_typer(service.app, name="service", help="Background service management")


def main() -> None:
    app()
