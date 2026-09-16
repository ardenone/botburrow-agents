#!/usr/bin/env python3
"""
Fail on any unpinned container image reference.

Fleet policy: runtime images must be pinned — never `:latest`, never a bare
git SHA, never an implicit (missing) tag. First-party images
(ghcr.io/ardenone/botburrow-agents, botburrow-sandbox) must additionally use
a semver X.Y.Z tag, the source of which is the repo's VERSION file.

Scans:
  - k8s/**/*.{yaml,yml}        every `image:` key and kustomize `newTag:`
  - cluster-configuration/**   same
  - docker/docker-compose.yaml `image:` keys
  - docker/Dockerfile*         FROM lines

A digest reference (`image@sha256:...`) counts as pinned. A tag that is not
`latest`, not a bare SHA, and present is accepted for third-party images
(e.g. `python:3.12-slim`, `valkey/valkey:8-alpine`).

Usage:
    python3 scripts/check_image_pins.py [paths...]

With no arguments, scans the default roots above. Exits 0 when clean,
1 when violations are found, 2 on usage/IO errors.
"""

import re
import sys
from dataclasses import dataclass
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent

DEFAULT_ROOTS = ("k8s", "cluster-configuration", "docker")
YAML_SUFFIXES = {".yaml", ".yml"}

# Images this repo (or its fleet siblings) build and publish. These must
# carry an exact semver tag, not just any non-latest tag.
FIRST_PARTY_PATTERNS = (
    "ardenone/botburrow-agents",
    "ardenone/botburrow-sandbox",
    "botburrow-agents",
    "botburrow-sandbox",
)

SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")
BARE_SHA_RE = re.compile(r"^[0-9a-fA-F]{7,40}$")
DIGEST_RE = re.compile(r"^[0-9a-zA-Z_+.-]+:[0-9a-fA-F]{32,}$")

FROM_RE = re.compile(r"^\s*FROM\s+(.+)$", re.IGNORECASE)


@dataclass
class Violation:
    file: Path
    line: int
    image: str
    reason: str

    def __str__(self) -> str:
        return f"{self.file}:{self.line}: {self.image}: {self.reason}"


def is_first_party(image_ref: str) -> bool:
    """True if the image is one this fleet publishes itself."""
    return any(p in image_ref for p in FIRST_PARTY_PATTERNS)


def classify_tag(image_ref: str, tag: str) -> str | None:
    """Return a violation reason for a tag, or None if it is pinned."""
    if tag.lower() == "latest":
        return ":latest is not allowed (pin a semver tag)"
    if BARE_SHA_RE.fullmatch(tag):
        return "bare git SHA tag is not allowed (pin a semver tag)"
    if is_first_party(image_ref) and not SEMVER_RE.fullmatch(tag):
        return (
            "first-party image must be pinned to a semver X.Y.Z tag "
            "from the repo VERSION file"
        )
    return None


def split_image_ref(image_ref: str) -> tuple[str, str | None]:
    """Split an image reference into (repository, tag-or-digest).

    The tag is everything after the last ':' that follows the last '/',
    so registry ports (localhost:5000/img) are not mistaken for tags.
    A digest reference keeps the whole '@sha256:...' suffix as the tag.
    """
    ref = image_ref.strip()
    if "@" in ref:
        repo, _, digest = ref.partition("@")
        return repo, digest
    slash = ref.rfind("/")
    colon = ref.rfind(":")
    if colon > slash:
        return ref[:colon], ref[colon + 1:]
    return ref, None


def check_image_ref(image_ref: str) -> str | None:
    """Return a violation reason for a full image reference, or None."""
    ref = image_ref.strip()
    if not ref:
        return "empty image reference"
    repo, tag = split_image_ref(ref)
    if tag is None:
        return "no tag (implicit :latest) is not allowed (pin a semver tag)"
    if DIGEST_RE.fullmatch(tag):
        return None  # digest-pinned, always acceptable
    return classify_tag(ref, tag)


def scan_yaml_file(path: Path) -> list[Violation]:
    violations: list[Violation] = []
    try:
        text = path.read_text(encoding="utf-8")
        docs = list(yaml.safe_load_all(text))
    except (OSError, yaml.YAMLError) as exc:
        return [Violation(path, 0, "<unreadable>", f"could not parse: {exc}")]

    def line_of(node: object) -> int:
        mark = getattr(node, "start_mark", None)
        return mark.line + 1 if mark else 0

    for doc in docs:
        if doc is None:
            continue
        stack = [doc]
        while stack:
            node = stack.pop()
            if isinstance(node, dict):
                for key, value in node.items():
                    if not isinstance(value, str):
                        if value is not None:
                            stack.append(value)
                        continue
                    if key == "image":
                        reason = check_image_ref(value)
                        if reason:
                            violations.append(
                                Violation(path, line_of(value), value, reason)
                            )
                    elif key == "newTag":
                        # kustomize images transformer: first-party is
                        # decided by the sibling name/newName entry.
                        sibling = node.get("newName") or node.get("name") or ""
                        reason = check_image_ref(f"{sibling}:{value}")
                        if reason:
                            violations.append(
                                Violation(path, line_of(value), value, reason)
                            )
            elif isinstance(node, list):
                stack.extend(node)
    return violations


def scan_dockerfile(path: Path) -> list[Violation]:
    violations: list[Violation] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        return [Violation(path, 0, "<unreadable>", f"could not read: {exc}")]
    for lineno, line in enumerate(lines, start=1):
        match = FROM_RE.match(line)
        if not match:
            continue
        # FROM [--platform=X] image [AS name] — first non-flag token.
        image = next(
            (t for t in match.group(1).split() if not t.startswith("--")),
            "",
        )
        reason = check_image_ref(image)
        if reason:
            violations.append(Violation(path, lineno, image, reason))
    return violations


def collect_files(roots: list[Path]) -> tuple[list[Path], list[Path]]:
    yaml_files: list[Path] = []
    dockerfiles: list[Path] = []
    for root in roots:
        if root.is_file():
            if root.suffix in YAML_SUFFIXES:
                yaml_files.append(root)
            elif root.name.startswith("Dockerfile"):
                dockerfiles.append(root)
            continue
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*")):
            if ".venv" in path.parts or ".git" in path.parts:
                continue
            if path.suffix in YAML_SUFFIXES:
                yaml_files.append(path)
            elif path.name.startswith("Dockerfile"):
                dockerfiles.append(path)
    return yaml_files, dockerfiles


def scan(roots: list[Path]) -> list[Violation]:
    yaml_files, dockerfiles = collect_files(roots)
    violations: list[Violation] = []
    for path in yaml_files:
        violations.extend(scan_yaml_file(path))
    for path in dockerfiles:
        violations.extend(scan_dockerfile(path))
    return violations


def version_mismatches(roots: list[Path]) -> list[str]:
    """Warn when a first-party tag differs from the repo VERSION file.

    A mismatch is expected between a CI build (which auto-bumps VERSION)
    and the next manifest re-pin, so this is advisory, not a failure.
    """
    version_file = REPO_ROOT / "VERSION"
    try:
        current = version_file.read_text(encoding="utf-8").strip()
    except OSError:
        return []
    if not SEMVER_RE.fullmatch(current):
        return [f"VERSION file does not contain a semver: {current!r}"]
    warnings = []
    yaml_files, _ = collect_files(roots)
    for path in yaml_files:
        try:
            docs = list(yaml.safe_load_all(path.read_text(encoding="utf-8")))
        except (OSError, yaml.YAMLError):
            continue
        stack = list(docs)
        while stack:
            node = stack.pop()
            if isinstance(node, dict):
                for key, value in node.items():
                    if key == "image" and isinstance(value, str):
                        repo, tag = split_image_ref(value)
                        if is_first_party(repo) and tag and tag != current:
                            warnings.append(
                                f"{path}: {value} != VERSION {current} "
                                "(re-pin after the next build)"
                            )
                    elif isinstance(value, (dict, list)):
                        stack.append(value)
            elif isinstance(node, list):
                stack.extend(node)
    return warnings


def main(argv: list[str]) -> int:
    roots = [Path(a) for a in argv] if argv else [
        REPO_ROOT / r for r in DEFAULT_ROOTS
    ]
    for root in roots:
        if not root.exists():
            print(f"error: path does not exist: {root}", file=sys.stderr)
            return 2

    violations = scan(roots)
    for v in violations:
        print(f"UNPINNED {v}", file=sys.stderr)
    for w in version_mismatches(roots):
        print(f"warning: {w}", file=sys.stderr)

    if violations:
        print(
            f"\n{len(violations)} unpinned image reference(s) found. "
            "Pin every image to a semver tag (first-party tags come from "
            "the repo VERSION file).",
            file=sys.stderr,
        )
        return 1
    print("image pins: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
