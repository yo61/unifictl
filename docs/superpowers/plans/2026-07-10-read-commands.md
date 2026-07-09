# Read commands (`list devices`, `show port`) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add two read-only commands — `unifictl list devices` and `unifictl show port <n> --switch <mac>` — the second reporting the LAG leader when a port is aggregated.

**Architecture:** Mirror the existing `set lag` DDD layering. Two pure domain functions (`device_summary`, `describe_port`) do the logic; the application layer orchestrates fetch→map; new thin cyclopts sub-apps (`list`, `show`) render tables/JSON; the client gains a `get_devices()` read. Reads are simpler than writes — no backup, confirm, or dry-run.

**Tech Stack:** Python 3.11+, cyclopts 4.11.2, httpx, rich, pytest, hypothesis, pytest-httpx, ty, ruff.

## Global Constraints

- Absolute imports only (`from unifictl.x import y`); no relative imports.
- `ruff` clean: line-length 100, double quotes, `select = E,F,I,UP,B,SIM,RUF`.
- `ty check src` clean (strict).
- import-linter contracts hold: `domain` imports nothing from `application`/`infrastructure`; `infrastructure` imports neither `domain` nor `application`; layering `commands → application → domain`.
- `PortOverride = dict[str, Any]` (already defined in `src/unifictl/domain/models.py`) — an opaque bag; never enumerate its fields in logic, only pass through.
- Every task ends green (`uv run --no-sync task dev:check` passes) and with a conventional commit.
- Run all commands with `uv run --no-sync <cmd>`.

---

### Task 1: `describe_port` domain function + value objects

**Files:**
- Modify: `src/unifictl/domain/models.py` (add `PortRole`, `PortDescription`, `DeviceSummary`)
- Create: `src/unifictl/domain/ports.py`
- Test: `tests/test_ports.py`

**Interfaces:**
- Consumes: `PortOverride` from `unifictl.domain.models`.
- Produces:
  - `PortRole(str, Enum)` with members `LEADER = "leader"`, `MEMBER = "member"`, `STANDALONE = "standalone"`.
  - `PortDescription` frozen dataclass: `port_idx: int`, `role: PortRole`, `leader_port: int | None`, `members: tuple[int, ...]`, `override: PortOverride | None`.
  - `DeviceSummary` frozen dataclass: `name: str`, `model: str`, `type: str`, `mac: str`, `ip: str`.
  - `describe_port(port_overrides: list[PortOverride], port_idx: int) -> PortDescription`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_ports.py`:

```python
"""Tests for the pure port-description function."""

from __future__ import annotations

import copy

import pytest
from hypothesis import given
from hypothesis import strategies as st

from unifictl.domain.models import PortRole
from unifictl.domain.ports import describe_port

LEADER_17 = {"port_idx": 17, "op_mode": "aggregate", "aggregate_members": [17, 18], "name": "Port 17"}


def test_leader_is_reported_as_leader() -> None:
    result = describe_port([LEADER_17], 17)
    assert result.role is PortRole.LEADER
    assert result.leader_port == 17
    assert result.members == (17, 18)
    assert result.override == LEADER_17


def test_member_reports_its_leader() -> None:
    result = describe_port([LEADER_17], 18)
    assert result.role is PortRole.MEMBER
    assert result.leader_port == 17
    assert result.members == (17, 18)
    assert result.override is None


def test_member_with_own_override_keeps_it() -> None:
    member = {"port_idx": 18, "poe_mode": "off"}
    result = describe_port([LEADER_17, member], 18)
    assert result.role is PortRole.MEMBER
    assert result.leader_port == 17
    assert result.override == member


def test_standalone_port_with_override() -> None:
    plain = {"port_idx": 3, "name": "Port 3"}
    result = describe_port([plain], 3)
    assert result.role is PortRole.STANDALONE
    assert result.leader_port is None
    assert result.members == ()
    assert result.override == plain


def test_standalone_port_without_override() -> None:
    result = describe_port([LEADER_17], 3)
    assert result.role is PortRole.STANDALONE
    assert result.override is None


@st.composite
def _overrides_and_target(draw: st.DrawFn) -> tuple[list[dict[str, object]], int]:
    indices = draw(st.lists(st.integers(min_value=1, max_value=52), unique=True, min_size=1))
    overrides: list[dict[str, object]] = []
    for idx in indices:
        override: dict[str, object] = {"port_idx": idx}
        if draw(st.booleans()):
            override["op_mode"] = "aggregate"
            override["aggregate_members"] = [idx, idx + 1]
        overrides.append(override)
    target = draw(st.sampled_from([*indices, max(indices) + 5]))
    return overrides, target


@given(_overrides_and_target())
def test_role_is_exactly_one_kind(data: tuple[list[dict[str, object]], int]) -> None:
    overrides, target = data
    result = describe_port(overrides, target)
    assert result.role in (PortRole.LEADER, PortRole.MEMBER, PortRole.STANDALONE)
    if result.role is PortRole.LEADER:
        assert result.leader_port == target
        assert target in result.members
    elif result.role is PortRole.MEMBER:
        assert result.leader_port != target
        assert target in result.members
    else:
        assert result.leader_port is None
        assert result.members == ()


@given(_overrides_and_target())
def test_input_never_mutated(data: tuple[list[dict[str, object]], int]) -> None:
    overrides, target = data
    snapshot = copy.deepcopy(overrides)
    describe_port(overrides, target)
    assert overrides == snapshot
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --no-sync pytest tests/test_ports.py -q`
Expected: FAIL — `ImportError: cannot import name 'PortRole'` / `describe_port`.

- [ ] **Step 3: Add the value objects to `src/unifictl/domain/models.py`**

Append to the file (it already defines `PortOverride`):

```python
from dataclasses import dataclass
from enum import Enum


class PortRole(str, Enum):
    """Whether a port leads a LAG, is a member of one, or is standalone."""

    LEADER = "leader"
    MEMBER = "member"
    STANDALONE = "standalone"


@dataclass(frozen=True)
class PortDescription:
    """A port's aggregation role plus its own override (if any)."""

    port_idx: int
    role: PortRole
    leader_port: int | None
    members: tuple[int, ...]
    override: PortOverride | None


@dataclass(frozen=True)
class DeviceSummary:
    """The lean device fields shown by ``list devices``."""

    name: str
    model: str
    type: str
    mac: str
    ip: str
```

(Ensure `from dataclasses import dataclass` and `from enum import Enum` are at the top of the file with the other imports; keep `from __future__ import annotations` first.)

- [ ] **Step 4: Create `src/unifictl/domain/ports.py`**

```python
"""Pure description of a port's LAG role over a device's port_overrides array."""

from __future__ import annotations

from unifictl.domain.models import PortDescription, PortOverride, PortRole


def describe_port(port_overrides: list[PortOverride], port_idx: int) -> PortDescription:
    """Return the aggregation role of ``port_idx`` and its own override.

    A port is a **leader** if its own override has ``op_mode == "aggregate"``; a
    **member** if it appears in some aggregate leader's ``aggregate_members``;
    otherwise **standalone**. The input array is not mutated.
    """
    own = next((o for o in port_overrides if o.get("port_idx") == port_idx), None)

    if own is not None and own.get("op_mode") == "aggregate":
        members = tuple(own.get("aggregate_members", []))
        return PortDescription(port_idx, PortRole.LEADER, port_idx, members, own)

    for override in port_overrides:
        if override.get("op_mode") == "aggregate" and port_idx in override.get(
            "aggregate_members", []
        ):
            leader = override.get("port_idx")
            members = tuple(override.get("aggregate_members", []))
            return PortDescription(port_idx, PortRole.MEMBER, leader, members, own)

    return PortDescription(port_idx, PortRole.STANDALONE, None, (), own)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run --no-sync pytest tests/test_ports.py -q`
Expected: PASS (all cases + hypothesis).

- [ ] **Step 6: Verify the gate and commit**

Run: `uv run --no-sync ruff check src tests -q && uv run --no-sync ty check src && uv run --no-sync lint-imports`
Expected: clean, contracts kept.

```bash
git add src/unifictl/domain/models.py src/unifictl/domain/ports.py tests/test_ports.py
git commit -m "feat(domain): describe_port and read value objects"
```

---

### Task 2: `device_summary` domain function

**Files:**
- Create: `src/unifictl/domain/devices.py`
- Test: `tests/test_devices.py`

**Interfaces:**
- Consumes: `DeviceSummary` from `unifictl.domain.models`.
- Produces: `device_summary(raw_device: dict[str, Any]) -> DeviceSummary`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_devices.py`:

```python
"""Tests for device-summary extraction."""

from __future__ import annotations

from unifictl.domain.devices import device_summary


def test_extracts_the_lean_fields() -> None:
    raw = {
        "name": "USW 24 PoE",
        "model": "USL24P",
        "type": "usw",
        "mac": "70:a7:41:90:82:dd",
        "ip": "192.168.1.10",
        "extra": "ignored",
    }
    summary = device_summary(raw)
    assert summary.name == "USW 24 PoE"
    assert summary.model == "USL24P"
    assert summary.type == "usw"
    assert summary.mac == "70:a7:41:90:82:dd"
    assert summary.ip == "192.168.1.10"


def test_missing_fields_become_empty_strings() -> None:
    summary = device_summary({"mac": "aa:bb"})
    assert summary.mac == "aa:bb"
    assert summary.name == ""
    assert summary.ip == ""
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --no-sync pytest tests/test_devices.py -q`
Expected: FAIL — `ModuleNotFoundError: unifictl.domain.devices`.

- [ ] **Step 3: Create `src/unifictl/domain/devices.py`**

```python
"""Pure extraction of the lean summary fields from a raw device object."""

from __future__ import annotations

from typing import Any

from unifictl.domain.models import DeviceSummary


def device_summary(raw_device: dict[str, Any]) -> DeviceSummary:
    """Pull ``name``/``model``/``type``/``mac``/``ip`` from a raw device dict.

    Missing fields default to an empty string so the table always renders.
    """
    return DeviceSummary(
        name=str(raw_device.get("name", "")),
        model=str(raw_device.get("model", "")),
        type=str(raw_device.get("type", "")),
        mac=str(raw_device.get("mac", "")),
        ip=str(raw_device.get("ip", "")),
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run --no-sync pytest tests/test_devices.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/unifictl/domain/devices.py tests/test_devices.py
git commit -m "feat(domain): device_summary extraction"
```

---

### Task 3: `client.get_devices()`

**Files:**
- Modify: `src/unifictl/infrastructure/client.py`
- Test: `tests/test_client.py` (add one test)

**Interfaces:**
- Consumes: the existing `UnifiClient._send` helper and `self._settings.site`.
- Produces: `UnifiClient.get_devices(self) -> list[dict[str, Any]]`.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_client.py`:

```python
def test_get_devices_returns_all_and_sends_api_key(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        method="GET",
        url="https://gw/proxy/network/api/s/default/stat/device",
        json={"meta": {"rc": "ok"}, "data": [{"_id": "a", "mac": "aa"}, {"_id": "b", "mac": "bb"}]},
    )
    client = UnifiClient(_settings())
    devices = client.get_devices()
    assert [d["mac"] for d in devices] == ["aa", "bb"]
    assert httpx_mock.get_requests()[0].headers["X-API-KEY"] == "secret"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --no-sync pytest tests/test_client.py::test_get_devices_returns_all_and_sends_api_key -q`
Expected: FAIL — `AttributeError: 'UnifiClient' object has no attribute 'get_devices'`.

- [ ] **Step 3: Add `get_devices` to `UnifiClient`**

In `src/unifictl/infrastructure/client.py`, add this method to the `UnifiClient` class, right after `get_device`:

```python
    def get_devices(self) -> list[dict[str, Any]]:
        """Return the raw device objects for every adopted device."""
        path = f"/proxy/network/api/s/{self._settings.site}/stat/device"
        response = self._send("GET", path)
        devices: list[dict[str, Any]] = response.json().get("data", [])
        return devices
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --no-sync pytest tests/test_client.py -q`
Expected: PASS (all client tests).

- [ ] **Step 5: Commit**

```bash
git add src/unifictl/infrastructure/client.py tests/test_client.py
git commit -m "feat(infra): UnifiClient.get_devices"
```

---

### Task 4: `device_service` + `PortNotFoundError`, wired into `main()`

**Files:**
- Create: `src/unifictl/application/device_service.py`
- Modify: `src/unifictl/cli.py` (catch `PortNotFoundError`)
- Test: `tests/test_device_service.py`

**Interfaces:**
- Consumes: `UnifiClient`, `device_summary`, `describe_port`, `DeviceSummary`, `PortDescription`.
- Produces:
  - `PortNotFoundError(ValueError)`.
  - `list_devices(client: UnifiClient) -> list[DeviceSummary]`.
  - `describe_switch_port(client: UnifiClient, switch_mac: str, port_idx: int) -> PortDescription`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_device_service.py`:

```python
"""Tests for the device read use-cases."""

from __future__ import annotations

from typing import Any

import pytest

from unifictl.application.device_service import (
    PortNotFoundError,
    describe_switch_port,
    list_devices,
)
from unifictl.domain.models import PortRole


class FakeClient:
    def __init__(self, devices: list[dict[str, Any]] | None = None, device: dict[str, Any] | None = None) -> None:
        self._devices = devices or []
        self._device = device or {}

    def get_devices(self) -> list[dict[str, Any]]:
        return self._devices

    def get_device(self, mac: str) -> dict[str, Any]:
        return self._device


def test_list_devices_maps_to_summaries() -> None:
    client = FakeClient(devices=[{"name": "SW", "mac": "aa", "model": "M", "type": "usw", "ip": "1.2.3.4"}])
    summaries = list_devices(client)
    assert summaries[0].mac == "aa"
    assert summaries[0].name == "SW"


def test_describe_switch_port_reports_leader() -> None:
    device = {
        "port_table": [{"port_idx": 17}, {"port_idx": 18}],
        "port_overrides": [{"port_idx": 17, "op_mode": "aggregate", "aggregate_members": [17, 18]}],
    }
    result = describe_switch_port(FakeClient(device=device), "aa", 18)
    assert result.role is PortRole.MEMBER
    assert result.leader_port == 17


def test_unknown_port_raises() -> None:
    device = {"port_table": [{"port_idx": 1}, {"port_idx": 2}], "port_overrides": []}
    with pytest.raises(PortNotFoundError, match="99"):
        describe_switch_port(FakeClient(device=device), "aa", 99)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --no-sync pytest tests/test_device_service.py -q`
Expected: FAIL — `ModuleNotFoundError: unifictl.application.device_service`.

- [ ] **Step 3: Create `src/unifictl/application/device_service.py`**

```python
"""Read use-cases: list devices, describe a switch port."""

from __future__ import annotations

from unifictl.domain.devices import device_summary
from unifictl.domain.models import DeviceSummary, PortDescription
from unifictl.domain.ports import describe_port
from unifictl.infrastructure.client import UnifiClient


class PortNotFoundError(ValueError):
    """Raised when a port index does not exist on the target switch."""


def list_devices(client: UnifiClient) -> list[DeviceSummary]:
    """Return a lean summary of every adopted device."""
    return [device_summary(raw) for raw in client.get_devices()]


def describe_switch_port(
    client: UnifiClient, switch_mac: str, port_idx: int
) -> PortDescription:
    """Return the aggregation role of ``port_idx`` on ``switch_mac``.

    Raises:
        PortNotFoundError: if the switch has a port table that does not list
            ``port_idx``.
    """
    device = client.get_device(switch_mac)
    port_indices = {p.get("port_idx") for p in device.get("port_table", [])}
    if port_indices and port_idx not in port_indices:
        raise PortNotFoundError(f"port {port_idx} not found on {switch_mac}")
    return describe_port(device["port_overrides"], port_idx)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run --no-sync pytest tests/test_device_service.py -q`
Expected: PASS.

- [ ] **Step 5: Catch `PortNotFoundError` in `main()`**

In `src/unifictl/cli.py`, extend the exception net. Change the import + `except` in `main()`:

```python
    from unifictl.application.device_service import PortNotFoundError
    from unifictl.infrastructure.client import UnifiClientError
    from unifictl.infrastructure.config import ConfigError

    try:
        app()
    except (ConfigError, UnifiClientError, PortNotFoundError) as exc:
        print(f"unifictl: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
```

- [ ] **Step 6: Run the gate and commit**

Run: `uv run --no-sync task dev:check`
Expected: clean, contracts kept.

```bash
git add src/unifictl/application/device_service.py src/unifictl/cli.py tests/test_device_service.py
git commit -m "feat(app): device read use-cases and PortNotFoundError"
```

---

### Task 5: `list devices` command

**Files:**
- Create: `src/unifictl/commands/list_.py`
- Modify: `src/unifictl/cli.py` (register the `list` sub-app)
- Test: `tests/test_list_command.py`

**Interfaces:**
- Consumes: `list_devices`, `UnifiClient`, `load_settings`.
- Produces: cyclopts `App` named `list` with a `devices` command; module attribute `app`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_list_command.py`:

```python
"""Tests for the `list devices` command adapter."""

from __future__ import annotations

import json
from typing import Any

import pytest

from unifictl.commands import list_ as list_cmd
from unifictl.domain.models import DeviceSummary
from unifictl.infrastructure.config import Settings

RAW = [{"name": "SW", "model": "M", "type": "usw", "mac": "aa", "ip": "1.2.3.4"}]


def _settings(**kw: Any) -> Settings:
    return Settings(base_url="https://gw", api_key="k", **kw)


class _FakeClient:
    def __init__(self, settings: Settings) -> None:
        self.closed = False

    def get_devices(self) -> list[dict[str, Any]]:
        return RAW

    def close(self) -> None:
        self.closed = True


@pytest.fixture(autouse=True)
def _wire(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(list_cmd, "load_settings", _settings)
    monkeypatch.setattr(list_cmd, "UnifiClient", _FakeClient)
    monkeypatch.setattr(
        list_cmd, "list_devices", lambda client: [DeviceSummary("SW", "M", "usw", "aa", "1.2.3.4")]
    )


def test_table_lists_the_mac(capsys: pytest.CaptureFixture[str]) -> None:
    list_cmd.devices()
    out = capsys.readouterr().out
    assert "aa" in out
    assert "SW" in out


def test_json_dumps_raw_devices(capsys: pytest.CaptureFixture[str]) -> None:
    list_cmd.devices(as_json=True)
    out = capsys.readouterr().out
    assert json.loads(out) == RAW
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --no-sync pytest tests/test_list_command.py -q`
Expected: FAIL — `ImportError: cannot import name 'list_'`.

- [ ] **Step 3: Create `src/unifictl/commands/list_.py`**

```python
"""``unifictl list`` sub-app. Currently exposes ``list devices``."""

from __future__ import annotations

import json
from typing import Annotated

from cyclopts import App, Parameter
from rich.console import Console
from rich.table import Table

from unifictl.application.device_service import list_devices
from unifictl.domain.models import DeviceSummary
from unifictl.infrastructure.client import UnifiClient
from unifictl.infrastructure.config import load_settings

app = App(name="list", help="List UniFi resources.")
_console = Console()


@app.command(name="devices")
def devices(*, as_json: Annotated[bool, Parameter(name=["--json"], negative=())] = False) -> None:
    """List all adopted devices with their MAC addresses.

    Args:
        as_json: Emit the raw device objects as JSON instead of a table.
    """
    settings = load_settings()
    client = UnifiClient(settings)
    try:
        if as_json:
            print(json.dumps(client.get_devices()))
            return
        _render_devices(list_devices(client))
    finally:
        client.close()


def _render_devices(summaries: list[DeviceSummary]) -> None:
    table = Table(box=None, pad_edge=False)
    for column in ("NAME", "MODEL", "TYPE", "MAC", "IP"):
        table.add_column(column)
    for summary in summaries:
        table.add_row(summary.name, summary.model, summary.type, summary.mac, summary.ip)
    _console.print(table)
```

- [ ] **Step 4: Register the `list` sub-app in `src/unifictl/cli.py`**

Add the import and registration alongside the existing `set` sub-app:

```python
from unifictl.commands.list_ import app as list_app
...
app.command(set_app)
app.command(list_app)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run --no-sync pytest tests/test_list_command.py -q`
Expected: PASS.

- [ ] **Step 6: Manual smoke + gate + commit**

Run: `uv run --no-sync unifictl list --help` (expect the `devices` command listed).
Run: `uv run --no-sync task dev:check`
Expected: clean.

```bash
git add src/unifictl/commands/list_.py src/unifictl/cli.py tests/test_list_command.py
git commit -m "feat(cli): list devices command"
```

---

### Task 6: `show port` command

**Files:**
- Create: `src/unifictl/commands/show.py`
- Modify: `src/unifictl/cli.py` (register the `show` sub-app)
- Test: `tests/test_show_command.py`

**Interfaces:**
- Consumes: `describe_switch_port`, `UnifiClient`, `load_settings`, `ConfigError`, `PortDescription`, `PortRole`.
- Produces: cyclopts `App` named `show` with a `port` command; module attribute `app`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_show_command.py`:

```python
"""Tests for the `show port` command adapter."""

from __future__ import annotations

import json
from typing import Any

import pytest

from unifictl.commands import show as show_cmd
from unifictl.domain.models import PortDescription, PortRole
from unifictl.infrastructure.config import ConfigError, Settings


def _settings(**kw: Any) -> Settings:
    base: dict[str, Any] = {"base_url": "https://gw", "api_key": "k", "switch": "aa"}
    base.update(kw)
    return Settings(**base)


class _FakeClient:
    def __init__(self, settings: Settings) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


@pytest.fixture
def wire(monkeypatch: pytest.MonkeyPatch):
    def _apply(desc: PortDescription) -> None:
        monkeypatch.setattr(show_cmd, "load_settings", _settings)
        monkeypatch.setattr(show_cmd, "UnifiClient", _FakeClient)
        monkeypatch.setattr(show_cmd, "describe_switch_port", lambda c, s, p: desc)

    return _apply


def test_member_prints_leader(wire, capsys: pytest.CaptureFixture[str]) -> None:
    wire(PortDescription(18, PortRole.MEMBER, 17, (17, 18), None))
    show_cmd.port(18)
    out = capsys.readouterr().out
    assert "member" in out.lower()
    assert "17" in out


def test_standalone_prints_not_aggregated(wire, capsys: pytest.CaptureFixture[str]) -> None:
    wire(PortDescription(3, PortRole.STANDALONE, None, (), {"port_idx": 3, "name": "Port 3"}))
    show_cmd.port(3)
    out = capsys.readouterr().out
    assert "not aggregated" in out.lower()
    assert "Port 3" in out


def test_json_dumps_description(wire, capsys: pytest.CaptureFixture[str]) -> None:
    wire(PortDescription(17, PortRole.LEADER, 17, (17, 18), {"port_idx": 17}))
    show_cmd.port(17, as_json=True)
    payload = json.loads(capsys.readouterr().out)
    assert payload["role"] == "leader"
    assert payload["leader_port"] == 17
    assert payload["members"] == [17, 18]


def test_missing_switch_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(show_cmd, "load_settings", lambda: _settings(switch=None))
    monkeypatch.setattr(show_cmd, "UnifiClient", _FakeClient)
    with pytest.raises(ConfigError, match="switch"):
        show_cmd.port(17)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --no-sync pytest tests/test_show_command.py -q`
Expected: FAIL — `ImportError: cannot import name 'show'`.

- [ ] **Step 3: Create `src/unifictl/commands/show.py`**

```python
"""``unifictl show`` sub-app. Currently exposes ``show port``."""

from __future__ import annotations

import json
from typing import Annotated

from cyclopts import App, Parameter
from rich.console import Console

from unifictl.application.device_service import describe_switch_port
from unifictl.domain.models import PortDescription, PortRole
from unifictl.infrastructure.client import UnifiClient
from unifictl.infrastructure.config import ConfigError, load_settings

app = App(name="show", help="Show UniFi resource configuration.")
_console = Console()


@app.command(name="port")
def port(
    port_idx: int,
    /,
    *,
    switch: str | None = None,
    as_json: Annotated[bool, Parameter(name=["--json"], negative=())] = False,
) -> None:
    """Show a port's configuration, and its LAG leader if it is aggregated.

    Args:
        port_idx: The port index to inspect.
        switch: MAC of the switch; falls back to config/env when omitted.
        as_json: Emit the description as JSON instead of formatted text.
    """
    settings = load_settings()
    switch_mac = switch or settings.switch
    if not switch_mac:
        raise ConfigError("no switch specified; pass --switch or set 'switch' in config")
    client = UnifiClient(settings)
    try:
        description = describe_switch_port(client, switch_mac, port_idx)
    finally:
        client.close()

    if as_json:
        print(json.dumps(_as_dict(description)))
        return
    _render(description)


def _as_dict(description: PortDescription) -> dict[str, object]:
    return {
        "port_idx": description.port_idx,
        "role": description.role.value,
        "leader_port": description.leader_port,
        "members": list(description.members),
        "override": description.override,
    }


def _render(description: PortDescription) -> None:
    members = list(description.members)
    if description.role is PortRole.LEADER:
        headline = f"port {description.port_idx}: LAG leader — members {members}"
    elif description.role is PortRole.MEMBER:
        headline = (
            f"port {description.port_idx}: member of LAG — "
            f"leader {description.leader_port}, members {members}"
        )
    else:
        headline = f"port {description.port_idx}: not aggregated"
    _console.print(headline)

    if description.override:
        fields = ", ".join(
            f"{key}={value!r}"
            for key, value in description.override.items()
            if key != "port_idx"
        )
        _console.print(f"  overrides: {fields}")
    else:
        _console.print("  overrides: (none; controller defaults)")
```

- [ ] **Step 4: Register the `show` sub-app in `src/unifictl/cli.py`**

```python
from unifictl.commands.show import app as show_app
...
app.command(show_app)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run --no-sync pytest tests/test_show_command.py -q`
Expected: PASS.

- [ ] **Step 6: Manual smoke + gate + commit**

Run: `uv run --no-sync unifictl show port --help`
Run: `uv run --no-sync task dev:check`
Expected: clean.

```bash
git add src/unifictl/commands/show.py src/unifictl/cli.py tests/test_show_command.py
git commit -m "feat(cli): show port command"
```

---

### Task 7: End-to-end tests through the CLI

**Files:**
- Create: `tests/test_e2e_reads.py`

**Interfaces:**
- Consumes: `unifictl.cli.app`, `pytest_httpx.HTTPXMock`. Cyclopts raises `SystemExit(0)` on success.

- [ ] **Step 1: Write the tests**

Create `tests/test_e2e_reads.py`:

```python
"""End-to-end read tests: CLI down to mocked HTTP."""

from __future__ import annotations

import json

import pytest
from pytest_httpx import HTTPXMock

from unifictl.cli import app

DEVICES_URL = "https://gw/proxy/network/api/s/default/stat/device"
DEVICE_URL = "https://gw/proxy/network/api/s/default/stat/device/70:aa"


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("UNIFI_BASE_URL", "https://gw")
    monkeypatch.setenv("UNIFI_API_KEY", "secret")


def _run(*argv: str) -> None:
    with pytest.raises(SystemExit) as exc:
        app(list(argv))
    assert exc.value.code in (0, None)


def test_list_devices_json(httpx_mock: HTTPXMock, capsys: pytest.CaptureFixture[str]) -> None:
    httpx_mock.add_response(
        method="GET",
        url=DEVICES_URL,
        json={"meta": {"rc": "ok"}, "data": [{"name": "SW", "mac": "aa", "model": "M", "type": "usw", "ip": "1.2.3.4"}]},
    )
    _run("list", "devices", "--json")
    assert json.loads(capsys.readouterr().out)[0]["mac"] == "aa"


def test_show_port_member(httpx_mock: HTTPXMock, capsys: pytest.CaptureFixture[str]) -> None:
    httpx_mock.add_response(
        method="GET",
        url=DEVICE_URL,
        json={
            "meta": {"rc": "ok"},
            "data": [
                {
                    "_id": "dev1",
                    "port_table": [{"port_idx": 17}, {"port_idx": 18}],
                    "port_overrides": [{"port_idx": 17, "op_mode": "aggregate", "aggregate_members": [17, 18]}],
                }
            ],
        },
    )
    _run("show", "port", "18", "--switch", "70:aa")
    out = capsys.readouterr().out.lower()
    assert "member" in out
    assert "17" in out
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `uv run --no-sync pytest tests/test_e2e_reads.py -q`
Expected: PASS.

- [ ] **Step 3: Full gate + commit**

Run: `uv run --no-sync task dev:check`
Expected: clean, all contracts kept.

```bash
git add tests/test_e2e_reads.py
git commit -m "test: end-to-end coverage for list devices and show port"
```

---

## Notes for the implementer

- `commands/list_.py` uses a trailing underscore (jobhound convention) to avoid shadowing the `list` builtin; the cyclopts sub-app is still named `"list"`, so the user types `unifictl list devices`.
- `--json` on `list devices` emits the **raw** device objects (everything); the table shows only the lean five columns. `--json` on `show port` emits the structured `PortDescription` (role, leader, members, plus the raw `override`).
- Reads never write, so there is no backup/confirm/dry-run surface to test.
- After all tasks: update `README.md` usage and `SPEC.md` are **not** required by this plan — the design doc is the record; a docs pass can follow separately if desired.
