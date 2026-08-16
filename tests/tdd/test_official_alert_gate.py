"""TDD RED — Der geteilte Freigabe-Baustein des amtlichen Alarms
(Issue #1467 S4a, AC-1 bis AC-3, AC-9, AC-12, AC-12b, AC-16).

SPEC:    docs/specs/modules/rework_1467_s4a_amtlich.md
KONTEXT: docs/context/rework-1467-s4a-amtlich.md

``check_official_alert_gate`` existiert heute nicht; beide amtlichen Pfade
fuehren je eine eigene Inline-Kette (``compare_official_alert.py`` Ruhezeit
``:128`` / Tageslimit ``:164`` NACH dem Abruf; ``trip_alert.py`` Ruhezeit
``:1485`` / Sperrzeit ``:1494`` / Tageslimit ``:1497``).

RED-Grund AC-1/2/3/9: ``ImportError``. RED-Grund AC-12: die aufgezeichnete
Laufzeit-Reihenfolge enthaelt heute nur ``check_briefing_imminent``.

Mock-frei: echte Presets/Orte/Trips auf Platte, echte Zustandsdateien, echte
Warnquellen-Registry ohne Netz. Pfadregel #1409.
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
for _p in (str(ROOT), str(ROOT / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from tests.helpers.briefing_imminent_fixtures import (  # noqa: E402
    LOCATION_ZONE, TRIP_ZONE, clean_uid, compare_official_versand_lauf, compare_preset,
    fresh_uid, ruhezeit_woanders, stunde_versetzt, write_location, write_presets,
    write_trip, write_user_tier,
)
from tests.helpers.nowcast_gate_fixtures import (  # noqa: E402
    read_daily_counter, seed_daily_counter,
)
from tests.helpers.official_alert_gate_fixtures import (  # noqa: E402
    gate_spion, trip_amtlicher_direktlauf, zaehlende_tagesgrenze,
)

GATE = "check_official_alert_gate"
BRIEFING = "check_briefing_imminent"
PRESET, ORT, TRIP = "cp-1467s4a", "loc-1467s4a", "trip-1467s4a-gate"


def _nah() -> int:
    """Ortsstunde im 60-Minuten-Vorlauf der Briefing-Sperre (#1594)."""
    return stunde_versetzt(1, zone=LOCATION_ZONE)


def _ruhezeit_jetzt(zone, puffer: int = 20) -> tuple[str, str]:
    """Fenster in der ORTSZONE des Gegenstands (dort wertet ``is_quiet_hours()``
    seit #1726 aus), das „jetzt" umschliesst."""
    jetzt = datetime.now(timezone.utc).astimezone(zone)
    return ((jetzt - timedelta(minutes=puffer)).strftime("%H:%M"),
            (jetzt + timedelta(minutes=puffer)).strftime("%H:%M"))


@pytest.fixture
def nutzer():
    vergeben: list[str] = []

    def _neu(kennung: str, tier: str = "premium") -> str:
        user_id = fresh_uid(f"s4a-gate-{kennung}")
        clean_uid(user_id)
        write_user_tier(user_id, tier)
        write_location(user_id, ORT)
        vergeben.append(user_id)
        return user_id

    yield _neu
    for user_id in vergeben:
        clean_uid(user_id)


def _preset_schreiben(user_id: str, **kwargs) -> None:
    kwargs.setdefault("morgen_stunde", stunde_versetzt(5, zone=LOCATION_ZONE))
    kwargs.setdefault("quiet", ruhezeit_woanders())
    kwargs.setdefault("location_ids", [ORT])
    write_presets(user_id, [compare_preset(PRESET, **kwargs)])


def _trip_schreiben(user_id: str, **kwargs) -> None:
    kwargs.setdefault("morgen_stunde", stunde_versetzt(5, zone=TRIP_ZONE))
    kwargs.setdefault("abend_stunde", stunde_versetzt(9, zone=TRIP_ZONE))
    kwargs.setdefault("quiet", ruhezeit_woanders(zone=TRIP_ZONE))
    kwargs.setdefault("cooldown_minutes", 0)
    write_trip(user_id, TRIP, **kwargs)


# ══════════════ AC-1: BEIDE amtlichen Pfade rufen denselben Baustein ════════


def test_ac1_beide_amtlichen_pfade_rufen_denselben_baustein(nutzer):
    """AC-1: Ortsvergleich-amtlich UND Trip-amtlich rufen je Lauf mindestens
    einmal ``check_official_alert_gate``. Ein Baustein mit nur EINEM Aufrufer
    waere keine Entdopplung, sondern eine dritte Fassung (Hausmuster S2 AG1/S3)
    — deshalb beides in EINEM Test.

    ROT HEUTE: ``ImportError``.
    """
    from services.alert_gate import check_official_alert_gate  # noqa: F401

    vergleich = nutzer("ac1-compare")
    _preset_schreiben(vergleich)
    with gate_spion() as spion_v:
        compare_official_versand_lauf(vergleich)

    trip = nutzer("ac1-trip")
    _trip_schreiben(trip)
    with gate_spion() as spion_t:
        trip_amtlicher_direktlauf(trip, TRIP)

    assert spion_v.zaehle(GATE) >= 1, (
        f"Ortsvergleich muss den geteilten Baustein rufen: {spion_v.reihenfolge()!r}")
    assert spion_t.zaehle(GATE) >= 1, (
        f"Trip muss den geteilten Baustein rufen: {spion_t.reihenfolge()!r}")


# ═══════════ AC-2: Ruhezeit stoppt VOR der Tages-Obergrenze ════════════════


def test_ac2_ruhezeit_stoppt_vor_der_tages_obergrenze(nutzer):
    """AC-2: Treffen Ruhezeit UND erschoepfte Tages-Obergrenze gleichzeitig zu,
    haelt der Baustein an der Ruhezeit an.

    Zwei unabhaengige Zeugen: der gemeldete ``reason`` (waere bei vertauschter
    Reihenfolge ``REASON_DAILY_LIMIT``) und der Aufrufzaehler. Der
    Kontroll-Aufruf belegt, dass der Zaehler hochgeht — sonst waere „0" die
    Antwort einer toten Naht.

    Mutations-Gegenprobe (Pflicht): Reihenfolge im Baustein vertauschen MUSS
    diesen Test rot machen. ROT HEUTE: ``ImportError``.
    """
    from services.alert_gate import check_official_alert_gate
    from services.alert_log import REASON_DAILY_LIMIT, REASON_QUIET_HOURS

    uid = nutzer("ac2", tier="free")  # Limit 2
    seed_daily_counter(uid, 2)
    quiet_from, quiet_to = _ruhezeit_jetzt(LOCATION_ZONE)

    with zaehlende_tagesgrenze() as zaehler:
        ergebnis = check_official_alert_gate(
            user_id=uid, quiet_from=quiet_from, quiet_to=quiet_to,
            context_label=PRESET, now=datetime.now(timezone.utc), zone=LOCATION_ZONE)

    assert ergebnis.allowed is False, f"Ruhezeit muss sperren: {ergebnis!r}"
    assert ergebnis.reason == REASON_QUIET_HOURS, (
        f"Der Grund muss die ERSTE zutreffende Stufe sein: {ergebnis.reason!r}")
    assert zaehler.aufrufe == 0, (
        f"Tages-Obergrenze darf bei aktiver Ruhezeit nicht geprueft werden, "
        f"{zaehler.aufrufe}x gerufen")

    frei_von, frei_bis = ruhezeit_woanders()
    with zaehlende_tagesgrenze() as kontrolle:
        ergebnis_limit = check_official_alert_gate(
            user_id=uid, quiet_from=frei_von, quiet_to=frei_bis,
            context_label=PRESET, now=datetime.now(timezone.utc), zone=LOCATION_ZONE)
    assert kontrolle.aufrufe >= 1, (
        f"Kontroll-Aufruf: ohne Ruhezeit MUSS geprueft werden ({kontrolle.aufrufe})")
    assert ergebnis_limit.reason == REASON_DAILY_LIMIT, (
        f"Erschoepftes Tagesbudget muss sperren: {ergebnis_limit.reason!r}")


def test_ac2_freie_bahn_wird_durchgelassen(nutzer):
    """AC-2 (Gegenprobe): Ohne Ruhezeit und mit freiem Tagesbudget laesst der
    Baustein durch und nennt keinen Grund. Ohne diese Haelfte waere ein
    Baustein, der ALLES sperrt, formal AC-konform — Risiko R-A: der Lauf bliebe
    komplett stumm, ohne dass ein Abruf noch Symptome hinterliesse.

    ROT HEUTE: ``ImportError``.
    """
    from services.alert_gate import check_official_alert_gate

    uid = nutzer("ac2-frei", tier="free")
    quiet_from, quiet_to = ruhezeit_woanders()
    ergebnis = check_official_alert_gate(
        user_id=uid, quiet_from=quiet_from, quiet_to=quiet_to,
        context_label=PRESET, now=datetime.now(timezone.utc), zone=LOCATION_ZONE)

    assert ergebnis.allowed is True, f"Ohne Sperre muss durchgelassen werden: {ergebnis!r}"
    assert ergebnis.reason is None, f"Kein Sperrgrund erwartet: {ergebnis.reason!r}"


# ═══ AC-3: „amtlich hat keinen Cooldown" ist Eigenschaft der Funktion ═══════


def test_ac3_baustein_kennt_keinen_cooldown_parameter():
    """AC-3: Die Parameterliste enthaelt keinen Cooldown-/Sperrzeit-Parameter.

    Kein Stil-, sondern ein Sicherheitskriterium: haette die Funktion einen,
    muesste jede Aufrufstelle daran denken, ``None`` zu uebergeben — und die
    Verletzung dieser Disziplin bedeutet „amtliche Warnung bleibt aus". Die
    zweite Haelfte verlangt die Stufen-Parameter, sonst waere eine Funktion ohne
    jeden Parameter formal AC-konform.

    ROT HEUTE: ``ImportError``.
    """
    import inspect

    from services.alert_gate import check_official_alert_gate

    namen = list(inspect.signature(check_official_alert_gate).parameters)
    verboten = [n for n in namen
                if any(t in n.lower() for t in ("cooldown", "throttle", "sperr"))]

    assert verboten == [], (
        f"Kein Cooldown-/Sperrzeit-Parameter erlaubt — gefunden {verboten!r} "
        f"(alle: {namen!r})")
    for pflicht in ("user_id", "quiet_from", "quiet_to", "now", "zone"):
        assert pflicht in namen, f"Pflicht-Parameter {pflicht!r} fehlt: {namen!r}"


# ══════ AC-9: der Stilllegungs-Riegel bleibt AUSSERHALB des Bausteins ══════


def test_ac9_stillgelegtes_preset_erreicht_den_baustein_gar_nicht(nutzer):
    """AC-9: Bei einem stillgelegten Preset (``is_silenced``) wird
    ``check_official_alert_gate`` gar nicht erst gerufen.

    Risiko R-C: zieht jemand ``is_silenced`` spaeter „vereinheitlichend" in den
    Baustein, aendert sich still das TRIP-Verhalten — Trips kennen das Konzept
    nicht, und ein pausierter Trip soll weiter alarmieren (#995, s. AC-10). Der
    Kontroll-Nutzer belegt, dass der Zaehler hier hochgeht.

    ROT HEUTE: ``ImportError``.
    """
    from services.alert_gate import check_official_alert_gate  # noqa: F401

    still = nutzer("ac9-still")
    _preset_schreiben(still, paused_at="2026-08-01T00:00:00Z")
    with gate_spion() as spion_still:
        compare_official_versand_lauf(still)

    aktiv = nutzer("ac9-aktiv")
    _preset_schreiben(aktiv)
    with gate_spion() as spion_aktiv:
        compare_official_versand_lauf(aktiv)

    assert spion_aktiv.zaehle(GATE) >= 1, (
        f"Kontroll-Lauf: aktives Preset MUSS den Baustein erreichen: "
        f"{spion_aktiv.reihenfolge()!r}")
    assert spion_still.zaehle(GATE) == 0, (
        f"Stillgelegtes Preset darf den Baustein nicht erreichen — der Riegel "
        f"wirkt VOR allem anderen: {spion_still.reihenfolge()!r}")


# ════════ AC-12: Gate VOR der Briefing-Sperre, in BEIDEN Pfaden ═══════════


def test_ac12_gate_laeuft_vor_der_briefing_sperre_in_beiden_pfaden(nutzer):
    """AC-12: In BEIDEN amtlichen Pfaden laeuft ``check_official_alert_gate``
    als erste Stufe und ``check_briefing_imminent`` unmittelbar danach — als
    weiterhin EIGENER Aufruf, nicht in den Baustein verschmolzen.

    ``trip_alert.py:1487-1490`` haelt seit #1594 fest, dass die Briefing-Sperre
    „dieselbe Stufe wie im Aenderungspfad, gleiche Position (nach der Ruhezeit)"
    einnimmt. Weil die Ruhezeit jetzt IM Baustein sitzt, wuerde ein Gate-Aufruf
    NACH der Briefing-Sperre diese Festlegung still umdrehen. Gemessen zur
    LAUFZEIT — ein Quellcode-Grep saehe beide Aufrufe und koennte ihre
    Reihenfolge nicht belegen.

    Mutations-Gegenprobe (Pflicht): die beiden Aufrufe vertauschen MUSS diesen
    Test rot machen. ROT HEUTE: aufgezeichnet wird nur ``check_briefing_imminent``.
    """
    from services.alert_gate import check_official_alert_gate  # noqa: F401

    vergleich = nutzer("ac12-compare")
    _preset_schreiben(vergleich)
    with gate_spion() as spion_v:
        compare_official_versand_lauf(vergleich)

    trip = nutzer("ac12-trip")
    _trip_schreiben(trip)
    with gate_spion() as spion_t:
        trip_amtlicher_direktlauf(trip, TRIP)

    assert spion_v.reihenfolge()[:2] == [GATE, BRIEFING], (
        f"Ortsvergleich: erwartet {[GATE, BRIEFING]!r}, aufgezeichnet "
        f"{spion_v.reihenfolge()!r}")
    assert spion_t.reihenfolge()[:2] == [GATE, BRIEFING], (
        f"Trip: erwartet {[GATE, BRIEFING]!r}, aufgezeichnet "
        f"{spion_t.reihenfolge()!r}")


def test_ac12b_erschoepftes_kontingent_und_briefing_lassen_den_zaehler_in_ruhe(nutzer):
    """AC-12b (Regressionswaechter): Tages-Obergrenze UND Briefing-Vorlauf
    gleichzeitig — nichts wird zugestellt, der Tageszaehler bleibt exakt gleich.
    Das belegt, dass das Vorziehen der Tages-Obergrenze VOR die Briefing-Sperre
    wirkungsfrei ist (``is_allowed()`` rein lesend, gebucht wird per
    ``increment()`` erst nach erfolgreicher Zustellung).

    Der zweite Fall (freies Kontingent, Briefing steht an) stellt aus dem
    ANDEREN Grund nichts zu; ohne ihn liessen sich die Gruende nicht trennen.
    """
    beides = nutzer("ac12b-beides", tier="free")
    seed_daily_counter(beides, 2)
    _preset_schreiben(beides, morgen_stunde=_nah())
    vorher_b = read_daily_counter(beides)
    sent_b, mails_b = compare_official_versand_lauf(beides)

    nur_briefing = nutzer("ac12b-briefing", tier="free")
    seed_daily_counter(nur_briefing, 0)
    _preset_schreiben(nur_briefing, morgen_stunde=_nah())
    vorher_n = read_daily_counter(nur_briefing)
    sent_n, mails_n = compare_official_versand_lauf(nur_briefing)

    assert (sent_b, mails_b) == (0, []), (
        f"Erschoepftes Kontingent + Briefing: nichts darf raus ({sent_b}, {mails_b!r})")
    assert read_daily_counter(beides) == vorher_b, (
        f"Gesperrter Lauf darf den Zaehler nicht aendern: {vorher_b} -> "
        f"{read_daily_counter(beides)}")
    assert (sent_n, mails_n) == (0, []), (
        f"Freies Kontingent, aber Briefing steht an: Sperre greift "
        f"({sent_n}, {mails_n!r})")
    assert read_daily_counter(nur_briefing) == vorher_n, (
        f"Auch die Briefing-Sperre darf nichts buchen: {vorher_n} -> "
        f"{read_daily_counter(nur_briefing)}")


# ════════════════════════ AC-16: Mandantentrennung ════════════════════════


def test_ac16_erschoepftes_kontingent_wirkt_nicht_ueber_die_nutzergrenze(nutzer):
    """AC-16 (Regressionswaechter): Zwei Nutzer mit DERSELBEN Preset-Kennung —
    das erschoepfte Tagesbudget von A darf B nicht sperren.

    Risiko R-A in seiner haesslichsten Form: faellt die Nutzer-Aufloesung im
    neuen Baustein still auf ``"default"`` zurueck, teilen sich alle Nutzer einen
    Zaehler; der erste erschoepft ihn, alle uebrigen bleiben stumm — ohne jede
    Fehlermeldung. Nachweis mit ZWEI Datenverzeichnissen ist Pflicht (CLAUDE.md).
    """
    a, b = nutzer("ac16-a", tier="free"), nutzer("ac16-b", tier="free")
    for uid in (a, b):
        _preset_schreiben(uid)  # gleiche Preset-Kennung
    seed_daily_counter(a, 2)
    seed_daily_counter(b, 0)

    sent_a, mails_a = compare_official_versand_lauf(a)
    sent_b, mails_b = compare_official_versand_lauf(b)

    assert (sent_a, mails_a) == (0, []), (
        f"A hat sein Tagesbudget aufgebraucht: sent={sent_a}, Mails={mails_a!r}")
    assert sent_b >= 1 and len(mails_b) >= 1, (
        f"Das Tagesbudget von A darf B — gleiche Kennung, anderes Konto — NICHT "
        f"sperren: sent={sent_b}, Mails={len(mails_b)}")
    assert read_daily_counter(a) == 2 and read_daily_counter(b) == 1, (
        f"Zaehlerstaende: A={read_daily_counter(a)} (erwartet 2), "
        f"B={read_daily_counter(b)} (erwartet 1)")
