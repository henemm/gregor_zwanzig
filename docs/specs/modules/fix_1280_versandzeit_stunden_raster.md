---
entity_id: fix_1280_versandzeit_stunden_raster
type: module
created: 2026-07-16
updated: 2026-07-16
status: draft
version: "1.0"
tags: [bugfix, versand-tab, scheduler, trip, compare, shared-component]
---

# Versandzeit-Eingabe auf volle Stunden begrenzen (#1280)

## Approval

- [x] Approved — PO-Freigabe ('go') 2026-07-16

## Purpose

Der Scheduler (Go-Cron, stündlicher Takt; Fälligkeit über `.hour`) versendet Briefings
schon heute ausschließlich zur vollen Stunde — Minuten werden serverseitig verworfen. Die
Versandzeit-Eingabe im geteilten Versand-Tab (Trip UND Ortsvergleich) erlaubt aber
minutengenaue Werte (z.B. 07:30), was ein falsches Versprechen macht: der Nutzer stellt
07:30 ein, der Versand kommt trotzdem um 07:00. Diese Spec richtet Eingabe, Speicherung
und Anzeige an der bereits bestehenden stundengenauen Realität aus — ohne das
Sendeverhalten selbst zu ändern.

## Source

- **File:** `frontend/src/lib/components/shared/versand-tab/VTSchedulePlan.svelte`
- **Identifier:** `<input type="time" data-testid="report-morning-time">` (Zeile 86),
  `<input type="time" data-testid="report-evening-time">` (Zeile 111)

> **Schicht-Hinweis:** Diese Spec berührt zwei Schichten:
> - **Frontend** → `frontend/src/lib/components/shared/versand-tab/VTSchedulePlan.svelte`
>   (geteilte SvelteKit-Komponente, `context="route"|"vergleich"`)
> - **Go-API** → `internal/handler/compare_preset.go`, `internal/store/trip.go` bzw.
>   Trip-PUT-Handler, sowie das jeweilige GET-Serialize (Compare-List + Trip-Get)

## Estimated Scope

- **LoC:** ~+80 / -5
- **Files:** ~5 (1 Svelte, 2 Go-Schreib-Seams, 1 Go-Lese-Seam-Gruppe, Tests)
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `internal/handler/compare_preset.go::validateComparePresetSlotTime` | function | Bestehender In-Place-Mutations-Seam für Compare-Slot-Zeiten; hier Minuten/Sekunden kappen |
| `internal/store/trip.go` / Trip-PUT-Handler | module | `report_config.morning_time`/`evening_time` als generische Map, RMW-Merge; neuer Normalisierungs-Seam |
| `src/services/compare_slot_scheduler.py` | module | Fälligkeitsprüfung über `.hour` (Zeile 96, 98) — unverändert, Referenz für "Realität" |
| `src/services/trip_report_scheduler.py` | module | `_get_morning_hour`/`_get_evening_hour` (Zeile 463, 469) — unverändert, Referenz für "Realität" |
| `frontend/src/lib/components/compare/subscriptionHelpers.ts::formatNextSend` | function | Formatiert `HH:MM` für zwei unterschiedliche Aufrufer (geplant vs. real) — Abgrenzung MUSS erhalten bleiben (#1268) |

## Implementation Details

**Technischer Ansatz (Tech-Lead-Empfehlung): Server-Write-Normalisierung + Read-Heilung +
Frontend-`step`** — statt separatem Migrations-Skript.

1. **Frontend `step={3600}`** auf beiden `<input type="time">` in
   `VTSchedulePlan.svelte:86,111`. Da die Komponente über die `context`-Prop von Trip
   (`context="route"`) UND Vergleich (`context="vergleich"`) gemeinsam genutzt wird, deckt
   dieser eine Fix beide Editoren ab (Trip/Compare-Teilungs-Invariante). Verhindert neue
   krumme Eingaben in beiden Kontexten.

2. **Write-Normalisierung (Go, Server-seitig)** — Minuten/Sekunden beim Schreiben auf
   `:00` kappen (Truncate, nicht Runden — Realität ist die volle Stunde davor):
   - **Compare:** `validateComparePresetSlotTime` in `internal/handler/compare_preset.go`
     (Zeile 42) mutiert den Wert bereits in-place (`*value = t.Format("15:04:05")`, Zeile
     53). Hier vor dem Zurückschreiben `t` auf volle Stunde kappen.
   - **Trip:** `report_config.morning_time`/`evening_time` liegen als generische
     `map[string]interface{}` ohne Zeit-Validator vor (RMW-Merge-Pattern gemäß CLAUDE.md
     "Daten-Schema-Reworks"). Der Developer identifiziert den konkreten Trip-Schreib-Seam
     (Trip-PUT-Handler bzw. `internal/store/trip.go`) und zieht dort einen analogen
     Kapp-Schritt für diese beiden Feldnamen ein — ohne andere `report_config`-Felder
     anzufassen (Merge, kein Replace).

3. **Read-Heilung (Go GET-Serialize)** — beim Ausliefern gespeicherter Bestandsdaten
   (z.B. `"07:30:00"`) an das Compare-List-Handler bzw. Trip-Get-Handler wird die Zeit
   ebenfalls auf volle Stunde gekappt, BEVOR sie an das Frontend geht. So zeigen
   Editor-Input und Zeitplan-Kachel sofort denselben Wert — ohne separates
   Migrations-Skript. Bestandsdaten heilen zusätzlich beim nächsten Save (RMW-Merge,
   self-healing).

4. **#1268-Schutz (KRITISCH, höchstes Regressions-Risiko dieser Änderung):** Die
   Normalisierung fasst AUSSCHLIESSLICH das Konfig-Feld `morning_time`/`evening_time` an,
   NIEMALS `letzter_versand` oder andere reale Sende-Zeitstempel.
   `formatNextSend` (`frontend/src/lib/components/compare/subscriptionHelpers.ts:54-58`)
   hat zwei Aufrufer:
   - `deriveNextSend` (geplanter Versand) — darf gerastet erscheinen, da er auf dem
     normalisierten Konfig-Feld basiert.
   - `letzter_versand` (`frontend/src/lib/utils/_home/cockpitHelpers.ts:223`, echter
     Zeitstempel wie 06:03) — MUSS minutengenau bleiben. Der #1268-Fix (Entfernung der
     hartkodierten `:00`-Verkürzung) wird durch diese Änderung NICHT berührt und NICHT
     rückgängig gemacht.

## Expected Behavior

- **Input:** Nutzer öffnet den Versand-Tab (Trip-Editor oder Vergleichs-Editor) und stellt
  eine Uhrzeit für Morgen- oder Abend-Briefing ein.
- **Output:** Das Zeitfeld erlaubt nur volle Stunden (00:00, 01:00, ... 23:00). Wird
  dennoch ein krummer Wert an den Server geschickt (z.B. per API direkt, nicht über die
  UI), normalisiert der Server ihn beim Speichern auf die volle Stunde davor. Beim Laden
  liefert der Server gespeicherte Bestandswerte ebenfalls als volle Stunde aus.
- **Side effects:** Zeitplan-Kachel (Home-Cockpit), Compare-Hero und Outbox zeigen nach
  dem Fix konsistent volle Stunden für den geplanten Versand. Der reale
  `letzter_versand`-Zeitstempel bleibt unverändert minutengenau. Das tatsächliche
  Sendeverhalten (Go-Cron, stündlicher Takt) ändert sich nicht — es wird nur sichtbar
  gemacht, was ohnehin gilt.

## Acceptance Criteria

- **AC-1:** Given der Nutzer öffnet den Vergleichs-Editor und trägt im Versand-Tab eine
  Uhrzeit mit Minuten ungleich :00 ein (z.B. 07:30) / When er speichert / Then der
  gespeicherte und beim erneuten Öffnen angezeigte Wert ist auf die volle Stunde
  gerundet (07:00), nicht 07:30.
  - Test: Im Vergleichs-Editor eine Slot-Zeit über das Zeitfeld auf 07:30 setzen,
    speichern, Editor neu laden (Reload oder Navigation weg und zurück) — angezeigter
    Wert ist 07:00, nicht 07:30.

- **AC-2:** Given der Nutzer öffnet den Trip-Editor und trägt im Versand-Tab eine Uhrzeit
  mit Minuten ungleich :00 ein / When er speichert / Then der gespeicherte und
  angezeigte Wert ist auf die volle Stunde gerundet — analog zu AC-1, aber im
  Trip-Kontext.
  - Test: Im Trip-Editor (Morgen- oder Abend-Briefing) eine Uhrzeit über das Zeitfeld auf
    18:45 setzen, speichern, Editor neu laden — angezeigter Wert ist 18:00, nicht 18:45.

- **AC-3:** Given ein Trip oder Vergleich hat aus der Zeit vor diesem Fix eine
  gespeicherte krumme Versandzeit (z.B. 07:30:00) / When der Nutzer den Editor UND die
  Zeitplan-Kachel im Cockpit öffnet, ohne zu speichern / Then beide zeigen denselben
  Wert (volle Stunde, z.B. 07:00) statt eines Widerspruchs zwischen Editor-Anzeige und
  Kachel-Anzeige.
  - Test: Über die API direkt (oder eine vor dem Fix erzeugte Konfiguration) eine
    Bestandszeit mit Minuten ungleich :00 setzen, dann Editor und Cockpit-Kachel für
    denselben Trip/Vergleich öffnen — beide zeigen die volle Stunde, kein Auseinanderfall.

- **AC-4:** Given ein Vergleich hat einen realen Versand-Zeitstempel `letzter_versand`
  mit Minuten ungleich :00 (z.B. 06:03) / When der Nutzer das Cockpit oder die
  Outbox öffnet / Then der reale Zeitstempel wird weiterhin minutengenau angezeigt
  (06:03), nicht auf die volle Stunde gerundet (kein Rückfall auf den vor #1268
  behobenen Fehler).
  - Test: Ein Test-Briefing auslösen, das zu einer Minute ungleich :00 tatsächlich
    versendet wird (oder eine bestehende Fixture mit `letzter_versand` = 06:03
    verwenden), Cockpit/Outbox öffnen — angezeigte Versandzeit ist weiterhin 06:03.

- **AC-5:** Given der geteilte Versand-Tab (`VTSchedulePlan.svelte`) wird sowohl im
  Trip-Editor (`context="route"`) als auch im Vergleichs-Editor (`context="vergleich"`)
  verwendet / When die Stunden-Beschränkung geprüft wird / Then sie greift in beiden
  Kontexten identisch, ohne dass der Fix an zwei Stellen dupliziert wurde.
  - Test: In beiden Editoren (Trip UND Vergleich) nacheinander versuchen, eine krumme
    Minute über das Zeitfeld einzustellen — in beiden Fällen verhindert das UI-Element
    die Feinjustierung auf Minutenebene bzw. der gespeicherte Wert landet nach dem
    Speichern auf der vollen Stunde.

## Known Limitations

- **Browser-Verhalten von `step`:** `step={3600}` auf `<input type="time">` blendet bei
  nativen Zeit-Pickern die Minuten-Spinner nicht in jedem Browser zwingend aus. Manuelles
  Tippen einer krummen Zeit (z.B. "07:30") kann je nach Browser zunächst im Feld
  akzeptiert und erst bei `onchange`/Commit normalisiert werden. Die verbindliche Instanz
  für Korrektheit ist deshalb NICHT das `step`-Attribut allein, sondern die
  Server-Write-Normalisierung (AC-1, AC-2) — das Frontend-`step` ist eine
  UX-Verbesserung, kein alleiniger Durchsetzungsmechanismus.
- **Kein separates Migrations-Skript:** Bestandsdaten werden nicht durch einen aktiven
  Migrationslauf verändert, sondern durch Read-Heilung (AC-3) beim Ausliefern sowie
  Self-Healing beim nächsten Save (RMW-Merge). Da es keine aktiven Produktiv-Nutzer gibt,
  ist dieser Zwischenzustand unkritisch.
- **Scheduler-Verhalten unverändert:** Diese Änderung ändert nichts an
  `compare_slot_scheduler.py`, `trip_report_scheduler.py` oder dem Go-Cron-Takt. Sie
  macht lediglich die UI/Anzeige konsistent mit der bereits bestehenden stundengenauen
  Versand-Realität.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Es handelt sich um einen Bug-Fix nach etabliertem Muster (Server-seitige
  Write-Normalisierung an bestehenden Mutations-Seams + Read-Heilung beim Serialize),
  der die bereits dokumentierte Trip/Compare-Teilungs-Invariante (geteilte
  `VTSchedulePlan.svelte`-Komponente) respektiert statt neue Architekturentscheidungen zu
  treffen. Die einzige bewusst getroffene Alternativen-Abwägung — separates
  Migrations-Skript vs. self-healing Write/Read-Normalisierung — ist keine
  Architekturentscheidung von Tragweite, sondern eine lokale Implementierungswahl:
  Migrations-Skripte sind laut CLAUDE.md ("Daten-Schema-Reworks") ein Per-Host-Deploy-
  Schritt mit zusätzlichem Betriebsrisiko, während RMW-Merge beim nächsten Save plus
  Read-Heilung beim GET denselben Effekt ohne zusätzlichen Deploy-Schritt erreicht — bei
  keinem aktiven Produktiv-Nutzer ist das Restrisiko vernachlässigbar.

## Changelog

- 2026-07-16: Initial spec created
