"""
volt_cli/ota.py — Over-the-air firmware push to VOLT devices.
"""

import os
import click
import requests as http
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

console = Console()


@click.group()
def ota():
    """Over-the-air update commands."""
    pass


@ota.command("push")
@click.argument("file", type=click.Path(exists=True))
@click.option("--device", "-d", required=True,
              help="Device IP address, or 'all' to broadcast.")
@click.option("--port", default=80, show_default=True,
              help="HTTP port of the device.")
def ota_push(file, device, port):
    """Push FILE to a device (or all discovered devices) via OTA."""
    file_size = os.path.getsize(file)
    console.print(f"[bold cyan]⚡ VOLT OTA Push[/bold cyan]")
    console.print(f"  File   : [green]{file}[/green] ({file_size:,} bytes)")

    if device == "all":
        _push_all(file, port)
    else:
        _push_one(file, device, port)


def _push_one(file: str, ip: str, port: int):
    url = f"http://{ip}:{port}/ota/upload"
    console.print(f"  Target : [yellow]{ip}:{port}[/yellow]")

    with Progress(SpinnerColumn(), TextColumn("{task.description}"), console=console) as progress:
        task = progress.add_task(f"Pushing to {ip}...", total=None)
        try:
            with open(file, "rb") as f:
                resp = http.post(url, files={"file": f}, timeout=30)
            progress.update(task, completed=True)
            if resp.status_code == 200:
                console.print(f"[bold green]✓ {ip} — OTA success. Device rebooting...[/bold green]")
            else:
                console.print(f"[bold red]✗ {ip} — HTTP {resp.status_code}[/bold red]")
        except Exception as e:
            progress.update(task, completed=True)
            console.print(f"[bold red]✗ {ip} — {e}[/bold red]")


def _push_all(file: str, port: int):
    """Discover all devices and push to each."""
    import socket
    import json
    import time

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.settimeout(0.5)
    sock.sendto(b'{"volt":"discover"}', ("<broadcast>", 5555))

    ips = []
    deadline = time.time() + 3.0
    while time.time() < deadline:
        try:
            data, addr = sock.recvfrom(1024)
            ips.append(addr[0])
        except socket.timeout:
            continue
    sock.close()

    if not ips:
        console.print("[yellow]No devices found.[/yellow]")
        return

    console.print(f"  Found {len(ips)} device(s): {', '.join(ips)}")
    for ip in ips:
        _push_one(file, ip, port)
