"""TDD RED — #1969 AC-26/AC-27: der Abo-Fuß der Compare-Mail nennt den
ECHTEN nächsten Versand (zentrale Ableitung, ``strict_after=True``).

Spec: docs/specs/modules/feat_1969_naechstes_briefing.md (AC-26, AC-27)

Heute rechnet ``compare_html._compute_next_send`` selbst: nur ein Datum,
daily = pauschal „morgen", weekly = nächster Wochentag ab morgen; Slots,
``end_date`` und Pause sind unbekannt, Uhrzeit und Zonenkürzel fehlen.

Einstieg: ``ComparePreviewService._render_email(ctx)`` — der Render-Pfad, der
das ROHE Preset-Dict bereits in der Hand hat (``ctx["preset"]``) und daraus
``render_compare_email`` aufruft. ``render_compare_email`` allein kennt nur
``preset_schedule``/``preset_weekday``; ein Test darüber müsste einen neuen
Parameter erfinden. GREEN muss das Preset von hier bis
``_render_abo_footer``/``_compute_next_send`` durchreichen. Bekannte Lücke:
die Verdrahtung im Versandpfad (``scheduler_dispatch_service`` ≈ Z. 648)
bewacht dieser Test NICHT (dort hängt der Render an Wetterabruf und Versand).

Zeit: Der Renderpfad hat keinen ``now``-Parameter, er liest die Systemuhr —
deshalb hier (wie im Bestandstest ``test_vorschau_anzeige_folgen_ortszone.py``)
``freeze_time``, mit Nachweis, dass das Einfrieren greift.

Alle Zusicherungen gelten NUR dem Fuß-Abschnitt „Nächster Versand" — die
Kopfzeile derselben Mail trägt bereits Datum und Zone, ein Treffer im
ganzen HTML wäre vakuum-grün.
"""
from __future__ import annotations

import re
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from freezegun import freeze_time

PARIS = (42.30, 8.93)            # Korsika -> Europe/Paris
AUCKLAND = (-36.85, 174.76)      # -> Pacific/Auckland
PARIS_TZ = ZoneInfo("Europe/Paris")
AUCKLAND_TZ = ZoneInfo("Pacific/Auckland")

D23 = date(2026, 10, 23)   # Freitag (weekday 4)
D24 = date(2026, 10, 24)
D30 = date(2026, 10, 30)   # Freitag eine Woche später

_DATUM = re.compile(r"\d{2}\.\d{2}\.\d{4}")


def _utc(zone: ZoneInfo, tag: date, stunde: int) -> datetime:
    return datetime(tag.year, tag.month, tag.day, stunde, tzinfo=zone).astimezone(timezone.utc)


def _preset(loc_id: str, **overrides) -> dict:
    preset = {
        "id": "fuss-preset",
        "kind": "vergleich",
        "name": "Fuss-Test",
        "schedule": "daily",
        "weekday": None,
        "location_ids": [loc_id],
        "archived_at": None,
        "morning_enabled": True,
        "morning_time": "07:00:00",
        "evening_enabled": True,
        "evening_time": "18:00:00",
    }
    preset.update(overrides)
    return preset


def _fuss(preset: dict, coords, now_utc: datetime, target_date: date) -> str:
    """Rendert die Compare-Mail über den Vorschau-Renderpfad zu ``now_utc`` und
    liefert NUR den Fuß-Abschnitt ab „Nächster Versand" bis zum Zellende."""
    from app.user import ComparisonResult, LocationResult, SavedLocation
    from services.compare_preview_service import ComparePreviewService
    from services.report_config_resolver import resolve_compare_render_options

    lat, lon = coords
    ort = SavedLocation(id=preset["location_ids"][0], name="Fuss-Ort",
                        lat=lat, lon=lon, elevation_m=100)
    ctx = {
        "preset": preset,
        "result": ComparisonResult(
            locations=[LocationResult(location=ort)], time_window=(9, 16),
            target_date=target_date,
        ),
        "profile": None,
        "opts": resolve_compare_render_options(preset),
        "name": preset["name"],
        "target_date": target_date,
    }
    with freeze_time(now_utc):
        assert datetime.now(tz=timezone.utc) == now_utc, "freeze_time greift nicht"
        html_body, _text = ComparePreviewService()._render_email(ctx)

    start = html_body.find("Nächster Versand")
    assert start >= 0, "Fuß-Abschnitt „Nächster Versand“ fehlt in der Mail"
    ende = html_body.find("</td>", start)
    return html_body[start:ende]


# ═══════════════════════════════ AC-26 ═══════════════════════════════


def test_ac26_daily_in_der_slot_stunde_nennt_den_folgetermin():
    """AC-26: daily 07:00/18:00, gerendert in der fälligen Stunde (Fr 23.10.
    07:00 CEST) ⇒ der laufende Versand zählt nicht; nächster = 23.10. 18:00
    (nicht pauschal „morgen" 24.10.)."""
    fuss = _fuss(_preset("ort-paris"), PARIS, _utc(PARIS_TZ, D23, 7), D23)

    assert "23.10.2026" in fuss, f"Folgetermin heute 18:00 fehlt: {fuss!r}"
    assert "18:00" in fuss, f"Uhrzeit des Folgetermins fehlt: {fuss!r}"
    assert "24.10.2026" not in fuss, f"pauschales „morgen“ statt Slot-Termin: {fuss!r}"
    assert "07:00" not in fuss, f"der gerade laufende Versand erscheint als nächster: {fuss!r}"


def test_ac26_weekly_morgens_gerendert_nennt_den_abend_des_versandtags():
    """AC-26: weekly Freitag, beide Slots, gerendert Fr 07:00 ⇒ nächster =
    Fr 23.10. 18:00 (heute nennt der Fuß pauschal den Freitag eine Woche später)."""
    preset = _preset("ort-paris", schedule="weekly", weekday=4)
    fuss = _fuss(preset, PARIS, _utc(PARIS_TZ, D23, 7), D23)

    assert "23.10.2026" in fuss and "18:00" in fuss, fuss
    assert "30.10.2026" not in fuss, fuss


def test_ac26_weekly_abends_gerendert_nennt_den_naechsten_wochentag():
    """AC-26: weekly Freitag, beide Slots, gerendert Fr 18:00 ⇒ nächster =
    Fr 30.10. 07:00 (nächster passender Wochentag, Morgen-Slot)."""
    preset = _preset("ort-paris", schedule="weekly", weekday=4)
    fuss = _fuss(preset, PARIS, _utc(PARIS_TZ, D23, 18), D24)

    assert "30.10.2026" in fuss, fuss
    assert "07:00" in fuss, f"Uhrzeit des Morgen-Slots fehlt: {fuss!r}"
    assert "18:00" not in fuss, f"der laufende Abend-Versand erscheint als nächster: {fuss!r}"


def test_ac26_end_date_heute_kein_weiterer_termin():
    """AC-26: end_date = heute, nur Morgen-Slot, gerendert in der Slot-Stunde ⇒
    kein weiterer Termin im Fuß (heute stünde dort „morgen", 24.10.)."""
    preset = _preset("ort-paris", end_date="2026-10-23", evening_enabled=False)
    fuss = _fuss(preset, PARIS, _utc(PARIS_TZ, D23, 7), D23)

    assert "24.10.2026" not in fuss, f"Termin nach end_date genannt: {fuss!r}"
    assert not _DATUM.search(fuss.replace("Nächster Versand", "")), (
        f"Fuß nennt trotz abgelaufenem Vergleich ein Datum: {fuss!r}"
    )


def test_ac26_pausierter_vergleich_nennt_keinen_termin():
    """AC-26: Pause (paused_at) ⇒ kein Termin im Fuß (heute: „morgen")."""
    preset = _preset("ort-paris", paused_at="2026-10-22T10:00:00+00:00")
    fuss = _fuss(preset, PARIS, _utc(PARIS_TZ, D23, 7), D23)

    assert not _DATUM.search(fuss), f"Fuß nennt trotz Pause ein Datum: {fuss!r}"


# ═══════════════════════════════ AC-27 ═══════════════════════════════


def test_ac27_termin_in_der_ortszone_mit_kuerzel():
    """AC-27: Ortsvergleich in Auckland; gerendert 23.10. 18:00 UTC = 24.10.
    07:00 NZDT (Slot-Stunde) ⇒ Fuß nennt 24.10.2026 18:00 mit Kürzel NZDT —
    nicht die UTC-Fassung (24.10. 05:00 UTC)."""
    now = _utc(AUCKLAND_TZ, D24, 7)
    assert now == datetime(2026, 10, 23, 18, tzinfo=timezone.utc)
    erwartet = datetime(2026, 10, 24, 18, tzinfo=AUCKLAND_TZ)
    kuerzel = erwartet.tzname()
    assert kuerzel == "NZDT"

    fuss = _fuss(_preset("ort-nz"), AUCKLAND, now, D24)

    assert "24.10.2026" in fuss, fuss
    assert "18:00" in fuss, f"Ortszeit 18:00 fehlt: {fuss!r}"
    assert kuerzel in fuss, f"Zonenkürzel {kuerzel} fehlt im Fuß: {fuss!r}"
    utc_fassung = erwartet.astimezone(timezone.utc).strftime("%H:00")
    assert utc_fassung not in fuss, f"Fuß nennt UTC-Zeit {utc_fassung}: {fuss!r}"
