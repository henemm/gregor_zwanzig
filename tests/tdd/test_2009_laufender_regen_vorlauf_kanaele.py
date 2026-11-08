"""Issue #2009 (Nachmessung): Kanal-Inhalt bei laufendem Regen bleibt "läuft bereits".

SPEC: docs/specs/modules/fix_2009_laufender_regen_vorlauf.md (Waechter 7 = AC-7)

Schutzpruefung, BEWUSST schon heute gruen: die Anzeige war korrekt (#2050
S2b), der Fehler sitzt in der Messung. Die Korrektur zieht den Beginn bei
laufendem Regen auf JETZT (`_onset_dt` im Trip-Pfad speist auch die
Beginn-Uhrzeit der Nachricht). Dieser Waechter faellt, sobald dadurch irgendein
Kanal "in 0 Min" oder die Laufzeit als Beginn zeigt.

Alle vier Kanaele (ADR-0095) ueber die `AlarmPruefstrecke`: E-Mail ueber
`mail_sink`, Telegram und SMS/Premium-SMS ueber die lokalen Stubs der
Pruefstrecke -- echter Transport, kein Versand ins Netz, kein Mock.

Wortlaut-Vertrag (aus #2050 S2b, `test_alarm_szenario_laufendes_ereignis.py`):
Langformen (E-Mail, Telegram) sagen "läuft bereits"; die Kurznachricht (SMS,
Premium-SMS) ist ENGLISCH und traegt dafuer den Laufend-Marker `now` an der
Stelle des Beginns (PO-Entscheid 2026-08-22).
"""
from __future__ import annotations

import re
import uuid
from datetime import timedelta

import pytest
from freezegun import freeze_time

from services.radar_service import RadarNowcastService

from tests.helpers.alarm_pruefstrecke import AlarmPruefstrecke
from tests.tdd.test_952_onset_alert_fidelity import _clean_user
from tests.tdd.test_alarm_pruefstrecke_selbstschutz import (
    _AT, _radar_trip, _settings_all_channels, _write_premium_profile,
)

_SLOT = _AT                                  # 10:00 UTC = 12:00 Ortszeit Korsika
_LAUF = _SLOT + timedelta(minutes=8)         # 10:08 UTC = 12:08 Ortszeit, Takt :08
_LAUF_LOKAL = "12:08"                        # Laufzeit als (falscher) Beginn
_NAECHSTER_SLOT_LOKAL = "12:15"              # naechster Viertelstundenpunkt

LAEUFT = "läuft bereits"
SMS_LAUFEND = "now@"
# "in 0 Min" / "in 0 min" / "in ~0 Min" -- jede Form eines Null-Vorlaufs.
_NULL_VORLAUF = re.compile(r"in ~?0 ?[Mm]in")

_ANGELEGT: list[str] = []


@pytest.fixture(autouse=True)
def _aufraeumen():
    _ANGELEGT.clear()
    yield
    for uid in _ANGELEGT:
        _clean_user(uid)


def _laeuft_bereits(lat: float, lon: float) -> list:
    """Laufendes (12:00) und naechstes Frame (12:15) nass, letztes nasses
    Frame 12:30 -- `already_running` mit `onset_minutes` = 7."""
    from providers.brightsky import RadarFrame
    return [
        RadarFrame(timestamp=_SLOT + timedelta(minutes=15 * k),
                   precip_mm_h=2.0 if k < 3 else 0.0)
        for k in range(11)
    ]


def test_waechter7_alle_vier_kanaele_zeigen_laeuft_bereits_nie_in_null_min():
    """AC-7: laufender Regen, Lauf im Takt (12:08 Ortszeit) -> E-Mail und
    Telegram sagen "läuft bereits", SMS und Premium-SMS tragen den
    Laufend-Marker `now`; KEIN Kanal zeigt "in 0 Min" und keiner nennt die
    Laufzeit 12:08 als Beginn."""
    uid = f"tdd-2009-kanaele-{uuid.uuid4().hex[:6]}"
    _ANGELEGT.append(uid)
    _clean_user(uid)
    _write_premium_profile(uid, _AT)
    with freeze_time(_AT):
        trip = _radar_trip(
            uid, "trip-2009-w7", send_email=True, send_telegram=True,
            send_sms=True, send_premium_sms=True,
        )
    lauf = AlarmPruefstrecke(user_id=uid, settings=_settings_all_channels()).lauf(
        at=_LAUF, zweig="radar", trip=trip,
        radar_service=RadarNowcastService(frame_source=_laeuft_bereits),
    )
    kanaele = {
        "email": "\n".join(f"{betreff}\n{koerper}" for betreff, koerper in lauf.mail),
        "telegram": "\n".join(lauf.telegram),
        "sms": "\n".join(lauf.sms),
        "premium_sms": "\n".join(lauf.premium_sms),
    }
    leer = [k for k, text in kanaele.items() if not text]
    assert lauf.triggered_count == 1 and not leer, (
        f"AC-7 Vorbedingung: der Lauf muss ausloesen und alle vier Kanaele "
        f"bedienen (triggered_count={lauf.triggered_count}, leer={leer})."
    )

    for kanal in ("email", "telegram"):
        assert LAEUFT in kanaele[kanal], (
            f"AC-7 ({kanal}): {LAEUFT!r} fehlt.\n{kanaele[kanal]}"
        )
    for kanal in ("sms", "premium_sms"):
        assert SMS_LAUFEND in kanaele[kanal], (
            f"AC-7 ({kanal}): der Laufend-Marker {SMS_LAUFEND!r} der "
            f"Kurznachricht fehlt.\n{kanaele[kanal]}"
        )
    for kanal, text in kanaele.items():
        assert not _NULL_VORLAUF.search(text), (
            f"AC-7 ({kanal}): ein laufender Regen darf nie als 'in 0 Min' "
            f"erscheinen.\n{text}"
        )
        for falscher_beginn in (f"ab {_LAUF_LOKAL}", f"@{_LAUF_LOKAL}",
                                f"ab {_NAECHSTER_SLOT_LOKAL}", f"@{_NAECHSTER_SLOT_LOKAL}"):
            assert falscher_beginn not in text, (
                f"AC-7 ({kanal}): {falscher_beginn!r} behauptet einen Beginn -- "
                f"der Regen laeuft aber bereits.\n{text}"
            )


def test_waechter7_ortsvergleich_mail_zeigt_laeuft_bereits_nie_in_null_min():
    """AC-7, Ortsvergleichs-Seite: der Buendel-Renderer
    (`project.py::to_multi_location_onset_alert_message`, ca. :609/:625)
    reicht `onset_minutes` bei laufendem Regen ungeprueft in das `OnsetEvent`
    -- die Anzeige verzweigt auf `already_running`. Die Korrektur der
    Ableitung darf daran nichts kippen: die Ortsvergleichs-Mail sagt
    "läuft bereits", nie "in 0 Min" und nennt keinen Beginn.

    Ort Wien-Zone (CEST, UTC+2): 10:08 UTC = 12:08 Ortszeit wie beim Trip."""
    from app.loader import save_location

    from tests.helpers.nowcast_gate_fixtures import (
        clean_uid, compare_radar_service, location, radar_preset,
        reset_radar_cache, settings_email_only, write_presets, write_user_tier,
    )

    uid = f"tdd-2009-kanaele-cmp-{uuid.uuid4().hex[:6]}"
    _ANGELEGT.append(uid)
    clean_uid(uid)
    try:
        preset_id = f"cp-{uid}"
        with freeze_time(_AT):
            write_user_tier(uid, "premium")
            save_location(location("loc-w7", "Laufend-Ort"), user_id=uid)
            write_presets(uid, [radar_preset(preset_id, ["loc-w7"], user_id=uid)])
        mails: list = []
        with freeze_time(_LAUF):
            reset_radar_cache()
            gesendet = compare_radar_service(
                uid, settings_email_only(), _laeuft_bereits,
                lambda subject, body: mails.append((subject, body)),
            ).check_all_compare_presets()
        reset_radar_cache()
        assert gesendet == 1 and mails, (
            f"AC-7 Vorbedingung (Ortsvergleich): genau ein Alarm erwartet "
            f"(gesendet={gesendet}, Mails={len(mails)})."
        )
        text = "\n".join(f"{betreff}\n{koerper}" for betreff, koerper in mails)
        assert LAEUFT in text, f"AC-7 (Ortsvergleich): {LAEUFT!r} fehlt.\n{text}"
        assert not _NULL_VORLAUF.search(text), (
            f"AC-7 (Ortsvergleich): 'in 0 Min' bei laufendem Regen.\n{text}"
        )
        for falscher_beginn in (f"ab {_LAUF_LOKAL}", f"ab {_NAECHSTER_SLOT_LOKAL}"):
            assert falscher_beginn not in text, (
                f"AC-7 (Ortsvergleich): {falscher_beginn!r} behauptet einen "
                f"Beginn -- der Regen laeuft aber bereits.\n{text}"
            )
    finally:
        clean_uid(uid)
