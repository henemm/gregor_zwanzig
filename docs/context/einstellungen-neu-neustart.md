# Context: einstellungen-neu-neustart (#2913, Epic #2791)

## Request Summary
Neustart „Einstellungen neu“ (PO-Entscheidung 2026-11-10): erst ADR-0112 (Oberflächen nur aus Design-System-Bausteinen, fehlende zuerst ins System, kein Styling außerhalb der Tokens, Wächter blockt beim Merge), dann Wächter + automatische Elementliste aus dem Mockup, dann Bausteine, dann die Reiter Wetter und Zustellung als senkrechte Scheiben (a)–(e). Abnahme durch die AI gegen das Mockup (Trip und Orte, DE und EN), Meldung an den PO mit Bild erst bei Abschluss.

## Stand der Lieferung (origin/main 18a18a79e)
- Geliefert: S1 Ampel im Briefing, S2a/S2b Alarm folgt der Ampel (`alarm_ab`, Migration #2860), #2794 S3a Teil-PR 1 (Backend: Vorlagen `kind`/Standard/Duplikat, Katalogfelder, Abweichungszähler, horizons-Migration) und Teil-PR 2 (Reiterleiste Übersicht · Etappen/Orte · Wetter · Zustellung, Umleitungen, Anlege-Ketten, Übergangsreiter Zustellung).
- Offen: alles Sichtbare — S3a Teil-PR 3 (Reiter Wetter) und 4 (Entfernen), S3b (#2795), S4 (#2796), S5 (#2797), S6 (#2798), S7–S9 (#2799–#2801).
- Spec `docs/specs/modules/feat_2794_s3a_reiter_wetter.md` (status draft, AC-1…AC-36, 4 Teil-PRs) ist inhaltliche Quelle für Scheiben (a)–(c); Analyse dazu `docs/context/feature-2794-s3a-reiter-wetter.md` (u. a. Alarmquellen-Gate muss `alarm_ab` anerkennen — nach S2b-Merge erneut prüfen).

## Soll: Mockup Fassung 3
`docs/context/einstellungen_neu/seiten/mockup-hub-fassung3.html` (676 Zeilen; online https://claude.ai/artifact/Lfo1pdrjrgcA3XMLLJrrwQ). Eine Seite, Inhalt per JS aus Datentabellen (`CTX`, `TRIP_METRICS`, `ORTE_METRICS`, `VORLAGEN`, `KZ`, `COLL`, `SIDES`, `EX`, `konto()`), Render-Funktionen `renderHead`, `viewWetter`, `viewZustellung`, `viewEtappen`, `viewOrte`. Rahmenleiste `.frame` (nur Mockup) schaltet Kontext Trip/Orte, Zustand normal/lädt/Ladefehler/Konto mit Lücken, Marken. **Nur Deutsch** — EN-Elementliste muss aus dem i18n-Katalog abgeleitet werden. Eigene `:root`-Tokens im `--g-*`-Stil plus `--a-green/yellow/orange/red` (Ampel), `--f-ui`, `--f-mono`.

Elemente in Reihenfolge:
- **Kopf (alle Reiter):** Brotkrumen; Kebab ⋮ (Aktivieren nur Entwurf, Pausieren/Fortsetzen, Archivieren…, Löschen… mit Bestätigung); „Test schicken ▾“ (Trip: Morgen/Abend-Umschalter; je Kanal E-Mail/Telegram/SMS/Premium-SMS mit Empfänger oder „gesperrt: … Im Konto X →“; „Alle eingerichteten Kanäle“; „Test-Alarm“); Eyebrow, H1 + Status-Pill (+ „Aktivieren“ bei Entwurf); Meta-Zeile; Reiter mit Badge.
- **Wetter:** H2 + Lead (Skelett / warnbox „Erneut laden“) → Vorlage-Karte (Picker „Alpen-Trekking ▾ unverändert / N Abweichungen“, Gruppen Vorlagen (7) / Eigene, Bestätigung „übernehmen?“, „Als eigene Vorlage speichern“, „Auf „X“ zurücksetzen“, Speicher-Dialog mit „Als Standard für neue Trips“) → Metrik-Karte („Alarm ab für alle“ Nie/Gelb/Orange/Rot + Zähltext, Info-warnbox wenn keine alarmiert; Gruppen Temperatur / Wind / Niederschlag & Gewitter / Himmel & Sicht / Schnee & Höhe; Metrik-Zeile `.mr`: „−“, Name + Einheit·Art, Ampel-Leiste mit Grenzwerten, „Alarm, wenn … · grün: a bis b“, „Alarm ab“-Segment (Gewitter Nie/Orange/Rot, Vorbote „kein Alarm (Vorbote)“), „Grenzen ändern“/„Fertig“ mit Feldern unten/oben je `SIDES` bzw. Gewitter mittel/hoch, Hinweis „Abweichend von der Vorlage“; Windrichtung „keine Ampel, nur Anzeige“; „Nicht im Briefing:“ + Chips „+ Metrik“) → Schalter-Karte Amtliche Warnungen / Radar-Regen → Karte „Inhalt je Kanal und Fläche“ (Segment E-Mail/Telegram/SMS/Premium-SMS/3-Tages-Ausblick, Orte zusätzlich Stundenverlauf; Zeile Amtliche Warnungen fix; je Metrik Griff, „Name (Col | Kürzel)“, Roh/Einfach, Beispielwert, Hinweis, Schalter; Zeichenbudget SMS/Premium-SMS, Kürzel-Legende; „Weitere Einstellungen für X“) → „Anpassen“ (Tagesfenster).
- **Zustellung:** H2 + Lead → zwei Karten Morgen-/Abend-Briefing (Uhrzeit + Schalter) → Laufzeit (Trip: Text + „Etappen öffnen →“; Orte: Bis auf Weiteres / Bis Datum) → warnbox „Kein Kanal für Briefings/Alarme an.“ → Kanal-Karte (Kopf „Briefings über N Kanälen · Alarme über N Kanälen“, Tabelle Kanal | Briefing | Alarme | „Alarm schon ab Dringlichkeit“ gering/mittel/hoch, Zeilen E-Mail/Telegram/SMS/Premium-SMS mit Status-Punkt, Empfänger, „Im Konto … →“, „gesperrt: Rückadresse verfallen“; Legende SMS mittel / Premium-SMS hoch) → Stille Stunden → „Anpassen“ (Mindestabstand Alarme).
- **Etappen:** Fortbewegung-Segment, Tempo flach/Aufstieg, E1–E4 mit Gehzeit + „Tempo ändern“. **Orte:** „+ Ort hinzufügen“, Liste mit „entfernen“. Übersicht nur Platzhalter.

Maschinenlesbarkeit: statisches HTML enthält die Elemente nicht → Elementliste nur durch Rendern je Kombination (Kontext × Zustand × Reiter × Kanal-Segment × offene Bearbeitung) und DOM-Auslesen (Playwright) oder Auswertung der JS-Tabellen. Teilweise stabile Haken: `data-sw`, `data-seg`/`data-v`, `data-row`, `data-tab`, `data-send`, aria-Rollen/-Labels; Abschnitte ohne IDs.

Zerlegungs-Vorschlag: Atome Btn (sm, ghost/accent/quiet/primary), Switch, Segmented (optional Farbpunkt), Pill, Chip, Input (Zeit/Zahl), Dot, Kürzel, Eyebrow, Checkbox · Moleküle lrow (~22×), Field, Ampel-Leiste, Grenzen-Gruppe, Warnbox, Bestätigung, Menü-Eintrag (mit gesperrt), Zeit-von-bis + Schalter, Ausgabe-Zeile `.oi`, Abschnittskopf · Organismen Metrik-Zeile, Metrik-Karte, Vorlage-Karte, Kanal-Inhaltsliste, Kanal-Tabelle, Test-schicken-/Kebab-Menü, Hub-Kopf, Aufklapper „Anpassen“.

## Ist: heutige Seiten (frontend/)
| Datei | Relevanz |
|---|---|
| `src/routes/trips/[id]/+page.svelte` → `lib/components/trip-detail/TripTabs.svelte` | Trip-Hub, rendert Reiter |
| `src/routes/compare/[id]/+page.svelte` → `lib/components/compare/CompareTabs.svelte` | Orte-Hub (bindet `AlarmeTab`, `ChannelToggle` zusätzlich direkt ein; 7 Hex-Werte) |
| `lib/components/shared/WetterMetrikenVersandPanel.svelte` | Reiter Wetter (Übergang), bindet `WeatherMetricsTab`, `VersandTab`, `BriefingScheduleTab` |
| `shared/WeatherMetricsTab.svelte` + `weather-metrics-tab/` (`WeatherV2PresetBar` = Profil-Chips, `WeatherV2Grundauswahl` = Haken-Knöpfe, `ThresholdMetricRow`, `MultiSymbolMetricRow`, `AggregationMetricRow`, `DayWindowCard`, `SavePresetDialog`) | alte Wetter-Seite, wird ersetzt/gelöscht (10 Hex-Werte) |
| `shared/MailInhaltCard`, `OutlookLayoutControls`, `compare/CompareHourlyLayoutControls`, `layout-tab/LayoutTab` | heutiger Inhalt je Kanal / Layout → Karte „Inhalt je Kanal und Fläche“ |
| `shared/zustellung-tab/ZustellungTab.svelte` | Übergangsreiter Zustellung |
| `shared/VersandTab.svelte` + `versand-tab/` (`VTBriefingChannels` = alte Kanal-Auswahl-Karte, `VTSchedulePlan`, `VTLaufzeitRoute`, `VTLaufzeitVergleich`; `VTNextBriefing` unbenutzt) | Briefing-Zeiten/Laufzeit/Kanäle heute |
| `shared/AlarmeTab.svelte` + `alerts-tab/` (`AlertCooldownCard`, `AlertQuietHoursCard`, `AlertPreviewCard`, `AlertMetricLevelTable`, `AlertMetricChannelsBlock`), `AlertChannelPicker`, `ChannelToggle`, `TelegramKurzstilToggle` | Alarm-Kanäle, Stille Stunden, Mindestabstand heute |
| `trip-detail/WeatherV2Kanaele.svelte` | seit #736 nicht eingebunden (Leiche) |
| Test-Versand: `routes/trips/[id]/+page.svelte`, `molecules/SendConfirmDialog.svelte`, `sendConfirmModel.ts` | heutiges „Senden“ → „Test schicken ▾“ |

**Atomic-Anteil heute praktisch null:** In den Reitern werden nur `molecules/CompareLocationRow` und `molecules/BegriffErklaerung` genutzt. `organisms/PresetRail` und `molecules/ThresholdRow` existieren, laufen aber nur im Showcase `routes/_design-system/+page.svelte`. Vorhandene Bausteine: atoms (Btn, Card, Dot, Eyebrow, Input, KV, PageHeader, Pill, SectionH, Segmented, Switch, …), molecules (AlertRow, BriefingScheduleRow, BriefingTimelineRow, ChannelChip (Premium-SMS), ChannelRow, ConfirmDialog, DatumFeld, Field, Infobox, ThresholdRow, UhrzeitFeld, …), organisms (AlertsCard, MetricOffShelf, PresetRail, OutboxCard, ListTable, …). Hub-Kopf: `shared/hub-kopf/HubKopf.svelte` (ADR-0110), Reiterleiste `MTabBar` (ADR-0111). Design-Referenz-JSX: `claude-code-handoff/current/jsx/{atoms,molecules,organisms}.jsx`, `tokens.css`.

## Existing Patterns / Wächter
- Tokens: `frontend/src/app.css` (`--g-*`, Dark-Block). Doku `docs/reference/design_system.md`, `docs/design-system/` (TOKENS.md, ANTI-PATTERNS.md, COPY.md).
- Vorhandene Sperren: `frontend/src/lib/__tests__/harte_farben_waechter.test.ts` (harte Farben, Ratsche `AUSNAHMEN` darf nur sinken, `audit:exempt`), `dark_palette_kontrast.test.ts`, `ink4_waechter.test.ts`; `.claude/hooks/pendant_gate.py` (Trip/Orte-Pendant, ADR-0097). **Kein** Wächter gegen Abstände/Größen ohne Token, kein Wächter „nur Bausteine aus atoms/molecules/organisms“, kein stylelint. Design-Gate (`design_fidelity_diff.py`, `pre_issue_close_design_gate.py`) seit ADR-0111 außer Dienst → Regel-Budget: neuer Wächter ersetzt das alte Gate.
- Frontend-Unit-Tests laufen über `node --test` (kein Vitest).
- Trip/Orte teilen Code über `context="route"|"vergleich"` (ADR-0097, `pendant_gate.py`).

## Dependencies
- Upstream: Go-API Proxy, Python `/api/metrics` (Katalogfelder aus Teil-PR 1), Vorlagen-API mit `kind`, Ampel-/`alarm_ab`-Speicherung (ADR-0101, Read-Modify-Write), i18n-Katalog (ADR-0104), Konto-Kanäle (Empfänger, Rückadresse Premium-SMS).
- Downstream: E2E `frontend/e2e/s3a2794-hub-reiter-wetter-zustellung.spec.ts`, `s3a2794-zustellung-inventar-speicherweg.spec.ts`, `versand-tab.spec.ts`, `versandzeit-stundenwahl.spec.ts`, `weather-metrics-tab-autosave.spec.ts`, `weather-metrics-editor-day-range-kuerzel.spec.ts`, `layout-tab-{route,vergleich}.spec.ts`, `issue-953-alerts-autosave-tabswitch.spec.ts`, `issue-767-768-test-briefing.spec.ts`, `trip-new-versand-unter-metriken-konsole.spec.ts`; Staging-Specs `kanal-*`, `metrik-*`, `wetter-metriken-vorschau-entfernt` (je `playwright.<name>.staging.config.ts`); `tokens-and-topo.spec.ts`, `kontrast-trip-vergleich.spec.ts`, `dark-mode-alle-routen.staging.spec.ts`; Goldens F9/F10 Hub. Anlegen-Editoren (`TripNewEditor`, `CompareNewEditor`) nutzen dieselben Panels.

## Existing Specs / ADRs
- `docs/specs/modules/feat_2794_s3a_reiter_wetter.md` (draft), `feat_2794_s3a_teil2_leiste.md` (geliefert), `rework_2837_s1_hub_kopf.md`, `rework_2845_hub_reiterleiste.md`.
- ADR-0097 (Code-Teilung), 0101 (Ampel-Speicherung), 0104 (DE/EN), 0106 (Profil-Ampel), 0107 (Orte 1..n), 0108 (Vorlage/Tempo getrennt), 0109 (Reiterstruktur), 0110 (Hub-Kopf), 0111 (Design-Vorgaben, Design-Gate außer Dienst). Nächste freie Nummer: **0112**.
- Konzept `docs/context/einstellungen_neu.md`, Abgleich `docs/context/einstellungen_neu/seiten/abgleich-alt-neu.html` (Marken K/A/V/W), `grundentscheidungen.html`, `ampel-grenzen.html`.
- Kind-Issues #2794–#2801 bleiben inhaltliche Quelle; Zuordnung zu Scheiben (a)–(e) in der Analyse prüfen.

## Risks & Considerations
- **Umfang:** Das Issue ist ein Arbeitsplan über mehrere Lieferungen (ADR, Wächter, Elementliste, Bausteine, 5 Scheiben). Für /20-analyse: Schnitt festlegen — diese Workflow-Runde liefert vermutlich Schritt 1–2 (ADR-0112 + Wächter + Elementliste), Bausteine/Scheiben folgen als eigene Workflows je Scheibe.
- **Mockup nur DE, nur per JS gerendert:** Elementliste braucht Playwright-Rendering je Kombination; EN-Soll muss aus dem Katalog kommen, nicht aus dem Mockup.
- **Wächter-Ratsche:** heute fast 100 % eigene Komponenten mit lokalem Styling → Wächter muss als Ratsche (Bestand darf nur sinken) oder auf neue/berührte Dateien beschränkt starten, sonst ist CI sofort rot.
- **Mockup-Tokens ≠ App-Tokens:** `--a-*` Ampel-Farben, `--f-ui`/`--f-mono` existieren evtl. nicht in `app.css` → als Tokens ins System aufnehmen statt lokal.
- **Alarmquellen-Gate** (`trip_alert.py`, `compare_alert.py`) muss `alarm_ab` als Quelle anerkennen, bevor die neue Oberfläche nur `alarm_ab` schreibt (vor Scheibe (b) prüfen).
- **Datenerhalt:** Vorlagen-/Ampel-Schreibwege Read-Modify-Write (#102); Zwei-Nutzer-Tests bei datenbewegenden Endpoints.
- **Parallele Stränge pausieren:** Dark Mode #2400 / Design-Politur ruhen bis (a)–(d) stehen; offene PRs #2874, #2846 berühren evtl. Hub-Kopf.
- Worktree-HEAD liegt hinter `origin/main` (18a18a79e) → vor Implementierung `merge --ff-only`.
- Prüf-Agent höchstens zwei Runden je Scheibe; Abschluss nur bei lückenloser Elementliste DE und EN, Meldung an PO mit Bild.

## Analysis

### Type
Feature (Arbeitsplan-Issue; dieser Workflow liefert Schritt 1–2 des Plans)

### Schnitt (Tech-Lead-Entscheidung)
Dieser Workflow: **ADR-0112 + Bausteine-Wächter + Elementlisten-Generator + Staging-Abgleich (Bericht) + Prüf-Agent-Definition.**
Eigene Folge-Workflows: Bausteine (inkl. Ampel-Tokens `--g-ampel-*` mit Dark-Block), danach Scheiben (a)–(e) je ein Workflow mit eigener Spec, Elementlisten-Teilmenge (`scope`) und Prüf-Agent-Lauf (max. 2 Runden). Alarmquellen-Gate (`alarm_ab`) gehört in Scheibe (b).

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| docs/adr/0112-oberflaechen-nur-aus-design-system-bausteinen.md | CREATE | Regel: nur Bausteine, fehlende zuerst ins System, nur Tokens, Wächter blockt beim Merge; Prüfdatum + Löschbedingung |
| docs/adr/README.md | MODIFY | Index-Zeile 0112 (test_adr_index_drift.py) |
| docs/adr/0111-*.md | MODIFY | „Ergänzt durch: ADR-0112“ |
| docs/design-system/ANTI-PATTERNS.md | MODIFY | AP-006/007/008: Vermerk „Pflicht mit Wächter, ADR-0112“ |
| frontend/src/lib/__tests__/bausteine_waechter.test.ts | CREATE | node:test, zwei Regeln (s. u.), Muster wie harte_farben_waechter |
| scripts/elementliste_aus_mockup.(ts/py) | CREATE | Playwright gegen Mockup per file://, alle Kombinationen, DOM-Auslesen |
| docs/context/einstellungen_neu/elementliste.json | CREATE | generiert, mit Mockup-Hash |
| frontend/src/lib/__tests__/elementliste_aktuell.test.ts | CREATE | CI-Check: Hash in JSON == Hash der Mockup-Datei (ohne Browser) |
| frontend/e2e/elementliste-abgleich.staging.spec.ts + frontend/playwright.elementliste.staging.config.ts | CREATE | Abgleich je Element auf Staging, Bericht; `--strict`/`scope` |
| .claude/agents/mockup-bildpruefer.md | CREATE | unabhängiger Prüf-Agent: nur Mockup-Bild + Staging-Bild + Elementliste-Auszug |
| docs/reference/gates_und_ratschen.md, docs/reference/design_system.md, docs/reference/workflow_und_agenten.md | MODIFY | Wächter + Prüfdatum (Regel-Budget-Tabelle), Ablauf Scheibe → Abgleich → Prüf-Agent |

### Scope Assessment
- Files: ~12–14 (ohne generiertes JSON)
- Estimated LoC: +900…1200 / −0 (JSON mehrere tausend Zeilen, generiert)
- Risk Level: MEDIUM — keine Produktfunktion geändert, aber neue Merge-Sperre; Fehlkalibrierung blockiert CI bzw. lässt Verstöße durch.

### Technical Approach
**Wächter (ein Test, zwei Regeln):**
- (a) Aufbau, Opt-in `SEITEN_SCOPE` (Seiten-/Reiter-Dateien, wandern mit jeder Scheibe hinein): kein `<style>`, kein `style=`-Attribut, keine Tailwind-Utility-Klassen, keine rohen `button/input/select/textarea/table`, Komponenten nur aus `$lib/components/{atoms,molecules,organisms}` (bzw. freigegebenen Kompositionen). Ausnahme nur `audit:exempt` + Begründung. Startet leer bzw. mit den in Scheibe (a) neuen Dateien — Bestand wird nicht nachträglich rot.
- (b) Tokens in `atoms/molecules/organisms`, Ratsche: Farbe/Abstand/Größe/Radius/Schrift/Schatten nur `var(--g-*)`; erlaubt 0, 1px-Rahmen, %, fr, auto, calc/min/max über Tokens. `AUSNAHMEN` je Datei = Ist-Stand, darf nur sinken; neue Baustein-Dateien starten bei 0.
- Zusätzlich: neue `.svelte`-Datei außerhalb der Baustein-Ordner unter `routes/` oder `lib/components/**` muss in `SEITEN_SCOPE` oder in einer Bestandsliste stehen (sonst rot) → nichts entgeht dem Wächter. Bestandsliste darf nur sinken.
- Regel-Budget: Prüfdatum +90 Tage (2027-02-08) im ADR und in `gates_und_ratschen.md`; Löschbedingung: kein nachweisbarer Fang bis dahin.

**Elementliste:**
- Generator rendert das Mockup per Playwright (`file://`), steuert per Klick (`data-ctx`, `data-zst`, `data-tab`, `data-seg`) und für reine Script-Zustände (`openEdit`, `channelTab`, `pickerOpen`, `saveOpen`, `kebabConfirm`) per `page.evaluate("…; render()")`; entfernt `.tag`, schließt `data-fb` und `.frame` aus.
- Felder: `id` (stabil), `ctx`, `reiter`, `zustand`, `abschnitt`, `ordnung`, `rolle`, `text_de`, `muster` (Platzhalter für Zahlen/Namen/Werte), `i18n_key`, `text_en`, `luecke`.
- EN: exakter Treffer im DE-Katalog → EN-Wert desselben Schlüssels; sonst Musterabgleich; ohne Treffer `luecke: true`.
- **Entscheidung zu EN-Lücken (nach ADR-0104, keine PO-Frage):** Lücken werden nicht akzeptiert, sondern sind Arbeitsposten der jeweiligen Scheibe (neuer Text kommt über den Katalog). Dynamische Texte (Zahlen, Namen, Werte) zählen als **ein** Element mit Muster.
- Abgleich auf Staging: Text sichtbar (normalisiert), richtiger Abschnitt, relative Reihenfolge im Abschnitt; keine Pixelpositionen. Nicht herstellbare Zustände (Ladefehler) über Route-Abfangen, sonst `nicht_pruefbar` mit Grund — nie still übersprungen.
- Läuft nicht im PR-CI (eigene Staging-Config); Bericht JSON+Markdown, Exit 0; `--scope <reiter/zustand>` für Scheiben, `--strict` macht rot. Abschlusskriterium #2913: `--strict` ohne Scope grün, DE und EN.
- CI-Anteil ohne Browser: Hash-Vergleich Mockup ↔ elementliste.json.

**Prüf-Agent:** Agent-Definition mit festen Eingaben (Mockup-Bild, Staging-Bild gleicher Viewport/Zustand, Elementliste-Auszug), ohne Quellcode-Zugriff; Aufruf am Scheibenende, max. 2 Runden; ergänzt die Elementliste (Optik), ersetzt sie nicht. Hier nur Definition + Probelauf.

### Dependencies
- Muster: `harte_farben_waechter.test.ts` (Ratsche, `audit:exempt`), CI-Job `frontend-test` (`npm test`, node --test) nimmt neue `__tests__/*.test.ts` automatisch auf.
- Playwright-Staging-Muster: setup-Projekt + storageState, `assertNotProdBaseURL`, Vorlage `playwright.sprachwechsel.staging.config.ts`.
- i18n: `frontend/src/lib/i18n/messages/{de,en}/*.json`, `hardcode_allowlist.json`.
- Tokens: `frontend/src/app.css` (`--g-s-*`, `--g-text-*`, `--g-radius-*`/`--g-r-*`, `--g-font-*`, `--g-elev/shadow-*`). Ampel-Tokens fehlen → Bausteine-Workflow.
- ADR-Prüfung: `tests/test_adr_index_drift.py`.

### Befunde gegen den Plan
- EN-Soll aus Katalog bleibt unvollständig, solange Mockup-Texte keinen Schlüssel haben → als Lücken sichtbar, nicht als Fehler des Generators.
- Regex-Wächter umgehbar (style=, Utility-Klassen, Direktiven) → Regeln decken diese explizit ab; Svelte-AST bevorzugt, falls `svelte/compiler` im node-Test nutzbar.
- Überschneidung mit `harte_farben_waechter` und `pendant_gate.py`: gleiches Muster nutzen, keine vierte Parallelstruktur.

### Open Questions
- keine an den PO (EN-Lücken und Zählweise dynamischer Texte als Tech-Lead entschieden, s. o.).
