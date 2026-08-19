"""TDD RED -- #1758 AC-10: `cape_geosphere_jkg` bleibt der CAPE-Fusion fremd.

Spec: docs/specs/modules/feat_1758_geosphere_cape_cin.md (AC-10, Invariante 3)

Hintergrund (Risiko 2 der Kontext-Analyse, Fehlertyp #1678): `geosphere.py`
setzt `reihe.meta.model="AROME"`. `model_registry.normalize_model_id` ist
case-insensitive und bildet `"arome"` auf `"meteofrance_arome"` ab -- damit
wuerde ein Datenpunkt mit GeoSphere-Herkunft ueber
`effective_cape_model_id()` die METEO-FRANCE-CAPE-Eichleiter ziehen, wenn er
sein CAPE ins GEMEINSAME Feld `cape_jkg` schriebe. Eigene Felder
(`cape_geosphere_jkg`/`convective_inhibition_geosphere_jkg`) umgehen das --
diese Datei belegt, dass die Fusion sie tatsaechlich NIE liest.

RED-GRUND (heute, unveraenderter Code): `ForecastDataPoint` kennt
`cape_geosphere_jkg` nicht -> TypeError beim Bauen des Datenpunkts mit
gesetztem Feld.

Testart: Kern-Schicht, keine Netzzugriffe, keine Mocks.
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

_SRC = Path(__file__).resolve().parents[2] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from app.models import ForecastDataPoint  # noqa: E402
from providers import thunder_enrichment  # noqa: E402

# Eine simple, feste Leiter genuegt hier -- der Pruefgegenstand ist NICHT die
# Eichung selbst (die ist Scope-Abgrenzung der Spec: "keine Schwellen, keine
# Eichung fuer GeoSphere-CAPE"), sondern OB `cape_geosphere_jkg` ueberhaupt in
# die Rechnung eingeht.
_CAPE_LEITER = (300.0, 500.0, 700.0)
_LPI_LEITER = (50.0, 100.0, 150.0)


def _dp(mit_geosphere_cape: bool) -> ForecastDataPoint:
    zusatz = (
        {"cape_geosphere_jkg": 713.5, "convective_inhibition_geosphere_jkg": -0.1}
        if mit_geosphere_cape else {}
    )
    return ForecastDataPoint(
        ts=datetime(2026, 8, 20, 11, 0, tzinfo=timezone.utc),
        t2m_c=20.0, wind10m_kmh=10.0,
        **zusatz,
    )


def test_ac10_fusion_liest_ausschliesslich_cape_jkg_nicht_cape_geosphere_jkg():
    """AC-10: Given einen Datenpunkt mit `reihe.meta.model="AROME"`
    (GeoSphere-Herkunft) und befuellten GeoSphere-cape/cin-Feldern, When
    `_fuse_thunder_levels` laeuft, Then bleibt `dp.cape_jkg` unangetastet
    (weiterhin `None`), und die resultierende `thunder_level` unterscheidet
    sich NICHT von einem Lauf ohne die GeoSphere-Felder -- die
    CAPE-Fusion darf `cape_geosphere_jkg` unter keinen Umstaenden lesen."""
    dp_ohne = _dp(mit_geosphere_cape=False)
    dp_mit = _dp(mit_geosphere_cape=True)

    thunder_enrichment._fuse_thunder_levels([dp_ohne], _CAPE_LEITER, _LPI_LEITER)
    thunder_enrichment._fuse_thunder_levels([dp_mit], _CAPE_LEITER, _LPI_LEITER)

    assert dp_mit.cape_jkg is None, (
        f"dp.cape_jkg wurde auf {dp_mit.cape_jkg} gesetzt -- die Fusion (oder ein "
        "anderer Codepfad) hat cape_geosphere_jkg in das Open-Meteo-Feld geschrieben"
    )
    assert dp_mit.thunder_level == dp_ohne.thunder_level, (
        f"thunder_level unterscheidet sich: ohne GeoSphere-Feld={dp_ohne.thunder_level}, "
        f"mit GeoSphere-Feld (713.5 J/kg, klar ueber jeder Leitersprosse)={dp_mit.thunder_level} -- "
        "die Fusion hat cape_geosphere_jkg mitgelesen und dadurch die "
        "Meteo-France-Eichleiter (model_registry.py) auf einen GeoSphere-Wert angewendet"
    )
