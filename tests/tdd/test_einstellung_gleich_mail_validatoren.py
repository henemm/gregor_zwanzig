"""Einstellung = Mail: Validatoren mit ``--konfig`` (Issue #3047, Paket C).

SPEC: docs/specs/modules/feat_3047_einstellung_gleich_mail_pruefkatalog.md
(§6, AC-11 Validator-Teil, AC-19, AC-20, M11).

Kern-Schicht, ohne Netz: die Mails entstehen aus der echten Kette -- Trip ueber
Loader, ``NotificationService.send_trip_report`` und ``build_outlook_row``
(Ausblick), Orte ueber ``send_one_compare_preset`` -- und werden mit
``build_mime_message`` zur echten multipart/alternative-Mail. Die beiden
Validatoren laufen als Prozess mit ``--eml`` aus einer Hook-Kopie (Log in
``tmp_path``). Naehte: Transport-Aufzeichner und Wetter (feste Werte), kein
``Mock()``/``patch()``. Negative Mails entstehen durch gezielte Textaenderung der
positiven. Die Fallliste steht in
``tests/fixtures/einstellung_gleich_mail/fallliste_validatoren.json``.
"""
from __future__ import annotations

import copy
import dataclasses
import email
import json
import re
from datetime import date, datetime
from email import policy
from pathlib import Path

import pytest

from tests.helpers.mail_lang_fixture import _setze_text, validator_lauf

TRIP = "briefing_mail_validator"
ORTE = "email_spec_validator"

#: Trip-Metriken im Katalog-Array (wie der Editor speichert), Reihenfolge ueber
#: ``order``: Boeen, Temperatur, Niederschlag, Wind -- ungleich der Katalogfolge.
_TRIP_FOLGE = {"gust": 0, "temperature": 1, "precipitation": 2, "wind": 3}
_ORTSNAMEN = {"golden-0": "Innsbruck", "golden-1": "Lienz", "golden-2": "Kufstein"}


# --------------------------------------------------------------------------- #
# Konfigurationen (rohes Persistenzformat)
# --------------------------------------------------------------------------- #
def _trip_daten(folge: dict, *, ausblick: list | None = ("wind", "temperature", "precipitation"),
                email_format: str = "full") -> dict:
    from tests.tdd._einstellung_auslieferung_fixtures import golden_dict

    daten = golden_dict("golden_a")
    katalogfolge = ("temperature", "wind", "gust", "precipitation", "humidity")
    metriken = [{"metric_id": m, "enabled": m in folge, "bucket": "primary",
                 "order": folge.get(m, 9), "use_friendly_format": False} for m in katalogfolge]
    daten["display_config"] = {"trip_id": daten["id"], "metrics": metriken}
    if ausblick is not None:
        daten["display_config"]["outlook_metrics"] = list(ausblick)
    daten["report_config"]["email_format"] = email_format
    daten["report_config"].update(send_sms=False, send_telegram=False, send_premium_sms=False)
    return daten


def _orte_preset(*, stunden=("gust", "temperature", "precipitation"),
                 orte=("golden-2", "golden-0", "golden-1"), altbestand: bool = False) -> dict:
    preset = {
        "id": "gleich-orte", "name": "Gleich Orte", "kind": "vergleich",
        "location_ids": list(orte), "schedule": "daily", "profil": "ALLGEMEIN",
        "morning_enabled": True, "morning_time": "07:00:00", "evening_enabled": False,
        "send_telegram": False, "send_sms": False, "send_premium_sms": False,
        "display_config": {
            "active_metrics": ["wind_max_kmh", "temp_max_c", "precip_sum_mm", "gust_max_kmh"],
            "channel_active_metrics": {"email": ["wind_max_kmh", "temp_max_c", "precip_sum_mm"]},
            "hourly_metrics": list(stunden),
            "outlook_metrics": ["precipitation", "wind", "temperature"],
        },
    }
    if altbestand:  # #3047 O3: Feld fehlt ganz -- nie eingestellt
        preset["display_config"] = {"hourly_metrics": list(stunden)}
    return preset


# --------------------------------------------------------------------------- #
# Mails aus der echten Kette
# --------------------------------------------------------------------------- #
def _mime(sendung: dict, *, to: str, html: bool, hourly=None) -> bytes:
    from output.channels.email import build_mime_message

    msg = build_mime_message(
        subject=sendung["subject"], body=sendung["body"], from_addr="gregor_zwanzig@henemm.com",
        to_header=to, reply_to=None, html=html,
        plain_text_body=sendung.get("plain_text_body") if html else None,
        mail_type=sendung["mail_type"], mail_format=sendung.get("mail_format"),
        compare_hourly_enabled=hourly, message_id="<gleich-3047@henemm.com>", lang="de",
    )
    return msg.as_bytes()


def _trip_eml(monkeypatch, daten: dict) -> bytes:
    """Trip-Briefing ueber Loader + ``send_trip_report``; Ausblick aus
    ``build_outlook_row`` mit der geladenen ``display_config``."""
    from app.ampel import resolve_ampel
    from app.loader import load_trip
    from output.renderers.email.outlook import build_outlook_row
    from services.notification_service import NotificationService, TripReportRequest
    from tests.helpers.transport_mitschrift import aufzeichner_installieren
    from tests.tdd import _einstellung_auslieferung_fixtures as fx

    for name, wert in fx.TRANSPORT_ENV.items():
        monkeypatch.setenv(name, wert)
    mit = aufzeichner_installieren(monkeypatch)
    uid = fx.frisches_profil()
    trip = load_trip(copy.deepcopy(daten), user_id=uid)
    seg = fx.segment()
    zeilen = [build_outlook_row(seg.aggregated, seg.timeseries.data, tag, fx.TZ,
                                trip_display_config=trip.display_config, report_type="evening",
                                context="route", ampel=resolve_ampel(trip.display_config))
              for tag in ("Di", "Mi", "Do")]
    rc = trip.report_config
    NotificationService(user_id=uid).send_trip_report(TripReportRequest(
        trip=trip, report_type="evening", segment_weather=[seg], trip_tz=fx.TZ,
        night_weather=fx.night_weather(), stage_name=fx.STAGE_NAME, multi_day_trend=zeilen,
        report_config=rc, display_config=trip.display_config, send_email=True,
    ))
    sendung = mit.sendungen("email")[-1]
    return _mime(sendung, to=f"{uid}@example.invalid", html=sendung["mail_format"] == "full")


def _orte_eml(monkeypatch, preset: dict) -> bytes:
    """Orts-Vergleich ueber ``send_one_compare_preset``; Wetter aus
    ``vergleichs_mail_fixture.build_result`` je Orts-Kennung."""
    import services.comparison_parallel as cp
    import services.scheduler_dispatch_service as sds
    from app.loader import get_data_root, load_all_locations, save_location
    from app.user import ComparisonResult
    from tests.helpers.transport_mitschrift import aufzeichner_installieren
    from tests.helpers.vergleichs_mail_fixture import build_result
    from tests.tdd._compare_kette_fixtures import (
        nutzer_anlegen, preset_ablegen, preset_laden, settings_fuer, transport_einrichten,
    )

    transport_einrichten(monkeypatch)
    basis = {lr.location.id: lr for lr in build_result(mit_fehlerort=False).locations}

    def _wetter(*, locations, target_date, **_rest):  # Wetter-Naht: echte Funktion
        return ComparisonResult(
            locations=[dataclasses.replace(basis[o.id], location=o) for o in locations],
            time_window=(9, 16), target_date=target_date, created_at=datetime(2026, 10, 29, 4, 0))

    monkeypatch.setattr(cp, "run_comparison_parallel", _wetter)
    monkeypatch.setattr(sds, "_write_compare_alert_snapshots", lambda *a, **k: None)
    mit = aufzeichner_installieren(monkeypatch)
    uid = nutzer_anlegen()
    for lr in basis.values():
        save_location(lr.location, user_id=uid)
    preset_ablegen(uid, preset)
    sds.send_one_compare_preset(
        preset_laden(uid, preset["id"]), settings_fuer(uid), uid, str(get_data_root()),
        all_locations_cache=load_all_locations(user_id=uid),
        target_date=date(2026, 10, 29), tage_ab_ortstag=0)
    sendung = mit.sendungen("email")[-1]
    return _mime(sendung, to=f"{uid}@example.invalid", html=True,
                 hourly=sendung["compare_hourly_enabled"])


def _konfig(tmp_path: Path, name: str, daten: dict) -> str:
    pfad = tmp_path / f"{name}.json"
    pfad.write_text(json.dumps(daten, ensure_ascii=False), encoding="utf-8")
    return str(pfad)


def _orte_konfig(tmp_path: Path, preset: dict, name: str = "orte") -> str:
    return _konfig(tmp_path, name, {"preset": preset, "orte": _ORTSNAMEN})


def _aendere(eml: bytes, *, html=None, plain=None) -> bytes:
    """Gezielte Textaenderung je Teil (Kopfzeilen bleiben)."""
    msg = email.message_from_bytes(eml, policy=policy.compat32)
    for teil in msg.walk():
        fn = {"text/html": html, "text/plain": plain}.get(teil.get_content_type())
        if fn is not None:
            text = teil.get_payload(decode=True).decode(teil.get_content_charset() or "utf-8")
            neu = fn(text)
            assert neu != text, "Testaufbau: die Aenderung muss die Mail treffen"
            _setze_text(teil, neu, teil.get_content_charset() or "utf-8")
    return msg.as_bytes()


def _tausche(text: str, a: str, b: str) -> str:
    return text.replace(a, "\x00").replace(b, a).replace("\x00", b)


def _ohne_block(text: str, ueberschrift: str) -> str:
    """Entfernt eine Klartext-Ueberschrift samt Zeilen bis zur Leerzeile."""
    return re.sub(rf"\n{re.escape(ueberschrift)}\n.*?\n\n", "\n\n", text, flags=re.S)


def _lauf(tmp_path, validator, eml, *args):
    lauf, _log = validator_lauf(tmp_path, validator, eml, *args)
    return lauf.returncode, lauf.stdout + lauf.stderr


# --------------------------------------------------------------------------- #
# Trip (briefing_mail_validator)
# --------------------------------------------------------------------------- #
@pytest.fixture
def trip_mail(monkeypatch, tmp_path):
    daten = _trip_daten(_TRIP_FOLGE)
    return _trip_eml(monkeypatch, daten), _konfig(tmp_path, "trip", daten)


def test_trip_positiv_mail_stimmt_mit_konfig(tmp_path, trip_mail):
    eml, konfig = trip_mail
    code, aus = _lauf(tmp_path, TRIP, eml, "--konfig", konfig)
    assert code == 0, aus


def test_trip_spalten_vertauscht_scheitert_mit_name(tmp_path, trip_mail):
    eml, konfig = trip_mail
    falsch = _aendere(eml, html=lambda h: _tausche(h, ">Gust</th>", ">Temp</th>"))
    code, aus = _lauf(tmp_path, TRIP, falsch, "--konfig", konfig)
    assert code == 1, aus
    assert "SOLL: Etappen-Stundentabelle (HTML)" in aus and "steht 'Temp' statt 'Gust'" in aus, aus


def test_trip_spalte_fehlt_im_klartext_scheitert(tmp_path, trip_mail):
    eml, konfig = trip_mail
    falsch = _aendere(eml, plain=lambda p: re.sub(r"(?m)^( {2}Zeit.*?) Rain(?= )", r"\1", p))
    code, aus = _lauf(tmp_path, TRIP, falsch, "--konfig", konfig)
    assert code == 1, aus
    assert "SOLL: Etappen-Stundentabelle (Klartext)" in aus and "Spalte fehlt: 'Rain'" in aus, aus


def test_trip_spalte_zu_viel_scheitert(tmp_path, trip_mail):
    eml, konfig = trip_mail
    falsch = _aendere(eml, html=lambda h: re.sub(r"(<th[^>]*>Risiko</th>)", r"<th>UV</th>\1", h))
    code, aus = _lauf(tmp_path, TRIP, falsch, "--konfig", konfig)
    assert code == 1, aus
    assert "Spalte zu viel: 'UV'" in aus, aus


def test_trip_klartext_ausblick_fehlt_scheitert(tmp_path, trip_mail):
    from i18n import t

    eml, konfig = trip_mail
    falsch = _aendere(eml, plain=lambda p: _ohne_block(p, t("mail.ausblick.naechste_etappen", "de")))
    code, aus = _lauf(tmp_path, TRIP, falsch, "--konfig", konfig)
    assert code == 1, aus
    assert "SOLL: Ausblick fehlt im Klartext-Teil" in aus, aus


def test_trip_kompakt_ausblick_folge(monkeypatch, tmp_path):
    daten = _trip_daten(_TRIP_FOLGE, email_format="compact")
    eml, konfig = _trip_eml(monkeypatch, daten), _konfig(tmp_path, "kompakt", daten)
    code, aus = _lauf(tmp_path, TRIP, eml, "--konfig", konfig)
    assert code == 0, aus
    falsch = _aendere(eml, plain=lambda p: re.sub(r"(?m)^(\S+ +)Wind (.*?)  Temp (.*?)  ",
                                                  r"\1Temp \3  Wind \2  ", p))
    code, aus = _lauf(tmp_path, TRIP, falsch, "--konfig", konfig)
    assert code == 1, aus
    assert "SOLL: Ausblick (Kompakt)" in aus and "steht 'Temp' statt 'Wind'" in aus, aus


def test_trip_ausblick_nie_eingestellt_folgt_trip_reihenfolge(monkeypatch, tmp_path):
    """AC-4: ohne ``outlook_metrics`` die ganze Grundauswahl in der eingestellten
    Trip-Reihenfolge (Boeen, Temp, Niederschlag, Wind), nicht in Katalogfolge."""
    daten = _trip_daten(_TRIP_FOLGE, ausblick=None)
    code, aus = _lauf(tmp_path, TRIP, _trip_eml(monkeypatch, daten),
                      "--konfig", _konfig(tmp_path, "t1", daten))
    assert code == 0, aus


# --------------------------------------------------------------------------- #
# Orte (email_spec_validator)
# --------------------------------------------------------------------------- #
@pytest.fixture
def orte_mail(monkeypatch, tmp_path):
    preset = _orte_preset()
    return _orte_eml(monkeypatch, preset), _orte_konfig(tmp_path, preset)


def test_orte_positiv_mail_stimmt_mit_konfig(tmp_path, orte_mail):
    eml, konfig = orte_mail
    code, aus = _lauf(tmp_path, ORTE, eml, "--konfig", konfig)
    assert code == 0, aus


def test_orte_ortsfolge_vertauscht_scheitert(tmp_path, orte_mail):
    eml, konfig = orte_mail
    tausch = lambda text: _tausche(text, "Kufstein", "Innsbruck")  # noqa: E731
    code, aus = _lauf(tmp_path, ORTE, _aendere(eml, html=tausch, plain=tausch), "--konfig", konfig)
    assert code == 1, aus
    assert "SOLL: Ortsfolge (HTML)" in aus and "SOLL: Ortsfolge (Klartext)" in aus, aus
    assert "steht 'Innsbruck' statt 'Kufstein'" in aus, aus


def test_orte_stundenspalten_vertauscht_scheitert(tmp_path, orte_mail):
    eml, konfig = orte_mail
    falsch = _aendere(eml, plain=lambda p: re.sub(r"(?m)^(\s+\d{2}:\d{2}  )Gust (\S+)  Temp (\S+)",
                                                  r"\1Temp \3  Gust \2", p))
    code, aus = _lauf(tmp_path, ORTE, falsch, "--konfig", konfig)
    assert code == 1, aus
    assert "SOLL: Stundenverlauf (Klartext)" in aus and "steht 'Temp' statt 'Gust'" in aus, aus


def test_orte_vergleichszeile_fehlt_scheitert(tmp_path, orte_mail):
    eml, konfig = orte_mail
    falsch = _aendere(eml, plain=lambda p: re.sub(r"(?m)^   Niederschlag: .*\n", "", p))
    code, aus = _lauf(tmp_path, ORTE, falsch, "--konfig", konfig)
    assert code == 1, aus
    assert "SOLL: Vergleichstabelle Zeilen (Klartext)" in aus and "Spalte fehlt: 'Niederschlag'" in aus, aus


def test_orte_klartext_ausblick_fehlt_scheitert(tmp_path, orte_mail):
    from i18n import t

    eml, konfig = orte_mail
    titel = t("vergleich.ausblick.titel", "de")
    falsch = _aendere(eml, plain=lambda p: re.sub(rf"(?m)^{re.escape(titel)}\n(?:\S.*\n)+", "", p))
    code, aus = _lauf(tmp_path, ORTE, falsch, "--konfig", konfig)
    assert code == 1, aus
    assert "SOLL: Ausblick fehlt im Klartext-Teil" in aus, aus


def test_orte_channel_layouts_vor_channel_active_metrics(monkeypatch, tmp_path):
    """#3039 / F8: das Orte-Soll der Vergleichstabelle liest
    ``channel_layouts.email`` (Folge Niederschlag, Wind, Temperatur; Boeen
    ``enabled: false``) VOR ``channel_active_metrics.email`` (Wind, Temperatur,
    Niederschlag). Die so gebaute Mail ist gruen; die Mail des Presets ohne
    ``channel_layouts`` scheitert gegen diese Konfiguration mit Zeilenname."""
    preset = _orte_preset()
    preset["display_config"]["channel_layouts"] = {"email": [
        {"metric_id": "precipitation", "enabled": True},
        {"metric_id": "gust", "enabled": False},
        {"metric_id": "wind", "enabled": True, "use_friendly_format": False},
        {"metric_id": "temperature", "enabled": True},
    ]}
    konfig = _orte_konfig(tmp_path, preset, "layout")
    code, aus = _lauf(tmp_path, ORTE, _orte_eml(monkeypatch, preset), "--konfig", konfig)
    assert code == 0, aus
    code, aus = _lauf(tmp_path, ORTE, _orte_eml(monkeypatch, _orte_preset()), "--konfig", konfig)
    assert code == 1, aus
    assert "SOLL: Vergleichstabelle Zeilen (HTML)" in aus, aus
    assert "SOLL: Vergleichstabelle Zeilen (Klartext)" in aus, aus
    assert "steht 'Wind' statt 'Niederschlag'" in aus, aus


def test_orte_altbestand_ausblick_klartext_wie_html(monkeypatch, tmp_path):
    """AC-21: Altbestand ohne ``active_metrics``/``outlook_metrics`` -- der
    Klartext-Ausblick zeigt dieselben Spalten wie das HTML (heute 4 statt 7)."""
    preset = _orte_preset(altbestand=True)
    code, aus = _lauf(tmp_path, ORTE, _orte_eml(monkeypatch, preset),
                      "--konfig", _orte_konfig(tmp_path, preset, "o3"))
    assert code == 0, aus


# --------------------------------------------------------------------------- #
# AC-11 / AC-20: keine feste Folge ohne --konfig, Soll nur aus der Konfiguration
# --------------------------------------------------------------------------- #
def test_orte_zwei_gueltige_folgen_ohne_konfig_beide_gruen_mit_konfig_nur_passende(
        monkeypatch, tmp_path):
    a, b = _orte_preset(), _orte_preset(stunden=("precipitation", "gust", "temperature"))
    mail_a, mail_b = _orte_eml(monkeypatch, a), _orte_eml(monkeypatch, b)
    for mail in (mail_a, mail_b):
        code, aus = _lauf(tmp_path, ORTE, mail)
        assert code == 0, aus
    konfig_a = _orte_konfig(tmp_path, a, "a")
    assert _lauf(tmp_path, ORTE, mail_a, "--konfig", konfig_a)[0] == 0
    code, aus = _lauf(tmp_path, ORTE, mail_b, "--konfig", konfig_a)
    assert code == 1 and "SOLL: Stundenverlauf (HTML)" in aus, aus


def test_trip_zwei_gueltige_folgen_ohne_konfig_beide_gruen_mit_konfig_nur_passende(
        monkeypatch, tmp_path):
    a = _trip_daten(_TRIP_FOLGE)
    b = _trip_daten({"wind": 0, "precipitation": 1, "temperature": 2, "gust": 3})
    mail_a, mail_b = _trip_eml(monkeypatch, a), _trip_eml(monkeypatch, b)
    for mail in (mail_a, mail_b):
        code, aus = _lauf(tmp_path, TRIP, mail)
        assert code == 0, aus
    konfig_a = _konfig(tmp_path, "a", a)
    assert _lauf(tmp_path, TRIP, mail_a, "--konfig", konfig_a)[0] == 0
    code, aus = _lauf(tmp_path, TRIP, mail_b, "--konfig", konfig_a)
    assert code == 1 and "SOLL: Etappen-Stundentabelle (HTML)" in aus, aus


# --------------------------------------------------------------------------- #
# Nachlieferung H3 (Nachpruefung #3047 Punkte 1, 4, 5)
# --------------------------------------------------------------------------- #
def test_orte_stunden_schnitt_mit_grundauswahl(monkeypatch, tmp_path):
    """Punkt 1 (Konzept §5.8): gespeicherter Stundenverlauf mit Sicht, die nicht
    in der Grundauswahl steht -- die Mail zeigt Boeen/Temp/Regen, der Validator
    besteht; gegen eine Grundauswahl ohne Boeen scheitert dieselbe Mail."""
    preset = _orte_preset(stunden=("visibility", "gust", "temperature", "precipitation"))
    eml = _orte_eml(monkeypatch, preset)
    code, aus = _lauf(tmp_path, ORTE, eml, "--konfig", _orte_konfig(tmp_path, preset, "s1"))
    assert code == 0, aus
    ohne_boeen = copy.deepcopy(preset)
    ohne_boeen["display_config"]["active_metrics"].remove("gust_max_kmh")
    code, aus = _lauf(tmp_path, ORTE, eml, "--konfig", _orte_konfig(tmp_path, ohne_boeen, "s2"))
    assert code == 1, aus
    assert "SOLL: Stundenverlauf (HTML)" in aus and "Spalte zu viel: 'Gust'" in aus, aus


def test_orte_stunden_leerer_schnitt_rueckfall(monkeypatch, tmp_path):
    """Punkt 1: gespeicherte Liste ganz ausserhalb der Grundauswahl -> Vorgabe
    der Stundenspalten geschnitten mit der Grundauswahl (Temp, Wind, Boeen,
    Regen), nicht die gespeicherten Sicht/UV."""
    preset = _orte_preset(stunden=("visibility", "uv_index"))
    eml = _orte_eml(monkeypatch, preset)
    code, aus = _lauf(tmp_path, ORTE, eml, "--konfig", _orte_konfig(tmp_path, preset, "s3"))
    assert code == 0, aus
    falsch = _aendere(eml, plain=lambda p: re.sub(r"(?m)^(\s+\d{2}:\d{2}  )Temp (\S+)  Wind (\S+)",
                                                  r"\1Wind \3  Temp \2", p))
    code, aus = _lauf(tmp_path, ORTE, falsch, "--konfig", _orte_konfig(tmp_path, preset, "s3"))
    assert code == 1 and "steht 'Wind' statt 'Temp'" in aus, aus


def test_orte_stunden_nie_eingestellt_folgt_grundauswahl(monkeypatch, tmp_path):
    """Punkt 1 (Nachpruefung Punkt 3): nie eingestellter Stundenverlauf mit
    Grundauswahl -> Grundauswahl, soweit stuendlich verfuegbar, in deren Folge."""
    preset = _orte_preset()
    del preset["display_config"]["hourly_metrics"]
    code, aus = _lauf(tmp_path, ORTE, _orte_eml(monkeypatch, preset),
                      "--konfig", _orte_konfig(tmp_path, preset, "s4"))
    assert code == 0, aus


def test_orte_stunden_altbestand_ohne_alles_vorgabe_geprueft(monkeypatch, tmp_path):
    """Punkt 1: weder Grundauswahl noch Stundenverlauf -> die Vorgabespalten;
    fehlt eine davon in der Mail, scheitert der Validator (bisher ungeprueft)."""
    preset = _orte_preset(altbestand=True)
    preset["display_config"] = {}
    eml = _orte_eml(monkeypatch, preset)
    konfig = _orte_konfig(tmp_path, preset, "s5")
    code, aus = _lauf(tmp_path, ORTE, eml, "--konfig", konfig)
    assert code == 0, aus
    falsch = _aendere(eml, plain=lambda p: re.sub(r"(?m)^(\s+\d{2}:\d{2}  .*?)  UV \S+", r"\1", p))
    code, aus = _lauf(tmp_path, ORTE, falsch, "--konfig", konfig)
    assert code == 1 and "SOLL: Stundenverlauf (Klartext)" in aus and "Spalte fehlt: 'UV'" in aus, aus


def _orte_verzeichnis(tmp_path: Path) -> Path:
    """Orts-JSONs wie ``data/users/<id>/locations/<id>.json``."""
    ordner = tmp_path / "locations"
    ordner.mkdir(exist_ok=True)
    for i, (kennung, name) in enumerate(_ORTSNAMEN.items()):
        (ordner / f"{kennung}.json").write_text(json.dumps(
            {"id": kennung, "name": name, "lat": 47.0 + i, "lon": 11.0, "elevation_m": 600}),
            encoding="utf-8")
    return ordner


def test_orte_rohes_preset_ohne_ortsnamen_scheitert_laut(tmp_path, orte_mail):
    """Punkt 4: rohes Preset ohne Ortsnamen -- die Ortsfolge wird nicht still
    uebersprungen, der Validator scheitert mit klarer Meldung."""
    eml, _konfig_huelle = orte_mail
    roh = _konfig(tmp_path, "roh", _orte_preset())
    code, aus = _lauf(tmp_path, ORTE, eml, "--konfig", roh)
    assert code != 0, aus
    assert "Ortsfolge nicht prüfbar" in aus, aus


def test_orte_rohes_preset_mit_orte_aus_nutzerverzeichnis(tmp_path, orte_mail):
    """Punkt 4: ``--orte`` loest die Namen aus dem Orts-Verzeichnis bzw. der
    Orts-Liste der API; die richtige Mail besteht, vertauschte Orte nicht."""
    eml, _konfig_huelle = orte_mail
    roh = _konfig(tmp_path, "roh", _orte_preset())
    ordner = _orte_verzeichnis(tmp_path)
    api_liste = _konfig(tmp_path, "api_orte", [{"id": k, "name": n} for k, n in _ORTSNAMEN.items()])
    for quelle in (str(ordner), api_liste):
        code, aus = _lauf(tmp_path, ORTE, eml, "--konfig", roh, "--orte", quelle)
        assert code == 0, aus
    tausch = lambda text: _tausche(text, "Kufstein", "Innsbruck")  # noqa: E731
    code, aus = _lauf(tmp_path, ORTE, _aendere(eml, html=tausch, plain=tausch),
                      "--konfig", roh, "--orte", str(ordner))
    assert code == 1 and "SOLL: Ortsfolge (HTML)" in aus, aus


def _trip_darstellung_daten() -> dict:
    """Roh/Einfach gemischt: Boeen Einfach (Ampel), Wolken Einfach (Symbol),
    Gewitter Einfach, Sonne/Wind/Regen Roh; Ausblick Wind/Regen Einfach,
    Boeen/Wolken Roh."""
    daten = _trip_daten(_TRIP_FOLGE, ausblick=("wind", "gust", "temperature", "precipitation",
                                               "cloud_total", "thunder"))
    dc = daten["display_config"]
    for m in dc["metrics"]:
        m["use_friendly_format"] = m["metric_id"] == "gust"
    dc["metrics"] += [{"metric_id": m, "enabled": True, "bucket": "primary", "order": 5 + i,
                       "use_friendly_format": einfach}
                      for i, (m, einfach) in enumerate((("cloud_total", True), ("sunshine", False),
                                                        ("thunder", True)))]
    dc["outlook_metric_formats"] = {"wind": True, "precipitation": True, "gust": False,
                                    "cloud_total": False}
    return daten


@pytest.fixture
def darstellung_mail(monkeypatch, tmp_path):
    daten = _trip_darstellung_daten()
    return _trip_eml(monkeypatch, daten), _konfig(tmp_path, "darstellung", daten)


def test_trip_darstellung_roh_einfach_positiv(tmp_path, darstellung_mail):
    eml, konfig = darstellung_mail
    code, aus = _lauf(tmp_path, TRIP, eml, "--konfig", konfig)
    assert code == 0, aus


def test_trip_darstellung_einfach_als_zahl_klartext_scheitert(tmp_path, darstellung_mail):
    """Punkt 5: Wolken auf Einfach, der Klartext zeigt die Zahl -> Exit 1 mit Spalte."""
    eml, konfig = darstellung_mail
    falsch = _aendere(eml, plain=lambda p: p.replace("⛅  ", "70 "))
    code, aus = _lauf(tmp_path, TRIP, falsch, "--konfig", konfig)
    assert code == 1, aus
    assert "SOLL: Darstellung Etappen-Stundentabelle (Klartext)" in aus and "'Cloud'" in aus, aus


def test_trip_darstellung_ampel_fehlt_html_scheitert(tmp_path, darstellung_mail):
    """Punkt 5: Boeen auf Einfach, das HTML zeigt die Zahl statt des Ampelpunkts."""
    eml, konfig = darstellung_mail
    falsch = _aendere(eml, html=lambda h: re.sub(
        r'(data-label="Gust">)<span[^>]*></span>', r"\g<1>45", h))
    code, aus = _lauf(tmp_path, TRIP, falsch, "--konfig", konfig)
    assert code == 1, aus
    assert "SOLL: Darstellung Etappen-Stundentabelle (HTML)" in aus and "'Gust'" in aus, aus


def test_trip_darstellung_roh_als_symbol_scheitert(tmp_path, darstellung_mail):
    """Punkt 5: Sonne auf Roh, der Klartext zeigt ein Symbol statt der Zahl."""
    eml, konfig = darstellung_mail
    falsch = _aendere(eml, plain=lambda p: p.replace("1.0 h", "☀    "))
    code, aus = _lauf(tmp_path, TRIP, falsch, "--konfig", konfig)
    assert code == 1, aus
    assert "SOLL: Darstellung" in aus and "'Sun'" in aus, aus


def test_trip_darstellung_ausblick_roh_statt_einfach_scheitert(tmp_path, darstellung_mail):
    """Punkt 5: Ausblick-Wind auf Einfach, HTML und Klartext zeigen die Zahl."""
    eml, konfig = darstellung_mail
    falsch = _aendere(eml, plain=lambda p: re.sub(r"Wind \S+  Gust", "Wind 20 km/h  Gust", p),
                      html=lambda h: re.sub(r"(<tr>\s*<td[^>]*>(?:Di|Mi|Do)</td>\s*<td[^>]*>)[^<]*",
                                            r"\g<1>20 km/h", h))
    code, aus = _lauf(tmp_path, TRIP, falsch, "--konfig", konfig)
    assert code == 1, aus
    assert "SOLL: Darstellung Ausblick (Klartext)" in aus and "'Wind'" in aus, aus
    assert "SOLL: Darstellung Ausblick (HTML)" in aus, aus


# --------------------------------------------------------------------------- #
# Fallliste (Paket C)
# --------------------------------------------------------------------------- #
def test_fallliste_validatoren_verweist_auf_vorhandene_tests():
    pfad = Path(__file__).resolve().parents[1] / "fixtures" / "einstellung_gleich_mail" / "fallliste_validatoren.json"
    liste = json.loads(pfad.read_text(encoding="utf-8"))
    namen = {n for n in globals() if n.startswith("test_")}
    assert liste["faelle"], "Fallliste ohne Faelle"
    for fall in liste["faelle"]:
        assert fall["test"] in namen, fall
        assert fall["liste"] in ("validator_trip", "validator_orte"), fall
        assert fall["status"] in ("gruen", "rot_erwartet", "ausnahme", "offen_feature"), fall
