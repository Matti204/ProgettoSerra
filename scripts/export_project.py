"""Crea uno ZIP trasferibile senza ambiente virtuale, segreti o dati di sviluppo."""

from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]
FILES = ["app.py", "config.py", "scheduler.py", "requirements.txt", "requirements-dev.txt",
         "requirements-pi.txt", "requirements-ui.txt", "requirements-local.lock.txt", "README.md", "pytest.ini",
         ".env.example", ".gitignore", "start.ps1"]
DIRECTORIES = ["hardware", "services", "templates", "static", "deploy", "tests", "scripts"]


def export():
    target = ROOT / "artifacts" / "smart-greenhouse.zip"
    target.parent.mkdir(exist_ok=True)
    with ZipFile(target, "w", ZIP_DEFLATED) as archive:
        for name in FILES:
            path = ROOT / name
            if path.exists():
                archive.write(path, name)
        for folder in DIRECTORIES:
            for path in sorted((ROOT / folder).rglob("*")):
                if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc":
                    archive.write(path, path.relative_to(ROOT))
    print(target)


if __name__ == "__main__":
    export()
