---
entity_id: issue_1256_compare_ui_rewire
type: feature
created: 2026-07-13
updated: 2026-07-13
status: draft
version: "1.2"
tags: [compare, ui-fidelity, design-handoff-4, epic-1230, frontend]
workflow: feat-1256-compare-ui-rewire
---

<!-- Issue #1256 (PO-Auftrag 2026-07-13). Kanonische Quelle: JSX in
     Handoff-4-Zip (claude-code-handoff/current/jsx/ + gregor-zwanzig-mobile/
     project/) FÜR DIE OPTIK, plus zwei sich gegenseitig bestätigende
     Verdrahtungs-Quellen FÜR NAVIGATION/LEBENSZYKLUS: der verdrahtete
     Klick-Prototyp "Gregor 20 - Ortsvergleich Fluss.html" (Zeilen 69-127)
     und die kanonische IA-Spec `body-20-canonical-ia-navigation.md`
     (PO-Korrektur 2026-07-13, s. Changelog). Bewusst NICHT-Quelle: alte
     Soll-PNGs mit Ranking/Signal, `nav-map.jsx` (stale Wizard-Edit-Aussage),
     `SOLL-COVERAGE.md` (kennt Compare-Editor/Korridor-Screens nicht),
     `MOCK_COMPARE_ROWS`/`MOCK_COMPARE_PRESETS` in `mock-locations.jsx`
     (rank/score-Reste). Zusätzlich gilt die geschäftsweite Invariante
     „Trip/Ortsvergleich-Code-Teilung" (CLAUDE.md, PO-Vorgabe) als bindende
     Prüfgröße für jede neue Komponente dieser Spec.
     Programm-Spec über 9 Scheiben (Muster #1231/#1250, eine Spec, Scheiben-
     Workflows). Kern-Erkenntnis der Spec-Phase: die FE-Struktur ist bereits
     zu einem erheblichen Teil deckungsgleich zur JSX/zum Fluss (Routen, 6
     Tabs, Progressive Editor, Smart-Import, Kachel-Grid, Create→Detail-
     Redirect existieren bereits) — mehrere Scheiben sind daher
     Fidelity-Verifikation statt Neubau. Die substantielle Struktur-Lücke
     (Inline-Edit im Hub, Scheiben 6/7) wird bewusst durch KONSUM der
     bereits geteilten Trip/Compare-Organismen (`CorridorEditor`,
     `VersandTab`) geschlossen, nicht durch neue Bespoke-Formulare. -->

# Issue 1256 — Orts-Vergleich-UI 1:1 auf Design-Handoff-4

## Approval

- [ ] Approved — wartet auf PO-Freigabe (getipptes „go")

## Purpose

Die drei Orts-Vergleich-Screens (Liste, Hub mit 6 Tabs, Editor create/edit)
inklusive Mobile-Varianten werden Feld für Feld und Klickpfad für
Klickpfad auf den aktuellen Design-Handoff-4-Stand gebracht — Optik nach
der JSX, Navigation/Verdrahtung nach zwei sich gegenseitig bestätigenden
Quellen (`Gregor 20 - Ortsvergleich Fluss.html` + `body-20-canonical-ia-
navigation.md`). Kein Neubau — die Analyse-Phase hat sieben optische und
vier navigatorische Abweichungen identifiziert, von denen mehrere bereits
im laufenden Code korrekt implementiert sind (Fidelity-Verifikation) und
eine substantielle Lücke offen ist: der Hub selbst ist Ansehen- UND
Editier-Fläche (Orte/Idealwerte/Versand) — ein separater Edit-Screen
(`/compare/{id}/edit`) ist im Ziel-Endzustand nicht mehr vorgesehen. Diese
Lücke wird — konsistent mit der geschäftsweiten Code-Teilungs-Invariante
zwischen Trip und Ortsvergleich — durch das Einbetten bereits geteilter
Editor-Organismen (`CorridorEditor`, `VersandTab`) geschlossen, nicht durch
neue Compare-eigene Formulare. Jede der 9 Scheiben schließt eine Untermenge
der Abweichungen und ist unabhängig auslieferbar.

## Source

> Schicht-Hinweis (Template-Pflicht): Diese Spec ist **frontend-only**
> (`frontend/src/lib/components/compare/`, `frontend/src/lib/components/shared/`,
> `frontend/src/routes/compare/`). Kein Go-/Python-Backend-Schema-Wechsel;
> Persistenzfelder (`location_ids`, `paused_at`) existieren bereits bzw.
> kommen additiv aus #1250; Inline-Edit-Scheiben (6/7) nutzen ausschließlich
> bestehende `PUT`/`PATCH`-Endpunkte, kein neuer Endpoint.

- **File (Ist-Vermessung, verbindlich):** `docs/context/feat-1256-compare-ui-rewire.md`
  (Soll-JSX-Kondensat + Ist-Kondensat aus der Analyse-Phase 2026-07-13)
- **Identifier (Soll, Optik/JSX):** `ScreenCompareList` (`screen-compare-list.jsx`),
  `ScreenCompareDetail` (`screen-compare-detail.jsx`, 6 Tabs),
  `ScreenCompareEditor` (`screen-compare-editor.jsx`, 5 Tabs + Chassis-Tab
  „Alarme"), `LayoutTab`/`LT_ComparePreview` (`layout-tab.jsx`),
  `CompareTile`/`compareActions`/`CompareKebab` (`molecules.jsx:1009-1185`)
  — alle unter `claude-code-handoff/current/jsx/`; Mobile-Pendants unter
  `gregor-zwanzig-mobile/project/screen-compare-*-mobile.jsx`
- **Identifier (Soll, Verdrahtung/Navigation — Quelle 1, verdrahteter
  Prototyp):** `Gregor 20 - Ortsvergleich Fluss.html:69-127` (Session-
  Scratchpad `handoff4/gregor-zwanzig/project/`) — `CompareFlowApp`.
  Kernaussagen (Kommentar Zeilen 70-77): Lebenszyklus 1:1 wie beim Trip
  (Liste → Detail mit Tabs „Ansehen + Inline-Editieren"; „Neuer Vergleich"
  → Editor create, progressiv → zurück ins Detail), „Kein separater
  Anzeige-/Edit-Screen", Zurück-Navigation voll verdrahtet. `mode="create"`
  wird im Fluss ausschließlich verwendet (Zeilen 96, 105).
- **Identifier (Soll, Verdrahtung/Navigation — Quelle 2, kanonische IA-Spec,
  bestätigt Quelle 1 wörtlich):** `claude-code-handoff/issue-bodies/
  body-20-canonical-ia-navigation.md`, Abschnitt „Ortsvergleich · analoges
  Modell" (Zeilen 71-108) + Constraints C1-C7 (Zeilen 125-135) + AC-
  Checkliste (Zeile 143: „Es existiert **keine** separate Edit-Route mit
  eigener Tab-Leiste"). Reconciliation-Note (Zeilen 102-108): „Derselbe
  Wizard im Edit-Modus (`routes/vergleich/[id]/bearbeiten`)" ist
  **verworfen** — Bearbeiten läuft „exakt wie beim Trip" über die Hub-Tabs;
  ein evtl. vorhandenes `/vergleich/[id]/bearbeiten` leitet auf `?tab=…`
  um. Damit ist der `/edit`-Redirect (Scheibe 9) keine Interpretation mehr,
  sondern wörtliche Design-Vorgabe aus zwei unabhängigen Quellen.
- **NICHT-Quelle (bewusst ausgeschlossen, mit Beleg):**
  - `nav-map.jsx:288` — behauptet noch „Bearbeiten → Wizard (Edit-Modus,
    gleiche Datei)", widerspricht direkt der Reconciliation-Note in
    body-20 — stale, nicht verwenden.
  - `claude-code-handoff/current/soll/SOLL-COVERAGE.md` — referenziert für
    Compare nur `screen-compare-wizard.jsx` (den laut
    `screen-compare-editor.jsx`-Kopfkommentar seit 2026-06-09 abgelösten
    alten Wizard) und kennt weder den Compare-Editor noch die
    Korridor-/Layout-/Versand-Organismen — für diese Spec veraltet.
  - `mock-locations.jsx:26-37` (`MOCK_COMPARE_ROWS`) und `:84+`
    (`MOCK_COMPARE_PRESETS`) — tragen `rank`/`score`-Felder (Ranking-Reste
    aus einem überholten Design-Stand) und widersprechen der Neutralitäts-
    Vorgabe (kein Score, kein Rang) — nicht als Datenmodell-Referenz
    verwenden.
  - Alte Soll-PNGs mit Ranking/Signal (bereits im Kontext-Dokument als
    überholt markiert).
- **Datenmodell-Referenz (Soll, maßgeblich):** `MOCK_COMPARE_SUBS`
  (`mock-locations.jsx:113-215`) — Felder `ideals[] = {metric, ideal,
  weight: hoch|mittel|niedrig}` (Priorität, kein numerischer Score),
  `layout = {email[], telegram[], sms[]}` (Spaltennamen je Kanal),
  `schedule` als fertig formatierter String (kein `briefings[]`-Array, kein
  `rank`/`score`-Feld auf Subscription-Ebene). Mapping auf die App:
  `layout{}` ↔ `display_config.channel_layouts`, `ideals[].weight` ↔
  Corridor-Priorität (`Corridor.prio`, analog #1231).
- **Bestätigung (Mail-Neutralität, peripher):**
  `Gregor 20 - Ortsvergleich Mail.html` (selber Scratchpad-Pfad) rendert
  `CompareEmailV2` (Desktop 680px + iPhone-Mail 380px) explizit ohne Score
  („Kein Score mehr — der User beurteilt die Kriterien selbst") — bestätigt,
  dass die im Kontext-Dokument vermutete Neutralitäts-Grauzone
  (`CompareMatrix`/`HourlyMatrix`) korrekt NICHT die aktuelle Mail-SSoT ist
  (siehe AC-20).
- **Identifier (Ist, FE):** `frontend/src/routes/compare/+page.svelte`,
  `frontend/src/routes/compare/[id]/+page.svelte`,
  `frontend/src/routes/compare/[id]/edit/+page.svelte`,
  `frontend/src/lib/components/compare/CompareTabs.svelte`,
  `frontend/src/lib/components/compare/CompareEditor.svelte`,
  `frontend/src/lib/components/compare/compareWizardState.svelte.ts`,
  `frontend/src/lib/components/shared/layout-tab/LayoutTab.svelte`,
  `frontend/src/lib/components/shared/VersandTab.svelte`,
  `frontend/src/lib/components/shared/corridor-editor/CorridorEditor.svelte`

## Estimated Scope

- **LoC:** ~1200 netto über 9 Scheiben (mehrere Scheiben stark negativ durch
  Totcode-Löschung — siehe Scheibe 1/4; zwei Scheiben sind LoC-Override-
  Kandidaten und benötigen eine Ankündigung beim Start — siehe Scheibe 6/7;
  LoC-Schätzung für 6/7 leicht gesenkt gegenüber der Vor-Version, da
  „geteilte Organismen einbetten" tendenziell weniger Code braucht als
  Bespoke-Formulare)
- **Files:** ~34 (Änderungen + gezielte Löschungen, kein neues Backend)
- **Effort:** medium-high — die Grundstruktur und die meisten
  Navigations-Übergänge existieren bereits (Fidelity-Korrektur), aber das
  Inline-Edit im Hub (Scheiben 6/7) ist echte neue Arbeit, auch wenn sie
  überwiegend aus dem Einbetten bestehender Organismen besteht

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `CLAUDE.md` § „Trip/Ortsvergleich-Code-Teilung" (Zeilen 248-255, frisch committed auf `main`) | Konvention/Invariante | PO-Vorgabe „möglichst viel Code zwischen Trip und Ortsvergleich teilen" als prüfbare Invariante — bindend für JEDE neue Komponente dieser Spec (Constraints, AC-40) |
| Issue #1250 (`docs/specs/modules/issue_1250_briefing_subscription.md`) | Spec | Chassis-Konvergenz; Scheibe 2 dort bringt `paused_at` additiv. Bis dahin nutzen S3/S8 dieser Spec die bestehende `computePauseToggle`-Logik (`subscriptionHelpers.ts`) — kein Doppel-Touch der Pause-Semantik in dieser Spec. |
| Issue #866 | Issue | Vorheriger Editor-Arbeitsstrang (Cross-Link, keine offene Abhängigkeit — Editor-Tabs sind bereits auf dem in dieser Spec vorausgesetzten Stand) |
| `docs/specs/modules/issue_1231_korridor_editor.md` | Spec | `CorridorEditor context="vergleich"` — Editor-Tab „Wertebereiche" konsumiert diesen Organism bereits fertig. Scheibe 6 (Hub-Idealwerte-Inline-Edit) bettet denselben Organism in den Hub ein (Entscheidung s. Implementation Details, löst das frühere Offen-Risiko „bespoke vs. reuse" auf). |
| `docs/specs/modules/layout_tab_vergleich.md` | Spec | Deckt den bereits gebauten, aber noch nicht in den Compare-Editor verdrahteten `LayoutTab`/`LTComparePreview`-Organism ab (#1232 Scheibe 3a) — Scheibe 4 dieser Spec verdrahtet ihn |
| Handoff-4-Zip | Design-Artefakt | `/home/hem/gregor_zwanzig/claude-code-handoff/Gregor-Zwanzig-handoff-4.zip` — kanonische JSX-Quelle für Optik, entpackter Arbeitsstand im Session-Scratchpad `handoff4/` |
| `Gregor 20 - Ortsvergleich Fluss.html` | Design-Artefakt | Kanonische Verdrahtungs-Quelle 1 (Navigation/Lebenszyklus), Zeilen 69-127 |
| `body-20-canonical-ia-navigation.md` | Design-Artefakt | Kanonische Verdrahtungs-Quelle 2 (IA-Spec), bestätigt Quelle 1 wörtlich für Compare (Zeilen 71-108, 125-135, 143) |
| Design-`CLAUDE.md` (`handoff4/gregor-zwanzig/project/CLAUDE.md`, Abschnitt „Orts-Vergleich = stehender Monitor · Briefing-Abo-Chassis", Zeilen 211-299) | Design-Artefakt | Aktuellste konsistente Design-Quelle: Versand identisch Trip (nur Briefing-Uhrzeiten), Editor-Konsolidierung (Layout-/Versand-Tab als geteilte Organismen) bereits in `screen-compare-editor(-mobile).jsx` verdrahtet, `screen-compare-email-v2.jsx` kanonisch, Wertebereiche-Tab beider Editoren ist REIN `CorridorEditor` (notify-Zustellung komplett in `VersandTab`). Vermerkt außerdem explizit Rest-Spuren (`timeWindow`) in mehreren JSX-Dateien als offene Folge-Bereinigung — siehe Umsetzungsregel in Implementation Details. |
| `body-29a-korridor-editor.md`, `body-29b-editor-konsolidierung.md` | Design-Artefakt | Komponenten-API + Migrations-Mapping für `CorridorEditor`/`VersandTab` — Scheibe 6/7 betten exakt diese bereits spezifizierten Organismen ein, bauen nichts Neues |
| Design-Request „Frage 5" (Alarme-Tab-Auflösung, Pfad wird vom PO ergänzt) | Design-Artefakt | Offene Rest-Config ohne neues Zuhause (Cooldown, Ruhezeiten, Radar-Toggle, amtliche-Warnungen-Toggle), sobald der separate Alarme-Tab (#1170) aufgelöst wird — nicht Teil dieser Spec, siehe KL-2 |
| Design-Request „Frage 7" (Pfad wird vom PO ergänzt) | Design-Artefakt | PO kündigt eine separate Ergänzung zur `mode="edit"`-Widerspruchsfrage an — Known Limitation KL-1 verweist darauf, sobald der Pfad existiert |
| `docs/context/feat-1256-compare-ui-rewire.md` | Kontext | Ist-Soll-Abgleich als PO-lesbarer Kommentar in #1256 (PO-Wunsch) — alle Datei:Zeile-Belege dieser Spec referenzieren diesen Abgleich bzw. die eigene Verifikation der Spec-Phase |

## Implementation Details

### Constraints (bindend)

0. **Code-Teilung (CLAUDE.md § „Trip/Ortsvergleich-Code-Teilung", PO-
   Vorgabe, mehrfach bekräftigt zuletzt 2026-07-13):** Editor-Rahmen und
   die Tab-Organismen Wertebereiche/Layout/Versand sind EIN Code mit
   `context="route"|"vergleich"`. Compare-eigen dürfen NUR sein: Orte-Tab,
   transponierte Übersicht (Orte = Spalten), Compare-Mail-Template. Eine
   neue Compare-Komponente, zu der ein Trip-Pendant existiert, ist per
   Default ein Fehler (Ausnahme nur mit dokumentierter Begründung —
   Anti-Pattern-Referenz #1170, `CompareAlarmSection` wurde „analog Trip"
   nachgebaut statt geteilt). Gilt für JEDE Scheibe dieser Spec, geprüft
   über AC-40.
1. Neutralität: kein Score, kein Rang, keine Empfehlung; Idealbereich ist
   ausschließlich eine Markierung (grün im Korridor), keine Bewertung.
2. Versand wie Trip: Morgen-Briefing = heute, Abend-Briefing = morgen,
   editierbare Uhrzeiten — KEIN rollierendes Zeitfenster, KEIN separater
   Versandrhythmus, KEIN Horizont-Feld (PO-Korrektur 2026-07-11, verworfen).
3. Kanäle: Email (alle Spalten), Telegram (max. 8 Spalten inkl. Label),
   SMS (≤140 Zeichen, keine Tabelle).
4. Orte-Reihenfolge = Spaltenreihenfolge im Briefing (kein separates
   Ranking-Konzept).
5. Kein Enddatum-Zwang — der Vergleich läuft „bis auf Weiteres", bis er
   pausiert wird; `CompareEndDateControl` erlaubt optional ein Enddatum.
6. `data-testid`-Bestand bleibt über alle Scheiben erhalten (C6, 17
   Playwright-Specs) — außer bewusst und dokumentiert in Scheibe 9.
7. JSX + Fluss-Prototyp + body-20 sind die Wahrheit — alte Soll-PNGs mit
   Ranking/Signal, `nav-map.jsx` und `SOLL-COVERAGE.md` sind für Compare
   NICHT-Quelle (siehe Source-Sektion); `screen-compare-email.jsx` ist
   DEPRECATED, kanonisch ist `screen-compare-email-v2.jsx`.

### Zielmodell: Detail-Hub = Ansehen + Inline-Editieren (PO-Korrektur 2026-07-13)

Zwei unabhängige, sich gegenseitig bestätigende Design-Quellen (Fluss-
Prototyp + body-20-Reconciliation-Note) gehen der optischen JSX-
Dokumentation von `screen-compare-editor.jsx` vor, wo diese sich
widersprechen. Konkret:

- Der Detail-Hub (`/compare/{id}`) ist zugleich Ansehen- UND
  Editier-Fläche. Die Tabs Orte, Idealwerte und Versand sind **inline
  editierbar** direkt im Hub — realisiert durch das Einbetten der bereits
  geteilten Organismen `CorridorEditor` (Idealwerte) und `VersandTab`
  (Versand), NICHT durch neue Bespoke-Formulare (Code-Teilungs-Invariante,
  Constraint 0). Übersicht, Layout und Vorschau bleiben reine Ansehen-Tabs
  (Layout ist im JSX ein reiner Summary-Tab ohne Editier-Affordanzen;
  Vorschau ist explizit Verifikation, kein Editier-Ort).
- Der heute existierende separate Editor-im-Edit-Modus
  (`/compare/{id}/edit`, `CompareEditor.svelte` mit `mode="edit"`) ist im
  **Ziel-Endzustand nicht mehr vorgesehen** — Fluss-Prototyp instanziiert
  `mode="edit"` nirgends (Zeilen 96, 105 nutzen ausschließlich
  `mode="create"`), body-20 sagt es explizit: „Derselbe Wizard im
  Edit-Modus … ist verworfen. Bearbeiten läuft jetzt — exakt wie beim Trip
  — über die Hub-Tabs."
- Konkrete Ist-Fundstelle des Widerspruchs: `CompareTabs.svelte:205-211`
  (`goToEditVersand()`, Kommentar „kein Inline-Edit, echter Absprung in den
  Editor … JSX hat bewusst keinen In-Hub-Handler") — dieser Kommentar
  bezieht sich auf die *statische Optik-JSX* (dort ist der Edit-Stift ein
  reines Mockup-Element ohne spezifizierten Klick-Handler) und übersieht
  sowohl den Fluss-Prototyp als auch body-20. Analog: die Kanal-Switches im
  Hub-Versand-Tab sind heute hart `disabled={true}`; die „Ort
  hinzufügen"/„Metrik hinzufügen"-Buttons in den Tabs Orte/Idealwerte haben
  aktuell keinen `onclick`-Handler; der Hub-Versand-Bereich ist zudem
  bereits selbst ein Bespoke-Nachbau (`CompareTabs.svelte`-eigene
  `DetailRow`/`Card`-Konstruktion) statt den geteilten `VersandTab` zu
  konsumieren — ein zweiter, unabhängiger Verstoß gegen Constraint 0, der
  durch dieselbe Scheibe 7 behoben wird.

### Datenmodell-Mapping (Mock → App, zur Orientierung bei der 1:1-Umsetzung)

| Mock-Feld (`MOCK_COMPARE_SUBS`) | App-Feld | Hinweis |
|---|---|---|
| `layout = {email[], telegram[], sms[]}` | `display_config.channel_layouts` | Spaltennamen je Kanal, keine neue Persistenzform |
| `ideals[].weight` (`hoch\|mittel\|niedrig`) | Corridor-Priorität (analog `Corridor.prio`, #1231) | Priorität = Reihenfolge in der Übersicht, kein numerischer Score |
| `schedule` (fertig formatierter String) | `presetBriefingTimesLabel(preset)` u. Ä. | Wird serverseitig/clientseitig aus den Briefing-Zeiten abgeleitet, kein eigenes String-Feld in der App |
| — (kein `briefings[]`-Array, kein `rank`/`score`) | — | Bestätigt: kein Ranking-Konzept im Zielmodell, konsistent mit Constraint 1 |

### Umsetzungsregel: Stale-Spuren nicht mitkopieren

Die Design-`CLAUDE.md` vermerkt selbst, dass in mehreren JSX-Dateien
(`screen-compare-email(-v2).jsx`, `screen-compare-detail.jsx`,
`screen-compare-list.jsx`, `mock-locations.jsx`) noch Rest-Spuren des
verworfenen `timeWindow`-Modells (rollierendes Zeitfenster/Versandrhythmus,
PO-Korrektur 2026-07-11) stehen und als „Folge-Bereinigung" offen sind.
Beim 1:1-Übersetzen einer JSX-Struktur in dieser Spec gilt: **diese
bekannten Stale-Spuren werden NICHT mitkopiert** — jede Scheibe, die eine
JSX-Struktur mit `timeWindow`-Bezug antrifft, übersetzt stattdessen nach
Constraint 2 (Versand wie Trip, nur Briefing-Uhrzeiten).

### Staffelung des `/edit`-Übergangs (PO-Vorgabe: Fluss + body-20 gewinnen, gestaffelt)

Um die 17 bestehenden Compare-Playwright-Specs nicht vorzeitig zu brechen
und keinen Big-Bang zu riskieren, wird der Übergang in drei Stufen
vollzogen:

1. **Sofort (Scheibe 2):** Die bereits implementierten Fluss-Übergänge
   (Kachel-Klick → Detail, Create → Aktivieren → Detail-Redirect, Create →
   Abbrechen → Liste, Hub-Zurück → Liste) werden verifiziert und mit
   Regressionstests abgesichert. `/compare/{id}/edit` bleibt als
   **technischer Unterbau** bestehen und unverändert erreichbar.
2. **Scheiben 6/7:** Inline-Edit-Parität wird in den Hub-Tabs Orte,
   Idealwerte und Versand nachgezogen — durch Einbetten der geteilten
   Organismen `CorridorEditor`/`VersandTab` (Idealwerte/Versand) bzw.
   gezieltes Wiring (Orte, compare-eigen). `/compare/{id}/edit` bleibt
   parallel bestehen (kein Bruch für die 17 Specs).
3. **Scheibe 9 (letzte Scheibe, gated):** Erst NACHDEM Scheiben 6/7
   ausgeliefert und vom PO als vollständige Parität bestätigt sind, leitet
   `/compare/{id}/edit` serverseitig auf `/compare/{id}?tab=<passender-tab>`
   um (wörtlich body-20, Zeile 105: „leitet auf `?tab=…`" um) — der
   separate Edit-Screen wird zur reinen Kompat-Route. Diese Scheibe ist
   **PO-bestätigungspflichtig vor Start** (siehe Known Limitations KL-1) —
   sollte die Parität-Prüfung Lücken zeigen, wird Scheibe 9 verschoben
   statt die Route vorzeitig zu kappen.

### Verifizierte Ausgangslage (Spec-Phase, mit Beleg)

Vor der Scheiben-Aufteilung wurden die im Kontext-Dokument als „unklar"
markierten Punkte sowie die vier Fluss-Übergänge in der Spec-Phase am Code
verifiziert:

- `CompareKebab.svelte:27` speist sich ausschließlich aus
  `compareActions(status)` (`subscriptionHelpers.ts:184`) — **dieselbe**
  Funktion wird sowohl von der Liste (`+page.svelte`, über `CompareTile`)
  als auch vom Hub-Header (`compare/[id]/+page.svelte:154`) aufgerufen. Der
  JSX-Soll kennt zwei unterschiedliche Aktionsmengen (`compareActions` für
  die Liste, `CHub_lifecycleActions` nur für den Hub-Header,
  `screen-compare-detail.jsx:27-33`) — das ist die konkrete Ursache für
  „Header-Kebab NUR Lifecycle" aus dem Kontext-Dokument.
- `compareActions('active'|'paused')` liefert im Ist **6** Einträge
  (`subscriptionHelpers.ts:184`, Tests `bug_626_compare_menu_actions.test.ts`,
  `issue_488_compare_tile_atoms.test.ts` erzwingen aktuell genau 6 inkl.
  `archive`), der JSX-Soll (`molecules.jsx:1018-1027`) kennt nur **5** (kein
  `archive` in der Liste — Archivieren gehört laut JSX nur zum Hub-Header).
- `LocationsRail.svelte`, `AutoReportsOverview.svelte`, `AutoReportCard.svelte`
  (alle `compare/`) haben **keinen** produktiven Import außerhalb ihrer
  eigenen Testdateien — verifizierter Totcode, keine „Unklar"-Frage mehr.
- `CompareMatrix.svelte`/`HourlyMatrix.svelte` (Best-Value-Hervorhebung,
  „Top-3 Locations") sind ebenfalls **nicht** in einem produktiven Pfad
  importiert — die im Kontext-Dokument vermutete „Neutralitäts-Grauzone" ist
  Totcode, kein aktiver Verhaltensfix nötig (siehe AC-20), zusätzlich
  bestätigt durch die neutrale `CompareEmailV2` in
  `Gregor 20 - Ortsvergleich Mail.html` als tatsächliche Mail-SSoT.
- `frontend/src/lib/components/shared/layout-tab/LayoutTab.svelte` +
  `LTComparePreview.svelte` sind bereits **fertig gebaut** (1:1 zu
  `layout-tab.jsx`, inkl. grüner Idealbereich-Markierung, „Kein Ranking",
  Telegram-Formel) — aber `CompareEditor.svelte` importiert an allen vier
  Stellen (Zeilen 31, 739-742, 910-913) weiterhin das alte
  `steps/Step4Layout.svelte`. `context="vergleich"` wird im gesamten
  `frontend/src` aktuell **nirgends** verwendet — reines Verdrahtungs-,
  kein Bau-Problem (Scheibe 4).
- `frontend/src/lib/components/shared/VersandTab.svelte` und
  `frontend/src/lib/components/shared/corridor-editor/CorridorEditor.svelte`
  unterstützen bereits ein `activation`-Prop-Pattern (im Editor:
  `<VersandTab context="vergleich" activation={activation}/>`,
  `screen-compare-editor.jsx:375`) — dieselbe Einbettung kann die Hub-
  Aktivierungs-Karte in Scheibe 7 wiederverwenden, statt sie neu zu bauen.
- `Step2Orte.svelte` (Editor-Orte-Tab, 319 LoC) implementiert Smart-Import
  (`POST /api/locations/resolve`, Zeile 90), nummerierte Auswahl
  (Zeile 283) und min-2-Validierung (Zeile 59) bereits — Scheibe 5 ist daher
  überwiegend Verifikation + Feinschliff (Bibliotheks-Gruppierung), kein
  Rebuild. Der Orte-Tab bleibt bewusst compare-eigen (dokumentierte
  Ausnahme von Constraint 0 — Trip hat strukturell keinen Orte-Tab,
  sondern einen Etappen-Tab mit anderer Domäne).
- `CompareTabs.svelte:238-284` (Übersicht-Monitoring-Streifen) und
  `:286-...` (4 SummaryCards + Verifikations-Hinweis) sind bereits fast 1:1
  zu `screen-compare-detail.jsx:134-189` — einzige nachgewiesene Abweichung:
  die „Kanäle"-Stat zeigt `channelCountLabel(N)` (Zahl, z. B. „2 Kanäle")
  statt der Kanal-Namen wie im JSX (`Email · Telegram`,
  `screen-compare-detail.jsx:147-150`).
- **Fluss-Übergänge bereits verdrahtet (Scheibe 2 wird primär Verifikation):**
  Kachel-Klick → `/compare/{id}` (`+page.svelte:90`, `CompareGrid`); Create
  → „Briefing aktivieren" → `goto('/compare/' + created.id)`
  (`compareWizardState.svelte.ts:138`, exakt `activateNew` aus dem Fluss);
  Create → „Abbrechen" → `href="/compare"` (`CompareEditor.svelte:497`);
  Hub-Breadcrumb/Zurück-Pfeil → `/compare` (`compare/[id]/+page.svelte:130,173`).
- **Fluss-Widerspruch bestätigt (substantielle Lücke, Scheiben 6/7):**
  `goToEditVersand()` (`CompareTabs.svelte:205-211`) navigiert bei Klick auf
  den Versand-Edit-Stift zu `/compare/{id}/edit?tab=versand` statt inline zu
  editieren; Kanal-Switches im Hub-Versand-Tab sind `disabled={true}`; „Ort
  hinzufügen" (Orte-Tab) und „Metrik hinzufügen" (Idealwerte-Tab) haben
  keinen `onclick`-Handler; kein Drag-Handle im Orte-Tab; der Hub-Versand-
  Bereich ist selbst ein Bespoke-Nachbau statt einer `VersandTab`-Einbettung.
- `CompareTabs.svelte:510-527` (Vorschau-Tab, `CompareChannelSwitch` +
  Desktop-Inbox/iPhone-Mail-Umschalter) ist bereits 1:1 vorhanden.

### Scheiben-Definition (1–9)

**Scheibe 1 — Liste: Kebab-Bereinigung + Alt-Rest-Entfernung**
- Inhalt: `compareActions()` auf 5 Einträge (kein `archive`) reduzieren;
  drei verifiziert unreferenzierte Alt-Komponenten entfernen.
- Dateien: `frontend/src/lib/components/compare/subscriptionHelpers.ts:184`
  (MODIFY, `archive` aus `active`/`paused`-Zweig entfernen),
  `frontend/src/lib/components/compare/__tests__/bug_626_compare_menu_actions.test.ts`,
  `.../__tests__/issue_488_compare_tile_atoms.test.ts`,
  `.../__tests__/issue_627_send_action.test.ts` (MODIFY, Erwartung 6→5 +
  `archive`-Assertions entfernen), `LocationsRail.svelte`,
  `AutoReportsOverview.svelte`, `AutoReportCard.svelte` (DELETE, nach
  finaler Grep-Verifikation unmittelbar vor dem Commit).
- ~LoC: ~60 netto, stark negativ in Summe (drei gelöschte Dateien >200 LoC
  Totcode).
- Abhängigkeiten: keine — erste Scheibe.

**Scheibe 2 — Fluss-Verdrahtung: Create→Detail-Redirect, Back-Nav, Abbrechen**
- Inhalt: Die vier bereits implementierten Fluss-Übergänge (Kachel-Klick →
  Detail, Create-Aktivieren → Detail-Redirect, Create-Abbrechen → Liste,
  Hub-Zurück → Liste) werden mit echten Playwright-Klickpfad-Tests
  gegen Regression abgesichert (bisher nur indirekt über Einzel-Tests
  abgedeckt); Mobile-Pendants (Fluss.html Zeilen 100-113) werden auf
  dieselbe Parität geprüft; `/compare/{id}/edit` bleibt für diese Scheibe
  unangetastet (Stufe 1 der Staffelung, s. o.).
- Dateien: Neue Playwright-Spec (Pfad wird beim Start festgelegt, Muster
  bestehender `frontend/e2e/playwright/compare-*.spec.ts`), keine
  Komponenten-Änderung erwartet (reiner Regressions-/Verifikations-Fund).
- ~LoC: ~90 (überwiegend Testcode).
- Abhängigkeiten: nach Scheibe 1 (vermeidet Kebab-bedingte Test-Flakes im
  selben Klickpfad).

**Scheibe 3 — Hub: Header-Kebab auf Lifecycle + Kanäle-Stat-Fidelity + Übersicht-Ansehen-Klarstellung**
- Inhalt: Neue `compareLifecycleActions(status)` (analog
  `CHub_lifecycleActions`, `screen-compare-detail.jsx:27-33`: Toggle,
  Archivieren, Löschen; bei `draft` nur Löschen) für den Hub-Header;
  `CompareKebab` bekommt eine `variant`-Prop oder der Aufrufer übergibt die
  Aktionsliste explizit statt intern `compareActions()` zu berechnen.
  Kanäle-Stat zeigt Kanal-Namen statt Kanal-Anzahl. Zusätzlich: der
  Übersicht-Tab wird explizit als reiner Ansehen-Tab dokumentiert/getestet
  (Abgrenzung zu den inline-editierbaren Tabs aus Scheibe 6/7).
- Dateien: `frontend/src/lib/components/compare/subscriptionHelpers.ts`
  (MODIFY, neue Funktion + Test), `frontend/src/lib/components/compare/CompareKebab.svelte`
  (MODIFY, Aktionsliste injizierbar statt hart auf `compareActions`
  verdrahtet), `frontend/src/routes/compare/[id]/+page.svelte:154` (MODIFY,
  Lifecycle-Variante übergeben), `frontend/src/lib/components/compare/CompareTabs.svelte:270-282`
  (MODIFY, Kanal-Namen-Label).
- ~LoC: ~120.
- Abhängigkeiten: nach Scheibe 1 (gleiche Datei `subscriptionHelpers.ts`).

**Scheibe 4 — Editor + Hub: Layout-Tab-Organism verdrahten (konsumiert `LayoutTab`/`LTComparePreview`)**
- Inhalt: `CompareEditor.svelte` (Desktop + Mobile) nutzt
  `<LayoutTab context="vergleich" pickedIds={...}>` mit
  `LTComparePreview`/Order-List-Snippet statt `<Step4Layout/>` — reine
  Konsumierung des bereits fertigen geteilten Organism (Constraint 0), kein
  neuer Code für die Layout-Logik selbst; `steps/Step3Idealwerte.svelte`
  (215 LoC Totcode, Idealwerte laufen vollständig über
  `CorridorEditor context="vergleich"`, #1231) wird entfernt;
  `steps/Step4Layout.svelte` wird nach erfolgreicher Migration entfernt,
  sofern kein anderer Konsument mehr existiert (Grep-Nachweis vor
  Löschung).
- Dateien: `frontend/src/lib/components/compare/CompareEditor.svelte:31,739-742,910-913`
  (MODIFY), `frontend/src/lib/components/shared/layout-tab/LayoutTab.svelte`
  (unverändert, nur konsumiert), `frontend/src/lib/components/compare/steps/Step3Idealwerte.svelte`
  (DELETE, 215 LoC), `frontend/src/lib/components/compare/steps/Step4Layout.svelte`
  (DELETE nach Grep-Nachweis, 358 LoC).
- ~LoC: ~180 netto, stark negativ in Summe (zwei gelöschte Step-Dateien
  >570 LoC gegen neue Verdrahtungsglue).
- Abhängigkeiten: nach Scheibe 1–3 (unabhängige Datei-Menge, aber
  Reihenfolge vermeidet Merge-Konflikte in `CompareEditor.svelte`).

**Scheibe 5 — Editor: Orte-Abschnitt Fidelity-Verifikation (compare-eigen, dokumentierte Ausnahme von Constraint 0)**
- Inhalt: Smart-Import/min-2-Validierung/nummerierte Auswahl bleiben
  unverändert (bereits 1:1); Bibliotheks-Grid auf 3-spaltige
  Gruppen-Darstellung mit Gruppen-Kopfzeile `Gruppe · N` prüfen/angleichen
  (`screen-compare-editor.jsx:271-296`). Der Orte-Tab ist die einzige
  Compare-eigene Editor-Tab-Domäne (kein Trip-Pendant — der Trip hat einen
  strukturell anderen Etappen-Tab) und bleibt dies bewusst.
- Dateien: `frontend/src/lib/components/compare/steps/Step2Orte.svelte`
  (MODIFY, ggf. nur CSS/Grid-Feinschliff, kein Verhaltenswechsel erwartet).
- ~LoC: ~70.
- Abhängigkeiten: keine (unabhängig von 1–4).

**Scheibe 6 — Hub: Orte-Tab (compare-eigen) + Idealwerte-Tab Inline-Edit-Parität durch `CorridorEditor`-Einbettung (Neubau, LoC-Override-Kandidat)**
- Inhalt: Orte-Liste im Hub-Orte-Tab wird per Drag umsortierbar
  (`location_ids`-Reihenfolge = Spaltenreihenfolge im Briefing,
  `CompareLocationRow`, `molecules.jsx:1188-1211`); „Ort hinzufügen" öffnet
  eine Inline-Auswahl im Hub statt eines Redirects; Orts-Entfernen wird
  wired und persistiert per PUT (bleibt compare-eigen, Scheibe 5). Der
  Idealwerte-Tab wird auf die Einbettung des geteilten
  `CorridorEditor context="vergleich"` (bzw. `CorridorEditorMobile`)
  umgestellt — statt eines neuen Bespoke-Formulars für den Edit-Stift und
  „Metrik hinzufügen" wird derselbe Organism gemountet, den auch der
  Editor bereits nutzt (löst das frühere Offen-Risiko „bespoke vs. reuse"
  zugunsten von „reuse", konsistent Constraint 0).
- Dateien: `frontend/src/lib/components/compare/CompareTabs.svelte`
  (MODIFY, Orte-Tab-Block um Drag-Handler erweitern; Idealwerte-Tab-Block
  durch eingebetteten `CorridorEditor` ersetzen), `frontend/src/lib/components/compare/locationHelpers.ts`
  (MODIFY, ggf. Reorder-Helfer), zugehöriger Save-Pfad (bestehender
  PUT-Handler wird wiederverwendet, kein neuer Endpoint).
- ~LoC: ~240 (Override-Kandidat, Ankündigung beim Scheiben-Start nötig;
  tendenziell niedriger als ein Bespoke-Formular, da `CorridorEditor`
  bereits fertig ist).
- Abhängigkeiten: nach Scheibe 3 (Header-Kebab-Refactor teilt sich
  `CompareTabs.svelte` mit dieser Scheibe) und nach Scheibe 4 (etabliert
  das Muster „geteilten Organism in einen Compare-Tab einbetten").

**Scheibe 7 — Hub: Versand-Tab Inline-Edit-Parität durch `VersandTab`-Einbettung + Vorschau-Neutralitäts-Klärung (LoC-Override-Kandidat)**
- Inhalt: Der heutige Bespoke-Nachbau des Versand-Bereichs in
  `CompareTabs.svelte` (eigene `DetailRow`/`Card`-Konstruktion, `disabled`-
  Kanal-Switches, `goToEditVersand()`-Redirect) wird durch eine Einbettung
  des geteilten `<VersandTab context="vergleich" activation={...}>` ersetzt
  — derselbe Organism, den der Editor bereits nutzt, inklusive
  funktionaler Kanal-Toggles, editierbarer Briefing-Zeiten und der
  kompletten notify-Zustellung (`AlertChannelPicker`/Cooldown/Stille
  Stunden). Die Aktivierungs-Karte nutzt das bereits vorhandene
  `activation`-Prop-Pattern (`screen-compare-editor.jsx:375`) statt einer
  neuen Hub-eigenen Komponente. Zusätzlich: erneute Verifikation, dass
  `CompareMatrix.svelte`/`HourlyMatrix.svelte` nicht produktiv gerendert
  werden (Commit-Gate). Desktop-Inbox/iPhone-Mail-Umschalter im Vorschau-
  Tab bleibt unverändert (Regression).
- Dateien: `frontend/src/lib/components/compare/CompareTabs.svelte`
  (MODIFY, Versand-Bereich durch `VersandTab`-Einbettung ersetzen, Bespoke-
  Markup entfernen), keine Änderung an `CompareMatrix.svelte`/
  `HourlyMatrix.svelte` nötig (verifizierter Totcode, kein Fix).
- ~LoC: ~200 (Override-Kandidat, Ankündigung beim Scheiben-Start nötig;
  Reduktion ggü. Vor-Version, da Einbettung statt Neubau tendenziell
  weniger Code braucht, gleichzeitig aber Bespoke-Markup entfernt wird —
  Netto-Effekt in Scheibe 7 selbst zu verifizieren).
- Abhängigkeiten: nach Scheibe 3 (gleiche Datei-Region) und nach Scheibe 6
  (etabliertes Einbettungs-Muster für geteilte Organismen im Hub).

**Scheibe 8 — Mobile-Vervollständigung (spiegelt die geteilten Organismen aus S4/S6/S7)**
- Inhalt: Liste dense+Chevron (Regressionsnachweis, bereits vorhanden),
  Hub-Detail 2×2-Monitoring (4 Stats), Lifecycle-Bottom-Sheet nutzt
  dieselbe Lifecycle-Aktionsliste aus Scheibe 3, Editor Lock-Toast +
  floating CTA, mobile Spiegelung der Inline-Edit-Parität aus Scheibe 6/7
  über dieselben geteilten Organismen in ihrer `dense`-Variante
  (`CorridorEditorMobile`, `VersandTab` mit `dense`-Prop) statt eines
  eigenen Mobile-Bespoke-Pfads.
- Dateien: `frontend/src/lib/components/compare/CompareTabs.svelte`
  (MODIFY, Mobile-2×2-Pfad, falls abweichend), zugehörige Mobile-Sheet-
  Komponente (im Ist bereits `MCompareActionSheet` vorhanden, „nutzt
  compareActions()" laut `issue_493_compare_mobile.test.ts:63-69` — wird
  auf die Lifecycle-Variante aus Scheibe 3 umgestellt), `CompareEditor.svelte`
  (Mobile-Zweig, Lock-Toast-Mechanismus existiert bereits ab Zeile 372-390
  — Scheibe prüft nur die floating-CTA-Fidelity gegen JSX).
- ~LoC: ~170.
- Abhängigkeiten: nach Scheibe 3 (Lifecycle-Aktionsliste), Scheibe 4
  (Mobile-LayoutTab-Verdrahtung) und Scheibe 6/7 (Inline-Edit-Parität, die
  hier auf Mobile gespiegelt wird).

**Scheibe 9 — `/compare/{id}/edit` → Redirect auf Hub (letzte Scheibe, GATED)**
- Inhalt: Sobald Scheiben 6/7 ausgeliefert UND vom PO als vollständige
  Inline-Edit-Parität bestätigt sind, leitet `/compare/{id}/edit`
  serverseitig (SvelteKit `redirect()` in `+page.server.ts`) auf
  `/compare/{id}?tab=<passender-tab>` um (wörtlich body-20, Zeile 105);
  `CompareEditor.svelte` mit `mode="edit"` wird nicht mehr über diese Route
  erreicht (kann als Totcode-Kandidat markiert, aber in dieser Spec noch
  nicht gelöscht werden — siehe KL-4).
- Dateien: `frontend/src/routes/compare/[id]/edit/+page.server.ts`
  (MODIFY, Redirect statt Daten-Load), betroffene Playwright-Specs, die
  `/edit` direkt ansteuern (MODIFY, sofern der Redirect ihre Assertions
  bricht).
- ~LoC: ~50 (plus Spec-Anpassungsaufwand, der beim Scheiben-Start separat
  geschätzt wird).
- Abhängigkeiten: **PO-bestätigungspflichtig vor Start** — braucht
  Scheiben 6/7 vollständig UND explizite PO-Freigabe, dass die
  Inline-Edit-Parität ausreicht (siehe KL-1). Wird verschoben, falls die
  Parität-Prüfung Lücken zeigt.

## Expected Behavior

- **Input:** Bestehende ComparePresets (Draft/Active/Paused), bestehende
  gespeicherte Orte, bestehende `/api/compare/presets*`- und
  `/api/locations/resolve`-Endpunkte (unverändert, keine Backend-Änderung
  in dieser Spec außer der additiven `location_ids`-Reihenfolge-PUT in
  Scheibe 6, die den bestehenden Endpoint wiederverwendet).
- **Output:** Nach Scheibe 8 sind Liste, Hub (6 Tabs, davon 3 inline
  editierbar über geteilte Organismen) und Editor (Desktop + Mobile, nur
  noch `mode="create"` im Ziel-Fluss aktiv genutzt) strukturell 1:1 zur
  Handoff-4-JSX bzw. zum Fluss-Prototyp/body-20. Nach Scheibe 9 (gated)
  entfällt der separate Edit-Screen als Nutzerpfad vollständig.
  `data-testid`-Bestand (C6, 17 Playwright-Specs) bleibt über alle
  Scheiben stabil bzw. wird in Scheibe 9 bewusst und dokumentiert
  angepasst.
- **Side effects:** Keine Datenmigration, keine Schema-Änderung — reine
  UI-Schicht. Löschungen von Totcode-Dateien (Scheibe 1, 4) reduzieren die
  Bundle-Größe, verändern kein Nutzerverhalten.

## Test Plan

Zwei Schichten gemäß Test-Politik (CLAUDE.md, PO-go 2026-07-09).

**Kern-Schicht (Vitest/Svelte-Unit + statische Checks, Commit-Gate je Scheibe):**
- Scheibe 1: Unit-Test `compareActions('active'|'paused')` liefert 5
  Einträge ohne `archive`; `compareActions('draft')` unverändert 2
  Einträge; statischer Grep-Test auf 0 Importe der drei Alt-Dateien
  (AC-1–AC-3).
- Scheibe 2: keine neuen Unit-Tests (reine Klickpfad-Verifikation, siehe
  Live-E2E) — bestehende Unit-Suiten für `compareWizardState.svelte.ts`
  und `CompareEditor.svelte` bleiben grün (Regressionsbasis für die Akzeptanzkriterien 25 bis 29).
- Scheibe 3: Unit-Test `compareLifecycleActions()` liefert 3 Einträge
  (Toggle/Archivieren/Löschen) bzw. 1 bei `draft`; Snapshot/DOM-Test
  Kanäle-Stat zeigt Kanal-Namen; DOM-Test SummaryCard-Sprung wechselt nur
  `activeTab` (AC-5, AC-6, AC-30).
- Scheibe 4: Unit-Test `CompareEditor.svelte` rendert `data-context="vergleich"`
  im `LayoutTab`-Wrapper statt `Step4Layout`; statischer Grep-Test auf 0
  verbleibende Importe der gelöschten Step-Dateien (AC-8, AC-11).
- Scheibe 5: Bestehende Step2Orte-Tests bleiben grün (Regressionsnachweis,
  AC-12); DOM-Test Bibliotheks-Grid-Gruppenkopf (AC-13).
- Scheibe 6: Unit-Test Reorder-Handler ändert `location_ids`-Reihenfolge im
  lokalen State und triggert den PUT-Aufruf mit der neuen Reihenfolge;
  DOM-Test „Ort hinzufügen"/Entfernen öffnet Inline-UI statt Navigation;
  DOM-Test Hub-Idealwerte-Tab rendert den eingebetteten `CorridorEditor`
  (`data-context="vergleich"`) statt einer eigenen Liste (AC-14,
  AC-31–AC-34).
- Scheibe 7: DOM-Test Hub-Versand-Tab rendert den eingebetteten
  `VersandTab` (`data-context="vergleich"`) statt Bespoke-Markup; DOM-Test
  Kanal-Switches reagieren auf Klick (nicht mehr `disabled`); DOM-Test
  Aktivierungs-Karte ändert Status ohne Redirect; statischer Grep-Test 0
  Importe `CompareMatrix.svelte`/`HourlyMatrix.svelte` außerhalb eigener
  Tests (AC-17, AC-18, AC-20, AC-35–AC-37).
- Scheibe 8: Unit-Test `MCompareActionSheet` nutzt nach der Umstellung die
  Lifecycle-Variante statt `compareActions()` (AC-23); DOM-Test 2×2-Grid
  mit 4 Stats (AC-22).
- Scheibe 9: Unit-Test des Redirect-Handlers in `+page.server.ts`
  (`?tab=`-Mapping korrekt) — nur ausgeführt, wenn die Scheibe freigegeben
  ist (AC-39).
- **Scheiben-übergreifend (jede Scheibe):** Adversary-Prüfpunkt „hätte das
  ein geteilter Baustein sein müssen?" (Constraint 0) + Review-Grep auf
  neue Dateien unter `components/compare/` mit Pendant-Abgleich gegen
  `components/trip*/`, `components/shared/` (AC-40).

**Live-E2E-Schicht (nur `/e2e-verify` gegen Staging):**
- Bestehende 17 Compare-Playwright-Specs bleiben grün nach jeder Scheibe
  (C6, Testid-Stabilität) — kein Playwright-Bruch durch Kebab-/Tab-/
  Inline-Edit-Änderungen, außer bewusst in Scheibe 9 dokumentiert.
- Fresh-Eyes-Screenshot-Abgleich je UI-Scheibe gegen die konkrete JSX-
  bzw. Fluss-/body-20-Struktur (Zeilennummern aus dieser Spec, kein
  Prosa-Abgleich): Liste (S1), Fluss-Klickpfad Gesamt (S2), Hub-Header +
  Übersicht (S3), Editor-Layout-Tab (S4), Editor-Orte-Tab (S5), Hub-Orte/
  Idealwerte-Inline-Edit (S6), Hub-Versand-Inline-Edit/Vorschau (S7),
  Mobile-Varianten (S8).
- Scheibe 2: EIN durchgehender Playwright-Klickpfad-Test (echte Klicks,
  kein `goto()`) für Liste→Kachel→Detail→Zurück→Neuer Vergleich→Editor→
  Aktivieren→Detail (AC-29), plus Mobile-Äquivalent.
- Scheibe 6: echter Drag-Interaktions-Test gegen Staging (kein reiner
  State-Test), echte Klicks für „Ort hinzufügen"/„Metrik hinzufügen"/
  Edit-Pencil (jetzt im eingebetteten `CorridorEditor`) statt direkter
  API-Manipulation.
- Scheibe 7: echte Klicks auf Kanal-Switches/Versand-Edit-Pencil/
  Aktivierungs-CTA im eingebetteten `VersandTab`, Assert auf ausbleibende
  `window.location`-Navigation.
- Scheibe 9 (nach Freigabe): Direktaufruf `/compare/{id}/edit`, Assert
  finale URL + `?tab=`-Parameter; volle Compare-Suite läuft danach erneut
  komplett gegen Staging.

## Acceptance Criteria

<!-- Hinweis zur Nummerierung: Die ursprünglichen ACs (1-24) behalten ihre
     Nummern unverändert (PO-Vorgabe „Nummerierung fortführen" bei der
     Fluss-Korrektur 2026-07-13) und wurden nur den neu benannten Scheiben
     zugeordnet. Neue Akzeptanzkriterien sind fortlaufend ab Nummer 25 angehängt und stehen an
     der inhaltlich passenden Stelle im Dokument — die Nummern sind daher
     nicht durchgehend chronologisch zur Lesereihenfolge, aber stabil. -->

<!-- Scheiben-übergreifend — Code-Teilungs-Invariante (CLAUDE.md, PO-Vorgabe, bekräftigt 2026-07-13) -->

- **AC-40:** Given die Gesamtheit der in allen Scheiben neu entstandenen
  oder geänderten Compare-Komponenten / When das Repository nach jeder
  Scheibe geprüft wird / Then existiert keine neue Compare-Komponente, zu
  der ein Trip-Pendant existiert, ohne dokumentierte Ausnahme-Begründung in
  dieser Spec — geteilte Organismen werden konsumiert, nicht kopiert.
  - Test: Adversary-Prüfpunkt je Scheibe + Review-Grep auf neue Dateien
    unter `components/compare/` mit Pendant-Abgleich gegen
    `components/trip*/`, `components/shared/`.

<!-- Scheibe 1 — Liste: Kebab-Bereinigung + Alt-Rest-Entfernung -->

- **AC-1:** Given den Kebab-Menü-Aufruf `compareActions('active')` oder
  `compareActions('paused')` in der Liste / When das Menü einer
  Compare-Kachel geöffnet wird / Then zeigt es genau 5 Einträge
  (Pausieren/Aktivieren, Briefing jetzt senden, Vorschau, Bearbeiten,
  Löschen) ohne „Archivieren" (Soll: `molecules.jsx:1018-1027`).
  - Test: Unit-Test gegen `compareActions('active')` und `('paused')`,
    Assert `length === 5` und kein Item mit `id === 'archive'`.

- **AC-2:** Given `compareActions('draft')` in der Liste / When das Menü
  einer Draft-Kachel geöffnet wird / Then bleiben exakt 2 Einträge
  (Setup fortsetzen, Löschen) unverändert erhalten (Regressionsnachweis,
  von der Scheibe nicht berührt).
  - Test: Bestehender Test-Teil aus `bug_626_compare_menu_actions.test.ts`
    (draft-Assertions) bleibt grün ohne Anpassung.

- **AC-3:** Given die drei Alt-Komponenten `LocationsRail.svelte`,
  `AutoReportsOverview.svelte`, `AutoReportCard.svelte` (`compare/`) / When
  das Repository nach Scheibe 1 durchsucht wird / Then existiert außerhalb
  ihrer eigenen Testdateien kein produktiver Import mehr — die Dateien sind
  gelöscht (verifizierter Totcode, kein stiller Alt-Rest auf `/compare`).
  - Test: Statischer Grep-Test auf die drei Dateipfade im `frontend/src`-Baum,
    0 Treffer außerhalb `__tests__/`.

- **AC-4:** Given die Kachel-Liste unter `/compare` mit ≥1 Vergleich / When
  sie nach Scheibe 1 gerendert wird / Then zeigt jede `CompareTile`
  weiterhin Status-Dot, Name, `status · region`, `N Orte · Profil`,
  Kanal-Pills und Fuß `schedule + zuletzt` unverändert (Regressionsnachweis
  gegen `molecules.jsx:1082-1137`, die Kebab-Änderung berührt nur `trailing`).
  - Test: Fresh-Eyes-Screenshot-Abgleich gegen `molecules.jsx:1057-1140`
    (Live-E2E).

<!-- Scheibe 2 — Fluss-Verdrahtung: Create→Detail-Redirect, Back-Nav, Abbrechen -->

- **AC-25:** Given eine Compare-Kachel in der Liste (Desktop oder Mobile) /
  When sie angeklickt bzw. angetippt wird / Then navigiert die App auf
  `/compare/{id}` (Detail-Hub), analog `openSub` im Fluss-Prototyp
  (`Ortsvergleich Fluss.html:88,94/103`) — bereits implementiert, diese
  Scheibe sichert den Pfad mit einem echten Klickpfad-Test ab.
  - Test: Playwright-Klickpfad (echter Klick auf Kachel, kein `goto()`),
    prüft URL `/compare/{id}` nach Klick.

- **AC-26:** Given den Editor im Create-Modus mit vollständig ausgefülltem
  Versand-Tab / When „Briefing aktivieren" geklickt wird / Then landet die
  App nach erfolgreichem POST auf `/compare/{neue-id}` (Detail des eben
  angelegten Vergleichs), NICHT auf der Liste — analog `activateNew`
  (`Ortsvergleich Fluss.html:90,96`). Bereits implementiert
  (`compareWizardState.svelte.ts:138`, `goto('/compare/' + created.id)`).
  - Test: Playwright-Klickpfad-Regressionstest sichert das ab, damit
    spätere Scheiben es nicht brechen.

- **AC-27:** Given den Editor im Create-Modus / When „Abbrechen" geklickt
  wird / Then navigiert die App auf `/compare` (Liste), analog
  `onCancel={goList}` (`Ortsvergleich Fluss.html:96,105`). Bereits
  implementiert (`CompareEditor.svelte:497`, `href="/compare"`).
  - Test: Playwright-Klickpfad-Regressionstest.

- **AC-28:** Given den Detail-Hub eines Vergleichs / When der
  Breadcrumb-Link „Orts-Vergleiche" oder der Zurück-Pfeil geklickt wird /
  Then navigiert die App auf `/compare` (Liste), analog `onBack={goList}`
  (`Ortsvergleich Fluss.html:88,94,103`). Bereits implementiert
  (`compare/[id]/+page.svelte:130,173`).
  - Test: Playwright-Klickpfad-Regressionstest.

- **AC-29:** Given den kompletten Fluss Liste→Detail→Editor→Detail / When
  alle vier Übergänge (AC-25–AC-28) nacheinander durchlaufen werden / Then
  existiert zu keinem Zeitpunkt ein zusätzlicher, im Fluss nicht
  vorgesehener Zwischen-Screen — der separate Edit-Screen
  `/compare/{id}/edit` bleibt für DIESE Scheibe unangetastet und wird nicht
  Teil dieses Klickpfads (siehe Scheibe 9 für den geplanten Rückbau).
  - Test: EIN durchgehender Playwright-Klickpfad-Test (Live-E2E) — Liste →
    Kachel-Klick → Detail → Zurück → Neuer Vergleich → Editor → Aktivieren
    → Detail, ohne Zwischenstopps.

<!-- Scheibe 3 — Hub: Header-Kebab auf Lifecycle + Kanäle-Stat-Fidelity + Übersicht-Ansehen-Klarstellung -->

- **AC-5:** Given den Hub-Header-Kebab (`compare/[id]/+page.svelte:154`) /
  When er nach Scheibe 3 geöffnet wird / Then zeigt er ausschließlich die
  Lifecycle-Aktionen Pausieren/Aktivieren, Archivieren, Löschen (bei
  `draft` nur Löschen) — nicht mehr Briefing senden/Vorschau/Bearbeiten,
  die weiterhin exklusiv über Tabs bzw. Primäraktion erreichbar bleiben.
  - Test: Unit-Test `compareLifecycleActions('active')` liefert genau 3
    Einträge (`pause|resume`, `archive`, `trash`); `('draft')` liefert 1
    Eintrag (`trash`).

- **AC-6:** Given die „Kanäle"-Stat im Übersicht-Monitoring-Streifen des
  Hubs / When ein Vergleich mit ≥1 aktivem Kanal angezeigt wird / Then
  zeigt sie die Kanal-Namen durch „ · " getrennt (z. B. „Email · Telegram")
  statt einer reinen Kanal-Anzahl (Soll: `screen-compare-detail.jsx:147-150`,
  Ist bisher `channelCountLabel(N)`).
  - Test: DOM-Test — Fixture mit `empfaenger`-Liste `[email, telegram]`
    rendert den String „Email · Telegram", nicht „2 Kanäle".

- **AC-7:** Given die 4 SummaryCards + der Verifikations-Hinweis im
  Übersicht-Tab / When Scheibe 3 ausgeliefert ist / Then bleiben
  „Bearbeiten →"-Tab-Sprünge und der Vorschau-Hinweis unverändert
  funktionsfähig (Regressionsnachweis, bereits vorhanden vor dieser Scheibe).
  - Test: Bestehende `CompareTabs.svelte`-Tests für die 4 Summary-Cards
    bleiben grün ohne Anpassung.

- **AC-30:** Given den Übersicht-Tab im Hub / When er dargestellt wird /
  Then bleibt er bewusst ein reiner Ansehen-Tab (Monitoring-Streifen +
  SummaryCards, kein Inline-Edit-Formular direkt hier) — jeder
  „Bearbeiten →"-Sprung landet auf einem der Tabs Orte/Idealwerte/Versand,
  die ab Scheibe 6/7 inline editierbar sind, nicht mehr auf
  `/compare/{id}/edit`.
  - Test: Regressions-DOM-Test — SummaryCard-„Bearbeiten →"-Klick wechselt
    `activeTab` (`handleValueChange`), löst keinen
    `window.location`-Navigationsaufruf aus.

<!-- Scheibe 4 — Editor + Hub: Layout-Tab-Organism verdrahten -->

- **AC-8:** Given den Editor-Tab „Layout" (Desktop UND Mobile,
  `CompareEditor.svelte:739-742` bzw. `:910-913`) / When er nach Scheibe 4
  geöffnet wird / Then rendert er den geteilten
  `<LayoutTab context="vergleich">`-Organism (`data-context="vergleich"`,
  `LayoutTab.svelte:43`) statt `<Step4Layout/>`.
  - Test: DOM-Test — `CompareEditor` mit `mode="create"` im Tab „layout"
    enthält `[data-testid="layout-tab"][data-context="vergleich"]`.

- **AC-9:** Given denselben Layout-Tab mit ≥2 ausgewählten Orten / When die
  Vorschau gerendert wird / Then zeigt sie Orte als Spalten mit grüner
  Markierung für Werte im Idealbereich und dem Copy „Kein Ranking"
  (`LTComparePreview.svelte`, bereits gebaut — Scheibe 4 verdrahtet ihn
  erstmals in den Compare-Editor).
  - Test: DOM-Test — Fixture mit 3 Orten, mind. eine Zelle trägt die Klasse
    `lt-good-cell`, Text „Kein Ranking" ist im DOM vorhanden.

- **AC-10:** Given den Kanal „Telegram" im Layout-Tab mit N ausgewählten
  Orten / When die Kappungs-Hinweiszeile gerendert wird / Then zeigt sie
  exakt „Label + N Orte = X Spalten (max 8)" über den geteilten `LTCapNote`
  (`context="vergleich"`), identisch zur Trip-Variante des Organism.
  - Test: DOM-Test — Fixture mit 4 Orten, Text enthält „Label + 4 Orte = 5
    Spalten (max 8)".

- **AC-11:** Given `steps/Step3Idealwerte.svelte` (215 LoC Totcode) / When
  das Repository nach Scheibe 4 durchsucht wird / Then existiert diese
  Datei nicht mehr, da die Idealwerte-Funktion vollständig über
  `CorridorEditor context="vergleich"` (#1231) läuft.
  - Test: Statischer Grep-Test auf `Step3Idealwerte`, 0 Treffer im
    gesamten `frontend/src`-Baum.

<!-- Scheibe 5 — Editor: Orte-Abschnitt Fidelity-Verifikation -->

- **AC-12:** Given den Editor-Tab „Orte" (`Step2Orte.svelte`) / When
  Scheibe 5 ausgeliefert ist / Then bleiben Smart-Import
  (`POST /api/locations/resolve`), min-2-Validierung und nummerierte
  Auswahlliste unverändert funktionsfähig (Regressionsnachweis — bereits
  vor dieser Scheibe 1:1 zum Soll implementiert).
  - Test: Bestehende `Step2Orte`-bezogene Tests bleiben grün ohne
    Anpassung.

- **AC-13:** Given die Bibliothek gespeicherter Orte im Orte-Tab / When sie
  gerendert wird / Then sind die Orte nach `group`-Feld in einem
  mehrspaltigen Grid gruppiert, jede Gruppe mit Kopfzeile `Gruppe · N`
  (Soll: `screen-compare-editor.jsx:271-296`).
  - Test: DOM-Test — Fixture mit Orten aus 2 Gruppen, DOM enthält 2
    Kopfzeilen mit korrektem Gruppennamen + Anzahl.

<!-- Scheibe 6 — Hub: Orte-Tab + Idealwerte-Tab Inline-Edit-Parität -->

- **AC-14:** Given den Hub-Orte-Tab mit ≥3 Orten / When ein Ort per Drag an
  eine neue Position gezogen wird / Then ändert sich die angezeigte
  Reihenfolge sofort im UI und ein PUT-Request mit der neuen
  `location_ids`-Reihenfolge wird ausgelöst.
  - Test: Playwright-Drag-Interaktions-Test gegen Staging (Live-E2E) — Ort
    an Position 3 auf Position 1 ziehen, DOM-Reihenfolge + Netzwerk-Request-
    Body prüfen.

- **AC-15:** Given einen Vergleich mit per Drag geänderter Orte-Reihenfolge
  / When die Hub-Seite neu geladen wird / Then zeigt der Orte-Tab die
  zuletzt gespeicherte Reihenfolge (kein Zurückspringen auf die
  ursprüngliche Reihenfolge).
  - Test: Live-E2E — Reorder speichern, Reload, DOM-Reihenfolge identisch
    zur gespeicherten `location_ids`-Reihenfolge.

- **AC-16:** Given `CompareIdealRow` bzw. den eingebetteten `CorridorEditor`
  im Idealwerte-Tab des Hubs / When Scheibe 6 ausgeliefert ist / Then
  bleibt die Basis-Aussage Metrik · Idealbereich · Priorität mit „kein
  Score"-Copy erhalten, jetzt über den geteilten Organism statt einer
  eigenen Liste, ergänzt um die neue Inline-Edit-Fähigkeit aus
  AC-33/AC-34.
  - Test: Bestehender Idealwerte-Tab-Test wird auf den eingebetteten
    `CorridorEditor` umgestellt, bleibt grün.

- **AC-31:** Given den Hub-Orte-Tab / When „Ort hinzufügen" geklickt wird /
  Then öffnet sich eine Inline-Auswahl (Bibliothek/Smart-Import, analog
  Editor-Orte-Tab aus Scheibe 5) INNERHALB des Hubs, kein Redirect zu
  `/compare/{id}/edit`.
  - Test: Playwright-Klickpfad — Klick auf „Ort hinzufügen" öffnet
    sichtbaren Picker im selben DOM, URL bleibt `/compare/{id}?tab=orte`.

- **AC-32:** Given einen Ort im Hub-Orte-Tab / When der Entfernen-Button
  geklickt wird / Then wird der Ort aus `location_ids` entfernt und die
  Änderung per PUT persistiert, ohne den Tab zu verlassen.
  - Test: Playwright-Klickpfad — Entfernen-Klick, Netzwerk-Request prüft
    reduzierte `location_ids`, DOM zeigt einen Eintrag weniger.

- **AC-33:** Given eine Metrik-Zeile im eingebetteten `CorridorEditor` des
  Hub-Idealwerte-Tabs / When der Edit-Stift geklickt wird / Then öffnet
  sich die Inline-Bearbeitung des Idealbereichs (min/max) direkt im Tab,
  kein Redirect zu `/compare/{id}/edit`.
  - Test: Playwright-Klickpfad — Stift-Klick öffnet Inline-Formular im
    selben DOM.

- **AC-34:** Given den Hub-Idealwerte-Tab / When „Metrik hinzufügen"
  geklickt wird / Then lässt sich eine neue Metrik mit Idealbereich über
  den eingebetteten `CorridorEditor` inline hinzufügen und per PUT
  persistieren, ohne den Tab zu verlassen.
  - Test: Playwright-Klickpfad — neue Metrik hinzufügen, DOM zeigt
    zusätzliche Korridor-Zeile, Netzwerk-Request bestätigt Persistenz.

<!-- Scheibe 7 — Hub: Versand-Tab Inline-Edit-Parität + Vorschau-Neutralitäts-Klärung -->

- **AC-17:** Given den Versand-Tab im Hub / When er gerendert wird / Then
  zeigt er eine eigene Aktivierungs-Karte mit Status (Entwurf/Aktiv/
  Pausiert) und kontextabhängigem Call-to-Action, getrennt von der
  Kanal-Liste (Soll: `screen-compare-detail.jsx:313-325`).
  - Test: DOM-Test — Fixture mit Status `active`, Aktivierungs-Karte zeigt
    „Aktiv" + CTA-Label „Pausieren".

- **AC-18:** Given denselben Versand-Tab / When der Status nicht `draft`
  ist / Then nennt der Copy-Text explizit, dass der Vergleich ohne
  Enddatum läuft, bis er pausiert wird — kein Enddatum-Eingabefeld ist
  sichtbar (außer optional über `CompareEndDateControl`, Constraint 5).
  - Test: DOM-Test — Text „bis du pausierst" bzw. äquivalenter Soll-Copy
    ist vorhanden.

- **AC-19:** Given den Vorschau-Tab mit Kanal „Email" / When zwischen
  Desktop-Inbox und iPhone-Mail umgeschaltet wird / Then bleibt dieses
  Verhalten nach Scheibe 7 unverändert funktionsfähig
  (Regressionsnachweis, `CompareTabs.svelte:510-527`).
  - Test: Bestehender Vorschau-Tab-Test bleibt grün ohne Anpassung.

- **AC-20:** Given `CompareMatrix.svelte` und `HourlyMatrix.svelte`
  (Best-Value-Hervorhebung, „Top-3 Locations") / When das Repository nach
  Scheibe 7 durchsucht wird / Then existiert außerhalb ihrer eigenen
  Testdateien kein produktiver Import — die vermutete
  Neutralitäts-Grauzone ist als Totcode bestätigt (zusätzlich bestätigt
  durch die neutrale `CompareEmailV2` in `Ortsvergleich Mail.html`), keine
  Änderung an diesen Dateien war nötig.
  - Test: Statischer Grep-Test auf beide Dateipfade, 0 Treffer außerhalb
    `__tests__/`.

- **AC-35:** Given die Kanal-Switches im eingebetteten `VersandTab` des
  Hub-Versand-Tabs (Email/Telegram/SMS) / When ein Switch geklickt wird /
  Then ändert sich der Kanal-Status sofort im UI und wird per PUT
  persistiert — die Switches sind nicht mehr `disabled` (Ist:
  `CompareTabs.svelte` Kanal-Switches heute `disabled={true}`).
  - Test: Playwright-Klickpfad — Switch-Klick, DOM-State-Änderung +
    Netzwerk-Request-Body prüfen.

- **AC-36:** Given die Briefing-Zeiten im eingebetteten `VersandTab` des
  Hub-Versand-Tabs / When eine Uhrzeit geändert wird / Then geschieht das
  inline direkt im Hub (statt der heutigen Navigation `goToEditVersand()`
  → `/compare/{id}/edit?tab=versand`, `CompareTabs.svelte:207-211`).
  - Test: Playwright-Klickpfad — Uhrzeit ändern, `window.location`-
    Navigation bleibt aus, Änderung erscheint im selben DOM.

- **AC-37:** Given die Aktivierungs-Karte im Hub-Versand-Tab
  (`activation`-Prop des eingebetteten `VersandTab`) / When
  „Aktivieren"/„Pausieren" geklickt wird / Then ändert sich der Status
  sofort (PATCH `.../state` bzw. äquivalent) ohne Redirect zu
  `/compare/{id}/edit`.
  - Test: Playwright-Klickpfad — Klick, Status-Pill im Header wechselt
    sichtbar ohne Seitenwechsel.

<!-- Scheibe 8 — Mobile-Vervollständigung -->

- **AC-21:** Given die mobile Liste (`/compare`, Viewport <900px) / When
  sie gerendert wird / Then zeigt jede Kachel `CompareTile` im `dense`-Modus
  mit Chevron statt Kebab (Regressionsnachweis, bereits über
  `+page.svelte` vorhanden — bestätigt nach den Kebab-Änderungen aus
  Scheibe 1/3, dass die mobile Liste NICHT versehentlich mitgeändert wurde).
  - Test: Fresh-Eyes-Screenshot-Abgleich gegen
    `screen-compare-list-mobile.jsx:48-57` (Live-E2E, Mobile-Viewport).

- **AC-22:** Given den mobilen Hub-Detail-Screen / When der Übersicht-Tab
  gerendert wird / Then zeigt er ein 2×2-Grid mit 4 Stats (Status/Nächster
  Versand/Zuletzt raus/Kanäle) statt der 5-Stat-Desktop-Leiste (Soll:
  `screen-compare-detail-mobile.jsx:79-85`).
  - Test: DOM-Test — Mobile-Viewport-Fixture, genau 4 Stat-Elemente im
    Monitoring-Grid.

- **AC-23:** Given die mobilen Lifecycle-Aktionen (`MCompareActionSheet`) /
  When das Bottom-Sheet geöffnet wird / Then zeigt es dieselbe
  Lifecycle-Aktionsliste (Toggle/Archivieren/Löschen) wie der
  Desktop-Header-Kebab aus Scheibe 3, nicht mehr den vollen
  `compareActions()`-Umfang.
  - Test: Unit-Test — `MCompareActionSheet` ruft nach der Umstellung
    `compareLifecycleActions()` statt `compareActions()` auf (ersetzt die
    Assertion aus `issue_493_compare_mobile.test.ts:63-69`).

- **AC-24:** Given den mobilen Editor mit einem gesperrten Tab (`mode="create"`,
  Voraussetzung nicht erfüllt) / When der Nutzer auf den gesperrten Tab tippt
  / Then zeigt die App einen kurzen Lock-Toast/Hinweis-Flash (bereits
  implementiert, `CompareEditor.svelte:372-390`, `showLockToast`) und eine
  floating Primär-CTA-Leiste bleibt am unteren Bildschirmrand sichtbar.
  - Test: Live-E2E — Playwright tippt auf gesperrten Tab im mobilen
    Viewport, prüft sichtbaren Toast-Text + fixierte CTA-Leiste.

<!-- Scheibe 9 — /compare/{id}/edit → Redirect auf Hub (letzte Scheibe, GATED) -->

- **AC-38:** Given vollständige Inline-Edit-Parität in den Hub-Tabs
  (Scheiben 6/7 abgeschlossen und vom PO ausdrücklich bestätigt) / When
  `/compare/{id}/edit` aufgerufen wird / Then leitet die Route serverseitig
  (redirect) auf `/compare/{id}?tab=<passender-tab>` um, der separate
  Editor-Screen im Edit-Modus wird nicht mehr gerendert.
  - Test: Live-E2E — Direktaufruf von `/compare/{id}/edit`, Assert finale
    URL `/compare/{id}` + korrekter `?tab=`-Parameter.

- **AC-39:** Given die 17 Compare-Playwright-Specs / When Scheibe 9
  ausgeliefert wird / Then sind alle Specs, die bisher
  `/compare/{id}/edit` direkt ansteuerten, entweder unverändert grün (weil
  der Redirect transparent funktioniert) oder in derselben Scheibe bewusst
  aktualisiert (C6, kein stiller Bruch).
  - Test: Volle Compare-Playwright-Suite gegen Staging, 0 rote Specs.

## Known Limitations

- **KL-1:** Der Widerspruch `mode="edit"` (dokumentiert in
  `screen-compare-editor.jsx`, aber weder im Fluss-Prototyp noch in
  body-20 vorgesehen) wird per PO-Vorgabe zugunsten der beiden
  Verdrahtungs-Quellen aufgelöst (kein separater Edit-Screen im
  Ziel-Endzustand). Scheibe 9 (Redirect) ist **PO-bestätigungspflichtig
  vor Start** und darf erst starten, wenn (a) Scheiben 6/7 vollständige
  Inline-Edit-Parität liefern und (b) der PO dies explizit bestätigt.
  Cross-Referenz: Design-Request „Frage 7", die der PO separat ergänzt
  (Pfad zum Zeitpunkt der Spec-Erstellung noch offen, siehe Dependencies).
- **KL-2 (revidiert):** Der 6. Editor-Tab „Alarme" (`CompareEditor.svelte:92`,
  nur im Edit-Modus, #1170) bleibt in dieser Spec **vorerst unangetastet**
  — keine Entfernung, kein Umbau, kein Scope einer der 9 Scheiben. Das
  Design-Zielbild (`body-29a`/`body-29b`) sieht jedoch **keinen eigenen
  Alarme-Tab** vor: die notify-Zustellung (Alert-Kanäle, Cooldown, Stille
  Stunden, Beispiel-Warnung) gehört in den geteilten Versand-Tab
  (`AlertChannelPicker` in `VersandTab`), die Schwellwerte selbst in den
  geteilten Wertebereiche-Tab (`CorridorEditor`, `notify`-Feld am
  Korridor). Damit ist Scheibe 7 dieser Spec bereits ein Teilschritt in
  diese Richtung (Versand-Tab wird zum geteilten Organism). Rest-Config
  ohne offensichtliches neues Zuhause (Cooldown, Ruhezeiten, Radar-Toggle,
  amtliche-Warnungen-Toggle) braucht eine PO-Entscheidung — Design-Request
  „Frage 5". Die eigentliche Auflösung des Alarme-Tabs (Entfernung +
  Migration seiner Inhalte) ist **explizit Out-of-Scope / Folge-Arbeit**
  dieser Spec, nicht als eigene Scheibe eingeplant.
- **KL-3:** `paused_at` existiert im FE-Modell noch nicht additiv (kommt
  aus #1250 Scheibe 2). Bis dahin nutzen Scheibe 3 (Lifecycle-Toggle-Label)
  und Scheibe 8 (Mobile-Bottom-Sheet) die bestehende
  `computePauseToggle`-Logik über `schedule=="manual"` — kein Doppel-Touch
  der Pause-Semantik in dieser Spec.
- **KL-4:** `steps/Step4Layout.svelte` wird erst gelöscht, nachdem
  Scheibe 4 verifiziert hat, dass kein anderer Konsument mehr existiert
  (aktuell nur `CompareEditor.svelte` an den vier genannten Stellen) —
  Löschung ist Teil von Scheibe 4, aber mit explizitem Vorab-Grep als
  Sicherung gegen versteckte Zweitverwendung.
- **KL-5:** `CompareMatrix.svelte`/`HourlyMatrix.svelte` werden in dieser
  Spec NICHT gelöscht, nur als Totcode verifiziert (AC-20) — Löschung ist
  optionale Aufräumarbeit und gehört, falls gewünscht, in den
  Nebenbefund-Sammel-Issue #1199, nicht in diese Spec.
- **KL-6 (aufgelöst):** Die frühere offene Frage „bespoke Inline-Formular
  vs. `CorridorEditor`-Einbettung" für die Idealwerte-Inline-Edit-Parität
  ist zugunsten der Einbettung entschieden (Code-Teilungs-Invariante,
  Constraint 0) — Scheibe 6 mountet direkt `CorridorEditor
  context="vergleich"`. Verbleibendes Restrisiko: die CSS-/Layout-
  Integration eines vollständigen Editor-Organism in den bisher rein
  lesenden Hub-Tab-Kontext kann von der ~240-LoC-Schätzung abweichen —
  wird in Scheibe 6 selbst als erster Analyseschritt geprüft, mit
  Eskalation an den PO bei größerer Abweichung.

- **KL-7 (PO-abgesegneter Zwischenzustand S1→S3, 2026-07-13):** Da Liste UND
  Hub heute dieselbe `compareActions()` konsumieren, ist „Archivieren" nach
  dem Solo-Deploy von Scheibe 1 auf ALLEN Oberflächen (Liste Desktop/Mobile,
  Hub-Header, Hub-Mobile-Sheet) unerreichbar, bis Scheibe 3 die dedizierte
  Lifecycle-Aktionsliste für den Hub liefert. Kein Crash — die
  `archive`-Handler-Zweige bleiben funktionsfähig, werden nur nicht mehr
  emittiert. Vom PO am 2026-07-13 nach Adversary-Finding F001 (Verdict
  AMBIGUOUS) explizit als akzeptierter Übergang freigegeben („S1 solo
  deployen"); Begründung: keine aktiven Produktiv-Nutzer, Scheibe 3 folgt
  unmittelbar. Backend-Endpoint `PATCH /api/compare/presets/{id}/state`
  bleibt unverändert verfügbar.

## Edge Cases

| Fall | Erwartetes Verhalten |
|---|---|
| Vergleich mit 0 Kanälen im Hub-Header-Kebab | Lifecycle-Aktionen bleiben verfügbar (Pausieren/Aktivieren funktioniert unabhängig von Kanälen), keine Sonderbehandlung nötig |
| Drag-Reordering (S6) bei genau 2 Orten | Reordering funktioniert wie bei mehr Orten, kein Sonderfall (min-2-Validierung bleibt vom Editor, nicht vom Hub-Orte-Tab durchgesetzt) |
| Netzwerkfehler beim PUT nach Drag-Reorder oder Inline-Edit (S6/S7) | UI zeigt den alten Zustand wieder (Rollback), kein stiller Datenverlust — analog zu bestehenden Fehlerpfaden in `compareEditorSave.ts` |
| Bibliotheks-Grid (S5) mit nur einer Gruppe | Ein einzelner Gruppen-Header wird gezeigt, kein leeres Grid-Fragment |
| Mobile Lock-Toast (S8) bei mehrfachem schnellen Antippen desselben gesperrten Tabs | Toast wird nicht mehrfach gestapelt (Debounce/Replace, bereits über `_lockToastTimer`-Clear-Pattern in `CompareEditor.svelte:376-381` abgedeckt) |
| `CompareMatrix`/`HourlyMatrix` (KL-5) werden versehentlich in einer künftigen Änderung wieder importiert | Der statische Grep-Test aus AC-20 wird bei künftigen PRs erneut fehlschlagen und macht die Reaktivierung sichtbar (kein automatisches Gate in dieser Spec, aber Testabdeckung als Frühwarnung) |
| Direktaufruf `/compare/{id}/edit` per Lesezeichen/Deep-Link NACH Scheibe 9 | Redirect greift transparent auf `/compare/{id}?tab=<passender-tab>`, kein 404, kein Datenverlust |
| Scheibe 9 startet, obwohl Idealwerte-Inline-Edit (KL-6) noch unvollständig ist | Darf laut KL-1 nicht passieren — Scheibe 9 ist explizit gated und wartet auf PO-Bestätigung, nicht auf einen automatischen Trigger |
| Eingebetteter `CorridorEditor`/`VersandTab` (S6/S7) bringt CSS/Layout mit, das im schmaleren Hub-Tab-Kontext bricht (statt im vollbreiten Editor) | Wird als Teil der Einbettungsarbeit selbst behoben (Container-Anpassung), kein neues Organism-internes Styling — Fresh-Eyes-Check pro Scheibe deckt das ab |

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine [no-adr]
- **Rationale:** Diese Spec ist eine reine UI-Fidelity-Angleichung an eine
  bereits bestehende Design-SSoT (Handoff-4-JSX für Optik, Fluss-Prototyp +
  body-20 für Navigation) innerhalb der bestehenden Frontend-Architektur
  (Svelte-Komponenten, bestehende API-Endpunkte, bestehende Route-
  Struktur). Es wird kein neues Architekturmuster eingeführt, kein neues
  Datenmodell, keine neue Persistenzform — im Gegenteil: die Scheiben 4, 6
  und 7 REDUZIEREN Architektur-Divergenz, indem sie bestehende, bereits
  geteilte Organismen (`LayoutTab`, `CorridorEditor`, `VersandTab`) an
  Stellen einbetten, wo bisher Bespoke-Code lag — konsistent mit der
  Code-Teilungs-Invariante (CLAUDE.md). Auch die in Scheibe 6 neu
  hinzukommende Drag-Reorder-Funktion nutzt bestehende PUT/PATCH-
  Endpunkte und bestehende Felder. Der Rückbau der separaten Edit-Route in
  Scheibe 9 ist eine Routing-Vereinfachung (Redirect), kein neues
  Architekturmuster. Analog zu #1231/#1250 Scheiben 0–4, die ebenfalls
  ohne ADR auskamen.

## Changelog

- **2026-07-13 (feat-1256-compare-ui-rewire, v1.3):** KL-7 ergänzt — PO-abgesegneter
  S1→S3-Zwischenzustand (Archivieren app-weit unerreichbar bis Scheibe 3), Auslöser
  Adversary-Finding F001 (AMBIGUOUS), PO-Entscheid „S1 solo deployen".

- 2026-07-13: Initial spec erstellt — Issue #1256, Programm-Spec über 7
  Scheiben nach Muster #1231/#1250, basierend auf
  `docs/context/feat-1256-compare-ui-rewire.md` sowie eigener
  Code-Verifikation der Spec-Phase (konkrete Datei:Zeile-Belege für alle
  sieben Kern-Abweichungen, u. a. Kebab-Aktionsumfang, Header-Kebab-Scope,
  unverdrahteter Layout-Tab-Organism, verifizierter Totcode bei
  LocationsRail/AutoReports/CompareMatrix/HourlyMatrix).
- 2026-07-13 (feat-1256-compare-ui-rewire): Fluss-Prototyp (Ortsvergleich
  Fluss.html) als Verdrahtungs-SSoT eingearbeitet — Inline-Edit im Hub,
  kein separater Edit-Screen im Zielbild, Create→Detail-Redirect. Auslöser:
  PO-Hinweis. Konkret: neue Scheibe 2 (Fluss-Verdrahtung, größtenteils
  Verifikation bereits implementierter Übergänge), Scheiben 6/7 signifikant
  erweitert um Inline-Edit-Parität (Orte/Idealwerte/Versand, zwei neue
  LoC-Override-Kandidaten), neue Scheibe 9 (gated Redirect-Rückbau von
  `/compare/{id}/edit`) angehängt. Bestehende ACs 1-24 unverändert
  (Nummerierung fortgeführt statt neu vergeben), 16 neue ACs (25-40), davon 15 scheiben-spezifisch und 1 scheiben-übergreifend
  ergänzt. Gesamt-Scheibenzahl 7 → 9, LoC-Schätzung ~840 → ~1220.
- 2026-07-13 (feat-1256-compare-ui-rewire, Vollsichtung): Zweite
  Verdrahtungs-Quelle `body-20-canonical-ia-navigation.md` bestätigt den
  Fluss-Prototyp wörtlich (Reconciliation-Note: Wizard-Edit-Modus
  verworfen, Bearbeiten läuft über Hub-Tabs, `/bearbeiten` leitet auf
  `?tab=…` um) — als zweite kanonische Quelle in Source aufgenommen;
  `nav-map.jsx` (stale Wizard-Edit-Aussage) und `SOLL-COVERAGE.md`
  (kennt Compare-Editor/Korridor-Screens nicht) explizit als
  NICHT-Quelle markiert. `MOCK_COMPARE_SUBS` (`mock-locations.jsx:113-215`)
  als maßgebliche Datenmodell-Referenz identifiziert, `MOCK_COMPARE_ROWS`/
  `MOCK_COMPARE_PRESETS` (rank/score-Reste) als NICHT-Quelle. Neue
  Datenmodell-Mapping-Tabelle (`layout{}` ↔ `display_config.channel_layouts`,
  `ideals[].weight` ↔ Corridor-Priorität) ergänzt. Design-`CLAUDE.md`
  (Abschnitt „Orts-Vergleich = stehender Monitor") als Dependency
  aufgenommen. Alarme-Tab-Known-Limitation (KL-2) revidiert: Tab bleibt
  vorerst unangetastet (kein Scope), Zielbild = Auflösung in
  Wertebereiche-Tab (Korridor-`notify`) + Versand-Tab
  (`AlertChannelPicker`), Rest-Config → Design-Request „Frage 5", eigene
  Auflösungs-Scheibe explizit als Out-of-Scope/Folge-Arbeit benannt statt
  eingeplant. Neue Umsetzungsregel „Stale-Spuren (`timeWindow`) nicht
  mitkopieren" ergänzt. Auslöser: PO-Hinweis nach Vollsichtung der
  restlichen Handoff-Dateien.
- 2026-07-13 (feat-1256-compare-ui-rewire, Code-Teilungs-Invariante):
  PO-Bekräftigung „möglichst viel Code zwischen Trip und Ortsvergleich
  teilen; Compare-Editor funktioniert wie Trip-Editor" als geschäftsweite,
  prüfbare Invariante (CLAUDE.md § „Trip/Ortsvergleich-Code-Teilung",
  frisch committed auf `main`) eingearbeitet. Konkret: neue Constraints-
  Liste mit der Invariante als erstem Eintrag; neues scheiben-
  übergreifendes AC-40 (Adversary-Prüfpunkt + Review-Grep je Scheibe);
  Scheiben 4/6/7/8 explizit umformuliert, welcher geteilte Baustein
  konsumiert wird (`LayoutTab`, `CorridorEditor`, `VersandTab`) statt neuer
  Bespoke-Formulare — löst dabei das frühere Offen-Risiko KL-6 auf und
  deckt einen zusätzlichen, unabhängig gefundenen Verstoß gegen die
  Invariante im heutigen Hub-Versand-Bereich auf (Bespoke-Nachbau statt
  `VersandTab`-Konsum). LoC-Schätzung für Scheibe 6/7 leicht gesenkt
  (~1220 → ~1200 gesamt) durch „konsumieren statt bauen". Auslöser:
  PO-Bekräftigung.
