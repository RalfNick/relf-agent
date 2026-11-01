"""The SDK source distribution must carry an installable standalone example."""

import os
import shutil
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = (
    "pyproject.toml",
    "assistant.example.toml",
    "demo-documents/oncall.md",
    "demo-documents/reports.txt",
    "LICENSE",
    "NOTICE",
    "README.md",
)


def test_sdk_sdist_contains_buildable_local_documents_example(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    for name in ("pyproject.toml", "MANIFEST.in", "README.md", "LICENSE", "NOTICE"):
        shutil.copy2(ROOT / name, source / name)
    shutil.copytree(ROOT / "src", source / "src", ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copytree(
        ROOT / "examples/local_documents",
        source / "examples/local_documents",
        ignore=shutil.ignore_patterns("__pycache__", "build", "*.egg-info"),
    )
    artifacts = tmp_path / "artifacts"
    env = {**os.environ, "PIP_NO_INDEX": "1", "PIP_DISABLE_PIP_VERSION_CHECK": "1"}
    env.pop("PYTHONPATH", None)
    built = subprocess.run(
        [sys.executable, "-m", "build", "--sdist", "--no-isolation", "--outdir", str(artifacts)],
        cwd=source,
        env=env,
        capture_output=True,
        text=True,
        timeout=90,
    )
    assert built.returncode == 0, built.stdout + built.stderr
    (sdist,) = artifacts.glob("*.tar.gz")
    extracted = tmp_path / "extracted"
    with tarfile.open(sdist) as archive:
        names = archive.getnames()
        for name in REQUIRED:
            member = next(
                (n for n in names if n.endswith("/examples/local_documents/" + name)), None
            )
            assert member is not None, f"SDK sdist omits standalone application file: {name}"
            assert (
                archive.extractfile(member).read()
                == (ROOT / "examples/local_documents" / name).read_bytes()
            )
        archive.extractall(extracted, filter="data")
    (app,) = extracted.glob("*/examples/local_documents")
    built = subprocess.run(
        [
            sys.executable,
            "-m",
            "build",
            "--wheel",
            "--no-isolation",
            "--outdir",
            str(tmp_path / "app-wheel"),
        ],
        cwd=app,
        env=env,
        capture_output=True,
        text=True,
        timeout=90,
    )
    assert built.returncode == 0, built.stdout + built.stderr
    (wheel,) = (tmp_path / "app-wheel").glob("*.whl")
    with zipfile.ZipFile(wheel) as archive:
        assert "local_documents/cli.py" in archive.namelist()
        (metadata,) = (name for name in archive.namelist() if name.endswith("/METADATA"))
        assert b"Name: relf-local-documents-example" in archive.read(metadata)
