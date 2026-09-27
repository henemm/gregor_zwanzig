"""
PII-Log-Maskierung fuer E-Mail-Adressen (Issue #2157).

Reine String-Utility ohne I/O/Rendering/Transport -- gehoert fachlich nicht
in die `output`-Schicht. Der Architektur-Waechter in trip_report_scheduler.py
(Epic #1301 B4, tests/unit/test_notification_service.py) verbietet dem
Scheduler Importe aus `output.*`; diese Maskierungsfunktion wird aber
sowohl von der Output-Schicht (output.channels.email) als auch von der
Service-/Scheduler-Schicht gebraucht. Deshalb liegt sie hier, in einer
neutralen Utility-Schicht, die von beiden Seiten importiert werden darf.
"""
from __future__ import annotations

from email.utils import getaddresses

from output.channels.email import _extract_addr


def _mask_addr_for_log(raw: str) -> str:
    """Issue #1219 AC-6: reduziert eine Adresse auf die Domain für Log-/
    Fehlermeldungen — verhindert, dass eine volle Empfängeradresse im
    Klartext geloggt bzw. in einer Exception-Message ausgegeben wird."""
    addr = _extract_addr(raw)
    _, sep, domain = addr.partition("@")
    return f"***@{domain.lower()}" if sep else "***"


_KNOWN_OPS_MAILBOXES = frozenset({
    "gregor-test@henemm.com",
    "gregor-staging@henemm.com",
})


def mask_addr_for_pii_log(raw: str) -> str:
    """PII-Maskierung fuer echte Nutzeradressen (#2157) -- bekannte
    Betriebs-/Test-Postfaecher bleiben unmaskiert, damit die #1847-Diagnose
    (gregor-test@ vs. gregor-staging@, gleiche Domain) erhalten bleibt."""
    teile = [addr for _, addr in getaddresses([raw]) if addr]
    if len(teile) > 1:
        return ", ".join(mask_addr_for_pii_log(addr) for addr in teile)
    addr = _extract_addr(raw).strip().lower()
    if addr in _KNOWN_OPS_MAILBOXES:
        return raw
    return _mask_addr_for_log(raw)
