"""TDD RED — Issue #1895 Scheibe S2: die MIGRATION
`alert_rules[].channels` → `alert_metric_channels`.

SPEC: docs/specs/modules/alert_metric_channels.md — AC-18 bis AC-23
      (plus die Nutzer-Haelfte von AC-24), Abschnitt
      "Implementation Details (S2)" Punkt 5.
KONTEXT: docs/context/feat-1895-s2-kanal-leser.md — "Vier Migrations-Fallen".
MAPPING: docs/artifacts/feat-1895-s2-kanal-leser/ac-test-mapping.md

────────────────────────────────────────────────────────────────────────────
Gemessen wird am LADEPFAD, nicht an einem Funktionsnamen
────────────────────────────────────────────────────────────────────────────
Kein Test hier importiert eine noch nicht existierende Migrations-Funktion —
das waere ein Kollektionsfehler statt eines roten Tests und wuerde nebenbei
einen Implementierungsnamen vorschreiben. Gemessen wird ausschliesslich am
echten Weg, den auch der Betrieb geht: eine Trip-Datei auf Platte ablegen,
ueber `app.loader.load_trip()` laden, das Ergebnis befragen; fuer AC-21/AC-22
zusaetzlich ueber `save_trip()` zurueckschreiben und die geschriebene Datei
lesen. Muster: `tests/test_trip_alert_metric_channels_roundtrip.py` (S1).

RED-Grund heute (gemessen): `load_trip()` laesst `alert_metric_channels`
unveraendert — es gibt keine Migration, `alert_rules[].channels` bleibt die
einzige Quelle (`src/services/alert_channels.py:92`, preset-weite Union ohne
Metrik-Bezug). Alle Zusicherungen unten fallen als `AssertionError`.

────────────────────────────────────────────────────────────────────────────
Wertform: die Migration formt UM, sie haengt nicht nur um
────────────────────────────────────────────────────────────────────────────
`alert_rules[].channels` ist eine LISTE von Kanal-Strings
(`src/app/models.py:1254`), das Zielfeld traegt `{kanal: bool}`
(`internal/handler/trip_alert_metric_channels_test.go:111`). Die Tests
pruefen deshalb ueber `_aktive_kanaele()` die MENGE der eingeschalteten
Kanaele, nicht eine bestimmte Behaelterform — die Bedeutung ist die
Zusicherung, nicht die Schreibweise.

Testpolitik (CLAUDE.md): kein `Mock()`/`patch()`/`MagicMock`, keine
Dateiinhalt-Checks auf Quellcode. Die einzige gelesene Datei ist die vom
Pruefling selbst GESCHRIEBENE Trip-JSON (AC-21/AC-22) — das ist die
ausgelieferte Persistenz, kein Quelltext-Check. Pfadregel #1409: alle Pfade
haengen an `tmp_path` bzw. `app.loader.get_data_dir()`.
"""
from __future__ import annotations

import json
import shutil
import uuid

import pytest


# ═══════════════════════════ Fixtures & Helfer ══════════════════════════════

def _uid(prefix: str) -> str:
    return f"tdd-1895-mig-{prefix}-{uuid.uuid4().hex[:8]}"


@pytest.fixture()
def sauberer_nutzer():
    from app.loader import get_data_dir

    angelegt: list[str] = []

    def _registriere(prefix: str) -> str:
        user_id = _uid(prefix)
        angelegt.append(user_id)
        pfad = get_data_dir(user_id)
        if pfad.exists():
            shutil.rmtree(pfad, ignore_errors=True)
        return user_id

    yield _registriere

    for user_id in angelegt:
        pfad = get_data_dir(user_id)
        if pfad.exists():
            shutil.rmtree(pfad, ignore_errors=True)


def _regel(regel_id: str, metrik: str, kanaele, *, enabled: bool = True) -> dict:
    """Eine persistierte `AlertRule` in ihrer JSON-Form
    (`app/loader.py:_alert_rule_from_dict`). `kanaele` ist die LISTE, die der
    Bestand traegt."""
    return {
        "id": regel_id, "kind": "delta", "metric": metrik, "threshold": 5.0,
        "unit": "", "severity": "warning", "enabled": enabled,
        "channels": list(kanaele),
    }


def _trip_json(trip_id: str, *, regeln: list[dict], **extra) -> dict:
    daten = {
        "id": trip_id,
        "name": f"Migrations-Trip {trip_id}",
        "kind": "route",
        "stages": [{
            "id": "stage-1", "name": "Etappe 1", "date": "2026-07-10",
            "waypoints": [{
                "id": "wp-1", "name": "Start", "lat": 46.0, "lon": 9.0,
                "elevation_m": 1200,
            }],
        }],
        "aggregation": {"profile": "allgemein"},
        "alert_rules": regeln,
    }
    daten.update(extra)
    return daten


def _lege_trip_datei(tmp_path, user_id: str, daten: dict):
    briefings = tmp_path / "users" / user_id / "briefings"
    briefings.mkdir(parents=True, exist_ok=True)
    pfad = briefings / f"{daten['id']}.json"
    pfad.write_text(json.dumps(daten), encoding="utf-8")
    return pfad


def _lade(tmp_path, user_id: str, trip_id: str):
    from app.loader import load_trip

    trip = load_trip(trip_id, data_dir=tmp_path, user_id=user_id)
    assert trip is not None, f"Vorbedingung: Trip {trip_id} muss ladbar sein"
    return trip


def _aktive_kanaele(eintrag) -> set[str]:
    """Die eingeschalteten Kanaele eines `alert_metric_channels`-Eintrags —
    bewusst tolerant gegenueber der Behaelterform (`{kanal: bool}` wie in S1
    persistiert, oder eine Liste), weil die AC die BEDEUTUNG festlegt, nicht
    die Schreibweise. `None` ⇒ leere Menge."""
    if eintrag is None:
        return set()
    if isinstance(eintrag, dict):
        return {k for k, v in eintrag.items() if v}
    return {str(k) for k in eintrag}


def _kanalbild(trip) -> dict[str, set[str]]:
    """`alert_metric_channels` des geladenen Trips als
    {metric_id: {eingeschaltete Kanaele}}."""
    feld = getattr(trip, "alert_metric_channels", None) or {}
    return {metrik: _aktive_kanaele(wert) for metrik, wert in feld.items()}


# ═══ AC-18 — eins-zu-viele ausrollen, Kollisionen unionieren ════════════════

def test_ac18_eins_zu_viele_wird_ausgerollt_und_kollisionen_unionieren(
    tmp_path, sauberer_nutzer,
):
    """AC-18 (ROT): die Abbildung `AlertMetric → Katalog-ID`
    (`weather_change_detection._ALERT_METRIC_TO_CATALOG_ID`) ist
    eins-zu-vielen.

    * `TEMPERATURE_MIN` bildet auf `("temperature_cold", "temperature")` ab —
      der Waehlbarkeits-Tie-Break (AC-14) laesst nur den WAEHLBAREN Eintrag
      `temperature` entstehen; `temperature_cold` traegt `selectable=False`
      (`metric_catalog.py:149`) und koennte im Editor (S3) nie angeboten
      werden.
    * `SNOW_LINE` bildet auf `("snowfall_limit", "freezing_level")` ab —
      BEIDE sind waehlbar, also entstehen BEIDE Eintraege (#961-OR-Politik).
    * Zwei aktivierte Regeln auf derselben `metric_id` (`PRECIPITATION_SUM`
      und `PRECIPITATION_CHANGE` fallen beide auf `precipitation`) werden
      UNIONIERT — eine Union kann nicht unterdruecken.
    """
    user_id = sauberer_nutzer("ac18")
    trip_id = "trip-ac18"
    _lege_trip_datei(tmp_path, user_id, _trip_json(trip_id, regeln=[
        _regel("r1", "temperature_min", ["telegram"]),
        _regel("r2", "snow_line", ["sms"]),
        _regel("r3", "precipitation_sum", ["email"]),
        _regel("r4", "precipitation_change", ["telegram"]),
    ]))

    bild = _kanalbild(_lade(tmp_path, user_id, trip_id))

    assert bild.get("temperature") == {"telegram"}, (
        "AC-18: TEMPERATURE_MIN migriert auf die WAEHLBARE Katalog-Groesse "
        f"`temperature`, gemessen: {bild!r}"
    )
    assert "temperature_cold" not in bild, (
        "AC-18/AC-14: `temperature_cold` ist nicht waehlbar und darf durch "
        f"den Tie-Break keinen Eintrag bekommen, gemessen: {bild!r}"
    )
    assert bild.get("snowfall_limit") == {"sms"}, (
        f"AC-18: SNOW_LINE rollt auf BEIDE Katalog-IDs aus, gemessen: {bild!r}"
    )
    assert bild.get("freezing_level") == {"sms"}, (
        f"AC-18: SNOW_LINE rollt auf BEIDE Katalog-IDs aus, gemessen: {bild!r}"
    )
    assert bild.get("precipitation") == {"email", "telegram"}, (
        "AC-18: zwei Regeln auf derselben metric_id ergeben die UNION ihrer "
        f"Kanaele, gemessen: {bild!r}"
    )


# ═══ AC-19 — leere Regel-Kanalliste erzeugt KEINEN Schluessel ═══════════════

def test_ac19_leere_regel_kanalliste_erzeugt_keinen_schluessel(
    tmp_path, sauberer_nutzer,
):
    """AC-19 (ROT): eine leere Regel-Kanalliste bedeutet "erbt". Die
    Migration darf dafuer KEINEN Schluessel anlegen — insbesondere kein `{}`.

    Ein leeres Dict wuerde laut `alert_channels.py:49-50` als vollstaendiges
    Override INS LEERE gelesen; aus "erbt alles" wuerde "erbt nichts". Der
    Test prueft deshalb beides getrennt: der Schluessel fehlt, und er ist
    auch nicht als leerer Eintrag vorhanden.
    """
    user_id = sauberer_nutzer("ac19")
    trip_id = "trip-ac19"
    _lege_trip_datei(tmp_path, user_id, _trip_json(trip_id, regeln=[
        _regel("r-leer", "wind_gust", []),
        _regel("r-voll", "precipitation_sum", ["email"]),
    ]))

    trip = _lade(tmp_path, user_id, trip_id)
    feld = getattr(trip, "alert_metric_channels", None) or {}

    assert "gust" not in feld, (
        "AC-19: die Regel mit leerer Kanalliste erbt — sie darf keinen "
        f"Schluessel `gust` erzeugen (auch kein {{}}), gemessen: {feld!r}"
    )
    assert _aktive_kanaele(feld.get("precipitation")) == {"email"}, (
        "AC-19, Gegenprobe (die HEUTE rote Haelfte): die Regel MIT Kanaelen "
        "muss sehr wohl migrieren. Ohne diese Haelfte waere der Test heute "
        "gruen und wuerde nur die Nicht-Aenderung feiern — er kann dann "
        "nicht zwischen `richtig weggelassen` und `gar keine Migration` "
        f"unterscheiden. Gemessen: {feld!r}"
    )


# ═══ AC-20 — deaktivierte Regeln migrieren nicht ════════════════════════════

def test_ac20_deaktivierte_regel_wandert_nicht_in_das_neue_feld(
    tmp_path, sauberer_nutzer,
):
    """AC-20 (ROT): eine deaktivierte Regel (`enabled=false`) ist heute
    wirkungslos (`alert_channels.py:89` filtert auf `r.enabled`). Wanderten
    ihre Kanaele mit, wuerde eine abgeschaltete Einschraenkung durch die
    Migration AKTIV — eine stille Verengung ohne Nutzerhandlung.
    """
    user_id = sauberer_nutzer("ac20")
    trip_id = "trip-ac20"
    _lege_trip_datei(tmp_path, user_id, _trip_json(trip_id, regeln=[
        _regel("r-aus", "wind_gust", ["sms"], enabled=False),
        _regel("r-an", "precipitation_sum", ["email"]),
    ]))

    bild = _kanalbild(_lade(tmp_path, user_id, trip_id))

    assert "gust" not in bild, (
        "AC-20: die Kanaele der DEAKTIVIERTEN Regel duerfen nicht migrieren, "
        f"gemessen: {bild!r}"
    )
    assert bild.get("precipitation") == {"email"}, (
        "AC-20, Gegenprobe (die HEUTE rote Haelfte): die AKTIVIERTE Regel "
        "muss migrieren. Ohne sie waere der Test heute gruen und unterschiede "
        f"nicht zwischen `korrekt gefiltert` und `keine Migration`. "
        f"Gemessen: {bild!r}"
    )


# ═══ AC-21 — ohne migrierbare Kanaele bleibt das Feld ungesetzt ═════════════

def test_ac21_ohne_migrierbare_regelkanaele_bleibt_das_feld_ungesetzt(
    tmp_path, sauberer_nutzer,
):
    """AC-21 (ROT): ein Trip ohne aktive, aktivierte Regel MIT Kanaelen
    bekommt kein Feld — kein leeres Objekt. Geprueft an der tatsaechlich
    geschriebenen Persistenz (`save_trip`), nicht am Quelltext: das ist das
    Python-Pendant zu `omitempty` auf der Go-Seite (AC-7).
    """
    from app.loader import save_trip

    user_id = sauberer_nutzer("ac21")
    ohne_id, mit_id = "trip-ac21-ohne", "trip-ac21-mit"
    _lege_trip_datei(tmp_path, user_id, _trip_json(ohne_id, regeln=[
        _regel("r-leer", "wind_gust", []),
        _regel("r-aus", "precipitation_sum", ["email"], enabled=False),
    ]))
    _lege_trip_datei(tmp_path, user_id, _trip_json(mit_id, regeln=[
        _regel("r-an", "wind_gust", ["telegram"]),
    ]))

    ohne = _lade(tmp_path, user_id, ohne_id)
    assert getattr(ohne, "alert_metric_channels", None) in (None, {}), (
        "AC-21: ohne migrierbare Regel-Kanaele darf kein Eintrag entstehen, "
        f"gemessen: {getattr(ohne, 'alert_metric_channels', None)!r}"
    )
    pfad_ohne = save_trip(ohne, user_id=user_id, data_dir=tmp_path)
    geschrieben_ohne = json.loads(pfad_ohne.read_text(encoding="utf-8"))
    assert "alert_metric_channels" not in geschrieben_ohne, (
        "AC-21: die geschriebene Trip-Datei darf den Schluessel gar nicht "
        f"tragen (kein leeres Objekt), gemessen: "
        f"{geschrieben_ohne.get('alert_metric_channels')!r}"
    )

    # Gegenprobe — die HEUTE rote Haelfte. Ohne sie waere diese AC vakuum-
    # gruen: "kein Schluessel" gilt heute schon, weil es ueberhaupt keine
    # Migration gibt. Erst der zweite Trip belegt, dass die Abwesenheit oben
    # eine ENTSCHEIDUNG ist und nicht das Fehlen der Funktion.
    mit = _lade(tmp_path, user_id, mit_id)
    pfad_mit = save_trip(mit, user_id=user_id, data_dir=tmp_path)
    geschrieben_mit = json.loads(pfad_mit.read_text(encoding="utf-8"))
    assert _aktive_kanaele(
        (geschrieben_mit.get("alert_metric_channels") or {}).get("gust")
    ) == {"telegram"}, (
        "AC-21, Gegenprobe: ein Trip MIT migrierbaren Regel-Kanaelen muss den "
        f"Schluessel sehr wohl tragen. Gemessen: {geschrieben_mit.get('alert_metric_channels')!r}"
    )


# ═══ AC-22 — Read-Modify-Write mit Merge, nie Replace ═══════════════════════

def test_ac22_migration_erhaelt_bestehende_eintraege_und_felder(
    tmp_path, sauberer_nutzer,
):
    """AC-22 (ROT): die Migration ergaenzt per Read-Modify-Write und ersetzt
    nie (BUG-DATALOSS-GR221, #102).

    Vorbefuellt: ein bestehender `alert_metric_channels`-Eintrag fuer eine
    ANDERE Metrik (`wind`), dazu weitere Bestandsfelder
    (`alert_channels`, `alert_channel_thresholds`, ein unmodellierter
    Top-Level-Key). Nach dem Laden UND nach dem Zurueckschreiben muessen der
    Alt-Eintrag, der neue Eintrag und alle uebrigen Felder vollstaendig da
    sein.

    Nachweis-Aufteilung (vgl. Mapping): die Go-Handler-Haelfte dieser AC
    traegt der vorbestehende, gruene Nachweis
    `internal/handler/trip_alert_metric_channels_test.go::
    TestTripAlertMetricChannels_RoundtripIsolatedPerUser` bzw.
    `::TestTripAlertMetricChannels_SingleMetricPutPreservesOtherMetrics` —
    der Go-Pfad fuehrt die Migration nicht aus, er reicht das Feld nur
    gemergt durch. Diese Datei deckt die Python-Haelfte ab.
    """
    from app.loader import save_trip

    user_id = sauberer_nutzer("ac22")
    trip_id = "trip-ac22"
    _lege_trip_datei(tmp_path, user_id, _trip_json(
        trip_id,
        regeln=[_regel("r1", "wind_gust", ["telegram"])],
        alert_metric_channels={"wind": {"sms": True}},
        alert_channels={"email": True, "telegram": True},
        alert_channel_thresholds={"telegram": "HIGH"},
        unbekanntes_bestandsfeld={"beliebig": 42},
    ))

    trip = _lade(tmp_path, user_id, trip_id)
    bild = _kanalbild(trip)

    assert bild.get("wind") == {"sms"}, (
        "AC-22: der bereits vorhandene Eintrag einer ANDEREN Metrik muss "
        f"unangetastet bleiben, gemessen: {bild!r}"
    )
    assert bild.get("gust") == {"telegram"}, (
        f"AC-22: der migrierte Eintrag muss dazukommen, gemessen: {bild!r}"
    )

    pfad = save_trip(trip, user_id=user_id, data_dir=tmp_path)
    geschrieben = json.loads(pfad.read_text(encoding="utf-8"))
    nach_roundtrip = {
        metrik: _aktive_kanaele(wert)
        for metrik, wert in (geschrieben.get("alert_metric_channels") or {}).items()
    }
    assert nach_roundtrip.get("wind") == {"sms"}, (
        f"AC-22: Roundtrip verliert den Alt-Eintrag, gemessen: {geschrieben!r}"
    )
    assert nach_roundtrip.get("gust") == {"telegram"}, (
        f"AC-22: Roundtrip verliert den neuen Eintrag, gemessen: {geschrieben!r}"
    )
    assert geschrieben.get("alert_channels") == {"email": True, "telegram": True}, (
        f"AC-22: Bestandsfeld `alert_channels` verloren, {geschrieben!r}"
    )
    assert geschrieben.get("alert_channel_thresholds") == {"telegram": "HIGH"}, (
        f"AC-22: Bestandsfeld `alert_channel_thresholds` verloren, {geschrieben!r}"
    )
    assert geschrieben.get("unbekanntes_bestandsfeld") == {"beliebig": 42}, (
        f"AC-22: unmodelliertes Bestandsfeld verloren (#991), {geschrieben!r}"
    )


# ═══ AC-23 — die bewusst freigegebene Bestandsdaten-Verengung ══════════════

def test_ac23_alarm_ueber_metrik_x_erreicht_nach_migration_nur_noch_telegram(
    tmp_path, sauberer_nutzer,
):
    """AC-23 (ROT) — 🔴 Bestandsdaten-Verengung, PO-freigegeben.

    Bestands-Trip mit Regel A (`wind_gust` → `telegram`) und Regel B
    (`precipitation_sum` → `email`). HEUTE erreicht ein Alarm, der
    ausschliesslich `gust` ausloest, `telegram ∪ email` — die Union laeuft
    ueber ALLE aktiven Regeln, unabhaengig von der ausloesenden Metrik
    (`alert_channels.py:92`). NACH der Migration erreicht er nur noch
    `telegram`.

    Das ist die Reparatur des in #1895 gemeldeten Fehlers (die Kanalzuordnung
    hing an der falschen Entitaet), keine Regression.

    Gemessen an der echten Versandstelle `trip_alert.py:2509` — der geladene
    Bestands-Trip geht unveraendert in `_send_alert`, aufgezeichnet wird der
    Kanalsatz, der an `send_deviation_alert` uebergeben wird.
    """
    from services.trip_alert import TripAlertService
    from tests.helpers.alert_log_fixtures import weather
    from tests.tdd.test_alert_metric_channel_reader import (
        _TripVersandRekorder, _aenderung, _schreibe_tarif, _settings_ohne_netz,
    )

    user_id = sauberer_nutzer("ac23")
    _schreibe_tarif(user_id, "premium")
    trip_id = "trip-ac23"
    _lege_trip_datei(tmp_path, user_id, _trip_json(
        trip_id,
        regeln=[
            _regel("regel-a", "wind_gust", ["telegram"]),
            _regel("regel-b", "precipitation_sum", ["email"]),
        ],
        report_config={
            "trip_id": trip_id, "send_email": True, "send_telegram": True,
            "alert_on_changes": True,
        },
    ))

    trip = _lade(tmp_path, user_id, trip_id)
    trip.alert_channel_thresholds = None

    svc = TripAlertService(
        settings=_settings_ohne_netz(), user_id=user_id, throttle_hours=0,
        mail_sink=lambda subject, body: None,
    )
    rekorder = _TripVersandRekorder()
    svc._notification_service = rekorder
    svc._send_alert(trip, [weather(1)], [_aenderung("gust_max_kmh")])

    assert rekorder.abweichung == [{"telegram"}], (
        "AC-23: nach der Migration erreicht ein Alarm ausschliesslich ueber "
        "Metrik X exakt {'telegram'} — NICHT mehr {'telegram','email'} aus "
        "der regeluebergreifenden Union. Gemessen an trip_alert.py:2509: "
        f"{rekorder.abweichung!r}"
    )


# ═══ AC-24 (Migrations-Haelfte) — je Nutzer nur die eigenen Daten ═══════════

def test_ac24_migration_haelt_zwei_nutzer_auseinander(tmp_path, sauberer_nutzer):
    """AC-24 (ROT), Migrations-Haelfte: zwei Nutzer, je eigener Trip mit
    UNTERSCHIEDLICHEN Regeln und unterschiedlichen Bestandseintraegen. Die
    Migration fuer A darf ausschliesslich As Daten sehen und schreiben — kein
    `"default"`, keine Vermischung.

    Die Leser-Haelfte derselben AC steht in
    `tests/tdd/test_alert_metric_channel_reader.py`; zusaetzlich bewacht der
    AST-Waechter `tests/test_user_id_default_guard.py` (ADR-0003).
    """
    user_a = sauberer_nutzer("ac24-a")
    user_b = sauberer_nutzer("ac24-b")
    assert user_a != "default" and user_b != "default" and user_a != user_b

    _lege_trip_datei(tmp_path, user_a, _trip_json(
        "trip-ac24-a",
        regeln=[_regel("r-a", "wind_gust", ["telegram"])],
        alert_metric_channels={"wind": {"telegram": True}},
    ))
    _lege_trip_datei(tmp_path, user_b, _trip_json(
        "trip-ac24-b",
        regeln=[_regel("r-b", "precipitation_sum", ["email"])],
        alert_metric_channels={"visibility": {"email": True}},
    ))

    bild_a = _kanalbild(_lade(tmp_path, user_a, "trip-ac24-a"))
    bild_b = _kanalbild(_lade(tmp_path, user_b, "trip-ac24-b"))

    assert bild_a == {"wind": {"telegram"}, "gust": {"telegram"}}, (
        f"AC-24: Nutzer A traegt ausschliesslich eigene Eintraege, {bild_a!r}"
    )
    assert bild_b == {"visibility": {"email"}, "precipitation": {"email"}}, (
        f"AC-24: Nutzer B traegt ausschliesslich eigene Eintraege, {bild_b!r}"
    )
