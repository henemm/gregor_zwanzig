"""TDD — Issue #1037: MassifClosureSource (Präfektur-Betretungsverbote).

SPEC: docs/specs/modules/issue_1037_official_alerts_massif_closure.md
AC-1 bis AC-5 + F002-Regression (Fix-Runde 2 nach Adversary Runde 2 BROKEN).

KEINE Mocks (CLAUDE.md-Projektkonvention "KEINE MOCKED TESTS!"):
- AC-1 ruft den echten Live-Endpoint für DEPT=83 (Var) auf — auth-frei, kein Mock.
  Verwendet REALE Ortskoordinaten (Trailheads/Orte). Welches Massiv ein realer
  Ort trifft, wird über die echte `massif_at()`-Funktion (Point-in-Polygon)
  bestimmt, nicht vorab geraten — das hätte den Adversary-Fund F004/F005
  (falsch geratene/geroutete Massiv-Zuordnung) gefangen.
- AC-2 ruft den echten Live-Endpoint für DEPT=20 (Korsika) auf und weist die
  Pfad-Generizität nach: dasselbe Point-in-Polygon wie Var, kein
  Korsika-Sonderfall-Zweig.
- AC-3 prüft echtes `covers()`-Verhalten für Paris (außerhalb aller Polygone).
- AC-4 ruft die echte Struktur-Guard-Funktion `_extract_alert()` mit kaputten
  Struktur- UND Value-Shape-Werten auf (kein Verhaltens-Mock der Kernlogik) und
  prüft [] + Log-Warnung (F001-Härtung).
- AC-5 (neu, Fix-Runde 2): reale Referenzorte mit amtlich bekanntem Massiv
  müssen über `massif_at()` (echtes Point-in-Polygon) das KORREKTE Massiv
  treffen — deckt F004/F005/F006 ab.
- F002-Regression: reale Var-Grenz-Orte müssen `covers() == True` liefern.
"""
from __future__ import annotations

import datetime
from pathlib import Path

import httpx
import pytest
from dotenv import load_dotenv

from app.profile import ActivityProfile
from app.user import SavedLocation
from services.comparison_engine import ComparisonEngine

REPO_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(REPO_ROOT / ".env")

_ENDPOINT = "https://www.risque-prevention-incendie.fr/static/{src}/import_data/{ymd}.json"


def _live_massifs(src: str) -> dict:
    """Holt das tagesaktuelle massifs-Dict für einen Source-DEPT (echter Call)."""
    ymd = datetime.date.today().strftime("%Y%m%d")
    resp = httpx.get(_ENDPOINT.format(src=src, ymd=ymd), timeout=15.0)
    resp.raise_for_status()
    return resp.json().get("massifs", {})


class TestIssue1037MassifClosure:
    """TDD-Reihenfolge laut Spec: AC-1 -> AC-2 -> AC-3 -> AC-4 -> AC-5."""

    # Reale Trailheads/Orte im Var — Point-in-Polygon (`massif_at()`) bestimmt
    # das zugehoerige Massiv, keine vorab geratene ID-Zuordnung.
    _VAR_REAL_POINTS = [
        ("Toulon (Mont Faron)", 43.1550, 5.9300),
        ("Plan-d'Aups-Sainte-Baume", 43.3339, 5.7139),
        ("Aups", 43.6297, 6.2183),
        ("Cavalaire-sur-Mer", 43.1725, 6.5286),
        ("Collobrières", 43.2333, 6.3092),
        ("Le Muy", 43.4736, 6.5561),
        ("Comps-sur-Artuby", 43.7213, 6.5039),
        ("Agay", 43.4322, 6.8580),
        ("Hyères", 43.1204, 6.1286),
    ]

    # Dialt real (Praefektur-API DEPT=83) -- #1211 Scheibe 2b Batch 3, nur via Marker ausfuehren.
    @pytest.mark.live
    def test_ac1_var_niveau3_abgestufter_badge(self):
        """AC-1: echter Live-Call für DEPT=83. Für jeden realen Var-Ortspunkt
        wird ueber `massif_at()` (echtes Point-in-Polygon) das abdeckende
        Massiv bestimmt und der strukturelle Vertrag geprueft (Niveau <3 ->
        kein Alert; Niveau 3 -> 'Zugang eingeschränkt'; Niveau >=4 -> 'Zugang
        gesperrt'). Zusaetzlich wird fuer das aktuell hoechste getroffene
        Var-Massiv (im Juli realistisch >=3) der Badge im gerenderten
        Compare-HTML geprueft — ausgehend vom realen Ortspunkt."""
        from output.renderers.email.compare_html import render_compare_html
        from services.official_alerts.massif_closure import MassifClosureSource
        from services.official_alerts.massif_zones import massif_at

        source = MassifClosureSource()
        levels = _live_massifs("83")

        best_niveau = 0
        best_name = None
        best_point = None
        for town, lat, lon in self._VAR_REAL_POINTS:
            hit = massif_at(lat, lon)
            assert hit is not None, (
                f"{town} (realer Var-Ort) muss ein amtliches Massiv-Polygon treffen"
            )
            assert hit.src == "83"
            assert source.covers(lat, lon) is True, (
                f"{town} (realer Ort, Massiv {hit.name}) muss von covers() "
                f"abgedeckt sein"
            )
            live = levels.get(hit.massif_id)
            niveau = live[0] if isinstance(live, list) and live else 0
            alerts = source.fetch(lat, lon)
            ban = [a for a in alerts if a.hazard == "access_ban"]
            if niveau < 3:
                assert not ban, (
                    f"Massiv {hit.name} auf Niveau {niveau} (<3) darf keinen "
                    f"access_ban-Alert liefern"
                )
                continue
            assert ban, f"Massiv {hit.name} auf Niveau {niveau} (>=3) muss Badge liefern"
            alert = ban[0]
            assert alert.source == "massif_closure"
            assert alert.level == niveau
            assert hit.name.title() in alert.label
            if niveau == 3:
                assert "eingeschränkt" in alert.label.lower()
            else:
                assert "gesperrt" in alert.label.lower()
            if niveau > best_niveau:
                best_niveau, best_name, best_point = niveau, hit.name.title(), (town, lat, lon)

        if best_name is None:
            pytest.skip(
                "Zum Testzeitpunkt kein reales Var-Massiv auf Niveau >=3 — "
                "im Juli sehr unwahrscheinlich; Known Limitation (Live-Abhängigkeit)."
            )

        town, lat, lon = best_point
        locations = [
            SavedLocation(id="massif-var", name=town, lat=lat, lon=lon, elevation_m=200)
        ]
        target = datetime.date.today() + datetime.timedelta(days=1)
        result = ComparisonEngine.run(
            locations, time_window=(9, 16), target_date=target,
            profile=ActivityProfile.ALLGEMEIN,
        )
        html = render_compare_html(result)
        expected_word = "eingeschränkt" if best_niveau == 3 else "gesperrt"
        assert best_name in html
        assert expected_word.lower() in html.lower()

    # Dialt real (Praefektur-API DEPT=20) -- #1211 Scheibe 2b Batch 3, nur via Marker ausfuehren.
    @pytest.mark.live
    def test_ac2_korsika_selber_code_pfad(self):
        """AC-2: Korsika läuft durch DENSELBEN Code-Pfad wie Var — dasselbe
        Point-in-Polygon, kein Korsika-Sonderfall-Zweig. `covers()` liefert
        True für einen realen, amtlich getrackten Korsika-Ort (Piana, Massiv
        PIANA/207), `fetch()` ruft den echten DEPT=20-Endpoint auf und läuft
        ohne Verzweigung durch dieselben Funktionen wie Var — Badge nur, falls
        das getroffene Massiv aktuell >=3 ist (Generizität ist
        live-Niveau-unabhängig nachweisbar)."""
        from services.official_alerts.massif_closure import MassifClosureSource
        from services.official_alerts.massif_zones import massif_at

        # Piana-Dorf, liegt real im amtlichen PIANA-Massiv-Polygon (id 207).
        piana_lat, piana_lon = 42.2467, 8.6333
        hit = massif_at(piana_lat, piana_lon)
        assert hit is not None, "Piana muss ein amtliches Korsika-Massiv-Polygon treffen"
        assert hit.src == "20", "Piana muss dem Source-DEPT '20' (Korsika) zugeordnet sein"

        source = MassifClosureSource()
        assert source.covers(piana_lat, piana_lon) is True
        alerts = source.fetch(piana_lat, piana_lon)  # echter Live-Call DEPT=20
        assert isinstance(alerts, list)
        for alert in alerts:
            assert alert.source == "massif_closure"
            assert alert.hazard == "access_ban"
            assert alert.level >= 3

    def test_f002_reale_var_orte_covered(self):
        """F002-Regression: reale Var-Orte, die vom ALTEN Departement-Gate
        faelschlich weggeroutet wurden, MUESSEN unter der neuen
        Point-in-Polygon-Zuordnung abgedeckt sein."""
        from services.official_alerts.massif_closure import MassifClosureSource

        source = MassifClosureSource()
        real_orte = {
            "Draguignan": (43.5375, 6.4653),
            "Le Muy": (43.4736, 6.5561),
            "Agay": (43.4322, 6.8580),
            "Collobrières": (43.2333, 6.3092),
        }
        for name, (lat, lon) in real_orte.items():
            assert source.covers(lat, lon) is True, (
                f"{name} ist ein realer Var-Ort und MUSS von covers() abgedeckt sein"
            )

    def test_ac3_paris_keine_abdeckung(self):
        """AC-3: Paris (außerhalb aller amtlichen Massiv-Polygone) -> covers()
        liefert False, kein Badge, kein Fehler."""
        from services.official_alerts.massif_closure import MassifClosureSource

        source = MassifClosureSource()
        assert source.covers(48.8566, 2.3522) is False, (
            "Paris liegt in keinem amtlichen Massiv-Polygon -> covers() muss False sein"
        )

    def test_ac4_kaputte_struktur_fail_soft(self, caplog):
        """AC-4 + F001-Härtung: fehlendes 'massifs'-Feld sowie kaputte VALUE-Shapes
        (Skalar statt Liste, leere Liste, None-Einträge, String-Niveaus, 'massifs'
        selbst als Liste) -> echte Struktur-/Shape-Guard-Funktion `_extract_alert()`
        loggt jeweils eine Warnung und liefert [] (kein Absturz, kein Mock der
        Kernlogik — echter Funktionsaufruf mit kaputtem Struktur-Wert)."""
        import logging

        from services.official_alerts.massif_closure import _extract_alert
        from services.official_alerts.massif_zones import Massif

        hit = Massif(src="83", massif_id="835", name="MAURES", rings=[])
        broken_payloads = [
            {"kein_massifs_feld": True},
            {"massifs": {"835": 3}},
            {"massifs": {"835": []}},
            {"massifs": {"835": [None, None]}},
            {"massifs": {"835": ["3", "3"]}},
            {"massifs": ["835"]},
        ]
        for payload in broken_payloads:
            caplog.clear()
            with caplog.at_level(logging.WARNING):
                result = _extract_alert(payload, hit)
            assert result == [], f"Kaputte Struktur {payload!r} muss [] liefern, kein Crash"
            assert any(r.levelno >= logging.WARNING for r in caplog.records), (
                f"Bei kaputter Struktur {payload!r} muss eine Warnung geloggt werden"
            )

    def test_f007_load_massifs_fail_soft_missing_file(self, tmp_path):
        """F007: fehlende Polygon-Datei darf `_load_massifs()` NICHT crashen
        lassen — [] zurueck, kein Raise (Fail-soft-Haertung)."""
        from services.official_alerts.massif_zones import _load_massifs

        result = _load_massifs(tmp_path / "nonexistent.json")
        assert result == []

    def test_f007_load_massifs_fail_soft_broken_json(self, tmp_path):
        """F007: kaputter JSON-Inhalt fuehrt ebenfalls zu [] statt Absturz."""
        from services.official_alerts.massif_zones import _load_massifs

        broken = tmp_path / "broken.json"
        broken.write_text("{ das ist kein json ]")
        result = _load_massifs(broken)
        assert result == []

    def test_f007_official_alerts_import_survives_missing_polygon_file(self):
        """F007: das gesamte `services.official_alerts`-Paket darf importierbar
        bleiben, selbst wenn die Polygon-Datei fehlt/kaputt ist. Da MASSIFS
        bereits beim Modul-Import geladen wird, wird hier direkt geprueft,
        dass `_load_massifs` mit einem kaputten Pfad kein Raise produziert —
        die eigentliche Import-Ueberlebensfaehigkeit wird zusaetzlich manuell
        (Datei umbenennen + Prozess-Neustart) verifiziert, siehe Meldung."""
        from services.official_alerts import massif_zones

        assert massif_zones._load_massifs(Path("/nonexistent/x.json")) == []

    # Dialt real (Praefektur-API, beide DEPTs) -- #1211 Scheibe 2b Batch 3, nur via Marker ausfuehren.
    @pytest.mark.live
    def test_f009_ueberlappende_massive_strengstes_niveau_gewinnt(self):
        """F009: Sainte-Baume liegt real in DEPT 83 (832) UND 13 (1322).
        `massifs_at()` muss BEIDE liefern; `fetch()` muss den Alert mit dem
        hoeheren der beiden Tages-Niveaus zurueckgeben (restriktivste Sperre
        gewinnt bei Ueberlappung)."""
        from services.official_alerts.massif_closure import MassifClosureSource
        from services.official_alerts.massif_zones import massifs_at

        # Punkt liegt nachweislich sowohl im 83er- als auch im 13er-Sainte-
        # Baume-Polygon (per massifs_at() verifiziert, kein Raten).
        lat, lon = 43.314, 5.700
        hits = massifs_at(lat, lon)
        assert len(hits) >= 2, (
            "Testpunkt muss mindestens zwei ueberlappende Massiv-Polygone treffen"
        )
        srcs = {h.src for h in hits}
        assert {"83", "13"}.issubset(srcs), (
            "Testpunkt muss sowohl DEPT 83 als auch DEPT 13 Sainte-Baume treffen"
        )

        source = MassifClosureSource()
        levels = {}
        for hit in hits:
            live = _live_massifs(hit.src)
            raw = live.get(hit.massif_id)
            levels[hit.src] = raw[0] if isinstance(raw, list) and raw else 0

        alerts = source.fetch(lat, lon)  # darf unter keinen Umstaenden crashen
        assert isinstance(alerts, list)

        expected_best = max(levels.values())
        if expected_best < 3:
            assert alerts == [], (
                "Kein Massiv auf Niveau >=3 -> fetch() muss [] liefern"
            )
        else:
            assert alerts, f"Bestes Niveau {expected_best} (>=3) muss einen Alert liefern"
            assert alerts[0].level == expected_best, (
                f"fetch() muss das strengste Niveau {expected_best} liefern, "
                f"nicht {alerts[0].level}"
            )

    def test_ac5_attributions_korrektheit(self):
        """AC-5 (Attributions-Korrektheit, Fix-Runde 2): reale, unabhängig
        gewählte Orte mit amtlich bekanntem Massiv müssen über `massif_at()`
        (echtes Point-in-Polygon) das KORREKTE Massiv treffen — deckt die
        Adversary-Findings F004 (falsch geratene IDs), F005
        (Radius-Fehlzuordnung an Küsten) und F006 (Fall-through) ab."""
        from services.official_alerts.massif_closure import MassifClosureSource
        from services.official_alerts.massif_zones import massif_at

        source = MassifClosureSource()
        referenz_orte = {
            "Le Lavandou": (43.1369, 6.3644, "corniche des maures"),
            "Vauvenargues": (43.5486, 5.6067, "sainte-victoire"),
            "Saint-Tropez": (43.2727, 6.6407, "corniche des maures"),
        }
        for name, (lat, lon, expected_massif) in referenz_orte.items():
            hit = massif_at(lat, lon)
            assert hit is not None, f"{name} muss ein amtliches Massiv-Polygon treffen"
            assert hit.name.title().lower() == expected_massif, (
                f"{name} muss dem Massiv '{expected_massif}' zugeordnet sein, "
                f"nicht '{hit.name}' (F004/F005-Regression)"
            )
            assert source.covers(lat, lon) is True
