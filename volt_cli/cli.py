"""
volt_cli/cli.py — Entry point for the `volt` CLI.

Registers all sub-commands under the top-level `volt` binary.
"""

import click
from rich.console import Console

console = Console()


@click.group()
@click.version_option("0.1.0", prog_name="volt")
def cli():
    """⚡ VOLT — FastAPI-inspired IoT framework for MicroPython."""
    pass


from .flash import flash          # noqa: E402
from .monitor import monitor      # noqa: E402
from .shell import shell          # noqa: E402
from .scan import scan            # noqa: E402
from .ota import ota              # noqa: E402
from .dashboard import dashboard  # noqa: E402

cli.add_command(flash)
cli.add_command(monitor)
cli.add_command(shell)
cli.add_command(scan)
cli.add_command(ota)
cli.add_command(dashboard)

if __name__ == "__main__":
    cli()
