"""Contract tests for the Persona fork's M3 character tools + registry.

lora_train / keyframe_lock / identity_drift follow the fork's tool contract
(key_alias everywhere, execute never raises, secrets redacted) and the
character registry is a separable JSON store keyed by character, not project.
All hermetic — no network; vault primed with injected envs; registry rooted
in tmp_path via PERSONA_CHARACTERS_DIR.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import lib.keyvault as kv
from lib.character_registry import CharacterNotFound, CharacterRegistry
from lib.keyvault import KeyVault
from tools.analysis.identity_drift import IdentityDrift
from tools.base_tool import BaseTool, ToolStatus
from tools.character.keyframe_lock import KeyframeLock
from tools.character.lora_train import LoraTrain
from tools.tool_registry import ToolRegistry

NO_KEYS_FILE = Path("/nonexistent/keys.json")
REPO_ROOT = Path(__file__).resolve().parents[2]

TOOLS = [LoraTrain, KeyframeLock, IdentityDrift]


@pytest.fixture
def prime_vault(monkeypatch):
    def _prime(env: dict[str, str]) -> None:
        monkeypatch.setattr(kv, "_vault", KeyVault(env=env, keys_file=NO_KEYS_FILE))

    return _prime


@pytest.fixture
def char_root(tmp_path, monkeypatch):
    root = tmp_path / "characters"
    monkeypatch.setenv("PERSONA_CHARACTERS_DIR", str(root))
    return root


def _make_character(root: Path, char_id: str = "ana", n_refs: int = 2) -> CharacterRegistry:
    registry = CharacterRegistry(root)
    registry.create(char_id, name="Ana", description="auburn hair, green eyes")
    for i in range(n_refs):
        src = root / f"src{i}.png"
        src.write_bytes(b"fake-png-%d" % i)
        registry.add_reference(char_id, src)
    return registry


# ---- Character registry (separable JSON store) ----

class TestCharacterRegistry:
    def test_create_get_list_roundtrip(self, tmp_path):
        registry = CharacterRegistry(tmp_path)
        registry.create("ana", name="Ana", description="d")
        assert registry.get("ana")["name"] == "Ana"
        assert [c["id"] for c in registry.list()] == ["ana"]
        assert registry.exists("ana") and not registry.exists("bob")

    def test_invalid_or_duplicate_ids_rejected(self, tmp_path):
        registry = CharacterRegistry(tmp_path)
        with pytest.raises(CharacterNotFound, match="kebab-case"):
            registry.create("Ana Bad!")
        with pytest.raises(CharacterNotFound, match="kebab-case"):
            registry.create("ana\n")  # '$'-anchored regex would allow this
        registry.create("ana")
        with pytest.raises(ValueError, match="already exists"):
            registry.create("ana")

    def test_unknown_character_error_lists_known(self, tmp_path):
        registry = CharacterRegistry(tmp_path)
        registry.create("ana")
        with pytest.raises(CharacterNotFound, match="ana"):
            registry.get("bob")

    def test_references_copied_local_and_recorded(self, tmp_path):
        registry = _make_character(tmp_path, n_refs=2)
        paths = registry.reference_paths("ana")
        assert len(paths) == 2
        assert all(p.is_file() and "refs" in str(p) for p in paths)
        # re-adding the identical file is a no-op, not a duplicate
        registry.add_reference("ana", paths[0])
        assert len(registry.get("ana")["reference_images"]) == 2

    def test_lora_keyed_to_character_and_latest_wins(self, tmp_path):
        registry = _make_character(tmp_path)
        registry.add_lora("ana", {"provider": "fal", "model_family": "flux",
                                  "adapter_url": "https://a/1", "trigger_phrase": "t"})
        registry.add_lora("ana", {"provider": "fal", "model_family": "flux",
                                  "adapter_url": "https://a/2", "trigger_phrase": "t"})
        assert registry.latest_lora("ana")["adapter_url"] == "https://a/2"
        assert registry.latest_lora("ana", model_family="sdxl") is None
        # the adapter lives on the character record — reusable from any project
        raw = json.loads((tmp_path / "ana" / "character.json").read_text())
        assert len(raw["loras"]) == 2

    def test_corrupt_character_does_not_hide_others(self, tmp_path):
        registry = CharacterRegistry(tmp_path)
        registry.create("ana")
        bad = tmp_path / "bob"
        bad.mkdir()
        (bad / "character.json").write_text("{not json")
        assert [c["id"] for c in registry.list()] == ["ana"]

    def test_env_override_root(self, char_root, monkeypatch):
        _make_character(char_root)
        assert CharacterRegistry().get("ana")["id"] == "ana"  # picks up env


# ---- Shared tool contract ----

@pytest.mark.parametrize("cls", TOOLS)
def test_identity_and_key_alias_contract(cls):
    tool = cls()
    assert isinstance(tool, BaseTool)
    assert tool.name and tool.version and tool.capabilities
    props = tool.input_schema["properties"]
    assert "key_alias" in props
    assert "PERSONA_KEY_" in props["key_alias"]["description"]
    assert "key_alias" not in tool.idempotency_key_fields
    assert tool.install_instructions
    for skill in cls.agent_skills:
        assert (REPO_ROOT / ".agents" / "skills" / skill / "SKILL.md").is_file()


@pytest.mark.parametrize("cls", TOOLS)
def test_estimate_cost_never_raises(cls):
    tool = cls()
    assert isinstance(tool.estimate_cost({}), float)
    assert isinstance(tool.estimate_cost({"candidate_paths": "x", "mode": []}), float)


def test_registry_discovers_all_three():
    discovered = ToolRegistry().discover("tools")
    for name in ("lora_train", "keyframe_lock", "identity_drift"):
        assert name in discovered


def test_status_contracts(prime_vault):
    prime_vault({})
    assert LoraTrain().get_status() == ToolStatus.UNAVAILABLE
    assert KeyframeLock().get_status() == ToolStatus.UNAVAILABLE
    assert IdentityDrift().get_status() == ToolStatus.UNAVAILABLE
    prime_vault({"FAL_KEY": "f"})
    assert LoraTrain().get_status() == ToolStatus.AVAILABLE
    assert KeyframeLock().get_status() == ToolStatus.AVAILABLE  # either backend
    prime_vault({"KIE_AI_API_KEY": "k"})
    assert KeyframeLock().get_status() == ToolStatus.AVAILABLE
    prime_vault({"OPENROUTER_API_KEY": "o"})
    assert IdentityDrift().get_status() == ToolStatus.AVAILABLE


# ---- lora_train ----

class TestLoraTrain:
    def test_unknown_character_fails_cleanly(self, prime_vault, char_root):
        prime_vault({"FAL_KEY": "f"})
        result = LoraTrain().execute({"character_id": "ghost"})
        assert result.success is False and "ghost" in result.error

    def test_too_few_refs_fails_cleanly(self, prime_vault, char_root):
        prime_vault({"FAL_KEY": "f"})
        _make_character(char_root, n_refs=2)
        result = LoraTrain().execute({"character_id": "ana"})
        assert result.success is False
        assert "at least 5" in result.error and "have 2" in result.error

    def test_success_stores_adapter_on_character(self, prime_vault, char_root, monkeypatch):
        prime_vault({"FAL_KEY": "f"})
        registry = _make_character(char_root, n_refs=6)
        monkeypatch.setattr(
            LoraTrain, "_upload_archive_fal", staticmethod(lambda z, k: "https://zip")
        )
        import sys
        import types

        fake_requests = types.ModuleType("requests")
        fake_requests.RequestException = type("RequestException", (Exception,), {})

        class _Resp:
            def __init__(self, payload):
                self._p = payload

            def raise_for_status(self):
                pass

            def json(self):
                return self._p

        fake_requests.post = lambda url, **kw: _Resp(
            {"status_url": "s", "response_url": "r", "request_id": "req1"}
        )
        state = {"polls": 0}

        def fake_get(url, **kw):
            if url == "s":
                state["polls"] += 1
                return _Resp({"status": "COMPLETED" if state["polls"] > 1 else "IN_PROGRESS"})
            return _Resp({"diffusers_lora_file": {"url": "https://adapter"}})

        fake_requests.get = fake_get
        monkeypatch.setitem(sys.modules, "requests", fake_requests)
        monkeypatch.setattr("time.sleep", lambda s: None)

        result = LoraTrain().execute({"character_id": "ana", "trigger_phrase": "anak woman"})
        assert result.success, result.error
        assert result.data["adapter_url"] == "https://adapter"
        stored = registry.latest_lora("ana")
        assert stored["adapter_url"] == "https://adapter"
        assert stored["trigger_phrase"] == "anak woman"


# ---- keyframe_lock ----

class TestKeyframeLock:
    def test_unknown_character_fails_cleanly(self, prime_vault, char_root):
        prime_vault({"KIE_AI_API_KEY": "k"})
        result = KeyframeLock().execute({"character_id": "ghost", "prompt": "x"})
        assert result.success is False and "ghost" in result.error

    def test_references_mode_delegates_with_identity_block(
        self, prime_vault, char_root, monkeypatch
    ):
        prime_vault({"KIE_AI_API_KEY": "k"})
        _make_character(char_root, n_refs=3)
        seen: dict[str, dict] = {}

        from tools.base_tool import ToolResult
        from tools.graphics.nano_banana_pro import NanoBananaPro

        def fake_execute(self, inputs):
            seen["inputs"] = inputs
            return ToolResult(success=True, data={}, artifacts=["kf.png"], cost_usd=0.12)

        monkeypatch.setattr(NanoBananaPro, "execute", fake_execute)
        result = KeyframeLock().execute(
            {"character_id": "ana", "prompt": "walking a dog in the park",
             "key_alias": "client", "output_path": "kf.png"}
        )
        assert result.success
        assert result.data["character_id"] == "ana"
        assert len(seen["inputs"]["image_paths"]) == 3
        assert "EXACT identity" in seen["inputs"]["prompt"]
        assert "walking a dog" in seen["inputs"]["prompt"]
        assert seen["inputs"]["key_alias"] == "client"

    def test_lora_mode_without_adapter_fails_cleanly(self, prime_vault, char_root):
        prime_vault({"FAL_KEY": "f"})
        _make_character(char_root)
        result = KeyframeLock().execute(
            {"character_id": "ana", "prompt": "x", "mode": "lora"}
        )
        assert result.success is False and "lora_train" in result.error


# ---- identity_drift ----

class TestIdentityDrift:
    def test_requires_refs_or_character(self, prime_vault, tmp_path):
        prime_vault({"OPENROUTER_API_KEY": "o"})
        img = tmp_path / "c.png"
        img.write_bytes(b"x")
        result = IdentityDrift().execute({"candidate_paths": [str(img)]})
        assert result.success is False and "character_id" in result.error

    def test_missing_files_fail_cleanly(self, prime_vault):
        prime_vault({"OPENROUTER_API_KEY": "o"})
        result = IdentityDrift().execute(
            {"candidate_paths": ["/nope/c.png"], "reference_image_paths": ["/nope/r.png"]}
        )
        assert result.success is False and "not found" in result.error

    def test_judges_and_applies_threshold(self, prime_vault, tmp_path, monkeypatch):
        prime_vault({"OPENROUTER_API_KEY": "o"})
        ref, good, bad = tmp_path / "r.png", tmp_path / "g.png", tmp_path / "b.png"
        for p in (ref, good, bad):
            p.write_bytes(b"png")
        import sys
        import types

        fake_requests = types.ModuleType("requests")
        fake_requests.RequestException = type("RequestException", (Exception,), {})

        class _Resp:
            def raise_for_status(self):
                pass

            def json(self):
                return {
                    "choices": [{"message": {"content": json.dumps({
                        "candidates": [
                            {"index": 1, "same_person": True, "similarity": 0.92, "differences": []},
                            {"index": 2, "same_person": True, "similarity": 0.55,
                             "differences": ["different jawline"]},
                        ]})}}]
                }

        fake_requests.post = lambda url, **kw: _Resp()
        monkeypatch.setitem(sys.modules, "requests", fake_requests)

        result = IdentityDrift().execute(
            {
                "reference_image_paths": [str(ref)],
                "candidate_paths": [str(good), str(bad)],
                "threshold": 0.75,
            }
        )
        assert result.success, result.error
        assert result.data["passed"] is False
        first, second = result.data["results"]
        assert first["passed"] is True and first["drift"] == pytest.approx(0.08)
        assert second["passed"] is False and "jawline" in second["differences"][0]

    def test_judge_failure_is_redacted_toolresult(self, prime_vault, tmp_path, monkeypatch):
        prime_vault({"OPENROUTER_API_KEY": "sk-or-SECRETXYZ"})
        ref = tmp_path / "r.png"
        ref.write_bytes(b"png")
        import sys
        import types

        fake_requests = types.ModuleType("requests")

        def boom(url, **kw):
            raise RuntimeError("InvalidHeader: 'Bearer sk-or-SECRETXYZ'")

        fake_requests.post = boom
        monkeypatch.setitem(sys.modules, "requests", fake_requests)
        result = IdentityDrift().execute(
            {"reference_image_paths": [str(ref)], "candidate_paths": [str(ref)]}
        )
        assert result.success is False
        assert "sk-or-SECRETXYZ" not in result.error
        assert "[REDACTED]" in result.error


# ---- Review-driven regressions (M3): traversal, corruption, never-raise ----

class TestRegistryHardening:
    def test_path_traversal_blocked_on_every_entry_point(self, tmp_path):
        registry = CharacterRegistry(tmp_path)
        for evil in ("../outside", "a/../../b", "/etc", ""):
            with pytest.raises(CharacterNotFound):
                registry.get(evil)
            assert registry.exists(evil) is False
            with pytest.raises((CharacterNotFound, FileNotFoundError)):
                registry.add_lora(evil, {"adapter_url": "https://x"})

    def test_tools_fail_cleanly_on_traversal_ids(self, prime_vault, char_root):
        prime_vault({"FAL_KEY": "f", "KIE_AI_API_KEY": "k", "OPENROUTER_API_KEY": "o"})
        for tool, extra in (
            (LoraTrain(), {}),
            (KeyframeLock(), {"prompt": "x"}),
        ):
            result = tool.execute({"character_id": "../evil", **extra})
            assert result.success is False
            assert "kebab-case" in result.error

    def test_corrupt_record_surfaces_as_character_not_found(self, tmp_path):
        registry = CharacterRegistry(tmp_path)
        bad = tmp_path / "ana"
        bad.mkdir()
        (bad / "character.json").write_text("{not json")
        with pytest.raises(CharacterNotFound, match="corrupt"):
            registry.get("ana")

    def test_tools_fail_cleanly_on_corrupt_record(self, prime_vault, char_root, tmp_path):
        prime_vault({"KIE_AI_API_KEY": "k", "OPENROUTER_API_KEY": "o"})
        bad = char_root / "ana"
        bad.mkdir(parents=True)
        (bad / "character.json").write_text("{not json")
        r1 = KeyframeLock().execute({"character_id": "ana", "prompt": "x"})
        assert r1.success is False and "corrupt" in r1.error
        img = tmp_path / "c.png"
        img.write_bytes(b"x")
        r2 = IdentityDrift().execute({"character_id": "ana", "candidate_paths": [str(img)]})
        assert r2.success is False and "corrupt" in r2.error

    def test_copied_directory_cannot_clobber_original(self, tmp_path):
        import shutil as _shutil

        registry = _make_character(tmp_path, n_refs=1)
        _shutil.copytree(tmp_path / "ana", tmp_path / "ana-v2")
        with pytest.raises(CharacterNotFound, match="does not belong"):
            registry.get("ana-v2")
        src = tmp_path / "new.png"
        src.write_bytes(b"new")
        with pytest.raises(CharacterNotFound, match="does not belong"):
            registry.add_reference("ana-v2", src)
        assert registry.get("ana")["id"] == "ana"  # original untouched

    def test_list_skips_wrong_shape_records_and_error_path_stays_clean(self, tmp_path):
        registry = CharacterRegistry(tmp_path)
        registry.create("ana")
        (tmp_path / "arr").mkdir()
        (tmp_path / "arr" / "character.json").write_text("[]")
        (tmp_path / "noid").mkdir()
        (tmp_path / "noid" / "character.json").write_text("{}")
        assert [c["id"] for c in registry.list()] == ["ana"]
        with pytest.raises(CharacterNotFound):  # message builder must not crash
            registry.get("ghost")

    def test_add_lora_requires_adapter_url(self, tmp_path):
        registry = _make_character(tmp_path)
        with pytest.raises(ValueError, match="adapter_url"):
            registry.add_lora("ana", {"model_family": "flux"})

    def test_missing_reference_paths_reported(self, tmp_path):
        registry = _make_character(tmp_path, n_refs=2)
        registry.reference_paths("ana")[0].unlink()
        assert len(registry.reference_paths("ana")) == 1
        assert len(registry.missing_reference_paths("ana")) == 1

    def test_default_root_expands_user(self, monkeypatch):
        from lib.character_registry import default_root

        monkeypatch.setenv("PERSONA_CHARACTERS_DIR", "~/persona-chars-test")
        assert "~" not in str(default_root())


class TestToolHardeningRegressions:
    def test_identity_drift_bad_threshold_and_paths_never_raise(self, prime_vault, tmp_path):
        prime_vault({"OPENROUTER_API_KEY": "o"})
        img = tmp_path / "c.png"
        img.write_bytes(b"x")
        r = IdentityDrift().execute(
            {"reference_image_paths": [str(img)], "candidate_paths": [str(img)],
             "threshold": "high"}
        )
        assert r.success is False and "threshold" in r.error
        r = IdentityDrift().execute({"candidate_paths": [123]})
        assert r.success is False and "path strings" in r.error
        r = IdentityDrift().execute(
            {"reference_image_paths": 5, "candidate_paths": [str(img)]}
        )
        assert r.success is False and "path strings" in r.error

    def test_identity_drift_malformed_judge_verdict_fails_closed(
        self, prime_vault, tmp_path, monkeypatch
    ):
        prime_vault({"OPENROUTER_API_KEY": "o"})
        ref = tmp_path / "r.png"
        ref.write_bytes(b"png")
        import sys
        import types

        def prime_judge(content):
            fake_requests = types.ModuleType("requests")

            class _Resp:
                def raise_for_status(self):
                    pass

                def json(self):
                    return {"choices": [{"message": {"content": content}}]}

            fake_requests.post = lambda url, **kw: _Resp()
            monkeypatch.setitem(sys.modules, "requests", fake_requests)

        # null similarity coerces to 0.0: the CANDIDATE fails closed, run succeeds
        prime_judge(json.dumps({"candidates": [{"similarity": None, "same_person": True}]}))
        result = IdentityDrift().execute(
            {"reference_image_paths": [str(ref)], "candidate_paths": [str(ref)]}
        )
        assert result.success is True
        assert result.data["passed"] is False
        assert result.data["results"][0]["similarity"] == 0.0

        # structurally broken verdict: the RUN fails cleanly, never raises
        prime_judge(json.dumps({"candidates": ["not-a-dict"]}))
        result = IdentityDrift().execute(
            {"reference_image_paths": [str(ref)], "candidate_paths": [str(ref)]}
        )
        assert result.success is False
        assert "judging failed" in result.error

    def test_lora_train_registry_write_failure_preserves_paid_adapter(
        self, prime_vault, char_root, monkeypatch
    ):
        prime_vault({"FAL_KEY": "f"})
        _make_character(char_root, n_refs=6)
        monkeypatch.setattr(
            LoraTrain, "_upload_archive_fal", staticmethod(lambda z, k: "https://zip")
        )
        import sys
        import types

        fake_requests = types.ModuleType("requests")
        fake_requests.RequestException = type("RequestException", (Exception,), {})

        class _Resp:
            def __init__(self, payload):
                self._p = payload

            def raise_for_status(self):
                pass

            def json(self):
                return self._p

        fake_requests.post = lambda url, **kw: _Resp(
            {"status_url": "s", "response_url": "r", "request_id": "req1"}
        )
        fake_requests.get = lambda url, **kw: _Resp(
            {"status": "COMPLETED"} if url == "s"
            else {"diffusers_lora_file": {"url": "https://adapter"}}
        )
        monkeypatch.setitem(sys.modules, "requests", fake_requests)
        monkeypatch.setattr("time.sleep", lambda s: None)

        from lib.character_registry import CharacterRegistry as _CR

        monkeypatch.setattr(
            _CR, "add_lora", lambda self, cid, a: (_ for _ in ()).throw(OSError("disk full"))
        )
        result = LoraTrain().execute({"character_id": "ana"})
        assert result.success is True  # never raises, never loses the adapter
        assert result.data["adapter_url"] == "https://adapter"
        assert "NOT saved" in result.data["warning_registry_write_failed"]

    def test_lora_train_submit_failure_is_redacted(self, prime_vault, char_root, monkeypatch):
        prime_vault({"FAL_KEY": "sk-fal-SECRETBIT"})
        _make_character(char_root, n_refs=6)
        monkeypatch.setattr(
            LoraTrain,
            "_upload_archive_fal",
            staticmethod(
                lambda z, k: (_ for _ in ()).throw(RuntimeError(f"Key {k} rejected"))
            ),
        )
        result = LoraTrain().execute({"character_id": "ana"})
        assert result.success is False
        assert "sk-fal-SECRETBIT" not in result.error
        assert "[REDACTED]" in result.error

    def test_keyframe_lock_lora_record_without_adapter_url_fails_cleanly(
        self, prime_vault, char_root
    ):
        prime_vault({"FAL_KEY": "f"})
        _make_character(char_root)
        # forge a bad record on disk (add_lora now validates, so write directly)
        record_path = char_root / "ana" / "character.json"
        record = json.loads(record_path.read_text())
        record["loras"] = [{"model_family": "flux"}]
        record_path.write_text(json.dumps(record))
        result = KeyframeLock().execute({"character_id": "ana", "prompt": "x", "mode": "lora"})
        assert result.success is False and "adapter_url" in result.error

    def test_keyframe_lock_warns_on_missing_references(
        self, prime_vault, char_root, monkeypatch
    ):
        prime_vault({"KIE_AI_API_KEY": "k"})
        registry = _make_character(char_root, n_refs=2)
        registry.reference_paths("ana")[0].unlink()
        from tools.base_tool import ToolResult
        from tools.graphics.nano_banana_pro import NanoBananaPro

        monkeypatch.setattr(
            NanoBananaPro, "execute",
            lambda self, inputs: ToolResult(success=True, data={}, artifacts=["kf.png"]),
        )
        result = KeyframeLock().execute({"character_id": "ana", "prompt": "x"})
        assert result.success
        assert "missing" in result.data["warning_missing_references"]

    def test_keyframe_lock_lora_rejects_unmappable_aspect_ratio(self, prime_vault, char_root):
        prime_vault({"FAL_KEY": "f"})
        registry = _make_character(char_root)
        registry.add_lora("ana", {"model_family": "flux", "adapter_url": "https://a"})
        result = KeyframeLock().execute(
            {"character_id": "ana", "prompt": "x", "mode": "lora", "aspect_ratio": "21:9"}
        )
        assert result.success is False and "references mode" in result.error
