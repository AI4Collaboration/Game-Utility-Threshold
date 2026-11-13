"""Build the public, offline GitHub Pages site from an explicit file allowlist.

No requests to model APIs are made. Raw datasets stay byte-for-byte intact.
The original study's figures are reproduced locally; the audited oversight
report is copied from its saved release. Nothing is copied from runs/ or .env.
"""

import argparse
from hashlib import sha256
from html.parser import HTMLParser
import gzip
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from urllib.parse import unquote, urlsplit
from zipfile import ZIP_DEFLATED, ZipFile

import reproduce
from gut.study import load_study

ROOT = Path(__file__).resolve().parent
OVERSIGHT = Path("data/oversight/2026-11-09")
WEB_FILES = ("index.html", "games.html", "oversight.html", "oversight.js", "game-engine.js", "results.html",
             "science.html", "science.css", "science.js", "science-engine.js")
POST_FILES = ("README.md", "manifest.json", "block-0.json", "block-1.json", "records.jsonl.gz")
OVERSIGHT_FILES = ("README.md", "analysis-requirements.txt", "checksums.json", "models.json", "plan.json.gz",
                   "provenance.json", "records.jsonl.gz", "anthropic--claude-haiku-4.5-endpoints.json",
                   "google--gemini-2.5-flash-endpoints.json", "openai--gpt-4.1-mini-endpoints.json")
ANALYSIS_FILES = ("report.html", "summary.json", "observations.csv", "cells.csv", "blocks.csv", *(
    f"{name}.{extension}" for name in ("sweep-defense", "framing", "presentation-blocks", "confusion")
    for extension in ("png", "svg")))
DOC_FILES = ("games.md", "experiments.md", "oversight.md", "oversight-validation-protocol.md",
             "oversight-validation-results.md", "pages.md", "science-game.md")
SOURCE_FILES = tuple([*(Path("data/post") / name for name in POST_FILES),
                      *(OVERSIGHT / name for name in OVERSIGHT_FILES),
                      *(OVERSIGHT / "analysis" / name for name in ANALYSIS_FILES),
                      *(Path("docs") / name for name in DOC_FILES)])
SCHEMA = "gut-pages-v1"
SECRET = re.compile(rb"(?<![A-Za-z0-9_-])(?:sk-or-v1-[A-Za-z0-9]{20,}|sk-[A-Za-z0-9_-]{32,}|"
                    rb"gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{30,}|"
                    rb"Bearer[ \t]+[A-Za-z0-9._-]{24,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)")


def publication_sources(root=ROOT):
    """Return only known inputs, rejecting missing files and source symlinks."""
    root = Path(root).resolve()
    files = [*(Path("web") / name for name in WEB_FILES), *SOURCE_FILES]
    for name in files:
        path = root / name
        if not path.is_file() or any(p.is_symlink() for p in [path, *path.parents] if p != root):
            raise ValueError(f"Missing or symlinked publication input: {name}")
        if not path.resolve().is_relative_to(root):
            raise ValueError(f"Publication input escapes source directory: {name}")
    return files


def scan_credentials(directory):
    """Scan both plain output and decompressed datasets; never print a match."""
    for path in Path(directory).rglob("*"):
        if not path.is_file():
            continue
        content = path.read_bytes()
        payloads = [content]
        if path.suffix == ".gz":
            payloads.append(gzip.decompress(content))
        elif path.suffix == ".zip":
            with ZipFile(path) as archive:
                payloads.extend(archive.read(name) for name in archive.namelist())
                payloads.extend(gzip.decompress(archive.read(name)) for name in archive.namelist()
                                if name.endswith(".gz"))
        if any(SECRET.search(payload) for payload in payloads):
            raise ValueError(f"Credential-pattern check failed in publication file: {path.name}")


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []

    def handle_starttag(self, tag, attributes):
        for key, value in attributes:
            if value and ((tag in ("a", "link") and key == "href") or
                          (tag in ("img", "script", "source") and key == "src")):
                self.links.append(value)


def validate_links(directory):
    """Check every local HTML link using the same project-subpath semantics as Pages."""
    root = Path(directory).resolve()
    for page in root.rglob("*.html"):
        links = Links()
        links.feed(page.read_text())
        for href in links.links:
            parsed = urlsplit(href)
            if parsed.scheme or parsed.netloc or not parsed.path:
                continue
            if parsed.path.startswith("/"):
                raise ValueError(f"Root-relative link would leave the Pages project: {page.name}: {href}")
            target = (page.parent / unquote(parsed.path)).resolve()
            if not target.is_relative_to(root) or not target.is_file():
                raise ValueError(f"Missing internal link: {page.relative_to(root)}: {href}")


def add_report_navigation(path):
    page = path.read_text()
    navigation = ('<nav aria-label="Research navigation" style="display:flex;flex-wrap:wrap;gap:20px;'
                  'padding:0 0 18px;margin:0 0 24px;border-bottom:1px solid #a8bcbc;font-size:14px">'
                  '<a href="../results.html">← All results</a>'
                  '<a href="../oversight.html">Oversight lab</a>'
                  '<a href="../games.html">Canonical games</a>'
                  '<a href="../index.html">PD explorer</a></nav>')
    if "</style>" not in page:
        raise ValueError(f"Report has no expected navigation insertion point: {path.name}")
    path.write_text(page.replace("</style>", "</style>" + navigation, 1))


def verify_oversight_sources():
    base = ROOT / OVERSIGHT
    for name, expected in json.loads((base / "checksums.json").read_text()).items():
        if Path(name).name != name or name not in OVERSIGHT_FILES:
            raise ValueError("Unexpected oversight checksum entry")
        if sha256((base / name).read_bytes()).hexdigest() != expected:
            raise ValueError(f"Oversight source checksum mismatch: {name}")


def build(output=ROOT / "_site"):
    output = Path(output).absolute()
    if output.is_symlink():
        raise ValueError("Do not build into a symlink")
    if output.exists() and any(output.iterdir()):
        marker = output / "site-manifest.json"
        if not marker.is_file() or json.loads(marker.read_text()).get("schema") != SCHEMA:
            raise ValueError("Refusing to replace a nonempty directory not owned by this site builder")
    inputs = publication_sources()
    verify_oversight_sources()
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="gut-pages-", dir=output.parent) as temporary:
        staged = Path(temporary) / "site"
        staged.mkdir()
        for name in inputs:
            target = staged / (name.name if name.parts[0] == "web" else name)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, target)
        (staged / ".nojekyll").write_text("")

        # Original report: verify source records and regenerate offline.
        study = load_study()
        summary, cells, regions = study.summary(), study.cells(), study.regions()
        report = staged / "report"
        report.mkdir()
        (report / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
        for name, rows in (("cells.csv", cells), ("regions.csv", regions),
                           ("theory-grid.csv", reproduce.theory_rows())):
            reproduce.write_csv(report / name, rows)
        reproduce.figures(report, cells)
        reproduce.report(report, summary, regions)
        add_report_navigation(report / "index.html")

        validation = staged / "validation"
        validation.mkdir()
        for name in ANALYSIS_FILES:
            shutil.copyfile(ROOT / OVERSIGHT / "analysis" / name, validation / name)
        add_report_navigation(validation / "report.html")

        downloads = staged / "downloads"
        downloads.mkdir()
        for label, prefix in (("post", Path("data/post")), ("oversight", OVERSIGHT)):
            with ZipFile(downloads / f"{label}-source.zip", "w", ZIP_DEFLATED) as archive:
                for name in SOURCE_FILES:
                    if name.is_relative_to(prefix):
                        archive.write(staged / name, str(name))
        # Reserve the manifest target so its public link can be checked too.
        (staged / "site-manifest.json").write_text(json.dumps({"schema": SCHEMA}) + "\n")
        scan_credentials(staged)
        validate_links(staged)
        revision = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True,
                                  capture_output=True, check=True).stdout.strip()
        manifest = {"schema": SCHEMA, "source_commit": revision,
                    "files": {str(p.relative_to(staged)): sha256(p.read_bytes()).hexdigest()
                              for p in sorted(staged.rglob("*"))
                              if p.is_file() and p.name != "site-manifest.json"}}
        (staged / "site-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
        if output.exists():
            shutil.rmtree(output)
        shutil.move(str(staged), output)
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "_site")
    args = parser.parse_args()
    print(f"Built verified static site: {build(args.output)}")
