---
entity_id: feat_2346_cockpit_paritaet
type: feature
created: 2026-10-23
updated: 2026-10-23
status: draft
version: "1.0"
workflow: feature-2346-cockpit-paritaet
tags: [epic-2345, etappe-p6, startseite, pendant-sperre, trip-compare-teilung]
---

# Startseiten-Parität Trip/Ortsvergleich und erweiterte Pendant-Sperre (#2346)

## Approval

- [ ] Approved

## Purpose

Trip und Ortsvergleich zeigen auf der Startseite dieselben Felder (Status, nächster Versand, letzter Versand, Kanäle) in derselben Anordnung aus **einem** Baustein, statt aus zwei verschieden gebauten Kacheln und einer inline doppelten Hero-Fläche. Gleichzeitig wird die Pendant-Sperre (`.claude/hooks/pendant_gate.py`) so erweitert, dass sie neue einseitige Dateien auch an Namensmustern außerhalb der heute überwachten Ordner erkennt — mit einer Ausnahmeliste, die nur schrumpfen darf. Etappe P6 von Epic #2345.

## Source

- **File:** `frontend/src/routes/+page.svelte`, `frontend/src/lib/components/organisms/SubscriptionCard.svelte`, `.claude/hooks/pendant_gate.py`
- **Identifier:** Startseiten-Kachel (`TripKachel`/`CompareKachel` → ein Baustein), `HomeHero` mit `kind`, Funktion `_namenspendant()` und Konstante `BEKANNTE_PAARE` im Hook, Feld `last_briefing` am Endpunkt `GET /api/next-briefings`

## Ticket-Korrekturen (am Code gemessen, 2026-10-23)

Das Ticket #2346 beschreibt den Bestand an drei Stellen überholt oder falsch. Maßgeblich ist diese Liste:

1. Die vier „Trip-Molecules" `DetailRow`, `ThresholdRow`, `ChannelRow`, `BriefingScheduleRow` sind allgemeine Design-System-Bausteine (nur `_design-system/+page.svelte` und Tests importieren sie). Sie sind **kein** Paar und werden nicht angefasst.
2. `organisms/HomeHeroTrip.svelte` und `HomeHeroCompare.svelte` sind produktiv **tot** (nur Barrel `organisms/index.ts:29-30` und Tests). Die echte Hero-Doppelung steckt **inline** in `frontend/src/routes/+page.svelte` (Trip-Hero ca. :2xx–480, Vergleichs-Hero :487–700). Ebenso tot ist `molecules/CompareIdealRow.svelte`.
3. `shared/CompareOutlookLayoutControls.svelte` ist bereits geteilt (Vergleich `WeatherMetricsTab.svelte:1616`, Trip `:2013`, #1720 S1) — es fehlt nur der Name. `shared/CompareHourlyLayoutControls.svelte` ist dagegen compare-only (siehe nächster Abschnitt).

## Befund Stundenverlauf-Steuerung (AC-4-Entscheidung)

Frage: Hat der Trip-Zweig von `WeatherMetricsTab.svelte` eine Stunden-Layout-Steuerung unter anderem Namen? **Nein.** Belege:

- `CompareHourlyLayoutControls` wird genau einmal eingebunden: `frontend/src/lib/components/shared/WeatherMetricsTab.svelte:1590`, im Zweig `context === 'vergleich'` (öffnet `:1429`), geschützt durch `sections.includes('stundenverlauf')` (`:1579`).
- Der Abschnitt `stundenverlauf` wird nur im Vergleich geschaltet: `frontend/src/lib/components/shared/weather-metrics-tab/weatherMetricsTabSections.ts:48` (`COMPARE_ONLY_SECTIONS`) und `:73`. Der Trip-Zweig (ab `:1971`, Ausblick `:2004-2025`) enthält keine Stundenverlauf-Steuerung; `grep` nach `stundenverlauf|HourlyLayout|hourly_metric_keys` in `trip-detail/`, `trip-new/`, `trips/` ergibt keinen Treffer.
- Fachliche Begründung: Beim Trip **ist** die Haupttabelle der Mail bereits die Stundentabelle; ihre Spalten steuert die normale Metrik-Auswahl (Grundauswahl und Reihenfolge). Beim Ortsvergleich ist die Haupttabelle die transponierte Vergleichsübersicht (Orte = Spalten, ausdrücklich compare-eigen erlaubt, CLAUDE.md). Der „Stundenverlauf" ist dort ein **Anhängsel** dieser Übersicht mit eigener Spalten-Auswahl, eigenem Schalter (`hourly_enabled`) und eigener Reihenfolge — ein Gegenstück ohne diese Übersicht gäbe es im Trip nicht.
- Entscheidung: **MOVE** nach `frontend/src/lib/components/compare/CompareHourlyLayoutControls.svelte` mit Kopfzeile `gz-eigenstaendig: Anhängsel der transponierten Vergleichsübersicht, Trip hat die Stundentabelle als Haupttabelle`. `COMPARE_ONLY_SECTIONS` allein ist ausdrücklich **nicht** die Begründung.
- Zu beachten: Der Kommentar in `weatherMetricsTabSections.ts:45-47` nennt die Beschränkung „Zuschnittgrenze der Scheibe". Diese Spec ersetzt ihn durch die fachliche Begründung oben (Kommentar wird in S3 angepasst), damit die Beschränkung nicht wie die #1720-Altlast (Zuschnittgrenze statt Entscheidung) liest.
- Die Datei hat Bezüge in ca. 9 Testdateien unter `shared/__tests__/` und `compare/` (Pfad `join(here,'..','CompareHourlyLayoutControls.svelte')`); sie werden in S3 mitgezogen. Die Tests lösen weiter relativ zur eigenen Testdatei auf.

## Estimated Scope

- **LoC:** gesamt ca. +700/-500 (weit über 250) ⇒ `loc_limit_override` nötig (`workflow.py set-field loc_limit_override 800`); je Scheibe siehe Scope-Tabelle
- **Files:** ca. 25 (inkl. Tests)
- **Effort:** high — vier Scheiben innerhalb dieses Tickets, **keine Reste werden abgespalten**; das Ticket bleibt offen, bis S4 geliefert ist

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `organisms/SubscriptionCard.svelte` (#2278) | module | bereits geteilte Karte `kind: 'trip'\|'vergleich'`, Basis des neuen Kachel-Bausteins |
| `shared/subscriptionActions.ts`, `_home/kachelActions.ts` (#2278) | module | Aktionsmodell; Startseiten-Kachel zeigt nur „Bearbeiten" |
| `src/services/briefing_log.py`, `GET /api/briefings/{id}/briefing-history` (#2281) | module | kind-neutrale Versand-Historie, Quelle für `last_briefing` |
| #1969 `GET /api/next-briefings` (Sitzung d6) | endpoint, **vorläufig** | liefert `{trips:{<id>:NextBriefing}, compare:{<id>:NextBriefing}}`, `NextBriefing {at\|null, local_date, local_time, tz, tz_abbr, slot, skipped?, reason?}`. Feldnamen/Format werden erst mit Freigabe der #1969-Spec verbindlich; d6 meldet sie. **S4 beginnt erst nach Merge von #1969 S1.** |
| `internal/handler/` (Go-Proxy), `api/routers/` (Python) | module | Auth-Kontext `user_id`, Mandantentrennung für den Endpunkt |
| `.claude/hooks/hook_utils.is_git_subcommand`, `tests/tdd/test_pendant_gate.py` | module | Commit-Erkennung und Gate-Testmuster (Wegwerf-Repos) |
| `docs/specs/modules/feat_1481b_pendant_gate.md` | spec | Vorgänger-Spec des Gates (Aufmaß-Messreihe, 95-%-Grenze) |
| `frontend/src/routes/_home/cockpitHelpers.ts` (`heroKanaele`, `reportChannels`) | module | Trip-Kanäle aus `report_config`-Flags (#1452) |
| `frontend/src/lib/utils/cockpitHelpers568.ts` (`deriveNextSend`) | module | **wird nicht angefasst** — Ablösung gehört #1969 |

## Scope

### Affected Files

| File | Change Type | Scheibe | Description |
|------|-------------|---------|-------------|
| `.claude/hooks/pendant_gate.py` | MODIFY | S1 | neue Funktion `_namenspendant()` neben `_gegenstueck` (nicht umgebaut), Konstante `BEKANNTE_PAARE`, `PRUEFDATUM` → 2027-01-21 |
| `tests/tdd/test_pendant_gate.py` | MODIFY | S1 | Fälle: neue Namens-Pendants ⇒ Exit 2, Ausnahmen, Störung ⇒ Exit 0 (Wegwerf-Repos) |
| `tests/tdd/test_pendant_gate_bekannte_paare.py` | CREATE | S1 | Ausnahmeliste: jeder Eintrag existiert, Liste ⊆ eingefrorene Menge, Bestandspaare ohne Fehlalarm |
| `docs/reference/gates_und_ratschen.md` | MODIFY | S1 (+S2/S3 Nachzug) | Reichweite, Ausnahmeliste, Prüfdatum, Beleg, Prüfdaten-Tabelle (:99-114, :426, :453) |
| `frontend/src/lib/components/organisms/SubscriptionCard.svelte` | MODIFY | S2 | Nur-Vergleich-Zweige kind-neutral (Kanäle :79, Zeitplan :80, letzter Versand :81-83, Fußzeile); neue Props `nextSend?`, `lastSent?` |
| `frontend/src/routes/_home/SubscriptionKachel.svelte` | CREATE | S2 | ein Kachel-Baustein für beide kinds (wrappt `SubscriptionCard compact`, `actions` aus `kachelActions.ts`) |
| `frontend/src/routes/_home/TripKachel.svelte`, `CompareKachel.svelte` | DELETE | S2 | ersetzt durch `SubscriptionKachel` |
| `frontend/src/routes/_home/cockpitHelpers.ts` | MODIFY | S2 | Trip-Kanäle aus `report_config`-Flags |
| `frontend/src/lib/components/organisms/HomeHeroTrip.svelte`, `HomeHeroCompare.svelte`, `organisms/index.ts` (:29-30) | DELETE/MODIFY | S2 | tot |
| `frontend/src/lib/components/molecules/CompareIdealRow.svelte` | DELETE | S2 | tot (Test `issue_491…test.ts:155` mitziehen) |
| Tests: `report_slot_aktiv.test.ts:178-193`, `issue_578_molecules_organisms.test.ts:310-355`, `subscription_card.test.ts`, `routes/_home/__tests__/*` | MODIFY | S2 | an neuen Baustein anpassen, HomeHero-Tests entfallen |
| `frontend/src/routes/+page.svelte` | MODIFY | S2/S3 | S2: Einbindung `SubscriptionKachel` (:792/:841); S3: Inline-Heros → `HomeHero` mit `kind`, :580-Fix |
| `frontend/src/routes/_home/HomeHero.svelte` | CREATE | S3 | ein Hero-Baustein mit `kind` (Muster `routes/_home/`, nicht `organisms/`, weil nur die Startseite ihn braucht) |
| `frontend/src/lib/components/shared/CompareOutlookLayoutControls.svelte` | RENAME | S3 | → `shared/OutlookLayoutControls.svelte`; Test `outlook_erbt_grundauswahl_structure.test.ts:168-172` und Importe nachziehen |
| `frontend/src/lib/components/shared/CompareHourlyLayoutControls.svelte` | MOVE | S3 | → `compare/CompareHourlyLayoutControls.svelte` mit `gz-eigenstaendig:`-Kopfzeile; ca. 9 Testdateien + Import `WeatherMetricsTab.svelte:118` nachziehen; Kommentar `weatherMetricsTabSections.ts:45-47` ersetzen |
| `.claude/hooks/pendant_gate.py` (`BEKANNTE_PAARE`), Test | MODIFY | S2/S3 | erledigte Paare (HomeHero*, Kachel) streichen, sobald die Dateien weg sind |
| `frontend/src/routes/+page.server.ts` | MODIFY | S4 | lädt `GET /api/next-briefings` zusätzlich (ein Sammelaufruf, kein N+1) |
| `src/services/` (Python-Ableitung `last_briefing` aus Briefing-Log #2281), `api/routers/` (Endpunkt-Erweiterung), `internal/handler/` (Go-Proxy-Durchreichung) | MODIFY/CREATE | S4 | `last_briefing` je Trip und Vergleich im #1969-Endpunkt |
| `frontend/src/lib/types.ts` | MODIFY | S4 | Typ `NextBriefing`/`LastBriefing`, Antwortform des Endpunkts |

### Estimated Changes (je Scheibe)

| Scheibe | Inhalt | LoC |
|---|---|---|
| S1 | Pendant-Sperre (zuerst — **muss vor 2026-11-03 auf `main`**) | ca. +250/-10 |
| S2 | gemeinsame Startseiten-Kachel, Kanäle aus Flags, tote Bausteine löschen | ca. +250/-220 |
| S3 | `HomeHero kind`, #1452-Fix, Rename/Move `shared/Compare*`, Ausnahmeliste kürzen | ca. +100/-200 (überwiegend Umbenennung/Verschiebung) |
| S4 | `last_briefing` + Verdrahtung next/last (nach #1969 S1) | ca. +150/-0 |

## Implementation Details

### S1 — Pendant-Sperre erweitern

Die bestehende Ordner-Erkennung (`FE_BEREICHE`, Renderer-Pfade, `_gegenstueck`) bleibt unverändert. Daneben tritt eine zweite, unabhängige Erkennung `_namenspendant()`:

- **Reichweite:** Neuanlagen unter `frontend/src/lib/components/**`, `frontend/src/routes/**`, `src/services/**`, `internal/handler/**` (Endungen `.svelte`, `.ts`, `.py`, `.go`).
- **Namensmuster:** Der Dateiname (ohne Endung) wird in Wörter zerlegt (CamelCase, `lowerCamel`, `snake_case`). Steht `compare` oder `trip` am Anfang oder Ende, gilt der Rest als „Kernname". Ein Treffer liegt vor, wenn im Repo (`git ls-files` plus der laufende Änderungssatz) eine Datei **gleicher Endung** mit dem gegenseitigen Präfix (`CompareFoo` ↔ `TripFoo`, `compare_foo` ↔ `trip_foo`, `FooCompare` ↔ `FooTrip`) existiert, oder eine neutrale Datei `Foo` — symmetrisch für **beide** Seiten (`CompareFoo.svelte` oder `TripFoo.svelte` neben `Foo.svelte`, `compare_alert_channels.py` neben `alert_channels.py`). Die Gegenrichtung (ein neues **neutrales** `Foo` neben bestehendem `CompareFoo`/`TripFoo`) ist die gewünschte Konvergenz und löst nichts aus.
- **Kein Treffer:** leerer Kernname (`Compare.svelte`); Testdateien (`TEST_ENDUNGEN`, `tests/`, `__tests__/`); Umbenennung mit Ähnlichkeit ≥ 95 % (`ECHTE_UMBENENNUNG`); Kopfzeile `gz-eigenstaendig: <≥15 Zeichen>` in den ersten 20 Zeilen (bestehende Mechanik, wiederverwendet); jede Datei, die per `BEKANNTE_PAARE` als Bestandspaar gelistet ist.
- **Nur Neuanlagen** (`A`, `R` unter 95 %); Änderung bestehender Dateien löst nichts aus. Exit 2 mit Meldung, die Partner und die beiden Auswege nennt (Datei nach `shared/` bzw. neutral benennen **oder** `gz-eigenstaendig:`).
- **Eigene Störung ⇒ Exit 0** und Hinweis auf stderr (Grundprinzip aller Wächter). Das gilt auch für Fehler **innerhalb** von `_namenspendant()`: Ein Fehler dort darf die bestehende Ordner-Erkennung nicht blockieren.
- **Bekannte Grenzen (dokumentieren, nicht verschweigen):** Ein neues `CompareFoo` **ohne** vorhandenen Partner wird nicht erkannt (ein Paar ist erst mit zwei Dateien ein Paar); ähnliche, aber nicht namensgleiche Paare (z. B. `compare_slot_scheduler.py`/`trip_report_scheduler.py`, `compare_preset.go`/`trip.go`, ca. 8) bleiben unerkennbar; Begründung wird auf Länge, nicht Substanz geprüft.
- **`BEKANNTE_PAARE`:** feste Konstante im Hook, bei Einführung genau die sieben Bestandspaare außerhalb der alten Reichweite: `HomeHeroCompare`/`HomeHeroTrip`, `CompareKachel`/`TripKachel`, `compare_alert.py`/`trip_alert.py`, `compare_alert_channels.py`/`alert_channels.py`, `compare_preview_service.py`/`preview_service.py`, `compare_weather_snapshot.py`/`weather_snapshot.py`, `compareChannelMetricLayouts.ts`/`channelMetricLayouts.ts`. (`CompareTabs`/`TripTabs` und `CompareNewEditor`/`TripNewEditor` fängt bereits die Ordner-Erkennung.) Die Liste darf nur schrumpfen: S2 streicht die HomeHero*- und Kachel-Paare, sobald ihre Dateien gelöscht sind.
- **Schrumpf-Test:** (a) jeder Eintrag in `BEKANNTE_PAARE` existiert noch als Datei (veralteter Eintrag ⇒ rot, zwingt zum Streichen), (b) `BEKANNTE_PAARE` ist Teilmenge einer **im Test eingefrorenen** Menge der sieben Paare (Hinzufügen ⇒ rot; Streichen ⇒ grün). Muster: `tests/test_trips_path_revival_guard.py:483`, `tests/unit/test_compare_catalog_derives_from_central_catalog.py:27-44`.
- **Prüfdatum und Regel-Budget:** `gates_und_ratschen.md` regelt eine Neudatierung bei **Erweiterung** nicht ausdrücklich. Es gilt nur die Generalregel („jede neue Pflicht-Regel … Prüfdatum +90 Tage", Zeile „Am Prüfdatum gilt: kein nachweisbarer Fang → Rückbau"), und die Zeile „Pendant-Sperre (#1481 B) | 2026-11-03 | —" trägt **keinen** Fang-Beleg; Präzedenz für Verlängerung ist die ausdrücklich als „verlängert, PO" gekennzeichnete Neudatierung beim Testnamens-Gate. Diese Spec behandelt die Erweiterung daher als **neue Regel** mit **neuem Prüfdatum 2027-01-21** (23.10.2026 + 90 Tage) und trägt den Beleg ausdrücklich ein: Aufmaß vom 2026-10-23 — 9 strenge Namenspaare, davon **7 außerhalb** der alten Reichweite, die das alte Gate nicht fangen konnte (Liste oben). Die Freigabe dieser Spec durch den PO gilt zugleich als Verlängerungsentscheidung; die Verlängerung wird in `gates_und_ratschen.md` mit „verlängert 2026-10-23, PO (Spec #2346)" vermerkt, nicht still durchgeführt. Der bestehende Fang-Beleg-Eintrag „—" wird durch diesen Beleg ersetzt.
- **Dringlichkeit:** Ohne S1 bis 2026-11-03 schaltet sich das Gate selbst ab (`pendant_gate.py:226-229`), und die blockierenden Fälle in `tests/tdd/test_pendant_gate.py` werden ab 04.11. vermutlich rot (die Tests frieren die Uhr nicht ein). S1 hat daher Vorrang vor allem anderen in diesem Ticket.

### S2 — Gemeinsame Startseiten-Kachel

- `SubscriptionCard` wird in den Nur-Vergleich-Zweigen kind-neutral: Kanäle, Zeitplan-Zeile und Fußzeile (letzter/nächster Versand) erscheinen für beide kinds, in derselben Anordnung. Für den Trip kommen die Kanäle aus den `report_config`-Flags (E-Mail, Telegram, SMS, Premium-SMS) über `heroKanaele`/`reportChannels`, **nie** aus `empfaenger` (#1452).
- `SubscriptionKachel.svelte` (neu, `routes/_home/`) ist der **eine** Baustein für `activePresets` und `otherTrips`; `TripKachel` und `CompareKachel` entfallen. Props `nextSend` und `lastSent` sind nullable und kind-neutral; eine eigene Fälligkeitsrechnung im Frontend gibt es nicht, `deriveNextSend` bleibt unberührt.
- **Sichtbare Änderung der Vergleichs-Kachel (bewusst, PO-bekannt):** Die compact-Kachel zeigt künftig für **beide** kinds Kanäle sowie letzten und nächsten Versand. Die Vergleichs-Kachel ändert damit ihr Aussehen (heute: Kanäle nur nicht-compact).
- Tote Bausteine werden gelöscht: `HomeHeroTrip`, `HomeHeroCompare` (inkl. Barrel-Einträge `organisms/index.ts:29-30`), `CompareIdealRow`. Zugehörige Tests, die nur deren Existenz prüfen, entfallen.
- Zwischenstand bis S4: Solange S4 nicht geliefert ist, zeigt die Kachel für Werte ohne Datenquelle den ehrlichen Leerzustand („—"). Das ist eine Lieferreihenfolge, **keine** Ausnahme von AC-1; das Ticket bleibt bis S4 offen.

### S3 — Hero, `shared/`

- Die beiden Inline-Heros in `+page.svelte` werden zu **einem** `HomeHero` mit Prop `kind` (Felder und Reihenfolge identisch, nur die kind-eigenen Inhalte — Etappen vs. Orte — unterscheiden sich).
- `+page.svelte:580` (`compareHero.empfaenger` als Kanäle) wird auf die Kanal-Flags umgestellt (#1452-Verstoß).
- `shared/CompareOutlookLayoutControls` → `shared/OutlookLayoutControls` (reine Umbenennung, Verhalten unverändert); `CompareHourlyLayoutControls` → `compare/` (siehe Befund oben).
- Erledigte Einträge aus `BEKANNTE_PAARE` und dessen eingefrorener Test-Menge streichen; Doku-Nachzug in `gates_und_ratschen.md`.

### S4 — `last_briefing` (nach #1969 S1)

- Der #1969-Endpunkt `GET /api/next-briefings` (Go-Proxy, `user_id` aus dem Auth-Kontext, optionale Filter `?trip_id=`/`?preset_id=`) wird um `last_briefing` je Trip und Vergleich ergänzt. Die Ableitung passiert in **Python** aus dem Briefing-Log (#2281, `entity_id`/`entity_type`), **nicht persistiert** (keine Schemaänderung; falls doch persistiert würde, gelten Read-Modify-Write und `data_schema_backup`).
- `+page.server.ts` lädt den Endpunkt zusätzlich zu den bestehenden drei Aufrufen, in **einem** Sammelaufruf; die Kachel nimmt `nextSend`/`lastSent` als Props. Damit ist AC-1 vollständig.
- **Abhängigkeit:** Feldnamen und Format von #1969 sind vorläufig; S4 beginnt erst, wenn #1969 S1 in `main` ist und d6 das endgültige Format gemeldet hat. Wird die Antwort dann anders benannt, passt S4 nur Typ und Mapping an.

## Expected Behavior

- **Input:** Startseite eines angemeldeten Nutzers mit Trips und Orts-Vergleichen; Commit mit neu angelegter Datei.
- **Output:** Beide kinds erscheinen als gleich aufgebaute Kachel (Status · nächster Versand · letzter Versand · Kanäle); ein Commit, der ein neues `CompareFoo` neben `Foo`/`TripFoo` anlegt, wird mit Exit 2 abgewiesen.
- **Side effects:** Die Vergleichs-Kachel sieht anders aus (compact zeigt Kanäle und Versandzeiten). Kein neues Datenfeld wird persistiert. Gate: Prüfdatum 2027-01-21.

## Acceptance Criteria

**AC-1** (S2 + S4, ungeteilt, vollständig mit S4): Given ein angemeldeter Nutzer mit einem Trip und einem Orts-Vergleich auf der Startseite / When die Startseite gerendert wird / Then zeigen beide Kacheln die Felder Status, nächster Versand, letzter Versand und Kanäle in derselben Reihenfolge und Anordnung aus **demselben** Baustein, und nächster/letzter Versand stammen für beide kinds aus `GET /api/next-briefings` (`next`/`last`), ohne eigene Fälligkeitsrechnung im Frontend.
  - Test: `node --test` rendert den Kachel-Baustein per SSR einmal mit `kind="trip"` und einmal mit `kind="vergleich"` und vergleicht die Reihenfolge der Felder; Fresh-Eyes-Screenshot-Paar Trip-/Vergleichs-Kachel auf Staging (die Home-E2E-Specs sind veraltet, eigene Staging-Messung).

**AC-2** (S1): Given ein Wegwerf-Repo, in dem `molecules/Foo.svelte` oder `molecules/TripFoo.svelte` bereits existiert / When ein Commit `molecules/CompareFoo.svelte` ohne `gz-eigenstaendig:`-Kopfzeile neu anlegt / Then gibt `pendant_gate.py` Exit 2 und nennt den Partner; mit gültiger Kopfzeile (≥15 Zeichen) Exit 0.
  - Test: `tests/tdd/test_pendant_gate.py`, Wegwerf-Repos wie bestehende Fälle, je ein Fall pro Muster (`Compare*`/`Trip*`, `*Compare`/`*Trip`, `compare_*`/`trip_*`, neutral für `CompareFoo` **und** `TripFoo`) in den vier Wurzeln; Gegenprobe: neues neutrales `Foo` neben bestehendem `CompareFoo` ⇒ Exit 0.

**AC-3** (S1, mit S2/S3 fortlaufend): Given die Ausnahmeliste `BEKANNTE_PAARE` / When ein Eintrag gestrichen wird / Then bleiben die Tests grün; When ein Eintrag hinzugefügt wird oder eine Datei eines Eintrags nicht mehr existiert / Then wird der Schrumpf-Test rot.
  - Test: `tests/tdd/test_pendant_gate_bekannte_paare.py` prüft (a) jeder Eintrag existiert, (b) Liste ⊆ eingefrorene Menge der sieben Paare.

**AC-4** (S3): Given der Stand nach S3 / When `frontend/src/lib/components/shared/` auf Komponentendateien mit `Compare`-Präfix geprüft wird / Then gibt es keine einzige; `OutlookLayoutControls` liegt in `shared/`, `CompareHourlyLayoutControls` in `compare/` mit der Kopfzeile `gz-eigenstaendig:` und fachlicher Begründung.
  - Test: Verzeichnisprüfung per Dateisystem-Listing (Strukturaussage, kein Verhaltensnachweis); zusätzlich die umgezogenen Tests (`outlook_erbt_grundauswahl_structure`, Stundenverlauf-Tests) grün gegen die neuen Pfade, und Trip- wie Vergleichs-Editor binden `OutlookLayoutControls` weiterhin ein.

**AC-5** (S1): Given der heutige Bestand (alle sieben Bestandspaare außerhalb der alten Reichweite plus `CompareTabs`/`TripTabs`, `CompareNewEditor`/`TripNewEditor`, `CompareOutlookLayoutControls`) / When Commits diese Dateien ändern, verschieben (Umbenennung ≥95 %) oder ein Bestandspaar-Mitglied unverändert mitführen / Then löst `pendant_gate.py` keinen Fehlalarm aus (Exit 0).
  - Test: Wegwerf-Repo mit allen Bestandspaaren; Änderungs-, Umbenennungs- und Mitführ-Commit je Paar ⇒ Exit 0.

**AC-6** (S1): Given Sonderfälle / When ein Commit legt an: eine Testdatei `CompareFoo.test.ts` neben `Foo.ts`; ein leerer Kernname `Compare.svelte`; eine Datei außerhalb der vier Wurzeln / Then Exit 0.
  - Test: `tests/tdd/test_pendant_gate.py`, drei Fälle.

**AC-7** (S1): Given eine Störung im Gate (Werkzeug `hook_utils` fehlt, `git` nicht auffindbar, Ausnahme in `_namenspendant()`, ungültige Eingabe) / When ein Commit geprüft wird / Then ist der Exit-Code 0 mit Hinweis auf stderr, und die bestehende Ordner-Erkennung blockiert weiterhin, wenn ihr Auslöser vorliegt.
  - Test: `tests/tdd/test_pendant_gate.py`, Störung der Namens-Erkennung erzwungen durch ein Wegwerf-Repo mit nicht lesbarer Datei bzw. unlesbarem Dateinamen — Exit 0.

**AC-8** (S1): Given die Pendant-Sperre mit erweiterter Reichweite / When `PRUEFDATUM` und die Doku gelesen werden / Then lautet das Prüfdatum 2027-01-21, und `docs/reference/gates_und_ratschen.md` nennt Reichweite, Ausnahmeliste, die Verlängerung („verlängert 2026-10-23, PO, Spec #2346") und den Beleg (7 Paare außerhalb der alten Reichweite) in Abschnitt „Pendant-Sperre" und in der Prüfdaten-Tabelle.
  - Test: Gate-Verhalten **am** Prüfdatum 2027-01-21 blockiert noch, am 2027-01-22 nicht (Datum über die bestehende Test-Uhr-Mechanik des Gate-Tests gesetzt); Doku-Zeilen als `# doc-compliance-test`.

**AC-9** (S2): Given ein Trip, dessen `report_config` nur E-Mail aktiviert hat, dessen `empfaenger` aber auch eine Telegram-Kennung enthält / When die Startseiten-Kachel gerendert wird / Then zeigt sie ausschließlich E-Mail als Kanal; die Kanalliste entsteht aus den Flags (E-Mail, Telegram, SMS, Premium-SMS), nie aus `empfaenger`.
  - Test: `node --test`, SSR-Render des Bausteins mit solchem Trip; Gegenprobe mit allen vier Flags ⇒ vier Kanäle.

**AC-10** (S2): Given der Stand nach S2 / When `HomeHeroTrip`, `HomeHeroCompare`, `CompareIdealRow`, `TripKachel`, `CompareKachel` und ihre Barrel-Einträge gesucht werden / Then existieren sie nicht mehr, und kein Import verweist darauf; `svelte-check` und `frontend-test` sind grün.
  - Test: Frontend-Testlauf und `svelte-check` (ungültige Importe wären ein Fehler); Schrumpf-Test (AC-3) erzwingt das Streichen der beiden Paare aus `BEKANNTE_PAARE`.

**AC-11** (S3): Given der Stand nach S3 / When `+page.svelte` gerendert wird (Trip-Hero und Vergleichs-Hero) / Then stammen beide aus **einem** `HomeHero`-Baustein mit `kind`; `+page.svelte` enthält keine zweite inline Hero-Fläche mehr.
  - Test: `node --test` SSR-Render von `HomeHero` mit beiden kinds (gleiche Felderfolge); Staging-Screenshot beider Heros im Fresh-Eyes-Paar.

**AC-12** (S3): Given ein Vergleichs-Hero, dessen `empfaenger` einen Kanal enthält, dessen Flag aber aus ist / When der Hero gerendert wird / Then zeigt er die Kanäle aus den Flags, nicht aus `empfaenger` (#1452-Verstoß `+page.svelte:580` behoben).
  - Test: `node --test` mit solchem Vergleich; rot vor, grün nach der Änderung.

**AC-13** (S4): Given ein Nutzer mit Trips und Orts-Vergleichen, die im Briefing-Log (#2281) Einträge haben / When `GET /api/next-briefings` aufgerufen wird / Then enthält die Antwort je Trip und je Vergleich ein `last_briefing` (Zeitpunkt des letzten tatsächlich versendeten Briefings, `null` wenn nie), abgeleitet in Python aus dem Briefing-Log, ohne zusätzliche Persistenz.
  - Test: pytest gegen den Python-Endpunkt mit echten Briefing-Log-Einträgen (aufgezeichnete Fixture), Go-Proxy-Test, dass die Antwort unverändert durchgereicht wird.

**AC-14** (S4): Given zwei verschiedene Nutzer A und B mit je eigenen Trips und Vergleichen sowie eigenen Briefing-Log-Einträgen / When A `GET /api/next-briefings` aufruft (Auth-Kontext von A) / Then enthält die Antwort ausschließlich A-Einträge — keine IDs, Zeitpunkte oder Kanäle von B —, und `user_id` stammt aus dem Auth-Kontext, nie aus `"default"`.
  - Test: pytest und Go-Test mit zwei Nutzern (Mandantentrennung, Pflicht laut CLAUDE.md); Gegenprobe: gleiche IDs bei beiden Nutzern liefern je eigene Werte.

**AC-15** (S4): Given die Startseite nach S4 / When sie für einen Trip mit versendetem Briefing gestern geladen wird / Then zeigt die Trip-Kachel den letzten Versand (nicht „—") und den nächsten Versand aus `next`, und bei `next.at === null` den Grund (`reason`) statt eines erfundenen Zeitpunkts; ein einziger Sammelaufruf (kein Aufruf je Kachel) lädt die Daten.
  - Test: `node --test` auf Mapping Antwort → Props (inkl. `null`-Fall); Staging-Messung mit Wegwerf-Nutzer (Trip + Vergleich) und Screenshot-Paar.

**AC-16** (S2): Given eine Vergleichs-Kachel auf der Startseite / When sie nach S2 gerendert wird / Then zeigt sie in der compact-Darstellung zusätzlich Kanäle sowie letzten und nächsten Versand (bewusste sichtbare Änderung) und behält ihre Aktion „Bearbeiten" sowie `data-testid="subscription-card-{id}"`.
  - Test: `subscription_card.test.ts` (SSR-Render compact, kind `vergleich`).

## Test Plan (Kern deterministisch, keine Mocks)

- **pytest (Gate):** Wegwerf-Git-Repos wie in `tests/tdd/test_pendant_gate.py` — echter Hook-Aufruf per Subprozess mit `tool_input.command`, geprüft wird Exit-Code und Meldung. Dateien: `tests/tdd/test_pendant_gate.py` (erweitert), `tests/tdd/test_pendant_gate_bekannte_paare.py` (neu). Benennung nach Verhalten, nicht nach Issue-Nummer.
- **Frontend (`node --test`, kein Vitest):** SSR-Render der Bausteine (`SubscriptionCard`, `SubscriptionKachel`, `HomeHero`) mit beiden kinds; Mapping-Test für `next`/`last`; keine Dateiinhalt-Checks als Verhaltensnachweis (strukturelle Pfadprüfung AC-4/AC-10 ist ausdrücklich Struktur, ergänzt durch `svelte-check`).
- **Backend S4:** pytest und Go-Test mit **zwei Nutzern**; echte aufgezeichnete Briefing-Log-Daten als versionierte Fixture, kein Netz.
- **Live (nur `/e2e-verify`):** Fresh-Eyes-Screenshot-Paar Trip-/Vergleichs-Kachel und Hero auf Staging (Wegwerf-Nutzer; Hauptkonto-Daten sind für `hem` dort nicht lesbar). Die veralteten Home-E2E-Specs (`issue-294-home-kachel.spec.ts`, `issue-579-home-fidelity.spec.ts`, nicht in `ci_e2e_specs.txt`) werden nicht repariert, sondern ersetzt durch eigene Staging-Messung.
- **Mutations-Gegenprobe (Adversary, Pflicht):** u. a. Gate-Muster auf nur eine Richtung verengen, `BEKANNTE_PAARE` aufweichen (Eintrag ergänzen), Kanäle wieder aus `empfaenger` lesen, `user_id` auf `"default"` fallen lassen, `last_briefing` ohne Nutzerfilter — jede muss einen **benannten** Test rot machen. Commit-Gate-Hooks sind Hochrisiko-Fläche (≥2 Adversary-Runden); Mutationen nur per String-Ersetzung mit externer Sicherungskopie.

## Known Limitations

- Die Namens-Erkennung kennt nur Paare mit **bereits vorhandenem** Partner und reine Namensähnlichkeit; ca. 8 ähnliche, nicht namensgleiche Paare (z. B. `compare_slot_scheduler.py`/`trip_report_scheduler.py`, `compare_preset.go`/`trip.go`) bleiben unerkannt. Die Ausnahmeliste nennt nur die 7 namensgleichen Bestandspaare.
- Die Begründung in `gz-eigenstaendig:` wird auf Länge geprüft, nicht auf Substanz (wie bisher).
- #1969-Feldnamen sind vorläufig; S4 wartet auf #1969 S1 und kann sich um Typ/Mapping anpassen.
- `deriveNextSend` (Frontend), `_compute_next_send` und die feste HubOverview-Zeit werden von #1969 abgelöst, nicht hier.
- Die Anlege-Seite/Editoren, Trip-Liste und Compare-Liste bleiben unberührt (dort läuft `SubscriptionCard` bereits kind-neutral).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Umsetzung der bestehenden, mehrfach bestätigten PO-Vorgabe zur Trip/Ortsvergleich-Code-Teilung (CLAUDE.md, Epic #2345) und Erweiterung eines vorhandenen Gates; kein neuer Grundsatz bei Kanälen, Provider, Datenmodell, Auth oder Editor-Paradigma. Das Gate trägt ein Prüfdatum (Regel-Budget).

## Definition of Done

- [ ] S1: Pendant-Sperre mit Namensmuster-Erkennung, `BEKANNTE_PAARE` und Prüfdatum 2027-01-21 vor 2026-11-03 auf `main`; AC-2/3/5/6/7/8 grün; `gates_und_ratschen.md` nachgezogen
- [ ] S2: Gemeinsame Startseiten-Kachel live; AC-9/10/16 grün; Fresh-Eyes-Screenshot-Paar Trip-/Vergleichs-Kachel auf Staging
- [ ] S3: `HomeHero` mit `kind`, #1452-Fix, `shared/` ohne `Compare*`-Komponenten; AC-4/11/12 grün; erledigte Einträge aus `BEKANNTE_PAARE` gestrichen
- [ ] S4 (nach #1969 S1): `last_briefing` im #1969-Endpunkt, Kachel verdrahtet; AC-1/13/14/15 grün inkl. Test mit zwei Nutzern
- [ ] Je Scheibe: CI-Ampel (6 Checks) grün, Staging verifiziert, Prod-Deploy + Selftest Exit 0
- [ ] Issue #2346 erst nach S4 geschlossen

## Changelog

- 2026-10-23: Initial spec created (Scheiben S1–S4, Ticket-Korrekturen, Befund Stundenverlauf-Steuerung, Abstimmung mit #1969)
