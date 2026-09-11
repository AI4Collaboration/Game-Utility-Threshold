import hashlib
import tempfile
import unittest
from pathlib import Path

from scripts.verify_artifact_manifest import verify_manifest


class ArtifactManifestTests(unittest.TestCase):
    def test_valid_manifest_verifies(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            artifact = root / "artifact.json"
            artifact.write_bytes(b'{"complete":true}\n')
            digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
            manifest = root / "checksums.sha256"
            manifest.write_text(f"{digest}  artifact.json\n", encoding="utf-8")
            self.assertEqual(verify_manifest(manifest), [("artifact.json", digest)])

    def test_tampering_and_path_traversal_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            artifact = root / "artifact.json"
            artifact.write_text("changed", encoding="utf-8")
            manifest = root / "checksums.sha256"
            manifest.write_text(f"{'0' * 64}  artifact.json\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "checksum mismatch"):
                verify_manifest(manifest)
            manifest.write_text(f"{'0' * 64}  ../artifact.json\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "invalid manifest line"):
                verify_manifest(manifest)


if __name__ == "__main__":
    unittest.main()
