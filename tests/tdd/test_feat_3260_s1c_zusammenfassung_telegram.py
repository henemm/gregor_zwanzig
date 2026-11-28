"""#3260 Schritt 1, Scheibe C: Kurz-Zusammenfassung und Orte-Telegram.

SPEC: docs/specs/modules/feat_3260_s1c_zusammenfassung_telegram.md
(AC-1.5, AC-1.6, AC-1.7, AC-4, AC-5, AC-6), ADR-0127.

Kern-Schicht ohne Netz und ohne ``Mock()``/``patch()``:

* Kurz-Zusammenfassung ueber den ECHTEN ``CompactSummaryFormatter`` -- derselbe
  Satz steht im HTML-Kopf, im Nur-Text und in der Telegram-Kurzfassung der
  Trip-Mail (``trip_report._generate_compact_summary``).
* Orte-Telegram ueber den ECHTEN Versandweg (``send_one_compare_preset`` ->
  ``NotificationService`` -> Transport-Mitschrift). Einzige Naht ist das
  Wetter: die Werte der Wetter-Naht bekommen eine Windrichtung (225 Grad), die
  sonst fehlt.

Erwartungen stehen von Hand im Test (Stufenwoerter, Himmelsrichtung, Wortlaut)
und importieren nichts aus Katalog oder Renderer.
"""
from __future__ import annotations

import dataclasses
import re
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pytest

import tests.helpers.einstellung_gleich_mail_orte as orte_helfer
from app.models import ForecastDataPoint, SegmentWeatherSummary, ThunderLevel
from tests.helpers.einstellung_gleich_mail_orte import ORTSNAMEN
from tests.tdd.test_einstellung_gleich_mail_orte_tabelle import (  # noqa: F401  (Fixture)
    AN, mit, preset, senden,
)

UTC = timezone.utc
TZ = ZoneInfo("UTC")


# ---------------------------------------------------------------------------
# Kurz-Zusammenfassung: Bausteine
# ---------------------------------------------------------------------------

def _dp(stunde: int, *, wind: float = 40.0, boe: float = 45.0,
        gewitter=ThunderLevel.NONE, hagel=None, signale=None) -> ForecastDataPoint:
    dp = ForecastDataPoint(
        ts=datetime(2026, 10, 29, stunde, 0, tzinfo=UTC), t2m_c=10.0, wind10m_kmh=wind,
        gust_kmh=boe, precip_1h_mm=0.0, cloud_total_pct=60, thunder_level=gewitter,
        wind_chill_c=7.0, wind_direction_deg=225.0,
    )
    dp.hail_flag = hagel
    dp.thunder_level_signals = signale
    return dp


def _summary() -> SegmentWeatherSummary:
    return SegmentWeatherSummary(
        temp_min_c=8.0, temp_max_c=14.0, wind_max_kmh=40.0, gust_max_kmh=45.0,
        precip_sum_mm=0.0, cloud_avg_pct=60, wind_chill_min_c=5.0, wind_chill_max_c=9.0,
        wind_direction_avg_deg=225,
    )


def _satz(lang: str, hourly, *, ids: list[str], friendly: bool) -> str:
    from app.models import MetricConfig, UnifiedWeatherDisplayConfig
    from output.renderers.compact_summary import CompactSummaryFormatter

    dc = UnifiedWeatherDisplayConfig(
        trip_id="t", metrics=[MetricConfig(metric_id=i, enabled=True, use_friendly_format=friendly)
                              for i in ids])
    return CompactSummaryFormatter().format_weather_summary(
        _summary(), hourly, "Lienz", dc, TZ, report_type="morning", lang=lang)


def _gewitter_stunden(stufe: ThunderLevel, *, hagel=True, signale=("cape",)):
    return ([_dp(h) for h in range(6, 9)]
            + [_dp(h, gewitter=stufe, hagel=hagel, signale=list(signale)) for h in range(9, 12)]
            + [_dp(h) for h in range(12, 16)])


#: Gewitter-Teil der Zusammenfassung, von Hand (Stufenwort + Zeitfenster).
GEWITTER_SOLL = {
    ("de", "MED"): "Gewitter mittel 9:00–12:00 · CAPE · Hagel: ja",
    ("de", "HIGH"): "Gewitter hoch 9:00–12:00 · CAPE · Hagel: ja",
    ("en", "MED"): "Thunderstorm medium 9:00–12:00 · CAPE · Hail: yes",
    ("en", "HIGH"): "Thunderstorm high 9:00–12:00 · CAPE · Hail: yes",
}
VERBOTEN = ("⚡ möglich", "Gewitter möglich", "⚡ possible", "Thunderstorm possible")

GEWITTER_IDS = ["temperature", "cloud_total", "wind", "gust", "thunder"]


# ---------------------------------------------------------------------------
# AC-1.5 / AC-4: Gewitter-Stufenwort, unabhaengig vom Umschalter
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("lang", ["de", "en"])
@pytest.mark.parametrize("stufe", ["MED", "HIGH"])
def test_ac15_ac4_gewitter_stufenwort_gleich_bei_roh_und_einfach(lang, stufe):
    """AC-1.5/AC-4: Gewitter mittel/hoch -> „Gewitter <Stufe> hh:00–hh:00“
    (EN „Thunderstorm <level>“) bei Roh UND Einfach, identischer Satz, kein
    „⚡ möglich“/„Gewitter möglich“."""
    stunden = _gewitter_stunden(getattr(ThunderLevel, stufe))
    roh = _satz(lang, stunden, ids=GEWITTER_IDS, friendly=False)
    einfach = _satz(lang, stunden, ids=GEWITTER_IDS, friendly=True)
    soll = GEWITTER_SOLL[(lang, stufe)]
    assert soll in roh, roh
    assert soll in einfach, einfach
    gew_roh = roh[roh.index(soll.split(" ")[0]):]
    gew_einfach = einfach[einfach.index(soll.split(" ")[0]):]
    assert gew_roh == gew_einfach == soll, (gew_roh, gew_einfach)
    for alt in VERBOTEN:
        assert alt not in roh and alt not in einfach, (alt, roh, einfach)


@pytest.mark.parametrize("lang,soll", [
    ("de", "Instabile Luftmasse (leicht) 9:00–10:00"),
    ("en", "Unstable air mass (light) 9:00–10:00"),
])
@pytest.mark.parametrize("friendly", [False, True])
def test_ac4_gewitter_leicht_bleibt_luftmassen_aussage(lang, soll, friendly):
    """AC-4: Gewitter der Stufe leicht zeigt weiter die Luftmassen-Aussage
    (#2176), bei Roh und Einfach."""
    stunden = ([_dp(h) for h in range(6, 9)]
               + [_dp(9, gewitter=ThunderLevel.LOW, signale=["cape"])]
               + [_dp(h) for h in range(10, 16)])
    satz = _satz(lang, stunden, ids=GEWITTER_IDS, friendly=friendly)
    assert soll in satz, satz
    for alt in VERBOTEN:
        assert alt not in satz, (alt, satz)


# ---------------------------------------------------------------------------
# AC-1.6 / AC-5: Windrichtung haengt nur an der Auswahl
# ---------------------------------------------------------------------------

WIND_SOLL = {"de": "starker Wind SW 40 km/h", "en": "strong wind SW 40 km/h"}
WIND_OHNE = {"de": "starker Wind 40 km/h", "en": "strong wind 40 km/h"}


@pytest.mark.parametrize("lang", ["de", "en"])
def test_ac16_windrichtung_bei_wind_roh_wie_bei_einfach(lang):
    """AC-1.6: Windrichtung in der Auswahl -> Kompass „SW“ (225 Grad) bei
    Wind auf Roh genauso wie auf Einfach."""
    ids = ["temperature", "wind", "gust", "wind_direction"]
    stunden = [_dp(h) for h in range(6, 16)]
    roh = _satz(lang, stunden, ids=ids, friendly=False)
    einfach = _satz(lang, stunden, ids=ids, friendly=True)
    assert WIND_SOLL[lang] in einfach, einfach
    assert WIND_SOLL[lang] in roh, roh


@pytest.mark.parametrize("lang", ["de", "en"])
@pytest.mark.parametrize("friendly", [False, True])
def test_ac5_ohne_windrichtung_in_der_auswahl_kein_kompass(lang, friendly):
    """AC-5: Windrichtung vorhanden, aber nicht gewaehlt -> keine
    Himmelsrichtung, egal ob Wind auf Roh oder Einfach."""
    satz = _satz(lang, [_dp(h) for h in range(6, 16)],
                 ids=["temperature", "wind", "gust"], friendly=friendly)
    assert WIND_OHNE[lang] in satz, satz
    assert not re.search(r"\bSW\b", satz), satz


# ---------------------------------------------------------------------------
# AC-1.7 / AC-6: Orte-Telegram, Vorlage Radtour
# ---------------------------------------------------------------------------

@pytest.fixture
def mit_windrichtung(mit, monkeypatch):  # noqa: F811
    """Wetter-Naht: jede Stunde und jeder Ort mit Windrichtung 225 Grad (SW)."""
    original = orte_helfer._ergebnis_je_ort

    def je_ort():
        aus = {}
        for lid, r in original().items():
            stunden = [dataclasses.replace(p, wind_direction_deg=225.0) for p in r.hourly_data]
            aus[lid] = dataclasses.replace(r, hourly_data=stunden, wind_direction_avg=225)
        return aus

    monkeypatch.setattr(orte_helfer, "_ergebnis_je_ort", je_ort)
    return mit


def _radtour_preset(mit_richtung: bool) -> dict:
    grund = [("temperature", "max"), ("wind", "max"), ("gust", "max")]
    if mit_richtung:
        grund.insert(2, ("wind_direction", "avg"))
    zeilen = [{"metric_id": m, "places": AN,
               "formats": {"email": "raw", "telegram": "simplified"}} for m, _ in grund]
    p = preset(zeilen, grund=grund)
    p["display_config"]["ampel"] = {"template": "radtour"}
    return p


#: Telegram-Beschriftungen (DE, von Hand); Werte koennen mehrwortig sein
#: („Böen sehr stark@16“), daher Trennung an der bekannten Beschriftung.
_TG_ZELLE = re.compile(r"^(Temp max|Windrichtung|Wind|Böen) (.+)$")


def _tg_zellen(tg: str) -> dict[str, dict[str, str]]:
    """Telegram -> {Ort: {Beschriftung: Wert}} (erste Zeile des Ortsblocks)."""
    aus: dict[str, dict[str, str]] = {}
    aktuell = None
    for z in tg.splitlines():
        if z in ORTSNAMEN:
            aktuell = aus.setdefault(z, {})
        elif aktuell is not None and z.startswith("   ") and not aktuell:
            for zelle in z.strip().split(" · "):
                m = _TG_ZELLE.match(zelle)
                if m:
                    aktuell[m.group(1)] = m.group(2)
    return aus


def test_ac17_radtour_telegram_windrichtung_ohne_stunden_marke(mit_windrichtung):
    """AC-1.7: Vorlage Radtour, Windrichtung in Telegram auf Einfach ->
    Windrichtung „SW“ ohne ``@hh``; Wind und Boeen (gelb oder schlechter)
    behalten ihre Stunden-Marke."""
    tg = senden(mit_windrichtung, _radtour_preset(True))["telegram"]
    zellen = _tg_zellen(tg)
    assert set(zellen) == set(ORTSNAMEN), tg
    for ort, z in zellen.items():
        assert z.get("Windrichtung") == "SW", f"{ort}: {z} -- {tg}"
        assert re.search(r"@\d{2}$", z["Wind"]), f"{ort}: Wind ohne Marke {z}"
        assert re.search(r"@\d{2}$", z["Böen"]), f"{ort}: Böen ohne Marke {z}"


@pytest.mark.parametrize("reihenfolge", ["a_zuerst", "b_zuerst"])
def test_ac6_zwei_nutzer_windrichtung_ohne_marke_keine_fremddaten(mit_windrichtung,
                                                                  reihenfolge):
    """AC-6: Nutzer A (Radtour, Wind + Windrichtung Einfach) und Nutzer B
    (ohne Windrichtung). A: Wind mit Marke, Windrichtung ohne; B: keine
    Windrichtung. Jede Sendung geht an den eigenen Nutzer, keine Fremdkennung."""
    from tests.tdd._compare_kette_fixtures import nutzer_anlegen

    uid_a, uid_b = nutzer_anlegen("premium"), nutzer_anlegen("premium")
    assert uid_a != uid_b and "default" not in (uid_a, uid_b)
    auftraege = [(uid_a, True), (uid_b, False)]
    if reihenfolge == "b_zuerst":
        auftraege.reverse()
    aus = {uid: senden(mit_windrichtung, _radtour_preset(r), uid=uid) for uid, r in auftraege}

    for ort, z in _tg_zellen(aus[uid_a]["telegram"]).items():
        assert z.get("Windrichtung") == "SW", f"A {ort}: {z}"
        assert re.search(r"@\d{2}$", z["Wind"]), f"A {ort}: Wind ohne Marke {z}"
    for ort, z in _tg_zellen(aus[uid_b]["telegram"]).items():
        assert "Windrichtung" not in z, f"B {ort}: {z}"
    assert aus[uid_a]["uid"] == uid_a and aus[uid_b]["uid"] == uid_b
    for eigen, fremd in ((uid_a, uid_b), (uid_b, uid_a)):
        for teil in ("html", "plain", "telegram"):
            assert fremd not in aus[eigen][teil], f"{teil} von {eigen} nennt {fremd}"
