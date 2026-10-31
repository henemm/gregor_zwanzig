---
entity_id: feat_2347_s4_paritaets_e2e
type: feature
created: 2026-10-30
updated: 2026-10-30
status: draft
version: "1.0"
workflow: feat-2347-s4-paritaets-e2e-altlast-leer
tags: [epic-2345, etappe-p6, ratsche, e2e, playwright, trip-compare-teilung, anlegen, altlast-leer, staging]
---

# Paritäts-E2E, Scheibe S4: ALTLAST leeren (#2347)

## Approval

- [ ] Approved

## Purpose

S1 bis S3d sind live (ALTLAST 48 → 14). S4 leert die **letzten 14 Einträge** der `ALTLAST`-Liste in `tests/unit/test_e2e_compare_paritaet_waechter.py` und räumt die #2243-Leiche `trip-edit.spec.ts` weg. Danach ist `ALTLAST` leer und `ALTLAST_MAX` ist im selben Commit 0: jede Compare-Spec ist kind-parametrisiert (`HUB_KINDS`) oder trägt einen `gz-eigenstaendig:`-Kopf mit wahrer Begründung.

Gewählt ist Variante B (wie S3d): **ein Ticket**, fünf AC-Gruppen G1 bis G4 und G6 (Nummer G5 entfällt, die Löschungen stehen in G2), keine Abspaltung von Resten. Regeln:

- Eine Datei wird nur **gelöscht**, wenn die Zuordnung alt → neu (unten, Fall für Fall, mit Dateiname und Testname) jede Zusicherung in einer anderen, **in der CI laufenden** Spec belegt. Ein Altfall, den kein Zielfall deckt, wird **als neuer Fall gebaut**, nie still gestrichen.
- **Keine Zusicherung geht verloren oder wird abgeschwächt.** Die Zuordnung stützt sich auf Rumpf-Lesen der Altfälle (Beleg-Stufe je Datei in „Befunde", Punkt 7); wo nur der Titel gelesen wurde, ist der Rumpf-Abgleich in /50 Pflicht und eine Abweichung erzeugt einen Zusatzfall.
- Rote Trip-Pendants in neuen Fällen sind eine Produktlücke und werden im selben Ticket behoben (AC-20, Regel wie S3d AC-16).
- Mandantentrennung: kein neuer Endpunkt; das Anlegen (`POST /api/trips`, `POST /api/compare/presets`) wird mit zwei Nutzern abgedeckt (AC-13).

## Source

- **Neu:** `frontend/e2e/hub-anlegen-ablauf.spec.ts` (AN, Anlege-Seite je kind) · `frontend/e2e/hub-liste-seitenrahmen.spec.ts` (HL, Listenseite je kind).
- **Erweitert (kind-parametrisiert):** `hub-list-menu` (LM-1b, LM-10b, LM-11 bis LM-13), `hub-kopf-aufbau` (KA-10, KA-11), `hub-tab-bar` (HT-11, HT-12), `hub-kopf-bearbeiten` (KB-11), `hub-alarme-wertprops` (AW-3c, AW-5b), `hub-cross-user-write-block` (XU-3), `hub-reiter-alt-kennungen-umleitung` (`?tab=layout` je Hub).
- **Gelöscht (8 Altlast-Dateien):** `compare-alarm-config`, `compare-detail-edit-entry`, `compare-edit-redirect` (+ `compare-edit-redirect.staging.setup.ts`, `e2e/playwright.1273-s3.red.config.ts`), `compare-editor-slice1`, `compare-editor-slice4`, `compare-legacy-fields-survive-save`, `feat-1461-s3b2b-compare-kanal-schwelle` (+ `feat-1461-s3b2b.staging.setup.ts`, `frontend/playwright.1461-s3b2b.staging.config.ts`), `issue-1093-compare-layout-crash` (+ `issue-1093.staging.setup.ts`, `e2e/playwright.1093.staging.config.ts`); dazu die Nicht-Altlast-Leiche `trip-edit.spec.ts`.
- **Gekürzt + `gz-eigenstaendig:`-Kopf (6 Altlast-Dateien):** `compare-editor-fidelity-s8d`, `compare-flow-navigation`, `compare-hub-fidelity-s8c`, `compare-layout-tab-dissolution`, `compare-new-vorlage`, `issue-1080-compare-new-url`.
- **Wächter/Ratsche/Doku:** `tests/unit/test_e2e_compare_paritaet_waechter.py`, `tests/tdd/test_compare_e2e_storagestate_migration.py`, `frontend/playwright.1273-s4c.staging.config.ts`, `.github/ci_e2e_specs.txt`, `.github/workflows/ci.yml` (Z. 285-286), `docs/reference/gates_und_ratschen.md` (Z. 232).
- **Identifier:** `HUB_KINDS`, `HUB_SEL`, `seedHub`, `openHub`, `hubApiPath`, `createTestLocation` (`frontend/e2e/helpers.ts`); neu in `helpers.ts`: `ANLEGE_SEL`, `anlegenPflicht(page, kind)` (aus `tripPflicht` in `standardwerte-und-hilfe.spec.ts` herausgehoben), `ALTLAST`, `ALTLAST_MAX`, `E2E_MIN_SPECS`, `E2E_MIN_EXECUTED_HAUPT`.
- **Produktcode:** nur falls AC-20 greift. Geplant und bereits benannt: `frontend/src/lib/components/trip-new/TripNewEditor.svelte` (Reiter-Zeilen 570-596 und Mobil-Leiste, Fortschrittsbalken): **rein attributive** Ergänzung `data-testid="trip-new-tab-<id>"`, `data-locked`, `data-active`, `data-done`, `data-testid="trip-new-progress"`/`-segment` — nur wenn die Trip-Anlege-Seite im RED nicht über Rolle/ARIA (`getByRole('tab')`, `aria-selected`, `not.toHaveAccessibleName(/⊘/)`) prüfbar ist.

**Schicht und Querschnitts-Prüfpunkte:**
- **Schicht:** Testschicht (`frontend/e2e/`, `frontend/playwright.*.config.ts`, `tests/`, `.github/`, `docs/reference/`). Produktcode nur wie oben.
- **Trip/Ortsvergleich-Teilung:** Kern. Das Anlegen folgt dem Trip-Muster (`/trips/new` = `TripNewEditor`, #622; `/compare/new` = `CompareNewEditor`, struktureller Spiegel, beide bauen ihre Reiterfolge aus `anlegeKette(kind)` in `shared/subscriptionTabs.ts`, beide nutzen `canFinish`): **keine offene Designfrage, nicht erneut vorlegen.** Compare-eigen sind nur der Orte-Tab, die transponierte Übersicht und das Compare-Mail-Template; jede Abweichung davon ist unten mit Fundstelle als Befund und als Kind-Kontrast geführt.
- **Mandantentrennung:** echte `user_id` aus dem Auth-Kontext (Admin-Sitzung `storageState` aus `global.setup.ts`); für das datenbewegende Anlegen siehe AC-13. **Keine neue Registrierung** (Bremse 5/h/IP).
- **Kanäle:** nicht betroffen, es wird nichts versendet.

## Gesamtschnitt #2347 (Stand)

| Scheibe | Inhalt | Stand |
|---|---|---|
| S1–S3d | Helfer, Reiterleiste, Kopf, Listen-Menü, Alarme, Wertebereiche, Wetter-Metriken, Versand, Konflikt-412, compare-eigener Rest (48 → 14) | live |
| **S4 (diese Spec)** | **14 Restdateien + trip-edit; ALTLAST → leer, `ALTLAST_MAX` 0** | diese Spec |

Mit dem Merge von S4 sind Ticket und Epic-Scheibe #2347 erfüllt; das Schließen folgt erst nach Deploy und Selftest (Prozessregel).

## Befunde (am Code gemessen, 2026-10-30; sie korrigieren die Analyse)

1. **`/trips/new?from=` ist tot** (`routes/trips/new/+page.server.ts` lädt `templateTrip`, `+page.svelte` mountet `<TripNewEditor />` ohne Props; kein UI-Link). Das ist bereits entschieden (`feat_2277_s2c_compare_from_vorlage` Entscheidung 1, Kopf in `compareNewVorlage.ts:5`, Nebenbefund #1199). ⇒ `compare-new-vorlage` wird **nicht** kind-parametrisiert, sondern bekommt einen Kopf (Abweichung von der Analyse-Empfehlung „a").
2. **Selektoren `/trips/new` und `/compare/new` sind nicht gleich**: Vergleich `compare-editor-name`, `compare-editor-tab-<id>` mit `data-locked/active/done`, `compare-editor-progress-segment`, `compare-editor-continue-orte`, `compare-editor-activate` („Briefing aktivieren"); Trip `trip-new-name-input-desktop|mobile`, `trip-new-date-input`, Reiter als `<div role="tab" aria-selected>` ohne Zustandsattribute, `trip-new-continue-etappen`, `trip-new-save-btn`, `tn-mobile-save`, Fortschritt ohne testid. Die Reihenfolge ist geteilt (`anlegeKette`, 5 Schritte je kind), die Gate-Logik ist geteilt (`canFinish`). ⇒ die Parametrisierung braucht die Tabelle `ANLEGE_SEL[kind]` (Kind-Kontraste). Der Trip braucht zusätzlich Name **und Startdatum** und je Etappe eine GPX (`standardwerte-und-hilfe.spec.ts:70-89`, `tripPflicht`).
3. **`compare-edit-redirect` hat ein E2E-Trip-Pendant:** `issue-616-trip-one-surface.spec.ts` AC-2 (auf der Positivliste, `ci_e2e_specs.txt:514`). **Kind-Unterschied:** Trip-`/edit` reicht `?tab=` durch (`routes/trips/[id]/edit/+page.server.ts`), Compare-`/edit` bewusst nicht (`routes/compare/[id]/edit/+page.server.ts`, „Kein tab-Query-Passthrough nötig"). Der neue Fall prüft deshalb nur das nackte `/<kind>/{id}/edit`.
4. **`issue-1093-compare-layout-crash` ist nicht tot:** AC-1 prüft „Wetter-Metriken auf `/compare/new` mit echten Orten ohne `pageerror`" und `compare-layout-hourly-enabled-toggle` — eine lebende Anlege-Fläche. Tot ist nur die alte Crash-Ursache (`Step4Layout`/`LayoutPreview`). `issue-1093-unit.spec.ts` (Positivliste Z. 504) prüft `selectPreviewRows`; `layoutPreviewRows.ts` hat keinen Produktaufrufer mehr, liegt aber in `src/` und ist hier **außer Scope**: Unit-Spec, `playwright.1093.unit.config.ts` und Z. 504 bleiben; Nebenbefund an #1199.
5. **`compare-layout-tab-dissolution` ist nicht ersatzlos löschbar:** AC-4 (Wächter gegen „Kappung der Orte je Kanal"-Aussagen über alle fünf Reiter, `FORBIDDEN_CLAIMS`) und AC-5 (`hour_from`/`hour_to` überleben einen Wetter-Metriken-Commit, kein RMW-Schutz im Go-Handler) sind lebende Vergleichs-Zusicherungen. Die Datei bleibt, gekürzt auf AC-4/AC-5, mit Kopf.
6. **Die Hub-Übersicht ist zweimal implementiert:** Vergleich `CompareTabs.svelte` (Summary-Karten 799-870, mobiler Chevron-Stack 808-827 `hub-summary-row-mobile`, „Läuft autom." 723, „Noch nicht geplant" 869, Draft-CTA „Setup abschließen" `routes/compare/[id]/+page.svelte:388`), Trip `trip-detail/HubOverview.svelte` (Sprungknopf „Im Editor öffnen →" Z. 88, kein Chevron-Stack, keine Status-Kurzform, keine Versand-Karte). Das sind **strukturelle** Unterschiede; sie anzugleichen wäre Produktarbeit außerhalb dieser Scheibe. ⇒ die Fälle der Vergleichs-Übersicht bleiben unverändert in `compare-hub-fidelity-s8c` (Kopf mit dieser Begründung) und sind als Nebenbefund an #1199 zu melden; **das ist eine Abweichung vom CLAUDE.md-Katalog der erlaubten Compare-Eigenheiten und ein Entscheidungspunkt für den Tech Lead** (siehe Known Limitations).
7. **Beleg-Stufe der Zuordnung:** Rumpf gelesen — `compare-alarm-config`, `compare-detail-edit-entry`, `compare-edit-redirect`, `compare-editor-slice1`, `compare-editor-slice4` (AC-8/AC-11/#1411, Kopf von AC-9), `compare-legacy-fields-survive-save`, `compare-new-vorlage`, `issue-1093-compare-layout-crash`, `compare-layout-tab-dissolution` (AC-4/AC-5), `trip-edit` (Seed, AC-1/3/4, data integrity), `compare-editor-fidelity-s8d` (AC-1 bis AC-5), `compare-hub-fidelity-s8c` (AC-4/AC-6/AC-7), `feat-1461-s3b2b` (Mandantentrennung). Nur **Titel/Kopf** gelesen — `compare-flow-navigation` (außer Z. 675-700), `compare-editor-fidelity-s8d` AC-6 bis AC-18, `compare-hub-fidelity-s8c` Rest, `feat-1461-s3b2b` Rest, `trip-edit` AC-2/AC-5/AC-6/tabs: dort ist der Rumpf-Abgleich in /50 Pflicht.
8. **Zahlen:** Fallzahlen Alt (Tests im Rumpf): flow-navigation 17 (nicht 31), s8c 11 Fälle in 9 `describe`-Blöcken (nicht 30), slice1 5 (nicht 7), detail-edit-entry 2. `test_echter_baum_ist_nicht_leer` (≥ 10 Dateien mit „compare" im Namen): heute 27 Dateien, nach S4 **19** ⇒ Schwelle bleibt 10 (kein Anpassen, kein Absenken eines Vakuum-Wächters ohne Not).
9. **Die sieben vorbestehend roten Staging-Tests:** drei gehören zu S4 und verschwinden mit dem Umbau (`compare-layout-tab-dissolution` AC-1: veraltete Erwartung „sieben Reiter, kein Layout" — der Hub hat 5 Reiter, `hub-tab-bar` HT-4; AC-2: Stundengröße, gedeckt durch `hub-wetter-metriken-speichert-selbst` MS-2 plus `compare-stundenverlauf-wertprops`; AC-6: Anlege-Stundenverlauf, wandert nach AN-12 und muss dort grün sein). Vier gehören **nicht** zu S4: `compare-outlook-metric-selection` AC-1/AC-8 (S3d-Kopf-Datei) und `layout-tab-vergleich` AC-7/AC-11 (#1196).
10. **Mandantentrennung bei 1461:** `hub-editor-autosave-user-isolation` UI-1 (Cross-GET ⇒ 404) und `hub-cross-user-write-block` AC-2 (Cross-PUT ⇒ 404) decken „Nutzer-A-Schwelle bleibt bei B unsichtbar, Cross-PUT scheitert" für beide kinds, weil das Objekt selbst unsichtbar ist; zusätzlich XU-3 (AC-13).

## Kind-Kontraste (compare-eigen vs. gemeinsam)

| Fall | route (Trip) | vergleich | Begründung |
|---|---|---|---|
| AN Pflichtangaben | Name (`trip-new-name-input-desktop|mobile`) **und** Startdatum (`trip-new-date-input`), je Etappe eine GPX (`/api/gpx/parse`) | nur Name (`compare-editor-name[-mobile]`), dann Orte aus der Bibliothek | Trip braucht Datum + Etappen (`tripNewLogic.ts`), Vergleich Orte; `anlegenPflicht(page, kind)` kapselt es |
| AN Reiter-Zustand | `getByRole('tab')`, `aria-selected`, gesperrt ⇔ Name enthält `⊘` (ARIA) | `compare-editor-tab-<id>` mit `data-locked/active/done` | `ANLEGE_SEL[kind].reiter(id)`; Fallback laut AC-20: Trip bekommt dieselben Datenattribute |
| AN Punkte-Schritt | `etappen`, Weiter `trip-new-continue-etappen` | `orte`, Weiter `compare-editor-continue-orte` | `anlegeKette(kind)` (`subscriptionTabs.ts`) |
| AN Abschluss | `trip-new-save-btn` / `tn-mobile-save`, Ziel `POST /api/trips`, danach `/trips/{id}` | `compare-editor-activate` / `cm-mobile-activate` („Briefing aktivieren"), Ziel `POST /api/compare/presets`, danach `/compare/{id}` | Gate `canFinish` ist geteilt, Beschriftung nicht |
| AN Profil | `activity-dropdown` | `compare-editor-profile-<wert>` (Kacheln) | `HUB_SEL[kind].profilFeld` |
| AN-12 Stundenverlauf, Temperatur Max/Min, Attrappen-Abwesenheit | **kein Zweig** | `compare-layout-hourly-enabled-toggle`; Zeilen `temp_max_c`/`temp_min_c`; `channel-tab-email`/`compare-step4-layout-preview` count 0 | **echtes Compare-Eigen**: Stundenverlauf steht in `COMPARE_ONLY_SECTIONS` (#2346 S3); Trip führt eine Zeile `temperature`; die Attrappe war Vergleichs-spezifisch (#1301) |
| HL Liste | `/trips`, Überschrift „Trips", Suche „Suchen..." | `/compare`, „Orts-Vergleiche", Suche „Suchen…", Intro „Ohne Ranking — läuft, bis du stoppst." | Texte je kind in `LISTE_SEL[kind]`, Strukturaussagen gemeinsam |
| LM-1b Redirect | `/trips/{id}/edit` ⇒ `/trips/{id}` | `/compare/{id}/edit` ⇒ `/compare/{id}` | nur das nackte `/edit`; `?tab=` wird beim Trip durchgereicht, beim Vergleich nicht (Befund 3) |
| LM-12 Entwurf | Hub-Kebab ohne „Bearbeiten" | zusätzlich Knopf „Setup abschließen" | Draft-CTA existiert nur im Vergleich (`routes/compare/[id]/+page.svelte:388`); `design-compliance-group-a` AC-2 deckt sie zusätzlich |
| KB-11 Bestandsfelder | Seed `extra`: `weather_config`, `report_config`, `display_config`, `avalanche_regions`, `aggregation` mit **nicht-default** Werten | Seed `extra`: `hour_from` 10, `hour_to` 14, `forecast_hours` 72, `empfaenger` | Feldmenge je kind; Zusicherung gleich: Kopf-Speichern lässt alles Übrige bitgleich |
| HT-12 Sprungknopf | `HubOverview.svelte:88` „Im Editor öffnen →" ⇒ Reiter Etappen | `CompareTabs.svelte:841` „Bearbeiten →" (Orte-Karte) ⇒ Reiter Orte | Beschriftung/Selektor je kind, Aussage gleich: Reiter wechselt inline, keine volle Navigation |

## Zuordnung alt → neu (Regressionsnetz)

### Gelöscht: `compare-alarm-config` (2 Fälle)

| Alt | Neu |
|---|---|
| AC-1 Alarme zeigt Empfindlichkeits-Tabelle + Cooldown/Ruhezeiten, Versand-Abschnitt nicht | `hub-versand-aufbau` **VA-2** je kind (Cooldown-Karte + Level-Tabelle im Reiter Alarme, im Versand-Abschnitt keins von beidem); `alert-quiet-hours-card` zusätzlich in `hub-alarme-wertprops` **AW-4** |
| AC-2 Cooldown 90 überlebt Speichern + Reload (Server-GET) | `hub-alarme-wertprops` **AW-4** je kind (Cooldown/Empfindlichkeit/Stille Stunden, je Einzelgeste ein PUT, nach Neuladen im Stand) + `hub-save-chip` SC-2 |

### Gelöscht: `compare-detail-edit-entry` (2 Fälle, beide auf der Positivliste)

| Alt | Neu |
|---|---|
| AC-3 Mobiles Blatt eines **aktiven** Vergleichs: „Pausieren" da, „Bearbeiten" nicht | **LM-11** neu je kind in `hub-list-menu` (LM-10 prüft nur den pausierten Zustand) |
| AC-4 Entwurf: „Setup abschließen" da, `compare-detail-edit-button` count 0, Kebab ohne „Bearbeiten" | **LM-12** neu (Kebab ohne „Bearbeiten" je kind; „Setup abschließen" nur vergleich, siehe Kind-Kontraste) |

### Gelöscht: `compare-edit-redirect` (1 Fall) und `trip-edit` (11 Fälle, Wizard-Selektoren, Seed über toten Wizard `wizard-next`)

| Alt | Neu |
|---|---|
| edit-redirect AC-1 `/compare/{id}/edit` ⇒ Hub, URL ohne `/edit`, Tab-Leiste da, kein Alt-Editor | **LM-1b** je kind (`hub-list-menu`, Positivliste); Trip zusätzlich `issue-616-trip-one-surface` AC-2 |
| trip-edit AC-1 (kein Wizard) | LM-1b (route) + `issue-616` AC-2 |
| trip-edit AC-2 fünf Tabs; „tabs: anderer Tab zeigt Inhalt" | `hub-tab-bar` HT-4/HT-7 (5 Reiter), HT-3/HT-9 (Panel wechselt) |
| trip-edit „tabs: zurück zu Etappen stellt Inhalt her" | **HT-11** neu je kind |
| trip-edit AC-3 Daten vorbelegt | `hub-kopf-bearbeiten` KB-1/KB-2/KB-3 + `hub-tab-bar` HT-6 (Badge 3) |
| trip-edit AC-4 Speichern-Knopf + PUT + Redirect | entfällt als Gesten-Modell (Hub speichert selbst): `hub-*-speichert-selbst`, `hub-save-chip` SC-2; Redirect-Aussage ⇒ LM-1b |
| trip-edit AC-5 Abbrechen ohne PUT | `hub-editor-autosave-gesten-gate` GG-1 (Öffnen + Verlassen ⇒ 0 PUT) |
| trip-edit AC-6 Mobil 375×667 | `hub-tab-bar` HT-1 bis HT-5 |
| trip-edit „data integrity" (Speichern ohne Änderung erhält `weather_config`, `report_config`, `display_config`, `avalanche_regions`, `aggregation`, Etappenzahl) | **KB-11** neu je kind (siehe unten) + KB-4 + GG-1 (Stand unverändert) |

### Gelöscht: `compare-legacy-fields-survive-save` (2 Fälle, Positivliste Z. 472)

| Alt | Neu |
|---|---|
| AC-3 reine Namensänderung lässt `hour_from`/`hour_to`/`forecast_hours`/`empfaenger` unverändert (Go ohne RMW-Schutz, #1268 F003) | **KB-11** je kind in `hub-kopf-bearbeiten` (Positivliste): Seed mit nicht-default Bestandsfeldern, Name per Kopf-Bearbeiten ändern, Server-GET: alle Bestandsfelder bitgleich |
| AC-3 zweiter Speichervorgang nullt nichts (Drift) | KB-11: **zwei** aufeinanderfolgende Umbenennungen, danach Server-GET |

### Gelöscht: `compare-editor-slice1` (5 Fälle, Positivliste Z. 469) und `compare-editor-slice4` (6 Fälle)

| Alt | Neu |
|---|---|
| slice1 AC-1 gesperrter 2. Schritt wechselt ohne Namen nicht | **AN-1** je kind |
| slice1 AC-2 Name schaltet 2. Schritt frei, erster „done" | AN-1 |
| slice1 AC-3 Fortschritt 5 Segmente, steigt mit Name | **AN-2** je kind |
| slice1 AC-4 Profil-Auswahl bleibt nach Reiterwechsel | **AN-3** je kind |
| slice1 AC-5 Weiter-Knopf wechselt zum Punkte-Schritt | **AN-4** je kind |
| slice4 AC-8 „Briefing aktivieren" disabled bis Alarme besucht, Hinweis „Alarme einrichten zum Aktivieren" | **AN-5** je kind |
| slice4 AC-8 Aktivieren-Knopf existiert im Anlegen | AN-5 |
| slice4 AC-9 voller Flow: ein POST, Körper vollständig (Metriken, Wertebereiche, Stundenverlauf), Roundtrip = Hub-Wahrheit | **AN-6** je kind (Stundenverlauf-Anteil nur vergleich) |
| slice4 AC-9b Doppelklick ⇒ genau ein POST | **AN-7** je kind (Guard `saving`/`savedTripId` im Trip) |
| slice4 AC-11 keine `channel_layouts`-Attrappe | **AN-12** (vergleich) |
| slice4 AC-8 (#1411) Temperatur Max/Min zwei getrennte Zeilen | AN-12 (vergleich; Vokabular, siehe Kind-Kontraste) |

### Gelöscht: `issue-1093-compare-layout-crash` (1 Fall)

| Alt | Neu |
|---|---|
| AC-1 Wetter-Metriken mit echten Orten ohne `pageerror`, Stundenverlauf-Schalter da | **AN-11** je kind (kein `pageerror` beim Durchklicken aller fünf Schritte mit echten Orten bzw. Etappen); Schalter in AN-12 (vergleich) |

### Gelöscht: `feat-1461-s3b2b-compare-kanal-schwelle` (9 Fälle)

| Alt | Neu |
|---|---|
| AC-13 Hub: alle drei Kanal-Schwellen ändern, Reload zeigt die zuletzt gesetzten | **AW-3c** neu je kind (alle drei Kanäle nacheinander; AW-3 prüft nur einen) |
| AC-15 Telegram-/SMS-Schalter speichern, Reload behält Stellung | `hub-alarme-wertprops` **AW-3** je kind |
| AC-14 Anlegen Desktop: im Alarme-Schritt gesetzte Stufe steht nach Aktivieren/Neuladen unverändert da | AN-6 (Stufe im Alarme-Schritt wählen, nach Anlegen im Hub-Stand und in der Anzeige) |
| Vierte Fläche: Anlegen mobil zeigt Stufen-Auswahl, Startwert „gering", nichts gesetzt | **AN-10** je kind |
| AC-16 Trip-Alarm-Reiter unverändert, Speichern fehlerfrei | AW-3/AW-4 (route) |
| Mandantentrennung (A-Schwelle bei B unsichtbar, Cross-PUT scheitert) | UI-1 + `hub-cross-user-write-block` AC-2 + XU-3 (Befund 10) |
| Adversary: Doppelklick auf zwei verschiedene Stufen ⇒ Endzustand nach Reload konsistent | AW-3c (Doppelklick-Variante) + `hub-editor-autosave-gesten-gate` GG-3 |
| Adversary: Schwelle setzen, dann andere Hub-Einstellung ändern ⇒ Schwelle bleibt | `hub-alarme-wertprops` AW-5 (andere Richtung) + **AW-5b** neu (Schwelle gesetzt, danach Name/Versand ändern) |

### Hub-Ergänzungen aus `compare-flow-navigation` und `compare-editor-fidelity-s8d`

| Alt | Neu |
|---|---|
| flow AC-25 Desktop: Klick auf Kachel/Zeile öffnet Detail | **LM-13** neu je kind; mobil `hub-list-menu` LM-9 |
| flow AC-28 Breadcrumb im Hub führt zurück zur Liste (Desktop) | **KA-10** neu je kind |
| flow AC-28 mobil: Zurück-Pfeil führt zur Liste | **KA-11** neu je kind |
| flow AC-27 „Abbrechen" im Anlegen ⇒ Liste, kein POST | **AN-8** je kind |
| flow AC-26/AC-29 kompletter Fluss endet im Hub des NEUEN Vergleichs | AN-6 (Ziel `HUB_SEL[kind].hubUrl(neueId)`) |
| flow AC-5 Hub-Kebab (pausiert) Fortsetzen/Archivieren/Löschen | `hub-list-menu` LM-10 |
| flow KL-7 „Archivieren" im Hub-Kebab ⇒ `PATCH /state`, verlässt die aktive Liste | **LM-10b** neu je kind (LM-10 öffnet nur) |
| flow AC-30 „Bearbeiten →" der Orte-Karte wechselt inline | **HT-12** je kind |
| flow Slice 4 AC-8 Stundenverlauf-Steuerung im Editor; AC-9 keine Attrappe, kein Channel-Tab | AN-12 (vergleich) |
| flow F001 bestehender Vergleich öffnet ohne „Ungespeichert" | Fläche entfällt (Alt-Editor, `/edit` ist Redirect, LM-1b); Speichern-Anzeige: `hub-save-chip` SC-1/SC-2 |
| flow `?tab=layout` landet in Wetter-Metriken, URL bereinigt (Z. 675-700) und layout-tab AC-3 | `hub-reiter-alt-kennungen-umleitung`: neuer Test je Hub `?tab=layout` ⇒ `?tab=wetter-metriken` (`LEGACY.layout`, `subscriptionTabs.ts`) |
| s8d AC-1 mobiler Seitenkopf, „Neuer Vergleich" navigiert; Desktop unverändert | **HL-1** je kind |
| s8d AC-2 kurzer mobiler Intro-Satz | **HL-2** je kind |
| s8d AC-3 Suchfeld nur Desktop, filtert | **HL-3** je kind |
| s8d AC-4 mobile Stats kompakt | **HL-4** je kind |
| s8d AC-5 mobiles Padding, kein Overflow | **HL-5** je kind |
| s8d AC-8 bis AC-12, AC-15, AC-17/AC-18 (mobile CTA je Schritt, Aktivieren im Sticky-Footer, genau ein Kopf, Zurück, Alarme letzter Schritt) | **AN-9** je kind |
| layout-tab AC-1 sieben Reiter, kein „Layout" | veraltete Erwartung; `hub-tab-bar` HT-4 (5 Reiter) + `hub-reiter-alt-kennungen-umleitung` Reihenfolge-Tests (Trip Z. 363, Vergleich Z. 380) |
| layout-tab AC-2 Stundengröße umschalten ⇒ PUT, bleibt | `hub-wetter-metriken-speichert-selbst` MS-2 + `compare-stundenverlauf-wertprops` |
| layout-tab AC-6 Anlege-Seite hat Stundenverlauf an derselben Stelle | AN-12 (vergleich) |

### Bleibt (Köpfe, gekürzt)

`compare-layout-tab-dissolution`: AC-4, AC-5 (Befund 5). `compare-flow-navigation`: Slice 5 AC-12/AC-13 (Orte-Tab: Smart-Import nummeriert, Zähler „min. 2 erforderlich", Bibliothek nach `group_id`). `compare-editor-fidelity-s8d`: AC-6/AC-7 (mobiler Orte-Tab), AC-13/AC-14 (Profil-Häkchen, gekürzte Metrik-Zeile), AC-16 (⊘-Hinweis bei 1 Ort). `compare-hub-fidelity-s8c`: AC-3, AC-4/AC-6, AC-5 (2), AC-7, AC-8 (2), AC-9 (Befund 6); **gelöscht** darin nur die drei gedeckten Fälle AC-10 (Breadcrumb 2 Krümel ⇒ `hub-kopf-aufbau` KA-7), AC-12 (mobile Eyebrow ⇒ KA-6), AC-11 (Profil-Label „Wandern" ⇒ KA-6/KA-7). `compare-new-vorlage` und `issue-1080-compare-new-url`: unverändert, nur Kopf.

## Köpfe (`gz-eigenstaendig:`, erste 30 Zeilen, ≥ 15 Zeichen, wahre Begründung)

| Datei | Begründung | Trip-Pendant / Beleg |
|---|---|---|
| `compare-new-vorlage.spec.ts` | `?from=`-Vorbelegung gilt nur für den Vergleich; `/trips/new?from=` ist tot (`templateTrip` ungenutzt), bewusst so entschieden | `feat_2277_s2c` Entscheidung 1; Cross-User AC-6 bleibt hier |
| `issue-1080-compare-new-url.spec.ts` | Smart-Import von Orten per URL/Koordinaten im Orte-Schritt; der Trip hat keine Orte, sondern Etappen mit GPX | Orte-Tab ist die erlaubte Compare-Eigenheit |
| `compare-layout-tab-dissolution.spec.ts` | „Kappung der Orte je Kanal"-Aussagen und `hour_from`/`hour_to` nach Stundenverlauf-Commit gibt es nur beim Ortsvergleich | Trip: `hub-wetter-metriken-speichert-selbst`, KB-11 |
| `compare-flow-navigation.spec.ts` | nur noch der Orte-Tab des Anlege-Ablaufs (Smart-Import, Zähler, Gruppen-Kopfzeilen); Navigation und Kebab leben kind-parametrisiert in `hub-list-menu`/`hub-kopf-aufbau`/`hub-tab-bar`/AN | `step2_orte_library_grouping.test.ts` |
| `compare-editor-fidelity-s8d.spec.ts` | nur noch Orte-Tab (mobil) und Vergleichs-Profilkachel mit gekürzter Metrik-Zeile; Trip wählt die Aktivität per Dropdown | `hub-kopf-bearbeiten` KB-3 |
| `compare-hub-fidelity-s8c.spec.ts` | Übersichts-Panel des Vergleichs-Hubs (Summary-Karten, Chevron-Stack, Status-Kurzform, Versand-Karte) hat keinen Gegenpart im Trip-Hub (`HubOverview.svelte` ist ein anderes Markup, Befund 6); Orte-Tab-Texte | `hub-tab-bar` HT-10 (Stat-Karten), `trip-detail-region` |

## Estimated Scope

- **LoC (Testcode, netto):** neu ca. +1100 (AN ≈ 450, HL ≈ 150, Hub-Ergänzungen ≈ 330, `helpers.ts` ≈ 80, Köpfe/Bereinigungen ≈ 90) / gelöscht ca. −2900 (alarm-config 125, detail 141, redirect 98, legacy 136, slice1 88, slice4 275, 1093 71, 1461 596, trip-edit 211, s8d/flow/s8c/layout-Kürzungen ≈ 900, Setups/Configs ≈ 250). Netto negativ, brutto über dem LoC-Limit (~250): `loc_limit_override` in /50 auf 1100 setzen, Reihenfolge der Commits unten.
- **Files:** ca. 45 (2 neu, 7 erweitert, 8+1 gelöscht samt ≈ 7 Setups/Configs, 6 Köpfe, Wächter, Struktur-Test, 1273-Config, Ratsche, `ci.yml`, Doku, Verweise).
- **Effort:** high. **Risiko:** MEDIUM bis HIGH — (1) Trip-Anlege-Fälle erstmals gemessen (GPX-Upload, Reiter ohne Attribute), (2) Ratschen-Zahlen müssen exakt stimmen, (3) viele Trip-Pendants können rot sein (AC-20), (4) CI-`e2e` ~17 min, Registrierungsbremse lokal.

**Commit-Reihenfolge in /50 (jeder Commit für sich grün, `ALTLAST`/`ALTLAST_MAX` nur zusammen):**
1. `helpers.ts` (`ANLEGE_SEL`, `anlegenPflicht`) + HL + AN-1 bis AN-8 (+ Positivliste, `E2E_MIN_SPECS` per Zählung, `E2E_MIN_EXECUTED_HAUPT` per `--list`).
2. AN-9 bis AN-12.
3. Hub-Ergänzungen (LM, KA, HT, KB-11, AW, XU-3, Alt-Kennungen) — KB-11 vor der Löschung von `compare-legacy-fields-survive-save` (Positivliste Z. 472 wechselt auf eine bereits gelistete Datei).
4. Löschungen G2 (je Datei: Datei, Setup/Config, Struktur-Test, 1273-Config, Wächter-Eintrag, Positivliste im selben Commit) — jede erst nach grünem Lauf ihres Zielfalls.
5. Köpfe + Kürzungen, ALTLAST → leer, `ALTLAST_MAX` = 0, Docstring, Doku, finale Ratsche-Messung.

## Dependencies

| Entity | Type | Purpose |
|---|---|---|
| `frontend/e2e/helpers.ts` (`HUB_KINDS`, `HUB_SEL`, `seedHub`, `openHub`, `hubApiPath`, `createTestLocation`) | module | Basis |
| `standardwerte-und-hilfe.spec.ts` (`tripPflicht`, `tripDurchgeklickt`), `e2e/fixtures/test-trip.gpx` | module | Vorlage Trip-Anlegen (wird nach `helpers.ts` gehoben, Spec bleibt Aufrufer) |
| `shared/subscriptionTabs.ts` (`anlegeKette`, `LEGACY`), `tripNewLogic.ts`/`compare-new` (`canFinish`) | module | geteilte Reiterfolge und Gate |
| `hub-list-menu`, `hub-kopf-aufbau`, `hub-tab-bar`, `hub-kopf-bearbeiten`, `hub-alarme-wertprops`, `hub-cross-user-write-block`, `hub-reiter-alt-kennungen-umleitung` | spec | Erweiterungsziele |
| `.github/ci_e2e_specs.txt`, `ci.yml`, `e2e_gate.py`, `tests/unit/test_e2e_positivliste_ratschen_bindung.py` | CI | Positivliste und Schwellen |
| `tests/unit/test_e2e_compare_paritaet_waechter.py`, `tests/tdd/test_compare_e2e_storagestate_migration.py`, `frontend/playwright.1273-s4c.staging.config.ts` | test/config | `ALTLAST`, `MIGRATED_FILES`, storageState-Projekt |

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `frontend/e2e/hub-anlegen-ablauf.spec.ts` | CREATE | AN-1 bis AN-12 (siehe Fälle) |
| `frontend/e2e/hub-liste-seitenrahmen.spec.ts` | CREATE | HL-1 bis HL-5 je kind |
| `frontend/e2e/helpers.ts` | MODIFY | `ANLEGE_SEL`, `LISTE_SEL`, `anlegenPflicht` |
| `frontend/e2e/standardwerte-und-hilfe.spec.ts` | MODIFY | ruft `anlegenPflicht` statt lokaler Kopie (Verhalten unverändert) |
| `hub-list-menu`, `hub-kopf-aufbau`, `hub-tab-bar`, `hub-kopf-bearbeiten`, `hub-alarme-wertprops`, `hub-cross-user-write-block`, `hub-reiter-alt-kennungen-umleitung` (`.spec.ts`) | MODIFY | Ergänzungsfälle laut Zuordnung |
| 8 Altlast-Specs + `trip-edit.spec.ts` | DELETE | siehe Source |
| `compare-edit-redirect.staging.setup.ts`, `playwright.1273-s3.red.config.ts`, `feat-1461-s3b2b.staging.setup.ts`, `playwright.1461-s3b2b.staging.config.ts`, `issue-1093.staging.setup.ts`, `e2e/playwright.1093.staging.config.ts` | DELETE | Setups/Configs der gelöschten Specs; vorher `grep` auf Mitbenutzer (Befund: `feat-1256-s2.staging.setup.ts` und `feat-1258-s4.staging.setup.ts` nennen Altlast-Specs nur im Kommentar; `playwright.1080.staging.config.ts`, `1256-s2/s8c/s8d` und `compare-layout-tab-dissolution` bleiben samt Setups) |
| 6 Köpfe-Specs | MODIFY | gekürzt, `gz-eigenstaendig:`-Kopf |
| `frontend/playwright.1273-s4c.staging.config.ts` | MODIFY | Einträge `compare-alarm-config`, `compare-legacy-fields-survive-save` raus |
| `tests/tdd/test_compare_e2e_storagestate_migration.py` | MODIFY | beide aus `MIGRATED_FILES` (Falle wie S3d: `read_text` auf gelöschte Datei = rot) |
| `tests/unit/test_e2e_compare_paritaet_waechter.py` | MODIFY | `ALTLAST` leer, `ALTLAST_MAX` Literal 0, Docstring/Kommentar „S4", Schwelle 10 bleibt |
| `.github/ci_e2e_specs.txt`, `.github/workflows/ci.yml` | MODIFY | Z. 468/469/472 raus, `hub-anlegen-ablauf` + `hub-liste-seitenrahmen` rein, Z. 504 bleibt; `E2E_MIN_SPECS` per Zählung (Erwartung 73 − 3 + 2 = 72), `E2E_MIN_EXECUTED_HAUPT` gemessen |
| `docs/reference/gates_und_ratschen.md` | MODIFY | Z. 232 (64/369 veraltet) auf gemessene Werte, „ALTLAST leer" |
| Verweis-Dateien (Kommentare/Quelltext-Belege) | MODIFY | `issue_683_wizard_remove.test.ts`, `compare_list_mobile_chrome.test.ts`, `compareAggregationGrouping.test.ts`, `step2_orte_library_grouping.test.ts`, `compare_hub_fidelity.test.ts`, `tests/tdd/test_bug590_signal_removal_telegram_start.py`, `tests/tdd/test_compare_alert_channel_threshold.py`, `issue-682-compare-editor-mobile.spec.ts`, `weather-metrics-tab-autosave.spec.ts`, `trips.spec.ts`, `feat-1745-a-alarm-premium-sms.spec.ts`, `e2e_frontend_browser_gate.py`, `operations_playbook.md`: jede Fundstelle prüfen; liest sie die Datei (`read_text`, `readFileSync`, Import), im selben Commit umhängen |
| `TripNewEditor.svelte` | MODIFY (nur AC-20) | rein attributive Testids/Datenattribute |

## Implementation Details

Alle neuen Fälle: `for (const kind of HUB_KINDS) test(\`XX-n (${kind}): …\`)`; Setup `seedHub`/`anlegenPflicht`; Warten nur `expect.poll`, `toHaveAttribute`, `toHaveCount`, `toBeVisible`, `waitForResponse`/`waitForRequest` und das Stabilitätsfenster `bleibtBei` — **kein** `waitForTimeout`, kein `skip`/`test.fixme`, kein UI-`login()`, kein fester `storageState`-Pfad, kein `__dirname`, kein `page.screenshot({path})`, kein `networkidle` als einziges Warten. Erwartungswerte stehen fest im Test, nie aus dem gerenderten Produkt. `finally`: `hub.aufraeumen()` bzw. Löschen des angelegten Objekts per API. kind-Zweige nur laut „Kind-Kontraste", jeder mit Begründungskommentar. Anlege-Fälle räumen ihr angelegtes Objekt (Präfix `E2E-GZ-`) im `finally` weg; höchstens ein aktiver Vergleich je Fall (kein 409).

### Fälle

**`hub-anlegen-ablauf.spec.ts` (AN, je kind, Desktop 1280×900 wenn nicht „mobil")**
- **AN-1:** Anlege-Seite öffnen ⇒ 2. Schritt gesperrt, Klick darauf wechselt nicht; nach `anlegenPflicht` (Name; Trip zusätzlich Datum) ist er frei, der 1. Schritt „done".
- **AN-2:** Fortschritt hat genau 5 Segmente (`anlegeKette(kind).length`) und steigt mit der Pflichteingabe („1 / 5").
- **AN-3:** Profil bzw. Aktivität wählen, Schritt wechseln und zurück ⇒ Auswahl bleibt.
- **AN-4:** Weiter-Knopf des 1. Schritts wechselt aktiv auf den Punkte-Schritt (`etappen`/`orte`).
- **AN-5:** vor dem Alarme-Schritt ist der Abschluss-Knopf `disabled`/`aria-disabled`, nach Besuch aller Pflichtschritte aktiv; Hinweistext je kind per `ANLEGE_SEL`.
- **AN-6:** voller Durchlauf mit echten Auswahlen (Metrik umschalten, Wertebereiche aus Profil-Vorbelegung, im Alarme-Schritt eine Stufe setzen; vergleich zusätzlich Stundenverlauf-Metrik) ⇒ genau **ein** `POST` (`waitForRequest`), Körper vollständig und ohne `id`, Antwort 200/201, Seite landet im Hub des **neuen** Objekts, `GET`-Roundtrip trägt jeden gewählten Wert und die Stufe, die Anzeige im Reiter Alarme zeigt sie.
- **AN-7:** Doppelklick auf den Abschluss-Knopf ⇒ genau ein `POST`, genau ein neues Objekt in der Liste.
- **AN-8:** „Abbrechen"/Zurück im Anlegen ⇒ Liste, **kein** `POST`, kein neues Objekt.
- **AN-9 (mobil 390×844):** Beschriftung der Floating-CTA wechselt je Schritt, im letzten Schritt der Abschluss im Sticky-Footer (nicht vorher), genau ein Seitenkopf, Zurück führt zur Liste, Titel wechselt mit dem Schritt, Alarme ist der letzte Schritt.
- **AN-10 (mobil):** Alarme-Schritt zeigt die Stufen-Auswahl, Startwert „gering", im Körper des späteren POST ist ohne Geste nichts gesetzt.
- **AN-11:** alle fünf Schritte mit echten Orten bzw. Etappen nacheinander öffnen ⇒ kein `pageerror` (Listener ab `goto`), Schritt-Inhalt sichtbar.
- **AN-12 (nur vergleich, Kind-Kontrast):** Wetter-Metriken-Schritt zeigt `compare-layout-hourly-enabled-toggle`; `channel-tab-email` und `compare-step4-layout-preview` count 0; Zeilen `temp_max_c` und `temp_min_c` je genau eine, mit „Maximum"/„Minimum", unabhängig anhakbar.

**`hub-liste-seitenrahmen.spec.ts` (HL, je kind)** HL-1 mobiler Seitenkopf mit Titel/Eyebrow, „Neu"-Knopf führt zur Anlege-Seite (`/trips/new` bzw. `/compare/new`), andere Liste trägt ihn nicht, Desktop unverändert; HL-2 kurzer Intro-Satz mobil sichtbar, langer Desktop-Satz nicht sichtbar; HL-3 Suchfeld mobil unsichtbar, Desktop sichtbar und filtert; HL-4 Stat-Schrift mobil kleiner als Desktop; HL-5 kein horizontaler Überlauf, erste Karte 12–20 px vom Rand.

**Hub-Ergänzungen (je kind, in den Zielspecs):** LM-1b nacktes `/<kind>/{id}/edit` ⇒ Hub, `/edit` nicht in der URL, Reiterleiste da, Anlege-Editor (`trip-new-editor`/`compare-editor`) count 0 · LM-10b Hub-Kebab „Archivieren" ⇒ `PATCH …/state`, Eintrag fehlt in der aktiven Liste, steht unter `/archiv` · LM-11 mobiles Blatt eines aktiven Eintrags: „Pausieren" da, „Bearbeiten" (exact) count 0 · LM-12 Entwurf: Hub-Kebab ohne „Bearbeiten"; vergleich: „Setup abschließen" sichtbar, `compare-detail-edit-button` count 0 · LM-13 Desktop-Klick auf Zeile/Kachel öffnet den Hub · KA-10 Breadcrumb-Klick (Desktop) ⇒ Liste · KA-11 mobiler Zurück-Pfeil ⇒ Liste · HT-11 Reiter A → B → A stellt den Inhalt von A wieder her · HT-12 Sprungknopf der Übersicht wechselt den Reiter inline (URL-`tab` ändert sich, keine volle Navigation) · KB-11 siehe Kind-Kontraste: Seed mit nicht-default Bestandsfeldern, **zwei** Umbenennungen nacheinander, Server-GET: alle Bestandsfelder bitgleich · AW-3c alle drei Kanal-Schwellen nacheinander setzen, Reload zeigt die zuletzt gesetzten; Variante Doppelklick auf zwei Stufen ⇒ Endzustand nach Reload konsistent · AW-5b Schwelle setzen, danach Name im Kopf ändern ⇒ Schwelle bleibt · XU-3 von Nutzer A per API angelegtes Objekt (Trip und Vergleich): Nutzer B `GET` ⇒ 404 und nicht in B's Liste (nutzt den Zweitnutzer, den `hub-cross-user-write-block` bereits anlegt) · `?tab=layout` ⇒ `?tab=wetter-metriken`, URL bereinigt, kein Layout-Panel.

### Wächter, Ratsche, CI

- **Wächter:** `ALTLAST = frozenset()`, `ALTLAST_MAX = 0` (Literal) im selben Commit wie die letzte Streichung; Kommentarblock um „S4 (2026-10-30): ALTLAST leer" ergänzen; die Selbsttests (`test_toter_altlast_eintrag_ist_rot`, `test_konformer_altlast_eintrag_ist_rot`, `test_altlast_deckt_verstoss` mit synthetischer Liste) bleiben; `test_echter_baum_ist_nicht_leer` bleibt bei ≥ 10 (Soll nach S4: 19 Dateien mit „compare" im Namen).
- **Ratsche:** `ci_e2e_specs.txt` verliert `compare-detail-edit-entry`, `compare-editor-slice1`, `compare-legacy-fields-survive-save`, gewinnt `hub-anlegen-ablauf` und `hub-liste-seitenrahmen` (alphabetisch, Aufnahme-Kommentar mit Filter-B-Beleg und #2347 S4); `issue-1093-unit` bleibt. `E2E_MIN_SPECS` = Ergebnis von `grep -c '^e2e/' .github/ci_e2e_specs.txt` (**Erwartung 72** = 73 − 3 + 2; verbindlich ist die Zählung). `E2E_MIN_EXECUTED_HAUPT` am Endstand **neu messen** per `npx playwright test --list` über die Hauptlauf-Auswahl (Positivliste ohne `bug-703`, `Total: … tests in … files` inkl. `global.setup`), **nie addieren**; Ausgangswert 549. Begründungszeilen in `ci.yml` um S4 fortschreiben; `docs/reference/gates_und_ratschen.md:232` auf die gemessenen Werte.
- **Filter A/B:** neue Positivlisten-Specs ohne `waitForTimeout`/`skip`/`__dirname`/`.staging`, Nachweise im Aufnahme-Kommentar.

### AC-20-Nachträge (Phase 6, 2026-10-30)

Die Abschnitte Source/Affected Files/Kind-Kontraste sind eingefroren; die laut AC-20 nachzutragenden Produktdateien und Kind-Kontraste stehen deshalb hier.

**Berührte Produktdateien (Trip dem Vergleich angeglichen, Code geteilt statt neu gebaut):**
- `frontend/src/lib/components/trip-new/tripNewLogic.ts` — AN-2: `PROGRESS_STEPS` = `anlegeKette('trip')` ohne optionale Schritte ⇒ 5 Segmente inkl. Wertebereiche (wie `CompareNewEditor`, das `TAB_DEFS` zählt).
- `frontend/src/lib/components/trip-new/TripNewEditor.svelte` — AN-2: `data-testid="trip-new-progress"`/`"trip-new-progress-segment"` (nur Desktop, wie `compare-editor-progress`); AN-5: Hinweis „Alarme einrichten zum Speichern" im Desktop-Sticky-Footer solange `!ready`; AN-9: die schwebenden CTAs der Schritte Route/Etappen/Wegpunkte in den `tn-mobile-footer` verlagert, Weiter-Aktion je Schritt („Etappen anlegen →" in `tn-mobile-route-cta`, „Wegpunkte prüfen →/Direkt zu Wetter", „Wegpunkte übernehmen →/Überspringen", „Wertebereiche festlegen →", „Alarme einrichten →"), `tn-mobile-save` nur im Schritt Alarme (wie `cm-mobile-cta`/`cm-mobile-activate`).
- `frontend/src/routes/trips/+page.svelte` — HL-1..HL-4: mobiler `PageHeader` in `desktop:hidden` (Eyebrow „Workspace · N", Titel „Trips", Knopf `trip-list-new-mobile`), kurzer Intro-Satz „Mehrtages-Trips mit Briefings je Etappe — morgens für heute, abends für morgen.", mobile Stats `size="sm"` vor den Filter-Pillen, Desktop-Kopf und Suche nur Desktop (gespiegelt aus `routes/compare/+page.svelte`).
- `frontend/src/routes/trips/[id]/+page.svelte` — KA-11: mobiler `BackLink` (`href="/trips"`, `aria-label` „Zurück zur Übersicht", wie `routes/compare/[id]/+page.svelte:349`) in `trip-detail-breadcrumb-bar`, nur ≤ 899 px, `margin-block: -8px` (Zeilenhöhe unverändert, `trip-hub-kopf-region-aktivitaet` AC-13). Der Krümel-Link „Trips" (KA-10, `issue-592` AC-13) bleibt.
- Abgelöste Alt-Invarianten (Tests umgestellt, nicht abgeschwächt): `tripNewLogic.test.ts` („Wertebereiche ist kein eigenes Segment" ⇒ eigenes Segment, Wegpunkte nicht), `trip_new_mobile_rahmen_angleichung.test.ts` und `trip_new_reiterleiste_besuchs_flags.test.ts` (`tn-mobile-save` im Schritt Alarme gerendert; neu: fehlt im Schritt Route), `e2e/issue-661-trip-new-mobile.spec.ts` AC-1 (Fuß sichtbar, Speichern verborgen).

**Neue Kind-Kontraste (Ergänzung zur Tabelle oben):**

| Fall | route (Trip) | vergleich | Begründung |
|---|---|---|---|
| AN-6 Metrik-Auswahl | Grundauswahl-Knopf in `wm2-grundauswahl` („Schneehöhe"), aktiv = Klasse `on`, Feldpfad `display_config.metrics[]` (`metric_id`/`enabled`) | Zeilen-Checkbox `weather-metrics-vergleich-row-snow_depth`, Feldpfad `display_config.active_metrics` | Bedienelement und Feldpfad je kind (wie `MS_SEL` in `hub-wetter-metriken-speichert-selbst`); Zusicherung gleich: Umschalten steht im POST und im Roundtrip |
| AN-5 Hinweis | „Alarme einrichten zum Speichern" | „Alarme einrichten zum Aktivieren" | folgt der Abschluss-Beschriftung; Gate `canFinish` geteilt |
| LM-10b Archivieren | Hub fragt vorher nach (`trip-detail-archive-confirm-dialog`) | archiviert sofort | Bedienschritt je kind; Zusicherung gleich: `PATCH …/state`, fehlt in der aktiven Liste, steht unter `/archiv` |
| HL-3 Suche | Platzhalter „Suchen...", zweiter Seed unverändert | Platzhalter „Suchen…", zweiter Seed `schedule: manual` | höchstens 2 aktive Vergleiche je Nutzer (409); Suche in beiden Listen nur Desktop |
| KA-10 Breadcrumb | Link „Trips" in `trip-detail-breadcrumb-bar` | Link „ORTS-VERGLEICHE" | Beschriftung je kind; Klick führt zur Liste dieser Art |

### Nachträge Teil D (Phase 6, 2026-10-30): Ersatzfälle für in Teil A gelöschte Aussagen

Die Abschnitte Source/Zuordnung sind eingefroren; die Ergänzungen der Zuordnung alt → neu stehen deshalb hier. Die Zahl 61 in AC-21 bleibt Bezug für die **Ursprungsfälle**; Teil D kommt mit **8 Zusatzfällen** hinzu (4 Fälle × 2 kinds), alle in bereits gelisteten Positivlisten-Dateien. `E2E_MIN_SPECS` bleibt 72 (`grep -c '^e2e/'`), `E2E_MIN_EXECUTED_HAUPT` neu gemessen: `Total: 607 tests in 72 files` (vorher 599).

| Alt (gelöscht in Teil A) | Neu (Teil D) |
|---|---|
| slice4 AC-11 / flow Slice 4 AC-9 „keine `channel_layouts`-Attrappe" (DOM: `channel-tab-email` count 0) | **AN-12** umgestellt: die DOM-Aussage ist seit #1703 S8 überholt (geteilter LayoutTab mit `LTChannelPicker` steht legitim im Abschnitt „Reihenfolge"); neu: der Kanal-Umschalter existiert genau einmal und nur im LayoutTab mit der Reihenfolge-Karte, kein Anlege-Schritt `layout`/`versand`, keine Layout-Vorschau. Dazu **AN-6** (vergleich): Anlege-POST und GET-Roundtrip tragen kein `display_config.channel_layouts` (im Vergleich Ballast, #1351; die Kanal-Auswahl reist als `channel_active_metrics`). Beim Trip ist `channel_layouts` echte Kanal-Auswahl (#1575) — daher dort kein Zweig. |
| feat-1461-s3b2b Adversary „Schwelle setzen, dann Amtliche-Warnungen-Schalter ⇒ PUT trägt die Schwelle mit" | **AW-5c** je kind (`hub-alarme-wertprops`): SMS-Schwelle „hoch", dann Amtliche Warnungen umschalten ⇒ PUT-Körper `alert_channel_thresholds.sms == HIGH`, Server-Stand und Anzeige nach Neuladen „hoch". Beide Speicherwege senden die Schwellen mit (Vergleich `alarmeVergleichSpeicherung.ts` ALARM_TOP, Trip `alarmeDeliveryPayload.ts`). |
| flow F001 „bestehender Vergleich MIT `channel_layouts` öffnet ohne Ungespeichert" (bisher „Fläche entfällt") | **SC-1b** je kind (`hub-save-chip`): Seed mit `display_config.channel_layouts` (Trip `gust`, Vergleich `wind_max_kmh`), Reiter Wetter-Metriken (dort verarbeitet der geteilte LayoutTab das Feld) ⇒ 2,5 s Stabilitätsfenster mit 0 PUT und Chip `idle`, Feld bitgleich. **Kein Kind-Kontrast**: das gleichwertige Trip-Feld ist dasselbe Feld (`WeatherMetricsTab.svelte` liest es beim Laden). |
| flow AC-26/AC-27 „echter Klick auf ‚+ Neuer Vergleich' statt goto", Abbrechen ⇒ Liste | **AN-13** je kind: Klick auf „+ Neuer Trip"/„+ Neuer Vergleich" in der Desktop-Liste (`LISTE_SEL[kind].neuDesktop`) ⇒ Anlege-URL im 1. Schritt; Abbrechen ⇒ Liste, 0 POST. Der Rest von AC-26/AC-29 (Landung im neuen Hub) bleibt AN-6. |
| s8d AC-8..AC-12 mobile CTA-Kette (Wortlaut je Schritt, Punkte-Gate) | **AN-14** je kind, auf den gemeinsamen Pflichtschritten per CTA-Klick: ohne Namen „Trip-Name eingeben"/„Name eingeben" (Klick wechselt nicht), mit Namen „Etappen anlegen →"/„Orte hinzufügen →", Punkte-Gate „noch N GPX nötig"/„noch 2 Orte nötig" **gesperrt**, Weiter „Direkt zu Wetter"/„Wetter-Metriken →" (Trip überspringt den optionalen Schritt Wegpunkte), dann gemeinsam „Wertebereiche festlegen →", „Alarme einrichten →", Abschluss im Sticky-Footer frei. |
| s8d AC-8 „CTA ohne Namen ist `disabled`" und AC-17/AC-18 Desktop-Weiter-Knöpfe | **nicht ersetzt — bleiben in `compare-editor-fidelity-s8d`** (Kopf fortgeschrieben). Zwei Trip-Produktlücken (AC-20): (1) `TripNewEditor.svelte` `tn-mobile-route-cta` (ca. Z. 1228) rendert das `MBtn` ohne `disabled`, nur `variant="quiet"`, der Handler schluckt den Klick; (2) der Desktop-Trip hat in Wetter-Metriken und Wertebereiche keinen Weiter-Knopf (Vergleich: `compare-editor-continue-wertebereiche`/`-alarme`). Erst nach deren Behebung können AC-8 (gesperrt) und AC-17/AC-18 in AN-14 bzw. einen Desktop-Fall wandern. |

### Nachträge Teil E (Phase 6, 2026-10-30): Trip-Lücken aus Teil D geschlossen, HL-4 neu gefasst, Race der Standardwerte

Source/Zuordnung bleiben eingefroren; Ergänzungen stehen hier. Prinzip AC-20: der Trip wird dem Vergleich angeglichen, die Tests bleiben streng.

**Berührte Produktdateien:**
- `frontend/src/lib/components/trip-new/TripNewEditor.svelte` — (1) `tn-mobile-route-cta`: das `MBtn` trägt `disabled={!(name.trim() && startDate)}`, dieselbe Bedingung wie der Handler (wie `cm-mobile-cta` im Vergleich). (2) Desktop-Weiter-Füße mit dem geteilten Atom `Btn` (`variant="accent"`), benannt nach dem Ziel wie im Vergleich: `trip-new-continue-wertebereiche` („Wertebereiche festlegen →", im Schritt Wetter-Metriken) und `trip-new-continue-alarme` („Alarme einrichten →", im Schritt Wertebereiche). (3) Race: `defaultsBereit` des Standardwerte-Knopfs = `catalogLoaded && (wertebereicheVorbelegt || weatherMetrics.length === 0)`; `wertebereicheVorbelegt` setzt `handleVorbelegungFertig`, das an beiden `CorridorEditor`-Einbettungen (Desktop und mobil) als `onVorbelegungFertig` hängt. Ohne aktive Metrik gibt es nichts vorzubelegen (der Editor bricht dann vor der Vorbelegung ab), deshalb kein Deadlock; scheitert der Wetter-Metriken-Katalog, bleibt der Knopf wie bisher gesperrt (Bestandsweg über die Reiter bleibt offen).
- `frontend/src/lib/components/shared/corridor-editor/CorridorEditor.svelte` — neue optionale Prop `onVorbelegungFertig`: der Vorbelegungs-Effekt (route, Anlege-Modus) ruft sie genau einmal, auf JEDEM Ausgang (mit Zeilen, leere Vorbelegung, Bestand/gehaltener Stand), und erst NACH `onCorridorsChange`. Scheitert der Zusatz-Katalog, setzt der Lade-Effekt `routeExtraDefs = []` und die Vorbelegung läuft trotzdem. Zeilenzahl der Datei oberhalb der eingefrorenen `context ===`-Zweige unverändert (`context_herkunft_zweige_eingefroren`).
- Unit-Nachweise: `trip-new/__tests__/standardwerte_wartet_auf_wertebereiche_vorbelegung.test.ts` (neu, Wirkstelle: Knopf gesperrt vor der Vorbelegung, Klick ohne POST; nach `onVorbelegungFertig` der Desktop- bzw. mobilen Einbettung frei, POST trägt die vorbelegten Korridore; ohne Metrik frei; Katalog-Fehler gesperrt), `corridor_editor_create_mode_route.test.ts` (Meldung einmal, jeder Ausgang, Reihenfolge nach den Korridoren), `standardwerte_payload_paritaet_trip.test.ts` F001 (Rückkanal allein gibt nicht mehr frei, erst mit der Vorbelegung — Vertrag geändert, Zusicherung verschärft).

**Zuordnung alt → neu (Ergänzung, ersetzt die Zeile „nicht ersetzt" aus Teil D):**

| Alt (`compare-editor-fidelity-s8d`) | Neu (Teil E) |
|---|---|
| AC-8 „leerer Name ⇒ CTA ‚Name eingeben' `disabled`, Schritt bleibt" | **AN-14** je kind: zusätzlich `toBeDisabled()` auf der CTA ohne Namen (Trip „Trip-Name eingeben", Vergleich „Name eingeben"); die Prüfung „Klick wechselt nicht" bleibt. Fallzahl gleich. |
| AC-17/AC-18 „Wertebereiche-Fuß, dann ‚Alarme einrichten →' ⇒ Alarme; kein Versand-Schritt; Aktivieren frei" | **AN-15** je kind (Desktop 1280): Wetter-Metriken ⇒ Weiter-Fuß „Wertebereiche festlegen →" ⇒ Wertebereiche aktiv ⇒ „Alarme einrichten →" ⇒ Alarme aktiv; je Schritt nur der eigene Fuß sichtbar; im Schritt Alarme ist **kein** Weiter-Fuß der Art sichtbar (Rumpf-Abgleich: alt nur `continue-versand`/`tab-versand` count 0 — strenger); Abschluss frei; der Weg legt nichts an (0 POST). Selektoren `ANLEGE_SEL[kind].weiterNach`/`weiterPraefix` (helpers.ts). |

In `compare-editor-fidelity-s8d` bleiben AC-6/AC-7, AC-9..AC-12 (Zwischenstand „noch 1 Ort nötig" ohne Trip-Pendant), AC-13/AC-14 und AC-16 (Kopf fortgeschrieben); die Staging-Config `playwright.1256-s8d` listet jetzt `Total: 5 tests in 2 files` (vorher 6). `E2E_MIN_SPECS` bleibt 72 (`grep -c '^e2e/'`), `E2E_MIN_EXECUTED_HAUPT` neu gemessen: `Total: 609 tests in 72 files` (vorher 607; +2 = AN-15 je kind).

**HL-4 neu gefasst** (ersetzt „HL-4 Stat-Schrift mobil kleiner als Desktop" in „Fälle" und den offenen Punkt in Known Limitations): HL-4 je kind — mobile Stats kompakt: je Stat **einzeilig inline** (Label rechts neben der Zahl, gleiche Unterkante ± 3 px, Höhe ≤ 28 px), Label ≥ 11 px (#2601), Abstand zwischen zwei Stats **20 px mobil** und **24 px Desktop**. Die Schriftgröße ist kein Messpunkt mehr (`Stat.svelte` hält sie in jeder Größe, siehe Known Limitations).

**Nebenbefund für Sammel-Issue #1199 (keine Änderung in dieser Scheibe):** Die Trip-Liste zeigt mobil **4** Stats (inkl. „Abgeschlossen"); die Trip-Zeile bricht bei 390 px auf zwei Reihen um (Höhe der Stats-Zeile 84 px gegenüber 42 px im Vergleich, der in einer Reihe bleibt). HL-4 misst je Stat und nur Lücken zwischen Stats derselben Reihe (gleiche Oberkante ± 1 px, `hub-liste-seitenrahmen.spec.ts` `statZeile`) und bleibt davon unberührt (statisch am Testcode geprüft).

## Expected Behavior

- **Input:** CI-Lauf `e2e` gegen den isolierten Stack; Unit-Läufe des Wächters, der Ratschen-Bindung und des Struktur-Tests.
- **Output:** Anlegen, Listenrahmen, Redirect, Bestandsfelder, Kanal-Schwellen und Hub-Navigation werden für Trip UND Ortsvergleich von denselben Specs geprüft und von der CI bewacht. Compare-eigene Restspecs tragen einen Kopf mit wahrer Begründung. `ALTLAST` ist leer, `ALTLAST_MAX` ist 0.
- **Side effects:** Wegwerf-Daten `E2E-GZ-…` (Aufräumen im `finally`, Sicherheitsnetz `global.teardown.ts`); keine Registrierung, kein Versand.

## Test Plan

### Automated Tests (TDD RED)

- [ ] Test 1: GIVEN die Anlege-Seite je kind WHEN Pflichtangaben gemacht werden THEN gelten Sperre, Fortschritt, Profil, Weiter-Knopf und Abschluss-Gate gleich (AN-1 bis AN-5).
- [ ] Test 2: GIVEN ein voller Durchlauf WHEN angelegt wird THEN genau ein POST, vollständig, Roundtrip, Landung im neuen Hub (AN-6, AN-7, AN-8).
- [ ] Test 3: GIVEN mobil WHEN durch die Anlege-Seite geklickt wird THEN stimmen CTA, Footer, Kopf, Alarm-Stufe und es gibt keinen `pageerror` (AN-9 bis AN-11); vergleich-Zweig AN-12.
- [ ] Test 4: GIVEN die Listenseite je kind THEN Kopf, Intro, Suche, Stats, Padding (HL-1 bis HL-5).
- [ ] Test 5: GIVEN die Hub-Ergänzungen THEN LM-1b, LM-10b, LM-11 bis LM-13, KA-10/11, HT-11/12, KB-11, AW-3c, AW-5b, XU-3 und `?tab=layout` grün.
- [ ] Test 6: GIVEN der Wächter WHEN er läuft THEN ist `ALTLAST` leer und `ALTLAST_MAX` 0, alle Köpfe ≥ 15 Zeichen.
- [ ] Test 7: GIVEN die Positivliste WHEN der Bindungstest läuft THEN entspricht `E2E_MIN_SPECS` der Listenlänge und jede Zeile zeigt auf eine vorhandene Datei.
- [ ] Test 8: GIVEN der Struktur-Test WHEN er läuft THEN ist er grün ohne die gelöschten Dateien.

## Acceptance Criteria

- **AC-1:** Given ein Wegwerf-Trip und ein Wegwerf-Ortsvergleich / When das nackte `/<kind>/{id}/edit` aufgerufen wird / Then führt der Aufruf auf `/<kind>/{id}`, `/edit` steht nicht mehr in der Adresse, die Reiterleiste ist sichtbar und kein Anlege-Editor wird gerendert — für Trip UND Ortsvergleich (`?tab=` wird bewusst nicht geprüft: nur der Trip reicht es durch). _[G1, Redirect]_
  - Test: `hub-list-menu.spec.ts` (LM-1b, 2 Fälle); Trip zusätzlich `issue-616-trip-one-surface.spec.ts` AC-2.
  - Mutation: Redirect-Route rendert den Alt-Editor oder bleibt auf `/edit` → LM-1b des kind rot.
- **AC-2:** Given ein aktiver, ein pausierter und ein Entwurfs-Eintrag je kind / When das mobile Blatt bzw. der Hub-Kebab geöffnet und „Archivieren" im Hub-Kebab gewählt wird / Then zeigt das Blatt des aktiven Eintrags „Pausieren" und kein „Bearbeiten", der Entwurf hat im Kebab kein „Bearbeiten" (beim Vergleich zusätzlich den Knopf „Setup abschließen"), und „Archivieren" setzt per `PATCH …/state` den Status und nimmt den Eintrag aus der aktiven Liste (unter `/archiv` auffindbar) — für Trip UND Ortsvergleich. _[G1, Aktionsblätter]_
  - Test: `hub-list-menu.spec.ts` (LM-10b, LM-11, LM-12, 6 Fälle).
  - Mutation: „Bearbeiten" wieder ins Blatt aufnehmen → LM-11/LM-12 rot; Archivieren im Hub-Kebab löst keinen `PATCH` aus → LM-10b rot.
- **AC-3:** Given je ein Hub und die Liste / When auf Desktop eine Zeile angeklickt, der Breadcrumb angeklickt, mobil der Zurück-Pfeil getippt, ein Reiter A → B → A gewechselt und der Übersichts-Sprungknopf („Bearbeiten →" bzw. „Im Editor öffnen →") betätigt wird / Then öffnet die Zeile den Hub, Breadcrumb und Pfeil führen zur Liste, der Inhalt von A ist nach der Rückkehr wiederhergestellt und der Sprungknopf wechselt den Reiter inline (die Adresse ändert `tab`, keine volle Navigation) — für Trip UND Ortsvergleich. _[G1, Navigation]_
  - Test: `hub-list-menu.spec.ts` (LM-13), `hub-kopf-aufbau.spec.ts` (KA-10, KA-11), `hub-tab-bar.spec.ts` (HT-11, HT-12), je 2 Fälle.
  - Mutation: Breadcrumb verlinkt ins Leere → KA-10 rot; Sprungknopf ruft `goto` statt Reiterwechsel → HT-12 rot.
- **AC-4:** Given ein Trip und ein Ortsvergleich mit nicht-default Bestandsfeldern (Vergleich `hour_from` 10, `hour_to` 14, `forecast_hours` 72, `empfaenger`; Trip `weather_config`, `report_config`, `display_config`, `avalanche_regions`, `aggregation`, Etappenzahl) / When der Name zweimal nacheinander im Kopf geändert wird / Then trägt der Server-Stand den neuen Namen und **alle** Bestandsfelder bitgleich, auch nach dem zweiten Speichern — für Trip UND Ortsvergleich. Der Seed setzt die Felder tatsächlich auf Nicht-Default-Werte (Vorbedingung per `expect` geprüft), sonst wäre ein Nullen unsichtbar. _[G1, Bestandsfelder]_
  - Test: `hub-kopf-bearbeiten.spec.ts` (KB-11, 2 Fälle).
  - Mutation: Kopf-Speichern sendet das Vollobjekt ohne die Bestandsfelder (Go schreibt 0) → KB-11 des kind rot; zweiter Speichervorgang nullt `hour_from` → KB-11 (vergleich) rot.
- **AC-5:** Given ein Trip-Hub und ein Vergleichs-Hub / When `?tab=layout` aufgerufen wird / Then landet der Hub im Reiter Wetter-Metriken, die Adresse wird auf `?tab=wetter-metriken` bereinigt und es gibt kein Layout-Panel. _[G1, Alt-Kennung `layout`]_
  - Test: `hub-reiter-alt-kennungen-umleitung.spec.ts` (neuer Test je `HUBS`-Eintrag, 2 Fälle).
  - Mutation: `LEGACY.layout` entfernen → beide Fälle rot (Rest-Fallback Übersicht).
- **AC-6:** Given je ein Trip und ein Ortsvergleich / When alle drei Kanal-Schwellen nacheinander geändert werden, auch per schnellem Doppelklick auf zwei verschiedene Stufen, und danach der Name geändert wird / Then zeigt der Reload genau die zuletzt gesetzten Werte (Endzustand konsistent) und die Schwelle bleibt nach der Namensänderung erhalten — für Trip UND Ortsvergleich. _[G1, Kanal-Schwellen]_
  - Test: `hub-alarme-wertprops.spec.ts` (AW-3c, AW-5b, 4 Fälle).
  - Mutation: Schwellen-Speichern überschreibt die beiden anderen Kanäle → AW-3c rot; Kopf-PUT sendet Alt-Baseline → AW-5b rot.
- **AC-7:** Given die Anlege-Seite von Trip (`/trips/new`) und Vergleich (`/compare/new`) / When sie leer geöffnet und die Pflichtangaben gemacht werden (Trip: Name, Startdatum, GPX je Etappe; Vergleich: Name) / Then ist der 2. Schritt zuerst gesperrt (Klick wechselt nicht) und danach frei, der 1. Schritt „done", der Fortschritt zeigt 5 Segmente und steigt, die Profil-/Aktivitätswahl bleibt nach Reiterwechsel erhalten und der Weiter-Knopf führt in den Punkte-Schritt (Etappen/Orte) — für Trip UND Ortsvergleich. _[G4, Anlegen: Gerüst]_
  - Test: `hub-anlegen-ablauf.spec.ts` (AN-1 bis AN-4, 8 Fälle).
  - Mutation (je kind): Sperre entfernen → AN-1 rot; Schrittzahl in `anlegeKette` ändern → AN-2 rot; Profilwahl beim Reiterwechsel zurücksetzen → AN-3 rot.
- **AC-8:** Given die Anlege-Seite je kind / When noch nicht alle Pflichtschritte (bis Alarme) besucht sind / Then ist der Abschluss-Knopf („Speichern" bzw. „Briefing aktivieren") gesperrt, mit Hinweistext, und nach dem Besuch aktiv — für Trip UND Ortsvergleich. _[G4, Anlegen: Abschluss-Gate]_
  - Test: `hub-anlegen-ablauf.spec.ts` (AN-5, 2 Fälle).
  - Mutation: `canFinish` liefert immer `true` → AN-5 beider kinds rot.
- **AC-9:** Given eine Anlege-Seite mit echten Auswahlen (Metrik umschalten, Wertebereiche, Alarm-Stufe, beim Vergleich Orte und Stundenverlauf-Metrik) / When angelegt wird, einmal normal und einmal per Doppelklick / Then geht genau **ein** POST hinaus (beim Trip mit clientseitig erzeugter `id`, die der Antwort entspricht und vorher nicht existierte; beim Vergleich ohne `id`), der Körper trägt jede Auswahl, die Seite landet im Hub des **neuen** Objekts, der GET-Roundtrip und die Anzeige zeigen jeden Wert und die Stufe, es entsteht genau ein Objekt, und „Abbrechen" führt zur Liste ohne POST — für Trip UND Ortsvergleich. _[G4, Anlegen: voller Durchlauf]_
  - Test: `hub-anlegen-ablauf.spec.ts` (AN-6, AN-7, AN-8, 6 Fälle).
  - Mutation: Auswahl fehlt im POST-Körper → AN-6 rot; Guard `saving`/`savedTripId` entfernen → AN-7 des kind rot; Abbrechen sendet POST → AN-8 rot.
- **AC-10:** Given 390×844 / When die Anlege-Seite durchlaufen wird / Then wechselt die Beschriftung der CTA je Schritt, der Abschluss steht erst im letzten Schritt im Sticky-Footer, es gibt genau einen Seitenkopf, Zurück führt zur Liste, der Titel wechselt mit dem Schritt, Alarme ist der letzte Schritt, und die Stufen-Auswahl steht auf „gering" ohne gesetzten Wert im späteren POST — für Trip UND Ortsvergleich. _[G4, Anlegen: mobil]_
  - Test: `hub-anlegen-ablauf.spec.ts` (AN-9, AN-10, 4 Fälle).
  - Mutation: zweiter Kopf im mobilen Editor → AN-9 rot; Startwert der Stufe auf „hoch" → AN-10 rot.
- **AC-11:** Given echte Orte bzw. Etappen / When alle fünf Schritte nacheinander geöffnet werden / Then tritt kein `pageerror` auf — für Trip UND Ortsvergleich; beim Vergleich zusätzlich zeigt der Schritt Wetter-Metriken den Stundenverlauf-Schalter, keine Layout-Attrappe (`channel-tab-email`, `compare-step4-layout-preview` count 0) und Temperatur Höchst- und Tiefstwert als je genau eine eigene Zeile (Kind-Kontrast: Vergleichs-Katalog bzw. `COMPARE_ONLY_SECTIONS`). _[G4, Anlegen: Absturzfreiheit und Vergleichs-Eigenheit]_
  - Test: `hub-anlegen-ablauf.spec.ts` (AN-11 2 Fälle, AN-12 1 Fall).
  - Mutation: ein Render-Fehler in einem Schritt (`rows[0].feels` ohne Schutz) → AN-11 rot; Attrappe wieder einblenden → AN-12 rot.
- **AC-12:** Given die Liste von Trips und Ortsvergleichen / When sie mobil und auf Desktop geöffnet wird / Then zeigt mobil der Seitenkopf Titel und „Neu"-Knopf (führt zur Anlege-Seite), der Intro-Satz ist mobil kurz und auf Desktop lang, die Suche ist mobil unsichtbar und auf Desktop sichtbar und filtert, die Stat-Schrift ist mobil kleiner, es gibt keinen horizontalen Überlauf und die erste Karte steht 12–20 px vom Rand — Texte je kind aus `LISTE_SEL`, Aussagen gleich. _[G3, Listenrahmen]_
  - Test: `hub-liste-seitenrahmen.spec.ts` (HL-1 bis HL-5, 10 Fälle).
  - Mutation: Suche auch mobil zeigen → HL-3 rot; Overflow durch festes Breitenmaß → HL-5 rot.
- **AC-13:** Given zwei verschiedene Nutzer / When Nutzer A einen Trip und einen Vergleich anlegt (POST, echte `user_id` aus der Sitzung, kein Fallback `default`) / Then liefert `GET` des Objekts bei Nutzer B 404 und es steht nicht in B's Liste; bestehende Abdeckung bleibt: `hub-editor-autosave-user-isolation` UI-1, `hub-cross-user-write-block` AC-2, `compare-new-vorlage` AC-6, `standardwerte-und-hilfe` AC-11. Es wird **keine** zusätzliche Registrierung angelegt (Bremse 5/h/IP): XU-3 nutzt den Zweitnutzer, den `hub-cross-user-write-block` bereits erzeugt. _[G1/G4, Mandantentrennung beim Anlegen]_
  - Test: `hub-cross-user-write-block.spec.ts` (XU-3, 2 Fälle).
  - Mutation: Cross-GET liefert das Objekt (Mandantenfilter entfernt) → XU-3 des kind rot.
- **AC-14:** Given grüne Zielfälle aus AC-1 bis AC-13 / When `compare-alarm-config`, `compare-detail-edit-entry`, `compare-edit-redirect`, `compare-editor-slice1`, `compare-editor-slice4`, `compare-legacy-fields-survive-save`, `feat-1461-s3b2b-compare-kanal-schwelle`, `issue-1093-compare-layout-crash` und `trip-edit` gelöscht werden / Then stehen im **selben** Commit je Datei: Setup/Config (`compare-edit-redirect.staging.setup.ts`, `playwright.1273-s3.red.config.ts`, `feat-1461-s3b2b.staging.setup.ts`, `playwright.1461-s3b2b.staging.config.ts`, `issue-1093.staging.setup.ts`, `playwright.1093.staging.config.ts`), der Eintrag in `MIGRATED_FILES` und in `playwright.1273-s4c.staging.config.ts` (`compare-alarm-config`, `compare-legacy-fields-survive-save`), der Wächter-Eintrag und die Positivlisten-Zeile (Z. 468/469/472); jede Zeile der Zuordnungstabellen ist durch einen **laufenden** Fall belegt, jeder dort als „Rumpf nur per Titel gelesen" markierte Altfall ist in /50 gegen seinen Rumpf abgeglichen (Abweichung ⇒ Zusatzfall, nicht Löschen). `issue-1093-unit.spec.ts`, `playwright.1093.unit.config.ts` und Positivlisten-Zeile 504 bleiben. _[G2, Löschungen im selben Commit]_
  - Test: `tests/tdd/test_compare_e2e_storagestate_migration.py`, Wächter, `test_e2e_positivliste_ratschen_bindung.py` (benannte Dateien); Zuordnungs-Abgleich im Adversary-Protokoll.
  - Mutation: gelöschten Namen in `MIGRATED_FILES` lassen → Struktur-Test rot; Setup stehen lassen, das eine gelöschte Spec startet → Config-/Existenzprüfung rot.
- **AC-15:** Given `compare-new-vorlage`, `issue-1080-compare-new-url`, `compare-layout-tab-dissolution`, `compare-flow-navigation`, `compare-editor-fidelity-s8d`, `compare-hub-fidelity-s8c` / When der Wächter läuft / Then trägt jede Datei in den ersten 30 Zeilen `gz-eigenstaendig:` mit einer Begründung ≥ 15 Zeichen, die laut Tabelle „Köpfe" wahr ist und das benannte Pendant nennt; die Dateien enthalten nur noch die Fälle aus „Bleibt" (alle übrigen sind laut Zuordnung an einen laufenden Zielfall gewandert oder mit Beleg gelöscht); `compare-new-vorlage` und `issue-1080` bleiben fallgleich. Die zugehörigen Configs (`playwright.1080.staging.config.ts`, `1256-s2`, `1256-s8c`, `1256-s8d`, `compare-layout-tab-dissolution`) und Setups bleiben und zeigen auf vorhandene Dateien. _[G3, Köpfe und Kürzungen]_
  - Test: Wächter (benannte Datei); `--list` je Datei gegen „Bleibt".
  - Mutation: Kopf entfernen → Wächter rot (Regel 1); Begründung auf < 15 Zeichen kürzen → rot („Zeichen Begruendung").
- **AC-16:** Given der Paritäts-Wächter / When der Unit-Test läuft / Then ist `ALTLAST` leer, `ALTLAST_MAX` das Literal 0 (gleich `len(ALTLAST)`), der Kommentarblock nennt S4, `test_echter_baum_ist_nicht_leer` bleibt bei ≥ 10 und ist erfüllt (19 Dateien mit „compare" im Namen), und die Selbsttests sind grün. _[G6, Wächter]_
  - Test: `tests/unit/test_e2e_compare_paritaet_waechter.py` (benannte Datei).
  - Mutation: einen gelöschten Namen in `ALTLAST` lassen → „zeigt auf keine Datei mehr" rot; eine Kopf-Datei in `ALTLAST` lassen → „inzwischen konform" rot; `ALTLAST_MAX` auf 14 lassen → rot.
- **AC-17:** Given die CI-Ampel / When die Ratsche geprüft wird / Then enthält `.github/ci_e2e_specs.txt` `hub-anlegen-ablauf` und `hub-liste-seitenrahmen`, nicht mehr `compare-detail-edit-entry`, `compare-editor-slice1`, `compare-legacy-fields-survive-save`, aber weiterhin `issue-1093-unit`; `E2E_MIN_SPECS` entspricht **exakt** `grep -c '^e2e/' .github/ci_e2e_specs.txt` (erwartet 72, nicht errechnet), `E2E_MIN_EXECUTED_HAUPT` ist der am Endstand per `npx playwright test --list` über die Hauptlauf-Auswahl gemessene Wert (nie addiert) mit fortgeschriebener Begründung, `gates_und_ratschen.md:232` nennt die gemessenen Werte, jede Listenzeile zeigt auf eine vorhandene Datei. _[G6, Ratsche]_
  - Test: `tests/unit/test_e2e_positivliste_ratschen_bindung.py`, CI-Job `e2e` (`e2e_gate.py`).
  - Mutation: Zeile auf nicht existierende Datei → Existenzprüfung rot; `E2E_MIN_SPECS` um 1 verfälschen → Kern-Test rot; `E2E_MIN_EXECUTED_HAUPT` um 1 verändern → `e2e_gate.py` rot.
- **AC-18:** Given alle gelöschten Dateien / When `grep -rn` über `frontend`, `.github`, `tests`, `scripts` nach den neun gelöschten Spec-Namen und den sechs gelöschten Setup-/Config-Namen läuft / Then bleibt kein Treffer außer Historie in `docs/` und in der Positivlisten-Historie; jede Fundstelle, die die Datei liest oder importiert (`read_text`, `readFileSync`, Import), ist im selben Commit angepasst, Kommentar-Zeiger sind auf die ersetzenden Specs umgehängt, nicht gelöscht. Kein überlebender Config nutzt ein gelöschtes Setup. _[G6, Verweis-Hygiene]_
  - Test: `grep`-Prüfung im Adversary-Protokoll; Struktur-Tests (AC-14, AC-16, AC-17).
  - Mutation: einen Zeiger auf eine gelöschte Datei in einer Positivlisten-Zeile lassen → Existenzprüfung rot.
- **AC-19:** Given `hub-anlegen-ablauf`, `hub-liste-seitenrahmen` und die erweiterten Specs / When sie im Zielverbund (Hauptlauf ohne `bug-703`) dreimal hintereinander laufen / Then sind alle drei Läufe grün (Filter B, im Aufnahme-Kommentar belegt); die Specs enthalten kein `waitForTimeout`, kein `skip`/`test.fixme`, kein `page.screenshot({path})`, keinen Hauptrepo-Pfad, kein `__dirname`, keinen festen `storageState`-Pfad, kein UI-`login()`; jeder Fall räumt sein Objekt auf (`finally`), `global.teardown.ts` meldet keinen Restbestand `E2E-GZ-`. _[Qualität der neuen und erweiterten Specs]_
  - Test: Filter B (3 Zyklen) + `grep -c "waitForTimeout\|\.skip(\|test\.fixme\|__dirname"` über die neuen Dateien = 0.
  - Mutation: `waitForTimeout` einfügen → Filter-A-Prüfung rot; `finally`-Aufräumen entfernen → Folgefall scheitert (Rest `E2E-GZ-`).
- **AC-20:** Given ein Fall der neuen oder erweiterten Specs wird für den Trip rot, obwohl er für den Ortsvergleich grün ist (oder umgekehrt) / When die Ursache untersucht wird / Then wird die Produktlücke im **selben** Ticket behoben und der Test bleibt streng; Abschwächen, `test.skip`, ein kind-Zweig, der nur eine Art prüft, oder ein „bekannte Abweichung"-Vermerk sind unzulässig, **außer** der Unterschied ist als echte Compare-Eigenheit in „Kind-Kontraste" mit Fundstelle belegt. Berührte Produktdateien werden in diese Spec nachgetragen. Vorgemerkte Messpunkte: Reiter-Zustand und Fortschritt der Trip-Anlege-Seite (rein attributive Ergänzung in `TripNewEditor.svelte`, falls Rolle/ARIA nicht reicht), GPX-Durchlauf bis zum Abschluss, Trip-Listenseite (HL), Alarm-Stufe im Trip-Anlegen (AN-10), Trip-Entwurfs-Kebab (LM-12). Strukturelle Unterschiede der Hub-Übersicht (Befund 6) sind ausdrücklich **nicht** Teil dieser Regel, sondern Nebenbefund an #1199. _[Produktlücke im selben Ticket]_
  - Test: Prozess-AC; Beleg im Adversary-Protokoll („rot beim Zusammenführen: ja/nein, wenn ja: Fix-Commit").
  - Mutation: keine (Regel).
- **AC-21:** Given jedes neue oder zusammengeführte Verhalten aus AC-1 bis AC-13 / When die Implementierung gezielt verfälscht wird (Sicherungskopie extern, nur String-Ersetzung, nie `git checkout/stash/reset`) / Then wird für **jedes** Verhalten und **beide** kinds der jeweils betroffene Fall rot, protokolliert wird, **welcher** Test rot wurde; eine Verfälschung, die kein Test fängt, ist ein Finding; eine kind-spezifische Verfälschung macht nur den Fall dieser Art rot. Zusätzlich die Ausfallprobe der Zuordnung: ein weggelassener Zielfall wird vom `--list`-Abgleich gemeldet (neue Fälle: AN 23 + HL 10 + LM 10 + KA 4 + HT 4 + KB 2 + AW 4 + XU 2 + Alt-Kennung 2 = 61 gegen die Zuordnungstabellen), und keine Altdatei wird vor dem grünen Lauf ihres Zielfalls gelöscht. _[Mutations-Gegenprobe, übergreifend]_
  - Test: Adversary-Dialog in /50 (Familien: Sperre/Gate, POST-Körper, Doppelklick-Guard, Redirect, Bestandsfelder, Schwellen, Navigation, Mandantenfilter, Selektor je kind).
  - Mutation: siehe die Mutationszeilen in AC-1 bis AC-13.
- **AC-22:** Given `docs/reference/gates_und_ratschen.md` / When S4 geliefert ist / Then nennt die Datei die gemessenen Schwellen, „ALTLAST leer (S4)", den Umgang mit `gz-eigenstaendig:` und den Hinweis, dass die Vergleichs-Hub-Übersicht eine dokumentierte Vergleichs-Eigenheit mit Nebenbefund #1199 ist. _[Doku]_
  - Test: `grep` im Adversary-Protokoll; `tests/test_claude_md_budget.py` bleibt grün (CLAUDE.md unverändert).
  - Mutation: veraltete Zahl 64/369 stehen lassen → manueller Abgleich rot.

## Definition of Done

- [ ] AC-1 bis AC-22 per Test und Mutations-Gegenprobe belegt (je Mutation protokolliert, welcher Test rot wurde)
- [ ] Neue/erweiterte Specs dreimal grün gegen den CI-Stack; Altdateien erst danach gelöscht
- [ ] Zuordnungstabellen vollständig gegen `--list` und Rumpf-Abgleich der Titel-gelesenen Altfälle
- [ ] Sechs Köpfe gesetzt, Begründungen gegen Fundstellen geprüft
- [ ] `ALTLAST` leer, `ALTLAST_MAX` 0, Wächter-Test grün
- [ ] `E2E_MIN_SPECS` per Zählung, `E2E_MIN_EXECUTED_HAUPT` per `--list` gemessen, Positivliste konsistent
- [ ] Struktur-Test, 1273-Config, Setups/Configs, Verweise bereinigt
- [ ] Nebenbefunde an #1199 gemeldet (toter `layoutPreviewRows.ts`, tote `/trips/new?from=`-Lade-Logik, Vergleichs-Hub-Übersicht ohne Trip-Pendant)
- [ ] CI-Ampel (6 Checks) grün, Produktcode nur wie AC-20 dokumentiert

## Known Limitations

- **Entscheidungspunkt für den Tech Lead:** Die Vergleichs-Hub-Übersicht (Summary-Karten, Chevron-Stack, Status-Kurzform, Versand-Karte) hat im Trip-Hub keinen Gegenpart (`CompareTabs.svelte` vs. `trip-detail/HubOverview.svelte`). Die Kopf-Lösung bildet den **Ist-Stand** ehrlich ab, steht aber nicht in der Liste der erlaubten Compare-Eigenheiten in `CLAUDE.md`. Das Angleichen wäre Produktarbeit außerhalb der Testschicht und ist als eigenes Ticket zu führen.
- Zielfeld und Körperform der Trip-Anlege-Fälle (GPX-Durchlauf bis zum Abschluss, Beschriftung des Hinweistexts, Trip-Entwurfs-Kebab) sind erst im RED messbar; die Spec legt die Zusicherung fest, nicht das Messergebnis.
- Die Rumpf-Abgleich-Pflicht gilt für die Titel-gelesenen Altfälle (Befund 7); ein dort gefundener Mehrbefund erzeugt einen Zusatzfall und kann die Fallzahlen in AC-21 erhöhen.
- `compare-new-vorlage` bleibt Vergleichs-eigen, solange `/trips/new?from=` tot ist (Entscheidung `feat_2277_s2c`). Wird der Trip-Pfad wiederbelebt, ist eine kind-Schleife neu zu spezifizieren.
- `issue-1093-unit.spec.ts` prüft eine Funktion ohne Produktaufrufer (`layoutPreviewRows.ts`); Löschen von Spec und Funktion ist eigener Nebenbefund.
- `E2E_MIN_EXECUTED_HAUPT` ist erst am Endstand messbar; die Erwartung für `E2E_MIN_SPECS` (72) ist nur Erwartung, verbindlich ist die Zählung.
- Staging-only-Reste (`compare-layout-tab-dissolution`, `…-s8c`, `…-s8d`, `…-flow-navigation`, `issue-1080`, `compare-new-vorlage`) laufen weiterhin nur gegen Staging; ihre Mutations-Gegenprobe ist im CI-Stack nicht prüfbar.
- **Offen (Phase 6, AC-20): AN-6 (route) „Wertebereiche fehlen im POST".** Der Vergleich belegt Wertebereiche beim frischen Anlegen aus dem Aktivitätsprofil vor (`CorridorEditor` `isFreshCompareCreate` ⇒ `buildComparePrefillRows` aus `PROFILE_METRICS_WITH_SCALES`/`IDEAL_DEFAULTS`, Vergleichs-Metrik-Kennungen). Für den Trip gibt es keine solche Quelle: `buildRoutePool` baut Zeilen nur aus vorhandenen `trip.corridors`, der Anlege-Modus meldet `onCorridorsChange` erst bei einer Nutzer-Änderung ⇒ `corridors: []`. Welche Trip-Metriken mit welchen Spannen vorbelegt werden (Abbildung Trip-Aktivität → Profil, Vergleichs- → Trip-Metrik-Kennung) ist eine Produktentscheidung und nicht erfunden worden; der Test bleibt streng.
- **Offen: HL-4 „Stat-Schrift mobil kleiner" ist für beide kinds strukturell nicht erfüllbar.** `Stat.svelte` hält das Label in jeder Größe bei 11 px (#2601) und die Inline-Zahl bei mind. 22 px; `size="sm"` ändert im Inline-Layout keine Schriftgröße. Das betrifft den Vergleich genauso (keine Trip-Lücke) — Zusicherung bzw. Messpunkt von HL-4 muss neu festgelegt werden.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Testschicht-Konsolidierung nach bestehender Vorgabe (Trip/Ortsvergleich-Code-Teilung, Epic #2345 P6); die einzige Produktänderung ist rein attributiv und bedingt (AC-20). Keine neue Entscheidungsfläche.

## Changelog

- 2026-10-30: Initial spec created (S4, ALTLAST leeren). Entscheidungen am Code, Abweichungen von der Analyse: `compare-new-vorlage` ⇒ Kopf (`/trips/new?from=` tot, bereits entschieden); `issue-1093-compare-layout-crash` ⇒ gelöscht, aber Zusicherung wandert nach AN-11 (Fläche lebt); `compare-layout-tab-dissolution` ⇒ nicht gelöscht, auf AC-4/AC-5 gekürzt + Kopf; `issue-1093-unit.spec.ts` bleibt (Nebenbefund); `/trips/new` und `/compare/new` haben verschiedene Selektoren, aber geteilte Reiterfolge und Gate ⇒ `ANLEGE_SEL`; `compare-edit-redirect` hat E2E-Trip-Pendant `issue-616` AC-2 (kind-Unterschied beim `?tab=`); Hub-Übersicht ist zweimal implementiert ⇒ `compare-hub-fidelity-s8c` Kopf plus Entscheidungspunkt; `test_echter_baum_ist_nicht_leer` bleibt bei ≥ 10 (Soll 19); vorbestehend rote Staging-Tests: 3 gehören zu S4, 4 nicht (#1196). ALTLAST 14 → 0, `E2E_MIN_SPECS` erwartet 72 (per Zählung), HAUPT per `--list`.
- 2026-10-30 (Phase 6, AC-20 Teil B): Trip-Produktlücken geschlossen (AN-2 Fortschritt 5 Segmente, AN-5 Hinweis, AN-9 mobiler Fuß je Schritt, HL-1..HL-3 Trip-Liste, KA-11 Trip-Hub-Zurück-Pfeil); Produktdateien und Kind-Kontraste unter „AC-20-Nachträge" (Implementation Details). Offen: AN-6 route (Wertebereiche-Vorbelegung, Produktentscheidung) und HL-4 (Stat-Schrift, beide kinds), siehe Known Limitations.
- 2026-10-30 (Phase 6, AC-20 Teil E): Trip-Lücken aus Teil D geschlossen (mobile Route-CTA `disabled`, Desktop-Weiter-Füße `trip-new-continue-wertebereiche`/`-alarme`), Race Standardwerte-Knopf ↔ Wertebereiche-Vorbelegung (`onVorbelegungFertig`); s8d AC-8 → AN-14, AC-17/AC-18 → AN-15; HL-4 neu gefasst; Nebenbefund Trip-Stats mobil (4 Stats, zwei Reihen) an #1199. Details unter „Nachträge Teil E".
