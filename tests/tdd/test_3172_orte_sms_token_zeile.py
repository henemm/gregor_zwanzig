"""Orte-SMS in der Token-Zeile der Trip-SMS (Issue #3172, ADR-0125).

SPEC: docs/specs/modules/feat_3172_orte_sms_token_zeile.md (AC-1 bis AC-8)

RED vor der Umstellung, warum: die Orte-SMS schreibt je Ort die alte Zellform
(``Aabenraa D 19C W 43 km/h ... +21``) statt der Token-Zeile der Trip-SMS
(``O1 D9/16 W13@11 G31@12 R- PR53%@13 TH:-``).

PO-Entscheidungen 2026-11-19 (Nachtrag zu ADR-0125, "jedes Zeichen ist
kostbar"): keine Ortsnamen, kein Kopf, kein Datum -- die Orte heissen ``O1``,
``O2``, ... wie die Etappen der Trip-SMS (Stelle in der Reihenfolge des Abos),
ohne Doppelpunkt, durch ein Leerzeichen getrennt; Grenze 160 Zeichen wie die
Trip-SMS, die Premium-SMS rendert ueber 153 Zeichen neu (Regel #3100).

Alle Faelle laufen ueber den echten Versandweg ``compare_kanaltexte_rendern``
(Kontext wie ``placements_view_service._orte_muster``); keine Mocks. Die
Paritaet (AC-1) wird unabhaengig gegengebaut: dieselben Werte gehen direkt als
``NormalizedForecast`` in ``build_token_line`` -- mit derselben Abo-Ampel.
"""
from __future__ import annotations

import json
import re
import uuid
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

import pytest

from app.ampel import profile_for_template, resolve_ampel, template_id_for
from app.models import ForecastDataPoint, ThunderLevel
from app.user import ComparisonResult, LocationResult, SavedLocation
from output.renderers.channel_layout import CHANNEL_LIMITS
from output.tokens.builder import build_token_line
from output.tokens.dto import DailyForecast, HourlyValue, MetricSpec, NormalizedForecast
from services import compare_briefing_aufbau as aufbau
from services import placements_beispiel as pb
from services.official_alerts.models import OfficialAlert
from services.report_config_resolver import resolve_compare_render_options
from utils.timezone import to_utc

ZONE = ZoneInfo("Europe/Berlin")
TAG = date(2026, 7, 14)
STUNDEN = range(9, 17)
SMS_MAX = 160  # wie die Trip-SMS (format_sms max_length=160)
PREMIUM_MAX = CHANNEL_LIMITS["premium_sms"]["max_chars"]

#: SMS-Spalte von AC-1 (Frontend-Schluessel der Orte-Auswahl).
AC1_AUSWAHL = ["temp_max_c", "temp_min_c", "wind_max_kmh", "gust_max_kmh",
               "precip_sum_mm", "pop_max_pct", "thunder_level_max"]
#: Abo-Ampel mit tiefer Wind-Gelbgrenze -- beweist, dass die Ampel DES ABOS wirkt.
ABO_AMPEL = {"template": "allgemein",
             "metrics": {"wind": {"upper": {"yellow": 12, "orange": 40, "red": 60}}}}


# ---------------------------------------------------------------------------
# Bausteine
# ---------------------------------------------------------------------------

def _ort(name: str, *, ort_id: str | None = None) -> SavedLocation:
    return SavedLocation(id=ort_id or name.lower().replace(" ", "-"), name=name,
                         lat=54.5, lon=9.5, elevation_m=10, timezone="Europe/Berlin")


def _ts(stunde: int) -> datetime:
    return to_utc(datetime(TAG.year, TAG.month, TAG.day, stunde, tzinfo=ZONE))


def _punkte(basis: dict, spitzen: dict | None = None) -> list[ForecastDataPoint]:
    """Stundenwerte 09-16 Uhr Ortszeit: ``basis`` je Feld, ``spitzen`` je Feld
    ``{stunde: wert}`` ueberschreibt einzelne Stunden."""
    spitzen = spitzen or {}
    return [
        ForecastDataPoint(ts=_ts(h), **{
            feld: spitzen.get(feld, {}).get(h, wert) for feld, wert in basis.items()})
        for h in STUNDEN
    ]


def _ergebnis(ort: SavedLocation, punkte: list, **felder) -> LocationResult:
    temps = [p.t2m_c for p in punkte if p.t2m_c is not None]
    return LocationResult(
        location=ort, hourly_data=punkte,
        temp_max=max(temps) if temps else None, temp_min=min(temps) if temps else None,
        **felder,
    )


def _vergleich(orte: list[LocationResult]) -> ComparisonResult:
    return ComparisonResult(locations=orte, time_window=(9, 16), target_date=TAG,
                            created_at=datetime(2026, 7, 14, 4, 0))


def _kontext(result: ComparisonResult, dc: dict | None = None, *, report_type=None) -> dict:
    """Kontext wie ``placements_view_service._orte_muster``."""
    preset = {"id": "p3172", "name": "Test",
              "location_ids": [r.location.id for r in result.locations],
              "display_config": dc or {}}
    return {"preset": preset, "result": result,
            "profile": profile_for_template(template_id_for(preset)),
            "opts": resolve_compare_render_options(preset, report_type=report_type),
            "name": "Test", "target_date": result.target_date}


def _sms(kontext: dict, lang: str = "de") -> str:
    return aufbau.compare_kanaltexte_rendern(kontext, lang=lang)[0]


def _ortsteile(sms: str) -> list[str]:
    """Ortsteile ``O{n} {Token}`` (ohne ``+k Orte``/``X?``); die SMS beginnt
    direkt mit ``O1`` (kein Kopf)."""
    assert sms.startswith("O1"), sms
    rumpf = re.sub(r"( \+\d+ Orte)?( X\?)?$", "", sms)
    return re.split(r" (?=O\d+(?: |$))", rumpf)


def _teil(sms: str, nummer: int) -> str:
    """Ortsteil ``O{nummer} ...`` (1-basierte Stelle in der Reihenfolge des Abos)."""
    treffer = [t for t in _ortsteile(sms) if t.startswith(f"O{nummer} ") or t == f"O{nummer}"]
    assert treffer, f"Ort O{nummer} fehlt in der SMS: {sms!r}"
    return treffer[0]


def _token(teil: str) -> list[str]:
    """Token eines Ortsteils (ohne ``O{n}``, ohne Warnblock)."""
    return [t for t in teil.split(" ")[1:] if t and not t.startswith("!")]


def _beispiel_orte(n: int) -> list[SavedLocation]:
    namen = ["Aabenraa", "Flensburg", "Schleswig", "Garmisch-Partenkirchen", "Bad Toelz"]
    return [SavedLocation(id=f"o{i}", name=nm, lat=47.27, lon=11.39, elevation_m=600)
            for i, nm in enumerate(namen[:n])]


# ---------------------------------------------------------------------------
# AC-1 -- Paritaet mit build_token_line, Abo-Ampel wirkt
# ---------------------------------------------------------------------------

#: (Name, Temperatur-Basis, Spitzen je Feld) -- drei Orte, Wind/Boeen bei Kiel
#: ueber Gelb der Abo-Ampel, Regen und Gewitter bei Sylt.
AC1_ORTE = [
    ("Kiel", {"t2m_c": (9.0, {16: 16.0}), "wind10m_kmh": (8.0, {11: 13.0}),
              "gust_kmh": (20.0, {12: 31.0}), "pop_pct": (20, {13: 53}),
              "precip_1h_mm": (0.0, {}), "thunder_level": (ThunderLevel.NONE, {})}),
    ("Sankt Peter-Ording", {"t2m_c": (8.0, {15: 15.0}), "wind10m_kmh": (9.0, {}),
                            "gust_kmh": (18.0, {}), "pop_pct": (10, {}),
                            "precip_1h_mm": (0.0, {}), "thunder_level": (ThunderLevel.NONE, {})}),
    ("Sylt", {"t2m_c": (7.0, {14: 14.0}), "wind10m_kmh": (10.0, {}),
              "gust_kmh": (15.0, {}), "pop_pct": (25, {}),
              "precip_1h_mm": (0.0, {13: 1.5}), "thunder_level": (ThunderLevel.NONE, {15: ThunderLevel.LOW})}),
]


def _ac1_punkte(felder: dict) -> list[ForecastDataPoint]:
    return _punkte({f: b for f, (b, _s) in felder.items()},
                   {f: s for f, (_b, s) in felder.items()})


def _reihe(felder: dict, feld: str) -> dict[int, object]:
    basis, spitzen = felder[feld]
    return {h: spitzen.get(h, basis) for h in STUNDEN}


def _erwartete_token(felder: dict, ampel: dict) -> str:
    """Unabhaengiger Gegenbau: dieselben Werte direkt in den Token-Baukasten."""
    temp = _reihe(felder, "t2m_c")
    tief = min(temp, key=lambda h: (temp[h], h))
    hoch = max(temp, key=lambda h: (temp[h], -h))
    stufe = {ThunderLevel.NONE: 0, ThunderLevel.LOW: 1, ThunderLevel.MED: 2, ThunderLevel.HIGH: 3}

    def _proben(feld, umrechnen=float):
        return tuple(HourlyValue(h, umrechnen(v)) for h, v in _reihe(felder, feld).items()
                     if umrechnen(v) > 0)

    heute = DailyForecast(
        temp_min_c=temp[tief], temp_max_c=temp[hoch],
        temp_min_hour=tief, temp_max_hour=hoch,
        wind_hourly=_proben("wind10m_kmh"), gust_hourly=_proben("gust_kmh"),
        pop_hourly=_proben("pop_pct"), rain_hourly=_proben("precip_1h_mm"),
        thunder_hourly=_proben("thunder_level", lambda v: float(stufe[v])),
    )
    specs = [MetricSpec(sym, position=i) for i, sym in
             enumerate(["D", "L", "W", "G", "R", "PR", "TH:"])]
    zeile = build_token_line(NormalizedForecast(days=(heute,)), specs,
                             report_type="morning", stage_name="X", ampel=ampel)
    return " ".join(t.render() for t in zeile.tokens)


def _ac1_kontext() -> dict:
    orte = [_ergebnis(_ort(name), _ac1_punkte(felder)) for name, felder in AC1_ORTE]
    return _kontext(_vergleich(orte), {"active_metrics": AC1_AUSWAHL, "ampel": ABO_AMPEL})


def test_ac1_ortsteil_ist_die_token_zeile_von_build_token_line():
    kontext = _ac1_kontext()
    ampel = resolve_ampel(kontext["preset"])
    sms = _sms(kontext)

    assert not sms.startswith("Orte") and "14.07." not in sms, f"kein Kopf: {sms}"
    assert len(sms) <= SMS_MAX, (len(sms), sms)
    teile = _ortsteile(sms)
    assert len(teile) == 3, sms
    for nummer, (teil, (_name, felder)) in enumerate(zip(teile, AC1_ORTE), start=1):
        assert teil == f"O{nummer} {_erwartete_token(felder, ampel)}", (teil, sms)


def test_ac1_hervorhebung_folgt_der_abo_ampel():
    sms = _sms(_ac1_kontext())
    kiel = _token(_teil(sms, 1))
    # Wind 13 km/h liegt nur nach der Abo-Ampel (Gelb ab 12) ueber Gelb.
    assert kiel == ["D9/16", "W13@11", "G31@12", "R-", "PR53%@13", "TH:-"], sms
    sylt = _token(_teil(sms, 3))
    assert sylt == ["D7/14", "W-", "G-", "R1.5@13", "PR-", "TH:L@15"], sms


def test_ac1_keine_ortsnamen_nur_nummern():
    """PO 2026-11-19: Orte stehen als ``O1``, ``O2``, ... -- kein Ortsname,
    kein Doppelpunkt, kein ``; `` in der SMS."""
    sms = _sms(_ac1_kontext())
    for name, _felder in AC1_ORTE:
        assert name not in sms, sms
    assert ";" not in sms and not re.search(r"O\d+:", sms), sms
    assert [t.split(" ", 1)[0] for t in _ortsteile(sms)] == ["O1", "O2", "O3"], sms


# ---------------------------------------------------------------------------
# AC-2 -- keine alte Zellform, keine negative Null, Windrichtung als Sektor
# ---------------------------------------------------------------------------

_ALTE_ZELLE = re.compile(
    r"(?:^| )(?:D|L|FD|FL|W|G|R|PR|TH|WD|SU|CT|UV|VS|SD|NS|FZ|HU|DP|HP|SL|PT|CL|CM|CH)"
    r" [-\d]")


@pytest.mark.parametrize("tief,hoch", [(-0.4, -0.1), (-0.5, 0.0), (-0.2, 0.4)])
@pytest.mark.parametrize("auswahl", [
    None,
    ["temp_min_c", "temp_max_c", "wind_direction_deg", "wind_max_kmh", "wind_chill_min_c",
     "wind_chill_max_c"],
])
def test_ac2_keine_alte_zellform_keine_negative_null(tief, hoch, auswahl):
    basis = {"t2m_c": tief, "wind_chill_c": tief - 0.0, "wind10m_kmh": 10.0,
             "gust_kmh": 18.0, "wind_direction_deg": 330, "precip_1h_mm": 0.0,
             "pop_pct": 10, "thunder_level": ThunderLevel.NONE, "cloud_total_pct": 40,
             "visibility_m": 20000, "uv_index": 1.0}
    orte = [
        _ergebnis(_ort("Kiel"), _punkte(basis, {"t2m_c": {14: hoch}, "wind_chill_c": {14: hoch}}),
                  wind_direction_avg=330, wind_chill_min=tief, wind_chill_max=hoch),
        _ergebnis(_ort("Husum"), _punkte(basis, {"t2m_c": {12: hoch}}),
                  wind_direction_avg=330, wind_chill_min=tief, wind_chill_max=tief),
    ]
    dc = {} if auswahl is None else {"active_metrics": auswahl}
    sms = _sms(_kontext(_vergleich(orte), dc))

    for teil in _ortsteile(sms):
        assert " km/h" not in teil and "°" not in teil, sms
        assert not re.search(r"-?\d+C\b", teil), sms
        assert not _ALTE_ZELLE.search(teil), sms
        assert not re.search(r" [+?]\d+(?: |$)", teil), f"Zaehler +N/?N: {sms}"
        assert not re.search(r"(?<![\d.])-0(?![\d.])", teil), f"negative Null: {sms}"
    if auswahl is not None:
        assert "WD:NW" in _token(_teil(sms, 1)), sms


# ---------------------------------------------------------------------------
# AC-3 -- "-" = geprueft und unauffaellig, "?" = kein Wert
# ---------------------------------------------------------------------------

def test_ac3_strich_fuer_unauffaellig_fragezeichen_fuer_fehlenden_wert():
    voll = _punkte({"t2m_c": 15.0, "wind10m_kmh": 9.0, "pop_pct": 20, "gust_kmh": 15.0})
    luecke = _punkte({"gust_kmh": 15.0, "t2m_c": None, "wind10m_kmh": None, "pop_pct": None})
    orte = [_ergebnis(_ort("Kiel"), voll), _ergebnis(_ort("Husum"), luecke)]
    sms = _sms(_kontext(_vergleich(orte),
                        {"active_metrics": ["temp_max_c", "wind_max_kmh", "pop_max_pct"]}))

    assert _token(_teil(sms, 1)) == ["D15", "W-", "PR-"], sms
    assert _token(_teil(sms, 2)) == ["D?", "W?", "PR?"], sms


def test_ac3_ohne_stundenwerte_steht_fragezeichen_nicht_strich():
    orte = [_ergebnis(_ort("Kiel"), _punkte({"t2m_c": 15.0, "wind10m_kmh": 9.0})),
            LocationResult(location=_ort("Husum"), temp_max=14.0, wind_max=8.0)]
    sms = _sms(_kontext(_vergleich(orte), {"active_metrics": ["temp_max_c", "wind_max_kmh"]}))
    assert _token(_teil(sms, 2)) == ["D14", "W?"], sms


# ---------------------------------------------------------------------------
# AC-4 -- Kuerzung: gleich viele Listenzeilen, dann erst " +k Orte"
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("anzahl", [1, 3, 5])
def test_ac4_volle_liste_gleich_viele_zeilen_je_ort(anzahl):
    sms = _sms(_kontext(pb.orte_ergebnis(_beispiel_orte(anzahl))))
    assert len(sms) <= SMS_MAX, (len(sms), sms)
    assert "+" not in sms.replace("NS24+", ""), f"kein +N/+k Orte erwartet: {sms}"
    assert "Aabenraa" not in sms and "Garmisch" not in sms, sms
    teile = _ortsteile(sms)
    assert [t.split(" ", 1)[0] for t in teile] == [f"O{i}" for i in range(1, anzahl + 1)], sms
    if anzahl == 1:
        assert sms.startswith("O1 D"), sms
        return
    assert len(teile) == anzahl, sms
    folgen = [[re.match(r"[A-Z+:]+", t).group(0) for t in _token(teil)] for teil in teile]
    assert all(f == folgen[0] for f in folgen), f"ungleiche Zeilenzahl/Folge: {sms}"
    assert folgen[0][0] == "D", sms


def _viele_orte(n: int, *, warnung_bei: int | None = None, ausfall_bei: int | None = None):
    basis = {"t2m_c": 15.0, "wind10m_kmh": 9.0, "gust_kmh": 15.0, "pop_pct": 10,
             "precip_1h_mm": 0.0, "thunder_level": ThunderLevel.NONE}
    orte = []
    for i in range(n):
        alerts = []
        if i == warnung_bei:
            alerts = [OfficialAlert(source="meteoalarm", hazard="thunderstorm", level=4,
                                    label="Gewitter", valid_from=_ts(14), valid_to=_ts(18),
                                    region_label="Nordfriesland")]
        orte.append(_ergebnis(_ort(f"Ortschaft Nummer {i + 1}", ort_id=f"o{i}"), _punkte(basis),
                              official_alerts=alerts,
                              official_alerts_unavailable=(i == ausfall_bei)))
    return orte


def test_ac4_orte_entfallen_erst_bei_einer_zeile_warnort_bleibt_x_am_ende():
    orte = _viele_orte(16, warnung_bei=15, ausfall_bei=2)
    sms = _sms(_kontext(_vergleich(orte), {"active_metrics": AC1_AUSWAHL}))

    assert len(sms) <= SMS_MAX, (len(sms), sms)
    assert sms.endswith(" X?"), sms
    assert re.search(r" \+\d+ Orte X\?$", sms), f"Orts-Ueberlauf fehlt: {sms}"
    teile = _ortsteile(sms)
    for teil in teile:
        assert len(_token(teil)) == 1, f"vor dem Wegfall von Orten nur die erste Zeile: {sms}"
    gewarnt = _teil(sms, 16)
    assert "!" in gewarnt, f"Ort mit amtlicher Warnung muss sichtbar bleiben: {sms}"


def test_ac4_ohne_platzmangel_alle_orte_mit_allen_zeilen():
    orte = _viele_orte(2)
    sms = _sms(_kontext(_vergleich(orte), {"active_metrics": AC1_AUSWAHL}))
    for teil in _ortsteile(sms):
        assert _token(teil) == ["D15/15", "W-", "G-", "R-", "PR-", "TH:-"], sms


# ---------------------------------------------------------------------------
# AC-5 -- kein N/FN/TH+: bei Orten
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("report_type", ["morning", "evening"])
def test_ac5_kein_nachtwert_kein_folgetag(report_type):
    basis = {"t2m_c": 12.0, "wind_chill_c": 10.0, "thunder_level": ThunderLevel.NONE,
             "wind10m_kmh": 9.0}
    orte = [_ergebnis(_ort("Kiel"), _punkte(basis, {"thunder_level": {15: ThunderLevel.MED}}),
                      wind_chill_min=10.0, wind_chill_max=10.0),
            _ergebnis(_ort("Husum"), _punkte(basis))]
    kontext = _kontext(_vergleich(orte), {"active_metrics": [
        "temp_min_c", "temp_max_c", "wind_chill_min_c", "wind_chill_max_c",
        "thunder_level_max"]}, report_type=report_type)
    sms = _sms(kontext)

    for teil in _ortsteile(sms):
        token = _token(teil)
        assert not any(re.match(r"(N|FN)[-?\d]", t) for t in token), sms
        assert not any(t.startswith("TH+:") for t in token), sms
        assert sum(t.startswith("TH:") for t in token) == 1, sms
    assert "TH:M@15" in _token(_teil(sms, 1)), sms
    assert "TH:-" in _token(_teil(sms, 2)), sms


# ---------------------------------------------------------------------------
# AC-6 -- ein Ort, Fehler-Ort, lauter Orte ohne Daten
# ---------------------------------------------------------------------------

def test_ac6_ein_ort_heisst_o1_unter_dem_kopf_orte():
    """PO 2026-11-19: auch bei genau einem Ort ``O1`` ohne Kopf und ohne Namen."""
    orte = [_ergebnis(_ort("Sankt Peter-Ording"), _punkte({"t2m_c": 15.0, "wind10m_kmh": 9.0}))]
    sms = _sms(_kontext(_vergleich(orte), {"active_metrics": ["temp_max_c", "wind_max_kmh"]}))
    assert sms == "O1 D15 W-", sms


def test_ac6_fehler_ort_und_keine_daten():
    gut = _ergebnis(_ort("Kiel"), _punkte({"t2m_c": 15.0, "wind10m_kmh": 9.0}))
    kaputt = LocationResult(location=_ort("Husum"), error="Abruf gescheitert")
    dc = {"active_metrics": ["temp_max_c", "wind_max_kmh"]}

    assert _sms(_kontext(_vergleich([gut, kaputt]), dc)) == "O1 D15 W- O2 n/a"
    # Die Nummer zaehlt auch Orte ohne Daten: der Ort danach bleibt O3.
    dritter = _ergebnis(_ort("Sylt"), _punkte({"t2m_c": 14.0, "wind10m_kmh": 9.0}))
    assert _sms(_kontext(_vergleich([gut, kaputt, dritter]), dc)) == "O1 D15 W- O2 n/a O3 D14 W-"
    # Ohne Daten an jedem Ort: nur die Liste ``O{n} n/a`` (kein Sondertext).
    alle_kaputt = [kaputt, LocationResult(location=_ort("Sylt"), error="x")]
    assert _sms(_kontext(_vergleich(alle_kaputt), dc)) == "O1 n/a O2 n/a"
    assert _sms(_kontext(_vergleich([kaputt]), dc)) == "O1 n/a"


# ---------------------------------------------------------------------------
# AC-7 -- SMS, Premium-SMS, Telegram-Kurzstil: derselbe Text, sprachfest
# ---------------------------------------------------------------------------

def test_ac7_kurzstil_und_sms_identisch_in_beiden_sprachen():
    kontext = _kontext(pb.orte_ergebnis(_beispiel_orte(3)), {"telegram_style": "kurzform"})
    sms_de, tg_de = aufbau.compare_kanaltexte_rendern(kontext, lang="de")
    sms_en, tg_en = aufbau.compare_kanaltexte_rendern(kontext, lang="en")

    assert sms_de == tg_de == sms_en == tg_en, (sms_de, sms_en)
    assert re.match(r"O1 D\d+/\d+", sms_de), sms_de


@pytest.fixture
def premium_nutzer(tmp_path, monkeypatch):
    """Isolierte Datenwurzel und ein Premium-Nutzer (Muster
    ``test_compare_premium_sms_versand.py``), kein Netz."""
    from app import loader as app_loader

    data_root = tmp_path / "data"
    data_root.mkdir()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(app_loader, "_DATA_ROOT", str(data_root))
    for name, wert in {"GZ_ENV": "development", "GZ_SMTP_HOST": "smtp.invalid",
                       "GZ_MAIL_FROM": "gregor@example.invalid",
                       "GZ_SMS_GATEWAY_URL": "https://gateway.invalid/api/sms",
                       "GZ_SEVEN_API_KEY": "unbrauchbar"}.items():
        monkeypatch.setenv(name, wert)
    uid = f"pcmp-{uuid.uuid4().hex[:8]}"
    d = app_loader.get_data_dir(uid)
    d.mkdir(parents=True, exist_ok=True)
    (d / "user.json").write_text(json.dumps({
        "id": uid, "tier": "premium",
        "premium_sms_reply_to": "49157" + str(int(uuid.uuid5(uuid.NAMESPACE_OID, uid)))[:8],
        "premium_sms_reply_at": datetime.now(timezone.utc).isoformat(),
    }))
    return uid


def test_ac7_premium_sms_sendet_die_token_zeile(premium_nutzer):
    from app.config import Settings
    from services.notification_service import NotificationService

    kontext = _kontext(pb.orte_ergebnis(_beispiel_orte(3)))
    sms, _tg = aufbau.compare_kanaltexte_rendern(kontext, lang="en")
    gesehen: list[str] = []
    NotificationService(settings=Settings(), user_id=premium_nutzer).send_compare_report(
        subject="Orte", html_body="<p>H</p>", text_body="T", telegram_text="TG",
        sms_text=sms, recipients=["to@example.invalid"], effective_channels={"premium_sms"},
        premium_sms_sink=gesehen.append,
    )
    assert gesehen == [aufbau.compare_premium_sms_rendern(kontext, sms)], gesehen
    assert re.match(r"O1 D\d+/\d+", gesehen[0]), gesehen


def test_ac7_premium_sms_ueber_153_zeichen_neu_gekuerzt():
    """#3172 (Regel #3100 wie im Trip): passt die 160-Zeichen-SMS nicht in die
    153 Zeichen der Premium-SMS, kuerzt derselbe Renderer erneut vom
    Listenende; sonst ist die Premium-SMS der SMS-Text."""
    kontext = _kontext(pb.orte_ergebnis(_beispiel_orte(1)))
    sms = _sms(kontext)
    assert PREMIUM_MAX < len(sms) <= SMS_MAX, (len(sms), sms)
    premium = aufbau.compare_premium_sms_rendern(kontext, sms)
    assert len(premium) <= PREMIUM_MAX, (len(premium), premium)
    assert sms.startswith(premium), (premium, sms)
    kurz = _kontext(_vergleich([_ergebnis(_ort("Kiel"), _punkte({"t2m_c": 15.0}))]),
                    {"active_metrics": ["temp_max_c"]})
    kurz_sms = _sms(kurz)
    assert aufbau.compare_premium_sms_rendern(kurz, kurz_sms) == kurz_sms == "O1 D15"


# ---------------------------------------------------------------------------
# AC-8 -- Listenfolge, Abwahl, Einfach/Roh
# ---------------------------------------------------------------------------

def _ac8_sms(einfach: bool) -> str:
    basis = {"t2m_c": 15.0, "wind10m_kmh": 9.0, "gust_kmh": 15.0, "cloud_total_pct": 30}
    orte = [_ergebnis(_ort("Kiel"), _punkte(basis, {"cloud_total_pct": {13: 70}}),
                      cloud_avg=40)]
    dc = {"active_metrics": ["wind_max_kmh", "cloud_avg_pct", "temp_max_c", "gust_max_kmh"],
          "channel_layouts": {"sms": [
              {"metric_id": "gust"}, {"metric_id": "cloud_total", "use_friendly_format": einfach},
              {"metric_id": "temperature", "enabled": False}, {"metric_id": "wind"}]}}
    return _sms(_kontext(_vergleich(orte), dc))


def test_ac8_listenfolge_abwahl_und_einfach():
    sms = _ac8_sms(einfach=True)
    assert sms == "O1 G- CT:SCT@13 W-", sms


def test_ac8_roh_zeigt_die_zahl():
    sms = _ac8_sms(einfach=False)
    assert sms == "O1 G- CT70@13 W-", sms
