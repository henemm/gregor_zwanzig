"""TDD RED — Issue #1186: ARPAE-ICON-2I-Modell-Rückfall unter Radar-DPC fuer Italien.

Spec: docs/specs/modules/radar_nowcast_italy_arpae_fallback.md

Faellt Radar-DPC (#1162, live) fuer eine Italien-Koordinate aus (leere Antwort/
Fehler), springt die Quellen-Kette heute direkt auf AROME-FR/ICON-D2 (nur fuer
Rand-Koordinaten treffend) bzw. den globalen `minutely_15`-Fallback — fuer Mittel-/
Sueditalien (Rom, Neapel, Sizilien) ohne jede regionale Zwischenstufe. Diese Tests
belegen die geplante ARPAE-ICON-2I-Integration: eine neue `_fetch_italy_arpae`
Methode (Open-Meteo, `models=italia_meteo_arpae_icon_2i`) als zweiter Schritt
innerhalb der bestehenden `_within_dpc`-Box, direkt nach dem DPC-Versuch, sowie
ein neuer `_SOURCE_LABELS`-Eintrag "ARPAE-2I" -> "ARPAE ICON-2I (2 km, Italien)".

KEINE MOCKS. DI erfolgt ausschliesslich durch Ersetzen von Instanz-/Klassenmethoden
mit echten Python-Funktionen (Muster aus test_issue_1161_inca_convective.py /
test_issue_1162_radar_dpc.py) — kein `Mock()`/`patch()`/`MagicMock`.

In der RED-Phase schlagen AC-1, AC-3 und AC-4 fehl, weil:
- `RadarNowcastService._fetch_italy_arpae` noch nicht existiert (AttributeError
  beim Lesen des Original-Attributs bzw. `result.source` landet bei
  `"minutely_15"` statt `"ARPAE-2I"`, da die Kette nach dem DPC-Stub direkt bis
  zum globalen Fallback durchlaeuft),
- `_SOURCE_LABELS` noch keinen Eintrag fuer `"ARPAE-2I"` besitzt (`source_label`
  faellt auf den Rohstring zurueck, der "Italien" nicht enthaelt).

AC-2 ist ein Bestandsschutz-Test (DPC existiert bereits aus #1162, ist also
JETZT SCHON GRUEN) — kein RED-Beweis fuer #1186, sondern Absicherung, dass die
neue ARPAE-Stufe DPC nicht verdraengt.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

# sys.path absichern: sowohl `services.*` als auch `src.services.*` Importpfade.
_ROOT = Path(__file__).resolve().parents[2]
for _p in (str(_ROOT), str(_ROOT / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# Rom — eindeutig innerhalb der bestehenden DPC-Box (lat 36.0-47.5 / lon 6.5-19.0),
# aber ausserhalb AROME-FR (lat 41.0-51.5 / lon -5.5-10.0 -> lon 12.5 knapp draussen)
# und ausserhalb ICON-D2. Landet bei DPC-Ausfall heute direkt bei minutely_15.
_ROME_LAT, _ROME_LON = 41.90, 12.50


# ===========================================================================
# AC-1: DPC-Ausfall -> Fallback auf ARPAE-2I (statt direkt minutely_15)
# ===========================================================================

@pytest.mark.live
def test_ac1_dpc_failure_falls_back_to_arpae_italy():
    """AC-1: schlaegt Radar-DPC fehl (Instanzmethoden-Ersatz -> [], DI ohne Mock),
    muss die Kette fuer eine IT-Koordinate beim ARPAE-ICON-2I-Modell landen, nicht
    direkt beim globalen `minutely_15`-Fallback. Echter HTTP-Call fuer den
    ARPAE-Schritt selbst (nur DPC ist gestubbt).

    Aktuell ROT: `_fetch_italy_arpae` existiert nicht, daher faellt die Kette nach
    dem DPC-Stub durch AROME-FR/ICON-D2 (Rom liegt in keiner der beiden Boxen)
    direkt bis zum globalen `minutely_15`-Fallback durch -> `result.source ==
    "minutely_15"`, nicht `"ARPAE-2I"`.
    """
    from services.radar_service import RadarNowcastService

    def fake_dpc_fetch(self, lat, lon):
        return []

    orig_dpc = RadarNowcastService._fetch_radar_dpc
    RadarNowcastService._fetch_radar_dpc = fake_dpc_fetch
    try:
        svc = RadarNowcastService()
        result = svc.get_nowcast(_ROME_LAT, _ROME_LON)

        assert result.source == "ARPAE-2I", (
            f"Bei DPC-Ausfall muss Rom beim ARPAE-ICON-2I-Modell landen, nicht "
            f"direkt beim globalen Fallback (war: {result.source})"
        )
        assert len(result.frames) >= 1, "ARPAE-Fallback muss mindestens ein Frame liefern"
        for frame in result.frames:
            assert isinstance(frame.precip_mm_h, (int, float)), (
                f"precip_mm_h muss numerisch sein (war: {frame.precip_mm_h!r})"
            )
            assert frame.precip_mm_h >= 0, (
                f"precip_mm_h darf nicht negativ sein (war: {frame.precip_mm_h})"
            )
    finally:
        RadarNowcastService._fetch_radar_dpc = orig_dpc


# ===========================================================================
# AC-2: DPC verfuegbar -> DPC behaelt Vorrang vor ARPAE (Bestandsschutz #1162)
# ===========================================================================

@pytest.mark.live
def test_ac2_dpc_available_keeps_dpc_priority_over_arpae():
    """AC-2: echter Live-Call ohne jede DI gegen die produktive Source-Chain (Rom)
    liefert weiterhin `source == "DPC"` — Radar behaelt Vorrang vor dem neuen
    Modell-Rueckfall, keine Regression an #1162.

    Bestandsschutz-Hinweis: dieser Test ist JETZT SCHON GRUEN, da DPC bereits aus
    #1162 (live) existiert und fuer Rom vor ARPAE greift. Er ist kein RED-Beweis
    fuer #1186, sondern testet ausschliesslich, dass die neue ARPAE-Stufe DPC
    nicht verdraengt (Muster
    `test_ac2_dpc_live_get_nowcast_uses_dpc_source_for_it_coordinate` aus #1162).
    """
    from providers.radar_dpc import RadarDPCProvider
    from services.radar_service import RadarNowcastService

    if not RadarDPCProvider().fetch_nowcast(_ROME_LAT, _ROME_LON):
        pytest.skip("Radar-DPC API nicht erreichbar (fetch_nowcast liefert leere Liste)")

    result = RadarNowcastService().get_nowcast(_ROME_LAT, _ROME_LON)
    assert result.source == "DPC", (
        f"Rom sollte explizit DPC nutzen, nicht den ARPAE-Rueckfall (war: {result.source})"
    )


# ===========================================================================
# AC-3: DPC und ARPAE beide leer -> fail-soft Fallback auf minutely_15
# ===========================================================================

@pytest.mark.live
def test_ac3_dpc_and_arpae_both_fail_falls_back_to_minutely15():
    """AC-3: schlagen sowohl Radar-DPC als auch ARPAE-2I fehl (beide
    Instanzmethoden durch `[]`-liefernde Ersatzmethoden ersetzt -> DI ohne Mock),
    faellt die Kette fuer eine Koordinate ausserhalb AROME-FR/ICON-D2 (Rom)
    fail-soft auf `source == "minutely_15"` zurueck, ohne Absturz.

    Aktuell ROT: `RadarNowcastService._fetch_italy_arpae` existiert noch nicht —
    schon das Lesen des Original-Attributs vor dem Ersetzen (`orig_arpae =
    RadarNowcastService._fetch_italy_arpae`) wirft `AttributeError`, bevor
    `get_nowcast` ueberhaupt aufgerufen wird.
    """
    from services.radar_service import RadarNowcastService

    def fake_dpc_fetch(self, lat, lon):
        return []

    def fake_arpae_fetch(self, lat, lon):
        return []

    orig_dpc = RadarNowcastService._fetch_radar_dpc
    orig_arpae = RadarNowcastService._fetch_italy_arpae  # AttributeError erwartet (RED)
    RadarNowcastService._fetch_radar_dpc = fake_dpc_fetch
    RadarNowcastService._fetch_italy_arpae = fake_arpae_fetch
    try:
        svc = RadarNowcastService()
        result = svc.get_nowcast(_ROME_LAT, _ROME_LON)
        assert result.source == "minutely_15", (
            f"Bei doppeltem DPC/ARPAE-Ausfall muss die Kette fail-soft auf den "
            f"globalen Fallback zurueckfallen (war: {result.source})"
        )
    finally:
        RadarNowcastService._fetch_radar_dpc = orig_dpc
        RadarNowcastService._fetch_italy_arpae = orig_arpae


# ===========================================================================
# AC-4: Quellen-Label ist transparent ("ARPAE" + "Italien")
# ===========================================================================

def test_ac4_source_label_transparent_arpae_italy():
    """AC-4: Pure-Function-Test (kein Netz). `source_label("ARPAE-2I")` muss beide
    Teilstrings "ARPAE" und "Italien" enthalten — transparente Quellenangabe,
    kein generisches Label.

    Aktuell ROT: `_SOURCE_LABELS` besitzt noch keinen `"ARPAE-2I"`-Eintrag,
    `source_label` faellt auf den Rohstring `"ARPAE-2I"` zurueck. Der enthaelt
    zwar "ARPAE", aber nicht "Italien" -> zweite Assertion schlaegt fehl.
    """
    from services.radar_service import RadarNowcastService

    label = RadarNowcastService().source_label("ARPAE-2I")

    assert "ARPAE" in label, f"Label muss 'ARPAE' enthalten (war: {label!r})"
    assert "Italien" in label, f"Label muss 'Italien' enthalten (war: {label!r})"
