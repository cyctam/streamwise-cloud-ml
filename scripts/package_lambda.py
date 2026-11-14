from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "infrastructure" / ".build"
LAMBDA_LAYER_UNCOMPRESSED_LIMIT = 245 * 1024 * 1024


def zip_tree(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for path in sorted(source.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(source).as_posix())


def prune_layer(root: Path) -> None:
    for path in sorted(root.rglob("*"), reverse=True):
        if path.is_dir() and path.name in {"tests", "__pycache__"}:
            shutil.rmtree(path, ignore_errors=True)
        elif path.is_file() and path.suffix in {".pyc", ".pyo"}:
            path.unlink(missing_ok=True)


def install_layer_with_docker(layer_root: Path) -> None:
    relative_target = layer_root.relative_to(ROOT).as_posix()
    command = [
        "docker", "run", "--rm", "--platform", "linux/amd64",
        "-v", f"{ROOT}:/workspace", "-w", "/workspace",
        "--entrypoint", "/bin/sh", "public.ecr.aws/lambda/python:3.12",
        "-c",
        f"python -m pip install --no-compile --disable-pip-version-check -r requirements-lambda.txt -t {relative_target}",
    ]
    subprocess.run(command, check=True)


def install_layer_with_pip(layer_root: Path) -> None:
    command = [
        sys.executable, "-m", "pip", "install", "--disable-pip-version-check", "--no-compile",
        "--only-binary=:all:", "--platform=manylinux_2_28_x86_64",
        "--implementation=cp", "--python-version=3.12", "--abi=cp312",
        "--target", str(layer_root), "-r", str(ROOT / "requirements-lambda.txt"),
    ]
    subprocess.run(command, check=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the Streamwise API Lambda package and Python dependency layer.")
    parser.add_argument("--build-method", choices=("docker", "pip"), default="docker", help="Build dependencies in the official Lambda runtime image (recommended) or cross-platform pip.")
    args = parser.parse_args()

    if BUILD.exists():
        shutil.rmtree(BUILD)
    function_root = BUILD / "function"
    layer_root = BUILD / "layer" / "python"
    function_root.mkdir(parents=True)

    for directory in ("backend", "api", "data/raw"):
        shutil.copytree(ROOT / directory, function_root / directory, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))

    layer_root.mkdir(parents=True)
    if args.build_method == "docker":
        install_layer_with_docker(layer_root)
    else:
        install_layer_with_pip(layer_root)

    prune_layer(layer_root)
    uncompressed_size = sum(path.stat().st_size for path in layer_root.rglob("*") if path.is_file())
    if uncompressed_size > LAMBDA_LAYER_UNCOMPRESSED_LIMIT:
        raise RuntimeError(
            f"Dependency layer is {uncompressed_size / 1024 / 1024:.1f} MiB after pruning; "
            "AWS Lambda's combined uncompressed package limit is 250 MiB. Reduce dependencies before deployment."
        )

    zip_tree(BUILD / "layer", BUILD / "python-dependencies.zip")
    zip_tree(function_root, BUILD / "streamwise-api.zip")
    print(f"Lambda assets created in {BUILD}")
    print(f"Dependency layer: {uncompressed_size / 1024 / 1024:.1f} MiB uncompressed")


if __name__ == "__main__":
    main()
