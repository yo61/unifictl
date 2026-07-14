"""The hidden `__complete` candidate emitter."""

from __future__ import annotations

import pytest

from unifictl.commands import _complete
from unifictl.infrastructure.config import Settings


@pytest.fixture()
def run(capsys: pytest.CaptureFixture[str]):
    def _call(*words: str, shell: str = "zsh") -> list[str]:
        _complete.run(shell, *words)
        out = capsys.readouterr().out
        return [line for line in out.splitlines() if line]

    return _call


def test_top_level_commands(run) -> None:
    assert set(run("unifictl", "")) == {
        "set",
        "list",
        "show",
        "completion",
        "profile",
        "credential",
    }


def test_profile_subcommands(run) -> None:
    assert set(run("unifictl", "profile", "")) == {
        "create",
        "edit",
        "set",
        "unset",
        "list",
        "describe",
        "activate",
        "delete",
    }


def test_credential_subcommands(run) -> None:
    assert set(run("unifictl", "credential", "")) == {"set", "list", "delete"}


def test_set_subcommands(run) -> None:
    assert set(run("unifictl", "set", "")) == {"lag"}


def test_completion_subcommands(run) -> None:
    assert set(run("unifictl", "completion", "")) == {"bash", "fish", "zsh", "install"}


def test_set_lag_state_values(run) -> None:
    assert run("unifictl", "set", "lag", "") == ["on", "off"]


def test_completion_install_shell_values(run) -> None:
    assert run("unifictl", "completion", "install", "--shell", "") == ["bash", "fish", "zsh"]


def test_completion_install_dest_emits_files_sentinel(run) -> None:
    assert run("unifictl", "completion", "install", "--dest", "") == [_complete.FILES_SENTINEL]


def test_empty_words_is_noop(run) -> None:
    assert run() == []


_DEVICES = [
    {
        "type": "usw",
        "mac": "70:a7:41:90:82:dd",
        "port_table": [
            {"port_idx": 1},
            {"port_idx": 2},
            {"port_idx": 17},
        ],
    },
    {"type": "ugw", "mac": "aa:bb:cc:dd:ee:ff", "port_table": [{"port_idx": 1}]},
]


@pytest.fixture()
def fake_devices(monkeypatch: pytest.MonkeyPatch):
    def _install(devices: list[dict]) -> None:
        monkeypatch.setattr(_complete, "_completion_devices", lambda: list(devices))

    return _install


def test_switch_mac_completion_lists_only_switches(run, fake_devices) -> None:
    fake_devices(_DEVICES)
    assert run("unifictl", "show", "port", "--switch", "") == ["70:a7:41:90:82:dd"]


def test_switch_mac_completion_on_set_lag(run, fake_devices) -> None:
    fake_devices(_DEVICES)
    assert run("unifictl", "set", "lag", "off", "--switch", "") == ["70:a7:41:90:82:dd"]


def test_port_index_completion_uses_typed_switch(run, fake_devices) -> None:
    fake_devices(_DEVICES)
    out = run("unifictl", "show", "port", "--switch", "70:a7:41:90:82:dd", "")
    assert out == ["1", "2", "17"]


def test_leader_flag_completes_port_indices(run, fake_devices) -> None:
    fake_devices(_DEVICES)
    out = run("unifictl", "set", "lag", "off", "--switch", "70:a7:41:90:82:dd", "--leader", "")
    assert out == ["1", "2", "17"]


def test_port_index_falls_back_to_config_switch(run, fake_devices, monkeypatch) -> None:
    fake_devices(_DEVICES)
    settings = Settings(base_url="https://c", api_key="k", switch="70:a7:41:90:82:dd")
    monkeypatch.setattr(_complete, "load_settings", lambda: settings)
    assert run("unifictl", "show", "port", "") == ["1", "2", "17"]


def test_port_index_no_switch_yields_nothing(run, fake_devices, monkeypatch) -> None:
    fake_devices(_DEVICES)
    from unifictl.infrastructure.config import ConfigError

    def _raise() -> Settings:
        raise ConfigError("no config")

    monkeypatch.setattr(_complete, "load_settings", _raise)
    assert run("unifictl", "show", "port", "") == []


def test_completion_devices_swallows_client_errors(monkeypatch) -> None:
    settings = Settings(base_url="https://c", api_key="k", timeout_ms=30000)
    monkeypatch.setattr(_complete, "load_settings", lambda: settings)

    class _BoomClient:
        def __init__(self, s: Settings) -> None:
            assert s.timeout_ms == _complete.COMPLETION_TIMEOUT_MS  # clamped
            self.closed = False

        def get_devices(self):
            raise RuntimeError("controller unreachable")

        def close(self) -> None:
            self.closed = True

    monkeypatch.setattr(_complete, "UnifiClient", _BoomClient)
    assert _complete._completion_devices() == []


def test_completion_devices_no_config_returns_empty(monkeypatch) -> None:
    from unifictl.infrastructure.config import ConfigError

    def _raise() -> Settings:
        raise ConfigError("no config")

    monkeypatch.setattr(_complete, "load_settings", _raise)
    assert _complete._completion_devices() == []


def test_set_lag_state_values_after_switch_flag(run) -> None:
    # State is positional 0 even when --switch was typed first.
    assert run("unifictl", "set", "lag", "--switch", "aa:bb", "") == ["on", "off"]


def test_positional_index_skips_flags_and_their_values() -> None:
    assert _complete._positional_index([]) == 0
    assert _complete._positional_index(["--switch", "aa:bb"]) == 0
    assert _complete._positional_index(["--json"]) == 0
    assert _complete._positional_index(["5"]) == 1
    assert _complete._positional_index(["--switch", "aa:bb", "5"]) == 1


def test_completion_devices_swallows_non_config_error(monkeypatch) -> None:
    # A malformed config.toml surfaces as TOMLDecodeError (a ValueError), not
    # ConfigError. It must still degrade to no candidates, never raise.
    def _raise() -> object:
        raise ValueError("malformed TOML")

    monkeypatch.setattr(_complete, "load_settings", _raise)
    assert _complete._completion_devices() == []


def test_port_completion_survives_malformed_config(run, monkeypatch) -> None:
    def _raise() -> object:
        raise ValueError("malformed TOML")

    monkeypatch.setattr(_complete, "load_settings", _raise)
    # Goes through _resolve_switch -> load_settings; must not raise.
    assert run("unifictl", "show", "port", "") == []


def test_set_lag_flag_names(run) -> None:
    assert run("unifictl", "set", "lag", "-") == [
        "--switch",
        "--leader",
        "--dry-run",
        "--yes",
    ]


def test_list_devices_flag_names(run) -> None:
    assert run("unifictl", "list", "devices", "-") == ["--json"]


def test_global_profile_flag_name(run) -> None:
    assert run("unifictl", "-") == ["--profile"]


def test_command_without_flags_yields_no_flag_names(run) -> None:
    # `set` is a group with no flags of its own.
    assert run("unifictl", "set", "-") == []


@pytest.fixture()
def fake_profiles(monkeypatch: pytest.MonkeyPatch):
    def _install(names: list[str]) -> None:
        monkeypatch.setattr(_complete, "_profile_names", lambda: list(names))

    return _install


@pytest.fixture()
def fake_credentials(monkeypatch: pytest.MonkeyPatch):
    def _install(names: list[str]) -> None:
        monkeypatch.setattr(_complete, "_credential_names", lambda: list(names))

    return _install


def test_profile_delete_completes_profile_names(run, fake_profiles) -> None:
    fake_profiles(["home", "work"])
    assert run("unifictl", "profile", "delete", "") == ["home", "work"]


def test_profile_describe_completes_profile_names(run, fake_profiles) -> None:
    fake_profiles(["home", "work"])
    assert run("unifictl", "profile", "describe", "") == ["home", "work"]


def test_credential_delete_completes_credential_names(run, fake_credentials) -> None:
    fake_credentials(["default", "lab"])
    assert run("unifictl", "credential", "delete", "") == ["default", "lab"]


def test_credential_set_completes_existing_credential_names(run, fake_credentials) -> None:
    fake_credentials(["default", "lab"])
    assert run("unifictl", "credential", "set", "") == ["default", "lab"]


def test_global_profile_flag_completes_names(run, fake_profiles) -> None:
    fake_profiles(["home", "work"])
    assert run("unifictl", "--profile", "") == ["home", "work"]


def test_profile_names_swallows_store_errors(monkeypatch) -> None:
    # The provider imports profile_store lazily; patch the real call site.
    import unifictl.infrastructure.profile_store as ps

    def _boom() -> list[str]:
        raise RuntimeError("store unreadable")

    monkeypatch.setattr(ps, "list_profile_names", _boom)
    assert _complete._profile_names() == []


def test_profile_set_completes_all_keys(run) -> None:
    from unifictl.infrastructure.profile_store import PROFILE_KEYS

    assert run("unifictl", "profile", "set", "home", "") == sorted(PROFILE_KEYS)


def test_profile_unset_completes_existing_keys(run, monkeypatch) -> None:
    monkeypatch.setattr(_complete, "_profile_existing_keys", lambda name: ["switch", "site"])
    assert run("unifictl", "profile", "unset", "home", "") == ["switch", "site"]


def test_nth_positional_skips_flags_and_values() -> None:
    assert _complete._nth_positional(["home"], 0) == "home"
    assert _complete._nth_positional(["--switch", "aa:bb", "home"], 0) == "home"
    assert _complete._nth_positional(["home", "switch"], 1) == "switch"
    assert _complete._nth_positional(["home"], 1) is None


def test_profile_existing_keys_swallows_errors(monkeypatch) -> None:
    import unifictl.infrastructure.profile_store as ps

    def _boom(name: str) -> object:
        raise RuntimeError("no such profile")

    monkeypatch.setattr(ps, "read_profile", _boom)
    assert _complete._profile_existing_keys("ghost") == []
