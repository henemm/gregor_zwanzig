"""#3462: Test-Alarm-Beispielwerte über der Schwelle, jede Größe einmal.

Spec: docs/specs/modules/fix_3462_testalarm_beispielwerte.md (AC-1 bis AC-4; AC-5 ist Staging-E2E).

VERTRAG für den Developer (``services.alert_test_service``):
    S = Schwelle der Regel. Richtung je Summary-Feld aus dem Katalog: hat ein Kandidat
    in ``_METRICS`` cmp "unter" ⇒ fallend ("decrease"), sonst steigend ("increase").
    Betrag der Änderung immer 1.2·|S| (auch negative Schwellen, z. B. Kälte −25 °C).
    steigend: alt = 0 bei DELTA, sonst 0.8·S; neu = alt + 1.2·|S|.
    fallend:  neu = 0.8·S; alt = neu + 1.2·|S|.
    Gewitter (``thunder_level_max``): alt = 0, neu = min(3, max(2, ceil(1.2·S))).
    Einheit "%": neu ≤ 100, alt = max(0, neu - 1.2·S).
    Dedupe je angezeigter Bezeichnung ``get_alert_label(_resolve_metric_id(feld, richtung), "de")``,
    erste Regel gewinnt (Kälte- und Hitzeseite heißen beide „Temp“ ⇒ Temperatur genau einmal).

Kein Mock: echte Trip-/Vergleichsdateien im isolierten Datenbaum, echte Loader, echter
Renderer (``over_thr``) und die echte Kette Endpoint -> Baustein -> ``NotificationService``
bis zum geteilten Transport-Aufzeichner (einzige Naht, an der Kanalgrenze).
"""
from __future__ import annotations

import json
from collections import Counter

import pytest

from app.loader import get_data_dir
from tests.helpers.transport_mitschrift import aufzeichner_installieren
from tests.tdd import _handversand_fixtures as hv
from tests.tdd._compare_kette_fixtures import engine_naht, nutzer_anlegen, preset_laden, transport_einrichten
from tests.tdd.test_briefings_test_alert_endpoint import ALLE_VIER, _trip, _vergleich


def _regel(metric: str, kind: str, threshold: float) -> dict:
    return {"id": f"r-{metric}", "kind": kind, "metric": metric, "threshold": threshold,
            "severity": "warning", "enabled": True}


#: Alle drei Regelarten; Temperatur-Änderung/-Maximum/-Minimum tragen dieselbe Bezeichnung
#: „Temp“, Niederschlag-Summe/-Änderung dieselbe „Niedersch“ (Dedupe); Sicht und
#: Nullgradgrenze sind fallend.
TRIP_REGELN = [
    _regel("wind_gust", "absolute", 50.0),
    _regel("temperature_change", "delta", 6.0),
    _regel("visibility", "threshold_crossing", 1000.0),
    _regel("thunder_level", "absolute", 1.0),
    _regel("temperature_max", "absolute", 30.0),
    _regel("temperature_min", "absolute", 5.0),
    _regel("precipitation_sum", "absolute", 10.0),
    _regel("precipitation_change", "delta", 7.0),
    _regel("freezing_level", "absolute", 400.0),
]
#: Je Bezeichnung genau einmal (erste Regel gewinnt): Temperatur-Änderung (temp_min_c, fallend
#: ⇒ Kälteseite) gewinnt vor Maximum und Minimum, Niederschlag-Summe vor -Änderung.
TRIP_ERWARTETE_METRIKEN = ["gust", "temperature_cold", "visibility", "thunder", "precipitation",
                           "freezing_level"]


# --------------------------------------------------------------------------- Helfer


def _service(uid: str):
    from services.alert_test_service import AlertTestService

    return AlertTestService(user_id=uid)


def _trip_laden(uid: str, tid: str):
    from app.loader import load_all_trips

    return next(t for t in load_all_trips(user_id=uid) if t.id == tid)


def _standard_vergleich(uid: str, **kw) -> str:
    """Vergleich OHNE ``metric_alert_levels`` und OHNE ``active_metrics``: alle Standard-
    metriken des Presets sind Alarm-Metriken (Legacy-Pfad ``display_config=None``)."""
    return _vergleich(uid, display_config={"hourly_metrics": []}, **kw)


def _metrik(c) -> str:
    from output.renderers.alert.project import _resolve_metric_id

    return _resolve_metric_id(c.metric, c.direction)


def _bezeichnung(c) -> str:
    from app.metric_catalog import get_alert_label

    return get_alert_label(_metrik(c), "de")


def _ereignis(c):
    """Echtes ``AlertEvent`` der Beispiel-Änderung (Katalog-Metrik und -cmp wie die Projektion)."""
    from app.metric_catalog import get_cmp
    from output.renderers.alert.model import AlertEvent

    mid = _metrik(c)
    return AlertEvent(metric_id=mid, value_from=c.old_value, value_to=c.new_value,
                      threshold=c.threshold, cmp=get_cmp(mid), occurred_at=None, km_from=0.0, km_to=0.0)


def _trip_aenderungen(uid: str, regeln) -> list:
    return _service(uid).beispiel_aenderungen(_trip_laden(uid, _trip(uid, rules=regeln)))


def _vergleich_aenderungen(uid: str) -> list:
    return _service(uid).beispiel_aenderungen(preset_laden(uid, _standard_vergleich(uid)))


def _sprache_setzen(uid: str, lang: str) -> None:
    pfad = get_data_dir(uid) / "user.json"
    pfad.write_text(json.dumps({**json.loads(pfad.read_text()), "language": lang}))


def _unter_texte(lang: str) -> list[str]:
    """Die „unter"-Urteilsformen des Katalogs in ``lang`` (Einzel-Urteil, Seitenangabe, Kurzform)."""
    from i18n import t

    unter = t("alarm.abweichung.unter", lang)
    urteil = t("alarm.abweichung.urteil", lang, pfeil="", seite=unter, schwelle="").split("(")[0].strip()
    seite = t("alarm.abweichung.seite_schwelle", lang, seite=unter, schwelle="", mark="").strip()
    return [urteil, seite, t("alarm.abweichung.unter_schwelle", lang)]


def _ueber_urteil(lang: str) -> str:
    from i18n import t

    seite = t("alarm.abweichung.ueber", lang)
    return t("alarm.abweichung.urteil", lang, pfeil="", seite=seite, schwelle="").split("(")[0].strip()


@pytest.fixture
def mit(monkeypatch):
    transport_einrichten(monkeypatch)
    engine_naht(monkeypatch)
    return aufzeichner_installieren(monkeypatch)


def _test_alarm(kind: str, lang: str, regeln=TRIP_REGELN) -> tuple[str, list]:
    """Test-Alarm über den echten Endpoint an alle vier Kanäle; (uid, Beispiel-Änderungen)."""
    uid = nutzer_anlegen()
    _sprache_setzen(uid, lang)
    if kind == "route":
        eid = _trip(uid, override=ALLE_VIER, rules=regeln)
        changes = _service(uid).beispiel_aenderungen(_trip_laden(uid, eid))
    else:
        eid = _standard_vergleich(uid, override=ALLE_VIER)
        changes = _service(uid).beispiel_aenderungen(preset_laden(uid, eid))
    r = hv.client().post(f"/api/briefings/{eid}/test-alert", params={"user_id": uid, "kind": kind})
    assert r.status_code == 200, r.text
    return uid, changes


def _texte(mit) -> dict[str, list[str]]:
    return {
        "email": [s["plain_text_body"] or "" for s in mit.sendungen("email")]
        + [s["body"] or "" for s in mit.sendungen("email")],
        "telegram": [s["body"] or "" for s in mit.sendungen("telegram")],
        "sms": [s["body"] or "" for s in mit.sendungen("sms")],
        "premium_sms": [s["body"] or "" for s in mit.sendungen("premium_sms")],
    }


def _ereigniszeilen(plain: str, lang: str) -> list[str]:
    """Datenzeilen der Mehr-Ereignis-Mail: enden auf das Seitenwort oder tragen „unter Schwelle"."""
    from i18n import t

    ueber, unter_kurz = t("alarm.abweichung.ueber", lang), t("alarm.abweichung.unter_schwelle", lang)
    return [z for z in plain.splitlines() if z.endswith(f" {ueber}") or f" · {unter_kurz}:" in z]


# --------------------------------------------------------------------------- AC-1


def test_ac1_trip_alle_drei_regelarten_jede_beispiel_aenderung_ueber_der_schwelle():
    from output.renderers.alert.model import over_thr

    changes = _trip_aenderungen(nutzer_anlegen(), TRIP_REGELN)

    assert changes, "kein Beispiel erzeugt"
    unter = [(c.metric, c.old_value, c.new_value, c.threshold) for c in changes if not over_thr(_ereignis(c))]
    assert unter == [], f"Renderer urteilt „unter“: {unter}"


def test_ac1_vergleich_standardmetriken_jede_beispiel_aenderung_ueber_der_schwelle():
    from output.renderers.alert.model import over_thr

    changes = _vergleich_aenderungen(nutzer_anlegen())

    assert changes, "kein Beispiel erzeugt"
    unter = [(c.metric, c.old_value, c.new_value, c.threshold) for c in changes if not over_thr(_ereignis(c))]
    assert unter == [], f"Renderer urteilt „unter“: {unter}"


def test_ac1_rueckfall_ohne_aktive_regel_boeen_40_auf_100_ueber_der_schwelle():
    from output.renderers.alert.model import over_thr

    changes = _trip_aenderungen(nutzer_anlegen(), [{**TRIP_REGELN[0], "enabled": False}])

    assert [(c.metric, c.old_value, c.new_value, c.threshold, c.direction) for c in changes] == [
        ("gust_max_kmh", pytest.approx(40.0), pytest.approx(100.0), 50.0, "increase"),
    ], changes
    assert over_thr(_ereignis(changes[0])), changes[0]


def test_ac1_negative_schwelle_kaelte_minus_25_betrag_1_2_mal_abs_s():
    """Kälte-Regel mit negativer Schwelle: fallend, neu = 0.8·S = −20, alt = neu + 1.2·|S| = 10."""
    changes = _trip_aenderungen(nutzer_anlegen(), [_regel("temperature_min", "absolute", -25.0)])

    assert [(c.metric, c.old_value, c.new_value, c.direction) for c in changes] == [
        ("temp_min_c", pytest.approx(10.0), pytest.approx(-20.0), "decrease"),
    ], changes


# --------------------------------------------------------------------------- AC-2


@pytest.mark.parametrize("lang", ["de", "en"])
@pytest.mark.parametrize("kind", ["route", "vergleich"])
def test_ac2_vier_kanaele_nie_unter_urteil_alle_ereignisse_ueber(mit, kind, lang):
    from i18n import t

    _uid, changes = _test_alarm(kind, lang)

    texte = _texte(mit)
    assert all(texte[k] for k in texte), f"nicht alle vier Kanäle bedient: {mit}"
    for kanal, bodies in texte.items():
        for verboten in _unter_texte(lang):
            treffer = [b for b in bodies if verboten in b]
            assert not treffer, (kanal, lang, verboten, treffer)
    bloecke = 1 if kind == "route" else 2
    zeilen = _ereigniszeilen(texte["email"][0], lang)
    ueber = t("alarm.abweichung.ueber", lang)
    assert len(zeilen) == len(changes) * bloecke and all(z.endswith(f" {ueber}") for z in zeilen), zeilen
    kopf = t("alarm.abweichung.ueber_schwelle", lang, n=len(changes))
    assert all(kopf in tg.splitlines()[0] for tg in texte["telegram"]), (kopf, texte["telegram"])


@pytest.mark.parametrize("lang", ["de", "en"])
def test_ac2_einzel_ereignis_urteil_ueber_deiner_alarm_schwelle(mit, lang):
    """Rückfall (eine Änderung) rendert das Einzel-Urteil ``alarm.abweichung.urteil``."""
    _uid, changes = _test_alarm("route", lang, regeln=[])

    assert len(changes) == 1, changes
    texte = _texte(mit)
    assert all(texte[k] for k in texte), f"nicht alle vier Kanäle bedient: {mit}"
    for kanal, bodies in texte.items():
        for verboten in _unter_texte(lang):
            assert not [b for b in bodies if verboten in b], (kanal, lang, verboten, bodies)
    assert _ueber_urteil(lang) in texte["email"][0], (_ueber_urteil(lang), texte["email"][0])


# --------------------------------------------------------------------------- AC-3


def test_ac3_trip_je_bezeichnung_hoechstens_eine_aenderung():
    changes = _trip_aenderungen(nutzer_anlegen(), TRIP_REGELN)

    assert [_metrik(c) for c in changes] == TRIP_ERWARTETE_METRIKEN, [
        (c.metric, c.direction, _metrik(c)) for c in changes]
    zaehlung = Counter(_bezeichnung(c) for c in changes)
    assert not {b: n for b, n in zaehlung.items() if n > 1}, zaehlung


def test_ac3_vergleich_standard_je_bezeichnung_hoechstens_eine_aenderung():
    from app.metric_catalog import get_alert_label

    changes = _vergleich_aenderungen(nutzer_anlegen())

    zaehlung = Counter(_bezeichnung(c) for c in changes)
    doppelt = {b: n for b, n in zaehlung.items() if n > 1}
    assert not doppelt, f"Bezeichnung mehrfach: {doppelt} in {[(c.metric, c.direction) for c in changes]}"
    assert zaehlung[get_alert_label("temperature", "de")] == 1, zaehlung
    assert zaehlung[get_alert_label("precipitation", "de")] == 1, zaehlung


@pytest.mark.parametrize("kind", ["route", "vergleich"])
def test_ac3_temperatur_minimum_beispiel_faellt(kind):
    uid = nutzer_anlegen()
    changes = _trip_aenderungen(uid, TRIP_REGELN) if kind == "route" else _vergleich_aenderungen(uid)

    temp_min = [c for c in changes if c.metric == "temp_min_c"]
    assert len(temp_min) == 1, [(c.metric, c.direction) for c in changes]
    c = temp_min[0]
    assert c.direction == "decrease" and c.new_value < c.old_value, c
    assert _metrik(c) == "temperature_cold", c


@pytest.mark.parametrize("lang", ["de", "en"])
@pytest.mark.parametrize("kind", ["route", "vergleich"])
def test_ac3_gerenderte_mail_je_block_jede_bezeichnung_hoechstens_einmal(mit, kind, lang):
    """Je Block (Etappe bzw. Ort) erscheint jede Bezeichnung höchstens einmal, Temperatur genau
    einmal (Kälte- und Hitzeseite tragen im Katalog dieselbe Kurzbezeichnung „Temp“)."""
    from app.metric_catalog import get_alert_label

    _test_alarm(kind, lang)

    zeilen = _ereigniszeilen(_texte(mit)["email"][0], lang)
    schluessel = Counter(tuple(z.split(" · ")[:2]) for z in zeilen)
    assert not {k: n for k, n in schluessel.items() if n > 1}, zeilen
    temp = get_alert_label("temperature", lang)
    bloecke = 1 if kind == "route" else 2
    assert len([z for z in zeilen if temp in z.split(" · ")[:2]]) == bloecke, zeilen


# --------------------------------------------------------------------------- AC-4


def test_ac4_gewitter_mindestens_maessig_sicht_faellt_prozent_in_0_bis_100():
    from app.metric_catalog import get_metric
    from app.models import AlertMetric
    from services.alert_preset import ONSET_METRICS

    alle = [_regel(m.value, "absolute", 1.0 if m == AlertMetric.THUNDER_LEVEL else 50.0)
            for m in AlertMetric if m.value not in ONSET_METRICS]
    changes = _trip_aenderungen(nutzer_anlegen(), TRIP_REGELN + alle)

    je_feld = {c.metric: c for c in changes}
    gewitter, sicht = je_feld["thunder_level_max"], je_feld["visibility_min_m"]
    assert gewitter.old_value == 0 and gewitter.new_value == 2, gewitter
    assert sicht.new_value < sicht.old_value and sicht.direction == "decrease", sicht
    prozent = [c for c in changes if get_metric(_metrik(c)).unit == "%"]
    assert all(0 <= c.old_value <= 100 and 0 <= c.new_value <= 100 for c in prozent), prozent


@pytest.mark.parametrize("lang", ["de", "en"])
@pytest.mark.parametrize("kind", ["route", "vergleich"])
def test_ac4_gerendert_gewitter_bezeichnung_nie_luftmasse_sicht_faellt(mit, kind, lang):
    from app.metric_catalog import get_alert_label
    from i18n import t

    _test_alarm(kind, lang)

    texte = _texte(mit)
    luftmasse = t("alarm.abweichung.luftmasse", lang)
    for kanal in ("email", "telegram"):
        assert not [b for b in texte[kanal] if luftmasse in b], (kanal, texte[kanal])
    zeilen = _ereigniszeilen(texte["email"][0], lang)
    gewitter = [z for z in zeilen if get_alert_label("thunder", lang) in z.split(" · ")[:2]]
    sicht = [z for z in zeilen if get_alert_label("visibility", lang) in z.split(" · ")[:2]]
    bloecke = 1 if kind == "route" else 2
    assert len(gewitter) == bloecke, zeilen
    assert len(sicht) == bloecke and all("↓" in z for z in sicht), sicht
