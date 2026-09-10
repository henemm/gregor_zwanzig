"""TDD RED -- Issue #2263: LPI-Leiter folgt der LIEFERNDEN Quelle, nicht dem
geografischen Gebiet.

Spec: docs/specs/modules/fix_2263_lpi_leiter_nach_liefernder_quelle.md
(AC-1..AC-6).
Kontext: docs/context/fix-2263-lpi-leiter-vertretung.md.

===========================================================================
Worum es geht
===========================================================================
`_schwellen_fuer_reihe()` (`src/providers/thunder_enrichment.py:279-304`)
waehlt die LPI-Schwellenleiter heute AUSSCHLIESSLICH nach dem geografischen
Gebiet der Koordinate (`thunder_region_for()`). Springt bei Ausfall der
Primaerquelle die Vertretung `eu_direct` ein (ADR-0047), wird deren Wert
trotzdem gegen die Leiter des URSPRUENGLICHEN Gebiets bewertet:
- Korsika (FR) hat GAR KEINE Leiter (`lpi_thresholds_jkg("FR") is None`) --
  das Vertretungssignal verpufft komplett (AC-1).
- Alpen (DE_ALPEN) hat die fuer ICON-D2 kalibrierte, deutlich schaerfere
  Leiter (1,0/30,0/50,0) -- der ICON-EU-Ersatzwert wird dagegen ueberhoeht
  bewertet (AC-2).

===========================================================================
Kein Mock-Theater
===========================================================================
Die Gewitterquellen werden durch FAKE-Provider vertreten, die
`providers.base.ThunderSignalProvider` strukturell erfuellen (Muster
tests/tdd/test_thunder_enrichment_health_journal.py, dort uebernommen aus
tests/unit/test_thunder_source_substitution.py) -- kein `Mock()`, kein
`patch()`, kein `MagicMock`. Jeder Test durchlaeuft die ECHTE Kette
`enrich_thunder() -> _fetch_lightning_density() -> _fetch_primaerquelle()
-> _schwellen_fuer_reihe() -> _fuse_thunder_levels()` bis `dp.thunder_level`
-- die Fusionsleiter (`app.model_registry.lpi_thresholds_jkg()`) wird dabei
vom Prueflingscode selbst aufgeloest, NIE als Literal in den Test geschrieben
(genau dieses Loch hat den Defekt bisher verdeckt).

Zeitstempel der Reihe liegen bewusst `now + 1 Tag` (Muster
`test_thunder_enrichment_fuses_level_shared_path.py::_valide_openmeteo_antwort`),
damit `_apply_radar_override()` (laeuft NACH der Fusion in `enrich_thunder()`)
aus dem 90-Minuten-Fenster faellt und keinen echten Netzwerkaufruf ausloest.

===========================================================================
Erwartete Rotfaerbung -- was rot ist und warum
===========================================================================
AC-1, AC-2, AC-6 sind heute ROT:
- AC-1: `_schwellen_fuer_reihe()` schlaegt ausschliesslich `thunder_region_for()`
  nach -> FR -> `lpi_thresholds_jkg("FR") is None` -> kein LPI-Signal ->
  `dp.thunder_level` bleibt `NONE` statt `MED`.
- AC-2: dieselbe Funktion liefert fuer die Alpen-Koordinate immer die
  DE_ALPEN-Leiter (1,0/30,0/50,0), unabhaengig davon, dass der Wert von der
  Vertretung `eu_direct` stammt -- 60 J/kg >= 50 (high) -> `dp.thunder_level`
  wird faelschlich `HIGH` statt `MED`.
- AC-6: identisch zu AC-2, zusaetzlich mit vorbelegtem `fallback_model`
  eines ANDEREN Fallback-Mechanismus -- bewacht, dass eine kuenftige
  Implementierung `fallback_model` statt `fallback_metrics` als
  Erkennungsmerkmal der Vertretung liest.

AC-3, AC-4, AC-5 sind BEWUSST von Anfang an GRUEN (Regressionswaechter auf
dem unveraenderten Primaerpfad):
- AC-3: `de_direct` liefert selbst (kein Ausfall) -> DE_ALPEN-Leiter war
  schon immer richtig.
- AC-4: `eu_direct` liefert selbst als reguläre Primaerquelle -> EU_REST-
  Leiter war schon immer richtig.
- AC-5: `fr_direct` liefert regulaer Blitzdichte statt Blitzpotenzial -> es
  entsteht ohnehin kein LPI-Signal, unabhaengig von der Leiterwahl.

Ausfuehrung (Datei NAMENTLICH, ein Lauf ohne benannte Testdateien ist
gesperrt):
    uv run pytest tests/tdd/test_lpi_ladder_follows_delivering_source.py \
        -v -rA
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Optional

_SRC = Path(__file__).resolve().parents[2] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from app.config import Location  # noqa: E402
from app.models import (  # noqa: E402
    ForecastDataPoint,
    ForecastMeta,
    NormalizedTimeseries,
    Provider,
    ThunderLevel,
)
from providers import base, thunder_enrichment, thunder_routing  # noqa: E402

# Korsika liegt innerhalb des FR-Rechtecks (`thunder_routing._REGIONS`:
# 41.3..51.1 N / -5.2..9.7 O) -- Primaerquelle `fr_direct`.
_KORSIKA = Location(latitude=42.2, longitude=9.1, name="Korsika")

# Karnischer Hoehenweg, dieselbe Koordinate wie im Journal-Test (#1581) --
# liegt innerhalb des DE_ALPEN-Rechtecks -- Primaerquelle `de_direct`.
_ALPEN = Location(latitude=46.40, longitude=12.52, name="Karnischer Hoehenweg")

# Athen liegt weder im FR- noch im DE_ALPEN-Rechteck (lat 37,98 < beide
# Untergrenzen 41,3/43,17) -- faellt auf die Weltrechteck-Zeile EU_REST,
# Primaerquelle `eu_direct` REGULAER (kein Vertretungsfall).
_EU_REST_ORT = Location(latitude=37.98, longitude=23.73, name="Athen")

_LPI_WERT = 60.0  # ueber EU_REST-med (23,81), unter DE_ALPEN-high (50,0) -- der Wert, an dem sich EU_REST- (MED) und DE_ALPEN-Leiter (HIGH) um eine volle Stufe unterscheiden.


# ---------------------------------------------------------------------------
# Fakes -- erfuellen providers.base.ThunderSignalProvider strukturell
# (Muster tests/tdd/test_thunder_enrichment_health_journal.py::_FakeBenannteQuelle,
# uebernommen aus tests/unit/test_thunder_source_substitution.py)
# ---------------------------------------------------------------------------

class _FakeBenannteQuelle:
    """Analog dwd.py/dwd_eu.py: bietet `fetch_thunder_signals_named`, liefert
    also Blitzpotenzial (Signalname `lpi`) statt roher Blitzdichte."""

    def __init__(
        self, name: str, *, wirft: bool = False,
        signale: Optional[Dict[str, Dict[int, float]]] = None,
    ) -> None:
        self._name = name
        self._wirft = wirft
        self._signale = signale or {}

    @property
    def name(self) -> str:
        return self._name

    def fetch_thunder_signals(self, location, start=None, end=None):
        return {}

    def fetch_thunder_signals_named(self, location, start=None, end=None):
        if self._wirft:
            raise base.ThunderSourceUnavailableError(self._name, 1)
        return self._signale


class _FakeEinzelwertQuelle:
    """Analog des heutigen `fr_direct`-Verhaltens (S2a): bietet NUR die
    Einzelwert-Methode (Blitzdichte), KEIN `fetch_thunder_signals_named` --
    dadurch entsteht strukturell kein Blitzpotenzial-Signal, unabhaengig vom
    gelieferten Wert (AC-5)."""

    def __init__(self, name: str, *, dichte: Optional[Dict[int, float]] = None) -> None:
        self._name = name
        self._dichte = dichte or {}

    @property
    def name(self) -> str:
        return self._name

    def fetch_thunder_signals(self, location, start=None, end=None):
        return self._dichte


# ---------------------------------------------------------------------------
# Helpers (Muster tests/tdd/test_thunder_enrichment_health_journal.py)
# ---------------------------------------------------------------------------

def _reihe(stunden: int = 4) -> NormalizedTimeseries:
    """Zeitstempel bewusst `now + 1 Tag`, NICHT `now` (Muster
    `test_thunder_enrichment_fuses_level_shared_path.py::_valide_openmeteo_antwort`)
    -- so faellt `_apply_radar_override()` (90-Minuten-Fenster um `jetzt`,
    laeuft am Ende von `enrich_thunder()`) sicher leer aus und loest keinen
    echten Netzwerkaufruf an `RadarNowcastService` aus."""
    start = (datetime.now(timezone.utc) + timedelta(days=1)).replace(
        minute=0, second=0, microsecond=0
    )
    data = [
        ForecastDataPoint(ts=start + timedelta(hours=h), t2m_c=12.3, wind10m_kmh=18.0)
        for h in range(1, stunden + 1)
    ]
    meta = ForecastMeta(provider=Provider.DWD, model="TEST", grid_res_km=2.2)
    return NormalizedTimeseries(meta=meta, data=data)


def _patch_provider(monkeypatch, mapping: dict) -> None:
    def _get(name):
        if name not in mapping:
            raise base.ProviderNotFoundError(name)
        return mapping[name]
    monkeypatch.setattr(base, "get_provider", _get, raising=True)


def _patch_quellen(monkeypatch, *namen: str) -> None:
    """Zwingt die Zustaendigkeitsaufloesung auf eine feste Quellenliste --
    verhindert, dass fuer DE_ALPEN unbemerkt die ECHTE additive Zusatzquelle
    (`geosphere`, ADR-0057) mitfaehrt und einen echten Netzwerkaufruf
    ausloest (Muster `test_thunder_enrichment_health_journal.py::_patch_quellen`).
    Die Vertretungstabelle (`thunder_vertretung_for`) bleibt ECHT."""
    monkeypatch.setattr(
        thunder_routing, "thunder_providers_for",
        lambda lat, lon: tuple(namen), raising=True,
    )


def _potenzial_signale(wert: float, stunden: int = 4) -> Dict[str, Dict[int, float]]:
    return {"lpi": {h: wert for h in range(1, stunden + 1)}}


# ---------------------------------------------------------------------------
# AC-1: Korsika, fr_direct faellt aus, eu_direct-Vertretung liefert 60 J/kg
# -> MED (EU_REST-Leiter), HEUTE ROT (verpufft komplett auf FR-Leiter=None)
# ---------------------------------------------------------------------------

def test_ac1_korsika_vertretung_eu_direct_bewertet_gegen_eu_rest_leiter(monkeypatch):
    """AC-1: GIVEN Korsika (~42,2 N / 9,1 O), `fr_direct` wirft eine
    `ThunderSourceUnavailableError`, die echte Vertretung `eu_direct` liefert
    60 J/kg Blitzpotenzial / WHEN `enrich_thunder` end-to-end durchlaeuft /
    THEN ist `dp.thunder_level` MED (EU_REST-Leiter 7,14/23,81/86,16) --
    heute entsteht aus diesem Signal GAR KEINE Stufe, weil die FR-Leiter
    (`lpi_thresholds_jkg("FR") is None`) gewaehlt wird.
    """
    # Testaufbau-Vorbedingung: Korsika muss WIRKLICH auf `fr_direct`/`FR`
    # routen -- `_REGIONS` ist first-match-wins mit `EU_REST` als
    # Weltrechteck am Ende; ein Verwechslungspunkt wuerde hier still den
    # falschen Pfad pruefen und den Waechter wertlos machen.
    assert thunder_routing.thunder_provider_for(_KORSIKA.latitude, _KORSIKA.longitude) == "fr_direct"
    assert thunder_routing.thunder_region_for(_KORSIKA.latitude, _KORSIKA.longitude) == "FR"

    reihe = _reihe()
    primaer = _FakeBenannteQuelle("fr_direct", wirft=True)
    ersatz = _FakeBenannteQuelle("eu_direct", signale=_potenzial_signale(_LPI_WERT))
    _patch_quellen(monkeypatch, "fr_direct")
    _patch_provider(monkeypatch, {"fr_direct": primaer, "eu_direct": ersatz})

    thunder_enrichment.enrich_thunder(reihe, _KORSIKA)

    # Testaufbau-Gegenprobe: die Vertretung hat wirklich geliefert, sonst
    # pruefte der Test unten ein Ergebnis, das aus einem ganz anderen Vorgang
    # (kein Signal ueberhaupt) stammt.
    assert any(dp.lightning_potential_lpi_jkg == _LPI_WERT for dp in reihe.data), (
        "Testaufbau: die Vertretung hat keinen Blitzpotenzial-Wert geliefert."
    )
    assert all(dp.thunder_level == ThunderLevel.MED for dp in reihe.data), (
        f"AC-1: erwartet ueberall MED (EU_REST-Leiter), bekommen "
        f"{[dp.thunder_level for dp in reihe.data]}"
    )


# ---------------------------------------------------------------------------
# AC-2: Alpen, de_direct faellt aus, eu_direct-Vertretung liefert 60 J/kg
# -> MED (EU_REST-Leiter), HEUTE ROT (faelschlich HIGH ueber DE_ALPEN-Leiter)
# ---------------------------------------------------------------------------

def test_ac2_alpen_vertretung_eu_direct_bewertet_gegen_eu_rest_leiter(monkeypatch):
    """AC-2: GIVEN eine Alpen-Koordinate, `de_direct` wirft eine
    `ThunderSourceUnavailableError`, die echte Vertretung `eu_direct` liefert
    60 J/kg Blitzpotenzial / WHEN `enrich_thunder` end-to-end durchlaeuft /
    THEN ist `dp.thunder_level` MED -- heute liefert dieselbe Situation
    faelschlich HIGH, weil der ICON-EU-Wert gegen die fuer ICON-D2 kalibrierte
    Leiter (1,0/30,0/50,0) bewertet wird (60 >= 50).
    """
    # Testaufbau-Vorbedingung: der Alpenpunkt muss WIRKLICH auf
    # `de_direct`/`DE_ALPEN` routen -- s. Begruendung in AC-1.
    assert thunder_routing.thunder_provider_for(_ALPEN.latitude, _ALPEN.longitude) == "de_direct"
    assert thunder_routing.thunder_region_for(_ALPEN.latitude, _ALPEN.longitude) == "DE_ALPEN"

    reihe = _reihe()
    primaer = _FakeBenannteQuelle("de_direct", wirft=True)
    ersatz = _FakeBenannteQuelle("eu_direct", signale=_potenzial_signale(_LPI_WERT))
    _patch_quellen(monkeypatch, "de_direct")
    _patch_provider(monkeypatch, {"de_direct": primaer, "eu_direct": ersatz})

    thunder_enrichment.enrich_thunder(reihe, _ALPEN)

    assert any(dp.lightning_potential_lpi_jkg == _LPI_WERT for dp in reihe.data), (
        "Testaufbau: die Vertretung hat keinen Blitzpotenzial-Wert geliefert."
    )
    assert all(dp.thunder_level == ThunderLevel.MED for dp in reihe.data), (
        f"AC-2: erwartet ueberall MED (EU_REST-Leiter), bekommen "
        f"{[dp.thunder_level for dp in reihe.data]} -- heute faelschlich HIGH "
        f"ueber die DE_ALPEN-Leiter der Primaerquelle."
    )


# ---------------------------------------------------------------------------
# AC-3: Alpen, de_direct liefert SELBST 60 J/kg (kein Ausfall) -> HIGH,
# HEUTE GRUEN (Regressionswaechter unveraenderter Primaerpfad)
# ---------------------------------------------------------------------------

def test_ac3_alpen_primaerquelle_ohne_ausfall_bleibt_high(monkeypatch):
    """AC-3: GIVEN eine Alpen-Koordinate, `de_direct` liefert als
    Primaerquelle SELBST 60 J/kg Blitzpotenzial (kein Ausfall) / WHEN
    `enrich_thunder` end-to-end durchlaeuft / THEN bleibt `dp.thunder_level`
    HIGH (DE_ALPEN-Leiter, unveraendert fuer die Primaerquelle) -- Regressions-
    waechter gegen den unveraenderten Primaerpfad.
    """
    # Testaufbau-Vorbedingung: s. Begruendung in AC-1/AC-2.
    assert thunder_routing.thunder_provider_for(_ALPEN.latitude, _ALPEN.longitude) == "de_direct"
    assert thunder_routing.thunder_region_for(_ALPEN.latitude, _ALPEN.longitude) == "DE_ALPEN"

    reihe = _reihe()
    primaer = _FakeBenannteQuelle("de_direct", signale=_potenzial_signale(_LPI_WERT))
    _patch_quellen(monkeypatch, "de_direct")
    _patch_provider(monkeypatch, {"de_direct": primaer})

    thunder_enrichment.enrich_thunder(reihe, _ALPEN)

    assert any(dp.lightning_potential_lpi_jkg == _LPI_WERT for dp in reihe.data), (
        "Testaufbau: die Primaerquelle hat keinen Blitzpotenzial-Wert geliefert."
    )
    assert all(dp.thunder_level == ThunderLevel.HIGH for dp in reihe.data), (
        f"AC-3: erwartet ueberall HIGH (DE_ALPEN-Leiter), bekommen "
        f"{[dp.thunder_level for dp in reihe.data]}"
    )


# ---------------------------------------------------------------------------
# AC-4: EU_REST-Koordinate, eu_direct liefert regulaer als Primaerquelle
# 60 J/kg -> MED, HEUTE GRUEN (Regressionswaechter unveraenderter Primaerpfad)
# ---------------------------------------------------------------------------

def test_ac4_eu_rest_primaerquelle_ohne_ausfall_bleibt_med(monkeypatch):
    """AC-4: GIVEN eine Koordinate, fuer die `eu_direct` reguläre
    Primaerquelle ist (kein Vertretungsfall), liefert 60 J/kg Blitzpotenzial
    / WHEN `enrich_thunder` end-to-end durchlaeuft / THEN ist
    `dp.thunder_level` MED ueber die EU_REST-Leiter -- Regressionswaechter
    gegen den unveraenderten Primaerpfad fuer EU_REST.
    """
    # Testaufbau-Vorbedingung: der Ort muss WIRKLICH auf `eu_direct`/`EU_REST`
    # routen, NICHT still auf FR oder DE_ALPEN fallen -- s. Begruendung in
    # AC-1. `_REGIONS` ist first-match-wins mit `EU_REST` als Weltrechteck
    # am Ende; ohne diese Vorbedingung wuerde eine Verwechslungskoordinate
    # den falschen Pfad pruefen und trotzdem gruen bleiben.
    assert thunder_routing.thunder_provider_for(_EU_REST_ORT.latitude, _EU_REST_ORT.longitude) == "eu_direct"
    assert thunder_routing.thunder_region_for(_EU_REST_ORT.latitude, _EU_REST_ORT.longitude) == "EU_REST"

    reihe = _reihe()
    primaer = _FakeBenannteQuelle("eu_direct", signale=_potenzial_signale(_LPI_WERT))
    _patch_quellen(monkeypatch, "eu_direct")
    _patch_provider(monkeypatch, {"eu_direct": primaer})

    thunder_enrichment.enrich_thunder(reihe, _EU_REST_ORT)

    assert any(dp.lightning_potential_lpi_jkg == _LPI_WERT for dp in reihe.data), (
        "Testaufbau: die Primaerquelle hat keinen Blitzpotenzial-Wert geliefert."
    )
    assert all(dp.thunder_level == ThunderLevel.MED for dp in reihe.data), (
        f"AC-4: erwartet ueberall MED (EU_REST-Leiter), bekommen "
        f"{[dp.thunder_level for dp in reihe.data]}"
    )


# ---------------------------------------------------------------------------
# AC-5: Korsika, fr_direct liefert regulaer Blitzdichte statt Blitzpotenzial
# -> kein LPI-Signal, lpi_thresholds_jkg("FR") is None, HEUTE GRUEN
# ---------------------------------------------------------------------------

def test_ac5_korsika_fr_direct_liefert_blitzdichte_kein_potenzial_signal(monkeypatch):
    """AC-5: GIVEN eine Korsika-Koordinate, `fr_direct` liefert als reguläre
    Primaerquelle (kein Ausfall) Blitzdichte statt Blitzpotenzial / WHEN
    `enrich_thunder` end-to-end durchlaeuft / THEN entsteht KEIN
    Blitzpotenzial-Signal und `lpi_thresholds_jkg("FR")` bleibt `None` --
    dies ist die Zusicherung, die eine quellenbezogene Umschreibung am
    ehesten still bricht, und kein bestehender Test bewacht den Draht dorthin.
    """
    from app.model_registry import lpi_thresholds_jkg

    # Testaufbau-Vorbedingung: s. Begruendung in AC-1.
    assert thunder_routing.thunder_provider_for(_KORSIKA.latitude, _KORSIKA.longitude) == "fr_direct"
    assert thunder_routing.thunder_region_for(_KORSIKA.latitude, _KORSIKA.longitude) == "FR"

    reihe = _reihe()
    primaer = _FakeEinzelwertQuelle(
        "fr_direct", dichte={h: 0.42 for h in range(1, 5)},
    )
    _patch_quellen(monkeypatch, "fr_direct")
    _patch_provider(monkeypatch, {"fr_direct": primaer})

    thunder_enrichment.enrich_thunder(reihe, _KORSIKA)

    # Testaufbau-Gegenprobe: die Quelle hat wirklich geliefert (Blitzdichte),
    # sonst waere "kein Blitzpotenzial-Signal" trivial erfuellt.
    assert any(
        dp.lightning_density_per_km2_3h == 0.42 for dp in reihe.data
    ), "Testaufbau: die Quelle hat keine Blitzdichte geliefert."

    assert all(dp.lightning_potential_lpi_jkg is None for dp in reihe.data), (
        "AC-5: eine reine Blitzdichte-Quelle darf KEIN Blitzpotenzial-Feld "
        "befuellen."
    )
    assert all(
        "lightning_potential_jkg" not in (dp.thunder_level_signals or [])
        for dp in reihe.data
    ), (
        "AC-5: die Fusion darf kein Blitzpotenzial-Signal als Traeger der "
        "Stufe ausweisen, wenn keines geliefert wurde."
    )
    assert lpi_thresholds_jkg("FR") is None, (
        "AC-5: FR darf weiterhin KEINE LPI-Kalibrierung haben."
    )


# ---------------------------------------------------------------------------
# F001 (Adversary-Finding #2263): direkter Wächter der Uebersetzungstabelle --
# `lpi_schluessel_fuer_quelle()` bekommt in AC-1..AC-6 nie zwei verschiedene
# Rueckgabewerte fuer denselben Aufruf zu sehen (jeder End-to-End-Test haengt
# an genau einer Quelle). Diese direkte Pruefung faengt die Mutation "ergaenze
# `_LPI_QUELLE_ZU_SCHLUESSEL` um `fr_direct` -> `EU_REST`" unmittelbar, ohne
# Umweg ueber die Fusion.
# ---------------------------------------------------------------------------

def test_lpi_schluessel_fuer_quelle_uebersetzt_bekannte_quellen_direkt():
    """Adversary F001: GIVEN die drei bekannten Gewitterquellen / WHEN
    `lpi_schluessel_fuer_quelle()` direkt aufgerufen wird / THEN liefert
    `de_direct` -> "DE_ALPEN", `eu_direct` -> "EU_REST", `fr_direct` -> `None`
    (AROME liefert Blitzdichte, keine Kalibrierung) -- fasst NICHT die
    Fusion an, damit die Mutation "ergaenze `fr_direct` in
    `_LPI_QUELLE_ZU_SCHLUESSEL`" unabhaengig vom End-to-End-Weg auffliegt.
    """
    from app.model_registry import lpi_schluessel_fuer_quelle

    assert lpi_schluessel_fuer_quelle("de_direct") == "DE_ALPEN"
    assert lpi_schluessel_fuer_quelle("eu_direct") == "EU_REST"
    assert lpi_schluessel_fuer_quelle("fr_direct") is None
    assert lpi_schluessel_fuer_quelle(None) is None
    assert lpi_schluessel_fuer_quelle("unbekannte_quelle") is None


# ---------------------------------------------------------------------------
# F001 (Adversary-Finding #2263), Wirksamkeits-Waechter zu AC-5: `fr_direct`
# liefert diesmal (anders als AC-5 oben) ueber die _FakeBenannteQuelle
# WIRKLICH einen benannten Blitzpotenzial-Wert -- so wirkt eine faelschlich
# ergaenzte Uebersetzung `fr_direct -> EU_REST` end-to-end, waehrend AC-5 mit
# der Einzelwert-Fake-Quelle strukturell NIE einen benannten Wert liefert und
# die Uebersetzung deshalb unbeobachtet laesst.
# ---------------------------------------------------------------------------

def test_ac5b_fr_direct_liefert_benanntes_lpi_erzeugt_dennoch_keine_stufe(monkeypatch):
    """Adversary F001: GIVEN Korsika, `fr_direct` liefert REGULAER (kein
    Ausfall) ueber `fetch_thunder_signals_named` einen benannten
    Blitzpotenzial-Wert von 60 J/kg / WHEN `enrich_thunder` end-to-end
    durchlaeuft / THEN steht der Wert an `dp.lightning_potential_lpi_jkg`,
    aber `dp.thunder_level` bleibt unveraendert `None` -- `fr_direct` hat
    KEINE Kalibrierung
    (`lpi_thresholds_jkg(lpi_schluessel_fuer_quelle("fr_direct")) is None`),
    das Signal traegt also KEINE Stufe. Eine Implementierung, die
    `_LPI_QUELLE_ZU_SCHLUESSEL` faelschlich um `"fr_direct": "EU_REST"`
    ergaenzt, liefert hier stattdessen MED (60 >= EU_REST-med 23,81) und
    faellt durch.
    """
    # Testaufbau-Vorbedingung: s. Begruendung in AC-1.
    assert thunder_routing.thunder_provider_for(_KORSIKA.latitude, _KORSIKA.longitude) == "fr_direct"
    assert thunder_routing.thunder_region_for(_KORSIKA.latitude, _KORSIKA.longitude) == "FR"

    reihe = _reihe()
    primaer = _FakeBenannteQuelle("fr_direct", signale=_potenzial_signale(_LPI_WERT))
    _patch_quellen(monkeypatch, "fr_direct")
    _patch_provider(monkeypatch, {"fr_direct": primaer})

    thunder_enrichment.enrich_thunder(reihe, _KORSIKA)

    # Testaufbau-Gegenprobe: `fr_direct` hat wirklich einen benannten Wert
    # geliefert, sonst pruefte der Test unten ein Ergebnis, das aus einem
    # ganz anderen Vorgang (kein Signal ueberhaupt) stammt.
    assert any(dp.lightning_potential_lpi_jkg == _LPI_WERT for dp in reihe.data), (
        "Testaufbau: `fr_direct` hat keinen benannten Blitzpotenzial-Wert geliefert."
    )
    assert all(dp.thunder_level is None for dp in reihe.data), (
        f"F001: erwartet ueberall KEINE Stufe (fr_direct ohne Kalibrierung), "
        f"bekommen {[dp.thunder_level for dp in reihe.data]} -- eine "
        f"Implementierung, die `fr_direct` faelschlich in "
        f"`_LPI_QUELLE_ZU_SCHLUESSEL` eintraegt, faellt hier durch."
    )


# ---------------------------------------------------------------------------
# AC-6: wie AC-2, aber `fallback_model`/`fallback_reason` sind VORHER schon
# vom Grundvorhersage-Fallback mit ANDERER Modell-Kennung belegt -> bleibt
# MED, HEUTE ROT
# ---------------------------------------------------------------------------

def test_ac6_alpen_vertretung_bleibt_med_trotz_fremdbelegtem_fallback_model(monkeypatch):
    """AC-6: GIVEN die Gewitter-Vertretung ist aktiv (`lightning_potential_lpi_jkg`
    steht in `fallback_metrics`) UND `fallback_model`/`fallback_reason` sind
    ZUGLEICH vom Grundvorhersage-Fallback mit einer ANDEREN Modell-Kennung
    belegt (VOR dem Aufruf gesetzt, `_fetch_primaerquelle` ueberschreibt ein
    bereits belegtes `fallback_model` bewusst nicht -- Merge-Schutz
    ADR-0047 Known Limitations Punkt 3) / WHEN `eu_direct` 60 J/kg
    Blitzpotenzial liefert / THEN ist `dp.thunder_level` weiterhin MED -- die
    Leiterwahl haengt an `fallback_metrics`, nicht an `fallback_model`. Eine
    Implementierung, die stattdessen `fallback_model == "eu_direct"` prueft,
    liest hier eine FREMDE Modell-Kennung und faellt durch.
    """
    # Testaufbau-Vorbedingung: s. Begruendung in AC-1/AC-2.
    assert thunder_routing.thunder_provider_for(_ALPEN.latitude, _ALPEN.longitude) == "de_direct"
    assert thunder_routing.thunder_region_for(_ALPEN.latitude, _ALPEN.longitude) == "DE_ALPEN"

    reihe = _reihe()
    reihe.meta.fallback_model = "icon_eu_grundvorhersage"
    reihe.meta.fallback_reason = "grundvorhersage_fallback"

    primaer = _FakeBenannteQuelle("de_direct", wirft=True)
    ersatz = _FakeBenannteQuelle("eu_direct", signale=_potenzial_signale(_LPI_WERT))
    _patch_quellen(monkeypatch, "de_direct")
    _patch_provider(monkeypatch, {"de_direct": primaer, "eu_direct": ersatz})

    thunder_enrichment.enrich_thunder(reihe, _ALPEN)

    # Testaufbau-Gegenprobe: der Merge-Schutz hat wirklich gegriffen --
    # `fallback_model` traegt weiterhin die FREMDE Kennung, nicht "eu_direct".
    assert reihe.meta.fallback_model == "icon_eu_grundvorhersage", (
        "Testaufbau: `fallback_model` wurde ueberschrieben -- der Merge-"
        "Schutz griff nicht, AC-6 prueft dann nicht mehr die Zusicherung."
    )
    assert "lightning_potential_lpi_jkg" in reihe.meta.fallback_metrics, (
        "Testaufbau: die Vertretung hat kein Erkennungsmerkmal in "
        "`fallback_metrics` hinterlassen."
    )
    assert all(dp.thunder_level == ThunderLevel.MED for dp in reihe.data), (
        f"AC-6: erwartet ueberall MED trotz fremdbelegtem `fallback_model`, "
        f"bekommen {[dp.thunder_level for dp in reihe.data]} -- eine "
        f"Implementierung, die `fallback_model` statt `fallback_metrics` "
        f"liest, faellt hier durch."
    )
