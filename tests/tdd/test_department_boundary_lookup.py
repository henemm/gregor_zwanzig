"""TDD — Département-Grenzen für lookup_department (Issue #1254).

SPEC: docs/specs/modules/issue_1254_department_boundaries.md
AC-1 bis AC-7.

KEINE Mocks für das Kernverhalten (CLAUDE.md-Projektkonvention): alle Tests
rufen die echte `lookup_department(lat, lon)` gegen die (zukuenftig)
gebuendelte `department_polygons.json` auf. Heute (vor dem Fix) loest die
Funktion ausschliesslich per Naechster-Nachbar-Zentroid auf — Draguignan und
Fréjus werden deshalb falsch dem entfernten Nachbar-Département zugeordnet
(RED-Beweis fuer AC-1/AC-2, im Subset von AC-3).
"""
from __future__ import annotations

import logging

import pytest

from services.official_alerts import department_mapper
from services.official_alerts.department_mapper import lookup_department


@pytest.fixture(autouse=True)
def _clear_lookup_department_cache():
    """F004 (Issue #1400 Fix-Loop): `lookup_department()` cacht jetzt ueber
    `functools.lru_cache` (`_lookup_department_cached`), geschluesselt auf
    gerundete Koordinaten. Tests, die `_DEPARTMENT_POLYGONS` monkeypatchen
    (s. `test_degraded_state_empty_polygons_still_falls_back_for_any_point`),
    wuerden sonst einen VOR dem Monkeypatch gecachten Treffer fuer dieselbe
    Koordinate aus einem frueheren Test wiederverwenden -- autouse leert den
    Cache vor UND nach jedem Test dieser Datei."""
    department_mapper._lookup_department_cached.cache_clear()
    yield
    department_mapper._lookup_department_cached.cache_clear()


def test_draguignan_maps_to_var_83():
    """AC-1: Draguignan liegt real im Département Var (83), nicht in 04
    (Alpes-de-Haute-Provence), obwohl dessen Praefektur-Zentroid (Digne)
    naeher liegt als die Praefektur von 83 (Toulon)."""
    assert lookup_department(43.5402, 6.4665) == "83"


def test_frejus_maps_to_var_83():
    """AC-2: Fréjus liegt real im Département Var (83), nicht in 06
    (Alpes-Maritimes), obwohl dessen Praefektur-Zentroid (Nice) naeher liegt
    als die Praefektur von 83 (Toulon)."""
    assert lookup_department(43.4332, 6.7370) == "83"


@pytest.mark.parametrize(
    "lat,lon,expected",
    [
        (43.5402, 6.4665, "83"),  # Draguignan
        (43.4332, 6.7370, "83"),  # Fréjus
        (43.4055, 6.0619, "83"),  # Brignoles
        (43.1258, 5.9304, "83"),  # Toulon
        (43.8339, 5.7870, "04"),  # Manosque
        (43.8470, 6.5127, "04"),  # Castellane
        (44.3866, 6.6521, "04"),  # Barcelonnette
        (43.7765, 7.5027, "06"),  # Menton
    ],
)
def test_border_towns_resolve_to_true_department(lat, lon, expected):
    """AC-3: eine Referenzliste echter Grenzorte muss jeweils im
    tatsaechlichen Département ihrer realen Lage landen, nicht im Département
    des naechstgelegenen Praefektur-Zentroids."""
    assert lookup_department(lat, lon) == expected


def test_corsica_contract_preserved():
    """AC-4 (Regressionsschutz, kein RED-Beweis noetig): Korsika bleibt als
    zwei normale Codes "2A"/"2B" aufgeloest, kein Sonderfall-Zweig."""
    assert lookup_department(41.9192, 8.7386) == "2A"  # Ajaccio
    assert lookup_department(42.6979, 9.4508) == "2B"  # Bastia


def test_point_outside_all_polygons_returns_none_when_polygons_loaded():
    """AC-5 (Issue #1400, ersetzt die fruehere AC-5-Erwartung): eine
    Koordinate klar ausserhalb aller Département-Polygone UND ausserhalb des
    5-km-Randpuffers (F001-Nachbesserung, s.
    `test_near_coast_point_within_5km_buffer_resolves_to_nearest_department`)
    — hier ein Punkt weit im Mittelmeer (gemessen ~55 km vom naechsten
    Département-Rand entfernt) — liefert `None`, solange Polygondaten
    geladen sind. Der Zentroid-Notbehelf greift NUR noch im degradierten
    Fall (leere Polygonliste, s. `test_missing_polygon_file_falls_back_failsoft`).
    Vorher lieferte der Notbehelf bedingungslos einen (falschen) franzoesischen
    Code — genau der Bug, der jedem Punkt der Erde ein Département
    zuordnete (#1400)."""
    result = lookup_department(42.50, 6.50)
    assert result is None


def test_near_coast_point_within_5km_buffer_resolves_to_nearest_department():
    """Adversary-Nachbesserung F001: ein Punkt knapp (~4 km, gemessen)
    ausserhalb aller Polygone, aber innerhalb des 5-km-Randpuffers (hier: ein
    Punkt im Mittelmeer nahe der Provence-Kueste, vor Toulon), wird dem
    naechstgelegenen Département zugerechnet statt `None` zu liefern —
    Vereinfachungsartefakte an der Kueste sollen den Randpuffer genau
    dafuer abfangen."""
    assert lookup_department(43.00, 6.30) == "83"


@pytest.mark.parametrize(
    "lat,lon,ort",
    [
        (45.4642, 9.1900, "Mailand"),
        (46.9480, 7.4474, "Bern"),
        (47.9990, 7.8421, "Freiburg im Breisgau"),
        (41.3874, 2.1686, "Barcelona"),
        (-33.8688, 151.2093, "Sydney"),
        (90.0, 0.0, "Nordpol"),
        (40.7128, -74.0060, "New York"),
        (55.7558, 37.6173, "Moskau"),
    ],
)
def test_points_outside_france_return_none_not_a_french_code(lat, lon, ort):
    """Issue #1400: Punkte klar ausserhalb Frankreichs — auch solche, die
    (ueber den fruehereren, bedingungslosen Zentroid-Notbehelf) frueher einen
    franzoesischen Département-Code bekamen, weil der AROME-Bbox-Vorfilter
    von VigilanceSource sie einschliesst (Mailand/Bern/Freiburg/Barcelona)
    oder weil der Notbehelf schlicht IMMER einen Code lieferte (Sydney,
    Nordpol, New York, Moskau) — muessen `None` liefern."""
    assert lookup_department(lat, lon) is None, (
        f"{ort} ({lat}, {lon}) darf keinen franzoesischen Département-Code "
        f"bekommen (Issue #1400)"
    )


def test_missing_polygon_file_falls_back_failsoft(tmp_path, caplog):
    """AC-6: fehlende/kaputte Polygondatei darf den Import von
    `services.official_alerts` NICHT reissen und `lookup_department` muss
    fail-soft auf die bestehende Nearest-Centroid-Logik zurueckfallen, dabei
    eine Warnung loggen.

    Erwartetes Ziel-Interface (analog `massif_zones._load_massifs` /
    `massif_zones._DATA_PATH`, Issue #1037-Muster), das die Implementierung
    in `department_mapper.py` bereitstellen MUSS:

    - Modul-Attribut `_DATA_PATH: Path` — Standardpfad der gebuendelten
      `department_polygons.json`.
    - Funktion `_load_department_polygons(path: Path = _DATA_PATH) -> list`
      — laedt die Polygondaten, faengt fehlende/kaputte Dateien fail-soft ab
      (loggt `logger.warning(...)`, liefert `[]`, wirft NIE eine Exception).

    Solange dieses Interface in `department_mapper.py` noch nicht existiert,
    ist dieser Test RED (AttributeError) — das ist im TDD-RED-Schritt
    ausdruecklich erwuenscht (Zielverhalten, nicht Ist-Zustand).
    """
    missing = tmp_path / "nonexistent_department_polygons.json"
    with caplog.at_level(logging.WARNING):
        result = department_mapper._load_department_polygons(missing)
    assert result == [], "fehlende Datei muss [] liefern, kein Crash"
    assert any(r.levelno >= logging.WARNING for r in caplog.records), (
        "fehlende Datei muss eine Warnung loggen"
    )

    broken = tmp_path / "broken_department_polygons.json"
    broken.write_text("{ das ist kein json ]")
    caplog.clear()
    with caplog.at_level(logging.WARNING):
        result_broken = department_mapper._load_department_polygons(broken)
    assert result_broken == [], "kaputte Datei muss [] liefern, kein Crash"

    # Import bleibt intakt + fail-soft Fallback: bereits heute korrekt
    # aufgeloeste Orte (Nearest-Centroid) bleiben unveraendert korrekt.
    assert lookup_department(43.1258, 5.9304) == "83"  # Toulon


def test_previously_correct_towns_no_regression():
    """AC-7: bereits vorher korrekt aufgeloeste Orte bleiben nach dem Fix
    unveraendert korrekt (keine Regression)."""
    assert lookup_department(43.1258, 5.9304) == "83"  # Toulon
    assert lookup_department(43.8339, 5.7870) == "04"  # Manosque
    assert lookup_department(43.7765, 7.5027) == "06"  # Menton
    assert lookup_department(43.4055, 6.0619) == "83"  # Brignoles


@pytest.mark.parametrize(
    "lat,lon",
    [
        (44.3796, 4.9895),  # Valréas
        (44.3311, 4.9291),  # Visan
        (44.3626, 4.9455),  # Grillon
    ],
)
def test_enclave_des_papes_maps_to_vaucluse_84(lat, lon):
    """AC-8: die Enclave des Papes (Valréas/Visan/Grillon) ist eine Exklave
    des Départements Vaucluse (84), vollstaendig vom Département Drôme (26)
    umschlossen. Ohne Loch-Behandlung im 26-Polygon liefert die einfache
    Exterior-Ring-Pruefung faelschlich "26", weil das 26-Aussenpolygon die
    Enklave mit-abdeckt."""
    assert lookup_department(lat, lon) == "84"


def test_degraded_state_empty_polygons_still_falls_back_for_any_point(monkeypatch):
    """Issue #1400 AC (Gegenprobe zum Fix): ist ``_DEPARTMENT_POLYGONS``
    global leer (Datei fehlt/kaputt — der DEGRADIERTE Fall), greift der
    Zentroid-Notbehelf weiterhin fail-soft fuer JEDEN Punkt, auch fuer einen
    Punkt weit ausserhalb Frankreichs. Das ist bewusst weiterhin so (fail-
    soft heisst: lieber ein grober Rateversuch als ein kompletter Ausfall der
    Vigilance-Quelle) — der Fix aus #1400 wirkt NUR im Normalfall (Polygone
    geladen), nicht im degradierten Fall."""
    monkeypatch.setattr(department_mapper, "_DEPARTMENT_POLYGONS", [])
    result = department_mapper.lookup_department(-33.8688, 151.2093)  # Sydney
    assert result is not None
    assert result in department_mapper.DEPARTMENT_CENTROIDS


# ---------------------------------------------------------------------------
# Adversary-Nachbesserung F001 (Issue #1400 Fix-Loop): echte franzoesische
# Kuesten-/Inselorte, deren Landmasse durch die Polygon-Vereinfachung
# (`simplify(0.005, ...)`, s. Modul-Docstring) knapp ausserhalb ihres eigenen
# Départements liegt. Ohne den 5-km-Randpuffer liefert `lookup_department()`
# hier faelschlich `None` -- stiller Warnungs-Verlust auf bewohnten Inseln.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "lat,lon,expected,ort",
    [
        (46.1833, -1.4167, "17", "Île de Ré (Zentrum)"),
        (46.9833, -2.1667, "85", "Île de Noirmoutier"),
        (48.2814, -4.5936, "29", "Camaret-sur-Mer (Presqu'île de Crozon)"),
    ],
)
def test_f001_real_french_coastal_points_resolve_via_border_buffer(lat, lon, expected, ort):
    """Adversary F001: die drei belegten Fundstellen (Abstand zum naechsten
    Polygonrand 0,05 km / 2,89 km / 0,09 km, alle unterhalb der 5-km-
    Schwelle) muessen ihr tatsaechliches Département liefern, nicht `None`."""
    assert lookup_department(lat, lon) == expected, (
        f"{ort} ({lat}, {lon}) muss trotz Polygon-Vereinfachungsartefakt "
        f"Département {expected} liefern (Issue #1400 Adversary F001)"
    )


def test_f001_threshold_constant_is_five_km():
    """Haelt die gewaehlte Schwelle als Wert fest (Regressionswaechter gegen
    unbemerktes Verrutschen, wie vom Team-Lead gefordert). 5 km wurden aus
    dem schlechtesten belegten F001-Fall (Noirmoutier, 2,89 km) plus
    Sicherheitsmarge abgeleitet -- s. Modul-Docstring fuer die volle
    Messreihe inkl. der akzeptierten Nebenwirkung (Basel/Genf/Saarbruecken)."""
    assert department_mapper._NEAR_BORDER_THRESHOLD_KM == 5.0


def test_f001_point_just_beyond_threshold_stays_none():
    """Gegenprobe zum Randpuffer: ein Punkt, der (gemessen) klar ausserhalb
    der 5-km-Schwelle liegt (~55 km, derselbe Punkt wie
    `test_point_outside_all_polygons_returns_none_when_polygons_loaded`),
    bleibt `None` -- der Puffer ist begrenzt, kein unbegrenzter Notbehelf."""
    assert lookup_department(42.50, 6.50) is None


@pytest.mark.parametrize(
    "lat,lon,ort",
    [
        (47.5596, 7.5886, "Basel"),
        (46.2044, 6.1432, "Genf"),
    ],
)
def test_f001_accepted_side_effect_nearby_foreign_cities_included(lat, lon, ort):
    """Dokumentierte, PO-akzeptierte Nebenwirkung des 5-km-Randpuffers:
    Basel (1,81 km) und Genf (4,33 km) liegen selbst so nah an der
    franzoesischen Grenze, dass sie in den Puffer fallen und ein
    franzoesisches Département zugeordnet bekommen. Bewusst in Kauf
    genommen (PO: "Wetter haelt sich nicht an Staatsgrenzen") -- Gegenprobe
    zu `test_points_outside_france_return_none_not_a_french_code`, wo
    WEITER entfernte Grenzstaedte (Freiburg 16,6 km, Bern 49,8 km) korrekt
    `None` bleiben."""
    assert lookup_department(lat, lon) is not None, (
        f"{ort} liegt innerhalb der 5-km-Schwelle -- akzeptierte Nebenwirkung, "
        f"kein Fehlschlag dieses Tests"
    )


# ---------------------------------------------------------------------------
# Adversary-Nachbesserung F003 (Issue #1400 Fix-Loop, KRITISCH): der
# Randpuffer aus F001 durchsuchte nur Exterior-Ringe und ignorierte Holes.
# Llívia (spanische Gemeinde, vollstaendig von Département 66 umschlossen,
# im Datensatz OHNE eigenes Polygon, weil Spanien darin nicht vorkommt) liegt
# nur ~2,9-4,2 km vom Aussenrand von 66 entfernt -- deutlich innerhalb der
# 5-km-Schwelle. Ohne Hole-Vorabpruefung haette der Puffer Llívia faelschlich
# Département 66 zugeordnet -- der Enklaven-Schutz aus #1254 (Enclave des
# Papes) waere fuer JEDES Hole ohne eigenes Polygon wirkungslos gewesen.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "lat,lon,ort",
    [
        (42.470394, 1.982462, "Llívia-Zentrum"),
        (42.47044, 1.96342, "Llívia-Westrand"),
        (42.45013, 1.98405, "Llívia-Suedrand"),
    ],
)
def test_f003_llivia_stays_none_despite_nearby_department_66_border(lat, lon, ort):
    """Adversary F003: alle drei Punkte liegen NACHWEISLICH innerhalb des
    Holes fuer Llívia UND innerhalb der 5-km-Schwelle zum Aussenrand von
    Département 66 (2,88-4,18 km, gemessen) -- also GENAU der Fall, in dem
    der F001-Puffer ohne Hole-Pruefung faelschlich "66" liefern wuerde.
    Muss `None` bleiben: Llívia ist spanisches Staatsgebiet."""
    assert lookup_department(lat, lon) is None, (
        f"{ort} ({lat}, {lon}) liegt in Spanien (Enklave Llívia) und darf "
        f"KEIN franzoesisches Département bekommen (Issue #1400 Adversary F003)"
    )


def test_f003_point_in_hole_stays_none_even_with_exterior_within_threshold():
    """Direkter Beweis der Abwaegung aus F003: `Llívia-Westrand` liegt nur
    2,875 km (gemessen) vom Aussenrand von Département 66 entfernt --
    WEIT innerhalb der 5-km-Schwelle, also naeher als z.B. Île de Noirmoutier
    (2,89 km, wird korrekt zugeordnet). Der EINZIGE Unterschied ist die
    Hole-Mitgliedschaft -- und die MUSS gewinnen."""
    westrand = (42.47044, 1.96342)
    from services.official_alerts import department_mapper as dm

    # Vorbedingung explizit machen: der Punkt liegt tatsaechlich im Hole
    # UND sein naechster Aussenrand liegt innerhalb der Schwelle.
    assert dm._point_in_any_hole(*westrand) is True
    assert lookup_department(*westrand) is None


def test_f003_enclave_des_papes_regression_still_maps_to_vaucluse_84():
    """Gegenprobe: die Enclave des Papes (Hole MIT eigenem Polygon, 84 in
    26) bleibt von der F003-Nachbesserung unberuehrt -- weiterhin `84` ueber
    den exakten Point-in-Polygon-Treffer in Schritt 1 (nicht ueber den
    Puffer)."""
    for lat, lon in ((44.3796, 4.9895), (44.3311, 4.9291), (44.3626, 4.9455)):
        assert lookup_department(lat, lon) == "84"


def test_f003_coastal_findings_from_f001_still_resolve_correctly():
    """Gegenprobe: die drei F001-Kuesten-Fundstellen (Île de Ré, Île de
    Noirmoutier, Camaret-sur-Mer) liefern nach der F003-Hole-Vorabpruefung
    weiterhin ihr korrektes Département -- die Vorabpruefung darf normale
    Randpuffer-Faelle (kein Hole beteiligt) nicht beeintraechtigen."""
    assert lookup_department(46.1833, -1.4167) == "17"  # Île de Ré
    assert lookup_department(46.9833, -2.1667) == "85"  # Île de Noirmoutier
    assert lookup_department(48.2814, -4.5936) == "29"  # Camaret-sur-Mer


# ---------------------------------------------------------------------------
# F004 (Issue #1400 Fix-Loop, Performance): Memoisierung von
# `lookup_department()` ueber `functools.lru_cache`, geschluesselt auf eine
# auf 4 Nachkommastellen gerundete Koordinate (~11 m, Vorbild
# `geosphere_warn._round_coord`).
# ---------------------------------------------------------------------------

def test_f004_repeated_lookup_for_same_point_is_cached():
    """GIVEN derselbe Wegpunkt wird mehrfach nachgeschlagen, WHEN
    `lookup_department()` wiederholt aufgerufen wird, THEN steigt
    `_lookup_department_cached.cache_info().hits`, statt bei jedem Aufruf
    den vollen Segment-Scan zu wiederholen."""
    department_mapper._lookup_department_cached.cache_clear()
    point = (47.2692, 11.4041)  # Innsbruck -- garantierter Nicht-Treffer, teuerster Pfad
    lookup_department(*point)
    info_after_first = department_mapper._lookup_department_cached.cache_info()
    for _ in range(10):
        lookup_department(*point)
    info_after_more = department_mapper._lookup_department_cached.cache_info()
    assert info_after_more.hits == info_after_first.hits + 10, (
        f"10 Wiederholungsaufrufe muessen 10 zusaetzliche Cache-Treffer ergeben, "
        f"war {info_after_more.hits - info_after_first.hits}"
    )


# ---------------------------------------------------------------------------
# Adversary-Nachbesserung F005 (Issue #1400 Fix-Loop, KRITISCH): die
# Rundung des Lookup-Cache-Schluessels (F004) erzeugt ein ~11-m-Fehlerband
# entlang JEDER Grenze, die sie beruehrt -- auch der Llívia-Enklavengrenze.
# Ein Feingitter-Scan des Adversary-Pruefers (3.835 Punkte) fand 5 Punkte,
# die ROH nachweislich im Hole liegen, nach der Rundung aber ausserhalb
# landen und faelschlich "66" statt `None` lieferten. Fix: die
# Hole-Mitgliedschaftspruefung laeuft seither IMMER auf der rohen
# Koordinate (s. `lookup_department()`-Docstring) -- diese Tests messen
# DIREKT AN DER ECHTEN GRENZE, nicht wie zuvor Hole-Zentrum gegen
# franzoesisches Landesinneres (das haette diesen Fund nie beruehrt).
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "lat,lon,ort",
    [
        (42.45855, 2.00006, "F005-Beispiel (Adversary, 5,3 m von der Grenze)"),
        (42.44755, 1.9899, "Feingitter-Fund 1"),
        (42.4507375, 2.00875, "Feingitter-Fund 2"),
        (42.4596625, 1.997875, "Feingitter-Fund 3"),
        (42.4813375, 1.993525, "Feingitter-Fund 4"),
        (42.4889875, 1.99425, "Feingitter-Fund 5"),
    ],
)
def test_f005_points_inside_llivia_near_border_stay_none(lat, lon, ort):
    """Alle sechs Punkte liegen NACHWEISLICH roh innerhalb des Llívia-Holes,
    nur wenige Meter von der echten Grenze entfernt -- vor F005 kippten sie
    nach der Rundung faelschlich auf `"66"`. Muessen `None` bleiben."""
    from services.official_alerts.geo_ray_cast import _point_in_ring

    hole = next(
        h
        for entry in department_mapper._DEPARTMENT_POLYGONS
        if entry["code"] == "66"
        for poly in entry["polygons"]
        for h in poly["holes"]
    )
    assert _point_in_ring(lat, lon, hole) is True, (
        f"Testvorbedingung: {ort} muss roh nachweislich im Hole liegen"
    )
    assert lookup_department(lat, lon) is None, (
        f"{ort} ({lat}, {lon}) liegt in Spanien, nur Meter von der Grenze "
        f"entfernt -- darf trotz Rundung KEIN franzoesisches Département "
        f"bekommen (Issue #1400 Adversary F005)"
    )


def test_f005_point_just_outside_llivia_border_still_resolves_to_66():
    """Gegenprobe: ein Punkt ~15 m ausserhalb derselben Llívia-Grenzkante
    (also tatsaechlich franzoesisches Staatsgebiet) muss weiterhin `"66"`
    liefern -- die F005-Nachbesserung darf den F001-Puffer fuer echte
    franzoesische Punkte nahe der Enklave nicht mit-abschalten."""
    assert lookup_department(42.45855, 2.000243) == "66"


def test_f004_cache_unterscheidet_deutlich_verschiedene_punkte():
    """Grober Regressionswaechter (KEINE Grenzpraezisions-Pruefung -- die
    liegt vollstaendig in den `test_f005_*`-Tests oben): das Llívia-
    Hole-Zentrum und ein Punkt tief im franzoesischen Landesinneren liegen
    so weit auseinander, dass sie bei JEDER denkbaren Rundungspraezision
    unterschiedliche Zellen treffen wuerden -- dieser Test kann also nie
    ein Rundungs-Fehlerband an der Enklavengrenze aufdecken (s. F005), nur
    grob beweisen, dass der Cache nicht pauschal alles auf ein Ergebnis
    zusammenfaltet."""
    department_mapper._lookup_department_cached.cache_clear()
    innerhalb = (42.470394, 1.982462)  # Llívia-Zentrum, im Hole -> None
    ausserhalb = (44.3055, 2.5000)  # klar im franzoesischen Landesinneren -> ein Code
    assert lookup_department(*innerhalb) is None
    assert lookup_department(*ausserhalb) is not None


def test_f004_cache_key_uses_rounded_coordinate_not_raw_float():
    """Zwei Aufrufe mit minimal unterschiedlichen Float-Repraesentationen
    derselben Koordinate (Unterschied weit unterhalb der 11-m-Rasterzelle)
    muessen denselben Cache-Eintrag treffen -- das ist der eigentliche Zweck
    der Rundung (Float-Jitter zwischen wiederholten Aufrufen abfangen)."""
    department_mapper._lookup_department_cached.cache_clear()
    lat, lon = 47.2692, 11.4041
    lookup_department(lat, lon)
    hits_before = department_mapper._lookup_department_cached.cache_info().hits
    lookup_department(lat + 1e-8, lon - 1e-8)  # rundet auf dieselbe Zelle
    hits_after = department_mapper._lookup_department_cached.cache_info().hits
    assert hits_after == hits_before + 1
