---
entity_id: rework_2881_design_system_bereinigung
type: feature
created: 2026-11-09
updated: 2026-11-10
status: approved
version: "1.0"
workflow: rework-2881-design-system
tags: [frontend-only, design-system, adr, doku, trip-compare-teilung, design-audit-2026-11-09]
---

# Design-System auf Trip- und Vergleichsseiten durchsetzen, widersprüchliche Vorgaben bereinigen (Issue #2881)

## Approval

- [x] Approved (PO Henning, 2026-11-09, Freigabe per AskUserQuestion)

## Purpose

Das Audit vom 9.11.2026 fand zwei Arten von Problemen:

- **Teil 1, Verstöße gegen geltende Regeln** (Charter §5/§7, AP-001, TOKENS.md, ADR-0110): native Eingabefelder (Datum zeigt im deutschen UI „11/19/2026“), Häkchen-Symbole ✓ und ⊘, „+ Neuer Trip“ in Orange statt Ink, Tippflächen unter 44 px am Handy, eine nicht definierte Hilfsklasse `.mono` (rund 118 Stellen meinen Mono-Schrift und bekommen Inter Tight), hart codierte Werte.
- **Teil 2, Vorgaben, die sich widersprechen oder veraltet sind:** Reiterleiste (ADR-0109 gegen Spec #2845 gegen Ist), Listen (Charter verlangt Kacheln, beide Listen sind Tabellen), zwei verschiedene Handy-Reiterleisten ohne gemeinsame Vorgabe, Fortschritts-Segmente unter 3:1, Soll-Bilder aus Juni 2026 (zeigen den entfernten Signal-Kanal), COPY.md und Charter mit „Tour“ und 4 Navigationspunkten, Tabu-Begriffe im UI.

**Leitlinie:** Teil 2 wird per **neuem ADR-0111** entschieden und dokumentiert (keine stille Abweichung); danach wird Teil 1 und der Code an die bereinigten Vorgaben angeglichen. Es gilt: PO-Entscheidungen und angenommene ADRs schlagen ältere Charter-/Copy-Texte; das Leitprinzip „hoher Kontrast“ schlägt weiche Optik.

**Nicht hier:** Fundstellen nur in den Reitern Wertebereiche, Alarme, Layout und Wetter-Metriken (Preset-Leiste, Kanal-Reiter, Häkchen der Grundauswahl, `--g-line` in `AlarmeTab`, toter Code `alerts-tab/`) entfallen oder werden mit #2794 neu gebaut; sie werden dort als Eingabe vermerkt. Native Felder außerhalb der Trip-/Vergleichsseiten (Konto, Admin, GPX-Upload) kommen als Sammel-Eintrag in #1199.

## Entscheidungen ADR-0111 (Teil 2)

1. **Hub-Reiterleiste am Computer:** maßgeblich ist ADR-0109 Punkt 7 (vom PO mit Mockup Fassung 3 angenommen): **eine Grundlinie in `--g-rule`, kein Kasten**, Reiter 13 px/500, aktiver Reiter 600 mit 2-px-Unterstrich `--g-accent`, Zähler Mono 10 px neutral, Radius 3 px. Inaktive Reiter bleiben `--g-ink` (aus #2845, Kontrast). Die abweichenden Werte aus Spec #2845 (14 px, Linie `--g-ink-faint`, aktiv 500) werden damit abgelöst; die Gleichheit Trip/Vergleich aus #2845 bleibt. Der Kasten entsteht heute, weil die globale Regel `[data-slot="segmented"]` aus `app.css` auf `MTabBar` durchschlägt; `MTabBar` setzt Rahmen und Radius künftig ausdrücklich zurück.
2. **Listen:** Trip-Liste und Vergleichsliste sind **Tabellen** (`ListTable`), am Handy Karten-Zeilen wie heute. AP-003 („Kachel-Grid, keine Tabelle“) und Charter §3 werden für diese beiden Listen abgelöst. Grund: beide Listen sind heute gleich gebaut (Parität), die Tabelle zeigt Status, Zeitraum und Versand vergleichbar, und das Trip-Soll zeigt selbst eine Tabelle.
3. **Reiterleisten:** Im **Hub** gibt es genau eine Leiste, `MTabBar` (Computer Unterstrich, Handy Pillen, ADR-0109). Beim **Anlegen** gibt es genau eine Leiste, `AnlegeReiter` aus #2880 (Unterstrich auf allen Breiten), weil die Schritte eine Reihenfolge mit Zuständen „erledigt“ und „gesperrt“ haben und keine frei wählbaren Reiter sind. Eine dritte Leiste ist nicht zulässig.
4. **Fortschritts-Segmente beim Anlegen:** erledigt `--g-accent` (3,94:1, erfüllt die Nicht-Text-Schwelle), offen als 1-px-Kontur in `--g-ink-3` (5,13:1) ohne Füllung statt Fläche in `--g-rule` (1,4:1). Erledigt = gefüllt, offen = nur Umriss: der Unterschied hängt nicht allein an der Farbe. Der Zähler „n von 5“ trägt dieselbe Information als Text (seit #2879 in `--g-ink-3`).
5. **Soll-Bilder:** `claude-code-handoff/current/soll/*.png` gelten als **historisch** (Stand Epic #575, Juni 2026). Maßstab sind `docs/reference/design_system.md`, das Mockup Fassung 3 (`docs/context/einstellungen_neu/seiten/mockup-hub-fassung3.html`) und die Playwright-Paritäts- und Kontrasttests. `design_fidelity_diff.py` und der Hook `pre_issue_close_design_gate.py` werden außer Dienst gestellt (Hook-Eintrag in `.claude/settings.json` entfernt, Skripte bleiben mit Vermerk liegen). Regel-Budget: das Gate wird durch die Kontrast- und Paritätstests aus #2879/#2880 ersetzt.
6. **COPY.md und Charter:** an die späteren PO-Entscheidungen angeglichen: Produktbegriff **Trip** (Glossar ADR-0104, „Tour“ verboten), Navigation wie die heutige Seitenleiste, Hauptaktion **Ink** (ADR-0110), Accent unter Text als `--g-accent-deep` (#2879), Kachel-Pflicht gestrichen (Punkt 2). Die Tabu-Liste in COPY.md bekommt „Drafts“, „Alert-Trigger“ und „Alerts justieren“.
7. **Zustands-Symbole:** statt ✓ und ⊘ der Baustein `Dot` (Charter §5) plus Text; gesperrt heißt `aria-disabled` und ein Punkt in `--g-ink-4`, erledigt ein Punkt in `--g-good`.

## Umfang Teil 1 (Code)

- **R2 Native Felder → Design-System-Bausteine (bits-ui, schon im Projekt):**
  - Datum: neuer Baustein `molecules/DatumFeld.svelte` (bits-ui `DatePicker`: Feld mit Tag/Monat/Jahr-Segmenten und Kalender im Popover, Format nach Konto-Sprache wie im übrigen UI, Wochenbeginn Montag). Ersetzt `input[type=date]` beim Trip-Anlegen (Computer und Handy) und in `edit/StageDateField.svelte` (Etappen-Reiter, `StageCardM`, `PauseStageView`).
  - Uhrzeit: `molecules/UhrzeitFeld.svelte` (bits-ui `TimeField`, 24 h). Ersetzt `input[type=time]` in `edit/StageTimeField.svelte`.
  - Auswahl: `ui/select/Select.svelte` wird auf bits-ui `Select` (eigene Liste statt nativem `<select>`) umgebaut, mit Eigenschaft `options: {value,label}[]`; die Aktivität beim Trip-Anlegen nutzt sie. Andere Aufrufer von `Select` werden mitgezogen, damit es nur eine Art gibt.
  - Mail-Format (Voll/Kompakt) in `shared/MailInhaltCard.svelte`: `Segmented` statt Radio-Knöpfen.
- **R3 Symbole:** ✓ und ⊘ auf Trip-/Vergleichsseiten und in den Katalogen `de`/`en` entfernt: `ui/SaveIndicator.svelte` („Gespeichert“ mit `Dot`), Anlegen-Hinweise („Name fehlt“, „min. 2 Orte auswählen“, „Alle GPX geladen“ usw.), Zustandsmarker in `AnlegeReiter` (aus #2880), `routes/_home/StartklarCheckliste.svelte`.
- **R4 „+ Neuer Trip“:** auf Trip-Liste, Vergleichsliste, Startseite (auch im Leerzustand) dieselbe Variante **primary (Ink)** für „Neuer Trip“ und „Neuer Vergleich“; keine Accent-Variante für Anlege-Aktionen.
- **R5 Tippflächen am Handy (unter 900 px) mindestens 44 × 44 px:** Zurück-Link (`atoms/BackLink.svelte`, Hub und Anlegen), „Mit Standardwerten speichern“ (`shared/StandardwerteSpeichernKnopf.svelte`), ⓘ-Knöpfe (`molecules/BegriffErklaerung.svelte`: Tippfläche 44 × 44 bei unverändert kleinem Zeichen, ohne die Zeile zu verschieben), Schnellwahl-Chips der Zustellung (`shared/versand-tab/VTSchedulePlan.svelte`).
- **R6 Hilfsklassen:** `.mono` (Mono-Schrift mit `font-feature-settings: "tnum", "zero"`) und `.tnum` in `frontend/src/app.css` nach TOKENS.md §12.
- **R7 Werte:** `AnlegeRahmen`/`AnlegeFortschritt`/`HubKopf` auf das 4-px-Raster (14→16, 22→24, 7→8, 10→12 px); Inline-Hex auf Trip-/Vergleichsseiten durch Tokens (`#fff` → `--g-paper` bzw. `--g-card`, `#8a6210` → `--g-warn-deep`).
- **Hub-Reiterleiste nach ADR-0111 Punkt 1** (`mobile/MTabBar.svelte`), Fortschritts-Segmente nach Punkt 4 (`AnlegeFortschritt.svelte`).
- **Tabu-Begriffe im UI** (Kataloge `de`/`en`): „Drafts“ → „Entwürfe“ (EN „Drafts“ bleibt), „Alert-Trigger“ → „Alarm-Auslöser“ (EN „Alert trigger“), „Alerts justieren“ → „Alarme einstellen“ (EN „adjust alerts“). Glossar zuerst ergänzen.

## Source

- **Neu:** `docs/adr/0111-design-vorgaben-bereinigt-audit-2026-11.md`, `frontend/src/lib/components/molecules/DatumFeld.svelte`, `frontend/src/lib/components/molecules/UhrzeitFeld.svelte`, `frontend/e2e/design-system-trip-vergleich.spec.ts`.
- **Geändert:** wie im Umfang genannt; dazu `docs/adr/README.md`, `docs/adr/0109-*.md` (Verweis auf 0111), `docs/specs/modules/rework_2845_hub_reiterleiste.md` (Changelog-Vermerk), `docs/design-system/CHARTER.md`, `docs/design-system/COPY.md`, `docs/design-system/ANTI-PATTERNS.md` (AP-003 abgelöst), `docs/reference/design_system.md` (veralteter Satz zu `--g-card`/`--g-rule`, Reiterleisten, Listen), `docs/reference/i18n_glossar.md`, `claude-code-handoff/current/soll/SOLL-COVERAGE.md` (Vermerk historisch), `.claude/settings.json` (Hook-Eintrag Design-Gate), `docs/reference/gates_und_ratschen.md` (Gate außer Dienst).

> **Schicht:** Frontend und Doku. Kein Go, kein Python, keine Daten (Datum und Uhrzeit werden im selben Format wie bisher gespeichert: `YYYY-MM-DD`, `HH:MM`).
> **Trip/Ortsvergleich-Teilung:** neue Bausteine unter `molecules/`, von beiden Seiten nutzbar; keine einseitige Komponente.
> **Mandantentrennung / Kanäle:** nicht betroffen.

## Estimated Scope

- **LoC:** ca. +450 / -250 Code, ca. +350 Test, Doku ca. +250
- **Files:** ca. 25
- **Effort:** high (wird in zwei Lieferungen geteilt: A = ADR-0111, Doku, R4, R6, R7, Reiterleiste, Segmente, Tabu-Begriffe; B = R2, R3, R5)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| #2880 (`AnlegeReiter`) | Vorgänger | R3-Marker sitzen dort |
| #2879 | Vorgänger | Accent-deep-Regel, Zähler `--g-ink-3` |
| bits-ui 2.x `DatePicker`, `TimeField`, `Select` | Bibliothek | vorhanden |
| ADR-0109, ADR-0110 | ADR | werden durch ADR-0111 präzisiert |
| #2794 | Folge-Scheibe | übernimmt die Reiter, die hier ausgenommen sind; Reiterleiste ist danach schon nach Soll |

## Implementation Details

1. ADR-0111 schreiben, Index und Querverweise nachziehen (Index-Test grün).
2. Lieferung A, dann B; je eigener RED-Nachweis.
3. Datum/Uhrzeit: Wert nach außen weiterhin als String `YYYY-MM-DD`/`HH:MM`, damit Speicherpfade unverändert bleiben (Read-Modify-Write bleibt unberührt).
4. Pflicht-Mutationen: (a) in `MTabBar` den Rahmen-Reset entfernen (Kasten kehrt zurück), (b) `.mono`-Regel löschen, (c) „+ Neuer Trip“ im Leerzustand zurück auf `accent`, (d) BackLink-Höhe am Handy zurück auf 36 px, (e) `DatumFeld` gibt das Datum im Format `MM/DD/YYYY` nach außen, (f) ein ✓ in `SaveIndicator` zurück. Jede muss einen AC rot machen.

## Expected Behavior

- **Input:** Trip-/Vergleichslisten, Hubs (Kopf, Reiterleiste, Etappen-Reiter, Zustellung), Anlegen.
- **Output:** keine nativen Datums-/Uhrzeit-/Auswahl-/Radio-Felder, keine ✓/⊘, gleiche Anlege-Aktion, Tippflächen ≥ 44 px am Handy, Mono-Schrift wo gemeint, Reiterleiste ohne Kasten; Doku ohne Widersprüche.
- **Side effects:** Zähler, Kürzel und Datumsangaben an rund 118 Stellen erscheinen jetzt in Mono-Schrift (so war es gemeint). Die Hub-Reiter am Computer werden 1 px kleiner (13 statt 14 px), der aktive Reiter fett.

## Acceptance Criteria

- **AC-1:** Given ein deutschsprachiger Nutzer beim Trip-Anlegen / When er das Startdatum über das Datumsfeld wählt (Kalender öffnen, 19. November 2026 anklicken) und den Trip anlegt / Then zeigt das Feld „19.11.2026“, der Kalender beginnt mit Montag, und nach dem Neuladen des Trips steht als Startdatum der 19.11.2026 (gespeichert als `2026-11-19`); ein englischsprachiger Nutzer sieht das Datum im englischen Format des übrigen UI.
  - Test: Playwright `design-system-trip-vergleich.spec.ts` DS-1, Klickweg über das Popover, Prüfung über die API-Antwort und die Anzeige nach Reload; DE und EN.

- **AC-2:** Given eine Etappe im Etappen-Reiter / When der Nutzer Datum und Startzeit über die neuen Felder ändert (z. B. 20.11.2026, 07:30) und die Seite neu lädt / Then sind beide Werte gespeichert und werden im 24-Stunden-Format angezeigt, am Computer und am Handy.
  - Test: Playwright DS-2.

- **AC-3:** Given Trip-Liste, Vergleichsliste, beide Hubs (Übersicht, Etappen bzw. Orte, Zustellung) und beide Anlege-Abläufe / When die Seiten bei 1280 × 900 und 390 × 844 gerendert sind / Then enthält keine davon ein natives `input[type=date]`, `input[type=time]`, `input[type=radio]` oder ein sichtbares natives `<select>`, und kein sichtbarer Text enthält „✓“ oder „⊘“.
  - Test: Playwright DS-3, Abfrage der gerenderten Seite (DOM des Browsers) und `innerText`.

- **AC-4:** Given die Aktivitätsauswahl beim Trip-Anlegen und das Mail-Format in der Zustellung / When der Nutzer per Maus und per Tastatur (Pfeiltasten, Enter) einen anderen Wert wählt und speichert / Then ist der Wert nach dem Neuladen gespeichert, und die Auswahl ist per Tastatur bedienbar (Rolle `listbox` bzw. `radiogroup`, Fokus sichtbar).
  - Test: Playwright DS-4.

- **AC-5:** Given Trip-Liste und Vergleichsliste, jeweils leer und gefüllt, Computer und Handy, sowie die Startseite im Leerzustand / When die Anlege-Aktion („Neuer Trip“ bzw. „Neuer Vergleich“) betrachtet wird / Then hat sie auf allen diesen Seiten dieselbe Knopf-Variante mit Ink-Fläche (rgb(26, 26, 24)) und heller Schrift.
  - Test: Playwright DS-5, `getComputedStyle().backgroundColor` und `data-variant`.

- **AC-6:** Given die Hubs und Anlege-Seiten bei 390 × 844 Pixel / When Zurück-Link, „Mit Standardwerten speichern“, jeder ⓘ-Knopf und jeder Schnellwahl-Chip der Zustellung vermessen werden / Then ist jede Tippfläche mindestens 44 Pixel hoch und 44 Pixel breit, und keine Seite läuft waagerecht über.
  - Test: Playwright DS-6, `boundingBox()`.

- **AC-7:** Given ein Element mit Klasse `mono` (z. B. der Fortschrittszähler beim Anlegen) / When seine berechnete Schrift gelesen wird / Then ist die Schriftfamilie die Mono-Schrift aus `--g-font-mono` und `font-feature-settings` enthält `"tnum"`.
  - Test: Playwright DS-7.

- **AC-8:** Given Trip-Hub und Vergleichs-Hub bei 1280 × 900 / When die Reiterleiste vermessen wird / Then hat die Leiste oben, links und rechts keinen Rahmen und keinen Radius, unten eine 1-px-Linie in `--g-rule` (rgb(216, 211, 194)); inaktive Reiter 13 px, Stärke 500, Farbe `--g-ink`; der aktive Reiter Stärke 600 mit 2-px-Unterstrich in `--g-accent`; Zähler in Mono 10 px, neutral; bei Trip und Vergleich gleich.
  - Test: Playwright DS-8 (Festwerte aus ADR-0111) und die angepassten Fälle in `hub-tab-bar.spec.ts` (Gleichheit Trip/Vergleich bleibt).

- **AC-9:** Given das Anlegen bei 1280 × 900 mit zwei von vier erledigten Abschnitten / When die Fortschritts-Segmente gemessen werden / Then sind erledigte Segmente `--g-accent`, offene haben keine Füllung und eine 1-px-Kontur in `--g-ink-3`, und beide erreichen gegen den Seitengrund mindestens 3:1; der Zähler daneben nennt den Stand als Text.
  - Test: Playwright DS-9.

- **AC-10:** Given ein deutschsprachiger Nutzer / When Trip-Liste und Trip-Übersicht geöffnet werden / Then erscheinen die Wörter „Drafts“, „Alert-Trigger“ und „Alerts justieren“ nirgends; an ihrer Stelle stehen „Entwürfe“, „Alarm-Auslöser“ und „Alarme einstellen“.
  - Test: Playwright DS-10, `innerText` der Seiten.

- **AC-11:** Given die Doku / When der ADR-Index geprüft wird / Then ist ADR-0111 im Index, ADR-0109 und AP-003 verweisen darauf, und der Index-Konsistenztest ist grün.
  - Test: `uv run pytest tests/test_adr_index_drift.py` (bestehender Kern-Test, `# doc-compliance-test`-Ausnahme gilt für Doku).

## Test Plan

- Playwright DS-1 bis DS-10 am isolierten Stack, DE und EN wo Texte betroffen sind.
- Bestehende Tests, die native Felder oder feste Werte ansprechen (`StageDateField`, `hub-tab-bar.spec.ts` 14 px, Anlege-Abläufe mit `fill()` auf `input[type=date]`), werden auf die neuen Bausteine umgestellt, nicht gelöscht.
- RED-Nachweis: DS-1, DS-3, DS-5, DS-6, DS-7, DS-8, DS-10 schlagen vor der Umsetzung fehl.

## Definition of Done

- AC-1 bis AC-11 grün, Adversary VERIFIED mit den sechs Pflicht-Mutationen gefangen, Fresh-Eyes-Blick auf Screenshots.
- ADR-0111 akzeptiert im Index; Kommentar in #2794, dass Reiterleiste (Punkt 1) und die ausgenommenen Fundstellen dort bzw. hier erledigt sind.
- Je Lieferung ein PR mit allen 6 CI-Checks grün gemergt; Staging-Prüfung und Prod-Deploy über die Server-Sitzung.

## Known Limitations

- Native Felder in Konto, Admin und GPX-Upload bleiben vorerst (Sammel-Eintrag #1199).
- Neue Soll-Bilder werden nicht erstellt; Maßstab sind Doku, Mockup und Tests (ADR-0111 Punkt 5).
- Scheitert das Speichern, während ein Segment des Datumsfelds angefangen ist (z. B. Monat „1“), zeigt das Feld wieder den gespeicherten Wert und die angefangene Ziffer ist verworfen; die nächste Ziffer beginnt das Segment neu (bits-ui: „2“ ergibt dann Februar und springt ins Jahr statt Dezember). Kein Datenverlust, Anzeige = gespeicherter Wert (Adversary Runde 2, P11).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0111 (neu), präzisiert ADR-0109 Punkt 7 und ADR-0110, löst AP-003 und Charter §3 für die beiden Listen ab.
- **Rationale:** mehrere sich widersprechende Vorgaben; eine Entscheidung wird nie still geändert (CLAUDE.md).

## Changelog

- 2026-11-09: Initial spec (Issue #2881).
- 2026-11-09: Vom PO freigegeben.
- 2026-11-09: Lieferung B umgesetzt (R2, R3, R5; AC-1/2/3/4/6, DS-1/2/3/4/6, Pflicht-Mutationen d–f). Englisches Datumsformat im DatumFeld: Segmente Tag zuerst (`19/11/2026`, en-GB) wie die Tag-zuerst-Reihenfolge im übrigen UI (`19 Nov 2026`); die Segmentfelder sind numerisch. Uhrzeit immer 24 h. Native Felder bleiben nur in den ausgenommenen Reitern (DayWindowCard, Alarme) und in Konto/Admin/GPX-Upload (#1199).
- 2026-11-10: AC-9 „zwei von fünf“ → „zwei von vier“ Abschnitten (Folge der Anlege-Kette aus #2794 S3a, keine Produktänderung). Fix-Loop Lieferung B nach Adversary (F-B1 bis F-B6): Segmentfelder melden nur fertige Segmente (getippte Ziffern gezählt, kein Ruhe-Zeitgeber), Leeren beim Anlegen ergibt „Startdatum fehlt“, an der Etappe springt ein geleertes/unvollständiges Feld beim Verlassen auf den gespeicherten Wert zurück, Startzeit leeren ⇒ 08:00; neue Fälle DS-1 Leeren, DS-2 Etappenwechsel/Zwischenstände/Leeren/en, DS-4 Standard-Option und rollendes tabindex; DS-5 leer mit frischem Konto. ✓ der Grundauswahl im Reiter Wetter bleibt ausgenommen (Nicht hier, #2794).
- 2026-11-10: Fix-Loop 2 Lieferung B nach Adversary Runde 2 (F-C1 bis F-C4): ein angefangenes Jahr („202“) wird an der Etappe nie gespeichert (Anzeige springt zurück), beim Anlegen ergibt es „Startdatum fehlt“; ein unverändert neu getipptes Datum schreibt nichts; ein Segment, in das man später zurückkehrt oder in dem man per Rücktaste eine Ziffer löscht, gilt als angefangen; scheitert das Speichern mitten im Tippen, schreibt das Verlassen den alten Tipp-Stand nicht nach. Jede Schutzstelle der Segmentfelder ist per Mutation an der Wirkstelle belegt oder entfernt (Beleg: `docs/artifacts/rework-2881-design-system/mutationen-B.txt`); wirkungslos und entfernt sind u. a. Sperre und Neuaufbau beim fremden Wertwechsel. Neue Fälle DS-2 Jahr angefangen, dasselbe Datum/dieselbe Startzeit, Rückkehr, Rücktaste, Rücknahme beim Tippen (Datum und Startzeit), Etappenwechsel Startzeit, Startzeit neu tippen; DS-1 Jahr angefangen und Neueintippen. P11 (Rücknahme mitten im Monat) als Known Limitation.
