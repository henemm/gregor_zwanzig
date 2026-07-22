# Context: feat-1348-warn-consumption (Scheibe 2a von #1337)

## Request Summary
MeteoAlarm (amtliche Warnungen AT/IT) liefert in Prod dauerhaft 429; Ausfall wird
still geschluckt (Briefing ohne Warnungen). Diese Scheibe (2a) senkt den
Verbrauch der Warn-Dienste und macht den Ausfall sichtbar — ohne Renderer- oder
Fixture-Infra. Test/Staging-Isolation der Warn-APIs ist Scheibe 2b (separat).

## Root-Cause-Belege (Prod-Logs 2026-07-22)
- Prod ruft **minimal** ab: nur Länder-Index, ~8/h (2 Länder × 15-Min-Takt),
  modul-gecacht. Geometrie-/CAP-Abrufe heute: **0** (Fan-out ist NICHT die Ursache).
- **Alle 429 auf dem Index-Endpunkt**, konstant ~8/h ab 08:15 ganztägig.
- Persistente 429 auf minimaler Last ⇒ **Tages-Kontingent erschöpft** (kein
  Rate-Limit — 8/h ist 0,13/min). Wer es erschöpft (Prod eigene ~192/Tag vs.
  Test/Staging-Fremdlast auf geteilter IP) ist **nicht trennscharf belegt** →
  robuster Fix greift beide Hebel, aufgeteilt in 2a/2b.

## Ist-Stand (Bestandsaufnahme #1337 + Code)
| Warn-Dienst | Datei | Cache | 429-Backoff | Zähler | Fehler |
|---|---|---|---|---|---|
| MeteoAlarm | `src/services/official_alerts/meteoalarm.py:205-237` (Index), :241-279 (Geo/CAP) | Modul-Cache TTL **300s** Erfolg / **60s** Fehler | **nein** — `raise_for_status()`→`except`→60s-Cache, kein Retry-After | **nein** | still (`return None`→`[]`) |
| Météo-France Vigilance | `vigilance.py:90` | 300/60s | nein | nein | still |
| GeoSphere Warn | `geosphere_warn.py:77` | 300/60s pro Koord | nein | nein | still |
| Météo Forêts | `meteo_forets.py:79` | 300/60s pro Dept | nein | nein | still |
| Massif-Closure | `massif_closure.py:104` | 300/60s | nein | `_STATUS.error_count` (leichtgewichtig) | still (zählt Fehler) |

- Vorbild für Zähler/Budget: open-meteo `src/providers/call_log.py` →
  `data/diagnostics/openmeteo_calls.jsonl`; `ForecastBudgetGate`
  (`src/services/forecast_budget.py`). **Kein** Warn-Dienst hat Analog.
- 300s-Erfolgs-TTL ist für **amtliche Warnungen** unnötig aggressiv — Warnungen
  ändern sich langsam (Onset/Expire in Stunden); 15-Min-Takt fragt trotzdem alle
  ~5 min neu, weil TTL < Takt.

## Scope 2a (diese Scheibe) — regressionsarm, enthalten in official_alerts/
1. **Warngerechter längerer Cache-TTL** für die Warn-Dienste (Erfolgs-TTL rauf,
   z.B. ~30 min — konkreter Wert in Spec) → drastisch weniger Abrufe unter jedem
   Kontingent. Failure-TTL differenziert.
2. **429-bewusster Rückzug:** bei 429 `Retry-After` respektieren (falls Header),
   sonst langes Backoff-Fenster — kein Dauerfeuer im Takt; und **laut** loggen
   statt still.
3. **Zentraler Egress-Zähler** für die Warn-Dienste (jsonl analog open-meteo bzw.
   erweiterter Zähler) — Observability, heute blind.

## Ausdrücklich NICHT in 2a (→ 2b / Folge)
- Test/Staging-Isolation der Warn-APIs (Wächter-Inventar `TEST_ACCESS`→`BLOCKED`
  + Attrappen + live-abfragende Tests auf `live`-Marker) — braucht Fixture-Infra
  + Test-Surgery, eigenes Regressionsrisiko.
- Briefing-sichtbarer Hinweis "Warnungen nicht abrufbar" (#1346-Prinzip) — berührt
  Renderer (Renderer-Mail-Gate #811), eigene Scheibe.

## Risks & Considerations
- **Regression:** längerer Cache darf Tests nicht brechen, die Cache-Verhalten/
  Frische prüfen — Modul-Cache-Reset in betroffenen Tests beachten. Charakterisierungs-
  Test des heutigen Verhaltens vor Umbau.
- **Kern-Test deterministisch:** 429-Backoff + TTL + Zähler ohne Live-Netz prüfbar
  (aufgezeichnete 429-Antwort als Fixture, Zeit mocken/injizieren).
- Warn-Dienste teilen **kein** gemeinsames Fetch-Gerüst → Gefahr der Duplizierung;
  wenn möglich einen geteilten Helfer (Cache+429-Backoff+Zähler) statt 5× Copy-Paste.
- Kein Live-Schaden (keine Nutzer), aber sicherheitsrelevanter Defekt vor Start.
