# Adversary-Dialog — fix-1895-s2-alarmkarte-rueckbau (#1895 Schritt 2)

Datum 2026-09-21. Pruefer: implementation-validator (unabhaengig). Mutationen nur per `sed -i` mit externer
Sicherungskopie im Scratchpad; nach jedem Rueckbau `diff` gegen die Kopie, am Ende der Arbeitsbaum-Diff vor/nach
dem Lauf byte-identisch (`cmp`). Nichts committet, keine Laeufe gegen Staging.

Testartefakte: `test-baustein-adversary.txt` (29/29), `test-docs-316-adversary.txt` (9 passed),
`test-e2e-local-adversary.txt` (7 passed, lokaler Stack), `/tmp/adversary_test_output.txt`.

### Runde 1 — Ist-Stand nachmessen und Pflicht-Mutationen M1-M4

- [x] Bausteintests nachgemessen (`npm test` mit den drei benannten Dateien): 29 tests, 29 pass, 0 fail, Exit 0.
- [x] `tests/tdd/test_issue_316_docs_cleanup.py`: 9 passed (nur Drift-Waechter, s. AC-9).
- [x] svelte-check nach Lieferung: 36 ERRORS, Fehlerliste (Zeitstempel entfernt, sortiert) zeichengleich zur Baseline `svelte-check-before.txt` (`diff` leer). Keine Fehler in `alert-rules-editor/`.
- [x] **M1** `delta_window: rule.delta_window ?? '6h'` -> `delta_window: '6h'`: 8 von 29 rot. Namentlich: Test 3 "AC-2 expandRules() liefert fuer JEDE Metrik genau eine Aenderungsregel"; Test 4 "Zeitfenster '1h' ... (Schwelle 11)"; 5 "'3h' (Schwelle 18)"; 7 "'12h' (Schwelle 32)"; 8 "'24h' (Schwelle 39)"; 11 "Bestandszeitfenster ueberlebt; 6h gilt nur fuer eine Regel ohne Fenster"; 25 "das Zeitfenster der Regel wird durchgereicht, nicht auf 6h festgenagelt"; 26 "Bestandsregel mit 17/12h behaelt 17 und 12h". Der '6h'-Fall (Test 6) bleibt gruen, wie erwartet (die Konstante erfuellt ihn) — kein Zufallstreffer, jeder rote Fall traegt ein Fenster != 6h.
- [x] **M1b (Zusatz)** Rueckfall entfernt (`delta_window: rule.delta_window`): rot Test 11 (Regel ohne Fenster) und Test 23 (Alt-Regel absolute). Der Rueckfall `'6h'` ist bewacht.
- [x] **M2** `threshold: rule.threshold` -> `threshold: 20`: 9 rot. Namentlich Test 3, 4, 5, 6 ("'6h' ... Schwelle 25" — hier greift die Schwelle, nicht das Fenster), 7, 8, 11, 24 "rule.threshold wird unveraendert durchgereicht (E-3)", 26. Jeder Fall traegt Schwelle != 20.
- [x] **M3** `newDefaultRule()` `threshold: 20` -> `50`: 4 rot: Test 1 "AC-7 newDefaultRule() liefert eine Aenderungsregel", 2 "S2 AC-7 eine neue Regel behaelt 20/6h", 20 "newDefaultRule: liefert AlertRule mit den Vorgabe-Werten", 22 "newDefaultRule: erzeugt keine geteilten Referenzen".
- [x] **M4** `saveEdit()` -> `expandRules(synced, 20, '6h')`: svelte-check meldet **37** ERRORS; Fehlerdiff gegen Baseline = genau eine neue Zeile: `AlertRuleRow.svelte 81:30 "Expected 1 arguments, but got 3."` (TS2554). Sonst nichts veraendert. Rueckbau verifiziert (`diff` gegen Kopie leer).
- [x] Sichtpruefung 1 (`startEdit`) — `AlertRuleRow.svelte:68`: `draft = { ...rule };` ist ein **voller Spread**, kein angehaengtes `delta_window`/`threshold`. Kommentar `:65-67` benennt E-3. Urteil: erfuellt. (Gleiches Muster in `cancelEdit()` `:86`.)
- [x] Sichtpruefung 2 (`saveEdit`) — `AlertRuleRow.svelte:75-78`: `const synced: AlertRule = { ...draft, unit: metricInfo?.unit || draft.unit };` — `synced` besteht **nur** aus `draft` und `unit`, kein drittes Feld; `:81` `onSave(expandRules(synced));`. Urteil: erfuellt. `toggleEnabled` (`:88-91`) reicht `{ ...rule, enabled }` ohne expandRules und ohne Feldueberschreibung.
- [x] **Verdrahtungs-Gegenprobe (Bestaetigung der dokumentierten Restluecke):** `draft = { ...rule, delta_window: '6h' }` (`:68`) UND `unit: ..., delta_window: '6h'` (`:77`) eingebaut: Bausteintests 29/29 gruen, Exit 0, svelte-check weiter 36 ERRORS. **Kein Test, keine Typpruefung faengt das.** Das ist exakt die in Known Limitations ("ZWEI Glieder") benannte Luecke, kein neuer Befund; einziger Waechter ist die Lesekontrolle oben, die bestanden ist. Auch der Browser kann es nicht messen (Bestandsregel nicht erreichbar, `/trips/<id>/edit` = redirect 307, #616).

### Runde 2 — Strukturinvarianten, Browser-Ebene, Mutationen M5/M6

- [x] **AC-8:** Die Namenliste des Diffs gegen die Merge-Base `2116d246` enthaelt nur docs/artifacts, docs/briefings, docs/context, docs/reference, docs/specs, `frontend/e2e/gewitter-absolutregel-gesperrt.spec.ts` und vier Dateien unter `frontend/src/lib/components/alert-rules-editor/`. Kein Treffer unter `internal/`, `src/`, `api/`, `cmd/`, `shared/`, `compare/`.
- [x] **AC-6:** `frontend/e2e/gewitter-absolutregel-gesperrt.spec.ts` existiert unter dem alten Namen (in place geaendert). Zeile 246 `e2e/gewitter-absolutregel-gesperrt.spec.ts` steht in der Ratschen-Datei `ci_e2e_specs.txt` (CI-Ordner); diese Datei ist im Diff seit `2116d246` nicht enthalten (unveraendert).
- [x] **AC-9:** `docs/reference/frontend_components.md:665-696`: "Δ-Schwelle"/"Zeitfenster" kommen nur als Historie der Entfernung (`:672-673`) und als Negation ("Kein Eingabefeld fuer Schwelle oder Zeitfenster", `:686`) vor, nicht als Karteninhalt; Karte = "Metrik · Kanaele · aktiv" (`:683`); `expandRules(rule)` "nimmt genau ein Argument ... unveraendert durchgereicht" (`:690-694`); `AlertRuleRow` steht weiter (`:682`).
- [x] **Scope-Treue Grid:** `.alert-rule-view` hat `grid-template-columns: minmax(140px, 1fr) auto auto auto;` = 4 Tracks (vorher 6); Ueberlauf ab zwei Kanaelen nicht geheilt (kein 5. Track, kein flex-wrap). `Pill`-Import und die Regeln `.threshold`/`.number-input`/`.window-select` entfernt (die vorherige svelte-check-Warnung "Unused CSS .window-select" ist weg).
- [x] **Browser-Ebene (lokaler Stack, alle vier Handgriffe):** `GZ_E2E_API_PROXY_TARGET`/`GZ_API_BASE` = `http://localhost:8191`, leere `GZ_REPO_ENV_FILE`, Ports Go 8191 / Py 8192 (frische Go-Binary aus dem Worktree gebaut, nicht die Wochen alte `/tmp/gregor-server`), `admin.json` vor jedem Zyklus geloescht, CI=1 (Frisch-Build). Spec `gewitter-absolutregel-gesperrt.spec.ts`, Projekt `tests`: **7 passed (30.4s)** — AC-1 (3 Faelle inkl. Schleife ueber alle Metriken), AC-2/AC-7, AC-2/AC-5 Speichern, AC-5 Kanal-Chips. Kein Staging-Zugriff. Lokal gemessen: PASS gemessen, kein `NOT_MEASURABLE_LOCALLY`.
- [x] **M5a** (AC-1, anderes Zahlenfeld mit fremder testid `wert-feld`, `type="number"`, in der Bearbeiten-Karte): 4 failed / 3 passed — rot Fall 2, 3, 4, 5 ueber `toHaveCount`, also ueber die testid-unabhaengige spinbutton-Pruefung. Kanal- und Speichern-Fall gruen. (Ein erster Versuch wurde vom Werkzeug-Filter abgelehnt, die Mutation war nie eingebaut; per `diff` gegen die Kopie als unmutiert belegt, der gruene Lauf zaehlt nicht als Messung. Die Messung oben ist der zweite, gueltige Lauf mit belegter Mutation.)
- [x] **M5b** (Beschriftung "Zeitfenster" als `aria-label`-Element ohne testid): 4 failed / 3 passed; Fehlerlocator woertlich `...alert-rule-edit').first().getByLabel('Zeitfenster')` Expected 0, Received 1 — rot ueber die Beschriftung.
- [x] **M2a** (AC-2, `<span class="threshold">{comparison} {threshold} {unit}</span>` in der Ansichtszeile): 2 failed (Fall 5 "Neue Regel erscheint ohne Wert und ohne Pille", Fall 6 "Speichern erhaelt genau eine Regel ..."), Rest gruen.
- [x] **M2b** (nacktes `<span>Δ</span>` in der Zeile, ohne Pill-Komponente): 2 failed (Fall 5, 6). Die Zusicherung haengt am Text, nicht an `[data-slot="pill"]`.
- [x] **M6a** (AC-5, `{#each activeChannels as ch}` der Bearbeiten-Karte zu `{#each [] as ch}`): 5 failed / 2 passed; rot u.a. **Fall 7 "Kanal-Chips ueberleben den Rueckbau und schalten weiterhin um (AC-5)"** (`toBeVisible` failed). Fall 2-5 ebenfalls rot durch ihre Anti-Vakuum-Zusicherung (`alert-rule-channel-email` sichtbar) — gewollt.
- [x] **M6b** (Kanal-Chips der Ansichtszeile zu `{#each [] as ch}`): 3 failed (Fall 5, 6, 7), Fall 7 ueber `toHaveText` (Zeile zeigt kein "E-Mail").
- [x] **Asymmetrie AC-5 bestaetigt:** `alertChannels.test.ts` importiert nur `./alertChannels.ts` und `$lib/types` (`:14-18`), nicht die `.svelte`. Unter M6a/M6b (reine `.svelte`-Aenderung) ist er strukturell unberuehrt und war in allen Bausteinlaeufen gruen; er ist Waechter der reinen Funktionen, **kein** Beweis fuer die Verdrahtung. Den Beweis liefert allein die E2E-Spec (Fall 7), die unter M6a/M6b rot wird.
- [x] Alle Mutationen zurueckgebaut: `diff` gegen die externen Kopien leer; Status zeigt nur die drei Ausgangs-Modifikationen; Arbeitsbaum-Diff vor und nach dem Lauf **byte-identisch** (`cmp`). Stack gestoppt, `frontend/playwright/.auth/admin.json` entfernt. Abschluss-Lauf der Bausteintests nach Rueckbau: 29/29 gruen.

- [x] **Ratschen-Gegenpruefung (Advisor-Nachlauf):** In `ci_e2e_specs.txt` steht von allen Specs mit `alert-rule-*`/`alert-rules-editor`-Testids (`alert-rules-editor.spec.ts`, `issue-284-alert-rules-restyle.spec.ts`, `issue-494-trip-edit-design.spec.ts`, `issue-687-alert-editor-soll-ist.spec.ts`, `gewitter-absolutregel-gesperrt.spec.ts`) **nur** `gewitter-absolutregel-gesperrt.spec.ts` (Zeile 246). Die einzigen Alert-Treffer der Ratsche (`alert-table-mobile-visibility`, `issue-1117-official-alerts-content-tab`) beruehren `AlertRuleRow` nicht. `fillStep4()` (`helpers.ts:299`, nutzt `alert-rule-threshold` in `:352`) hat null Aufrufer. Im `frontend/src` referenzieren nur `alert-rules-editor/`-Dateien `expandRules`/`AlertRuleRow` (AlertRulesEditor.svelte ruft `expandRules` nicht selbst). Damit ist kein weiterer geratschter Test von den entfallenen Elementen betroffen: AC-6 haelt.

### Befunde

Finding F001 — INFO/LOW (kein Blocker, von der Spec als Known Limitation akzeptiert)
  Category: edge_case
  Code reference: frontend/src/lib/components/alert-rules-editor/AlertRuleRow.svelte:68 und :75-78
  Description: `startEdit()`/`saveEdit()` koennen ein festes `delta_window: '6h'` einschleusen (typkorrekt); nachgewiesen: Bausteintests 29/29 gruen, svelte-check 36. Die Zusicherung "Bestandsfenster ueberlebt das Speichern" ist an ihrer Wirkstelle (Zusammenbau in der Komponente) nicht automatisch bewacht, nur auf `expandRules()`-Ebene.
  Spec requirement: AC-3 / Known Limitations "Restrisiko Verdrahtung — ZWEI Glieder"
  Conflict: keiner — die Spec benennt die Luecke, begruendet die Unmoeglichkeit einer Browser-Strecke (#616) und schreibt die Lesekontrolle vor; diese ist bestanden.
  Remediation: keine in dieser Lieferung; bei kuenftigen Aenderungen an `AlertRuleRow.svelte` beide Zeilen erneut lesen.

Finding F002 — LOW
  Category: edge_case
  Code reference: frontend/e2e/gewitter-absolutregel-gesperrt.spec.ts:149
  Description: Die Spec scoped ausschliesslich auf den `.tn-mobile`-Baum (Kommentar `:148`: der Editor ist im `.tn-desktop`- und im `.tn-mobile`-Baum gemountet). Der zweite Mount wird nicht gemessen. Beide rendern dieselbe Komponente `AlertRuleRow`, die Luecke ist praktisch gering und stammt aus Schritt 1.
  Spec requirement: AC-1 / AC-2 (Reiter "Alerts" auf `/trips/new`)
  Conflict: keiner nachweisbar.
  Remediation: Sammel-Eintrag #1199 (LOW).

Finding F003 — LOW
  Category: anti_pattern
  Code reference: docs/reference/frontend_components.md:3
  Description: Die `**Updated:**`-Kopfzeile nennt weiter nur "Issue #1895 — Alert-Rules-Editor kennt nur noch den Aenderungs-Modus" und erwaehnt Schritt 2 nicht; der Abschnitt selbst (`:665-696`) ist korrekt nachgezogen.
  Spec requirement: AC-9 (Abschnitt "Alert-Rules-Editor")
  Conflict: keiner (AC-9 bezieht sich auf den Abschnitt).
  Remediation: Sammel-Eintrag #1199.

### Confirmations

- AC-1 CONFIRMED — `AlertRuleRow.svelte:105-131` (Bearbeiten-Karte ohne Zahlenfeld); E2E 7/7 lokal, M5a/M5b rot.
- AC-2 CONFIRMED — `AlertRuleRow.svelte:152-158` (Label, Kanal-Chips, Checkbox; kein `.threshold`, keine Pille); M2a/M2b rot.
- AC-3 CONFIRMED — `alertRuleDefaults.ts:60-71` (`threshold: rule.threshold`, `delta_window: rule.delta_window ?? '6h'`); M1/M1b/M2 rot mit benannten Faellen.
- AC-4 CONFIRMED — `AlertRuleRow.svelte:81` ein Argument; 36 == Baseline, Listen identisch; M4 = 37 mit TS2554-Text.
- AC-5 CONFIRMED — `AlertRuleRow.svelte:112-119`; E2E Fall 7 und Speichern-Fall gruen; M6a/M6b rot; `alertChannels.test.ts` bleibt gruen (Asymmetrie bestaetigt).
- AC-6 CONFIRMED — Datei nicht umbenannt, Ratschen-Zeile 246 steht, Ratschen-Datei nicht im Diff; die Gegenproben M5/M2/M6 liefen gegen genau diese Datei.
- AC-7 CONFIRMED — `alertRuleDefaults.ts:18-19` (`threshold: 20`, `delta_window: '6h'`); M3 rot (4 Faelle).
- AC-8 CONFIRMED — Diff-Namenliste ohne verbotene Pfade.
- AC-9 CONFIRMED — `docs/reference/frontend_components.md:665-696`; `test_issue_316_docs_cleanup.py` 9 passed (nur Zusatzwaechter).

## Verdict

**VERIFIED**

Tests: Bausteine 29/29, Docs-Drift 9/9, lokale E2E-Spec 7/7 (Browser-Ebene lokal gemessen, kein Staging). Mutationen: M1-M4 (Pflicht) plus M1b, M2a, M2b, M5a, M5b, M6a, M6b, alle rot mit benannten Testfaellen; die einzige unbewachte Verfaelschung (Verdrahtung in `startEdit`/`saveEdit`) ist die von der Spec ausdruecklich akzeptierte Restluecke und per Sichtpruefung als sauber belegt. Findings: 0 blockierend (F001 INFO, F002/F003 LOW -> #1199).
