# Context: feature-2346-cockpit-paritaet

## Request Summary
Issue #2346 (Epic #2345, Etappe P6): Startseite (Kachel, Hero, Zeilen-Bausteine) für Trip und Ortsvergleich auf **einen** Baustein mit `kind` bringen und die Pendant-Sperre (`.claude/hooks/pendant_gate.py`) so erweitern, dass Paare auch an Namensmustern außerhalb der heute überwachten Ordner erkannt werden — mit einer Ausnahmeliste, die nur schrumpfen darf. Prüfdatum des Gates: **2026-11-03** (danach schaltet es sich selbst ab, `pendant_gate.py:34`, `:226-229`).

Gemessen 2026-10-23 auf Worktree `worktree-declarative-orbiting-wave` (Basis `49b0826e4`).

## Related Files

### Startseite
| File | Relevance |
|------|-----------|
| `frontend/src/routes/+page.svelte` | Einziger Einbinder: `TripKachel` :841 (nur `otherTrips`, nicht im `planning`-Modus), `CompareKachel` :792 (`activePresets`), `CompareStatusRow` :830 („Außerdem beobachtet"), `EmptyKachel` :207. Hero für Trip (~:2xx–480) und Vergleich (:487–700) **inline**. :580 nutzt `compareHero.empfaenger` als Kanäle (Verstoß gegen #1452, Feld sonst stillgelegt) |
| `frontend/src/routes/+page.server.ts:21-28` | Lädt `/api/trips`, `/api/compare/presets`, `/api/cockpit/status` parallel |
| `frontend/src/routes/_home/TripKachel.svelte` (103 Z.) | Eigenes `<a>`, **kein** geteilter Baustein. Zeigt Typ-Label, Status (`tripStatus()`), Name, Datumsspanne, „N Etappen · Reports ✓". Kein nächster/letzter Versand, keine Kanäle, keine Aktionen |
| `frontend/src/routes/_home/CompareKachel.svelte` (23 Z.) | Hülle um `organisms/SubscriptionCard.svelte` mit `kind="vergleich"`, `compact`, `actions={compareKachelActions()}` |
| `frontend/src/routes/_home/kachelActions.ts:3-5` | Nur `edit/Bearbeiten` (#2278 AC-15) |
| `frontend/src/lib/components/organisms/SubscriptionCard.svelte` (266 Z.) | **Bereits geteilte Karte** aus #2278 (`kind: 'trip'|'vergleich'`, :24); für Trips schon in `routes/trips/+page.svelte:220`. Nur-Vergleich-Zweige: Kanäle :79/:207, Zeitplan-Label :80, „zuletzt …" :81-83 (Trip fest `relativeLastSent(undefined)`), Fußzeile :236ff |
| `frontend/src/lib/components/organisms/HomeHeroTrip.svelte` / `HomeHeroCompare.svelte` | **Produktiv unbenutzt** (nur Barrel `organisms/index.ts:29-30` + Tests). Eigene Ersatz-Interfaces, `href="#"` |
| `frontend/src/lib/types.ts` | `Trip` :359 (kein `letzter_versand`; flache abgeleitete `morning_*`/`send_*` :385-397), `BriefingLogEntry` :629ff (`entity_id/entity_type`, #2281), `CockpitStatus` :656, `ComparePreset` :664 (`letzter_versand` :676, Kanal-Flags, Slots, `paused_at`) |
| `frontend/src/lib/utils/cockpitHelpers568.ts:231,248` | `deriveNextSend`/`primarySendSlot` — nur `ComparePreset` |
| `frontend/src/lib/components/compare/subscriptionHelpers.ts:211,269` | `presetChannels`/`presetTileScheduleLabel` — nur `ComparePreset` |
| `frontend/src/routes/_home/cockpitHelpers.ts:137,156,172` | Trip-Seite: `heroKanaele(report_config)`, `plannedBriefings` (filtert `entity_type==='trip'`) |
| `internal/handler/cockpit.go:27-30` | Cockpit-Status liefert nur Briefings von **heute** |
| `src/services/briefing_log.py`, `GET /api/briefings/{id}/briefing-history` | Kind-neutrale Versand-Historie (#2281) — Datenquelle für „letzter Versand" eines Trips existiert, aber kein Feld am Trip-Objekt |

### Molecules (Ticket-Paarung ist nur namentlich, nicht fachlich)
| Molecule | Produktive Importeure | Befund |
|---|---|---|
| `DetailRow`, `ThresholdRow`, `ChannelRow`, `BriefingScheduleRow` | keine (nur `_design-system/+page.svelte` + Tests) | allgemeine Design-System-Molecules, **keine** Trip-Bausteine |
| `CompareIdealRow` | **keine** (Test `issue_491…test.ts:155` prüft Nicht-Import) | **tot** |
| `CompareLocationRow` | `compare/CompareTabs.svelte:15,914` | compare-eigen (Orte-Tab) |
| `CompareStatusRow` | `routes/+page.svelte:12,830` | Kompaktzeile Name/nächster Versand/Kanäle; kein Trip-Gegenstück |

### `shared/` mit Compare-Präfix
| Datei | Befund |
|---|---|
| `shared/CompareHourlyLayoutControls.svelte` (294 Z.) | compare-only: einmal eingebunden `WeatherMetricsTab.svelte:1590` im Zweig `context === 'vergleich'` (:1429); Abschnitt `stundenverlauf` ist `COMPARE_ONLY_SECTIONS` (`weatherMetricsTabSections.ts:48`) |
| `shared/CompareOutlookLayoutControls.svelte` (272 Z.) | **schon geteilt**: Vergleich :1616, Trip :2013 (#1720 S1); Test `outlook_erbt_grundauswahl_structure.test.ts:168-172` verlangt beide Einbindungen ⇒ nur Umbenennung nötig |

### Pendant-Sperre
| File | Relevance |
|------|-----------|
| `.claude/hooks/pendant_gate.py` (324 Z.) | PreToolUse/Bash auf `git commit` (`.claude/settings.json:57-65`). Überwacht `components/{compare,compare-new}/` ↔ `{trip-detail,trip-new}/` + `src/output/renderers/**/{compare_,trip_}*.py` (:53-61, :150-165). Nur **Neuanlagen** (`A`, `R` außer gleiche Seite ≥95 %). Ausnahme `gz-eigenstaendig:` (≥15 Wortzeichen) in den ersten 20 Zeilen. Exit 2 = Block, eigene Störung ⇒ 0. `_gegenstueck` (:188-207) findet nur getauschtes Präfix, keine neutralen Pendants |
| `tests/tdd/test_pendant_gate.py` (31 Tests), `tests/tdd/test_commit_gate_invocation_forms.py:190ff` | bestehende Gate-Tests |
| `docs/specs/modules/feat_1481b_pendant_gate.md` | Spec (implemented) |
| `docs/reference/gates_und_ratschen.md` :99-114, :426, :453 | Doku; Prüfdatum-Zeile ohne Fang-Beleg |

## Existing Patterns
- **Geteilte Karte statt Doppel:** `SubscriptionCard` mit `kind` (#2278) ist das Vorbild; die Trip-Liste nutzt sie bereits. Naheliegend: TripKachel durch `SubscriptionCard kind="trip" compact` ersetzen und die Nur-Vergleich-Zweige kind-neutral machen.
- **„Darf nur schrumpfen"-Ausnahmelisten:** `tests/unit/test_compare_catalog_derives_from_central_catalog.py` (:27-44, :310, :322) — Festlegung auf Inhalt + Test auf veraltete Einträge; härter: Obergrenze `assert len(KNOWN_VIOLATIONS) <= 1` (`tests/test_trips_path_revival_guard.py:483`), eingefrorene Liste `context_herkunft_zweige_eingefroren.test.ts:467`. Für AC-3 („Hinzufügen blockiert") passt fester Inhalt / Obergrenze.
- **Kanal-Anzeige aus Flags**, nicht aus `empfaenger` (#1452; `cockpitHelpers.ts:270-272`).

## Namensmuster-Aufmaß (ohne Tests)
Strenge Paare (getauschtes Präfix oder neutraler Name): **9**, davon **7 außerhalb** der heutigen Gate-Reichweite:
`CompareTabs`/`TripTabs` (überwacht) · `CompareNewEditor`/`TripNewEditor` (überwacht) · `HomeHeroCompare`/`HomeHeroTrip` · `CompareKachel`/`TripKachel` · `compare_alert.py`/`trip_alert.py` · `compare_alert_channels.py`/`alert_channels.py` · `compare_preview_service.py`/`preview_service.py` · `compare_weather_snapshot.py`/`weather_snapshot.py` · `compareChannelMetricLayouts.ts`/`channelMetricLayouts.ts`.
Dazu ~8 ähnliche, nicht namensgleiche Paare (z. B. `compare_slot_scheduler.py`/`trip_report_scheduler.py`, `compare_preset.go`/`trip.go`). 36 Dateien mit Compare-Präfix insgesamt.

## Dependencies
- Upstream: `SubscriptionCard` + `subscriptionActions` (#2278), Briefing-Log (#2281), Cockpit-Status-Endpunkt, `hook_utils.is_git_subcommand`.
- Downstream: Startseite (jeder Nutzer), alle Commits aller Sitzungen (Gate).

## Existing Specs
- `docs/specs/modules/startseite_kacheln.md` (F76, draft), `screen_home_migration.md` (#386), `home_h1_trip_terminology.md`, `home_weather_fetch_timeout.md`
- `docs/specs/modules/feat_2278_aktionsmodell.md` (implemented), `feat_2281_vergleich_versand_historie.md` (Kopf noch `draft`, faktisch umgesetzt)
- `docs/specs/modules/feat_1481b_pendant_gate.md`
- Archiv: `issue_294_home_kachel`, `issue_571_home_cockpit_hero`, `issue_372_molecules`, `issue_489_compare_row_molecules`, `issue_578_molecules_organisms`

## Tests
- Unit (`node --test`): `routes/_home/__tests__/*`, `routes/_home/cockpitHelpers.test.ts`, `routes/__tests__/{cockpit_alerts_entity_filter,startseite_*}.test.ts`, `lib/utils/__tests__/report_slot_aktiv.test.ts:178-193` (SSR-Render TripKachel), `organisms/__tests__/subscription_card.test.ts`, `lib/issue_393_cockpit_kacheln.test.ts`, `lib/issue_579_home_screen.test.ts`, `lib/issue_647_home_fidelity.test.ts`, `molecules/issue_578_molecules_organisms.test.ts:310-355` (HomeHero*), `shared/__tests__/aktionsmodell_bausteine_ausloeser.test.ts:79-83`
- E2E: `startseite.spec.ts`, `issue-294-home-kachel.spec.ts` (**veraltet**: suchen `subscription-card` exakt + H1 „Startseite"), `issue-579-home-fidelity.spec.ts` — keine davon in `.github/ci_e2e_specs.txt`

## Risks & Considerations
1. **Ticket-Annahmen teilweise überholt:** HomeHero-Organismen sind tot (nicht vereinen, sondern löschen bzw. Inline-Hero betrachten); `CompareOutlookLayoutControls` ist bereits geteilt (nur umbenennen); die vier „Trip-Molecules" sind keine Trip-Bausteine. Die echte Doppelung des Heros steckt **inline** in `+page.svelte`.
2. **AC-1 braucht Trip-Daten, die es am Trip-Objekt nicht gibt:** letzter Versand (Log-Quelle vorhanden, kein Feld), nächster Versand (keine Trip-Funktion). Entweder Go-Feld/Cockpit-Erweiterung (Backend-Anteil) oder Ableitung im Frontend aus `report_config` + Briefing-Log.
3. **Gate-Fehlalarme blockieren alle Sitzungen.** Namensmuster über `src/services/**` und `internal/handler/**` greifen breit; Ausnahmeliste muss alle heutigen Paare enthalten und darf nur schrumpfen. Gate-Störung muss weiter ⇒ Exit 0 bleiben.
4. **Prüfdatum 2026-11-03:** Ohne Verlängerung/Beleg schaltet sich das Gate in 11 Tagen ab. Die Erweiterung braucht ein neues Prüfdatum (+90 Tage, Regel-Budget) und den Eintrag in `gates_und_ratschen.md`.
5. **Commit-Gate-Hooks sind Hoch-Risiko** für den Adversary (≥2 Runden).
6. Veraltete Home-E2E-Specs: Fresh-Eyes-Screenshot-Paar (AC-1) braucht eine lauffähige Spec bzw. eigene Staging-Messung.
7. Nebenbefunde (Triage → #1199): `+page.svelte:580` `empfaenger` als Kanäle (#1452-Verstoß), `feat_2281`-Spec-Kopf `draft`, `CompareIdealRow` tot.
8. Umfang: Frontend + Gate + ggf. Backend-Feld ⇒ LoC-Limit 250 wahrscheinlich überschritten; ggf. Scheibenschnitt (S1 Startseite, S2 Gate) — Gate wegen Prüfdatum zuerst erwägen.

## Analysis

### Type
Feature (Rework, Teil von Epic #2345 Etappe P6). Zwei fachlich getrennte Vorhaben in einem Ticket: **Startseiten-Parität** und **Erweiterung der Pendant-Sperre**.

### Abstimmung mit #1969 (Sitzung gregor-zwanzig-d6, 2026-10-23)
- „Nächster Versand“ wird in #1969 **eine** Python-Ableitung für Trip UND Ortsvergleich (Scheduler-Bausteine `_slot_stunde`/`trip_local_now`/`tz_for_coords`, Pausen, skip_next), ausgeliefert über Go als Feld an den Listen-/Detail-Objekten. Vorläufiger Name `next_briefing`: ISO-8601 mit Offset, IANA-Zone/Kürzel, `null` wenn nichts ansteht, optional Grund. **Verbindlich erst nach PO-Freigabe der #1969-Spec.**
- **Korrektur d6 (2026-10-23, später):** „Nächster Versand“ kommt voraussichtlich **nicht** als Feld am Trip-/Preset-JSON. Grund: Diese Listen liefert Go allein aus dem Store, die Fälligkeit liegt nur in Python. Ein Feld hieße N+1 Go→Python und würde den ETag berühren.
  - Arbeitsrichtung: eigener Abruf `GET /api/next-briefings` als Go-Proxy, `user_id` aus dem Auth-Kontext.
  - Antwort `{trips: {<id>: NextBriefing}, compare: {<id>: NextBriefing}}`, optionaler Filter `?trip_id=` / `?preset_id=`.
  - `NextBriefing` = `{at: ISO-8601+Offset | null, local_date, local_time "HH:00", tz, tz_abbr, slot, skipped?, reason?}`. Ist `at` null, ist `reason` Pflicht.
  - Folge für #2346: Die Startseite lädt diese Datenquelle **zusätzlich** in `+page.server.ts`. Die Kachel nimmt `nextSend` als Prop. Verbindlich wird das erst mit der Freigabe der #1969-Spec.
- #1969 löst auch `deriveNextSend` (Frontend), `_compute_next_send` (Compare-Mail) und die feste HubOverview-Zeit ab.
- **Folge für #2346:** keine eigene Fälligkeitsrechnung, `deriveNextSend` nicht anfassen. Die Kachel bekommt einen kind-neutralen Platz `nextSend` (nullable). Der Trip-Wert für AC-1 „nächster Versand“ wird als **Abhängigkeit von #1969** markiert. Feldname/Format meldet d6 nach seiner Spec-Freigabe.
- Begründung gegen Frontend-Ableitung: Trip-Slots sind Ortszeit des Startpunkts. Eine Browser-Rechnung aus `morning_time` zeigt in fremder Zone eine falsche Zeit (genau der #1969-Befund).

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `.claude/hooks/pendant_gate.py` | MODIFY | Zweite Erkennung `_namenspendant()`: Basisnamen-Muster `Compare*`/`Trip*`, `*Compare`/`*Trip`, `compare_*`/`trip_*`, neutral `Foo`↔`CompareFoo` in `frontend/src/lib/components/**`, `frontend/src/routes/**`, `src/services/**`, `internal/handler/**`. Nur Neuanlagen (A, R <95 %), `gz-eigenstaendig:` bleibt, Störung ⇒ Exit 0. Konstante `BEKANNTE_PAARE` (schrumpfende Ausnahmeliste). Prüfdatum neu **2027-01-21** |
| `tests/tdd/test_pendant_gate.py` | MODIFY | Fälle AC-2 (neues `CompareFoo` neben `Foo`/`TripFoo` ⇒ Exit 2), Nicht-Fehlalarm für alle Bestandspaare, Testdateien ausgenommen, leerer Rest (`Compare.svelte`) |
| neuer Test „Ausnahmeliste darf nur schrumpfen“ | CREATE | Jeder Eintrag existiert noch (veraltete fallen auf) + Liste ⊆ eingefrorene Menge / `len <= N` ⇒ Hinzufügen rot (AC-3). Muster `tests/unit/test_compare_catalog_derives_from_central_catalog.py:27-44`, `tests/test_trips_path_revival_guard.py:483` |
| `docs/reference/gates_und_ratschen.md` | MODIFY | Reichweite, Ausnahmeliste, neues Prüfdatum, Fang-Beleg (:99-114, :426, :453) |
| `frontend/src/lib/components/organisms/SubscriptionCard.svelte` | MODIFY | Nur-Vergleich-Zweige kind-neutral: Kanäle :79 + `!compact`-Block, Zeitplan :80, letzter Versand :81-83 (Trip fest `undefined`), Fußzeile ~:236. Props `nextSend?`/`lastSent?`. **Achtung:** auch die sichtbare Vergleichs-Kachel ändert sich (compact zeigt künftig Kanäle + Fußzeile für beide) |
| `frontend/src/routes/_home/TripKachel.svelte` | MODIFY/DELETE | Durch Wrapper um `SubscriptionCard kind="trip" compact` ersetzen (Muster `CompareKachel.svelte`) bzw. eine gemeinsame `SubscriptionKachel` für beide kinds |
| `frontend/src/routes/_home/CompareKachel.svelte`, `kachelActions.ts` | MODIFY | Auf gemeinsamen Kachel-Baustein konvergieren |
| `frontend/src/routes/+page.svelte` | MODIFY | Einbindung :792/:841; Hero inline (Trip ~:2xx–480, Vergleich :487–700) → `HomeHero kind` (eigene Scheibe); :580 `compareHero.empfaenger` als Kanäle (#1452-Verstoß) mitbeheben |
| `frontend/src/routes/+page.server.ts` | MODIFY | „Letzter Versand“ für Trips über **einen** Sammelaufruf (kein N+1 je Kachel); Quelle Briefing-Log #2281 |
| `frontend/src/routes/_home/cockpitHelpers.ts` | MODIFY | Trip-Kanäle aus `report_config`-Flags (`heroKanaele`/`reportChannels` :123/:137), nie `empfaenger` |
| `organisms/HomeHeroTrip.svelte`, `HomeHeroCompare.svelte`, `organisms/index.ts:29-30` | DELETE | produktiv tot |
| `molecules/CompareIdealRow.svelte` | DELETE | tot (Test `issue_491…test.ts:155` mitziehen) |
| `shared/CompareOutlookLayoutControls.svelte` | RENAME | → `shared/OutlookLayoutControls.svelte` (schon geteilt; Test `outlook_erbt_grundauswahl_structure.test.ts:168-172`) |
| `shared/CompareHourlyLayoutControls.svelte` | MOVE | → `components/compare/` (compare-only, `stundenverlauf` ist `COMPARE_ONLY_SECTIONS`) — AC-4 |
| Tests: `report_slot_aktiv.test.ts:178-193`, `issue_578_molecules_organisms.test.ts:310-355`, `subscription_card.test.ts`, `routes/_home/__tests__/*`, E2E `startseite.spec.ts` | MODIFY | Selektor `trip-card` → `subscription-card-{id}`, HomeHero-Tests entfallen |
| Backend (Go/Python) | offen | `next_briefing` kommt aus #1969. **Letzter Versand für Trips braucht Backend-Arbeit** (siehe „Letzter Versand“ unten) |

### Scope Assessment
- Files: ~20
- Estimated LoC: ~+700/-500 gesamt (deutlich > 250) ⇒ Scheibenschnitt **innerhalb dieses Tickets** (kein Abspalten von Resten):
  - **S1 Gate** (zuerst, Prüfdatum 2026-11-03): ~250 LoC. Ausnahmeliste enthält alle heutigen Paare.
  - **S2 Startseiten-Kachel** (gemeinsamer Kachel-Baustein, Trip-Kanäle/letzter Versand, Platz für `next_briefing`, tote HomeHero*/CompareIdealRow löschen): ~250–350 LoC, ggf. `loc_limit_override`.
  - **S3 Hero + shared/** (`HomeHero kind` aus Inline-Code, #1452-Fix :580, Rename/Move `shared/Compare*`, erledigte Einträge aus Ausnahmeliste streichen).
  - **S4 (nach #1969 S1):** `last_briefing` (Python-Ableitung) in `GET /api/next-briefings` ergänzen. Kachel auf `next`/`last` verdrahten, damit ist AC-1 vollständig. Backend-Anteil, Test mit zwei Nutzern.
- Risk Level: **MEDIUM–HIGH** — Commit-Gate betrifft jede Sitzung (Fehlalarm blockiert alle); Startseite sieht jeder Nutzer.

### Technical Approach
1. **Gate:** zusätzliche Namensmuster-Erkennung neben der Ordner-Erkennung, nicht `_gegenstueck` umbauen. Ausnahmeliste als feste Konstante im Hook, Test erzwingt „nur schrumpfen“. Alle heutigen Paare (9 strenge, 7 davon außerhalb heutiger Reichweite, ~8 ähnliche) gegen Fehlalarm testen. Adversary ≥2 Runden.
2. **Kachel:** `SubscriptionCard` ist bereits die geteilte Karte (#2278); Trip-Startseite nutzt sie bisher nicht. Ein Kachel-Baustein mit `kind` für beide; Felder Status · nächster Versand · letzter Versand · Kanäle in identischer Anordnung. Trip „nächster Versand“ zeigt bis #1969 einen ehrlichen Leerzustand.
3. **Hero:** tote Organismen löschen; die echte Doppelung (inline in `+page.svelte`) in einen `HomeHero kind` zusammenführen.
4. **shared/:** geteiltes umbenennen, compare-only herausziehen.
5. Fresh-Eyes-Nachweis über eigene Staging-Messung (Home-E2E-Specs veraltet, nicht in `ci_e2e_specs.txt`).

### Letzter Versand für Trips (Backend-Anteil, offen)
- Heute gibt es keine Sammelquelle: `cockpit/status` liefert nur Briefings von **heute** (`internal/handler/cockpit.go:27-30`). Ein Trip, der gestern versendet hat, stünde auf „zuletzt —“. `briefing-history` je Trip ergibt N+1. Am Trip-Objekt fehlt das Feld, `ComparePreset` hat `letzter_versand` (`types.ts:676`).
- Jede ehrliche Lösung ist Backend-Arbeit: Feld am Trip-Listenobjekt (abgeleitet aus dem Briefing-Log #2281, nicht persistiert) oder Erweiterung von `cockpit/status`.
- **Entschieden mit d6 (2026-10-23):** #1969 nimmt `last_briefing` **nicht** auf. #2346 ergänzt `last_briefing` **nach dem Merge von #1969 S1 im selben Endpunkt** `GET /api/next-briefings`. Die Ableitung kommt in Python als `_internal` aus dem Briefing-Log #2281. So bleibt es bei einer Datenquelle für die Kachel, ohne zweiten Endpunkt. Eine Kollision am Go-Trip-DTO gibt es nicht, weil #1969 es nicht anfasst. d6 meldet Feldname und Format, sobald S1 in `main` ist.
- Falls #2346 es selbst liefert: Datenbewegender Pfad, also Pflicht zum Test mit **zwei Nutzern**, `user_id` aus dem Auth-Kontext. Ein abgeleitetes Feld ist keine Persistenz-Änderung; falls doch persistiert wird, gilt Read-Modify-Write und `data_schema_backup`.
- S2 hat damit möglicherweise einen Backend-Anteil, Risiko steigt auf MEDIUM–HIGH.

### Stundenverlauf-Steuerung: Paar oder compare-eigen? (für AC-4)
- `CompareHourlyLayoutControls` wird nur im Vergleichszweig von `WeatherMetricsTab.svelte:1579-1590` eingebunden (Abschnitt `stundenverlauf`, #1360).
- Arbeitshypothese: Im Trip-Briefing **ist** die Haupttabelle schon die Stundentabelle, gesteuert über die normale Metrik-Auswahl. Der Vergleich hat als Haupttabelle die transponierte Übersicht (compare-eigen erlaubt) und einen zusätzlichen Stundenverlauf. Danach wäre die Steuerung ein Anhängsel der transponierten Übersicht und damit compare-eigen.
- **Diese Hypothese ist nicht belegt.** Die Spec muss sie am Code prüfen: Gibt es im Trip-Zweig eine Stunden-Layout-Steuerung unter anderem Namen? Falls ja, ist das ein Paar und wird zusammengeführt (dann kein MOVE). Falls nein: MOVE nach `components/compare/` und die Begründung in die Spec. Allein `COMPARE_ONLY_SECTIONS` reicht als Begründung nicht.

### Prüfdatum und Dringlichkeit von S1
- `pendant_gate.py:226-229`: Ab dem 2026-11-04 gibt das Gate still Exit 0. Die Gate-Tests frieren die Uhr nicht ein. Die blockierenden Fälle in `tests/tdd/test_pendant_gate.py` (z. B. `test_ac1_…blockiert`) werden dann **vermutlich rot**, der Kern-Testlauf und die CI-Ampel ebenfalls.
- S1 muss deshalb bis 2026-11-03 auf `main` sein (Spec, Freigabe, TDD, Merge).
- Begründung für das neue Prüfdatum 2027-01-21: Die Erweiterung der Reichweite ist eine neue Regel. Als Beleg dient das Aufmaß mit 7 Paaren außerhalb der heutigen Reichweite, die das alte Gate nicht fangen konnte. Das muss explizit in der Spec stehen, nicht als stille Verlängerung. Ob `gates_und_ratschen.md` eine Neudatierung bei Erweiterung erlaubt, ist in der Spec zu prüfen.

### AC-1-Wortlaut
- AC-1 bleibt ungeteilt. S4 (Trip-`next_briefing` verdrahten) ist **Teil dieses Tickets**. Das Ticket bleibt offen, bis S4 geliefert ist. Es gibt **keine** befristete Ausnahme der Art „Trip zeigt bis #1969 einen Leerzustand“.

### Dependencies
- Upstream: `SubscriptionCard`/`subscriptionActions` (#2278), Briefing-Log (#2281), `/api/cockpit/status`, `hook_utils.is_git_subcommand`, **#1969 (`next_briefing`)**.
- Downstream: Startseite (alle Nutzer), Commits aller Sitzungen (Gate).

### Ticket-Korrekturen (in Spec festhalten)
- Die vier „Trip-Molecules“ (`DetailRow`, `ThresholdRow`, `ChannelRow`, `BriefingScheduleRow`) sind allgemeine Design-System-Bausteine, keine Trip-Pendants ⇒ kein Paar.
- `HomeHeroTrip/Compare` sind tot; die Hero-Doppelung liegt inline.
- `CompareOutlookLayoutControls` ist schon geteilt.

### Nebenbefunde (Triage → #1199)
- `feat_2281`-Spec-Kopf steht auf `draft`, obwohl umgesetzt.
- Home-E2E-Specs `issue-294-home-kachel.spec.ts`/`issue-579-home-fidelity.spec.ts` veraltet.

### Open Questions
- [ ] Format/Name `next_briefing` — kommt von #1969 nach dessen Spec-Freigabe (keine PO-Frage).
- [x] Letzter Versand für Trips: #2346 liefert ihn selbst, als `last_briefing` im #1969-Endpunkt, nach #1969 S1. Damit gehört er zur Scheibe S4. Die Pflicht zum Test mit zwei Nutzern gilt.
- [ ] Stundenverlauf-Steuerung: Gibt es ein Trip-Pendant? Am Code prüfen, das entscheidet zwischen MOVE und Zusammenführen.

## Vertrag #1969 — `GET /api/next-briefings` (freigegeben 2026-10-23, verbindlich ab Merge #1969 S1)
Mitgeteilt von der Sitzung gregor-zwanzig-d6. Die Spec dazu: `docs/specs/modules/feat_1969_naechstes_briefing.md` (Worktree majestic-dazzling-knuth, noch nicht in main).
- Sammelantwort `{ "trips": { "<trip_id>": NextBriefing }, "compare": { "<preset_id>": NextBriefing } }`, optional `?trip_id=` / `?preset_id=`. **Kein** Feld am Trip-/Preset-JSON.
- `NextBriefing = { at: ISO-8601+Offset | null, local_date, local_time "HH:00", tz (IANA, Fallback "UTC"), tz_abbr, slot: "morning"|"evening", skipped?: {local_date, local_time, slot}, overdue?: true, reason?: "manual"|"paused"|"disabled"|"ended"|"none" (Pflicht wenn at==null, sonst fehlt es), paused_until? }`
- Vorrang der Gründe: manual → paused → disabled → ended → none. Ein archivierter Vergleich ⇒ "ended".
- `last_briefing` ist nicht Teil von #1969. #2346 ergänzt es nach S1 im selben Endpunkt (S4).
- Für S2: Die Kachel-Props `nextSend`/`lastSent` sind so zu typisieren, dass `NextBriefing` 1:1 hineinpasst. Bei `at===null` wird `reason` angezeigt (AC-15).

## RED-Phase (2026-10-23) — Übergabe an /50

**Lieferreihenfolge / CI:** Zwei getrennte Commits. Commit 1 = Spec/Kontext/Briefing + S1-Tests (`tests/tdd/test_pendant_gate.py`, `tests/tdd/test_pendant_gate_bekannte_paare.py`). Commit 2 = RED-Tests S2–S4. Die S2–S4-Tests sind rot, bis ihre Scheibe gebaut ist, und würden den S1-PR (`test`, `frontend-test`) rot machen. Für die S1-Auslieferung (Frist 2026-11-03) also einen eigenen Branch ab `origin/main` + Commit 1 + S1-Implementierung bilden; Commit 2 erst mit den Scheiben S2–S4 ausliefern.

**Festgelegte API (in den Tests verankert):**
- `frontend/src/routes/_home/SubscriptionKachel.svelte`: Props `kind`, `sub`, `nextSend: NextSendView|null`, `lastSent: string|null`, optional `now?: Date`. testids `kachel-status`, `kachel-next-send`, `kachel-last-sent`, `kachel-channels`, je Kanal `kachel-channel` (Label Email/Telegram/SMS/Premium-SMS). Wurzel bleibt `subscription-card-{id}` mit `data-kind`; `actions` aus `compareKachelActions` bzw. Trip-Pendant.
- `frontend/src/routes/_home/HomeHero.svelte`: Props `kind`, `sub`, `now?`. testids `home-hero` (Wurzel, `data-kind`), dann `home-hero-status`, `home-hero-title`, `home-hero-subtitle`, `home-hero-channels`, je Kanal `home-hero-channel`; kind-eigener Inhalt in `home-hero-body`.
- `frontend/src/routes/_home/kachelBriefings.ts`: `type NextSendView` (= NextBriefing unverändert), `kachelBriefingProps(resp, kind, id) => {nextSend, lastSent}`.
- Endpunkt-Erweiterung: Geschwister-Objekt `last_briefing: {trips: {<id>: ISO|null}, compare: {<id>: ISO|null}}` neben `trips`/`compare` (von d6 für #1969 bestätigt: bricht dort keinen Test). Alt-Log-Einträge ohne `entity_type` zählen als Trip; maßgeblich ist das Maximum von `sent_at`.

**Hinweise:**
- S4-Backend-Test braucht `--disable-socket --allow-unix-socket` (TestClient-Eventloop), Netz bleibt gesperrt.
- Go-Proxy-Test für AC-13/14 folgt in S4 nach Merge von #1969 S1 (Handler existiert noch nicht).
- Lücke: `_test.go` steht nicht in `TEST_ENDUNGEN` des Gates — neue Go-Testdateien `compare_x_test.go` neben `x_test.go` würden blockiert. In S1 mit aufnehmen (Testdatei-Ausnahme gilt laut Spec für alle Testdateien).
- Gate-Lesart: Partner wird im ganzen Repo gesucht (nicht nur im selben Ordner); ungültige Eingabe ⇒ Exit 0 **mit** stderr-Hinweis (neu).
- Beim Löschen der Altbausteine (S2/S3) umhängen statt löschen: `compare_kachel_aktionen.test.ts` (→ SubscriptionKachel), `issue_578_molecules_organisms`, `issue_489_compare_rows`, `issue_491_compare_detail`, `compare_channel_display_from_flags`, `issue_1273_s3_redirect_links`, `aktionsmodell_bausteine_ausloeser`, `report_slot_aktiv`.
