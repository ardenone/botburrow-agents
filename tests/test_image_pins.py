"""Tests for the image-pin policy check (scripts/check_image_pins.py).

Fleet policy: no ``:latest``, no bare git SHA, no implicit tag; first-party
images must carry a semver tag sourced from the repo VERSION file.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "check_image_pins.py"

spec = importlib.util.spec_from_file_location("check_image_pins", SCRIPT)
if spec is None or spec.loader is None:  # pragma: no cover - load failure
    raise ImportError(f"cannot load {SCRIPT}")
cip = importlib.util.module_from_spec(spec)
sys.modules["check_image_pins"] = cip
spec.loader.exec_module(cip)


class TestClassifyImageRef:
    def test_latest_is_rejected(self):
        assert cip.check_image_ref("ghcr.io/ardenone/botburrow-agents:latest")
        assert cip.check_image_ref("alpine/git:latest")
        assert cip.check_image_ref("bitnami/kubectl:latest")

    def test_untagged_is_rejected(self):
        assert cip.check_image_ref("ghcr.io/ardenone/botburrow-agents")
        assert cip.check_image_ref("alpine/git")

    def test_bare_sha_is_rejected(self):
        assert cip.check_image_ref("ghcr.io/ardenone/botburrow-agents:abc1234")
        assert cip.check_image_ref(
            "ghcr.io/ardenone/botburrow-agents:"
            "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2"
        )

    def test_first_party_requires_semver(self):
        assert (
            cip.check_image_ref("ghcr.io/ardenone/botburrow-agents:v0.1.1")
            is not None
        )
        assert cip.check_image_ref("ghcr.io/ardenone/botburrow-agents:0.1") is not None
        assert cip.check_image_ref("ghcr.io/ardenone/botburrow-sandbox:0.1.1") is None

    def test_semver_first_party_passes(self):
        assert cip.check_image_ref("ghcr.io/ardenone/botburrow-agents:0.1.1") is None

    def test_third_party_version_tags_pass(self):
        assert cip.check_image_ref("alpine/git:v2.54.0") is None
        assert cip.check_image_ref("registry.k8s.io/kubectl:v1.34.9") is None
        assert cip.check_image_ref("valkey/valkey:8-alpine") is None
        assert cip.check_image_ref("python:3.12-slim") is None

    def test_digest_pin_passes(self):
        digest = "sha256:" + "0" * 64
        assert cip.check_image_ref(f"ghcr.io/ardenone/botburrow-agents@{digest}") is None
        assert cip.check_image_ref(f"alpine/git@{digest}") is None

    def test_registry_port_is_not_a_tag(self):
        # localhost:5000/img has no tag -> rejected; localhost:5000/img:1.2.3 ok
        assert cip.check_image_ref("localhost:5000/img") is not None
        assert cip.check_image_ref("localhost:5000/img:1.2.3") is None


class TestScanTree:
    def test_repo_manifests_are_pinned(self):
        """The real k8s/, cluster-configuration/ and docker/ trees are clean."""
        roots = [REPO_ROOT / r for r in cip.DEFAULT_ROOTS]
        violations = cip.scan(roots)
        assert violations == []

    def test_unpinned_manifest_fails_scan(self, tmp_path: Path):
        manifest = tmp_path / "deploy.yaml"
        manifest.write_text(
            "apiVersion: apps/v1\n"
            "kind: Deployment\n"
            "spec:\n"
            "  template:\n"
            "    spec:\n"
            "      containers:\n"
            "        - name: app\n"
            "          image: ghcr.io/ardenone/botburrow-agents:latest\n"
        )
        violations = cip.scan([manifest])
        assert len(violations) == 1
        assert ":latest is not allowed" in violations[0].reason

    def test_kustomize_newtag_is_checked(self, tmp_path: Path):
        kustomization = tmp_path / "kustomization.yaml"
        kustomization.write_text(
            "images:\n"
            "  - name: ghcr.io/ardenone/botburrow-agents\n"
            "    newName: ghcr.io/ardenone/botburrow-agents\n"
            "    newTag: latest\n"
        )
        violations = cip.scan([kustomization])
        assert len(violations) == 1

    def test_dockerfile_latest_from_fails_scan(self, tmp_path: Path):
        dockerfile = tmp_path / "Dockerfile.test"
        dockerfile.write_text("FROM python:latest\nRUN true\n")
        violations = cip.scan([dockerfile])
        assert len(violations) == 1
