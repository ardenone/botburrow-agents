"""Guard the contract between secret manifests and the env vars the app reads.

The 401 outage (docs/ACTION-REQUIRED-hub-auth-fix.md) happened because the
secret manifests and sealing docs carried keys like ``HUB_API_KEY`` while the
application reads ``BOTBURROW_HUB_API_KEY`` (pydantic-settings
``env_prefix="BOTBURROW_"`` in ``config.py``). These tests fail if any secret
manifest under ``k8s/`` carries a key the coordinator/runner code cannot
actually read, if a workload manifest references a secret key that no
secret manifest defines, or if a script inside ``k8s/`` reads a secret key
via a ``.data.KEY`` jsonpath that no secret manifest defines.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import yaml

from botburrow_agents.config import Settings

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src" / "botburrow_agents"

# Every manifest that defines (or seals) the secret payloads.
SECRET_MANIFESTS = [
    REPO_ROOT / "k8s/apexalgo-iad/botburrow-agents-secrets-PLACEHOLDER.yml",
    REPO_ROOT / "k8s/apexalgo-iad/botburrow-agents-secret.yml.template",
    REPO_ROOT / "k8s/apexalgo-iad/botburrow-agents-sealedsecrets.yml.template",
]

# Keys kept in the secret for parity with the live cluster secret (and the
# preservation logic in scripts/fix-hub-auth.sh) but not read by the Python
# code. Every entry here is a deliberate, documented exception; a new key
# landing in a manifest without being read anywhere must fail instead of
# being added here.
KNOWN_UNREAD_KEYS = {"FORGEJO_USER", "FORGEJO_TOKEN", "GITHUB_USER"}

# Standalone MCP server processes get their credentials injected by the runner
# (mcp/manager.py copies pod env and explicitly sets e.g. HUB_API_KEY from
# HUB_API_KEY_MCP), so a literal read inside mcp/servers/ says nothing about
# which pod env names are live. Counting it would legitimize an unprefixed
# HUB_API_KEY secret key - the exact bug these tests guard against.
DIRECT_READ_EXCLUDED_DIRS = {"mcp/servers"}


def settings_env_vars() -> set[str]:
    """Env var names pydantic-settings maps onto Settings fields."""
    prefix = Settings.model_config.get("env_prefix", "")
    return {f"{prefix}{field.upper()}" for field in Settings.model_fields}


def _is_os_environ(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Attribute)
        and node.attr == "environ"
        and isinstance(node.value, ast.Name)
        and node.value.id == "os"
    )


def _direct_env_reads(path: Path) -> set[str]:
    """Literal env var names read via os.environ/os.getenv in one file."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: set[str] = set()
    for node in ast.walk(tree):
        # os.environ["NAME"] (loads only - os.environ["NAME"] = x is a write)
        if (
            isinstance(node, ast.Subscript)
            and isinstance(node.ctx, ast.Load)
            and _is_os_environ(node.value)
            and isinstance(node.slice, ast.Constant)
            and isinstance(node.slice.value, str)
        ):
            found.add(node.slice.value)
            continue
        # os.environ.get("NAME"...) / os.getenv("NAME"...)
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
            continue
        func = node.func
        if func.attr == "get" and _is_os_environ(func.value):
            is_env_read = True
        elif func.attr == "getenv" and isinstance(func.value, ast.Name) and func.value.id == "os":
            is_env_read = True
        else:
            is_env_read = False
        if is_env_read and node.args and isinstance(node.args[0], ast.Constant):
            found.add(node.args[0].value)
    return found


def readable_env_vars() -> set[str]:
    """Every env var name the coordinator/runner code can actually read."""
    reads: set[str] = settings_env_vars()
    for path in SRC_DIR.rglob("*.py"):
        rel = path.relative_to(SRC_DIR).as_posix()
        if any(rel.startswith(d) or f"/{d}/" in f"/{rel}" for d in DIRECT_READ_EXCLUDED_DIRS):
            continue
        reads |= _direct_env_reads(path)
    return reads


def _secret_manifests() -> dict[str, dict[str, set[str]]]:
    """{file: {secret name: set of data keys}} for every secret manifest."""
    manifests: dict[str, dict[str, set[str]]] = {}
    for path in SECRET_MANIFESTS:
        docs = yaml.safe_load_all(path.read_text(encoding="utf-8"))
        secrets: dict[str, set[str]] = {}
        for doc in docs:
            if not isinstance(doc, dict) or doc.get("kind") != "Secret":
                continue
            payload = doc.get("stringData") or doc.get("data") or {}
            secrets[doc["metadata"]["name"]] = set(payload)
        manifests[f"k8s/apexalgo-iad/{path.name}"] = secrets
    return manifests


def _merged_secret_keys() -> dict[str, set[str]]:
    merged: dict[str, set[str]] = {}
    for secrets in _secret_manifests().values():
        for name, keys in secrets.items():
            merged.setdefault(name, set()).update(keys)
    return merged


def test_secret_manifest_keys_are_readable_env_vars() -> None:
    """Every key in a secret manifest must be an env var the code reads."""
    readable = readable_env_vars()
    allowed = readable | KNOWN_UNREAD_KEYS
    for manifest, secrets in _secret_manifests().items():
        for secret_name, keys in secrets.items():
            unread = keys - allowed
            assert not unread, (
                f"{manifest}: secret {secret_name} defines keys the application "
                f"never reads: {sorted(unread)}. Settings fields are read as "
                f"'{Settings.model_config.get('env_prefix', '')}<FIELD>' and other "
                f"names must appear as a literal os.environ/os.getenv read in "
                f"src/. If the key is genuinely unused, remove it from the "
                f"manifest instead of adding it here."
            )


def test_hub_api_key_uses_botburrow_prefix() -> None:
    """Direct regression test for the 401 outage key naming."""
    for manifest, secrets in _secret_manifests().items():
        keys = secrets.get("botburrow-agents-secrets", set())
        assert "HUB_API_KEY" not in keys, (
            f"{manifest}: use BOTBURROW_HUB_API_KEY - config.py env_prefix means "
            f"an unprefixed HUB_API_KEY is invisible to the application"
        )
        assert "BOTBURROW_HUB_API_KEY" in keys, (
            f"{manifest}: botburrow-agents-secrets must define BOTBURROW_HUB_API_KEY"
        )


def test_secret_manifests_agree_on_key_sets() -> None:
    """The placeholder and both sealing templates must define the same keys."""
    manifests = _secret_manifests()
    reference_name, reference = next(iter(manifests.items()))
    for other_name, secrets in manifests.items():
        if other_name == reference_name:
            continue
        assert secrets == reference, (
            f"{other_name} disagrees with {reference_name}: "
            f"only in {other_name}: "
            f"{ {k: v - reference.get(k, set()) for k, v in secrets.items()} }, "
            f"only in {reference_name}: "
            f"{ {k: v - secrets.get(k, set()) for k, v in reference.items()} }"
        )


def test_workloads_only_reference_existing_secret_keys() -> None:
    """secretKeyRef entries must name keys the secret manifests actually define."""
    merged = _merged_secret_keys()
    for path in sorted((REPO_ROOT / "k8s").rglob("*.y*ml")):
        if path.is_dir():
            continue
        for doc in yaml.safe_load_all(path.read_text(encoding="utf-8")):
            if not isinstance(doc, dict):
                continue
            for container in _containers(doc):
                for env_var in container.get("env", []):
                    ref = (env_var.get("valueFrom") or {}).get("secretKeyRef")
                    if not ref:
                        continue
                    secret_name, key = ref["name"], ref["key"]
                    assert key in merged.get(secret_name, set()), (
                        f"{path.relative_to(REPO_ROOT)}: {doc.get('kind')} "
                        f"{doc.get('metadata', {}).get('name', '?')} references "
                        f"secret {secret_name} key '{key}', which no secret "
                        f"manifest defines. Defined keys: "
                        f"{sorted(merged.get(secret_name, set()))}"
                    )


def _containers(doc: dict) -> list[dict]:
    """All containers+initContainers of any pod-carrying k8s document."""
    containers: list[dict] = []
    kind = doc.get("kind")
    spec = doc.get("spec", {})
    if kind in {"Deployment", "StatefulSet", "DaemonSet", "Job", "CronJob"}:
        template = spec.get("template", {})
        pod_spec = template.get("spec", {})
    elif kind == "Pod":
        pod_spec = spec
    else:
        return containers
    containers.extend(pod_spec.get("containers", []))
    containers.extend(pod_spec.get("initContainers", []))
    return containers


def test_jsonpath_secret_reads_reference_defined_keys() -> None:
    """.data.KEY reads inside k8s/apexalgo-iad must name keys the secrets define.

    argocd-health-checks.yaml used to probe ``.data.HUB_API_KEY`` and would have
    failed every ArgoCD pre-sync validation once the secret was renamed - a key
    rename must update its consumers in the same change.
    """
    merged = _merged_secret_keys()
    allowed = set().union(*merged.values()) if merged else set()
    pattern = re.compile(r"\.data\.([A-Z_][A-Z0-9_]*)")
    for path in sorted((REPO_ROOT / "k8s" / "apexalgo-iad").rglob("*")):
        if not path.is_file() or path.suffix not in {".yaml", ".yml", ".md", ".sh", ".template"}:
            continue
        for match in pattern.finditer(path.read_text(encoding="utf-8", errors="replace")):
            key = match.group(1)
            assert key in allowed, (
                f"{path.relative_to(REPO_ROOT)} reads secret key '{key}' via "
                f".data.{key}, which no secret manifest defines. Defined keys: "
                f"{sorted(allowed)}. Update consumers in the same change that "
                f"renames a secret key."
            )
