"""TDD RED -- Issue #1992 Amendment: Health-Journal der additiven
Gewitter-Zusatzquelle (`geosphere` in `DE_ALPEN`, #1758).

Spec: docs/specs/modules/feat_1992_geosphere_health_amendment.md (AC-4, AC-5).
Vorbild: tests/tdd/test_thunder_enrichment_health_journal.py (#1581).

Deckt hier ab: AC-4 (additive Quelle scheitert -> `path="thunder_additive"`,
`outcome="unavailable"`, `detail="geosphere"`, getrennt von `path="thunder"`),
AC-5 (additive Quelle liefert, mit oder ohne gefuellte Werte ->
`outcome="ok"`, Primaerquelle bleibt in Zeilenzahl/Inhalt unveraendert).

===========================================================================
Kein Mock-Theater
===========================================================================
Beide Quellen (Primaer- und Zusatzquelle) werden durch FAKE-Provider
vertreten, die `providers.base.ThunderSignalProvider` strukturell erfuellen
(Muster tests/unit/test_thunder_source_substitution.py) -- kein `Mock()`,
kein `patch()`, kein `MagicMock`. Das Journal wird ECHT geschrieben (durch
den Prueflingspfad `thunder_enrichment._fetch_lightning_density`) und ECHT
gelesen (JSONL geparst, Felder geprueft).

`providers.thunder_routing.thunder_providers_for` wird auf eine feste
Quellenliste `("de_direct", "geosphere")` gezwungen (analog #1758 DE_ALPEN)
-- so kann keine ECHTE Zusatzquelle unbemerkt mitfahren und eine im Test
nicht erwartete Journalzeile erzeugen.

===========================================================================
Erwartete Rotfaerbung
===========================================================================
AC-4 und AC-5 sind heute rot: die Zusatzquellen-Schleife in
`_fetch_lightning_density` (thunder_enrichment.py:589-604) journalt heute
NICHTS -- weder Erfolg noch Fehlschlag, nur ein `logger.warning` beim
Fehlschlag. `path="thunder_additive"` existiert im Journal ueberhaupt nicht
(auch `PATH_THUNDER_ADDITIVE` fehlt noch in enrichment_health.py). Jede
Journal-Zusicherung scheitert an "keine Zeile".

Ausfuehrung:
    uv run pytest tests/tdd/test_thunder_additive_enrichment_health.py \
        --disable-socket --allow-unix-socket -v
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional

_SRC = Path(__file__).resolve().parents[2] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from app.config import Location  # noqa: E402
from app.models import (  # noqa: E402
    ForecastDataPoint,
    ForecastMeta,
    NormalizedTimeseries,
    Provider,
)
from providers import base, thunder_enrichment, thunder_routing  # noqa: E402

_ORT = Location(latitude=47.26, longitude=11.39, name="Testort DE_ALPEN")

_JOURNAL_UNTERPFAD = ("diagnostics", "enrichment_calls.jsonl")


# ---------------------------------------------------------------------------
# Fakes -- erfuellen providers.base.ThunderSignalProvider strukturell
# (uebernommen aus tests/unit/test_thunder_source_substitution.py)
# ---------------------------------------------------------------------------

class _FakeQuelle:
    def __init__(
        self, name: str, *, wirft: bool = False,
        signale: Optional[Dict[str, Dict[int, float]]] = None,
    ) -> None:
        self._name = name
        self._wirft = wirft
        self._signale = signale or {}
        self.call_count = 0

    @property
    def name(self) -> str:
        return self._name

    def fetch_thunder_signals(self, location, start=None, end=None):
        return {}

    def fetch_thunder_signals_named(self, location, start=None, end=None):
        self.call_count += 1
        if self._wirft:
            raise RuntimeError(f"Zusatzquelle '{self._name}' nicht erreichbar (simuliert)")
        return self._signale


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _reihe(stunden: int = 4) -> NormalizedTimeseries:
    start = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    data = [
        ForecastDataPoint(ts=start + timedelta(hours=h), t2m_c=9.5, wind10m_kmh=12.0)
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


def _patch_quellen_de_alpen(monkeypatch) -> None:
    """Zwingt die Zustaendigkeitsaufloesung auf die #1758-DE_ALPEN-Kette
    `("de_direct", "geosphere")` -- primaer + EINE additive Zusatzquelle."""
    monkeypatch.setattr(
        thunder_routing, "thunder_providers_for",
        lambda lat, lon: ("de_direct", "geosphere"), raising=True,
    )


def _journalpfad() -> Path:
    from app.loader import get_data_root
    return get_data_root().joinpath(*_JOURNAL_UNTERPFAD)


def _zeilen() -> List[dict]:
    pfad = _journalpfad()
    if not pfad.is_file():
        return []
    return [json.loads(z) for z in pfad.read_text().splitlines() if z.strip()]


def _thunder_zeilen() -> List[dict]:
    return [z for z in _zeilen() if z.get("path") == "thunder"]


def _thunder_additive_zeilen() -> List[dict]:
    return [z for z in _zeilen() if z.get("path") == "thunder_additive"]


def _letzte_thunder_additive_zeile() -> dict:
    zeilen = _thunder_additive_zeilen()
    assert zeilen, (
        f"Keine Journalzeile mit path='thunder_additive' in {_journalpfad()} "
        f"-- vorhandene Zeilen: {_zeilen()}. Die Zusatzquellen-Schleife in "
        f"_fetch_lightning_density journalt heute nichts."
    )
    return zeilen[-1]


# ---------------------------------------------------------------------------
# AC-4: additive Quelle scheitert -> outcome="unavailable", detail="geosphere"
# ---------------------------------------------------------------------------

def test_ac4_additive_quelle_scheitert_schreibt_unavailable_getrennt_von_thunder(
    monkeypatch,
) -> None:
    assert _zeilen() == [], (
        "Testaufbau: Journal muss vor dem Abruf leer sein."
    )
    reihe = _reihe()
    primaer = _FakeQuelle(
        "de_direct", signale={"lpi": {h: 3.0 for h in range(1, 5)}},
    )
    additiv = _FakeQuelle("geosphere", wirft=True)
    _patch_quellen_de_alpen(monkeypatch)
    _patch_provider(monkeypatch, {"de_direct": primaer, "geosphere": additiv})

    thunder_enrichment._fetch_lightning_density(reihe, _ORT, None)

    assert additiv.call_count == 1, (
        f"Testaufbau: die additive Quelle wurde {additiv.call_count}x "
        f"gerufen, erwartet genau einmal."
    )

    zeile = _letzte_thunder_additive_zeile()
    assert zeile.get("outcome") == "unavailable", (
        f"AC-4: eine scheiternde additive Quelle muss outcome='unavailable' "
        f"hinterlassen, bekommen {zeile.get('outcome')!r} "
        f"(ganze Zeile: {zeile})"
    )
    assert zeile.get("detail") == "geosphere", (
        f"AC-4: `detail` muss die additive Quelle nennen ('geosphere'), "
        f"bekommen {zeile.get('detail')!r} (ganze Zeile: {zeile})"
    )

    # Trennungsnachweis: die primaerquellen-Zeile (`path='thunder'`) darf
    # durch den additiven Fehlschlag NICHT beruehrt werden -- genau EINE
    # Zeile, aus dem erfolgreichen Primaerabruf.
    thunder_zeilen = _thunder_zeilen()
    assert len(thunder_zeilen) == 1, (
        f"AC-4: erwartet GENAU eine 'thunder'-Zeile (Primaerquelle), "
        f"bekommen {len(thunder_zeilen)}: {thunder_zeilen} -- der additive "
        f"Fehlschlag darf keine zusaetzliche Zeile unter path='thunder' "
        f"erzeugen (Trennungsnachweis)."
    )
    assert thunder_zeilen[0].get("outcome") == "ok", (
        f"Testaufbau: die Primaerquelle hat geliefert -- erwartet "
        f"outcome='ok' unter path='thunder', bekommen "
        f"{thunder_zeilen[0].get('outcome')!r}"
    )


# ---------------------------------------------------------------------------
# AC-5: additive Quelle liefert (gefuellt oder leer) -> outcome="ok"
# ---------------------------------------------------------------------------

def test_ac5_additive_quelle_erfolg_mit_werten_schreibt_ok(monkeypatch) -> None:
    assert _zeilen() == [], "Testaufbau: Journal muss vor dem Abruf leer sein."
    reihe = _reihe()
    primaer = _FakeQuelle(
        "de_direct", signale={"lpi": {h: 3.0 for h in range(1, 5)}},
    )
    additiv = _FakeQuelle(
        "geosphere", signale={"cape": {h: 250.0 for h in range(1, 5)}},
    )
    _patch_quellen_de_alpen(monkeypatch)
    _patch_provider(monkeypatch, {"de_direct": primaer, "geosphere": additiv})

    thunder_enrichment._fetch_lightning_density(reihe, _ORT, None)

    assert any(
        getattr(dp, "cape_geosphere_jkg", None) == 250.0 for dp in reihe.data
    ), (
        "Testaufbau: die additive Quelle hat keine Werte in die Reihe "
        "eingetragen -- der Test unten prueft dann den falschen Ausgang."
    )

    zeile = _letzte_thunder_additive_zeile()
    assert zeile.get("outcome") == "ok", (
        f"AC-5: eine erfolgreiche additive Quelle mit gefuellten Werten "
        f"muss outcome='ok' hinterlassen, bekommen {zeile.get('outcome')!r} "
        f"(ganze Zeile: {zeile})"
    )
    assert zeile.get("detail") == "geosphere", (
        f"AC-5: `detail` muss die additive Quelle nennen ('geosphere'), "
        f"bekommen {zeile.get('detail')!r} (ganze Zeile: {zeile})"
    )

    thunder_zeilen = _thunder_zeilen()
    assert len(thunder_zeilen) == 1, (
        f"AC-5: die Primaerquelle darf durch die additive Quelle nicht "
        f"beeinflusst werden -- erwartet GENAU eine 'thunder'-Zeile, "
        f"bekommen {len(thunder_zeilen)}: {thunder_zeilen}"
    )


def test_ac5_additive_quelle_erfolg_leer_schreibt_ebenfalls_ok(monkeypatch) -> None:
    """AC-5, zweite Auspraegung: die additive Quelle antwortet gueltig, aber
    ohne einen einzigen Wert -- auch das ist ein Erfolg ('kein Gewitter in
    Sicht'), kein Ausfall (dieselbe Regel wie bei der Primaerquelle)."""
    assert _zeilen() == [], "Testaufbau: Journal muss vor dem Abruf leer sein."
    reihe = _reihe()
    primaer = _FakeQuelle(
        "de_direct", signale={"lpi": {h: 3.0 for h in range(1, 5)}},
    )
    additiv = _FakeQuelle("geosphere", signale={})
    _patch_quellen_de_alpen(monkeypatch)
    _patch_provider(monkeypatch, {"de_direct": primaer, "geosphere": additiv})

    thunder_enrichment._fetch_lightning_density(reihe, _ORT, None)

    assert additiv.call_count == 1, (
        f"Testaufbau: die additive Quelle wurde {additiv.call_count}x "
        f"gerufen, erwartet genau einmal."
    )
    assert all(
        getattr(dp, "cape_geosphere_jkg", None) is None for dp in reihe.data
    ), (
        "Testaufbau: es wurde doch ein Wert gesetzt -- dann ist es nicht "
        "der 'leere Antwort'-Ausgang."
    )

    zeile = _letzte_thunder_additive_zeile()
    assert zeile.get("outcome") == "ok", (
        f"AC-5: eine leere, aber gueltige Antwort der additiven Quelle muss "
        f"ebenfalls outcome='ok' hinterlassen (sonst meldet jede ruhige "
        f"Wetterlage einen Dauerausfall), bekommen "
        f"{zeile.get('outcome')!r} (ganze Zeile: {zeile})"
    )

    thunder_zeilen = _thunder_zeilen()
    assert len(thunder_zeilen) == 1, (
        f"AC-5: erwartet GENAU eine 'thunder'-Zeile (Primaerquelle "
        f"unveraendert), bekommen {len(thunder_zeilen)}: {thunder_zeilen}"
    )
