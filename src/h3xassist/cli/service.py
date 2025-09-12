"""Service management CLI commands."""

import logging

import typer
import uvicorn

from h3xassist.settings import settings
from h3xassist.ui import console

logger = logging.getLogger(__name__)

app = typer.Typer(help="Background service management")


@app.command()
def run(
    host: str = typer.Option(None, help="Host to bind to (overrides config)"),
    port: int = typer.Option(None, help="Port to bind to (overrides config)"),
    reload: bool = typer.Option(False, help="Enable auto-reload for development"),
    log_level: str = typer.Option("warning", help="Log level (debug, info, warning, error)"),
) -> None:
    """Start the H3xAssist HTTP server with API and web interface."""

    # Use config values if not overridden
    actual_host = host or settings.http.host
    actual_port = port or settings.http.port

    console.print("[bold green]Starting H3xAssist HTTP Server[/bold green]")
    console.print(f"[blue]Host:[/blue] {actual_host}")
    console.print(f"[blue]Port:[/blue] {actual_port}")
    console.print(f"[blue]Web Interface:[/blue] http://{actual_host}:{actual_port}")

    # Configure logging
    log_config = uvicorn.config.LOGGING_CONFIG
    log_config["formatters"]["default"]["fmt"] = (
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    log_config["formatters"]["access"]["fmt"] = (
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    try:
        uvicorn.run(
            "h3xassist.api.app:app",
            host=actual_host,
            port=actual_port,
            reload=reload,
            log_level=log_level.lower(),
            log_config=log_config,
        )
    except KeyboardInterrupt:
        console.print("\n[yellow]Service stopped by user[/yellow]")
    except Exception as e:
        console.print(f"[red]Service failed to start: {e}[/red]")
        console.print_exception()
        raise typer.Exit(1) from e


@app.command()
def status() -> None:
    """Check service status."""
    import requests

    try:
        response = requests.get(
            f"http://{settings.http.host}:{settings.http.port}/health", timeout=5
        )
        if response.status_code == 200:
            console.print("[green]✓ Service is running[/green]")
            data = response.json()
            console.print(f"Status: {data.get('status', 'unknown')}")
        else:
            console.print(f"[red]✗ Service returned status {response.status_code}[/red]")
    except requests.exceptions.ConnectionError:
        console.print("[red]✗ Service is not running[/red]")
    except requests.exceptions.Timeout:
        console.print("[red]✗ Service is not responding[/red]")
    except Exception as e:
        console.print(f"[red]✗ Error checking service: {e}[/red]")
        console.print_exception()
        raise typer.Exit(1) from e
