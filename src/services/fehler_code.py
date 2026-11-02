"""Ausnahmen mit stabilem Fehlercode (Issue #2674, ADR-0104).

Dienste kennen keine Nutzersprache: die Meldung ist der deutsche Katalogtext,
damit ``str(exc)`` fuer Logs und Altaufrufer byte-gleich bleibt. Der Router
lokalisiert ueber ``.code``/``.params`` (``api.fehler.api_fehler_aus``).
"""
from __future__ import annotations

from i18n import t


def fehler_mit_code(exc_type: type[Exception], code: str, **params: object) -> Exception:
    """Ausnahme ``exc_type`` mit Text ``api.fehler.<code>`` (de) plus ``.code``/``.params``."""
    exc = exc_type(t(f"api.fehler.{code}", "de", **params))
    exc.code = code  # type: ignore[attr-defined]
    exc.params = dict(params)  # type: ignore[attr-defined]
    return exc
