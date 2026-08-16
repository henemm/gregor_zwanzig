"""TDD RED — Ortsvergleich (amtlich): die Tages-Obergrenze prueft VOR dem
Warnungs-Abruf (Issue #1467 S4a, AC-7, AC-8, AC-17).

SPEC:    docs/specs/modules/rework_1467_s4a_amtlich.md
KONTEXT: docs/context/rework-1467-s4a-amtlich.md

Heute steht die Tages-Obergrenze in ``compare_official_alert.py:164`` — also
NACH ``_detect()`` (``:159``). Ein erschoepftes Kontingent kostet damit
trotzdem einen vollstaendigen Warnungs-Abruf gegen eine Quelle, die produktiv
bereits an ihr Tageslimit stoesst (``warn_service_consumption.md:22-28``:
„liefert in Prod dauerhaft HTTP 429"; ``fix_1397_meteoalarm_coverage_budget.md``:
gemessen ~160 Abrufe je rollierender 24 h bei Tagesbudget 100).

Gemessen wird an der ABRUF-Naht, nicht am Ausbleiben der Zustellung: eine
Sperre, die erst nach dem Abruf greift, sieht fuer den Nutzer gleich aus, kostet
aber weiter Kontingent — genau der Unterschied, den E2 herstellt. Die Zaehl-Naht
liegt doppelt: ``_detect()`` (die Methode, die ``get_official_alerts_for_location``
ruft) UND die Quelle selbst (``fetch_calls``); jeder Test fuehrt einen
Kontroll-Lauf, in dem beide beweisbar hochgehen.

Mock-frei: echte Presets/Orte auf Platte, echte Warnquelle in der Registry
(kein Netz), echter Tageszaehler; die zaehlende Unterklasse ruft die ECHTE
Fassung (``super()._detect(...)``) auf. Pfadregel #1409.
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
    LOCATION_ZONE, FakeOfficialAlertSource, clean_uid, compare_preset, fresh_uid,
    nur_diese_warnquelle, ruhezeit_woanders, settings_email_only, stunde_versetzt,
    write_location, write_presets, write_user_tier,
)
from tests.helpers.nowcast_gate_fixtures import (  # noqa: E402
    read_daily_counter, seed_daily_counter,
)

PRESET = "cp-1467s4a-limit"
ORT = "loc-1467s4a-limit"


@pytest.fixture
def nutzer():
    vergeben: list[str] = []

    def _neu(kennung: str, tier: str = "free") -> str:
        user_id = fresh_uid(f"s4a-limit-{kennung}")
        clean_uid(user_id)
        write_user_tier(user_id, tier)
        write_location(user_id, ORT)
        vergeben.append(user_id)
        return user_id

    yield _neu
    for user_id in vergeben:
        clean_uid(user_id)


def _preset_schreiben(user_id: str) -> None:
    write_presets(user_id, [compare_preset(
        PRESET,
        morgen_stunde=stunde_versetzt(5, zone=LOCATION_ZONE),  # Briefing weit weg
        quiet=ruhezeit_woanders(), location_ids=[ORT],
    )])


class _Abruflauf:
    def __init__(self, detect_aufrufe: int, quellen_abrufe: int, sent: int, mails: list):
        self.detect_aufrufe = detect_aufrufe
        self.quellen_abrufe = quellen_abrufe
        self.sent = sent
        self.mails = mails

    def __repr__(self) -> str:  # pragma: no cover - nur fuer Fehlermeldungen
        return (f"<Lauf detect={self.detect_aufrufe} quelle={self.quellen_abrufe} "
                f"sent={self.sent} mails={len(self.mails)}>")


def _lauf_mit_abrufzaehlern(user_id: str) -> _Abruflauf:
    """Echter ``check_all_compare_presets()``-Lauf mit gezaehlter Abruf-Naht.

    Die Unterklasse ersetzt nichts — sie zaehlt und delegiert an die echte
    Fassung; der Abruf laeuft damit wirklich durch
    ``get_official_alerts_for_location()``.
    """
    from services.compare_official_alert import CompareOfficialAlertService

    class _Zaehlend(CompareOfficialAlertService):
        detect_aufrufe = 0

        def _detect(self, preset_id, locs, sources=None):
            type(self).detect_aufrufe += 1
            return super()._detect(preset_id, locs, sources)

    _Zaehlend.detect_aufrufe = 0
    mails: list = []
    quelle = FakeOfficialAlertSource()
    with nur_diese_warnquelle(quelle):
        sent = _Zaehlend(
            settings=settings_email_only(), user_id=user_id,
            mail_sink=lambda subject, body: mails.append((subject, body)),
        ).check_all_compare_presets()
    return _Abruflauf(_Zaehlend.detect_aufrufe, quelle.fetch_calls, sent, mails)


# ════ AC-7: erschoepftes Kontingent kostet keinen Warnungs-Abruf mehr ═══════


def test_ac7_erschoepftes_tageslimit_loest_keinen_warnungs_abruf_aus(nutzer):
    """AC-7: Ist die Tages-Obergrenze erreicht, wird ``_detect()`` — und damit
    ``get_official_alerts_for_location`` — gar nicht mehr gerufen.

    Der Kontroll-Nutzer mit freiem Kontingent belegt im selben Test, dass beide
    Zaehler hochgehen koennen; ohne ihn koennte „0 Abrufe" auch heissen, dass
    die Naht tot ist.

    Mutations-Gegenprobe (Pflicht): die Reihenfolge zurueckdrehen (Abruf vor
    Gate) MUSS diesen Test rot machen.

    ROT HEUTE: die Tages-Obergrenze steht bei ``:164``, also NACH ``_detect()``
    (``:159``) — der Abruf laeuft, das Kontingent wird trotzdem verbraucht.
    """
    erschoepft = nutzer("ac7-voll")
    _preset_schreiben(erschoepft)
    seed_daily_counter(erschoepft, 2)  # free -> Limit 2

    frei = nutzer("ac7-frei")
    _preset_schreiben(frei)
    seed_daily_counter(frei, 0)

    lauf_voll = _lauf_mit_abrufzaehlern(erschoepft)
    lauf_frei = _lauf_mit_abrufzaehlern(frei)

    assert lauf_frei.detect_aufrufe >= 1 and lauf_frei.quellen_abrufe >= 1, (
        f"Kontroll-Lauf: bei freiem Kontingent MUSS abgerufen werden, sonst "
        f"messen die Zaehler eine tote Naht — {lauf_frei!r}")
    assert lauf_voll.detect_aufrufe == 0, (
        f"Bei erschoepftem Tageslimit darf die Warnungs-Erkennung gar nicht "
        f"laufen, es waren {lauf_voll.detect_aufrufe} Aufrufe")
    assert lauf_voll.quellen_abrufe == 0, (
        f"Bei erschoepftem Tageslimit darf keine Warnquelle abgefragt werden, "
        f"es waren {lauf_voll.quellen_abrufe} Abrufe")
    assert (lauf_voll.sent, lauf_voll.mails) == (0, []), (
        f"Bei erschoepftem Tageslimit darf nichts zugestellt werden: {lauf_voll!r}")


# ═════ AC-8: bei freiem Kontingent aendert das Vorziehen gar nichts ═════════


def test_ac8_freies_kontingent_stellt_unveraendert_zu(nutzer):
    """AC-8 (Regressionswaechter): Mit freiem Kontingent wird die neue bzw.
    eskalierte amtliche Warnung unveraendert zugestellt — und der Tageszaehler
    genau um eins erhoeht.

    Gegenrichtung zu Risiko R-A: eine falsch verdrahtete Zone oder ein falsch
    gelesener Zaehlerstand im neuen Gate liesse den Lauf komplett stumm werden,
    und zwar OHNE dass ueberhaupt noch ein Abruf Symptome hinterliesse.
    """
    uid = nutzer("ac8")
    _preset_schreiben(uid)
    seed_daily_counter(uid, 0)

    lauf = _lauf_mit_abrufzaehlern(uid)

    assert lauf.sent >= 1 and len(lauf.mails) >= 1, (
        f"Bei freiem Kontingent muss zugestellt werden: {lauf!r}")
    assert read_daily_counter(uid) == 1, (
        f"Nach erfolgreicher Zustellung muss der Tageszaehler auf 1 stehen, "
        f"steht auf {read_daily_counter(uid)}")


# ══════════ AC-17: ``_day_window_end()`` bleibt komplett unberuehrt ═════════

#: SHA-256 des Quelltexts von ``CompareOfficialAlertService._day_window_end``,
#: erhoben am 2026-08-16 gegen den Stand VOR dieser Scheibe (Basis ``098226ae``).
#: Ein einziges geaendertes Zeichen — auch Einrueckung oder Kommentar — bricht
#: diesen Waechter. Genau das ist gewollt: die Methode ist ausdruecklich
#: Nicht-Ziel (R-E), und ihr Abendverhalten haelt sonst kein Test.
DAY_WINDOW_END_HASH_VOR_S4A = (
    "01c0741eba359d1d9aab55c017c609c88deb5fac3d65b8844d96cc8807beae99"
)


def _day_window_end_hash() -> str:
    import hashlib
    import inspect

    from services.compare_official_alert import CompareOfficialAlertService

    quelltext = inspect.getsource(CompareOfficialAlertService._day_window_end)
    return hashlib.sha256(quelltext.encode("utf-8")).hexdigest()


def test_ac17_day_window_end_bleibt_zeichengleich_unveraendert():
    """AC-17 (Regressionswaechter): ``_day_window_end()`` ist textidentisch
    unveraendert.

    Wandert die Methode beim Umbau versehentlich mit — etwa weil jemand ihre
    Preset-Suche auf den neuen geteilten Helfer umstellt —, verliert der Nutzer
    nach Fensterende Ortszeit seine Warnungen (nullbreites Fenster, R-E). Der
    Hash ist hier kein Dateiinhalt-Check als Verhaltensnachweis, sondern die von
    AC-17 verlangte Unveraenderlichkeits-Zusicherung; der Verhaltensfall
    darunter traegt die fachliche Aussage.
    """
    assert _day_window_end_hash() == DAY_WINDOW_END_HASH_VOR_S4A, (
        f"``_day_window_end()`` wurde veraendert — ausdrueckliches Nicht-Ziel "
        f"dieser Scheibe. Erwartet {DAY_WINDOW_END_HASH_VOR_S4A!r}, erhalten "
        f"{_day_window_end_hash()!r}")


def test_ac17_fenster_nach_fensterende_bleibt_nullbreit(nutzer):
    """AC-17 (Verhaltensfall): Liegt das Ende des Tagesfensters bereits hinter
    dem Abrufzeitpunkt, liefert ``_day_window_end()`` unveraendert ``now`` — ein
    nullbreites Fenster ``[now, now]``.

    Der Zeitpunkt wird als PARAMETER uebergeben statt die Systemuhr zu stellen:
    so ist der Fall zu jeder Tageszeit derselbe, und ein Rueckfall auf die
    Systemuhr im Pruefling wuerde sichtbar.
    """
    from app.loader import load_all_locations
    from services.compare_official_alert import CompareOfficialAlertService

    uid = nutzer("ac17")
    _preset_schreiben(uid)

    dienst = CompareOfficialAlertService(settings=settings_email_only(), user_id=uid)
    ort = next(loc for loc in load_all_locations(user_id=uid) if loc.id == ORT)

    # 20:30 Ortszeit (Europe/Vienna) — nach dem ADR-0035-Default-Fensterende 19.
    abends_lokal = (datetime.now(timezone.utc).astimezone(LOCATION_ZONE)
                    .replace(hour=20, minute=30, second=0, microsecond=0))
    abends = abends_lokal.astimezone(timezone.utc)

    ende = dienst._day_window_end(PRESET, ort, abends)
    assert ende == abends, (
        f"Nach dem Fensterende muss auf ``now`` geklemmt werden (nullbreites "
        f"Fenster), erhalten {ende.isoformat()} fuer now={abends.isoformat()}")

    mittags = abends_lokal.replace(hour=10, minute=0).astimezone(timezone.utc)
    ende_mittags = dienst._day_window_end(PRESET, ort, mittags)
    assert ende_mittags > mittags + timedelta(hours=1), (
        f"Mitten im Tagesfenster muss ein echtes, breites Fenster entstehen, "
        f"erhalten {ende_mittags.isoformat()} fuer now={mittags.isoformat()}")
