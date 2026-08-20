"""Regressions-Waechter — Issue #1944, AC-8: SMS-, E-Mail- und
Telegram-Ausgabe der amtlichen Warnung bleiben bei gleicher Eingabe
BYTE-IDENTISCH.

SPEC: docs/specs/modules/feat_1944_warn_mitschnitt_herkunft.md (AC-8)

Diese Datei ist BEWUSST BEREITS GRUEN. Sie friert den gerenderten String je
Kanal als Ganzes ein (Schnappschuss-Fixture
``tests/fixtures/official_alert_render_snapshot_1944.json``) -- kein
``assert "xy" in text``. Die Herkunfts-Erweiterung ist reine Beweisaufnahme;
aendert sich hier auch nur ein Zeichen, hat sie sichtbares Verhalten
angefasst.

Deterministisch ohne Wanduhr: alle Gueltigkeitszeiten sind feste
Zeitstempel, ``stand_at`` und ``tz`` sind Parameter. Die Renderer selbst
rufen kein ``datetime.now()``.

Pfadregel #1409: die Fixture wird relativ zu DIESER Datei aufgeloest
(``Path(__file__)``), nie ueber einen festen Hauptrepo-Pfad -- sonst laese
der Lauf aus dem Worktree die Datei des Hauptrepos.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

SNAPSHOT = Path(__file__).resolve().parents[1] / "fixtures" / \
    "official_alert_render_snapshot_1944.json"

TZ = ZoneInfo("Europe/Vienna")


def _alert(source: str, hazard: str, level: int, label: str, region: str,
           von: datetime, bis: datetime):
    from services.official_alerts.models import OfficialAlert

    return OfficialAlert(
        source=source, hazard=hazard, level=level, label=label,
        region_label=region, valid_from=von, valid_to=bis,
    )


def _feste_warnungen() -> list:
    """Zwei Warnungen unterschiedlicher Stufe/Gefahr mit festen Zeitraeumen."""
    return [
        _alert(
            "geosphere_warn", "wind_gust", 3, "Sturmwarnung", "Gailtal",
            datetime(2026, 7, 10, 13, 0, tzinfo=timezone.utc),
            datetime(2026, 7, 10, 19, 0, tzinfo=timezone.utc),
        ),
        _alert(
            "geosphere_warn", "extreme_heat", 2, "Hitzewarnung", "Hermagor",
            datetime(2026, 7, 10, 8, 0, tzinfo=timezone.utc),
            datetime(2026, 7, 11, 1, 0, tzinfo=timezone.utc),
        ),
    ]


def render_all() -> dict:
    """Alle vier Ausgabefassungen beider Flaechen -- eine Funktion, damit
    Schnappschuss-Erzeugung und Pruefung nachweislich denselben Aufbau
    verwenden."""
    from output.renderers.alert.official_alerts import (
        build_compare_official_alert_notices,
        build_official_alert_notices,
        render_official_alert_html,
        render_official_alert_mail_plain,
        render_official_alert_sms,
        render_official_alert_subject,
        render_official_alert_telegram,
    )

    warnungen = _feste_warnungen()
    trip_notices = build_official_alert_notices(
        None, [(warnungen[0], ["1"]), (warnungen[1], ["2"])],
    )
    compare_notices = build_compare_official_alert_notices(
        ["loc-a", "loc-b"], {"loc-a": "Hermagor", "loc-b": "St. Stefan"},
        [(warnungen[0], ["loc-a"]), (warnungen[1], ["loc-b"])],
    )
    quelle = "GeoSphere Austria"
    return {
        "trip_subject": render_official_alert_subject(trip_notices, prefix="Trip"),
        "trip_html": render_official_alert_html(
            trip_notices, source_label=quelle, stand_at="09:30", tz=TZ,
        ),
        "trip_mail_plain": render_official_alert_mail_plain(
            trip_notices, source_label=quelle, stand_at="09:30", tz=TZ,
        ),
        "trip_telegram": render_official_alert_telegram(
            trip_notices, prefix="Trip", source_label=quelle, tz=TZ,
        ),
        # FORTGESCHRIEBEN (#1948 S5): `sms_prefix` (Trip-/Preset-Name) ist
        # ersatzlos entfallen; der Schnappschuss wird fuer `trip_sms`/
        # `compare_sms` bewusst neu erzeugt (kein Goldstring-Editieren).
        "trip_sms": render_official_alert_sms(trip_notices, tz=TZ),
        "compare_subject": render_official_alert_subject(
            compare_notices, prefix="Vergleich",
        ),
        "compare_html": render_official_alert_html(
            compare_notices, source_label=quelle, stand_at="09:30", tz=TZ,
        ),
        "compare_telegram": render_official_alert_telegram(
            compare_notices, prefix="Vergleich", source_label=quelle, tz=TZ,
        ),
        "compare_sms": render_official_alert_sms(compare_notices, tz=TZ),
    }


def test_ac8_ausgabe_aller_kanaele_bleibt_byte_identisch():
    """AC-8: GIVEN identische Eingabedaten, WHEN SMS-, E-Mail- und
    Telegram-Ausgabe gerendert werden, THEN sind Inhalt und Format
    byte-identisch zum eingefrorenen Stand -- verglichen wird der GESAMTE
    gerenderte String je Kanal, nicht das Vorkommen einer Teilzeichenkette."""
    assert SNAPSHOT.exists(), (
        f"Schnappschuss-Fixture fehlt: {SNAPSHOT} — ohne sie bewacht dieser "
        f"Test nichts."
    )
    erwartet = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    ist = render_all()

    assert sorted(ist) == sorted(erwartet), (
        f"Andere Ausgabemenge als eingefroren: {sorted(ist)!r} vs "
        f"{sorted(erwartet)!r}"
    )
    abweichungen = [k for k in erwartet if ist[k] != erwartet[k]]
    assert not abweichungen, (
        "Die Ausgabe hat sich veraendert (AC-8 verlangt Byte-Identitaet) in: "
        + ", ".join(
            f"{k} (erwartet {len(erwartet[k])} Zeichen, war {len(ist[k])})"
            for k in abweichungen
        )
    )


def test_ac8_die_pruefung_schlaegt_bei_einer_echten_abweichung_an():
    """Gegenprobe: der Vergleich oben ist eine Gleichheitspruefung auf dem
    ganzen String -- schon ein einzelnes zusaetzliches Zeichen faellt auf.
    Ohne diesen Nachweis waere „keine Abweichungen" auch die Antwort einer
    Pruefung, die gar nichts vergleicht."""
    erwartet = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    verfaelscht = dict(erwartet)
    schluessel = "trip_sms"
    verfaelscht[schluessel] = erwartet[schluessel] + "."
    assert [k for k in erwartet if verfaelscht[k] != erwartet[k]] == [schluessel]
