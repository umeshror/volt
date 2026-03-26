"""
volt_cli/monitor.py — Stream serial output from a MicroPython device.
"""

import click
import serial
from rich.console import Console
from rich.text import Text

console = Console()

_LEVEL_STYLES = {
    "ERROR":   "bold red",
    "WARNING": "bold yellow",
    "WARN":    "bold yellow",
    "INFO":    "bold blue",
    "DEBUG":   "dim",
}


@click.command()
@click.option("--port", "-p", default="/dev/ttyUSB0", show_default=True,
              help="Serial port of the device.")
@click.option("--baud", "-b", default=115200, show_default=True,
              help="Baud rate.")
@click.option("--filter", "-f", "filter_str", default=None,
              help="Only show lines containing this string.")
def monitor(port, baud, filter_str):
    """Stream serial logs from a MicroPython device. Press Ctrl+C to exit."""
    console.print(f"[bold cyan]⚡ VOLT Monitor[/bold cyan]  {port} @ {baud}")
    if filter_str:
        console.print(f"  Filter: [yellow]{filter_str}[/yellow]")
    console.print("[dim]Press Ctrl+C to exit[/dim]\n")

    try:
        with serial.Serial(port, baud, timeout=1) as ser:
            while True:
                try:
                    raw = ser.readline()
                    if not raw:
                        continue
                    line = raw.decode("utf-8", errors="replace").rstrip()

                    if filter_str and filter_str not in line:
                        continue

                    text = Text(line)
                    for level, style in _LEVEL_STYLES.items():
                        if level in line:
                            text.stylize(style)
                            break

                    console.print(text)
                except Exception:
                    continue
    except KeyboardInterrupt:
        console.print("\n[dim]Monitor stopped.[/dim]")
    except serial.SerialException as e:
        console.print(f"[bold red]Serial error:[/bold red] {e}")
        raise SystemExit(1)
