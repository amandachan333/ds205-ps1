#!/usr/bin/env python
"""Pipeline for enriching and serving Waitrose product data."""

import os
import subprocess
import sys
import click


@click.group()
def cli():
    """Waitrose NOVA enrichment pipeline."""
    pass


@cli.command()
@click.option("--only-new/--all", default=False, help="Skip already-enriched products")
def enrich(only_new: bool):
    """Match scraped products against OpenFoodFacts and save to data/enriched/."""
    click.echo("Starting enrichment...")
    args = ["python", "api/enrichment.py"]
    if only_new:
        args.append("--only-new")
    result = subprocess.run(args)
    if result.returncode != 0:
        click.echo("Enrichment failed.", err=True)
        sys.exit(1)


@cli.command()
def serve():
    """Start the FastAPI server on port 8000."""
    root_path = "/proxy/8000" if os.path.exists("/files") else ""
    click.echo("Starting API on port 8000...")
    subprocess.run(["uvicorn", "api.main:app", "--reload", "--root-path", root_path])


if __name__ == "__main__":
    cli()
