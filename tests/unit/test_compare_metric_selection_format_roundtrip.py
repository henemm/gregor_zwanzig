"""Bestandsschutz (#2232, AC-7): alle drei gespeicherten Auswahl-Formate loesen
nach der Kuerzel-Umstellung unveraendert auf.

SPEC: docs/specs/modules/fix_2232_kuerzel_ein_modell_trip_vergleich.md

Hintergrund (Befund B2 der Rev.-1-Messung): Rev. 1 wollte die `metric_id` der
vier Temperatur-Eintraege umstellen. Gemessen wurde dabei, dass genau das drei
Bestandsformate stillschweigend entwertet haette --

  1. String-Altformat            `['temp_max_c', 'temp_min_c']`
  2. Paar-Neuformat (ADR-0037)   `[{'metric_id': 'temperature', 'aggregation': 'max'}, ...]`
  3. Ausblick-Kennungen (#1848 A2) `['temperature', 'wind_chill']`

Formate 2 und 3 lieferten nach der Umstellung `[]` bzw. `None`: die gespeicherte
Metrik-Auswahl waere ohne Fehlermeldung verschwunden (Datenverlust-Klasse #102,
BUG-DATALOSS-GR221). Weg A (Rev. 2) laesst `metric_id` unangetastet -- dieser
Test nagelt das fest, damit eine kuenftige Scheibe die Kennung nicht doch noch
verschiebt, ohne den Bestand mitzunehmen.

🔴 Dieser Test ist am Bestand GRUEN und soll es sein: er bewacht eine
Zusicherung, die diese Scheibe bewusst NICHT antastet. Seine Aussagekraft kommt
aus der Gegenprobe unten, die dieselben Aufloeser gegen eine verschobene
Katalog-Kopie fuehrt und zeigt, dass sie dann tatsaechlich leer laufen.

Test-Politik (CLAUDE.md, Schicht "Kern"): deterministisch, kein Netz, kein Mock.
"""
from __future__ import annotations

from output.renderers.compare_metric_catalog import COMPARE_METRIC_CATALOG, key_for
from output.renderers.compare_metric_ids import resolve_enabled_metrics
from output.renderers.compare_outlook_metric_ids import (
    derived_aggregations, resolve_outlook_metrics,
)

# Die vier Eintraege, deren Kuerzel diese Scheibe umstellt -- genau sie sind es,
# deren Auflösungs-Identitaet unberuehrt bleiben MUSS.
_BETROFFENE_KEYS = ("temp_max_c", "temp_min_c", "wind_chill_max_c", "wind_chill_min_c")


def test_format_1_string_altformat_loest_unveraendert_auf():
    """AC-7 (1): die gespeicherten Katalog-Schluessel ergeben weiterhin die
    Renderer-Kennungen der Uebersicht."""
    assert resolve_enabled_metrics(["temp_max_c", "temp_min_c"]) == [
        "temp_max", "temp_min",
    ]
    assert resolve_enabled_metrics(["wind_chill_max_c", "wind_chill_min_c"]) == [
        "wind_chill_max", "wind_chill_min",
    ]


def test_format_2_paar_neuformat_loest_unveraendert_auf():
    """AC-7 (2): das seit ADR-0037 geschriebene Paar-Format bleibt aufloesbar.

    Genau dieses Format lieferte in der Rev.-1-Messung `[]` -- der Fall, der
    Weg B verworfen hat."""
    gespeichert = [
        {"metric_id": "temperature", "aggregation": "max"},
        {"metric_id": "temperature", "aggregation": "min"},
        {"metric_id": "wind_chill", "aggregation": "max"},
        {"metric_id": "wind_chill", "aggregation": "min"},
    ]
    assert resolve_enabled_metrics(gespeichert) == [
        "temp_max", "temp_min", "wind_chill_max", "wind_chill_min",
    ]
    # Und die Rueckrichtung, ueber die dieselbe Naht laeuft:
    assert key_for("temperature", "max") == "temp_max_c"
    assert key_for("temperature", "min") == "temp_min_c"
    assert key_for("wind_chill", "max") == "wind_chill_max_c"
    assert key_for("wind_chill", "min") == "wind_chill_min_c"


def test_format_3_ausblick_kennungen_loesen_unveraendert_auf():
    """AC-7 (3): `outlook_metrics` speichert seit #1848 A2 die reine Kennung.

    Dieses Format lieferte in der Rev.-1-Messung `None` (= Rueckfall auf die
    sieben festen Spalten, die gespeicherte Auswahl weg)."""
    assert resolve_outlook_metrics(["temperature", "wind_chill"]) == [
        "temperature", "wind_chill",
    ]
    # Gemessen, nicht geraten: der Ausblick zeigt fuer beide Groessen genau die
    # zwei Richtungen, fuer die es eine Vergleichs-Katalogzeile MIT
    # `SegmentWeatherSummary`-Feld gibt (`temperature/avg` hat keine Zeile).
    assert derived_aggregations("temperature") == ["min", "max"]
    assert derived_aggregations("wind_chill") == ["min", "max"]


def test_die_vier_eintraege_behalten_ihre_aufloesungs_identitaet():
    """Der Kern von Weg A: `kuerzel_metric_id` traegt das Kuerzel, `metric_id`
    bleibt `temperature`/`wind_chill`. Wer die Kennung doch verschiebt, faellt
    hier auf, bevor die drei Formate oben leer laufen."""
    nach_key = {e["key"]: e for e in COMPARE_METRIC_CATALOG}
    ist = {k: nach_key[k]["metric_id"] for k in _BETROFFENE_KEYS}
    assert ist == {
        "temp_max_c": "temperature",
        "temp_min_c": "temperature",
        "wind_chill_max_c": "wind_chill",
        "wind_chill_min_c": "wind_chill",
    }, (
        "Die Auflösungs-Identitaet der vier Eintraege hat sich verschoben. "
        "Damit verlieren gespeicherte Vergleiche im Paar- und im "
        "Ausblick-Kennungsformat ihre Auswahl (Befund B2, Datenverlust-Klasse "
        f"#102). Gefunden: {ist!r}"
    )


def test_gegenprobe_verschobene_kennung_laesst_die_bestandsformate_leer_laufen():
    """Wirkungsnachweis an einer KOPIE: waeren die vier Eintraege auf die
    Gehzeit-Kennungen verschoben (Weg B aus Rev. 1), faende `key_for()` das
    gespeicherte Paar nicht mehr -- genau der gemessene Datenverlust.

    Die Gegenprobe fuehrt DIESELBE Indexbildung wie das Produktionsmodul
    (`(metric_id, aggregation) -> key`), nur ueber die verschobene Kopie."""
    verschoben = {
        "temp_max_c": "temperature_day_high", "temp_min_c": "temperature_day_low",
        "wind_chill_max_c": "wind_chill_day_high",
        "wind_chill_min_c": "wind_chill_day_low",
    }
    kopie = [
        {**e, "metric_id": verschoben.get(e["key"], e["metric_id"])}
        for e in COMPARE_METRIC_CATALOG
    ]
    index = {(e["metric_id"], e["aggregation"]): e["key"] for e in kopie}

    assert index.get(("temperature", "max")) is None, (
        "Die Gegenprobe findet das Bestandspaar weiterhin -- sie zeigt dann "
        "nicht, wovor dieser Test schuetzt."
    )
    # Positivkontrolle: derselbe Index ueber den ECHTEN Katalog findet es.
    echt = {(e["metric_id"], e["aggregation"]): e["key"] for e in COMPARE_METRIC_CATALOG}
    assert echt.get(("temperature", "max")) == "temp_max_c"
