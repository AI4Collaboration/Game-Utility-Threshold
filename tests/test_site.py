"""Verify publication completeness, project-subpath links, and exclusion boundaries."""

from hashlib import sha256
import gzip
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from urllib.parse import urljoin, urlsplit
from zipfile import ZipFile

import build_site


class PublicationBoundaryTests(unittest.TestCase):
    def test_allowlist_excludes_unrelated_source_files_and_rejects_symlinks(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            expected = [*(Path("web") / p for p in build_site.WEB_FILES), *build_site.SOURCE_FILES]
            for relative in expected:
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("")
            for relative in (".env", "runs/private.json", "data/post/private-notes.md", "web/private.html"):
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("must not be published")
            self.assertEqual(build_site.publication_sources(root), expected)
            selected = root / "web/index.html"
            selected.unlink()
            selected.symlink_to(root / ".env")
            with self.assertRaisesRegex(ValueError, "symlinked"):
                build_site.publication_sources(root)

    def test_scanner_checks_decompressed_credentials_without_disclosing_them(self):
        with tempfile.TemporaryDirectory() as directory:
            secret = "sk-or-v1-" + "f" * 64
            Path(directory, "records.jsonl.gz").write_bytes(gzip.compress(secret.encode()))
            with self.assertRaises(ValueError) as raised:
                build_site.scan_credentials(directory)
            self.assertNotIn(secret, str(raised.exception))
            self.assertIn("Credential-pattern", str(raised.exception))

    def test_unowned_output_is_not_replaced(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory, "private.txt")
            path.write_text("keep this")
            with self.assertRaisesRegex(ValueError, "not owned"):
                build_site.build(directory)
            self.assertEqual(path.read_text(), "keep this")


@unittest.skipUnless(importlib.util.find_spec("matplotlib"), "Optional figures dependency is not installed")
class BuiltSiteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.site = Path(cls.temporary.name) / "project"
        # Report tests exercise optional-import failure paths. A fresh process
        # keeps their module mocks away from NumPy's extension-module state.
        result = subprocess.run([sys.executable, str(build_site.ROOT / "build_site.py"),
                                 "--output", str(cls.site)], cwd=build_site.ROOT,
                                text=True, capture_output=True)
        if result.returncode:
            raise AssertionError(result.stderr)

    def test_complete_datasets_and_manifest_match_original_bytes(self):
        manifest = json.loads((self.site / "site-manifest.json").read_text())
        self.assertEqual(manifest["schema"], build_site.SCHEMA)
        for relative in build_site.SOURCE_FILES:
            self.assertEqual((self.site / relative).read_bytes(), (build_site.ROOT / relative).read_bytes())
        for relative, digest in manifest["files"].items():
            self.assertEqual(sha256((self.site / relative).read_bytes()).hexdigest(), digest, relative)
            self.assertFalse(set(Path(relative).parts) & {".env", ".git", "runs", ".venv"})
        for label, prefix in (("post", Path("data/post")), ("oversight", build_site.OVERSIGHT)):
            with ZipFile(self.site / "downloads" / f"{label}-source.zip") as archive:
                expected = {str(p) for p in build_site.SOURCE_FILES if p.is_relative_to(prefix)}
                self.assertEqual(set(archive.namelist()), expected)
                for relative in expected:
                    self.assertEqual(archive.read(relative), (build_site.ROOT / relative).read_bytes())

    def test_internal_links_work_under_a_project_subpath(self):
        build_site.validate_links(self.site)
        prefix = "https://example.github.io/Game-Utility-Threshold/"
        for page in self.site.rglob("*.html"):
            links = build_site.Links()
            links.feed(page.read_text())
            for link in links.links:
                if urlsplit(link).scheme or urlsplit(link).netloc:
                    continue
                resolved = urljoin(prefix + str(page.relative_to(self.site)), link)
                self.assertTrue(resolved.startswith(prefix), (page.name, link))
        for path in ("report/index.html", "validation/report.html"):
            text = (self.site / path).read_text()
            self.assertIn('href="../results.html"', text)
            self.assertIn('href="../oversight.html"', text)

    def test_catalogue_counts_and_scope_match_saved_results(self):
        page = (self.site / "results.html").read_text()
        oversight = json.loads((self.site / "validation/summary.json").read_text())
        post = json.loads((self.site / "report/summary.json").read_text())
        self.assertIn(f"{oversight['planned']:,}", page)
        self.assertIn(f"{post['valid_games']:,} / {post['planned_games']:,}", page)
        self.assertIn(f"{post['dominance_correct']:,} / {post['dominance_decisions']:,}", page)
        self.assertIn("new fixed-baseline penalty sweep not run", page)
        self.assertIn("Battle of the Sexes", page)
        self.assertIn("Resource control · hidden incentives", page)
        self.assertIn("Off-switch", page)
        for filename in ("resource-control.html", "off-switch.html", "uncertainty.css", "uncertainty.js", "uncertainty-engine.js"):
            self.assertEqual((self.site / filename).read_bytes(), (build_site.ROOT / "web" / filename).read_bytes())
        self.assertIn("before-lesswrong-simplification-2026-11-09", page)
        self.assertIn("not been revalidated or pooled", page)
        self.assertIn("not empirical Nash or Stackelberg play", page)


if __name__ == "__main__":
    unittest.main()
