"""TDD RED — ein Radar-Quellenausfall wird protokolliert statt lautlos zu
verschwinden (Issue #2050 Scheibe S4a, Teil A: AC-1 bis AC-6, AC-10, AC-11).

SPEC:    docs/specs/modules/feat_2050_s4a_radar_teilausfall.md
KONTEXT: docs/context/feat-2050-s4a-radar-teilausfall.md

Anforderung B-4 („Teilausfall einer Quelle gilt nie als Entwarnung") mit D-2
(„jede Unterdrueckung hat einen benannten Grund"). Heute endet ein echter
Ausfall der Radarquelle im Alarmpfad als lautloses Nichts: `frames=[]` ->
`onset_minutes=None` -> `radar_alert_due()` False -> nacktes `continue`
(`trip_alert.py:1760`). Im Alarmprotokoll des Nutzers ist das ununterscheidbar
von „geprueft, alles ruhig".

RED-Stand (gemessen, s. `docs/artifacts/.../test-red-output.txt`):

* AC-1/AC-2/AC-6 sind ROT, weil `alert_log.REASON_DATA_UNAVAILABLE` gar nicht
  existiert UND an keiner der drei Stellen ein Eintrag entsteht.
* AC-3/AC-4 sind ABGRENZUNGEN und heute wie nachher GRUEN — sie muessen rot
  werden, wenn die neue Regel ueberreagiert (ruhige Viertelstunde bzw. eigene
  Budget-Drosselung als „Ausfall" bucht).
* AC-5 ist ROT: der neue Grund hat keinen Eintrag in `_REASON_LABELS`, die
  Mail zeigte den rohen Code.
* AC-10 ist die POSITIVKONTROLLE und heute wie nachher GRUEN. Ohne sie belegt
  keiner der uebrigen Tests dieser Datei, dass die Pruefung ueberhaupt misst.
* AC-11 ist ROT aus demselben Grund wie AC-1, prueft aber zusaetzlich die
  Mandantentrennung.

AC-12/AC-13 fehlen hier BEWUSST: sie haengen an der raeumlichen Ausdehnung aus
Issue #2051 S2a, die zum Zeitpunkt dieser RED-Phase nicht in `origin/main`
liegt.

Mock-frei. Der Ausfall wird NICHT als fertiges `NowcastResult` in den Test
gelegt, sondern an der Naht nachgestellt, an der er im Betrieb entsteht
(`_fetch_frames_with_fallback` liefert keine Frames und vermerkt den
Fremdausfall) — die Marker `data_unavailable`/`throttled` bildet der echte
Dienst danach SELBST (`radar_service.py:993-1003`). Waeren sie im Test
gesetzt, prueften diese Tests ihre eigene Annahme statt der Bildungsregel.
Jeder Lauf faehrt ueber die echte Ausloeseentscheidung
(`TripAlertService.check_radar_alerts()` bzw.
`CompareRadarAlertService.check_all_compare_presets()`), gelesen wird ueber
die produktive Leseseite `alert_log.read_undelivered()` — kein
Dateiinhalt-Check.

Keine Wanduhr: alle Trip-Zeitpunkte haengen an `_AT` (gestellte Uhr), und der
Trip wird unter derselben gestellten Uhr gebaut UND gespeichert
(`_radar_trip`) — `app.loader.save_trip()` rechnet Ankunftszeiten beim
Schreiben per Naismith neu (#802), ohne diesen Rahmen haengt das aktive
Segment an der Wanduhr des Testlaufs.

Pfadregel #1409: alles relativ zu DIESER Datei, nie ueber einen festen
Hauptrepo-Pfad — sonst pruefte der Lauf aus dem Worktree den Bestand des
Hauptrepos und waere falsch gruen.
"""
from __future__ import annotations

import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from freezegun import freeze_time

ROOT = Path(__file__).resolve().parents[2]
for _p in (str(ROOT), str(ROOT / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from app.loader import save_location  # noqa: E402
from services import alert_log  # noqa: E402
from services.radar_cache import reset_shared_radar_cache_for_tests  # noqa: E402
from services.radar_service import RadarNowcastService  # noqa: E402
from services.trip_day import anchor_tz  # noqa: E402

from tests.helpers.alarm_pruefstrecke import AlarmPruefstrecke  # noqa: E402
from tests.helpers.nowcast_gate_fixtures import (  # noqa: E402
    location, radar_preset, settings_email_only, write_presets,
)
from tests.helpers.nowcast_gate_fixtures import clean_uid as compare_clean_uid  # noqa: E402
from tests.helpers.nowcast_gate_fixtures import write_user_tier as compare_write_tier  # noqa: E402
from tests.tdd.test_952_onset_alert_fidelity import _clean_user  # noqa: E402
from tests.tdd.test_alarm_pruefstrecke_selbstschutz import (  # noqa: E402
    _AT, _radar_trip, _settings_all_channels, _write_premium_profile,
)
from tests.tdd.test_alarm_szenario_briefing_ueberholung_zeitreihe import (  # noqa: E402
    _dauerregen, _radar,
)

# Die sieben heute belegten Gate-Gruende. Der Ausfall-Grund muss sich von
# JEDEM von ihnen unterscheiden (Spec: „keiner der sieben bestehenden Gruende
# beschreibt einen Fremdausfall") — eine Vermengung fuehrte spaetere
# Auswertungen in die Irre, insbesondere die Trennung „eigener Rueckzug" vs.
# „Anbieterausfall" aus ADR-0018.
_BELEGTE_GRUND_NAMEN = (
    "REASON_CHANNEL_DISABLED", "REASON_DELIVERY_FAILED", "REASON_QUIET_HOURS",
    "REASON_DAILY_LIMIT", "REASON_COOLDOWN", "REASON_BELOW_THRESHOLD",
    "REASON_EVENT_DUPLICATE", "REASON_DOUBLE_ALERT_GUARD",
)


def _uid(tag: str) -> str:
    return f"tdd-2050-s4a-{tag}-{uuid.uuid4().hex[:6]}"


def _ausfallgrund() -> str:
    """Der eigenstaendige Grund-Code des Fremdausfalls.

    BEWUSST ohne festgeschriebenes Literal: der WERT ist Sache der
    GREEN-Phase, die Zusicherung ist seine EIGENSTAENDIGKEIT. Ein `==
    "data_unavailable"` bewachte eine Schreibweise; hier wird bewacht, dass
    der Code existiert, gefuellt ist und mit KEINEM der bestehenden Gruende
    zusammenfaellt.

    ROT heute: die Konstante existiert nicht (`None`).
    """
    grund = getattr(alert_log, "REASON_DATA_UNAVAILABLE", None)
    assert isinstance(grund, str) and grund.strip(), (
        f"Der Radar-Quellenausfall braucht einen eigenen, benannten Grund "
        f"`alert_log.REASON_DATA_UNAVAILABLE` — gefunden: {grund!r}. Ohne ihn "
        f"kann kein Protokolleintrag den Ausfall benennen."
    )
    belegt = {name: getattr(alert_log, name) for name in _BELEGTE_GRUND_NAMEN}
    doppelt = [name for name, wert in belegt.items() if wert == grund]
    assert not doppelt, (
        f"Der Ausfall-Grund {grund!r} faellt mit bestehenden Gruenden zusammen "
        f"({doppelt!r}). ADR-0018 trennt Fremdausfall von jedem anderen Fall — "
        f"eine Vermengung liesse eine Auswertung den falschen Schluss ziehen."
    )
    return grund


# ─────────────────────────── Radar-Naehte (echt) ────────────────────────────


class _AusfallRadar(RadarNowcastService):
    """Echter `RadarNowcastService`; nachgestellt wird ausschliesslich die
    Abrufkette (`_fetch_frames_with_fallback`) — genau die Naht, hinter der im
    Betrieb HTTP 503/Timeout bzw. die Budget-Drosselung sitzt.

    `data_unavailable`/`throttled` bildet der Dienst danach SELBST aus den
    beiden Merkern (`radar_service.py:993-1003`). Kein Mock, kein
    vorgefertigtes `NowcastResult`: haenge man das Ergebnis fertig hinein,
    pruefte der Test seine eigene Annahme statt der Bildungsregel.

    `eigene_drosselung=True` setzt ZUSAETZLICH `_openmeteo_unavailable_this_call`
    — so verhaelt sich die Drosselung im Betrieb (Doppelverbrauch-Sperre,
    `radar_service.py:431-433`). Genau daran entscheidet sich, ob die
    Trennung aus ADR-0018 wirklich traegt oder ob die Implementierung den
    selbst gewaehlten Rueckzug als Fremdausfall bucht (AC-4).
    """

    def __init__(self, *, eigene_drosselung: bool = False) -> None:
        super().__init__()
        self._eigene_drosselung = eigene_drosselung

    def _fetch_frames_with_fallback(self, lat, lon, elevation_m=None):
        self._openmeteo_unavailable_this_call = True
        if self._eigene_drosselung:
            self._budget_throttled_this_call = True
        return [], "radar"


class _AbsturzRadar(RadarNowcastService):
    """Der Abruf scheitert mit einer GEWORFENEN Ausnahme statt mit einem
    fail-soft-Leerergebnis (AC-2). Fachlich derselbe Quellenausfall, anderer
    Weg durch den Code (`trip_alert.py:1634-1639` statt `:1760`)."""

    fehler = RuntimeError("Radar-Quelle nicht erreichbar (HTTP 503)")

    def get_nowcast(self, lat, lon, elevation_m=None, priority="user_briefing"):
        raise self.fehler


def _trocken():
    """Echte, VOLLSTAENDIGE Frames — nur eben trocken (0,0 mm/h).

    Abgrenzung zu `_AusfallRadar`: hier liegen Daten vor, sie sagen nur „kein
    Regen". Genau dieser Fall darf keinen Eintrag erzeugen (AC-3)."""
    def _quelle(lat: float, lon: float) -> list:
        from providers.brightsky import RadarFrame
        jetzt = datetime.now(timezone.utc)
        return [
            RadarFrame(timestamp=jetzt + timedelta(minutes=m), precip_mm_h=0.0)
            for m in (5, 20, 35, 50)
        ]
    return _quelle


def _gemessenes_ergebnis(trip, dienst, at: datetime):
    """Das ECHTE `NowcastResult` dieses Dienstes an den Koordinaten des Trips.

    Die Vorbedingungen jedes Tests unten haengen an DIESEM gemessenen Wert,
    nicht an einer Behauptung im Testkopf: bewegt sich die Bildungsregel von
    `data_unavailable`/`throttled`, faellt das hier LAUT auf, statt den Test
    still am falschen Fall gruen werden zu lassen.

    Der Frame-Cache ist ein Prozess-Singleton (TTL 300 s) — vor und nach der
    Messung geleert, damit weder ein frueherer Lauf diese Messung noch diese
    Messung den folgenden Prueflauf faelscht."""
    lat, lon = trip.stages[0].waypoints[0].lat, trip.stages[0].waypoints[0].lon
    with freeze_time(at):
        reset_shared_radar_cache_for_tests()
        ergebnis = dienst.get_nowcast(lat, lon)
        reset_shared_radar_cache_for_tests()
    return ergebnis


# ───────────────────────── Leseseite (produktiv) ────────────────────────────


def _vorfaelle(uid: str, entity_id: str, entity_type: str, seit: datetime) -> list:
    """Alle Nicht-Zustellungen dieser Kennung ueber die PRODUKTIVE Leseseite —
    dieselbe Funktion, aus der auch der Briefing-Hinweis gespeist wird."""
    return alert_log.read_undelivered(
        uid, entity_id=entity_id, entity_type=entity_type, since=seit,
    )


def _genau_ein_ausfall(
    uid: str, entity_id: str, entity_type: str, seit: datetime,
):
    """GENAU EIN Vorfall mit GENAU DIESEM Grund.

    Reihenfolge mit Absicht: ZUERST die Zahl der Vorfaelle, DANN der Grund.
    Umgekehrt schlueg heute ueberall zuerst die fehlende Konstante zu, und
    jeder Test dieser Datei meldete dasselbe „Konstante fehlt" — die
    eigentliche Luecke (es entsteht ueberhaupt kein Eintrag) bliebe im
    RED-Nachweis unsichtbar.

    Bewusst Gleichheit statt Enthaltensein: `grund in v.reasons` waere auch
    dann erfuellt, wenn der Eintrag zusaetzlich einen zweiten, falschen Grund
    traegt; „mindestens einer" liesse eine Eintragsflut je Prueflauf durch.
    Geprueft wird der WERT, nicht die Form."""
    vorfaelle = _vorfaelle(uid, entity_id, entity_type, seit)
    assert len(vorfaelle) == 1, (
        f"Erwartet GENAU EINEN Ausfall-Vorfall fuer {entity_type}/{entity_id}, "
        f"gefunden {len(vorfaelle)}: {vorfaelle!r}"
    )
    grund = _ausfallgrund()
    vorfall = vorfaelle[0]
    assert set(vorfall.reasons) == {grund}, (
        f"Der Vorfall muss GENAU den Ausfall-Grund {grund!r} tragen, gefunden "
        f"{sorted(vorfall.reasons)!r}"
    )
    assert vorfall.trigger == alert_log.REASON_NOWCAST, (
        f"Der Ausloeser der Meldung bleibt {alert_log.REASON_NOWCAST!r} (er "
        f"darf nicht mit dem Ausfall-Grund verschmelzen), gefunden "
        f"{vorfall.trigger!r}"
    )
    assert vorfall.channels, (
        f"Ein Vorfall ohne betroffenen Kanal ist im Briefing unsichtbar: "
        f"{vorfall!r}"
    )
    return vorfall


def _kein_vorfall(
    uid: str, entity_id: str, entity_type: str, seit: datetime,
) -> None:
    """Gar KEIN Vorfall — bewusst schaerfer als „kein Vorfall mit dem
    Ausfall-Grund".

    Die enge Fassung waere heute inhaltsleer: solange die Konstante gar nicht
    existiert, kann kein Eintrag sie tragen, und die Abgrenzung waere trivial
    erfuellt, ohne irgendetwas zu messen. Diese Scheibe fuehrt genau EINE neue
    Schreibgelegenheit ein; ein Lauf ohne Fremdausfall bleibt danach so still
    wie heute. Will eine spaetere Scheibe die eigene Drosselung mit einem
    ANDEREN Grund protokollieren, aendert sie diesen Waechter bewusst."""
    vorfaelle = _vorfaelle(uid, entity_id, entity_type, seit)
    assert vorfaelle == [], (
        f"Fuer {entity_type}/{entity_id} darf KEIN Unterdrueckungs-Vorfall "
        f"entstanden sein, gefunden: {vorfaelle!r}"
    )


# ───────────────────────────── Trip-Aufbau ──────────────────────────────────


def _aufbau(uid: str, tag: str):
    """Nutzer (Premium-Profil fuer den vierten Kanal) + Trip mit allen vier
    Kanaelen. Kein Briefing-Anker: `_briefing_announced` bleibt False, die
    Briefing-Unterdrueckung faellt als Entscheidungsgrund komplett aus — sonst
    koennte eine Stille auch von IHR kommen und die geprueften Bedingungen
    waeren nie die wirksamen."""
    _clean_user(uid)
    _write_premium_profile(uid, _AT)
    with freeze_time(_AT):
        return _radar_trip(
            uid, f"trip-2050-s4a-{tag}", send_email=True, send_telegram=True,
            send_sms=True, send_premium_sms=True,
        )


def _nichts_versendet(lauf) -> bool:
    return not (lauf.mail or lauf.telegram or lauf.sms or lauf.premium_sms)


def _wet_kontrolllauf(uid: str, tag: str):
    """Positivkontrolle fuer die Abgrenzungen AC-3/AC-4: DIESELBE Strecke, nur
    mit echtem, alarmwuerdigem Regen. Ohne sie bewiese ein „kein Eintrag" nur,
    dass der Pfad gar nicht erst lief."""
    trip = _aufbau(uid, tag)
    strecke = AlarmPruefstrecke(user_id=uid, settings=_settings_all_channels())
    return trip, strecke.lauf(
        at=_AT, zweig="radar", trip=trip, radar_service=_radar(_dauerregen(11.0)),
    )


# ──────────────────── AC-1: fail-soft-Leerergebnis ──────────────────────────


def test_ac1_quellenausfall_hinterlaesst_genau_einen_benannten_ausfall_eintrag():
    """AC-1. GIVEN der Radarabruf meldet einen echten Quellenausfall
    (`NowcastResult.data_unavailable=True`), WHEN der Radar-Alarmpfad fuer
    einen Trip geprueft wird, THEN entsteht GENAU EIN Protokolleintrag mit dem
    eigenen Ausfall-Grund — und es geht kein Alarm raus.

    Die Ausfall-Lage wird POSITIV gemessen (`data_unavailable is True`,
    `throttled is False`), nicht behauptet: ohne diese Vorbedingung koennte
    der Test auch mit einer harmlos trockenen Lage gruen sein und bewachte
    dann nichts.

    ROT heute doppelt: `alert_log.REASON_DATA_UNAVAILABLE` existiert nicht,
    und der Lauf endet mit nacktem `continue` (`trip_alert.py:1760`) —
    `read_undelivered()` liefert eine leere Liste."""
    uid = _uid("ac1")
    try:
        trip = _aufbau(uid, "ac1")
        ergebnis = _gemessenes_ergebnis(trip, _AusfallRadar(), _AT)
        assert ergebnis.data_unavailable is True, (
            f"AC-1 Vorbedingung: der Abruf muss einen FREMDAUSFALL melden, "
            f"gemessen data_unavailable={ergebnis.data_unavailable!r}."
        )
        assert ergebnis.throttled is False, (
            f"AC-1 Vorbedingung: es darf KEINE eigene Drosselung sein (die ist "
            f"AC-4), gemessen throttled={ergebnis.throttled!r}."
        )
        assert ergebnis.onset_minutes is None, (
            f"AC-1 Vorbedingung: ohne Frames gibt es keinen Beginn — genau "
            f"deshalb faellt der Ausfall heute in den stummen Ausstieg. "
            f"Gemessen onset_minutes={ergebnis.onset_minutes!r}."
        )

        seit = _AT - timedelta(minutes=1)
        strecke = AlarmPruefstrecke(user_id=uid, settings=_settings_all_channels())
        lauf = strecke.lauf(
            at=_AT, zweig="radar", trip=trip, radar_service=_AusfallRadar(),
        )
        assert lauf.triggered_count == 0, (
            f"AC-1: ein Quellenausfall darf keinen Alarm ausloesen "
            f"(war {lauf.triggered_count})."
        )
        assert _nichts_versendet(lauf), (
            f"AC-1: kein Kanal darf etwas ausliefern: mail={lauf.mail!r} "
            f"telegram={lauf.telegram!r} sms={lauf.sms!r} "
            f"premium_sms={lauf.premium_sms!r}"
        )
        _genau_ein_ausfall(uid, trip.id, "trip", seit)
    finally:
        _clean_user(uid)


# ──────────────────────── AC-2: geworfene Ausnahme ──────────────────────────


def test_ac2_geworfene_ausnahme_beim_radarabruf_erzeugt_denselben_ausfall_grund():
    """AC-2. GIVEN der Radarabruf scheitert mit einer GEWORFENEN Ausnahme
    statt mit einem Leerergebnis, WHEN derselbe Radar-Alarmpfad geprueft wird,
    THEN entsteht derselbe Eintrag mit demselben Ausfall-Grund wie in AC-1.

    Zwei verschiedene Wege in den Code, EIN fachlicher Fall — nur einen zu
    behandeln liesse die Haelfte aller echten Ausfaelle weiterhin still. Der
    Ausnahme-Zweig (`trip_alert.py:1634-1639`) protokolliert heute NUR, wenn
    zufaellig gerade eine Sperrzeit lief; dieser Test faehrt bewusst den
    Regelfall OHNE Sperrzeit — die heute stumme Luecke aus #1628.

    Dass der Abruf wirklich wirft, wird vorher gemessen: sonst koennte der
    Test denselben Weg wie AC-1 fahren und die zweite Haelfte bliebe
    unbewacht.

    ROT heute: kein Eintrag, `read_undelivered()` ist leer."""
    uid = _uid("ac2")
    try:
        trip = _aufbau(uid, "ac2")
        geworfen = None
        try:
            _gemessenes_ergebnis(trip, _AbsturzRadar(), _AT)
        except Exception as e:  # noqa: BLE001 — genau das ist die Vorbedingung
            geworfen = e
        assert geworfen is _AbsturzRadar.fehler, (
            f"AC-2 Vorbedingung: der Abruf muss eine AUSNAHME werfen (anderer "
            f"Weg als AC-1), gefangen wurde {geworfen!r}."
        )

        seit = _AT - timedelta(minutes=1)
        strecke = AlarmPruefstrecke(user_id=uid, settings=_settings_all_channels())
        lauf = strecke.lauf(
            at=_AT, zweig="radar", trip=trip, radar_service=_AbsturzRadar(),
        )
        assert lauf.triggered_count == 0, (
            f"AC-2: ein gescheiterter Abruf darf keinen Alarm ausloesen "
            f"(war {lauf.triggered_count})."
        )
        assert _nichts_versendet(lauf), (
            f"AC-2: kein Kanal darf etwas ausliefern: mail={lauf.mail!r} "
            f"telegram={lauf.telegram!r}"
        )
        _genau_ein_ausfall(uid, trip.id, "trip", seit)
    finally:
        _clean_user(uid)


def test_geworfener_abruf_traegt_den_ausfall_grund_auch_bei_offener_sperrzeit():
    """AC-2, zweite Haelfte — die Zusicherung „UNABHAENGIG von der Sperrzeit".

    GIVEN eine nachweislich OFFENE Sperrzeit aus einem vorangegangenen Alarm,
    WHEN der Radarabruf im selben Sperrfenster mit einer geworfenen Ausnahme
    scheitert, THEN traegt der entstehende Vorfall den Ausfall-Grund und
    NICHT `cooldown`.

    Der Test oben faehrt laut eigenem Docstring bewusst nur den Regelfall ohne
    Sperrzeit. Damit war die Haelfte der Zusicherung unbewacht, die den alten
    Zustand beschreibt: bis #2050 S4a protokollierte der Ausnahme-Zweig NUR bei
    offener Sperrzeit, und dann unter `cooldown`. Wer diese Fassung
    wiederherstellt, faellt heute keinem Test dieser Datei auf — der Nutzer
    saehe im Briefing „so hast du es eingestellt", waehrend in Wahrheit die
    Quelle ausgefallen ist. Genau das faengt dieser Test.

    Die Sperrzeit entsteht ueber den ECHTEN Schreibweg: Lauf 1 loest mit echtem
    Regen aus und bucht sie dabei selbst (`record_nowcast_sent`, erst nach
    Zustellung). Dass sie zum Zeitpunkt des Ausfalls noch OFFEN war, wird
    GEMESSEN statt behauptet — der Kontrolllauf 15 Minuten SPAETER bleibt an
    ihr haengen und protokolliert `cooldown`. Der Schluss auf den frueheren
    Zeitpunkt ist zwingend: zwischen beiden Laeufen wurde nichts zugestellt,
    die Sperrzeit laeuft also unveraendert aus Lauf 1 und ist als
    zusammenhaengendes Fenster bei +30 offen, wenn sie es bei +45 ist.

    Der Kontrolllauf traegt dieselbe Menge wie Lauf 1 (kein Faktor) und kann
    die Sperrzeit deshalb nicht ueberholen (#2065) — er misst sie, statt sie
    zu durchbrechen.

    Reihenfolge mit Absicht: der Ausfall-Vorfall wird VOR dem Kontrolllauf
    gelesen. Danach lagen zwei Vorfaelle im selben Zeitfenster, und die
    Zusicherung „genau einer" liesse sich nicht mehr sauber pruefen."""
    uid = _uid("sperrzeit")
    try:
        trip = _aufbau(uid, "sperrzeit")
        strecke = AlarmPruefstrecke(user_id=uid, settings=_settings_all_channels())

        lauf1 = strecke.lauf(
            at=_AT, zweig="radar", trip=trip, radar_service=_radar(_dauerregen(11.0)),
        )
        assert lauf1.triggered_count == 1, (
            f"Vorbedingung: Lauf 1 muss ausloesen und dabei die Sperrzeit "
            f"buchen — ohne sie pruefte dieser Test denselben Fall wie AC-2 "
            f"(war {lauf1.triggered_count})."
        )

        at_ausfall = _AT + timedelta(minutes=30)
        seit_ausfall = at_ausfall - timedelta(minutes=1)
        ausfall_lauf = strecke.lauf(
            at=at_ausfall, zweig="radar", trip=trip, radar_service=_AbsturzRadar(),
        )
        assert ausfall_lauf.triggered_count == 0, (
            f"Ein gescheiterter Abruf darf keinen Alarm ausloesen "
            f"(war {ausfall_lauf.triggered_count})."
        )
        assert _nichts_versendet(ausfall_lauf), (
            f"Kein Kanal darf etwas ausliefern: mail={ausfall_lauf.mail!r} "
            f"telegram={ausfall_lauf.telegram!r} sms={ausfall_lauf.sms!r} "
            f"premium_sms={ausfall_lauf.premium_sms!r}"
        )
        vorfall = _genau_ein_ausfall(uid, trip.id, "trip", seit_ausfall)
        assert alert_log.REASON_COOLDOWN not in vorfall.reasons, (
            f"Der Vorfall darf NICHT {alert_log.REASON_COOLDOWN!r} tragen: die "
            f"Sperrzeit hat diesen Lauf nicht unterdrueckt, die ausgefallene "
            f"Quelle hat ihn verhindert. Gefunden {sorted(vorfall.reasons)!r}"
        )

        at_kontrolle = _AT + timedelta(minutes=45)
        seit_kontrolle = at_kontrolle - timedelta(minutes=1)
        kontrolle = strecke.lauf(
            at=at_kontrolle, zweig="radar", trip=trip,
            radar_service=_radar(_dauerregen(11.0)),
        )
        assert kontrolle.triggered_count == 0, (
            f"Sperrzeit-Nachweis: der Kontrolllauf mit unveraenderter Menge "
            f"muss an der Sperrzeit haengenbleiben (war "
            f"{kontrolle.triggered_count})."
        )
        kontroll_vorfaelle = _vorfaelle(uid, trip.id, "trip", seit_kontrolle)
        assert len(kontroll_vorfaelle) == 1, (
            f"Sperrzeit-Nachweis: erwartet GENAU EINEN Kontroll-Vorfall, "
            f"gefunden {len(kontroll_vorfaelle)}: {kontroll_vorfaelle!r}"
        )
        assert set(kontroll_vorfaelle[0].reasons) == {alert_log.REASON_COOLDOWN}, (
            f"Sperrzeit-Nachweis: der Kontrolllauf muss unter "
            f"{alert_log.REASON_COOLDOWN!r} gebucht sein — nur dann war die "
            f"Sperrzeit beim Ausfall-Lauf 15 Minuten frueher nachweislich "
            f"offen. Gefunden {sorted(kontroll_vorfaelle[0].reasons)!r}"
        )
    finally:
        _clean_user(uid)


# ─────────────────── AC-3: echte Daten, kein Regen (Abgrenzung) ─────────────


def test_ac3_echte_daten_ohne_regen_hinterlassen_keinen_vorfall():
    """AC-3 (ABGRENZUNG, muss rot werden, wenn man sie verletzt). GIVEN echte,
    vollstaendige Radardaten, die schlicht keinen Regen finden, WHEN der
    Radar-Alarmpfad geprueft wird, THEN entsteht KEIN Protokolleintrag — eine
    ruhige Viertelstunde ist kein Vorfall.

    Die gefaehrlichste Fehl-Umsetzung dieser Scheibe ist die Ueberreaktion:
    einen Eintrag an jeden ergebnislosen Lauf zu haengen. Der Nutzer bekaeme
    dann in jedem Briefing einen „nicht zugestellt"-Block fuer 96 ruhige
    Prueflaeufe des Tages.

    POSITIVKONTROLLE im selben Test: derselbe Aufbau mit echtem Regen loest
    aus. Ohne sie bewiese das „kein Eintrag" nur, dass der Pfad gar nicht bis
    zur Entscheidung lief."""
    uid, ctrl = _uid("ac3"), _uid("ac3-ctrl")
    try:
        trip = _aufbau(uid, "ac3")
        ergebnis = _gemessenes_ergebnis(trip, _radar(_trocken()), _AT)
        assert ergebnis.data_unavailable is False and ergebnis.throttled is False, (
            f"AC-3 Vorbedingung: die Lage muss ECHTE Daten tragen, gemessen "
            f"data_unavailable={ergebnis.data_unavailable!r}, "
            f"throttled={ergebnis.throttled!r}."
        )
        assert ergebnis.frames, (
            "AC-3 Vorbedingung: es muessen Frames vorliegen — ohne sie waere "
            "das wieder der Ausfall aus AC-1 und nicht die Abgrenzung."
        )
        assert ergebnis.onset_minutes is None, (
            f"AC-3 Vorbedingung: trockene Frames ergeben keinen Beginn, "
            f"gemessen {ergebnis.onset_minutes!r}."
        )

        seit = _AT - timedelta(minutes=1)
        strecke = AlarmPruefstrecke(user_id=uid, settings=_settings_all_channels())
        lauf = strecke.lauf(
            at=_AT, zweig="radar", trip=trip, radar_service=_radar(_trocken()),
        )
        assert lauf.triggered_count == 0, (
            f"AC-3 Vorbedingung: trockene Daten loesen keinen Alarm aus "
            f"(war {lauf.triggered_count})."
        )
        assert _vorfaelle(uid, trip.id, "trip", seit) == [], (
            f"AC-3: eine ruhige Viertelstunde ist KEIN Vorfall — im Protokoll "
            f"darf nichts stehen, gefunden "
            f"{_vorfaelle(uid, trip.id, 'trip', seit)!r}"
        )

        _, kontrolle = _wet_kontrolllauf(ctrl, "ac3-ctrl")
        assert kontrolle.triggered_count == 1, (
            f"AC-3 Positivkontrolle: derselbe Aufbau mit echtem Regen MUSS "
            f"ausloesen — sonst sagt die Stille oben nichts ueber die "
            f"Trockenheit aus (war {kontrolle.triggered_count})."
        )
    finally:
        _clean_user(uid)
        _clean_user(ctrl)


# ───────────────── AC-4: eigene Budget-Drosselung (Abgrenzung) ──────────────


def test_ac4_eigene_budget_drosselung_ist_kein_fremdausfall():
    """AC-4 (ABGRENZUNG, muss rot werden, wenn man sie verletzt). GIVEN eine
    EIGENE Budget-Drosselung des Abrufs (`throttled=True,
    data_unavailable=False`), WHEN der Radar-Alarmpfad geprueft wird, THEN
    entsteht KEIN Ausfall-Eintrag.

    ADR-0018 trennt den selbst gewaehlten Rueckzug vom Fremdausfall. Wer beide
    auf denselben Grund bucht, laesst eine externe Auswertung den eigenen
    Rueckzug als Anbieterausfall eskalieren. Die Drosselung setzt im Betrieb
    ZUSAETZLICH den Unavailable-Merker (Doppelverbrauch-Sperre) — genau
    deshalb ist die Verwechslung naheliegend und braucht einen Waechter.

    Geprueft wird das Ausbleiben JEDES Eintrags, nicht nur des Ausfall-Grundes
    — Begruendung s. `_kein_vorfall()`: die enge Fassung waere solange
    inhaltsleer, wie es die Konstante nicht gibt.

    POSITIVKONTROLLE im selben Test wie bei AC-3."""
    uid, ctrl = _uid("ac4"), _uid("ac4-ctrl")
    try:
        trip = _aufbau(uid, "ac4")
        ergebnis = _gemessenes_ergebnis(
            trip, _AusfallRadar(eigene_drosselung=True), _AT,
        )
        assert ergebnis.throttled is True, (
            f"AC-4 Vorbedingung: die Lage muss die EIGENE Drosselung sein, "
            f"gemessen throttled={ergebnis.throttled!r}."
        )
        assert ergebnis.data_unavailable is False, (
            f"AC-4 Vorbedingung: eine Drosselung ist ausdruecklich KEIN "
            f"Fremdausfall (`radar_service.py:993-1003`), gemessen "
            f"data_unavailable={ergebnis.data_unavailable!r} — waere sie True, "
            f"pruefte dieser Test denselben Fall wie AC-1."
        )

        seit = _AT - timedelta(minutes=1)
        strecke = AlarmPruefstrecke(user_id=uid, settings=_settings_all_channels())
        lauf = strecke.lauf(
            at=_AT, zweig="radar", trip=trip,
            radar_service=_AusfallRadar(eigene_drosselung=True),
        )
        assert lauf.triggered_count == 0, (
            f"AC-4 Vorbedingung: eine gedrosselte Abfrage loest keinen Alarm "
            f"aus (war {lauf.triggered_count})."
        )
        _kein_vorfall(uid, trip.id, "trip", seit)

        _, kontrolle = _wet_kontrolllauf(ctrl, "ac4-ctrl")
        assert kontrolle.triggered_count == 1, (
            f"AC-4 Positivkontrolle: derselbe Aufbau mit echtem Regen MUSS "
            f"ausloesen (war {kontrolle.triggered_count})."
        )
    finally:
        _clean_user(uid)
        _clean_user(ctrl)


# ───────────────────── AC-5: deutsche Beschriftung, Block ───────────────────


def test_ac5_der_ausfall_grund_erscheint_deutsch_im_fehlgeschlagen_block():
    """AC-5. GIVEN ein Ausfall-Eintrag liegt im Alarmprotokoll eines Nutzers,
    WHEN der „nicht zugestellt"-Abschnitt des Briefings gerendert wird, THEN
    erscheint der Grund als DEUTSCHE Beschriftung — nicht als roher Code — im
    Block „FEHLGESCHLAGEN", nicht in „ZURUECKGEHALTEN".

    Ein Quellenausfall ist keine Nutzereinstellung. Die bestehenden
    „withheld"-Gruende (Stille Stunden, Cooldown, Tageslimit) sagen dem Nutzer
    „so hast du es eingestellt" — bei einem Anbieterausfall waere das schlicht
    falsch.

    Gemessen wird am Renderer-Baustein mit einem ECHTEN Vorfall, den der
    Prueflauf selbst geschrieben und die produktive Leseseite
    zurueckgeliefert hat — nicht mit einem im Test zusammengesetzten Objekt.
    Der vollstaendige Mail-Weg braucht Staging (Anker `last_briefing_at`,
    Reihenfolge Briefing -> Eintrag -> zweites Briefing) und gehoert damit
    nicht in die Kernschicht; der Baustein hier ist derselbe, den `plain.py`/
    `html.py`/`compact.py` einbinden.

    Die beiden Haelften wirken unterschiedlich scharf, das ist bewusst so
    benannt: die BLOCK-Haelfte ist heute auch ohne Registereintrag erfuellt
    (`_REASON_BLOCK.get(reason, "failed")` faellt auf „failed" zurueck) und
    faengt die FALSCHE Einsortierung nach „withheld". Die
    BESCHRIFTUNGS-Haelfte ist die, die den Eintrag in `_REASON_LABELS`
    erzwingt: ohne ihn zeigt `_gruende()` den rohen Code.

    ROT heute: es entsteht schon kein Eintrag (AC-1), und der Code hat keine
    Beschriftung."""
    from output.renderers.email.undelivered_hint import (
        HEADING_FAILED, HEADING_WITHHELD, render_undelivered_plain,
    )

    uid = _uid("ac5")
    try:
        trip = _aufbau(uid, "ac5")
        seit = _AT - timedelta(minutes=1)
        strecke = AlarmPruefstrecke(user_id=uid, settings=_settings_all_channels())
        strecke.lauf(
            at=_AT, zweig="radar", trip=trip, radar_service=_AusfallRadar(),
        )
        vorfall = _genau_ein_ausfall(uid, trip.id, "trip", seit)

        text = render_undelivered_plain([vorfall], tz=anchor_tz(trip, _AT))
        grund = _ausfallgrund()
        assert grund not in text, (
            f"AC-5: im Briefing darf der rohe Code {grund!r} nicht erscheinen "
            f"— der Grund braucht eine deutsche Beschriftung in "
            f"`_REASON_LABELS`:\n{text}"
        )
        assert HEADING_FAILED in text, (
            f"AC-5: ein Quellenausfall gehoert in den Block "
            f"{HEADING_FAILED!r}:\n{text}"
        )
        assert HEADING_WITHHELD not in text, (
            f"AC-5: {HEADING_WITHHELD!r} behauptet eine Nutzereinstellung — "
            f"ein Anbieterausfall ist keine:\n{text}"
        )
    finally:
        _clean_user(uid)


# ───────────────────── AC-6: Paritaet Ortsvergleich ─────────────────────────


def test_ac6_der_ortsvergleich_radarpfad_protokolliert_denselben_ausfall():
    """AC-6. GIVEN dieselbe Ausfall-Lage wie in AC-1, aber am gleichartigen
    Radarpfad des Ortsvergleichs (`compare_radar_alert.py`), WHEN dieser Pfad
    geprueft wird, THEN entsteht ebenfalls GENAU EIN Eintrag mit dem
    Ausfall-Grund und `entity_type == "compare"`.

    Die Schwester-Scheibe S3b hat beide Flaechen im selben Commit bedient; ein
    Unterdrueckungsgrund, den nur eine Flaeche kennt, waere ein Paritaetsbruch.

    Der Weg ueber `AlarmPruefstrecke` steht hier NICHT zur Verfuegung — sie
    kennt nur die drei Trip-Zweige (`deviation`/`official`/`radar`,
    `alarm_pruefstrecke.py:40`). Gefahren wird deshalb nach dem Muster der
    bestehenden Compare-Radar-Tests (`test_compare_radar_alert_daily_limit.py`):
    echtes Preset und echter Ort auf Platte, echter
    `CompareRadarAlertService`, Radar ueber die DI-Naht, Versand ueber
    `mail_sink`.

    ROT heute: `_detect_triggered_locations` steigt bei `radar_alert_due()`
    False mit nacktem `continue` aus (`compare_radar_alert.py:447-448`)."""
    from services.compare_radar_alert import CompareRadarAlertService

    uid, preset_id = _uid("ac6"), "cp-2050-s4a-ac6"
    compare_clean_uid(uid)
    try:
        compare_write_tier(uid, "premium")  # kein Tageslimit im Weg
        ort = location("loc-2050-s4a", "Ausfalldorf")
        save_location(ort, user_id=uid)
        write_presets(uid, [radar_preset(preset_id, [ort.id], user_id=uid)])

        seit = datetime.now(timezone.utc) - timedelta(minutes=1)
        mails: list = []
        sent = CompareRadarAlertService(
            settings=settings_email_only(), user_id=uid,
            radar_service=_AusfallRadar(),
            mail_sink=lambda subject, body: mails.append((subject, body)),
        ).check_all_compare_presets()

        assert sent == 0, (
            f"AC-6 Vorbedingung: ein Quellenausfall darf keinen "
            f"Vergleichs-Alarm ausloesen (war {sent})."
        )
        assert mails == [], f"AC-6: es darf nichts versendet werden: {mails!r}"
        _genau_ein_ausfall(uid, preset_id, "compare", seit)
    finally:
        compare_clean_uid(uid)


def test_geworfener_abruf_im_ortsvergleich_protokolliert_denselben_ausfall():
    """AC-2 x AC-6 — der Ausnahme-Zweig des Ortsvergleichs.

    GIVEN der Radarabruf des Vergleichs-Pfads scheitert mit einer GEWORFENEN
    Ausnahme statt mit einem Leerergebnis, WHEN der Pfad geprueft wird, THEN
    entsteht GENAU EIN Vorfall mit dem Ausfall-Grund und `entity_type ==
    "compare"`.

    AC-6 faehrt nur die fail-soft-Form (`data_unavailable=True`) und laesst
    damit die zweite Haelfte der Paritaet unbewacht: der gesamte
    Ausnahme-Zweig (`compare_radar_alert.py:479-487`) liess sich entfernen,
    ohne dass ein Test dieser oder einer Nachbardatei rot wurde. Im Betrieb
    ist genau das der haeufigere Fall — HTTP 503 und Timeout werfen, sie
    liefern kein leeres Ergebnis.

    Dass der Abruf wirklich WIRFT, wird vorher an den Koordinaten des Orts
    gemessen: sonst koennte dieser Test unbemerkt denselben Weg wie AC-6
    fahren und der Ausnahme-Zweig bliebe erneut unbewacht.

    Der Gegenprobe-Blick auf `entity_type == "trip"` ist kein Beiwerk: ein
    Eintrag unter der falschen Flaeche waere im Vergleichs-Briefing unsichtbar
    und tauchte stattdessen bei einem gleichnamigen Trip auf."""
    from services.compare_radar_alert import CompareRadarAlertService

    uid, preset_id = _uid("compare-absturz"), "cp-2050-s4a-absturz"
    compare_clean_uid(uid)
    try:
        compare_write_tier(uid, "premium")  # kein Tageslimit im Weg
        ort = location("loc-2050-s4a-absturz", "Absturzdorf")
        save_location(ort, user_id=uid)
        write_presets(uid, [radar_preset(preset_id, [ort.id], user_id=uid)])

        geworfen = None
        try:
            _AbsturzRadar().get_nowcast(
                ort.lat, ort.lon, elevation_m=ort.elevation_m,
            )
        except Exception as e:  # noqa: BLE001 — genau das ist die Vorbedingung
            geworfen = e
        assert geworfen is _AbsturzRadar.fehler, (
            f"Vorbedingung: der Abruf muss eine AUSNAHME werfen (anderer Weg "
            f"als AC-6), gefangen wurde {geworfen!r}."
        )

        seit = datetime.now(timezone.utc) - timedelta(minutes=1)
        mails: list = []
        sent = CompareRadarAlertService(
            settings=settings_email_only(), user_id=uid,
            radar_service=_AbsturzRadar(),
            mail_sink=lambda subject, body: mails.append((subject, body)),
        ).check_all_compare_presets()

        assert sent == 0, (
            f"Vorbedingung: ein gescheiterter Abruf darf keinen "
            f"Vergleichs-Alarm ausloesen (war {sent})."
        )
        assert mails == [], f"Es darf nichts versendet werden: {mails!r}"
        _genau_ein_ausfall(uid, preset_id, "compare", seit)
        assert _vorfaelle(uid, preset_id, "trip", seit) == [], (
            f"Der Vorfall gehoert zur Flaeche 'compare' — unter 'trip' darf "
            f"nichts stehen, gefunden "
            f"{_vorfaelle(uid, preset_id, 'trip', seit)!r}"
        )
    finally:
        compare_clean_uid(uid)


# ──────────────────────── AC-10: Positivkontrolle ───────────────────────────


def test_ac10_lauf_ohne_jeden_ausfall_loest_aus_und_wird_versendet():
    """AC-10 (POSITIVKONTROLLE — der wichtigste Test dieser Datei). GIVEN ein
    Radar-Prueflauf OHNE jeden Ausfall (echte Daten, durchgefuehrte
    Gewitterpruefung, Regen ueber der Ausloeseschwelle), WHEN der
    Radar-Alarmpfad geprueft wird, THEN loest der Lauf weiterhin aus und der
    Alarm wird TATSAECHLICH versendet.

    Ohne diesen Nachweis belegt kein einziger der uebrigen Tests, dass die
    Pruefung ueberhaupt etwas misst: „kein Alarm" ist auch das Ergebnis eines
    Pfads, der aus einem ganz anderen Grund gar nicht erst losliefe. Gemessen
    wird nicht nur der Zaehler (er zaehlt bereits den VERSUCH, Anti-Muster
    #656), sondern der Inhalt an allen vier Kanal-Abgriffen der Pruefstrecke.

    Die Ausfall-Freiheit wird am echten Ergebnis GEMESSEN — auch
    `convective_checked`: ein Lauf, dessen Gewitterpruefung heimlich ausfiele,
    waere keine Positivkontrolle fuer Teil B.

    Heute wie nachher GRUEN."""
    uid = _uid("ac10")
    try:
        trip = _aufbau(uid, "ac10")
        ergebnis = _gemessenes_ergebnis(trip, _radar(_dauerregen(11.0)), _AT)
        assert ergebnis.data_unavailable is False, (
            f"AC-10 Vorbedingung: kein Fremdausfall, gemessen "
            f"{ergebnis.data_unavailable!r}."
        )
        assert ergebnis.throttled is False, (
            f"AC-10 Vorbedingung: keine Drosselung, gemessen "
            f"{ergebnis.throttled!r}."
        )
        assert ergebnis.convective_checked is True, (
            f"AC-10 Vorbedingung: die Gewitterpruefung muss STATTGEFUNDEN "
            f"haben, gemessen {ergebnis.convective_checked!r}."
        )
        assert ergebnis.onset_minutes is not None, (
            f"AC-10 Vorbedingung: die Lage muss einen Beginn tragen, gemessen "
            f"{ergebnis.onset_minutes!r}."
        )

        seit = _AT - timedelta(minutes=1)
        strecke = AlarmPruefstrecke(user_id=uid, settings=_settings_all_channels())
        lauf = strecke.lauf(
            at=_AT, zweig="radar", trip=trip,
            radar_service=_radar(_dauerregen(11.0)),
        )
        assert lauf.triggered_count == 1, (
            f"AC-10: ein Lauf ohne jeden Ausfall MUSS ausloesen (war "
            f"{lauf.triggered_count})."
        )
        assert lauf.mail and lauf.telegram and lauf.sms and lauf.premium_sms, (
            f"AC-10: alle vier Kanaele muessen Inhalt tragen: mail={lauf.mail!r} "
            f"telegram={lauf.telegram!r} sms={lauf.sms!r} "
            f"premium_sms={lauf.premium_sms!r}"
        )
        assert _vorfaelle(uid, trip.id, "trip", seit) == [], (
            f"AC-10: ein zugestellter Alarm darf keinen Unterdrueckungs-"
            f"Eintrag hinterlassen, gefunden "
            f"{_vorfaelle(uid, trip.id, 'trip', seit)!r}"
        )
    finally:
        _clean_user(uid)


# ─────────────────────── AC-11: zwei Nutzer, zwei Logs ──────────────────────


def test_ac11_zwei_nutzer_teilen_sich_keinen_ausfall_eintrag():
    """AC-11. GIVEN zwei VERSCHIEDENE Nutzer erleiden im selben Pruefzyklus je
    einen Radar-Quellenausfall, WHEN beide Alarmpfade geprueft werden, THEN
    landet jeder Eintrag ausschliesslich im Alarmprotokoll des jeweils
    betroffenen Nutzers.

    Pflicht bei jedem datenbewegenden Nachweis in diesem Projekt: jeder Nutzer
    hat sein eigenes Datenverzeichnis (`get_data_dir(user_id)`), ein
    gemeinsamer Eintrag waere ein Cross-User-Datenleck. Geprueft wird in BEIDE
    Richtungen — jeder Nutzer sieht seinen eigenen Vorfall und in seinem
    Protokoll KEINE Spur der Kennung des anderen.

    ROT heute aus demselben Grund wie AC-1 (es entsteht ueberhaupt kein
    Eintrag)."""
    uid_a, uid_b = _uid("ac11-a"), _uid("ac11-b")
    try:
        trip_a = _aufbau(uid_a, "ac11-a")
        trip_b = _aufbau(uid_b, "ac11-b")
        assert trip_a.id != trip_b.id, (
            "AC-11 Vorbedingung: die beiden Trips brauchen verschiedene "
            "Kennungen, sonst laesst sich Vermischung gar nicht erkennen."
        )
        seit = _AT - timedelta(minutes=1)

        for uid, trip in ((uid_a, trip_a), (uid_b, trip_b)):
            lauf = AlarmPruefstrecke(
                user_id=uid, settings=_settings_all_channels(),
            ).lauf(at=_AT, zweig="radar", trip=trip, radar_service=_AusfallRadar())
            assert lauf.triggered_count == 0, (
                f"AC-11 Vorbedingung: der Ausfall darf bei {uid!r} keinen "
                f"Alarm ausloesen (war {lauf.triggered_count})."
            )

        _genau_ein_ausfall(uid_a, trip_a.id, "trip", seit)
        _genau_ein_ausfall(uid_b, trip_b.id, "trip", seit)

        assert _vorfaelle(uid_a, trip_b.id, "trip", seit) == [], (
            f"AC-11: im Protokoll von {uid_a!r} darf KEIN Vorfall der Kennung "
            f"{trip_b.id!r} stehen, gefunden "
            f"{_vorfaelle(uid_a, trip_b.id, 'trip', seit)!r}"
        )
        assert _vorfaelle(uid_b, trip_a.id, "trip", seit) == [], (
            f"AC-11: im Protokoll von {uid_b!r} darf KEIN Vorfall der Kennung "
            f"{trip_a.id!r} stehen, gefunden "
            f"{_vorfaelle(uid_b, trip_a.id, 'trip', seit)!r}"
        )
    finally:
        _clean_user(uid_a)
        _clean_user(uid_b)
