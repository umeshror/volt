"""
volt_cli/scan.py — Discover VOLT devices on the local network.

Sends a UDP broadcast on port 5555 and waits for device responses.
"""

import socket
import json
import time

import click
from rich.console import Console
from rich.table import Table

console = Console()

_BROADCAST_PORT = 5555
_DISCOVERY_MSG = b'{"volt":"discover"}'
_TIMEOUT = 3.0


@click.command()
@click.option("--timeout", "-t", default=3, show_default=True,
              help="Time in seconds to wait for responses.")
def scan(timeout):
    """Discover VOLT devices on the local network via UDP broadcast."""
    console.print(f"[bold cyan]⚡ VOLT Scan[/bold cyan]  Broadcasting on port {_BROADCAST_PORT}...")

    devices = []

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.settimeout(0.5)

        sock.sendto(_DISCOVERY_MSG, ("<broadcast>", _BROADCAST_PORT))

        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                data, addr = sock.recvfrom(1024)
                info = json.loads(data.decode())
                info["ip"] = addr[0]
                # Deduplicate
                if not any(d.get("id") == info.get("id") for d in devices):
                    devices.append(info)
                    console.print(f"  [green]Found:[/green] {info.get('id', 'unknown')} @ {addr[0]}")
            except socket.timeout:
                continue
            except Exception:
                continue
    except Exception as e:
        console.print(f"[bold red]Scan error:[/bold red] {e}")
    finally:
        try:
            sock.close()
        except Exception:
            pass

    if not devices:
        console.print("[yellow]No VOLT devices found.[/yellow]")
        return

    table = Table(title=f"\n⚡ VOLT Devices ({len(devices)} found)")
    table.add_column("ID", style="cyan")
    table.add_column("IP Address", style="green")
    table.add_column("Version", style="blue")

    for d in devices:
        table.add_row(
            d.get("id", "—"),
            d.get("ip", "—"),
            d.get("version", "—"),
        )

    console.print(table)
