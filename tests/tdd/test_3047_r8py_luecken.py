"""#3047 Runde 8, Paket r8py: Testluecken aus der Abnahme 7b (Mutationen M05,
M19, M20, M32, M52) und Befund F1 (Trip-Altbestand ``metrics: []``, SMS-Folge).

SPEC: docs/specs/modules/feat_3047_einstellung_gleich_mail_pruefkatalog.md,
"Nachtrag Runde 7" (AC-22, AC-23, AC-26, AC-27).

Jeder Test laeuft ueber den echten Weg bis zur fertigen Ausgabe (Mail,
SMS-Zeile, Transport-Mitschrift, Validator-Prozess); Erwartungen stehen von
Hand im Test. Datenbewegende Faelle laufen mit zwei frischen Nutzern.
"""
from __future__ import annotations

import pytest

# --------------------------------------------------------------------------- #
# F1 -- Trip-Altbestand ``metrics: []``: SMS = was der Editor zeigt und speichert
# --------------------------------------------------------------------------- #
_SMS_KANAELE = {"send_sms": True, "send_telegram": True, "send_premium_sms": True}

#: Register-Standard (``trip_default_rank``), von Hand: so zeigt der Editor den
#: Altbestand und so speichert er ihn (Kinder ohne eigenen Eintrag ausdruecklich
#: aus, ``ampelSchreiben.ts::kinderAusdruecklich``).
_REGISTER = ["temperature", "wind", "gust", "precipitation", "thunder",
             "freezing_level", "visibility", "temperature_day_low", "temperature_day_high"]


def _sms_trip(monkeypatch, metrics: list) -> tuple[str, str, str]:
    from tests.tdd._einstellung_gleich_mail_trip_fixtures import render_trip_mit_ausblick, trip_json

    d = trip_json(["wind"], report_config=_SMS_KANAELE)
    d["display_config"]["metrics"] = metrics
    ms, _trip, uid = render_trip_mit_ausblick(monkeypatch, d)
    return uid, ms.sendungen("sms")[0]["body"], ms.sendungen("premium_sms")[0]["body"]


def test_f1_altbestand_leer_sms_folgt_register_wie_editor_gespeichert(monkeypatch):
    """F1 (AC-22/AC-26): ``metrics: []`` zeigt im Editor den Register-Standard
    (Tagestief/-hoch auf Rang 8/9). Die SMS und Premium-SMS folgen genau dieser
    Folge -- und aendern sich nicht, wenn der Editor die Liste unveraendert
    speichert. Zwei Nutzer."""
    gespeichert = [{"metric_id": m, "enabled": True, "bucket": "primary", "order": i}
                   for i, m in enumerate(_REGISTER)]
    gespeichert.append({"metric_id": "temperature_night", "enabled": False})
    #: von Hand: Folge der SMS-Token
    soll = "E1 W- G45@4 R2.0@4 TH:M@4 TH+:- FZ2500@4 VS- D15/15"
    uids = set()
    for _ in range(2):
        uid, sms, premium = _sms_trip(monkeypatch, [])
        uid2, sms_gesp, premium_gesp = _sms_trip(monkeypatch, gespeichert)
        uids |= {uid, uid2}
        assert sms == soll, sms
        assert sms_gesp == sms, f"Speichern aendert die SMS: {sms_gesp!r} statt {sms!r}"
        assert premium == premium_gesp == sms
    assert len(uids) == 4


#: von Hand, je Kanal die Folge der Editor-Liste ``_REGISTER``. Temperatur
#: (Rang 1) ist in Mail/Telegram eine eigene Spalte vorn; Tagestief/-hoch
#: (Rang 8/9) haben dort keine Spalte und erscheinen nur in SMS/Premium-SMS als
#: ``D`` hinten. In der SMS hat die Temperatur selbst kein Kuerzel.
_SPALTEN = ["temperature", "wind", "gust", "precipitation", "thunder", "freezing_level", "visibility"]
_TG_KUERZEL = ["T", "W", "G", "R", "TH", "FZ", "VS"]
_KOMPAKT_AUSBLICK = ["Temp", "Wind", "Gust", "Rain", "Thdr", "0Line", "Visib"]
_SMS_KUERZEL = ["W", "G", "R", "TH:", "TH+:", "FZ", "VS", "D"]


def _alle_kanaele(monkeypatch, metrics: list) -> dict:
    import re

    from tests.helpers.einstellung_gleich_mail_trip import html_ausblick, html_tabellen, klartext_tabellen
    from tests.tdd._einstellung_gleich_mail_trip_fixtures import (
        mail_teile, render_trip_mit_ausblick, trip_json,
    )

    def lauf(fmt: str):
        d = trip_json(["wind"], report_config={**_SMS_KANAELE, "email_format": fmt})
        d["display_config"]["metrics"] = metrics
        return render_trip_mit_ausblick(monkeypatch, d)

    ms, _t, uid = lauf("full")
    html, plain = mail_teile(ms)
    tg = [s["body"] for s in ms.sendungen("telegram")]
    ov = next(b for b in tg if b.startswith("Kurzübersicht")).splitlines()[1:]
    tab = next(b for b in tg if "<pre>" in b).split("<pre>")[1].strip().splitlines()[0].split()[1:]
    mk, _t2, uid2 = lauf("compact")
    kompakt = next(z for z in mail_teile(mk)[1].splitlines() if re.match(r"^(Mo|Di|Mi)  ", z))
    return {
        "uids": {uid, uid2},
        "html": html_tabellen(html)["etappe"][0].spalten,
        "klartext": klartext_tabellen(plain)["etappe"][0].spalten,
        "ausblick": html_ausblick(html).spalten,
        "telegram_ueberblick": [z.split()[0] for z in ov if z.strip() and not z.startswith("⚡")],
        "telegram_tabelle": tab,
        "kompakt_ausblick": [f.split()[0] for f in kompakt.split("  ")[1:]],
        "sms": [re.match(r"[A-Z]+\+?:?", t).group(0) for t in
                ms.sendungen("sms")[0]["body"].split()[1:]],  # #3174: Praefix ohne ':'
        "premium_sms": ms.sendungen("premium_sms")[0]["body"],
        "sms_roh": ms.sendungen("sms")[0]["body"],
    }


def test_f1_altbestand_leer_jeder_kanal_folgt_editor(monkeypatch):
    """F1 (AC-22/AC-26), Nachfrage Koordinator: ``metrics: []`` und die vom
    Editor unveraendert gespeicherte Liste ergeben in HTML, Klartext,
    Ausblick, Kompakt, Telegram, SMS und Premium-SMS dieselbe Folge -- die
    Editor-Folge. Zwei Nutzer je Liste."""
    gespeichert = [{"metric_id": m, "enabled": True, "bucket": "primary", "order": i}
                   for i, m in enumerate(_REGISTER)]
    gespeichert.append({"metric_id": "temperature_night", "enabled": False})
    uids = set()
    for metrics in ([], [], gespeichert, gespeichert):
        k = _alle_kanaele(monkeypatch, metrics)
        uids |= k["uids"]
        assert k["html"] == k["klartext"] == k["ausblick"] == _SPALTEN, k
        assert k["telegram_ueberblick"] == k["telegram_tabelle"] == _TG_KUERZEL, k
        assert k["kompakt_ausblick"] == _KOMPAKT_AUSBLICK, k
        assert k["sms"] == _SMS_KUERZEL, k["sms_roh"]
        assert k["premium_sms"] == k["sms_roh"]
    assert len(uids) == 8


# --------------------------------------------------------------------------- #
# T2 / M05 -- Orte-Altbestand ohne Grundauswahl, Ausblick-Folge gespeichert
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("folge", [
    ["precipitation", "wind", "temperature"],
    ["gust", "temperature", "rain_probability", "wind"],
])
def test_t2_orte_altbestand_ausblick_folge_gespeichert(folge):
    """M05: Altbestand ohne ``active_metrics`` (kein Maximum), ``outlook_metrics``
    in eigener Folge gespeichert -> HTML und Klartext zeigen im Ausblick genau
    diese Spalten in dieser Folge (nicht die sieben festen). Zwei Nutzer."""
    from tests.helpers.einstellung_gleich_mail_orte import (
        html_ausblick, kennungen, klartext_ausblick, preset_dict, sende_orte_mail,
    )

    uids = set()
    for _ in range(2):
        p = preset_dict("altbestand_ohne_grundauswahl")
        p["display_config"]["outlook_metrics"] = list(folge)
        mail = sende_orte_mail(p)
        uids.add(mail.uid)
        assert "active_metrics" not in mail.roh["display_config"], "Vorbedingung"
        for teil, ausblick in (("html", html_ausblick(mail.html)),
                               ("klartext", klartext_ausblick(mail.plain))):
            assert len(ausblick) == 3, f"{teil}: Ausblick je Ort fehlt: {ausblick}"
            for ort, zellen in ausblick.items():
                assert kennungen(zellen) == folge, f"{teil} {ort}: {kennungen(zellen)}"
    assert len(uids) == 2


# --------------------------------------------------------------------------- #
# T3 / M19 -- Kuerzung: amtliche Bausteine nach Prioritaet, Warnung zuletzt
# --------------------------------------------------------------------------- #
def _lange_warnzeile(max_len: int) -> str:
    from output.tokens.builder import build_token_line
    from output.tokens.dto import DailyForecast, NormalizedForecast
    from output.tokens.render import render_line
    from tests.helpers.ampel_allgemein import AMPEL_ALLGEMEIN

    fc = NormalizedForecast(
        days=(DailyForecast(temp_min_c=5, temp_max_c=15),),
        provider="meteofrance", country="FR",
        vigilance_hr_level="M", vigilance_hr_hour=14,
        vigilance_th_level="H", vigilance_th_hour=17,
        official_alerts=(("TS", "H", 14), ("WI", "M", 10)),
        fire_zones_high=tuple(str(200 + i) for i in range(20)),
        fire_zones_max=tuple(str(300 + i) for i in range(12)),
        fire_massifs=tuple(str(i) for i in range(10)),
    )
    line = build_token_line(fc, [], report_type="evening", stage_name="E1", ampel=AMPEL_ALLGEMEIN)
    return render_line(line, max_len)


@pytest.mark.parametrize("max_len, soll", [
    # von Hand: Liste weg, dann Brandzonen (Prio 3) vor Vigilance (10), Warnung (11) zuletzt
    (160, "E1 VR:M@14VT:H@17 !TS:H@14 WI:M@10 MAX300,301,302,303,304,305,306,307,308,"
          "309,310,311 M:0,1,2,3,4,5,6,7,8,9"),
    (40, "E1 VR:M@14VT:H@17 !TS:H@14 WI:M@10"),
    (25, "E1 !TS:H@14 WI:M@10"),
])
def test_t3_kuerzung_warnung_faellt_zuletzt(max_len, soll):
    """M19 (AC-23): beim Kuerzen fallen die amtlichen Bausteine in aufsteigender
    Prioritaet -- die amtliche Warnung bleibt bis zuletzt stehen."""
    assert _lange_warnzeile(max_len) == soll


# --------------------------------------------------------------------------- #
# T3 / M20 -- Premium-SMS folgt der SMS-Liste, solange sie keine eigene hat
# --------------------------------------------------------------------------- #
_GRUND = [{"metric_id": m, "enabled": True, "bucket": "primary", "order": i}
          for i, m in enumerate(["temperature", "wind", "gust", "precipitation", "thunder"])]
_SMS_LISTE = [{"metric_id": m, "bucket": "primary", "order": i}
              for i, m in enumerate(["gust", "precipitation", "temperature"])]


@pytest.mark.parametrize("report_type", ["morning", "evening"])
def test_t3_premium_sms_folgt_sms_liste(report_type):
    """M20 (AC-22): eigene SMS-Liste -> Premium-SMS hat dieselben Zeilen in
    derselben Folge. #3237: die SMS-Liste steht in der Tabelle "Was steht wo"
    (Stelle ``sms``, Premium-SMS hat keine eigene Stelle); eine frueher
    moegliche eigene Premium-Liste (Altfeld ``channel_layouts.premium_sms``)
    wirkt nicht mehr -- Premium-SMS bleibt die SMS-Liste."""
    from services.channel_list_resolver import resolve_channel_lists
    from tests.helpers.tabelle_aus_wunsch import trip_wunsch_als_tabelle

    def ids(zeilen):
        return [z.metric_id for z in zeilen if z.enabled]

    def dc(layouts):
        return trip_wunsch_als_tabelle(
            {"display_config": {"metrics": _GRUND, "channel_layouts": layouts}})["display_config"]

    vm = resolve_channel_lists(dc({"sms": _SMS_LISTE}), "trip", report_type)
    assert ids(vm.sms)[:3] == ["gust", "precipitation", "temperature"], ids(vm.sms)
    assert ids(vm.premium_sms) == ids(vm.sms)
    eigen = [{"metric_id": "wind", "bucket": "primary", "order": 0}]
    vm2 = resolve_channel_lists(dc({"sms": _SMS_LISTE, "premium_sms": eigen}), "trip", report_type)
    assert ids(vm2.premium_sms) == ids(vm2.sms) == ids(vm.sms)


# --------------------------------------------------------------------------- #
# T4 / M32 -- Tagesfenster start == end faellt auf den Standard 4-19 zurueck
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("lang", ["de", "en"])
def test_t4_tagesfenster_start_gleich_ende_wie_standard(monkeypatch, lang):
    """M32: ein ungueltiges Fenster 10-10 wirkt wie nie eingestellt (4-19):
    SMS und Telegram nennen Regen 2.0 um 04 und die Boeenspitze 80 um 08."""
    from tests.tdd.test_3047_runde7_telegram_tagesfenster import _fall, _kurzuebersicht, _sms, _tg

    for uid, mit in _fall(monkeypatch, (10, 10), lang):
        ov = _kurzuebersicht(mit, lang)
        sms = mit.sendungen("sms")[0]["body"]
        assert _sms(sms, "R") == ("2.0", 4), sms
        assert _sms(sms, "G") == ("80", 8), sms
        assert _tg(ov, "R") == ("2.0", 4), f"{uid}: {ov}"
        assert _tg(ov, "G") == ("80", 8), f"{uid}: {ov}"


@pytest.mark.parametrize("fenster, soll", [
    ((10, 10), (4, 19)),   # ungueltig -> Standard
    ((0, 0), (4, 19)),     # ungueltig -> Standard
    ((10, 18), (10, 18)),  # gueltig bleibt
    ((22, 2), (22, 2)),    # ueber Mitternacht bleibt
])
def test_t4_orte_tagesfenster_start_gleich_ende_wie_standard(fenster, soll):
    """M32: Orte-Presets laufen ungeklemmt aus dem Loader (anders als der
    Trip-Loader) -- das Fenster, das Versand und Vorschau dem Wetterabruf
    geben (``resolve_compare_time_window``), faellt bei start == end auf 4-19
    zurueck. Echter Loader aus dem Nutzerordner, zwei Nutzer."""
    from services.report_config_resolver import resolve_compare_time_window
    from tests.helpers.einstellung_gleich_mail_orte import preset_dict, profil_anlegen
    from tests.tdd._compare_kette_fixtures import preset_ablegen, preset_laden

    uids = set()
    for _ in range(2):
        uid = profil_anlegen()
        uids.add(uid)
        p = preset_dict("basis")
        p["day_window_start_hour"], p["day_window_end_hour"] = fenster
        preset_ablegen(uid, p)
        geladen = preset_laden(uid, p["id"])
        assert (geladen["day_window_start_hour"], geladen["day_window_end_hour"]) == fenster
        assert resolve_compare_time_window(geladen) == soll
    assert len(uids) == 2


# --------------------------------------------------------------------------- #
# T4 / M52 -- Trip-Validator weist eine Orte-Konfiguration ab
# --------------------------------------------------------------------------- #
def test_t4_trip_validator_weist_orte_konfig_ab(monkeypatch, tmp_path):
    """M52 (AC-27): ``briefing_mail_validator --konfig <Orte>`` scheitert mit
    der Meldung, dass die Konfiguration keine Trip-Konfiguration ist."""
    from tests.tdd.test_einstellung_gleich_mail_validatoren import (
        _TRIP_FOLGE, TRIP, _konfig, _lauf, _orte_konfig, _orte_preset, _trip_daten, _trip_eml,
    )

    daten = _trip_daten(_TRIP_FOLGE)
    eml = _trip_eml(monkeypatch, daten)
    code, aus = _lauf(tmp_path, TRIP, eml, "--konfig", _konfig(tmp_path, "trip", daten))
    assert code == 0, f"Vorbedingung: Trip-Mail mit Trip-Konfiguration gruen: {aus}"
    code, aus = _lauf(tmp_path, TRIP, eml, "--konfig", _orte_konfig(tmp_path, _orte_preset()))
    assert code == 1, aus
    assert "SOLL: --konfig ist keine Trip-Konfiguration" in aus, aus
