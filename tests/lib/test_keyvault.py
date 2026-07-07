"""Contract tests for lib/keyvault.py (Persona fork, M1).

All hermetic: the vault is constructed with an injected env dict and a
nonexistent keys_file so no real ~/.persona/keys.json or os.environ leaks in.
"""

from __future__ import annotations

import dataclasses
import json
import subprocess
import sys
from pathlib import Path

import pytest

from lib.keyvault import KeyVault, get_vault

NO_KEYS_FILE = Path("/nonexistent/keys.json")


def make_vault(env: dict[str, str], keys_file: Path = NO_KEYS_FILE) -> KeyVault:
    return KeyVault(env=env, keys_file=keys_file)


# ---- Acceptance: several keys per provider, selectable per call ----

def test_two_openrouter_keys_selectable_per_call():
    vault = make_vault(
        {
            "PERSONA_KEY_openrouter_main": "secret-main",
            "PERSONA_KEY_openrouter_client": "secret-client",
        }
    )
    assert vault.resolve("openrouter", "client") == "secret-client"
    assert vault.resolve("openrouter", "main") == "secret-main"
    assert vault.resolve("openrouter") == "secret-main"  # no alias -> 'main'


def test_alias_matching_is_case_insensitive():
    vault = make_vault({"PERSONA_KEY_FAL_Client_EU": "s1"})
    assert vault.resolve("fal", "client_eu") == "s1"
    assert vault.resolve("FAL", "CLIENT_EU") == "s1"


def test_sole_named_key_used_without_alias_when_no_conventional():
    vault = make_vault({"PERSONA_KEY_kie_billing": "s2"})
    assert vault.resolve("kie") == "s2"


# ---- Alias-less precedence: main -> conventional env -> sole named key ----

def test_conventional_env_beats_sole_non_main_named_key():
    # Adding one client-specific named key must NOT silently move alias-less
    # calls (and their billing) off the conventional key already in use.
    vault = make_vault(
        {"PERSONA_KEY_fal_acme": "client-secret", "FAL_KEY": "personal-secret"}
    )
    assert vault.resolve("fal") == "personal-secret"
    assert vault.resolve("fal", "acme") == "client-secret"


def test_main_still_beats_conventional_env():
    vault = make_vault({"PERSONA_KEY_fal_main": "named", "FAL_KEY": "conventional"})
    assert vault.resolve("fal") == "named"


# ---- Conventional env fallbacks ----

def test_kie_fallback_uses_canonical_kie_ai_api_key():
    vault = make_vault({"KIE_AI_API_KEY": "kie-conventional"})
    assert vault.resolve("kie") == "kie-conventional"


def test_fal_fallback_chain_matches_tool_behavior():
    assert make_vault({"FAL_KEY": "a"}).resolve("fal") == "a"
    assert make_vault({"FAL_AI_API_KEY": "b"}).resolve("fal") == "b"
    assert make_vault({"FAL_KEY": "a", "FAL_AI_API_KEY": "b"}).resolve("fal") == "a"


def test_conventional_env_read_from_injected_env_not_os_environ(monkeypatch):
    monkeypatch.setenv("FAL_KEY", "from-os-environ")
    with pytest.raises(KeyError):
        make_vault({}).resolve("fal")


# ---- Ambiguity and errors (aliases only, never secrets) ----

def test_multiple_keys_without_main_and_no_conventional_is_ambiguous():
    vault = make_vault(
        {"PERSONA_KEY_openrouter_a": "s1", "PERSONA_KEY_openrouter_b": "s2"}
    )
    with pytest.raises(KeyError, match="none named 'main'"):
        vault.resolve("openrouter")


def test_conventional_env_breaks_the_ambiguity():
    vault = make_vault(
        {
            "PERSONA_KEY_openrouter_a": "s1",
            "PERSONA_KEY_openrouter_b": "s2",
            "OPENROUTER_API_KEY": "conventional",
        }
    )
    assert vault.resolve("openrouter") == "conventional"


def test_unknown_alias_error_lists_aliases_but_no_secrets():
    vault = make_vault({"PERSONA_KEY_fal_main": "topsecret-value"})
    with pytest.raises(KeyError) as exc:
        vault.resolve("fal", "nope")
    message = str(exc.value)
    assert "main" in message and "nope" in message
    assert "topsecret-value" not in message


def test_missing_provider_error_names_conventional_var():
    with pytest.raises(KeyError, match="KIE_AI_API_KEY"):
        make_vault({}).resolve("kie")


def test_case_variant_collision_raises_naming_both_env_vars():
    vault = make_vault(
        {"PERSONA_KEY_fal_Main": "secret-A", "PERSONA_KEY_FAL_MAIN": "secret-B"}
    )
    with pytest.raises(KeyError) as exc:
        vault.resolve("fal")
    message = str(exc.value)
    assert "PERSONA_KEY_fal_Main" in message and "PERSONA_KEY_FAL_MAIN" in message
    assert "secret-A" not in message and "secret-B" not in message


# ---- No secrets in any inspectable surface ----

def test_list_repr_and_asdict_never_contain_secrets():
    vault = make_vault({"PERSONA_KEY_replicate_main": "r8-secret"})
    entry = vault._entries[0]
    dumped = (
        json.dumps(vault.list())
        + repr(vault._entries)
        + json.dumps(dataclasses.asdict(entry))
        + str(entry)
    )
    assert "r8-secret" not in dumped
    assert vault.list()[0]["alias"] == "main"
    assert not hasattr(entry, "secret")  # secrets live outside KeyEntry


# ---- keys.json overrides ----

def test_keys_file_annotates_and_overrides(tmp_path):
    keys_file = tmp_path / "keys.json"
    keys_file.write_text(
        json.dumps(
            [
                {"provider": "openrouter", "alias": "main", "label": "personal", "cap_usd": 20},
                {"provider": "kie", "alias": "extra", "secret": "from-file"},
            ]
        )
    )
    vault = make_vault({"PERSONA_KEY_openrouter_main": "env-secret"}, keys_file=keys_file)
    assert vault.resolve("openrouter") == "env-secret"  # annotation kept env secret
    assert vault.list()[0]["label"] == "personal"
    assert vault.resolve("kie", "extra") == "from-file"


def test_malformed_keys_file_never_breaks_construction_but_blocks_resolve(tmp_path):
    # A user typo in an optional dotfile must never crash get_status()/preflight
    # for every tool; the error surfaces loudly at the point of use instead.
    keys_file = tmp_path / "keys.json"
    keys_file.write_text("{not json")
    vault = make_vault({"PERSONA_KEY_fal_main": "s"}, keys_file=keys_file)  # no raise
    assert vault.keys_file_error and "keys.json" in vault.keys_file_error
    with pytest.raises(KeyError, match="Key resolution blocked"):
        vault.resolve("fal")


# ---- Singleton + CLI ----

def test_get_vault_returns_cached_instance(monkeypatch):
    import lib.keyvault as kv

    sentinel = make_vault({})
    monkeypatch.setattr(kv, "_vault", sentinel)
    assert get_vault() is sentinel


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX-only subprocess env")
def test_cli_lists_aliases_without_secrets(tmp_path):
    repo_root = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        [sys.executable, "-m", "lib.keyvault"],
        capture_output=True,
        text=True,
        cwd=repo_root,
        env={
            "PATH": "/usr/bin:/bin",
            "HOME": str(tmp_path),  # keep any real ~/.persona/keys.json out
            "PERSONA_KEY_openrouter_main": "supersecret123",
            "PERSONA_KEY_openrouter_client": "supersecret456",
        },
        timeout=60,
    )
    assert result.returncode == 0, result.stderr
    assert "openrouter" in result.stdout
    assert "client" in result.stdout
    assert "supersecret123" not in result.stdout
    assert "supersecret456" not in result.stdout
