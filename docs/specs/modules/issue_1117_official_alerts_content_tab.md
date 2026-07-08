---
entity_id: issue_1117_official_alerts_content_tab
type: bugfix
created: 2026-07-08
updated: 2026-07-08
status: draft
version: "1.0"
tags: [frontend, trip-detail, official-alerts, content-tab]
---

<!-- Issue #1117 — Amtliche Warnungen fehlen bei E-Mail-Inhalts-Auswahl -->

# Amtliche Warnungen im Inhalt-Tab (Issue #1117)

## Approval

- [ ] Approved

## Purpose

Der bestehende Schalter „Amtliche Warnungen" (`trip.official_alerts_enabled`, steuert ob amtliche Wetterwarnungen im E-Mail-Briefing erscheinen) ist aktuell nur im Tab „Alerts" konfigurierbar. Er gehört inhaltlich auch in den Tab „Inhalt" (E-Mail-Inhalts-Auswahl), wo alle anderen E-Mail-Bausteine (Ausblick, Etappen-Kennzahlen, Vortag-Vergleich) an-/abgeschaltet werden — Nutzer suchen ihn dort und finden ihn nicht. Diese Spec ergänzt einen zweiten, gleichwertigen Einstiegspunkt für dasselbe Datenfeld, ohne den bestehenden im Alerts-Tab zu entfernen.

## Source

- **File:** `frontend/src/lib/components/trip-detail/WeatherMetricsTab.svelte`
- **Identifier:** neuer State `officialAlertsEnabled`, Funktionen `handleSave()`, `scheduleAutoSave()`, `handleDiscard()`, `snapshot()`
- **File (Korrektur nach TDD-RED-Vorbereitung):** `frontend/src/lib/components/trip-detail/TripTabs.svelte`
- **Identifier:** `handleValueChange()` — Flush-Guard-Bedingung erweitert

> **Schicht-Hinweis:** Reine Frontend-Änderung (`frontend/src/...`, SvelteKit, produktive Oberfläche auf gregor20.henemm.com). Kein Go-API-Code, kein Python-Core-Code betroffen — beide sind bereits vollständig verdrahtet (Issue #1087/#1040).

## Estimated Scope

- **LoC:** ~48 (WeatherMetricsTab.svelte, tatsächlich) + ~6 (TripTabs.svelte Flush-Guard, tatsächlich) + ~200 (Playwright-E2E-Testdatei)
- **Files:** 3 (2 MODIFY Komponenten + 1 CREATE Test-Spec — kein separates Staging-Setup/-Config nötig, siehe Test Plan-Korrektur unten)
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `PUT /api/trips/{id}` (`internal/handler/trip.go`, Pointer-Pattern `OfficialAlertsEnabled *bool`) | Go-API | Nimmt `official_alerts_enabled` bereits entgegen und merged es korrekt (Read-Modify-Write, `nil` = unverändert). Reine Nutzung, keine Änderung. |
| `src/services/trip_report_scheduler.py:652` | Python-Core | Liest `trip.official_alerts_enabled` bereits als Gate für den Abruf amtlicher Warnungen im Trip-Briefing. Reine Nutzung, keine Änderung. |
| `frontend/src/lib/types.ts` (Z. 281, 496) | Frontend-Typ | `Trip.official_alerts_enabled?: boolean` bereits typisiert. Keine Typ-Änderung nötig. |
| `frontend/src/lib/components/alerts-tab/AlertsTab.svelte` | Frontend-Referenz | Bestehender Schalter (Zeilen ~49/92/135-140) dient als Vorlage für Feld-Semantik (`?? true`-Default) und bleibt unverändert als zweiter, weiterhin gültiger Einstiegspunkt bestehen. |
| `frontend/src/lib/components/edit/EditReportConfigSection.svelte` | Frontend, NICHT geändert | Enthält die Card „E-Mail-Inhalt" (`data-testid="report-mail-content"`), in der `official_alerts_enabled` bewusst NICHT als neue Prop ergänzt wird (5 Einbindungsstellen, davon 2 toter Code — Blast Radius wird klein gehalten). |
| `Checkbox` (`$lib/components/ui/checkbox`) | Frontend-Komponente | Wiederverwendetes UI-Element, identisch zum Checkbox-Pattern der 3 bestehenden Content-Bausteine (`show_outlook`, `show_stage_stats`, `show_yesterday_comparison`). |

## Implementation Details

Alle Änderungen ausschließlich in `WeatherMetricsTab.svelte`:

1. **Neuer State** (nahe der bestehenden `telegramKurzform`-Deklaration, Z. 76):
   `let officialAlertsEnabled = $state<boolean>(trip.official_alerts_enabled ?? true);`
   — analog zum bestehenden `telegramKurzform`-Init-Pattern, Default `true` matcht den Backend-Default.

2. **`snapshot()`** (Z. 145-150) und **`isDirty`** (Z. 141-143) werden um `officialAlertsEnabled` erweitert, damit eine reine Checkbox-Änderung den Tab korrekt als „dirty" markiert und ein Reload/Preset-Wechsel den Wert korrekt vergleicht.

3. **`initFromTrip()`** (Z. 219 `savedSnapshot = snapshot(...)`): Aufruf um den neuen Parameter erweitert, damit der initiale Snapshot den geladenen Trip-Wert enthält (kein `isDirty=true` direkt nach dem Laden).

4. **`handleDiscard()`** (Z. 355-373): `officialAlertsEnabled` wird aus dem geparsten `savedSnapshot` wiederhergestellt (`snap.officialAlertsEnabled ?? true`), im Catch-Fallback aus `trip.official_alerts_enabled ?? true` — Konsistenz-Vollständigkeit für den Code-Pfad (bekanntes Muster aus Issue #774, dort für `reportConfig` bereits gelöst). **Korrektur nach TDD-RED-Vorbereitung:** Die zugehörige UI (Pille „Ungespeicherte Änderungen" + „Verwerfen"-Button, Z. 473-476) rendert nur bei `!saveController` — auf der Live-Route (`/trips/[id]/+page.svelte:22/285`) wird `saveController` jedoch **immer** gesetzt (`tripSaveCtl = createSaveStatus()`), d. h. dieser UI-Pfad ist auf der echten Seite unerreichbarer Alt-Code. AC-3 testet daher NICHT „Verwerfen", sondern das tatsächliche Auto-Save-Verhalten (siehe unten).

4b. **`TripTabs.svelte` — `handleValueChange()`** (Z. 108-121): Der bestehende Flush-Guard (`if (activeTab === 'alerts' && value !== 'alerts' && saveController?.hasPending) { await saveController.flush(); }`, eingeführt in Issue #953 für den Alerts-Tab) wird auf den Inhalt-Tab erweitert: `if ((activeTab === 'alerts' || activeTab === 'weather') && value !== activeTab && saveController?.hasPending)`. Begründung: Der neue Schalter im Inhalt-Tab nutzt denselben debounce-basierten Auto-Save (700 ms, `SaveStatus.schedule()`). Ohne diese Erweiterung könnte ein sehr schneller Tab-Wechsel (Inhalt → Alerts, innerhalb des 700-ms-Fensters) dazu führen, dass der frisch gemountete Alerts-Tab kurzzeitig den alten Wert zeigt, weil sein lokaler `$state` nur beim Mount aus der `trip`-Prop initialisiert wird (kein reaktives Nachziehen bei späterem `onTripUpdate`). Diese Lücke existierte in die andere Richtung (Alerts → andere Tabs) bereits nicht, weil sie in #953 bereits geschlossen wurde — jetzt wird sie symmetrisch für den Inhalt-Tab geschlossen.

5. **`handleSave()`** (Z. 394-418, konkret der zweite PUT in Z. 405) und **`scheduleAutoSave()`** (Z. 421-431, konkret Z. 427): Der bereits bestehende zweite PUT-Call wird um das Feld erweitert:
   `await api.put<Trip>(\`/api/trips/${trip.id}\`, { report_config: reportConfig, official_alerts_enabled: officialAlertsEnabled })`
   Es wird **kein** dritter, separater `saveController.schedule()`-Aufruf ergänzt — `SaveStatus` hält nur eine pending Funktion gleichzeitig, ein dritter Call würde die bestehende `reportConfig`-Persistenz-Funktion überschreiben (Race-Risiko).

6. **Markup**: Ein neues Checkbox-Segment wird direkt im Markup-Bereich der `EditReportConfigSection`-Einbindung (Z. 641-649) ergänzt — visuell unmittelbar neben/unter der Card „E-Mail-Inhalt" platziert, mit identischer Optik (gleiche Tailwind-Klassen `text-sm` / `inline-flex items-center gap-2` / `pl-6 text-xs text-muted-foreground`, gleiche `Checkbox`-Komponente aus `$lib/components/ui/checkbox`) wie die 3 bestehenden Content-Bausteine, aber als eigener Block in `WeatherMetricsTab.svelte` (kein Eingriff in `EditReportConfigSection.svelte`). `data-testid="report-show-official-alerts"` (Namensraum konsistent zu `report-show-outlook` etc.). Label: „Amtliche Warnungen" (identisch zum Alerts-Tab, keine neue Formulierung). Beschreibungstext: „Amtliche Wetterwarnungen (z. B. Unwetterwarnung) im E-Mail-Briefing anzeigen."

7. **`{#if !createMode}`-Guard** (Z. 641): Der neue Block wird innerhalb desselben Guards gerendert wie `EditReportConfigSection` — im Create-Modus existiert kein `trip.id` für den PUT, siehe Known Limitations.

## Expected Behavior

- **Input:** Nutzer öffnet Tab „Inhalt" eines bestehenden Trips, klickt die Checkbox „Amtliche Warnungen" an/aus.
- **Output:** Checkbox-Zustand wird sofort (Auto-Save via `saveController`) oder per Button „Speichern" (ohne `saveController`) via `PUT /api/trips/{id}` mit `official_alerts_enabled: <bool>` persistiert; die Server-Antwort (aktualisierter Trip) wird über `onTripUpdate?.(updated)` nach oben propagiert, wodurch der Tab „Alerts" beim nächsten Wechsel denselben Wert zeigt.
- **Side effects:** `isDirty` wird `true` solange nicht gespeichert; ohne `saveController` erscheint die Pille „Ungespeicherte Änderungen" + „Verwerfen"-Button; „Verwerfen" setzt den Wert auf den zuletzt gespeicherten Stand zurück.

## Acceptance Criteria

- **AC-1:** Given ein eingeloggter Nutzer öffnet einen bestehenden Trip im Tab „Inhalt" und der Schalter „Amtliche Warnungen" ist aktuell aktiviert / When der Nutzer die Checkbox deaktiviert und speichert (Button oder Auto-Save-Debounce abwarten), dann die Seite neu lädt und erneut den Tab „Inhalt" öffnet / Then zeigt die Checkbox „Amtliche Warnungen" den Zustand „deaktiviert".
  - Test: Playwright-E2E als eingeloggter Test-Nutzer gegen einen echten `gregor-api`-Prozess (lokaler Preview-Build via Standard-`playwright.config.ts` — Erreichbarkeit auf Staging ist Aufgabe des separaten `staging-validator`/`/e2e-verify`-Gates nach dem Push, nicht dieser Testdatei), echter persistierter Trip, Klick auf `[data-testid="report-show-official-alerts"] input`, `page.reload()`, erneute Prüfung des `checked`-Attributs im DOM — kein API-Response-Mock, kein Dateiinhalts-Check.

- **AC-2:** Given ein eingeloggter Nutzer ändert den Schalter „Amtliche Warnungen" im Tab „Inhalt" und speichert / When der Nutzer anschließend zum Tab „Alerts" desselben Trips wechselt (Tab-Klick, kein `goto`) / Then zeigt der dortige Schalter „Amtliche Warnungen" denselben, gerade geänderten Zustand — als Beweis, dass beide UI-Einstiegspunkte dasselbe Backend-Feld über `onTripUpdate` synchron halten.
  - Test: Playwright-E2E (gleiche Testumgebung wie AC-1), Toggle im Inhalt-Tab, Warten auf die PUT-Antwort, Tab-Klick auf „Alerts" (kein Reload), Lesen des `ChannelToggle`-Zustands im DOM. Und umgekehrt: Änderung im Alerts-Tab zuerst, danach Tab-Wechsel zu „Inhalt" — beide Richtungen werden geprüft.

- **AC-3:** Given ein Nutzer ändert den Schalter „Amtliche Warnungen" im Tab „Inhalt" und wechselt SOFORT (innerhalb des Auto-Save-Debounce-Fensters, ohne zu warten) per echtem Tab-Klick zum Tab „Alerts" / When der Hintergrund-Speichervorgang danach abschließt / Then zeigt der Alerts-Tab-Schalter zuverlässig den neu gesetzten Wert — keine verlorene oder veraltete Anzeige durch die schnelle Navigation.
  - Test: Playwright-E2E (gleiche Testumgebung wie AC-1), Toggle-Klick im Inhalt-Tab OHNE Wartezeit direkt gefolgt von `page.getByRole('tab', { name: 'Alerts' }).click()`, danach Prüfung des `checked`-Zustands im Alerts-Tab-DOM UND per `GET /api/trips/{id}` (beweist: kein Datenverlust, kein Stale-Render) — kein Mock, kein Dateiinhalts-Check.

- **AC-4:** Given der bestehende Schalter im Tab „Alerts" (Referenz-Implementierung, Regression-Schutz) / When der Nutzer den Trip nach Fertigstellung dieses Fixes öffnet / Then existiert der Alerts-Tab-Schalter unverändert weiter und funktioniert eigenständig (kein Entfernen, keine Verhaltensänderung an `AlertsTab.svelte`).
  - Test: Playwright-E2E (gleiche Testumgebung wie AC-1), Navigation zu Tab „Alerts", Sichtbarkeits- und Funktionsprüfung des dortigen `ChannelToggle` „Amtliche Warnungen" (Klick, Speichern, Reload, Zustand geprüft) — beweist, dass der bestehende Pfad durch die Ergänzung nicht beschädigt wurde.

## Known Limitations

- Der Schalter erscheint **nicht** im Create-Wizard (`TripNewEditor.svelte`) — dort existiert noch kein `trip.id` für den PUT-Aufruf. Der Backend-Default `true` greift beim POST automatisch; der Nutzer justiert den Wert danach im Tab „Inhalt" des fertig angelegten Trips.
- Der bestehende Schalter im Tab „Alerts" bleibt bewusst **zusätzlich** erhalten (keine Entfernung, keine Migration) — beide Orte bilden denselben Datenwert für unterschiedliche Nutzerkontexte ab („Sofort-Alarm bei amtlicher Warnung" vs. „amtliche Warnung im Briefing zeigen"). Diese Redundanz ist gewollt, kein technischer Kompromiss.
- `EditReportConfigSection.svelte`, `TripEditView.svelte` und `BriefingsTab.svelte` werden in diesem Fix nicht angefasst. `TripEditView.svelte`/`BriefingsTab.svelte` sind über keine aktive Route erreichbar (toter Code, Nebenbefund aus Phase 2) — Bereinigung erfordert ein separates Folge-Issue.
- Bei theoretisch gleichzeitig geöffneten Tabs „Inhalt" und „Alerts" in zwei Browser-Fenstern könnte ein Auto-Save-Race auftreten (letzter Schreiber gewinnt) — in der Praxis nicht relevant, da ein Nutzer immer nur einen Tab aktiv bedient; kein zusätzlicher Locking-Mechanismus in dieser Spec vorgesehen.
- Die Pille „Ungespeicherte Änderungen" + „Verwerfen"-Button (`weather-metrics-dirty-pill`/`weather-metrics-discard`) existieren im Code, sind auf der Live-Route aber unerreichbar, da dort immer ein `saveController` gesetzt ist (Auto-Save-Modus). Dieser Alt-Code-Pfad wird durch diese Spec nicht getestet und nicht bereinigt (kein Bug-Bezug, separates Aufräum-Thema).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Es wird kein neues Architekturmuster, kein neuer Speicherpfad und kein neuer Endpunkt eingeführt. Der Fix nutzt ausschließlich bereits bestehende, produktiv verdrahtete Bausteine (Backend-Feld, PUT-Endpoint, Auto-Save-Controller-Pattern) und ergänzt lediglich einen zweiten UI-Einstiegspunkt nach demselben Muster, das im selben Tab bereits für `reportConfig` existiert. Kein architektur-relevanter Entscheidungsbedarf.

## Test Plan

### Automated Tests (TDD RED)

- [ ] Test 1: GIVEN aktivierter Schalter im Inhalt-Tab WHEN deaktiviert + gespeichert + Reload THEN Checkbox zeigt „deaktiviert" (AC-1)
- [ ] Test 2: GIVEN Änderung im Inhalt-Tab WHEN Wechsel zum Alerts-Tab THEN identischer Zustand sichtbar, und umgekehrt (AC-2)
- [ ] Test 3: GIVEN Toggle-Änderung im Inhalt-Tab WHEN sofortiger Tab-Wechsel zu Alerts (innerhalb Debounce-Fenster) THEN Alerts-Tab zeigt korrekten neuen Wert, kein Datenverlust (AC-3)
- [ ] Test 4: GIVEN bestehender Alerts-Tab-Schalter WHEN Fix ausgerollt ist THEN Alerts-Tab-Schalter weiterhin funktional (Regression, AC-4)

Alle Tests laufen als echte Playwright-E2E-Läufe mit echtem, persistiertem Trip gegen einen echten `gregor-api`-Prozess — kein Mock, kein reiner Dateiinhalts-Check (CLAUDE.md-Pflicht).

**Korrektur nach Adversary-Finding F001 (2 Runden):** Umgesetzt wurde EINE Testdatei (`frontend/e2e/issue-1117-official-alerts-content-tab.spec.ts`) über die Standard-`playwright.config.ts` (lokaler Preview-Build, Login via `helpers.ts::login()`) — nicht die ursprünglich in „Estimated Scope" geplanten 3 Dateien (eigene Staging-Config + Staging-Setup analog #953). Diese Testdatei prüft reales Verhalten gegen einen echten Backend-Prozess; sie ersetzt NICHT die reguläre Staging-Verifikation vor dem Prod-Deploy — diese läuft unverändert über den separaten `staging-validator`-Agenten (`/e2e-verify`, `staging_gate.py`) nach dem Push, wie für jeden Fix in diesem Projekt.

**Korrigierte Begründung (1. Fassung fälschlich #774 als Präzedenzfall für „lokale Konvention" zitiert — `playwright.774.config.ts` ist tatsächlich eine dedizierte Staging-Config, siehe Datei-Kommentar):** Es gibt in diesem Repo keine einheitliche Konvention — manche Testdateien (z.B. `issue-619-mail-elements-ui.spec.ts`) laufen bewusst gegen die Standard-Config (lokaler Preview-Build), andere gegen eigens angelegte Staging-Configs. Für #1117 wurde bewusst die einfachere Standard-Config gewählt, weil kein staging-spezifisches Verhalten (z.B. Live-Bug-Reproduktion wie bei #953) nachgewiesen werden musste — die Funktionalität ist umgebungsunabhängig. Die ACs oben wurden entsprechend präzisiert: sie verlangen keinen Staging-spezifischen Testlauf mehr, sondern einen echten (nicht gemockten) Testlauf gegen einen laufenden Backend-Prozess.

## Changelog

- 2026-07-08: Initial spec created
- 2026-07-08: Nach TDD-RED-Vorbereitung korrigiert (User-Rückfrage beantwortet): AC-3 von unerreichbarem "Verwerfen"-Button auf reales Auto-Save-Race-Szenario umgestellt; `TripTabs.svelte`-Flush-Guard-Erweiterung als zusätzliche notwendige Änderung ergänzt (Affected Files, Estimated Scope)
- 2026-07-08: Adversary-Verdict VERIFIED (Finding F001, MEDIUM, non-blocking). 1. Korrekturversuch: Estimated Scope korrigiert, aber AC-„Test:"-Zeilen fälschlich unverändert gelassen + falscher #774-Präzedenzfall zitiert (playwright.774.config.ts ist tatsächlich Staging-Config). 2. Korrekturversuch: AC-1 bis AC-4 „Test:"-Formulierungen auf tatsächliches Verhalten präzisiert (kein „gegen Staging" mehr, stattdessen „echter Backend-Prozess", Staging-Gate bleibt separater `/e2e-verify`-Schritt), falsches Präzedenzfall-Zitat entfernt. Implementierung selbst in beiden Runden unverändert korrekt.
