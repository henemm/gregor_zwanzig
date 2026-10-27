"""AC-8/AC-3 (#1765 Scheibe B1) am WIRKORT: systemische Stoerung vs. Ortsfehler.

Spec: docs/specs/modules/fix_1765_b1_compare_vorschau_parallel.md
Anlass: Adversary-Finding F001 (HIGH, Verdict BROKEN) —
docs/artifacts/fix-1765-compare-vorschau-parallel/adversary-dialog.md

``ComparisonEngine.run()`` fasst einen echten ORTSFEHLER bereits selbst in ein
``LocationResult(error=...)`` und wirft dafuer nicht (comparison_engine.py:
128-147, :369-381). Was als AUSNAHME herauskommt, ist deshalb per Definition
systemisch (z.B. die ``Settings()``-Konstruktion vor der Ortsschleife) — vor
der Parallelisierung schlug so etwas als ``RuntimeError`` aus dem Dienst durch.
Ein breiter Ausnahmefang je Ort machte daraus ein Ergebnis mit N
gleichlautenden Ortsfehlern: andere Form, anderer Inhalt, AC-8 verletzt.

Issue #1743: die HTTP-Route ``POST /api/preview/compare/{id}`` ist entfallen
(PO-Entscheid 22.10.2026); die Zusicherung wird deshalb am Dienst
``ComparePreviewService.render_all_channels`` geprueft, der weiter den
Render-Pfad der Paritaetstests traegt. Es laeuft der ECHTE Dienst mit echten
Preset-/Ortsdaten; substituiert wird ausschliesslich die teure Engine-Naht
(braucht Live-Wetter, in der Kern-Schicht verboten), und zwar per echter
Subklasse, kein Mock.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime
from pathlib import Path

import pytest

from app.loader import get_data_dir, save_location
from app.models import ForecastDataPoint, ThunderLevel
from app.user import SavedLocation

from tests.helpers.compare_briefings import write_compare_briefings

WORKTREE = Path(__file__).resolve().parents[2]
ZIELDATUM = date(2026, 7, 8)
AUSFALL = "Wetterdaten aktuell nicht verfuegbar (Testfall)"
ORTE = [
    ("loc-ibk", "Innsbruck", 47.27, 11.39),
    ("loc-bz", "Bozen", 46.50, 11.35),
    ("loc-muc", "Muenchen", 48.14, 11.58),
]


def _dp(hour: int) -> ForecastDataPoint:
    return ForecastDataPoint(
        ts=datetime(ZIELDATUM.year, ZIELDATUM.month, ZIELDATUM.day, hour, 0),
        t2m_c=22.0, wind_chill_c=21.0, wind10m_kmh=11.0, gust_kmh=19.0,
        precip_1h_mm=0.0, cloud_total_pct=35, uv_index=5.0,
        thunder_level=ThunderLevel.NONE, pop_pct=10, visibility_m=9000,
    )


@pytest.fixture
def preset_mit_drei_orten(tmp_path, monkeypatch):
    """Isolierter Daten-Root mit drei ECHTEN Orten + Preset; liefert
    ``(preset_id, user_id)``. Muster: tests/tdd/test_compare_preview_service.py."""
    from app import loader as app_loader

    data_root = tmp_path / "data"
    data_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(app_loader, "_DATA_ROOT", str(data_root))
    try:
        from src.app import loader as src_loader

        monkeypatch.setattr(src_loader, "_DATA_ROOT", str(data_root))
    except ImportError:  # pragma: no cover — Alias-Modul immer vorhanden
        pass
    user_id = f"f001-{uuid.uuid4().hex[:8]}"
    for loc_id, name, lat, lon in ORTE:
        save_location(
            SavedLocation(id=loc_id, name=name, lat=lat, lon=lon, elevation_m=1000),
            user_id=user_id,
        )
    preset_id = "cp-f001"
    write_compare_briefings(get_data_dir(user_id), [{
        "id": preset_id, "name": "Urlaubsorte", "user_id": user_id,
        "location_ids": [loc_id for loc_id, *_ in ORTE],
        "schedule": "daily", "profil": "ALLGEMEIN",
        "empfaenger": ["gregor-test@henemm.com"],
        "created_at": "2026-07-01T00:00:00Z",
    }])
    return preset_id, user_id


@pytest.fixture
def dienst():
    """Echter ``ComparePreviewService``. Issue #1743: die HTTP-Route
    ``POST /api/preview/compare/{id}`` ist entfallen; geprueft wird deshalb
    direkt am Dienst — systemische Stoerung = durchgereichte ``RuntimeError``
    (vormals vom Router auf 503 abgebildet)."""
    import services.comparison_parallel as pruefling
    from services.compare_preview_service import ComparePreviewService

    # Pfadregel #1409: der Pruefling muss aus DIESEM Checkout stammen -- sonst
    # misst dieser Test aus dem Worktree die unveraenderte Hauptrepo-Kopie und
    # meldet falsches Gruen.
    assert Path(pruefling.__file__).resolve().is_relative_to(WORKTREE), pruefling.__file__
    return ComparePreviewService()


def _engine_scheitert_bei(monkeypatch, ids: set[str]) -> None:
    """Engine-Naht durch eine echte Subklasse ersetzen, die fuer die genannten
    Orte WIRFT — das Muster einer Stoerung AUSSERHALB der ortsinternen
    Fehlerbehandlung (ein Ortsfehler kaeme als ``LocationResult(error=...)``)."""
    import services.comparison_engine as ce_mod
    from app.user import ComparisonResult, LocationResult

    class ScheiterndeEngine(ce_mod.ComparisonEngine):  # echte Subklasse, kein Mock
        @staticmethod
        def run(*args, **kwargs):
            orte = list(kwargs.get("locations") or (args[0] if args else []))
            for ort in orte:
                if ort.id in ids:
                    raise RuntimeError(AUSFALL)
            return ComparisonResult(
                locations=[
                    LocationResult(
                        location=o, score=90, temp_max=22.0, temp_min=12.0,
                        wind_max=11.0, gust_max=19.0, cloud_avg=35, sunny_hours=6,
                        official_alerts=[], hourly_data=[_dp(9), _dp(12), _dp(15)],
                    )
                    for o in orte
                ],
                time_window=kwargs.get("time_window", (4, 19)),
                target_date=kwargs.get("target_date", ZIELDATUM),
                created_at=datetime(2026, 7, 8, 4, 0),
            )

    monkeypatch.setattr(ce_mod, "ComparisonEngine", ScheiterndeEngine)


def _vorschau(dienst, preset_id: str, user_id: str) -> dict:
    return dienst.render_all_channels(
        preset_id, user_id=user_id, target_date=ZIELDATUM.isoformat(),
    )


def _blockzeile(telegram: str, ortsname: str) -> str:
    """Die Inhaltszeile des Ortsblocks (Renderer: Name als eigene Zeile, danach
    entweder ``   Fehler: …`` oder die Werte-Zellen)."""
    zeilen = telegram.splitlines()
    assert ortsname in zeilen, f"Ort {ortsname!r} fehlt in der Vorschau:\n{telegram}"
    return zeilen[zeilen.index(ortsname) + 1]


def test_systemische_stoerung_bleibt_eine_ausnahme(dienst, preset_mit_drei_orten, monkeypatch):
    """AC-8: JEDER Ort scheitert mit derselben Ausnahme (Wetterdienst komplett
    weg / Konfigurationsfehler) → der echte Vorschau-Pfad reicht die
    ``RuntimeError`` mit der Meldung durch, wie vor der Parallelisierung —
    statt ein Ergebnis mit N eingebetteten Ortsfehlern zu liefern."""
    preset_id, user_id = preset_mit_drei_orten
    _engine_scheitert_bei(monkeypatch, {loc_id for loc_id, *_ in ORTE})

    with pytest.raises(RuntimeError) as fehler:
        _vorschau(dienst, preset_id, user_id)

    assert AUSFALL in str(fehler.value), (
        f"Die Meldung des Dienstes muss durchgereicht werden: {fehler.value!r}"
    )


def test_ein_ort_von_dreien_scheitert_liefert_weiter_ein_ergebnis(
    dienst, preset_mit_drei_orten, monkeypatch
):
    """AC-3: Scheitert nur EIN Ort mit einer Ausnahme, bleibt es beim heutigen
    Verhalten — Ergebnis, die uebrigen Orte vollstaendig, der betroffene mit
    Fehler AN SEINER POSITION. Die Ausnahme-Regel aus AC-8 darf nicht greifen."""
    preset_id, user_id = preset_mit_drei_orten
    _engine_scheitert_bei(monkeypatch, {"loc-bz"})

    nutzlast = _vorschau(dienst, preset_id, user_id)
    telegram, html = nutzlast["telegram"], nutzlast["email_html"]
    zeilen = telegram.splitlines()
    assert [n for n in ("Innsbruck", "Bozen", "Muenchen") if n in zeilen] == [
        "Innsbruck", "Bozen", "Muenchen",
    ] and zeilen.index("Innsbruck") < zeilen.index("Bozen") < zeilen.index("Muenchen"), (
        f"Alle drei Orte muessen in konfigurierter Reihenfolge erscheinen:\n{telegram}"
    )
    assert AUSFALL in _blockzeile(telegram, "Bozen"), (
        f"Der gescheiterte Ort braucht seine Fehlermeldung an seiner Position:\n{telegram}"
    )
    for name in ("Innsbruck", "Muenchen"):
        zeile = _blockzeile(telegram, name)
        assert "Fehler" not in zeile and "22" in zeile, (
            f"AC-3: {name} muss seine VOLLSTAENDIGEN Werte behalten (temp_max=22), "
            f"geliefert wurde: {zeile!r}\n{telegram}"
        )
    assert "Innsbruck" in html and "Muenchen" in html, (
        "Auch die E-Mail-Vorschau derselben Antwort muss die gesunden Orte zeigen"
    )
