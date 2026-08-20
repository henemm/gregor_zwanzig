"""Issue #1987 (S1), Nebenbefund aus der GREEN-Phase: die Aufraeumung der
datierten Snapshots darf die kanalscharfen Alarm-Anker nicht mitreissen.

`_prune_dated_snapshots()` (`weather_snapshot.py`) haelt maximal sieben
datierte Snapshots je Tour und loescht den Rest. Es sammelte sie ueber
`{trip_id}_*.json` ein — ein Muster, das jede Nachbardatei derselben Tour
mitnimmt, also auch `{trip_id}_alarm_anchor_{channel}.json`.

Gemessen VOR dem Fix (vier Kanal-Anker, danach acht Briefing-Laeufe): von
den vier Ankern ueberlebte genau EINER, und zwei der acht datierten
Snapshots fielen zusaetzlich weg, weil die Anker das 7er-Kontingent
mitfuellten. Getroffen haette es bevorzugt die Kanaele mit dem aeltesten
Schreibzeitpunkt — also genau jene, die laenger nichts zugestellt bekommen
haben. Das sind die Kanaele, deren eigenen Stand #1987 ueberhaupt erst
erhalten will: die Zusicherung waere in Produktion still ausgehoehlt worden,
ohne dass ein Test es bemerkt.

Kern-Schicht, kein Mock: echte Dateien in der pytest-isolierten
`get_data_dir()`-Basis (#1133), geprueft wird der Bestand nach dem echten
`save_dated()`-Pfad.
"""
from __future__ import annotations

import uuid
from datetime import date, timedelta

from tests.helpers.alert_log_fixtures import weather

ALLE_KANAELE = ("email", "telegram", "sms", "premium_sms")


def test_aufraeumung_der_datierten_snapshots_laesst_kanal_anker_stehen():
    """GIVEN eine Tour mit einem rollierenden Alarm-Anker je Kanal.
    WHEN  acht Briefing-Laeufe datierte Snapshots schreiben und die
          Aufraeumung auf sieben zurueckschneidet.
    THEN  stehen ALLE VIER Kanal-Anker unveraendert da, und es bleiben
          trotzdem sieben datierte Snapshots uebrig — die Aufraeumung zaehlt
          die Anker also weder mit noch loescht sie sie.
    """
    from app.loader import get_snapshots_dir
    from services.weather_snapshot import WeatherSnapshotService

    user_id, trip_id = f"tdd-1987-prune-{uuid.uuid4().hex[:6]}", "trip-1987-prune"
    svc = WeatherSnapshotService(user_id=user_id)
    heute = date.today()

    for channel in ALLE_KANAELE:
        svc.save_alarm_anchor(trip_id, heute, [weather(1, gust_max_kmh=10.0)], channel)
    for tag in range(8):
        svc.save_dated(
            trip_id, heute - timedelta(days=tag), [weather(1, gust_max_kmh=20.0)],
        )

    for channel in ALLE_KANAELE:
        assert svc.load_alarm_anchor(trip_id, channel), (
            f"Der rollierende Alarm-Anker des Kanals {channel!r} wurde von der "
            "Aufraeumung der datierten Snapshots mitgeloescht — betroffen sind "
            "bevorzugt die Kanaele, die am laengsten nichts zugestellt bekamen, "
            "also genau die, deren Stand #1987 erhalten soll."
        )

    datiert = sorted(
        p.name for p in get_snapshots_dir(user_id).glob(f"{trip_id}_*.json")
        if "alarm_anchor" not in p.name
    )
    assert len(datiert) == 7, (
        "Die Aufraeumung muss weiterhin genau sieben datierte Snapshots halten "
        "— zaehlt sie die Anker mit, fallen zusaetzlich echte Snapshots weg. "
        f"Vorhanden: {datiert}"
    )
