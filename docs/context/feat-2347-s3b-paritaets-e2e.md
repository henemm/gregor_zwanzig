# Context: feat-2347-s3b-paritaets-e2e

## Request Summary
Scheibe S3b von #2347 (Epic #2345, Etappe P6): Die verbliebenen Compare-only-Playwright-Specs zu Versand, Konflikt-412, Radar, Stundenverlauf und Rest von `compare-hub-inline-edit` werden zu kind-parametrisierten `hub-*`-Specs (Trip UND Ortsvergleich). Reine Testschicht; Trip-Rotfälle sind Produktlücken und werden im selben Ticket behoben (Muster S2/S3a, AC-13).

## Stand
- S1 (PR #2623), S2 (#2627), S3a (#2633, c8bb30d) live. Wächter `ALTLAST` = 34, `E2E_MIN_SPECS` 68, `E2E_MIN_EXECUTED_HAUPT` 479.
- S3a-Spec `docs/specs/modules/feat_2347_s3a_paritaets_e2e.md` ist die Vorlage (Aufbau, Zuordnungstabelle, Mutations-Gegenprobe).
- Keine Parallel-Lieferung auf `origin/main` zu #2347 über S3a hinaus; keine andere Sitzung auf #2347.

## Related Files (Kandidaten S3b, Zeilen gemessen)
| Datei | Zeilen | Ratsche | Anmerkung |
|---|---|---|---|
| `compare-versand-speichert-selbst.spec.ts` | 316 | ja | Versand-Autosave; S1 deckt nur Uhrzeit-Teil ab |
| `compare-hub-versand-inline.spec.ts` | 420 | **nein** | braucht eigenen storageState (`staging-1256-s7.json`), trägt Lost-Update-Nachweis F004 (:314) |
| `compare-hub-briefing-times.spec.ts` | 263 | **nein** | 4 von 9 Fällen rot (AC-2, AC-4, AC-8, AC-10), Texte veraltet |
| `versand-tab-vergleich.spec.ts` | 313 | nein | Regel-2-Altlast (Compare-Hub-Reiter ohne Trip-Pendant) |
| `compare-konfliktschutz-zwei-kontexte.spec.ts` | 394 | ja | Konflikt-412, #2375/#2381 |
| `compare-radar-toggle.spec.ts` | 150 | ja | Radar ist Vergleichs-Preset (compare-eigen) |
| `compare-stundenverlauf-wertprops.spec.ts` | 249 | ja | Stundenverlauf-Schalter (compare-eigen) |
| `compare-hourly-metric-order.spec.ts` | 456 | nein | `waitForTimeout` :411 (Filter A) |
| `compare-editor-autosave.spec.ts` | 501 | nein | Autosave-Altspec |
| `issue-682-compare-editor-mobile.spec.ts` | 217 | ja | Gegenstück `issue-661-trip-new-mobile.spec.ts` |
| `compare-hub-inline-edit.spec.ts` | 171 | nein | Rest Z. 1-172 |
| `.staging`-Specs (`compare-*.staging.spec.ts`, `fix-1350*`, `kanal-grenzen-ortsvergleich`) | 100-650 | nein | laufen manuell gegen Staging, eigene Setups |
| `tests/unit/test_e2e_compare_paritaet_waechter.py` | – | – | `ALTLAST`, `ALTLAST_MAX` |
| `.github/ci_e2e_specs.txt`, `.github/workflows/ci.yml` | – | – | Ratsche (`E2E_MIN_*`) |
| `frontend/e2e/helpers.ts` | – | – | `HUB_KINDS`, `seedHub`, `openHub`, `zaehlePuts` u. a. |

## Existing Patterns
- Kind-Schleife `for (const kind of HUB_KINDS)`, Setup `seedHub`, `openHub`, Aufräumen im `finally`, Warten nur über `expect.poll`/`waitForResponse` (kein `waitForTimeout`).
- Compare-eigene Zweige nur als `if (kind === 'vergleich')` mit Begründungskommentar; erlaubt sind nur Orte-Tab, transponierte Übersicht, Compare-Mail (plus Radar/Telegram-Kurzstil/Stundenverlauf als Vergleichs-Preset).
- Nicht zusammenführbare Specs bekommen den `gz-eigenstaendig:`-Kopf (erste 30 Zeilen, mind. 15 Zeichen).
- Ratschenmodus: `ALTLAST` darf nur schrumpfen, `len(ALTLAST) == ALTLAST_MAX`.
- Zweitnutzer: genau eine Registrierung (Bremse 5/h/IP), serial + `beforeAll`.
- Quota: max. 2 aktive Vergleiche pro Nutzer (409), `workers: 1`.

## Dependencies
- Upstream: geteilte Bausteine `VersandTab`/`WetterMetrikenVersandPanel`, `saveController`, ETag-Registry (#2381, ETag fängt Same-Tab-Race nicht), `TripTabs.svelte`, `CompareTabs.svelte`.
- Downstream: CI-Job `e2e` (Positivliste, `E2E_MIN_SPECS`, `E2E_MIN_EXECUTED_HAUPT`), Wächter-Test, `docs/reference/gates_und_ratschen.md`, Staging-Configs (`playwright.*.staging.config.ts`).

## Existing Specs
- `docs/specs/modules/feat_2347_s1_paritaets_e2e.md`, `..._s2_...`, `..._s3a_...`

## Risks & Considerations
1. **Zusicherungsverlust:** Die Altspecs sind das Regressionsnetz für #2276/#2277 (Konflikt-412, Lost-Update F004). Pro Zusicherung 1:1-Zuordnung plus Mutations-Gegenprobe je kind; nichts abschwächen.
2. **Nicht geratschte Altspecs** (`briefing-times`, `hub-versand-inline`) sind rot bzw. nicht lauffähig im CI-Stack. Beim Zusammenführen entscheiden, ob die Zusicherung neu geschrieben (geteilt, geratscht) oder wegen veralteter Texte gelöscht wird. Rot ≠ Abschwächungsgrund. `hub-send-dialog-target.staging` zeigt den Weg für Staging-Setup-Fälle.
3. **Umfang:** ~3.500 Zeilen Altbestand in ~11 Dateien. Möglicherweise Teilung in S3b-1 (Versand-Trio + Konflikt) und S3b-2 (Radar/Stundenverlauf/Mobile/Rest, `.staging`). Das entscheidet `/20-analyse` nach Messung. Eine Sitzung bearbeitet ein Epic; Reste nicht abspalten, sondern als weitere Scheibe führen.
4. **Trip-Pendants** zum Konflikt-412 und zu Versand-Kanälen sind erstmals gemessen und können Produktlücken zeigen (AC-13).
5. **CI-Zeit:** `e2e` dauert ~14 min; Registrierungsbremse erschwert lokale 3×-Läufe (AC-10, S3a-Befund).
6. **Mail-Pfade:** Versand-Specs ändern nur Einstellungen eines Wegwerf-Objekts; es wird nichts versendet.

## Analysis

### Type
Feature (Testschicht-Rework, Epic #2345 P6). Kein Produktcode geplant; Produktfixes nur, wenn ein Trip-Pendant rot wird (AC-13-Muster S2/S3a).

### Messung (2026-10-28, am Worktree-Stand c8bb30d)
| Datei | Zeilen | Fälle | Ratsche | Befund |
|---|---|---|---|---|
| compare-versand-speichert-selbst | 316 | 5 (AC-4/5/6/7/11) | ja | Versand-Autosave; S1 deckt nur Uhrzeit-Chip |
| compare-hub-versand-inline | 420 | 8 (AC-35/36/37, F001, F002, F004, #2283) | nein, ENOENT `staging-1256-s7.json` | trägt Lost-Update F004; #2283-Fall überschneidet sich mit `hub-send-dialog-target.staging` |
| compare-hub-briefing-times | 263 | 9 | nein, 4 rot | Texte veraltet (AC-2/4/8/10); AC-1/7/10 Übersicht-/Vergleichs-Eigenheit |
| versand-tab-vergleich | 313 | 9 | nein | Regel-2-Altlast; AC-6 Create-Flow, AC-10 Mobile, Staging-F001 Stundenverlauf |
| compare-editor-autosave | 501 | 12 | nein, `waitForTimeout` | Mischung Orte/Wertebereich/Versand; Wertebereich-Teil durch S3a großenteils gedeckt |
| compare-konfliktschutz-zwei-kontexte | 394 | 5 (+Schleife über 4 Reiter) | ja | Konflikt-412; Trip-Seite hat ETag-Mechanik (`trips/[id]/+page.svelte`, TripHeader), E2E-Pendant fehlt |
| compare-radar-toggle | 150 | 3 | ja | Trip-Modell hat KEIN `radar_alert_enabled`/Stundenverlauf (`trip.go`: 0 Treffer) ⇒ compare-eigen |
| compare-stundenverlauf-wertprops | 249 | 4 | ja | compare-eigen (siehe oben) |
| compare-hourly-metric-order | 456 | 3 | nein, `waitForTimeout`:411 | compare-eigen |
| issue-682-compare-editor-mobile | 217 | 6 | ja | Gegenstück `issue-661-trip-new-mobile` (geratscht) |
| compare-hub-inline-edit (Rest) | 171 | 3 (Orte AC-14/15/31/32) | ja | Orte-Tab = erlaubte Compare-Eigenheit |
| ~12 `.staging`-Specs | 100–650 | – | nein | laufen manuell, eigene Setups |

Summe Kern-Altbestand ≈ 3.450 Zeilen / ≈ 67 Fälle in 11 Dateien (+ Staging-Gruppe).

### Technischer Ansatz
Teilung nach Verwandtschaft, jede Scheibe eigenständig auslieferbar (Muster S3a: Zuordnung alt→neu je Fall, Mutations-Gegenprobe je kind, Wächter `ALTLAST` schrumpft, Ratsche gemessen):
- **S3b (diese Scheibe) – Versand-Gruppe:** versand-speichert-selbst, hub-versand-inline, briefing-times, versand-tab-vergleich, Versand-Anteil von editor-autosave → kind-parametrisierte `hub-versand-*`-Specs. Nicht-geratschte Altfälle (inline, briefing-times) werden neu geschrieben (geteilt, geratscht, eigener Setup über `seedHub`) statt wegen roter/veralteter Texte gestrichen; veraltete Textzusicherungen werden am Ist-Stand neu formuliert, nie abgeschwächt. Compare-eigene Reste (Übersicht-Stat, Create-Flow-POST) bleiben als `if (kind === 'vergleich')` bzw. `gz-eigenstaendig:`.
- **S3c – Konflikt-412:** konfliktschutz parametrisieren; Trip-Pendant erstmals gemessen ⇒ Produktlücken wahrscheinlich (AC-13).
- **S3d – compare-eigener Rest:** radar, stundenverlauf ×2, hourly-order, 682-mobile, inline-edit-Rest, `.staging`-Specs → `gz-eigenstaendig:`-Kopf bzw. Zusammenführung mit `issue-661`.
- **S4:** Gruppe ohne Trip-Pendant, #2243-Leichen, ALTLAST leer.

### Scope S3b
- Dateien: ~5 löschen/kürzen, ~4–5 neue `hub-versand-*`, Wächter-Test, Ratsche, `docs/reference/gates_und_ratschen.md`, ggf. 1 Produktfix
- LoC: +700/-1.500 (Tests; `loc_limit_override` nötig); Risiko: MITTEL (Zusicherungsverlust, Trip-Rotfälle)

### Dependencies
`helpers.ts` (`seedHub`, `openHub`, `HUB_SEL`, `zaehlePuts`), `VersandTab`/`WetterMetrikenVersandPanel`, `saveController`, ETag-Registry; Ratsche `E2E_MIN_SPECS` 68 / `E2E_MIN_EXECUTED_HAUPT` 479; Wächter `ALTLAST_MAX` 34.

### Open Questions
- [ ] Welche der 4 roten briefing-times-Fälle gelten noch (Ist-Texte am Produkt prüfen) – in /30 je Fall entscheiden
- [ ] Hat `hub-send-dialog-target.staging` den #2283-Fall bereits voll abgedeckt (dann Löschung statt Neuschrieb)?
- [ ] F004 (Lost-Update, Kebab-Pausieren) für Trip: gibt es ein Trip-Kebab mit Pausieren im Hub?
