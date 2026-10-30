---
entity_id: i18n_f3_home_listen_2652
type: module
created: 2026-10-30
updated: 2026-10-30
status: draft
version: "1.0"
tags: [i18n, epic-2644, issue-2652, frontend, model-haiku]
---

# i18n F3: Katalog-Migration Home/Cockpit und Listen (Trips, Ortsvergleiche, Orte, Archiv, Kacheln, Hero)

**Issue:** #2652 · **Epic:** #2644 · **Modell:** Haiku · **Konventionen:** docs/features/epic-i18n-de-en-konventionen.md Abschnitt(e) 2, 3 (Frontend), 8

## Approval

- [ ] Approved

## Purpose

Wer Englisch eingestellt hat, soll das Cockpit (Startseite nach dem Login), die Trip-Liste, die Liste der Ortsvergleiche, die Orte-Liste und das Archiv auf Englisch lesen: Kacheln, Hero, Zähler, Leerzustände, Datums- und Tagesangaben. Deutsch bleibt Zeichen für Zeichen wie heute. Trip und Ortsvergleich teilen sich dieselben Schlüssel, wo der Text nur im Nomen abweicht (kein Pendant-Baustein, Anti-Pattern #1170).

## Source

- **File:** `frontend/src/routes/+page.svelte` (Cockpit-Zweig), `frontend/src/routes/_home/**`, `frontend/src/routes/trips/+page.svelte`, `frontend/src/routes/compare/+page.svelte`, `frontend/src/routes/locations/+page.svelte`, `frontend/src/routes/archiv/+page.svelte`, `frontend/src/routes/archiv/+page.server.ts`, `frontend/src/lib/components/organisms/ListTable.svelte`, `frontend/src/lib/utils/tripHero.ts`, `frontend/src/lib/utils/schedulerTime.ts`, `frontend/src/lib/pwa/standText.ts`
- **Identifier:** `getDaysLabel`, `formatDateRange` (tripHero.ts), `formatNextRun` (schedulerTime.ts), `standZeile`, `standKurz`, `formatiereStandZeit`, `STAND_HERKUNFT` (standText.ts), `plannedBriefings`, `homeCompareTimeline`, `heroKanaele` (cockpitHelpers.ts), `OEFFNEN` (HomeHero.svelte), Katalog-Namensräume `home.*` und `listen.*`

> **Schicht-Hinweis:** Reines SvelteKit-Frontend (`frontend/src/...`). Kein Go-, kein Python-Code. Die Nutzer-Sprache kommt aus S2 (`locale`-Store, `locals.lang`), nicht aus diesem Paket.

### Affected Files

| Datei | CREATE/MODIFY | Zweck |
|---|---|---|
| `frontend/src/lib/i18n/messages/de/home.json` | MODIFY | Cockpit-, Hero-, Kachel-, Tages-, Stand-Texte (deutscher Ist-Wortlaut, wörtlich) |
| `frontend/src/lib/i18n/messages/en/home.json` | MODIFY | gleiche Schlüssel, englisch laut Glossar |
| `frontend/src/lib/i18n/messages/de/listen.json` | MODIFY | Texte der Listen (Trips, Vergleiche, Orte, Archiv) |
| `frontend/src/lib/i18n/messages/en/listen.json` | MODIFY | gleiche Schlüssel, englisch |
| `frontend/src/routes/+page.svelte` | MODIFY | Cockpit-Zweig (Annahme A1): Eyebrow, Pills, Versand-/Alert-Karten, SectionH-Texte, Datumsformate (Zeilen 97, 104, 173, 380) |
| `frontend/src/routes/_home/HomeHero.svelte` | MODIFY | `OEFFNEN`-Map, „Nächster Versand", „Kanäle", „Schnell eingreifen", „Schnellaktionen" |
| `frontend/src/routes/_home/EmptyKachel.svelte` | MODIFY | Titel/Beschreibung des Leerzustands |
| `frontend/src/routes/_home/SubscriptionKachel.svelte` | MODIFY | nur sichtbare Texte; Kanalnamen (Eigennamen) bleiben |
| `frontend/src/routes/_home/cockpitHelpers.ts` | MODIFY | `Orte`, `Zuletzt ·`, `Nächster ·`, `Vergleich`, Monatskürzel `MONTHS_DE`, `morgen`/`abend` |
| `frontend/src/routes/_home/homeHeroProps.ts` | MODIFY | `{n} Orte verglichen` (Plural) |
| `frontend/src/routes/_home/kachelActions.ts` | MODIFY | Label „Bearbeiten" (Schlüssel `home.kachel.bearbeiten`, siehe Known Limitations) |
| `frontend/src/routes/trips/+page.svelte` | MODIFY | Überschrift, Stat-Zähler, Spaltenköpfe, Leerzustand, Suche, Dialog, Meldungen |
| `frontend/src/routes/compare/+page.svelte` | MODIFY | Überschrift, Stats, Suche, Leerzustand, Lösch-Dialog |
| `frontend/src/routes/locations/+page.svelte` | MODIFY | Überschrift, Tabelle, Dialoge, Leerzustand |
| `frontend/src/routes/archiv/+page.svelte` | MODIFY | Überschrift, Filter-Chips, Tabellenkopf, Zeilen-Aktionen, Zähler |
| `frontend/src/routes/archiv/+page.server.ts` | MODIFY | Eintrag erhält zusätzlich `count: number`; `detail` bleibt unverändert (Tests) |
| `frontend/src/lib/components/organisms/ListTable.svelte` | MODIFY | Standard `emptyText` und Kopf „Aktionen" |
| `frontend/src/lib/utils/tripHero.ts` | MODIFY | Tagesangaben und Zeitraum über Katalog; Monatsnamen de/en |
| `frontend/src/lib/utils/schedulerTime.ts` | MODIFY | „heute um" / „morgen um" und Fernzeit sprachabhängig |
| `frontend/src/lib/pwa/standText.ts` | MODIFY | Stand-Zeilen sprachabhängig, ohne Svelte-Store (Service-Worker-tauglich) |
| `frontend/src/lib/pwa/offlineStand.ts` | MODIFY | übergibt `get(locale)` an `standZeile` |
| `frontend/src/service-worker.ts` | MODIFY | bestimmt die Sprache aus `<html lang>` des abzulegenden Dokuments (Fallback `de`) und übergibt sie an `standZeile`/`standKurz` |
| `frontend/src/lib/i18n/hardcode_allowlist.json` | MODIFY | Einträge `routes/_home`, `routes/trips/+page`, `routes/compare/+page`, `routes/locations`, `routes/archiv`, `routes/+page.svelte`, `organisms/ListTable` entfernen |
| `frontend/src/routes/_home/__tests__/cockpit_sprache.test.ts` | CREATE | Hero/Kachel/Tagesangaben de und en |
| `frontend/src/routes/__tests__/listen_sprache_je_nutzer.test.ts` | CREATE | Listen zweisprachig, zwei Nutzer, Golden de |
| `frontend/src/lib/utils/__tests__/tripHero_sprache.test.ts` | CREATE | Plural und Zeitraum de/en |
| `frontend/src/lib/pwa/__tests__/standText_sprache.test.ts` | CREATE | Stand-Zeile de byte-gleich, en |
| `tests/golden/f3_home_listen/*.de.html` | CREATE | Golden-Fixtures (vor der Umstellung aus dem Ist-Stand erzeugt) |

> **Querschnitts-Prüfpunkte**
> - **Trip/Ortsvergleich-Teilung:** Es entsteht keine neue Komponente. Geteilte Bausteine (`ListTable`, `HomeHero` mit `kind`) bleiben ein Code; Texte, die nur im Nomen abweichen, liegen als zwei Schlüssel (`listen.leer.trip`, `listen.leer.vergleich`). Aktions-Labels (Pausieren, Archivieren, Löschen …) kommen aus `shared/subscriptionActions.ts` und gehören zu F9 (`aktionen.*`); F3 führt dafür keinen eigenen Schlüssel ein.
> - **Mandantentrennung:** Die Seiten lesen Nutzerdaten über bestehende Loader (`user_id` aus Auth-Kontext, unverändert). Die Sprache wird pro Anfrage aus `locals.lang` bzw. Nutzer-`language` gelöst, nie global. Test mit zwei Nutzern (AC-5).
> - **Kanäle:** Briefing-Inhalt wird nicht verändert; die Kanalnamen (Email, Telegram, SMS, Premium-SMS) sind Eigennamen und bleiben (`heroKanaele`, `homeHeroChannels`).

## Estimated Scope

- **LoC:** ca. 330 Code-Zeilen (ohne Katalogdaten und Tests): ca. 200 Textstellen, dazu Datums- und Zeitformate. Das überschreitet das Workflow-Limit von 250: `workflow.py set-field loc_limit_override 500` einplanen.
- **Files:** 23 Code-/Katalogdateien plus 4 Tests plus Golden-Fixtures
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|---|---|---|
| #2647 (S2) | Paket | `t`, `tn`, `tr`, `locale`, `fmtDate`, `fmtWeekday`; Katalog-Ladeliste für `home`/`listen` bereits angelegt |
| #2649 (S4) | Paket | Ratsche und `hardcode_allowlist.json` |
| #2655 (F6) | Paket (später) | `nextBriefingText.ts` (`formatNextBriefing`, Wert der Zeile „Nächster Versand") wird dort migriert |
| #2658 (F9) | Paket (später) | `aktionen.*` und `subscriptionActions.ts`: Zeilenmenü-Labels bleiben bis dahin deutsch |
| #2659 (F10) | Paket (später) | `subscriptionHelpers.ts` (`formatNextSend`, `relativeLastSent`, `presetTileScheduleLabel`) wird dort migriert; F10 verwendet `home.tage.heute` und `listen.anzahl.orte` aus diesem Paket |
| `docs/reference/i18n_glossar.md` | Doku | Begriffe (Trip, stage, location comparison, delivery, archive …) |
| ADR-0104 | adr | Zweisprachigkeit, Formate (24 h, `Thu 30 Oct`) |

## Implementation Details

**1. Katalog.** Nur `messages/{de,en}/home.json` und `messages/{de,en}/listen.json` anfassen. Schlüssel `bereich.gruppe.element`, `{name}`-Platzhalter identisch in de und en, Plural als `x.one`/`x.other` mit Aufruf `tn("x", count)`. Deutsch ist der heutige Wortlaut, wörtlich (auch „Orts-Vergleich" mit Bindestrich, wo er heute so steht).

**2. Beispiel-Schlüssel (de / en).**

| Schlüssel | de | en |
|---|---|---|
| `home.hero.naechster_versand` | Nächster Versand | Next delivery |
| `home.hero.kanaele` | Kanäle | Channels |
| `home.hero.schnellaktionen` | Schnellaktionen | Quick actions |
| `home.hero.oeffnen.trip` | Trip öffnen → | Open trip → |
| `home.hero.oeffnen.vergleich` | Vergleich öffnen → | Open comparison → |
| `home.hero.orte_verglichen.one` / `.other` | {count} Orte verglichen (beide gleich) | {count} location compared / {count} locations compared |
| `home.tage.heute` / `home.tage.morgen` | heute / morgen | today / tomorrow |
| `home.tage.pausiert_seit_heute` | pausiert seit heute | paused since today |
| `home.tage.pausiert_seit.one` / `.other` | pausiert seit {count} Tagen (beide gleich) | paused for {count} day / paused for {count} days |
| `home.tage.beendet_vor.one` / `.other` | beendet vor {count} Tagen (beide gleich) | ended {count} day ago / ended {count} days ago |
| `home.tage.laeuft_seit` | läuft seit Tag {tag} | running since day {tag} |
| `home.stand.zeile` | Stand: {zeit} — offline, aus dem Gerätespeicher | As of: {zeit} — offline, from device storage |
| `listen.trips.neuer_trip` | + Neuer Trip | + New trip |
| `listen.leer.trip` | Noch keine Trips | No trips yet |
| `listen.leer.vergleich` | Noch keine Vergleiche angelegt. | No comparisons yet. |
| `listen.zaehler.trips` | {gefiltert} von {gesamt} Trips | {gefiltert} of {gesamt} trips |
| `listen.anzahl.etappen.one` / `.other` | {count} Etappe / {count} Etappen | {count} stage / {count} stages |
| `listen.anzahl.orte.one` / `.other` | {count} Ort / {count} Orte | {count} location / {count} locations |

Die deutschen Plural-Paare der Tagesangaben sind bewusst gleich (das heutige Verhalten `1 Tagen` bleibt byte-gleich, Golden). `listen.anzahl.*` wird in der Trip-Liste (`trips/+page.svelte:82`), im Archiv und von F10 benutzt (ein Schlüssel für denselben Text).

**3. Beispiel-Umstellung vorher → nachher.**

- `frontend/src/routes/_home/HomeHero.svelte:89` — vorher `>Nächster Versand</div>`, nachher `>{$t('home.hero.naechster_versand')}</div>`; Zeile 31–34 `OEFFNEN`: Werte werden `$t('home.hero.oeffnen.trip')` / `$t('home.hero.oeffnen.vergleich')` (als `$derived`-Map, damit sie auf Sprachwechsel reagiert).
- `frontend/src/routes/trips/+page.svelte:251` — vorher `{filteredTrips.length} von {trips.length} Trips`, nachher `{$t('listen.zaehler.trips', { gefiltert: filteredTrips.length, gesamt: trips.length })}`.
- `frontend/src/routes/trips/+page.svelte:82` — vorher `` `${n} ${n === 1 ? 'Etappe' : 'Etappen'}` ``, nachher `get(tn)('listen.anzahl.etappen', n)`.
- `frontend/src/lib/utils/tripHero.ts:62-63` — vorher `return \`pausiert seit ${diff} Tagen\``, nachher `return get(tn)('home.tage.pausiert_seit', diff)` (`get` aus `svelte/store`; die Konventionen kennen für `.ts` nur `tr`, daher Annahme A2).
- `frontend/src/lib/utils/schedulerTime.ts:35` — vorher `` `heute um ${time}` ``, nachher `tr('home.zeit.heute_um', { zeit: time })` (de `heute um {zeit}`, en `today at {zeit}`).

**4. Datums- und Zeitformate.**

- `tripHero.ts`: `MONTH_NAMES_DE` entfällt als Konstante; Monatsnamen kommen aus `home.monat.1` … `home.monat.12` (de: Januar … Dezember, wörtlich; en: January … December). Der Zeitraum wird mit vier Mustern zusammengesetzt: `home.zeitraum.tag` (de `{tag}. {monat} {jahr}`, en `{tag} {monat} {jahr}`), `home.zeitraum.gleicher_monat` (de `{von}.–{bis}. {monat} {jahr}`, en `{von}–{bis} {monat} {jahr}`), `home.zeitraum.verschiedene_monate`, `home.zeitraum.verschiedene_jahre`. Kein `toLocaleString` (deterministische Tests ohne ICU, wie heute).
- `schedulerTime.ts`: Locale-Zeichenkette für `toLocaleString` ist `de-AT` bei `de` (heutiges Verhalten, byte-gleich), `en-GB` bei `en` (24 h). Fernzeit englisch: `fmtDate(date, 'en', 'kurz')` + `, ` + Uhrzeit mit Zonenkürzel.
- `routes/+page.svelte:97,104,173,380` (`toLocaleDateString('de-DE', …)`): bei `de` unverändert (byte-gleich), bei `en` mit `en-GB` und denselben Optionen.
- `standText.ts`: keine Store-Abhängigkeit (Service Worker). Die Funktionen erhalten `lang: Lang = 'de'` als letzten Parameter und lesen die Texte direkt aus `../i18n/messages/{de,en}/home.json` (Platzhalter `{zeit}` selbst ersetzen). Der Service Worker (`service-worker.ts:254,428`) bestimmt `lang` aus dem Attribut `<html lang>` des abzulegenden Dokuments (Fallback `de`); `offlineStand.ts:70` übergibt `get(locale)`. `STAND_HERKUNFT` entfällt zugunsten des Katalogschlüssels `home.stand.herkunft`.

**5. Reaktivität.** Reine `.ts`-Funktionen lesen `get(locale)`. Aufrufer in Svelte, die sie in `$derived` benutzen, lesen vorher `$locale` (`$derived.by(() => { $locale; return getDaysLabel(trip, now); })`), damit ein Sprachwechsel ohne Neuladen wirkt.

**6. Archiv serverseitig.** `archiv/+page.server.ts` darf `tr` nicht verwenden (kein Store im Server-Load). Es liefert zusätzlich `count`; `+page.svelte` rendert `tn('listen.anzahl.etappen', item.count)` bzw. `listen.anzahl.orte`. Das Feld `detail` bleibt unverändert bestehen (bestehende Tests), wird aber nicht mehr angezeigt.

**7. Nicht anfassen.** Kanalnamen, `data-testid`, CSS-Klassen, Routen, `col_label`/`sms_code`/Kürzel, Nutzertexte (Trip- und Vergleichsnamen), Onboarding-Texte (`onboarding.*`, gehören F2).

**8. Allowlist.** Aus `frontend/src/lib/i18n/hardcode_allowlist.json` die Einträge entfernen, die auf Dateien dieser Tabelle zeigen: `routes/_home`, `routes/trips/+page`, `routes/compare/+page`, `routes/locations`, `routes/archiv`, `routes/+page.svelte`, `organisms/ListTable`. Danach muss `keine_hartkodierten_nutzertexte.test.ts` grün sein.

**9. Golden-Fixture.** Vor der Umstellung je Fall (Cockpit mit aktivem Trip, Cockpit mit Ortsvergleich, Trip-Liste mit 2 Trips, Compare-Liste leer, Archiv mit 1 Trip + 1 Vergleich) mit fester Zeit `2026-10-29T06:00+02:00` und Nutzer `golden-de` per Svelte-SSR-Render nach `tests/golden/f3_home_listen/<fall>.de.html` schreiben. Nach der Umstellung muss der Test byte-gleich vergleichen. Die englische Ausgabe wird als `*.en.html` eingecheckt (Review-Hilfe).

## Expected Behavior

- **Input:** Aufruf von `/`, `/trips`, `/compare`, `/locations`, `/archiv` mit Nutzer `language=en` bzw. `de`.
- **Output:** Alle sichtbaren Texte dieser Seiten, die in den Dateien dieses Pakets liegen, in der Nutzersprache; Zahlen, Kanalnamen, Trip-/Ortsnamen unverändert; Deutsch byte-gleich zum Ist-Stand.
- **Side effects:** Keine. Keine neuen Netzaufrufe, keine neuen Abhängigkeiten.

## Acceptance Criteria

- **AC-1:** Given ein Nutzer mit Sprache Englisch, ein aktiver Trip und ein Ortsvergleich / When das Cockpit `/` lädt / Then stehen Hero-Beschriftungen, Kacheln, Versand-/Alert-Karten, Überschriften und Tagesangaben auf Englisch (z. B. „Next delivery", „Open trip →", „running since day 2"), Trip- und Ortsnamen sowie Kanalnamen unverändert.
  - Test: `frontend/src/routes/_home/__tests__/cockpit_sprache.test.ts` — rendert Hero und Kachel mit `locale.set('en')` und prüft Texte über `tr()`-Werte, nie über Literale.

- **AC-2:** Given Trips mit Status pausiert, geplant, laufend und beendet / When `getDaysLabel` und `formatDateRange` mit Sprache Englisch und mit Deutsch aufgerufen werden / Then lauten die Texte `paused for 1 day`, `paused for 3 days`, `running since day 2`, `ended 1 day ago` bzw. deutsch `pausiert seit 1 Tagen`, `läuft seit Tag 2`, `beendet vor 3 Tagen`, und der Zeitraum `1.–5. Oktober 2026` bzw. `1–5 October 2026`.
  - Test: `frontend/src/lib/utils/__tests__/tripHero_sprache.test.ts` — Plural und Zeitraum-Muster für beide Sprachen, deutsche Werte byte-gleich zu den bisherigen Tests in `tripHero.test.ts`.

- **AC-3:** Given die Trip-Liste mit 3 Trips und gesetzter Suche ohne Treffer / When die Seite `/trips` in Englisch angezeigt wird / Then lauten Überschrift, Stat-Beschriftungen, Zähler („0 of 3 trips") und Leerzustand englisch, und der Suchbegriff erscheint unverändert im Hinweis; im Archiv stehen „1 stage" und „2 stages" im richtigen Plural.
  - Test: `frontend/src/routes/__tests__/listen_sprache_je_nutzer.test.ts` — Liste und Archiv mit `en` und `de`, `tn()`-Plural für `listen.anzahl.etappen` und `listen.anzahl.orte`.

- **AC-4:** Given die deutsche Oberfläche / When Cockpit, Trip-Liste, Compare-Liste und Archiv mit der Fixture `golden-de` gerendert werden / Then ist die Ausgabe Byte für Byte gleich zu `tests/golden/f3_home_listen/*.de.html`.
  - Test: `frontend/src/routes/__tests__/listen_sprache_je_nutzer.test.ts` — Golden-Vergleich (deutsche Ausgabe unverändert).

- **AC-5:** Given Nutzer A mit Englisch und Nutzer B mit Deutsch, jeder mit eigenen Trips / When beide nacheinander `/trips` und `/archiv` laden / Then sieht A englische Texte nur mit A's Trips, B deutsche Texte nur mit B's Trips, und keine Sprache oder Daten wandern von einem Nutzer zum anderen.
  - Test: `frontend/src/routes/__tests__/listen_sprache_je_nutzer.test.ts` — zwei Nutzer in einem Lauf, Server-Load mit jeweils eigenem `locals.userId` und `locals.lang`.

- **AC-6:** Given die Offline-Stand-Zeile des Service Workers / When `standZeile` für den 5. September 06:12 mit Sprache Englisch aufgerufen wird / Then beginnt sie mit „As of:" und endet mit „offline, from device storage"; mit Sprache Deutsch ist sie wörtlich `Stand: … — offline, aus dem Gerätespeicher`.
  - Test: `frontend/src/lib/pwa/__tests__/standText_sprache.test.ts` — beide Sprachen, ohne Svelte-Store-Import; bestehende `standText`-Tests bleiben grün.

- **AC-7:** Given die Allowlist der Ratsche / When `keine_hartkodierten_nutzertexte.test.ts` läuft / Then enthalten die Dateien dieses Pakets keine Treffer mehr und die Allowlist enthält keinen Eintrag mehr für `routes/_home`, `routes/trips/+page`, `routes/compare/+page`, `routes/locations`, `routes/archiv`, `organisms/ListTable`.
  - Test: `frontend/src/lib/i18n/__tests__/keine_hartkodierten_nutzertexte.test.ts` — Ratschen-/Paritätstest (`# doc-compliance-test`), dazu `paritaet_de_en.test.ts` für `home` und `listen`.

## Known Limitations

- **A1 (Annahme):** `frontend/src/routes/+page.svelte` (Cockpit) ist in der Issue-Liste nicht genannt, trägt aber die meisten Cockpit-Texte; es gehört zu diesem Paket, sonst bliebe das Cockpit deutsch.
- **A2 (Annahme):** Für Plurale in `.ts`-Modulen gibt es in den Konventionen kein `trn`; F3 nutzt `get(tn)(...)`. Ändert S2 die Signatur, folgt F3 ihr.
- Zeilenmenü-Labels (`Pausieren`, `Archivieren`, `Löschen` …) in `shared/subscriptionActions.ts`, der Wert der Zeile „Nächster Versand" (`formatNextBriefing`, F6) und die Compare-Helfer in `subscriptionHelpers.ts` (`vor N Wochen`, `tägl.`, F10) bleiben bis zu den jeweiligen Paketen deutsch; die Tests dieses Pakets prüfen nur Texte, die in den Dateien der Tabelle liegen.
- Die Issue-Skizze nennt „vor 1 Minute"; die Zeit-vor-Text `vor {n} Min` steht tatsächlich in `routes/account/+page.svelte` (`timeAgo`, F4) und wird dort mit `fmtRelativeMinutes` umgestellt. In F3 wird der Plural stattdessen an `getDaysLabel` bewiesen.
- `kachelActions.ts` bekommt den Schlüssel `home.kachel.bearbeiten`; ein späterer Nebenbefund darf ihn durch `aktionen.edit` ersetzen (Schlüssel werden im Epic nicht umbenannt).
- Der englische Zeitstempel im Offline-Stand nutzt `en-GB` (`05/09, 06:12 CEST`), nicht das Format `Thu 30 Oct`; Offline-Hinweise sind bewusst minimal.
- `StartklarCheckliste.svelte` (Onboarding) gehört zu F2.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0104
- **Rationale:** Sprache gehört dem Nutzer, Texte liegen im Katalog je Bereich; Deutsch bleibt byte-gleich (Golden).

## Changelog

- 2026-10-30: Initial spec created (Planung Epic #2644)
