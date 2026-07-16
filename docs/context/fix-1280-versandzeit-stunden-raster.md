# Context: fix-1280-versandzeit-stunden-raster

## Request Summary
Die Oberfläche lässt Versandzeiten minutengenau (`<input type="time">` ohne `step`)
einstellen, der Scheduler-Takt hält aber nur volle Stunden ein (Vergleich `.hour ==
hour`, Go-Cron ruft Dispatch stündlich). PO-Entscheid #1280 (bindend): **Eingabe auf
volle Stunden begrenzen** — für Trip UND Ortsvergleich, da das Feld geteilt ist.

## Related Files
| File | Relevance |
|------|-----------|
| `frontend/src/lib/components/shared/versand-tab/VTSchedulePlan.svelte:86,111` | Geteiltes `<input type="time">` (Morgen/Abend) OHNE `step`. Trip (`context="route"`) + Vergleich (`context="vergleich"`). Kern-Fix: `step`-Begrenzung |
| `src/services/compare_slot_scheduler.py:96,98` | Vergleich-Fälligkeit vergleicht `slots.morning_time.hour == hour` — verwirft Minuten (Backend, konsistent, nicht zu ändern) |
| `src/services/trip_report_scheduler.py:463,469` | `_get_morning_hour`/`_get_evening_hour` geben `.hour` zurück — identisches Muster beim Trip |
| `api/routers/scheduler.py:135` | Go-Cron ruft Dispatch **stündlich** — struktureller Takt, Ursache der Stunden-Granularität |
| `frontend/src/lib/utils/cockpitHelpers568.ts:240-272` | `deriveNextSend` — **geplanter** Versand, nutzt `slot.hour, slot.minute` → rendert aktuell Minuten (07:30). Nach Fix immer volle Stunde |
| `frontend/src/lib/components/compare/subscriptionHelpers.ts:54-58` | `formatNextSend(d)` formatiert `HH:MM` — wird für ZWEI Fälle genutzt: geplant (deriveNextSend) UND echter Zeitstempel (`letzter_versand`) |
| `frontend/src/lib/utils/_home/cockpitHelpers.ts:223` | `letzter_versand` — **echter** Versand-Zeitstempel (06:03), muss minutengenau bleiben. #1268-Fix hier NICHT rückgängig machen |
| `src/app/loader.py:249-251,536-537,647-648,1491-1492,1526-1527` | Persistenz `morning_time`/`evening_time` als ISO-String (`"07:30:00"`). Bestandsdaten-Rundungspunkt läge hier (Rundung beim Laden) |
| `src/app/models.py:725-726`, `src/app/trip.py:221-222` | Datenmodell der Zeitfelder (`time`-Objekt bzw. Optional[str]) |

## Existing Patterns
- **Slot-Auflösung:** `resolve_preset_slots()` (Compare) / `report_config.morning_time`
  (Trip) liefern `time`-Objekte; Scheduler nimmt nur `.hour`. Minuten werden serverseitig
  schon heute verworfen — die UI verspricht mehr, als das System hält.
- **Anzeige-Trennung (subtil, #1268):** `formatNextSend` rendert `HH:MM`. Geplant
  (`deriveNextSend`) darf gerastet werden; echter `letzter_versand` NICHT. In #1268 wurde
  die hartkodierte `:00`-Verkürzung entfernt, weil sie 06:03 als 06:00 auswies.
- **Bestandsdaten:** CLAUDE.md „Daten-Schema-Reworks" — Read-Modify-Write mit Merge,
  **niemals** Replace. Migration ODER Rundung beim Laden — Spec entscheidet.
- **Geteilte Komponente:** VTSchedulePlan wird über `context`-Prop von Trip und Vergleich
  geteilt (Trip/Compare-Teilungs-Invariante, CLAUDE.md). Ein `step` fixt beide zugleich.

## Dependencies
- **Upstream:** `<input type="time">` HTML-Attribut `step` (Sekunden; `step="3600"` = volle
  Stunde). Persistierte ISO-Zeitstrings. Go-Cron-Takt (stündlich, unverändert).
- **Downstream:** Zeitplan-Kachel + Versand-Anzeige (Home-Cockpit, Compare-Hero, Outbox);
  Scheduler-Fälligkeit (Trip + Compare). Beide Scheduler nehmen ohnehin nur `.hour`.

## Existing Specs
- `docs/specs/modules/` — Compare/Trip Versand-Tab (geteilte versand-tab-Organismen)
- Bezug: #1268 (Versandzeit-Anzeige auf echte Slots), #1232 (letzter Commit compare_slot_scheduler)

## Risks & Considerations
- **Regressions-Risiko #1268:** Wer ein Stunden-Raster in die Anzeige einzieht, darf NICHT
  den echten `letzter_versand`-Zeitstempel runden. Die beiden Aufrufer von `formatNextSend`
  müssen getrennt behandelt werden. Höchstes Risiko dieses Issues.
- **Bestandsdaten:** Gespeicherte `07:30:00` bleiben von `step` unberührt (`step` prüft nur
  Neu-Eingaben, nicht Bestandswerte im `value`). Ohne Migration/Rundung zeigt die Kachel bei
  Altdaten weiter 07:30, Versand läuft 07:00 → Widerspruch bliebe für Altdaten bestehen.
  Spec muss zwischen Migration (loader.py, RMW-Merge) und Rundung-beim-Laden entscheiden.
- **Browser-Verhalten `step`:** `step="3600"` blendet bei nativen Time-Pickern die
  Minuten-Spinner nicht zwingend aus, verhindert aber Nicht-Raster-Werte bei Validierung/
  Eingabe. Manuelles Tippen von 07:30 kann je nach Browser zunächst akzeptiert und erst bei
  Commit/`onchange` normalisiert werden — Verhalten auf Staging in beiden Kontexten prüfen.
- **Geteilte Validierung:** Staging-Prüfung MUSS beide Kontexte abdecken (Trip-Editor UND
  Vergleichs-Editor), sonst ist die Teilungs-Invariante nicht belegt.

## Analysis

### Type
Bug (PO-verifiziert, Adversary-Runde 3, file:line-belegt). Vorbestehend, nur durch #1268
sichtbar gemacht. PO-Entscheid bindend: Eingabe auf volle Stunden begrenzen.

### Kern-Erkenntnis
Der Scheduler-Takt (Go-Cron stündlich; Fälligkeit über `.hour`) verwirft Minuten **bereits
heute** — der reale Versand ist längst stundengenau. Der Bug ist ein **Anzeige-/
Versprechen-Widerspruch**, kein Versand-Fehler. Deshalb ändert die Normalisierung auf volle
Stunden **nichts** am tatsächlichen Sendeverhalten — sie richtet nur den gespeicherten/
angezeigten Wert an der Realität aus.

### Asymmetrie der Schreib-Seams (wichtigster Implementierungs-Befund)
| Kontext | Schreibpfad | Normalisierungs-Seam |
|---------|-------------|----------------------|
| **Compare** | `internal/handler/compare_preset.go` — typisiertes Feld | `validateComparePresetSlotTime:42` mutiert den Wert schon in-place (`*value = t.Format(...)`) → Minuten hier auf `:00` kappen |
| **Trip** | `internal/store/trip.go` / Trip-PUT — `report_config` als generische `map[string]interface{}` (RMW-Merge) | KEIN Zeit-Validator vorhanden → Normalisierung im Trip-Schreibpfad neu einziehen |
| **Geteilt** | `frontend/.../VTSchedulePlan.svelte:86,111` | `step` auf beiden `<input type="time">` — der EINZIGE echt geteilte Fix |

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `frontend/src/lib/components/shared/versand-tab/VTSchedulePlan.svelte` | MODIFY | `step={3600}` auf beiden Zeit-Feldern (Trip+Compare zugleich) |
| `internal/handler/compare_preset.go` | MODIFY | In `validateComparePresetSlotTime` Minuten/Sekunden auf `:00` kappen (Write-Normalisierung) |
| `internal/store/trip.go` (bzw. Trip-PUT-Handler) | MODIFY | `report_config.morning_time`/`evening_time` beim Schreiben auf volle Stunde kappen |
| Go GET-Serialize (Compare-List + Trip-Get) | MODIFY | Bestandsdaten (`07:30:00`) beim Ausliefern auf `:00` kappen, damit Editor-Input + Zeitplan-Kachel sofort konsistent sind |
| Tests (Go + Frontend) | CREATE | Write-Normalisierung, Read-Heilung, `step`-Präsenz, #1268-Nicht-Regress |

### Scope Assessment
- Files: ~5 (2 Go-Handler/Store, 1 Svelte, GET-Serialize, Tests)
- Estimated LoC: +80 / -5
- Risk Level: **MEDIUM** — Regressions-Risiko #1268 (letzter_versand darf NICHT gerundet werden); zwei getrennte Go-Seams

### Technical Approach (Tech-Lead-Empfehlung)
**Server-Write-Normalisierung + Read-Heilung + Frontend-`step`** — statt separatem
Migrations-Skript:
1. **`step={3600}`** auf beiden geteilten Inputs → verhindert neue krumme Eingaben in
   beiden Kontexten mit einem Fix.
2. **Write-Normalisierung** (floor Minute/Sekunde → `:00`) an beiden Go-Schreib-Seams →
   neue Speicherungen sind sauber; Bestand heilt beim nächsten Save (RMW-Merge, kein
   Replace).
3. **Read-Heilung** beim Go-GET-Serialize → gespeicherte `07:30:00` werden dem Frontend als
   `07:00:00` geliefert → Editor-Input, Zeitplan-Kachel und Scheduler zeigen denselben Wert.
   Kein per-Host-Migrations-Deploy-Schritt nötig.
4. **#1268-Schutz strukturell:** Normalisierung fasst AUSSCHLIESSLICH das Konfig-Feld
   (`morning_time`/`evening_time`) an, NIE `letzter_versand`/reale Sende-Zeitstempel. Die
   beiden `formatNextSend`-Aufrufer bleiben unberührt; der #1268-Fix wird nicht rückgängig.

**Verworfen:** (a) separates Migrations-Skript (per-Host-Deploy-Schritt, schwerer, unnötig
da kein aktiver Prod-User und Write-Normalisierung self-healing ist); (b) reine
Frontend-Rundung nur in `deriveNextSend` (ließe Editor-Input bei Altdaten weiter `07:30`
zeigen → Widerspruch innerhalb der UI bliebe).

### Dependencies
- Upstream: HTML-`step`-Attribut; Go `time.Parse`/Truncate; RMW-Merge-Pattern (CLAUDE.md)
- Downstream: Zeitplan-Kachel, Compare-Hero, Outbox, beide Scheduler (nehmen ohnehin `.hour`)

### Open Questions
- [ ] Trip-Read-Heilung: `report_config` ist generische Map — Kappung beim GET-Serialize
      oder erst beim nächsten Save akzeptieren? (Spec entscheidet; Empfehlung: GET-Serialize
      für sofortige Konsistenz.) → Kein PO-Eingriff nötig, technische Entscheidung.
