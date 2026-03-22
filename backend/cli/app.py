from __future__ import annotations

import sys

import typer

app = typer.Typer(help="Creature Hunter CLI", no_args_is_help=True)


@app.command("find-occurrences")
def find_occurrences_cmd() -> None:
    from cli.commands.find_occurrences.run import main

    try:
        code = main()
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        raise typer.Exit(1) from e
    raise typer.Exit(code)


@app.command("load-data")
def load_data_cmd() -> None:
    from cli.commands.load_data.run import main

    try:
        code = main()
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        print(
            "If this is an Earth Engine registration/project issue, see the one-time steps in setup-gcp.sh.",
            file=sys.stderr,
        )
        raise typer.Exit(1) from e
    raise typer.Exit(code)
