"""Contract tests for the Persona fork's M2 provider tools.

seedance_kie / seedance_openrouter / nano_banana_pro follow the provider-tool
contract (mirrors test_dashscope_tools.py) plus the fork's key_alias contract:
every new tool resolves keys via lib/keyvault.py and accepts key_alias.
All hermetic — no network, vault primed with injected envs.
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pytest

import lib.keyvault as kv
from lib.keyvault import KeyVault
from tools.base_tool import BaseTool, ToolRuntime, ToolStatus, ToolTier
from tools.graphics.nano_banana_pro import NanoBananaPro
from tools.tool_registry import ToolRegistry
from tools.video.seedance_kie import SeedanceKie
from tools.video.seedance_openrouter import SeedanceOpenRouter

NO_KEYS_FILE = Path("/nonexistent/keys.json")

TOOLS = [
    (SeedanceKie, "seedance_kie", "video_generation", "seedance", "KIE_AI_API_KEY"),
    (SeedanceOpenRouter, "seedance_openrouter", "video_generation", "seedance", "OPENROUTER_API_KEY"),
    (NanoBananaPro, "nano_banana_pro", "image_generation", "nano_banana", "KIE_AI_API_KEY"),
]

REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def prime_vault(monkeypatch):
    def _prime(env: dict[str, str]) -> None:
        monkeypatch.setattr(kv, "_vault", KeyVault(env=env, keys_file=NO_KEYS_FILE))

    return _prime


@pytest.mark.parametrize("cls,name,capability,provider,env_var", TOOLS)
def test_identity_contract(cls, name, capability, provider, env_var):
    tool = cls()
    assert isinstance(tool, BaseTool)
    assert tool.name == name
    assert tool.version
    assert tool.tier in ToolTier
    assert tool.capability == capability
    assert tool.provider == provider
    assert tool.runtime == ToolRuntime.API
    assert len(tool.capabilities) >= 1
    assert tool.install_instructions and env_var in tool.install_instructions
    assert tool.fallback_tools
    assert tool.side_effects and any("API" in s for s in tool.side_effects)
    assert tool.user_visible_verification
    assert tool.resource_profile.network_required is True
    assert tool.retry_policy.max_retries >= 0


@pytest.mark.parametrize("cls,name,capability,provider,env_var", TOOLS)
def test_get_info_and_dry_run(cls, name, capability, provider, env_var):
    tool = cls()
    info = tool.get_info()
    assert info["name"] == name
    assert info["status"] in ("available", "unavailable", "degraded")
    schema = tool.input_schema
    assert schema.get("type") == "object"
    assert "prompt" in schema.get("required", [])
    result = tool.dry_run({})
    assert result["tool"] == name


@pytest.mark.parametrize("cls,name,capability,provider,env_var", TOOLS)
def test_key_alias_contract(cls, name, capability, provider, env_var):
    """Fork rule: every new provider tool accepts key_alias, excludes it from
    idempotency, and documents the PERSONA_KEY_ convention."""
    tool = cls()
    props = tool.input_schema["properties"]
    assert "key_alias" in props
    assert "PERSONA_KEY_" in props["key_alias"]["description"]
    assert "key_alias" not in tool.idempotency_key_fields
    assert tool.idempotency_key_fields  # non-empty


@pytest.mark.parametrize("cls,name,capability,provider,env_var", TOOLS)
def test_status_flips_on_env_key(cls, name, capability, provider, env_var, prime_vault):
    prime_vault({})
    assert cls().get_status() == ToolStatus.UNAVAILABLE
    prime_vault({env_var: "fake-key"})
    assert cls().get_status() == ToolStatus.AVAILABLE


@pytest.mark.parametrize("cls,name,capability,provider,env_var", TOOLS)
def test_status_available_via_named_key_only(cls, name, capability, provider, env_var, prime_vault):
    vault_provider = "kie" if env_var == "KIE_AI_API_KEY" else "openrouter"
    prime_vault({f"PERSONA_KEY_{vault_provider}_main": "named-secret"})
    assert cls().get_status() == ToolStatus.AVAILABLE


@pytest.mark.parametrize("cls,name,capability,provider,env_var", TOOLS)
def test_execute_without_key_fails_cleanly(cls, name, capability, provider, env_var, prime_vault):
    prime_vault({})
    result = cls().execute({"prompt": "a cat"})
    assert result.success is False
    assert env_var in result.error


@pytest.mark.parametrize("cls,name,capability,provider,env_var", TOOLS)
def test_execute_with_unknown_alias_names_alias_not_secret(
    cls, name, capability, provider, env_var, prime_vault
):
    vault_provider = "kie" if env_var == "KIE_AI_API_KEY" else "openrouter"
    prime_vault({f"PERSONA_KEY_{vault_provider}_main": "supersecret-value"})
    result = cls().execute({"prompt": "a cat", "key_alias": "nope"})
    assert result.success is False
    assert "nope" in result.error
    assert "supersecret-value" not in result.error


@pytest.mark.parametrize("cls,name,capability,provider,env_var", TOOLS)
def test_estimate_cost_positive_and_scales(cls, name, capability, provider, env_var):
    tool = cls()
    base = tool.estimate_cost({"prompt": "x"})
    assert isinstance(base, float) and base >= 0
    if tool.capability == "video_generation":
        assert tool.estimate_cost({"duration": 10}) > tool.estimate_cost({"duration": 4})
    else:
        assert tool.estimate_cost({"resolution": "4K"}) > tool.estimate_cost({"resolution": "1K"})


@pytest.mark.parametrize("cls,name,capability,provider,env_var", TOOLS)
def test_idempotency_key_varies_with_output_affecting_inputs(cls, name, capability, provider, env_var):
    tool = cls()
    a = tool.idempotency_key({"prompt": "a cat"})
    b = tool.idempotency_key({"prompt": "a dog"})
    assert a != b
    # key_alias must NOT change the cache key
    c = tool.idempotency_key({"prompt": "a cat", "key_alias": "client"})
    assert a == c


@pytest.mark.parametrize("cls,name,capability,provider,env_var", TOOLS)
def test_agent_skills_exist(cls, name, capability, provider, env_var):
    for skill in cls.agent_skills:
        skill_file = REPO_ROOT / ".agents" / "skills" / skill / "SKILL.md"
        assert skill_file.is_file(), f"{name} references missing agent skill: {skill}"


@pytest.mark.parametrize("module_name", [
    "tools.video.seedance_kie",
    "tools.video.seedance_openrouter",
    "tools.graphics.nano_banana_pro",
    "tools._kie.client",
])
def test_requests_imported_lazily(module_name):
    """Heavy deps must not load at import time — registry discovery imports
    every module under tools/."""
    import importlib

    module = importlib.import_module(module_name)
    tree = ast.parse(inspect.getsource(module))
    top_level_imports = {
        alias.name
        for node in tree.body
        if isinstance(node, (ast.Import,))
        for alias in node.names
    } | {
        node.module
        for node in tree.body
        if isinstance(node, ast.ImportFrom) and node.module
    }
    assert "requests" not in top_level_imports


def test_registry_auto_discovers_all_three():
    registry = ToolRegistry()
    discovered = registry.discover("tools")
    for _, name, _, _, _ in TOOLS:
        assert name in discovered, f"{name} not auto-discovered"


def test_seedance_kie_validates_reference_ceilings(prime_vault):
    prime_vault({"KIE_AI_API_KEY": "fake"})
    tool = SeedanceKie()
    result = tool.execute(
        {
            "prompt": "x",
            "operation": "reference_to_video",
            "reference_image_urls": [f"https://example.com/{i}.png" for i in range(10)],
        }
    )
    assert result.success is False and "9" in result.error


def test_nano_banana_pro_validates_reference_ceiling(prime_vault):
    prime_vault({"KIE_AI_API_KEY": "fake"})
    result = NanoBananaPro().execute(
        {"prompt": "x", "image_input": [f"https://example.com/{i}.png" for i in range(9)]}
    )
    assert result.success is False and "8" in result.error


def test_seedance_kie_image_to_video_requires_url(prime_vault):
    prime_vault({"KIE_AI_API_KEY": "fake"})
    result = SeedanceKie().execute({"prompt": "x", "operation": "image_to_video"})
    assert result.success is False and "image_url" in result.error


# ---- Review-driven regressions: never-raise, redaction, resilience ----

BAD_DURATIONS = ["5s", "abc", [5], {"n": 5}]


@pytest.mark.parametrize("cls", [SeedanceKie, SeedanceOpenRouter])
@pytest.mark.parametrize("duration", BAD_DURATIONS)
def test_bad_duration_returns_toolresult_not_raise(cls, duration, prime_vault):
    prime_vault({"KIE_AI_API_KEY": "fake", "OPENROUTER_API_KEY": "fake"})
    result = cls().execute({"prompt": "x", "duration": duration})
    assert result.success is False
    assert "duration" in result.error


@pytest.mark.parametrize("cls", [SeedanceKie, SeedanceOpenRouter])
@pytest.mark.parametrize("duration", ["auto", None, "7", 7])
def test_lenient_durations_accepted_and_estimates_never_raise(cls, duration, prime_vault):
    # 'auto' is valid for the fal sibling and selectors forward inputs verbatim.
    prime_vault({})
    tool = cls()
    assert isinstance(tool.estimate_cost({"prompt": "x", "duration": duration}), float)
    # No key primed: execute must fail at key resolution, not on the duration.
    result = tool.execute({"prompt": "x", "duration": duration})
    assert result.success is False
    assert "duration" not in (result.error or "")


def test_non_iterable_references_return_toolresult_not_raise(prime_vault):
    prime_vault({"KIE_AI_API_KEY": "fake"})
    result = SeedanceKie().execute(
        {"prompt": "x", "operation": "reference_to_video", "reference_image_urls": 42}
    )
    assert result.success is False
    assert "reference_image_urls" in result.error


def test_nano_banana_single_string_reference_is_wrapped_not_iterated(prime_vault, monkeypatch):
    prime_vault({"KIE_AI_API_KEY": "fake"})
    seen: dict[str, object] = {}

    def fake_run_job(model, payload, api_key, **kwargs):
        seen["payload"] = payload
        raise RuntimeError("stop-before-network")

    import tools._kie.client as kie_client

    monkeypatch.setattr(kie_client, "run_job", fake_run_job)
    result = NanoBananaPro().execute(
        {"prompt": "x", "image_input": "https://example.com/face.png"}
    )
    assert result.success is False and "stop-before-network" in result.error
    assert seen["payload"]["image_input"] == ["https://example.com/face.png"]


def test_nano_banana_image_urls_alias_merges_into_image_input(prime_vault, monkeypatch):
    prime_vault({"KIE_AI_API_KEY": "fake"})
    seen: dict[str, object] = {}

    def fake_run_job(model, payload, api_key, **kwargs):
        seen["payload"] = payload
        raise RuntimeError("stop-before-network")

    import tools._kie.client as kie_client

    monkeypatch.setattr(kie_client, "run_job", fake_run_job)
    NanoBananaPro().execute(
        {
            "prompt": "x",
            "image_input": ["https://example.com/a.png"],
            "image_urls": ["https://example.com/b.png", "https://example.com/a.png"],
        }
    )
    assert seen["payload"]["image_input"] == [
        "https://example.com/a.png",
        "https://example.com/b.png",
    ]


@pytest.mark.parametrize("cls,vault_env", [
    (SeedanceKie, {"KIE_AI_API_KEY": "sk-fake-SECRETPART"}),
    (NanoBananaPro, {"KIE_AI_API_KEY": "sk-fake-SECRETPART"}),
])
def test_network_errors_are_redacted_toolresults(cls, vault_env, prime_vault, monkeypatch):
    prime_vault(vault_env)

    def fake_run_job(model, payload, api_key, **kwargs):
        raise RuntimeError(f"InvalidHeader: 'Bearer {api_key}\\n'")

    import tools._kie.client as kie_client

    monkeypatch.setattr(kie_client, "run_job", fake_run_job)
    result = cls().execute({"prompt": "x"})
    assert result.success is False
    assert "sk-fake-SECRETPART" not in result.error
    assert "[REDACTED]" in result.error


def test_kie_client_tolerates_transient_poll_failures(monkeypatch):
    """createTask ok -> two poll blips -> success. Must return, not raise."""
    import sys
    import types

    calls = {"n": 0}

    class _Resp:
        def __init__(self, payload):
            self._payload = payload

        def raise_for_status(self):
            pass

        def json(self):
            return self._payload

    class _Boom:
        def raise_for_status(self):
            raise fake_requests.RequestException("502 blip")

        def json(self):  # pragma: no cover
            return {}

    fake_requests = types.ModuleType("requests")
    fake_requests.RequestException = type("RequestException", (Exception,), {})

    def fake_post(url, **kwargs):
        return _Resp({"code": 200, "data": {"taskId": "task_test"}})

    def fake_get(url, **kwargs):
        calls["n"] += 1
        if calls["n"] <= 2:
            return _Boom()
        return _Resp(
            {"data": {"state": "success", "resultJson": '{"resultUrls": ["u"]}',
                      "creditsConsumed": 1}}
        )

    fake_requests.post = fake_post
    fake_requests.get = fake_get
    monkeypatch.setitem(sys.modules, "requests", fake_requests)
    monkeypatch.setattr("time.sleep", lambda s: None)

    from tools._kie.client import run_job

    job = run_job("m", {"prompt": "x"}, "k")
    assert job["task_id"] == "task_test"
    assert job["result"]["resultUrls"] == ["u"]


def test_kie_client_gives_up_with_task_id_after_repeated_poll_failures(monkeypatch):
    import sys
    import types

    fake_requests = types.ModuleType("requests")
    fake_requests.RequestException = type("RequestException", (Exception,), {})

    class _Resp:
        def raise_for_status(self):
            pass

        def json(self):
            return {"code": 200, "data": {"taskId": "task_gone"}}

    class _Boom:
        def raise_for_status(self):
            raise fake_requests.RequestException("502 blip")

        def json(self):  # pragma: no cover
            return {}

    fake_requests.post = lambda url, **kw: _Resp()
    fake_requests.get = lambda url, **kw: _Boom()
    monkeypatch.setitem(sys.modules, "requests", fake_requests)
    monkeypatch.setattr("time.sleep", lambda s: None)

    from tools._kie.client import KieJobError, run_job

    with pytest.raises(KieJobError, match="task_gone"):
        run_job("m", {"prompt": "x"}, "k")


def test_openrouter_image_to_video_sends_frame_type(prime_vault):
    prime_vault({"OPENROUTER_API_KEY": "fake"})
    tool = SeedanceOpenRouter()
    body = tool._build_body(
        {
            "prompt": "x",
            "operation": "image_to_video",
            "image_url": "https://example.com/first.png",
            "end_image_url": "https://example.com/last.png",
        }
    )
    assert body["frame_images"][0]["frame_type"] == "first_frame"
    assert body["frame_images"][1]["frame_type"] == "last_frame"


# ---- Kie upload bridge regressions (M3): local files, no FAL_KEY needed ----

def test_upload_file_error_branches(monkeypatch, tmp_path):
    import sys
    import types

    from tools._kie.client import KieJobError, upload_file

    with pytest.raises(KieJobError, match="not found"):
        upload_file("/nope/x.png", "k")

    src = tmp_path / "x.png"
    src.write_bytes(b"png")
    fake_requests = types.ModuleType("requests")

    class _Resp:
        def raise_for_status(self):
            pass

        def json(self):
            return {"success": False, "code": 455, "msg": "quota"}

    fake_requests.post = lambda url, **kw: _Resp()
    monkeypatch.setitem(sys.modules, "requests", fake_requests)
    with pytest.raises(KieJobError, match="455"):
        upload_file(str(src), "k")


def test_seedance_kie_image_path_uploads_with_named_key(prime_vault, monkeypatch, tmp_path):
    import lib.keyvault as kv2
    from lib.keyvault import KeyVault as KV

    monkeypatch.setattr(
        kv2, "_vault",
        KV(env={"PERSONA_KEY_kie_client": "named-secret"}, keys_file=NO_KEYS_FILE),
    )
    frame = tmp_path / "frame.png"
    frame.write_bytes(b"png")
    seen: dict[str, object] = {}

    import tools._kie.client as kie_client

    def fake_upload(path, api_key, **kwargs):
        seen["api_key"] = api_key
        return "https://tempfile.example/frame.png"

    def fake_run_job(model, payload, api_key, **kwargs):
        seen["payload"] = payload
        raise RuntimeError("stop-before-network")

    monkeypatch.setattr(kie_client, "upload_file", fake_upload)
    monkeypatch.setattr(kie_client, "run_job", fake_run_job)
    result = SeedanceKie().execute(
        {
            "prompt": "x",
            "operation": "image_to_video",
            "image_path": str(frame),
            "key_alias": "client",
        }
    )
    assert seen["api_key"] == "named-secret"
    assert seen["payload"]["first_frame_url"] == "https://tempfile.example/frame.png"
    assert result.success is False and "stop-before-network" in result.error


def test_nano_banana_image_paths_upload_and_merge(prime_vault, monkeypatch, tmp_path):
    prime_vault({"KIE_AI_API_KEY": "k"})
    local = tmp_path / "ref.png"
    local.write_bytes(b"png")
    seen: dict[str, object] = {}

    import tools._kie.client as kie_client

    monkeypatch.setattr(
        kie_client, "upload_file", lambda path, api_key, **kw: "https://up/ref.png"
    )

    def fake_run_job(model, payload, api_key, **kwargs):
        seen["payload"] = payload
        raise RuntimeError("stop-before-network")

    monkeypatch.setattr(kie_client, "run_job", fake_run_job)
    NanoBananaPro().execute(
        {
            "prompt": "x",
            "image_input": ["https://existing/a.png"],
            "image_paths": [str(local)],
        }
    )
    assert seen["payload"]["image_input"] == ["https://existing/a.png", "https://up/ref.png"]


def test_nano_banana_caps_references_before_uploading(prime_vault, monkeypatch, tmp_path):
    prime_vault({"KIE_AI_API_KEY": "k"})
    local = tmp_path / "ref.png"
    local.write_bytes(b"png")

    import tools._kie.client as kie_client

    def must_not_upload(path, api_key, **kwargs):
        raise AssertionError("upload_file must not be called for an over-limit request")

    monkeypatch.setattr(kie_client, "upload_file", must_not_upload)
    result = NanoBananaPro().execute(
        {
            "prompt": "x",
            "image_input": [f"https://e/{i}.png" for i in range(8)],
            "image_paths": [str(local)],
        }
    )
    assert result.success is False and "8" in result.error
