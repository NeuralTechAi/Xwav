"""Operator setup for the native subscription gateway."""

from __future__ import annotations

import json
import os
import shlex
from importlib.resources import files
from pathlib import Path

import click
from cryptography.fernet import Fernet

from omnigent.billing.config import BillingConfig


@click.group()
def billing() -> None:
    """Configure subscription plans and providers without installing a gateway stack."""


@billing.command("init")
@click.option("--directory", type=click.Path(path_type=Path), required=True)
@click.option("--public-url", default="http://localhost:6767", show_default=True)
def initialize(directory: Path, public_url: str) -> None:
    """Create private configuration; never print the generated encryption key."""
    directory = directory.expanduser().resolve()
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    config_path, env_path = directory / "plans.json", directory / "billing.env"
    if config_path.exists() or env_path.exists():
        raise click.ClickException("Configuration already exists; edit it instead of overwriting.")
    config = json.loads(files("omnigent.billing").joinpath("plans.json").read_text())
    config.update(public_url=public_url.rstrip("/"), database=str(directory / "billing.sqlite3"))
    BillingConfig.model_validate(config)
    for path, content in (
        (config_path, json.dumps(config, indent=2) + "\n"),
        (
            env_path,
            "XWAV_BILLING_CONFIG="
            + shlex.quote(str(config_path))
            + "\n"
            + "XWAV_BILLING_ENCRYPTION_KEY="
            + Fernet.generate_key().decode()
            + "\n",
        ),
    ):
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as stream:
            stream.write(content)
    click.echo(f"Created {config_path} and private {env_path}.")
    click.echo(
        "Configure models and Stripe prices, then load billing.env into the server environment."
    )


@billing.command("validate")
@click.argument("config", type=click.Path(exists=True, path_type=Path))
def validate(config: Path) -> None:
    """Validate registry shape without reading keys or contacting providers."""
    registry = BillingConfig.model_validate_json(config.read_text())
    click.echo(f"Valid: {len(registry.plans)} plans, {len(registry.providers)} providers.")


@billing.command("connect-freellmapi")
@click.option("--config", type=click.Path(exists=True, path_type=Path), required=True)
@click.option("--url", default="http://127.0.0.1:4000/v1", show_default=True)
@click.option("--key-file", type=click.Path(exists=True, path_type=Path), required=True)
@click.option("--model", "model_ids", multiple=True, required=True)
@click.option(
    "--auto-model",
    "auto_model_ids",
    multiple=True,
    help="Concrete model in the gateway's verified Auto pool; repeat for each member.",
)
def connect_free_gateway(
    config: Path,
    url: str,
    key_file: Path,
    model_ids: tuple[str, ...],
    auto_model_ids: tuple[str, ...],
) -> None:
    """Verify and connect approved FreeLLMAPI models; keep its unified key private."""
    from httpx import HTTPError

    from omnigent.billing.freellmapi import connect_freellmapi

    try:
        selected = connect_freellmapi(
            config, url, key_file, model_ids, auto_model_ids=auto_model_ids
        )
    except (ValueError, OSError, HTTPError) as exc:
        raise click.ClickException(
            "FreeLLMAPI configuration failed; check the endpoint and model IDs"
        ) from exc
    click.echo(f"Connected {len(selected)} FreeLLMAPI models. No provider keys were copied.")
    click.echo("Reload the private billing.env into the Xwav server environment, then restart it.")
