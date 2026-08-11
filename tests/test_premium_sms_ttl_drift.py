# doc-compliance-test
"""Frist-Drift-Waechter Python <-> Go fuer die gelernte Premium-SMS-Rueckadresse.

Issue #1717 (Scheibe S3), AC-11. Spec:
docs/specs/modules/feat_1717_s3_premium_sms_ui.md.

Werkzeug-Klasse (CLAUDE.md-Ausnahme ``# doc-compliance-test``, Vorbild
``tests/test_egress_inventory_drift.py``): dieser Laeufer liest
``internal/model/premium_sms.go`` als DATEN fuer eine Inventar-Regel (decken
sich die beiden Fristen?), nicht als Verhaltensnachweis auf Code-Strings. Aus
Python ist eine Go-Konstante nur als Text erreichbar; die Python-Seite kommt
bewusst ueber den echten Import, damit sie nicht durch einen Parser-Fehler
stillschweigend falsch gelesen werden kann.

Warum ein AC und keine Fussnote: die Verfallsfrist existiert nach S3
zwangsläufig zweimal — im Python-Sendepfad (``PREMIUM_SMS_REPLY_TTL``,
``src/output/channels/premium_sms.py``) und in der neuen Go-Ableitung, die
``GET /api/auth/profile`` fuer die Oberflaeche berechnet. Aendert eine Sitzung
nur eine der beiden Zahlen, zeigt die Oberflaeche "frisch", waehrend der
Sendepfad genau dieselbe Rueckadresse schon blockt — eine Anzeige, die der
Wirklichkeit widerspricht, ist schlechter als keine.

Erwartung in dieser Phase (TDD RED): ``internal/model/premium_sms.go``
existiert noch nicht -> ROT.

Pfadregel #1409: der Pruefling wird relativ zu DIESER Datei aufgeloest.
"""
from __future__ import annotations

import re
from datetime import timedelta
from pathlib import Path

from output.channels.premium_sms import PREMIUM_SMS_REPLY_TTL

REPO_ROOT = Path(__file__).resolve().parents[1]
GO_SOURCE = REPO_ROOT / "internal" / "model" / "premium_sms.go"

#: Deklarationsform in der Go-Quelle:
#:     PremiumSmsReplyTTL = 30 * 24 * time.Hour
_GO_TTL = re.compile(
    r"PremiumSmsReplyTTL\s*(?:time\.Duration\s*)?=\s*(?P<expr>[0-9A-Za-z_.*\s]+)"
)

#: time-Einheiten, die als Faktor auftreten duerfen.
_GO_UNITS = {
    "time.Nanosecond": timedelta(microseconds=0.001),
    "time.Microsecond": timedelta(microseconds=1),
    "time.Millisecond": timedelta(milliseconds=1),
    "time.Second": timedelta(seconds=1),
    "time.Minute": timedelta(minutes=1),
    "time.Hour": timedelta(hours=1),
}


def _parse_go_duration(expr: str) -> timedelta:
    """Rechnet einen Go-Duration-Ausdruck wie ``30 * 24 * time.Hour`` aus.

    Erlaubt sind ganzzahlige Faktoren und GENAU eine ``time.*``-Einheit. Alles
    andere ist ein Fehler und wird gemeldet statt stillschweigend als 0
    interpretiert -- sonst waere der Waechter gruen, weil er nichts versteht.
    """
    faktor = 1
    einheit: timedelta | None = None
    for teil in (t.strip() for t in expr.split("*")):
        if not teil:
            raise ValueError(f"Leerer Faktor in Go-Ausdruck: {expr!r}")
        if teil in _GO_UNITS:
            if einheit is not None:
                raise ValueError(f"Mehr als eine time-Einheit in {expr!r}")
            einheit = _GO_UNITS[teil]
            continue
        if not teil.isdigit():
            raise ValueError(f"Unverstaendlicher Faktor {teil!r} in {expr!r}")
        faktor *= int(teil)
    if einheit is None:
        raise ValueError(f"Keine time-Einheit in {expr!r}")
    return faktor * einheit


def _extract_go_ttl(text: str) -> timedelta:
    """Liest die Go-Frist aus dem Quelltext.

    Jede Zeile wird am ERSTEN ``//`` abgeschnitten und nur der Teil DAVOR
    geprueft (Vorbild egress-Drift-Waechter F002): eine auskommentierte
    Deklaration zaehlt nicht, ein Inline-Kommentar hinter einer echten
    Deklaration stoert nicht.
    """
    treffer: list[str] = []
    for line in text.splitlines():
        code = line.split("//", 1)[0]
        m = _GO_TTL.search(code)
        if m:
            treffer.append(m.group("expr"))
    if not treffer:
        raise AssertionError(
            "Keine Deklaration von PremiumSmsReplyTTL in "
            f"{GO_SOURCE.relative_to(REPO_ROOT)} gefunden — dann leitet die "
            "Go-Seite den Zustand der gelernten Rueckadresse ohne Frist ab."
        )
    if len(treffer) > 1:
        raise AssertionError(
            f"PremiumSmsReplyTTL ist {len(treffer)}-mal deklariert: {treffer} — "
            "genau eine Quelle je Prozess, sonst driften schon die Go-Kopien."
        )
    return _parse_go_duration(treffer[0])


def test_go_und_python_frist_sind_deckungsgleich():
    """GIVEN je eine Verfallsfrist der gelernten Rueckadresse in Python und Go
    WHEN eine der beiden Zahlen geaendert wird, die andere nicht
    THEN schlaegt dieser Test rot und benennt beide Fundstellen.
    """
    assert GO_SOURCE.exists(), (
        f"Go-Quelle fehlt: {GO_SOURCE.relative_to(REPO_ROOT)} — dort gehoert "
        "PremiumSmsReplyTTL hin (Go-Pendant zu PREMIUM_SMS_REPLY_TTL in "
        "src/output/channels/premium_sms.py). Ohne sie kann GET /api/auth/profile "
        "den Zustand der Rueckadresse nicht ableiten (Issue #1717 AC-11)."
    )

    go_ttl = _extract_go_ttl(GO_SOURCE.read_text(encoding="utf-8"))

    assert go_ttl == PREMIUM_SMS_REPLY_TTL, (
        "Verfallsfrist der gelernten Premium-SMS-Rueckadresse ist auseinander "
        f"gelaufen: Go ({GO_SOURCE.relative_to(REPO_ROOT)}: PremiumSmsReplyTTL) "
        f"= {go_ttl}, Python (src/output/channels/premium_sms.py: "
        f"PREMIUM_SMS_REPLY_TTL) = {PREMIUM_SMS_REPLY_TTL}. Die Oberflaeche "
        "wuerde damit 'frisch' anzeigen, wo der Sendepfad schon blockt (oder "
        "umgekehrt). Beide Werte angleichen — nicht einen."
    )


def test_go_duration_parser_versteht_was_er_liest():
    """GIVEN der Waechter liest die Go-Seite als Text
    WHEN der Ausdruck ein anderer ist als erwartet
    THEN faellt das auf, statt still als 0 durchzugehen.

    Ohne diese Gegenprobe koennte der Drift-Test gruen bleiben, weil der Parser
    nichts findet und trotzdem etwas vergleicht -- derselbe blinde Fleck, den
    F002 beim egress-Inventar hatte.
    """
    assert _parse_go_duration("30 * 24 * time.Hour") == timedelta(days=30)
    assert _parse_go_duration(" 7*24*time.Hour ") == timedelta(days=7)
    assert _parse_go_duration("90 * time.Minute") == timedelta(minutes=90)

    for kaputt in ("30 * 24", "30 * 24 * time.Hour * time.Minute", "dreissig * time.Hour"):
        try:
            _parse_go_duration(kaputt)
        except ValueError:
            continue
        raise AssertionError(
            f"Parser hat {kaputt!r} stillschweigend akzeptiert — dann bewacht er nichts."
        )


def test_go_ttl_extraktion_ignoriert_auskommentierte_deklaration():
    """GIVEN eine auskommentierte Deklaration und ein Inline-Kommentar
    WHEN die Go-Quelle geparst wird
    THEN zaehlt nur die echte Deklaration (F002-Lehre).
    """
    text = (
        "package model\n"
        "\n"
        "// PremiumSmsReplyTTL = 7 * 24 * time.Hour  // alter Wert, ersetzt\n"
        "const PremiumSmsReplyTTL = 30 * 24 * time.Hour // siehe premium_sms.py\n"
    )
    assert _extract_go_ttl(text) == timedelta(days=30)
