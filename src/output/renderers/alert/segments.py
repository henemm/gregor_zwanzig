"""Eine Ortssprache fuer alle Alarme (Issue #1744 Scheibe A1).

`format_segment_reference()` stand bis 2026-08-12 in `official_alerts.py` und
war damit faktisch der amtlichen Warnung vorbehalten; Abweichungs- und
Nowcast-Alarm bauten ihre Ortsangabe selbst als km-Spanne. Zwei Mails zum
selben Ort nannten dadurch zwei verschiedene Dinge ("km 8–8" gegen "🏁 Ziel").

Dieses Modul ist die EINE Stelle, an der eine Alarm-Ortsangabe entsteht:
beide Renderer (`render.py`, `official_alerts.py`) importieren von hier.
Es importiert selbst nichts aus dem Paket — der Umzug ist zyklenfrei.
`official_alerts.py` re-exportiert `format_segment_reference` weiter, damit
Bestandsimporte (z.B. `email/html.py:53`) unveraendert halten.
"""
from __future__ import annotations


def normalize_segment_id(value) -> str | None:
    """Rohe Segment-Kennung -> `str` oder `None` (Issue #1744 AC-7).

    `TripSegment.segment_id` ist `int | str` (`app/models.py:389`), gespeicherte
    Altdaten koennen ohne Kennung ankommen (`WeatherChange.segment_id` hat den
    Default `""`, `app/models.py:541`). Beides muss hier zu `None` werden, damit
    die Aufloesung sauber auf die km-Spanne zurueckfaellt statt "Segment None"
    zu erfinden.
    """
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def format_segment_reference(segment_ids: list[str]) -> str:
    """Issue #1200: kompakter Segment-/Etappen-Bezug fuer die Standalone-
    Alert-Mail. Numerische IDs werden sortiert, zusammenhaengende Laeufe als
    Range ('Segment 3–5'), sonst als Aufzaehlung ('Segment 3, 5'). `"Ziel"`
    wird NIE in die numerische Range/Aufzaehlung gemischt, sondern immer als
    eigenes Element '🏁 Ziel' angehaengt. Mehr als 4 betroffene Segmente
    insgesamt -> Verdichtung 'N Segmente' (Begriff bewusst 'Segmente', nicht
    'Etappen')."""
    has_ziel = "Ziel" in segment_ids
    numeric = sorted({int(s) for s in segment_ids if s != "Ziel"})

    total = len(numeric) + (1 if has_ziel else 0)
    if total > 4:
        return f"{total} Segmente"

    numeric_part = ""
    if numeric:
        is_consecutive = numeric == list(range(numeric[0], numeric[-1] + 1))
        if is_consecutive and len(numeric) > 1:
            numeric_part = f"Segment {numeric[0]}–{numeric[-1]}"
        else:
            numeric_part = "Segment " + ", ".join(str(n) for n in numeric)

    if numeric_part and has_ziel:
        return f"{numeric_part}, 🏁 Ziel"
    if has_ziel:
        return "🏁 Ziel"
    return numeric_part


def _renderable_segment_ids(segment_ids) -> list[str]:
    """Nur Kennungen, die `format_segment_reference` auch verarbeiten kann:
    "Ziel" oder eine Zahl. Ist auch nur EINE Kennung von anderer Bauart, gilt
    die ganze Menge als unbrauchbar — eine Teilangabe waere unehrlich (sie
    verschwiege einen betroffenen Abschnitt), und `int()` wuerde werfen."""
    ids = [normalize_segment_id(s) for s in segment_ids or ()]
    usable = [s for s in ids if s]
    if not usable or len(usable) != len(ids):
        return []
    if not all(s == "Ziel" or s.isdigit() for s in usable):
        return []
    return usable


def format_alert_location(
    location_label: str | None, segment_ids, km_from: float, km_to: float,
) -> str:
    """Die Ortsangabe eines Alarms — DIE gemeinsame Aufloesungsreihenfolge
    (Issue #1744 AC-3):

    1. `location_label` gesetzt   -> Ortsname (Ortsvergleich, unveraendert)
    2. Segment-Kennung(en) da     -> `format_segment_reference`
    3. sonst                      -> `km {von}–{bis}` (Rueckfall, Altdaten)

    Stufe 3 ist kein Notnagel, sondern AC-7: ein Alarm ohne Segment-Kennung
    muss weiterhin einen Ort nennen und versendet werden.
    """
    if location_label:
        return location_label
    ids = _renderable_segment_ids(segment_ids)
    if ids:
        reference = format_segment_reference(ids)
        if reference:
            return reference
    return f"km {int(round(km_from))}–{int(round(km_to))}"
