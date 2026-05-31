# Contributing to nodus-sdk

## Setup

```bash
git clone https://github.com/Masterplanner25/nodus-sdk.git
cd nodus-sdk
pip install -e ".[dev]"
```

Tests require nodus-lang source:

```bash
PYTHONPATH="C:/dev/Coding Language/src" pytest tests/ -q
```

## Code style

- Python 3.10+
- Bridge host functions must return plain dicts (maps), not `Record` objects —
  `NodusRuntime._to_runtime_value` converts dicts to maps; `.nd` code uses
  `r["key"]` not `r.key`
- All bridge `available()` methods must guard with `importlib.util.find_spec`
- `attach_*` methods must be idempotent (check `_attached` set)
- `_ClosureProxy`-aware execution: when passing closures across module
  boundaries, check `isinstance(fn, _ClosureProxy)` and use `caller_vm`

## Bridge development pattern

Each bridge follows this structure:
1. Module-level `_AVAILABLE = importlib.util.find_spec("dep") is not None`
2. Bridge class with `available()` method
3. `register_host_functions(runtime)` registers Python callables as nodus builtins
4. Return dicts (not Records) from host functions

## Submitting changes

1. Fork the repo and create a branch from `main`
2. Add tests for any new behaviour
3. Ensure `PYTHONPATH=... pytest tests/ -q` passes
4. Open a pull request with a description of what changes and why
