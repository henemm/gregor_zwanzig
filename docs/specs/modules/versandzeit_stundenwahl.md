---
entity_id: versandzeit_stundenwahl
type: bug
created: 2026-07-25
updated: 2026-07-25
status: approved
version: "1.0"
tags: [frontend, mobile, versand-tab, shared-component, trip-compare-sharing]
---

# Versandzeit-Auswahl: Stunden-Liste statt Uhrzeit-Eingabefeld (Issue #1379)

## Approval

- [x] Approved
- PO-Freigabe 2026-07-25 (go)

## Purpose

Im Versand-Reiter (Trip **und** Ortsvergleich) lässt sich die Briefing-Uhrzeit
aktuell in ein `<input type="time">` eintippen, das Minuten zulässt — der
Server kappt diese beim Speichern kommentarlos auf die volle Stunde (gewolltes
Verhalten aus #1280, bleibt unverändert). Für den Nutzer sieht das wie
Datenverlust aus: er trägt `05:30` ein, die Oberfläche bestätigt „gespeichert",
nach dem Neuladen steht dort `05:00`, ohne jeden Hinweis. Dieser Fix ersetzt
das Eingabefeld durch eine Auswahlliste mit den 24 vollen Stunden (`00:00` bis
`23:00`), sodass eine minutengenaue Eingabe von vornherein unmöglich ist
(PO-Entscheidung 2026-07-25).

## Source

- **File:** `frontend/src/lib/components/shared/versand-tab/VTSchedulePlan.svelte`
- **Identifier:** die beiden Uhrzeit-Felder mit `data-testid="report-morning-time"`
  und `data-testid="report-evening-time"` (aktuell `<input type="time"
  step={3600}>`)

**Schicht:** Frontend (`frontend/src/...`, SvelteKit) — kein Go-API-/Python-Core-Anteil.
Die serverseitige Kappung (`internal/store/slot_hour_normalization.go`,
`TruncateTimeStringToHour`) bleibt unverändert bestehen; sie ist die
Absicherung für Bestandsdaten und API-Direktzugriffe, nicht der primäre
Nutzerpfad.

## Estimated Scope

- **LoC:** ~+90/-40
- **Files:** 4-5 (1 Kern-Komponente, 2-3 Tests angepasst, 1 Test neu/erweitert)
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `VTSchedulePlan.svelte` (`frontend/src/lib/components/shared/versand-tab/`) | Svelte-Komponente | Geteilter Zeitplan-Baustein — **einzige** Einbindungsstelle der Uhrzeit-Felder (verifiziert, s. u.), Parameter `context="route"\|"vergleich"` |
| `VersandTab.svelte` (`frontend/src/lib/components/shared/`) | Svelte-Organism | Bindet `VTSchedulePlan` zweimal ein — einmal für `context="route"` (Trip), einmal für `context="vergleich"` (Ortsvergleich); beide Male dieselbe Instanz, keine Kopie |
| `EditReportConfigSection.svelte` (`frontend/src/lib/components/edit/`) | Svelte-Komponente | Bindet `VTSchedulePlan context="route"` ein — läuft sowohl in `TripNewEditor.svelte` (Trip anlegen) als auch in `TripEditView.svelte` (Trip bearbeiten), also derselbe Baustein für beide Wege |
| `TruncateTimeStringToHour` / `NormalizeReportConfigSlotTimes` (`internal/store/slot_hour_normalization.go`) | Go-Funktion | Serverseitige Kappung auf volle Stunde — bleibt unverändert, ist NICHT Teil dieses Fixes |
| `toHHMMSS` (`frontend/src/lib/utils/time.ts`) | TS-Funktion | Formatiert den Auswahlwert vor dem Schreiben ins `reportConfig`-Objekt — unverändert weiterverwendet |
| `makeTimeHandler` (in `VersandTab.svelte` und `EditReportConfigSection.svelte`, je eigene Kopie) | Handler-Factory | Reicht `(e.target as HTMLInputElement).value` an die Callbacks `onMorningTime`/`onEveningTime` durch — funktioniert unverändert mit einem `<select>`-Element, da `.value` auf beiden Element-Typen existiert; die Typannotation `HTMLInputElement` ist danach ungenau, aber kein Build-Fehler |

## Implementation Details

Die beiden `<input type="time" step={3600} ...>`-Felder in
`VTSchedulePlan.svelte` (Morgen- und Abend-Karte) werden durch je ein
`<select>` mit 24 Optionen (`00:00` … `23:00`) ersetzt — dasselbe Muster, das
im selben File bereits für das Tagesfenster (`day-window-start-hour`/
`day-window-end-hour`) und in der unabhängigen Altkomponente
`ReportConfigDialog.svelte` (s. „Weitere Uhrzeit-Eingaben" unten) verwendet
wird. `data-testid`, Callback-Namen (`onMorningTime`/`onEveningTime`) und das
Wertformat (`"HH:MM"`) bleiben unverändert, damit Eltern-Komponenten
(`VersandTab.svelte`, `EditReportConfigSection.svelte`) unangetastet bleiben
und die Trip/Compare-Teilungsinvariante automatisch für beide Kontexte greift
— es gibt nur diese eine Einbindungsstelle.

Für Bestandswerte mit Minuten (siehe „Bestandsdaten" unten) wird die
angezeigte Auswahl aus der Stunde des übergebenen Werts abgeleitet (Minuten
ignoriert, keine Rundung nötig — Truncate wie serverseitig), damit die Liste
nie leer erscheint und nie einen falschen Wert stumm zurückschreibt, bevor der
Nutzer selbst etwas auswählt.

Die Schnellwahl-Chips („Morgens 07:00" / „Abends 18:00") bleiben unverändert
bestehen — sie feuern denselben Callback mit einem festen `"HH:MM"`-String und
sind vom Feldtyp unabhängig.

### Weitere Uhrzeit-Eingaben (Recherche-Ergebnis)

- **`ReportConfigDialog.svelte`** (`frontend/src/lib/components/molecules/`):
  ist **produktiv eingebunden** — mobiler Bottom-Sheet-Eintrag „Alerts
  justieren" auf `/trips` (kein Desktop-Zugang, `desktop:hidden`). Verwendet
  bereits ein `<Select>` mit den 24 vollen Stunden (`getHour`/`setHour`-Helfer
  auf `config.morning_time`/`evening_time`) — **hat den Bug nicht**, da dort
  ohnehin nie Minuten eingegeben werden können. Eigenständige, unabhängige
  UI-Fläche (kein Import von `VTSchedulePlan`, keine geteilte Datei) und daher
  **nicht Teil dieses Fixes** — wird nicht verändert.
- Keine weiteren `type="time"`-Felder oder `morning_time`/`evening_time`-Eingaben
  in `frontend/src`, die produktiv erreichbar sind (grep-verifiziert).
- Der Ortsvergleich nutzt **dieselben** Zeitfelder über `VTSchedulePlan
  context="vergleich"` (`VersandTab.svelte`, vergleich-Zweig) — die
  serverseitige Kappung greift dort identisch (`validateComparePresetSlotTime`
  in `internal/handler/compare_preset.go`, `HealComparePresetSlotTimes` in
  `slot_hour_normalization.go`). Der Ortsvergleich ist damit **im
  Geltungsbereich der ACs**, nicht nur der Trip.

## Expected Behavior

- **Input:** Nutzer öffnet den Versand-Reiter eines Trips oder eines
  Ortsvergleichs (bestehend oder neu angelegt) und will die Uhrzeit für das
  Morgen- oder Abend-Briefing festlegen.
- **Output:** Statt eines frei beschreibbaren Uhrzeit-Feldes zeigt die
  Oberfläche eine Liste der 24 vollen Stunden zur Auswahl. Die getroffene
  Auswahl bleibt nach dem Speichern und Neuladen exakt erhalten.
- **Side effects:** keine — die serverseitige Stundenkappung (#1280) bleibt
  als Absicherung bestehen, greift im UI-Pfad aber nicht mehr sichtbar ein,
  weil gar keine ungültige Eingabe mehr möglich ist.

## Acceptance Criteria

- **AC-1:** Given der Versand-Reiter eines Trips ist geöffnet und mindestens
  ein Briefing-Kanal ist aktiv / When der Nutzer die Uhrzeit für das
  Morgen- oder das Abend-Briefing ändern will / Then stehen ihm dafür nur die
  24 vollen Stunden (00:00 bis 23:00) zur Auswahl; eine Eingabe mit Minuten
  ist an dieser Stelle nicht möglich.
  - Test: `frontend/src/lib/components/shared/versand-tab/__tests__/vt_schedule_plan_hour_step.test.ts`
    (umgebaut) — prüft, dass die Morgen- und Abend-Zeitfelder als
    Auswahlliste mit genau 24 Optionen (`00:00`…`23:00`) angelegt sind, kein
    frei beschreibbares Eingabefeld mehr.

- **AC-2:** Given der Nutzer wählt für das Morgen-Briefing eine bestimmte
  volle Stunde aus der Liste aus und speichert / When die Seite anschließend
  neu geladen wird / Then zeigt die Liste exakt dieselbe Stunde wieder an —
  kein anderer Wert erscheint, nichts „springt" nach dem Neuladen (der
  ursprünglich gemeldete Fall aus #1379).
  - Test: neuer/erweiterter E2E-Test (`frontend/e2e/`, echtes Backend, kein
    Mock) — Uhrzeit über die Auswahlliste setzen, speichern, Seite neu laden,
    denselben Wert in der Auswahlliste erneut prüfen.

- **AC-3:** Given im Ortsvergleich (Compare-Editor, Versand-Reiter) ist
  mindestens ein Kanal aktiv / When der Nutzer dort die Versandzeit für das
  Morgen- oder Abend-Briefing wählt / Then verhält sich die Auswahl exakt
  identisch zum Trip (24 volle Stunden, keine Minuteneingabe möglich) — es
  handelt sich um denselben Baustein, keine eigene Nachbildung im Ortsvergleich.
  - Test: `frontend/e2e/versand-tab-vergleich.spec.ts` (angepasst: bisheriges
    `.fill('08:00')` auf die neue Auswahlliste umgestellt) plus die
    Teilungs-Prüfung in `vt_schedule_plan_hour_step.test.ts`, die verifiziert,
    dass `VersandTab.svelte` dieselbe `VTSchedulePlan`-Instanz für beide
    Kontexte verwendet (kein Duplikat).

- **AC-4:** Given ein Nutzer legt einen neuen Trip an und aktiviert dabei
  einen Briefing-Kanal im Versand-Schritt / When er dort die Morgen- oder
  Abend-Uhrzeit setzen will / Then steht ihm dieselbe Stunden-Auswahlliste zur
  Verfügung wie beim nachträglichen Bearbeiten eines bestehenden Trips — kein
  Unterschied zwischen Anlegen und Bearbeiten.
  - Test: E2E-Test über `/trips/new` (`TripNewEditor`/`EditReportConfigSection`)
    — Auswahlliste im Versand-Schritt vorhanden und bedienbar, gleiche
    `data-testid`s wie beim Bearbeiten.

- **AC-5:** Given ein Trip oder Ortsvergleich hat aus welchem Grund auch immer
  einen gespeicherten Versandzeit-Wert mit Minuten ungleich `:00` (z. B. ein
  Altbestand vor der serverseitigen Kappung) / When der Versand-Reiter für
  diesen Trip/Ortsvergleich geöffnet wird / Then zeigt die Auswahlliste eine
  gültige, sinnvoll vorbelegte volle Stunde (die Stunde des gespeicherten
  Werts) — die Auswahl erscheint nicht leer und nicht zufällig, und nichts
  wird automatisch überschrieben, bevor der Nutzer selbst eine Auswahl trifft.
  - Test: `vt_schedule_plan_hour_step.test.ts` bzw. Komponenten-Logik-Test,
    der einen `"07:30"`-Wert übergibt und die vorbelegte Auswahl (`07:00`)
    prüft.

## Known Limitations

- `ReportConfigDialog.svelte` (mobiler Bottom-Sheet-Zugang „Alerts justieren"
  auf `/trips`) bleibt unverändert. Sie hat den Bug nicht (bereits
  Auswahlliste), ist aber eine dritte, von `VTSchedulePlan` unabhängige
  Editier-Fläche für dieselben Felder — eine mögliche künftige
  Konsolidierung ist NICHT Teil dieses Fixes.
- Die Schnellwahl-Chips (07:00/18:00) und das Tagesfenster
  (`day-window-start-hour`/`-end-hour`) sind von diesem Fix inhaltlich nicht
  betroffen und bleiben unverändert.
- Die serverseitige Stundenkappung (#1280) wird durch diesen Fix nicht
  entfernt — sie bleibt als Absicherung für API-Direktzugriffe und
  Altbestand aktiv, ist im UI-Pfad nach diesem Fix aber nicht mehr sichtbar
  wirksam, weil keine ungültige Eingabe mehr möglich ist.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reiner UI-Bugfix innerhalb des bereits etablierten
  Auswahllisten-Musters (Tagesfenster-Selects im selben File,
  `ReportConfigDialog.svelte`) — keine neue Grundsatzentscheidung nötig.

## Changelog

- 2026-07-25: Initial spec erstellt — Issue #1379
- 2026-07-25: PO-Freigabe (go), Status auf `approved` gesetzt, ACs unverändert.
