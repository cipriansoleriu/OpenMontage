"""Named-key vault for the Persona fork (FORK_PLAN addition B).

Lets you define several API keys per provider and pick one per call, without
changing OpenMontage's single-key tools: a tool calls
``get_vault().resolve(provider, key_alias)`` and, when no alias is given,
falls back to the provider's conventional env var — so existing setups keep
working unchanged.

Env convention (loaded from .env by the standard loaders):

    PERSONA_KEY_<provider>_<alias> = <secret>
    PERSONA_KEY_openrouter_main=sk-or-...
    PERSONA_KEY_openrouter_client=sk-or-...

``provider`` is the first segment after the prefix and must not contain
underscores; the alias is everything after it (underscores allowed) and is
matched case-insensitively.

Alias-less resolution order: key named 'main' -> the provider's conventional
env var -> the provider's sole named key. The conventional var outranks a
non-'main' named key on purpose: adding one client-specific named key must
never silently move every alias-less call (and its billing) off the key that
was already powering the system.

Optional metadata (labels, spend caps) and overrides: ``~/.persona/keys.json``
(git-ignored), a JSON list of objects with ``provider`` and ``alias`` plus any
of ``secret``, ``label``, ``cap_usd``. Entries without a ``secret`` only
annotate an existing env-defined key. A malformed file never breaks tool
discovery or status: the error is deferred and raised (as KeyError) by
``resolve()`` at the point of use, and shown by the discovery CLI.

Discovery (aliases only, never secrets):  python -m lib.keyvault

Secrets never appear in logs, error messages, repr, dataclasses.asdict, or
CLI output — they are stored outside KeyEntry, keyed by (provider, alias).
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

_PREFIX = "PERSONA_KEY_"

# Conventional single-key env vars per provider, tried in order when no
# PERSONA_KEY_* entry resolves. Mirrors the fallback chains the tools
# themselves use (e.g. seedance_video reads FAL_KEY or FAL_AI_API_KEY).
_DEFAULT_ENV: dict[str, tuple[str, ...]] = {
    "openrouter": ("OPENROUTER_API_KEY",),
    "kie": ("KIE_AI_API_KEY",),
    "fal": ("FAL_KEY", "FAL_AI_API_KEY"),
    "replicate": ("REPLICATE_API_TOKEN",),
    "eleven": ("ELEVENLABS_API_KEY",),
    "elevenlabs": ("ELEVENLABS_API_KEY",),
    "openai": ("OPENAI_API_KEY",),
}


@dataclass
class KeyEntry:
    """Key metadata only — the secret lives in the vault, keyed by
    (provider, alias), so no repr/asdict/logging of entries can leak it.
    cap_usd is forward-looking metadata read only by the discovery CLI."""

    alias: str
    provider: str
    label: Optional[str] = None
    cap_usd: Optional[float] = None


class KeyVault:
    """Parses PERSONA_KEY_* entries from an env mapping (injectable for tests).

    Construction never raises: config-file problems and duplicate definitions
    are recorded and surfaced by resolve() at the point of use, so tool
    get_status()/registry preflight can never be crashed by a bad dotfile.
    """

    def __init__(
        self,
        env: Optional[dict[str, str]] = None,
        keys_file: Optional[Path] = None,
    ) -> None:
        self._env: dict[str, str] = dict(os.environ) if env is None else dict(env)
        self._entries: list[KeyEntry] = []
        self._secrets: dict[tuple[str, str], str] = {}
        # (provider, alias) -> env var names that collided after lowercasing
        self._conflicts: dict[tuple[str, str], list[str]] = {}
        self.keys_file_error: Optional[str] = None

        sources: dict[tuple[str, str], list[str]] = {}
        for name in sorted(self._env):  # sorted -> deterministic parse order
            value = self._env[name]
            if not name.startswith(_PREFIX) or not value:
                continue
            rest = name[len(_PREFIX):]
            provider, _, alias = rest.partition("_")
            if not provider or not alias:
                continue
            key = (provider.lower(), alias.lower())
            sources.setdefault(key, []).append(name)
            if key not in self._secrets:
                self._entries.append(KeyEntry(alias=key[1], provider=key[0]))
                # strip: a stray CR/LF in a secret would make requests raise
                # InvalidHeader with the full key repr'd into the message
                self._secrets[key] = value.strip()
        self._conflicts = {k: v for k, v in sources.items() if len(v) > 1}
        self._entries.sort(key=lambda k: (k.provider, k.alias))

        try:
            self._load_keys_file(
                keys_file if keys_file is not None else Path.home() / ".persona" / "keys.json"
            )
        except Exception as exc:  # deferred, not silent: resolve() raises it
            self.keys_file_error = str(exc)

    def _load_keys_file(self, path: Path) -> None:
        if not path.is_file():
            return
        try:
            entries = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            raise ValueError(f"Malformed key overrides file {path}: {exc}") from exc
        if not isinstance(entries, list):
            raise ValueError(f"{path} must contain a JSON list of key entries")
        for raw in entries:
            if not isinstance(raw, dict):
                raise ValueError(f"{path}: entries must be JSON objects, got {type(raw).__name__}")
            provider = str(raw.get("provider", "")).lower()
            alias = str(raw.get("alias", "")).lower()
            if not provider or not alias:
                raise ValueError(f"{path}: every entry needs 'provider' and 'alias'")
            key = (provider, alias)
            existing = self._find(provider, alias)
            if raw.get("secret"):
                self._secrets[key] = str(raw["secret"]).strip()
                if existing:
                    existing.label = raw.get("label", existing.label)
                    existing.cap_usd = raw.get("cap_usd", existing.cap_usd)
                else:
                    self._entries.append(
                        KeyEntry(alias=alias, provider=provider,
                                 label=raw.get("label"), cap_usd=raw.get("cap_usd"))
                    )
            elif existing:
                existing.label = raw.get("label", existing.label)
                existing.cap_usd = raw.get("cap_usd", existing.cap_usd)

    def _find(self, provider: str, alias: str) -> Optional[KeyEntry]:
        for k in self._entries:
            if k.provider == provider and k.alias == alias:
                return k
        return None

    def _secret_for(self, provider: str, alias: str) -> str:
        conflict = self._conflicts.get((provider, alias))
        if conflict:
            raise KeyError(
                f"Conflicting env vars define the key {provider}:{alias}: "
                f"{', '.join(conflict)}. Remove the duplicates."
            )
        return self._secrets[(provider, alias)]

    def list(self) -> list[dict]:
        """Aliases and metadata only — safe to print (no secrets)."""
        return [
            {"provider": k.provider, "alias": k.alias, "label": k.label, "cap_usd": k.cap_usd}
            for k in self._entries
        ]

    def resolve(self, provider: str, alias: Optional[str] = None) -> str:
        """Return the secret for (provider, alias).

        No alias: 'main' -> conventional env var -> sole named key. Multiple
        named keys without a 'main' and no conventional env var is ambiguous
        and raises rather than picking one arbitrarily. Error messages carry
        aliases and env-var names only, never secrets. Raises KeyError.
        """
        if self.keys_file_error:
            raise KeyError(
                f"Key resolution blocked: {self.keys_file_error}. "
                f"Fix or remove the file, then retry."
            )
        provider = provider.lower()
        if alias:
            alias = alias.lower()
            if self._find(provider, alias) or (provider, alias) in self._conflicts:
                return self._secret_for(provider, alias)
            have = ", ".join(
                k.alias for k in self._entries if k.provider == provider
            ) or "none"
            raise KeyError(
                f"No key alias '{alias}' for provider '{provider}' "
                f"(configured aliases: {have}). "
                f"Add PERSONA_KEY_{provider}_{alias} to .env or run "
                f"`python -m lib.keyvault` to list keys."
            )

        named = [k for k in self._entries if k.provider == provider]
        if self._find(provider, "main") or (provider, "main") in self._conflicts:
            return self._secret_for(provider, "main")
        for env_name in _DEFAULT_ENV.get(provider, ()):
            if self._env.get(env_name):
                return self._env[env_name].strip()
        if len(named) == 1:
            return self._secret_for(provider, named[0].alias)
        if named:
            raise KeyError(
                f"Multiple keys for provider '{provider}' "
                f"({', '.join(k.alias for k in named)}) and none named 'main' — "
                f"pass key_alias or add PERSONA_KEY_{provider}_main."
            )
        conventional = " or ".join(_DEFAULT_ENV.get(provider, ())) or "(none known)"
        raise KeyError(
            f"No key for provider '{provider}'. Add PERSONA_KEY_{provider}_main "
            f"to .env, or set the conventional env var: {conventional}."
        )


_vault: Optional[KeyVault] = None


def get_vault() -> KeyVault:
    """Process-wide vault snapshot, built on first use. Never raises.

    Env edits after first use are not seen (matching the repo's .env-at-import
    semantics); construct KeyVault(env=...) directly in tests.
    """
    global _vault
    if _vault is None:
        _vault = KeyVault()
    return _vault


def _main() -> None:
    """Discovery CLI: `python -m lib.keyvault` — aliases only, no secrets."""
    # Load .env the same way production tools do. tools.base_tool's import-time
    # loader strips inline comments (`KEY=  # note` -> empty); python-dotenv's
    # load_env() does not, and would report placeholder comments as live keys.
    import tools.base_tool  # noqa: F401

    vault = KeyVault()
    if vault.keys_file_error:
        print(f"WARNING: {vault.keys_file_error}")
    entries = vault.list()
    if not entries:
        print("No PERSONA_KEY_* named keys configured.")
    else:
        print(f"{'PROVIDER':<12} {'ALIAS':<16} {'LABEL':<24} CAP_USD")
        for e in entries:
            print(
                f"{e['provider']:<12} {e['alias']:<16} "
                f"{(e['label'] or '-'):<24} {e['cap_usd'] if e['cap_usd'] is not None else '-'}"
            )
    detected = sorted(
        {
            f"{provider} -> {name}"
            for provider, names in _DEFAULT_ENV.items()
            for name in names
            if os.environ.get(name)
        }
    )
    if detected:
        print("\nConventional single-key env vars detected (fallbacks):")
        for line in detected:
            print(f"  {line}")


if __name__ == "__main__":
    _main()
