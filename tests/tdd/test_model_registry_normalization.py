"""TDD RED -- Issue #1592 Scheibe C0 (Fundament), AC-4.

SPEC: docs/specs/modules/fix_1592_s1_cape_modellschwelle.md Abschnitt 2 (C0)

Neues Modul `app.model_registry` (noch nicht angelegt): buendelt das
uneinheitliche Modell-Vokabular (`icon_d2`/`ICON-D2`,
`meteofrance_arome`/`AROME-HIGHRES`, ...) auf einen kanonischen
Schluessel. Meteo-France meldet `AROME-HIGHRES` (-> `meteofrance_arome`),
GeoSphere meldet `AROME` (-> eigener Schluessel `geosphere_arome`) -- zwei
getrennte Modellwelten, kein gemeinsamer Alias (Issue #2225). `effective_cape_model_id()` buendelt zusaetzlich die
Fallback-Vorrang-Regel (steht "cape" in `meta.fallback_metrics`, gilt
`meta.fallback_model`, sonst `meta.model`) -- EINMAL fuer C0 und C1 (DRY,
Spec Abschnitt 2).

RED-Ursache (heute): `app.model_registry` existiert nicht -> ImportError bei
jedem Test dieser Datei.

Keine Mocks: reine Funktionsaufrufe, kein Netz.
"""
from __future__ import annotations

import pytest


# ───────────────────── AC-4 -- Vokabular-Buendelung ───────────────────────

@pytest.mark.parametrize(
    "raw, expected",
    [
        # ICON-D2-Familie: Open-Meteo-Technik-Schluessel vs. DWD-Direktwort
        ("icon_d2", "icon_d2"),
        ("ICON-D2", "icon_d2"),
        # Meteo-France-AROME: Open-Meteo-Technik-Schluessel vs. MF-Direktwort
        ("meteofrance_arome", "meteofrance_arome"),
        ("AROME-HIGHRES", "meteofrance_arome"),
        # GeoSphere-AROME: eigener Zweig, KEINE gemeinsame Welt mit Meteo-France
        ("AROME", "geosphere_arome"),
        # Uebrige drei produktiv gewaehlte Modelle, unveraendert kanonisch
        ("icon_eu", "icon_eu"),
        ("metno_nordic", "metno_nordic"),
        ("ecmwf_ifs04", "ecmwf_ifs04"),
        # Kuenstliche Werte und Unbekanntes -> None (keine Herkunft)
        ("aggregate", None),
        ("snapshot", None),
        ("fixture", None),
        ("NOWCAST", None),
        ("irgendein_unbekanntes_modell", None),
        (None, None),
    ],
)
def test_ac4_normalize_model_id_buendelt_vokabular_auf_kanonischen_schluessel(
    raw, expected,
):
    """AC-4: jede Schreibweise derselben Modellwelt liefert DENSELBEN
    kanonischen Schluessel; aggregate/snapshot/fixture/Unbekanntes -> None.

    Gegenprobe fest verdrahtet in den Parametern selbst: 'ICON-D2' und
    'icon_d2' muessen auf denselben Wert 'icon_d2' abbilden (nicht etwa
    'ICON-D2' unveraendert durchreichen) -- sonst haette eine Schwellen-
    tabelle je Modell zwei Eintraege fuer dieselbe Modellwelt.
    """
    from app.model_registry import normalize_model_id

    result = normalize_model_id(raw)
    assert result == expected, (
        f"normalize_model_id({raw!r}) muss {expected!r} liefern, "
        f"erhalten {result!r}"
    )


def test_ac4_gegenprobe_zwei_schreibweisen_derselben_modellwelt_kollidieren_nicht_mit_anderer_welt():
    """AC-4 Gegenprobe: 'AROME' und 'icon_d2' MUESSEN sich unterscheiden --
    eine Implementierung, die pauschal alles auf einen einzigen Schluessel
    abbildet (oder rohe Werte einfach durchreicht), waere hier blind."""
    from app.model_registry import normalize_model_id

    arome = normalize_model_id("AROME")
    icon = normalize_model_id("icon_d2")
    assert arome != icon, (
        f"AROME ({arome!r}) und icon_d2 ({icon!r}) muessen auf "
        "unterschiedliche kanonische Schluessel abbilden"
    )
    assert arome == "geosphere_arome"
    assert icon == "icon_d2"


# ───────────────── Fundament -- Fallback-Vorrang (DRY C0/C1) ──────────────

def test_effective_cape_model_id_nutzt_fallback_model_wenn_cape_darin_steht():
    """`effective_cape_model_id()`: steht 'cape' in `meta.fallback_metrics`,
    gilt der (normalisierte) `fallback_model`, NICHT das primaere `model` --
    das ist der WEATHER-05b-Lueckenfueller-Fall (Kontextdoku 'Gute Nachricht
    fuer die Feld-Herkunft')."""
    from app.model_registry import effective_cape_model_id
    from app.models import ForecastMeta, Provider

    meta = ForecastMeta(
        provider=Provider.OPENMETEO,
        model="meteofrance_arome",
        grid_res_km=1.3,
        fallback_model="icon_eu",
        fallback_metrics=["cape"],
    )
    result = effective_cape_model_id(meta)
    assert result == "icon_eu", (
        f"Steht 'cape' in fallback_metrics, muss effective_cape_model_id() "
        f"den normalisierten fallback_model liefern, erhalten {result!r}"
    )


def test_effective_cape_model_id_nutzt_primaermodell_wenn_cape_nicht_im_fallback_steht():
    """Gegenfall: `fallback_metrics` ist gesetzt, enthaelt aber 'cape' NICHT
    (z. B. nur 'wind10m_kmh' wurde nachgefuellt) -- dann gilt weiterhin das
    primaere `meta.model`, nicht der Fallback."""
    from app.model_registry import effective_cape_model_id
    from app.models import ForecastMeta, Provider

    meta = ForecastMeta(
        provider=Provider.OPENMETEO,
        model="meteofrance_arome",
        grid_res_km=1.3,
        fallback_model="icon_eu",
        fallback_metrics=["wind10m_kmh"],
    )
    result = effective_cape_model_id(meta)
    assert result == "meteofrance_arome", (
        f"Ohne 'cape' in fallback_metrics muss das primaere Modell gelten, "
        f"erhalten {result!r}"
    )


# ──────────── GeoSphere vs. Meteo-France -- getrennte Modellwelten ──────────

def test_geosphere_arome_bekommt_eigenen_schluessel_und_keine_meteofrance_eichung():
    """AC-1: GeoSphere-Herkunft ('AROME') darf NICHT die fuer Meteo-France
    geeichte DE_ALPEN-Schwelle (380.0 J/kg) erben. Verkettet ueber
    effective_cape_model_id() -> cape_threshold_jkg()/cape_ladder_thresholds_jkg(),
    NICHT nur isoliert das Alias-Dict -- sonst waere der Test schon vor dem
    Fix teilweise gruen (unbekannter Schluessel liefert ohnehin None)."""
    from app.model_registry import (
        cape_ladder_thresholds_jkg,
        cape_threshold_jkg,
        effective_cape_model_id,
    )
    from app.models import ForecastMeta, Provider

    meta = ForecastMeta(
        provider=Provider.GEOSPHERE,
        model="AROME",
        grid_res_km=2.5,
        interp="bilinear",
    )
    model_id = effective_cape_model_id(meta)
    assert model_id == "geosphere_arome", (
        f"GeoSphere-Herkunft muss auf einen eigenen Schluessel 'geosphere_arome' "
        f"abbilden, nicht auf Meteo-France, erhalten {model_id!r}"
    )
    assert cape_threshold_jkg(model_id, "DE_ALPEN") is None, (
        "geosphere_arome hat bewusst KEINE Eichung -- darf NICHT die "
        "Meteo-France-Schwelle 380.0 J/kg fuer DE_ALPEN erben"
    )
    assert cape_ladder_thresholds_jkg(model_id, "DE_ALPEN") is None, (
        "Ohne 'low'-Eichung muss die GESAMTE Leiter None sein, nicht "
        "(None, 1000.0, 2500.0)"
    )


def test_meteofrance_arome_highres_bleibt_unveraendert_bei_eigenem_schluessel():
    """AC-2 Regressionsschutz: Meteo-France ('AROME-HIGHRES') bleibt bei
    'meteofrance_arome' und behaelt seine Eichung -- dieser Test ist
    ABSICHTLICH bereits vor dem Fix gruen (keine Verhaltensaenderung fuer
    Meteo-France)."""
    from app.model_registry import cape_threshold_jkg, effective_cape_model_id
    from app.models import ForecastMeta, Provider

    meta = ForecastMeta(
        provider=Provider.METEOFRANCE,
        model="AROME-HIGHRES",
        grid_res_km=1.3,
    )
    model_id = effective_cape_model_id(meta)
    assert model_id == "meteofrance_arome"
    assert cape_threshold_jkg(model_id, "DE_ALPEN") == 380.0


def test_geosphere_und_meteofrance_arome_liefern_unterschiedliche_schluessel():
    """AC-4: 'AROME' (GeoSphere) und 'AROME-HIGHRES' (Meteo-France) muessen
    auf UNTERSCHIEDLICHE kanonische Schluessel abbilden -- Kollisions-
    Gegenprobe direkt im Vergleich (!=), nicht nur je einzeln gegen einen
    erwarteten String."""
    from app.model_registry import effective_cape_model_id
    from app.models import ForecastMeta, Provider

    geosphere_meta = ForecastMeta(provider=Provider.GEOSPHERE, model="AROME", grid_res_km=2.5)
    mf_meta = ForecastMeta(provider=Provider.METEOFRANCE, model="AROME-HIGHRES", grid_res_km=1.3)

    geosphere_id = effective_cape_model_id(geosphere_meta)
    mf_id = effective_cape_model_id(mf_meta)

    assert geosphere_id != mf_id, (
        f"GeoSphere ({geosphere_id!r}) und Meteo-France ({mf_id!r}) muessen "
        "sich unterscheiden -- sonst kollidieren beide weiterhin auf denselben "
        "Schluessel"
    )
