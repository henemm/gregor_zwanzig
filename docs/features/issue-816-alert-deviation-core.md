# Feature: Alert-Abweichungs-Kern (Issue #816)

**Status:** LIVE (v1.0 seit 2026-06-14)  
**Prioritaet:** HIGH  
**Kategorie:** Services / Alert System  
**Erstellt:** 2026-06-14  
**Spec:** `docs/specs/_archive/modules/issue_816_alert_deviation_core.md` (v1.0)  
**Epic:** #813 (Alert-Rework Slice 1)

## Problem

Das bisherige Alert-Modell basiert auf **absoluten Schwellwerten** pro Metrik (z. B. "Wind > 50 km/h" = Warnung).
Dies führt zu:

- **Konstanten Spam:** Warnung bleibt den ganzen Tag an, wenn Wind stabil über Schwelle.
- **Kontextblindheit:** Wanderer braucht nicht "Wind ist hoch", sondern **"Wind ist STÄRKER als das letzte Briefing"**.
- **Keine Entwarnung:** Symmetrische Verbesserungen werden nicht gemeldet.

## Lösung: Abweichungs-Melder

Der Alert meldet jetzt **Δ gegenüber dem letzten Briefing-Snapshot** statt absoluter Schwellwerte:

1. **Stabile Referenz:** Der Briefing-Snapshot bleibt nach dem Alert-Check unverändert (read-only).
2. **Melde-Gedächtnis:** Neue Datei `alert_state` verhindert Spam bei Stagnation (Re-Alert nur bei weiterer Δ-Stufe).
3. **Symmetrisch:** Sowohl Verschlechterung als auch Verbesserung (Entwarnung) werden gemeldet.
4. **Knapp:** Alert-Mail enthält NICHT das ganze Briefing, sondern nur Kopfzeile + Änderungen + Fußzeile.

---

## Architektur

### 1. Melde-Gedächtnis: `AlertStateService`

**Datei:** `src/services/alert_state.py`  
**Persistenz:**
```
data/users/<user_id>/alert_state/
  └── <trip_id>.json
```

**Schema:** eine Datei, **zwei** Schlüsselräume.

```json
{
  "<metric>:<segment_id>": {
    "last_reported_value": 18.5,
    "reported_at": "2026-06-14T13:30:00+00:00"
  },
  "official_alert:<ident>:<hazard>:<valid_from>:<valid_to>": {
    "last_reported_value": 2.0,
    "reported_at": "2026-08-10T05:01:19+00:00",
    "valid_from": "2026-08-10T12:00:00+00:00",
    "valid_to": "2026-08-10T20:00:00+00:00"
  }
}
```

Der zweite Raum gehört den **amtlichen Warnungen** (Präfix-Konstante
`OFFICIAL_ALERT_KEY_PREFIX`, Schlüsselbildung `official_alert_state_key()` in
`src/output/renderers/alert/official_alerts.py`). `ident` folgt der Präzedenz
`dedup_id` > `region_label` > `label`. Die Felder `valid_from`/`valid_to` kamen mit
**#1685** hinzu; Bestandseinträge ohne sie bleiben gültig (Read-Modify-Write mit Merge)
und werden dann wie vor #1685 allein über den exakten Schlüsseltreffer bewertet.

**Re-Alert-Logik (Δ-Raum):**
- **Erste Erkennung:** Eintrag fehlt → Alert send, Eintrag angelegt mit aktuellem Wert.
- **Stagnation:** `|current - last_reported| < threshold` → unterdrückt (keine E-Mail).
- **Eskalation:** `|current - last_reported| >= threshold` → erneut Alert, Wert aktualisiert.

**Re-Alert-Logik (amtliche Warnungen, #1685, präzisiert durch #1657 am 2026-08-17):**
entscheidet `official_alert_revision_verdict()` — geteilt von Trip und Ortsvergleich.
Überlappt das Gültigkeitsfenster einer Warnung mit dem eines bereits gemeldeten Eintrags
gleicher Identität + Gefahr, bleibt sie **still**; Ausnahmen: die Stufe ist gestiegen ODER
der Beginn liegt **≥ 2 h früher**. **Seit #1657 zählt Berührung als Überlappung:**
aneinandergrenzende Fenster (A endet 22:00, B beginnt 22:00) gelten als dieselbe Warnung
und bleiben still — das revidiert die vormalige #1245-AC-4-Präzisierung „T2 überlappt T1
nicht"; nur eine echte Lücke bleibt eigenständig. #1657 erkennt außerdem **Containment**:
umschließt das neue Fenster einen Bestandskandidaten vollständig und ist dessen
`reported_at` höchstens 6 h alt, bleibt der Fall trotz früherem Beginn still (reiner
Granularitätswechsel, Eskalation bei Stufenanstieg bleibt wirksam); bei einem älteren
Kandidaten greift Containment nicht. Bei stiller Revision wird der Eintrag fortgeschrieben
— der alte Schlüssel entfällt, `reported_at` bleibt das Datum der **tatsächlichen** Meldung.

**Reset:** siehe Punkt 3 — er trifft **nur** den Δ-Raum, nicht die amtlichen Warnungen.

### 2. Read-Only Briefing-Snapshot

**Änderung in `trip_alert.py`:**
- **ENTFERNT:** Zeile 160–168 — der Snapshot-Overwrite-Block nach erfolgreichem Alert.
- **Ergebnis:** `WeatherSnapshotService.save()` wird NUR vom Briefing-Scheduler aufgerufen.

Der Snapshot bleibt stabil bis zum nächsten Briefing (Morgen ODER Abend) — erlaubt konsistente Vergleiche über mehrere Alert-Läufe.

### 3. Reset beim Briefing

Nach dem `WeatherSnapshotService.save()`-Block wird `AlertStateService.reset(trip_id)`
aufgerufen — heute über die geteilte Fassung `reset_alert_memory()` in
`src/services/alert_briefing_anchor.py`, an die der Scheduler nur noch delegiert.

**Effekt:** Nach jedem Briefing endet der „Alert-Zyklus"; die Abweichung wird neu gemessen.

**🔴 Der Reset löscht NICHT die ganze Datei.** Hier stand bis 2026-08-11 „Dies löscht den
kompletten Trip-Alert-State" — das ist **seit #1460 (P2) falsch**. `AlertStateService.reset()`
schneidet am Präfix `official_alert:` und **behält** die amtlichen Warnungen: sie haben ihre
eigene Entprellung und überleben den Briefing-Versand. Ohne diesen Schnitt galt dieselbe,
unveränderte amtliche Warnung nach jedem Briefing wieder als „neu" und wurde erneut gemeldet.
Bleibt nach dem Schnitt kein amtlicher Eintrag übrig, verschwindet die Datei wie bisher ganz.

### 4. Symmetrische Δ-Erkennung

**Datei:** `src/services/weather_change_detection.py`

**Änderung:** Parameter `include_absolute: bool = True` hinzugefügt.

```python
def detect_changes(self, cached, fresh, include_absolute=True):
    """
    Erkennt Δ gegenüber Cache.
    - include_absolute=True (default): auch absolute Regel-Verletzungen
    - include_absolute=False (Alert-Pfad): nur symmetrische Δ
    """
```

**Alert-Pfad:** Ruft `detect_changes(cached, fresh, include_absolute=False)` auf.

**Schwellen Slice 1:** Kommen aus `MetricCatalog.get_change_detection_map()` (Defaults):
- Temperatur: ±5.0 °C
- Wind / Böen: ±20.0 km/h
- Regen: ±10.0 mm
- Nullgradgrenze (`freezing_level`): ±200.0 m — einzige Winter-Alert-Metrik seit Issue #959/ADR-0019 (`snow_line` konsolidiert)
- Gewitter (Wahrscheinlichkeit): ±1.0 (nur bei Level-Änderung)

### 5. Knapper Alert-Render-Pfad

**Datei:** `src/output/renderers/email/alert_compact.py` (NEU)

**Komplett RAUS:**
- Stundentabellen
- Etappen-Ausblick / Nächste Etappen
- Gewitter-Vorschau
- Metrik-Pills / Tages-Übersicht
- Stabilitäts-/Confidence-Hinweis
- Vortags-Vergleich
- Etappen-Statistik
- Nacht am Ziel

**DRIN — exakt drei Blöcke:**

1. **Kopfzeile (neutral):** "Wetter ändert sich seit dem Briefing"
2. **Pro Metrik:** `Metrik  Vorher → Jetzt  (Etappe N, km X–Y, HH–HH Uhr)` — sortiert nach **Stärke der Abweichung** (größtes `|delta|/threshold` zuerst)
3. **Fußzeile:** "Stand: <HH:MM> · verglichen mit dem letzten Briefing"

**Beispiel-Mail:**
```
Betreff: [GR20] Wetter ändert sich seit dem Briefing

Wetter ändert sich seit dem Briefing

Regen      2 → 18 mm     (Segment 3, 14–16 Uhr)
Böen      25 → 48 km/h   (Segment 3, 14–16 Uhr)
Temp      22 → 16 °C     (Segment 4, 16–18 Uhr)

Stand: heute 13:30 · verglichen mit dem letzten Briefing
```

> **Hinweis (#1744 A1, 2026-08-12):** Der Ortsbezug lautet seit dieser Änderung
> `Segment N` bzw. `🏁 Ziel` statt einer km-Spanne — dieselbe Sprache, die die
> amtliche Warnung spricht; die km-Spanne bleibt der Rückfall für Etappen ohne
> Kennung. Die obige Beispiel-Mail ist im Übrigen eine **Entwurfsskizze aus #816**
> und bildet den heutigen Renderer nicht zeilengetreu ab (real: Datenzeilen mit
> „Wo & wann"). Maßgeblich ist der Renderer, nicht diese Skizze.

**km-Erweiterung:** `build_segment_label()` in `helpers.py` wird um km erweitert:
- Neu: `"Etappe N, km X–Y, HH:MM–HH:MM"`
- Fallback (km = None/0.0): `"Etappe N, HH:MM–HH:MM"`

### 6. Mail-Header: `X-GZ-Mail-Type`

**Header setzt Alert-Typ:**
```
X-GZ-Mail-Type: deviation-alert
```

Dies unterscheidet Alert-Mails von Briefing-Mails (`trip-briefing`) und Orts-Vergleiche (`compare`).

**`briefing_mail_validator.py` Verhalten:** No-Op bei `X-GZ-Mail-Type: deviation-alert` (falsch-positiv vermeiden).

---

## Datenfluss

```
check_and_send_alerts(trip, cached_weather)
  ↓
  Laden alert_state (leer oder mit Einträgen)
  ↓
  detect_changes(cached, fresh, include_absolute=False)
  ↓
  Pro Change: alert_state Lookup
  ├─ Neu oder Eskalation → Alert durchlassen
  └─ Stagnation → unterdrücken
  ↓
  render_deviation_alert(changes, segments, trip_name) → (html, plain)
  ↓
  Versand via EmailOutput / TelegramOutput
  ↓
  alert_state updaten (neue/eskalierte Werte speichern)
```

**Nach Briefing-Versand (`trip_report_scheduler.py`):**
```
_send_briefing_report(trip, ...)
  ↓
  WeatherSnapshotService.save(snapshot)
  ↓
  AlertStateService.reset(trip_id)  ← NEU
```

**Additiver amtlicher Trigger (Issue #1088, Epic #1073 Slice 4):** `check_all_trips()` ruft pro
Trip zusätzlich `check_official_alert_triggers()` auf (neue/gestiegene amtliche Warnungen,
Toggle `Trip.official_alert_triggers_enabled`, strukturell getrennt von diesem
Wetter-Delta-Mechanismus). Feuert im selben Zyklus ein Wetter-Delta-Alert, wird die amtliche
Warnung als Text-Zusatz in dieselbe Nachricht gebündelt (`_send_alert(..., official_notices=...)`);
ohne Wetter-Delta erfolgt ein eigenständiger Versand über
`NotificationService.send_official_alert()`. SMS bleibt ohne Zusatztext (Zeichenlimit). Details:
`docs/features/epic-1073-alerts-at-it.md` (Slice 4), Spec
`docs/specs/_archive/modules/issue_1088_alert_official_warnings.md`.

---

## Mandantentrennung

`AlertStateService(user_id=...)` lädt/speichert strikt unter `data/users/{user_id}/alert_state/`.

**Test:** Zwei Nutzer mit je einem Trip — Alert für Nutzer A beeinflusst nicht Nutzer B.

---

## Referenzen

- **Spec:** `docs/specs/_archive/modules/issue_816_alert_deviation_core.md`
- **Weather Snapshot Service:** `docs/features/weather_snapshot_service.md`
- **Change Detection:** `src/services/weather_change_detection.py`
- **Trip Report Scheduler:** `src/services/trip_report_scheduler.py`
- **Alert Rendering:** `src/output/renderers/email/alert_compact.py`
- **Epic #813:** Alert-Rework (4 Slices)
  - Slice 1: Deviation-Kern (#816) ✓
  - Slice 2: Tab-Delta-Justierung (#817) ✓
  - Slice 3: Radar-Briefing-Integration (#818) ✓
  - Slice 4: Konvektiver Sicherheits-Override (#883) ✓ — konvektive Nowcast-Gefahr (Gewitter/Hagel) durchbricht die Briefing-Unterdrückung; normaler Regen, Quiet Hours und Cooldown bleiben aktiv

---

## Changelog

- **2026-06-14:** v1.0 Release — Alert-Deviation-Kern LIVE. Snapshot read-only, alert_state Melde-Gedächtnis, knapper Render-Pfad.
- **2026-07-08:** `check_all_trips()` um additiven amtlichen Alert-Trigger erweitert (Issue #1088, Epic #1073 Slice 4) — siehe Datenfluss-Abschnitt.
- **2026-07-09:** Auswertungskern (Change-Detection-Aufruf, Filter, Severity, Quiet-Hours, Cooldown, Kanal-/Detektorwahl) aus `trip_alert.py` in den location-generischen Shared-Service `DeviationAlertEngine` (`src/services/deviation_alert_engine.py`) extrahiert; `TripAlertService` ist seither dünner Adapter (Issue #1168, Epic #1095 Scheibe 1, reiner Umbau, Trip-Verhalten bit-identisch). Siehe `docs/adr/0021-shared-deviation-alert-engine.md` und `docs/features/architecture.md` (Abschnitt „Alert-System").
