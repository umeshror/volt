"""
volt_cli/dashboard.py — Start the local VOLT web dashboard.
"""

import click
from rich.console import Console

console = Console()


@click.command()
@click.option("--port", "-p", default=8765, show_default=True,
              help="Port to serve the dashboard on.")
@click.option("--open", "auto_open", is_flag=True, default=False,
              help="Automatically open the dashboard in the default browser.")
@click.option("--host", default="127.0.0.1", show_default=True,
              help="Host interface to bind to.")
def dashboard(port, auto_open, host):
    """Launch the local VOLT web dashboard."""
    console.print(f"[bold cyan]⚡ VOLT Dashboard[/bold cyan]")
    console.print(f"  URL : [link=http://{host}:{port}]http://{host}:{port}[/link]")

    if auto_open:
        import webbrowser
        import threading
        import time

        def _open():
            time.sleep(1.5)
            webbrowser.open(f"http://{host}:{port}")

        threading.Thread(target=_open, daemon=True).start()

    try:
        import uvicorn
        from dashboard.server import app as fastapi_app
        uvicorn.run(fastapi_app, host=host, port=port, log_level="warning")
    except ImportError as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        console.print("Install dependencies: pip install volt-iot")
        raise SystemExit(1)
    except KeyboardInterrupt:
        console.print("\n[dim]Dashboard stopped.[/dim]")
