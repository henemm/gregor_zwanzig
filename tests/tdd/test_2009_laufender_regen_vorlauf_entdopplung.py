"""TDD RED — Issue #2009 (Nachmessung): Entdopplung eines laufenden Regens.

SPEC: docs/specs/modules/fix_2009_laufender_regen_vorlauf.md
      (Waechter 3 = AC-3, Waechter 4 = AC-4)

Die Identitaet eines Ereignisses haengt an seinem Anker (`event_at` bzw.
`point_at` der Ereignis-Identitaet, `alert_gate.py`). Wandert der Anker bei
laufendem Regen je Lauf zum naechsten Viertelstundenpunkt, sieht die
Entdopplung nach genuegend Laeufen ein "neues" Ereignis. Diese Waechter
messen die Wirkung, nicht den Anker: Anzahl tatsaechlich gesendeter Alarme
ueber eine Folge echter Laeufe.

Die Sperrzeit ist AUS (Trip `alert_cooldown_minutes = 0`, Preset
`alert_cooldown_minutes = 0`) -- sonst entschiede die Sperrzeit statt der
Entdopplung, und der Waechter waere aus dem falschen Grund gruen (Muster
`test_alarm_szenario_laufendes_ereignis.py::test_ac11_...`). Positivkontrollen
auf frischem Datentraeger belegen, dass jede Stille von der Entdopplung kommt.

Kein Mock()/patch(): echter `check_radar_alerts()` ueber die
`AlarmPruefstrecke` bzw. echter `CompareRadarAlertService`, Frames ueber die
DI-Naht `frame_source=` eines echten `RadarNowcastService`. Gestellte Uhr,
Ort Reykjavik (ganzjaehrig UTC+0, Ortszeit == UTC), Ganztags-Etappe.
"""
from __future__ import annotations

import uuid
from datetime import datetime, time, timedelta, timezone

import pytest
from freezegun import freeze_time

from app.loader import save_location
from services.radar_service import RadarNowcastService

from tests.helpers.alarm_pruefstrecke import AlarmPruefstrecke
from tests.helpers.nowcast_gate_fixtures import (
    clean_uid, compare_radar_service, location, radar_preset, reset_radar_cache,
    save_trip, settings_email_only, write_presets, write_user_tier,
)
from tests.helpers.radar_vorlauf_strecke import ETAPPE_GANZTAGS, baue_trip

# Bezugstag mittags-nah, weit weg von jeder Tagesgrenze (Reykjavik, UTC+0).
_TAG = datetime(2026, 8, 11, tzinfo=timezone.utc)
_REGEN_VON = _TAG.replace(hour=10)                     # 10:00 UTC
_REGEN_BIS = _REGEN_VON + timedelta(hours=4)           # 14:00 UTC (exklusiv)
# Takt `3-58/5`: 10:03, 10:08, ..., 13:58 -- 48 Laeufe ueber den Regen.
_TAKT = [
    _REGEN_VON + timedelta(minutes=3 + 5 * i)
    for i in range(48)
]

_ANGELEGT: list[str] = []


@pytest.fixture(autouse=True)
def _aufraeumen():
    _ANGELEGT.clear()
    yield
    for uid in _ANGELEGT:
        clean_uid(uid)


def _uid(tag: str) -> str:
    uid = f"tdd-2009-dedup-{tag}-{uuid.uuid4().hex[:6]}"
    _ANGELEGT.append(uid)
    return uid


def _vier_stunden_regen(lat: float, lon: float) -> list:
    """INCA-Raster (15 Min) von 09:45 bis 17:45, nass genau in
    [10:00, 14:00) -- ein ueber vier Stunden andauerndes Ereignis."""
    from providers.brightsky import RadarFrame
    anker = _REGEN_VON - timedelta(minutes=15)
    return [
        RadarFrame(
            timestamp=anker + timedelta(minutes=15 * k),
            precip_mm_h=2.0 if _REGEN_VON <= anker + timedelta(minutes=15 * k) < _REGEN_BIS else 0.0,
        )
        for k in range(33)
    ]


# Waechter 4: um 1 Min versetztes Raster (:01/:16/...), damit "Regen kommt in
# 8 Min" im Takt `3-58/5` erreichbar ist (gegen :00/:15 nur 2/7/12).
_W4_ANKER = _REGEN_VON + timedelta(minutes=1)          # 10:01, trocken
_W4_BEGINN = _W4_ANKER + timedelta(minutes=15)         # 10:16, nass
_W4_LAUF1 = _REGEN_VON + timedelta(minutes=8)          # 10:08 -> "kommt in 8"
_W4_LAUF2 = _REGEN_VON + timedelta(minutes=18)         # 10:18 -> "laeuft"


def _kommt_dann_laeuft(lat: float, lon: float) -> list:
    from providers.brightsky import RadarFrame
    return [
        RadarFrame(
            timestamp=_W4_ANKER + timedelta(minutes=15 * k),
            precip_mm_h=2.0 if 1 <= k <= 8 else 0.0,
        )
        for k in range(16)
    ]


# ─────────────────────────────── Trip-Pfad ──────────────────────────────────


class _TripStrecke:
    """Ein Nutzer, ein Trip (Ganztags-Etappe, Sperrzeit aus), EINE
    Pruefstrecke ueber alle Laeufe -- die Kontinuitaet traegt der
    Datentraeger wie in Produktion."""

    def __init__(self, tag: str, quelle) -> None:
        self.uid = _uid(tag)
        clean_uid(self.uid)
        self.trip = baue_trip(self.uid, ETAPPE_GANZTAGS, at=_REGEN_VON)
        self.trip.alert_cooldown_minutes = 0
        # Briefing-Zeiten ausserhalb des gesamten Messzeitraums (10-14 UTC),
        # sonst misst der Waechter die Briefing-Naehe-Sperre (#1594).
        self.trip.report_config.morning_time = time(5, 0)
        self.trip.report_config.evening_time = time(21, 0)
        with freeze_time(_REGEN_VON):
            save_trip(self.trip, self.uid)
        self._quelle = quelle
        self._strecke = AlarmPruefstrecke(user_id=self.uid, settings=settings_email_only())

    def lauf(self, at: datetime) -> int:
        return self._strecke.lauf(
            at=at, zweig="radar", trip=self.trip,
            radar_service=RadarNowcastService(frame_source=self._quelle),
        ).triggered_count


# ─────────────────────────── Ortsvergleichs-Pfad ────────────────────────────


class _OrtsvergleichStrecke:
    def __init__(self, tag: str, quelle) -> None:
        self.uid = _uid(tag)
        clean_uid(self.uid)
        self.preset_id = f"cp-{self.uid}"
        with freeze_time(_REGEN_VON):
            write_user_tier(self.uid, "premium")
            save_location(location("loc-2009", "Dauerregen-Ort"), user_id=self.uid)
            write_presets(self.uid, [radar_preset(
                self.preset_id, ["loc-2009"], user_id=self.uid, cooldown_minutes=0,
            )])
        self._quelle = quelle

    def lauf(self, at: datetime) -> int:
        with freeze_time(at):
            reset_radar_cache()
            gesendet = compare_radar_service(
                self.uid, settings_email_only(), self._quelle,
                lambda subject, body: None,
            ).check_all_compare_presets()
        reset_radar_cache()
        return gesendet


_PFADE = {"trip": _TripStrecke, "ortsvergleich": _OrtsvergleichStrecke}


# ═══════════════════════════ Waechter 3 (AC-3) ═════════════════════════════


@pytest.mark.parametrize("pfad", sorted(_PFADE))
def test_waechter3_vier_stunden_laufender_regen_hoechstens_ein_alarm_je_drei_stunden(pfad):
    """AC-3 (neu gefasst, PO-Entscheid 2026-11-08): Regen dauert vier
    Stunden, Laeufe alle 5 Minuten (48 Laeufe im Takt `3-58/5`) -> innerhalb
    von 3 Stunden hoechstens EIN Alarm, nicht einer je Lauf, im Trip und im
    Ortsvergleich; insgesamt nicht mehr Alarme als vor der Korrektur (heute 2:
    10:03 und 13:18).

    Schutzpruefung, darf schon heute gruen sein. Ohne Entdopplung (Sperrzeit
    ist hier aus) ginge je Lauf ein Alarm raus -- 48 statt hoechstens 2.

    Hintergrund: die Ereignis-Identitaet vergleicht Punkt gegen Punkt mit
    `NOWCAST_HORIZON_MIN` (180 Min, `alert_gate._times_overlap`); nach drei
    Stunden gilt der laufende Regen deshalb als neues Ereignis. "Genau ein
    Alarm" fuer ein beliebig langes Ereignis (stabiler Anker `running_since`,
    Variante C) ist Folgeticket #2851."""
    strecke = _PFADE[pfad](f"w3-{pfad}", _vier_stunden_regen)
    je_lauf = [(at, strecke.lauf(at)) for at in _TAKT]
    alarme = [at for at, n in je_lauf for _ in range(n)]
    bericht = [at.strftime("%H:%M") for at in alarme]
    assert je_lauf[0][1] == 1, (
        f"AC-3 ({pfad}) Vorbedingung: der erste Lauf (10:03) muss den laufenden "
        f"Regen melden (war {je_lauf[0][1]})."
    )
    for frueher, spaeter in zip(alarme, alarme[1:]):
        abstand_min = (spaeter - frueher).total_seconds() / 60
        assert abstand_min > 180, (
            f"AC-3 ({pfad}): zwei Alarme fuer denselben laufenden Regen nur "
            f"{abstand_min:.0f} Min auseinander ({frueher:%H:%M} -> "
            f"{spaeter:%H:%M}) -- innerhalb von 3 Stunden ist hoechstens einer "
            f"erlaubt. Gesendet: {bericht}."
        )
    assert len(alarme) <= 2, (
        f"AC-3 ({pfad}): mehr Alarme als vor der Korrektur (hoechstens 2 ueber "
        f"vier Stunden), gesendet {len(alarme)} bei {len(_TAKT)} Laeufen: "
        f"{bericht}."
    )


# ═══════════════════════════ Waechter 4 (AC-4) ═════════════════════════════


@pytest.mark.parametrize("pfad", sorted(_PFADE))
def test_waechter4_kommt_in_acht_dann_laeuft_kein_zweiter_alarm(pfad):
    """AC-4: Lauf 1 (10:08) meldet "Regen kommt in 8 Min" (Beginn 10:16),
    Lauf 2 (10:18) sieht den Regen als laufend -> kein zweiter Alarm.
    Positivkontrolle: die Lage von Lauf 2 loest auf frischem Datentraeger
    selbst aus -- die Stille kommt also von der Entdopplung."""
    strecke = _PFADE[pfad](f"w4-{pfad}", _kommt_dann_laeuft)
    erster = strecke.lauf(_W4_LAUF1)
    assert erster == 1, (
        f"AC-4 ({pfad}) Vorbedingung: Lauf 1 muss 'kommt in 8' melden (war {erster})."
    )
    zweiter = strecke.lauf(_W4_LAUF2)

    kontrolle = _PFADE[pfad](f"w4-{pfad}-ctrl", _kommt_dann_laeuft).lauf(_W4_LAUF2)
    assert kontrolle == 1, (
        f"AC-4 ({pfad}) Positivkontrolle: die laufende Lage um 10:18 muss auf "
        f"frischem Datentraeger ausloesen (war {kontrolle}) -- sonst kaeme die "
        f"Stille nicht von der Entdopplung."
    )
    assert zweiter == 0, (
        f"AC-4 ({pfad}): der Uebergang 'kommt' -> 'laeuft' ist DASSELBE "
        f"Ereignis, ein zweiter Alarm ist eine Doppelmeldung (war {zweiter})."
    )
