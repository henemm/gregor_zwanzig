"""TDD RED -- Issue #1648: der Italien-Zweig der NowCast-Kette laeuft direkt
auf ARPAE ICON-2I; Radar-DPC ist ersatzlos entfernt.

SPEC: docs/specs/modules/fix_1648_radar_dpc_entfernen.md (AC-1, AC-2 + der
verbliebene Bestandsschutz aus #1186).

Vorgeschichte: diese Datei ist die ueberarbeitete Fassung von
`tests/tdd/test_feature_1186_arpae_it_fallback.py` (nach der Namensregel
umbenannt -- Verhalten statt Issue-Nummer). ARPAE war dort ein RUECKFALL
UNTER Radar-DPC; nach #1648 ist es die alleinige Italien-Quelle. Das
bisherige AC-2 ("DPC behaelt Vorrang vor ARPAE") entfaellt ersatzlos.

Warum DPC weg muss: `RadarDPCProvider` lieferte immer genau EIN Bild (eine
SRI-Momentaufnahme, also stets Vergangenheit). `_derive_result` zaehlt nur
Frames mit `timestamp >= now` -- das eine DPC-Bild wurde damit strukturell
IMMER verworfen, und weil DPC `frames` lieferte, wurde der darunterliegende
ARPAE-Zweig nie erreicht. Ergebnis: der Italien-Zweig konnte faktisch nie
einen Radar-Alarm ausloesen. Genau deshalb pruefen AC-1 und AC-2 nicht nur
`source`, sondern ausdruecklich, dass mindestens ein Frame in der ZUKUNFT
liegt -- die Quelle allein umzustellen, ohne dass Zukunfts-Frames ankommen,
waere der gleiche Fehler unter neuem Namen.

Live-Schicht (echte HTTP-Calls gegen Open-Meteo). 🔴 Der `live`-Marker steht
BEWUSST an jedem einzelnen Test, NIE als modulweites `pytestmark`: ein
modulweiter `live`-Marker hebt in diesem Repo die Daten-Isolation der
conftest-Fixtures auf.

KEINE MOCKS. DI erfolgt ausschliesslich durch Ersetzen von Instanz-/
Klassenmethoden mit echten Python-Funktionen und Wiederherstellung im
`finally` -- kein `Mock()`/`patch()`/`MagicMock`.

RED-Erwartung vor der Implementierung: alle Live-Tests liefern `source ==
"DPC"` statt `"ARPAE-2I"`, weil `_fetch_radar_dpc` in der Kette noch vor
`_fetch_italy_arpae` steht und immer Frames zurueckgibt.
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

# sys.path absichern: sowohl `services.*` als auch `src.services.*` Importpfade.
# Pfadregel #1409: relativ zu DIESER Datei, nie ueber einen festen Hauptrepo-Pfad.
_ROOT = Path(__file__).resolve().parents[2]
for _p in (str(_ROOT), str(_ROOT / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# Vizzavona (GR20, Korsika) -- liegt sowohl in der Italien-Radar-Box
# (lat 36.0-47.5 / lon 6.5-19.0) als auch in der AROME-FR-Box
# (lat 41.0-51.5 / lon -5.5-10.0). Die Italien-Box wird in der Kette ZUERST
# geprueft. ARPAE ICON-2I liefert dort echte (nicht-None) Werte -- am
# 2026-08-11 gegen die Live-API nachgemessen (elevation 992 m,
# precipitation-Reihe vollstaendig belegt), der All-None-Guard in
# `_fetch_openmeteo_15` greift also nicht.
_VIZZAVONA_LAT, _VIZZAVONA_LON = 42.1244, 9.1339

# Karnischer Hoehenweg (Spec-Koordinate fuer AC-2).
# ⚠️ Gemessen am Stand 4e5098a7: dieser Punkt liegt NICHT in der INCA-Box
# (_INCA_LAT_MIN = 46.3 > 46.20) -- die Spec bezeichnet ihn als
# "Ueberlappungsgebiet von INCA und Italien-Radar-Box". Der INCA-Ersatz unten
# ist hier deshalb eine Absicherung gegen kuenftige Box-Verschiebungen, nicht
# der tragende Teil. Der tragende Nachweis fuer die Ueberlappung steht im
# Test darunter (_KHW_IT_*).
_KHW_LAT, _KHW_LON = 46.20, 12.85

# Karnischer Hoehenweg, italienische Seite -- echter Ueberlappungspunkt:
# in der INCA-Box (46.3-49.1 / 9.5-17.2) UND in der Italien-Radar-Box.
# Selbe Koordinate wie Zone Tren-A in tests/tdd/test_dpc_bulletin_source.py.
_KHW_IT_LAT, _KHW_IT_LON = 46.7248, 12.2254

# Rom -- in der Italien-Radar-Box, aber ausserhalb AROME-FR (lon 12.5 > 10.0)
# und ausserhalb ICON-D2 (lat 41.9 < 44.0). Faellt bei ARPAE-Ausfall direkt
# auf den globalen `minutely_15`-Fallback durch.
_ROME_LAT, _ROME_LON = 41.90, 12.50


def _assert_has_future_frame(result, label: str) -> None:
    """Kernaussage von #1648: die Italien-Quelle muss den Vertrag der
    NowCast-Kette erfuellen ('was kommt in den naechsten Stunden'). Ein
    Ergebnis ohne einen einzigen Frame mit `timestamp >= now` kann per
    `_derive_result` NIE einen Alarm ausloesen -- genau der Zustand, den
    Radar-DPC erzeugt hat."""
    now = datetime.now(timezone.utc)
    future = [f for f in result.frames if f.timestamp >= now]
    assert future, (
        f"{label}: mindestens ein Frame muss in der Zukunft liegen "
        f"(timestamp >= {now.isoformat()}); erhalten: "
        f"{[f.timestamp.isoformat() for f in result.frames][:5]} "
        f"(insgesamt {len(result.frames)} Frames, source={result.source!r})"
    )


# ===========================================================================
# AC-1: GR20/Vizzavona -- die Kette landet ohne jede DI bei ARPAE-2I
# ===========================================================================

@pytest.mark.live
def test_ac1_gr20_vizzavona_uses_arpae_with_future_frames():
    """AC-1: reale GR20-Koordinate (Vizzavona), `get_nowcast()` OHNE
    Dependency-Injection -- die produktive Quellenkette muss `ARPAE-2I`
    liefern, mindestens einen Frame, und mindestens einen davon in der
    Zukunft.

    RED: heute greift `_within_dpc` zuerst, `_fetch_radar_dpc` liefert genau
    ein Vergangenheitsbild -> `result.source == "DPC"`, und kein einziger
    Frame liegt in der Zukunft.
    """
    from services.radar_service import RadarNowcastService

    result = RadarNowcastService().get_nowcast(_VIZZAVONA_LAT, _VIZZAVONA_LON)

    assert result.source == "ARPAE-2I", (
        f"Vizzavona muss ueber ARPAE ICON-2I laufen (war: {result.source})"
    )
    assert len(result.frames) >= 1, "ARPAE muss mindestens ein Frame liefern"
    _assert_has_future_frame(result, "AC-1 Vizzavona")

    for frame in result.frames:
        assert isinstance(frame.precip_mm_h, (int, float)), (
            f"precip_mm_h muss numerisch sein (war: {frame.precip_mm_h!r})"
        )
        assert frame.precip_mm_h >= 0, (
            f"precip_mm_h darf nicht negativ sein (war: {frame.precip_mm_h})"
        )


# ===========================================================================
# AC-2: INCA liefert leer -> die Kette faellt auf ARPAE-2I, nicht auf eine
# einzelne Vergangenheits-Beobachtung
# ===========================================================================

@pytest.mark.live
def test_ac2_khw_falls_back_to_arpae_when_inca_is_empty():
    """AC-2 (Spec-Koordinate 46.20/12.85): liefert GeoSphere INCA leer
    (echter Instanzmethoden-Ersatz, kein Mock), muss die Kette bei ARPAE-2I
    landen und Zukunfts-Frames liefern.

    RED: heute liefert die Kette an diesem Punkt `"DPC"` mit genau einem
    Vergangenheitsbild.
    """
    from services.radar_service import RadarNowcastService

    def empty_inca(self, lat, lon):
        return []

    orig_inca = RadarNowcastService._fetch_geosphere_inca
    RadarNowcastService._fetch_geosphere_inca = empty_inca
    try:
        result = RadarNowcastService().get_nowcast(_KHW_LAT, _KHW_LON)
    finally:
        RadarNowcastService._fetch_geosphere_inca = orig_inca

    assert result.source == "ARPAE-2I", (
        f"Karnischer Hoehenweg muss bei INCA-Ausfall auf ARPAE ICON-2I fallen "
        f"(war: {result.source})"
    )
    assert len(result.frames) >= 1, "ARPAE muss mindestens ein Frame liefern"
    _assert_has_future_frame(result, "AC-2 KHW 46.20/12.85")


@pytest.mark.live
def test_ac2_real_inca_italy_overlap_point_falls_back_to_arpae():
    """AC-2 (Wirkort): derselbe Nachweis an einem Punkt, der TATSAECHLICH in
    beiden Boxen liegt (46.7248/12.2254, KHW italienische Seite) -- hier ist
    der INCA-Ersatz tragend, weil die Kette ohne ihn bei `"INCA"` stehen
    bliebe. Ergaenzt die Spec-Koordinate, deren Breite (46.20) knapp
    unterhalb von `_INCA_LAT_MIN = 46.3` liegt.

    RED: heute faellt die Kette nach dem leeren INCA auf `"DPC"`.
    """
    from services.radar_service import RadarNowcastService

    def empty_inca(self, lat, lon):
        return []

    orig_inca = RadarNowcastService._fetch_geosphere_inca
    RadarNowcastService._fetch_geosphere_inca = empty_inca
    try:
        result = RadarNowcastService().get_nowcast(_KHW_IT_LAT, _KHW_IT_LON)
    finally:
        RadarNowcastService._fetch_geosphere_inca = orig_inca

    assert result.source == "ARPAE-2I", (
        f"Echter INCA/Italien-Ueberlappungspunkt muss bei INCA-Ausfall auf "
        f"ARPAE ICON-2I fallen (war: {result.source})"
    )
    _assert_has_future_frame(result, "AC-2 KHW-IT 46.7248/12.2254")


# ===========================================================================
# Bestandsschutz aus #1186: ARPAE-Ausfall bleibt fail-soft
# ===========================================================================

@pytest.mark.live
def test_arpae_failure_falls_back_to_global_minutely15():
    """Faellt ARPAE-2I aus (ein einziger Instanzmethoden-Ersatz -> `[]`, seit
    #1648 ist kein zweiter DPC-Stub mehr noetig), faellt die Kette fuer eine
    Koordinate ausserhalb AROME-FR/ICON-D2 (Rom) fail-soft auf
    `source == "minutely_15"` zurueck, ohne Absturz.

    RED: heute greift vor ARPAE noch `_fetch_radar_dpc` und liefert `"DPC"`.
    """
    from services.radar_service import RadarNowcastService

    def empty_arpae(self, lat, lon):
        return []

    orig_arpae = RadarNowcastService._fetch_italy_arpae
    RadarNowcastService._fetch_italy_arpae = empty_arpae
    try:
        result = RadarNowcastService().get_nowcast(_ROME_LAT, _ROME_LON)
    finally:
        RadarNowcastService._fetch_italy_arpae = orig_arpae

    assert result.source == "minutely_15", (
        f"Bei ARPAE-Ausfall muss die Kette fail-soft auf den globalen "
        f"Fallback zurueckfallen (war: {result.source})"
    )


# ===========================================================================
# Bestandsschutz aus #1186 (Kern-Schicht): transparentes Quellen-Label
# ===========================================================================

def test_source_label_for_arpae_is_transparent():
    """Pure-Function-Test (kein Netz, KEIN `live`-Marker):
    `source_label("ARPAE-2I")` muss "ARPAE" und "Italien" enthalten --
    transparente Quellenangabe, kein generisches Label. Heute schon gruen
    (aus #1186) und muss es bleiben: das Label ist nach #1648 die EINZIGE
    Quellenangabe, die Nutzer fuer Italien noch zu sehen bekommen."""
    from services.radar_service import RadarNowcastService

    label = RadarNowcastService().source_label("ARPAE-2I")

    assert "ARPAE" in label, f"Label muss 'ARPAE' enthalten (war: {label!r})"
    assert "Italien" in label, f"Label muss 'Italien' enthalten (war: {label!r})"
