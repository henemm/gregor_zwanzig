"""RED — #1848 Scheibe A1: Ausblick liest Temperatur/gefuehlte Temperatur aus
dem Etappenaggregat statt aus dem Gehzeit-Fenster (Nachzug zu #1417).

SPEC: docs/specs/modules/outlook_gehzeit_und_spanne.md AC-1, AC-2, AC-3
KONTEXT: docs/context/feat-1848-a1-tagesfenster-kennungen.md, Abschnitt
"WERT-MESSUNG" (gemessene Sweep-Konstellation, Median-Differenz 1,23 C).

**Nachweisform Funktionsebene, NICHT "in derselben Mail".** Der Ausblick
zeigt strukturell nie den heutigen Tag (``get_future_stages()`` filtert
``>``, Spec "Known Limitations") -- ein Vergleich "gleiche Mail" waere nie
erfuellbar. AC-1/AC-3 rufen ``build_outlook_row()`` mit DENSELBEN
Segment-Daten auf, die ``sms_trip.py`` fuer den D-/FD-Token derselben Etappe
verwendet (``collect_hiking_window_points()`` + ``hiking_field_min_max()``,
Vorbild ``tests/tdd/_hiking_window_fixtures.py``, Issue #1417).

**Angenommene Schnittstelle (RED definiert den Vertrag).** Zum Zeitpunkt
dieses Tests existiert noch kein Weg, das Gehzeit-Fenster an
``build_outlook_row()`` zu uebergeben -- die Funktion kennt keine Segmente,
nur ``summary``+``points`` (flache, ungefensterte Stundenliste ueber ALLE
Segmente, s. Docstring). Der "Naht"-Abschnitt des Kontexts sagt: der
Aufrufer (``trip_report_scheduler.py``, hat ``seg_weather`` bereits vorliegen)
berechnet ``hiking_field_min_max()`` SELBST und reicht das ERGEBNIS als
optionalen Parameter durch (Vorbild ``sms_thresholds``). Diese Tests nehmen
dafuer den Parameter ``hiking_extrema: dict[str, tuple] | None`` an -- Keys
sind die ``ForecastDataPoint``-Feldnamen (``"t2m_c"``/``"wind_chill_c"``,
identisch zum ``field``-Argument von ``hiking_field_min_max()``), Werte das
3-Tupel ``(min, max, max_ts)``, wie die Funktion es liefert. Fehlt ein Key
(oder ist ``hiking_extrema`` ganz ``None``), bleibt der Fail-soft-Rueckfall
aufs Etappenaggregat unveraendert (AC-2). Der genaue Parametername ist eine
Implementierungsentscheidung des GREEN-Schritts -- entscheidend ist die
Zusicherung "Ausblick-Wert == hiking_field_min_max()-Wert bei gesetztem
Override", nicht der Name selbst.

RED heute: ``TypeError: unexpected keyword argument 'hiking_extrema'`` fuer
AC-1/AC-3 (Parameter existiert nicht) -- ehrlich rot aus dem richtigen
Grund, nicht aus einem Tippfehler.

Kern-Schicht: keine Mocks, kein Netz. Segmente/Aggregate kommen aus dem
ECHTEN Produktivpfad (``SegmentWeatherService._aggregate_for_segment()``
ueber ``_hiking_window_fixtures.build_segments()``). Pfadregel #1409:
Aufloesung relativ zu dieser Testdatei (``from tests.tdd import ...``).
"""
from __future__ import annotations

from app.models import SegmentWeatherSummary
from tests.tdd import _hiking_window_fixtures as F


def _summary_and_segments(name: str):
    """Etappenaggregat (wie build_outlook_row es heute liest) UND die
    zugrundeliegenden Segmente derselben Sweep-Konstellation."""
    from services.weather_metrics import aggregate_stage

    segments = F.CONSTELLATIONS_BY_NAME[name].segments()
    return aggregate_stage(segments), segments


def _hiking(segments, field: str):
    from output.renderers.day_window import (
        collect_hiking_window_points, hiking_field_min_max,
    )

    return hiking_field_min_max(collect_hiking_window_points(segments), field)


# ---------------------------------------------------------------------------
# AC-1 -- Temperatur, fester Altform-Pfad (metrics=None): temp_hi/temp_lo
# ---------------------------------------------------------------------------

def test_ac1_vorbedingung_etappenaggregat_und_gehzeit_liefern_verschiedene_werte():
    """Kein AC, Testaufbau-Beleg: die gewaehlte Konstellation muss ueberhaupt
    divergieren, sonst pruefte AC-1 nichts (Muster #1841-Vorlage)."""
    summary, segments = _summary_and_segments("extremwert_an_der_ankunftsstunde")
    hiking = _hiking(segments, "t2m_c")
    assert hiking is not None, "Sweep-Konstellation liefert kein Gehzeit-Fenster"
    assert int(summary.temp_max_c) != int(hiking[1]), (
        f"Vorbedingung verletzt: Etappenaggregat ({summary.temp_max_c}) und "
        f"Gehzeit-Hoch ({hiking[1]}) sind gleich -- AC-1 koennte nichts pruefen."
    )


def test_ac1_altform_temp_hi_matches_hiking_window_not_stage_aggregate():
    """AC-1: Given eine Etappe, deren Ankunftsstunde im Gehzeit-Fenster das
    Tageshoch traegt, im vollen Etappenfenster aber nicht / When der
    Trip-Ausblick (feste Altform) fuer diese Etappe gerendert wird / Then
    zeigt die Temperatur-Hoch-Spalte denselben Wert wie
    ``hiking_field_min_max(collect_hiking_window_points(seg_weather), "t2m_c")``
    -- nicht mehr ``summary.temp_max_c`` des vollen Etappenfensters."""
    from output.renderers.email.outlook import build_outlook_row

    summary, segments = _summary_and_segments("extremwert_an_der_ankunftsstunde")
    hiking = _hiking(segments, "t2m_c")

    row = build_outlook_row(
        summary, points=[], weekday="Mo", tz=F.TZ,
        hiking_extrema={"t2m_c": hiking},
    )

    assert row["temp_hi"] == int(hiking[1]), (
        f"Ausblick-Hoch {row['temp_hi']} weicht vom Gehzeit-Hoch {int(hiking[1])} "
        f"ab (zeigt weiterhin das Etappenaggregat {summary.temp_max_c})."
    )
    assert row["temp_lo"] == int(hiking[0]), (
        f"Ausblick-Tief {row['temp_lo']} weicht vom Gehzeit-Tief {int(hiking[0])} ab."
    )


def test_ac1_configurable_path_temp_cell_matches_hiking_window():
    """AC-1, zweite Haelfte (Spec "Implementation Details"): derselbe Fehler
    besteht auch im konfigurierbaren ``cells``-Pfad (``metrics`` gesetzt) --
    ein Fix, der nur ``temp_lo``/``temp_hi`` ueberschreibt, traefe den in der
    Praxis ueberwiegend aktiven Pfad NICHT."""
    from output.renderers.email.outlook import build_outlook_row

    summary, segments = _summary_and_segments("extremwert_an_der_ankunftsstunde")
    hiking = _hiking(segments, "t2m_c")
    # #1848 A2: gewaehlt wird die KENNUNG; sie zeigt Tief UND Hoch in einer
    # Spannen-Zelle. Die Zusicherung wird dadurch SCHAERFER statt schwaecher:
    # jetzt muessen BEIDE Seiten aus dem Gehzeit-Fenster stammen, vorher nur
    # das Hoch.
    metrics = ["temperature"]

    row = build_outlook_row(
        summary, points=[], weekday="Mo", tz=F.TZ, metrics=metrics,
        hiking_extrema={"t2m_c": hiking},
    )

    cell = row["cells"][0]
    tief, hoch = cell.split()[0].split("/")
    assert int(float(hoch)) == int(hiking[1]), (
        f"Konfigurierbare Ausblick-Zelle {cell!r} zeigt nicht das Gehzeit-Hoch "
        f"{int(hiking[1])} (Etappenaggregat: {summary.temp_max_c})."
    )
    assert int(float(tief)) == int(hiking[0]), (
        f"Konfigurierbare Ausblick-Zelle {cell!r} zeigt nicht das Gehzeit-Tief "
        f"{int(hiking[0])} (Etappenaggregat: {summary.temp_min_c})."
    )


# ---------------------------------------------------------------------------
# AC-2 -- leeres Gehzeit-Fenster: Fail-soft-Rueckfall (GRUEN, Regressionsschutz)
# ---------------------------------------------------------------------------

def test_ac2_fail_soft_keeps_stage_aggregate_when_no_hiking_extrema_supplied():
    """AC-2: Given ein Segment, dessen Gehzeit-Fenster keinen einzigen
    Datenpunkt mit ``t2m_c`` traegt (Provider-Luecke) / When der
    Trip-Ausblick gerendert wird / Then faellt die Temperatur-Zelle
    fail-soft auf ``summary.temp_min_c``/``temp_max_c`` zurueck statt "-" zu
    zeigen oder abzustuerzen.

    GRUEN erwartet -- Regressionsschutz, kein Bug-Nachweis: kein Aufrufer
    liefert fuer diesen Fall einen ``hiking_extrema``-Eintrag (analog zu
    einem ``hiking_field_min_max()``-Ergebnis von ``None``), der Aufruf
    entspricht exakt dem heutigen Signaturstand -- muss vor UND nach dieser
    Aenderung gleich bleiben."""
    from output.renderers.email.outlook import build_outlook_row

    summary = SegmentWeatherSummary(temp_min_c=3.0, temp_max_c=11.0)
    row = build_outlook_row(summary, points=[], weekday="Mo", tz=F.TZ)

    assert row["temp_lo"] == 3 and row["temp_hi"] == 11, (
        f"Fail-soft-Rueckfall gebrochen: temp_lo/temp_hi={row['temp_lo']}/"
        f"{row['temp_hi']} statt des Etappenaggregats 3/11."
    )


# ---------------------------------------------------------------------------
# AC-3 -- gefuehlte Temperatur, NUR konfigurierbarer Pfad (kein Altform-Weg)
# ---------------------------------------------------------------------------

def test_ac3_vorbedingung_etappenaggregat_und_gehzeit_liefern_verschiedene_werte():
    """Kein AC, Testaufbau-Beleg fuer die gefuehlte Temperatur."""
    summary, segments = _summary_and_segments("extremwert_an_der_ankunftsstunde")
    hiking = _hiking(segments, "wind_chill_c")
    assert hiking is not None, "Sweep-Konstellation liefert kein Gehzeit-Fenster (gefuehlt)"
    assert int(summary.wind_chill_max_c) != int(hiking[1]), (
        f"Vorbedingung verletzt: Etappenaggregat ({summary.wind_chill_max_c}) und "
        f"Gehzeit-Hoch ({hiking[1]}) sind gleich -- AC-3 koennte nichts pruefen."
    )


def test_ac3_configurable_path_wind_chill_cell_matches_hiking_window():
    """AC-3: Given ``outlook_metrics`` waehlt gefuehlte Temperatur max / When
    der Trip-Ausblick gerendert wird / Then liest die Zelle aus
    ``hiking_field_min_max(punkte, "wind_chill_c")`` statt aus
    ``summary.wind_chill_max_c`` des vollen Etappenfensters -- strukturell
    derselbe Fehler wie AC-1, eigener Test wegen eigenem Datenfeld/Token
    (``FK``/``FD``, ``sms_trip.py:240``). Gefuehlte Temperatur hat keinen
    Altform-Weg (Spec "Implementation Details") -- nur der ``cells``-Pfad
    ist hier zu pruefen."""
    from output.renderers.email.outlook import build_outlook_row

    summary, segments = _summary_and_segments("extremwert_an_der_ankunftsstunde")
    hiking = _hiking(segments, "wind_chill_c")
    # #1848 A2: siehe AC-1 -- die Kennung zeigt beide Tagesenden, beide
    # muessen aus dem Gehzeit-Fenster stammen.
    metrics = ["wind_chill"]

    row = build_outlook_row(
        summary, points=[], weekday="Mo", tz=F.TZ, metrics=metrics,
        hiking_extrema={"wind_chill_c": hiking},
    )

    cell = row["cells"][0]
    tief, hoch = cell.split()[0].split("/")
    assert int(float(hoch)) == int(hiking[1]), (
        f"Konfigurierbare Ausblick-Zelle {cell!r} zeigt nicht das gefuehlte "
        f"Gehzeit-Hoch {int(hiking[1])} (Etappenaggregat: {summary.wind_chill_max_c})."
    )
    assert int(float(tief)) == int(hiking[0]), (
        f"Konfigurierbare Ausblick-Zelle {cell!r} zeigt nicht das gefuehlte "
        f"Gehzeit-Tief {int(hiking[0])} (Etappenaggregat: {summary.wind_chill_min_c})."
    )
