"""Verify a SHA-256 manifest containing files beside the manifest itself."""

from __future__ import annotations

import argparse
import hashlib
import re
from pathlib import Path


SHA256_LINE = re.compile(r"^([0-9a-f]{64})  ([^/\\]+)$")


def verify_manifest(path: str | Path) -> list[tuple[str, str]]:
    manifest = Path(path)
    verified: list[tuple[str, str]] = []
    for line_number, line in enumerate(
        manifest.read_text(encoding="utf-8").splitlines(),
        start=1,
    ):
        if not line:
            continue
        match = SHA256_LINE.fullmatch(line)
        if match is None:
            raise ValueError(f"{manifest}:{line_number}: invalid manifest line")
        expected, filename = match.groups()
        artifact = manifest.parent / filename
        if not artifact.is_file():
            raise FileNotFoundError(f"manifest artifact does not exist: {artifact}")
        actual = hashlib.sha256(artifact.read_bytes()).hexdigest()
        if actual != expected:
            raise ValueError(
                f"checksum mismatch for {artifact}: expected {expected}, got {actual}"
            )
        verified.append((filename, actual))
    if not verified:
        raise ValueError(f"{manifest}: manifest contains no artifacts")
    return verified


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest")
    args = parser.parse_args()
    verified = verify_manifest(args.manifest)
    for filename, digest in verified:
        print(f"verified {digest}  {filename}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
