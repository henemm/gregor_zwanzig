"""Issue #2050 Scheibe S2b — Waechter: laufendes Regen-/Gewitterereignis.

SPEC: docs/specs/modules/alarm_szenario_laufendes_ereignis.md (AC-1..AC-15)
Zusaetzlich AC-11b: Gegenrichtung zu AC-11 (Befund der Parallelsession #2065,
`alert_gate.py:489-494`) -- die Entdopplung darf keinen NEUEN Alarm fressen.

Laeuft ein Ereignis zum Zeitpunkt des Alarmlaufs BEREITS, meldet Gregor es
heute als bevorstehend ("Regen in 8 Min"): `_derive_result` filtert
`f.timestamp >= now` und verwirft damit das Frame der laufenden Viertelstunde
(Frames tragen den Slot-Start im Raster :00/:15/:30/:45, der Cron laeuft
:07/:22/:37/:52 -- "in 8 Min" ist deshalb nicht der gemessene, sondern der
einzig moegliche Wert).

Alle Kanal-Waechter fahren ueber die `AlarmPruefstrecke` (S1) gegen die ECHTE
Ausloeseentscheidung (`check_radar_alerts()`) -- kein Mock()/patch()/
MagicMock: Frames ueber die DI-Naht `frame_source=` eines echten
`RadarNowcastService`, Kanaltexte ueber den echten Telegram-/seven.io-
Transport (lokale Stubs der Pruefstrecke) bzw. `mail_sink`. Kein echter Versand.

WORTLAUT-VERTRAG dieser Scheibe (GREEN zieht nach). Die Herkunft ist bewusst
getrennt ausgewiesen -- Freigabe ist nicht dasselbe wie Entwurfsentscheidung:

  * LAUFEND-AUSSAGE, vom Product Owner bei der S2b-Freigabe ausgewaehlt:
    E-Mail/Telegram-Langform/Betreff/`/jetzt`/Briefing-Zeile melden
    "Regen laeuft bereits" statt einer Beginn-Angabe.
  * ENDE-AUSSAGE aus #2051 S1, PO-Entscheid 2026-08-22 (unser urspruenglicher
    Wortlaut ist zurueckgezogen). Nachgelesen im Quelltext
    `render.py::_onset_end_suffix`/`_sms_onset_ende` auf
    `origin/feat-2051-s1-dauer-und-ende`. ZWEI Formen, entschieden allein am
    R4-Waechter `event_ongoing_beyond_horizon` -- bekanntes Ende
    (Trockenuebergang beobachtet, unsere Lage A): ` · letzter Regen gegen
    HH:MM`, Kurznachricht `@HH:MM` direkt angehaengt (`R2.5@18:00@20:00`);
    Untergrenze (Zeitreihe/Horizont ausgegangen, Lage B): ` · Regen
    mindestens bis HH:MM`, Kurznachricht ` >@HH:MM`.
  * LAUFEND-MARKER der Kurznachricht, PO-Entscheid 2026-08-22 (verbindlich):
    das Wort `now` steht dort, wo sonst der Beginn stuende, danach
    unveraendert die Ende-Grammatik -- `R2.0 now@12:45` bei bekanntem Ende,
    `R2.0 now >@14:30` bei der Untergrenze, `TH now@12:45` beim Gewitter.

🔴 Die Kurznachricht (SMS, Premium-SMS, Telegram-Kurzform) ist ENGLISCH --
`R` = Rain, `TH` = Thunder, und deshalb `now` statt "jetzt". Nur die
Langformen (E-Mail, Telegram-Langform) sprechen Deutsch. Jedes neue Wort in
der Kurzform ist englisch, auch wenn dieselbe Aussage in der E-Mail deutsch
lautet: Langform `letzter Regen gegen 12:30`, Kurzform `R2.0 now@12:30`.
"""
from __future__ import annotations

import re
import uuid
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest
from freezegun import freeze_time

from app.loader import save_trip
from output.renderers.alert.project import to_multi_location_onset_alert_message
from output.renderers.alert.render import render_email, render_telegram
from services.radar_cache import reset_shared_radar_cache_for_tests
from services.radar_service import (
    INTENSITY_DRY, NowcastResult, RadarNowcastService,
)

from tests.helpers.alarm_pruefstrecke import AlarmPruefstrecke
from tests.tdd.test_952_onset_alert_fidelity import _clean_user
from tests.tdd.test_alarm_pruefstrecke_selbstschutz import (
    _AT, _radar_trip, _settings_all_channels, _write_premium_profile,
)

# `_AT` (10:00 UTC) taugt als Laufzeitpunkt NICHT: dort faellt `now` genau auf
# den Slot-Start, `f.timestamp >= now` behielte das Frame und der Defekt waere
# unsichtbar. Der Versatz +7 Min bildet den echten Cron-Takt ab.
_SLOT = _AT                              # 10:00 UTC -- Beginn des laufenden Slots
_AT_LAUF = _AT + timedelta(minutes=7)    # 10:07 UTC = 12:07 Ortszeit

# Ortszeit der Etappe: Korsika (42.20/9.10) -> Europe/Paris, am 2026-04-05
# Sommerzeit (UTC+2). LITERALE -- bewusst nicht aus derselben Zonenaufloesung
# gezogen, die der Pruefling benutzt.
TZ_ORT = ZoneInfo("Europe/Paris")
# Die beiden Ende-Zeiten sind an der GEMERGTEN Ableitung
# `_derive_wet_block_end()` (#2051 S1) gemessen, nicht aus der Lage
# geschaetzt -- sie folgen zwei verschiedenen Konventionen, und das ist dort
# Absicht: bei bekanntem Ende zaehlt das letzte NASSE Frame, bei der
# Untergrenze die Reichweite seiner Deckung.
ENDE_LOKAL = "12:30"       # Lage A: letztes nasses Frame (Slot +30)
HORIZONT_LOKAL = "14:45"   # Lage B: Deckungsende des letzten Frames (Slot +150 +15)
BEGINN_LOKAL = "12:45"     # Lage E: kuenftiger Beginn (Slot +45)
# Lage C endet IN der laufenden Viertelstunde. Genannt wird die Deckungsgrenze
# des laufenden Frames (Slot +15), NICHT sein Zeitstempel (Slot +0) -- der
# laege VOR dem Pruefzeitpunkt 12:07 und waere eine Aussage ueber die
# Vergangenheit im Gewand einer Auskunft ueber die Zukunft.
LAGE_C_ENDE_LOKAL = "12:15"
LAGE_C_FRAME_LOKAL = "12:00"
PRUEFZEIT_MIN = 12 * 60 + 7   # 12:07 Ortszeit, in Minuten seit Mitternacht

LAEUFT = "läuft bereits"                             # S2b-Freigabe
# Ende-Wortlaut aus #2051 S1 (PO-Entscheid 2026-08-22), Lage A = bekanntes
# Ende, Lage B = belegte Untergrenze.
ENDE_WORTLAUT = "letzter Regen gegen"          # Ende bekannt (Lage A)
ENDE_FORM = f"{ENDE_WORTLAUT} {ENDE_LOKAL}"
UNTERGRENZE_WORTLAUT = "Regen mindestens bis"  # kein Ende absehbar (Lage B)
UNTERGRENZE_FORM = f"{UNTERGRENZE_WORTLAUT} {HORIZONT_LOKAL}"
# Kurznachricht: `@HH:MM` = "hoert um HH:MM auf", ` >@HH:MM` = "hoert
# fruehestens um HH:MM auf". Das `>` traegt die Bedeutung, es ist kein
# Trennzeichen (`render.py::_sms_onset_ende`). Lage B laeuft ebenfalls, traegt
# also zusaetzlich den `now`-Marker.
SMS_UNTERGRENZE = f"now >@{HORIZONT_LOKAL}"
# Kurznachricht (ENGLISCH): `now` an der Stelle des Beginns, danach die
# Ende-Grammatik aus #2051. `12:15` waere der falsche kuenftige Beginn, den
# die Laufend-Kurznachricht nicht mehr behaupten darf.
SMS_LAUFEND = f"now@{ENDE_LOKAL}"
SMS_FALSCHER_BEGINN = "@12:15"
# Die Beginn-Angabe ("in 8 Min"). Negative Vorschau, damit der Cooldown-Satz
# ("... hoechstens einmal in 30 Minuten") nicht als Beginn-Angabe zaehlt.
_BEGINN_MIN = re.compile(r"in \d+ Min(?![a-zäöüA-Z])")

_ANGELEGT: list[str] = []


@pytest.fixture(autouse=True)
def _aufraeumen():
    """Jeder Test raeumt die von ihm angelegten `user_id`-Ablagen ab —
    Datentraeger und Test-Postfach werden mit Parallelsessions geteilt."""
    _ANGELEGT.clear()
    yield
    for uid in _ANGELEGT:
        _clean_user(uid)


def _uid(tag: str) -> str:
    uid = f"tdd-2050-s2b-{tag}-{uuid.uuid4().hex[:6]}"
    _ANGELEGT.append(uid)
    return uid


def _quelle(*, nass_bis: int, nass_von: int = 0, konvektiv: bool = False,
            gesamt: int = 11, ab=None, rate: float = 2.0):
    """Frames im 15-Min-Raster ab `ab` (Default `_SLOT`); die Slots
    `[nass_von, nass_bis)` liegen ueber der Trockenschwelle
    (`_DRY_THRESHOLD_MM_H`, 0,1 mm/h) mit `rate` mm/h.

    `ab`/`rate` sind Vorbelegungen fuer AC-11b (zweite, eigenstaendige Lage zu
    einem spaeteren Rasterslot) -- die Defaults halten alle uebrigen Lagen
    unveraendert."""
    anker = _SLOT if ab is None else ab

    def _frames(lat: float, lon: float) -> list:
        from providers.brightsky import RadarFrame
        return [
            RadarFrame(
                timestamp=anker + timedelta(minutes=15 * k),
                precip_mm_h=rate if nass_von <= k < nass_bis else 0.0,
                is_convective=konvektiv and nass_von <= k < nass_bis,
            )
            for k in range(gesamt)
        ]
    return _frames


# Lage A: laeuft und hoert im Sichtfenster auf (Ende = Slot +45 Min).
def _laeuft_mit_ende(konvektiv: bool = False):
    return _quelle(nass_bis=3, konvektiv=konvektiv)


# Lage B: laeuft ueber den verfuegbaren Datenbestand hinaus (kein Ende).
def _laeuft_ohne_ende():
    return _quelle(nass_bis=11)


# Lage C: laeuft, hoert aber IN der laufenden Viertelstunde auf -- KEIN
# kuenftiges Frame ist nass, ein kuenftiger Beginn ist nicht bestimmbar
# (`onset_minutes is None`). NUR diese Lage erreicht die Bruchstellen 1-3.
def _laeuft_endet_im_slot():
    return _quelle(nass_bis=1)


# Lage E: Normalfall -- jetzt trocken, Beginn erst Slot +45 Min. (Bewusst
# NICHT Slot +30: dort faellt der kuenftige Beginn auf dieselbe Ortszeit wie
# das Ende der Lage A, und ein Literal haette zwei Bedeutungen.)
def _erst_spaeter():
    return _quelle(nass_von=3, nass_bis=6)


# Lage F (AC-11b): zweite, eigenstaendige Lage 75 Min spaeter -- eigener
# Rasterslot, jetzt trocken, Beginn erst +23 Min und mit 12 mm/h deutlich
# staerker als die 2 mm/h der ersten Lage.
_SLOT2 = _SLOT + timedelta(minutes=75)        # 11:15 UTC
_AT_LAUF2 = _SLOT2 + timedelta(minutes=7)     # 11:22 UTC, derselbe Cron-Versatz


def _neue_lage_spaeter():
    return _quelle(nass_von=2, nass_bis=5, ab=_SLOT2, rate=12.0)


def _quelle_jetzt(*, laufend: bool, rate: float = 10.0):
    """Dieselben Lagen wie oben, aber am RASTER DER WANDUHR ausgerichtet --
    fuer die zwei Ketten-Waechter (AC-11c, AC-15b), die ueber Bausteine
    laufen, die ihre eigene Uhr benutzen und sich nicht einfrieren lassen.

    `laufend=True` -> nur der aktuelle Slot ist nass (Lage C: laeuft, kein
    kuenftiger Beginn). `laufend=False` -> der aktuelle Slot ist trocken, der
    Regen beginnt in einem der naechsten Frames (Positivkontrolle).
    Faellt die Wanduhr genau auf eine Rastergrenze, deckt das Frame `now`
    weiterhin ab (`ts <= now < ts + 15 Min`) -- die Lage bleibt dieselbe."""
    def _frames(lat: float, lon: float) -> list:
        from providers.brightsky import RadarFrame
        jetzt = datetime.now(timezone.utc)
        slot = jetzt.replace(
            minute=(jetzt.minute // 15) * 15, second=0, microsecond=0,
        )
        nass = (lambda k: k == 0) if laufend else (lambda k: 1 <= k <= 3)
        return [
            RadarFrame(timestamp=slot + timedelta(minutes=15 * k),
                       precip_mm_h=rate if nass(k) else 0.0)
            for k in range(11)
        ]
    return _frames


def _radar(quelle) -> RadarNowcastService:
    return RadarNowcastService(frame_source=quelle)


def _aufbau(uid: str, tag: str, **flags):
    """Nutzer (Premium-Profil fuer den vierten Kanal) + Trip mit allen vier
    Kanaelen. Aufbau unter der gestellten Uhr, weil `save_trip()` die
    Ankunftszeiten beim Schreiben neu rechnet (Compute-on-Save, #802)."""
    _clean_user(uid)
    _write_premium_profile(uid, _AT)
    with freeze_time(_AT):
        return _radar_trip(
            uid, f"trip-2050-s2b-{tag}", send_email=True, send_telegram=True,
            send_sms=True, send_premium_sms=True, **flags,
        )


def _ohne_sperrzeit(uid: str, trip):
    """Sperrzeit aus (`alert_cooldown_minutes = 0`). PFLICHT fuer den
    Entdopplungs-Waechter: `check_radar_alerts()` liest den Trip vom
    Datentraeger, der Wert muss also mitgespeichert werden."""
    trip.alert_cooldown_minutes = 0
    with freeze_time(_AT):
        save_trip(trip, user_id=uid)
    return trip


def _lauf(uid: str, trip, quelle, *, at=_AT_LAUF, strecke=None):
    s = strecke or AlarmPruefstrecke(user_id=uid, settings=_settings_all_channels())
    return s.lauf(at=at, zweig="radar", trip=trip, radar_service=_radar(quelle))


def _mailtext(lauf) -> str:
    return "\n".join(f"{betreff}\n{koerper}" for betreff, koerper in lauf.mail)


def _kanaltext(lauf) -> str:
    """Betreff + Mailkoerper + Telegram-Text eines Laufs, zusammengelegt."""
    return _mailtext(lauf) + "\n" + "\n".join(lauf.telegram)


def _test_lauf(tag: str, quelle, **flags):
    """Ein Prueflauf auf eigener `user_id` (Aufraeumen per Fixture)."""
    uid = _uid(tag)
    return _lauf(uid, _aufbau(uid, tag, **flags), quelle)


def test_ac1_laufendes_ereignis_wird_als_laufend_gemeldet():
    """AC-1: das den aktuellen Rasterslot deckende Frame ist nass -> die
    Nachricht meldet "laeuft bereits" statt einer Beginn-Angabe."""
    lauf = _test_lauf("ac1", _laeuft_mit_ende())
    assert lauf.triggered_count == 1, (
        f"AC-1 Vorbedingung: der Lauf muss ausloesen -- sonst prueft der "
        f"Wortlaut nichts (war {lauf.triggered_count})."
    )
    text = _kanaltext(lauf)
    assert LAEUFT in text, f"AC-1: {LAEUFT!r} fehlt.\n{text}"
    assert not _BEGINN_MIN.search(text), (
        f"AC-1: kein Kanal darf einen kuenftigen Beginn behaupten.\n{text}"
    )


def test_ac2_kuenftiger_beginn_bleibt_unveraendert_bei_der_beginn_angabe():
    """AC-2: Regressions-Invariante -- BEWUSST von Anfang an GRUEN. Liegt das
    Ereignis wirklich in der Zukunft (jetzt trocken, nasses Frame erst Slot
    +30 Min), bleibt der bisherige Wortlaut unveraendert."""
    lauf = _test_lauf("ac2", _erst_spaeter())
    assert lauf.triggered_count == 1, (
        f"AC-2 Vorbedingung: der Normalfall muss ausloesen "
        f"(war {lauf.triggered_count})."
    )
    text = _kanaltext(lauf)
    assert _BEGINN_MIN.search(text), (
        f"AC-2: der Normalfall MUSS die Beginn-Angabe 'in N Min' behalten.\n{text}"
    )
    assert BEGINN_LOKAL in text, f"AC-2: Beginn-Uhrzeit {BEGINN_LOKAL} fehlt.\n{text}"
    assert LAEUFT not in text, (
        f"AC-2: ein kuenftiger Beginn darf NICHT als laufend erscheinen.\n{text}"
    )


def test_ac3_laufendes_gewitter_wird_ebenfalls_als_laufend_gemeldet():
    """AC-3: dieselbe Lage konvektiv -- auch das laufende Gewitter wird als
    laufend gemeldet, nicht nur laufender Regen (`is_convective`)."""
    lauf = _test_lauf("ac3", _laeuft_mit_ende(konvektiv=True))
    text = _kanaltext(lauf)
    assert "Gewitter" in text, (
        f"AC-3 Vorbedingung: die Lage muss als Gewitter erkannt sein "
        f"(triggered_count={lauf.triggered_count}).\n{text}"
    )
    assert LAEUFT in text, f"AC-3: das laufende GEWITTER zeigt {LAEUFT!r} nicht.\n{text}"
    assert not _BEGINN_MIN.search(text), (
        f"AC-3: kein Kanal darf einen kuenftigen Gewitterbeginn behaupten.\n{text}"
    )


def test_ac4_laufendes_ereignis_nennt_das_voraussichtliche_ende():
    """AC-4: auf die laufende nasse Strecke folgt bei Slot +45 Min ein
    trockenes Frame -- der Trockenuebergang ist damit BEOBACHTET und das Ende
    bekannt. Genannt wird das letzte NASSE Frame (Slot +30), so leitet
    `_derive_wet_block_end()` (#2051 S1, gemergt) es ab; an dieser Ableitung
    ist der Erwartungswert gemessen, nicht aus der Lage geschaetzt.

    Gegenrichtung mitgeprueft (Muster #2051 AC-20): weder die Langform
    "Regen mindestens bis" noch das Kurznachrichten-Praefix ` >` duerfen
    vorkommen. Beide sagen "hoert FRUEHESTENS um 12:45 auf" -- die Umkehrung.
    Ohne diese Haelfte waere ein Renderer, der IMMER die Untergrenzen-Form
    baut, hier wie in AC-5 gruen."""
    lauf = _test_lauf("ac4", _laeuft_mit_ende())
    text = _kanaltext(lauf) + "\n" + "\n".join(lauf.sms)
    assert ENDE_FORM in text, (
        f"AC-4: das bekannte Ende ({ENDE_FORM!r}, letztes nasses Frame) "
        f"fehlt.\n{text}"
    )
    assert UNTERGRENZE_WORTLAUT not in text and " >" not in text, (
        f"AC-4: die Untergrenzen-Form ({UNTERGRENZE_WORTLAUT!r} bzw. ` >`) "
        f"behauptet, das Ende sei UNBEKANNT -- hier ist der Trockenuebergang "
        f"aber beobachtet.\n{text}"
    )


def test_ac4b_ende_in_der_laufenden_viertelstunde_liegt_nach_dem_pruefzeitpunkt():
    """AC-4b: endet das laufende Ereignis IN der laufenden Viertelstunde, ist
    das genannte Ende die Deckungsgrenze des laufenden Frames (12:15) und
    NICHT dessen Zeitstempel (12:00).

    Die eigentliche Zusicherung ist nicht die Zahl, sondern ihre Lage: die
    genannte Zeit muss NACH dem Pruefzeitpunkt (12:07) liegen. Sonst liest
    der Wanderer, waehrend er im Regen steht, dass der Regen vorbei sei --
    eine Aussage ueber die Vergangenheit im Gewand einer Auskunft ueber die
    Zukunft. Die Konvention ist nicht neu: der Untergrenzen-Zweig aus
    #2051 S1 nennt ebenfalls die Deckungsgrenze (Lage B, 14:45 statt 14:30).

    Beide Richtungen: dreht jemand auf den Frame-Zeitstempel zurueck, faellt
    dieser Test -- ueber die Zahl UND ueber den Lagevergleich."""
    lauf = _test_lauf("ac4b", _laeuft_endet_im_slot())
    text = _kanaltext(lauf) + "\n" + "\n".join(lauf.sms)
    assert f"{ENDE_WORTLAUT} {LAGE_C_ENDE_LOKAL}" in text, (
        f"AC-4b: erwartet {ENDE_WORTLAUT!r} mit der Deckungsgrenze "
        f"{LAGE_C_ENDE_LOKAL} (triggered_count={lauf.triggered_count}).\n{text}"
    )
    assert LAGE_C_FRAME_LOKAL not in text, (
        f"AC-4b: {LAGE_C_FRAME_LOKAL} ist der Zeitstempel des laufenden "
        f"Frames und liegt VOR dem Pruefzeitpunkt -- als Ende genannt sagt er "
        f"dem Wanderer, der Regen sei vorbei, waehrend es regnet.\n{text}"
    )
    assert f"now@{LAGE_C_ENDE_LOKAL}" in text, (
        f"AC-4b: die Kurznachricht muss dieselbe Deckungsgrenze tragen "
        f"('now@{LAGE_C_ENDE_LOKAL}').\n{text}"
    )
    treffer = re.search(rf"{ENDE_WORTLAUT} (\d{{1,2}}):(\d{{2}})", text)
    assert treffer, f"AC-4b: keine Ende-Uhrzeit im Text gefunden.\n{text}"
    genannt = int(treffer.group(1)) * 60 + int(treffer.group(2))
    assert genannt > PRUEFZEIT_MIN, (
        f"AC-4b: das genannte Ende ({treffer.group(0)!r}) liegt VOR dem "
        f"Pruefzeitpunkt 12:07 -- ein Ende in der Vergangenheit ist keine "
        f"Auskunft ueber ein laufendes Ereignis.\n{text}"
    )


def test_ac5_kein_ende_im_datenbestand_wird_ausdruecklich_gesagt():
    """AC-5: alle verfuegbaren Frames sind nass -> die Nachricht sagt
    ausdruecklich, dass kein Ende erkennbar ist, und nennt die Reichweite
    (Uhrzeit des letzten Frames) -- OHNE eine Dauer zu erfinden."""
    lauf = _test_lauf("ac5", _laeuft_ohne_ende())
    text = _kanaltext(lauf) + "\n" + "\n".join(lauf.sms)
    assert SMS_UNTERGRENZE in text, (
        f"AC-5: die Kurznachricht muss die Untergrenzen-Form "
        f"{SMS_UNTERGRENZE!r} tragen -- ohne das `>` liest der Wanderer "
        f"'hoert um {HORIZONT_LOKAL} auf' statt 'fruehestens'.\n{text}"
    )
    assert UNTERGRENZE_FORM in text, (
        f"AC-5: {UNTERGRENZE_FORM!r} fehlt -- die Zeitreihe ist ausgegangen, "
        f"waehrend es noch regnete, die Uhrzeit des letzten verfuegbaren "
        f"Frames ist damit belegte Untergrenze und kein Ende "
        f"(triggered_count={lauf.triggered_count}).\n{text}"
    )
    assert ENDE_WORTLAUT not in text, (
        f"AC-5: die Form des BEKANNTEN Endes ('letzter Regen gegen') darf hier "
        f"nicht stehen -- sie behauptet einen beobachteten Trockenuebergang, "
        f"den es im Datenbestand nicht gibt.\n{text}"
    )
    assert not _BEGINN_MIN.search(text), (
        f"AC-5: es darf KEINE erfundene Dauer im Text stehen.\n{text}"
    )


def test_ac6_alarm_mail_sagt_laeuft_bereits_statt_ab_uhrzeit():
    """AC-6: der E-Mail-Zweig (Einzelort) verliert die Beginn-Form
    "ab HH:MM"/"in N Min" und traegt stattdessen die Laufend-Aussage."""
    lauf = _test_lauf("ac6", _laeuft_mit_ende())
    assert lauf.mail, f"AC-6 Vorbedingung: keine E-Mail ({lauf.triggered_count})."
    text = _mailtext(lauf)
    assert LAEUFT in text, f"AC-6: die E-Mail sagt nicht {LAEUFT!r}.\n{text}"
    assert "ab 12:15" not in text, (
        f"AC-6: die E-Mail behauptet weiterhin einen Beginn ('ab 12:15' -- das "
        f"naechste kuenftige Frame).\n{text}"
    )
    assert not _BEGINN_MIN.search(text), (
        f"AC-6: die E-Mail traegt weiterhin die Beginn-Angabe.\n{text}"
    )


def test_ac7_telegram_langform_sagt_laeuft_bereits():
    """AC-7: derselbe Lauf, Telegram-Langform (rich) -- dieselbe Aussage."""
    lauf = _test_lauf("ac7", _laeuft_mit_ende())
    assert lauf.telegram, f"AC-7 Vorbedingung: kein Telegram ({lauf.triggered_count})."
    text = "\n".join(lauf.telegram)
    assert LAEUFT in text, f"AC-7: Telegram sagt nicht {LAEUFT!r}.\n{text}"
    assert not _BEGINN_MIN.search(text), (
        f"AC-7: Telegram traegt weiterhin die Beginn-Angabe.\n{text}"
    )


def test_ac8_kurznachricht_kennzeichnet_den_laufend_fall():
    """AC-8: SMS und Premium-SMS behaupten keinen kuenftigen Beginn mehr. Das
    Ende steht in der #2051-Form (`@HH:MM`, bekanntes Ende -- Lage A hat den
    Trockenuebergang beobachtet), davor der Laufend-Marker. Zeichenbudget
    (140) bleibt gewahrt."""
    lauf = _test_lauf("ac8", _laeuft_mit_ende())
    assert lauf.sms and lauf.premium_sms, (
        f"AC-8 Vorbedingung: sms={lauf.sms!r} premium_sms={lauf.premium_sms!r}"
    )
    for kanal, texte in (("sms", lauf.sms), ("premium_sms", lauf.premium_sms)):
        text = "\n".join(texte)
        assert SMS_LAUFEND in text, (
            f"AC-8 ({kanal}): Laufend-Marker samt Ende-Token {SMS_LAUFEND!r} "
            f"fehlt.\n{text}"
        )
        assert SMS_FALSCHER_BEGINN not in text, (
            f"AC-8 ({kanal}): {SMS_FALSCHER_BEGINN!r} behauptet weiter einen "
            f"kuenftigen Beginn -- das naechste kuenftige Frame.\n{text}"
        )
        assert " >" not in text, (
            f"AC-8 ({kanal}): ` >` ist in der #2051-Grammatik die "
            f"UNTERGRENZEN-Form. Lage A hat ein beobachtetes Ende -- hier "
            f"waere sie eine Falschaussage.\n{text}"
        )
        assert all(len(t) <= 140 for t in texte), (
            f"AC-8 ({kanal}): Zeichenbudget 140 gerissen: {[len(t) for t in texte]}"
        )


def test_ac9_telegram_kurzform_erbt_den_laufend_text_der_sms():
    """AC-9: bei `telegram_style="kurzform"` traegt Telegram denselben
    Kurznachrichten-Text wie die SMS (geerbtes Verhalten seit #1948 S4)."""
    lauf = _test_lauf("ac9", _laeuft_mit_ende(), telegram_style="kurzform")
    assert lauf.telegram, f"AC-9 Vorbedingung: kein Telegram ({lauf.triggered_count})."
    text = "\n".join(lauf.telegram)
    assert SMS_LAUFEND in text, (
        f"AC-9: die Kurzform traegt {SMS_LAUFEND!r} nicht wie die SMS.\n{text}"
    )
    assert SMS_FALSCHER_BEGINN not in text, (
        f"AC-9: die Kurzform behauptet weiter einen kuenftigen Beginn "
        f"({SMS_FALSCHER_BEGINN!r}).\n{text}"
    )


def test_ac10_ereignis_endet_in_der_laufenden_viertelstunde_loest_trotzdem_aus():
    """AC-10: nasser aktueller Slot, ausschliesslich TROCKENE kuenftige
    Frames -> `onset_minutes is None`. Heute liefert `radar_alert_due()`
    daran `False` und der Alarm faellt ERSATZLOS aus (Bruchstelle 1).

    Vorgeschaltet die Konstruktions-Gegenprobe: DIESELBEN Frames, einmal zur
    Cron-Laufzeit 10:07 und einmal exakt auf dem Slot-Start 10:00 gemessen.
    Ohne sie waere "kein kuenftiger Beginn" nicht von "gar kein Regen"
    unterscheidbar -- und der Waechter beruehrte den Laufend-Zweig nie."""
    uid = _uid("ac10")
    trip = _aufbau(uid, "ac10")
    lat, lon = trip.stages[0].waypoints[0].lat, trip.stages[0].waypoints[0].lon
    # Frame-Cache ist ein Prozess-Singleton mit Koordinaten-Schluessel
    # (TTL 300 s) -- ohne Reset lieferte die zweite Messung die erste zurueck.
    with freeze_time(_AT_LAUF):
        reset_shared_radar_cache_for_tests()
        versteckt = _radar(_laeuft_endet_im_slot()).get_nowcast(lat, lon)
    with freeze_time(_SLOT):
        reset_shared_radar_cache_for_tests()
        sichtbar = _radar(_laeuft_endet_im_slot()).get_nowcast(lat, lon)
    reset_shared_radar_cache_for_tests()
    assert versteckt.onset_minutes is None, (
        f"AC-10 Konstruktion: zur Cron-Laufzeit darf KEIN kuenftiger Beginn "
        f"bestimmbar sein (war {versteckt.onset_minutes})."
    )
    assert sichtbar.onset_minutes == 0, (
        f"AC-10 Konstruktion: dieselben Frames, gemessen auf dem Slot-Start, "
        f"muessen das nasse Frame zeigen (onset 0, war {sichtbar.onset_minutes}) "
        f"-- sonst regnet es gar nicht und der Waechter misst Luft."
    )

    lauf = _lauf(uid, trip, _laeuft_endet_im_slot())
    assert lauf.triggered_count == 1, (
        f"AC-10: das Ereignis laeuft JETZT und endet in der laufenden "
        f"Viertelstunde -- ein Alarm muss trotzdem raus. War "
        f"triggered_count={lauf.triggered_count}."
    )


def test_ac11_unveraenderte_laufende_lage_loest_kein_zweites_mal_aus():
    """AC-11: zweiter Prueflauf mit identischer, weiterhin laufender Lage ->
    kein zweiter Alarm. Die Sperrzeit ist AUSGESCHALTET
    (`alert_cooldown_minutes = 0`), sonst waere der Test aus dem falschen
    Grund gruen und wuerde die Entdopplung ueberhaupt nicht messen. Die
    Kontrolle auf frischem Datentraeger zeigt, dass die Stille aus dem
    gebuchten Zustand kommt, nicht aus den Eingangsdaten."""
    uid, kontrolle = _uid("ac11"), _uid("ac11-ctrl")
    trip = _ohne_sperrzeit(uid, _aufbau(uid, "ac11"))
    assert trip.alert_cooldown_minutes == 0, (
        "AC-11 Vorbedingung: die Sperrzeit MUSS aus sein, sonst misst der "
        "Waechter den Cooldown statt der Entdopplung."
    )
    strecke = AlarmPruefstrecke(user_id=uid, settings=_settings_all_channels())
    lauf1 = _lauf(uid, trip, _laeuft_endet_im_slot(), strecke=strecke)
    assert lauf1.triggered_count == 1, (
        f"AC-11 Vorbedingung: Lauf 1 muss ausloesen und die Ereignis-Identitaet "
        f"buchen (war {lauf1.triggered_count})."
    )

    # 🔴 +5 Min, NICHT +15: die Spec verlangt fuer Lauf 2 eine UNVERAENDERTE
    # Lage ("weiterhin laufend, weiterhin kein kuenftiger Beginn"). Bei +15
    # Min deckt der Slot 10:15 die Pruefzeit ab -- und der ist in Lage C
    # TROCKEN, das Ereignis waere dann wirklich vorbei. Lauf 2 schwiege dann
    # aus Mangel an Lage statt wegen der Entdopplung, und dieser Waechter
    # waere wertlos. Bitte nicht "aufraeumend" zurueckdrehen.
    #
    # Gefunden hat das die Positivkontrolle unten, nicht der Haupttest: Sie
    # laeuft auf frischem Datentraeger, wo es keine Entdopplung gibt, die
    # etwas unterdruecken koennte -- und loeste trotzdem nicht aus. Ohne sie
    # waere AC-11 gruen gewesen, waehrend die Entdopplung unbewacht blieb.
    at2 = _AT_LAUF + timedelta(minutes=5)
    lauf2 = _lauf(uid, trip, _laeuft_endet_im_slot(), at=at2, strecke=strecke)
    assert lauf2.triggered_count == 0, (
        f"AC-11: dasselbe laufende Ereignis darf kein zweites Mal gemeldet "
        f"werden (war {lauf2.triggered_count})."
    )

    trip_k = _ohne_sperrzeit(kontrolle, _aufbau(kontrolle, "ac11-ctrl"))
    lauf_k = _lauf(kontrolle, trip_k, _laeuft_endet_im_slot(), at=at2)
    assert lauf_k.triggered_count == 1, (
        f"AC-11 Gegenprobe: dieselben Eingangsdaten zum selben Zeitpunkt OHNE "
        f"Lauf 1 muessen ausloesen -- sonst kommt die Stille oben nicht von der "
        f"Entdopplung (war {lauf_k.triggered_count})."
    )


def test_ac11b_neues_ereignis_nach_laufendem_wird_nicht_als_wiederholung_unterdrueckt():
    """AC-11b: die GEGENRICHTUNG zu AC-11 -- die gefaehrlichere, weil ihr
    Schaden ein AUSBLEIBENDER Alarm ist (Befund #2065).

    `check_event_identity_gate` vergleicht Punkt gegen Punkt und wertet eine
    Differenz bis `NOWCAST_HORIZON_MIN` (180 Min) als Duplikat
    (`alert_gate.py:489-494`). Der Laufend-Fall bucht mit `now_utc` einen
    Punkt, den es vorher gar nicht gab -- eine 75 Min spaeter aufziehende,
    EIGENSTAENDIGE Lage liegt damit im Duplikat-Fenster und darf trotzdem
    nicht verschluckt werden. Sie kommt ueber die Eskalationspruefung durch
    (V2, `alert_gate.py:669` -- "muss IMMER durchkommen"): 12 mm/h gegen
    2 mm/h ist eine echte Verschaerfung. Sperrzeit wieder aus; den
    Identitaets-Gate beruehrt das nicht (der Radar-Pfad ruft ihn OHNE
    `cooldown_minutes` auf, sein Fenster bleibt 180 Min)."""
    uid = _uid("ac11b")
    trip = _ohne_sperrzeit(uid, _aufbau(uid, "ac11b"))
    lat, lon = trip.stages[0].waypoints[0].lat, trip.stages[0].waypoints[0].lon

    # Konstruktions-Gegenprobe: beide Laeufe sehen die Lage, die sie sollen.
    with freeze_time(_AT_LAUF):
        reset_shared_radar_cache_for_tests()
        lage1 = _radar(_laeuft_endet_im_slot()).get_nowcast(lat, lon)
    with freeze_time(_SLOT):
        reset_shared_radar_cache_for_tests()
        lage1_am_slotstart = _radar(_laeuft_endet_im_slot()).get_nowcast(lat, lon)
    with freeze_time(_AT_LAUF2):
        reset_shared_radar_cache_for_tests()
        lage2 = _radar(_neue_lage_spaeter()).get_nowcast(lat, lon)
    reset_shared_radar_cache_for_tests()
    assert lage1.onset_minutes is None and lage1_am_slotstart.onset_minutes == 0, (
        f"AC-11b Konstruktion: Lauf 1 muss die LAUFENDE Lage ohne kuenftigen "
        f"Beginn sehen (onset={lage1.onset_minutes}, am Slot-Start "
        f"{lage1_am_slotstart.onset_minutes})."
    )
    assert lage2.onset_minutes == 23 and not getattr(lage2, "already_running", False), (
        f"AC-11b Konstruktion: Lauf 2 muss eine NEUE Lage mit kuenftigem "
        f"Beginn sehen, nicht dieselbe laufende (onset={lage2.onset_minutes})."
    )
    assert lage2.max_rate_mm_h >= 10.0, (
        f"AC-11b Konstruktion: Lauf 2 muss deutlich staerker sein als Lauf 1 "
        f"-- sonst traegt die Eskalation nicht (war {lage2.max_rate_mm_h})."
    )

    # Positivkontrolle auf frischem Datentraeger: die zweite Lage ist FUER SICH
    # alarmwuerdig. Ohne sie waere eine Stille unten nicht von "diese Lage
    # loest generell nicht aus" unterscheidbar.
    kontrolle = _uid("ac11b-ctrl")
    trip_k = _ohne_sperrzeit(kontrolle, _aufbau(kontrolle, "ac11b-ctrl"))
    lauf_k = _lauf(kontrolle, trip_k, _neue_lage_spaeter(), at=_AT_LAUF2)
    assert lauf_k.triggered_count == 1, (
        f"AC-11b Positivkontrolle: die zweite Lage muss allein ausloesen "
        f"(war {lauf_k.triggered_count})."
    )

    strecke = AlarmPruefstrecke(user_id=uid, settings=_settings_all_channels())
    lauf1 = _lauf(uid, trip, _laeuft_endet_im_slot(), strecke=strecke)
    assert lauf1.triggered_count == 1, (
        f"AC-11b Vorbedingung: Lauf 1 muss ausloesen und die Ereignis-"
        f"Identitaet buchen -- ohne diese Buchung prueft der zweite Lauf "
        f"nichts (war {lauf1.triggered_count})."
    )

    lauf2 = _lauf(uid, trip, _neue_lage_spaeter(), at=_AT_LAUF2, strecke=strecke)
    assert lauf2.triggered_count == 1, (
        f"AC-11b: die neue, eigenstaendige und staerkere Lage darf NICHT als "
        f"Wiederholung des laufenden Ereignisses unterdrueckt werden "
        f"(war {lauf2.triggered_count})."
    )


def test_ac11c_ortsvergleich_meldet_dasselbe_laufende_ereignis_nicht_zweimal():
    """AC-11c: die Entdopplung des ORTSVERGLEICHS (Adversary-Fund F001).

    AC-11/AC-11b bewachen sie nur auf der Trip-Seite -- die Pruefstrecke kennt
    keinen Compare-Zweig. `compare_radar_alert._identity_inputs` war damit
    unbewacht: Ohne den Laufend-Zweig bliebe `onset_at` dort `None`, und
    `_times_overlap` faende NIE einen Kandidaten. Die Entdopplung waere ein
    stiller No-Op -- sie saehe funktionsfaehig aus und wirkte nie.

    Direkt gegen `CompareRadarAlertService` (Muster AC-12), Sperrzeit AUS
    (`alert_cooldown_minutes = 0`), damit nicht sie statt der Entdopplung
    entscheidet. Positivkontrolle auf frischem Zustand: sonst waere ein
    schweigender zweiter Lauf nicht von "diese Lage loest generell nicht aus"
    zu unterscheiden."""
    from app.loader import save_location
    from services.compare_radar_alert import CompareRadarAlertService

    from tests.tdd.test_compare_radar_alert import (
        _CoordFrameSource, _clean_user as _clean_compare_user, _location,
        _radar_preset, _settings_email_capable_dummy, _write_preset_file,
    )

    lat, lon = 46.0207, 7.7491

    def _lauf(uid: str) -> list:
        """Ein Prueflauf wie ein Cron-Tick: frische Instanz, eigener Mail-Abgriff."""
        reset_shared_radar_cache_for_tests()
        mails: list = []
        CompareRadarAlertService(
            settings=_settings_email_capable_dummy(), user_id=uid,
            radar_service=_radar(_CoordFrameSource(
                {(lat, lon): _quelle_jetzt(laufend=True, rate=2.0)(lat, lon)},
            )),
            mail_sink=lambda subject, body: mails.append((subject, body)),
        ).check_all_compare_presets()
        return mails

    def _aufbau_preset(uid: str) -> None:
        _clean_compare_user(uid)
        save_location(_location("loc-s2b", "Zermatt-S2b", lat, lon), user_id=uid)
        preset = _radar_preset(
            f"cp-{uid}", ["loc-s2b"], ["gregor-test@henemm.com"],
        )
        preset["alert_cooldown_minutes"] = 0
        _write_preset_file(uid, [preset])

    uid, kontrolle = _uid("ac11c"), _uid("ac11c-ctrl")
    try:
        _aufbau_preset(uid)
        erste = _lauf(uid)
        assert len(erste) == 1, (
            f"AC-11c Vorbedingung: der erste Lauf muss die laufende Lage melden "
            f"und ihre Ereignis-Identitaet buchen (war {len(erste)} Mails)."
        )
        assert LAEUFT in erste[0][1], (
            f"AC-11c Vorbedingung: die Ortsvergleich-Mail muss die "
            f"Laufend-Aussage tragen.\n{erste[0][1]}"
        )

        zweite = _lauf(uid)
        assert zweite == [], (
            f"AC-11c: dasselbe laufende Ereignis darf im Ortsvergleich kein "
            f"zweites Mal gemeldet werden (war {len(zweite)} Mails)."
        )

        _aufbau_preset(kontrolle)
        assert len(_lauf(kontrolle)) == 1, (
            "AC-11c Positivkontrolle: dieselbe Lage auf frischem Zustand MUSS "
            "melden -- sonst kommt die Stille oben nicht von der Entdopplung."
        )
    finally:
        _clean_compare_user(uid)
        _clean_compare_user(kontrolle)


def test_ac12_ortsvergleich_buendel_traegt_den_laufenden_ort_mit():
    """AC-12: ein Buendel aus einem laufenden Ort (ohne bestimmbaren
    kuenftigen Beginn) und einem Ort mit kuenftigem Beginn -- der laufende
    Ort faellt heute VOR dem `OnsetEvent`-Bau aus dem Filter
    (`nc.onset_minutes is not None`, Bruchstelle 4)."""
    laufend = NowcastResult(
        onset_minutes=None, intensity_label="Starker Regen", source="radar",
    )
    laufend.already_running = True
    laufend.event_end_minutes = 23   # Feldname aus #2051 S1 (gemergt)
    kuenftig = NowcastResult(
        onset_minutes=25, intensity_label="Leichter Regen", source="radar",
    )
    with freeze_time(_AT_LAUF):
        msg = to_multi_location_onset_alert_message(
            [("Laufend-Ort", laufend), ("Zukunft-Ort", kuenftig)],
            tz=TZ_ORT, stand_at="12:07",
        )
        _html, plain = render_email(msg)
        text = f"{plain}\n{render_telegram(msg)}"
    assert "Zukunft-Ort" in text, (
        f"AC-12 Vorbedingung: der Ort mit kuenftigem Beginn muss im Buendel "
        f"stehen.\n{text}"
    )
    assert "Laufend-Ort" in text, (
        f"AC-12: der laufende Ort darf NICHT vor dem Nachrichtenbau "
        f"herausfallen.\n{text}"
    )
    assert LAEUFT in text, f"AC-12: Laufend-Aussage fehlt.\n{text}"


def test_ac13_laufender_fall_ohne_kuenftigen_beginn_liefert_alle_vier_kanaele():
    """AC-13: derselbe Eingangsfall wie AC-10/AC-11 laeuft ohne Exception
    durch (`now + timedelta(minutes=None)` stuerzt ab, sobald Bruchstelle 1
    faellt) und liefert gueltige Inhalte auf allen vier Kanaelen."""
    lauf = _test_lauf("ac13", _laeuft_endet_im_slot())
    assert lauf.mail and lauf.telegram and lauf.sms and lauf.premium_sms, (
        f"AC-13: alle vier Kanaele muessen Inhalt tragen: mail={lauf.mail!r} "
        f"telegram={lauf.telegram!r} sms={lauf.sms!r} "
        f"premium_sms={lauf.premium_sms!r}"
    )
    assert LAEUFT in _kanaltext(lauf), (
        f"AC-13: die Nachricht muss trotz fehlendem kuenftigen Beginn die "
        f"Laufend-Aussage tragen.\n{_kanaltext(lauf)}"
    )


def test_ac13b_staerke_im_laufend_fall_entspricht_dem_laufenden_bild():
    """AC-13b: die Staerke des LAUFENDEN Bildes darf nicht verlorengehen.

    `max_rate`/`is_convective` entstehen heute nur aus dem Zukunftsfenster
    (`f.timestamp >= now`) -- im Laufend-Fall ohne kuenftigen Regen bleibt
    davon "Kein Niederschlag" uebrig. Folgen: der sinnlose Satz "Kein
    Niederschlag laeuft bereits" (gegen AC-13, "gueltige Kanal-Inhalte"), ein
    laufendes Gewitter ohne Gewitter-Kennzeichen (gegen AC-3) und die
    NIEDRIGSTE Dringlichkeitsstufe, waehrend es schuettet -- was ueber die
    Eskalationspruefung auf AC-11b zurueckwirkt.

    Referenz sind DIESELBEN Frames am Slot-Start, wo das nasse Frame im
    Zukunftsfenster liegt und heute schon ein Regen-Label ergibt: aus dem
    Pruefling selbst, aber aus einem Moment ohne strittiges Verhalten."""
    uid = _uid("ac13b")
    trip = _aufbau(uid, "ac13b")
    lat, lon = trip.stages[0].waypoints[0].lat, trip.stages[0].waypoints[0].lon
    with freeze_time(_SLOT):
        reset_shared_radar_cache_for_tests()
        referenz = _radar(_laeuft_endet_im_slot()).get_nowcast(lat, lon)
    with freeze_time(_AT_LAUF):
        reset_shared_radar_cache_for_tests()
        laufend = _radar(_laeuft_endet_im_slot()).get_nowcast(lat, lon)
        reset_shared_radar_cache_for_tests()
        gewitter = _radar(_quelle(nass_bis=1, konvektiv=True)).get_nowcast(lat, lon)
    reset_shared_radar_cache_for_tests()

    assert referenz.intensity_label != INTENSITY_DRY, (
        f"AC-13b Konstruktion: am Slot-Start muss dieselbe Lage ein "
        f"Regen-Label ergeben (war {referenz.intensity_label!r})."
    )
    assert laufend.intensity_label == referenz.intensity_label, (
        f"AC-13b: dieselben Frames, nur {_AT_LAUF - _SLOT} spaeter gemessen -- "
        f"die Staerke darf nicht auf {laufend.intensity_label!r} umkippen, "
        f"waehrend das laufende Frame {referenz.intensity_label!r} zeigt."
    )
    assert gewitter.is_convective, (
        "AC-13b: ein LAUFENDES Gewitter muss konvektiv bleiben -- sonst "
        "verliert die Nachricht das Gewitter-Kennzeichen (AC-3)."
    )

    lauf = _lauf(uid, trip, _laeuft_endet_im_slot())
    text = _kanaltext(lauf)
    assert INTENSITY_DRY not in text, (
        f"AC-13b: '{INTENSITY_DRY}' darf in einer Laufend-Meldung nicht "
        f"stehen -- das ist kein gueltiger Kanal-Inhalt.\n{text}"
    )


def test_ac14_jetzt_antwort_meldet_das_laufende_ereignis_als_laufend():
    """AC-14: `/jetzt` (`format_now_text`) macht dieselbe Falschaussage aus
    derselben Datenbasis -- heute steht dort bei laufendem Ereignis ohne
    kuenftigen Beginn die Entwarnung "kein Regen erwartet"."""
    result = NowcastResult(
        onset_minutes=None, intensity_label="Starker Regen", source="radar",
    )
    # Feldnamen aus #2051 S1 (gemergt): das Ende heisst `event_end_minutes`,
    # der Untergrenzen-Waechter `event_ongoing_beyond_horizon`. S2b legt nur
    # `already_running` daneben -- kein zweites Ende-Feld.
    result.already_running = True
    result.event_end_minutes = 23   # 10:07 + 23 Min = 10:30 UTC = 12:30 Ortszeit
    with freeze_time(_AT_LAUF):
        text = RadarNowcastService().format_now_text(
            result, tz=TZ_ORT, include_source=False,
        )
    assert LAEUFT in text, f"AC-14: die /jetzt-Antwort sagt nicht {LAEUFT!r}.\n{text}"
    assert ENDE_LOKAL in text, f"AC-14: das Ende ({ENDE_LOKAL}) fehlt.\n{text}"
    assert "kein Regen erwartet" not in text, f"AC-14: Entwarnung.\n{text}"


def test_ac14b_vorschau_sagt_dasselbe_wie_der_versand():
    """AC-14b: der Vorschau-/Replay-Weg (`/alert-preview`, Frame-Mitschnitt)
    muss fuer den Laufend-Fall DIESELBE Aussage liefern wie der Versand.

    Betrieblicher Grund, kein aesthetischer: Mit dieser Vorschau wird beim
    Ausrollen geprueft. Zeigte sie etwas anderes als der Versandweg, pruefte
    die Staging-Verifikation eine Aussage, die so nie beim Nutzer ankommt --
    und meldete gruen. #2051 musste dort ihre Ende-Felder aus genau diesem
    Grund nachziehen; dieser Waechter haelt fest, dass es beim naechsten Feld
    nicht wieder vergessen wird.

    Beide Seiten laufen ueber DIESELBEN Frames (Lage C)."""
    from types import SimpleNamespace

    from services.validator_render_service import _render_nowcast_replay

    uid = _uid("ac14b")
    trip = _aufbau(uid, "ac14b")
    lat, lon = trip.stages[0].waypoints[0].lat, trip.stages[0].waypoints[0].lon
    body = SimpleNamespace(
        source="radar", km_from=0.0, km_to=8.0, segment_id="1",
        frames=[
            SimpleNamespace(
                timestamp=f.timestamp.isoformat(),
                precip_mm_h=f.precip_mm_h, is_convective=f.is_convective,
            )
            for f in _laeuft_endet_im_slot()(lat, lon)
        ],
    )
    with freeze_time(_AT_LAUF):
        reset_shared_radar_cache_for_tests()
        vorschau = _render_nowcast_replay(trip, body)
    reset_shared_radar_cache_for_tests()

    assert vorschau["onset_detected"], (
        "AC-14b: die Vorschau meldet 'kein Onset', waehrend der Versandweg "
        "alarmiert -- ein laufendes Ereignis IST ein Ereignis."
    )
    vorschau_text = "\n".join(
        str(vorschau.get(k) or "") for k in ("subject", "email_plain", "telegram")
    )
    versand = _kanaltext(_lauf(uid, trip, _laeuft_endet_im_slot()))
    for aussage in (LAEUFT, f"{ENDE_WORTLAUT} {LAGE_C_ENDE_LOKAL}"):
        assert aussage in versand, (
            f"AC-14b Vorbedingung: der VERSAND muss {aussage!r} tragen.\n{versand}"
        )
        assert aussage in vorschau_text, (
            f"AC-14b: die Vorschau sagt {aussage!r} nicht -- sie zeigt damit "
            f"etwas anderes als der Versand.\n{vorschau_text}"
        )
    assert not _BEGINN_MIN.search(vorschau_text), (
        f"AC-14b: die Vorschau behauptet einen kuenftigen Beginn.\n{vorschau_text}"
    )


def test_ac15_briefing_kurzfristzeile_weist_das_ereignis_als_laufend_aus():
    """AC-15: `format_starkregen_hint` traegt heute unbedingt die Beginn-Form
    "ab ca. HH:MM (in ~N Min)"; der Laufend-Eingang muss stattdessen die
    Laufend-Aussage liefern. Der `TypeError` der noch fehlenden Signatur wird
    in den Text gefaltet, damit der Test an der ASSERTION scheitert und die
    Ursache im Fehlerbericht sichtbar bleibt."""
    from output.renderers.email.starkregen_hint import format_starkregen_hint

    with freeze_time(_AT_LAUF):
        try:
            text = format_starkregen_hint(
                "Starker Regen", None, tz=TZ_ORT,
                already_running=True, event_end_minutes=23,
            )
        except TypeError as e:
            text = f"<TypeError: {e}>"
    assert LAEUFT in text, (
        f"AC-15: die Briefing-Zeile weist das Ereignis nicht als {LAEUFT!r} "
        f"aus.\n{text}"
    )
    assert ENDE_LOKAL in text, f"AC-15: das Ende ({ENDE_LOKAL}) fehlt.\n{text}"


def test_ac15b_briefing_kette_stellt_die_laufend_zeile_wirklich_zu(monkeypatch):
    """AC-15b: dieselbe Zusicherung wie AC-15, aber an der WIRKSTELLE
    (Adversary-Fund F002).

    AC-15 ruft den Formatierer direkt auf und bewies deshalb nur, dass der
    Renderer-Zweig gebaut ist -- nicht, dass ihn je etwas erreicht. Tat es
    nicht: `_build_starkregen_hint` brach bei `onset_minutes is None` ab,
    fuehrte `already_running` nicht im Rohdaten-Tupel, und die Aufrufstelle
    im NotificationService uebergab den Parameter nie. Drei Huerden
    hintereinander, jede fuer sich ausreichend -- dieselbe Familie wie der
    stille Ausstieg im Vorschau-Weg.

    Dieser Waechter faehrt die ECHTE Kette (Scheduler -> Rohdaten-Tupel ->
    NotificationService -> Renderer) ueber den produktiven Briefing-Pfad. Der
    Nowcast kommt aus der echten Ableitung ueber die DI-Naht `frame_source`,
    nur der Netzzugriff ist ersetzt.

    Positivkontrolle zuerst: der kuenftige Beginn muss ueber DIESELBE Kette
    eine Zeile erzeugen -- sonst vergleicht der Hauptfall zwei leere
    Briefings."""
    from tests.tdd.test_starkregen_kurzfristhinweis import (
        _ReportRecorder, _active_trip, _run_briefing,
    )

    # Die ECHTE `get_nowcast`-Implementierung, nur mit gestellter Frame-
    # Quelle -- vor dem Patchen gebunden, sonst riefe sie sich selbst auf.
    _echte_get_nowcast = RadarNowcastService.get_nowcast

    def _kette(quelle):
        def _mit_frames(self, lat, lon, elevation_m=None, priority="user_briefing"):
            reset_shared_radar_cache_for_tests()
            return _echte_get_nowcast(
                RadarNowcastService(frame_source=quelle), lat, lon,
                elevation_m=elevation_m, priority=priority,
            )
        return _mit_frames

    def _briefingtext(quelle) -> str:
        monkeypatch.setattr(RadarNowcastService, "get_nowcast", _kette(quelle))
        recorder = _ReportRecorder()
        recorder.install(monkeypatch)
        _outcome, bericht = _run_briefing(
            recorder, _uid("ac15b"), _active_trip(f"trip-s2b-{uuid.uuid4().hex[:6]}"),
        )
        return bericht.email_plain

    kontrolle = _briefingtext(_quelle_jetzt(laufend=False))
    assert _BEGINN_MIN.search(kontrolle) or "ab ca." in kontrolle, (
        f"AC-15b Positivkontrolle: der kuenftige Beginn muss ueber die Kette "
        f"eine Kurzfristzeile erzeugen -- sonst prueft der Hauptfall zwei "
        f"leere Briefings.\n{kontrolle}"
    )

    laufend = _briefingtext(_quelle_jetzt(laufend=True))
    assert LAEUFT in laufend, (
        f"AC-15b: die Briefing-Kurzfristzeile erreicht den Laufend-Fall nicht "
        f"-- der Renderer-Zweig ist gebaut, aber unerreichbar.\n{laufend}"
    )
    assert not _BEGINN_MIN.search(laufend) and "ab ca." not in laufend, (
        f"AC-15b: die Zeile behauptet weiterhin einen kuenftigen Beginn.\n{laufend}"
    )
