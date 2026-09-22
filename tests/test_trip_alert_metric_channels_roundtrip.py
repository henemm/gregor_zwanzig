"""
Issue #1895 Scheibe S1 (Epic #1230) — Kanalzuordnung je Metrik, Python-Seite.

Spec: docs/specs/modules/alert_metric_channels.md, AC-6.

NO MOCKS — echte Trip-Datei auf Platte, echter Lade-/Speicherpfad des Loaders.

Warum drei Zusicherungen statt einer: Ein reiner Datei-Roundtrip waere HEUTE
schon gruen, weil der generische `extra`-Mechanismus (#991,
`src/app/loader.py:667`) jeden unbekannten Top-Level-Key konserviert. Er wuerde
also nichts bewachen. Die drei Zusicherungen treffen die drei Stellen einzeln:

1. `trip.alert_metric_channels` — bewacht Dataclass-Feld (`src/app/trip.py`)
   und `data.get(...)` im Konstruktor (`src/app/loader.py`). Heute rot:
   das Attribut existiert nicht.
2. `"alert_metric_channels" not in trip.extra` — bewacht den
   `KNOWN_TOP_LEVEL`-Eintrag. Heute rot: der Key landet im `extra`-Auffangnetz.
3. `_trip_to_dict(trip)` direkt — bewacht die Rueckschreibe-Zeile. Diese
   Zusicherung muss den Serialisierer DIREKT befragen: `save_trip` schreibt
   die Datei nicht wholesale, sondern merged auf den Vorzustand
   (`_deep_merge_preserve_unknown`, `src/app/loader.py:1857`). Ein reiner
   Datei-Roundtrip wuerde den alten Wert also auch dann wiederfinden, wenn
   die Rueckschreibe-Zeile fehlt — er waere gegen genau diese Mutation blind.
4. Datei-Roundtrip ueber `save_trip` — belegt zusaetzlich den echten
   End-zu-End-Weg (Falle `src/app/loader.py:657-658`, in der Spec benannt).
"""
from __future__ import annotations

import json

from app.loader import _trip_to_dict, load_trip, save_trip

USER_ID = "user-1895-a"
TRIP_ID = "trip-1895-ac6"

BESTANDSWERT = {
    "rain": {"telegram": True, "email": False},
    "wind": {"email": True},
}


def _trip_json() -> dict:
    return {
        "id": TRIP_ID,
        "name": "AC6 Bestandstrip",
        "kind": "route",
        "stages": [
            {
                "id": "stage-1",
                "name": "Etappe 1",
                "date": "2026-07-10",
                "waypoints": [
                    {"id": "wp-1", "name": "Start", "lat": 46.0, "lon": 9.0, "elevation_m": 1200},
                ],
            },
        ],
        "aggregation": {"profile": "allgemein"},
        # Der vorbefuellte Bestandswert, um den es geht.
        "alert_metric_channels": BESTANDSWERT,
    }


def test_alert_metric_channels_survives_python_load_save_roundtrip(tmp_path):
    """AC-6: Bestandswert uebersteht Laden + Zurueckschreiben unveraendert."""
    briefings = tmp_path / "users" / USER_ID / "briefings"
    briefings.mkdir(parents=True)
    trip_file = briefings / f"{TRIP_ID}.json"
    trip_file.write_text(json.dumps(_trip_json()), encoding="utf-8")

    trip = load_trip(TRIP_ID, data_dir=tmp_path, user_id=USER_ID)
    assert trip is not None, "Trip wurde nicht geladen"

    # (1) benanntes Dataclass-Feld statt anonymes extra-Auffangnetz
    assert getattr(trip, "alert_metric_channels", None) == BESTANDSWERT, (
        "Trip.alert_metric_channels traegt den geladenen Wert nicht — "
        "Dataclass-Feld oder data.get(...) im Konstruktor fehlt"
    )

    # (2) der Key darf NICHT mehr im generischen extra-Auffangnetz liegen,
    #     sonst ist er nicht als bekanntes Feld modelliert
    assert "alert_metric_channels" not in trip.extra, (
        "alert_metric_channels landet im extra-Auffangnetz — "
        "KNOWN_TOP_LEVEL-Eintrag fehlt"
    )

    # (3) Serialisierer DIREKT befragen — der Datei-Roundtrip unten kann die
    #     fehlende Rueckschreibe-Zeile nicht sehen, weil save_trip auf den
    #     Vorzustand der Datei merged statt sie zu ersetzen.
    assert _trip_to_dict(trip).get("alert_metric_channels") == BESTANDSWERT, (
        "_trip_to_dict schreibt alert_metric_channels nicht zurueck — "
        "ohne diese Zeile geht der Wert verloren, sobald er nicht mehr im "
        "extra-Auffangnetz liegt"
    )

    # (4) Rueckschreiben ueber den echten Speicherpfad, danach Datei erneut lesen
    save_trip(trip, USER_ID, data_dir=tmp_path)
    wieder_gelesen = json.loads(trip_file.read_text(encoding="utf-8"))
    assert wieder_gelesen.get("alert_metric_channels") == BESTANDSWERT, (
        "Bestandswert ging beim Zurueckschreiben verloren — "
        "Rueckschreibe-Zeile in _trip_to_dict fehlt"
    )


def test_trip_without_alert_metric_channels_stays_key_free(tmp_path):
    """AC-6 Gegenprobe: Ein Trip ohne das Feld bekommt beim Speichern keinen
    Schluessel angehaengt — das Feld bleibt additiv und verhaltensneutral
    (Python-Pendant zu omitempty, AC-7 auf der Go-Seite).

    Ohne diese Gegenprobe waere die Roundtrip-Zusicherung oben auch von einer
    Implementierung erfuellt, die das Feld bedingungslos (mit `None` oder `{}`)
    in jede Trip-Datei schreibt und damit jeden Bestandstrip veraendert.
    """
    briefings = tmp_path / "users" / USER_ID / "briefings"
    briefings.mkdir(parents=True)
    trip_file = briefings / f"{TRIP_ID}.json"
    ohne_feld = _trip_json()
    del ohne_feld["alert_metric_channels"]
    trip_file.write_text(json.dumps(ohne_feld), encoding="utf-8")

    trip = load_trip(TRIP_ID, data_dir=tmp_path, user_id=USER_ID)
    assert trip is not None, "Trip wurde nicht geladen"
    assert getattr(trip, "alert_metric_channels", "ATTRIBUT-FEHLT") is None, (
        "Ein Trip ohne den Schluessel muss None tragen (nicht {} und nicht "
        "fehlendes Attribut)"
    )

    save_trip(trip, USER_ID, data_dir=tmp_path)
    wieder_gelesen = json.loads(trip_file.read_text(encoding="utf-8"))
    assert "alert_metric_channels" not in wieder_gelesen, (
        "Trip ohne Zuordnung hat nach dem Speichern trotzdem den Schluessel — "
        "das Feld ist nicht verhaltensneutral"
    )
