"""TDD RED — Issue #2050 Scheibe S4b-2, Punkt 2: eine MESSLUECKE in der
Radar-Ausdehnung wird im Alarmtext kenntlich gemacht.

SPEC:    docs/specs/modules/feat_2050_s4b2_wortebene_kennzeichnung.md
         (AC-9 bis AC-16)
KONTEXT: docs/context/feat-2050-s4b2-wortebene-kennzeichnung.md

`measurement_gaps` steht seit #2050 S4b im Alarmprotokoll, erreicht den
Renderer aber nicht. Faellt ein Messpunkt aus, ist die genannte Ausdehnung
tendenziell ZU KLEIN (nass, nass, LUECKE, trocken -> der Text behauptet
implizit Trockenheit hinter der Luecke, wo nichts gemessen wurde). Der Text
verschweigt heute, dass ein Teil der Strecke gar nicht gemessen wurde.

Wortlaut dieser Scheibe (Spec, PO-Freigabe 2026-08-23):

  * Langform (Deutsch, E-Mail/Telegram): ` · Ausdehnung unvollständig gemessen`
  * Kurzform (ENGLISCH, SMS/Premium-SMS): `>` UNMITTELBAR hinter der
    Zonen-Liste — `km2-4,9-11>`. `>` traegt im Alarm-Vokabular bereits die
    Bedeutung „Untergrenze" (`>@20:00`, #2051 S1) — hier dieselbe Bedeutung
    („reicht mindestens so weit"), auf die Strecke statt auf die Zeit
    angewandt. GSM-7-BASISzeichen, kein Extension-Faltungsrisiko.

RED-Ursache: `gap_km` existiert weder auf `RadarAlertRequest` noch auf
`OnsetEvent`; der Renderer bildet weder Suffix noch Marker.

🔴 Die Budget-Falle (Kontextdokument, Risiko 1): `render.py:1054` endet mit
`return body if len(body) <= limit else body[:limit]`. Eine Assertion
`len(sms) <= 140` bewacht deshalb NICHTS — sie bleibt auch dann gruen, wenn
der Marker unbedingt angehaengt und danach vom harten Schnitt gefressen wird.
AC-16 misst deshalb die ANWESENHEIT des Markers im Randfall und die
VOLLSTAENDIGKEIT der Zonen daneben (s. Docstring dort).

Mock-frei: die Kanal-Nachweise (AC-9..AC-13) fahren ueber die ECHTE
Ausloeseentscheidung (`TripAlertService.check_radar_alerts()` ueber die
`AlarmPruefstrecke`, #2050 S1) mit der echten `RadarNowcastService`-
Unterklasse `_LueckenRadar` (#2050 S4b) am DI-Seam — echte
`NowcastResult`-Objekte, gesteuert wird nur, WELCHER Punkt ein Ergebnis
bekommt. Die Grenzfaelle (AC-14..AC-16) laufen gegen die echten Renderer mit
echten `OnsetEvent`/`AlertMessage`-Objekten. Kein `Mock()`, kein `patch()`
von Verhalten, kein echter Versand.

Pfadregel #1409: alles relativ zu DIESER Datei, nie ueber einen festen
Hauptrepo-Pfad.
"""
from __future__ import annotations

import inspect
import json
import re
import sys
import uuid
from datetime import datetime
from pathlib import Path

import pytest
from freezegun import freeze_time

ROOT = Path(__file__).resolve().parents[2]
for _p in (str(ROOT), str(ROOT / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from app.loader import get_briefings_dir, load_trip  # noqa: E402
from output.renderers.alert.model import AlertMessage, OnsetEvent  # noqa: E402
from output.renderers.alert.render import (  # noqa: E402
    render_email, render_sms, render_subject, render_telegram,
)
from services.rain_extent import RainZone  # noqa: E402
from utils.geo import haversine_km  # noqa: E402

from tests.helpers.alarm_pruefstrecke import AlarmPruefstrecke  # noqa: E402
from tests.helpers.arrival_window_fixtures import stage_date  # noqa: E402
from tests.tdd.test_952_onset_alert_fidelity import _clean_user  # noqa: E402
from tests.tdd.test_alarm_pruefstrecke_selbstschutz import (  # noqa: E402
    _settings_all_channels, _write_premium_profile,
)
from tests.tdd.test_radar_messluecken_protokoll import _LueckenRadar  # noqa: E402
from tests.tdd.test_regen_ausdehnung_textstellen import (  # noqa: E402
    _UHR_TIROL, _ZONEN_LAT0, _ZONEN_LAT1, _ZONEN_LON0, _ZONEN_LON1,
)

_UHR = datetime.fromisoformat(_UHR_TIROL)

# Wortlaut der Langform (Fuge ` · ` gehoert dazu, Muster `_onset_end_suffix`).
LANGFORM = " · Ausdehnung unvollständig gemessen"

# Kurzform: `>` unmittelbar hinter der Zonen-Liste. Der Ausdruck bindet an die
# Liste — ein `>` an anderer Stelle (die Untergrenzen-Ende-Form ` >@HH:MM` aus
# #2051 S1 traegt eines!) darf NICHT als Treffer durchgehen.
_MARKER_NACH_ZONEN_RE = re.compile(r"km[\d,\-]+>")

# Die Zonen-Liste selbst (ohne Marker) — fuer die Testvoraussetzung „es wird
# ueberhaupt eine Ausdehnung gezeigt".
_ZONEN_LISTE_RE = re.compile(r"km[\d,\-]+")

_ZONE = RainZone(km_from=8.0, km_to=12.0, onset_minutes=20, event_end_minutes=40)

_UNSET = object()  # Sentinel: `gap_km` gar nicht erst uebergeben.


def _uid(tag: str) -> str:
    return f"tdd-2050-s4b2-p2-{tag}-{uuid.uuid4().hex[:6]}"


# ---------------------------------------------------------------------------
# Vier-Kanal-Lauf ueber die echte Ausloeseentscheidung
# ---------------------------------------------------------------------------


def _vier_kanal_lauf(radar: _LueckenRadar, tag: str):
    """Ein echter `check_radar_alerts()`-Lauf auf der Zonen-Etappe (Nord-
    Strecke aus #2051 S2a, ~24 km -> sechs Messpunkte), mit Abgriff ALLER VIER
    Kanaele ueber die `AlarmPruefstrecke`.

    Der Trip wird als Datei geschrieben und vom Pruefling selbst geladen —
    dieselbe Strecke wie in Produktion. `distance_from_start_km` ist auf
    beiden Wegpunkten gesetzt, damit die Etappe als VERMESSEN gilt: ohne das
    zeigt der Text ueberhaupt keine Ausdehnung (`km_measured`, #2051 S2a AC-8)
    und Punkt 2 haette keinen Bezugspunkt.
    """
    uid = _uid(tag)
    _clean_user(uid)
    # Premium-Profil VOR der Pruefstrecke: deren Konstruktor liest es ueber
    # `with_user_profile()` ein — danach geschrieben, bliebe der vierte Kanal
    # strukturell unerreichbar (`alarm_pruefstrecke.py:131`).
    _write_premium_profile(uid, _UHR)
    with freeze_time(_UHR):
        luftlinie = haversine_km(
            _ZONEN_LAT0, _ZONEN_LON0, _ZONEN_LAT1, _ZONEN_LON1,
        )
        trip_id = f"tdd-2050-s4b2-trip-{uuid.uuid4().hex[:6]}"
        trips_dir = get_briefings_dir(uid)
        trips_dir.mkdir(parents=True, exist_ok=True)
        pfad = trips_dir / f"{trip_id}.json"
        pfad.write_text(json.dumps({
            "id": trip_id, "name": "Messluecken Wortebene Trip",
            "stages": [{
                "id": "S1", "name": "Tag 1",
                "date": stage_date(_ZONEN_LAT0, _ZONEN_LON0).isoformat(),
                "waypoints": [
                    {
                        "id": "WP0", "name": "WP0",
                        "lat": _ZONEN_LAT0, "lon": _ZONEN_LON0,
                        "elevation_m": 1000.0, "arrival_calculated": "11:00",
                        "distance_from_start_km": 0.0,
                    },
                    {
                        "id": "WP1", "name": "WP1",
                        "lat": _ZONEN_LAT1, "lon": _ZONEN_LON1,
                        "elevation_m": 1000.0, "arrival_calculated": "17:00",
                        "distance_from_start_km": round(luftlinie, 3),
                    },
                ],
            }],
            "report_config": {
                "trip_id": trip_id, "send_email": True, "send_telegram": True,
                "send_sms": True, "send_premium_sms": True,
                "alert_on_changes": True,
            },
        }))
        trip = load_trip(pfad)

    strecke = AlarmPruefstrecke(user_id=uid, settings=_settings_all_channels())
    lauf = strecke.lauf(
        at=_UHR, zweig="radar", trip=trip, radar_service=radar,
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


def _mailtext(lauf) -> str:
    return "\n".join(f"{betreff}\n{koerper}" for betreff, koerper in lauf.mail)


def _kanaele(lauf) -> dict[str, str]:
    return {
        "mail": _mailtext(lauf),
        "telegram": "\n".join(lauf.telegram),
        "sms": "\n".join(lauf.sms),
        "premium_sms": "\n".join(lauf.premium_sms),
    }


def _pruefe_ausdehnung_wird_gezeigt(lauf, wer: str) -> None:
    """Testvoraussetzung fuer JEDEN Kanal-Nachweis: der Lauf muss ueberhaupt
    eine Ausdehnung zeigen. Ohne sie haette der Hinweis auf eine unvollstaendig
    gemessene Ausdehnung keinen Bezugspunkt (AC-15) und der Test pruefte eine
    Lage, die es nicht gibt."""
    kanaele = _kanaele(lauf)
    assert "· Nass km" in kanaele["mail"], (
        f"Testvoraussetzung ({wer}): die E-Mail muss eine Ausdehnungsangabe "
        f"(`· Nass km …`) tragen.\n{kanaele['mail']}"
    )
    assert _ZONEN_LISTE_RE.search(kanaele["sms"]), (
        f"Testvoraussetzung ({wer}): die Kurzform muss eine Zonen-Liste "
        f"tragen: {kanaele['sms']!r}"
    )


@pytest.fixture(scope="module")
def laeufe():
    """Zwei Laeufe auf DERSELBEN Strecke, unterschieden in GENAU EINEM Punkt:
    einmal faellt der dritte Messpunkt aus, einmal liefern alle sechs ein
    Ergebnis. Beide Laeufe zeigen dieselbe Art Ausdehnungsangabe — genau
    darum muss der Unterschied am Text haengen.

    Einmalig je Testlauf: der Pruefstrecken-Lauf ist teuer (Trip-Ablage, zwei
    HTTP-Stubs, echte Ausloeseentscheidung); die Kanaltexte werden danach nur
    gelesen.
    """
    uids: list[str] = []
    ergebnisse = {}
    for name, radar in (
        ("mit_luecke", _LueckenRadar(luecken={2: {"data_unavailable": True}})),
        ("ohne_luecke", _LueckenRadar()),
    ):
        uid, lauf = _vier_kanal_lauf(radar, name)
        uids.append(uid)
        ergebnisse[name] = lauf
    yield ergebnisse
    for uid in uids:
        _clean_user(uid)


# ---------------------------------------------------------------------------
# Renderer-Bausteine fuer die Grenzfaelle (AC-14..AC-16)
# ---------------------------------------------------------------------------


def _onset_event(*, gap_km: object = _UNSET, **overrides) -> OnsetEvent:
    """`gap_km` wird NUR uebergeben, wenn ein Aufrufer es ausdruecklich setzt
    (Muster `test_onset_kurzform_menge.py`): so bleibt die Bestandsfassung
    ohne das Feld unabhaengig vom Modell-Erweiterungsstand pruefbar."""
    fields = dict(
        onset_minutes=30, onset_time="18:00", km_from=0.0, km_to=13.0,
        is_convective=False, intensity_label="Mäßiger Regen",
        source_label="Radar (DWD)", segment_id="Ziel", onset_precip_mm=2.5,
        km_measured=True, rain_zones=(_ZONE,),
    )
    fields.update(overrides)
    if gap_km is not _UNSET:
        fields["gap_km"] = gap_km
    return OnsetEvent(**fields)


def _onset_msg(*events: OnsetEvent) -> AlertMessage:
    return AlertMessage(
        trip_short="KHW 403", stand_at="17:30", events=tuple(events),
        source="Radar (DWD)",
    )


_RENDERER = {
    "subject": render_subject,
    "email_plain": lambda m: render_email(m)[1],
    "telegram": render_telegram,
    "sms": render_sms,
}


def _traegt_hinweis(text: str) -> bool:
    return LANGFORM in text or bool(_MARKER_NACH_ZONEN_RE.search(text))


def test_prueling_stammt_aus_diesem_arbeitsbaum():
    """Vorbedingung (kein AC): der geprueft Renderer wird RELATIV ZU DIESER
    Testdatei aufgeloest — sonst pruefte ein Worktree-Lauf still die Datei des
    Hauptrepos und lieferte falsches Gruen."""
    from output.renderers.alert import render as render_modul

    pfad = Path(inspect.getfile(render_modul)).resolve()
    arbeitsbaum = Path(__file__).resolve().parents[2]
    assert pfad.is_relative_to(arbeitsbaum), (
        f"Prueling stammt nicht aus diesem Arbeitsbaum: {pfad}"
    )


# ---------------------------------------------------------------------------
# AC-9 bis AC-12 — die vier Kanaele des Trip-Versands
# ---------------------------------------------------------------------------


def test_ac9_email_nennt_die_unvollstaendig_gemessene_ausdehnung(laeufe):
    """AC-9 GIVEN ein Radar-Onset-Alarm mit gezeigter Ausdehnung, bei deren
    Ermittlung Messpunkte fehlten (`gap_km` nicht leer), wird per E-Mail
    versendet
    WHEN der Trip-Nutzer das Briefing liest
    THEN steht hinter der Ausdehnungsangabe der Zusatz
    ` · Ausdehnung unvollständig gemessen`.

    Gemessen am TATSAECHLICH zugestellten Mailtext eines echten
    `check_radar_alerts()`-Laufs, bei dem der dritte von sechs Messpunkten
    keine Daten lieferte.

    RED heute: die Luecken-Angabe erreicht den Renderer nicht."""
    lauf = laeufe["mit_luecke"]
    _pruefe_ausdehnung_wird_gezeigt(lauf, "AC-9")
    text = _mailtext(lauf)
    assert LANGFORM in text, (
        f"RED/AC-9: die E-Mail muss {LANGFORM!r} tragen — sonst haelt der "
        f"Leser die genannte Strecke fuer vollstaendig gemessen.\n{text}"
    )


def test_ac10_telegram_nennt_die_unvollstaendig_gemessene_ausdehnung(laeufe):
    """AC-10 GIVEN denselben Alarm per Telegram
    WHEN der Trip-Nutzer die Nachricht liest
    THEN traegt auch die Telegram-Langform denselben Zusatz.

    RED heute: wie AC-9."""
    text = "\n".join(laeufe["mit_luecke"].telegram)
    assert LANGFORM in text, (
        f"RED/AC-10: die Telegram-Nachricht muss {LANGFORM!r} tragen.\n{text}"
    )


def test_ac11_sms_traegt_das_zeichen_unmittelbar_hinter_der_zonenliste(laeufe):
    """AC-11 GIVEN denselben Alarm per SMS
    WHEN der Trip-Nutzer die Kurznachricht liest
    THEN steht UNMITTELBAR hinter der Zonen-Liste das Zeichen `>`
    (`km2-4,9-11>`).

    Geprueft wird die POSITION, nicht die blosse Anwesenheit eines `>`: die
    Untergrenzen-Ende-Form aus #2051 S1 (` >@HH:MM`) traegt bereits eines, und
    ein `>` an falscher Stelle waere im knappsten Kanal eine ANDERE Aussage
    („Regen mindestens bis") statt einer ueber die Strecke.

    RED heute: der Kurzform-Marker existiert nicht."""
    lauf = laeufe["mit_luecke"]
    _pruefe_ausdehnung_wird_gezeigt(lauf, "AC-11")
    sms = "\n".join(lauf.sms)
    assert _MARKER_NACH_ZONEN_RE.search(sms), (
        f"RED/AC-11: das Zeichen `>` muss unmittelbar hinter der Zonen-Liste "
        f"stehen: {sms!r}"
    )
    assert sms.isascii(), f"AC-11: Kurznachricht ist nicht ASCII-rein: {sms!r}"


def test_ac12_premium_sms_traegt_denselben_marker_wie_die_sms(laeufe):
    """AC-12 GIVEN denselben Alarm per Premium-SMS (Garmin inReach)
    WHEN der Trip-Nutzer sie liest
    THEN traegt sie denselben `>`-Marker wie die regulaere SMS.

    Warum eigens geprueft und nicht „ist ja derselbe `sms_body`": auf der
    Huette am Karnischen Hoehenweg kommt NUR dieser Kanal an. Gemessen wird am
    Absenderfeld getrennt (`PREMIUM_SMS_SENDER`, `alarm_pruefstrecke.py:185`)
    — also an dem, was der Transport fuer diesen Kanal tatsaechlich absetzt.

    RED heute: wie AC-11."""
    lauf = laeufe["mit_luecke"]
    premium = "\n".join(lauf.premium_sms)
    sms = "\n".join(lauf.sms)
    assert _MARKER_NACH_ZONEN_RE.search(premium), (
        f"RED/AC-12: die Premium-SMS muss `>` unmittelbar hinter der "
        f"Zonen-Liste tragen: {premium!r}"
    )
    assert premium == sms, (
        f"AC-12: Premium-SMS und SMS muessen denselben Text tragen — "
        f"premium={premium!r}, sms={sms!r}"
    )


# ---------------------------------------------------------------------------
# AC-13 — Gegenprobe: vollstaendig vermessene Strecke bleibt stumm
# ---------------------------------------------------------------------------


def test_ac13_vollstaendige_messung_traegt_keinen_hinweis(laeufe):
    """AC-13 (GEGENPROBE, sichert AC-9..AC-12 gegen Uebersteuerung) GIVEN die
    Mehrpunkt-Abfrage lief vollstaendig durch und alle Punkte wurden gemessen
    (`gap_km == []`)
    WHEN derselbe Alarm ueber alle vier Kanaele gerendert wird
    THEN erscheint KEIN Hinweis auf Punkt 2.

    Das zaehlt besonders, weil `gap_km` laut `trip_alert.py:222-229` IMMER
    entsteht, sobald die Mehrpunkt-Abfrage lief — auch als LEERE Liste. Eine
    leere Liste ist kein Signal fuer „es fehlt etwas"; wer nur auf das
    Vorhandensein des Feldes prueft, kennzeichnet jeden Alarm.

    Positivkontrolle im SELBEN Test: derselbe Aufbau MIT Luecke muss den
    Hinweis tragen — ohne sie waere die Stille trivial wahr.

    Beide Laeufe zeigen nachweislich DIESELBE Art Ausdehnungsangabe; der
    Unterschied darf allein an der Kennzeichnung haengen."""
    ohne, mit = laeufe["ohne_luecke"], laeufe["mit_luecke"]
    _pruefe_ausdehnung_wird_gezeigt(ohne, "AC-13/ohne Luecke")
    _pruefe_ausdehnung_wird_gezeigt(mit, "AC-13/mit Luecke")

    # Testvoraussetzung: beide Laeufe nennen DIESELBE Ausdehnung — die Luecke
    # laesst die Zone weder zusammenwachsen noch trennen (#2051 S2a). Nur
    # deshalb kann der Unterschied allein an der Kennzeichnung haengen; eine
    # abweichende Zonen-Liste erklaerte die Stille sonst schon anders.
    zonen_ohne = _ZONEN_LISTE_RE.search(_kanaele(ohne)["sms"])
    zonen_mit = _ZONEN_LISTE_RE.search(_kanaele(mit)["sms"])
    assert zonen_ohne and zonen_mit and zonen_ohne.group() == zonen_mit.group(), (
        f"Testvoraussetzung/AC-13: beide Laeufe muessen DIESELBE Zonen-Liste "
        f"zeigen — ohne Luecke {zonen_ohne!r}, mit Luecke {zonen_mit!r}"
    )

    for name, text in _kanaele(ohne).items():
        assert LANGFORM not in text, (
            f"AC-13: eine vollstaendig gemessene Ausdehnung darf im Kanal "
            f"{name} keinen Zusatz tragen.\n{text}"
        )
        assert not _MARKER_NACH_ZONEN_RE.search(text), (
            f"AC-13: im Kanal {name} darf kein `>` hinter der Zonen-Liste "
            f"stehen.\n{text}"
        )

    kanaele_mit = _kanaele(mit)
    assert LANGFORM in kanaele_mit["mail"], (
        f"Positivkontrolle/AC-13: derselbe Aufbau MIT Luecke muss den "
        f"Langform-Zusatz tragen — sonst prueft die Stille oben nur ein "
        f"nicht existierendes Merkmal.\n{kanaele_mit['mail']}"
    )
    assert _MARKER_NACH_ZONEN_RE.search(kanaele_mit["sms"]), (
        f"Positivkontrolle/AC-13: derselbe Aufbau MIT Luecke muss den "
        f"`>`-Marker tragen: {kanaele_mit['sms']!r}"
    )


# ---------------------------------------------------------------------------
# AC-14 — Feld gar nicht vorhanden (Altdaten / Abfrage lief nicht)
# ---------------------------------------------------------------------------


def test_ac14_fehlendes_feld_erzeugt_keinen_hinweis():
    """AC-14 GIVEN ein `OnsetEvent`, an dem das Messluecken-Feld gar nicht
    gesetzt wurde (Altdaten, oder die Mehrpunkt-Abfrage lief nicht)
    WHEN es gerendert wird
    THEN erscheint KEIN Hinweis — Abwesenheit des Feldes bedeutet ausdruecklich
    NICHT „alles wurde gemessen", sondern nur, dass ueber Luecken nichts
    bekannt ist. Bewusst dieselbe Beobachtung wie AC-13, andere Ursache.

    Zwei Kontrollen im selben Test:
      * BYTE-Gleichheit zwischen „Feld gar nicht uebergeben" und
        „ausdruecklich leer" — der Default darf nicht bloss zufaellig dasselbe
        ergeben;
      * Positivkontrolle mit gesetzter Luecke — sonst waere die Stille der
        Beweis eines ueberhaupt nicht existierenden Merkmals.

    RED heute: die Konstruktion mit `gap_km=` scheitert am `TypeError` —
    `OnsetEvent` kennt das Feld nicht."""
    ohne = _onset_msg(_onset_event())
    leer = _onset_msg(_onset_event(gap_km=()))
    mit = _onset_msg(_onset_event(gap_km=(6.4,)))

    for name, rendern in _RENDERER.items():
        text_ohne = rendern(ohne)
        assert not _traegt_hinweis(text_ohne), (
            f"AC-14: ohne gesetztes Feld darf {name} keinen Hinweis tragen: "
            f"{text_ohne!r}"
        )
        assert text_ohne == rendern(leer), (
            f"AC-14: {name} muss fuer „Feld nicht uebergeben\" und "
            f"„ausdruecklich leer\" BYTE-identisch sein.\n"
            f"  ohne = {text_ohne!r}\n  ()   = {rendern(leer)!r}"
        )

    assert LANGFORM in render_email(mit)[1], (
        f"Positivkontrolle/AC-14: mit gesetzter Luecke MUSS der Zusatz "
        f"erscheinen: {render_email(mit)[1]!r}"
    )
    assert _MARKER_NACH_ZONEN_RE.search(render_sms(mit)), (
        f"Positivkontrolle/AC-14: mit gesetzter Luecke MUSS der `>`-Marker "
        f"erscheinen: {render_sms(mit)!r}"
    )


# ---------------------------------------------------------------------------
# AC-15 — ohne gezeigte Ausdehnung kein Hinweis (kein Bezugspunkt)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("lage, overrides", [
    ("keine Zonen", dict(rain_zones=(), km_measured=True)),
    ("unvermessene Etappe", dict(rain_zones=(_ZONE,), km_measured=False)),
])
def test_ac15_ohne_gezeigte_ausdehnung_kein_hinweis(lage, overrides):
    """AC-15 GIVEN ein Alarm zeigt gar keine Ausdehnung (keine Zonen ODER
    unvermessene Etappe — dieselbe Sichtbarkeitsregel wie die
    Ausdehnungsangabe selbst), aber `gap_km` ist gesetzt
    WHEN er gerendert wird
    THEN erscheint KEIN Hinweis auf Punkt 2 — ein Hinweis auf eine
    unvollstaendig gemessene Ausdehnung OHNE gezeigte Ausdehnung hinge ohne
    Bezugsgroesse in der Luft.

    Fuer die Kurzform ist das zugleich die Zusicherung, dass der `>`-Marker
    nie freistehend hinter dem Zeit-Token landet: dort truege er die ANDERE
    Bedeutung der Ende-Grammatik („Regen mindestens bis") und waere damit eine
    falsche Aussage, keine fehlende.

    Positivkontrolle im selben Test: derselbe Aufbau MIT gezeigter Ausdehnung
    traegt den Hinweis.

    RED heute: `TypeError` — `OnsetEvent` kennt `gap_km` nicht."""
    msg = _onset_msg(_onset_event(gap_km=(6.4,), **overrides))
    for name, rendern in _RENDERER.items():
        text = rendern(msg)
        assert LANGFORM not in text, (
            f"AC-15/{lage}: {name} darf ohne gezeigte Ausdehnung keinen "
            f"Zusatz tragen: {text!r}"
        )
        assert not _MARKER_NACH_ZONEN_RE.search(text), (
            f"AC-15/{lage}: {name} darf keinen `>` hinter einer Zonen-Liste "
            f"tragen: {text!r}"
        )
    kurz = render_sms(msg)
    assert ">" not in kurz, (
        f"AC-15/{lage}: in dieser Lage darf UEBERHAUPT kein `>` in der "
        f"Kurzform stehen — freistehend truege es die Ende-Bedeutung "
        f"(„mindestens bis\"): {kurz!r}"
    )

    sichtbar = _onset_msg(_onset_event(
        gap_km=(6.4,), rain_zones=(_ZONE,), km_measured=True,
    ))
    assert LANGFORM in render_email(sichtbar)[1], (
        f"Positivkontrolle/AC-15: mit gezeigter Ausdehnung MUSS der Zusatz "
        f"erscheinen: {render_email(sichtbar)[1]!r}"
    )
    assert _MARKER_NACH_ZONEN_RE.search(render_sms(sichtbar)), (
        f"Positivkontrolle/AC-15: mit gezeigter Ausdehnung MUSS der "
        f"`>`-Marker erscheinen: {render_sms(sichtbar)!r}"
    )


# ---------------------------------------------------------------------------
# AC-16 — 🔴 die Budget-Falle
# ---------------------------------------------------------------------------

# Ortsname mit genau 24 Zeichen (die Kopf-Obergrenze von `_render_sms_onset`).
_AC16_ORT = "Obertilliacher Bergalm".ljust(24, "x")

# Elf Zonen: zehn mit dreistelligen km-Zahlen (`100-110`, 7 Zeichen) und eine
# mit vierstelligem Ende (`900-1000`, 8 Zeichen). Aufsteigend und
# ueberschneidungsfrei. Die Laengen sind so gewaehlt, dass die VOLLE Liste
# exakt das nach Kopf und Zeit-Token verbleibende Budget von 140 Zeichen
# ausfuellt — der Marker passt dann nur noch, wenn er im Budget MITGEZAEHLT
# wird. Der Test rechnet das unten selbst nach, statt es zu behaupten.
_AC16_ZONEN = tuple(
    RainZone(km_from=float(a), km_to=float(b), onset_minutes=15,
             event_end_minutes=25)
    for a, b in (
        (100, 110), (120, 130), (140, 150), (160, 170), (180, 190),
        (200, 210), (220, 230), (240, 250), (260, 270), (280, 290),
        (900, 1000),
    )
)
_AC16_LETZTE_ZONE = "900-1000"


def _ac16_event(zonen) -> AlertMessage:
    """Der Randfall-Aufbau aus AC-16: 24-Zeichen-Ortsname,
    Untergrenzen-Ende-Form mit Wochentagskuerzeln, grosse Mengenangabe."""
    return _onset_msg(OnsetEvent(
        onset_minutes=40, onset_time="18:00", onset_day_offset=1,
        onset_weekday="Do", km_from=0.0, km_to=0.0, is_convective=False,
        intensity_label="Starker Regen", source_label="Radar (DWD)",
        location_label=_AC16_ORT, onset_precip_mm=99.9,
        event_end_time="23:59", event_end_day_offset=1,
        event_end_weekday="Fr", event_ongoing_beyond_horizon=True,
        km_measured=True, rain_zones=zonen, gap_km=(6.4,),
    ))


def _ac16_zonen_text(zonen) -> str:
    return " km" + ",".join(
        f"{int(round(z.km_from))}-{int(round(z.km_to))}" for z in zonen
    )


def test_ac16_marker_wird_nie_angeschnitten_und_erscheint_mit_platz():
    """AC-16 🔴 GIVEN eine SMS-Kurzform, die mit 24-Zeichen-Ortsname,
    Untergrenzen-Ende-Form mit Wochentagskuerzel und vollstaendiger
    Zonen-Liste bereits an der 140-Zeichen-Grenze steht, und Messluecken sind
    gesetzt
    WHEN der `>`-Marker nach der Zonen-Liste nicht mehr vollstaendig ins
    verbleibende Budget passt
    THEN landet er NIEMALS angeschnitten im Text, und die Zonen-Liste bleibt
    vollstaendig — die letzte Zone entfaellt GANZ, nie zur Haelfte.
    (b) Positivkontrolle mit Platz: derselbe Aufbau mit groesserem Budget
    zeigt die volle Liste UND den Marker.

    🔴 Warum die Assertion NICHT `len(sms) <= 140` lautet: `render.py:1054`
    endet mit `return body if len(body) <= limit else body[:limit]`. Die
    Laenge haelt der harte Schnitt IMMER ein — auch dann, wenn der Marker
    unbedingt angehaengt und anschliessend gefressen wird. Ein reiner
    Laengentest bleibt bei genau diesem Defekt gruen und bewacht nichts.

    🔴 Was hier stattdessen gemessen wird, und warum: der Aufbau ist so
    gewaehlt, dass die VOLLE Liste das Budget exakt ausfuellt (unten
    nachgerechnet, nicht behauptet). Wer den Marker im Budget MITZAEHLT, bevor
    die abwaehlbaren Zonen genommen werden (Kontextdokument, Risiko 1), laesst
    die letzte Zone weg und zeigt den Marker. Wer ihn unbedingt anhaengt,
    zeigt alle elf Zonen, und der harte Schnitt frisst den Marker still — der
    Leser sieht dann eine Ausdehnung, die vollstaendig gemessen AUSSIEHT.
    Genau diese beiden Ausgaenge trennt der Test; „Marker fehlt" ist deshalb
    hier ein Befund, nicht die zulaessige Sparform.

    Die Positivkontrolle (b) belegt zusaetzlich, dass die weggelassene Zone
    ECHT ist und mit Platz erschiene — sonst waere ihre Abwesenheit in (a)
    kein Weglassen, sondern ein nie gebautes Merkmal.

    RED heute: `TypeError` — `OnsetEvent` kennt `gap_km` nicht."""
    # Testvoraussetzung 1: der Rumpf OHNE Zonen ist so lang wie angenommen.
    basis = render_sms(_ac16_event(()), limit=140)
    budget = 140 - len(basis)
    volle_liste = _ac16_zonen_text(_AC16_ZONEN)
    assert budget == len(volle_liste), (
        f"Testvoraussetzung: die volle Zonen-Liste ({len(volle_liste)} "
        f"Zeichen) muss das verbleibende Budget ({budget} Zeichen nach dem "
        f"{len(basis)} Zeichen langen Rumpf {basis!r}) EXAKT ausfuellen — nur "
        f"dann entscheidet sich am Marker, ob er mitgezaehlt wurde."
    )

    knapp = render_sms(_ac16_event(_AC16_ZONEN), limit=140)
    mit_platz = render_sms(_ac16_event(_AC16_ZONEN), limit=160)

    # (b) Positivkontrolle zuerst: mit Platz erscheint die volle Liste MIT
    # Marker — die letzte Zone ist echt, der Marker wird ueberhaupt gebaut.
    assert f"{_AC16_LETZTE_ZONE}>" in mit_platz, (
        f"RED/AC-16 (b): mit ausreichend Platz muss die volle Zonen-Liste "
        f"stehen und der `>`-Marker unmittelbar dahinter "
        f"({_AC16_LETZTE_ZONE}>): {mit_platz!r}"
    )
    assert len(mit_platz) <= 160, (
        f"AC-16 (b): {len(mit_platz)} Zeichen ueberschreiten das Budget: "
        f"{mit_platz!r}"
    )

    # (a) Randfall: Marker vorhanden, letzte Zone GANZ entfallen.
    assert _MARKER_NACH_ZONEN_RE.search(knapp), (
        f"RED/AC-16 (a): der `>`-Marker fehlt im Randfall — er muss im Budget "
        f"MITGEZAEHLT werden, bevor die abwaehlbaren Zonen genommen werden. "
        f"Wird er stattdessen unbedingt angehaengt, frisst ihn der harte "
        f"Schnitt `body[:limit]` still, und der Text sieht vollstaendig "
        f"gemessen aus: {knapp!r}"
    )
    assert _AC16_LETZTE_ZONE not in knapp, (
        f"AC-16 (a): die letzte Zone haette im Randfall entfallen muessen — "
        f"steht sie noch da, war fuer den Marker kein Platz reserviert: "
        f"{knapp!r}"
    )
    assert "900" not in knapp, (
        f"AC-16 (a): kein FRAGMENT der weggelassenen Zone darf im Text "
        f"landen: {knapp!r}"
    )
    assert not knapp.rstrip().endswith((",", "-")), (
        f"AC-16 (a): haengendes Trennzeichen am Textende: {knapp!r}"
    )
    assert len(knapp) <= 140, (
        f"AC-16 (a): {len(knapp)} Zeichen ueberschreiten das Limit "
        f"(nachrangige Kontrolle): {knapp!r}"
    )
    assert knapp.isascii(), f"AC-16 (a): nicht ASCII-rein: {knapp!r}"


def test_ac16_marker_entfaellt_wenn_gar_keine_zone_passt():
    """AC-16 (a, zweite Lage) GIVEN denselben Aufbau, aber ein Budget, in das
    nicht einmal die ERSTE Zone passt
    WHEN gerendert wird
    THEN entfaellt die Ausdehnungsangabe komplett — und mit ihr der Marker.
    Ein freistehendes `>` hinter dem Zeit-Token waere keine fehlende, sondern
    eine FALSCHE Angabe: dort bedeutet `>` „Regen mindestens bis" (#2051 S1).

    Diese Lage ist die einzige, in der der Marker tatsaechlich „vollstaendig
    entfaellt" — und sie ist zugleich die, die den unbedingten Anbau entlarvt:
    ohne eigene Pruefung landet das Zeichen hier direkt hinter der Uhrzeit.

    Positivkontrolle: dasselbe Ereignis mit Platz zeigt Liste UND Marker.

    RED heute: `TypeError` — `OnsetEvent` kennt `gap_km` nicht."""
    basis = render_sms(_ac16_event(()), limit=140)
    eng = len(basis) + 3  # weniger als die kuerzeste Zonen-Angabe (` kmA-B`)

    knapp = render_sms(_ac16_event(_AC16_ZONEN), limit=eng)
    assert "km" not in knapp[len(_AC16_ORT):], (
        f"Testvoraussetzung: in dieses Budget darf keine Zone passen: "
        f"{knapp!r}"
    )
    assert knapp.count(">") == 1, (
        f"AC-16: ohne Zonen-Liste darf KEIN zusaetzliches `>` entstehen — "
        f"genau eines gehoert der Untergrenzen-Ende-Form ( >@Fr23:59). "
        f"Gezaehlt {knapp.count('>')}: {knapp!r}"
    )

    mit_platz = render_sms(_ac16_event(_AC16_ZONEN), limit=160)
    assert _MARKER_NACH_ZONEN_RE.search(mit_platz), (
        f"Positivkontrolle: mit Platz MUSS der Marker hinter der Zonen-Liste "
        f"stehen — sonst belegt sein Fehlen oben nichts: {mit_platz!r}"
    )
