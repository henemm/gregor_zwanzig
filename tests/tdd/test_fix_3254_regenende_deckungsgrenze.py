"""TDD RED — Issue #3254: Regen-Ende = Ende des letzten nassen Zeitabschnitts.

SPEC: docs/specs/modules/fix_3254_regenende_deckungsgrenze.md — AC-1 bis AC-6.

Nutzersicht: ein kurzer Schauer (ein einziger nasser 15-Minuten-Abschnitt
16:45, danach trocken) kam als `Aabenraa: R@16:45@16:45` bzw. E-Mail
„ab 16:45 · letzter Regen gegen 16:45“ an. Beginn gleich Ende ist fuer den
Wanderer unlesbar; der Abschnitt 16:45–17:00 endet um 17:00.

Ursache: `_derive_wet_block_end()` gibt beim ersten Trockenframe den
ZEITSTEMPEL (= Abschnitts-Anfang) des letzten nassen Frames zurueck statt
seiner Deckungsgrenze `min(ts + 15 Min, naechster Frame, Horizont)`.

Weg jedes Tests (Wirkort, nicht Baustein allein): echte `RadarFrame`-Reihe
-> echtes `RadarNowcastService._derive_result` (Uhr fest injiziert) ->
`NowcastResult` -> echter Baustein `to_multi_location_onset_alert_message`
(gestellte Uhr per freezegun, keine Wanduhr) -> echte Renderer
`render_sms` / `render_email` / `render_telegram`.

Kein Mock-Theater: kein `Mock()`/`patch()`/`MagicMock`, kein Netz.
"""
from __future__ import annotations

import inspect
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest
from freezegun import freeze_time

from providers.brightsky import RadarFrame
from services.radar_cache import RadarNowcastCacheService
from services.radar_service import RadarNowcastService, _derive_wet_block_end

# Sa 21.11.2026 15:30 UTC = 16:30 Ortszeit Aabenraa (CET, UTC+1).
_NOW = datetime(2026, 11, 21, 15, 30, tzinfo=timezone.utc)
_UHR = _NOW.isoformat()
_ZONE = "Europe/Copenhagen"
AABENRAA = SimpleNamespace(lat=55.04, lon=9.42, timezone=_ZONE)
SONDERBORG = SimpleNamespace(lat=54.91, lon=9.79, timezone=_ZONE)

# 0.3 mm/h: unter der Mengen-Anzeigeschwelle der Kurzform (0.1 mm im
# Abschnitt) -> das Token traegt keine Menge und lautet wie im Issue `R@...`.
_NASS = 0.3

# Kurzform-Zeitgruppe: Beginn, optional Untergrenzen-Praefix ` >`, Ende.
_ZEITGRUPPE_RE = re.compile(r"@(\d{1,2}:\d{2})( >)?@(\d{1,2}:\d{2})")


def _frames(nasse_minuten: set[int], raster: int = 15, ende: int = 180) -> list[RadarFrame]:
    """Durchgehendes Raster ab `_NOW`; nass genau in `nasse_minuten`."""
    return [
        RadarFrame(
            timestamp=_NOW + timedelta(minutes=m),
            precip_mm_h=_NASS if m in nasse_minuten else 0.0,
            is_convective=False,
        )
        for m in range(0, ende + 1, raster)
    ]


def _nowcast(frames: list[RadarFrame]):
    svc = RadarNowcastService(cache=RadarNowcastCacheService())
    return svc._derive_result(frames, "radar", now=_NOW)


def _nachricht(*orte):
    """`orte`: Paare `(Ortsname, Ortsobjekt, NowcastResult)`."""
    from app.ampel import resolve_ampel
    from output.renderers.alert.project import to_multi_location_onset_alert_message

    with freeze_time(_UHR):
        return to_multi_location_onset_alert_message(
            list(orte), tz=ZoneInfo(_ZONE), stand_at="16:30",
            ampel=resolve_ampel(None),
        )


def _kurzform(frames: list[RadarFrame]) -> str:
    from output.renderers.alert.render import render_sms

    return render_sms(_nachricht(("Aabenraa", AABENRAA, _nowcast(frames))), limit=140)


def _minuten(hhmm: str) -> int:
    stunde, minute = hhmm.split(":")
    return int(stunde) * 60 + int(minute)


def test_prueling_stammt_aus_diesem_arbeitsbaum():
    """Vorbedingung (kein AC): sonst prueft ein Worktree-Lauf still das
    Hauptrepo und meldet falsches Gruen."""
    from services import radar_service as radar_module

    modul_pfad = Path(inspect.getfile(radar_module)).resolve()
    assert modul_pfad.is_relative_to(Path(__file__).resolve().parents[2])


# ---------------------------------------------------------------------------
# AC-1 — Ein-Abschnitt-Ereignis in der Kurzform
# ---------------------------------------------------------------------------


def test_ac1_ein_abschnitt_kurzform_endet_am_abschnittsende():
    """AC-1 GIVEN 16:45 nass, 17:00 trocken
    WHEN die Kurzform erzeugt wird
    THEN lautet der Text `R@16:45@17:00`, nie `R@16:45@16:45`."""
    sms = _kurzform(_frames({15}))

    assert "R@16:45@16:45" not in sms, f"Beginn gleich Ende: {sms!r}"
    assert sms == "Aabenraa: R@16:45@17:00", sms


# ---------------------------------------------------------------------------
# AC-2 — E-Mail und Telegram nennen dasselbe, spaetere Ende
# ---------------------------------------------------------------------------


def test_ac2_email_und_telegram_letzter_regen_nach_beginn():
    """AC-2 GIVEN dasselbe Ein-Abschnitt-Ereignis
    WHEN E-Mail (HTML und Klartext) und Telegram erzeugt werden
    THEN steht dort „letzter Regen gegen 17:00“, nie „gegen 16:45“."""
    from output.renderers.alert.render import render_email, render_telegram

    msg = _nachricht(("Aabenraa", AABENRAA, _nowcast(_frames({15}))))
    html, plain = render_email(msg)
    telegram = render_telegram(msg)

    for kanal, text in (("E-Mail HTML", html), ("E-Mail Text", plain), ("Telegram", telegram)):
        assert "letzter Regen gegen 16:45" not in text, f"{kanal}: Ende gleich Beginn"
        assert "letzter Regen gegen 17:00" in text, f"{kanal}: {text!r}"


# ---------------------------------------------------------------------------
# AC-3 — Mehrabschnitts-Ereignis
# ---------------------------------------------------------------------------


def test_ac3_mehrere_abschnitte_ende_am_letzten_abschnittsende():
    """AC-3 GIVEN 16:45, 17:00, 17:15 nass, 17:30 trocken
    WHEN `_derive_result` das Ende bestimmt
    THEN liegt es bei 17:30 (= 60 Min nach 16:30), nicht bei 17:15."""
    nc = _nowcast(_frames({15, 30, 45}))

    assert nc.onset_minutes == 15
    assert nc.event_ongoing_beyond_horizon is False
    assert nc.event_end_minutes == 60, nc.event_end_minutes


def test_ac3_feineres_raster_endet_am_naechsten_frame():
    """AC-3 (Deckungsgrenze im 5-Minuten-Raster) GIVEN 16:45 nass, 16:50
    trocken WHEN das Ende bestimmt wird THEN liegt es bei 16:50 — die
    Deckung endet am naechsten Frame, nicht pauschal 15 Min spaeter."""
    nc = _nowcast(_frames({15}, raster=5))

    assert nc.event_end_minutes == 20, nc.event_end_minutes


# ---------------------------------------------------------------------------
# AC-4 — Eigenschaft: Ende stets nach dem Beginn
# ---------------------------------------------------------------------------


_REIHEN = {
    "einzelabschnitt": _frames({15}),
    "mehrfachabschnitt": _frames({15, 30, 45}),
    "einzelabschnitt_5min": _frames({15}, raster=5),
    "spaeter_einzelabschnitt": _frames({90}),
    "luecke": [f for f in _frames({15}) if f.timestamp != _NOW + timedelta(minutes=30)],
    "horizont": _frames(set(range(15, 181, 15))),
}


@pytest.mark.parametrize("name", sorted(_REIHEN))
def test_ac4_ende_liegt_stets_nach_dem_beginn(name):
    """AC-4 GIVEN Ereignisse mit bekanntem Ende (Einzelabschnitt,
    Mehrfachabschnitt, feines Raster, Luecke, Horizont)
    WHEN die Kurzform erzeugt wird
    THEN liegt das Ende stets nach dem Beginn, nie dieselbe Uhrzeit."""
    sms = _kurzform(_REIHEN[name])
    treffer = _ZEITGRUPPE_RE.search(sms)

    assert treffer, f"{name}: keine Beginn/Ende-Gruppe in {sms!r}"
    beginn, _, ende = treffer.groups()
    assert _minuten(ende) > _minuten(beginn), f"{name}: {sms!r}"


def test_ac4_rest_rueckgabe_ohne_nassen_frame_liegt_nach_dem_beginn():
    """AC-4 (Rest-Rueckgabe) GIVEN ein Beginn ohne Frame im Fenster
    WHEN `_derive_wet_block_end` das Ende bestimmt
    THEN ist es die Deckungsgrenze des Beginn-Frames (Beginn + 15 Min),
    nicht der Beginn selbst."""
    beginn = _NOW + timedelta(minutes=15)
    horizont = _NOW + timedelta(minutes=180)

    ende, laufend = _derive_wet_block_end([], [], beginn, horizont)

    assert ende == beginn + timedelta(minutes=15)
    assert laufend is False


# ---------------------------------------------------------------------------
# AC-5 — Horizont-Form bleibt
# ---------------------------------------------------------------------------


def test_ac5_horizont_bleibt_untergrenzen_form():
    """AC-5 GIVEN Regen von 16:45 bis an den Rand der Radarvorhersage
    (19:30) WHEN die Kurzform erzeugt wird THEN bleibt die Form
    „mindestens bis“ ` >@19:30` erhalten."""
    sms = _kurzform(_frames(set(range(15, 181, 15))))

    # Die Stunde Regen ab Beginn ergibt hier eine Menge (`R0.3`) — sie ist
    # nicht Gegenstand von AC-5, geprueft wird allein die Ende-Form.
    assert re.fullmatch(r"Aabenraa: R[0-9.]*@16:45 >@19:30\??", sms), sms


# ---------------------------------------------------------------------------
# AC-6 — Mehrort-Kurzform
# ---------------------------------------------------------------------------


def test_ac6_mehrort_kurzform_jeder_ort_ende_nach_beginn():
    """AC-6 GIVEN zwei Orte mit kurzen Schauern (Aabenraa 16:45, Sonderborg
    17:15, je ein Abschnitt) WHEN die Mehrort-Kurzform erzeugt wird
    THEN traegt jeder Ort ein Ende nach seinem Beginn."""
    from output.renderers.alert.render import render_sms

    msg = _nachricht(
        ("Aabenraa", AABENRAA, _nowcast(_frames({15}))),
        ("Sonderborg", SONDERBORG, _nowcast(_frames({45}))),
    )
    sms = render_sms(msg, limit=140, location_positions={"Aabenraa": 1, "Sonderborg": 2})

    assert sms == "1:R@16:45@17:00 2:R@17:15@17:30", sms
