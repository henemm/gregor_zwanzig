"""TDD RED/GREEN — Issue #1427 S1: die neue Gefahrenart "flood" (Hochwasser/
Erdrutsch) braucht eine deutsche Anzeige-Bezeichnung im Mail-/Telegram-Renderer
UND einen eigenen Kurz-Chip mit stufengerechter Farbe in der Vergleichs-Mail
(statt des rohen Quell-Labels mit neutraler Farbe, Bug-Muster #1239).

SPEC: docs/specs/modules/feat_1427_dpc_warn_fallback.md, AC-1.

Kein Mock: ruft die echten Renderer-Funktionen
`output.renderers.alert.official_alerts._hazard_display()` und
`output.renderers.email.compare_html._warn_short()` mit einem echten
`OfficialAlert`-Objekt auf (kein Patch, keine nachgebaute Kopie der Logik).
"""
from __future__ import annotations

from services.official_alerts.models import OfficialAlert


def _flood_alert(level: int = 3) -> OfficialAlert:
    """Realistisches OfficialAlert-Objekt mit hazard='flood' -- Label wie ein
    unaufbereitetes MeteoAlarm-Rohlabel, damit ein durchgereichter Rohwert im
    Test sichtbar würde (statt eines zufällig 'schön' aussehenden Labels)."""
    return OfficialAlert(
        source="meteoalarm", hazard="flood", level=level,
        label="12; flooding", region_label="Alba",
    )


def test_flood_hazard_erscheint_als_hochwasser_erdrutsch_im_mail_label():
    """AC-1: GIVEN eine amtliche Warnung mit hazard='flood', WHEN sie fuer die
    Mail aufbereitet wird (_hazard_display, nutzt _HAZARD_LABELS), THEN
    erscheint die deutsche Bezeichnung 'Hochwasser/Erdrutsch' -- RED heute:
    'flood' fehlt im Katalog, die Funktion faellt auf das rohe Quell-Label
    zurueck."""
    from output.renderers.alert.official_alerts import _hazard_display

    alert = _flood_alert()

    typ, _sms = _hazard_display(alert)

    assert typ == "Hochwasser/Erdrutsch", (
        f"hazard='flood' muss auf die deutsche Bezeichnung 'Hochwasser/Erdrutsch' "
        f"abbilden (_HAZARD_LABELS), erhalten {typ!r} -- heute fehlt 'flood' im "
        f"Katalog, _hazard_display() faellt auf das rohe Quell-Label "
        f"({alert.label!r}) zurueck"
    )


def test_flood_kurzchip_hat_eigenen_text_statt_rohem_quelllabel():
    """AC-1: GIVEN dieselbe Warnung, WHEN der Kurz-Chip fuer die
    Vergleichs-Mail erzeugt wird (_warn_short), THEN traegt er einen EIGENEN
    Kurztext -- nicht das rohe Quell-Label unveraendert durchgereicht
    (Bug-Muster #1239: fehlendes Mapping erscheint sonst als Rohtext)."""
    from output.renderers.email.compare_html import _warn_short

    alert = _flood_alert()

    text, _severity = _warn_short(alert)

    assert text != alert.label, (
        f"Kurz-Chip fuer 'flood' muss einen EIGENEN Kurztext tragen, nicht "
        f"das rohe Quell-Label durchreichen, erhalten {text!r} (== alert.label)"
    )


def test_flood_kurzchip_hat_stufenfarbe_statt_neutraler_default_farbe():
    """AC-1: GIVEN dieselbe Warnung, WHEN der Kurz-Chip erzeugt wird, THEN
    traegt er eine zur Warnstufe passende Farbe -- nicht die neutrale
    Default-Severity 'info', die heute jeder unbekannte hazard erhaelt."""
    from output.renderers.email.compare_html import _warn_short

    alert = _flood_alert(level=3)

    _text, severity = _warn_short(alert)

    assert severity != "info", (
        f"Kurz-Chip fuer 'flood' muss eine zur Stufe passende Farbe tragen "
        f"(analog wildfire_risk: caution/warn/danger je level), nicht die "
        f"neutrale Default-Farbe 'info', erhalten severity={severity!r}"
    )


def test_flood_kurzchip_farbe_eskaliert_mit_der_stufe():
    """AC-1 (Praezisierung): GIVEN zwei Warnungen mit hazard='flood', aber
    unterschiedlicher Stufe (gelb=2 vs. rot=4), WHEN der Kurz-Chip fuer beide
    erzeugt wird, THEN unterscheidet sich die Farbe zwischen den beiden --
    eine feste, stufenunabhaengige Farbe waere fuer eine Sicherheitsmeldung
    irrefuehrend (Rot muss dringlicher aussehen als Gelb)."""
    from output.renderers.email.compare_html import _warn_short

    _text_low, severity_low = _warn_short(_flood_alert(level=2))
    _text_high, severity_high = _warn_short(_flood_alert(level=4))

    assert severity_low != severity_high, (
        f"Stufe 2 (gelb) und Stufe 4 (rot) muessen unterschiedliche Farben "
        f"ergeben, beide lieferten severity={severity_low!r}"
    )
