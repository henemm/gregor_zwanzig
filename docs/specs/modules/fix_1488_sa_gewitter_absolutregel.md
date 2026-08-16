---
entity_id: fix_1488_sa_gewitter_absolutregel
type: bugfix
created: 2026-08-16
updated: 2026-08-16
status: draft
version: "1.0"
tags: [gewitter, alarm-regeln, trip-new, frontend]
---

# #1488 Scheibe A — Absolut-Modus für Gewitter-Alarmregeln entfernen

## Approval

- [ ] Approved

## Purpose

Beim Anlegen einer Tour (`/trips/new` → Alarmregeln) kann ein Nutzer für die Metrik
„Gewitter" eine Regel im Modus „Absolut" mit Schwelle „MITTEL"/„HOCH" anlegen. Diese
Einstellung wird gespeichert, aber vom Alarm-Dienst **nie ausgewertet** — für Gewitter
zählt ausschließlich die Empfindlichkeitsstufe (`?tab=alarme`). Die Bedienfläche
verspricht also eine Wirkung, die es nicht gibt, und wäre zusätzlich falsch beschriftet.

Scheibe A schließt das bereits vorhandene Guard-Loch (`DELTA_ONLY_METRICS` kennt
`thunder_level` schon, greift aber nur im Modus „Beides", nicht im Modus „Absolut")
und entfernt die dazugehörige Bedienfläche und die veraltete Wortquelle. Bestandsdaten
bleiben unangetastet — sie tun heute nichts und sollen weiterhin nichts tun.

PO-Entscheidung (2026-08-16): **entfernen statt umbenennen.**

## Source

- **File:** `frontend/src/lib/components/alert-rules-editor/alertRuleDefaults.ts`
- **Identifier:** `function expandRules()`

> Schicht: **Frontend / User-UI** (`frontend/src/lib/components/...`, SvelteKit,
> produktive Oberfläche auf `/trips/new`). Kein Go- oder Python-Code betroffen —
> Scheibe A ändert ausschließlich Frontend-Dateien.

## Estimated Scope

- **LoC:** ~215–250 (touched lines, s. Tabelle unten) — **eng am Limit, s. „Offene Punkte"**
- **Files:** 8 (6 geändert, 1 gelöschter Testblock in einer Bestandsdatei, 1 neue Datei)
- **Effort:** medium (Fix selbst klein, Browser-Nachweis dominiert)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `DELTA_ONLY_METRICS` (`alertRuleDefaults.ts:46-51`) | Konstante | bereits vorhandene Guard-Liste, wird um den `absolute`-Zweig ergänzt |
| `ModeCard.svelte` | Komponente | rendert die drei Modus-Karten; bekommt hier keine eigene Logik — die Sperre sitzt im Aufrufer `AlertRuleRow.svelte` |
| `AlertRulesEditor.svelte` → `AlertRuleRow.svelte` | Komponente | einziger produktiver Konsument von `expandRules()` und `thunderLevelLabel()` im erreichbaren Code |
| `AlertsPreviewCard.svelte` (tot, s. u.) | Komponente | zweiter, aber unerreichbarer Konsument von `thunderLevelLabel()` — durch die Löschung der Funktion **erzwungen** mitgezogen (sonst bricht `svelte-check`) |
| ADR-0043 | Architektur-Entscheidung | Empfindlichkeitsstufe ist der einzige Alarm-Regler — diese Scheibe vollzieht das für Gewitter in der Bedienfläche nach, ohne ADR-0043 selbst zu ändern |

## Scope

### Affected Files

| File | Change Type | ~LoC (touched) | Warum |
|------|-------------|----------------|-------|
| `frontend/src/lib/components/alert-rules-editor/alertRuleDefaults.ts` | MODIFY | +10 | Guard im `mode==='absolute'`-Zweig, analog zum bestehenden `both`-Zweig |
| `frontend/src/lib/components/alert-rules-editor/alertRuleDefaults.test.ts` | MODIFY | +24 | 2 neue RED→GREEN-Tests für den geschlossenen Guard |
| `frontend/src/lib/components/alert-rules-editor/AlertRuleRow.svelte` | MODIFY | ~23 | Thunder-Sonderfall im Threshold-Feld entfernen, „Absolut"-ModeCard für `DELTA_ONLY_METRICS` ausblenden, Editmodus-Guard beim Metrik-Wechsel/Altregel-Öffnen, `valueText` vereinfacht |
| `frontend/src/lib/utils/alertMetricLabels.ts` | MODIFY | -9 | `thunderLevelLabel()` ersatzlos gelöscht |
| `frontend/src/lib/utils/alertMetricLabels.test.ts` | MODIFY | -11 | die 3 Tests, die den falschen Zustand zementierten, gelöscht |
| `frontend/src/lib/components/trip-detail/AlertsPreviewCard.svelte` | MODIFY (erzwungen) | -2 | einziger zweiter Aufrufer von `thunderLevelLabel()` — Spezialfall entfernt, fällt auf den generischen Label-Pfad zurück. **Keine** weitere Bereinigung dieser toten Datei (s. Abgrenzung, Scheibe A2) |
| `frontend/e2e/alert-rules-editor.spec.ts` | MODIFY | -38 | AC-10 (Zeilen 292–329) gelöscht — kodiert exakt das entfernte Verhalten (Select mit MITTEL/HOCH). Rest der Datei (20 weitere Tests gegen die tote Route `/trips/[id]/edit`) bleibt unangetastet — eigenständiges Aufräumen außerhalb dieser Scheibe (s. Abgrenzung) |
| `frontend/e2e/fix-1488-gewitter-absolutregel-gesperrt.spec.ts` | CREATE | ~100 | Pflicht-Browser-Nachweis (PO-Vorgabe), s. Testplan — **regulärer CI-Spec, kein `.staging.spec.ts`** |
| `.github/ci_e2e_specs.txt` | MODIFY | +1 | Aufnahme des neuen Specs in die CI-Positivliste, damit der Nachweis dauerhaft automatisch läuft |

### Estimated Changes

- Files: 9
- LoC: ca. +135 / −114 (touched ≈ 249 von 250 — **siehe „Offene Punkte"**)

## Implementation Details

**1. Guard in `expandRules()` schließen** (analog Zeile 77-82, bereits vorhanden für `mode==='both'`):

```ts
if (mode === 'absolute') {
	if (DELTA_ONLY_METRICS.has(rule.metric)) {
		// #1488 Scheibe A: dieselbe Behandlung wie im 'both'-Zweig — eine
		// Delta-only-Metrik darf nie als kind='absolute' persistiert werden.
		const { pair_id: _pid, ...rest } = rule;
		return [{ ...rest, kind: 'delta', threshold: deltaThreshold, delta_window: deltaWindow }];
	}
	const { pair_id: _pid, delta_window: _dw, ...rest } = rule;
	return [{ ...rest, kind: 'absolute', threshold: absThreshold }];
}
```

**2. `AlertRuleRow.svelte`:**

- Thunder-Sonderfall im Threshold-Feld (Zeilen 172-180, `<option value={1.0}>MITTEL</option>` etc.)
  ersatzlos entfernen — das Feld fällt für `thunder_level` auf die normale
  `editMode`-Kette (`both`/`delta`/`absolute`) zurück.
- „Absolut"-ModeCard (Zeilen 140-143) in `{#if !DELTA_ONLY_METRICS.has(draft.metric)}`
  einpacken — für Delta-only-Metriken bleiben nur „Änderung" und „Beides" wählbar.
- Neuer Guard, weil `editMode` sowohl beim Metrik-Wechsel im Select als auch beim
  Öffnen einer Altregel mit `kind='absolute'` (`startEdit()`) auf `'absolute'`
  hängen bleiben könnte, obwohl die zugehörige Karte nicht mehr existiert:

```ts
$effect(() => {
	if (editing && DELTA_ONLY_METRICS.has(draft.metric) && editMode === 'absolute') {
		editMode = 'delta';
	}
});
```

- `valueText` verliert den Thunder-Sonderfall (Zeilen 55-59 → 1 Zeile):
  `let valueText = $derived(\`${rule.threshold} ${info?.unit ?? ''}\`.trim());`
  Für eine bestehende Altregel zeigt der View-Modus damit z. B. „≥ 1" statt der
  falschen Wörter — ehrlich, auch wenn (noch) kein Stufenwort. Live erreichbar ist
  das ohnehin nicht (s. „Was darf sich NICHT ändern").

**3. `alertMetricLabels.ts`:** `thunderLevelLabel()` (Zeilen 54-62) komplett löschen.

**4. `AlertsPreviewCard.svelte` (erzwungene Mini-Änderung, KEINE Vollsanierung):**
Zeile 29 `if (key === 'thunder_level') return \`Gewitter ${thunderLevelLabel(...)}\`;`
entfernen — die Funktion fällt sonst auf einen nicht mehr existierenden Import.
`metricLabel()` nutzt danach für alle Metriken denselben generischen Pfad
(Zeilen 30-31). Die Datei bleibt ansonsten unverändert und weiterhin tot
(kein Importer außer dem Barrel-Export, s. Abgrenzung Scheibe A2).

## Expected Behavior

- **Input:** Nutzer öffnet `/trips/new`, navigiert zu Alarmregeln, wählt/bearbeitet
  eine Regel mit Metrik „Gewitter".
- **Output:** Modus-Auswahl zeigt nur „Änderung" und „Beides" (Δ-Rückfall), keine
  „Absolut"-Karte, kein MITTEL/HOCH-Select. Für alle anderen Metriken (z. B. Böen)
  ändert sich nichts.
- **Side effects:** keine — es wird nichts migriert, nichts automatisch umgeschrieben,
  kein Backend-Code berührt.

## Acceptance Criteria

- **AC-1:** Given ein Nutzer legt einen neuen Trip an und öffnet im Bereich
  „Alarmregeln" eine Regel zur Metrik „Gewitter" im Bearbeiten-Modus, When er sich
  die Modus-Auswahl ansieht, Then wird ihm dort keine „Absolut"-Karte mehr angeboten
  und der Schwellwert-Select mit den Optionen „MITTEL"/„HOCH" existiert nicht mehr im DOM.
  - Test: `frontend/e2e/fix-1488-gewitter-absolutregel-gesperrt.spec.ts`,
    Testfall „Gewitter: keine Absolut-Karte, kein MITTEL/HOCH-Select" (echter Browser
    im CI-`e2e`-Job, `/trips/new`).

- **AC-2:** Given derselbe Bereich, When der Nutzer stattdessen die Metrik „Böen"
  bearbeitet, Then wird ihm die „Absolut"-Karte weiterhin angeboten und bleibt
  anklickbar — die Sperre gilt ausschließlich für Delta-only-Metriken, nicht
  metrikübergreifend.
  - Test: derselbe Testfall wie AC-1, Positivkontrolle im selben Testlauf (sonst wäre
    „nicht gefunden" wertlos, s. PO-Vorgabe).

- **AC-3:** Given eine Regel wird dennoch mit Metrik „Gewitter" und Modus „Absolut"
  angefordert (z. B. per direktem API-Aufruf oder aus Alt-Code), When die Regel intern
  über `expandRules()` expandiert wird, Then erzeugt das System keine Regel mit
  `kind='absolute'` für Gewitter, sondern fällt auf eine Δ-Regel zurück — analog zum
  bereits bestehenden Verhalten im Modus „Beides".
  - Test: `frontend/src/lib/components/alert-rules-editor/alertRuleDefaults.test.ts`,
    neuer Fall `expandRules > mode=absolute + thunder_level → fällt auf delta zurück
    (Bugfix #1488 AC-3)`.

- **AC-4:** ~~Bestandsregel überlebt PUT→GET unverändert~~ — **gestrichen (PO 2026-08-16)**,
  weil in der RED-Phase gemessen wurde, dass die Given-Bedingung nicht herstellbar ist:
  Der Go-Store normalisiert `alert_rules` bei **jedem** Laden und Speichern
  (`internal/store/trip.go:206` und `:238` → `model.SyncAlertRules`;
  `internal/model/trip.go:383` setzt hart `rule.Kind = AlertRuleKindDelta`, Regeln zu
  nicht-aktiven Metriken entfallen ganz). Einen Bestandstrip mit `kind='absolute'` gibt
  es im Go-Pfad nicht — weder über die API noch per Datei auf Platte.
  Ein Test dafür würde nicht Scheibe A prüfen, sondern fremdes Serververhalten
  festschreiben, und wäre in RED grün. Beleg:
  `docs/artifacts/fix-1488-gewitterstufen/red_ac4_go_store_normalizes_alert_rules.txt`.
  Der Befund selbst ist in [#1895](https://github.com/henemm/gregor_zwanzig/issues/1895)
  nachgetragen. Die Zusicherung „Scheibe A fügt keinen Umschreibe-Code hinzu" bleibt als
  Unterlassung unter „Was darf sich NICHT ändern" bestehen — dort, wo sie hingehört.
  **Der zugehörige Testfall ist in Phase 6 aus
  `frontend/e2e/gewitter-absolutregel-gesperrt.spec.ts` zu entfernen.**

- **AC-5:** Given die Empfindlichkeitsstufen-Fläche für Gewitter (`?tab=alarme`),
  When Scheibe A umgesetzt ist, Then zeigt diese Fläche unverändert weiterhin die
  vier Stufen (Aus/Entspannt/Standard/Sensibel) — sie ist von dieser Änderung nicht
  betroffen.
  - Test: Regressionsschutz durch Unterlassung (kein Datei aus dieser Fläche wird
    angefasst) + bestehender Test `alarme_tab_alert_metrics_from_catalog.test.ts`
    muss nach der Änderung weiterhin grün laufen (kein neuer Test nötig).

## Abgrenzung — ausdrücklich NICHT in Scheibe A

- **Scheibe A2 (Kandidat, separates Ticket/Sammel-Eintrag):**
  - Vollständige Löschung der toten Dateien `AlertsPreviewCard.svelte` (117 Zeilen)
    und `TripEditView.svelte` (217 Zeilen) samt Barrel-Export (`trip-detail/index.ts:8`)
    und der vier content-check-Tests, die auf `TripEditView.svelte` lesen
    (`bug_596.test.ts`, Teile von `issue_523_suggested_flag_cleanup.test.ts` und
    `issue_503_etappen_waypoints.test.ts`). Der bereits vorhandene Wächtertest
    `deadTripOverviewComponentsRemoved.test.ts` wäre die richtige Stelle, die Liste
    zu erweitern. **Nicht in Scheibe A**, weil nur die in dieser Spec genannte
    Mini-Änderung an `AlertsPreviewCard.svelte` durch das Löschen von
    `thunderLevelLabel()` erzwungen ist — die Vollsanierung ist eigenständige Arbeit
    und hätte das LoC-Budget gesprengt.
  - Lokale Stufenliste in `WeatherMetricsTab.svelte:1629-1634` auf den Backend-Katalog
    umstellen (Vorbild: `CorridorEditor.svelte`).
  - Die drei toten E2E-Dateien, die vollständig auf die tote Route
    `/trips/[id]/edit` zielen (`frontend/e2e/alert-rules-editor.spec.ts` minus AC-10,
    `issue-284-alert-rules-restyle.spec.ts`, `issue-687-alert-editor-soll-ist.spec.ts`)
    — insgesamt ~1200 Zeilen. Scheibe A entfernt nur den einen Test, der das
    entfernte Verhalten kodiert; die Route war schon vor dieser Scheibe tot
    (`bug-274-safe-area-insets.spec.ts`-Kommentar in `.github/ci_e2e_specs.txt:76-78`
    belegt das unabhängig).
- **Scheibe B (schließt #1488):** Mail-Textfassung `_THUNDER_MAP`
  (`⚡MED`/`⚡HIGH` → `⚡mittel`/`⚡hoch`) in `email/helpers.py`, veraltete
  Backend-Kommentare (`weather_change_detection.py:814-816`, `alert_preset.py:75-77`
  u. a.), zieht Renderer-Commit-Gate + Mail-Validatoren nach sich.
- **#1480** (Wächter gegen neue Kopien) — kommt laut PO-Entscheidung nach #1488.
- **Umdeutung/Migration bestehender Regeln** — PO-Entscheidung 2026-08-16: Bestandsdaten
  bleiben unangetastet, keine Migration.

## Was darf sich NICHT ändern

- **Bestandsdaten:** Scheibe A fügt **keinen** Migrations- oder Normalisierungscode für
  gespeicherte Regeln hinzu und ändert die bestehende serverseitige Behandlung nicht.
  ⚠️ Präzisierung nach der Messung (s. gestrichenes AC-4): „unangetastet" wäre falsch —
  der Go-Store normalisiert `alert_rules` schon heute bei jedem Laden und Speichern.
  Die PO-Vorgabe lautet, dass **wir** daran nichts ändern, nicht dass nichts geschieht.
- **Empfindlichkeitsstufen-Fläche** (`?tab=alarme`, `AlarmeTab` →
  `AlertMetricLevelRow`) bleibt vollständig unberührt — kein Datei-Zugriff, kein
  Verhaltensunterschied.
- **Andere Metriken behalten den Absolut-Modus.** Nur die vier Metriken in
  `DELTA_ONLY_METRICS` (`thunder_level`, `temperature_change`, `wind_change`,
  `precipitation_change`) verlieren die „Absolut"-Karte — das war für die anderen
  drei bereits im Modus „Beides" so und wird hier nur auf den Modus „Absolut"
  ausgeweitet (derselbe Guard, keine neue Metrik betroffen als `thunder_level`
  im engeren Sinn des Issues).

## Testwege für den Browser-Nachweis

- **Reachability, laufzeit-bestätigt heute (2026-08-16):** `/trips/new` →
  Alarmregeln benötigt den vollständigen Progressive-Tab-Unlock-Pfad: Name+Datum
  (`trip-new-name-input-mobile`/`-desktop` + `trip-new-date-input`) → je Etappe GPX
  hochladen (`etDone`, schaltet `wegpunkte`+`metriken` frei) → Tab „Wetter-Metriken"
  besuchen (`wtVisited`, schaltet `zeitplan` frei) → Tab „Briefing-Zeitplan" besuchen
  (`ztVisited`, schaltet `alerts` frei) → Tab „Alerts". Bereits als funktionierendes
  Muster vorhanden: `frontend/e2e/issue-776-metrics-toggle.spec.ts::openNewTripZeitplan()`
  (mobile Viewport, `.tn-mobile input[type="file"][accept=".gpx"]`-Schleife,
  `frontend/e2e/fixtures/test-trip.gpx`) — **wiederverwenden/adaptieren**, nicht neu
  erfinden. Der Klick auf „Alerts" ist der einzige zusätzliche Schritt.
- **Kein Trip-Anlegen nötig:** GPX-Upload löst nur den zustandslosen
  `POST /api/gpx/parse` aus (staging-bestätigt, s. `docs/context/fix-1488-gewitterstufen.md`
  „Erreichbarkeit"-Abschnitt) — der Nachweis darf also **ohne** `Speichern`-Klick
  auskommen: keine Testdaten, kein Cleanup nötig für den UI-Testfall.
- **🔴 Regulärer CI-Spec, ausdrücklich KEIN `.staging.spec.ts`.** Ein Staging-Spec läuft
  nur, wenn ihn jemand von Hand startet — er belegt den Fix einmal und bewacht ihn danach
  nie wieder. Genau das ist der Fehlertyp, den dieses Ticket behebt (eine Zusicherung, die
  niemand prüft, driftet still). Der Nachweis gehört deshalb in die automatische Kette.
- **Kosten der Aufnahme, am CI gemessen (nicht geschätzt):** Ein Eintrag in
  `.github/ci_e2e_specs.txt` genügt. Die Ratsche prüft
  `N=$(wc -l < /tmp/e2e-specs.txt); [ "$N" -ge "$E2E_MIN_SPECS" ]`
  (`.github/workflows/ci.yml:299-303`) — also **mindestens**, nicht exakt, entgegen dem
  Kommentar bei `E2E_MIN_SPECS: 45` (`ci.yml:232`), der „EXAKT" behauptet. Die Liste führt
  heute 45 Nicht-Kommentarzeilen; 46 ist grün, eine Anhebung der Konstante ist **nicht
  nötig**. `E2E_MIN_EXECUTED_HAUPT: 224` prüft ebenfalls `>=` — zusätzliche Testfälle
  erhöhen die Zahl und blockieren nicht. Beide Konstanten sollten dennoch mitgezogen
  werden, damit die Ratsche ihren Zweck behält (Empfehlung, kein Blocker).
- **⚠️ Offenes Umsetzungsrisiko:** Das oben genannte Vorbild
  `issue-776-metrics-toggle.spec.ts` steht **nicht** auf der Positivliste — der
  `/trips/new`-Pfad mit GPX-Upload ist im CI-Stack also **unerprobt**. Der Implementierer
  muss belegen, dass er dort trägt (`POST /api/gpx/parse` gegen den lokalen Stack), statt
  es anzunehmen. Trägt er nicht, ist das ein Befund für die Analyse — **nicht** der Anlass,
  auf einen Staging-only-Spec auszuweichen.
- **Aufnahmekriterium Filter B** der Positivliste verlangt 3× hintereinander grün gegen den
  isolierten CI-Stack. Das gehört in den Nachweis der Implementierungsphase.
- **Locators, bereits vorhanden:** `alert-rules-editor-add`, `alert-rule-row`,
  `alert-rule-kebab-trigger`, `alert-rule-edit-btn`, `alert-rule-metric`
  (Select für die Metrik), `mode-card-{absolute|delta|both}` (fehlt/vorhanden =
  die eigentliche Zusicherung). `alert-rule-threshold` verschwindet für
  `thunder_level` komplett — dessen Abwesenheit ist Teil der Zusicherung, nicht
  nur ein Nebenbefund.
- **`frontend/e2e/alert-rules-editor.spec.ts` AC-10:** wird gelöscht, weil sie
  exakt das MITTEL/HOCH-Select-Verhalten prüft, das diese Scheibe entfernt — sie
  lief zwar schon vorher nicht auf CI (nicht auf der Positivliste, tote Route),
  soll aber nicht mit einer nachweislich falschen Zusicherung im Repo stehen bleiben.

## Known Limitations

- Für eine bestehende (unreachable) Gewitter-Altregel im Modus „Absolut" zeigt der
  View-Modus von `AlertRuleRow.svelte` nach dieser Änderung nur noch die nackte
  Zahl (z. B. „≥ 1") statt eines Stufenworts. Das ist kein Rückschritt (vorher war
  das Wort schlicht falsch) und ohnehin nicht live erreichbar — die korrekte
  Wort-Anzeige über den Backend-Katalog ist Scheibe A2/B.
- Die Guard-Erweiterung betrifft alle vier Einträge von `DELTA_ONLY_METRICS`, also neben
  `thunder_level` auch `temperature_change`/`wind_change`/`precipitation_change`. **Gemessen
  und dem PO vorgelegt (2026-08-16): für alle vier ist die Sperre folgenlos** — keine von
  ihnen wertet heute eine absolute Schwelle aus (`_PRESET_TABLE`, `alert_preset.py:47-58`,
  erzeugt für **jede** Zeile `AlertRuleKind.DELTA`; der reale Detektor liest
  `trip.alert_rules` nicht, `trip_alert.py:366-381`). Kein Rückschritt.
- 🔴 **Bewusst in Kauf genommene Ungleichheit (PO-Entscheid „eng", 2026-08-16):** Der Modus
  „Absolut" ist seit #946 für **alle** Metriken nur noch eine Kanal-Auswahl — die dort
  eingetragene Schwelle löst nirgends mehr etwas aus, auch nicht bei `wind_gust`,
  `precipitation_sum`, `temperature_min`/`_max`, `snow_line`. Nach dieser Scheibe
  verschwindet die Absolut-Karte bei Gewitter, bleibt bei Böen aber stehen, obwohl sie
  dort genauso wenig tut. Das ist der Preis dafür, diese Scheibe klein und beweisbar
  folgenlos zu halten. Belege: `tests/tdd/test_issue_816_alert_deviation.py:740-750`
  (Kommentar: „dieser Routing-Pfad wurde abgeschafft, `metric_alert_levels` ist jetzt die
  einzige Quelle"), `tests/tdd/test_issue_638_alerts_redesign.py:479-528`.
  **Aufgeräumt wird das in [#1895](https://github.com/henemm/gregor_zwanzig/issues/1895)**
  (angelegt 2026-08-16) — nicht hier, weil dieselbe Regel heute noch die Kanalzuordnung
  trägt und ihr Rückbau einen eigenen Entwurf braucht.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue
- **Rationale:** Diese Scheibe vollzieht ADR-0043 („Empfindlichkeitsstufe ist der
  einzige Alarm-Regler") für Gewitter in der Bedienfläche nach, ändert ADR-0043
  selbst aber nicht. Kein neues Architekturprinzip, kein neuer Entscheidungsraum.

## Offene Punkte

- **LoC-Budget reicht voraussichtlich nicht.** Die Schätzung liegt bei ~249 von 250
  berührten Zeilen — mit einem bewusst schlanken Browser-Nachweis. Erfahrungswert im
  Projekt: der **Nachweis** kostet regelmäßig mehr als der Eingriff, und der
  GPX-Upload-Pfad ist im CI unerprobt (s. Testwege). Der Eingriff selbst ist klein
  (~40 Zeilen); alles darüber ist Beweisführung, die nicht gekürzt werden darf —
  Browser-Nachweis und Guard-Tests sind beide PO-Pflichtvorgaben.
  **Empfehlung an den PO: das Limit vorab auf 400 anheben**
  (`workflow.py set-field loc_limit_override 400`), statt mitten in der Umsetzung
  zwischen Budget und Beweis wählen zu müssen. Ohne diese Anhebung ist mit einem
  Abbruch am Limit zu rechnen.

## Changelog

- 2026-08-16: Initial spec created (spec-writer, Workflow `fix-1488-gewitterstufen`)
