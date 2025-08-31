


# Source Code – Gregor Zwanzig

This folder contains the Python source code for the project.

---

## Structure

- `app/cli.py` → Command-line entry point. Handles arguments (`--report`, `--channel`, `--dry-run`, `--config`, `--debug`) and invokes business logic.
- `app/core.py` → Core functions, including mailer and channel handling.
- `app/debug.py` → DebugBuffer implementation; ensures identical debug output for console and email.
- `app/__init__.py` → Package marker.
- `__init__.py` → Root package marker.

---

## Guidelines

- Follow `.cursor/rules/00_scoping.mdc`: keep functions small (≤50 LoC), modules ≤400 LoC.
- Test-first: always add a test before implementing new functionality.
- All output formats (SMS, Email, Console) must remain consistent with `docs/*_spec.md`.

---

## Notes
- No business logic should be placed in `cli.py`; keep it in `core.py` or dedicated modules.
- Debug output must follow `docs/debug_format.md`.
- Contracts and schemas are the single source of truth; do not diverge.