import base64
import os
import secrets
import sys
from pathlib import Path

import typer
import uvicorn
from typing import Optional
from typing_extensions import Annotated

app = typer.Typer()

KEY_FILE = Path.cwd() / ".bcgpt_secret_key"


def version_callback(value: bool):
    if value:
        from bcgpt.env import VERSION

        typer.echo(f"BCGPT version: {VERSION}")
        raise typer.Exit()


@app.command()
def main(
    version: Annotated[
        Optional[bool], typer.Option("--version", callback=version_callback)
    ] = None,
):
    pass


@app.command()
def serve(
    host: str = "0.0.0.0",
    port: int = 8090,
):
    os.environ["FROM_INIT_PY"] = "true"
    if os.getenv("BCGPT_SECRET_KEY") is None:
        typer.echo(
            "Loading BCGPT_SECRET_KEY from file, not provided as an environment variable."
        )
        if not KEY_FILE.exists():
            typer.echo(f"Generating a new secret key and saving it to {KEY_FILE}")
            KEY_FILE.write_bytes(base64.b64encode(secrets.token_bytes(32)))
            os.chmod(KEY_FILE, 0o600)
        typer.echo(f"Loading BCGPT_SECRET_KEY from {KEY_FILE}")
        os.environ["BCGPT_SECRET_KEY"] = KEY_FILE.read_text()

    if os.getenv("USE_CUDA_DOCKER", "false") == "true":
        typer.echo(
            "CUDA is enabled, appending LD_LIBRARY_PATH to include torch/cudnn & cublas libraries."
        )
        _pyver = f"python{sys.version_info.major}.{sys.version_info.minor}"
        LD_LIBRARY_PATH = os.getenv("LD_LIBRARY_PATH", "").split(":")
        os.environ["LD_LIBRARY_PATH"] = ":".join(
            LD_LIBRARY_PATH
            + [
                f"/usr/local/lib/{_pyver}/site-packages/torch/lib",
                f"/usr/local/lib/{_pyver}/site-packages/nvidia/cudnn/lib",
            ]
        )
        try:
            import torch

            assert torch.cuda.is_available(), "CUDA not available"
            typer.echo("CUDA seems to be working")
        except Exception as e:
            typer.echo(
                "Error when testing CUDA but USE_CUDA_DOCKER is true. "
                "Resetting USE_CUDA_DOCKER to false and removing "
                f"LD_LIBRARY_PATH modifications: {e}"
            )
            os.environ["USE_CUDA_DOCKER"] = "false"
            os.environ["LD_LIBRARY_PATH"] = ":".join(LD_LIBRARY_PATH)

    import bcgpt.main  # we need set environment variables before importing main

    uvicorn.run(bcgpt.main.app, host=host, port=port, forwarded_allow_ips="*")


@app.command()
def dev(
    host: str = "0.0.0.0",
    port: int = 8090,
    reload: bool = True,
):
    uvicorn.run(
        "bcgpt.main:app",
        host=host,
        port=port,
        reload=reload,
        forwarded_allow_ips="*",
    )


if __name__ == "__main__":
    app()
