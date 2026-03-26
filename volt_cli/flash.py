"""
volt_cli/flash.py — Upload files to a MicroPython device.

Uses mpremote under the hood.
"""

import subprocess
import os
import time

import click
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

console = Console()


@click.command()
@click.argument("file", type=click.Path(exists=True))
@click.option("--port", "-p", default="/dev/ttyUSB0", show_default=True,
              help="Serial port of the device.")
@click.option("--run", "-r", is_flag=True, default=False,
              help="Execute the file immediately after upload.")
@click.option("--dest", "-d", default=None,
              help="Destination path on device (default: same filename).")
def flash(file, port, run, dest):
    """Upload FILE to a MicroPython device."""
    dest_path = dest or os.path.basename(file)
    file_size = os.path.getsize(file)

    console.print(f"[bold cyan]⚡ VOLT Flash[/bold cyan]")
    console.print(f"  Source : [green]{file}[/green] ({file_size:,} bytes)")
    console.print(f"  Device : [yellow]{port}[/yellow]")
    console.print(f"  Dest   : [blue]:{dest_path}[/blue]")

    cmd = ["mpremote", "connect", port, "cp", file, f":{dest_path}"]

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Uploading...", total=None)
        start = time.time()
        result = subprocess.run(cmd, capture_output=True, text=True)
        elapsed = time.time() - start
        progress.update(task, completed=True)

    if result.returncode == 0:
        speed = file_size / elapsed / 1024 if elapsed > 0 else 0
        console.print(
            f"[bold green]✓ Upload complete[/bold green]  "
            f"({elapsed:.1f}s, {speed:.1f} KB/s)"
        )
        if run:
            console.print("[cyan]Running file on device...[/cyan]")
            run_cmd = ["mpremote", "connect", port, "run", file]
            subprocess.run(run_cmd)
    else:
        console.print(f"[bold red]✗ Upload failed[/bold red]")
        if result.stderr:
            console.print(f"[red]{result.stderr}[/red]")
        raise SystemExit(1)
