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
def _mime(sendung: dict, *, to: str, html: bool, hourly=None, lang: str = "de") -> bytes:
    from output.channels.email import build_mime_message

    msg = build_mime_message(
        subject=sendung["subject"], body=sendung["body"], from_addr="gregor_zwanzig@henemm.com",
        to_header=to, reply_to=None, html=html,
        plain_text_body=sendung.get("plain_text_body") if html else None,
        mail_type=sendung["mail_type"], mail_format=sendung.get("mail_format"),
        compare_hourly_enabled=hourly, message_id="<gleich-3047@henemm.com>", lang=lang,
    )
    return msg.as_bytes()


def _sprache_setzen(uid: str, lang: str) -> None:
    """Nutzersprache im echten ``user.json`` (ADR-0104, ``resolve_user_lang``)."""
    from app.loader import get_data_dir

    pfad = get_data_dir(uid) / "user.json"
    pfad.write_text(json.dumps({**json.loads(pfad.read_text()), "language": lang}))


def _trip_eml(monkeypatch, daten: dict, *, lang: str = "de", tage=("Di", "Mi", "Do"),
              etappen_namen=None, notiz: str | None = None) -> bytes:
    """Trip-Briefing ueber Loader + ``send_trip_report``; Ausblick aus
    ``build_outlook_row`` mit der geladenen ``display_config``. ``etappen_namen``
    und ``notiz`` setzen Etappenname bzw. Hinweis ("↳") je Ausblick-Zeile, wie
    der Scheduler (``row["name"]``/``row["note"]``)."""
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
    _sprache_setzen(uid, lang)
    trip = load_trip(copy.deepcopy(daten), user_id=uid)
    seg = fx.segment()
    zeilen = [build_outlook_row(seg.aggregated, seg.timeseries.data, tag, fx.TZ,
                                trip_display_config=trip.display_config, report_type="evening",
                                context="route", ampel=resolve_ampel(trip.display_config), lang=lang)
              for tag in tage]
    for zeile, name in zip(zeilen, etappen_namen or ()):
        zeile["name"] = name
    for zeile in zeilen if notiz else ():
        zeile["note"] = notiz
    rc = trip.report_config
    NotificationService(user_id=uid).send_trip_report(TripReportRequest(
        trip=trip, report_type="evening", segment_weather=[seg], trip_tz=fx.TZ,
        night_weather=fx.night_weather(), stage_name=fx.STAGE_NAME, multi_day_trend=zeilen,
        report_config=rc, display_config=trip.display_config, send_email=True,
    ))
    sendung = mit.sendungen("email")[-1]
    return _mime(sendung, to=f"{uid}@example.invalid", html=sendung["mail_format"] == "full",
                 lang=lang)


def _orte_eml(monkeypatch, preset: dict, *, lang: str = "de", namen: dict | None = None,
              versatz: int = 0) -> bytes:
    """Orts-Vergleich ueber ``send_one_compare_preset``; Wetter aus
    ``vergleichs_mail_fixture.build_result`` je Orts-Kennung. ``namen``
    (Kennung -> Name) benennt die gespeicherten Orte um. ``versatz`` = Zieltag
    ab Erstellungstag (Morgen-Slot 0, Abend-Slot 1, ``compare_slot_scheduler``)."""
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

    def _wetter(*, locations, target_date, official_alerts_enabled=True, **_rest):  # Wetter-Naht
        # #3047 Runde 7: wie ``comparison_engine`` -- Schalter aus = kein
        # Abruf, also weder Warnungen noch "nicht abrufbar".
        aus = {} if official_alerts_enabled else {"official_alerts": [], "official_alerts_unavailable": False}
        return ComparisonResult(
            locations=[dataclasses.replace(basis[o.id], location=o, **aus) for o in locations],
            time_window=(9, 16), target_date=target_date, created_at=datetime(2026, 10, 29, 4, 0))

    monkeypatch.setattr(cp, "run_comparison_parallel", _wetter)
    monkeypatch.setattr(sds, "_write_compare_alert_snapshots", lambda *a, **k: None)
    mit = aufzeichner_installieren(monkeypatch)
    uid = nutzer_anlegen()
    _sprache_setzen(uid, lang)
    for kennung, lr in basis.items():
        save_location(dataclasses.replace(lr.location, name=(namen or {}).get(kennung, lr.location.name)),
                      user_id=uid)
    preset_ablegen(uid, preset)
    sds.send_one_compare_preset(
        preset_laden(uid, preset["id"]), settings_fuer(uid), uid, str(get_data_root()),
        all_locations_cache=load_all_locations(user_id=uid),
        target_date=date(2026, 10, 29 + versatz), tage_ab_ortstag=versatz)
    sendung = mit.sendungen("email")[-1]
    return _mime(sendung, to=f"{uid}@example.invalid", html=True,
                 hourly=sendung["compare_hourly_enabled"], lang=lang)


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
    falsch = _aendere(eml, plain=lambda p: _ohne_block(p, t("mail.ausblick.name", "de")))
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


# ---- #3156 AC-9: Ampel-Groessen auf Einfach -> Klartext Wortstufe ---- #
@pytest.fixture
def ampel_einfach_mail(monkeypatch, tmp_path):
    """Wind, Regen und Regen-W. mit ``format_mode: simplified``: der echte
    Renderer schreibt im Klartext die Wortstufe (Regen-W. Skala 25/50/75),
    das Validator-Soll muss dieselbe Form erwarten."""
    daten = _trip_daten(_TRIP_FOLGE)
    dc = daten["display_config"]
    dc["metrics"].append({"metric_id": "rain_probability", "enabled": True, "bucket": "primary",
                          "order": 4, "use_friendly_format": True})
    for m in dc["metrics"]:
        if m["metric_id"] in ("wind", "precipitation", "rain_probability"):
            m.update(use_friendly_format=True, format_mode="simplified")
    return _trip_eml(monkeypatch, daten), _konfig(tmp_path, "ampel_einfach", daten)


def test_trip_ampel_einfach_klartext_wortstufe_positiv(tmp_path, ampel_einfach_mail):
    eml, konfig = ampel_einfach_mail
    text = next(t.get_payload(decode=True).decode() for t in email.message_from_bytes(eml).walk()
                if t.get_content_type() == "text/plain")
    assert re.search(r"(?m)^  \d\d +\d+ +[\d.]+ +[a-zäöüß]+ +[a-zäöüß]+ +"
                     r"(sehr wahrscheinlich|unwahrscheinlich|wahrscheinlich|möglich)\s*$", text), (
        "Testaufbau: Regen/Wind/Regen-W. Einfach muessen im Klartext als Wort erscheinen")
    code, aus = _lauf(tmp_path, TRIP, eml, "--konfig", konfig)
    assert code == 0, aus


def test_trip_ampel_einfach_klartext_zahl_scheitert(tmp_path, ampel_einfach_mail):
    """Regen-W. auf Einfach, der Klartext zeigt die Prozentzahl -> Exit 1."""
    eml, konfig = ampel_einfach_mail
    falsch = _aendere(eml, plain=lambda p: re.sub(
        r"\b(sehr wahrscheinlich|unwahrscheinlich|wahrscheinlich|möglich)\b",
        lambda t: "40".ljust(len(t.group(0))), p))
    code, aus = _lauf(tmp_path, TRIP, falsch, "--konfig", konfig)
    assert code == 1, aus
    assert ("SOLL: Darstellung Etappen-Stundentabelle (Klartext) 1: Spalte 'Rain%' soll "
            "Symbol/Wort (Einfach) zeigen") in aus, aus
    assert "Spalte 'Rain' soll" not in aus and "Spalte 'Wind' soll" not in aus, aus


def _soll_modul():
    """Das Soll-Modul der Validatoren direkt aus ``.claude/hooks`` (nur lesen)."""
    import importlib.util

    pfad = Path(__file__).resolve().parents[2] / ".claude" / "hooks" / "_soll_aus_konfiguration.py"
    spec = importlib.util.spec_from_file_location("_soll_aus_konfiguration_3156", pfad)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.parametrize("freundlich, modus, html, klartext", [
    (True, "simplified", ("ampel",), ("wort",)),
    (True, "raw", ("ampel",), ("zahl",)),
    (False, "simplified", ("zahl",), ("wort",)),
    (False, "raw", ("zahl",), ("zahl",)),
])
def test_trip_stunden_soll_regenwahrscheinlichkeit_ampelzweig_3156(freundlich, modus, html,
                                                                     klartext):
    """#3156 F002: Die Regenwahrscheinlichkeit gehoert im Soll der Trip-
    Stundenzeilen zum Ampel-Zweig -- HTML folgt ``use_friendly_format``
    (Ampel bzw. Zahl), der Klartext dem ``format_mode`` (Einfach = Wortstufe,
    Roh = Zahl). Exakter Vergleich: der allgemeine Einfach-Zweig liesse im
    HTML auch das Wort zu bzw. zeigte bei Roh keine Ampel."""
    soll = _soll_modul()
    eintrag = {"metric_id": "rain_probability", "enabled": True, "bucket": "primary",
               "order": 0, "use_friendly_format": freundlich, "format_mode": modus}
    spalte = soll._REG["rain_probability"].col_label
    formen = soll._formen_stunden([eintrag])
    assert formen[spalte] == {"HTML": html, "Klartext": klartext}, formen


def _ampel_zwei_formen() -> list[str]:
    """Ampelgroessen aus der Quelle (``AMPEL_METRIC_IDS``), die laut Katalog
    zwei Darstellungen kennen (nur dort wirkt Einfach)."""
    from app.metric_catalog import AMPEL_METRIC_IDS, get_metric

    return sorted(m for m in AMPEL_METRIC_IDS if len(get_metric(m).format_modes) > 1)


def test_orte_soll_ampelmenge_enthaelt_regenwahrscheinlichkeit_3156():
    """Vorbedingung F005: die Parametrisierung unten deckt die Regen-W. ab."""
    assert "rain_probability" in _ampel_zwei_formen(), _ampel_zwei_formen()


@pytest.mark.parametrize("metrik", _ampel_zwei_formen())
@pytest.mark.parametrize("modus, html, klartext", [
    ("simplified", ("ampel",), ("wort",)),
    ("raw", ("zahl",), ("zahl",)),
])
def test_orte_soll_ampelgroessen_einfach_nur_ampelpunkt_3156(metrik, modus, html, klartext):
    """#3156 F005: Im Soll der Orte-Vergleichstabelle zeigt eine Ampelgroesse
    (aus ``AMPEL_METRIC_IDS``) auf Einfach im HTML NUR den Ampelpunkt -- das
    Wort scheitert --, im Klartext die Wortstufe; Roh = Zahl in beiden Teilen.
    Exakter Vergleich: der allgemeine Einfach-Zweig liesse (Wort, Ampel) zu."""
    soll = _soll_modul()
    dc = {"channel_layouts": {"email": [
        {"metric_id": metrik, "enabled": True, "format_mode": modus}]}}
    paare = [(metrik, "max")]
    label = soll._uebersicht_labels(paare, "de")[0]
    formen = soll._orte_formen(dc, paare, "de")
    assert formen[label] == {"HTML": html, "Klartext": klartext}, formen


# --------------------------------------------------------------------------- #
# Nachlieferung J2: Fall A (``metrics`` fehlt bzw. ``[]``) und bewusst leer
# --------------------------------------------------------------------------- #
def _trip_fall_a(variante: str, email_format: str = "full") -> dict:
    """Trip-Altbestand Fall A (#1394, #3068): ``metrics`` fehlt bzw. ist ``[]``,
    Ausblick nie eingestellt -- der Loader liest den Register-Standardsatz."""
    daten = _trip_daten(_TRIP_FOLGE, ausblick=None, email_format=email_format)
    if variante == "leer":
        daten["display_config"]["metrics"] = []
    else:
        del daten["display_config"]["metrics"]
    return daten


@pytest.mark.parametrize("variante,email_format", [
    ("fehlt", "full"), ("leer", "full"), ("fehlt", "compact"), ("leer", "compact")])
def test_trip_fall_a_register_standard_positiv(monkeypatch, tmp_path, variante, email_format):
    """AC-19/AC-20: die korrekte Mail eines Fall-A-Trips (Stunden und Ausblick =
    Register-Standardsatz) besteht mit ``--konfig`` -- statt an den alten
    sieben festen Ausblick-Spalten zu scheitern."""
    daten = _trip_fall_a(variante, email_format)
    code, aus = _lauf(tmp_path, TRIP, _trip_eml(monkeypatch, daten),
                      "--konfig", _konfig(tmp_path, f"a-{variante}-{email_format}", daten))
    assert code == 0, aus


@pytest.fixture
def fall_a_mail(monkeypatch, tmp_path):
    daten = _trip_fall_a("fehlt")
    return _trip_eml(monkeypatch, daten), _konfig(tmp_path, "fall-a", daten)


def test_trip_fall_a_stundenfolge_falsch_scheitert(tmp_path, fall_a_mail):
    """AC-19: Fall A pruefte die Stundentabelle bisher gar nicht (Soll ``None``);
    eine vertauschte Spalte faellt jetzt mit Namen auf."""
    eml, konfig = fall_a_mail
    falsch = _aendere(eml, html=lambda h: _tausche(h, ">Wind</th>", ">Gust</th>"))
    code, aus = _lauf(tmp_path, TRIP, falsch, "--konfig", konfig)
    assert code == 1, aus
    assert "SOLL: Etappen-Stundentabelle (HTML)" in aus and "steht 'Gust' statt 'Wind'" in aus, aus


def test_trip_fall_a_ausblickfolge_falsch_scheitert(tmp_path, fall_a_mail):
    """AC-19: Fall A, Ausblick-Spalten im Klartext vertauscht -> Exit 1 mit Namen."""
    eml, konfig = fall_a_mail
    falsch = _aendere(eml, plain=lambda p: re.sub(r"(?m)^(.*?)Wind (\S+ km/h)  Gust (\S+ km/h)",
                                                  r"\1Gust \3  Wind \2", p))
    code, aus = _lauf(tmp_path, TRIP, falsch, "--konfig", konfig)
    assert code == 1, aus
    assert "SOLL: Ausblick (Klartext)" in aus and "steht 'Gust' statt 'Wind'" in aus, aus


def _trip_bewusst_leer() -> dict:
    """Bewusst leer (#1394 Fall B): Eintraege vorhanden, alle ``enabled: false``."""
    daten = _trip_daten({}, ausblick=None)
    assert daten["display_config"]["metrics"] and not any(
        m["enabled"] for m in daten["display_config"]["metrics"])
    return daten


def test_trip_bewusst_leer_ausblick_entfaellt_positiv(monkeypatch, tmp_path):
    """Konzept "alle Zeilen abgewaehlt -> Ausblick entfaellt": die Mail eines
    bewusst leeren Trips hat weder Stundentabelle (J3: entfaellt ohne Spalten)
    noch Ausblick; der Validator besteht -- "keine Stundentabelle" bzw. "Viewport
    leer" sind laut Soll kein Fehler (#3047 J4)."""
    daten = _trip_bewusst_leer()
    code, aus = _lauf(tmp_path, TRIP, _trip_eml(monkeypatch, daten),
                      "--konfig", _konfig(tmp_path, "leer", daten))
    assert code == 0, aus


def test_trip_bewusst_leer_ohne_konfig_tabelle_bleibt_pflicht(monkeypatch, tmp_path):
    """#3047 J4: die Lockerung "keine Tabelle" gilt NUR laut Soll -- ohne
    ``--konfig`` scheitert dieselbe bewusst leere Mail weiter an der fehlenden
    Stundentabelle und am leeren Viewport."""
    code, aus = _lauf(tmp_path, TRIP, _trip_eml(monkeypatch, _trip_bewusst_leer()))
    assert code == 1, aus
    assert "keine sequenzielle Stundentabelle" in aus, aus
    assert "keine Wetterdaten-Tabelle sichtbar" in aus, aus


def test_trip_bewusst_leer_ausblick_erscheint_scheitert(monkeypatch, tmp_path):
    """Bewusst leer: der Validator verlangt KEINEN Ausblick -- die Mail eines
    Trips mit Ausblick scheitert gegen die bewusst leere Konfiguration."""
    eml = _trip_eml(monkeypatch, _trip_daten(_TRIP_FOLGE))
    code, aus = _lauf(tmp_path, TRIP, eml, "--konfig", _konfig(tmp_path, "leer", _trip_bewusst_leer()))
    assert code == 1, aus
    assert "Ausblick (HTML) erscheint, obwohl er laut Konfiguration aus ist" in aus, aus
    assert "SOLL: Etappen-Stundentabelle (HTML)" in aus and "Spalte zu viel" in aus, aus


# --------------------------------------------------------------------------- #
# Nachlieferung 3 (dritte Nachpruefung #3047, N1, N2, N4-N7)
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("grund_aus", [False, True], ids=["nur_fremd", "grund_ausdruecklich_aus"])
def test_trip_kanal_liste_totalschnitt_volle_grundauswahl(monkeypatch, tmp_path, grund_aus):
    """N1 (AC-10, Repro TF): die E-Mail-Liste traegt nur Luftfeuchte (in der
    Grundauswahl abgewaehlt) als aktive Zeile -- auch wenn sie die Metriken der
    Grundauswahl ausdruecklich ausschaltet -> die Mail zeigt die volle
    Grundauswahl (``_clip_to_global_maximum``), das Soll ebenso. Totalschnitt
    ist nicht "bewusst leer": gegen eine leere E-Mail-Liste ist dieselbe Mail
    falsch."""
    daten = _trip_daten(_TRIP_FOLGE)
    daten["display_config"]["channel_layouts"] = {"email": [
        {"metric_id": "humidity", "enabled": True, "bucket": "primary", "order": 0}] + (
        [{"metric_id": m, "enabled": False, "bucket": "primary", "order": i + 1}
         for i, m in enumerate(_TRIP_FOLGE)] if grund_aus else [])}
    eml = _trip_eml(monkeypatch, daten)
    code, aus = _lauf(tmp_path, TRIP, eml, "--konfig", _konfig(tmp_path, "tf", daten))
    assert code == 0, aus
    leer = copy.deepcopy(daten)
    leer["display_config"]["channel_layouts"] = {"email": []}
    code, aus = _lauf(tmp_path, TRIP, eml, "--konfig", _konfig(tmp_path, "tf-leer", leer))
    assert code == 1 and "SOLL: Etappen-Stundentabelle (HTML) 1: Spalte zu viel" in aus, aus


@pytest.mark.parametrize("email_format", ["full", "compact"])
def test_trip_ausblick_totalschnitt_volle_grundauswahl(monkeypatch, tmp_path, email_format):
    """N1 (AC-10, Repro TG, Mutation V04): gespeicherter Ausblick nur mit der
    abgewaehlten Luftfeuchte -> volle Grundauswahl statt verschwindendem Block;
    gegen den bewusst geleerten Ausblick (``[]``) ist dieselbe Mail falsch."""
    daten = _trip_daten(_TRIP_FOLGE, ausblick=("humidity",), email_format=email_format)
    eml = _trip_eml(monkeypatch, daten)
    code, aus = _lauf(tmp_path, TRIP, eml, "--konfig", _konfig(tmp_path, "tg", daten))
    assert code == 0, aus
    leer = _trip_daten(_TRIP_FOLGE, ausblick=(), email_format=email_format)
    code, aus = _lauf(tmp_path, TRIP, eml, "--konfig", _konfig(tmp_path, "tg-leer", leer))
    teil = "Kompakt" if email_format == "compact" else "HTML"
    assert code == 1 and f"SOLL: Ausblick ({teil}) erscheint" in aus, aus


_ORTE_TOTALSCHNITT = {
    "channel_layouts": ({"email": [{"metric_id": "humidity", "enabled": True}]},
                        {"email": [{"metric_id": m, "enabled": False}
                                   for m in ("wind", "temperature", "precipitation", "gust")]},
                        "SOLL: Vergleichstabelle Zeilen (HTML) Block 1: Spalte zu viel"),
    "channel_active_metrics": ({"email": ["humidity_avg_pct"]}, {"email": []},
                               "SOLL: Vergleichstabelle Zeilen (HTML) Block 1: Spalte zu viel"),
    "outlook_metrics": (["humidity"], [], "SOLL: Ausblick (HTML) erscheint"),
}


@pytest.mark.parametrize("feld", list(_ORTE_TOTALSCHNITT))
def test_orte_totalschnitt_volle_grundauswahl(monkeypatch, tmp_path, feld):
    """N1 (AC-10, Repro OF, Mutation V04): Kanal-Liste bzw. Ausblick ganz
    ausserhalb der Grundauswahl -> volle Grundauswahl in der Mail und im Soll;
    die bewusst leere Liste (alle aus bzw. ``[]``) verlangt dagegen nichts."""
    total, leer, meldung = _ORTE_TOTALSCHNITT[feld]
    preset = _orte_preset()
    preset["display_config"][feld] = total
    eml = _orte_eml(monkeypatch, preset)
    code, aus = _lauf(tmp_path, ORTE, eml, "--konfig", _orte_konfig(tmp_path, preset, "of"))
    assert code == 0, aus
    preset["display_config"][feld] = leer
    code, aus = _lauf(tmp_path, ORTE, eml, "--konfig", _orte_konfig(tmp_path, preset, "of-leer"))
    assert code == 1 and meldung in aus, aus


def _orte_bewusst_leer(**schalter) -> dict:
    """N2: ``active_metrics: []`` = bewusst leere Grundauswahl."""
    preset = _orte_preset()
    preset["display_config"]["active_metrics"] = []
    preset.update(schalter)
    return preset


def test_orte_grundauswahl_bewusst_leer_positiv(monkeypatch, tmp_path):
    """N2: bewusst leere Grundauswahl -> Vergleichstabelle ohne Metrikzeilen,
    kein Stundenverlauf, kein Ausblick; die Mail besteht mit ``--konfig``."""
    preset = _orte_bewusst_leer()
    code, aus = _lauf(tmp_path, ORTE, _orte_eml(monkeypatch, preset),
                      "--konfig", _orte_konfig(tmp_path, preset, "n2"))
    assert code == 0, aus


@pytest.mark.parametrize("stunden_gespeichert", [True, False], ids=["stunden_gespeichert", "stunden_nie"])
def test_orte_grundauswahl_bewusst_leer_soll_ohne_bloecke(tmp_path, orte_mail, stunden_gespeichert):
    """N2 (Soll-Seite): gegen die bewusst leere Grundauswahl ist eine Mail mit
    Metrikzeilen, Stundenverlauf und Ausblick in allen drei Teilen falsch --
    auch bei nie eingestelltem Stundenverlauf (kein Rueckfall auf die Vorgabe)."""
    eml, _konfig_voll = orte_mail
    leer = _orte_bewusst_leer()
    if not stunden_gespeichert:
        del leer["display_config"]["hourly_metrics"]
    code, aus = _lauf(tmp_path, ORTE, eml, "--konfig", _orte_konfig(tmp_path, leer, "n2s"))
    assert code == 1, aus
    assert "SOLL: Vergleichstabelle Zeilen (HTML) Block 1: Spalte zu viel" in aus, aus
    assert "SOLL: Stundenverlauf (HTML) erscheint" in aus, aus
    assert "SOLL: Ausblick (HTML) erscheint" in aus, aus


def test_orte_leere_vergleichstabelle_kein_falscher_ort_fehlt(monkeypatch, tmp_path):
    """N6: leere Vergleichstabelle (bewusst leere Grundauswahl, Ausblick aus) --
    der Klartext nennt die Orte ohne Zeilen; kein falsches "Ort fehlt". Die
    Ortsfolge bleibt geprueft: vertauscht scheitert sie."""
    preset = _orte_bewusst_leer(outlook_enabled=False)
    eml = _orte_eml(monkeypatch, preset)
    konfig = _orte_konfig(tmp_path, preset, "n6")
    code, aus = _lauf(tmp_path, ORTE, eml, "--konfig", konfig)
    assert code == 0, aus
    falsch = _aendere(eml, plain=lambda p: _tausche(p, "Kufstein", "Innsbruck"))
    code, aus = _lauf(tmp_path, ORTE, falsch, "--konfig", konfig)
    assert code == 1 and "SOLL: Ortsfolge (Klartext)" in aus, aus


def _orte_einfach(fmt: str = "simplified") -> dict:
    preset = _orte_preset()
    preset["display_config"]["channel_layouts"] = {"email": [
        {"metric_id": m, "enabled": True, "format": fmt}
        for m in ("wind", "temperature", "precipitation", "gust")]}
    return preset


def test_orte_einfach_zeilen_kein_format_fehler(monkeypatch, tmp_path):
    """N4: Vergleichszeilen auf Einfach zeigen im HTML den Ampelpunkt ohne Text --
    mit ``--konfig`` kein FORMAT-Fehler. Ohne ``--konfig`` (unbekannt) und gegen
    eine Roh-Konfiguration bleibt die Zahlform Pflicht."""
    eml = _orte_eml(monkeypatch, _orte_einfach())
    code, aus = _lauf(tmp_path, ORTE, eml, "--konfig", _orte_konfig(tmp_path, _orte_einfach(), "n4"))
    assert code == 0, aus
    code, aus = _lauf(tmp_path, ORTE, eml, "--konfig", _orte_konfig(tmp_path, _orte_einfach("raw"), "n4r"))
    assert code == 1 and "FORMAT: 'Wind'" in aus, aus
    code, aus = _lauf(tmp_path, ORTE, eml)
    assert code == 1 and "FORMAT: 'Wind'" in aus, aus


def test_trip_kompakt_bewusst_leer_ohne_ueberblick(monkeypatch, tmp_path):
    """N5: Kompakt, alle Zeilen abgewaehlt -> kein Metriken-Ueberblick; mit
    ``--konfig`` kein Fehler, ohne bleibt der Block Pflicht; gegen die bewusst
    leere Konfiguration ist eine Mail MIT Ueberblick falsch."""
    leer = _trip_daten({}, ausblick=None, email_format="compact")
    eml = _trip_eml(monkeypatch, leer)
    code, aus = _lauf(tmp_path, TRIP, eml, "--konfig", _konfig(tmp_path, "n5", leer))
    assert code == 0, aus
    code, aus = _lauf(tmp_path, TRIP, eml)
    assert code == 1 and "Metriken-Ueberblick ==' fehlt" in aus, aus
    voll = _trip_eml(monkeypatch, _trip_daten(_TRIP_FOLGE, email_format="compact"))
    code, aus = _lauf(tmp_path, TRIP, voll, "--konfig", _konfig(tmp_path, "n5", leer))
    assert code == 1 and "erscheint, obwohl die Grundauswahl bewusst leer ist" in aus, aus


def test_trip_kompakt_ausblick_roh_einfach(monkeypatch, tmp_path):
    """N7: Kompakt-Ausblick Roh/Einfach laut ``outlook_metric_formats`` (Wind und
    Regen Einfach = Wort, Temperatur Roh = Zahl). Wind als Zahl, Temperatur als
    Wort bzw. die Mail gegen eine Roh-Konfiguration scheitern mit Spaltennamen."""
    daten = _trip_daten(_TRIP_FOLGE, email_format="compact")
    daten["display_config"]["outlook_metric_formats"] = {"wind": True, "precipitation": True}
    eml = _trip_eml(monkeypatch, daten)
    konfig = _konfig(tmp_path, "n7", daten)
    code, aus = _lauf(tmp_path, TRIP, eml, "--konfig", konfig)
    assert code == 0, aus
    for alt, neu, spalte in ((r"Wind [a-z]+", "Wind 20 km/h", "'Wind'"),
                             (r"Temp \d+/\d+", "Temp mild", "'Temp'")):
        falsch = _aendere(eml, plain=lambda p, a=alt, n=neu: re.sub(a, n, p))
        code, aus = _lauf(tmp_path, TRIP, falsch, "--konfig", konfig)
        assert code == 1 and "SOLL: Darstellung Ausblick (Kompakt)" in aus and spalte in aus, aus
    roh = _konfig(tmp_path, "n7-roh", _trip_daten(_TRIP_FOLGE, email_format="compact"))
    code, aus = _lauf(tmp_path, TRIP, eml, "--konfig", roh)
    assert code == 1 and "SOLL: Darstellung Ausblick (Kompakt)" in aus and "'Wind'" in aus, aus


def _ohne_seg_tabellen(html: str) -> str:
    """Entfernt Desktop- und Handy-Tabelle der ersten Etappe (Ueberschrift bleibt)."""
    a = html.index(">SEG 1</span>")
    b = html.index("🌙", a)
    return html[:a] + re.sub(r'<table data-table="resp".*?</table>', "", html[a:b], flags=re.S) + html[b:]


def test_trip_verwaiste_ueberschrift_scheitert(tmp_path, trip_mail):
    """N7: eine Etappen- bzw. Nacht-Ueberschrift ohne Stundentabelle ist ein
    Fehler (HTML und Klartext) -- bei bewusst leerer Auswahl muss der ganze
    Abschnitt entfallen, nicht nur die Tabelle."""
    from i18n import t

    eml, konfig = trip_mail
    falsch = _aendere(eml, html=_ohne_seg_tabellen,
                      plain=lambda p: re.sub(r"(━━ Segment 1:[^\n]*\n)(?: {2}[^\n]*\n)+", r"\1", p))
    code, aus = _lauf(tmp_path, TRIP, falsch, "--konfig", konfig)
    assert code == 1, aus
    assert "SOLL: verwaiste Ueberschrift (HTML) 'SEG 1'" in aus, aus
    assert "SOLL: verwaiste Ueberschrift (Klartext) 'Segment 1:" in aus, aus
    nacht = t("mail.nacht.am_ziel", "de", hoehe=1400)
    falsch = _aendere(eml, plain=lambda p: re.sub(
        rf"({re.escape(nacht)} ━━\n[^\n]*\n)(?: {{2}}[^\n]*\n)+", r"\1", p))
    code, aus = _lauf(tmp_path, TRIP, falsch, "--konfig", konfig)
    assert code == 1 and f"SOLL: verwaiste Ueberschrift (Klartext) '{nacht}'" in aus, aus


# --------------------------------------------------------------------------- #
# Nachlieferung 4 (vierte unabhaengige Pruefung #3047, F001, F002, F006-F008a, F004)
# --------------------------------------------------------------------------- #
def _trip_en_daten(email_format: str = "full") -> dict:
    """F001-Repro: Wind, Temperatur, Boeen; Ausblick Wind, Temperatur."""
    return _trip_daten({"wind": 0, "temperature": 1, "gust": 2}, ausblick=("wind", "temperature"),
                       email_format=email_format)


@pytest.mark.parametrize("email_format", ["full", "compact"])
def test_trip_en_ausblick_sonntag_kein_spaltenkuerzel(monkeypatch, tmp_path, email_format):
    """F001: der Wochentag "Sun" vor einer Ausblick-Zeile ist keine Spalte
    "Sun" (Sonnenstunden); ebenso wenig ein Etappenname, der mit einem Kuerzel
    beginnt ("Wind Pass", "Sun Valley", auch laenger als das 26-Zeichen-Feld).
    Die korrekte EN-Mail besteht; eine echte Vertauschung faellt weiter auf."""
    daten = _trip_en_daten(email_format)
    eml = _trip_eml(monkeypatch, daten, lang="en", tage=("Fri", "Sat", "Sun"),
                    etappen_namen=("Wind Pass", "Sun Valley", "Sun Valley Traverse to the Hut"))
    konfig = _konfig(tmp_path, f"f001-{email_format}", daten)
    code, aus = _lauf(tmp_path, TRIP, eml, "--konfig", konfig)
    assert code == 0, aus
    falsch = _aendere(eml, plain=lambda p: re.sub(r"(?m)^(Sun .*?)Wind (\S+(?: km/h)?)  Temp (\S+)",
                                                  r"\1Temp \3  Wind \2", p))
    code, aus = _lauf(tmp_path, TRIP, falsch, "--konfig", konfig)
    teil = "Kompakt" if email_format == "compact" else "Klartext"
    assert code == 1 and f"SOLL: Ausblick ({teil}) Zeile 3" in aus and "steht 'Temp' statt 'Wind'" in aus, aus


def test_orte_en_ausblick_sonntag_kein_spaltenkuerzel(monkeypatch, tmp_path):
    """F001 (Orte): EN-Ausblick Wind, Regen ueber Fr/Sa/So -- "Sun" ist der
    Wochentag, keine Spalte; die korrekte Mail besteht."""
    preset = _orte_preset()
    preset["display_config"]["outlook_metrics"] = ["wind", "precipitation"]
    eml = _orte_eml(monkeypatch, preset, lang="en")
    assert re.search(rb"(?m)^Sun ", email.message_from_bytes(eml).get_payload()[0].get_payload(
        decode=True)), "Testaufbau: Sonntag im Ausblick"
    code, aus = _lauf(tmp_path, ORTE, eml, "--konfig", _orte_konfig(tmp_path, preset, "f001o"))
    assert code == 0, aus


@pytest.mark.parametrize("liste", ["leer", "alle_aus"])
def test_trip_leere_email_liste_mit_ausblick_besteht(monkeypatch, tmp_path, liste):
    """F002: leere E-Mail-Liste (``[]`` bzw. alle ``enabled: false``) -- die Mail
    hat keine Stundentabelle, aber den Ausblick. Der sichtbare Ausblick zaehlt;
    "keine Wetterdaten-Tabelle sichtbar" ist dann kein Fehler. Gegen dieselbe
    Konfiguration ohne Ausblick (``[]``) scheitert die Mail weiter."""
    daten = _trip_daten(_TRIP_FOLGE)
    daten["display_config"]["channel_layouts"] = {"email": [] if liste == "leer" else [
        {"metric_id": m, "enabled": False, "bucket": "primary", "order": i}
        for i, m in enumerate(_TRIP_FOLGE)]}
    eml = _trip_eml(monkeypatch, daten)
    konfig = _konfig(tmp_path, f"f002-{liste}", daten)
    code, aus = _lauf(tmp_path, TRIP, eml, "--konfig", konfig)
    assert code == 0, aus
    ohne = copy.deepcopy(daten)
    ohne["display_config"]["outlook_metrics"] = []
    code, aus = _lauf(tmp_path, TRIP, eml, "--konfig", _konfig(tmp_path, f"f002o-{liste}", ohne))
    assert code == 1 and "SOLL: Ausblick (HTML) erscheint" in aus, aus


def test_trip_ausblick_erwartet_aber_versteckt_scheitert(monkeypatch, tmp_path):
    """F002 (Gegenprobe): ohne Stundentabellen muss der erwartete Ausblick bei
    390px und 1000px sichtbar sein -- per ``display:none`` versteckt scheitert die Mail."""
    daten = _trip_daten(_TRIP_FOLGE)
    daten["display_config"]["channel_layouts"] = {"email": []}
    eml = _trip_eml(monkeypatch, daten)
    falsch = _aendere(eml, html=lambda h: h.replace(
        '<table cellpadding="0" cellspacing="0" style="border-collapse:collapse;width:100%;border-top',
        '<table cellpadding="0" cellspacing="0" style="display:none;border-collapse:collapse;'
        'width:100%;border-top', 1))
    code, aus = _lauf(tmp_path, TRIP, falsch, "--konfig", _konfig(tmp_path, "f002v", daten))
    assert code == 1 and "Ausblick-Tabelle sichtbar" in aus, aus


def _ohne_erste_stunden(p: str) -> str:
    """Entfernt nur die Stundenzeilen des ersten Orts im Stundenverlauf."""
    return re.sub(r"(?m)(^Kufstein \(\w+\)\n)(?:   \d{2}:\d{2} .*\n)+", r"\1", p, count=1)


def _ohne_ersten_ausblick(p: str) -> str:
    """Entfernt nur den Ausblick-Block (Ueberschrift + Zeilen) des ersten Orts."""
    from i18n import t

    titel = re.escape(t("vergleich.ausblick.titel", "de"))
    return re.sub(rf"(?m)(^Kufstein \(\w+\)\n(?:   .*\n)*){titel}\n(?:.+\n)*", r"\1", p, count=1)


@pytest.mark.parametrize("entfernt,meldung", [
    (_ohne_erste_stunden, "SOLL: Stundenverlauf (Klartext) fehlt bei Ort 'Kufstein'"),
    (_ohne_ersten_ausblick, "SOLL: Ausblick (Klartext) fehlt bei Ort 'Kufstein'"),
], ids=["stunden", "ausblick"])
def test_orte_einzelner_ortsblock_fehlt_im_klartext_scheitert(tmp_path, orte_mail, entfernt, meldung):
    """F006: fehlt der Stundenverlauf- bzw. Ausblick-Block NUR des ersten Orts im
    Klartext, scheitert der Validator mit Ortsnamen (bisher Exit 0)."""
    eml, konfig = orte_mail
    code, aus = _lauf(tmp_path, ORTE, _aendere(eml, plain=entfernt), "--konfig", konfig)
    assert code == 1 and meldung in aus, aus


def test_orte_ortsabschnitt_fehlt_im_klartext_scheitert(tmp_path, orte_mail):
    """F006: fehlt der ganze Klartext-Abschnitt eines Orts (Stunden und
    Ausblick), stimmen Anzahl und Folge der Ortsabschnitte nicht mehr."""
    eml, konfig = orte_mail
    falsch = _aendere(eml, plain=lambda p: re.sub(r"(?ms)^Innsbruck \(\w+\)\n.*?\n\n", "", p, count=1))
    code, aus = _lauf(tmp_path, ORTE, falsch, "--konfig", konfig)
    assert code == 1 and "SOLL: Ortsabschnitte (Klartext)" in aus and "Ort fehlt: 'Innsbruck'" in aus, aus


@pytest.mark.parametrize("konfig_format,mail_format", [("compact", "full"), ("full", "compact")])
def test_trip_format_widerspricht_konfig_scheitert(monkeypatch, tmp_path, konfig_format, mail_format):
    """F007 (H07): ``X-GZ-Format`` der Mail gegen ``email_format`` der
    Konfiguration -- Kompakt eingestellt, Voll zugestellt (und umgekehrt) scheitert."""
    eml = _trip_eml(monkeypatch, _trip_daten(_TRIP_FOLGE, email_format=mail_format))
    konfig = _konfig(tmp_path, "h07", _trip_daten(_TRIP_FOLGE, email_format=konfig_format))
    code, aus = _lauf(tmp_path, TRIP, eml, "--konfig", konfig)
    assert code == 1 and f"SOLL: Format '{mail_format}' statt '{konfig_format}'" in aus, aus


def test_trip_nachttabelle_trotz_show_night_block_aus_scheitert(tmp_path, trip_mail):
    """F007 (Q10): ``show_night_block`` aus, die Mail traegt die Nachttabelle -> Exit 1."""
    eml, konfig = trip_mail
    daten = json.loads(Path(konfig).read_text(encoding="utf-8"))
    daten["display_config"]["show_night_block"] = False
    code, aus = _lauf(tmp_path, TRIP, eml, "--konfig", _konfig(tmp_path, "q10", daten))
    assert code == 1, aus
    assert "SOLL: Nachttabelle (HTML) erscheint, obwohl show_night_block aus ist" in aus, aus
    assert "SOLL: Nachttabelle (Klartext) erscheint, obwohl show_night_block aus ist" in aus, aus


@pytest.mark.parametrize("orte", [("golden-0",), ("golden-1", "geloescht-9", "golden-2")],
                         ids=["ein_ort", "ort_geloescht"])
def test_orte_mindestzahl_aus_konfig(monkeypatch, tmp_path, orte):
    """F008a: mit ``--konfig`` folgt die erwartete Ortszahl der Konfiguration --
    ein Ein-Ort-Briefing bzw. ein Preset mit geloeschtem Ort (Kennung ohne
    Ortsdatei; der Versand laesst ihn weg, ``order_locations_by_ids``) besteht
    ohne ``--min-locations 1``, ueber die Huelle wie ueber ``--orte``. Ein
    ausdruecklich gesetztes ``--min-locations`` hat Vorrang."""
    preset = _orte_preset(orte=orte)
    eml = _orte_eml(monkeypatch, preset)
    konfig = _orte_konfig(tmp_path, preset, "f008")
    code, aus = _lauf(tmp_path, ORTE, eml, "--konfig", konfig)
    assert code == 0, aus
    roh = _konfig(tmp_path, "f008-roh", preset)
    code, aus = _lauf(tmp_path, ORTE, eml, "--konfig", roh, "--orte", str(_orte_verzeichnis(tmp_path)))
    assert code == 0, aus
    code, aus = _lauf(tmp_path, ORTE, eml, "--konfig", konfig, "--min-locations", "3")
    assert code == 1 and "erwartet: mindestens 3" in aus, aus


def test_orte_mindestzahl_aus_konfig_fehlender_ort_scheitert(monkeypatch, tmp_path):
    """F008a (Gegenprobe): die Konfiguration nennt drei vorhandene Orte, die Mail
    traegt nur zwei -- die aus der Konfiguration abgeleitete Ortszahl verlangt drei."""
    eml = _orte_eml(monkeypatch, _orte_preset(orte=("golden-2", "golden-0")))
    code, aus = _lauf(tmp_path, ORTE, eml, "--konfig", _orte_konfig(tmp_path, _orte_preset(), "f008g"))
    assert code == 1 and "LOCATIONS: 2 Locations gefunden, erwartet: mindestens 3" in aus, aus


def _trip_windrichtung_daten(wind_einfach: bool) -> dict:
    """F004: Wind (Roh bzw. Einfach) + Windrichtung Einfach -> verschmolzen."""
    daten = _trip_daten({"wind": 0, "temperature": 1})
    dc = daten["display_config"]
    dc["metrics"].append({"metric_id": "wind_direction", "enabled": True, "bucket": "primary",
                          "order": 2, "use_friendly_format": True})
    for m in dc["metrics"]:
        if m["metric_id"] == "wind":
            m["use_friendly_format"] = wind_einfach
    return daten


def test_trip_windrichtung_verschmolzen_roh_positiv_und_ohne_richtung_scheitert(monkeypatch, tmp_path):
    """F004: Wind Roh + Windrichtung Einfach -- jede Wind-Zelle zeigt "20 W" und
    besteht; fehlt die Richtung in HTML bzw. Klartext, scheitert die Mail mit Spalte."""
    daten = _trip_windrichtung_daten(wind_einfach=False)
    eml = _trip_eml(monkeypatch, daten)
    konfig = _konfig(tmp_path, "f004r", daten)
    code, aus = _lauf(tmp_path, TRIP, eml, "--konfig", konfig)
    assert code == 0, aus
    falsch = _aendere(eml, html=lambda h: h.replace('data-label="Wind">20 W<', 'data-label="Wind">20<'),
                      plain=lambda p: p.replace("20 W   ", "20     "))
    code, aus = _lauf(tmp_path, TRIP, falsch, "--konfig", konfig)
    assert code == 1, aus
    assert "SOLL: Windrichtung Etappen-Stundentabelle (HTML) 1: Wind-Zelle ohne Kompassrichtung" in aus, aus
    assert "SOLL: Windrichtung Nachttabelle (Klartext) 1: Wind-Zelle ohne Kompassrichtung" in aus, aus


def _wind_nur_ampel(html: str) -> str:
    """Wind-Zelle nur mit Ampelpunkt, ohne Richtung (Stand vor dem Renderer-Fix)."""
    return re.sub(r'(data-label="Wind">)(<span[^>]*></span>)[^<]+<', r"\1\2<", html)


def test_trip_windrichtung_verschmolzen_einfach_ohne_richtung_scheitert(monkeypatch, tmp_path):
    """F004 (Validator-Seite): Wind Einfach + Windrichtung Einfach, die HTML-
    Windzelle zeigt nur den Ampelpunkt ohne Richtung -> der Validator ist nicht
    mehr blind dafuer (Exit 1 mit Spalte), vor wie nach dem Renderer-Fix."""
    daten = _trip_windrichtung_daten(wind_einfach=True)
    eml = _trip_eml(monkeypatch, daten)
    html = next(t.get_payload(decode=True).decode() for t in email.message_from_bytes(eml).walk()
                if t.get_content_type() == "text/html")
    assert 'data-label="Wind"><span' in html, "Testaufbau: Ampelpunkt in der Wind-Zelle"
    falsch = eml if _wind_nur_ampel(html) == html else _aendere(eml, html=_wind_nur_ampel)
    code, aus = _lauf(tmp_path, TRIP, falsch, "--konfig", _konfig(tmp_path, "f004e", daten))
    assert code == 1, aus
    assert "SOLL: Windrichtung Etappen-Stundentabelle (HTML) 1: Wind-Zelle ohne Kompassrichtung" in aus, aus


def test_trip_windrichtung_verschmolzen_einfach_positiv(monkeypatch, tmp_path):
    """F004: Wind Einfach + Windrichtung Einfach -- die HTML-Windzelle zeigt
    Ampelpunkt UND Kompassrichtung (wie der Klartext "20 W"); die Mail besteht.
    Zeigt das HTML eine andere Richtung als der Klartext, scheitert sie."""
    daten = _trip_windrichtung_daten(wind_einfach=True)
    eml = _trip_eml(monkeypatch, daten)
    konfig = _konfig(tmp_path, "f004p", daten)
    code, aus = _lauf(tmp_path, TRIP, eml, "--konfig", konfig)
    assert code == 0, aus
    falsch = _aendere(eml, html=lambda h: re.sub(r'(data-label="Wind"><span[^>]*></span>[^<]*?)W<',
                                                 r"\1O<", h))
    code, aus = _lauf(tmp_path, TRIP, falsch, "--konfig", konfig)
    assert code == 1 and "SOLL: Windrichtung Etappen-Stundentabelle 1: HTML ['O'" in aus, aus


def _trip_nur_nacht(email_format: str) -> dict:
    """F008b: nur die Nacht-Tiefsttemperatur gewaehlt -- keine Groesse mit Kachel."""
    daten = _trip_daten({}, email_format=email_format)
    daten["display_config"]["metrics"].append({"metric_id": "temperature_night", "enabled": True,
                                               "bucket": "primary", "order": 0})
    return daten


@pytest.mark.parametrize("email_format", ["full", "compact"])
def test_trip_ueberblick_nur_ohne_kachel_entfaellt(monkeypatch, tmp_path, email_format):
    """F008b: nur ``temperature_night`` gewaehlt -> kein Metriken-Ueberblick
    (keine Kachel, ``_PILL_CATALOG_ORDER``); die Mail besteht mit ``--konfig``.
    Gegenproben: die Mail MIT Ueberblick gegen diese Konfiguration und die Mail
    OHNE Ueberblick gegen eine Konfiguration mit Temperatur scheitern."""
    nacht = _trip_nur_nacht(email_format)
    eml = _trip_eml(monkeypatch, nacht)
    konfig_nacht = _konfig(tmp_path, f"f008b-{email_format}", nacht)
    code, aus = _lauf(tmp_path, TRIP, eml, "--konfig", konfig_nacht)
    assert code == 0, aus
    voll = _trip_daten(_TRIP_FOLGE, email_format=email_format)
    code, aus = _lauf(tmp_path, TRIP, _trip_eml(monkeypatch, voll), "--konfig", konfig_nacht)
    erscheint = ("SOLL: COMPACT: Block '== Metriken-Ueberblick ==' erscheint" if email_format == "compact"
                 else "SOLL: Metriken-Ueberblick (HTML) erscheint")
    assert code == 1 and erscheint in aus, aus
    code, aus = _lauf(tmp_path, TRIP, eml, "--konfig", _konfig(tmp_path, f"f008b-voll-{email_format}", voll))
    fehlt = ("COMPACT: Block '== Metriken-Ueberblick ==' fehlt" if email_format == "compact"
             else "SOLL: Metriken-Ueberblick fehlt im Klartext-Teil")
    assert code == 1 and fehlt in aus, aus


# --------------------------------------------------------------------------- #
# Nachlieferung 5 (fuenfte unabhaengige Pruefung #3047, F1, F2, A3c)
# --------------------------------------------------------------------------- #
#: Ortsnamen mit Zeichen, die das HTML maskiert (``&#x27;``, ``&amp;``).
_SONDERNAMEN = {"golden-0": "Col d'Izoard", "golden-1": "Alp Nord & Süd", "golden-2": "Hütte A&B"}


def _html_teil(eml: bytes) -> str:
    return next(t.get_payload(decode=True).decode() for t in email.message_from_bytes(eml).walk()
                if t.get_content_type() == "text/html")


@pytest.mark.parametrize("lang", ["de", "en"])
def test_orte_ortsnamen_mit_sonderzeichen_besteht(monkeypatch, tmp_path, lang):
    """F1: Ortsnamen mit Apostroph und ``&`` stehen im HTML maskiert
    (``d&#x27;Izoard``, ``&amp;``). Die korrekte Mail besteht mit ``--konfig``
    (DE und EN); vertauschte Orte scheitern weiter mit dem echten Namen."""
    preset = _orte_preset()
    eml = _orte_eml(monkeypatch, preset, lang=lang, namen=_SONDERNAMEN)
    html = _html_teil(eml)
    assert "d&#x27;Izoard" in html and "Nord &amp; Süd" in html, "Testaufbau: Namen maskiert"
    konfig = _konfig(tmp_path, f"f1-{lang}", {"preset": preset, "orte": _SONDERNAMEN})
    code, aus = _lauf(tmp_path, ORTE, eml, "--konfig", konfig)
    assert code == 0, aus
    falsch = _aendere(eml, html=lambda h: _tausche(h, "Col d&#x27;Izoard", "Alp Nord &amp; Süd"),
                      plain=lambda p: _tausche(p, "Col d'Izoard", "Alp Nord & Süd"))
    code, aus = _lauf(tmp_path, ORTE, falsch, "--konfig", konfig)
    assert code == 1 and "SOLL: Ortsfolge (HTML)" in aus and "SOLL: Ortsfolge (Klartext)" in aus, aus
    assert "steht 'Alp Nord & Süd' statt 'Col d'Izoard'" in aus, aus


#: F2: Etappennamen ueber dem 26-Zeichen-Feld mit Spaltenkuerzeln darin ("Sun"
#: am Ende, wie der Wochentag), dazu Apostroph und "&" (F1 im Trip-Validator).
_LANGE_NAMEN = ("Col d'Izoard & Hütte A&B", "Gust Temp Rain Wind Sun Valley Traverse Hut",
                "Wind Gust Temp Rain Hut Above The Lake Of Sun")


@pytest.mark.parametrize("bekannt", [True, False], ids=["namen_in_konfig", "namen_unbekannt"])
def test_trip_en_ausblick_langer_etappenname_mit_kuerzeln(monkeypatch, tmp_path, bekannt):
    """F2: der Renderer kuerzt den Etappennamen nicht (``f"{name:<26} "``); ein
    Name ueber 26 Zeichen, der Kuerzel enthaelt ("... Lake Of Sun"), ist keine
    Spalte. Die korrekte EN-Mail (Wochentag "Sun", Notizzeilen "↳") besteht --
    mit den Namen aus ``stages[].name`` der Konfiguration wie ohne sie. Eine
    echte Vertauschung in der Zeile mit dem langen Namen faellt weiter auf."""
    daten = _trip_en_daten()
    if bekannt:
        for stage, name in zip(daten["stages"], _LANGE_NAMEN):
            stage["name"] = name
    eml = _trip_eml(monkeypatch, daten, lang="en", tage=("Fri", "Sat", "Sun"),
                    etappen_namen=_LANGE_NAMEN, notiz="Thunderstorms from noon · Rain 6 mm")
    plain = next(t.get_payload(decode=True).decode() for t in email.message_from_bytes(eml).walk()
                 if t.get_content_type() == "text/plain")
    assert f"Sun {_LANGE_NAMEN[2]} Wind " in plain and "    ↳ Thunderstorms" in plain, "Testaufbau"
    konfig = _konfig(tmp_path, f"f2-{bekannt}", daten)
    code, aus = _lauf(tmp_path, TRIP, eml, "--konfig", konfig)
    assert code == 0, aus
    falsch = _aendere(eml, plain=lambda p: re.sub(r"(?m)^(Sun .*?Of Sun )Wind (\S+(?: km/h)?)  Temp (\S+)",
                                                  r"\1Temp \3  Wind \2", p))
    code, aus = _lauf(tmp_path, TRIP, falsch, "--konfig", konfig)
    assert code == 1 and "SOLL: Ausblick (Klartext) Zeile 3" in aus and "steht 'Temp' statt 'Wind'" in aus, aus


def test_trip_ausblick_etappenname_aus_konfig_exakt_abgetrennt(monkeypatch, tmp_path):
    """F2: ein Name mit Doppel-Leerzeichen hinter dem 26-Zeichen-Feld ist nur
    ueber ``stages[].name`` der Konfiguration eindeutig -- mit ihm besteht die
    korrekte Mail (die Zeilenstruktur allein saehe "Sun" als Spalte)."""
    namen = ("Etappe 0", "Etappe 1", "Wind Gust Temp Rain Hut Above  Sun Lake Of Sun")
    daten = _trip_en_daten()
    for stage, name in zip(daten["stages"], namen):
        stage["name"] = name
    eml = _trip_eml(monkeypatch, daten, lang="en", tage=("Fri", "Sat", "Sun"), etappen_namen=namen)
    code, aus = _lauf(tmp_path, TRIP, eml, "--konfig", _konfig(tmp_path, "f2-exakt", daten))
    assert code == 0, aus


def _orte_ausblick_formate() -> dict:
    """A3c: Ausblick Niederschlag/Wind/Temperatur/Boeen; Niederschlag und Boeen
    Einfach, Wind Roh, Temperatur Einfach (ohne Einfach-Form im Ausblick)."""
    preset = _orte_preset()
    preset["display_config"]["outlook_metrics"] = ["precipitation", "wind", "temperature", "gust"]
    preset["display_config"]["outlook_metric_formats"] = {
        "precipitation": True, "wind": False, "temperature": True, "gust": True}
    return preset


def _ausblick_html_zelle(h: str, lang: str, spalte: str, neu: str) -> str:
    """Ersetzt den Inhalt aller Zellen der Spalte ``spalte`` in den Ausblick-Tabellen."""
    from i18n import t

    def _tabelle(m: re.Match) -> str:
        koepfe = [re.sub(r"<[^>]+>", "", k) for k in re.findall(r"<th[^>]*>(.*?)</th>", m.group(), re.S)]
        if not koepfe or koepfe[0] != t("mail.ausblick.spalte_tag", lang) or spalte not in koepfe:
            return m.group()
        i = koepfe.index(spalte)

        def _zeile(z: re.Match) -> str:
            zellen = re.split(r"(?=<td)", z.group(1))
            if len(zellen) > i + 1:
                zellen[i + 1] = re.sub(r"(<td[^>]*>).*?(</td>)", rf"\g<1>{neu}\2", zellen[i + 1], flags=re.S)
            return f"<tr>{''.join(zellen)}</tr>"
        return re.sub(r"<tr>(.*?)</tr>", _zeile, m.group(), flags=re.S)
    return re.sub(r"<table[^>]*>.*?</table>", _tabelle, h, flags=re.S)


@pytest.mark.parametrize("lang", ["de", "en"])
def test_orte_ausblick_roh_einfach(monkeypatch, tmp_path, lang):
    """A3c: der Orte-Validator prueft Roh/Einfach der Ausblick-Zellen wie der
    Trip-Validator (geteilte Mechanik): die korrekte Mail besteht; Einfach als
    Zahl ("Rain 2.4 mm") bzw. Roh als Wort ("Wind maessig") scheitert in HTML
    und Klartext mit Spaltennamen; gegen eine Roh-Konfiguration scheitert sie."""
    preset = _orte_ausblick_formate()
    eml = _orte_eml(monkeypatch, preset, lang=lang)
    konfig = _orte_konfig(tmp_path, preset, f"a3c-{lang}")
    code, aus = _lauf(tmp_path, ORTE, eml, "--konfig", konfig)
    assert code == 0, aus
    for spalte, html_neu, klartext in (("Rain", "2.4 mm", (r"Rain [^\d\s]\S*(?=  )", "Rain 2.4 mm")),
                                       ("Wind", "maessig", (r"Wind \d+ km/h", "Wind maessig"))):
        falsch = _aendere(eml, html=lambda h, s=spalte, n=html_neu: _ausblick_html_zelle(h, lang, s, n),
                          plain=lambda p, k=klartext: re.sub(rf"(?m)^(\S+ .*?){k[0]}", rf"\g<1>{k[1]}", p))
        code, aus = _lauf(tmp_path, ORTE, falsch, "--konfig", konfig)
        assert code == 1, aus
        for teil in ("HTML", "Klartext"):
            assert f"SOLL: Darstellung Ausblick ({teil})" in aus and f"Spalte '{spalte}'" in aus, aus
    roh = copy.deepcopy(preset)
    roh["display_config"]["outlook_metric_formats"] = {}
    code, aus = _lauf(tmp_path, ORTE, eml, "--konfig", _orte_konfig(tmp_path, roh, f"a3c-roh-{lang}"))
    assert code == 1 and "SOLL: Darstellung Ausblick" in aus and "Spalte 'Rain'" in aus, aus


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


# --------------------------------------------------------------------------- #
# Runde 7, Paket p4 (AC-27): Ausblick-Zeilenzahl, Zusatzbloecke, Roh/Einfach der
# Vergleichstabelle, Klartext-Stunden ab Zeile 2, Tagesfenster, Ortsabschnitte
# sprachunabhaengig, Warnzeile/Hinweis (AC-28), Mutations-Testluecken V01-V03.
# Mails aus der echten Kette wie oben; Verfaelschung per Textaenderung.
# --------------------------------------------------------------------------- #
_MAILTAG = date(2026, 7, 20)  # Datum der Fixture-Etappe (``fx.segment``), Montag


def _wochentage(lang: str, n: int = 3) -> tuple:
    from datetime import timedelta

    from i18n.format import fmt_weekday

    return tuple(fmt_weekday(_MAILTAG + timedelta(days=i + 1), lang) for i in range(n))


def _mit_etappen(daten: dict, folgende: int) -> dict:
    """Etappen ab dem Mail-Tag: die berichtete Etappe plus ``folgende`` weitere
    (Scheduler: ``get_future_stages`` -> hoechstens drei Ausblick-Zeilen)."""
    from datetime import timedelta

    vorlage = daten["stages"][0]
    daten["stages"] = [{**copy.deepcopy(vorlage), "id": f"R{i}", "name": f"Etappe {i}",
                        "date": (_MAILTAG + timedelta(days=i)).isoformat()} for i in range(folgende + 1)]
    return daten


def _trip_eml_r7(monkeypatch, daten: dict, *, lang: str = "de", report: str = "evening",
                 stage_stats: dict | None = None, vortag: bool = False, tage=None) -> bytes:
    """Wie ``_trip_eml``, zusaetzlich Morgen/Abend (Ausblick nur fuer Berichte in
    ``multi_day_trend_reports``, wie der Scheduler), Etappen-Kennzahlen und
    Vortag-Vergleich (Renderer gatet sie an ``show_stage_stats``/
    ``show_yesterday_comparison``)."""
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
    _sprache_setzen(uid, lang)
    trip = load_trip(copy.deepcopy(daten), user_id=uid)
    seg = fx.segment()
    zeilen = [build_outlook_row(seg.aggregated, seg.timeseries.data, tag, fx.TZ,
                                trip_display_config=trip.display_config, report_type=report,
                                context="route", ampel=resolve_ampel(trip.display_config), lang=lang)
              for tag in (tage or _wochentage(lang))]
    rc = trip.report_config
    vergleich = None
    if vortag:
        from services.day_comparison import DayComparison
        vergleich = DayComparison(wind_delta_kmh=12.0, gust_delta_kmh=18.0, precip_delta_mm=4.0)
    NotificationService(user_id=uid).send_trip_report(TripReportRequest(
        trip=trip, report_type=report, segment_weather=[seg], trip_tz=fx.TZ,
        night_weather=fx.night_weather(), stage_name=fx.STAGE_NAME,
        multi_day_trend=zeilen if report in (rc.multi_day_trend_reports or []) else None,
        report_config=rc, display_config=trip.display_config, send_email=True,
        stage_stats=stage_stats, day_comparison=vergleich,
    ))
    sendung = mit.sendungen("email")[-1]
    return _mime(sendung, to=f"{uid}@example.invalid", html=sendung["mail_format"] == "full", lang=lang)


def _zeile_weg_html(tag: str):
    return lambda h: re.sub(rf"<tr>(?:(?!</tr>).)*?>{tag}</td>(?:(?!</tr>).)*?</tr>", "", h, flags=re.S)


def _zeile_weg_klartext(tag: str):
    return lambda p: re.sub(rf"(?m)^{tag} .*\n", "", p)


# ---- B-V1 Trip: Zahl der Ausblick-Zeilen = folgende Etappen (hoechstens 3) ---- #
@pytest.mark.parametrize("lang", ["de", "en"])
def test_r7_trip_ausblick_tageszeile_fehlt_scheitert(monkeypatch, tmp_path, lang):
    daten = _mit_etappen(_trip_daten(_TRIP_FOLGE), folgende=4)
    eml, konfig = _trip_eml_r7(monkeypatch, daten, lang=lang), _konfig(tmp_path, "r7", daten)
    code, aus = _lauf(tmp_path, TRIP, eml, "--konfig", konfig)
    assert code == 0, aus
    mitte = _wochentage(lang)[1]
    falsch = _aendere(eml, html=_zeile_weg_html(mitte), plain=_zeile_weg_klartext(mitte))
    code, aus = _lauf(tmp_path, TRIP, falsch, "--konfig", konfig)
    assert code == 1, aus
    assert "SOLL: Ausblick (HTML) hat 2 Tageszeilen, erwartet 3" in aus, aus
    assert "SOLL: Ausblick (Klartext) hat 2 Tageszeilen, erwartet 3" in aus, aus


def test_r7_trip_ausblick_zeilen_nach_folgenden_etappen(monkeypatch, tmp_path):
    """Zwei folgende Etappen -> zwei Zeilen; die Mail mit drei Zeilen ist falsch,
    die mit zwei richtig."""
    daten = _mit_etappen(_trip_daten(_TRIP_FOLGE), folgende=2)
    konfig = _konfig(tmp_path, "r7-2", daten)
    code, aus = _lauf(tmp_path, TRIP, _trip_eml_r7(monkeypatch, daten), "--konfig", konfig)
    assert code == 1 and "SOLL: Ausblick (HTML) hat 3 Tageszeilen, erwartet 2" in aus, aus
    zwei = _trip_eml_r7(monkeypatch, daten, tage=_wochentage("de", 2))
    code, aus = _lauf(tmp_path, TRIP, zwei, "--konfig", konfig)
    assert code == 0, aus


def test_r7_trip_ausblick_zeile_fehlt_nur_im_klartext_scheitert(tmp_path, trip_mail):
    """Ohne verankerbare Etappendaten: HTML und Klartext tragen gleich viele Zeilen."""
    eml, konfig = trip_mail
    falsch = _aendere(eml, plain=_zeile_weg_klartext("Mi"))
    code, aus = _lauf(tmp_path, TRIP, falsch, "--konfig", konfig)
    assert code == 1, aus
    assert "SOLL: Ausblick Tageszeilen: HTML 3, Klartext 2" in aus, aus


def test_r7_trip_kompakt_ausblick_tageszeile_fehlt_scheitert(monkeypatch, tmp_path):
    daten = _mit_etappen(_trip_daten(_TRIP_FOLGE, email_format="compact"), folgende=3)
    eml, konfig = _trip_eml_r7(monkeypatch, daten), _konfig(tmp_path, "r7k", daten)
    assert _lauf(tmp_path, TRIP, eml, "--konfig", konfig)[0] == 0
    code, aus = _lauf(tmp_path, TRIP, _aendere(eml, plain=_zeile_weg_klartext("Mi")), "--konfig", konfig)
    assert code == 1 and "SOLL: Ausblick (Kompakt) hat 2 Tageszeilen, erwartet 3" in aus, aus


# ---- B-V1 Orte: Ausblick je Ort, drei Tageszeilen ---- #
def test_r7_orte_ausblick_tageszeile_fehlt_scheitert(tmp_path, orte_mail):
    eml, konfig = orte_mail
    falsch = _aendere(eml, html=_zeile_weg_html("Sa"), plain=_zeile_weg_klartext("Sa"))
    code, aus = _lauf(tmp_path, ORTE, falsch, "--konfig", konfig)
    assert code == 1, aus
    assert "SOLL: Ausblick (HTML) Tabelle 1: 2 Tageszeilen, erwartet 3" in aus, aus
    assert "SOLL: Ausblick (Klartext) Ort 2: 2 Tageszeilen, erwartet 3" in aus, aus


def _letzter_ausblick_weg(h: str) -> str:
    from i18n import t

    # #3155: Etikett aus dem Katalog ("3-Tages-Ausblick", vorher "AUSBLICK").
    etikett = re.escape(t("vergleich.ausblick.eyebrow", "de"))
    treffer = list(re.finditer(rf"<div[^>]*>\s*<div[^>]*>\s*<span[^>]*>{etikett}</span>.*?</table>\s*</div>",
                               h, re.S))
    return h[:treffer[-1].start()] + h[treffer[-1].end():]


def test_r7_orte_ausblick_eines_orts_fehlt_im_html_scheitert(tmp_path, orte_mail):
    eml, konfig = orte_mail
    code, aus = _lauf(tmp_path, ORTE, _aendere(eml, html=_letzter_ausblick_weg), "--konfig", konfig)
    assert code == 1, aus
    assert "SOLL: Ausblick (HTML): 2 Orts-Abschnitte statt 3" in aus, aus


# ---- B-V2 Zusatzbloecke (Vollformat); Kompakt ignoriert die Schalter (#722) ---- #
_KENNZAHLEN = {"distance_km": 12.3, "ascent_m": 800, "descent_m": 400, "max_elevation_m": 2100}


@pytest.mark.parametrize("lang", ["de", "en"])
def test_r7_trip_zusatzbloecke_trotz_aus_scheitern(monkeypatch, tmp_path, lang):
    an = _trip_daten(_TRIP_FOLGE)
    aus_daten = copy.deepcopy(an)
    aus_daten["report_config"].update(show_stage_stats=False, show_yesterday_comparison=False)
    mit = _trip_eml_r7(monkeypatch, an, lang=lang, stage_stats=_KENNZAHLEN, vortag=True)
    code, aus = _lauf(tmp_path, TRIP, mit, "--konfig", _konfig(tmp_path, "an", an))
    assert code == 0, aus
    code, aus = _lauf(tmp_path, TRIP, mit, "--konfig", _konfig(tmp_path, "aus", aus_daten))
    assert code == 1, aus
    for teil in ("HTML", "Klartext"):
        assert f"SOLL: Etappen-Kennzahlen ({teil}) erscheinen, obwohl show_stage_stats aus ist" in aus, aus
        assert f"SOLL: Vortag-Vergleich ({teil}) erscheint, obwohl show_yesterday_comparison aus ist" in aus, aus
    ohne = _trip_eml_r7(monkeypatch, aus_daten, lang=lang, stage_stats=_KENNZAHLEN, vortag=True)
    code, aus = _lauf(tmp_path, TRIP, ohne, "--konfig", _konfig(tmp_path, "aus2", aus_daten))
    assert code == 0, aus


def test_r7_trip_kompakt_ignoriert_bausteinschalter(monkeypatch, tmp_path):
    """PO-Entscheidung #722: das Kompaktformat zeigt Ueberblick, Kennzahlen und
    Ausblick unabhaengig von den Baustein-Schaltern -- kein Fehler bei Aus."""
    an = _mit_etappen(_trip_daten(_TRIP_FOLGE, email_format="compact"), folgende=3)
    eml = _trip_eml_r7(monkeypatch, an, stage_stats=_KENNZAHLEN)
    assert b"12.3 km" in eml, "Vorbedingung: Kennzahlen in der Kompakt-Mail"
    aus_daten = copy.deepcopy(an)
    aus_daten["report_config"].update(show_stage_stats=False, show_outlook=False)
    code, aus = _lauf(tmp_path, TRIP, eml, "--konfig", _konfig(tmp_path, "kaus", aus_daten))
    assert code == 0, aus


def test_r7_trip_show_outlook_aus_vollformat(monkeypatch, tmp_path):
    """Mutation V14: ``show_outlook`` aus -> im Vollformat kein Ausblick."""
    daten = _trip_daten(_TRIP_FOLGE)
    aus_daten = copy.deepcopy(daten)
    aus_daten["report_config"]["show_outlook"] = False
    konfig = _konfig(tmp_path, "oaus", aus_daten)
    code, aus = _lauf(tmp_path, TRIP, _trip_eml_r7(monkeypatch, aus_daten), "--konfig", konfig)
    assert code == 0, aus
    code, aus = _lauf(tmp_path, TRIP, _trip_eml_r7(monkeypatch, daten), "--konfig", konfig)
    assert code == 1 and "SOLL: Ausblick (HTML) erscheint, obwohl er laut Konfiguration aus ist" in aus, aus


# ---- B-V3 Roh/Einfach der Vergleichstabelle (HTML und Klartext) ---- #
@pytest.fixture
def orte_darstellung_mail(monkeypatch, tmp_path):
    preset = _orte_preset()
    preset["display_config"]["active_metrics"] = ["wind_max_kmh", "temp_max_c", "precip_sum_mm", "gust_max_kmh"]
    preset["display_config"]["channel_layouts"] = {"email": [
        {"metric_id": "gust", "enabled": True, "use_friendly_format": True},
        {"metric_id": "temperature", "enabled": True},
        {"metric_id": "precipitation", "enabled": True, "format": "simplified"},
        {"metric_id": "wind", "enabled": True, "use_friendly_format": False}]}
    return _orte_eml(monkeypatch, preset), _orte_konfig(tmp_path, preset, "darst")


def test_r7_orte_vergleich_roh_einfach_positiv(tmp_path, orte_darstellung_mail):
    eml, konfig = orte_darstellung_mail
    code, aus = _lauf(tmp_path, ORTE, eml, "--konfig", konfig)
    assert code == 0, aus


_DARSTELLUNG_FAELLE = {
    "html_zahl_statt_ampel": ("HTML", "Böen", {"html": lambda h: re.sub(
        r"(>Böen</td>(?:<td[^>]*>)?)<span[^>]*border-radius:50%[^>]*></span>", r"\g<1>48 km/h", h)}),
    "klartext_zahl_statt_wort": ("Klartext", "Niederschlag", {"plain": lambda p: re.sub(
        r"Niederschlag: [a-zäöü]+", "Niederschlag: 8.4 mm", p)}),
    "klartext_wort_statt_zahl": ("Klartext", "Wind", {"plain": lambda p: re.sub(
        r"Wind: \d+ km/h", "Wind: stark", p)}),
}


@pytest.mark.parametrize("fall", list(_DARSTELLUNG_FAELLE))
def test_r7_orte_vergleich_falsche_darstellung_scheitert(tmp_path, orte_darstellung_mail, fall):
    eml, konfig = orte_darstellung_mail
    teil, spalte, aenderung = _DARSTELLUNG_FAELLE[fall]
    code, aus = _lauf(tmp_path, ORTE, _aendere(eml, **aenderung), "--konfig", konfig)
    assert code == 1, aus
    assert f"SOLL: Darstellung Vergleichstabelle ({teil})" in aus and f"'{spalte}'" in aus, aus


# ---- B-V4 Klartext-Stundenverlauf: jede Stundenzeile ---- #
def test_r7_orte_klartext_spalte_fehlt_ab_zeile_zwei_scheitert(tmp_path, orte_mail):
    eml, konfig = orte_mail
    falsch = _aendere(eml, plain=lambda p: re.sub(r"(?m)^(   11:00  .*?)  Temp \S+(.*)$", r"\1\2", p))
    code, aus = _lauf(tmp_path, ORTE, falsch, "--konfig", konfig)
    assert code == 1, aus
    assert "SOLL: Stundenverlauf (Klartext) Ort 1 Zeile 4" in aus and "Spalte fehlt: 'Temp'" in aus, aus


# ---- B-V5 Tagesfenster des Presets ---- #
def test_r7_orte_tagesfenster_wird_nicht_abgelehnt(tmp_path, orte_mail):
    eml, _konfig_alt = orte_mail
    preset = _orte_preset()
    preset.update(day_window_start_hour=12, day_window_end_hour=16)
    konfig = _orte_konfig(tmp_path, preset, "tf")
    fenster = _aendere(eml, html=lambda h: re.sub(
        r"<tr[^>]*><td[^>]*>(?:08|09|10|11)</td>(?:(?!</tr>).)*</tr>", "", h, flags=re.S),
        plain=lambda p: re.sub(r"(?m)^   (?:08|09|10|11):00  .*\n", "", p))
    code, aus = _lauf(tmp_path, ORTE, fenster, "--konfig", konfig)
    assert code == 0, aus
    code, aus = _lauf(tmp_path, ORTE, eml, "--konfig", konfig)
    assert code == 1 and "ausserhalb des Tagesfensters 12–16" in aus, aus


# ---- B-V7 Ortsabschnitte sprachunabhaengig ---- #
def _abschnitte_tauschen(h: str) -> str:
    return re.sub(r'(letter-spacing:0\.1em;">[^<]*</span> <span style="font-size:15px;[^"]*">)(Kufstein|Innsbruck)<',
                  lambda m: m.group(1) + {"Kufstein": "Innsbruck", "Innsbruck": "Kufstein"}[m.group(2)] + "<", h)


@pytest.mark.parametrize("lang", ["de", "en"])
@pytest.mark.parametrize("eyebrow", ["unveraendert", "uebersetzt"])
def test_r7_orte_ortsabschnitte_html_vertauscht_scheitert(monkeypatch, tmp_path, lang, eyebrow):
    """Nur die HTML-Ortsabschnitte vertauscht (Uebersicht und Klartext richtig);
    ``uebersetzt`` simuliert die Uebersetzung des Etiketts "ORT" (#3074)."""
    preset = _orte_preset()
    eml, konfig = _orte_eml(monkeypatch, preset, lang=lang), _orte_konfig(tmp_path, preset, "ab")
    if eyebrow == "uebersetzt":
        eml = _aendere(eml, html=lambda h: h.replace(">ORT</span>", ">PLACE</span>"))
    code, aus = _lauf(tmp_path, ORTE, eml, "--konfig", konfig)
    assert code == 0, aus
    code, aus = _lauf(tmp_path, ORTE, _aendere(eml, html=_abschnitte_tauschen), "--konfig", konfig)
    assert code == 1 and "SOLL: Ortsfolge (HTML-Abschnitte)" in aus, aus


# ---- AC-28 Warnzeile bei Schalter aus, Hinweis "nicht abrufbar" im Klartext ---- #
def _ohne_warnzeile(h: str) -> str:
    return re.sub(r"<tr[^>]*>\s*<td[^>]*>Amtliche Warnungen</td>(?:(?!</tr>).)*</tr>", "", h, count=1, flags=re.S)


def test_r7_orte_warnzeile_folgt_dem_schalter(tmp_path, orte_mail):
    eml, konfig_an = orte_mail
    preset = _orte_preset()
    preset.update(official_alerts_enabled=False, official_warnings={"enabled": False})  # E4: beide aus
    konfig_aus = _orte_konfig(tmp_path, preset, "waus")
    # #3047 Runde 7 (p4b, B-L5): Schalter aus = kein Abruf, also auch kein
    # Hinweis "nicht abrufbar" (``comparison_engine``) -- die Aus-Mail traegt
    # weder Warnzeile noch Hinweis (HTML und Klartext).
    ohne = _aendere(eml, html=lambda h: re.sub(
        r'<div[^>]*><strong[^>]*>Amtliche Warnungen aktuell nicht abrufbar</strong>.*?</p></div>', "",
        _ohne_warnzeile(h), count=1, flags=re.S),
        plain=lambda p: re.sub(r"(?m)^.*Amtliche Warnungen aktuell nicht abrufbar.*\n\n", "", p, count=1))
    code, aus = _lauf(tmp_path, ORTE, ohne, "--konfig", konfig_aus)
    assert code == 0, aus
    code, aus = _lauf(tmp_path, ORTE, eml, "--konfig", konfig_aus)
    assert code == 1 and "Spalte zu viel: 'Amtliche Warnungen'" in aus, aus
    code, aus = _lauf(tmp_path, ORTE, ohne, "--konfig", konfig_an)
    assert code == 1 and "Spalte fehlt: 'Amtliche Warnungen'" in aus, aus


@pytest.mark.parametrize("lang", ["de", "en"])
def test_r7_orte_klartext_hinweis_nicht_abrufbar_wie_html(tmp_path, monkeypatch, lang):
    """AC-28 (nach p2): die echte Mail traegt den Hinweis in beiden Teilen und
    besteht; fehlt er im Klartext, scheitert sie."""
    from i18n import t

    preset = _orte_preset()
    eml, konfig = _orte_eml(monkeypatch, preset, lang=lang), _orte_konfig(tmp_path, preset, "hw")
    hinweis = t("mail.hinweis.warnungen_nicht_abrufbar.text", lang)
    # Vorbedingung (Hinweis im Klartext der echten Mail) prueft ``_aendere``.
    code, aus = _lauf(tmp_path, ORTE, eml, "--konfig", konfig)
    assert code == 0, aus
    falsch = _aendere(eml, plain=lambda p: re.sub(rf"(?m)^.*{re.escape(hinweis)}\n", "", p))
    code, aus = _lauf(tmp_path, ORTE, falsch, "--konfig", konfig)
    assert code == 1 and "SOLL: Hinweis 'Amtliche Warnungen nicht abrufbar' fehlt im Klartext-Teil" in aus, aus


@pytest.mark.parametrize("lang", ["de", "en"])
def test_r7_orte_warnungen_aus_echte_mail(tmp_path, monkeypatch, lang):
    """AC-28 / E4 (nach p2): Briefing- und Alarm-Schalter aus -> die echte Mail
    hat keine Warnzeile; der Validator findet die Vergleichstabelle ueber die
    Kopfzelle und besteht. Gegen die Konfiguration "an" (Mischzustand: nur der
    Alarm-Schalter an = beides an) fehlt die Zeile."""
    from i18n import t

    aus_preset = _orte_preset()
    aus_preset.update(official_alerts_enabled=False, official_warnings={"enabled": False})
    eml = _orte_eml(monkeypatch, aus_preset, lang=lang)
    assert t("vergleich.zeile.amtliche_warnungen", lang).encode() not in eml, "Vorbedingung: keine Warnzeile"
    code, aus = _lauf(tmp_path, ORTE, eml, "--konfig", _orte_konfig(tmp_path, aus_preset, "waus"))
    assert code == 0, aus
    misch = copy.deepcopy(aus_preset)
    misch["official_warnings"] = {"enabled": True}
    code, aus = _lauf(tmp_path, ORTE, eml, "--konfig", _orte_konfig(tmp_path, misch, "wmisch"))
    warn = t("vergleich.zeile.amtliche_warnungen", lang)
    assert code == 1 and f"Spalte fehlt: '{warn}'" in aus, aus


def test_r7_orte_ortsabschnitt_fehlt_im_html_scheitert(tmp_path, orte_mail):
    """B-V7: fehlt der HTML-Abschnittskopf eines erwarteten Orts, meldet die
    Ortsfolge der Abschnitte ihn (nicht nur die Strukturpruefung)."""
    eml, konfig = orte_mail
    falsch = _aendere(eml, html=lambda h: re.sub(
        r'<div style="padding-bottom:8px;[^"]*"><span[^>]*>ORT</span> <span[^>]*>Lienz</span>.*?</div>', "", h,
        count=1, flags=re.S))
    code, aus = _lauf(tmp_path, ORTE, falsch, "--konfig", konfig)
    assert code == 1 and "SOLL: Ortsfolge (HTML-Abschnitte): Ort fehlt: 'Lienz'" in aus, aus


@pytest.mark.parametrize("form", ["zeichenketten", "ohne_enabled"])
def test_r7_trip_altformat_ohne_order_register_prioritaet(monkeypatch, tmp_path, form):
    """B-L6 (Tech-Lead-Entscheidung Runde 7): Altformat ohne ``order`` -> die
    Mail ordnet nach Register-Prioritaet (Loader ``auto_distribute``: Temp,
    Boeen, Regen), das Soll ebenso; vertauschte Spalten scheitern."""
    daten = _trip_daten(_TRIP_FOLGE)
    ids = ["gust", "precipitation", "temperature"]
    daten["display_config"]["metrics"] = ids if form == "zeichenketten" else [{"metric_id": m} for m in ids]
    eml, konfig = _trip_eml(monkeypatch, daten), _konfig(tmp_path, "alt", daten)
    code, aus = _lauf(tmp_path, TRIP, eml, "--konfig", konfig)
    assert code == 0, aus
    code, aus = _lauf(tmp_path, TRIP, _aendere(eml, html=lambda h: _tausche(h, ">Gust</th>", ">Rain</th>")),
                      "--konfig", konfig)
    assert code == 1 and "SOLL: Etappen-Stundentabelle (HTML)" in aus, aus


# ---- B-V8 / H1: Kanal-Liste nach order, Bericht-Flags je Metrik ---- #
def test_r7_trip_kanal_liste_array_ungleich_order(monkeypatch, tmp_path):
    """Mutation V03: ``channel_layouts.email`` in Array-Folge Wind, Regen, Temp,
    ``order`` Regen, Temp, Wind -- die Mail folgt ``order``, das Soll auch."""
    daten = _trip_daten({"temperature": 0, "wind": 1, "precipitation": 2})
    daten["display_config"]["channel_layouts"] = {"email": [
        {"metric_id": "wind", "enabled": True, "bucket": "primary", "order": 2},
        {"metric_id": "precipitation", "enabled": True, "bucket": "primary", "order": 0},
        {"metric_id": "temperature", "enabled": True, "bucket": "primary", "order": 1}]}
    code, aus = _lauf(tmp_path, TRIP, _trip_eml(monkeypatch, daten), "--konfig", _konfig(tmp_path, "t23", daten))
    assert code == 0, aus


def _trip_morgen_flag() -> dict:
    daten = _trip_daten(_TRIP_FOLGE)
    for m in daten["display_config"]["metrics"]:
        if m["metric_id"] == "gust":
            m["morning_enabled"] = False
    return daten


def test_r7_trip_morgen_flag_je_metrik(monkeypatch, tmp_path):
    """H1 (Mutationen V01, V02, V19): Boeen nur abends. Morgen- und Abendmail
    derselben Konfiguration bestehen; eine Morgenmail mit Boeen scheitert."""
    daten = _trip_morgen_flag()
    konfig = _konfig(tmp_path, "h1", daten)
    for report in ("morning", "evening"):
        code, aus = _lauf(tmp_path, TRIP, _trip_eml_r7(monkeypatch, daten, report=report), "--konfig", konfig)
        assert code == 0, (report, aus)
    code, aus = _lauf(tmp_path, TRIP, _trip_eml_r7(monkeypatch, _trip_daten(_TRIP_FOLGE), report="morning"),
                      "--konfig", konfig)
    assert code == 1 and "Spalte zu viel: 'Gust'" in aus, aus


def test_r7_orte_stundenverlauf_aus(monkeypatch, tmp_path):
    """Mutation V18: ``hourly_enabled: false`` -> kein Stundenverlauf erwartet."""
    preset = _orte_preset()
    preset["hourly_enabled"] = False
    code, aus = _lauf(tmp_path, ORTE, _orte_eml(monkeypatch, preset), "--konfig", _orte_konfig(tmp_path, preset, "haus"))
    assert code == 0, aus


# --------------------------------------------------------------------------- #
# Runde 7, Paket p4b (B-L5, Punkt 2): der Trip-Validator prueft amtliche
# Warnungen (Schalter E4, erste Stelle), die Kachelfolge des Ueberblicks, die
# Ampelfarbe gegen die Ampel-Grenzen und die erlaubten Stunden aus Tagesfenster
# und Etappenstart; der Orte-Validator die Zeilen bei nie eingestellter
# Grundauswahl, den Zieltag, den Hinweis "nicht abrufbar" bei Schalter aus und
# die Ampelfarbe. Je Pruefung: die echte Mail besteht, die verfaelschte nicht.
# --------------------------------------------------------------------------- #
_WARN_AUS = {"official_alerts_enabled": False, "official_warnings": {"enabled": False}}


def _segment_naht(monkeypatch, *, warnungen: bool = False, nicht_abrufbar: bool = False, start=None):
    """Wetter-Naht der Trip-Kette: die Etappe aus ``fx.segment`` mit einer
    amtlichen Warnung und/oder Ausfall der Warnquelle (wie der Zeitplaner sie
    bei Schalter an liefert) bzw. mit anderem Etappenstart."""
    from datetime import timezone

    from services.official_alerts.models import OfficialAlert
    from tests.tdd import _einstellung_auslieferung_fixtures as fx

    original = fx.segment

    def _segment(*args, **kwargs):
        s = original(*args, **kwargs)
        if warnungen:
            s.official_alerts = [OfficialAlert(
                source="meteofrance", hazard="thunderstorm", level=3, label="Orages",
                region_label="Haute-Corse", valid_from=datetime(2026, 7, 20, 6, tzinfo=timezone.utc),
                valid_to=datetime(2026, 7, 20, 22, tzinfo=timezone.utc))]
        s.official_alerts_unavailable = nicht_abrufbar
        if start is not None:
            s.segment = dataclasses.replace(s.segment, start_time=start)
        return s

    monkeypatch.setattr(fx, "segment", _segment)


def _warnblock_nach_hinten(text: str, kopf: str, vor: str) -> str:
    """Schneidet den Block ``kopf`` (bis zur Leerzeile) aus und setzt ihn vor ``vor``."""
    block = re.search(rf"{re.escape(kopf)}\n(?:.+\n)*\n", text).group(0)
    rest = text.replace(block, "", 1)
    return rest.replace(vor, block + vor, 1)


@pytest.mark.parametrize("lang", ["de", "en"])
def test_r7b_trip_warnungen_trotz_schalter_aus_scheitern(monkeypatch, tmp_path, lang):
    """Briefing- und Alarm-Schalter aus: die echte Mail (kein Abruf) besteht;
    die Mail mit Warnblock und Hinweis "nicht abrufbar" scheitert in HTML und
    Klartext. Mischzustand (nur Alarm an) = beides an (E4): sie besteht."""
    aus = {**_trip_daten(_TRIP_FOLGE), **_WARN_AUS}
    konfig = _konfig(tmp_path, "waus", aus)
    code, text = _lauf(tmp_path, TRIP, _trip_eml(monkeypatch, aus, lang=lang), "--konfig", konfig)
    assert code == 0, text
    _segment_naht(monkeypatch, warnungen=True, nicht_abrufbar=True)
    mit = _trip_eml(monkeypatch, aus, lang=lang)
    code, text = _lauf(tmp_path, TRIP, mit, "--konfig", konfig)
    assert code == 1, text
    for teil in ("HTML", "Klartext"):
        assert f"SOLL: Amtliche Warnungen ({teil}) erscheinen, obwohl sie laut Konfiguration aus sind" in text, text
    misch = {**aus, "official_warnings": {"enabled": True}}
    code, text = _lauf(tmp_path, TRIP, mit, "--konfig", _konfig(tmp_path, "wmisch", misch))
    assert code == 0, text


def test_r7b_trip_kompakt_warnungen_trotz_schalter_aus_scheitern(monkeypatch, tmp_path):
    aus = {**_trip_daten(_TRIP_FOLGE, email_format="compact"), **_WARN_AUS}
    konfig = _konfig(tmp_path, "kwaus", aus)
    code, text = _lauf(tmp_path, TRIP, _trip_eml(monkeypatch, aus), "--konfig", konfig)
    assert code == 0, text
    _segment_naht(monkeypatch, warnungen=True)
    code, text = _lauf(tmp_path, TRIP, _trip_eml(monkeypatch, aus), "--konfig", konfig)
    assert code == 1 and "SOLL: Amtliche Warnungen (Kompakt) erscheinen" in text, text


@pytest.mark.parametrize("lang", ["de", "en"])
def test_r7b_trip_warnungen_an_erster_stelle(monkeypatch, tmp_path, lang):
    """AC-25/WV6: die echte Mail mit Warnung besteht; steht der Warnblock hinter
    dem Metriken-Ueberblick (Klartext) bzw. der Ueberblick vor ihm (HTML),
    scheitert sie."""
    from i18n import t

    daten = _trip_daten(_TRIP_FOLGE)
    konfig = _konfig(tmp_path, "wan", daten)
    _segment_naht(monkeypatch, warnungen=True, nicht_abrufbar=True)
    eml = _trip_eml(monkeypatch, daten, lang=lang)
    code, text = _lauf(tmp_path, TRIP, eml, "--konfig", konfig)
    assert code == 0, text
    pillen = t("mail.pille.ueberschrift", lang)
    klartext = _aendere(eml, plain=lambda p: _warnblock_nach_hinten(
        p, f"━━ {t('mail.warnungen.ueberschrift', lang)} ━━", "━━ Segment"))
    code, text = _lauf(tmp_path, TRIP, klartext, "--konfig", konfig)
    assert code == 1 and "SOLL: Amtliche Warnungen (Klartext) stehen nicht an erster Stelle" in text, text

    def _ueberblick_nach_vorn(h: str) -> str:
        block = re.search(rf'<div[^>]*><p[^>]*>{re.escape(pillen)}</p><div[^>]*>.*?</div></div>', h, re.S).group(0)
        return h.replace(block, "", 1).replace('<div class="wb ', block + '<div class="wb ', 1)
    code, text = _lauf(tmp_path, TRIP, _aendere(eml, html=_ueberblick_nach_vorn), "--konfig", konfig)
    assert code == 1 and "SOLL: Amtliche Warnungen (HTML) stehen nicht an erster Stelle" in text, text


def test_r7b_trip_kompakt_warnungen_an_erster_stelle(monkeypatch, tmp_path):
    from i18n import t

    daten = _trip_daten(_TRIP_FOLGE, email_format="compact")
    konfig = _konfig(tmp_path, "kwan", daten)
    _segment_naht(monkeypatch, warnungen=True)
    eml = _trip_eml(monkeypatch, daten)
    code, text = _lauf(tmp_path, TRIP, eml, "--konfig", konfig)
    assert code == 0, text
    falsch = _aendere(eml, plain=lambda p: _warnblock_nach_hinten(
        p, f"== {t('mail.kompakt.warnungen', 'de')} ==", t("mail.ausblick.name", "de")))
    code, text = _lauf(tmp_path, TRIP, falsch, "--konfig", konfig)
    assert code == 1 and "SOLL: Amtliche Warnungen (Kompakt) stehen nicht an erster Stelle" in text, text


def _pillen_tauschen_klartext(kopf: str):
    def _tausch(p: str) -> str:
        zeilen = p.split("\n")
        i = zeilen.index(kopf)
        zeilen[i + 1], zeilen[i + 2] = zeilen[i + 2], zeilen[i + 1]
        return "\n".join(zeilen)
    return _tausch


@pytest.mark.parametrize("lang", ["de", "en"])
def test_r7b_trip_ueberblick_folge_vertauscht_scheitert(monkeypatch, tmp_path, lang):
    """Kacheln in der Folge der E-Mail-Liste (Boeen, Temp, Regen, Wind, #1703 S7):
    die echte Mail besteht, zwei vertauschte Kacheln scheitern je Teil."""
    from i18n import t

    daten = _trip_daten(_TRIP_FOLGE)
    eml, konfig = _trip_eml(monkeypatch, daten, lang=lang), _konfig(tmp_path, "pf", daten)
    code, text = _lauf(tmp_path, TRIP, eml, "--konfig", konfig)
    assert code == 0, text
    titel = t("mail.pille.ueberschrift", lang)
    code, text = _lauf(tmp_path, TRIP, _aendere(eml, plain=_pillen_tauschen_klartext(f"━━ {titel} ━━")),
                       "--konfig", konfig)
    assert code == 1 and "SOLL: Metriken-Ueberblick (Klartext): Reihenfolge ['temperature', 'gust'" in text, text

    def _html(h: str) -> str:
        spans = re.findall(r'<span style="display:inline-block;vertical-align:middle;[^"]*">[^<]*</span>', h)
        return _tausche(h, spans[0], spans[1])
    code, text = _lauf(tmp_path, TRIP, _aendere(eml, html=_html), "--konfig", konfig)
    assert code == 1 and "SOLL: Metriken-Ueberblick (HTML): Reihenfolge ['temperature', 'gust'" in text, text


def test_r7b_trip_kompakt_ueberblick_folge_vertauscht_scheitert(monkeypatch, tmp_path):
    daten = _trip_daten(_TRIP_FOLGE, email_format="compact")
    eml, konfig = _trip_eml(monkeypatch, daten), _konfig(tmp_path, "kpf", daten)
    assert _lauf(tmp_path, TRIP, eml, "--konfig", konfig)[0] == 0
    falsch = _aendere(eml, plain=_pillen_tauschen_klartext("== Metriken-Ueberblick =="))
    code, text = _lauf(tmp_path, TRIP, falsch, "--konfig", konfig)
    assert code == 1 and "SOLL: Metriken-Ueberblick (Kompakt): Reihenfolge ['temperature', 'gust'" in text, text


def _trip_ampel_daten(eigene_grenzen: bool = True) -> dict:
    """Boeen Einfach (Ampelpunkt); eigene Grenzen 100/110/120 -> 45 km/h gruen
    (Vorlage "allgemein": 30/45/60 -> orange)."""
    daten = _trip_daten(_TRIP_FOLGE)
    for m in daten["display_config"]["metrics"]:
        if m["metric_id"] == "gust":
            m["use_friendly_format"] = True
    if eigene_grenzen:
        daten["display_config"]["ampel"] = {"template": "allgemein", "metrics": {
            "gust": {"upper": {"yellow": 100, "orange": 110, "red": 120}}}}
    return daten


def test_r7b_trip_ampelfarbe_folgt_den_grenzen(monkeypatch, tmp_path):
    """Ampelpunkt (Einfach) gegen den Klartext-Wert derselben Stunde: die echte
    Mail besteht; rot statt gruen scheitert; dieselbe Mail gegen die Vorlage
    ohne eigene Grenzen (45 = orange) scheitert ebenso."""
    daten = _trip_ampel_daten()
    eml, konfig = _trip_eml(monkeypatch, daten), _konfig(tmp_path, "amp", daten)
    code, text = _lauf(tmp_path, TRIP, eml, "--konfig", konfig)
    assert code == 0, text
    falsch = _aendere(eml, html=lambda h: h.replace("background:#15803d;", "background:#a8104a;"))
    code, text = _lauf(tmp_path, TRIP, falsch, "--konfig", konfig)
    assert code == 1 and "SOLL: Ampelfarbe Etappen-Stundentabelle (HTML) 08:00 'Gust': red statt green" in text, text
    code, text = _lauf(tmp_path, TRIP, eml, "--konfig", _konfig(tmp_path, "amp2", _trip_ampel_daten(False)))
    assert code == 1 and "'Gust': green statt orange" in text, text


def test_r7b_trip_ampelfarbe_roh_zelle(monkeypatch, tmp_path):
    """Roh: die Toenung der Zahl-Zelle folgt den Grenzen (Boeen 45 = orange bei
    "allgemein"); gegen eigene Grenzen 100/110/120 ist die Toenung falsch."""
    daten = _trip_daten(_TRIP_FOLGE)
    eml = _trip_eml(monkeypatch, daten)
    code, text = _lauf(tmp_path, TRIP, eml, "--konfig", _konfig(tmp_path, "roh", daten))
    assert code == 0, text
    grenzen = copy.deepcopy(daten)
    grenzen["display_config"]["ampel"] = {"metrics": {"gust": {"upper": {"yellow": 100, "orange": 110, "red": 120}}}}
    code, text = _lauf(tmp_path, TRIP, eml, "--konfig", _konfig(tmp_path, "roh2", grenzen))
    assert code == 1 and "'Gust': orange statt green" in text, text


def _trip_fruehstart(start: str | None) -> dict:
    daten = _trip_daten(_TRIP_FOLGE)
    daten["report_config"].update(day_window_start_hour=6, day_window_end_hour=20)
    for etappe in daten["stages"] if start else ():
        etappe["start_time"] = start
    return daten


def test_r7b_trip_etappenstart_vor_sechs_besteht(monkeypatch, tmp_path):
    """Punkt 2: Etappenstart 04:30 -> die Stundentabelle beginnt um 04. Mit
    ``--konfig`` (Start 04:30) besteht die echte Mail; ohne gespeicherten
    Start (Vorgabe 08:00, Fenster 06-20) ist 04 ausserhalb."""
    from datetime import timedelta

    from tests.tdd import _einstellung_auslieferung_fixtures as fx

    _segment_naht(monkeypatch, start=fx._local_to_utc(fx.DAY, 4) + timedelta(minutes=30))
    daten = _trip_fruehstart("04:30")
    eml = _trip_eml(monkeypatch, daten)
    code, text = _lauf(tmp_path, TRIP, eml, "--konfig", _konfig(tmp_path, "fs", daten))
    assert code == 0, text
    code, text = _lauf(tmp_path, TRIP, eml, "--konfig", _konfig(tmp_path, "fs2", _trip_fruehstart(None)))
    assert code == 1 and "FULL: Stunde 04 ausserhalb Tagesfenster 06–22" in text, text


@pytest.mark.parametrize("lang", ["de", "en"])
def test_r7b_orte_nie_eingestellt_zeilen_wie_mail(monkeypatch, tmp_path, lang):
    """``active_metrics`` fehlt: die Mail zeigt alle Zeilen in Standardfolge,
    das Soll ebenso; eine fehlende Zeile scheitert im HTML und im Klartext."""
    from app.metric_catalog import get_metric

    preset = _orte_preset(altbestand=True)
    eml, konfig = _orte_eml(monkeypatch, preset, lang=lang), _orte_konfig(tmp_path, preset, "nie")
    code, text = _lauf(tmp_path, ORTE, eml, "--konfig", konfig)
    assert code == 0, text
    boeen = get_metric("gust").label(lang)
    falsch = _aendere(eml, plain=lambda p: re.sub(rf"(?m)^   {boeen}: .*\n", "", p, count=1))
    code, text = _lauf(tmp_path, ORTE, falsch, "--konfig", konfig)
    assert code == 1 and "SOLL: Vergleichstabelle Zeilen (Klartext) Block 1" in text and f"'{boeen}'" in text, text
    falsch = _aendere(eml, html=lambda h: re.sub(
        rf"<tr[^>]*>\s*<td[^>]*>{boeen}</td>(?:(?!</tr>).)*</tr>", "", h, count=1, flags=re.S))
    code, text = _lauf(tmp_path, ORTE, falsch, "--konfig", konfig)
    assert code == 1 and "SOLL: Vergleichstabelle Zeilen (HTML) Block 1" in text, text


@pytest.mark.parametrize("lang", ["de", "en"])
def test_r7b_orte_zieltag_morgen_heute_abend_morgen(monkeypatch, tmp_path, lang):
    """Morgen-Slot: Zieltag = Erstellungstag; Abend-Slot: der Folgetag. Die
    jeweils echte Mail besteht, die des anderen Slots scheitert."""
    morgen = _orte_preset()
    abend = {**_orte_preset(), "morning_enabled": False, "evening_enabled": True, "evening_time": "18:00:00"}
    k_morgen, k_abend = _orte_konfig(tmp_path, morgen, "zm"), _orte_konfig(tmp_path, abend, "za")
    m_eml = _orte_eml(monkeypatch, morgen, lang=lang)
    a_eml = _orte_eml(monkeypatch, abend, lang=lang, versatz=1)
    assert _lauf(tmp_path, ORTE, m_eml, "--konfig", k_morgen)[0] == 0
    code, text = _lauf(tmp_path, ORTE, a_eml, "--konfig", k_abend)
    assert code == 0, text
    code, text = _lauf(tmp_path, ORTE, m_eml, "--konfig", k_abend)
    assert code == 1 and "SOLL: Zieltag 2026-10-29 bei Erstellung 2026-10-29, erwartet der Folgetag" in text, text
    code, text = _lauf(tmp_path, ORTE, a_eml, "--konfig", k_morgen)
    assert code == 1 and "SOLL: Zieltag 2026-10-30 bei Erstellung 2026-10-29, erwartet der Erstellungstag" in text, text


def test_r7b_orte_hinweis_nicht_abrufbar_trotz_schalter_aus(monkeypatch, tmp_path):
    """Schalter aus: kein Abruf, also kein Hinweis "nicht abrufbar". Die echte
    Mail besteht, mit eingesetztem Hinweis (HTML und Klartext) scheitert sie."""
    from i18n import t

    preset = {**_orte_preset(), **_WARN_AUS}
    eml, konfig = _orte_eml(monkeypatch, preset), _orte_konfig(tmp_path, preset, "haus")
    code, text = _lauf(tmp_path, ORTE, eml, "--konfig", konfig)
    assert code == 0, text
    titel, satz = (t(f"mail.hinweis.warnungen_nicht_abrufbar.{k}", "de") for k in ("titel", "text"))
    falsch = _aendere(
        eml, html=lambda h: h.replace('<div class="container">', f'<div class="container"><div><strong>{titel}</strong></div>', 1),
        plain=lambda p: p.replace("-" * 50, f"⚠️ {satz}\n\n" + "-" * 50, 1))
    code, text = _lauf(tmp_path, ORTE, falsch, "--konfig", konfig)
    assert code == 1, text
    for teil in ("HTML", "Klartext"):
        assert f"SOLL: Hinweis 'Amtliche Warnungen nicht abrufbar' ({teil}) erscheint" in text, text


def test_r7b_orte_ampelfarbe_folgt_den_grenzen(monkeypatch, tmp_path):
    """Toenung der Zahl-Zellen: Niederschlag 8.4 mm ist bei "allgemein" orange.
    Die echte Mail besteht; ungetoent scheitert sie; gegen eigene Grenzen
    50/60/70 ist die echte Toenung falsch."""
    preset = _orte_preset()
    eml, konfig = _orte_eml(monkeypatch, preset), _orte_konfig(tmp_path, preset, "oa")
    code, text = _lauf(tmp_path, ORTE, eml, "--konfig", konfig)
    assert code == 0, text
    falsch = _aendere(eml, html=lambda h: h.replace("background:#fbe3cc;", "background:transparent;", 1))
    code, text = _lauf(tmp_path, ORTE, falsch, "--konfig", konfig)
    assert code == 1 and "SOLL: Ampelfarbe Vergleichstabelle (HTML) 'Niederschlag' Ort 1: green statt orange" in text, text
    grenzen = copy.deepcopy(preset)
    grenzen["display_config"]["ampel"] = {"metrics": {"precipitation": {"upper": {"yellow": 50, "orange": 60, "red": 70}}}}
    code, text = _lauf(tmp_path, ORTE, eml, "--konfig", _orte_konfig(tmp_path, grenzen, "oa2"))
    assert code == 1 and "'Niederschlag' Ort 1: orange statt green" in text, text


# --------------------------------------------------------------------------- #
# #3122 B5 (AC-35, AC-36): Bereichsname "Orte", Ein-Ort-Texte
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("lang, alt", [("de", "Vergleich in App öffnen →"),
                                       ("en", "Open comparison in app →")])
def test_b5_orte_alter_bereichsname_scheitert(monkeypatch, tmp_path, lang, alt):
    """AC-35: die echte Mail (neue Texte) besteht; steht der alte Bereichsname
    wieder darin, scheitert der Validator mit ``NAME:`` -- in HTML und Klartext."""
    preset = _orte_preset()
    eml, konfig = _orte_eml(monkeypatch, preset, lang=lang), _orte_konfig(tmp_path, preset, f"b5{lang}")
    code, aus = _lauf(tmp_path, ORTE, eml, "--konfig", konfig)
    assert code == 0, aus
    falsch = _aendere(eml, html=lambda h: h.replace("</body>", f"<p>{alt}</p></body>", 1),
                      plain=lambda p: p + f"\n{alt}\n")
    code, aus = _lauf(tmp_path, ORTE, falsch, "--konfig", konfig)
    assert code == 1, aus
    assert "NAME: alter Bereichsname (HTML)" in aus and "NAME: alter Bereichsname (Klartext)" in aus, aus


@pytest.mark.parametrize("lang", ["de", "en"])
def test_b5_orte_kopf_fehlt_scheitert(monkeypatch, tmp_path, lang):
    """AC-35: der Kopf heisst "ORTE" bzw. "LOCATIONS"; fehlt er (anderes Wort),
    scheitert der Validator in HTML und Klartext."""
    from i18n import t

    preset = _orte_preset()
    eml, konfig = _orte_eml(monkeypatch, preset, lang=lang), _orte_konfig(tmp_path, preset, f"b5k{lang}")
    kopf = t("vergleich.kopf.titel", lang)
    falsch = _aendere(eml, html=lambda h: h.replace(f"{kopf} · ", "BRIEFING · ", 1),
                      plain=lambda p: p.replace(f"{kopf}\n", "BRIEFING\n", 1))
    code, aus = _lauf(tmp_path, ORTE, falsch, "--konfig", konfig)
    assert code == 1, aus
    assert f"NAME: Kopf '{kopf}' fehlt (HTML)" in aus and f"NAME: Kopf '{kopf}' fehlt (Klartext)" in aus, aus


@pytest.mark.parametrize("lang, mehrzahl", [("de", "1 Orte · Vorlage"), ("en", "1 locations · Template")])
def test_b5_orte_ein_ort_mehrzahl_scheitert(monkeypatch, tmp_path, lang, mehrzahl):
    """AC-36: die echte Ein-Ort-Mail besteht (Fuss "1 Ort"); ein Text, der
    mehrere Orte voraussetzt ("1 Orte"), laesst den Validator scheitern."""
    from i18n import tn

    preset = _orte_preset(orte=("golden-0",))
    eml, konfig = _orte_eml(monkeypatch, preset, lang=lang), _orte_konfig(tmp_path, preset, f"b5e{lang}")
    code, aus = _lauf(tmp_path, ORTE, eml, "--konfig", konfig)
    assert code == 0, aus
    richtig = tn("vergleich.fuss.abo_zeile", 1, lang, vorlage="").strip()
    falsch = _aendere(eml, html=lambda h: h.replace(richtig, mehrzahl, 1))
    code, aus = _lauf(tmp_path, ORTE, falsch, "--konfig", konfig)
    assert code == 1, aus
    assert "NAME: Text setzt mehrere Orte voraus (HTML)" in aus, aus


@pytest.mark.parametrize("lang, orte, namen, abo", [
    ("de", ("golden-2", "golden-0", "golden-1"), {"golden-0": "Vergleichsberg"}, "Vergleich Tirol"),
    ("en", ("golden-2", "golden-0", "golden-1"), {"golden-0": "Comparison Peak"}, "Comparison Tour"),
    ("de", ("golden-0",), {"golden-0": "Alle Orte Bar"}, "Gleich Orte"),
], ids=["vergleichsberg", "comparison_peak", "alle_orte_bar_ein_ort"])
def test_b5_orte_nutzernamen_loesen_keinen_fehlalarm_aus(monkeypatch, tmp_path, lang, orte,
                                                         namen, abo):
    """F-V1: Orts- und Abo-Namen sind Nutzerdaten. "Vergleichsberg",
    "Comparison Peak" oder bei einem Ort "Alle Orte Bar" sind kein alter
    Bereichsname und kein Mehrzahl-Text -- die echte Mail besteht."""
    preset = {**_orte_preset(orte=orte), "name": abo}
    eml = _orte_eml(monkeypatch, preset, lang=lang, namen=namen)
    konfig = _konfig(tmp_path, f"fv1{lang}", {"preset": preset, "orte": {**_ORTSNAMEN, **namen}})
    code, aus = _lauf(tmp_path, ORTE, eml, "--konfig", konfig)
    assert code == 0, aus
    # Gegenprobe: der alte Name an fester Stelle (Kopf) scheitert weiter.
    from i18n import t

    kopf = t("vergleich.kopf.titel", lang)
    alt = {"de": "ORTS-VERGLEICH", "en": "LOCATION COMPARISON"}[lang]
    falsch = _aendere(eml, html=lambda h: h.replace(f"{kopf} · ", f"{alt} · ", 1))
    code, aus = _lauf(tmp_path, ORTE, falsch, "--konfig", konfig)
    assert code == 1 and "NAME: Kopf" in aus, aus


@pytest.mark.parametrize("lang", ["de", "en"])
def test_b5_orte_ein_ort_alle_orte_in_fester_zeile_scheitert(monkeypatch, tmp_path, lang):
    """AC-36: bei einem Ort steht in der Unterzeile der Uebersicht die
    Mehrzahl-Form ("Alle Orte · gewählte Metriken") -> Fehler."""
    from i18n import tn

    preset = _orte_preset(orte=("golden-0",))
    eml, konfig = _orte_eml(monkeypatch, preset, lang=lang), _orte_konfig(tmp_path, preset, f"b5a{lang}")
    eins, viele = (tn("vergleich.uebersicht.titel", n, lang) for n in (1, 3))
    falsch = _aendere(eml, html=lambda h: h.replace(f">{eins}<", f">{viele}<", 1))
    code, aus = _lauf(tmp_path, ORTE, falsch, "--konfig", konfig)
    assert code == 1 and "NAME: Text setzt mehrere Orte voraus (HTML)" in aus, aus


@pytest.mark.parametrize("lang", ["de", "en"])
def test_b5_orte_ein_ort_fuss_fehlt_scheitert(monkeypatch, tmp_path, lang):
    """T3: bei einem Ort fehlt der Fuss "1 Ort · Vorlage …" -> Fehler, auch
    ohne Mehrzahl-Text."""
    from i18n import tn

    preset = _orte_preset(orte=("golden-0",))
    eml, konfig = _orte_eml(monkeypatch, preset, lang=lang), _orte_konfig(tmp_path, preset, f"b5f{lang}")
    fuss = tn("vergleich.fuss.abo_zeile", 1, lang, vorlage="").strip()
    falsch = _aendere(eml, html=lambda h: h.replace(fuss, "", 1))
    code, aus = _lauf(tmp_path, ORTE, falsch, "--konfig", konfig)
    assert code == 1, aus
    assert "NAME: Fuss" in aus and "fehlt bei einem Ort (HTML)" in aus, aus
    assert "NAME: Text setzt mehrere Orte voraus" not in aus, aus
