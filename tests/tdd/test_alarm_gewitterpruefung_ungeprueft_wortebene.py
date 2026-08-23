"""TDD RED — Issue #2050 Scheibe S4b-2, Punkt 1: eine AUSGEFALLENE
Gewitterpruefung wird im Alarmtext kenntlich gemacht.

SPEC:    docs/specs/modules/feat_2050_s4b2_wortebene_kennzeichnung.md
         (AC-1 bis AC-8)
KONTEXT: docs/context/feat-2050-s4b2-wortebene-kennzeichnung.md

Der Sachverhalt ist bekannt (`NowcastResult.convective_checked`, seit #2050
S4a in Ausloeseentscheidung und Protokoll), erreicht den Text aber nicht: die
Nachricht beschriftet das Ereignis als „Regen" bzw. `R`, obwohl niemand
geprueft hat, ob es ein Gewitter war. „Geprueft, kein Gewitter" und „nicht
geprueft" sind im Text ununterscheidbar.

Wortlaut dieser Scheibe (Spec, PO-Freigabe 2026-08-23):

  * Langform (Deutsch, E-Mail/Telegram): ` · Gewitter ungeprüft`
  * Kurzform (ENGLISCH, SMS/Premium-SMS/Telegram-Kurzstil): `#` UNMITTELBAR
    hinter dem Kuerzel — `R#2.5@18:00`, `TH#@18:00`. `?` scheidet aus (durch
    die Einsetzschaerfe #2051 S3 belegt), `*` waere vor einer Zahl als
    Multiplikation lesbar. `#` ist GSM-7-BASISzeichen, kein
    Extension-Faltungsrisiko.

RED-Ursache: weder `RadarAlertRequest` noch `OnsetEvent` kennen
`convective_checked`; der Renderer bildet weder Suffix noch Marker. AC-5,
AC-8 und die Gegenproben sind heute (und nachher) GRUEN — sie sichern die
Zusagen gegen Uebersteuerung ab und tragen deshalb jeweils ihre eigene
Positivkontrolle im selben Test.

Mock-frei: jeder Kanal-Nachweis faehrt ueber die ECHTE Ausloeseentscheidung
(`TripAlertService.check_radar_alerts()` ueber die `AlarmPruefstrecke`, #2050
S1) mit einer echten `RadarNowcastService`-Unterklasse, die den Ausfall an
SEINER Bildungsstelle nachstellt (`radar_service.py:762-764`,
`_convective_checked = False` bei leerem INCA-Gewitter-Beiabruf). Kein
`Mock()`, kein `patch()` von Verhalten, kein echter Versand — Telegram und
seven.io laufen gegen die lokalen HTTP-Stubs der Pruefstrecke, E-Mail ueber
`mail_sink`.

Pfadregel #1409: alles relativ zu DIESER Datei, nie ueber einen festen
Hauptrepo-Pfad.
"""
from __future__ import annotations

import inspect
import re
import sys
import uuid
from datetime import timezone
from pathlib import Path

import pytest
from freezegun import freeze_time

ROOT = Path(__file__).resolve().parents[2]
for _p in (str(ROOT), str(ROOT / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from output.renderers.alert.model import AlertMessage, OnsetEvent  # noqa: E402
from output.renderers.alert.project import (  # noqa: E402
    to_multi_location_onset_alert_message,
)
from output.renderers.alert.render import (  # noqa: E402
    render_email, render_sms, render_subject, render_telegram,
)
from services.radar_service import NowcastResult  # noqa: E402

from tests.helpers.alarm_pruefstrecke import AlarmPruefstrecke  # noqa: E402
from tests.tdd.test_952_onset_alert_fidelity import _clean_user  # noqa: E402
from tests.tdd.test_alarm_pruefstrecke_selbstschutz import (  # noqa: E402
    _AT, _radar_trip, _settings_all_channels, _write_premium_profile,
)
from tests.tdd.test_alarm_szenario_briefing_ueberholung_zeitreihe import (  # noqa: E402
    _kurze_spitze,
)
from tests.tdd.test_radar_convective_check_failure import (  # noqa: E402
    _RadarMitGewitterpruefung,
)

# Der Wortlaut der Langform. Die Fuge ` · ` gehoert dazu — alle Langform-
# Stellen (Betreff, E-Mail-Zeile, Telegram) reihen ihre Angaben mit diesem
# Trenner (Muster `_onset_end_suffix`, `render.py:556`).
LANGFORM = " · Gewitter ungeprüft"

# Kurzform: EIN Zeichen, unmittelbar hinter dem Kuerzel. Der Ausdruck bindet
# an die Wortgrenze VOR dem Kuerzel, damit ein `#` irgendwo sonst im Text
# nicht faelschlich als Treffer durchgeht.
KURZFORM_MARKER = "#"
_MARKER_AM_KUERZEL_RE = re.compile(r"\b(TH|R)#")

# 11 mm/h ueber 10 Minuten (~1,83 mm im 60-Min-Fenster): der Beginn liegt weit
# innerhalb der Ausloeseschwelle, die Lage ist NICHT konvektiv. Dieselbe Lage
# wie in `test_radar_convective_check_failure.py` — nur ohne Briefing-Anker,
# damit der Alarm in BEIDEN Varianten (geprueft/ungeprueft) rausgeht und die
# Texte vergleichbar sind.
_LAGE_RATE_MM_H = 11.0

# Ortsvergleich (AC-6): gestellte Uhr, weil der Buendel-Konstruktor
# `onset_time` aus `datetime.now()` ableitet.
_UHR = "2026-08-23T12:00:00+00:00"


def _uid(tag: str) -> str:
    return f"tdd-2050-s4b2-p1-{tag}-{uuid.uuid4().hex[:6]}"


def _pruefstrecken_lauf(*, gewitterpruefung_lief: bool):
    """EIN echter Radar-Alarmlauf ueber alle vier Kanaele.

    Kein Briefing-Anker: die Briefing-Unterdrueckung soll hier gar nicht erst
    mitspielen — sonst unterschieden sich die beiden Varianten nicht nur im
    Wortlaut, sondern schon darin, OB ein Alarm rausging (dann pruefte der
    Wortlaut-Vergleich nichts).
    """
    uid = _uid("lauf")
    _clean_user(uid)
    # Premium-Profil VOR der Pruefstrecke: deren Konstruktor liest es ueber
    # `with_user_profile()` ein (`alarm_pruefstrecke.py:131`) — danach
    # geschrieben, bliebe der vierte Kanal strukturell unerreichbar.
    _write_premium_profile(uid, _AT)
    trip = _radar_trip(
        uid, f"trip-2050-s4b2-{uuid.uuid4().hex[:6]}",
        send_email=True, send_telegram=True, send_sms=True,
        send_premium_sms=True,
    )
    strecke = AlarmPruefstrecke(user_id=uid, settings=_settings_all_channels())
    lauf = strecke.lauf(
        at=_AT, zweig="radar", trip=trip,
        radar_service=_RadarMitGewitterpruefung(
            _kurze_spitze(_LAGE_RATE_MM_H),
            gewitterpruefung_lief=gewitterpruefung_lief,
        ),
    )
    assert lauf.triggered_count == 1, (
        f"Testvoraussetzung: der Lauf muss GENAU EINEN Alarm ausloesen — sonst "
        f"prueft der Wortlaut nichts (war {lauf.triggered_count})."
    )
    assert lauf.mail and lauf.telegram and lauf.sms and lauf.premium_sms, (
        f"Testvoraussetzung: alle vier Kanaele muessen Inhalt tragen: "
        f"mail={lauf.mail!r} telegram={lauf.telegram!r} sms={lauf.sms!r} "
        f"premium_sms={lauf.premium_sms!r}"
    )
    return uid, lauf


@pytest.fixture(scope="module")
def laeufe():
    """Beide Varianten EINMAL je Testlauf — der Pruefstrecken-Lauf ist teuer
    (echte Trip-Ablage, zwei HTTP-Stubs, echte Ausloeseentscheidung), die
    gelieferten Kanaltexte sind danach nur noch gelesen."""
    ergebnisse = {}
    uids = []
    for gepruef in (False, True):
        uid, lauf = _pruefstrecken_lauf(gewitterpruefung_lief=gepruef)
        uids.append(uid)
        ergebnisse[gepruef] = lauf
    yield ergebnisse
    for uid in uids:
        _clean_user(uid)


def _mailtext(lauf) -> str:
    return "\n".join(f"{betreff}\n{koerper}" for betreff, koerper in lauf.mail)


def _onset_event(**overrides) -> OnsetEvent:
    fields = dict(
        onset_minutes=30, onset_time="18:00", km_from=8.0, km_to=8.0,
        is_convective=False, intensity_label="Mäßiger Regen",
        source_label="Radar (DWD)", segment_id="Ziel", onset_precip_mm=2.5,
    )
    fields.update(overrides)
    return OnsetEvent(**fields)


def _onset_msg(*events: OnsetEvent) -> AlertMessage:
    return AlertMessage(
        trip_short="KHW 403", stand_at="17:30", events=tuple(events),
        source="Radar (DWD)",
    )


def test_prueling_stammt_aus_diesem_arbeitsbaum():
    """Vorbedingung (kein AC): Renderer, Ortsvergleich-Projektion und
    Vorschau-Dienst werden RELATIV ZU DIESER Testdatei aufgeloest — sonst
    pruefte ein Worktree-Lauf still die Dateien des Hauptrepos und lieferte
    falsches Gruen."""
    from output.renderers.alert import project as project_modul
    from output.renderers.alert import render as render_modul
    from services import validator_render_service as vorschau_modul

    arbeitsbaum = Path(__file__).resolve().parents[2]
    for modul in (render_modul, project_modul, vorschau_modul):
        pfad = Path(inspect.getfile(modul)).resolve()
        assert pfad.is_relative_to(arbeitsbaum), (
            f"Prueling stammt nicht aus diesem Arbeitsbaum: {pfad}"
        )


# ---------------------------------------------------------------------------
# AC-1 bis AC-4 — die vier Kanaele des Trip-Versands
# ---------------------------------------------------------------------------


def test_ac1_email_langform_nennt_die_ausgefallene_gewitterpruefung(laeufe):
    """AC-1 GIVEN ein Radar-Onset-Alarm, dessen Gewitterpruefung ausgefallen
    ist (`convective_checked=False`), wird per E-Mail versendet
    WHEN der Trip-Nutzer das Briefing liest
    THEN steht in der Langform-Darstellung des Ereignisses der Zusatz
    ` · Gewitter ungeprüft`.

    Gemessen am TATSAECHLICH zugestellten Mailtext der Pruefstrecke (Betreff +
    Koerper), nicht an einer Renderer-Hilfsfunktion.

    RED heute: der Marker reist gar nicht bis zum Renderer."""
    text = _mailtext(laeufe[False])
    assert LANGFORM in text, (
        f"RED/AC-1: die E-Mail muss {LANGFORM!r} tragen — sonst kann der Leser "
        f"„geprüft, kein Gewitter\" nicht von „nicht geprüft\" "
        f"unterscheiden.\n{text}"
    )


def test_ac2_telegram_langform_nennt_die_ausgefallene_gewitterpruefung(laeufe):
    """AC-2 GIVEN denselben Alarm per Telegram
    WHEN der Trip-Nutzer die Nachricht liest
    THEN traegt auch die Telegram-Langform den Zusatz ` · Gewitter ungeprüft`
    — kein Kanal ist gegenueber der E-Mail nachrangig (PO-Vorgabe: auf dem
    Pass ist Telegram der gelesene Kanal).

    RED heute: derselbe fehlende Draht wie AC-1."""
    text = "\n".join(laeufe[False].telegram)
    assert LANGFORM in text, (
        f"RED/AC-2: die Telegram-Nachricht muss {LANGFORM!r} tragen.\n{text}"
    )


def test_ac3_sms_traegt_das_zeichen_unmittelbar_hinter_dem_kuerzel(laeufe):
    """AC-3 GIVEN denselben Alarm per SMS
    WHEN der Trip-Nutzer die Kurznachricht liest
    THEN steht UNMITTELBAR hinter dem Kuerzel (`R` bzw. `TH`) das Zeichen `#`
    (`R#2.5@18:00`) — genau EINMAL im Text.

    Geprueft wird die POSITION, nicht nur die Anwesenheit: ein `#` irgendwo im
    Text (etwa am Ende angehaengt) waere im knappsten Kanal nicht dem
    Sachverhalt zuzuordnen, den es qualifiziert.

    RED heute: der Kurzform-Marker existiert nicht."""
    sms = "\n".join(laeufe[False].sms)
    assert _MARKER_AM_KUERZEL_RE.search(sms), (
        f"RED/AC-3: das Zeichen {KURZFORM_MARKER!r} muss unmittelbar hinter "
        f"dem Kuerzel (`R`/`TH`) stehen: {sms!r}"
    )
    assert sms.count(KURZFORM_MARKER) == 1, (
        f"AC-3: genau EIN Kennzeichen erwartet, gezaehlt "
        f"{sms.count(KURZFORM_MARKER)}: {sms!r}"
    )
    assert sms.isascii(), f"AC-3: Kurznachricht ist nicht ASCII-rein: {sms!r}"


def test_ac4_premium_sms_traegt_denselben_marker_wie_die_sms(laeufe):
    """AC-4 GIVEN denselben Alarm per Premium-SMS (Garmin inReach)
    WHEN der Trip-Nutzer sie liest
    THEN traegt sie denselben `#`-Marker wie die regulaere SMS.

    Warum eigens geprueft und nicht „ist ja derselbe `sms_body`": auf der
    Huette am Karnischen Hoehenweg kommt NUR dieser Kanal an; es gibt dort
    keinen zweiten, der den Sachverhalt nachreicht. Gemessen wird am
    Absenderfeld getrennt (`PREMIUM_SMS_SENDER`, `alarm_pruefstrecke.py:185`)
    — also an dem, was der Transport tatsaechlich fuer diesen Kanal absetzt.

    RED heute: wie AC-3."""
    lauf = laeufe[False]
    premium = "\n".join(lauf.premium_sms)
    sms = "\n".join(lauf.sms)
    assert _MARKER_AM_KUERZEL_RE.search(premium), (
        f"RED/AC-4: die Premium-SMS muss {KURZFORM_MARKER!r} unmittelbar "
        f"hinter dem Kuerzel tragen: {premium!r}"
    )
    assert premium == sms, (
        f"AC-4: Premium-SMS und SMS muessen denselben Text tragen — "
        f"premium={premium!r}, sms={sms!r}"
    )


# ---------------------------------------------------------------------------
# AC-5 — Gegenprobe: durchgefuehrte Pruefung ohne Gewitter bleibt stumm
# ---------------------------------------------------------------------------


def test_ac5_durchgefuehrte_pruefung_ohne_gewitter_traegt_keine_kennzeichnung(laeufe):
    """AC-5 (GEGENPROBE, sichert AC-1..AC-4 gegen Uebersteuerung) GIVEN die
    Gewitterpruefung wurde DURCHGEFUEHRT und ergab kein Gewitter
    (`convective_checked=True, is_convective=False`)
    WHEN derselbe Alarm ueber alle vier Kanaele gerendert wird
    THEN erscheint WEDER der Langform-Zusatz NOCH der `#`-Marker.

    Die Positivkontrolle steht im SELBEN Test: derselbe Aufbau mit
    ausgefallener Pruefung MUSS die Kennzeichnung tragen. Ohne sie waere diese
    Abwesenheit trivial wahr — sie bestuende auch dann, wenn die Kennzeichnung
    ueberhaupt nie gebaut wird.

    Beide Laeufe unterscheiden sich in GENAU EINEM Bit
    (`gewitterpruefung_lief`); alles andere ist identisch."""
    geprueft, ungeprueft = laeufe[True], laeufe[False]

    kanaele_geprueft = {
        "mail": _mailtext(geprueft),
        "telegram": "\n".join(geprueft.telegram),
        "sms": "\n".join(geprueft.sms),
        "premium_sms": "\n".join(geprueft.premium_sms),
    }
    kanaele_ungeprueft = {
        "mail": _mailtext(ungeprueft),
        "telegram": "\n".join(ungeprueft.telegram),
        "sms": "\n".join(ungeprueft.sms),
        "premium_sms": "\n".join(ungeprueft.premium_sms),
    }

    for name, text in kanaele_geprueft.items():
        assert LANGFORM not in text, (
            f"AC-5: eine DURCHGEFUEHRTE Pruefung ohne Gewitter darf im Kanal "
            f"{name} keinen Ungeprueft-Zusatz tragen.\n{text}"
        )
        assert not _MARKER_AM_KUERZEL_RE.search(text), (
            f"AC-5: im Kanal {name} darf kein `#` am Kuerzel stehen.\n{text}"
        )

    # Positivkontrolle — ohne sie belegt die Abwesenheit oben nichts.
    assert LANGFORM in kanaele_ungeprueft["mail"], (
        f"Positivkontrolle/AC-5: derselbe Aufbau mit AUSGEFALLENER Pruefung "
        f"muss den Langform-Zusatz tragen — sonst prueft die Abwesenheit oben "
        f"nur ein nicht existierendes Merkmal.\n{kanaele_ungeprueft['mail']}"
    )
    assert _MARKER_AM_KUERZEL_RE.search(kanaele_ungeprueft["sms"]), (
        f"Positivkontrolle/AC-5: derselbe Aufbau mit AUSGEFALLENER Pruefung "
        f"muss den `#`-Marker tragen: {kanaele_ungeprueft['sms']!r}"
    )


# ---------------------------------------------------------------------------
# AC-6 — Ortsvergleich: eigene Konstruktionsstelle (`project.py`)
# ---------------------------------------------------------------------------


def test_ac6_ortsvergleich_traegt_dieselbe_kennzeichnung():
    """AC-6 GIVEN derselbe Sachverhalt (`convective_checked=False`) tritt an
    einem Ortsvergleichs-Preset auf statt an einem Trip
    WHEN der Ortsvergleich-Alarm gerendert wird
    THEN traegt er dieselbe Kennzeichnung wie der Trip-Alarm.

    Warum eigens geprueft: der Ortsvergleich baut sein `OnsetEvent` an einer
    ANDEREN Stelle (`project.to_multi_location_onset_alert_message`), ohne den
    Umweg ueber `RadarAlertRequest`. Wird nur der Trip-Pfad verdrahtet, ist der
    Ortsvergleich still leiser als der Trip — genau die Fehlerklasse, die der
    Adversary bei #2046 (F001) fand.

    Gegenprobe im selben Test: derselbe Aufbau mit DURCHGEFUEHRTER Pruefung
    bleibt stumm.

    RED heute: `NowcastResult.convective_checked` erreicht das `OnsetEvent`
    dieses Pfades nicht."""
    def _nachricht(*, geprueft: bool):
        nc = NowcastResult(
            onset_minutes=30, intensity_label="Mäßiger Regen", source="radar",
            is_convective=False, onset_precip_mm=2.5,
            convective_checked=geprueft,
        )
        assert nc.convective_checked is geprueft, (
            f"Testvoraussetzung: `NowcastResult.convective_checked` muss "
            f"{geprueft!r} tragen, war {nc.convective_checked!r}"
        )
        return to_multi_location_onset_alert_message(
            [("Zermatt", nc)], tz=timezone.utc, stand_at="10:00",
        )

    with freeze_time(_UHR):
        _html, plain_aus = render_email(_nachricht(geprueft=False))
        sms_aus = render_sms(_nachricht(geprueft=False))
        _html2, plain_an = render_email(_nachricht(geprueft=True))
        sms_an = render_sms(_nachricht(geprueft=True))

    assert LANGFORM in plain_aus, (
        f"RED/AC-6: der Ortsvergleich-Alarm muss {LANGFORM!r} tragen — sonst "
        f"meldet er einen Sachverhalt nicht, den das System kennt.\n{plain_aus}"
    )
    assert _MARKER_AM_KUERZEL_RE.search(sms_aus), (
        f"RED/AC-6: die Ortsvergleich-Kurzform muss `#` unmittelbar hinter dem "
        f"Kuerzel tragen: {sms_aus!r}"
    )
    # Gegenprobe: mit durchgefuehrter Pruefung bleibt beides stumm.
    assert LANGFORM not in plain_an, (
        f"AC-6 (Gegenprobe): eine durchgefuehrte Pruefung darf im "
        f"Ortsvergleich keinen Zusatz erzeugen.\n{plain_an}"
    )
    assert not _MARKER_AM_KUERZEL_RE.search(sms_an), (
        f"AC-6 (Gegenprobe): kein `#` bei durchgefuehrter Pruefung: {sms_an!r}"
    )


# ---------------------------------------------------------------------------
# AC-7 — Vorschau/Validator: BEIDE Unterpfade
# ---------------------------------------------------------------------------


def test_ac7_vorschau_payload_zeigt_dieselbe_kennzeichnung():
    """AC-7 (Unterpfad Live-Preview / API-Payload) GIVEN einen
    `AlertPreviewBody` mit `convective_checked=False`
    WHEN `render_alert_preview(trip, body)` laeuft
    THEN tragen Betreff, E-Mail-Klartext und Telegram den Langform-Zusatz und
    die Kurzform den `#`-Marker — die Vorschau zeigt, was der Versand sendet.

    Die Vorbedingung prueft zuerst das PAYLOAD-SCHEMA selbst: pydantic
    verwirft unbekannte Schluessel STILL (Muster #2046 Finding F002). Ohne
    `OnsetPayload.convective_checked` waere der Rest des Tests eine Aussage
    ueber einen Payload, der den Sachverhalt gar nicht enthaelt — und die
    Vorschau bliebe dauerhaft leiser als der Versand.

    Gegenprobe im selben Test: ohne das Feld (Alt-Client) erscheint nichts.

    RED heute: `OnsetPayload` kennt das Feld nicht (`AttributeError` an der
    Vorbedingung)."""
    from api.routers.validator import AlertPreviewBody
    from app.trip import Trip
    from services.validator_render_service import render_alert_preview

    basis = {
        "onset_minutes": 25, "onset_time": "15:00", "km_from": 0.0,
        "km_to": 6.0, "is_convective": False,
        "intensity_label": "Mäßiger Regen", "source_label": "Radar (DWD)",
        "segment_id": "Ziel", "onset_precip_mm": 2.5,
    }
    trip = Trip(id="trip-2050-s4b2", name="Vorschau-Trip", stages=[])

    body = AlertPreviewBody(onset={**basis, "convective_checked": False})
    assert body.onset.convective_checked is False, (
        "Vorbedingung/AC-7: `OnsetPayload` muss `convective_checked` fuehren "
        "— pydantic verwirft ein unbekanntes Feld sonst STILL, und die "
        "Vorschau saehe den Sachverhalt nie."
    )

    with freeze_time(_UHR):
        aus = render_alert_preview(trip, body)
        alt = render_alert_preview(trip, AlertPreviewBody(onset=dict(basis)))

    for feld in ("subject", "email_plain", "telegram"):
        assert LANGFORM in (aus[feld] or ""), (
            f"RED/AC-7: das Vorschau-Feld {feld!r} traegt {LANGFORM!r} nicht: "
            f"{aus[feld]!r}"
        )
    assert _MARKER_AM_KUERZEL_RE.search(aus["sms"] or ""), (
        f"RED/AC-7: die Vorschau-Kurzform traegt den `#`-Marker nicht: "
        f"{aus['sms']!r}"
    )
    # Gegenprobe (Alt-Client ohne das Feld): unveraendert stumm.
    for feld in ("subject", "email_plain", "telegram", "sms"):
        assert LANGFORM not in (alt[feld] or ""), (
            f"AC-7 (Gegenprobe): ohne das Feld darf {feld!r} keinen Zusatz "
            f"tragen: {alt[feld]!r}"
        )
    assert not _MARKER_AM_KUERZEL_RE.search(alt["sms"] or ""), (
        f"AC-7 (Gegenprobe): ohne das Feld kein `#`: {alt['sms']!r}"
    )


def test_ac7_vorschau_replay_zeigt_dieselbe_kennzeichnung(monkeypatch):
    """AC-7 (Unterpfad Payload-Replay) GIVEN einen Frame-Mitschnitt, der ueber
    `_render_nowcast_replay` abgespielt wird, waehrend der Gewitter-Beiabruf
    ausgefallen ist
    WHEN die Vorschau gerendert wird
    THEN traegt sie dieselbe Kennzeichnung wie der echte Versand.

    Warum eigens geprueft: der Replay-Zweig baut seinen Onset-Namespace SELBST
    (`validator_render_service.py:297-335`) und reicht ihn an dieselbe
    `render_alert_preview` weiter. Wird dort `convective_checked` vergessen,
    ist genau der Weg stumm, mit dem beim Ausrollen geprueft wird — die
    Verifikation meldete gruen fuer etwas, das so nie beim Nutzer ankommt.

    Der Ausfall wird an SEINER Bildungsstelle nachgestellt (echte
    `RadarNowcastService`-Unterklasse, `_convective_checked = False` wie bei
    leerem INCA-Beiabruf); die Ergebnis-Ableitung `_derive_result` bleibt die
    echte. Umgebogen wird die Klasse im Herkunftsmodul, weil der Replay-Zweig
    sie erst zur Laufzeit importiert.

    Gegenprobe im selben Test: derselbe Mitschnitt mit DURCHGEFUEHRTER
    Pruefung bleibt stumm.

    RED heute: der Namespace traegt das Feld nicht."""
    from types import SimpleNamespace

    from app.trip import Trip
    from services import radar_service as radar_service_mod
    from services.validator_render_service import _render_nowcast_replay

    class _OhneGewitterpruefung(radar_service_mod.RadarNowcastService):
        """Echter Dienst, echte Ableitung — nachgestellt wird ausschliesslich
        der ausgefallene Gewitter-Beiabruf (`radar_service.py:762-764`)."""

        def __init__(self, *a, **kw) -> None:
            super().__init__(*a, **kw)
            self._convective_checked = False

    def _mitschnitt():
        from datetime import datetime, timedelta

        jetzt = datetime.now(timezone.utc).replace(microsecond=0)
        return SimpleNamespace(
            source="radar", km_from=0.0, km_to=6.0, segment_id="Ziel",
            frames=[
                SimpleNamespace(
                    timestamp=(jetzt + timedelta(minutes=m)).isoformat(),
                    precip_mm_h=(3.0 if 15 <= m <= 45 else 0.0),
                    is_convective=False,
                )
                for m in range(0, 91, 15)
            ],
        )

    trip = Trip(id="trip-2050-s4b2-replay", name="Replay-Trip", stages=[])

    with freeze_time(_UHR):
        an = _render_nowcast_replay(trip, _mitschnitt())
        monkeypatch.setattr(
            radar_service_mod, "RadarNowcastService", _OhneGewitterpruefung,
        )
        aus = _render_nowcast_replay(trip, _mitschnitt())

    assert an.get("onset_detected") and aus.get("onset_detected"), (
        f"Testvoraussetzung: beide Replay-Laeufe muessen einen Onset erkennen "
        f"— sonst sind alle Kanalfelder `None`. an={an!r}\naus={aus!r}"
    )
    for feld in ("subject", "email_plain", "telegram"):
        assert LANGFORM in (aus[feld] or ""), (
            f"RED/AC-7 (Replay): das Feld {feld!r} traegt {LANGFORM!r} nicht: "
            f"{aus[feld]!r}"
        )
    assert _MARKER_AM_KUERZEL_RE.search(aus["sms"] or ""), (
        f"RED/AC-7 (Replay): die Kurzform traegt den `#`-Marker nicht: "
        f"{aus['sms']!r}"
    )
    # Gegenprobe: mit durchgefuehrter Pruefung bleibt derselbe Mitschnitt stumm.
    for feld in ("subject", "email_plain", "telegram", "sms"):
        assert LANGFORM not in (an[feld] or ""), (
            f"AC-7 (Replay, Gegenprobe): {feld!r} darf ohne Ausfall keinen "
            f"Zusatz tragen: {an[feld]!r}"
        )


# ---------------------------------------------------------------------------
# AC-8 — Bestandslage: ungesetztes Feld gilt als GEPRUEFT
# ---------------------------------------------------------------------------


def test_ac8_ungesetztes_feld_gilt_als_geprueft_und_bleibt_stumm():
    """AC-8 GIVEN ein `OnsetEvent`, bei dem `convective_checked` gar nicht
    gesetzt wurde (Bestandscode, Altdaten)
    WHEN es gerendert wird
    THEN gilt es als GEPRUEFT und traegt KEINEN Hinweis — in Betreff, E-Mail,
    Telegram und Kurzform.

    Ein `False`-Default wuerde jede Bestands-Fixture, die das Feld nicht setzt,
    ploetzlich „ungeprueft" behaupten: eine Regression auf breiter Front.

    Zwei Kontrollen im selben Test:
      * BYTE-Gleichheit zwischen „Feld gar nicht uebergeben" und „Feld
        ausdruecklich `True`" — der Default darf nicht bloss zufaellig
        dasselbe ergeben;
      * Positivkontrolle mit `False` — sonst waere die Stille oben der Beweis
        eines ueberhaupt nicht existierenden Merkmals.

    RED heute: die Konstruktion mit `convective_checked=` scheitert am
    `TypeError` — `OnsetEvent` kennt das Feld nicht."""
    ohne = _onset_msg(_onset_event())
    explizit_wahr = _onset_msg(_onset_event(convective_checked=True))
    ausgefallen = _onset_msg(_onset_event(convective_checked=False))

    kanaele = {
        "subject": render_subject,
        "email_plain": lambda m: render_email(m)[1],
        "telegram": render_telegram,
        "sms": render_sms,
    }
    for name, rendern in kanaele.items():
        text_ohne = rendern(ohne)
        assert LANGFORM not in text_ohne and KURZFORM_MARKER not in text_ohne, (
            f"AC-8: ohne gesetztes Feld darf {name} keinen Hinweis tragen: "
            f"{text_ohne!r}"
        )
        assert text_ohne == rendern(explizit_wahr), (
            f"AC-8: {name} muss fuer „Feld nicht uebergeben\" und "
            f"„ausdruecklich geprüft\" BYTE-identisch sein.\n"
            f"  ohne    = {text_ohne!r}\n"
            f"  True    = {rendern(explizit_wahr)!r}"
        )

    # Positivkontrolle: derselbe Aufbau MIT dem Ausfall traegt die
    # Kennzeichnung — sonst belegt die Stille oben nichts.
    assert LANGFORM in render_email(ausgefallen)[1], (
        f"Positivkontrolle/AC-8: mit `convective_checked=False` MUSS der "
        f"Zusatz erscheinen: {render_email(ausgefallen)[1]!r}"
    )
    assert _MARKER_AM_KUERZEL_RE.search(render_sms(ausgefallen)), (
        f"Positivkontrolle/AC-8: mit `convective_checked=False` MUSS der "
        f"`#`-Marker erscheinen: {render_sms(ausgefallen)!r}"
    )
