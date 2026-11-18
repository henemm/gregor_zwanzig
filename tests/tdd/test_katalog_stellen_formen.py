"""Katalog: eine Quelle fuer Roh/Einfach je Stelle und fuer gesperrte Stellen.

Issue #3122, Scheibe B1a. SPEC: docs/specs/modules/feat_3122_was_steht_wo.md,
Teil A Nr. 4 (Tabelle "zwei Formen je Stelle") und Nr. 5 (gesperrte Stellen).

Kern-Schicht, ohne Netz, ohne Mock. Das Soll der Tabelle steht hier von Hand
(abgeschrieben aus der Spec), nicht aus dem Katalog erzeugt. Die alten,
verstreuten Listen bleiben in dieser Scheibe bestehen; ihre Deckung mit der
neuen Quelle ist hier festgehalten, die Abweichungen der freigegebenen
Spec-Tabelle stehen als benannte, erwartete Differenz.
"""
from __future__ import annotations

import pytest

from app.metric_catalog import get_all_metrics

VIER = frozenset({"email", "telegram", "hourly", "outlook"})
DREI = frozenset({"email", "telegram", "outlook"})

#: Spec Teil A Nr. 4, von Hand.
SOLL_ZWEI_FORMEN = {
    "wind": VIER, "gust": VIER, "precipitation": VIER, "rain_probability": VIER,
    "cloud_total": VIER, "cloud_low": VIER, "cloud_mid": VIER, "cloud_high": VIER,
    "sunshine": DREI,
    "wind_direction": DREI,
    "thunder": frozenset({"email"}),
}

FENSTER = ("temperature_night", "wind_chill_night", "temperature_day_low",
           "temperature_day_high", "wind_chill_day_low", "wind_chill_day_high")

ALLE_IDS = [m.id for m in get_all_metrics()]
STELLEN = ("email", "telegram", "sms", "hourly", "outlook")


def _katalog():
    from app import metric_catalog

    return metric_catalog


@pytest.mark.parametrize("metric_id", ALLE_IDS)
def test_zwei_formen_je_stelle_wie_spec_tabelle(metric_id):
    """GIVEN jede waehlbare Metrik WHEN der Katalog nach den Stellen mit zwei
    Formen gefragt wird THEN steht dort genau die Zeile der Spec-Tabelle
    ("alle uebrigen": keine); die SMS hat nie zwei Formen."""
    stellen = _katalog().zwei_formen_stellen(metric_id)
    assert stellen == SOLL_ZWEI_FORMEN.get(metric_id, frozenset())
    assert "sms" not in stellen


def test_zwei_formen_unbekannte_metrik_ist_leer():
    k = _katalog()
    assert k.zwei_formen_stellen("gibt_es_nicht") == frozenset()
    assert k.zwei_formen_stellen(None) == frozenset()
    assert k.zwei_formen_stellen("confidence") == frozenset()


def test_ausblick_spalte_deckt_sich_mit_outlook_friendly_capable():
    """Die Ausblick-Spalte der neuen Quelle und die alte Ausblick-Liste sind
    deckungsgleich (keine erwartete Differenz)."""
    k = _katalog()
    neu = {m for m in ALLE_IDS if "outlook" in k.zwei_formen_stellen(m)}
    assert neu == set(k.OUTLOOK_FRIENDLY_CAPABLE)


def test_email_spalte_gegen_format_modes_nur_benannte_differenz():
    """``format_modes`` (alte Faehigkeits-Abfrage) gegen die E-Mail-Spalte:
    einzige erwartete Differenz ist die Regenwahrscheinlichkeit, die mit der
    Spec zwei Formen bekommt (PO-Freigabe 2026-11-17). Gewitter hatte schon
    zwei Formen und behaelt sie nur in der E-Mail."""
    k = _katalog()
    alt = {m.id for m in get_all_metrics() if len(m.format_modes) > 1}
    neu = {m for m in ALLE_IDS if "email" in k.zwei_formen_stellen(m)}
    assert neu - alt == {"rain_probability"}
    assert alt - neu == set()
    telegram = {m for m in ALLE_IDS if "telegram" in k.zwei_formen_stellen(m)}
    assert alt - telegram == {"thunder"}, "Gewitter: zwei Formen nur in der E-Mail"


def test_stundenverlauf_spalte_gegen_hourly_friendly_benannte_differenz():
    """Der heutige Orte-Stundenverlauf folgt der Ausblick-Liste. Neu: Sonnen-
    stunden gesperrt (kein Stundenwert), Windrichtung immer Kompass."""
    k = _katalog()
    neu = {m for m in ALLE_IDS if "hourly" in k.zwei_formen_stellen(m)}
    assert set(k.OUTLOOK_FRIENDLY_CAPABLE) - neu == {"sunshine", "wind_direction"}
    assert neu <= set(k.OUTLOOK_FRIENDLY_CAPABLE)


@pytest.mark.parametrize("metric_id", ALLE_IDS)
def test_standard_form_aus_katalog(metric_id):
    """Katalog-Standard je Metrik (fuer Trip und Orte gleich): Einfach genau
    dann, wenn der Katalog-Standard keine Rohzahl ist."""
    from app.metric_catalog import get_metric

    erwartet = "raw" if get_metric(metric_id).default_format_mode == "raw" else "simplified"
    assert _katalog().standard_form(metric_id) == erwartet


# ---------------------------------------------------------------------------
# Gesperrte Stellen (Spec Teil A Nr. 5)
# ---------------------------------------------------------------------------

def test_sperre_sonnenstunden_im_stundenverlauf():
    assert _katalog().stellen_sperre("sunshine", "hourly", "compare") == "kein_stundenwert"


@pytest.mark.parametrize("metric_id", FENSTER)
def test_sperre_fenstergroessen(metric_id):
    """Tages-/Nachtgroessen: keine Spalte in der Stundentabelle der Trip-Mail,
    kein Stundenwert, kein Tageswert im Ausblick; Telegram und SMS bleiben
    (Bedingung "nur abends" ist keine Sperre)."""
    k = _katalog()
    assert k.stellen_sperre(metric_id, "email", "trip") == "keine_eigene_spalte"
    assert k.stellen_sperre(metric_id, "hourly", "compare") == "kein_stundenwert"
    assert k.stellen_sperre(metric_id, "outlook", "trip") == "kein_tageswert"
    assert k.stellen_sperre(metric_id, "outlook", "compare") == "kein_tageswert"
    assert k.stellen_sperre(metric_id, "telegram", "trip") is None
    assert k.stellen_sperre(metric_id, "sms", "trip") is None


def test_windrichtung_im_stundenverlauf_nicht_gesperrt():
    k = _katalog()
    assert k.stellen_sperre("wind_direction", "hourly", "compare") is None
    assert "hourly" not in k.zwei_formen_stellen("wind_direction")


def test_sperren_deckungsgleich_mit_den_alten_listen():
    """Gesperrt im Stundenverlauf == HOURLY_EXCLUDED_METRIC_IDS; gesperrte
    E-Mail-Stelle der Trip-Mail == NO_HOURLY_COLUMN_METRIC_IDS; gesperrter
    Ausblick == Metriken ohne darstellbare Tagesauswertung; SMS: jede waehlbare
    Metrik hat ein Kuerzel, also keine Sperre."""
    from output.renderers.compare_hourly_metric_ids import HOURLY_EXCLUDED_METRIC_IDS
    from output.renderers.compare_outlook_metric_ids import derived_aggregations
    from output.renderers.email.helpers import NO_HOURLY_COLUMN_METRIC_IDS

    k = _katalog()
    for surface in ("trip", "compare"):
        stunde = {m for m in ALLE_IDS if k.stellen_sperre(m, "hourly", surface)}
        assert stunde == set(HOURLY_EXCLUDED_METRIC_IDS)
        ausblick = {m for m in ALLE_IDS if k.stellen_sperre(m, "outlook", surface)}
        assert ausblick == {m for m in ALLE_IDS if not derived_aggregations(m)}
        assert {m for m in ALLE_IDS if k.stellen_sperre(m, "sms", surface)} == set()
        assert {m for m in ALLE_IDS if k.stellen_sperre(m, "telegram", surface)} == set()
    assert {m for m in ALLE_IDS if k.stellen_sperre(m, "email", "trip")} == set(
        NO_HOURLY_COLUMN_METRIC_IDS)


def test_sperrgruende_sind_schluessel_aus_der_spec():
    k = _katalog()
    gruende = {
        k.stellen_sperre(m, s, f) for m in ALLE_IDS for s in STELLEN for f in ("trip", "compare")
    } - {None}
    assert gruende <= {"kein_stundenwert", "keine_eigene_spalte", "kein_tageswert", "kein_kuerzel"}
    assert {"kein_stundenwert", "keine_eigene_spalte", "kein_tageswert"} <= gruende


def test_sperre_unbekannte_eingaben_werfen_nicht():
    k = _katalog()
    assert k.stellen_sperre("gibt_es_nicht", "hourly", "compare") is None
    assert k.stellen_sperre("wind", "fax", "trip") is None
    assert k.stellen_sperre(None, "email", "trip") is None
