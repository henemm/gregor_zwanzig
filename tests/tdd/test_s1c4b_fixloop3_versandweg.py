"""Issue #2792 S1c-4b, Fix-Loop 3 (Adversary F001-F003, Koordinator-Entscheide).

SPEC: docs/specs/modules/feat_2792_s1_profil_ampel.md v1.5 (AC-1, AC-2, AC-7,
AC-15, AC-25; §5 Punkt 2 und 7). Protokoll:
docs/artifacts/feat-2792-s1c4b-umschalten/adversary-dialog.md.

Die Ampel muss auf dem ECHTEN Versand- und Vorschauweg ankommen, nicht nur am
Renderer: Vergleich ueber ``send_one_compare_preset`` und
``ComparePreviewService``, Trip ueber ``TripReportSchedulerService.
send_due_reports`` (Scheduler -> ``TripReportRequest`` -> ``NotificationService``
-> Formatter) und ``PreviewService.render_sms_preview``. Gemessen wird am
Transport-Aufzeichner (E-Mail, SMS, Premium-SMS, Telegram) bzw. an der
Vorschau-Antwort; Skitouren/Wintersport gegen Allgemein in beiden
Reihenfolgen. Naehte nur an Wetter (Fixture-Provider/Engine-Subklasse) und
Transport -- kein Mock-Theater.
"""
from __future__ import annotations

import copy
import json
import re

import pytest

from tests.helpers.einstellung_auslieferung_orakel import roh_wert_der_metrik
from tests.helpers.transport_mitschrift import aufzeichner_installieren
from tests.tdd._compare_kette_fixtures import (
    TARGET_DATE, briefing_senden, engine_naht, fixture_dict, nutzer_anlegen, orte_anlegen,
    preset_ablegen, settings_fuer, transport_einrichten,
)
from tests.tdd._einstellung_auslieferung_fixtures import TRANSPORT_ENV, frisches_profil, golden_dict
from tests.tdd.test_kanal_an_aus_kette import ROOT, _jetzt, _lauf, _trip_schreiben

# ---------------------------------------------------------------------------
# F001: Vergleichs-Versand und -Vorschau tragen die Vorlage des Presets
# ---------------------------------------------------------------------------

#: Vorlage im Preset auf beiden Wegen, die ein Nutzer speichern kann: Abo-Ampel
#: (Editor) und Compare-``profil`` (Altbestand, Prod ``henning/zillertal``).
_VERGLEICH_VORLAGEN = {
    "skitouren": lambda p: p["display_config"].__setitem__("ampel", {"template": "skitouren"}),
    "wintersport_profil": lambda p: p.__setitem__("profil", "WINTERSPORT"),
    "allgemein": lambda p: None,
}
_LABEL = {"skitouren": "Skitouren", "wintersport_profil": "Wintersport", "allgemein": "Allgemein"}


def _rot() -> str:
    from output.renderers.email.design_tokens import tone_css
    return f"background:{tone_css('red')[0]};"


def _vergleich_preset(vorlage: str) -> dict:
    p = copy.deepcopy(fixture_dict("basis"))
    _VERGLEICH_VORLAGEN[vorlage](p)
    return p


def _profil_kopfzelle(html: str) -> str:
    """Wert der Kopfzelle „Profil" der Vergleichs-Mail (AC-15)."""
    m = re.search(r">Profil</div[^>]*>\s*<div[^>]*>([^<]+)</div", html)
    assert m, "Vorbedingung: Kopfzelle 'Profil' fehlt"
    return m.group(1).strip()


def _vergleich_pruefen(vorlage: str, html: str) -> None:
    """Kopfzelle = Label der Vorlage; Temperatur 22/27 °C ist bei Skitouren/
    Wintersport rot getoent, bei Allgemein nicht (Uebersichtstabelle)."""
    assert _profil_kopfzelle(html) == _LABEL[vorlage], (vorlage, _profil_kopfzelle(html))
    rot = html.count(_rot())
    if vorlage == "allgemein":
        assert rot == 0, (vorlage, rot)
    else:
        assert rot >= 2, (vorlage, rot)


@pytest.fixture
def vergleich_env(monkeypatch):
    transport_einrichten(monkeypatch)
    engine_naht(monkeypatch)
    return aufzeichner_installieren(monkeypatch)


@pytest.mark.parametrize("abo", ["skitouren", "wintersport_profil"])
@pytest.mark.parametrize("zuerst_allgemein", [False, True], ids=["abo_zuerst", "allgemein_zuerst"])
def test_vergleichs_versand_traegt_die_vorlage_des_presets(vergleich_env, abo, zuerst_allgemein):
    """AC-15/AC-25: der geplante Versand (``send_one_compare_preset`` ->
    ``render_compare_email``) bewertet nach der Vorlage DES Presets -- in der
    tatsaechlich versendeten Mail."""
    folge = ["allgemein", abo] if zuerst_allgemein else [abo, "allgemein"]
    for vorlage in folge:
        uid = nutzer_anlegen("premium")
        orte_anlegen(uid)
        p = _vergleich_preset(vorlage)
        preset_ablegen(uid, p)
        vergleich_env.leeren()
        briefing_senden(uid, p["id"], settings_fuer(uid))
        _vergleich_pruefen(vorlage, vergleich_env.sendungen("email")[-1]["body"])


@pytest.mark.parametrize("abo", ["skitouren", "wintersport_profil"])
@pytest.mark.parametrize("zuerst_allgemein", [False, True], ids=["abo_zuerst", "allgemein_zuerst"])
def test_vergleichs_vorschau_traegt_die_vorlage_des_presets(vergleich_env, abo, zuerst_allgemein):
    """Spec §5 Punkt 2: Vorschau und Versand haben dieselbe Quelle --
    ``ComparePreviewService.render_all_channels`` zeigt dieselbe Bewertung."""
    from services.compare_preview_service import ComparePreviewService
    folge = ["allgemein", abo] if zuerst_allgemein else [abo, "allgemein"]
    for vorlage in folge:
        uid = nutzer_anlegen("premium")
        orte_anlegen(uid)
        p = _vergleich_preset(vorlage)
        preset_ablegen(uid, p)
        antwort = ComparePreviewService().render_all_channels(
            p["id"], user_id=uid, target_date=TARGET_DATE)
        _vergleich_pruefen(vorlage, antwort["email_html"])


# ---------------------------------------------------------------------------
# F002: Trip-Versand und -Vorschau tragen die Vorlage der display_config
# ---------------------------------------------------------------------------

#: Regen 1,5 mm je Stunde: Allgemein gelb ab 1 mm (erwaehnt), Skitouren erst
#: ab 2 mm (nicht erwaehnt). Boeen 35 km/h: Allgemein gelb ab 30, Skitouren ab 40.
_REGEN_MM, _BOEEN_KMH = 1.5, 35.0
_KURZKANAELE = ("sms", "premium_sms", "telegram_kurzform")


@pytest.fixture
def trip_env(monkeypatch, tmp_path):
    for k, v in TRANSPORT_ENV.items():
        monkeypatch.setenv(k, v)
    for datei in (ROOT / "fixtures" / "openmeteo").glob("*.json"):
        roh = json.loads(datei.read_text())
        for punkt in roh["data"]:
            punkt["precip_1h_mm"], punkt["gust_kmh"] = _REGEN_MM, _BOEEN_KMH
        (tmp_path / datei.name).write_text(json.dumps(roh))
    monkeypatch.setenv("GZ_TEST_FIXTURE_DIR", str(tmp_path))
    return aufzeichner_installieren(monkeypatch)


def _trip_dict(vorlage: str) -> dict:
    """Golden D (Morgen an, alle vier Kanaele) mit NUR ``preset_name`` (Spec
    v1.5 §5 Punkt 1/2: der Trip traegt seine Vorlage ueber die display_config)."""
    d = copy.deepcopy(golden_dict("golden_d"))
    d["display_config"]["preset_name"] = vorlage
    return d


def _trip_pruefen(vorlage: str, mail: str, kurz: dict[str, str | None]) -> None:
    allgemein = vorlage == "allgemein"
    for kanal, wert in kurz.items():
        assert wert is not None, (vorlage, kanal, "Regen-Token fehlt")
        erwaehnt = wert not in ("-", "?")
        assert erwaehnt == allgemein, (vorlage, kanal, wert)
        if allgemein:
            assert wert.startswith(f"{_REGEN_MM}@"), (vorlage, kanal, wert)
    assert bool(re.search(r"Regen ab \d\d:00", mail)) == allgemein, (vorlage, "Regen-Kachel")
    assert bool(re.search(r"Bo\w+ >30 km/h ab", mail)) == allgemein, (vorlage, "Boeen-Kachel")


@pytest.mark.parametrize("zuerst_allgemein", [False, True], ids=["skitouren_zuerst", "allgemein_zuerst"])
def test_trip_versand_bewertet_alle_vier_kanaele_nach_der_vorlage(trip_env, zuerst_allgemein):
    """AC-1/AC-2/AC-25: geplanter Versand (``send_due_reports``) eines Trips
    mit ``preset_name`` „skitouren" -- Mail, SMS, Premium-SMS und Telegram
    bewerten nach Skitouren (Regen 1,5 mm nicht erwaehnt), der Allgemein-Trip
    nach Allgemein (erwaehnt). Gemessen an den vier Transport-Ausgaengen."""
    folge = ["allgemein", "skitouren"] if zuerst_allgemein else ["skitouren", "allgemein"]
    for vorlage in folge:
        d = _trip_dict(vorlage)
        uid = frisches_profil()
        _trip_schreiben(uid, d["report_config"], basis=d)
        trip_env.leeren()
        _lauf(uid, _jetzt(6))
        assert set(trip_env.kanaele) == {"email", "sms", "premium_sms", "telegram"}, trip_env.kanaele
        kurz = {k: roh_wert_der_metrik(trip_env, k, "precipitation") for k in _KURZKANAELE}
        _trip_pruefen(vorlage, trip_env.sendungen("email")[-1]["body"], kurz)


@pytest.mark.parametrize("zuerst_allgemein", [False, True], ids=["skitouren_zuerst", "allgemein_zuerst"])
def test_premium_sms_ausgang_unterscheidet_skitouren_von_allgemein(trip_env, zuerst_allgemein):
    """Zusatz (Koordinator): direkt am Premium-SMS-Ausgang -- der tatsaechlich
    gesendete Premium-SMS-Text eines Skitouren-Trips ist ein anderer als der
    eines Allgemein-Trips (Regen-Token ``R-`` gegen ``R1.5@…``)."""
    texte = {}
    folge = ["allgemein", "skitouren"] if zuerst_allgemein else ["skitouren", "allgemein"]
    for vorlage in folge:
        d = _trip_dict(vorlage)
        uid = frisches_profil()
        _trip_schreiben(uid, d["report_config"], basis=d)
        trip_env.leeren()
        _lauf(uid, _jetzt(6))
        sendungen = trip_env.sendungen("premium_sms")
        assert len(sendungen) == 1, sendungen
        texte[vorlage] = sendungen[0]["body"]
    regen = {v: next(t for t in texte[v].split() if t.startswith("R")) for v in texte}
    assert regen["skitouren"] == "R-", texte
    assert regen["allgemein"].startswith(f"R{_REGEN_MM}@"), texte


@pytest.mark.parametrize("zuerst_allgemein", [False, True], ids=["skitouren_zuerst", "allgemein_zuerst"])
def test_trip_vorschau_bewertet_nach_der_vorlage_wie_der_versand(trip_env, zuerst_allgemein):
    """Spec §5 Punkt 2: die Vorschau (``PreviewService.render_sms_preview``)
    bewertet wie der Versand nach der Vorlage des Trips. Ohne ``demo``: derselbe
    Provider-Weg wie der Versand (Offline-Naht ``GZ_TEST_FIXTURE_DIR``); ``demo``
    laese die festen Repo-Fixtures und saehe den kontrollierten Regen nicht."""
    from app.loader import load_trip, save_trip
    from services.preview_service import PreviewService
    folge = ["allgemein", "skitouren"] if zuerst_allgemein else ["skitouren", "allgemein"]
    for vorlage in folge:
        uid = frisches_profil()
        trip = load_trip(_trip_dict(vorlage), user_id=uid)
        save_trip(trip, uid)
        _betreff, sms = PreviewService().render_sms_preview(
            trip.id, user_id=uid, report_type="morning")
        regen = next(t for t in sms.split() if t.startswith("R"))
        if vorlage == "allgemein":
            assert regen.startswith(f"R{_REGEN_MM}@"), (vorlage, sms)
        else:
            assert regen == "R-", (vorlage, sms)


# ---------------------------------------------------------------------------
# F003: Gleichstand im Schlimmsten -> frueheste Stunde
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("reihenfolge", ["zeitlich", "umgekehrt"])
def test_gleichstand_im_schlimmsten_waehlt_die_frueheste_stunde(reihenfolge):
    """35 @8, 50 @10, 50 @12 (Allgemein-Boeen: 35 gelb, 50 orange, gleich
    schlimm) -> Klammer ``(50@10)``, nie ``(50@12)``; unabhaengig von der
    Eingabereihenfolge. SMS-Token und Ausblick gleich."""
    from output.renderers.email.helpers import format_trend_tokens
    from tests.tdd.test_s1c4b_fixloop1_findings import _ampel, _hv, _sms_token
    paare = [(8, 35.0), (10, 50.0), (12, 50.0)]
    if reihenfolge == "umgekehrt":
        paare.reverse()
    allg = _ampel("allgemein")
    assert _sms_token("G", "gust_hourly", _hv(*paare), allg) == "35@8(50@10)"
    assert format_trend_tokens({"hourly_gust": _hv(*paare)}, ampel=allg)["gust_token"] == "35@8(50@10)"


def test_gleichstand_in_der_wind_kachel_waehlt_die_frueheste_stunde():
    """Mail-Kachel und SMS derselben Sendung: Wind 35 @8, 50 @10, 50 @12 ->
    Kachel „max 50 (10:00)", SMS ``W35@8(50@10)``."""
    from tests.tdd.test_s1c4b_fixloop2_findings import _kachel, _sendung
    wind = {8: 35.0, 10: 50.0, 12: 50.0}
    rep = _sendung("allgemein", lambda h: {"wind10m_kmh": wind.get(h, 12.0)})
    text, _ton = _kachel(rep.email_html, "Wind")
    assert text == "Wind >30 km/h ab 08:00 · max 50 (10:00)", text
    assert "W35@8(50@10)" in rep.sms_text.split(), rep.sms_text
