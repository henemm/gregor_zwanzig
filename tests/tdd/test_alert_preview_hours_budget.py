"""Zeitbudget der Vorschau-Reihen (Issue #1737, AC-11 Fallback "Zeitueberschreitung").

Der Go-Proxy bricht die Alarm-Vorschau nach 30 s ab; die Frisch-Abrufe laufen seriell.
`alert_preview_hours` begrenzt deshalb ALLE Abrufe einer Vorschau auf ein gemeinsames Budget
(`PREVIEW_FETCH_BUDGET_S`). Laeuft es ab: `(None, None)`, kein Fehler -- die Vorschau zeigt dann
keine Stundenzeilen (AC-10). Gemessen ueber die `fetch`-Naht mit einer langsamen Abruf-Funktion;
das Budget wird per `deadline` klein gesetzt (kein echter 15-s-Schlaf).
"""
from __future__ import annotations

import time
from datetime import datetime, timezone

from tests.helpers.vorschau_umgebung import env  # noqa: F401  (Fixture)
from tests.tdd.test_alert_hour_rows import _cmp_orte, _cmp_welt, _trip_welt

LANGSAM_S = 1.5
BUDGET_S = 0.2


def _langsam(aufrufe: list):
    def fetch(*args, **kwargs):
        aufrufe.append(args)
        time.sleep(LANGSAM_S)
        raise AssertionError("haette nach Fristablauf nicht mehr gelesen werden duerfen")
    return fetch


def test_budget_konstante_liegt_deutlich_unter_dem_proxy_timeout():
    from services.alert_preview_hours import PREVIEW_FETCH_BUDGET_S

    assert 0 < PREVIEW_FETCH_BUDGET_S <= 20.0  # Go-Proxy: 30 s


def test_trip_langsamer_abruf_endet_mit_dem_budget_ohne_fehler(env, monkeypatch, tmp_path):  # noqa: F811
    from services.alert_preview_hours import preview_deadline, trip_preview_series

    trip = _trip_welt(monkeypatch, tmp_path, env, anker_boeen={})
    aufrufe: list = []
    t0 = time.monotonic()
    out = trip_preview_series(
        trip, user_id=env, now_utc=datetime.now(timezone.utc),
        fetch=_langsam(aufrufe), deadline=preview_deadline(BUDGET_S),
    )
    dauer = time.monotonic() - t0
    assert aufrufe, "Vorbedingung: der Anker lag vor, der Abruf wurde gestartet"
    assert out == (None, None)
    assert dauer < LANGSAM_S - 0.5, f"Vorschau wartete den langsamen Abruf ab ({dauer:.2f} s)"


def test_ortsvergleich_ein_budget_fuer_alle_orte(env, monkeypatch, tmp_path):  # noqa: F811
    """Erster Ort verbraucht das Budget -> der zweite Ort ruft gar nicht mehr ab."""
    from services.alert_preview_hours import compare_preview_point, preview_deadline
    from tests.tdd.test_alert_preview_compare_paritaet import PRESET_ID

    preset = _cmp_welt(monkeypatch, tmp_path, env, anker_boeen={})
    erster, zweiter = _cmp_orte()
    frist = preview_deadline(BUDGET_S)
    aufrufe: list = []
    t0 = time.monotonic()
    assert compare_preview_point(
        preset, PRESET_ID, erster, user_id=env, fetch=_langsam(aufrufe), deadline=frist,
    ) == (None, None)
    assert compare_preview_point(
        preset, PRESET_ID, zweiter, user_id=env, fetch=_langsam(aufrufe), deadline=frist,
    ) == (None, None)
    dauer = time.monotonic() - t0
    assert len(aufrufe) == 1, f"nach Fristablauf darf kein Abruf mehr starten: {aufrufe!r}"
    assert dauer < LANGSAM_S - 0.5, f"Vorschau wartete den langsamen Abruf ab ({dauer:.2f} s)"
