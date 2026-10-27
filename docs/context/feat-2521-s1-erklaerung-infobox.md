# Context: feat-2521-s1-erklaerung-infobox

## Request Summary
Issue #2521, Schnitt S1, PO-Entscheid vom 2026-10-08 (Kommentar im Issue):

- **Begriff-Erklärung:** ein kleines ⓘ neben dem Fachbegriff. Tippen oder Klicken öffnet eine Sprechblase, Tippen daneben oder Esc schließt sie. Hover wird nicht vorausgesetzt. Basis ist der bits-ui-Popover.
- **Infobox** „Kannst du überspringen — Standard: …“ je überspringbarem Editor-Reiter. Sie ist immer sichtbar, lässt sich nicht wegklicken und speichert keinen Zustand.
- **Texte** stehen im Textkatalog `frontend/src/lib/i18n/messages/de.json` (aus #2520).
- **Einbau** in den Trip- und den Ortsvergleichs-Editor über die geteilten Reiter-Organismen. Erklärungen gibt es für Wertebereiche, Kanal-Schwelle, CAPE und Cooldown.

Nicht in S1: Willkommen, Startklar-Checkliste, „Mit Standardwerten speichern“, Hilfeseite. Diese Teile folgen in späteren Schnitten.

## Related Files
| File | Relevance |
|------|-----------|
| `frontend/src/lib/i18n/index.ts:3-9` | `t(key: MessageKey)`, typisiert über `keyof typeof de`. Ein unbekannter Schlüssel ist ein TS-Fehler, `svelte-check` wird dann rot. Keine Interpolation |
| `frontend/src/lib/i18n/messages/de.json` | flacher Katalog, heute nur Schlüssel `start.*` (30 Stück) |
| `frontend/src/lib/i18n/__tests__/textkatalog.test.ts` | Muster für Katalogtests (node:test). Die Prüfungen filtern auf `start.*` |
| `frontend/src/routes/_start/Startseite.svelte:6` | bisher einzige Stelle, die `t()` nutzt |
| `frontend/package.json:35` | `bits-ui` ^2.17.3 (Popover und Tooltip vorhanden, noch nirgends genutzt) |
| `frontend/src/lib/components/ui/dialog/*` | Muster für einen bits-ui-Wrapper (`ui/popover` analog) |
| `frontend/src/lib/components/atoms/`, `molecules/` | Ablage der Bausteine. Atom-Barrel `atoms/index.ts`, `molecules/Field.svelte` mit `hint` |
| `frontend/src/lib/components/shared/anlegeLockEngine.ts:33-58` | Freischaltkette Metriken → Wertebereiche → Alarme → Versand. `canFinish` = `done.has('versand')` |
| `frontend/src/lib/components/trip-new/TripNewEditor.svelte:76-84`, `tripNewLogic.ts:29/56/91/97` | Trip-Reiter: route, etappen, wegpunkte (`optional`), wetter-metriken, wertebereiche, alarme, versand |
| `frontend/src/lib/components/compare-new/CompareNewEditor.svelte:113-120` | Vergleichs-Reiter: vergleich, orte, wetter-metriken, wertebereiche, alarme, versand |
| `frontend/src/lib/components/shared/subscriptionTabs.ts:28-38` | Reiter der Bearbeiten-Hubs |
| `trip-detail/TripTabs.svelte:201-206`, `AlarmeScheduleTab.svelte:60`, `BriefingScheduleTab.svelte:139`, `compare/CompareTabs.svelte:1039-1104` | Einbindung derselben Organismen in den Bearbeiten-Editoren |
| `shared/corridor-editor/CorridorEditor.svelte:382-416`, `CorridorEditorMobile.svelte:349-376` | Reiter Wertebereiche: Eyebrows und Lead-Text, verzweigt nach Kontext |
| `shared/AlarmeTab.svelte` (:523 Picker, :544 Cooldown, :495 „Alarm-Schwellen“) | Reiter Alarme |
| `shared/AlertChannelPicker.svelte:92/101-104/122-133` | Kanal-Schwelle. Sichtbar ist nur die Eyebrow „Alert-Kanäle“, das `aria-label` lautet „Dringlichkeits-Schwelle“ |
| `alerts-tab/AlertCooldownCard.svelte:11/26-28` | Eyebrow „Cooldown“ plus bestehender `.hint` |
| `utils/alertMetricLabels.ts:35`, `alerts-tab/AlertMetricLevelRow.svelte:32-43`, `alerts-tab/alertMetricTable.ts:273-282` | CAPE: Label „Gewitterenergie (CAPE)“ und vorhandener `title` (`thresholdTitle`, Regressions-Invariante: nur CAPE hat einen) |
| `shared/VersandTab.svelte`, `versand-tab/*` | Reiter Versand |
| `shared/WeatherMetricsTab.svelte:1515/1706`, `layout-tab/LayoutTab.svelte` | Layout ist **kein eigener Reiter**, sondern ein Abschnitt im Reiter Wetter-Metriken |
| `frontend/src/app.css:99-112, :195-215` | Tokens (`--g-card`, `--g-ink-2/3/4`, Akzente). Kein Dark Mode |
| `frontend/test-svelte-ssr-hooks.mjs`, `shared/__tests__/app_footer_kontrast_und_tippflaeche.test.ts` | SSR-Harness und Vorlage für den Kontrasttest (kein `--g-ink-4`) |
| `frontend/e2e/*`, `.github/ci_e2e_specs.txt` | Playwright-Specs. Die CI-Positivliste darf nur wachsen, `waitForTimeout`, `skip` und `*.staging.spec.ts` sind ausgeschlossen |
| `docs/specs/modules/onboarding_hilfe_2521.md` | Spec-Entwurf v1.1 (draft, nicht freigegeben) |

## Existing Patterns
- **bits-ui-Wrapper:** nach dem Muster `ui/dialog/*` (shadcn-artig). `DropdownMenu` wird direkt in `CompareKebab.svelte` genutzt.
- **Hinweistexte:** Es gibt viele lokale Hinweis-Klassen ohne gemeinsamen Baustein: `.option-hint`, `.alarme-*-hint`, `.hint` in OutputLayoutEditor und AlertCooldownCard, `LTCapNote.svelte`, `ChannelToggle` mit Prop `hint`. Eine Komponente für Infobox, Tooltip, Callout oder Notice gibt es **nicht**, also auch kein Duplikat.
- **Native `title=`:** 75-mal verwendet, darunter die CAPE-Erklärung.
- **Frontend-Tests:** `node --test` mit `--experimental-strip-types`, kein Vitest. Komponenten werden über den SSR-Harness geprüft (`render` aus `svelte/server`), Kontraste aus den Werten in `app.css`.
- **Unterscheidung Anlegen und Bearbeiten:** Der Prop `createMode` existiert bei Trip-new schon.

## Dependencies
- **Upstream:** bits-ui Popover, Textkatalog `t()`, Tokens aus `app.css`, Atoms wie `Eyebrow`.
- **Downstream:** Trip-new, Compare-new, TripTabs und CompareTabs (Bearbeiten). Alle rendern dieselben geteilten Organismen.

## Existing Specs
- `docs/specs/modules/onboarding_hilfe_2521.md`: Entwurf für das ganze Issue (S1–S5). Er muss auf den PO-Schnitt umgestellt werden: S1 = Bausteine plus Einbau, die Hilfeseite fällt aus S1 heraus. Außerdem nennt der Entwurf fälschlich „Vitest“ und beschreibt einen Tooltip, bei dem „Hover nur Zusatz“ ist. Der PO will stattdessen ein Popover per Tippen.

## Risks & Considerations
1. **„Überspringbar“ ist im Code nicht modelliert.** `optional: true` gibt es nur bei Trip-`wegpunkte`. Wertebereiche und Alarme gelten schon durch bloßes Öffnen als erledigt. Versand ist Pflicht für `canFinish`. Die Liste der Reiter mit Infobox muss die Spec ausdrücklich festlegen.
2. **Layout hat keinen eigenen Reiter.** Eine Layout-Infobox gehört deshalb an den Layout-Abschnitt im Reiter Wetter-Metriken, oder sie entfällt.
3. **Infobox in den Bearbeiten-Editoren.** Dieselben Organismen erscheinen auch in TripTabs und CompareTabs. Die Spec muss entscheiden, ob die Infobox nur beim Anlegen erscheint (Prop) oder überall.
4. **HERKUNFT-Ratsche:** Neue `context ===`-Verzweigungen unter `shared/` machen den Test `context_herkunft_zweige_eingefroren` rot. Auch eingefügte Zeilen verschieben die eingefrorenen Zeilennummern. Texte deshalb per Prop oder Lookup-Map wählen und die Ratsche bewusst nachführen.
5. **Zwei Corridor-Varianten:** Der Einbau ist in `CorridorEditor` **und** `CorridorEditorMobile` nötig.
6. **CAPE-`title`-Invariante:** Den vorhandenen `thresholdTitle` nicht brechen. Das ⓘ sitzt am Label.
7. **Kanal-Schwelle braucht einen sichtbaren Anker.** Heute gibt es nur das `aria-label`.
8. **Popover-Verhalten** (Klick daneben, Esc, Tastatur) lässt sich im SSR-Harness nicht prüfen. Das braucht Playwright, möglichst als Spec in `ci_e2e_specs.txt` ohne `waitForTimeout`. Ob bits-ui im SSR-Harness kompiliert, ist noch unbelegt.
9. **Katalogtests** prüfen nur `start.*`. Neue Präfixe (`tip.*`, `info.*`) brauchen eigene Prüfungen: kein Fließtext außerhalb von `t()`, Kontrast ≥ 4.5:1, nie `--g-ink-4`.
10. **Pendant-Sperre:** Neue Bausteine gehören nach `shared/`, `ui/`, `atoms/` oder `molecules/`, nie nach `trip-new/` oder `compare-new/`.
11. **Frontend-Browser-Gate:** Ein Konsolenfehler auf `/trips/new` oder `/compare/new` (Popover-Portal, Hydration) blockiert den Deploy.
12. **Produktregel:** Nur Daten, keine Handlungsempfehlungen. Die Erklärtexte erklären Begriffe und raten nichts. Es heißt immer „Trip“, nie „Tour“.

## Analysis

### Type
Feature (Issue #2521, Schnitt S1 — Begriff-Erklärung ⓘ + Infobox je überspringbarem Reiter)

### Überspringbare Reiter und ihre Standards (Ist-Stand, belegt)
Freischaltung prüft nur den **Besuch** eines Reiters, nie den Inhalt (`shared/anlegeLockEngine.ts:33-56`; Besuchs-Flag `TripNewEditor.svelte:254-257`, `CompareNewEditor.svelte:210-213`).

| Reiter | Trip | Ortsvergleich |
|---|---|---|
| Pflicht (keine Infobox) | route (Name+Startdatum), etappen (GPX je Etappe) | vergleich (Name), orte (≥2) |
| wegpunkte | `optional` (Trip-only, `TripNewEditor.svelte:79`) | — |
| wetter-metriken | 9 Katalog-Defaults (`trip_default_rank`, `src/app/metric_catalog.py`), Tagesfenster 4–19 h | `COMPARE_METRIC_KEYS` (`weather-metrics-tab/compareMetricOrder.ts:23-25`), Stundenverlauf + 3-Tages-Ausblick AN |
| wertebereiche | keine (`corridors: []`, `tripNewLogic.ts:234`) | keine (`compareWizardState.svelte.ts:20,42`) |
| alarme | Kanäle E-Mail **+ Telegram** AN (`alarme-tab/alertChannelState.ts:31-36`, #2518), Schwelle „gering“, amtliche Warnungen AUS (`tripNewLogic.ts:153`) | Kanal **nur E-Mail** AN, Telegram aus Versand-Preset (=AUS) (`compare/alarmePropsAus.ts:88-93`), Schwelle „gering“, amtliche Warnungen AUS, Radar AUS |
| versand | E-Mail, Morgen 07:00 + Abend 18:00 (`reportSlotAktiv.ts:23-31`, `VersandTab.svelte:146-147`) | E-Mail, nur Morgen 07:00, kein Enddatum (`compareWizardState.svelte.ts:60-62,102-111`) |

→ Infobox-Reiter: **wetter-metriken, wertebereiche, alarme, versand** (beide Editoren) + Trip-**wegpunkte**. Texte je Kontext unterschiedlich (Alarme/Versand/Metriken weichen ab).

### Einbaustellen Begriff-Erklärung (alle in geteilten Organismen → wirkt in Trip + Vergleich, Anlegen + Bearbeiten)
| Begriff | Stelle | Heute |
|---|---|---|
| Wertebereiche | Eyebrow `shared/corridor-editor/CorridorEditor.svelte:382-416` **und** `CorridorEditorMobile.svelte:349-376` (je `context`-verzweigt) | Lead-Text :405/:416 |
| Kanal-Schwelle | `shared/AlertChannelPicker.svelte:92-100` (acp-head) — **kein sichtbarer Begriff**, nur `aria-label` „Dringlichkeits-Schwelle“ :122 → sichtbares Label nötig | Lead :101-103 |
| CAPE | `alerts-tab/AlertMetricLevelRow.svelte:43` (`td.metric-label`), Label aus `utils/alertMetricLabels.ts:35`; nur für CAPE (Map) | `title` an Schwellwert-Zelle :58 (Invariante `alertMetricTable.ts:273-282`, unverändert lassen) |
| Cooldown | `alerts-tab/AlertCooldownCard.svelte:11` | hint :26-28 |

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `frontend/src/lib/components/ui/popover/*` (index.ts + 2–3 .svelte) | CREATE | bits-ui-Popover-Wrapper nach Muster `ui/dialog/*` |
| `frontend/src/lib/components/molecules/BegriffErklaerung.svelte` | CREATE | ⓘ-Button (`type=button`, `aria-label`, ≥24 px) + Popover, Text via `t()` |
| `frontend/src/lib/components/molecules/Infobox.svelte` | CREATE | `<aside>`, immer sichtbar, kein Schließen, kein Zustand |
| `frontend/src/lib/components/shared/infoboxKeys.ts` | CREATE | Lookup-Map `Record<'route'\|'vergleich', Record<tab, MessageKey>>` + Begriff-Map (statt neuer `context ===`-Zweige) |
| `frontend/src/lib/i18n/messages/de.json` | MODIFY | neue Schlüssel `info.*` (Infobox je Reiter × Kontext), `tip.*` (4 Begriffe) |
| `shared/WeatherMetricsTab.svelte`, `shared/corridor-editor/CorridorEditor.svelte`, `CorridorEditorMobile.svelte`, `shared/AlarmeTab.svelte`, `shared/VersandTab.svelte` | MODIFY | Infobox oben im Reiter; Wertebereiche-ⓘ |
| Trip-wegpunkte-Organismus (`TripNewEditor` Panel bzw. Wegpunkte-Komponente) | MODIFY | Infobox — Ort in Spec festlegen (ist trip-eigen) |
| `shared/AlertChannelPicker.svelte`, `alerts-tab/AlertCooldownCard.svelte`, `alerts-tab/AlertMetricLevelRow.svelte` | MODIFY | ⓘ + sichtbares Label „Dringlichkeits-Schwelle“ |
| `shared/__tests__/context_herkunft_zweige_eingefroren.test.ts` | MODIFY (nur falls nötig) | Zeilennummern bewusst nachführen (BLEIBT_MIT_INHALT-Fesselung beachten) — besser: Einfügungen unterhalb der eingefrorenen Zeilen |
| `frontend/src/lib/i18n/__tests__/textkatalog.test.ts` o. neu | CREATE/MODIFY | Katalogtests für `info.*`/`tip.*` (vorhanden, nicht leer, kein „Tour“) |
| neue SSR-Tests (`shared/__tests__/…`) | CREATE | ⓘ + Infobox in allen vier Flächen; Kontrast ≥4.5:1, nie `--g-ink-4` |
| `frontend/e2e/begriff-erklaerung.spec.ts` + `.github/ci_e2e_specs.txt` | CREATE/MODIFY | Öffnen per Klick/Tastatur, Esc, Klick daneben; ohne `waitForTimeout` |

### Scope Assessment
- Files: ~12 produktiv (5 neu), plus Tests
- Estimated LoC: ~+215 produktiv / −5 (Limit 250, knapp → ggf. `loc_limit_override 500` statt Scope-Schnitt)
- Risk Level: MEDIUM — viele geteilte Organismen werden angefasst (Trip+Vergleich, Anlegen+Bearbeiten), aber rein additive Anzeige ohne Datenänderung

### Technical Approach (Empfehlung)
1. **Baustein-Trio:** `ui/popover` (Wrapper) → `molecules/BegriffErklaerung` → `molecules/Infobox`. Pendant-Sperre unkritisch (ui/molecules/shared).
2. **Infobox in den geteilten Organismen, nicht in den Editoren** — Editoren rendern Desktop- und Mobile-Panel doppelt (16 Einbaustellen statt 5 Dateien). Wirkt automatisch auch in TripTabs/CompareTabs (Bearbeiten).
3. **Immer sichtbar, auch beim Bearbeiten** (PO: „immer sichtbar“; „Standard: …“ beschreibt den Standard, bleibt wahr). Kein `createMode`-Durchreichen (fehlt in VersandTab, CorridorEditorMobile, Compare).
4. **Texte kontextabhängig über Lookup-Map** indexiert mit `context` — keine neuen `context ===`-Zeilen (HERKUNFT-Ratsche bleibt bei 46). `t()` hat keine Interpolation → je Kontext vollständiger Schlüssel.
5. **Kanal-Schwelle:** sichtbares Label „Dringlichkeits-Schwelle“ einmal im acp-head + ⓘ.
6. **CAPE:** Map Metrik→Erklärschlüssel mit nur `cape`; ⓘ am Label; vorhandener `title` bleibt.
7. **Produktregel:** Texte erklären Begriffe/Standards, keine Handlungsempfehlungen; immer „Trip“.

### Dependencies
- Upstream: `bits-ui` 2.17.3 Popover (`node_modules` fehlt im Worktree → vor Bau `npm ci` im Worktree-Frontend), `t()`/`de.json` (#2520), Tokens `app.css`.
- Downstream: TripNewEditor, CompareNewEditor, TripTabs (+AlarmeScheduleTab/BriefingScheduleTab), CompareTabs — alle über dieselben Organismen.
- Tests: SSR-Harness rendert bits-ui bereits (`trip-new/__tests__/tripNewSsr.ts`), Popover-Portal aber nicht → Interaktion nur per Playwright.

### Risiken (zusätzlich zu den 12 aus dem Kontext)
- Desktop- und Mobile-Panel rendern gleichzeitig → `data-testid`/Popover-IDs pro Instanz eindeutig halten.
- Frontend-Browser-Gate: Konsolenfehler/Hydration durch Popover auf `/trips/new`, `/compare/new` blockt Deploy.
- Doppelte Erklärung: bestehende Lead-/hint-Texte (Wertebereiche, Cooldown) nicht widersprüchlich doppeln — Spec legt fest, ob sie bleiben.

### Open Questions (für die Spec; keine PO-Technikfragen)
- [ ] **Nebenbefund Alarm-Kanal-Default:** Trip-Anlage hat Alarm-Telegram AN (#2518), Vergleichs-Anlage nur E-Mail (`alarmePropsAus.ts:88-93`). Infobox-Text muss den echten Ist-Stand je Kontext nennen; die Abweichung selbst ist nicht S1 → als Paritätsbefund melden (Bezug #2518), nicht in S1 fixen.
- [ ] Infobox für Trip-`wegpunkte`: in S1 aufnehmen (überspringbar) — Spec entscheidet Ablage (trip-eigener Reiter, Pendant-Sperre beachten: nur Einbau, kein neuer Baustein).
- [ ] Bleiben die bestehenden Lead-/hint-Texte (Wertebereiche, Cooldown, Alert-Kanäle) neben der neuen Erklärung stehen? Empfehlung: ja, unverändert (S1 ist additiv).

## Übergabe aus Phase 5 (RED) an /50-implement

Die RED-Tests legen diese Schnittstellen fest. Der Implementierer baut genau danach:

- **Prop `showInfobox`** (boolean, Default `false`) an `WeatherMetricsTab`, `CorridorEditor`, `CorridorEditorMobile`, `AlarmeTab`, `VersandTab`. `TripNewEditor`/`CompareNewEditor` setzen es an JEDEM Mount explizit `showInfobox={true}`. Gezählte Mounts: Trip je 2× `WeatherMetricsTab`/`CorridorEditor`/`AlarmeTab`/`VersandTab`; Vergleich `WeatherMetricsTab` 2, `CorridorEditor` 1, `CorridorEditorMobile` 1, `AlarmeTab` 2, `VersandTab` 2. Hubs (`TripTabs`, `AlarmeScheduleTab`, `BriefingScheduleTab`, `CompareTabs`) und `*PropsAus`-Bündel setzen es NICHT.
- **`molecules/Infobox.svelte`**, Props `{reiter, context}` → `<aside data-testid="infobox-<reiter>-<route|vergleich>">`, ohne button/input/a/onclick. Reiter-IDs `wetter-metriken`, `wertebereiche`, `alarme`, `versand`, `wegpunkte` (nur route). Trip-Wegpunkte-Panel in `TripNewEditor`: je eine `<Infobox>` im Desktop- und Mobil-Baum (genau 2). Steht oben im Organismus, außerhalb jeder Lade-/Fehlerverzweigung.
- **`molecules/BegriffErklaerung.svelte`**, Prop `begriff` ∈ `wertebereiche | kanal_schwelle | cape | cooldown` → `<button type="button" data-testid="begriff-erklaerung-<begriff>[-suffix]" aria-label={t('tip.aria.<begriff>')}>ⓘ</button>`; genau ein ⓘ je Instanz.
- **`shared/infoboxKeys.ts`**: `infoboxKey(context, reiter)` → `info.<reiter>.<kontext>`; `BEGRIFF_KEYS` mit den vier Begriffen.
- **`ui/popover/`** nach Schema `ui/dialog/`: `popover.svelte`, `popover-content.svelte`, `popover-trigger.svelte`, `index.ts` (Tests lesen `popover-content.svelte`).
- **Katalog `de.json`**: genau neun `info.*` (Reiter-ID mit Bindestrich, z. B. `info.wetter-metriken.route`; kein `info.wegpunkte.vergleich`), `tip.wertebereiche|kanal_schwelle|cape|cooldown`, `tip.aria.<begriff>` (nennt „Wertebereich“, „Dringlichkeits-Schwelle“, „CAPE“, „Cooldown“). Wortlaut wortgleich zur Spec (Literale in `shared/__tests__/infoboxTexte.ts`). Keine weiteren `info.*`/`tip.*`.
- **Platzierung**: ⓘ Wertebereiche in allen 5 Eyebrow-Zweigen des Corridor-Editors (Fehler, Laden vergleich/route, Haupt vergleich/route) und in `CorridorEditorMobile`. Kanal-Schwelle: sichtbares Label „Dringlichkeits-Schwelle“ + ⓘ in `alert-channel-picker`, `aria-label` der Stufen-Gruppe bleibt. CAPE: ⓘ im `.metric-label`-`td` von `AlertMetricLevelRow`, nur bei `cape`, `title` der Schwellwert-Zelle unverändert. Cooldown: ⓘ in `AlertCooldownCard` vor dem Eingabefeld, `.hint` unverändert.
- **Styling (AC-14)**: `Infobox.svelte` und `popover-content.svelte` setzen Text- und Hintergrundfarbe explizit als `var(--g-…)` mit `#rrggbb`-Tokens aus `app.css` (kein Tailwind-Klassenstil wie `dialog-content`), nie `--g-ink-4`. `BegriffErklaerung.svelte`: `color: var(--g-…)`; am `<button>` `display` und Breite/Höhe ≥ 24 px außerhalb von `@media`.
- **AC-15**: In den Bausteinen ist nur das Zeichen ⓘ als Markup-Text erlaubt, alles andere über `t()`.
- **AC-10 ohne Browserfall**: `cape` ist `selectable=False` (#1585); die Alarm-Zeilen im Anlege-Flow kommen aus dem wählbaren Katalog (`deriveActiveAlertMetricsForTrip`), die CAPE-Zeile ist in `/trips/new` und `/compare/new` nicht erreichbar. AC-10 ist am Baustein bewacht (`begriff_erklaerung_an_den_vier_begriffen.test.ts`).
- **CI**: `frontend/e2e/begriff-erklaerung.spec.ts` steht schon in RED auf `.github/ci_e2e_specs.txt` (`E2E_MIN_SPECS` 62). Der `e2e`-Check ist bis GREEN rot; Filter-B-Messung (3× grün) gehört zu /50. Die Mobil-Fälle auf `/compare/new` verkleinern den Viewport erst nach der Navigation; ob das im Browser trägt, ist ungeprüft.
