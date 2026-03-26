"""
volt_cli/shell.py — Interactive REPL passthrough to a MicroPython device.
"""

import subprocess
import click
from rich.console import Console

console = Console()


@click.command()
@click.option("--port", "-p", default="/dev/ttyUSB0", show_default=True,
              help="Serial port of the device.")
def shell(port):
    """Open an interactive MicroPython REPL on the device. Press Ctrl+] to exit."""
    console.print(f"[bold cyan]⚡ VOLT Shell[/bold cyan]  {port}")
    console.print("[dim]Press Ctrl+] to exit[/dim]\n")

    try:
        subprocess.run(["mpremote", "connect", port, "repl"])
    except FileNotFoundError:
        console.print("[bold red]Error:[/bold red] mpremote not found. Install with: pip install mpremote")
        raise SystemExit(1)
    except KeyboardInterrupt:
        pass
