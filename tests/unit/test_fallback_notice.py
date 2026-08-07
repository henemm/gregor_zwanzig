"""TDD RED — Issue #1492 Scheibe 2b: Klartext-Formulierung der Herkunfts-Vertretung.

SPEC: docs/specs/modules/feat_1492_s2b_fallback_sichtbarkeit.md (R1-R7, AC-4..AC-9)

Prueft die geteilte, reine Formulierungsfunktion
``output.renderers.fallback_notice.build_fallback_lines(meta) -> list[str]``.
Sie existiert heute NICHT — alle Tests scheitern mit ``ModuleNotFoundError``
(der Import liegt bewusst IN den Testfunktionen, damit ein fehlendes Modul
keinen Collection-Error der ganzen Datei ausloest).

Zwei unabhaengige Zeilen (R1):
  1. Gewitterzeile — wenn ``fallback_metrics`` einen der Gewitter-Feldnamen
     traegt (SSoT: ``providers.thunder_enrichment``).
  2. Wetterzeile — wenn ``fallback_model`` gesetzt ist UND
     ``fallback_reason != "thunder_source_unavailable"``.

KEINE Mocks, KEIN Dateiinhalt-Check: echte ``ForecastMeta``-Objekte, echter
Funktionsaufruf.
"""
from __future__ import annotations

import contextlib
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest


# Pfadregel #1409: Prueflingsaufloesung relativ zu DIESER Datei, nie ueber
# einen festen Hauptrepo-Pfad — sonst misst der Worktree die fremde Kopie.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from app.models import ForecastMeta, Provider


# --- PO-freigegebener Wortlaut (Spec, Abschnitt "Wortlaut-Muster") ----------
_GEWITTER_MIT_QUELLE = "Gewitterdaten von Ersatzquelle: DWD Europa (gröbere Auflösung)"
_GEWITTER_OHNE_QUELLE = "Gewitterdaten von einer Ersatzquelle (gröbere Auflösung)"


def _thunder_field_names() -> list[str]:
    """Die Gewitter-Feldnamen aus der EINZIGEN Quelle der Wahrheit (R1).

    Kein Hartkodieren hier: waechst ``_SIGNAL_ZU_FELD`` um eine vierte
    Gewittergroesse, muss ``build_fallback_lines`` sie automatisch erkennen —
    dieser Test zieht dann von selbst mit.
    """
    from providers.thunder_enrichment import _EINZELWERT_FELD, _SIGNAL_ZU_FELD

    return sorted({*_SIGNAL_ZU_FELD.values(), _EINZELWERT_FELD})


def _make_meta(
    *,
    fallback_model: str | None = None,
    fallback_metrics: list[str] | None = None,
    fallback_reason: str | None = None,
) -> ForecastMeta:
    meta = ForecastMeta(
        provider=Provider.OPENMETEO,
        model="meteofrance_arome",
        run=datetime(2026, 8, 6, 0, 0, tzinfo=timezone.utc),
        grid_res_km=1.3,
        interp="grid_point",
    )
    meta.fallback_model = fallback_model
    meta.fallback_metrics = list(fallback_metrics or [])
    meta.fallback_reason = fallback_reason
    return meta


def _make_segment(
    *,
    segment_id: int = 1,
    with_timeseries: bool = True,
    has_error: bool = False,
    fallback_model: str | None = None,
    fallback_metrics: list[str] | None = None,
    fallback_reason: str | None = None,
):
    """Echtes ``SegmentWeatherData`` (kein Mock) fuer die Segmentauswahl.

    ``with_timeseries=False`` bildet den echten Provider-Fehlerfall ab: das
    Segment hat keine Zeitreihe und damit auch kein ``meta``.
    """
    from app.models import (
        GPXPoint, NormalizedTimeseries, SegmentWeatherData,
        SegmentWeatherSummary, TripSegment,
    )

    seg = TripSegment(
        segment_id=segment_id,
        start_point=GPXPoint(lat=39.7, lon=2.6, elevation_m=100.0),
        end_point=GPXPoint(lat=39.8, lon=2.7, elevation_m=200.0),
        start_time=datetime(2026, 8, 6, 8, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 8, 6, 10, 0, tzinfo=timezone.utc),
        duration_hours=2.0, distance_km=5.0, ascent_m=100.0, descent_m=0.0,
    )
    ts = None
    if with_timeseries:
        ts = NormalizedTimeseries(
            meta=_make_meta(
                fallback_model=fallback_model,
                fallback_metrics=fallback_metrics,
                fallback_reason=fallback_reason,
            ),
            data=[],
        )
    return SegmentWeatherData(
        segment=seg,
        timeseries=ts,
        aggregated=SegmentWeatherSummary(
            temp_min_c=10.0, temp_max_c=12.0, wind_max_kmh=15.0,
            precip_sum_mm=0.0, cloud_avg_pct=50,
        ),
        fetched_at=datetime.now(timezone.utc),
        provider="openmeteo",
        has_error=has_error,
    )


@contextlib.contextmanager
def _thunder_import_kaputt():
    """Laesst ``providers.thunder_enrichment`` ECHT am Importmechanismus
    scheitern — kein ``unittest.mock``, keine gefaelschte Rueckgabe.

    Ein Finder auf ``sys.meta_path`` protokolliert jeden Importversuch fuer
    genau dieses Modul und wirft dann ``ImportError``. Das Modul wird vorher
    aus ``sys.modules`` genommen (sonst wuerde der Import es dort finden und
    den Finder nie befragen) und danach wieder eingesetzt.

    Der Kontextmanager liefert die Liste der protokollierten Versuche —
    damit laesst sich auch pruefen, dass ein Import GAR NICHT stattfand.
    """
    name = "providers.thunder_enrichment"
    versuche: list[str] = []

    class _Blocker:
        def find_spec(self, fullname, path=None, target=None):
            if fullname == name:
                versuche.append(fullname)
                raise ImportError("simuliert: providers.thunder_enrichment kaputt")
            return None

    gesichert = sys.modules.pop(name, None)
    blocker = _Blocker()
    sys.meta_path.insert(0, blocker)
    try:
        yield versuche
    finally:
        sys.meta_path.remove(blocker)
        if gesichert is not None:
            sys.modules[name] = gesichert


def _thunder_line(lines: list[str]) -> str | None:
    return next((ln for ln in lines if ln.startswith("Gewitterdaten")), None)


def _weather_line(lines: list[str]) -> str | None:
    return next((ln for ln in lines if ln.startswith("Einzelne Wetterwerte")), None)


# ===========================================================================
# AC-6 — Normalfall: kein Fallback, keine Zeile.
# ===========================================================================

def test_no_fallback_returns_no_lines() -> None:
    """AC-6: Given ForecastMeta ohne jeden Fallback, When build_fallback_lines
    laeuft, Then ist die Rueckgabe eine leere Liste (kein leerer Rahmen, kein
    Artefakt, das ein Renderer spaeter verpacken wuerde)."""
    from output.renderers.fallback_notice import build_fallback_lines

    assert build_fallback_lines(_make_meta()) == []


# ===========================================================================
# AC-1 — Nur Gewitter-Vertretung: genau EINE Zeile, mit Quellen-Klartext.
# ===========================================================================

@pytest.mark.parametrize("feld", _thunder_field_names())
def test_thunder_only_shows_thunder_line_with_source(feld: str) -> None:
    """AC-1: Given fallback_metrics traegt einen Gewitter-Feldnamen und 2a hat
    die Ersatzquelle vermerkt (fallback_model='eu_direct',
    fallback_reason='thunder_source_unavailable'), When build_fallback_lines
    laeuft, Then genau EINE Zeile, die die Ersatzquelle in Klartext nennt
    ('DWD Europa') — und KEINE Wetterzeile (R1.2 schliesst sie aus, weil
    fallback_reason == 'thunder_source_unavailable').

    Abweichung vom Spec-GIVEN (als Befund gemeldet): die Spec notiert fuer
    diesen Test ``fallback_model=None``, verlangt aber gleichzeitig
    'DWD Europa' in der Ausgabe. Beides zusammen ist unerfuellbar — ohne
    ``fallback_model`` existiert kein Quellenname. Geprueft wird deshalb der
    Zustand, den ``thunder_enrichment.py:286-288`` im Gewitter-Alleinfall
    tatsaechlich schreibt.
    """
    from output.renderers.fallback_notice import build_fallback_lines

    lines = build_fallback_lines(_make_meta(
        fallback_metrics=[feld],
        fallback_model="eu_direct",
        fallback_reason="thunder_source_unavailable",
    ))

    assert lines == [_GEWITTER_MIT_QUELLE], (
        f"Gewitter-Alleinfall ({feld}) muss genau die Gewitterzeile mit "
        f"Quellen-Klartext liefern — war: {lines!r}"
    )


# ===========================================================================
# AC-4 — Nur Grundvorhersage-Fallback: Metriknamen in deutschem Klartext.
# ===========================================================================

def test_weather_only_shows_weather_line_translated() -> None:
    """AC-4: Given fallback_model='icon_eu', fallback_reason='model_5xx',
    fallback_metrics=['cape','visibility'], When build_fallback_lines laeuft,
    Then genau EINE Zeile mit 'Gewitterenergie, Sicht' und 'DWD Europa' —
    keine technische Kennung ('icon_eu', 'cape'), kein Wort 'Fallback'."""
    from output.renderers.fallback_notice import build_fallback_lines

    lines = build_fallback_lines(_make_meta(
        fallback_model="icon_eu",
        fallback_reason="model_5xx",
        fallback_metrics=["cape", "visibility"],
    ))

    assert lines == [
        "Einzelne Wetterwerte von Ersatzmodell: DWD Europa "
        "(Gewitterenergie, Sicht)"
    ], f"Wetterzeile mit uebersetzten Metriken erwartet — war: {lines!r}"
    joined = "\n".join(lines)
    assert "icon_eu" not in joined, f"Rohkennung icon_eu sichtbar: {joined!r}"
    assert "cape" not in joined, f"Rohkennung cape sichtbar: {joined!r}"
    assert "Fallback" not in joined, f"Technisches Wort 'Fallback' sichtbar: {joined!r}"


# ===========================================================================
# AC-5 + AC-8 — Kollisionsfall: zwei Zeilen, Gewitterzeile OHNE Quellenname,
#               Wetterzeile OHNE Gewitter-Metrik.
# ===========================================================================

def test_collision_shows_both_lines_thunder_without_source() -> None:
    """AC-5/AC-8: Given beide Mechanismen haben gefeuert (Grundvorhersage
    zuerst: fallback_model='icon_eu'/'model_5xx'; die Gewitter-Vertretung
    danach nur noch in fallback_metrics), When build_fallback_lines laeuft,
    Then ZWEI Zeilen. Die Gewitterzeile nennt KEINEN Quellennamen (R3:
    'icon_eu' ist der Name des FALSCHEN Ersatzmodells), die Wetterzeile
    enthaelt nur die Nicht-Gewitter-Metrik ('Gewitterenergie' aus 'cape'),
    NICHT 'Blitzpotenzial' (R4-Abzug)."""
    from output.renderers.fallback_notice import build_fallback_lines

    lines = build_fallback_lines(_make_meta(
        fallback_metrics=["cape", "lightning_potential_lpi_jkg"],
        fallback_model="icon_eu",
        fallback_reason="model_5xx",
    ))

    assert len(lines) == 2, f"Kollisionsfall muss zwei Zeilen liefern — war: {lines!r}"
    thunder, weather = _thunder_line(lines), _weather_line(lines)
    assert thunder is not None, f"Gewitterzeile fehlt: {lines!r}"
    assert weather is not None, f"Wetterzeile fehlt: {lines!r}"
    assert lines.index(thunder) < lines.index(weather), (
        f"Gewitterzeile steht laut Wortlaut-Muster VOR der Wetterzeile — war: {lines!r}"
    )

    assert thunder == _GEWITTER_OHNE_QUELLE, (
        f"Gewitterzeile im Kollisionsfall muss quellenlos sein — war: {thunder!r}"
    )
    assert "DWD Europa" not in thunder, (
        "R3-Verstoss: Gewitterzeile nennt den Klartextnamen des "
        f"Grundvorhersage-Ersatzmodells — {thunder!r}"
    )
    assert "icon_eu" not in thunder, (
        f"R3-Verstoss: Rohkennung des falschen Modells in der Gewitterzeile — {thunder!r}"
    )

    assert weather == (
        "Einzelne Wetterwerte von Ersatzmodell: DWD Europa (Gewitterenergie)"
    ), f"Wetterzeile ohne Gewitter-Metrik erwartet — war: {weather!r}"
    assert "Blitzpotenzial" not in weather, (
        f"AC-8-Verstoss: Gewitter-Metrik in der Wetterzeile — {weather!r}"
    )


# ===========================================================================
# R4/#1145 — Leere Restliste: Klammer entfaellt ersatzlos.
# ===========================================================================

def test_weather_line_empty_bracket_omitted() -> None:
    """R4/#1145: Given fallback_model='at_direct' und leere fallback_metrics,
    When build_fallback_lines laeuft, Then traegt die Wetterzeile weder eine
    leere Klammer noch ein Doppelpunkt-/Leerzeichen-Artefakt."""
    from output.renderers.fallback_notice import build_fallback_lines

    lines = build_fallback_lines(_make_meta(
        fallback_model="at_direct", fallback_metrics=[],
    ))

    assert lines == [
        "Einzelne Wetterwerte von Ersatzmodell: GeoSphere Österreich"
    ], f"Wetterzeile ohne Klammer erwartet — war: {lines!r}"
    line = lines[0]
    assert "(" not in line and ")" not in line, f"Klammer trotz leerer Restliste: {line!r}"
    assert " : " not in line, f"Leerzeichen-vor-Doppelpunkt-Artefakt (#1145): {line!r}"
    assert "  " not in line, f"Doppeltes Leerzeichen: {line!r}"
    assert not line.endswith(":"), f"Doppelpunkt ohne Inhalt: {line!r}"


# ===========================================================================
# AC-9/R7 — Unbekannte Kennungen erscheinen roh, ohne Absturz.
# ===========================================================================

def test_unknown_model_shows_raw_value() -> None:
    """AC-9/R7: Given fallback_model und ein Metrikname ohne hinterlegte
    Uebersetzung, When build_fallback_lines laeuft, Then erscheinen BEIDE
    Rohwerte unveraendert (kein KeyError, keine stille Auslassung)."""
    from output.renderers.fallback_notice import build_fallback_lines

    lines = build_fallback_lines(_make_meta(
        fallback_model="unbekanntes_modell_xyz",
        fallback_reason="model_5xx",
        fallback_metrics=["ein_unbekanntes_feld"],
    ))

    assert len(lines) == 1, f"Genau eine Wetterzeile erwartet — war: {lines!r}"
    line = lines[0]
    assert "unbekanntes_modell_xyz" in line, (
        f"R7: unuebersetzte Modellkennung muss roh erscheinen — {line!r}"
    )
    assert "ein_unbekanntes_feld" in line, (
        f"R7: unuebersetzter Metrikname darf nicht verschluckt werden — {line!r}"
    )


# ===========================================================================
# F001 — Segmentauswahl: ALLE Segmente durchsuchen, nicht nur das erste.
#
# Vorher gab es ZWEI verschiedene Auswahlregeln: die drei Mail-Renderer lasen
# starr ``segments[0]``, ``narrow.py`` das erste fehlerfreie Segment mit
# Zeitreihe. Beide verschweigen eine Vertretung, die erst eine spaetere
# Etappe betraf (ADR-0018/ADR-0047: Fallback ohne Kaschieren).
# ===========================================================================

def test_select_skips_segment_without_timeseries() -> None:
    """F001: Given Segment 1 hat einen Provider-Fehler (keine Zeitreihe) und
    Segment 2 traegt einen echten Fallback, When die Segmentauswahl laeuft,
    Then liefert sie das ``meta`` von Segment 2 — das fehlende ``meta`` von
    Segment 1 ist ein Ueberspringgrund, kein Abbruchgrund."""
    from output.renderers.fallback_notice import select_fallback_meta

    seg1 = _make_segment(segment_id=1, with_timeseries=False, has_error=True)
    seg2 = _make_segment(
        segment_id=2, fallback_model="icon_eu",
        fallback_metrics=["cape", "visibility"], fallback_reason="model_5xx",
    )

    meta = select_fallback_meta([seg1, seg2])
    assert meta is not None, "Fallback aus Segment 2 wurde nicht gefunden"
    assert meta.fallback_model == "icon_eu"


def test_select_skips_segment_without_fallback() -> None:
    """F001: Given Segment 1 ist fehlerfrei UND ohne Fallback, Segment 2
    traegt einen Fallback, When die Segmentauswahl laeuft, Then liefert sie
    das ``meta`` von Segment 2.

    Das ist der Fall, den BEIDE frueheren Varianten verschluckt haben:
    ``segments[0]`` ebenso wie „erstes fehlerfreies Segment"."""
    from output.renderers.fallback_notice import select_fallback_meta

    seg1 = _make_segment(segment_id=1)
    seg2 = _make_segment(
        segment_id=2, fallback_model="at_direct", fallback_reason="model_5xx",
    )

    meta = select_fallback_meta([seg1, seg2])
    assert meta is not None, "Fallback aus Segment 2 wurde nicht gefunden"
    assert meta.fallback_model == "at_direct"


def test_select_finds_thunder_only_marking_without_model() -> None:
    """F001: Eine Gewitter-Vertretung kann sich allein in ``fallback_metrics``
    zeigen (R2: der Merge-Schutz aus 2a laesst ``fallback_model`` belegt).
    Auch dieses Segment muss die Auswahl finden."""
    from output.renderers.fallback_notice import select_fallback_meta

    seg1 = _make_segment(segment_id=1)
    seg2 = _make_segment(
        segment_id=2, fallback_metrics=["lightning_potential_lpi_jkg"],
    )

    meta = select_fallback_meta([seg1, seg2])
    assert meta is not None, "Gewitter-Markierung ohne fallback_model uebersehen"
    assert meta.fallback_metrics == ["lightning_potential_lpi_jkg"]


def test_select_returns_none_without_any_fallback() -> None:
    """AC-6 Gegenprobe: Given kein Segment traegt eine Fallback-Markierung,
    When die Segmentauswahl laeuft, Then liefert sie ``None`` — und
    ``build_fallback_lines(None)`` daraufhin keine Zeile."""
    from output.renderers.fallback_notice import build_fallback_lines, select_fallback_meta

    segmente = [
        _make_segment(segment_id=1),
        _make_segment(segment_id=2, with_timeseries=False, has_error=True),
        _make_segment(segment_id=3),
    ]

    assert select_fallback_meta(segmente) is None
    assert build_fallback_lines(select_fallback_meta(segmente)) == []


def test_select_takes_first_marked_segment() -> None:
    """Known Limitation (Spec): tragen mehrere Segmente unterschiedliche
    Vertretungen, gewinnt die ERSTE gefundene. Die Aussage lautet „hier wurde
    ausgewichen", nicht „auf Etappe N wurde ausgewichen"."""
    from output.renderers.fallback_notice import select_fallback_meta

    seg1 = _make_segment(segment_id=1, fallback_model="icon_eu", fallback_reason="model_5xx")
    seg2 = _make_segment(segment_id=2, fallback_model="at_direct", fallback_reason="model_5xx")

    meta = select_fallback_meta([seg1, seg2])
    assert meta is not None and meta.fallback_model == "icon_eu"


def test_select_handles_empty_segment_list() -> None:
    """Grenzfall: leere Segmentliste stuerzt nicht ab."""
    from output.renderers.fallback_notice import select_fallback_meta

    assert select_fallback_meta([]) is None


# ===========================================================================
# F002 — Der Hinweis darf das Briefing nicht mitreissen.
#
# ADR-0047 Entscheidung 3: ein Ausfall der Gewitterquelle darf die
# Grundvorhersage nie kippen. Fuer den Anzeigeweg gilt dasselbe Prinzip.
# ===========================================================================

def test_no_fallback_does_not_import_thunder_provider() -> None:
    """F002: Given ein ``meta`` ganz ohne Fallback (Normalfall), When
    ``build_fallback_lines`` laeuft, Then wird ``providers.thunder_enrichment``
    GAR NICHT erst importiert — ein kaputter Provider-Zweig kann das Briefing
    dann nicht mitreissen."""
    from output.renderers.fallback_notice import build_fallback_lines

    with _thunder_import_kaputt() as versuche:
        lines = build_fallback_lines(_make_meta())

    assert lines == [], f"Normalfall muss leer bleiben — war: {lines!r}"
    assert versuche == [], (
        "F002: der Provider-Import wurde im Normalfall ohne Fallback versucht "
        f"— Versuche: {versuche!r}"
    )


def test_broken_thunder_import_still_renders_weather_line() -> None:
    """F002/F003: Given ``providers.thunder_enrichment`` ist nicht importierbar
    und ein Grundvorhersage-Fallback liegt vor, When ``build_fallback_lines``
    laeuft, Then wirft die Funktion nicht — die Gewitterzeile entfaellt, die
    WETTERZEILE BLEIBT.

    Die Klammer entfaellt dabei ebenfalls (F003): ohne die Feldnamen ist nicht
    entscheidbar, ob ``visibility`` ein Wetter- oder ein Gewitter-Feld ist. Die
    Erwartung wurde gegenueber dem F002-Stand bewusst geaendert — dort stand
    ``(Sicht)``, was im Kollisionsfall zu einer FALSCHEN Zuschreibung fuehrte.
    Zugesichert bleibt hier, was F002 zusicherte: kein Absturz, die Zeile
    ueberlebt."""
    from output.renderers.fallback_notice import build_fallback_lines

    with _thunder_import_kaputt() as versuche:
        lines = build_fallback_lines(_make_meta(
            fallback_model="icon_eu",
            fallback_reason="model_5xx",
            fallback_metrics=["visibility"],
        ))

    assert versuche, "Vorbedingung: bei nicht-leeren fallback_metrics wird importiert"
    assert lines == [
        "Einzelne Wetterwerte von Ersatzmodell: DWD Europa"
    ], f"Wetterzeile muss den Importfehler ueberleben — war: {lines!r}"


def test_broken_thunder_import_drops_only_thunder_line() -> None:
    """F002: Given der Importfehler, eine reine Gewitter-Markierung UND
    ZUSAETZLICH ein Grundvorhersage-Fallback, When ``build_fallback_lines``
    laeuft, Then bleibt GENAU EINE Zeile uebrig — die Wetterzeile —, und die
    Gewitterzeile fehlt.

    L1/L2: die fruehere Fassung setzte ``fallback_reason``
    ``"thunder_source_unavailable"`` und erwartete ``lines == []``. Damit war
    sie auch dann gruen, wenn ``build_fallback_lines`` im Importfehlerfall
    pauschal ALLES verschluckt — sie konnte „richtig unterdrueckt" nicht von
    „gar nichts getan" unterscheiden und hielt den eigenen Namen („drops ONLY
    the thunder line") nicht. Erst der Zustand mit BEIDEN Zeilen im Normalfall
    macht den Unterschied messbar.
    """
    from output.renderers.fallback_notice import build_fallback_lines

    kwargs = dict(
        fallback_metrics=["lightning_potential_lpi_jkg"],
        fallback_model="icon_eu",
        fallback_reason="model_5xx",
    )

    # Vorbedingung: bei INTAKTEM Import traegt genau diese Eingabe BEIDE
    # Zeilen. Ohne diesen Bezugspunkt sagt das Fehlen der Gewitterzeile unten
    # nichts aus — sie koennte auch aus anderen Gruenden nie entstanden sein.
    intakt = build_fallback_lines(_make_meta(**kwargs))
    assert _thunder_line(intakt) is not None, (
        f"Vorbedingung: bei intaktem Import muss die Gewitterzeile da sein — {intakt!r}"
    )
    assert _weather_line(intakt) is not None, (
        f"Vorbedingung: bei intaktem Import muss die Wetterzeile da sein — {intakt!r}"
    )

    with _thunder_import_kaputt() as versuche:
        lines = build_fallback_lines(_make_meta(**kwargs))

    assert versuche, "Vorbedingung: bei nicht-leeren fallback_metrics wird importiert"
    assert len(lines) == 1, (
        "Der Importfehler darf NUR die Gewitterzeile kosten — genau eine Zeile "
        f"muss uebrig bleiben, war: {lines!r}"
    )
    assert _thunder_line(lines) is None, (
        f"Ohne die Feldnamen ist die Gewitterzeile nicht bildbar — war: {lines!r}"
    )
    assert lines == ["Einzelne Wetterwerte von Ersatzmodell: DWD Europa"], (
        "Die Wetterzeile muss den Importfehler ueberleben (ohne Klammer, weil "
        f"die Trennung nicht moeglich ist) — war: {lines!r}"
    )


# ===========================================================================
# F003 — Keine FALSCHE Zuschreibung: lieber gar keine Werte nennen.
#
# Bricht der Provider-Import, kennt dieses Modul die Gewitter-Feldnamen nicht
# mehr und kann Gewitter- von Wetterwerten nicht mehr TRENNEN. Der R4-Abzug
# greift dann nicht — ein Gewitter-Feldname landete bisher in der Klammer der
# WETTERZEILE und wurde damit dem Ersatzmodell der Grundvorhersage
# zugeschrieben, das mit den Blitzdaten nichts zu tun hat (AC-8-Verstoss).
#
# Tech-Lead-Entscheidung: koennen die beiden Herkuenfte nicht sicher getrennt
# werden, nennt die Wetterzeile GAR KEINE Werte. Weniger Information ist
# hinnehmbar, eine falsche Zuschreibung nicht.
# ===========================================================================

def test_broken_import_with_collision_drops_weather_bracket() -> None:
    """F003/AC-8: Given der Kollisionsfall (``fallback_metrics`` traegt einen
    Gewitter- UND einen Nicht-Gewitter-Feldnamen) UND ein kaputter
    ``providers.thunder_enrichment``-Import, When ``build_fallback_lines``
    laeuft, Then traegt die Wetterzeile UEBERHAUPT KEINE Klammer — insbesondere
    keinen Gewitter-Feldnamen, der sonst faelschlich dem
    Grundvorhersage-Ersatzmodell zugeschrieben wuerde."""
    from output.renderers.fallback_notice import build_fallback_lines

    with _thunder_import_kaputt() as versuche:
        lines = build_fallback_lines(_make_meta(
            fallback_metrics=["cape", "lightning_potential_lpi_jkg"],
            fallback_model="icon_eu",
            fallback_reason="model_5xx",
        ))

    assert versuche, "Vorbedingung: bei nicht-leeren fallback_metrics wird importiert"

    # L3: Zeilenzahl mitpruefen — sonst faellt weder „eine Zeile zu viel" noch
    # „eine Zeile zu wenig" auf. Der Zugriff ueber `_weather_line()` unten
    # findet die Wetterzeile auch dann, wenn daneben noch eine zweite,
    # unerwuenschte Zeile steht; genau das blieb hier vorher unbemerkt.
    assert len(lines) == 1, (
        "Im Kollisionsfall mit kaputtem Import darf GENAU EINE Zeile entstehen "
        f"— die Wetterzeile — war: {lines!r}"
    )
    assert _thunder_line(lines) is None, (
        "Ohne die Feldnamen ist die Gewitterzeile nicht bildbar und darf hier "
        f"nicht auftauchen — war: {lines!r}"
    )

    weather = _weather_line(lines)
    assert weather is not None, (
        f"Die Wetterzeile selbst muss den Importfehler ueberleben — war: {lines!r}"
    )
    assert weather == "Einzelne Wetterwerte von Ersatzmodell: DWD Europa", (
        "F003: ohne die Feldnamen ist keine Trennung moeglich — dann nennt die "
        f"Wetterzeile GAR KEINE Werte — war: {weather!r}"
    )
    assert "(" not in weather and ")" not in weather, (
        f"F003: Klammer trotz unmoeglicher Trennung — {weather!r}"
    )
    for feld in ("Blitzpotenzial", "Blitzdichte", "Hagelsignal"):
        assert feld not in weather, (
            f"F003/AC-8-Verstoss: Gewitter-Klartext {feld!r} faelschlich dem "
            f"Grundvorhersage-Ersatzmodell zugeschrieben — {weather!r}"
        )
    # Auch der Rohname darf nicht durchrutschen (R7 uebersetzt Unbekanntes roh).
    assert "lightning_potential_lpi_jkg" not in weather, (
        f"F003: Roher Gewitter-Feldname in der Wetterzeile — {weather!r}"
    )
