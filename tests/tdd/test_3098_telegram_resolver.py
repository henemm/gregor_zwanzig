"""#3098 (Phase 3c von #3047, Epic #3058): Telegram liest aus dem Kanal-Listen-Resolver.

SPEC: docs/specs/modules/feat_3098_telegram_resolver.md (AC-2 bis AC-9)

Trip: Spalten, Folge und Roh/Einfach der Telegram-Nachricht kommen aus
``resolve_channel_lists(dc, "trip", report_type).telegram`` (Adapter
``telegram_metric_configs``), nicht mehr aus ``dc.get_metrics_for_channel("telegram", ...)``.
Orte: liest bereits ``view.telegram`` -- hier nur Nachweis-Faelle (Versand und Vorschau).

Zusicherungen an der echten Telegram-Ausgabe (``TripReportFormatter.format_email``
-> ``telegram_bubbles``; Orte ueber den echten Versandweg bzw. ``ComparePreviewService``).
Soll von Hand. Kein ``Mock()``/``patch()``.

ROT vor der Umstellung:
* ``test_adapter_*`` -- ``telegram_metric_configs`` existiert nicht.
* ``test_ac8_*`` -- der Trip-Telegram-Pfad liest heute
  ``dc.get_metrics_for_channel("telegram", ...)``; weicht diese Methode von der
  Resolver-Liste ab, folgt die Nachricht heute der Methode statt dem Resolver.
* ``test_ac9_*`` -- ``fallliste_telegram.json`` fehlt, der Waechter kennt sie nicht.

Die uebrigen Faelle (AC-2 bis AC-7) sind Bestandsschutz der zugestellten Nachricht
(ADR-0095: Ergebnis unveraendert) und schon heute gruen; sie bewachen die Umstellung.
"""
from __future__ import annotations

import copy
import dataclasses
import json
import re
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
    _sprache, mit, ortsbloecke, preset, text, wertezeilen, zwei_nutzer,
)

REPO_ROOT = Path(__file__).resolve().parents[2]

#: Grundauswahl (Folge = Katalogfolge der Golden-Fixture der Runde 7).
GRUNDAUSWAHL = ["gust", "temperature", "rain_probability", "wind", "wind_direction", "thunder",
                "cloud_total", "precipitation", "uv_index", "humidity"]

#: Spaltenkoepfe/Kuerzel der Telegram-Tabelle je Metrik, von Hand (Register).
KUERZEL = {"gust": "G", "temperature": "T", "rain_probability": "PR", "wind": "W",
           "wind_direction": "WD", "thunder": "TH", "cloud_total": "CT",
           "precipitation": "R", "uv_index": "UV", "humidity": "HU"}

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


def _trip_dict(telegram: list[dict] | None = None, *, grund: list[dict] | None = None) -> dict:
    """Trip-JSON: Grundauswahl + optional Telegram-Kanal-Ebene (``None`` = nie gesetzt)."""
    d = golden_dict("golden_c")
    d["display_config"]["metrics"] = grund if grund is not None else [
        _mc(m, i) for i, m in enumerate(GRUNDAUSWAHL)]
    d["display_config"]["channel_layouts"] = {} if telegram is None else {"telegram": telegram}
    d["display_config"]["outlook_metrics"] = []
    return d


def _dc(data: dict, uid: str | None = None) -> UnifiedWeatherDisplayConfig:
    """Echter Loader (Persistenzformat -> Modell) fuer einen echten Nutzer.
    #3237: die Kanal-Einstellung des Falls steht in der Tabelle "Was steht wo"
    (Altfelder wirken nicht mehr, sie bleiben Beschreibung)."""
    from tests.helpers.tabelle_aus_wunsch import trip_wunsch_als_tabelle

    trip = load_trip(trip_wunsch_als_tabelle(data), user_id=uid or frisches_profil())
    assert trip is not None
    return trip.display_config


def _bubbles(dc, report_type: str = "evening", lang: str = "de") -> list[str]:
    return TripReportFormatter().format_email(
        [segment()], trip_name="Issue3098", report_type=report_type,
        night_weather=night_weather(), display_config=dc, stage_name=STAGE_NAME,
        tz=TZ, lang=lang,
    ).telegram_bubbles


def _tabelle(bubbles: list[str]) -> tuple[list[str], list[list[str]]] | None:
    """Kopfzeile (ohne Zeitspalte) und Zellen der ersten Segment-Tabelle; ``None`` ohne Tabelle."""
    for b in bubbles:
        if "<pre>" in b:
            zeilen = b.split("<pre>")[1].split("</pre>")[0].strip().splitlines()
            return zeilen[0].split()[1:], [z.split()[1:] for z in zeilen[1:]]
    return None


def _kurzuebersicht(bubbles: list[str]) -> list[str]:
    for b in bubbles:
        zeilen = b.splitlines()
        if zeilen and zeilen[0] in ("Kurzübersicht", "Summary"):
            return zeilen[1:]
    raise AssertionError(f"keine Kurzuebersicht: {bubbles}")


def _kuerzel_folge(bubbles: list[str]) -> list[str]:
    """Kuerzel der Kurzuebersicht in Ausgabefolge (nur Metrik-Zeilen)."""
    bekannt = set(KUERZEL.values())
    return [z.split(" ", 1)[0] for z in _kurzuebersicht(bubbles)
            if z.split(" ", 1)[0] in bekannt]


def _koepfe(bubbles: list[str]) -> list[str]:
    tab = _tabelle(bubbles)
    assert tab is not None, f"keine Telegram-Tabelle: {bubbles}"
    return tab[0]


def _spalte(bubbles: list[str], kuerzel: str) -> set[str]:
    """Zellwerte einer Spalte. Die Windspalte ``W`` traegt bei zusammengefuehrter
    Windrichtung zwei Woerter (``20 W``); daher zeilenweise am Kopfindex lesen."""
    koepfe, zeilen = _tabelle(bubbles)
    i = koepfe.index(kuerzel)
    # Spalten vor ``kuerzel`` mit zusammengefuehrtem Wind belegen zwei Woerter.
    versatz = sum(1 for k in koepfe[:i] if k == "W" and len(zeilen[0]) > len(koepfe))
    return {z[i + versatz] for z in zeilen}


# ---------------------------------------------------------------------------
# AC-2: Folge und Menge = Resolver-Liste; Kurzuebersicht + Windrichtung dieselbe Liste
# ---------------------------------------------------------------------------

#: Telegram-Liste: andere Folge als die Grundauswahl, Teilmenge (abgewaehlt:
#: temperature, rain_probability, thunder, precipitation, uv_index, humidity).
TG_FOLGE = ["cloud_total", "gust", "wind", "wind_direction"]


@pytest.mark.parametrize("report_type", REPORT_TYPES)
def test_ac2_tabelle_folgt_telegram_auswahl(report_type):
    """AC-2: Tabelle = genau die aktiven Telegram-Metriken in gewaehlter Folge;
    Windrichtung (Einfach) steckt in der Windspalte, keine eigene WD-Spalte."""
    dc = _dc(_trip_dict([_mc(m, i) for i, m in enumerate(TG_FOLGE)]))
    bubbles = _bubbles(dc, report_type)
    assert _koepfe(bubbles) == ["CT", "G", "W"], bubbles


@pytest.mark.parametrize("report_type", REPORT_TYPES)
def test_ac2_kurzuebersicht_folgt_derselben_liste(report_type):
    """AC-2 (F004 aus #1719): Kurzuebersicht zeigt dieselben Groessen in derselben
    Folge wie die Tabelle; abgewaehlte Groessen erscheinen nicht."""
    dc = _dc(_trip_dict([_mc(m, i) for i, m in enumerate(TG_FOLGE)]))
    bubbles = _bubbles(dc, report_type)
    assert _kuerzel_folge(bubbles) == ["CT", "G", "W"], _kurzuebersicht(bubbles)
    for weg in ("T", "PR", "TH", "R", "UV", "HU"):
        assert weg not in _kuerzel_folge(bubbles)


def test_ac2_windrichtung_merge_folgt_telegram_liste_nicht_grundauswahl():
    """AC-2: Grundauswahl hat Windrichtung Roh, die Telegram-Liste Einfach --
    Tabelle UND Kurzuebersicht fuehren die Richtung in der Windzeile zusammen
    (keine eigene WD-Zeile/Spalte), weil beide derselben Telegram-Liste folgen."""
    grund = [_mc(m, i, "raw" if m == "wind_direction" else None)
             for i, m in enumerate(GRUNDAUSWAHL)]
    tg = [_mc("wind", 0), _mc("wind_direction", 1, "scale"), _mc("gust", 2)]
    bubbles = _bubbles(_dc(_trip_dict(tg, grund=grund)))
    assert _koepfe(bubbles) == ["W", "G"], bubbles
    assert "WD" not in _kuerzel_folge(bubbles)
    assert any(re.fullmatch(r"W \d+ W", z) for z in _kurzuebersicht(bubbles)), bubbles


def test_ac2_windrichtung_roh_in_telegram_liste_eigene_angabe():
    """AC-2 Gegenprobe: Grundauswahl Einfach, Telegram-Liste Roh -> eigene WD-Spalte
    und eigene WD-Zeile mit Gradzahl."""
    tg = [_mc("wind", 0), _mc("wind_direction", 1, "raw"), _mc("gust", 2)]
    bubbles = _bubbles(_dc(_trip_dict(tg)))
    assert _koepfe(bubbles) == ["W", "WD", "G"], bubbles
    assert "WD 250°" in _kurzuebersicht(bubbles), bubbles


# ---------------------------------------------------------------------------
# AC-3: Roh / Einfach / ohne Angabe
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("fmt,soll_roh", [("raw", True), ("symbol", False), (None, False)],
                         ids=["roh", "einfach", "ohne_angabe"])
def test_ac3_bewoelkung_roh_einfach_ohne_angabe(fmt, soll_roh):
    """AC-3: Bewoelkung Roh = Prozentzahl (70), Einfach = Symbol; ohne Angabe
    bleibt die Katalog-Darstellung (Symbol), sie wird NICHT als Roh gedeutet."""
    tg = [_mc("cloud_total", 0, fmt), _mc("gust", 1)]
    if fmt is None:
        # "ohne Angabe" heisst: kein format_mode, use_friendly_format Standard (wahr).
        tg[0] = {"metric_id": "cloud_total", "enabled": True, "bucket": "primary", "order": 0}
    bubbles = _bubbles(_dc(_trip_dict(tg)))
    zellen = _spalte(bubbles, "CT")
    if soll_roh:
        assert zellen == {"70"}, bubbles
    else:
        assert zellen == {"⛅"}, bubbles


def test_ac3_ohne_angabe_gleich_katalog_standard_explizit():
    """AC-3: ohne Angabe ergibt dieselbe Nachricht wie die ausdrueckliche
    Katalog-Darstellung (Windrichtung: scale)."""
    ohne = {"metric_id": "wind_direction", "enabled": True, "bucket": "primary", "order": 1}
    a = _bubbles(_dc(_trip_dict([_mc("wind", 0), ohne, _mc("gust", 2)])))
    b = _bubbles(_dc(_trip_dict([_mc("wind", 0), _mc("wind_direction", 1, "scale"),
                                 _mc("gust", 2)])))
    assert a == b


# ---------------------------------------------------------------------------
# AC-4: Windrichtung Roh/Einfach DE/EN, Kopf-Typ (#3063)
# ---------------------------------------------------------------------------

KOPF_TYP = {("morning", "de"): "Morgen", ("evening", "de"): "Abend",
            ("morning", "en"): "Morning", ("evening", "en"): "Evening"}


@pytest.mark.parametrize("lang", ["de", "en"])
@pytest.mark.parametrize("report_type", REPORT_TYPES)
def test_ac4_telegram_windrichtung_roh(report_type, lang):
    """AC-4 / #3063 P2: Windrichtung Roh -> eigene Angabe in Grad (Tabelle + Kurzuebersicht)."""
    tg = [_mc("wind_direction", 0, "raw"), _mc("wind", 1), _mc("gust", 2)]
    bubbles = _bubbles(_dc(_trip_dict(tg)), report_type, lang)
    assert _koepfe(bubbles)[0] == "WD", bubbles
    assert _spalte(bubbles, "WD") == {"250°"}, bubbles
    assert "WD 250°" in _kurzuebersicht(bubbles)


@pytest.mark.parametrize("lang", ["de", "en"])
@pytest.mark.parametrize("report_type", REPORT_TYPES)
def test_ac4_telegram_windrichtung_einfach(report_type, lang):
    """AC-4: Windrichtung Einfach -> zusammengefasste Darstellung in der Windzeile."""
    tg = [_mc("wind_direction", 0, "scale"), _mc("wind", 1), _mc("gust", 2)]
    bubbles = _bubbles(_dc(_trip_dict(tg)), report_type, lang)
    assert "WD" not in _koepfe(bubbles), bubbles
    assert any(re.fullmatch(r"W \d+ W", z) for z in _kurzuebersicht(bubbles)), bubbles


@pytest.mark.parametrize("lang", ["de", "en"])
@pytest.mark.parametrize("report_type", REPORT_TYPES)
def test_ac4_telegram_kopf_typ_in_nutzersprache(report_type, lang):
    """AC-4 / #3063 P1: der Kopf nennt den Berichtstyp in der Sprache des Nutzers."""
    tg = [_mc("wind", 0), _mc("gust", 1)]
    kopf = _bubbles(_dc(_trip_dict(tg)), report_type, lang)[0].splitlines()
    assert kopf[1].split()[0] == KOPF_TYP[(report_type, lang)], kopf


# ---------------------------------------------------------------------------
# AC-5: Kanal-Ebene nie / leer / gesetzt
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("report_type", REPORT_TYPES)
def test_ac5_kanal_ebene_nie_gesetzt_folgt_grundauswahl(report_type):
    """AC-5: ohne Telegram-Ebene folgt die Tabelle der Grundauswahl (Folge der
    Grundauswahl, Windrichtung Einfach in W, Kappung auf sieben Spalten)."""
    bubbles = _bubbles(_dc(_trip_dict(None)), report_type)
    assert _koepfe(bubbles) == ["G", "T", "PR", "W", "TH", "CT", "R"], bubbles


@pytest.mark.parametrize("report_type", REPORT_TYPES)
def test_ac5_kanal_ebene_leer_keine_tabelle(report_type):
    """AC-5: leere Telegram-Ebene -> keine Metrik-Tabelle, keine Metrik-Zeilen."""
    bubbles = _bubbles(_dc(_trip_dict([])), report_type)
    assert _tabelle(bubbles) is None, bubbles
    assert _kuerzel_folge(bubbles) == [], bubbles


@pytest.mark.parametrize("report_type", REPORT_TYPES)
def test_ac5_kanal_ebene_gesetzt_genau_diese_auswahl(report_type):
    """AC-5: gesetzte Telegram-Ebene -> genau diese Auswahl in dieser Folge."""
    tg = [_mc("precipitation", 0), _mc("temperature", 1), _mc("gust", 2)]
    bubbles = _bubbles(_dc(_trip_dict(tg)), report_type)
    assert _koepfe(bubbles) == ["R", "T", "G"], bubbles


# ---------------------------------------------------------------------------
# AC-7: zwei Nutzer, beide Aufrufreihenfolgen (Trip)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("reihenfolge", ["ab", "ba"])
def test_ac7_trip_zwei_nutzer_je_eigene_telegram_nachricht(reihenfolge):
    """AC-7: zwei Nutzer, unterschiedliche Folge und Format; jede Nachricht zeigt
    nur die eigene Auswahl, unabhaengig von der Aufrufreihenfolge."""
    a = _dc(_trip_dict([_mc("gust", 0), _mc("cloud_total", 1, "raw")]), frisches_profil())
    b = _dc(_trip_dict([_mc("cloud_total", 0, "symbol"), _mc("precipitation", 1),
                        _mc("gust", 2)]), frisches_profil())
    folge = [("a", a), ("b", b)] if reihenfolge == "ab" else [("b", b), ("a", a)]
    ist = {}
    for name, dc in folge:
        bubbles = _bubbles(dc)
        ist[name] = (_koepfe(bubbles), _spalte(bubbles, "CT"))
    assert ist == {"a": (["G", "CT"], {"70"}), "b": (["CT", "R", "G"], {"⛅"})}, ist


# ---------------------------------------------------------------------------
# AC-8: Quelle ist der Resolver, nicht get_metrics_for_channel("telegram", ...)
# ---------------------------------------------------------------------------

class _AbweichendesModell(UnifiedWeatherDisplayConfig):
    """Echte Unterklasse (kein Mock): ``get_metrics_for_channel("telegram", ...)``
    liefert bewusst eine ANDERE Liste als der Resolver (Altpfad-Signatur).
    Der Resolver liest die Kaskade ueber ``trip_channel_metrics`` und sieht die
    Abweichung nicht; folgt die Nachricht ihr, liest der Trip-Pfad noch den Altpfad."""

    def get_metrics_for_channel(self, channel, report_type):
        echt = super().get_metrics_for_channel(channel, report_type)
        if channel != "telegram":
            return echt
        return [MetricConfig(metric_id="humidity", enabled=True, order=0),
                MetricConfig(metric_id="uv_index", enabled=True, order=1)]


@pytest.mark.parametrize("report_type", REPORT_TYPES)
def test_ac8_trip_telegram_folgt_resolver_nicht_altpfad(report_type):
    """AC-8: Resolver-Liste (G, R, T) und Altpfad (HU, UV) weichen ab -- die
    Telegram-Nachricht folgt der Resolver-Liste."""
    from services.channel_list_resolver import resolve_channel_lists

    dc = _dc(_trip_dict([_mc("gust", 0), _mc("precipitation", 1), _mc("temperature", 2)]))
    abw = _AbweichendesModell(**{f.name: getattr(dc, f.name) for f in dataclasses.fields(dc)})
    # ``temperature_night`` (Abspaltung beim Laden, #1484) hat keine eigene Spalte.
    soll = [KUERZEL[z.metric_id]
            for z in resolve_channel_lists(abw, "trip", report_type).telegram
            if z.enabled and z.metric_id in KUERZEL]
    assert soll == ["G", "R", "T"], "Vorbedingung: Resolver-Liste"
    bubbles = _bubbles(abw, report_type)
    assert _koepfe(bubbles) == soll, bubbles
    assert _kuerzel_folge(bubbles) == soll, _kurzuebersicht(bubbles)


# ---------------------------------------------------------------------------
# Fix-Runde 1 (Adversary F001/F002): Quelle ist der UNKOLLABIERTE dc, und die
# Telegram-Kanal-Ebene wird nicht ein zweites Mal kaskadiert.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("report_type", REPORT_TYPES)
def test_f001_email_ebene_schmaler_als_telegram_ebene(report_type):
    """F001: E-Mail-Ebene [gust], Telegram-Ebene [gust, temperature, wind] --
    die Telegram-Tabelle zeigt alle Telegram-Metriken in Telegram-Folge (die
    Kollabierung auf die E-Mail-Auswahl darf Telegram nicht beschneiden)."""
    d = _trip_dict([_mc("gust", 0), _mc("temperature", 1), _mc("wind", 2)])
    d["display_config"]["channel_layouts"]["email"] = [_mc("gust", 0)]
    bubbles = _bubbles(_dc(d), report_type)
    assert _koepfe(bubbles) == ["G", "T", "W"], bubbles
    assert _kuerzel_folge(bubbles) == ["G", "T", "W"], _kurzuebersicht(bubbles)


#: Telegram-Layout-Eintraege mit abweichendem bucket (gust secondary, Grundauswahl
#: primary) und abweichender Folge (gust zuerst gespeichert).
def _tg_bucket_folge() -> list[dict]:
    gust = _mc("gust", 0)
    gust["bucket"] = "secondary"
    return [gust, _mc("temperature", 0), _mc("wind", 1)]


@pytest.mark.parametrize("report_type", REPORT_TYPES)
def test_f002_per_channel_layout_bucket_und_folge(report_type):
    """F002: Telegram-Ebene in ``channel_layouts`` mit gust als secondary --
    Spalten folgen der Resolver-Liste (T, W, G); bucket aus der Grundauswahl,
    die Kanal-Ebene wird nicht erneut kaskadiert."""
    bubbles = _bubbles(_dc(_trip_dict(_tg_bucket_folge())), report_type)
    assert _koepfe(bubbles) == ["T", "W", "G"], bubbles


# ---------------------------------------------------------------------------
# Adapter telegram_metric_configs (AC-3, AC-8)
# ---------------------------------------------------------------------------

def _grund_dc() -> UnifiedWeatherDisplayConfig:
    return UnifiedWeatherDisplayConfig(trip_id="t3098", metrics=[
        MetricConfig(metric_id="gust", enabled=True, bucket="primary", order=0, sms_threshold=50.0),
        MetricConfig(metric_id="wind", enabled=True, bucket="secondary", order=1),
        MetricConfig(metric_id="cloud_total", enabled=True, bucket="primary", order=2,
                     format_mode="symbol"),
        MetricConfig(metric_id="wind_direction", enabled=True, bucket="primary", order=3),
    ])


def test_adapter_folge_enabled_unbekannt():
    """Adapter: Resolver-Folge bleibt, nur ``enabled``-Zeilen, unbekannte IDs
    uebersprungen, ``enabled=True`` erzwungen."""
    from output.renderers.email.helpers import telegram_metric_configs
    from services.channel_list_resolver import ChannelRow

    rows = (
        ChannelRow("wind_direction", True, None, 0),
        ChannelRow("gibt_es_nicht", True, None, 1),
        ChannelRow("wind", False, None, 2),
        ChannelRow("gust", True, None, 3),
    )
    ist = telegram_metric_configs(rows, _grund_dc())
    assert [mc.metric_id for mc in ist] == ["wind_direction", "gust"]
    assert all(mc.enabled for mc in ist)


def test_adapter_bucket_order_schwelle_aus_grundauswahl():
    """Adapter: ``bucket``/``order``/``sms_threshold`` kommen aus der Grundauswahl
    (``ChannelRow`` traegt sie nicht); die Sortierung nach bucket/order in
    ``render_for_channel`` ergibt die Resolver-Folge."""
    from output.renderers.channel_layout import render_for_channel
    from output.renderers.email.helpers import telegram_metric_configs
    from services.channel_list_resolver import ChannelRow

    rows = (ChannelRow("cloud_total", True, None, 0), ChannelRow("gust", True, None, 1))
    ist = {mc.metric_id: mc for mc in telegram_metric_configs(rows, _grund_dc())}
    assert ist["gust"].sms_threshold == 50.0
    assert ist["gust"].bucket == "primary" and ist["cloud_total"].bucket == "primary"
    dc = dataclasses.replace(_grund_dc(), metrics=telegram_metric_configs(rows, _grund_dc()))
    # Grundauswahl: gust order 0, cloud_total order 2 -- die Resolver-Folge
    # (cloud_total vor gust) muss trotzdem die Tabellenfolge sein.
    spalten = render_for_channel("telegram", dc, "evening").table_columns
    assert spalten == ["cloud_total", "gust"], spalten


@pytest.mark.parametrize("fmt,soll_mode,soll_friendly", [
    (None, "symbol", True),          # Katalog-Standard: MetricConfig unveraendert
    ("raw", "raw", False),
    ("simplified", "simplified", True),
])
def test_adapter_format_zurueckschreiben(fmt, soll_mode, soll_friendly):
    """Adapter (AC-3): ``None`` laesst das Quell-MetricConfig unveraendert (nicht
    Roh), ``raw`` -> format_mode raw + use_friendly_format falsch, sonst format_mode."""
    from output.renderers.email.helpers import telegram_metric_configs
    from services.channel_list_resolver import ChannelRow

    (mc,) = telegram_metric_configs((ChannelRow("cloud_total", True, fmt, 0),), _grund_dc())
    assert mc.format_mode == soll_mode
    assert mc.use_friendly_format is soll_friendly


def test_adapter_format_none_ohne_format_mode_bleibt_none():
    """Adapter: ohne Format und ohne format_mode im Quell-Eintrag bleibt
    format_mode ``None`` (Katalog-Standard), nicht ``raw``."""
    from output.renderers.email.helpers import telegram_metric_configs
    from services.channel_list_resolver import ChannelRow

    (mc,) = telegram_metric_configs((ChannelRow("wind_direction", True, None, 0),), _grund_dc())
    assert mc.format_mode is None and mc.use_friendly_format is True


# ---------------------------------------------------------------------------
# AC-6 / AC-7: Orte-Telegram (Versand und Vorschau), DE/EN, zwei Nutzer
# ---------------------------------------------------------------------------

def _orte_liste(aktiv: list[dict]) -> list[dict]:
    """Telegram-Liste im Speicherformat des Editors: die aktiven Zeilen vorn, die
    uebrigen Groessen der Grundauswahl ausdruecklich abgewaehlt (der Editor
    speichert jede Zeile; nicht genannte Groessen haengt Orte sonst hinten an)."""
    from tests.tdd.test_3047_runde7_orte_kanaele import GRUND

    genannt = {z["metric_id"] for z in aktiv}
    return copy.deepcopy(aktiv) + [{"metric_id": m, "enabled": False}
                                   for m, _ in GRUND if m not in genannt]


#: Telegram-Liste der Orte: eigene Folge, Roh/Einfach/ohne Angabe gemischt.
ORTE_TG = [
    {"metric_id": "precipitation", "enabled": True},
    {"metric_id": "wind_direction", "enabled": True, "format": "simplified"},
    {"metric_id": "cloud_total", "enabled": True, "format": "raw"},
    {"metric_id": "gust", "enabled": True},
]


def _orte_vorschau(p: dict, uid: str) -> str:
    from services.compare_preview_service import ComparePreviewService
    from tests.tdd._compare_kette_fixtures import TARGET_DATE

    return ComparePreviewService().render_all_channels(
        p["id"], user_id=uid, target_date=TARGET_DATE)["telegram"]


def _orte_zellen(tg: str) -> list[str]:
    return wertezeilen(ortsbloecke(tg)["Innsbruck"])[0]


def _pruefe_orte_zellen(zellen: list[str], tg: str) -> None:
    """Folge R, Windrichtung (Einfach: Kompass), Wolken (Roh: Prozent), Boeen."""
    assert len(zellen) == 4, tg
    regen, richtung, wolken, boeen = zellen
    assert re.search(r"\d", regen), f"Regen: {regen}"
    assert richtung.endswith(" W") and not re.search(r"\d", richtung), f"Windrichtung Einfach: {richtung}"
    assert wolken.endswith(" 35%"), f"Wolken Roh: {wolken}"
    assert re.search(r"\d", boeen), f"Boeen: {boeen}"


@pytest.mark.parametrize("lang", ["de", "en"])
def test_ac6_orte_telegram_versand_folge_und_format(mit, lang):
    """AC-6: Versand -- Spalten/Folge/Darstellung = Telegram-Auswahl (zwei Nutzer)."""
    p = preset({"telegram": _orte_liste(ORTE_TG)})
    for _uid, snap in zwei_nutzer(mit, p, lang=lang):
        tg = text(snap, "telegram")
        _pruefe_orte_zellen(_orte_zellen(tg), tg)


@pytest.mark.parametrize("lang", ["de", "en"])
def test_ac6_orte_telegram_vorschau_gleich_versand(mit, lang):
    """AC-6: Vorschau und Versand derselben Konfiguration zeigen dieselben Zellen."""
    from tests.tdd._compare_kette_fixtures import nutzer_anlegen, orte_anlegen, preset_ablegen

    p = preset({"telegram": _orte_liste(ORTE_TG)})
    (uid, snap), _ = zwei_nutzer(mit, p, lang=lang)
    versand = _orte_zellen(text(snap, "telegram"))
    neu = nutzer_anlegen("premium")
    _sprache(neu, lang)
    orte_anlegen(neu)
    preset_ablegen(neu, copy.deepcopy(p))
    vorschau = _orte_zellen(_orte_vorschau(p, neu))
    assert vorschau == versand


def test_ac6_orte_ohne_format_angabe_bleibt_roh(mit):
    """AC-6: ohne Format-Angabe zeigt Orte-Telegram Roh (Windrichtung in Grad)."""
    p = preset({"telegram": _orte_liste([{"metric_id": "wind_direction", "enabled": True},
                                         {"metric_id": "gust", "enabled": True}])})
    for _uid, snap in zwei_nutzer(mit, p):
        tg = text(snap, "telegram")
        assert _orte_zellen(tg)[0].endswith(" 250 °"), tg


@pytest.mark.parametrize("reihenfolge", ["ab", "ba"])
def test_ac7_orte_zwei_nutzer_je_eigene_auswahl(mit, reihenfolge):
    """AC-7 (Orte): zwei Nutzer mit unterschiedlicher Folge/Format; jede
    Telegram-Nachricht zeigt nur die eigene Auswahl, beide Reihenfolgen."""
    pa = preset({"telegram": _orte_liste([
        {"metric_id": "gust", "enabled": True},
        {"metric_id": "cloud_total", "enabled": True, "format": "raw"}])})
    pb = preset({"telegram": _orte_liste([
        {"metric_id": "cloud_total", "enabled": True, "format": "simplified"},
        {"metric_id": "precipitation", "enabled": True}])})
    folge = [("a", pa), ("b", pb)] if reihenfolge == "ab" else [("b", pb), ("a", pa)]
    for name, p in folge:
        for _uid, snap in zwei_nutzer(mit, p):
            zellen = _orte_zellen(text(snap, "telegram"))
            assert len(zellen) == 2, zellen
            if name == "a":
                assert re.search(r"\d", zellen[0]) and zellen[1].endswith(" 35%"), zellen
            else:
                assert not re.search(r"\d", zellen[0]) and re.search(r"\d", zellen[1]), zellen


# ---------------------------------------------------------------------------
# AC-9: eigene Fallliste im Pruefkatalog
# ---------------------------------------------------------------------------

def _fallliste_telegram() -> dict:
    pfad = REPO_ROOT / "tests" / "fixtures" / "einstellung_gleich_mail" / "fallliste_telegram.json"
    assert pfad.is_file(), f"Fallliste fehlt: {pfad}"
    return json.loads(pfad.read_text(encoding="utf-8"))


def test_ac9_waechter_kennt_fallliste_telegram():
    """AC-9: der Waechter laedt ``fallliste_telegram.json`` mit (registriert) und
    findet Verweise auf diese Testdatei."""
    from tests.tdd import test_einstellung_gleich_mail_fallliste as w

    assert "telegram" in w.TEILDATEIEN
    assert "tests/tdd/test_3098_*.py" in w.PY_TEST_GLOBS
    geladen = w.lade_falllisten(w.FALLLISTEN_DIR)
    assert "fallliste_telegram.json" in geladen


def test_ac9_fallliste_telegram_faelle_und_achsen():
    """AC-9: neue IDs (Praefix ``telegram-``), alle gruen, Telegram-Format, beide
    Kontexte, beide Sprachen, Aspekte Auswahl/Reihenfolge/Darstellung, Faelle
    zu #3063 (Kopf-Typ, Windrichtung Roh) in DE und EN."""
    faelle = _fallliste_telegram()["faelle"]
    ids = [f["id"] for f in faelle]
    assert ids and all(i.startswith("telegram-") for i in ids), ids
    assert all(f["status"] == "gruen" for f in faelle)
    assert all("telegram" in f["format"].split("+") for f in faelle)
    assert {f["kontext"] for f in faelle} >= {"trip", "orte"}
    aspekte = set()
    for f in faelle:
        aspekte |= set(f.get("aspekte") or []) | {f["pruefung"]}
    assert aspekte >= {"auswahl", "reihenfolge", "darstellung"}, aspekte
    for pflicht in ("telegram-kopf-typ-de", "telegram-kopf-typ-en",
                    "telegram-windrichtung-roh-de", "telegram-windrichtung-roh-en",
                    "telegram-windrichtung-einfach-de", "telegram-windrichtung-einfach-en"):
        assert pflicht in ids, pflicht
    assert any(i.startswith("telegram-orte-") for i in ids), ids
