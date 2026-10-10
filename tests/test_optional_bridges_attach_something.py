"""A bridge is recorded as attached only if something was actually attached (#9).

`attach_auth()` and `attach_events()` both reported success and attached
`None`, for the life of the package. Each imported a name from a module that
does not export it -- `nodus_auth.tokens.KeyRing` (that module has never
existed; the class is in `nodus_auth.jwt`) and `nodus_events.bus.get_event_bus`
(the name is on the package) -- inside one
`except (ImportError, AttributeError): pass`, which also happens to be how an
absent optional dependency is handled. So a wrong import was indistinguishable
from a package nobody installed.

Nothing in the suite called either method, which is why it shipped. `0.1.3`
fixed three bridges of exactly this kind (#5, #6, #7) and the lesson recorded
then was to drive the guest side; these two bridges have no guest side -- they
are Python-side holders -- so the equivalent is to **use the thing**: sign a
token with the ring, publish an event on the bus. `is not None` is what the
old tests would have asserted, and `None` is what they would have caught, but
a ring built from the wrong key or a bus that cannot publish would both pass it.

`test_optional_imports_resolve` is the one that would have caught both at once.
"""
from __future__ import annotations

import ast
import importlib
import pathlib

import pytest

import nodus_sdk.runtime
from nodus_sdk import NodusSDKRuntime, create_runtime
from nodus_sdk.runtime import _available, _require

CONFIGURED_SECRET = "a-configured-signing-secret-at-least-32-bytes"


# --------------------------------------------------------------------------- #
# the check that would have caught both defects
# --------------------------------------------------------------------------- #

def _required_imports() -> list[tuple[str, tuple[str, ...]]]:
    """Every `_require("module", "name", ...)` call in runtime.py, from its AST.

    Read out of the source rather than restated in a table here. The first
    version of this test *was* a table, and the neuter that put the original
    wrong import back left it green -- because a table compares the table to
    reality, not the code to reality. One question, two voices, which is the
    shape this whole file is about.

    Reading the AST also means a `_require` call added later is checked without
    anybody remembering to extend a list.
    """
    source = pathlib.Path(nodus_sdk.runtime.__file__).read_text(encoding="utf-8")
    found: list[tuple[str, tuple[str, ...]]] = []
    for node in ast.walk(ast.parse(source)):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "_require"
            and node.args
            and all(isinstance(a, ast.Constant) and isinstance(a.value, str)
                    for a in node.args)
        ):
            module, *names = [a.value for a in node.args]
            found.append((module, tuple(names)))
    return found


def test_the_ast_scan_finds_the_require_calls():
    """Control for the test below.

    If `_required_imports()` returned nothing -- a renamed helper, a changed
    AST shape -- the parametrised test would collect zero cases and the file
    would look entirely green while checking nothing. An empty scan is
    indistinguishable from a clean one, which has bitten this ecosystem before.
    """
    found = _required_imports()
    assert len(found) >= 4, f"the AST scan found only {found}; it has stopped working"
    assert any("nodus_auth" in m for m, _ in found)
    assert any("nodus_events" in m for m, _ in found)


# closes: #9
@pytest.mark.parametrize("module,names", _required_imports(),
                         ids=[m for m, _ in _required_imports()])
def test_optional_imports_resolve(module, names):
    """Every name runtime.py imports from an optional package is really there.

    Against the unfixed tree this fails twice: `nodus_events.bus` has no
    `get_event_bus`, and `nodus_auth.tokens` is not a module at all. Skips
    rather than passes when the optional package is absent -- a skip says "not
    checked", where a pass would say "checked and fine", and the whole defect
    was a missing name mistaken for a missing package.
    """
    package = module.split(".")[0]
    if not _available(package):
        pytest.skip(f"{package} is not installed; nothing to check")
    mod = importlib.import_module(module)
    for name in names:
        assert hasattr(mod, name), (
            f"runtime.py does `_require({module!r}, {name!r})`, and {module} "
            f"does not export {name}"
        )


def test_require_tells_a_mismatch_from_a_missing_package():
    """`_require` must be loud. Swallowing is what hid #9 for a whole package."""
    with pytest.raises(ImportError, match="version mismatch"):
        _require("nodus_sdk.does_not_exist", "anything")
    with pytest.raises(AttributeError, match="version mismatch"):
        _require("nodus_sdk", "a_name_nobody_exports")


# --------------------------------------------------------------------------- #
# auth
# --------------------------------------------------------------------------- #

requires_auth = pytest.mark.skipif(
    not _available("nodus_auth"), reason="nodus-auth is not installed")


@requires_auth
def test_attach_auth_builds_a_ring_that_actually_signs(monkeypatch):
    """The functional assertion. `auth_key_ring is not None` would also pass on
    a ring built from the wrong secret, which is the next bug of this shape."""
    from nodus_auth import create_access_token, decode_access_token

    monkeypatch.setenv("SECRET_KEY", CONFIGURED_SECRET)
    rt = NodusSDKRuntime().attach_auth()

    ring = rt.auth_key_ring
    assert ring is not None, "attach_auth() attached nothing"
    assert ring.active_key == CONFIGURED_SECRET, (
        "the ring was built on some other secret than the configured one"
    )
    token = create_access_token({"sub": "alice"}, key_ring=ring)
    assert decode_access_token(token, key_ring=ring)["sub"] == "alice"


@requires_auth
def test_attach_auth_refuses_the_published_dev_secret(monkeypatch):
    """A ring on nodus-auth's default SECRET_KEY is forgeable by anyone who has
    read the package, so it is refused rather than attached."""
    from nodus_auth import AuthSettings

    monkeypatch.delenv("SECRET_KEY", raising=False)
    monkeypatch.setenv("SECRET_KEY", AuthSettings.model_fields["SECRET_KEY"].default)

    rt = NodusSDKRuntime()
    with pytest.raises(RuntimeError, match="published constant"):
        rt.attach_auth()
    assert "auth" not in rt.attached_bridges(), (
        "a refusal must not leave the bridge recorded as attached"
    )
    assert rt.auth_key_ring is None


@requires_auth
def test_attach_auth_refuses_an_unset_secret(monkeypatch):
    monkeypatch.delenv("SECRET_KEY", raising=False)
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        NodusSDKRuntime().attach_auth()


@requires_auth
def test_a_caller_supplied_ring_is_used_verbatim(monkeypatch):
    """An explicit ring needs no SECRET_KEY: the caller has already decided."""
    from nodus_auth import KeyRing

    monkeypatch.delenv("SECRET_KEY", raising=False)
    ring = KeyRing(active="a-ring-the-caller-made-at-least-32-bytes")
    rt = NodusSDKRuntime().attach_auth(ring)
    assert rt.auth_key_ring is ring
    assert "auth" in rt.attached_bridges()


@requires_auth
def test_attach_auth_is_idempotent(monkeypatch):
    from nodus_auth import KeyRing

    monkeypatch.setenv("SECRET_KEY", CONFIGURED_SECRET)
    rt = NodusSDKRuntime().attach_auth()
    first = rt.auth_key_ring
    rt.attach_auth(KeyRing(active="a-different-ring-at-least-32-bytes-ok"))
    assert rt.auth_key_ring is first, "a second call must be a no-op"


@requires_auth
def test_create_runtime_auth_true_builds_a_working_ring(monkeypatch):
    from nodus_auth import create_access_token, decode_access_token

    monkeypatch.setenv("SECRET_KEY", CONFIGURED_SECRET)
    rt = create_runtime(auth=True)
    token = create_access_token({"sub": "bob"}, key_ring=rt.auth_key_ring)
    assert decode_access_token(token, key_ring=rt.auth_key_ring)["sub"] == "bob"


# --------------------------------------------------------------------------- #
# events
# --------------------------------------------------------------------------- #

requires_events = pytest.mark.skipif(
    not _available("nodus_events"), reason="nodus-events is not installed")


@pytest.fixture
def fresh_event_bus():
    """`get_event_bus()` is a process-wide singleton, so a test that touches it
    leaks into every later test in the run. CI runs these per-file under
    `unittest discover` as well as under pytest, where that pollution shows up
    as a different test failing."""
    if not _available("nodus_events"):
        yield
        return
    from nodus_events import reset_event_bus
    reset_event_bus()
    try:
        yield
    finally:
        reset_event_bus()


@requires_events
def test_attach_events_builds_a_bus_that_actually_publishes(fresh_event_bus):
    rt = NodusSDKRuntime().attach_events()
    bus = rt.event_bus
    assert bus is not None, "attach_events() attached nothing"
    # Use it: a bus that cannot publish would satisfy `is not None`.
    bus.publish("nodus_sdk.test", payload={"k": "v"})
    assert bus.get_status() is not None


@requires_events
def test_attach_events_takes_the_process_bus(fresh_event_bus):
    from nodus_events import get_event_bus

    rt = NodusSDKRuntime().attach_events()
    assert rt.event_bus is get_event_bus()


@requires_events
def test_an_event_bus_config_is_built_into_a_bus(fresh_event_bus):
    """README has documented `events=EventBusConfig(...)` since 0.1.0.

    It stored the config object as the bus, so `rt.event_bus` had no `publish`
    -- a documented call that could not work. Asserted by publishing, not by
    checking the type, because the type was never the problem.
    """
    from nodus_events import EventBusConfig

    cfg = EventBusConfig(channel="nodus-sdk-test")
    rt = NodusSDKRuntime().attach_events(cfg)

    assert rt.event_bus is not cfg, "the config was stored instead of a bus"
    assert hasattr(rt.event_bus, "publish")
    rt.event_bus.publish("nodus_sdk.test")

    rt2 = create_runtime(events=EventBusConfig(channel="nodus-sdk-test-2"))
    rt2.event_bus.publish("nodus_sdk.test")


@requires_events
def test_a_caller_supplied_bus_is_used_verbatim(fresh_event_bus):
    sentinel = object()
    rt = NodusSDKRuntime().attach_events(sentinel)
    assert rt.event_bus is sentinel
    assert "events" in rt.attached_bridges()


@requires_events
def test_create_runtime_events_true_builds_a_working_bus(fresh_event_bus):
    rt = create_runtime(events=True)
    assert rt.event_bus is not None
    rt.event_bus.publish("nodus_sdk.test")


# --------------------------------------------------------------------------- #
# the invariant, over every holder bridge
# --------------------------------------------------------------------------- #

# (bridge name in attached_bridges(), attribute holding what was attached)
HOLDER_BRIDGES = [
    ("events", "event_bus"),
    ("auth", "auth_key_ring"),
]


@pytest.mark.parametrize("bridge,attribute", HOLDER_BRIDGES, ids=[b for b, _ in HOLDER_BRIDGES])
def test_a_holder_bridge_is_never_recorded_holding_nothing(
    bridge, attribute, monkeypatch, fresh_event_bus
):
    """The rule both defects broke, stated once.

    Driven off a table so a *third* holder bridge added later has to answer it
    too -- the fix for this class is to name the set once and make the test
    read the set, not to patch the two methods that happened to be wrong.

    Checked with the optional packages installed *and* with them hidden, since
    "package absent" is the branch that used to record a bridge anyway.
    """
    monkeypatch.setenv("SECRET_KEY", CONFIGURED_SECRET)

    for hide in (False, True):
        if hide:
            monkeypatch.setattr("nodus_sdk.runtime._available", lambda pkg: False)
        rt = NodusSDKRuntime()
        getattr(rt, f"attach_{bridge}")()
        held = getattr(rt, attribute)
        recorded = bridge in rt.attached_bridges()
        assert recorded == (held is not None), (
            f"attach_{bridge}() with the package "
            f"{'hidden' if hide else 'present'}: recorded={recorded} but "
            f"{attribute} is {'set' if held is not None else 'None'}"
        )
