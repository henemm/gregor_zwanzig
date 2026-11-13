# Context: feature-2913-abgleich-ganzseite

## Request Summary
Teil des Arbeitsplans #2913 (Plan A–C aus dem Kommentar vom 12.11.2026 11:15 UTC): Der Elementlisten-Abgleich
soll die **ganze Seite** bewerten und nicht nur die Abschnitte der jeweiligen Scheibe. Dazu gehören
(A) die Triage aller Abweichungen mit Besitzer (Scheibe, Issue oder Freigabe),
(B) die Gegenrichtung: Was live sichtbar ist und keinem Elementlisten-Eintrag entspricht, wird als `zusaetzlich` gemeldet, rot nachgewiesen an der Profil-Zeile des Seitenkopfs,
(C) die Abnahmeregel „keine Abweichung ohne Besitzer“.
Plan D (mockup-bildpruefer mit Ganzseitenbild) wurde in `fix-2913-metrikliste-mockup` bereits gebaut.

## Related Files
| File | Relevance |
|------|-----------|
| `frontend/e2e/elementliste_abgleich_logik.ts` (570 Z.) | reine Logik: Status-Typ (`gefunden/abweichend/nicht_pruefbar/freigegeben`), `bewerteAbschnitt`, `baueBericht`, `exitCode`, `berichtAlsMarkdown`, Freigaben. Hier kommen der Status `zusaetzlich` und der Besitzer hinzu. |
| `frontend/e2e/elementliste-abgleich.staging.spec.ts` (244 Z.) | Playwright-Lauf gegen Staging; `texteImBereich(page, abschnitt)` liest sichtbare Texte unter `[data-abschnitt]` (sonst `document.body`). Für die Gegenrichtung muss je Reiter einmal die ganze Seite gelesen werden. |
| `scripts/elementliste_abgleich.ts` | CLI (`npm run elementliste:abgleich [-- --strict --scope …]`) |
| `frontend/e2e/elementliste-generator.mockup.spec.ts` | erzeugt `docs/context/einstellungen_neu/elementliste.json` aus dem Mockup |
| `docs/context/einstellungen_neu/elementliste.json` | 4148 Elemente; Felder id, ctx, reiter, zustand, segment, abschnitt, ordnung, rolle, text_de, muster, i18n_key, text_en, luecke |
| `docs/context/einstellungen_neu/elementliste_freigaben.json` | Freigaben (bisher nur Trip-Radar, AC-3/#2800); Vorbild für eine Besitzer-Datei |
| `docs/artifacts/feature-2913-scheibe-c/elementliste-bericht-{de,en}.json` | letzter vollständiger Bericht (vor dem Metrik-Umbau, daher für `metriken` veraltet) |
| `frontend/src/lib/components/shared/subscription-header/SubscriptionHeader.svelte` | Seitenkopf inkl. Profil-Zeile (Feld `profile`), Ziel der Rot-Probe für `zusaetzlich`; Marker `kopf` fehlt |
| `frontend/src/lib/components/shared/hub-kopf/HubKopf.svelte`, `hub-reiterflaeche/HubReiterflaeche.svelte`, `subscriptionTabs.ts` | Reiterleiste; Marker `reiterleiste` fehlt |
| `frontend/src/lib/components/organisms/wetter-tab/VorlageKarte.svelte`, `WetterTabInhalt.svelte` | Marker `vorlage`, `warnung`, `laden` fehlen; `metriken` ist gesetzt |
| `AnpassenKarte.svelte`, `WarnungenRadarKarte.svelte` | einzige Bausteine mit Marker neben `metriken` |
| `frontend/src/lib/__tests__/bausteine_waechter*.ts` | Bausteine-Wächter (SEITEN_SCOPE); neue Marker dürfen ihn nicht verletzen |

## Existing Patterns
- Jeder Status außer `gefunden`/`abweichend` braucht einen Grund (`baueBericht` wirft sonst).
- `freigegeben` wird über eine JSON-Datei mit `grund` und `spec` vergeben (`wendeFreigabenAn`), nach dem Lauf angewendet. Der Besitzer einer Abweichung (Scheibe/Issue) kann genauso als JSON-Zuordnung angelegt werden.
- `exitCode` mit `--strict`: ≠ 0 bei `abweichend + nicht_pruefbar > 0`; `freigegeben` zählt nicht.
- Die Logik ist rein und wird mit `node --test` geprüft (kein Vitest), der Staging-Lauf nur außerhalb der PR-CI.

## Letzter Bericht (DE, Scheibe c, vor Metrik-Umbau): 404 abweichend
metriken 256 (150 Reihenfolge, 106 nicht sichtbar, veraltet), kopf 68 (60 nicht sichtbar, 8 Haken fehlt),
reiterleiste 40 (36 Haken fehlt), abschnittskopf 16 (15 Haken fehlt), vorlage 16, warnung 6, laden 2.
Ein großer Teil sind fehlende `data-abschnitt`-Haken (Werkzeuglücke), der Rest echte Abweichungen (Kopf, Bereichsköpfe).

## Abgrenzung zur parallelen Sitzung (#2795, Zustellung, Absprache 12.11.)
Die Sitzung #2795 setzt die Marker im Reiter **Zustellung** selbst (abschnittskopf, briefing-zeiten, laufzeit,
kanaele, stille-stunden). Dieser Workflow setzt `abschnittskopf` nur in den anderen Reitern und ändert keine
Zustellungs-Komponenten. Die Abgleich-Werkzeuge gehören diesem Workflow.

## Dependencies
- Upstream: Mockup `docs/context/einstellungen_neu/seiten/mockup-hub-fassung3.html`, Elementliste, Staging-Konto (Staging-`.env`, GZ_VALIDATOR_USER/PASS)
- Downstream: Abnahme jeder Scheibe von #2913 (d, c2, e), `mockup-bildpruefer`, `/e2e-verify`

## Existing Specs
- Spec der Schritte 1–2 (#2918): Elementliste, Abgleich, Wächter (unter `docs/specs/modules/`, Suche `elementliste`)
- `docs/adr/0112-*` (Oberflächen nur aus Bausteinen)

## Risks & Considerations
- Gegenrichtung braucht eine Zuordnung „Live-Text ↔ Elementliste“; Konto-Daten (Trip-Name, Orte, Chips) dürfen nicht als `zusaetzlich` zählen → Muster/Platzhalter und gezielte Ausnahmen mit Grund.
- Fixierte Elemente (SaveIndicator, BottomNav, App-Navigation/Seitenleiste außerhalb des Hubs) gehören nicht zur Seite → Wurzel für die Gegenrichtung = Hub-Container, nicht `body`.
- Elementliste enthält Zustände (`laedt`, `fehler`, `luecken`); die Gegenrichtung zuerst nur für `normal`.
- Marker sind unsichtbar (Attribut), ändern das Aussehen nicht; Bausteine-Wächter muss grün bleiben.
- Staging-Rate-Limits (Registrierung 429) betreffen den Abgleich nicht, er nutzt das vorhandene Konto.

## Analysis

### Type
Feature (Prüfwerkzeug), Teil des Arbeitsplans #2913 (Plan A–C).

### Befunde der Analyse (12.11.2026)
- Kein gemeinsamer Hub-Container: Trip `routes/trips/[id]/+page.svelte:307` (`<main>` enthält auch Dialoge/TopoBg), Vergleich `routes/compare/[id]/+page.svelte:364/415` (HubKopf und CompareDetail als Geschwister ohne Wrapper). `body` enthält Seitenleiste, BottomNav, SaveIndicator → ungeeignet.
- Elementliste kennt nur die Reiter `etappen|orte|wetter|zustellung`, **kein `uebersicht`** (Mockup Z. 594 hat einen). `kopf`, `reiterleiste`, `vorlage` stehen nur unter `reiter=wetter` (für trip und orte), gelten aber für `kopf`/`reiterleiste` auf jedem Reiter.
- Gesetzte Marker heute nur `metriken`, `anpassen`, `warnungen-radar`.
- Profil-Zeile: `SubscriptionHeader.svelte:150–160` (Desktop-Knopfzeile), Z. 169 Mobil-Dropdown (je Viewport nur eines sichtbar). Profil-Optionen stehen nicht in der Elementliste → werden in der Gegenrichtung `zusaetzlich` (gewollte Rot-Probe).
- `abschluss` prüft `eintraege.length === elemente.length` (Logik Z. 523 f.) → Zusätzlich-Einträge in eigener Liste führen, nicht in `plan.elemente`.
- Letzter Bericht (404 abweichend) ist vor dem Metrik-Umbau entstanden → vor der Triage (A) neu erzeugen.

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `frontend/e2e/elementliste_abgleich_logik.ts` | MODIFY | Status `zusaetzlich` + Zähler; `findeZusaetzliche(befund, liste, ausnahmen, kontoTexte, sprache)`; stabile ID `zus:<ctx>/<reiter>/<hash normalisierter Text, Zahlen→{zahl}>`; Besitzer-Datei lesen/prüfen/anwenden; `exitCode` mit `abnahme`; Markdown mit Besitzer-Spalte und Zusätzlich-Tabelle |
| `frontend/e2e/elementliste-abgleich.staging.spec.ts` | MODIFY | je Kombi (zustand normal, ohne Segment) Texte unter allen `[data-seite="hub"]` lesen; Konto-Texte (Trip-/Preset-Name, Etappen-, Ortsnamen) aus der API an die Logik reichen; Besitzer anwenden |
| `scripts/elementliste_abgleich.ts` (+ `flagsAlsUmgebung`) | MODIFY | Flag `--abnahme` |
| `docs/context/einstellungen_neu/elementliste_besitzer.json` | CREATE | Zuordnung Abweichung → Besitzer (Scheibe/Issue) mit Grund; Ziel-Arten element / abschnitt / zusaetzlich (Text oder Muster) |
| `docs/context/einstellungen_neu/elementliste_ausnahmen.json` (oder Teil der Besitzer-Datei) | CREATE | Live-Texte, die bewusst nicht in der Elementliste stehen (Kontodaten ohne Muster), je mit Grund + Spec |
| `frontend/src/lib/components/shared/hub-kopf/HubKopf.svelte` | MODIFY | `data-seite="hub"` + `data-abschnitt="kopf"` am Wurzel-div |
| `frontend/src/lib/components/trip-detail/TripTabs.svelte`, `.../CompareTabs.svelte` | MODIFY | `data-seite="hub"` an der Wurzel; `data-abschnitt="reiterleiste"` an einem Wrapper um `MTabBar` (ohne Klassen/Style, Bausteine-Wächter) |
| `frontend/src/lib/components/organisms/wetter-tab/VorlageKarte.svelte` | MODIFY | `data-abschnitt="vorlage"` (Z. 66) |
| `frontend/src/lib/components/organisms/wetter-tab/WetterTabInhalt.svelte` | MODIFY | `laden`/`warnung` an `wt-laden`/`wt-fehler` (≈ Z. 226/231) |
| `frontend/src/lib/__tests__/elementliste_abgleich*.test.ts` | MODIFY/CREATE | Zähler nachziehen; neue Tests für Gegenrichtung, Besitzer, `--abnahme`, Rot-Probe Profil-Zeile (Fixture) |
| Spec `docs/specs/modules/einstellungen_neu_neustart_adr_waechter_elementliste.md` bzw. neue Teil-Spec | CREATE/MODIFY | ACs für A–C |

### Scope Assessment
- Files: ~15
- Estimated LoC: ≈ +600 / −20 (Logik +150–200, Staging-Spec +50, Starter +10, Tests +250, Svelte je 1 Attribut/Wrapper, JSON)
- Risk Level: MEDIUM (Prüfwerkzeug, keine Nutzerfunktion; Risiko liegt im Rauschen der Gegenrichtung und in der Besitzer-Datei als „Verschiebebahnhof“)

### Technical Approach
1. **Besitzer + Abnahmeregel (A, C):** eigene Datei `elementliste_besitzer.json`, getrennt von den Freigaben. Freigabe bleibt Status `freigegeben` (Spec-Pflicht) und zählt als Besitzer. Parser wirft bei fehlendem Grund oder fehlendem Verweis (Scheibe `#2913-c2|d|e` oder Issue `#NNNN`), wie `leseFreigaben`. Abschnitts-Besitzer erlaubt (z. B. „kopf → Scheibe c2“), damit nicht 400 Einzelzeilen nötig sind. Neuer Modus `--abnahme`: Exit ≠ 0, sobald ein Eintrag `abweichend`, `nicht_pruefbar` oder `zusaetzlich` keinen Besitzer hat. `--strict` bleibt unverändert.
2. **Marker:** `data-seite="hub"` (Wurzel für die Gegenrichtung) an HubKopf und TripTabs/CompareTabs; `kopf`, `reiterleiste`, `vorlage`, `laden`, `warnung` nachrüsten. Nur Attribute bzw. ein Wrapper ohne Styling. Zustellungs-Komponenten bleiben unberührt (#2795).
3. **Gegenrichtung (B):** je Kombination ctx × Reiter (zustand `normal`, ohne Segment) sichtbare Texte aller `[data-seite="hub"]` lesen (Desktop-Viewport). Erklärt ist ein Text, wenn er auf einen Eintrag des Reiters oder auf `kopf`/`reiterleiste` des ctx passt (`erwartung` wiederverwenden, DE/EN), auf einen Konto-Text aus der API oder auf eine Ausnahme mit Grund. Der Rest wird `zusaetzlich` mit stabiler ID. Reihenfolge und Mehrfachvorkommen spielen keine Rolle. Zustellung wird mitgelesen (Lesen ändert nichts an #2795); Befunde dort bekommen den Besitzer Scheibe d.
4. **Rot-Probe:** Unit mit Befund-Fixture, das die Profil-Zeile enthält → `zusaetzlich`, Exit 1 bei `--abnahme`; mit Besitzer-Eintrag → Exit 0. Danach Staging-Lauf mit `--abnahme` rot an der Profil-Zeile.
5. **Triage (A):** neuen Ganzseitenbericht DE+EN erzeugen, jede Abweichung einem Besitzer zuordnen (Werkzeuglücke ⇒ durch Marker behoben; echte Abweichung ⇒ Scheibe c2/d/e oder Issue). Ergebnis als Tabelle ins Issue #2913.
- Reihenfolge innerhalb dieses Workflows: 1 → 2 → 3 → 4 → 5. Auslieferung in einem PR (der Plan-Agent hat drei PRs vorgeschlagen; das Werkzeug ist erst mit allen drei Teilen nutzbar, und die Rot-Probe braucht Marker und Gegenrichtung zusammen).

### Dependencies
- Upstream: Elementliste + Generator (Mockup Fassung 3), Freigaben-Datei, Staging-Konto (Staging-`.env`).
- Downstream: Abnahme der Scheiben c2, d, e; `mockup-bildpruefer`; `/e2e-verify`.
- Bausteine-Wächter (`frontend/src/lib/__tests__/bausteine_waechter*.ts`): TripTabs/CompareTabs stehen im Bestand (Ratsche) → Wrapper ohne `style=`/Utility-Klassen.
- Parallele Sitzung #2795: CompareTabs/TripTabs liegen nahe an Zustellung → vor dem Ändern per SendMessage abstimmen, falls die Sitzung läuft.

### Open Questions (technisch, von Claude entschieden)
- Reiter **Übersicht** fehlt in der Elementliste: in der Gegenrichtung mit Grund ausgenommen, Besitzer ein neues Issue „Elementliste: Reiter Übersicht aus dem Mockup erzeugen“. Keine PO-Frage.
- Handy-Viewport: Gegenrichtung zunächst nur Desktop; Handy-Zusätze (Zeile „Etappe · Briefing · Start in“) sind laut Nachtrag 11:11 bereits Scheibe c2 zugeordnet. Handy-Lauf als Folge-Issue.
- Rauschen erster Lauf geschätzt 20–60 Treffer → iterativ mit Ausnahmen/Besitzern triagieren, nie pauschal filtern.
