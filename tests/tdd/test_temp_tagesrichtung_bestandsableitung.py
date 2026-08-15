"""Bestandsdaten erben die Tagesrichtungen aus der Elterngroesse (#1728 S1).

Spec: ``docs/specs/modules/feat_1728_s1_temp_aufloesung.md`` — AC-8 bis AC-13
(DEC-6 Ableitung im Ladepfad, Roundtrip-Invarianz, reale Bestandsdatei,
Zwei-Nutzer-Trennung, Kanal-Kaskade).

🔴 Prueflogik: die Ableitung muss im LADEPFAD (``loader.py``) wirken, nicht nur
im Katalog-Default. Deshalb geht jeder Test durch ``load_trip()`` gegen eine
echte JSON-Datei — ein von Hand mit den vier neuen IDs vorbelegtes
``MetricConfig`` umginge genau die Stelle, die hier bewiesen werden soll.
Gerendert wird anschliessend ueber ``TripReportFormatter().format_email()``
(Wirkort), nie ueber einen Helfer.

Kern-Schicht, deterministisch: kein ``Mock()``, kein ``patch()``, kein Netz,
kein Transport.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
TESTS_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from app.loader import load_trip, save_trip  # noqa: E402
from app.models import TripReportConfig  # noqa: E402
from output.renderers.trip_report import TripReportFormatter  # noqa: E402

from tests.tdd import _min_temp_felt_fixtures as F  # noqa: E402

TEMP_LOW = "temperature_day_low"
TEMP_HIGH = "temperature_day_high"
FELT_LOW = "wind_chill_day_low"
FELT_HIGH = "wind_chill_day_high"
NEW_IDS = (TEMP_LOW, TEMP_HIGH, FELT_LOW, FELT_HIGH)

# Die reale Bestandsdatei (versionierte Kopie des Produktiv-Trips; die
# Session-Fixture tests/conftest.py::_materialize_real_data_root_fixtures
# spiegelt genau diese Datei in den Datenbaum, #1624).
GR221 = TESTS_ROOT / "fixtures" / "data_root" / "users" / "default" / \
    "trips" / "gr221-mallorca.json"


def _write_trip(root: Path, user_id: str, trip_id: str,
                metrics: list[dict], channel_layouts: dict | None = None,
                channel_layouts_per_report: dict | None = None) -> None:
    """Gespeicherter Bestands-Trip im echten Dateiformat (briefings/<id>.json)."""
    display_config: dict = {"trip_id": trip_id, "metrics": metrics,
                            "show_night_block": True, "night_interval_hours": 2}
    if channel_layouts is not None:
        display_config["channel_layouts"] = channel_layouts
    if channel_layouts_per_report is not None:
        display_config["channel_layouts_per_report"] = channel_layouts_per_report
    path = root / "users" / user_id / "briefings" / f"{trip_id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "id": trip_id, "name": trip_id, "kind": "route", "stages": [],
        "display_config": display_config,
    }, indent=2, ensure_ascii=False), encoding="utf-8")


def _load(root: Path, user_id: str, trip_id: str):
    trip = load_trip(trip_id, data_dir=root, user_id=user_id)
    assert trip is not None, f"Trip {trip_id!r} von {user_id!r} nicht geladen"
    return trip


def _sms(dc) -> str:
    """Echtes Abend-Briefing — der Weg, den der Versand nimmt."""
    return TripReportFormatter().format_email(
        [F.segment()], trip_name="I1728", report_type="evening",
        night_weather=F.night_weather(), display_config=dc,
        stage_name=F.STAGE_NAME, tz=F.TZ,
        report_config=TripReportConfig(),
    ).sms_text


def _enabled_state(dc, metric_id: str):
    """``True``/``False`` = Eintrag vorhanden, ``None`` = gar kein Eintrag."""
    for mc in dc.metrics:
        if mc.metric_id == metric_id:
            return mc.enabled
    return None


# ---------------------------------------------------------------------------
# AC-8 / AC-9 — DEC-6: die gespeicherte Auswertungswahl der Elterngroesse
# entscheidet, welche Tagesrichtung abgeleitet AN ist
# ---------------------------------------------------------------------------

class TestLoaderDerivesDayDirectionsFromParent:

    def test_stored_min_only_yields_k_without_d(self, tmp_path):
        """AC-8: ``temperature: {enabled: true, aggregations: ["min"]}`` ohne
        eigene Tagesrichtungs-Eintraege -> ``temperature_day_low`` abgeleitet
        AN, ``temperature_day_high`` AUS; die SMS traegt K und kein D."""
        _write_trip(tmp_path, "default", "bestand-min", [
            {"metric_id": "temperature", "enabled": True, "aggregations": ["min"]},
            {"metric_id": "precipitation", "enabled": True},
        ])
        dc = _load(tmp_path, "default", "bestand-min").display_config

        assert _enabled_state(dc, TEMP_LOW) is True, (
            f"{TEMP_LOW!r} nach dem Laden: {_enabled_state(dc, TEMP_LOW)!r} — "
            f"die Bestands-Ableitung in loader.py fehlt oder wertet 'min' "
            f"nicht aus.\nGeladen: {[m.metric_id for m in dc.metrics]}"
        )
        assert _enabled_state(dc, TEMP_HIGH) is False, (
            f"{TEMP_HIGH!r} nach dem Laden: "
            f"{_enabled_state(dc, TEMP_HIGH)!r} — 'max' steht NICHT in der "
            f"gespeicherten Auswertungswahl ['min']."
        )
        sms = _sms(dc)
        assert F.sms_token_value(sms, "K") == str(int(F.HIKE_MIN_C)), (
            f"K fehlt im Briefing des Bestands-Trips.\nSMS: {sms}"
        )
        assert F.sms_token_value(sms, "D") is None, (
            f"D erscheint, obwohl der Bestands-Trip nur 'min' gespeichert "
            f"hat.\nSMS: {sms}"
        )

    def test_stored_default_keeps_both_felt_directions(self, tmp_path):
        """AC-9: ``wind_chill: {enabled: true}`` (impliziter Default
        min+max, 16 von 17 Bestandstrips) -> beide gefuehlten Tagesrichtungen
        abgeleitet AN; die SMS traegt FK UND FD. Kein Bestandstrip verliert
        durch die Umstellung eine Tagesrichtung."""
        _write_trip(tmp_path, "default", "bestand-default", [
            {"metric_id": "wind_chill", "enabled": True},
            {"metric_id": "precipitation", "enabled": True},
        ])
        dc = _load(tmp_path, "default", "bestand-default").display_config

        ist = {mid: _enabled_state(dc, mid) for mid in (FELT_LOW, FELT_HIGH)}
        assert ist == {FELT_LOW: True, FELT_HIGH: True}, (
            f"Ableitung falsch: {ist} — der gespeicherte Default "
            f"['min','max'] (loader.py:790) muss BEIDE Tagesrichtungen "
            f"anschalten.\nGeladen: {[m.metric_id for m in dc.metrics]}"
        )
        sms = _sms(dc)
        fehlend = [s for s in ("FK", "FD") if F.sms_token_value(sms, s) is None]
        assert not fehlend, (
            f"Der Default-Bestandsfall verliert {fehlend} im Briefing.\n"
            f"SMS: {sms}"
        )


# ---------------------------------------------------------------------------
# AC-10 — Roundtrip: abgeleitete Eintraege werden nie zurueckgeschrieben
# ---------------------------------------------------------------------------

class TestRoundtripDoesNotMaterializeDerivedEntries:

    def test_load_save_keeps_file_free_of_derived_ids(self, tmp_path):
        """AC-10: Laden + unveraendert Speichern schreibt keine expliziten
        Eintraege fuer die vier neuen IDs, und die uebrigen
        ``display_config``-Felder bleiben erhalten (Merge, kein Replace).

        # BESTANDSSCHUTZ: heute bereits gruen — bewacht, dass Scheibe 1
        # dieses Verhalten nicht bricht. Kein RED-Nachweis.
        """
        original = [
            {"metric_id": "temperature", "enabled": True,
             "aggregations": ["min", "max"]},
            {"metric_id": "wind_chill", "enabled": True, "aggregations": ["min"]},
            {"metric_id": "precipitation", "enabled": True, "aggregations": ["sum"]},
        ]
        _write_trip(tmp_path, "default", "roundtrip", original)
        path = tmp_path / "users" / "default" / "briefings" / "roundtrip.json"
        vorher = json.loads(path.read_text(encoding="utf-8"))

        trip = _load(tmp_path, "default", "roundtrip")
        save_trip(trip, user_id="default", data_dir=tmp_path)
        nachher = json.loads(path.read_text(encoding="utf-8"))

        gespeichert = {m["metric_id"]: m
                       for m in nachher["display_config"]["metrics"]}
        materialisiert = [mid for mid in NEW_IDS if mid in gespeichert]
        assert not materialisiert, (
            f"Abgeleitete Eintraege {materialisiert} wurden in die Datei "
            f"zurueckgeschrieben — der derived-Filter "
            f"(loader.py:1324-1325/1529-1530) greift fuer sie nicht."
        )
        assert set(gespeichert) == {m["metric_id"] for m in original}, (
            f"Die Metrik-Menge der Datei hat sich geaendert: "
            f"{sorted(gespeichert)} statt "
            f"{sorted(m['metric_id'] for m in original)}"
        )
        for eintrag in original:
            gesp = gespeichert[eintrag["metric_id"]]
            assert (gesp["enabled"], gesp["aggregations"]) == (
                eintrag["enabled"], eintrag["aggregations"]), (
                f"{eintrag['metric_id']!r} hat sich beim Roundtrip "
                f"veraendert: {gesp!r} statt {eintrag!r}"
            )
        for feld in ("show_night_block", "night_interval_hours"):
            assert nachher["display_config"][feld] == \
                vorher["display_config"][feld], (
                f"display_config.{feld} ist beim Speichern verloren gegangen."
            )


# ---------------------------------------------------------------------------
# AC-11 — die reale Bestandsdatei mit abweichender Auswertung
# ---------------------------------------------------------------------------

class TestRealLegacyTripKeepsItsTokens:

    def test_gr221_mallorca_keeps_k_d_fk_and_loses_only_fd(self):
        """AC-11: ``gr221-mallorca.json`` (``temperature: ["min","max","avg"]``,
        ``wind_chill: ["min"]``) -> K und D bleiben (der entfallende
        Mittelwert kostet keine Tagesrichtung, E1), FK bleibt, FD fehlt.
        N/FN/WC unveraendert.

        # BESTANDSSCHUTZ: heute bereits gruen — bewacht, dass Scheibe 1
        # dieses Verhalten nicht bricht. Kein RED-Nachweis.
        """
        assert GR221.exists(), f"Bestandsdatei fehlt: {GR221}"
        trip = load_trip(GR221)
        assert trip is not None
        sms = _sms(trip.display_config)

        vorhanden = F.present_symbols(sms, ("N", "K", "D", "FN", "FK", "FD", "WC"))
        assert vorhanden == {"N", "K", "D", "FN", "FK", "WC"}, (
            f"Token-Menge des realen Bestandstrips: {sorted(vorhanden)} — "
            f"erwartet N/K/D/FN/FK/WC ohne FD (wind_chill: ['min']).\n"
            f"SMS: {sms}"
        )


# ---------------------------------------------------------------------------
# AC-12 — zwei Nutzer, entgegengesetzte Auswahl, keine Vermischung
# ---------------------------------------------------------------------------

class TestTwoUsersOppositeDayDirections:

    def test_opposite_selections_do_not_bleed(self, tmp_path):
        """AC-12: Nutzer A waehlt nur ``temperature_day_high`` und
        ``wind_chill_day_low``, Nutzer B genau umgekehrt. Beide Briefings im
        selben Prozess duerfen sich nicht faerben."""
        def eintraege(temp_low, temp_high, felt_low, felt_high):
            return [
                {"metric_id": "temperature", "enabled": True},
                {"metric_id": TEMP_LOW, "enabled": temp_low},
                {"metric_id": TEMP_HIGH, "enabled": temp_high},
                {"metric_id": "wind_chill", "enabled": True},
                {"metric_id": FELT_LOW, "enabled": felt_low},
                {"metric_id": FELT_HIGH, "enabled": felt_high},
                {"metric_id": "precipitation", "enabled": True},
            ]
        _write_trip(tmp_path, "alpha", "tour", eintraege(False, True, True, False))
        _write_trip(tmp_path, "beta", "tour", eintraege(True, False, False, True))

        sms_a = _sms(_load(tmp_path, "alpha", "tour").display_config)
        sms_b = _sms(_load(tmp_path, "beta", "tour").display_config)

        ist_a = F.present_symbols(sms_a, ("K", "D", "FK", "FD"))
        ist_b = F.present_symbols(sms_b, ("K", "D", "FK", "FD"))
        assert ist_a == {"D", "FK"}, (
            f"Nutzer alpha zeigt {sorted(ist_a)} statt ['D', 'FK'].\n"
            f"SMS A: {sms_a}\nSMS B: {sms_b}"
        )
        assert ist_b == {"K", "FD"}, (
            f"Nutzer beta zeigt {sorted(ist_b)} statt ['FD', 'K'] — die "
            f"Auswahl von alpha faerbt offenbar ab.\n"
            f"SMS A: {sms_a}\nSMS B: {sms_b}"
        )


# ---------------------------------------------------------------------------
# AC-13 — Kanal-Kaskade: abgeleitete Groessen fallen nicht aus der SMS-Ebene
# ---------------------------------------------------------------------------

class TestCascadeKeepsDerivedDayDirections:

    def test_sms_channel_layout_without_new_ids_keeps_them(self, tmp_path):
        """AC-13: ein kanal-konfigurierter Bestands-Trip fuehrt in
        ``channel_layouts.sms`` (vom Editor vor dieser Scheibe geschrieben)
        keinen Eintrag fuer die vier neuen IDs. Sie muessen im SMS-Ergebnis
        trotzdem erhalten bleiben — sonst verliert JEDER kanal-konfigurierte
        Trip seine Tages-Token.

        Das BEFUELLTE Kanal-Layout ist der Kern des Tests: ohne es antwortet
        die Kaskade auf Ebene 3 (global) und der Test waere gruen, egal ob
        Ableitung und Kaskade zusammenspielen (Spec-Pruefhinweis 4).
        """
        _write_trip(
            tmp_path, "default", "kanal", [
                {"metric_id": "temperature", "enabled": True,
                 "aggregations": ["min", "max"]},
                {"metric_id": "precipitation", "enabled": True},
            ],
            channel_layouts={"sms": [
                {"metric_id": "temperature", "enabled": True},
                {"metric_id": "precipitation", "enabled": True},
            ]},
        )
        dc = _load(tmp_path, "default", "kanal").display_config

        assert dc.cascade_source_for_channel("sms", "evening") == "per_channel", (
            "Das Fixture antwortet nicht auf der Kanal-Ebene — der Test "
            "wuerde die Kaskade gar nicht pruefen."
        )
        ids = [m.metric_id for m in dc.get_metrics_for_channel("sms", "evening")]
        fehlend = [mid for mid in (TEMP_LOW, TEMP_HIGH) if mid not in ids]
        assert not fehlend, (
            f"{fehlend} fallen aus dem SMS-Schnitt heraus: {ids!r} — die "
            f"abgeleiteten Tagesrichtungen fehlen im gespeicherten "
            f"Kanal-Layout und werden vom Maximum-Schnitt (ADR-0050) "
            f"weggeschnitten."
        )
        sms = _sms(dc)
        fehlende_token = [s for s in ("K", "D")
                          if F.sms_token_value(sms, s) is None]
        assert not fehlende_token, (
            f"Der kanal-konfigurierte Trip verliert {fehlende_token} im "
            f"Briefing.\nSMS: {sms}"
        )


    def test_per_report_layout_without_new_ids_keeps_them(self, tmp_path):
        """DEC-6b, zweite Ebene: dieselbe Ableitung muss in
        ``channel_layouts_per_report`` greifen (``loader.py:877-905``). Die
        per-Report-Ebene schlaegt die Kanal-Ebene (#434) — greift die
        Ableitung nur dort, verliert ein Trip mit Abend-Sonderlayout seine
        Tages-Token trotzdem."""
        eintraege = [
            {"metric_id": "temperature", "enabled": True},
            {"metric_id": "precipitation", "enabled": True},
        ]
        _write_trip(
            tmp_path, "default", "kanal-report", [
                {"metric_id": "temperature", "enabled": True,
                 "aggregations": ["min", "max"]},
                {"metric_id": "precipitation", "enabled": True},
            ],
            channel_layouts={"sms": [{"metric_id": "precipitation",
                                      "enabled": True}]},
            channel_layouts_per_report={"evening": {"sms": eintraege}},
        )
        dc = _load(tmp_path, "default", "kanal-report").display_config

        assert dc.cascade_source_for_channel("sms", "evening") == "per_report", (
            "Das Fixture antwortet nicht auf der per-Report-Ebene — der Test "
            "wuerde die falsche Ebene pruefen."
        )
        ids = [m.metric_id for m in dc.get_metrics_for_channel("sms", "evening")]
        fehlend = [mid for mid in (TEMP_LOW, TEMP_HIGH) if mid not in ids]
        assert not fehlend, (
            f"{fehlend} fallen aus dem per-Report-SMS-Schnitt heraus: {ids!r}"
        )
        sms = _sms(dc)
        fehlende_token = [s for s in ("K", "D")
                          if F.sms_token_value(sms, s) is None]
        assert not fehlende_token, (
            f"Der Trip mit Abend-Sonderlayout verliert {fehlende_token}.\n"
            f"SMS: {sms}"
        )

    def test_channel_configured_trip_roundtrip_stays_free_of_derived(self, tmp_path):
        """Gegenstueck zu AC-10 fuer die KANAL-Ebene: der AC-10-Fixture traegt
        kein ``channel_layouts`` und haette nicht gefangen, dass die
        Kanal-Layout-Serialisierung (``loader.py:1361-1376``) abgeleitete
        Eintraege bis dahin ungefiltert zurueckschrieb. Ein Editor-Save haette
        die vier Gates damit materialisiert — genau der Replace-Effekt, den
        die Roundtrip-Invarianz verhindern soll."""
        _write_trip(
            tmp_path, "default", "kanal-roundtrip", [
                {"metric_id": "temperature", "enabled": True,
                 "aggregations": ["min", "max"]},
                {"metric_id": "precipitation", "enabled": True},
            ],
            channel_layouts={"sms": [
                {"metric_id": "temperature", "enabled": True},
                {"metric_id": "precipitation", "enabled": True},
            ]},
            channel_layouts_per_report={"evening": {"sms": [
                {"metric_id": "temperature", "enabled": True},
            ]}},
        )
        path = tmp_path / "users" / "default" / "briefings" / "kanal-roundtrip.json"

        trip = _load(tmp_path, "default", "kanal-roundtrip")
        save_trip(trip, user_id="default", data_dir=tmp_path)
        nachher = json.loads(path.read_text(encoding="utf-8"))["display_config"]

        abgeleitet = {*NEW_IDS, "temperature_night", "wind_chill_night"}
        for pfad, liste in (
            ("channel_layouts.sms", nachher["channel_layouts"]["sms"]),
            ("channel_layouts_per_report.evening.sms",
             nachher["channel_layouts_per_report"]["evening"]["sms"]),
            ("metrics", nachher["metrics"]),
        ):
            materialisiert = [m["metric_id"] for m in liste
                              if m["metric_id"] in abgeleitet]
            assert not materialisiert, (
                f"{pfad}: abgeleitete Eintraege {materialisiert} wurden in "
                f"die Datei zurueckgeschrieben."
            )


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__, "-v"])
