"""Leerauswahl heisst leer (Trip) — Issue #1394, Resolver-Ebene.

Spec: docs/specs/modules/trip_empty_metric_selection.md
Kontext: docs/context/fix-1394-leere-metrikauswahl.md

Kern-Tests (Test-Politik "Zwei Schichten", CLAUDE.md): kein Netz, keine
Live-Dienste, kein Mock/patch. Reine Datenstrukturen + echte Aufrufe des
(noch zu bauenden) Resolvers.

RED-Grund: `src/output/renderers/trip_metric_ids.py` existiert noch nicht —
der Import unten schlaegt mit ModuleNotFoundError fehl.
"""
from __future__ import annotations

from app.models import MetricConfig


def _mc(metric_id: str, *, enabled: bool) -> MetricConfig:
    return MetricConfig(metric_id=metric_id, enabled=enabled)


class TestFallAAltbestand:
    """Fall A: Feld fehlt ganz (`metrics == []`) UND `altbestand=True` →
    die sieben Standard-IDs (AC-5/AC-6 auf Resolver-Ebene)."""

    def test_empty_metrics_altbestand_true_returns_default_seven(self):
        from output.renderers.trip_metric_ids import (
            DEFAULT_TRIP_METRIC_IDS, resolve_trip_active_metrics,
        )
        result = resolve_trip_active_metrics([], altbestand=True)
        assert result == list(DEFAULT_TRIP_METRIC_IDS)
        assert result == [
            "temperature", "wind", "gust", "precipitation",
            "thunder", "freezing_level", "visibility",
        ], f"Standard-Siebener-Liste weicht ab: {result!r}"

    def test_default_altbestand_is_true(self):
        """`altbestand` ist rueckwaertskompatibel Default True (Invariante 5)."""
        from output.renderers.trip_metric_ids import (
            DEFAULT_TRIP_METRIC_IDS, resolve_trip_active_metrics,
        )
        result = resolve_trip_active_metrics([])
        assert result == list(DEFAULT_TRIP_METRIC_IDS)


class TestFallBBewussteLeerauswahl:
    """Fall B: `metrics` hat Eintraege, alle `enabled=False`, UND
    `altbestand=False` → `[]` (AC-1..AC-3 auf Resolver-Ebene)."""

    def test_all_disabled_altbestand_false_returns_empty(self):
        from output.renderers.trip_metric_ids import resolve_trip_active_metrics
        metrics = [_mc(m, enabled=False) for m in (
            "temperature", "wind", "gust", "precipitation",
            "thunder", "freezing_level", "visibility",
        )]
        result = resolve_trip_active_metrics(metrics, altbestand=False)
        assert result == [], (
            f"Fall B (bewusste Leerauswahl) muss [] liefern, nicht {result!r}"
        )

    def test_all_disabled_altbestand_true_still_falls_back(self):
        """Bug-Falle: 'alle enabled=False' + altbestand=True (irrtuemlich
        gesetzt) faellt auf die Default-Liste zurueck — das ist die dokumentierte
        Known-Limitation, kein neuer Fehler dieses Tests."""
        from output.renderers.trip_metric_ids import (
            DEFAULT_TRIP_METRIC_IDS, resolve_trip_active_metrics,
        )
        metrics = [_mc(m, enabled=False) for m in ("temperature", "wind")]
        result = resolve_trip_active_metrics(metrics, altbestand=True)
        assert result == list(DEFAULT_TRIP_METRIC_IDS)


class TestGefuellteAuswahlUnabhaengigVonAltbestand:
    """Eine gefuellte, aktive Auswahl bleibt unveraendert — unabhaengig vom
    `altbestand`-Flag (Invariante 4: Reihenfolge = Erstvorkommen)."""

    def test_active_selection_unchanged_altbestand_true(self):
        from output.renderers.trip_metric_ids import resolve_trip_active_metrics
        metrics = [
            _mc("gust", enabled=True),
            _mc("wind", enabled=False),
            _mc("temperature", enabled=True),
        ]
        result = resolve_trip_active_metrics(metrics, altbestand=True)
        assert result == ["gust", "temperature"]

    def test_active_selection_unchanged_altbestand_false(self):
        from output.renderers.trip_metric_ids import resolve_trip_active_metrics
        metrics = [
            _mc("gust", enabled=True),
            _mc("wind", enabled=False),
            _mc("temperature", enabled=True),
        ]
        result = resolve_trip_active_metrics(metrics, altbestand=False)
        assert result == ["gust", "temperature"]

    def test_order_is_first_occurrence_not_sorted(self):
        """Invariante 4: Reihenfolge bleibt Erstvorkommen in `metrics`, kein
        Sortier-Eingriff."""
        from output.renderers.trip_metric_ids import resolve_trip_active_metrics
        metrics = [
            _mc("visibility", enabled=True),
            _mc("temperature", enabled=True),
            _mc("gust", enabled=True),
        ]
        result = resolve_trip_active_metrics(metrics, altbestand=False)
        assert result == ["visibility", "temperature", "gust"]


class TestDefaultTripMetricIdsIstAusDemRegisterAbgeleitet:
    """Issue #1552: DEFAULT_TRIP_METRIC_IDS muss aus dem Register (`trip_default_
    rank`) abgeleitet sein, nicht als Literal gefuehrt werden -- sonst laeuft das
    Register (Frontend-Vorbelegung liest `trip_default_enabled`) und der Server-
    Rueckfall (`DEFAULT_TRIP_METRIC_IDS`) irgendwann auseinander (zwei Quellen
    statt einer, s. Spec § B).

    Mutations-Falle (CLAUDE.md, Regel-Budget-Familie "Ableitung durch das alte
    Literal ersetzen"): weil der heutige Registerstand zufaellig dieselbe
    Reihenfolge/Menge liefert wie die frueher hartkodierte Liste, wuerde ein Test,
    der nur den RESULTIERENDEN Wert prueft (wie die Klasse oben), eine
    Ruecksubstitution durch das alte Literal NICHT bemerken. Dieser Test stoert
    stattdessen echt die Registerdaten (kein Mock -- eine reale Kopie der
    `_METRICS`-Liste mit einem echten zusaetzlichen `MetricDefinition`-Objekt) und
    erzwingt einen frischen Import, um zu beweisen, dass die Ableitung tatsaechlich
    zur Laufzeit aus dem Register liest.
    """

    def test_derivation_tracks_a_real_registry_change(self, monkeypatch):
        import importlib

        from app import metric_catalog
        from output.renderers import trip_metric_ids as tmi_module

        extra = dataclasses_replace_temperature_with_rank_eight(metric_catalog)
        monkeypatch.setattr(
            metric_catalog, "_METRICS", metric_catalog._METRICS + [extra],
        )
        try:
            reloaded = importlib.reload(tmi_module)
            assert reloaded.DEFAULT_TRIP_METRIC_IDS[-1] == "trip_1552_mutation_probe", (
                "DEFAULT_TRIP_METRIC_IDS reagiert nicht auf eine echte "
                "Registeraenderung -- das ist nur moeglich, wenn die Liste (wieder) "
                "hartkodiert ist statt aus get_all_metrics() abgeleitet zu werden"
            )
        finally:
            importlib.reload(tmi_module)  # Modul-Cache fuer alle Folgetests bereinigen


def dataclasses_replace_temperature_with_rank_eight(metric_catalog):
    """Baut ein echtes zusaetzliches MetricDefinition-Objekt (Rang 8) -- kein
    Mock, reale Dataclass-Instanz aus dem Produktivtyp."""
    temperature = metric_catalog.get_metric("temperature")
    import dataclasses
    return dataclasses.replace(
        temperature,
        id="trip_1552_mutation_probe",
        trip_default_rank=8,
    )
