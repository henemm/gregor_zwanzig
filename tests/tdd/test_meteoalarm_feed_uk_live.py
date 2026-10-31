"""Live-Nachweis -- MeteoAlarm Vereinigtes Koenigreich am ECHTEN Feed (Issue #1442 S3b, AC-10 / Test 11).

SPEC: docs/specs/modules/feat_1442_s3b_meteoalarm_uk.md (AC-10)

Nur ``/e2e-verify`` (Marker ``live``), nicht im Kern-Testlauf. Fuehrt der Feed gerade keine aktuell
gueltige, von der App auswertbare Warnung, ist das Ergebnis SKIP mit Grund, NICHT Bestehen.
Bekannt (#2696): reine Nebelwarnungen waehlt der Selektor nicht als "gewarntes Gebiet".
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from services.official_alerts.meteoalarm import _TYPE_HAZARD_MAP, _leading_int
from tests.tdd.test_meteoalarm_feed_nordics_live import _aktiv, _punkt_polygon  # noqa: F401

pytestmark = pytest.mark.live


def test_ac10_echter_feed_liefert_warnung_fuer_gewarntes_gebiet():
    """AC-10: GIVEN der echte UK-Feed fuehrt eine aktuell gueltige Warnung, WHEN die Quelle fuer
    einen Punkt in deren Gebiet abgefragt wird, THEN mindestens 1 Warnung, kein Ausfall."""
    from services.official_alerts import get_official_alerts_with_status, meteoalarm_feed
    from services.official_alerts.meteoalarm_feed import MeteoAlarmFeedSource
    import services.official_alerts.base as oa_base

    assert "GB" in meteoalarm_feed._FEED_PATHS, "GB-Quelle nicht eingerichtet"
    meteoalarm_feed._cache.clear()
    feed = meteoalarm_feed._get_cached_feed("GB")
    assert feed is not None, "echter UK-Feed nicht abrufbar"

    jetzt = datetime.now(timezone.utc)
    punkt = _punkt_polygon(feed, jetzt)
    if punkt is None:
        pytest.skip("UK-Feed fuehrt gerade keine aktuell gueltige Warnung -- kein Nachweis moeglich")

    quelle = MeteoAlarmFeedSource("GB")
    backup = list(oa_base._REGISTERED_SOURCES)
    oa_base._REGISTERED_SOURCES[:] = [quelle]
    try:
        alerts, unavailable = get_official_alerts_with_status(*punkt, now=jetzt)
    finally:
        oa_base._REGISTERED_SOURCES[:] = backup
    assert unavailable is False
    assert len(alerts) >= 1, f"mindestens 1 Warnung erwartet fuer GB {punkt}"
