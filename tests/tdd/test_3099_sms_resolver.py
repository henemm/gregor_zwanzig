"""#3099 (Phase 3d von #3047, Epic #3058): SMS liest aus dem Kanal-Listen-Resolver.

SPEC: docs/specs/modules/feat_3099_sms_resolver.md (AC-2 bis AC-11)

Trip: Auswahl, Folge und Roh/Einfach der SMS kommen aus
``resolve_channel_lists(dc, "trip", report_type).sms`` (Adapter
``sms_rows_to_maps``), nicht mehr aus ``dc.get_metrics_for_channel("sms", ...)``.
Orte: liest bereits ``view.sms`` -- hier nur Nachweis-Faelle (Versand und Vorschau).
Amtliche Warnungen bleiben am Ende der SMS (ADR-0121 Nr. 6), Premium-SMS sendet
den SMS-Text (nur Limit 153).

Zusicherungen an der echten SMS-Ausgabe (``TripReportFormatter.format_email``
-> ``sms_text``; Premium-SMS und Orte ueber den echten Versandweg bis zur
Transport-Mitschrift bzw. ``ComparePreviewService``). Soll von Hand. Kein
``Mock()``/``patch()``.

ROT vor der Umstellung:
* ``test_adapter_*`` -- ``sms_rows_to_maps`` existiert in ``sms_trip`` nicht (ImportError).
* ``test_ac9_*`` -- der Trip-SMS-Pfad liest heute
  ``dc.get_metrics_for_channel("sms", ...)``; weicht diese Methode von der
  Resolver-Liste ab, folgt die SMS heute der Methode statt dem Resolver.
* ``test_ac11_waechter_kennt_fallliste_sms`` -- der Waechter registriert
  ``fallliste_sms.json`` und ``tests/tdd/test_3099_*.py`` noch nicht.

Die uebrigen Faelle (AC-2 bis AC-8, AC-10) sind Bestandsschutz der zugestellten
SMS (ADR-0095: Ergebnis unveraendert) und schon heute gruen; sie bewachen die Umstellung.
"""
from __future__ import annotations

import copy
import dataclasses
import json
import re
from datetime import datetime
from pathlib import Path

import pytest

from app.loader import load_trip
from app.models import MetricConfig, UnifiedWeatherDisplayConfig
from output.renderers.trip_report import TripReportFormatter
from tests.tdd._einstellung_auslieferung_fixtures import (
    STAGE_NAME, TZ, frisches_profil, golden_dict, night_weather, segment,
)

# Orte-Helfer der Runde-7-Kette (echter Versandweg, Transport-Mitschrift);
# ``mit`` ist dort eine Fixture und wird hier mitbenutzt.
# ruff: noqa: F811  (mit = geteilte Fixture als Testparameter)
from tests.tdd.test_3047_runde7_orte_kanaele import (  # noqa: F401  (Fixture)
    GRUND as ORTE_GRUND, KUERZEL as ORTE_KUERZEL, _sms_ort, _sprache, mit, preset, text,
    zwei_nutzer,
)

REPO_ROOT = Path(__file__).resolve().parents[2]

#: Grundauswahl (Folge = Katalogfolge der Golden-Fixture der Runde 7).
GRUNDAUSWAHL = ["gust", "temperature", "rain_probability", "wind", "wind_direction", "thunder",
                "cloud_total", "precipitation", "uv_index", "humidity"]

#: SMS-Kuerzel je Metrik (Token-Symbol ohne Doppelpunkt), von Hand (sms_format.md).
KUERZEL = {"gust": {"G"}, "temperature": {"N", "D"}, "rain_probability": {"PR"},
           "wind": {"W"}, "wind_direction": {"WD"}, "thunder": {"TH", "TH+"},
           "cloud_total": {"CT"}, "precipitation": {"R"}, "uv_index": {"UV"},
           "humidity": {"HU"}}

REPORT_TYPES = ("morning", "evening")


# ---------------------------------------------------------------------------
# Trip-Helfer
# ---------------------------------------------------------------------------

def _mc(mid: str, order: int, fmt: str | None = None, enabled: bool = True) -> dict:
    """Listeneintrag im Speicherformat des Editors (Roh = ``format_mode: raw``)."""
    d = {"metric_id": mid, "enabled": enabled, "bucket": "primary", "order": order,
         "use_friendly_format": fmt != "raw"}
    if fmt is not None:
        d["format_mode"] = fmt
    return d


def _ohne_angabe(mid: str, order: int) -> dict:
    """Eintrag ohne jede Format-Angabe (kein ``format_mode``, kein ``use_friendly_format``)."""
    return {"metric_id": mid, "enabled": True, "bucket": "primary", "order": order}


def _liste(ids: list[str]) -> list[dict]:
    return [_mc(m, i) for i, m in enumerate(ids)]


def _trip_dict(sms: list[dict] | None = None, *, grund: list[dict] | None = None,
               extra_layouts: dict | None = None) -> dict:
    """Trip-JSON: Grundauswahl + optional SMS-Kanal-Ebene (``None`` = nie gesetzt)."""
    d = golden_dict("golden_c")
    d["display_config"]["metrics"] = grund if grund is not None else _liste(GRUNDAUSWAHL)
    layouts = {} if sms is None else {"sms": sms}
    layouts.update(extra_layouts or {})
    d["display_config"]["channel_layouts"] = layouts
    d["display_config"]["outlook_metrics"] = []
    return d


def _trip(data: dict, uid: str | None = None):
    """Echter Loader (Persistenzformat -> Modell) fuer einen echten Nutzer."""
    trip = load_trip(copy.deepcopy(data), user_id=uid or frisches_profil())
    assert trip is not None
    return trip


def _warnung(level: int = 3):
    from services.official_alerts.models import OfficialAlert

    return OfficialAlert(source="meteoalarm", hazard="thunderstorm", level=level,
                         label="Gewitter", region_label="Tirol",
                         valid_from=datetime(2026, 7, 20, 10, 0, tzinfo=TZ),
                         valid_to=datetime(2026, 7, 20, 20, 0, tzinfo=TZ))


def _sms(trip_or_dc, report_type: str = "evening", *, warnung: int | None = None,
         lang: str = "de") -> str:
    """Echte Trip-SMS (``sms_text``). ``trip_or_dc``: Trip (mit Kanal-Schwelle)
    oder blosse Display-Config (fuer die Unterklasse aus AC-9)."""
    if isinstance(trip_or_dc, UnifiedWeatherDisplayConfig):
        trip, dc = None, trip_or_dc
    else:
        trip, dc = trip_or_dc, trip_or_dc.display_config
    seg = segment()
    if warnung is not None:
        seg.official_alerts = [_warnung(warnung)]
    return TripReportFormatter().format_email(
        [seg], trip_name="Issue3099", report_type=report_type,
        night_weather=night_weather(), display_config=dc, stage_name=STAGE_NAME,
        tz=TZ, trip=trip, lang=lang,
    ).sms_text


def _symbole(sms: str) -> list[str]:
    """Token-Symbole der SMS in Ausgabefolge (ohne Warnblock ``!..``)."""
    body = sms.split(": ", 1)[1]
    return [re.match(r"([A-Z]+\+?)", tok).group(1) for tok in body.split()
            if re.match(r"[A-Z]", tok)]


def _metrik_folge(sms: str) -> list[str]:
    """Metrik-IDs in Ausgabefolge (Mehrfach-Symbole einer Metrik zaehlen einmal)."""
    folge: list[str] = []
    for sym in _symbole(sms):
        mid = next((m for m, syms in KUERZEL.items() if sym in syms), None)
        if mid is not None and (not folge or folge[-1] != mid):
            folge.append(mid)
    return folge


# ---------------------------------------------------------------------------
# AC-2: Folge und Menge = SMS-Auswahl (Resolver-Liste), Morgen und Abend
# ---------------------------------------------------------------------------

#: SMS-Liste: andere Folge als die Grundauswahl, Teilmenge.
SMS_FOLGE = ["cloud_total", "precipitation", "gust", "wind", "temperature"]

SOLL_FOLGE = {
    "morning": "E1: CT:SCT@4 R2.0@4 G45@4 W- D15/15",
    "evening": "E1: CT:SCT@4 R2.0@4 G45@4 W- N15 D15/15",
}


@pytest.mark.parametrize("report_type", REPORT_TYPES)
def test_ac2_sms_folgt_sms_auswahl(report_type):
    """AC-2: SMS = genau die aktiven SMS-Metriken in der gewaehlten Folge
    (Soll von Hand); dieselbe Folge liefert der Resolver ``.sms``."""
    from services.channel_list_resolver import resolve_channel_lists

    trip = _trip(_trip_dict(_liste(SMS_FOLGE)))
    rows = resolve_channel_lists(trip.display_config, "trip", report_type).sms
    resolver_folge = [z.metric_id for z in rows if z.enabled and z.metric_id in KUERZEL]
    assert resolver_folge == SMS_FOLGE, "Vorbedingung: Resolver-Liste"
    sms = _sms(trip, report_type)
    assert sms == SOLL_FOLGE[report_type], sms
    assert _metrik_folge(sms) == resolver_folge, sms


SOLL_NIE = {
    "morning": "E1: G45@4 D15/15 PR60%@4 W- WD:W TH:M@4 TH+:- CT:SCT@4 R2.0@4 UV5@4 HU-",
    "evening": "E1: G45@4 N15 D15/15 PR60%@4 W- WD:W TH:M@4 TH+:- CT:SCT@4 R2.0@4 UV5@4 HU-",
}


@pytest.mark.parametrize("report_type", REPORT_TYPES)
def test_ac2_kanal_ebene_nie_gesetzt_folgt_grundauswahl(report_type):
    """AC-2: ohne SMS-Ebene folgt die SMS der Grundauswahl (Folge der Grundauswahl)."""
    sms = _sms(_trip(_trip_dict(None)), report_type)
    assert sms == SOLL_NIE[report_type], sms


@pytest.mark.parametrize("report_type", REPORT_TYPES)
def test_ac2_email_auswahl_leckt_nicht_in_sms_ohne_sms_ebene(report_type):
    """AC-2: E-Mail-Ebene weicht von der Grundauswahl ab (nur Wind, Boeen), SMS-Ebene
    nie gesetzt -> die SMS folgt der Grundauswahl, NICHT der E-Mail-Auswahl
    (der Trip-Pfad kollabiert die Display-Config auf die E-Mail-Auswahl; die SMS
    muss aus der unkollabierten Resolver-Sicht lesen)."""
    data = _trip_dict(None, extra_layouts={"email": _liste(["wind", "gust"])})
    sms = _sms(_trip(data), report_type)
    assert sms == SOLL_NIE[report_type], sms


@pytest.mark.parametrize("report_type", REPORT_TYPES)
def test_ac2_kanal_ebene_leer_keine_metrik(report_type):
    """AC-2: leere SMS-Ebene -> keine Metrik-Tokens (bewusste Leerauswahl bleibt leer)."""
    sms = _sms(_trip(_trip_dict([])), report_type)
    assert sms == "E1: ", sms


# ---------------------------------------------------------------------------
# AC-3: Roh / Einfach / ohne Angabe
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("fmt,soll", [("raw", "E1: CT70@4 G45@4"),
                                      ("symbol", "E1: CT:SCT@4 G45@4"),
                                      (None, "E1: CT:SCT@4 G45@4")],
                         ids=["roh", "einfach", "ohne_angabe"])
def test_ac3_bewoelkung_roh_einfach_ohne_angabe(fmt, soll):
    """AC-3: Bewoelkung Roh = Prozentzahl (CT70), Einfach = Stufe (CT:SCT); ohne
    Angabe bleibt die Katalog-Darstellung (Stufe), sie wird NICHT als Roh gedeutet."""
    erste = _ohne_angabe("cloud_total", 0) if fmt is None else _mc("cloud_total", 0, fmt)
    sms = _sms(_trip(_trip_dict([erste, _mc("gust", 1)])))
    assert sms == soll, sms


def test_ac3_kanal_format_gewinnt_gegen_grundauswahl():
    """AC-3: Grundauswahl Bewoelkung Roh, SMS-Liste ohne Angabe -> die SMS-Liste
    gilt (Katalog-Darstellung); umgekehrt Grundauswahl ohne Angabe, SMS-Liste Roh -> Roh."""
    grund_roh = [_mc(m, i, "raw" if m == "cloud_total" else None)
                 for i, m in enumerate(GRUNDAUSWAHL)]
    a = _sms(_trip(_trip_dict([_ohne_angabe("cloud_total", 0), _mc("gust", 1)], grund=grund_roh)))
    b = _sms(_trip(_trip_dict([_mc("cloud_total", 0, "raw"), _mc("gust", 1)])))
    assert a == "E1: CT:SCT@4 G45@4", a
    assert b == "E1: CT70@4 G45@4", b


@pytest.mark.parametrize("mid,sym,roh_wert", [("cloud_total", "CT", "70"),
                                               ("cloud_low", "CL", "40"),
                                               ("cloud_mid", "CM", "30"),
                                               ("cloud_high", "CH", "20")])
def test_ac3_alle_vier_format_metriken_roh_und_einfach(mid, sym, roh_wert):
    """AC-3: alle vier Format-Metriken -- Roh zeigt den Prozentwert, Einfach die
    Stufe (``SYM:`` + Buchstaben), ohne Angabe = Einfach."""
    grund = _liste(GRUNDAUSWAHL + ([mid] if mid not in GRUNDAUSWAHL else []))
    roh = _sms(_trip(_trip_dict([_mc(mid, 0, "raw")], grund=grund)))
    einfach = _sms(_trip(_trip_dict([_mc(mid, 0, "symbol")], grund=grund)))
    ohne = _sms(_trip(_trip_dict([_ohne_angabe(mid, 0)], grund=grund)))
    assert re.fullmatch(rf"E1: {sym}{roh_wert}@\d+", roh), roh
    assert re.fullmatch(rf"E1: {sym}:[A-Z]+@\d+", einfach), einfach
    assert ohne == einfach, (ohne, einfach)


# ---------------------------------------------------------------------------
# AC-4: abgewaehlte Metriken (#944)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("report_type", REPORT_TYPES)
def test_ac4_abgewaehlte_metriken_ohne_wert(report_type):
    """AC-4: abgewaehlte Temperatur, Feuchte und Windrichtung erscheinen nicht;
    die aktiven Tokens sind dieselben wie bei einer Liste ganz ohne diese Zeilen.
    Kein weiteres Symbol (z. B. Schneefallgrenze, gefuehlte Temperatur trotz Daten)
    taucht auf -- die deaktivierten Specs (#944) bleiben wirksam."""
    mit_abwahl = [_mc("gust", 0), _mc("temperature", 1, enabled=False),
                  _mc("humidity", 2, enabled=False), _mc("precipitation", 3),
                  _mc("wind_direction", 4, enabled=False)]
    a = _sms(_trip(_trip_dict(mit_abwahl)), report_type)
    b = _sms(_trip(_trip_dict(_liste(["gust", "precipitation"]))), report_type)
    assert a == "E1: G45@4 R2.0@4", a
    assert a == b


@pytest.mark.parametrize("report_type", REPORT_TYPES)
def test_ac4_grundauswahl_metrik_nicht_in_sms_liste(report_type):
    """AC-4: Groessen der Grundauswahl, die die SMS-Liste nicht nennt, bleiben aus
    der SMS draussen (auch die Null-Form ``HU-`` erscheint nicht)."""
    sms = _sms(_trip(_trip_dict(_liste(["wind", "gust"]))), report_type)
    assert sms == "E1: W- G45@4", sms
    assert "HU" not in _symbole(sms) and "UV" not in _symbole(sms)


# ---------------------------------------------------------------------------
# AC-5: Warnblock bleibt hinten, keine Zeile der Liste
# ---------------------------------------------------------------------------

FOLGE_A = ["thunder", "gust", "precipitation", "cloud_total"]
FOLGE_B = ["cloud_total", "precipitation", "gust", "thunder"]


@pytest.mark.parametrize("report_type", REPORT_TYPES)
def test_ac5_warnblock_hinten_bei_zwei_folgen(report_type):
    """AC-5: dieselbe Auswahl in zwei Folgen -- die Metrik-Tokens folgen der Liste,
    der Warnblock ``!TS:M@10`` steht in beiden Faellen am Ende."""
    a = _sms(_trip(_trip_dict(_liste(FOLGE_A))), report_type, warnung=3)
    b = _sms(_trip(_trip_dict(_liste(FOLGE_B))), report_type, warnung=3)
    assert a == "E1: TH:M@4 TH+:- G45@4 R2.0@4 CT:SCT@4 !TS:M@10", a
    assert b == "E1: CT:SCT@4 R2.0@4 G45@4 TH:M@4 TH+:- !TS:M@10", b


@pytest.mark.parametrize("sms_liste", [[], [_mc("thunder", 0, enabled=False), _mc("gust", 1)]],
                         ids=["leer", "gewitter_abgewaehlt"])
def test_ac5_warnblock_nicht_abwaehlbar(sms_liste):
    """AC-5: leere SMS-Liste bzw. abgewaehltes Gewitter -- die amtliche Warnung
    erscheint trotzdem am Ende (keine Zeile der Liste, nicht abwaehlbar)."""
    sms = _sms(_trip(_trip_dict(sms_liste)), warnung=3)
    assert sms.endswith(" !TS:M@10"), sms
    assert "TH" not in _symbole(sms), sms


@pytest.mark.parametrize("umgekehrt", [False, True], ids=["listenfolge", "umgekehrt"])
def test_ac5_kuerzung_vom_listenende_warnblock_bleibt_hinten(umgekehrt):
    """AC-5 / AC-1: ueberlange SMS-Liste -- hoechstens 160 Zeichen, gekuerzt wird
    vom Ende der SMS-Liste (erhalten bleibt ein lueckenloser Listenanfang), der
    Warnblock bleibt in beiden Folgen am Ende."""
    from tests.tdd.test_3047_r7_kanaele_trip import _EXTRA, _LANGE_LISTE, _listenplaetze

    liste = list(reversed(_LANGE_LISTE)) if umgekehrt else list(_LANGE_LISTE)
    grund = _liste(GRUNDAUSWAHL + list(_EXTRA))
    sms = _sms(_trip(_trip_dict(_liste(liste), grund=grund)), warnung=3)
    assert len(sms) <= 160, sms
    assert sms.endswith(" !TS:M@10"), sms
    erhalten = sorted(set(_listenplaetze(sms, liste)))
    assert erhalten and erhalten == list(range(len(erhalten))), sms
    assert len(erhalten) < len(liste), sms


# ---------------------------------------------------------------------------
# AC-6: Premium-SMS = SMS-Text trotz abweichender premium_sms-Ebene
# ---------------------------------------------------------------------------

def test_ac6_premium_gleich_sms_trotz_abweichender_premium_ebene(monkeypatch):
    """AC-6: ``channel_layouts.premium_sms`` weicht von der SMS-Liste ab (der
    Resolver-Zweig ``premium_sms`` ist anders) -- der gesendete Premium-Text ist
    trotzdem der SMS-Text, hoechstens 153 Zeichen. Echter Versandweg, zwei Nutzer."""
    from services.channel_list_resolver import resolve_channel_lists
    from tests.tdd.test_3047_r7_kanaele_trip import _zwei_nutzer

    sms_liste = _liste(["precipitation", "gust", "cloud_total"])
    premium_liste = _liste(["humidity", "uv_index"])
    data = _trip_dict(sms_liste, extra_layouts={"premium_sms": premium_liste})
    data["report_config"]["telegram_style"] = "rich"
    view = resolve_channel_lists(_trip(data).display_config, "trip", "evening")
    assert [z.metric_id for z in view.premium_sms] != [z.metric_id for z in view.sms], \
        "Vorbedingung: premium_sms-Zweig weicht ab"
    for _uid, mit_tr in _zwei_nutzer(monkeypatch, data):
        sms = mit_tr.sendungen("sms")[0]["body"]
        premium = mit_tr.sendungen("premium_sms")[0]["body"]
        assert sms == "E1: R2.0@4 G45@4 CT:SCT@4", sms
        assert premium == sms, (premium, sms)
        assert len(premium) <= 153


# ---------------------------------------------------------------------------
# AC-8: zwei Nutzer, beide Aufrufreihenfolgen (Trip)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("reihenfolge", ["ab", "ba"])
def test_ac8_trip_zwei_nutzer_je_eigene_sms(reihenfolge):
    """AC-8: zwei Nutzer mit unterschiedlicher Auswahl, Folge und Format; jede SMS
    zeigt nur die eigene Auswahl, unabhaengig von der Aufrufreihenfolge."""
    a = _trip(_trip_dict([_mc("gust", 0), _mc("cloud_total", 1, "raw")]), frisches_profil())
    b = _trip(_trip_dict([_mc("cloud_total", 0, "symbol"), _mc("precipitation", 1),
                          _mc("gust", 2)]), frisches_profil())
    folge = [("a", a), ("b", b)] if reihenfolge == "ab" else [("b", b), ("a", a)]
    ist = {name: _sms(t) for name, t in folge}
    assert ist == {"a": "E1: G45@4 CT70@4", "b": "E1: CT:SCT@4 R2.0@4 G45@4"}, ist


# ---------------------------------------------------------------------------
# AC-9: Quelle ist der Resolver, nicht get_metrics_for_channel("sms", ...)
# ---------------------------------------------------------------------------

class _AbweichendesModell(UnifiedWeatherDisplayConfig):
    """Echte Unterklasse (kein Mock): ``get_metrics_for_channel("sms", ...)``
    liefert bewusst eine ANDERE Liste als der Resolver (Altpfad-Signatur).
    Der Resolver liest die Kaskade ueber ``trip_channel_metrics`` und sieht die
    Abweichung nicht; folgt die SMS ihr, liest der Trip-Pfad noch den Altpfad."""

    def get_metrics_for_channel(self, channel, report_type):
        echt = super().get_metrics_for_channel(channel, report_type)
        if channel != "sms":
            return echt
        return [MetricConfig(metric_id="humidity", enabled=True, order=0),
                MetricConfig(metric_id="uv_index", enabled=True, order=1),
                MetricConfig(metric_id="cloud_total", enabled=True, order=2,
                             format_mode="raw", use_friendly_format=False)]


@pytest.mark.parametrize("report_type", REPORT_TYPES)
def test_ac9_trip_sms_folgt_resolver_nicht_altpfad(report_type):
    """AC-9: Resolver-Liste (G, R, CT Einfach) und Altpfad (HU, UV, CT Roh) weichen
    ab -- die SMS folgt der Resolver-Liste, auch in der Darstellung."""
    from services.channel_list_resolver import resolve_channel_lists

    dc = _trip(_trip_dict([_mc("gust", 0), _mc("precipitation", 1),
                           _mc("cloud_total", 2, "symbol")])).display_config
    # Der Trip-Pfad arbeitet auf dieser (unkollabierten) Instanz: die
    # Unterklasse wird direkt als display_config uebergeben.
    abw = _AbweichendesModell(**{f.name: getattr(dc, f.name) for f in dataclasses.fields(dc)})
    soll_folge = [z.metric_id for z in resolve_channel_lists(abw, "trip", report_type).sms
                  if z.enabled and z.metric_id in KUERZEL]
    assert soll_folge == ["gust", "precipitation", "cloud_total"], "Vorbedingung: Resolver-Liste"
    assert [m.metric_id for m in abw.get_metrics_for_channel("sms", report_type)] == [
        "humidity", "uv_index", "cloud_total"], "Vorbedingung: Altpfad weicht ab"
    sms = _sms(abw, report_type)
    assert sms == "E1: G45@4 R2.0@4 CT:SCT@4", sms


# ---------------------------------------------------------------------------
# AC-10: Kanal-Schwelle der SMS wirkt, Metrik-sms_threshold nicht
# ---------------------------------------------------------------------------

def _schwellen_trip(kanal: str, metrik_schwelle: float | None) -> object:
    liste = _liste(FOLGE_A)
    grund = _liste(GRUNDAUSWAHL)
    if metrik_schwelle is not None:
        for eintrag in liste + grund:
            eintrag["sms_threshold"] = metrik_schwelle
    data = _trip_dict(liste, grund=grund)
    data["alert_channel_thresholds"] = {"sms": kanal}
    return _trip(data)


@pytest.mark.parametrize("kanal,soll_warnung", [("LOW", True), ("HIGH", False)])
@pytest.mark.parametrize("metrik_schwelle", [None, 1.0, 99.0], ids=["ohne", "niedrig", "hoch"])
def test_ac10_kanal_schwelle_wirkt_metrik_schwelle_nicht(kanal, soll_warnung, metrik_schwelle):
    """AC-10: Warnstufe 3 (orange). Kanal-Schwelle LOW -> Warnblock, HIGH -> keiner;
    ein ``sms_threshold`` je Metrik aendert die SMS nicht (#2792 E1)."""
    sms = _sms(_schwellen_trip(kanal, metrik_schwelle), warnung=3)
    basis = "E1: TH:M@4 TH+:- G45@4 R2.0@4 CT:SCT@4"
    assert sms == (basis + " !TS:M@10" if soll_warnung else basis), sms


# ---------------------------------------------------------------------------
# Adapter sms_rows_to_maps (AC-3, AC-4, AC-9)
# ---------------------------------------------------------------------------

def test_adapter_ids_nur_enabled():
    """Adapter: ``ids`` = Menge der ``enabled``-Zeilen; abgewaehlte fehlen (#944)."""
    from output.renderers.sms_trip import sms_rows_to_maps
    from services.channel_list_resolver import ChannelRow

    rows = (ChannelRow("gust", True, None, 0), ChannelRow("temperature", False, None, 1),
            ChannelRow("precipitation", True, None, 2))
    ids, _pos, _fmt = sms_rows_to_maps(rows)
    assert ids == {"gust", "precipitation"}


def test_adapter_position_resolver_folge():
    """Adapter: ``position_by_metric`` = Index in der Resolver-Folge (nicht Katalog-
    oder Grundauswahl-Folge)."""
    from output.renderers.sms_trip import sms_rows_to_maps
    from services.channel_list_resolver import ChannelRow

    rows = (ChannelRow("cloud_total", True, None, 0), ChannelRow("precipitation", True, None, 1),
            ChannelRow("gust", True, None, 2), ChannelRow("temperature", True, None, 3))
    _ids, pos, _fmt = sms_rows_to_maps(rows)
    assert {m: pos[m] for m in ("cloud_total", "precipitation", "gust", "temperature")} == {
        "cloud_total": 0, "precipitation": 1, "gust": 2, "temperature": 3}


@pytest.mark.parametrize("fmt,soll", [(None, "symbol"), ("raw", "raw"), ("symbol", "symbol")],
                         ids=["ohne_angabe", "roh", "einfach"])
def test_adapter_format_none_ist_katalog_standard(fmt, soll):
    """Adapter (AC-3): ``format=None`` -> Katalog-Standard ``symbol`` (NICHT Roh),
    ``raw`` bleibt Roh."""
    from output.renderers.sms_trip import sms_rows_to_maps
    from services.channel_list_resolver import ChannelRow

    _ids, _pos, formate = sms_rows_to_maps((ChannelRow("cloud_total", True, fmt, 0),))
    assert formate == {"cloud_total": soll}


def test_adapter_format_nur_fuer_format_metriken():
    """Adapter: ``format_by_metric`` nur fuer ``SMS_FORMAT_MODE_METRIC_IDS``; ein
    Format an Wind/Windrichtung/Temperatur bleibt aussen vor."""
    from app.metric_catalog import SMS_FORMAT_MODE_METRIC_IDS
    from output.renderers.sms_trip import sms_rows_to_maps
    from services.channel_list_resolver import ChannelRow

    rows = (ChannelRow("wind_direction", True, "raw", 0), ChannelRow("wind", True, "raw", 1),
            ChannelRow("temperature", True, "raw", 2), ChannelRow("cloud_low", True, "raw", 3),
            ChannelRow("cloud_high", True, None, 4))
    _ids, _pos, formate = sms_rows_to_maps(rows)
    assert formate == {"cloud_low": "raw", "cloud_high": "symbol"}
    assert set(formate) <= SMS_FORMAT_MODE_METRIC_IDS


def test_adapter_unbekannte_ids_wirkungslos():
    """Adapter: eine unbekannte ID wirft nicht und bekommt kein Format; die
    bekannten Zeilen behalten ihre Werte."""
    from output.renderers.sms_trip import sms_rows_to_maps
    from services.channel_list_resolver import ChannelRow

    rows = (ChannelRow("gibt_es_nicht", True, "raw", 0), ChannelRow("cloud_total", True, "raw", 1))
    ids, pos, formate = sms_rows_to_maps(rows)
    assert "cloud_total" in ids and pos["cloud_total"] == 1
    assert formate == {"cloud_total": "raw"}


def test_adapter_leere_liste():
    """Adapter: bewusst leere SMS-Liste -> leere Abbildungen."""
    from output.renderers.sms_trip import sms_rows_to_maps

    assert sms_rows_to_maps(()) == (set(), {}, {})


# ---------------------------------------------------------------------------
# AC-7 / AC-8: Orte-SMS (Versand und Vorschau), zwei Nutzer
# ---------------------------------------------------------------------------

def _orte_liste(aktiv: list[dict]) -> list[dict]:
    """SMS-Liste im Speicherformat des Editors: aktive Zeilen vorn, die uebrigen
    Groessen der Grundauswahl ausdruecklich abgewaehlt."""
    genannt = {z["metric_id"] for z in aktiv}
    return copy.deepcopy(aktiv) + [{"metric_id": m, "enabled": False}
                                   for m, _ in ORTE_GRUND if m not in genannt]


#: SMS-Liste der Orte: eigene Folge, Bewoelkung je Fall Roh/Einfach.
def _orte_sms(cloud_fmt: str | None) -> list[dict]:
    ct = {"metric_id": "cloud_total", "enabled": True}
    if cloud_fmt is not None:
        ct["format"] = cloud_fmt
    return _orte_liste([{"metric_id": "precipitation", "enabled": True}, ct,
                        {"metric_id": "gust", "enabled": True}])


def _orte_kuerzel_folge(ortsteil: str) -> list[str]:
    """#3172 (ADR-0125): Kuerzel der Token-Zeile (``CT:SCT@11`` -> ``CT``)."""
    kuerzel = (re.match(r"[A-Z]+", t) for t in ortsteil.split(" ")[1:])
    return [k.group(0) for k in kuerzel if k and k.group(0) in ORTE_KUERZEL.values()]


def _orte_wolke(ortsteil: str) -> str:
    m = re.search(r"(?<= )CT(\S+)", ortsteil)
    assert m, ortsteil
    return m.group(1)


#: Wolken-Token Orte-SMS (Innsbruck, Stundenspitze 35 % um 11 Uhr): Roh = Zahl,
#: Einfach = Stufe (#3172: Token-Zeile wie im Trip, ``CT:SCT@11``).
ORTE_WOLKE = {"raw": "35@11", "simplified": ":SCT@11"}


@pytest.mark.parametrize("cloud_fmt", ["raw", "simplified"], ids=["roh", "einfach"])
def test_ac7_orte_sms_versand_folge_und_format(mit, cloud_fmt):
    """AC-7: Versand -- Auswahl/Folge/Darstellung = SMS-Auswahl (zwei Nutzer);
    Premium-SMS ist derselbe Text."""
    p = preset({"sms": _orte_sms(cloud_fmt)})
    for _uid, snap in zwei_nutzer(mit, p):
        sms = text(snap, "sms")
        ibk = _sms_ort(sms, "Innsbruck")
        assert _orte_kuerzel_folge(ibk) == ["R", "CT", "G"], sms
        assert _orte_wolke(ibk) == ORTE_WOLKE[cloud_fmt], sms
        assert text(snap, "premium_sms") == sms


@pytest.mark.parametrize("cloud_fmt", ["raw", "simplified"], ids=["roh", "einfach"])
def test_ac7_orte_sms_vorschau_gleich_versand(mit, cloud_fmt):
    """AC-7: Vorschau und Versand derselben Konfiguration zeigen dieselbe SMS."""
    from services.compare_preview_service import ComparePreviewService
    from tests.tdd._compare_kette_fixtures import (
        TARGET_DATE, nutzer_anlegen, orte_anlegen, preset_ablegen,
    )

    p = preset({"sms": _orte_sms(cloud_fmt)})
    (_uid, snap), _ = zwei_nutzer(mit, p)
    versand = _sms_ort(text(snap, "sms"), "Innsbruck")
    neu = nutzer_anlegen("premium")
    _sprache(neu, "de")
    orte_anlegen(neu)
    preset_ablegen(neu, copy.deepcopy(p))
    vorschau = ComparePreviewService().render_all_channels(
        p["id"], user_id=neu, target_date=TARGET_DATE)["sms"]
    assert _sms_ort(vorschau, "Innsbruck") == versand, (vorschau, versand)


def test_ac7_orte_telegram_kurzform_gleich_sms(mit):
    """AC-7: Telegram-Kurzform der Orte = SMS-Text (folgt der SMS-Auswahl)."""
    p = preset({"sms": _orte_sms("raw")})
    p["display_config"]["telegram_style"] = "kurzform"
    for _uid, snap in zwei_nutzer(mit, p):
        assert text(snap, "telegram") == text(snap, "sms")
        assert _orte_kuerzel_folge(_sms_ort(text(snap, "sms"), "Innsbruck")) == ["R", "CT", "G"]


@pytest.mark.parametrize("reihenfolge", ["ab", "ba"])
def test_ac8_orte_zwei_nutzer_je_eigene_sms(mit, reihenfolge):
    """AC-8 (Orte): zwei Konfigurationen mit unterschiedlicher Folge/Format; jede
    SMS zeigt nur die eigene Auswahl, beide Aufrufreihenfolgen."""
    pa = preset({"sms": _orte_liste([
        {"metric_id": "gust", "enabled": True},
        {"metric_id": "cloud_total", "enabled": True, "format": "raw"}])})
    pb = preset({"sms": _orte_liste([
        {"metric_id": "cloud_total", "enabled": True, "format": "simplified"},
        {"metric_id": "precipitation", "enabled": True}])})
    soll = {"a": (["G", "CT"], "35@11"), "b": (["CT", "R"], ":SCT@11")}
    folge = [("a", pa), ("b", pb)] if reihenfolge == "ab" else [("b", pb), ("a", pa)]
    for name, p in folge:
        for _uid, snap in zwei_nutzer(mit, p):
            ibk = _sms_ort(text(snap, "sms"), "Innsbruck")
            assert (_orte_kuerzel_folge(ibk), _orte_wolke(ibk)) == soll[name], ibk


# ---------------------------------------------------------------------------
# AC-11: eigene Fallliste im Pruefkatalog
# ---------------------------------------------------------------------------

def _fallliste_sms() -> dict:
    pfad = REPO_ROOT / "tests" / "fixtures" / "einstellung_gleich_mail" / "fallliste_sms.json"
    assert pfad.is_file(), f"Fallliste fehlt: {pfad}"
    return json.loads(pfad.read_text(encoding="utf-8"))


def test_ac11_waechter_kennt_fallliste_sms():
    """AC-11: der Waechter laedt ``fallliste_sms.json`` mit (registriert) und
    findet Verweise auf diese Testdatei."""
    from tests.tdd import test_einstellung_gleich_mail_fallliste as w

    assert "sms" in w.TEILDATEIEN
    assert "tests/tdd/test_3099_*.py" in w.PY_TEST_GLOBS
    geladen = w.lade_falllisten(w.FALLLISTEN_DIR)
    assert "fallliste_sms.json" in geladen


def test_ac11_fallliste_sms_faelle_und_achsen():
    """AC-11: neue IDs (Praefix ``sms-``), alle gruen, SMS-/Premium-Format, beide
    Kontexte, Aspekte Auswahl/Reihenfolge/Darstellung, IDs global eindeutig ueber
    alle Falllisten, Achsen der Spec Nr. 8 belegt."""
    faelle = _fallliste_sms()["faelle"]
    ids = [f["id"] for f in faelle]
    assert ids and all(i.startswith("sms-") for i in ids), ids
    assert len(ids) == len(set(ids)), "IDs doppelt in fallliste_sms.json"
    andere = set()
    for pfad in (REPO_ROOT / "tests" / "fixtures" / "einstellung_gleich_mail").glob("fallliste_*.json"):
        if pfad.name != "fallliste_sms.json":
            andere |= {f.get("id") for f in json.loads(pfad.read_text(encoding="utf-8"))["faelle"]}
    assert not (set(ids) & andere), set(ids) & andere
    assert all(f["status"] == "gruen" for f in faelle)
    assert all({"sms", "premium_sms"} & set(f["format"].split("+")) for f in faelle)
    assert {f["kontext"] for f in faelle} >= {"trip", "orte"}
    aspekte = set()
    for f in faelle:
        aspekte |= set(f.get("aspekte") or []) | {f["pruefung"]}
    assert aspekte >= {"auswahl", "reihenfolge", "darstellung"}, aspekte
    merkmale: dict[str, set] = {}
    for f in faelle:
        for k, v in (f.get("merkmale") or {}).items():
            merkmale.setdefault(k, set()).add(v)
    assert merkmale.get("kanal_ebene", set()) >= {"nie", "leer", "gesetzt"}, merkmale
    assert merkmale.get("darstellung", set()) >= {"roh", "einfach", "ohne_angabe"}, merkmale
    assert merkmale.get("reihenfolge", set()) >= {"katalog", "ziehfolge"}, merkmale
    assert {"abgewaehlt", "warnung", "kuerzung"} <= set(merkmale), merkmale
    for kontext in ("trip", "orte"):
        for fmt in ("sms", "premium_sms"):
            assert any(f["kontext"] == kontext and fmt in f["format"].split("+")
                       for f in faelle), (kontext, fmt)
