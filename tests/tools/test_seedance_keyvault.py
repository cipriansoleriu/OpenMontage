"""key_alias threading through seedance_video (Persona fork, M1 proof tool).

Hermetic: the vault singleton is primed with an injected-env KeyVault so no
os.environ, .env, or ~/.persona/keys.json state leaks in, and no network is
touched (execute() either fails at key resolution or hits a patched uploader).
"""

from __future__ import annotations

from pathlib import Path

import pytest

import lib.keyvault as kv
from lib.keyvault import KeyVault
from tools.base_tool import ToolStatus
from tools.video.seedance_video import SeedanceVideo

NO_KEYS_FILE = Path("/nonexistent/keys.json")


@pytest.fixture
def prime_vault(monkeypatch):
    def _prime(env: dict[str, str], keys_file: Path = NO_KEYS_FILE) -> KeyVault:
        vault = KeyVault(env=env, keys_file=keys_file)
        monkeypatch.setattr(kv, "_vault", vault)
        return vault

    return _prime


def test_key_alias_selects_named_key(prime_vault):
    prime_vault(
        {"PERSONA_KEY_fal_client": "named-secret", "FAL_KEY": "conventional-secret"}
    )
    tool = SeedanceVideo()
    assert tool._get_api_key("client") == "named-secret"
    # alias-less calls stay on the conventional key (billing never moves silently)
    assert tool._get_api_key() == "conventional-secret"


def test_no_alias_falls_back_to_conventional_fal_key(prime_vault):
    prime_vault({"FAL_KEY": "conventional-secret"})
    assert SeedanceVideo()._get_api_key() == "conventional-secret"


def test_execute_with_unknown_alias_fails_cleanly_without_network(prime_vault):
    prime_vault({"FAL_KEY": "conventional-secret"})
    result = SeedanceVideo().execute({"prompt": "a cat", "key_alias": "nope"})
    assert result.success is False
    assert "nope" in result.error
    assert "conventional-secret" not in result.error


def test_execute_without_any_key_reports_install_instructions(prime_vault):
    prime_vault({})
    result = SeedanceVideo().execute({"prompt": "a cat"})
    assert result.success is False
    assert "FAL_KEY" in result.error
    assert "fal.ai" in result.error  # install_instructions appended


def test_status_reflects_vault_resolution(prime_vault):
    prime_vault({"PERSONA_KEY_fal_main": "named-secret"})
    assert SeedanceVideo().get_status() == ToolStatus.AVAILABLE
    prime_vault({})
    assert SeedanceVideo().get_status() == ToolStatus.UNAVAILABLE


def test_malformed_keys_file_degrades_status_and_never_raises(prime_vault, tmp_path):
    keys_file = tmp_path / "keys.json"
    keys_file.write_text("{not json")
    prime_vault({"FAL_KEY": "conventional-secret"}, keys_file=keys_file)
    tool = SeedanceVideo()
    assert tool.get_status() == ToolStatus.UNAVAILABLE  # degraded, not crashed
    result = tool.execute({"prompt": "a cat"})  # must not raise
    assert result.success is False
    assert "keys.json" in result.error


def test_aliased_key_threads_into_fal_upload(prime_vault, monkeypatch, tmp_path):
    prime_vault({"PERSONA_KEY_fal_client": "named-secret"})  # no FAL_KEY at all
    image = tmp_path / "frame.png"
    image.write_bytes(b"png")
    seen: dict[str, str | None] = {}

    def fake_upload(image_path: str, api_key: str | None = None) -> str:
        seen["api_key"] = api_key
        raise RuntimeError("stop-before-network")

    import tools.video._shared as shared

    monkeypatch.setattr(shared, "upload_image_fal", fake_upload)
    result = SeedanceVideo().execute(
        {
            "prompt": "a cat",
            "operation": "image_to_video",
            "image_path": str(image),
            "key_alias": "client",
        }
    )
    # upload got the vault-resolved key (no cross-account billing split) and
    # its failure came back as a ToolResult, not a raise
    assert seen["api_key"] == "named-secret"
    assert result.success is False
    assert "stop-before-network" in result.error


def test_input_schema_declares_key_alias():
    props = SeedanceVideo.input_schema["properties"]
    assert "key_alias" in props
    # key choice must not affect the idempotency/cache key
    assert "key_alias" not in SeedanceVideo.idempotency_key_fields
