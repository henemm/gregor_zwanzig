"""TDD RED — Issue #1895 Scheibe S2: der LESER von `alert_metric_channels`
im Alarm-Pfad (Trip und Ortsvergleich).

SPEC: docs/specs/modules/alert_metric_channels.md — Abschnitt
      "Implementation Details (S2)", AC-10 bis AC-17, AC-24.
KONTEXT: docs/context/feat-1895-s2-kanal-leser.md
MAPPING: docs/artifacts/feat-1895-s2-kanal-leser/ac-test-mapping.md

────────────────────────────────────────────────────────────────────────────
WO gemessen wird (bindend aus Spec + Analyse, NICHT verhandelbar)
────────────────────────────────────────────────────────────────────────────
* AC-10 wird an `src/services/trip_alert.py:2509` (`_send_alert`) gemessen —
  ausdruecklich NICHT an `:552`. Bei `:552` wird `eval_result.channels`
  nirgends weiterverwendet und erscheint nur im Protokoll (`:730`); der
  Versand loest bei `:2509` unabhaengig NEU auf. Ein bei `:552` gruener Test
  beweist ueber den tatsaechlichen Versand nichts.
* AC-11 und AC-16 werden an `src/services/compare_alert.py:335`
  (`send_multi_location_deviation_alert`) gemessen — NICHT an `:601`
  (`_build_eval_config`), wo die ausloesenden Metriken noch gar nicht bekannt
  sind und das Ergebnis nur der preset-weite Startwert ist.

Kern-Tests gegen `resolve_alert_channels`/`effective_alert_channels` stehen
ZUSAETZLICH daneben; sie ersetzen die Versandstellen-Messung nie.

────────────────────────────────────────────────────────────────────────────
Warum die aufzeichnenden Doppelgaenger KEIN Mock-Theater sind
────────────────────────────────────────────────────────────────────────────
Kein `Mock()`, kein `patch()`, kein `MagicMock` — und vor allem KEIN Patch
auf den Aufloeser selbst (der spiegelte nur die eigene Annahme zurueck).
Aufgezeichnet wird an der TRANSPORT-Grenze: `_TripVersandRekorder` bzw.
`_VergleichVersandRekorder` halten genau den Kanalsatz fest, den der
PRODUKTIVCODE berechnet und an die Versandfunktion uebergibt, und geben ein
echtes `NotificationResult` zurueck. Gemessen wird also die Groesse, um die
es fachlich geht, an der Stelle, an der sie wirkt. Kein Netz: die Transporte
werden gar nicht erst betreten (`--disable-socket`-tauglich, keine lokalen
HTTP-Stubs, keine echten Versaende — #1477).

Pfadregel #1409: alle Nutzer-/Datenpfade laufen ueber
`app.loader.get_data_dir()` bzw. `get_data_root()` (die pytest-isolierte
Wurzel, #1133) — nie ueber einen festen Hauptrepo-Pfad. Der Pruefling wird in
JEDER Testfunktion lokal importiert, damit ein fehlendes Symbol als EINZELNER
roter Fall sichtbar wird statt als Kollektionsfehler.

────────────────────────────────────────────────────────────────────────────
RED-Gruende (zwei Klassen, in dieser Datei beide vertreten)
────────────────────────────────────────────────────────────────────────────
(a) `TypeError: ... unexpected keyword argument 'metrics'` /
    `'metric_channel_sets'` — die metrik-bewusste Eingabe existiert noch
    nicht (`src/services/alert_channels.py:28/113`).
(b) `AssertionError` an der Versandstelle — der Versand loest heute
    preset-weit auf, `alert_metric_channels` hat keinen Leser.
"""
from __future__ import annotations

import json
import shutil
import uuid
from datetime import datetime, timedelta, timezone

import pytest


# ═══════════════════════════ Fixtures & Helfer ══════════════════════════════

def _uid(prefix: str) -> str:
    return f"tdd-1895-s2-{prefix}-{uuid.uuid4().hex[:8]}"


@pytest.fixture()
def sauberer_nutzer():
    """Registriert echte `data/users/<user_id>`-Verzeichnisse (isolierte
    Wurzel, #1133) und raeumt sie zuverlaessig wieder ab — Vorbild
    `test_alert_channel_resolution_parity.py::clean_user_dir`."""
    from app.loader import get_data_dir, get_data_root

    angelegt: list[str] = []

    def _registriere(prefix: str) -> str:
        user_id = _uid(prefix)
        angelegt.append(user_id)
        for pfad in (get_data_dir(user_id), get_data_root() / "users" / user_id):
            if pfad.exists():
                shutil.rmtree(pfad, ignore_errors=True)
        return user_id

    yield _registriere

    for user_id in angelegt:
        for pfad in (get_data_dir(user_id), get_data_root() / "users" / user_id):
            if pfad.exists():
                shutil.rmtree(pfad, ignore_errors=True)


def _schreibe_tarif(user_id: str, tarif: str) -> None:
    """Echtes `user.json` — `sms_allowed()`/`premium_sms_allowed()`
    (`services/user_tier.py`) lesen es aus dem `get_data_dir()`-Baum.
    `is_test_user` verhindert, dass `with_user_profile()` Prod-Zugangsdaten
    zieht (#2152)."""
    from app.loader import get_data_dir

    pfad = get_data_dir(user_id)
    pfad.mkdir(parents=True, exist_ok=True)
    (pfad / "user.json").write_text(
        json.dumps({"id": user_id, "tier": tarif, "is_test_user": True})
    )


def _settings_ohne_netz():
    """JEDES versandrelevante Feld ausdruecklich gesetzt (#1477) — ohne das
    faellt `Settings()` still auf die Prod-`.env` des Worktrees zurueck.
    Angesteuert wird hier ohnehin kein Transport: die Versandobjekte sind
    durch aufzeichnende Doppelgaenger ersetzt."""
    from app.config import Settings

    return Settings(
        smtp_host="dummy.invalid", smtp_user="dummy", smtp_pass="dummy",
        mail_to="dummy@example.invalid",
        telegram_bot_token="tdd-stub-token", telegram_chat_id="99999",
        sms_gateway_url="http://127.0.0.1:1/api/sms",
        seven_api_key="tdd-stub-key", sms_to="+49000000000", sms_from=None,
    )


def _ergebnis(kanaele):
    from services.notification_service import NotificationResult

    kanaele = sorted(kanaele)
    return NotificationResult(sent=bool(kanaele), sent_channels=list(kanaele))


class _TripVersandRekorder:
    """Aufzeichnender Doppelgaenger des `NotificationService` am Trip-
    Transport. Haelt fest, welchen Kanalsatz der Produktivcode an die drei
    Versandfunktionen uebergibt — der Wert wird NICHT vorgegeben, sondern
    beobachtet."""

    def __init__(self) -> None:
        self.abweichung: list[set[str]] = []
        self.radar: list[set[str]] = []
        self.amtlich: list[set[str]] = []

    def send_deviation_alert(self, **kw):
        self.abweichung.append(set(kw["effective_channels"]))
        return _ergebnis(kw["effective_channels"])

    def send_radar_alert(self, **kw):
        self.radar.append(set(kw["effective_channels"]))
        return _ergebnis(kw["effective_channels"])

    def send_official_alert(self, **kw):
        self.amtlich.append(set(kw["effective_channels"]))
        return _ergebnis(kw["effective_channels"])


class _VergleichVersandRekorder:
    """Pendant fuer die drei Ortsvergleich-Versandwege. Haelt je Aufruf den
    Kanalsatz UND die beteiligten Ortsnamen fest — AC-16 braucht beides."""

    def __init__(self) -> None:
        self.abweichung: list[tuple[set[str], list[str]]] = []
        self.metriken_je_ort: dict[str, set[str]] = {}
        self.radar: list[set[str]] = []
        self.amtlich: list[set[str]] = []

    def send_multi_location_deviation_alert(self, **kw):
        kanaele = set(kw["effective_channels"])
        eintraege = kw.get("entities") or []
        orte = [e[0] for e in eintraege]
        # Fuer die VORBEDINGUNGS-Pruefung in AC-16: welcher Ort hat ueber
        # welchen rohen Summary-Key ausgeloest (`WeatherChange.metric`).
        for name, _punkte, aenderungen in eintraege:
            self.metriken_je_ort.setdefault(name, set()).update(
                c.metric for c in aenderungen
            )
        self.abweichung.append((kanaele, orte))
        return _ergebnis(kanaele)

    def send_multi_location_radar_alert(self, **kw):
        self.radar.append(set(kw["effective_channels"]))
        return _ergebnis(kw["effective_channels"])

    def send_multi_location_official_alert(self, *args, **kw):
        # Signatur ist hier POSITIONAL (`compare_official_alert.py:282-288`):
        # (name, locs, tagged_alerts, allowed, telegram_style, ...).
        kanaele = set(args[3]) if len(args) > 3 else set(kw["effective_channels"])
        self.amtlich.append(kanaele)
        return _ergebnis(kanaele)


# ───────────────────────────── Trip-Bausteine ───────────────────────────────

def _trip(trip_id: str, *, eintrag=None, geerbt=("email", "telegram")):
    """Trip mit scharfer Boeen-Regel (geteilter Baustein
    `tests/helpers/alert_log_fixtures.gust_alert_trip`), gesetztem
    Briefing-Kanalsatz (= geerbter Anteil) und optionalem
    `alert_metric_channels`-Eintrag. KEINE `alert_rules` — diese Datei misst
    den EINTRAGS-Arm gegen den GEERBTEN Arm; der mittlere (Regel-)Arm ist
    Sache der Migrations-Datei (AC-23)."""
    from app.models import TripReportConfig
    from tests.helpers.alert_log_fixtures import gust_alert_trip
    from tests.helpers.briefing_zeiten import briefing_zeiten_fuer_trip

    trip = gust_alert_trip(trip_id)
    morgen, abend = briefing_zeiten_fuer_trip(trip)
    trip.report_config = TripReportConfig(
        trip_id=trip_id,
        send_email="email" in geerbt,
        send_telegram="telegram" in geerbt,
        send_sms="sms" in geerbt,
        alert_on_changes=True, morning_time=morgen, evening_time=abend,
    )
    trip.alert_cooldown_minutes = 0
    trip.official_alert_triggers_enabled = False
    # Ausdruecklich KEINE Kanal-Schwelle: sonst filterte `split_by_threshold`
    # zwischen Aufloesung und Rekorder und der Test maesse die falsche Groesse.
    trip.alert_channel_thresholds = None
    trip.alert_metric_channels = eintrag
    return trip


def _aenderung(summary_key: str):
    """Echte `WeatherChange` mit dem ROHEN Summary-Key — das ist das
    Vokabular, das `_send_alert` in der Hand haelt (`app/models.py:602`)."""
    from app.models import ChangeSeverity, WeatherChange

    return WeatherChange(
        metric=summary_key, old_value=10.0, new_value=60.0, delta=50.0,
        threshold=20.0, severity=ChangeSeverity.MODERATE, direction="increase",
        segment_id="1",
    )


def _trip_versand(trip, user_id: str, aenderungen) -> _TripVersandRekorder:
    """Faehrt den ECHTEN Trip-Versandweg `_send_alert` (`trip_alert.py:2509`)
    und liefert den Rekorder zurueck."""
    from services.trip_alert import TripAlertService
    from tests.helpers.alert_log_fixtures import weather

    svc = TripAlertService(
        settings=_settings_ohne_netz(), user_id=user_id, throttle_hours=0,
        mail_sink=lambda subject, body: None,
    )
    rekorder = _TripVersandRekorder()
    svc._notification_service = rekorder
    svc._send_alert(trip, [weather(1)], list(aenderungen))
    return rekorder


# ═════════════════ AC-10 — Trip: dreiarmige Union je Metrik ═════════════════

def test_ac10_trip_versand_nutzt_eintrag_der_ausloesenden_metrik(sauberer_nutzer):
    """AC-10 (ROT, Klasse b): Trip mit Eintrag `{telegram}` fuer Metrik X
    (`gust`), KEIN Eintrag fuer Metrik Y (`precipitation`), geerbter Satz
    `{email, telegram}`.

    * Alarm ausschliesslich ueber X  ⇒ versandter Satz exakt `{telegram}`.
    * Alarm ueber X UND Y            ⇒ versandter Satz `{email, telegram}`
      (Y erbt und zieht die Union wieder hoch).

    Gemessen an `trip_alert.py:2509` (`_send_alert` → `send_deviation_alert`),
    ausdruecklich NICHT an `:552`.

    Der X-ONLY-Fall ist der rote: er liefert heute `{email, telegram}`, weil
    der Versand preset-weit aufloest. Der X+Y-Fall ist heute schon gruen und
    steht bewusst daneben — ohne ihn koennte eine Implementierung die Union
    kaputtsparen (Kanal-Verlust, #1701/ADR-0046), ohne dass ein Test es merkt.
    """
    user_id = sauberer_nutzer("ac10")
    _schreibe_tarif(user_id, "premium")
    trip = _trip("trip-ac10", eintrag={"gust": {"telegram": True}})

    nur_x = _trip_versand(trip, user_id, [_aenderung("gust_max_kmh")])
    x_und_y = _trip_versand(
        trip, user_id, [_aenderung("gust_max_kmh"), _aenderung("precip_sum_mm")]
    )

    assert nur_x.abweichung == [{"telegram"}], (
        "AC-10: ein Alarm ausschliesslich ueber die Metrik mit Eintrag "
        "{telegram} muss GENAU ueber telegram versendet werden. Gemessen an "
        f"trip_alert.py:2509: {nur_x.abweichung!r}"
    )
    assert x_und_y.abweichung == [{"email", "telegram"}], (
        "AC-10: kommt eine Metrik OHNE Eintrag dazu, erbt sie den abo-weiten "
        "Satz und die Union zieht wieder hoch — eine Verengung waere hier "
        f"Kanal-Verlust (#1701). Gemessen: {x_und_y.abweichung!r}"
    )


def test_ac10_kern_unioniert_je_metrik_mit_rueckfall_auf_geerbt(sauberer_nutzer):
    """AC-10, Kern-Schicht (ROT, Klasse a) — ZUSAETZLICH zur Versandstellen-
    Messung, nie als deren Ersatz.

    Der reine Kern bekommt die fuenfte Eingabe `metric_channel_sets`
    (Spec, Implementation Details S2 Punkt 1): dieselbe Schleife wie
    `alert_channels.py:56-60`, nur je METRIK statt je Regel — nicht-leerer
    Satz gewinnt fuer diese Metrik, leerer faellt auf `inherited` zurueck.

    ⚠️ Dieser EINE Test nagelt einen Implementierungs-NAMEN fest
    (`metric_channel_sets`). Der Name steht so in der freigegebenen Spec und
    ist damit bindend; waehlt `/50` trotzdem einen anderen, ist der Test
    anzupassen — NICHT die AC. Die bindende Messung der AC-10 liegt ohnehin
    an der Versandstelle (`test_ac10_trip_versand_...`) und ist namensfrei.
    """
    from services.alert_channels import resolve_alert_channels

    user_id = sauberer_nutzer("ac10-kern")
    _schreibe_tarif(user_id, "premium")

    nur_x = resolve_alert_channels(
        override=None, inherited={"email", "telegram"}, rule_channel_sets=[],
        user_id=user_id, metric_channel_sets={"gust": {"telegram"}},
    )
    x_und_y = resolve_alert_channels(
        override=None, inherited={"email", "telegram"}, rule_channel_sets=[],
        user_id=user_id,
        metric_channel_sets={"gust": {"telegram"}, "precipitation": set()},
    )

    assert nur_x == {"telegram"}, (
        f"AC-10 Kern: Eintrag der einzigen ausloesenden Metrik gewinnt, "
        f"gemessen: {nur_x!r}"
    )
    assert x_und_y == {"email", "telegram"}, (
        f"AC-10 Kern: die eintragslose Metrik faellt auf `inherited` zurueck, "
        f"die Union traegt beides, gemessen: {x_und_y!r}"
    )


# ══════════ AC-11 — Ortsvergleich: dieselbe Union, an der Versandstelle ═════

def _ort(loc_id: str, name: str, lat: float, lon: float):
    from app.user import SavedLocation

    return SavedLocation(id=loc_id, name=name, lat=lat, lon=lon, elevation_m=300)


def _punktwetter(point_id: str, name: str, lat: float, lon: float, **werte):
    from app.models import SegmentWeatherSummary
    from services.point_weather import PointWeatherData

    return PointWeatherData(
        id=point_id, name=name, lat=lat, lon=lon, timeseries=None,
        aggregated=SegmentWeatherSummary(**werte),
        fetched_at=datetime.now(timezone.utc), provider="tdd-1895-scripted",
    )


class _GeskripteteWetterquelle:
    """Deterministische `LocationWeatherSource` (kein Mock, kein Netz):
    liefert je Ort echte `PointWeatherData` mit vorab festgelegten
    Summary-Werten."""

    def __init__(self, werte_je_ort: dict[str, dict]) -> None:
        self._werte = dict(werte_je_ort)

    def fetch(self, point_id: str, lat: float, lon: float,
              start_hour=None, end_hour=None, **kw):
        return _punktwetter(
            point_id, point_id, lat, lon, **self._werte.get(point_id, {})
        )


_ORTE = {
    "loc-graz": ("Graz", 47.07, 15.44),
    "loc-wien": ("Wien", 48.21, 16.37),
}


def _lege_vergleich_an(user_id: str, preset_id: str, *, orte: list[str],
                       anker: dict[str, dict], **preset_extra) -> None:
    """Echter Ortsvergleich auf Platte: Orte, Preset-Datei (per-Datei
    `briefings/<id>.json`, #1250 S7b) und Δ-Anker je Ort."""
    from app.loader import get_data_root, save_location
    from services.compare_weather_snapshot import CompareWeatherSnapshotService
    from tests.helpers.compare_briefings import write_compare_briefings

    for loc_id in orte:
        name, lat, lon = _ORTE[loc_id]
        save_location(_ort(loc_id, name, lat, lon), user_id=user_id)

    preset: dict = {
        "id": preset_id, "name": preset_id, "user_id": user_id,
        "location_ids": list(orte), "schedule": "daily", "weekday": 4,
        "profil": "ALLGEMEIN", "hour_from": 9, "hour_to": 16,
        "empfaenger": [], "letzter_versand": None,
        "top_ort_letzter_versand": None, "created_at": "2026-09-22T00:00:00Z",
        "alert_cooldown_minutes": 0,
    }
    preset.update(preset_extra)
    write_compare_briefings(get_data_root() / "users" / user_id, [preset])

    snapshots = CompareWeatherSnapshotService(user_id=user_id)
    for loc_id in orte:
        name, lat, lon = _ORTE[loc_id]
        snapshots.save(
            preset_id, loc_id, _punktwetter(loc_id, name, lat, lon, **anker[loc_id])
        )


def _vergleich_versand(monkeypatch, user_id: str,
                       frisch: dict[str, dict]) -> _VergleichVersandRekorder:
    """Faehrt den ECHTEN Vergleichs-Aenderungsalarm
    (`CompareAlertService.check_all_compare_presets` →
    `compare_alert.py:335`) und liefert den Rekorder zurueck."""
    import services.compare_alert as compare_alert_modul
    from services.compare_alert import CompareAlertService

    rekorder = _VergleichVersandRekorder()
    monkeypatch.setattr(
        compare_alert_modul, "notification_service_for_preset",
        lambda *a, **kw: rekorder,
    )
    service = CompareAlertService(
        settings=_settings_ohne_netz(), user_id=user_id,
        weather_source=_GeskripteteWetterquelle(frisch),
        mail_sink=lambda subject, body: None,
    )
    service.check_all_compare_presets()
    return rekorder


def test_ac11_vergleich_versand_traegt_dieselbe_union_je_metrik(
    monkeypatch, sauberer_nutzer,
):
    """AC-11 (ROT, Klasse b): Preset mit `config.channels={email}` (kein
    `send_telegram`) und Metrik-Eintrag `{telegram}` fuer Metrik X
    (`precipitation`), KEIN Eintrag fuer Metrik Y (`gust`). EIN Ort loest
    ueber X UND Y aus ⇒ versandter Satz fuer diesen Ort ist
    `{email, telegram}`.

    Gemessen an `compare_alert.py:335`
    (`send_multi_location_deviation_alert`), NICHT an `:601` — dort ist nur
    der preset-weite Startwert bekannt, die ausloesenden Metriken nicht.

    Heute: der Versand traegt `{email}`; `alert_metric_channels` hat keinen
    Leser. Zusaetzlich bewacht dieser Fall die `ids_by_channel`-Vorbelegung
    (AC-17): `telegram` steht nicht in `config.channels`.
    """
    user_id = sauberer_nutzer("ac11")
    _schreibe_tarif(user_id, "premium")
    _lege_vergleich_an(
        user_id, "cp-ac11", orte=["loc-graz"],
        anker={"loc-graz": {"precip_sum_mm": 2.0, "gust_max_kmh": 10.0}},
        alert_metric_channels={"precipitation": {"telegram": True}},
    )

    rekorder = _vergleich_versand(
        monkeypatch, user_id,
        {"loc-graz": {"precip_sum_mm": 40.0, "gust_max_kmh": 95.0}},
    )

    assert len(rekorder.abweichung) == 1, (
        "Vorbedingung: der Ort muss genau EINEN Vergleichs-Alarm ausloesen, "
        f"aufgezeichnet: {rekorder.abweichung!r}"
    )
    kanaele, orte = rekorder.abweichung[0]
    assert orte == ["Graz"], f"Vorbedingung: Ort 'Graz' erwartet, {orte!r}"
    assert rekorder.metriken_je_ort.get("Graz") == {"precip_sum_mm", "gust_max_kmh"}, (
        "Vorbedingung AC-11: der Ort muss ueber BEIDE Metriken ausloesen "
        f"(X mit Eintrag, Y ohne), gemessen: {rekorder.metriken_je_ort!r}"
    )
    assert kanaele == {"email", "telegram"}, (
        "AC-11: Metrik X traegt den Eintrag {telegram}, Metrik Y erbt "
        "{email} — die Union je Metrik muss BEIDES versenden. Gemessen an "
        f"compare_alert.py:335: {kanaele!r}"
    )


# ═══════════ AC-12 — Leer-Rueckfall VOR den Tier-Gates ══════════════════════
# Der dritte Fall der AC ("explizit leeres `override` bleibt leer") ist
# vorbestehend bewacht in
# `tests/tdd/test_alert_channel_resolution_parity.py:166` und wird hier
# bewusst NICHT neu geschrieben.

def test_ac12_leerender_metrik_arm_faellt_auf_satz_ohne_metrik_arm_zurueck(
    sauberer_nutzer,
):
    """AC-12, Fall 1 (ROT, Klasse a): der Metrik-Arm allein darf eine
    nicht-leere Kanalmenge nicht auf leer bringen.

    Eintrag fuer `gust` vorhanden, aber mit ALLEN Kanaelen auf `False` — er
    loest sich zu `{}` auf. Ohne den Metrik-Arm waere das Ergebnis
    `{email, telegram}` (geerbt). Also gilt der Satz OHNE Metrik-Arm.

    Genau diese Unterscheidung ist die AC: "Eintrag vorhanden, loest sich
    leer auf" ist etwas anderes als "kein Eintrag" — sonst braeuchte es den
    Guard gar nicht.
    """
    from services.alert_channels import effective_alert_channels

    user_id = sauberer_nutzer("ac12-rueckfall")
    _schreibe_tarif(user_id, "premium")
    trip = _trip(
        "trip-ac12a",
        eintrag={"gust": {"email": False, "telegram": False,
                          "sms": False, "premium_sms": False}},
    )

    ergebnis = effective_alert_channels(
        trip, _settings_ohne_netz(), user_id, metrics=["gust_max_kmh"],
    )

    assert ergebnis == {"email", "telegram"}, (
        "AC-12: ein leerender Metrik-Arm darf den Alarm nicht verstummen "
        "lassen (ADR-0046: die Kanal-Ebene regelt den WEG, nie das OB). "
        f"Erwartet der Satz ohne Metrik-Arm {{'email','telegram'}}, gemessen: "
        f"{ergebnis!r}"
    )


def test_ac12_tier_gate_darf_nach_nicht_leerem_metrik_arm_auf_leer_fuehren(
    sauberer_nutzer,
):
    """AC-12, Fall 3 (ROT, Klasse a): der Rueckfall-Guard liegt VOR den
    Tier-Gates.

    Free-Tarif-Nutzer, Eintrag fuer `gust` = `{sms}` (nicht leer!). Der
    Metrik-Arm liefert `{sms}`, das Tier-Gate streicht `sms` — uebrig bleibt
    leer. Das MUSS leer bleiben: ein Rueckfall an dieser Stelle waere eine
    vom Tier-Gate ausgeloeste Kanal-ERWEITERUNG und verletzte AC-4 aus
    #2279 S1 ("Tier-Gates genau einmal").

    Der Tarif wird ausdruecklich als Datei geschrieben (`free`), damit die
    Vorbedingung ausgesprochen und nicht bloss zufaellig (fail-closed bei
    unbekanntem Nutzer) erfuellt ist.
    """
    from services.alert_channels import effective_alert_channels

    user_id = sauberer_nutzer("ac12-tier")
    _schreibe_tarif(user_id, "free")
    trip = _trip("trip-ac12c", eintrag={"gust": {"sms": True}})

    ergebnis = effective_alert_channels(
        trip, _settings_ohne_netz(), user_id, metrics=["gust_max_kmh"],
    )

    assert ergebnis == set(), (
        "AC-12: der Metrik-Arm war NICHT leer ({sms}) — erst das Tier-Gate "
        "hat geleert. Das ist Tarif-Politik, kein Fall fuer den Rueckfall-"
        f"Guard; die Menge muss leer bleiben. Gemessen: {ergebnis!r}"
    )


# ═══ AC-13 — metrikfreie Alarme: GRUEN, Fixture fuer die Mutations-Probe ════
#
# 🟢 DIESE VIER TESTS SIND HEUTE GRUEN UND BLEIBEN ES NACH `/50`.
#
# Sie sind die FIXTURE fuer die Mutations-Gegenprobe aus der Spec
# ("Mutations-Gegenprobe (S2)", erster Punkt): wird in `/50` ein
# Metrik-Argument an einer der acht metrikfreien Aufrufstellen ergaenzt
# (Radar `trip_alert.py:1671` / `compare_radar_alert.py:168`, amtlich
# `trip_alert.py:2726` / `compare_official_alert.py:472`), MUESSEN sie rot
# werden.
#
# Die zwei Vorbedingungen, ohne die die Mutation strukturell unbeobachtbar
# bliebe (Spec woertlich):
#   1. `alert_metric_channels` traegt einen Eintrag fuer eine Metrik, die im
#      Radar-/amtlichen Pfad strukturell NICHT vorkommt (`gust`).
#   2. Dieser Eintrag ist DISJUNKT zur abo-weiten Kanalmenge:
#      abo-weit `{email}`, Eintrag `{telegram}`. Waere er deckungsgleich,
#      bliebe die Mutation gruen und die Fixture waere wertlos.

_AC13_EINTRAG = {"gust": {"telegram": True}}
_AC13_ABO_WEIT = {"email"}


def test_ac13_trip_radar_alarm_bleibt_beim_abo_weiten_satz(sauberer_nutzer):
    """AC-13 (GRUEN, Mutations-Fixture) — Trip-Radar (`trip_alert.py:1671`,
    Versand `:2333`). Trotz abweichendem `gust`-Eintrag bleibt der versandte
    Satz exakt der abo-weite `{email}`."""
    from services.radar_service import NowcastResult, RadarNowcastService
    from services.trip_alert import TripAlertService

    user_id = sauberer_nutzer("ac13-trip-radar")
    _schreibe_tarif(user_id, "premium")

    class _GarantiertNass(RadarNowcastService):
        def __init__(self) -> None:
            super().__init__()
            self._fest = NowcastResult(
                onset_minutes=12, intensity_label="leichter Regen",
                source="radar", is_convective=False,
            )

        def get_nowcast(self, lat, lon, elevation_m=None,
                        priority="user_briefing", user_id=None):
            return self._fest

    trip = _radar_trip(f"trip-ac13-{uuid.uuid4().hex[:6]}")
    trip.alert_metric_channels = dict(_AC13_EINTRAG)
    _speichere_trip(trip, user_id)

    svc = TripAlertService(
        settings=_settings_ohne_netz(), user_id=user_id, throttle_hours=0,
        radar_service=_GarantiertNass(), mail_sink=lambda subject, body: None,
    )
    rekorder = _TripVersandRekorder()
    svc._notification_service = rekorder
    svc.check_radar_alerts()

    assert rekorder.radar, (
        "Vorbedingung: der Radar-Alarm muss ueberhaupt versendet werden — "
        "sonst bewacht diese Fixture nichts."
    )
    assert rekorder.radar == [_AC13_ABO_WEIT], (
        "AC-13: der Radar-Alarm ist strukturell metrikfrei und muss exakt den "
        f"abo-weiten Satz {_AC13_ABO_WEIT!r} verwenden. Gemessen: "
        f"{rekorder.radar!r}. Wird diese Zusicherung rot, hat jemand den "
        "Metrik-Parameter an einer metrikfreien Aufrufstelle ergaenzt."
    )


def test_ac13_trip_amtliche_warnung_bleibt_beim_abo_weiten_satz(sauberer_nutzer):
    """AC-13 (GRUEN, Mutations-Fixture) — amtliche Warnung des Trips
    (`trip_alert.py:2726`, Versand `:2796`)."""
    import services.official_alerts.base as official_base
    from services.official_alerts import register_official_alert_source
    from services.official_alerts.models import OfficialAlert
    from services.trip_alert import TripAlertService

    user_id = sauberer_nutzer("ac13-trip-amtlich")
    _schreibe_tarif(user_id, "premium")

    jetzt = datetime.now(timezone.utc)

    class _FesteQuelle:
        @property
        def name(self) -> str:
            return "tdd-1895-amtlich"

        def covers(self, lat, lon) -> bool:
            return True

        def fetch(self, lat, lon, **kw):
            return [OfficialAlert(
                source="tdd-1895", hazard="thunderstorm", level=4,
                label="AC-13-Warnung", valid_from=jetzt - timedelta(minutes=5),
                valid_to=jetzt + timedelta(minutes=45), region_label="AC13",
            )]

    trip = _trip("trip-ac13-amtlich", eintrag=dict(_AC13_EINTRAG),
                 geerbt=("email",))
    trip.official_alert_triggers_enabled = True
    # Vorbedingung: ohne Alarm-Anker findet `check_official_alert_triggers`
    # keine Segmente und meldet nichts (Muster
    # `test_alert_addendum_sms.py::test_ac_b12`).
    from tests.helpers.alert_log_fixtures import LAT as _GLAT, LON as _GLON, weather
    from tests.helpers.ortstag import ortstag
    from services.weather_snapshot import WeatherSnapshotService

    WeatherSnapshotService(user_id=user_id).save_dated(
        trip.id, ortstag(_GLAT, _GLON), [weather(1, precip_sum_mm=2.0)],
    )

    quellen = list(official_base._REGISTERED_SOURCES)
    official_base._REGISTERED_SOURCES.clear()
    try:
        register_official_alert_source(_FesteQuelle())
        svc = TripAlertService(
            settings=_settings_ohne_netz(), user_id=user_id, throttle_hours=0,
            mail_sink=lambda subject, body: None,
        )
        rekorder = _TripVersandRekorder()
        svc._notification_service = rekorder
        notices = svc.check_official_alert_triggers(trip)
        assert notices, (
            "Vorbedingung: die amtliche Warnung muss als neu erkannt werden."
        )
        svc._send_official_alert_only(trip, notices)
    finally:
        official_base._REGISTERED_SOURCES.clear()
        official_base._REGISTERED_SOURCES.extend(quellen)

    assert rekorder.amtlich == [_AC13_ABO_WEIT], (
        "AC-13: die amtliche Warnung kennt keine Katalog-Metrik (die "
        "Gefahrenart steht in `hazards`) und muss exakt den abo-weiten Satz "
        f"{_AC13_ABO_WEIT!r} verwenden. Gemessen: {rekorder.amtlich!r}"
    )


def test_ac13_vergleich_radar_alarm_bleibt_beim_abo_weiten_satz(
    monkeypatch, sauberer_nutzer,
):
    """AC-13 (GRUEN, Mutations-Fixture) — Vergleichs-Radar
    (`compare_radar_alert.py:168`, Versand `:342`)."""
    import services.compare_radar_alert as crm
    from providers.brightsky import RadarFrame
    from services.compare_radar_alert import CompareRadarAlertService
    from services.radar_service import RadarNowcastService

    user_id = sauberer_nutzer("ac13-vgl-radar")
    _schreibe_tarif(user_id, "premium")
    _lege_vergleich_an(
        user_id, "cp-ac13-radar", orte=["loc-graz"],
        anker={"loc-graz": {"precip_sum_mm": 2.0}},
        radar_alert_enabled=True,
        alert_metric_channels=dict(_AC13_EINTRAG),
    )

    nass = [RadarFrame(
        timestamp=datetime.now(timezone.utc) + timedelta(minutes=8),
        precip_mm_h=0.6,
    )]

    rekorder = _VergleichVersandRekorder()
    monkeypatch.setattr(
        crm, "notification_service_for_preset", lambda *a, **kw: rekorder,
    )
    svc = CompareRadarAlertService(
        settings=_settings_ohne_netz(), user_id=user_id,
        radar_service=RadarNowcastService(frame_source=lambda lat, lon: list(nass)),
        mail_sink=lambda subject, body: None,
    )
    svc.check_all_compare_presets()

    assert rekorder.radar, (
        "Vorbedingung: der Vergleichs-Radar-Alarm muss versendet werden."
    )
    assert rekorder.radar == [_AC13_ABO_WEIT], (
        "AC-13: der Vergleichs-Radar-Pfad ist ein metrikfreier Parallelpfad "
        f"und muss beim abo-weiten Satz {_AC13_ABO_WEIT!r} bleiben. "
        f"Gemessen: {rekorder.radar!r}"
    )


def test_ac13_vergleich_amtliche_warnung_bleibt_beim_abo_weiten_satz(
    monkeypatch, sauberer_nutzer,
):
    """AC-13 (GRUEN, Mutations-Fixture) — amtliche Warnung des Ortsvergleichs
    (`compare_official_alert.py:472`, Versand `:282`)."""
    import services.compare_official_alert as coa
    import services.official_alerts.base as official_base
    from services.compare_official_alert import CompareOfficialAlertService
    from services.official_alerts.models import OfficialAlert
    from services.official_alerts import register_official_alert_source

    user_id = sauberer_nutzer("ac13-vgl-amtlich")
    _schreibe_tarif(user_id, "premium")
    _lege_vergleich_an(
        user_id, "cp-ac13-amtlich", orte=["loc-graz"],
        anker={"loc-graz": {"precip_sum_mm": 2.0}},
        alert_metric_channels=dict(_AC13_EINTRAG),
    )

    jetzt = datetime.now(timezone.utc)
    name, lat, lon = _ORTE["loc-graz"]

    class _FesteQuelle:
        @property
        def name(self) -> str:
            return "tdd-1895-vgl-amtlich"

        def covers(self, p_lat, p_lon) -> bool:
            return abs(p_lat - lat) < 0.05 and abs(p_lon - lon) < 0.05

        def fetch(self, p_lat, p_lon, **kw):
            return [OfficialAlert(
                source="tdd-1895", hazard="extreme_heat", level=3,
                label="AC-13-Vergleichswarnung",
                valid_from=jetzt - timedelta(minutes=5),
                valid_to=jetzt + timedelta(hours=3), region_label=name,
            )]

    rekorder = _VergleichVersandRekorder()
    quellen = list(official_base._REGISTERED_SOURCES)
    official_base._REGISTERED_SOURCES.clear()
    try:
        register_official_alert_source(_FesteQuelle())
        monkeypatch.setattr(
            coa, "notification_service_for_preset", lambda *a, **kw: rekorder,
        )
        svc = CompareOfficialAlertService(
            settings=_settings_ohne_netz(), user_id=user_id,
            mail_sink=lambda subject, body: None,
            sms_sink=lambda text: None,
            telegram_sink=lambda text: None,
        )
        svc.check_all_compare_presets()
    finally:
        official_base._REGISTERED_SOURCES.clear()
        official_base._REGISTERED_SOURCES.extend(quellen)

    assert rekorder.amtlich, (
        "Vorbedingung: die amtliche Vergleichswarnung muss versendet werden."
    )
    assert rekorder.amtlich == [_AC13_ABO_WEIT], (
        "AC-13: auch der amtliche Vergleichspfad ist metrikfrei und muss beim "
        f"abo-weiten Satz {_AC13_ABO_WEIT!r} bleiben. Gemessen: "
        f"{rekorder.amtlich!r}"
    )


# ═══════ AC-15 — unaufloesbarer Summary-Key erbt, wirft nicht ═══════════════

def test_ac15_unaufloesbarer_summary_key_erbt_und_wirft_nicht(sauberer_nutzer):
    """AC-15 (ROT, Klasse a): ein Summary-Key, der sich keiner Katalog-
    `metric_id` zuordnen laesst, wird behandelt wie eine Metrik ohne Eintrag —
    er erbt den abo-weiten Satz. Weder `KeyError` noch `ValueError`.

    `_resolve_metric_id` (`output/renderers/alert/project.py:123`) WIRFT
    heute bei unbekanntem Feld — im Kanalpfad waere das ein Totalausfall des
    Alarms. Der Leser braucht die Fail-soft-Huelle (Spec, Implementation
    Details S2 Punkt 2).

    🔴 Abdeckungs-Grenze, ausdruecklich benannt: die AC nennt zwei Arme
    ("unbekannt ODER mehrdeutig ohne eindeutigen Waehlbarkeits-Tie-Break").
    Geprueft wird hier nur der UNBEKANNT-Arm. Der mehrdeutige Arm ist im
    heutigen Katalog strukturell nicht herstellbar — gemessen: jedes
    `summary_field` mit mehreren Kandidaten hat genau EINEN mit
    `selectable=True` (`metric_catalog.metric_and_aggregation_for_field`
    entscheidet damit immer eindeutig). Ein Test dafuer muesste den Katalog
    verfaelschen und pruefte dann nicht mehr den Bestand.
    """
    from services.alert_channels import effective_alert_channels

    user_id = sauberer_nutzer("ac15")
    _schreibe_tarif(user_id, "premium")
    trip = _trip("trip-ac15", eintrag={"gust": {"telegram": True}})

    for schluessel in ("voellig_unbekannter_key_xyz", ""):
        ergebnis = effective_alert_channels(
            trip, _settings_ohne_netz(), user_id, metrics=[schluessel],
        )
        assert ergebnis == {"email", "telegram"}, (
            f"AC-15: der unaufloesbare Schluessel {schluessel!r} muss den "
            f"abo-weiten Satz erben, gemessen: {ergebnis!r}"
        )


# ═══ AC-16 — zwei Orte, zwei verschiedene Kanalsaetze im selben Lauf ════════

def test_ac16_zwei_orte_erhalten_unterschiedliche_kanalsaetze(
    monkeypatch, sauberer_nutzer,
):
    """AC-16 (ROT, Klasse b): Ort 1 (Graz) loest NUR ueber `precipitation`
    aus (Eintrag `{telegram}`), Ort 2 (Wien) NUR ueber `gust` (Eintrag
    `{sms}`). Im selben Alarmlauf muss Graz ausschliesslich ueber `telegram`
    und Wien ausschliesslich ueber `sms` erreicht werden.

    Das ist nur moeglich, wenn die metrik-bewusste Aufloesung JE ORT in der
    Ortsschleife (`compare_alert.py:286-293`) geschieht — bei `:601`
    (`_build_eval_config`) sind die ausloesenden Metriken noch unbekannt.

    Der entscheidende Nachweis ist die NEGATIVE Zusicherung: kein einziger
    Versand-Aufruf darf beide Kanaele gemeinsam tragen. Ohne sie koennte eine
    preset-weite Aufloesung (Union ueber alle Orte) den Test bestehen.
    """
    user_id = sauberer_nutzer("ac16")
    _schreibe_tarif(user_id, "standard")  # standard ⇒ `sms` passiert das Gate
    _lege_vergleich_an(
        user_id, "cp-ac16", orte=["loc-graz", "loc-wien"],
        anker={
            "loc-graz": {"precip_sum_mm": 2.0, "gust_max_kmh": 10.0},
            "loc-wien": {"precip_sum_mm": 2.0, "gust_max_kmh": 10.0},
        },
        alert_metric_channels={
            "precipitation": {"telegram": True},
            "gust": {"sms": True},
        },
    )

    rekorder = _vergleich_versand(
        monkeypatch, user_id,
        {
            # Graz: nur Niederschlag steigt, Boeen bleiben gleich.
            "loc-graz": {"precip_sum_mm": 40.0, "gust_max_kmh": 10.0},
            # Wien: nur Boeen steigen, Niederschlag bleibt gleich.
            "loc-wien": {"precip_sum_mm": 2.0, "gust_max_kmh": 95.0},
        },
    )

    # Vorbedingung: jeder Ort loest GENAU ueber seine eine Metrik aus —
    # sonst misst der Test etwas anderes als die AC beschreibt.
    assert rekorder.metriken_je_ort.get("Graz") == {"precip_sum_mm"}, (
        "Vorbedingung AC-16: Graz muss ausschliesslich ueber Niederschlag "
        f"ausloesen, gemessen: {rekorder.metriken_je_ort!r}"
    )
    assert rekorder.metriken_je_ort.get("Wien") == {"gust_max_kmh"}, (
        "Vorbedingung AC-16: Wien muss ausschliesslich ueber Boeen ausloesen, "
        f"gemessen: {rekorder.metriken_je_ort!r}"
    )

    assert len(rekorder.abweichung) == 2, (
        "AC-16: zwei Orte mit verschiedenen Kanalsaetzen ergeben ZWEI "
        "getrennte Versand-Aufrufe (die Kanal-Buendelung fasst nur Kanaele "
        "mit IDENTISCHER Ortsliste zusammen, `compare_alert.py:296-302`). "
        f"Aufgezeichnet: {rekorder.abweichung!r}"
    )
    for kanaele, orte in rekorder.abweichung:
        assert len(orte) == 1, (
            "AC-16: jeder der beiden Aufrufe traegt GENAU EINEN Ort — ein "
            "Aufruf mit beiden Orten waere eine preset-weite Aufloesung. "
            f"Aufgezeichnet: {rekorder.abweichung!r}"
        )

    je_ort = {}
    for kanaele, orte in rekorder.abweichung:
        for ort in orte:
            je_ort.setdefault(ort, set()).update(kanaele)

    assert je_ort.get("Graz") == {"telegram"}, (
        "AC-16: Ort 1 loest nur ueber die Metrik mit Eintrag {telegram} aus "
        f"und darf nur telegram erreichen. Gemessen: {je_ort!r}"
    )
    assert je_ort.get("Wien") == {"sms"}, (
        "AC-16: Ort 2 loest nur ueber die Metrik mit Eintrag {sms} aus und "
        f"darf nur sms erreichen. Gemessen: {je_ort!r}"
    )
    for kanaele, orte in rekorder.abweichung:
        assert not {"telegram", "sms"} <= kanaele, (
            "AC-16: kein Versand-Aufruf darf die Vereinigung {telegram, sms} "
            "tragen — das waere eine preset-weite Aufloesung statt einer je "
            f"Ort. Aufgezeichnet: {rekorder.abweichung!r}"
        )


# ═══ AC-17 — hinzukommender Kanal sprengt `ids_by_channel` nicht ════════════

def test_ac17_hinzukommender_kanal_laesst_den_ortsalarm_nicht_ausfallen(
    monkeypatch, sauberer_nutzer,
):
    """AC-17 (ROT, Klasse b): `config.channels` ist `{email}`, der
    Metrik-Eintrag der ausloesenden Metrik bringt `telegram` NEU hinzu.

    POSITIV formuliert (bewusst KEIN `pytest.raises(KeyError)`): der Alarm
    fuer diesen Ort wird versendet UND der Kanalsatz enthaelt den
    hinzugekommenen Kanal. Ein `pytest.raises` waere heute gruen und nach dem
    Fix rot — also genau verkehrt herum.

    Der heutige Defekt liegt bei `compare_alert.py:293`: `ids_by_channel`
    wird nur aus `config.channels` vorbelegt; ein erst durch den Metrik-
    Eintrag hinzugekommener Kanal wirft dort `KeyError` und der GANZE
    Vergleichs-Alarm fuer den Ort faellt aus. Diese Zusicherung faellt in
    beiden Fehlerrichtungen: kein Leser ⇒ `telegram` fehlt; Leser ohne
    reparierte Vorbelegung ⇒ der `KeyError` reisst den Lauf mit.
    """
    user_id = sauberer_nutzer("ac17")
    _schreibe_tarif(user_id, "premium")
    _lege_vergleich_an(
        user_id, "cp-ac17", orte=["loc-graz"],
        anker={"loc-graz": {"precip_sum_mm": 2.0}},
        alert_metric_channels={"precipitation": {"telegram": True}},
    )

    rekorder = _vergleich_versand(
        monkeypatch, user_id, {"loc-graz": {"precip_sum_mm": 40.0}},
    )

    assert rekorder.abweichung, (
        "AC-17: der Vergleichs-Alarm fuer diesen Ort darf NICHT ausfallen — "
        "aufgezeichnet wurde kein einziger Versand-Aufruf."
    )
    kanaele = set().union(*(k for k, _orte in rekorder.abweichung))
    assert "telegram" in kanaele, (
        "AC-17: der erst durch den Metrik-Eintrag hinzugekommene Kanal "
        f"`telegram` muss im Versand ankommen. Gemessen: {kanaele!r}"
    )


# ═════ AC-24 — echte `user_id`, nie `"default"`, nie fremde Daten ═══════════

def test_ac24_aufloesung_traegt_je_nutzer_ausschliesslich_eigene_eintraege(
    sauberer_nutzer,
):
    """AC-24 (ROT, Klasse b): zwei verschiedene Nutzer mit unterschiedlichen
    `alert_metric_channels`-Eintraegen auf derselben Metrik. Die Aufloesung
    fuer A verwendet ausschliesslich As Eintrag, die fuer B ausschliesslich
    Bs — kein Rueckfall auf `"default"`, keine Vermischung.

    Gemessen an der Versandstelle `trip_alert.py:2509`, fuer jeden Nutzer mit
    einem EIGENEN `TripAlertService` (eigene `user_id`). Zusaetzlich bewacht
    vom AST-Waechter `tests/test_user_id_default_guard.py` (ADR-0003).
    """
    user_a = sauberer_nutzer("ac24-a")
    user_b = sauberer_nutzer("ac24-b")
    assert user_a != "default" and user_b != "default" and user_a != user_b
    _schreibe_tarif(user_a, "premium")
    _schreibe_tarif(user_b, "premium")

    trip_a = _trip("trip-ac24-a", eintrag={"gust": {"telegram": True}},
                   geerbt=("email", "telegram"))
    trip_b = _trip("trip-ac24-b", eintrag={"gust": {"email": True}},
                   geerbt=("email", "telegram"))

    rek_a = _trip_versand(trip_a, user_a, [_aenderung("gust_max_kmh")])
    rek_b = _trip_versand(trip_b, user_b, [_aenderung("gust_max_kmh")])

    assert rek_a.abweichung == [{"telegram"}], (
        f"AC-24: Nutzer A muss genau seinen eigenen Eintrag bekommen, "
        f"gemessen: {rek_a.abweichung!r}"
    )
    assert rek_b.abweichung == [{"email"}], (
        f"AC-24: Nutzer B muss genau seinen eigenen Eintrag bekommen, "
        f"gemessen: {rek_b.abweichung!r}"
    )


# ────────────────── Bausteine fuer den Trip-Radar-Pfad ──────────────────────

def _radar_trip(trip_id: str):
    """Trip mit garantiert JETZT aktivem Segment (Vorbild
    `test_issue_1069_tier_channel_gating.py::_make_radar_trip`) und
    abo-weitem Kanalsatz `{email}`."""
    from datetime import time as time_type

    from app.models import TripReportConfig
    from app.trip import Stage, TimeWindow, Trip, Waypoint
    from tests.helpers.ortstag import ortstag

    lat, lon = 42.20, 9.10
    start_str, end_str, start_time = _aktives_fenster_jetzt(lat, lon)
    wp0 = Waypoint(
        id="G1", name="Start", lat=lat, lon=lon, elevation_m=1000.0,
        time_window=TimeWindow(start=time_type(0, 0), end=time_type(23, 57)),
        arrival_override=start_str,
    )
    wp1 = Waypoint(
        id="G2", name="Ziel", lat=42.25, lon=9.15, elevation_m=1200.0,
        time_window=TimeWindow(start=time_type(23, 58), end=time_type(23, 59)),
        arrival_override=end_str,
    )
    stage = Stage(
        id="T1", name="Tag 1", date=ortstag(lat, lon), start_time=start_time,
        waypoints=[wp0, wp1],
    )
    trip = Trip(id=trip_id, name="AC13 Radar-Trip", stages=[stage])
    trip.report_config = TripReportConfig(
        trip_id=trip_id, send_email=True, send_sms=False, send_telegram=False,
    )
    trip.alert_cooldown_minutes = 0
    trip.alert_channel_thresholds = None
    return trip


def _aktives_fenster_jetzt(lat: float, lon: float):
    """(`HH:MM` Start, `HH:MM` Ende, `time` Etappenstart) fuer ein Segment,
    das JETZT in Ortszeit laeuft — Vorbild
    `test_issue_1069_tier_channel_gating.py::_active_window_now`."""
    from datetime import time as time_type

    from utils.timezone import tz_for_coords

    zone = tz_for_coords(lat, lon)
    jetzt = datetime.now(zone)
    start = jetzt - timedelta(hours=1)
    ende = jetzt + timedelta(hours=3)
    tages_start = jetzt.replace(hour=0, minute=1, second=0, microsecond=0)
    tages_ende = jetzt.replace(hour=23, minute=55, second=0, microsecond=0)
    if start < tages_start:
        start = tages_start
    if ende > tages_ende:
        ende = tages_ende
    if start > jetzt:
        start = jetzt
    if ende <= jetzt:
        ende = jetzt + timedelta(hours=1)
    return (
        start.strftime("%H:%M"), ende.strftime("%H:%M"),
        time_type(start.hour, start.minute),
    )


def _speichere_trip(trip, user_id: str) -> None:
    from app.loader import save_trip

    save_trip(trip, user_id=user_id)
