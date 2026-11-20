---
entity_id: feat_3196_trip_tempo_etappen
type: module
created: 2026-11-20
updated: 2026-11-20
status: draft
version: "1.0"
workflow: feat-3196-trip-tempo-etappen
tags: [trip, etappen, tempo, fortbewegung, gehzeit, dav, migration, i18n, epic-2791]
---

# Einstellungen neu S4b-1: Trip — Fortbewegung und Grundtempo im Reiter Etappen, Gehzeit nach DAV (#3196)

## Approval

- [ ] Approved

## Purpose

Im Trip-Kopf stehen heute Aktivitäts-Chips (Trekking, Skitour, Hochtour, Klettersteig, MTB, Fahrrad 15/20/25), die im Hintergrund das Gehtempo bestimmen. Nach ADR-0108 entfallen sie. Das Tempo bekommt seinen Platz im Reiter Etappen: eine Karte mit **Fortbewegung** (zu Fuß, Rad, MTB, Ski) und **Grundtempo** (km/h). Gleichzeitig wechselt die Gehzeit-Berechnung auf das Modell des Deutschen Alpenvereins (DIN 33466); der Aufstieg und Abstieg folgen dem Grundtempo und sind nicht mehr sichtbar. Bestandstrips werden verlustfrei übernommen.

Grundlagen: Issue #3196 (Teil von #2796, Epic #2791), ADR-0108 (wird mit dieser Spec angepasst), ADR-0101 (Read-Modify-Write), ADR-0097 (geteilter Code Trip/Orte), ADR-0095 (Kanal-Parität), ADR-0104 (zweisprachig), Analyse `docs/context/feat-3196-trip-tempo-etappen.md`, Soll-Bild `docs/context/einstellungen_neu/seiten/mockup-hub-fassung4.html` `viewEtappen()`.

## PO-Entscheidungen 2026-11-20 (verbindlich)

1. Gehzeit nach DAV (DIN 33466) statt der bisherigen Summenformel. Der PO akzeptiert bewusst, dass sich die Gehzeiten **aller** Bestandstrips einmalig ändern und damit die bewerteten Stunden je Wegpunkt.
2. Eingabe nur **Grundtempo** (eine Zahl je Trip) für alle vier Fortbewegungen; Aufstieg/Abstieg folgen im Verhältnis.
3. Wechsel der Fortbewegung setzt das Grundtempo auf den Vorschlagswert.

## ADR-0108: Anpassung (Teil dieser Lieferung)

Punkt 2 des ADR („Tempo flach und Aufstieg, Abstieg bleibt im Modell") wird ersetzt durch: „Fortbewegung und **Grundtempo**; Gehzeit nach DAV, Auf-/Abstiegsrate folgt dem Grundtempo im festen Verhältnis je Fortbewegung; je Etappe überschreibbar (nur Grundtempo, #3197)". Punkt 5 wird ergänzt: Migration erhält Fortbewegung und Grundtempo, nicht die Gehzeiten. Status wechselt von „Vorgeschlagen" auf **Angenommen** (mit dem Merge dieser Lieferung); `docs/adr/README.md` wird nachgezogen (`tests/test_adr_index_drift.py` bewacht den Index).

## Gehzeit-Modell (DAV, DIN 33466)

- `t_h = km / v` (v = Grundtempo)
- `t_v = Hm_auf / R_auf + Hm_ab / R_ab`
- `t = max(t_h, t_v) + min(t_h, t_v) / 2`
- `R = R_ref · v / v_ref` (Raten wachsen und fallen im selben Verhältnis wie das Grundtempo)

Referenzwerte je Fortbewegung (Vorschlags-Grundtempo `v_ref` · `R_ref` Aufstieg/Abstieg in Hm/h):

| Fortbewegung | Wert im Feld | Vorschlag km/h | R_ref auf | R_ref ab |
|---|---|---|---|---|
| zu Fuß | `fuss` | 4 | 300 | 500 |
| Rad | `rad` | 20 | 600 | 1000 |
| MTB | `mtb` | 12 | 500 | 1000 |
| Ski | `ski` | 3 | 300 | 1500 |

Die Konstanten haben **eine Quelle in Go** (`internal/model/naismith.go`), sind in Python (`src/core/naismith.py`) und TypeScript (`frontend/src/lib/utils/naismith.ts`) gespiegelt und werden durch eine gemeinsame JSON-Falltabelle bewacht, die alle drei Rechner lesen (siehe Tests).

## Datenmodell

- Neues Trip-Feld `tempo = {fortbewegung: "fuss"|"rad"|"mtb"|"ski", grundtempo_kmh: number}`. Kein Feld je Etappe (Override je Etappe ist #3197, dort nur `grundtempo_kmh`).
- `activity` bleibt als **Altfeld auf der Platte** (ADR-0101, Rollback, Mischbetrieb); die Oberfläche schreibt es nicht mehr.
- **Lazy-Ableitung beim Lesen**, wenn `tempo` fehlt (Go `normalizeTrip`, Python Loader): `fahrrad_15/20/25` wird `rad` mit 15/20/25 km/h; alles andere (leer, `wandern`, `hiking`, `trekking`, `hochtour`, `klettersteig`, `skitour`, `mtb`) wird `fuss` mit 4 km/h. Die Migration setzt nie `mtb` oder `ski`.
- Einzige Auflösungsstellen: `ResolveTempo(trip)` (Go), `tempo_speeds(trip)` (Python), `tripTempo(trip)` (TS). Sie liefern Grundtempo und die daraus folgenden Raten.

## Source

| Datei | Änderung |
|---|---|
| `internal/model/trip.go` | MODIFY: Feld `Tempo` am Trip (sonst verwirft Go es) |
| `internal/model/naismith.go` | MODIFY: Konstanten, `ResolveTempo`, Ableitung aus `activity`, DAV-Formel in `ComputeStageArrivals` |
| `internal/store/trip.go` | MODIFY: Lazy-Ableitung in `normalizeTrip`, `SaveTrip` rechnet mit Tempo |
| `internal/handler/trip.go` | MODIFY: Optional-Merge des Feldes `tempo` im Etappen-PUT |
| `src/app/trip.py`, `src/app/loader.py` | MODIFY: Modell, Laden/Schreiben, Whitelist, Lazy-Ableitung |
| `src/core/naismith.py`, `src/services/trip_segments.py`, `src/services/stage_weather.py` | MODIFY: `tempo_speeds`, DAV-Formel, Tempo im Scoped-Trip mitgeben |
| `scripts/migrate_3196_trip_tempo.py` | CREATE: Eager-Migration nach Muster `migrate_2794` |
| `tests/fixtures/naismith_dav_paritaet.json` | CREATE: gemeinsame Falltabelle für Go, Python, TS |
| `frontend/src/lib/types.ts`, `frontend/src/lib/utils/naismith.ts` | MODIFY: Typ `Tempo`, DAV-Rechner |
| `frontend/src/lib/components/shared/TempoKarte.svelte` | CREATE: Karte Fortbewegung + Grundtempo (geteilt: Anlegen und Bearbeiten nutzen dieselbe Komponente) |
| `EditStagesPanelNew.svelte`, `EditStagesSection.svelte`, `etappenListe.ts`, `mobile/StageCardM.svelte`, `trip-detail/TripTabs.svelte` | MODIFY: Tempo statt `activityType`, Kopf-Text |
| `frontend/src/lib/components/trip-detail/TripHeader.svelte` | MODIFY: Aktivitäts-Chips (Desktop und mobil) entfallen, `profile` an `SubscriptionHeader` entfällt |
| `frontend/src/lib/components/trip-new/TripNewEditor.svelte`, `tripNewLogic.ts` | MODIFY: Aktivitäts-Dropdown wird durch `TempoKarte` ersetzt, Default `fuss` 4 |
| `frontend/src/lib/components/shared/WeatherMetricsTab.svelte`, `wizardHelpers.ts` | MODIFY: Vorlagen-Vorbelegung hängt an `fortbewegung` |
| `frontend/src/lib/i18n/messages/{de,en}/trip.json`, `docs/reference/i18n_glossar.md` | MODIFY: Texte und Glossar (Fortbewegung = Mode of travel, Grundtempo = Base pace) |
| `docs/adr/0108-vorlage-und-tempo-getrennt.md`, `docs/adr/README.md` | MODIFY: Anpassung Punkt 2/5, Status Angenommen |

Schichten: Frontend (`frontend/src`), Go-API (`internal`), Python-Core (`src`). Trip/Orte-Teilung: Die Karte hat kein Orts-Pendant (Tempo gibt es nur für Trips), ist aber als eine Komponente für Anlegen und Bearbeiten gebaut (Anlegen = Bearbeiten).

## Estimated Scope

- **LoC:** produktiv +450..550 / −150, ca. 25 produktive und ca. 25 Test-Dateien
- **Files:** ca. 50
- **Effort:** high (Risiko mittel-hoch: `arrival_calculated` bestimmt bewertete Stunden und Alarme)
- Umsetzung in **einem Workflow, zwei Commits** (1: Backend + Migration + Paritätstabelle; 2: Frontend), **ein Deploy** (vermeidet den Mischstand „Frontend schreibt `tempo`, Go verwirft es"). Scope für den Deploy: full-stack.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| ADR-0108 | adr | Entscheidung, wird angepasst und angenommen |
| #3197 | issue | Folge: Tempo je Etappe überschreiben (nicht hier) |
| #3198 | issue | Folge: Anlege-Kette Orts-Vergleich (nicht hier) |
| `internal/store/trip.go` SaveTrip | go | speichert `arrival_calculated` zentral |
| `src/app/loader.py`, `src/services/trip_segments.py` | python | rechnen Ankunftszeiten nach (Selbstheilung) |
| Risk Engine, Renderer, Alarme | python | lesen `arrival_calculated` (bewertete Stunden je Wegpunkt) |
| `scripts/migrate_2794_preset_horizons.py` | script | Muster für planen, sichern, `--execute` |
| ADR-0101 | adr | Read-Modify-Write mit Merge |

## Implementation Details

### Backend (Commit 1)

- Go rechnet gespeicherte Ankunftszeiten mit `ResolveTempo` und der DAV-Formel; Python und TS rechnen identisch. Die Falltabelle `tests/fixtures/naismith_dav_paritaet.json` (Fortbewegung, Grundtempo, km, Hm auf/ab, erwartete Minuten) wird von allen drei Rechnern gelesen.
- Der bestehende Etappen-PUT erhält `Optional[Tempo]`: fehlt das Feld, bleibt `tempo` unverändert; ist es gesetzt, wird nur dieses Feld überschrieben (Read-Modify-Write mit Merge). Nach dem Speichern werden `arrival_calculated` aller Etappen neu berechnet. Ungültige Werte (unbekannte Fortbewegung, Grundtempo ≤ 0 oder unplausibel groß) werden mit 422 abgelehnt.
- Python-Schreibpfade, die `tempo` nicht kennen, dürfen es nicht verlieren: die Loader-Whitelist nimmt `tempo` auf; fehlt es dennoch, greift die Lazy-Ableitung aus `activity`.
- `scripts/migrate_3196_trip_tempo.py`: planen (Trockenlauf mit Tabelle je Trip: alt → neu), sichern (Kopie der Dateien), `--execute` schreibt `tempo` per Read-Modify-Write mit Merge. `activity` und alle anderen Felder bleiben unverändert. Mehrfachlauf ändert nichts (idempotent). Ausführung nach dem Prod-Deploy; Hook `data_schema_backup.py` greift bei den Schema-Dateien.
- Schema-Drift-Wächter (`internal/model/trip_schema_drift_test.go`, `tests/test_trip_schema_drift.py`) werden um `tempo` erweitert.

### Frontend (Commit 2)

- `TempoKarte` oben im Reiter Etappen: vier Auswahl-Chips für die Fortbewegung, daneben ein Zahlenfeld „Grundtempo (km/h)". Hinweis darunter: „Gilt für alle Etappen." (Der Zusatz „je Etappe überschreibbar" kommt erst mit #3197, damit der Text jetzt nicht lügt.) Der Kopf der Seite lautet „Etappen & Wegpunkte — Das Tempo bestimmt die Gehzeiten und damit, welche Stunden je Wegpunkt bewertet werden." Aufstieg und Abstieg sind nirgends sichtbar.
- Wechsel der Fortbewegung setzt das Grundtempo auf den Vorschlagswert der Tabelle. Änderung von Fortbewegung oder Grundtempo wird zusammen mit den Etappen über den bestehenden Autosave- und ETag-Pfad gespeichert; die Gehzeiten je Etappe (Liste, Mobilkarte) werden sofort mit dem DAV-Rechner neu angezeigt.
- Aktivitäts-Chips in `TripHeader` (Desktop und mobil) entfallen ersatzlos; die Kopf-Parität Trip/Orte bleibt gewahrt (`hub_kopf_seiten_paritaet`).
- Anlegen: Das Aktivitäts-Dropdown wird durch dieselbe `TempoKarte` ersetzt; neuer Trip startet mit `fuss` 4. Die Vorlagen-Vorbelegung (`ACTIVITY_TO_TEMPLATE`, `mapActivityToProfile`) hängt an der Fortbewegung (`fuss` → Wandern/Alpen-Trekking-Vorbelegung wie bisher für Trekking, `rad` → Radtour, `ski` → Skitouren, `mtb` → Radtour).
- Alle neuen Nutzertexte nur über den Katalog (DE/EN); Protokoll-Token werden nicht übersetzt.
- Umsetzung der Karte (ADR-0108): Die Inhalte liegen im Organismus `frontend/src/lib/components/organisms/tempo-karte/TempoKarteInhalt.svelte` (neu); `shared/TempoKarte.svelte` ist nur die Hülle, die Anlegen und Bearbeiten gemeinsam nutzen.
- Die Vorlagen-Zuordnung (Fortbewegung → Vorlage) liegt in `shared/WeatherMetricsTab.svelte` (Konstante `FORTBEWEGUNG_TO_TEMPLATE`, Vorbelegung im Anlegen-Modus), nicht in `wizardHelpers.ts`.

## Test Plan

### Automated Tests (TDD RED, Kern-Schicht ohne Mocks)

- [ ] Go: DAV-Formel je Fortbewegung gegen die Falltabelle (`ComputeStageArrivals`), inkl. Rechenbeispiel 8 km/↑600/↓600/4 km/h = 252 min
- [ ] Python: `tempo_speeds` und DAV-Rechner gegen dieselbe Falltabelle
- [ ] TS (`node --test`): `naismith.ts` gegen dieselbe Falltabelle; Rad hat 600/1000 (Drift behoben)
- [ ] Go und Python: Lazy-Ableitung aller Altwerte (`fahrrad_15/20/25`, leer, `wandern`, `hiking`, `trekking`, `hochtour`, `klettersteig`, `skitour`, `mtb`)
- [ ] Go: Etappen-PUT mit `tempo` merged nur dieses Feld, andere Felder bleiben; PUT ohne `tempo` lässt es unverändert; ungültige Werte werden abgelehnt
- [ ] Go: Zwei-Nutzer-Test, Nutzer A ändert `tempo`, Nutzer B sieht seinen Trip unverändert und kann den Trip von A nicht ändern
- [ ] Python: Migrationsskript gegen Kopie echter Trip-Fixtures: planen schreibt nichts, `--execute` schreibt `tempo`, `activity` und alle anderen Felder bleiben, zweiter Lauf ändert nichts
- [ ] Schema-Drift (Go und Python) kennt `tempo`
- [ ] Frontend: `TempoKarte` setzt beim Wechsel den Vorschlagswert; Anlegen und Bearbeiten nutzen dieselbe Komponente
- [ ] Frontend: Katalog-Vollständigkeit DE/EN für alle neuen Schlüssel
- [ ] Wächter: kein Aktivitäts-Chip mehr in `TripHeader`

### E2E gegen Staging (`/e2e-verify`)

- [ ] Bestandstrip mit `fahrrad_20` öffnen: Reiter Etappen zeigt Rad und 20 km/h, Kopf ohne Chips
- [ ] Trip mit `hochtour` und Trip ohne Aktivität: zeigen zu Fuß und 4 km/h
- [ ] Fortbewegung wechseln, Grundtempo ändern, neu laden: Werte und Gehzeiten bleiben
- [ ] Neuen Trip anlegen mit derselben Karte; Trip-Briefing-Mail enthält die neuen Ankunftszeiten bzw. bewerteten Stunden
- [ ] Sprache EN: Karte und Kopf-Text in Englisch

### Zu ersetzende oder zu löschende Alt-Tests

- Go: `naismith_674_test.go`, `naismith_802_test.go`, `naismith_test.go`, `naismith_gemessene_strecke_test.go` (Summenformel wird durch DAV-Erwartungen ersetzt), `trip_optional_clear_test.go` (um `tempo` ergänzen)
- Python: `test_674_aktivitaetstyp_fahrrad.py`, `test_issue_802_fahrrad_segment_zeit.py` (auf DAV und `tempo` umstellen); Fixtures mit `"activity": "wandern"` bleiben gültig dank Ableitung
- Frontend: `naismith_674.test.ts`, `issue_943_activity_edit.test.ts`, `trip_kopf_aktivitaet_melden_konflikt.test.ts`, `trip_header_status_profil.test.ts` (Chips entfallen: ersetzen oder löschen), Reiter-Roundtrip-Prüfstände (`f9KatalogAnker.ts`, `f9Pruefstand.ts`, `tripMehrreiterPruefstand.ts`), `hub_kopf_seiten_paritaet.test.ts`, `subscription_header_*`
- E2E: `issue-943-activity-edit.spec.ts`, `issue-932-activity-type-route-tab.spec.ts`, `trip-hub-kopf-region-aktivitaet.spec.ts` (löschen oder auf Fortbewegungs-Karte umschreiben), `hub-kopf-*.spec.ts`, `design-system-trip-vergleich.spec.ts` (nachziehen)

## Definition of Done

Fertig ist #3196, wenn jeder Trip ein gespeichertes Tempo (Fortbewegung + Grundtempo) trägt (Bestand per Migration, alt geschriebene Trips per Ableitung beim Lesen), die drei Rechner (Go, Python, Frontend) nach dem DAV-Modell dieselben Gehzeiten liefern (Paritätstabelle grün), der Reiter Etappen und das Anlegen dieselbe Fortbewegungs-Karte zeigen, die Aktivitäts-Chips im Kopf (Desktop und mobil) fehlen, Texte DE und EN aus dem Katalog kommen, ADR-0108 angepasst und angenommen ist, die Staging-Prüfung (Zwei-Nutzer-Trennung, Ankunftszeiten, bewertete Stunden) bestanden ist und Henning ein Soll/Ist-Bild des Reiters Etappen bekommen hat.

## Acceptance Criteria

- **AC-1:** Given ein bestehender Trip mit gespeicherter Aktivität „fahrrad_20" / When der Nutzer den Reiter Etappen öffnet / Then zeigt die Karte „Fortbewegung" mit „Rad" und das Grundtempo 20 km/h, und im Trip-Kopf gibt es keine Aktivitäts-Chips mehr (weder am Desktop noch am Handy).
  - Test: E2E gegen Staging mit Bestandstrip; Kopf und Reiter werden aus Nutzersicht geprüft.

- **AC-2:** Given ein bestehender Trip mit Aktivität „hochtour" und ein Trip ganz ohne Aktivität / When der Nutzer jeweils den Reiter Etappen öffnet / Then steht bei beiden „zu Fuß" und 4 km/h; dasselbe gilt für „wandern", „trekking", „klettersteig", „skitour" und „mtb" (Altwerte werden nie zu MTB oder Ski).
  - Test: Kern-Test der Lazy-Ableitung in Go und Python über alle Altwerte plus E2E für „hochtour" und leer.

- **AC-3:** Given eine Etappe mit 8 km Länge, 600 Hm Aufstieg und 600 Hm Abstieg und Fortbewegung „zu Fuß" mit 4 km/h / When die Gehzeit berechnet wird / Then beträgt sie 4:12 Stunden nach DAV (t_h = 2:00, t_v = 3:12, max + min/2 = 3:12 + 1:00); nach dem alten Modell waren es 5:12. Dieselbe Zahl zeigen Liste, Karte und gespeicherte Ankunftszeit.
  - Test: Falltabellen-Eintrag in Go, Python und TS; E2E liest die Gehzeit der Etappe aus der Oberfläche.

- **AC-4:** Given der Nutzer steht im Reiter Etappen eines Trips mit zu Fuß und 4 km/h / When er die Fortbewegung auf Rad, danach auf MTB und auf Ski stellt / Then springt das Grundtempo jeweils auf den Vorschlagswert (20, 12, 3 km/h), und die Gehzeiten aller Etappen passen sich sofort an.
  - Test: Frontend-Komponententest der Karte und E2E mit Sichtprüfung der Zahl.

- **AC-5:** Given ein Trip mit mehreren Etappen / When der Nutzer das Grundtempo von 4 auf 5 km/h ändert und die Seite neu lädt / Then zeigt die Karte 5 km/h, alle Gehzeiten sind kürzer, und die gespeicherten Ankunftszeiten der Wegpunkte entsprechen den neuen Gehzeiten.
  - Test: E2E gegen Staging mit Neuladen; Backend-Test prüft `arrival_calculated` nach dem PUT.

- **AC-6:** Given dieselbe Strecke und dasselbe Tempo / When Go, Python und die Oberfläche die Gehzeit berechnen / Then ist das Ergebnis in allen drei identisch für alle vier Fortbewegungen, auch bei Rad (600/1000 statt der früheren Abweichung 300/500 im Frontend).
  - Test: gemeinsame JSON-Falltabelle, die Go-, Python- und TS-Test lesen; Änderung nur eines Rechners macht einen Test rot.

- **AC-7:** Given der Nutzer legt einen neuen Trip an / When er den Anlege-Dialog öffnet / Then sieht er dieselbe Karte Fortbewegung und Grundtempo wie im Reiter Etappen (vorbelegt zu Fuß, 4 km/h) und kein Aktivitäts-Dropdown; die Vorlagen-Vorbelegung im Reiter Wetter richtet sich nach der gewählten Fortbewegung.
  - Test: E2E Anlegen mit Rad, danach Prüfung von `tempo` im gespeicherten Trip und der vorbelegten Vorlage.

- **AC-8:** Given zwei verschiedene Nutzer mit je einem eigenen Trip / When Nutzer A über den Etappen-Speichern Fortbewegung und Grundtempo seines Trips ändert / Then bleibt der Trip von Nutzer B unverändert, und B kann den Trip von A nicht ändern; es wird nie mit der Kennung „default" gespeichert.
  - Test: Go-Handler-Test mit zwei Nutzern und E2E mit zwei Konten gegen Staging.

- **AC-9:** Given die Oberfläche steht auf Englisch / When der Nutzer den Reiter Etappen und den Anlege-Dialog öffnet / Then erscheinen „Mode of travel" und „Base pace" sowie der englische Kopf-Text; in Deutsch „Fortbewegung" und „Grundtempo". Das Kürzel-Protokoll (SMS-Codes) bleibt unübersetzt.
  - Test: Katalog-Vollständigkeits-Test DE/EN und E2E in beiden Sprachen.

- **AC-10:** Given Bestandstrips mit Aktivität und weiteren Einstellungen / When die Migration mit `--execute` läuft (und ein zweites Mal) / Then enthält jeder Trip zusätzlich `tempo`, das alte Feld `activity` und alle übrigen Felder (Etappen, Wegpunkte, Empfänger, Metriken) sind unverändert, ein zweiter Lauf ändert nichts, und der Trockenlauf schreibt nichts.
  - Test: Kern-Test gegen Kopie der Fixtures: Vorher/Nachher-Vergleich aller Felder außer `tempo` und `arrival_calculated`.

- **AC-11:** Given ein Bestandstrip, dessen Gehzeiten nach DAV kürzer ausfallen als bisher / When das Briefing erzeugt wird / Then folgen die bewerteten Stunden je Wegpunkt den neuen Ankunftszeiten, in der E-Mail ebenso wie in Telegram, SMS und Premium-SMS (gleicher Inhalt in allen vier Kanälen).
  - Test: E2E gegen Staging: Trip-Briefing-Mail gegen die neuen Ankunftszeiten des Reiters prüfen; Kern-Test für die Wegpunkt-Stundenzuordnung aus `arrival_calculated`.

- **AC-12:** Given ein Trip ohne `tempo`, den ein älterer Schreibpfad gespeichert hat / When er gelesen wird / Then leitet das System `tempo` aus `activity` ab (Rad 20 bleibt Rad 20), ohne dass der Nutzer etwas tun muss, und ein Speichern über die Oberfläche lässt `activity` stehen.
  - Test: Kern-Test Loader und Go-Store mit Trip ohne `tempo`.

## Scope

### Nicht-Ziele

- Tempo je Etappe überschreiben (#3197), Pausentag/Ruhetag-Verhalten (#3197)
- Anlege-Kette Orts-Vergleich (#3198)
- Löschen des Altfeldes `activity` von der Platte
- Sichtbare Auf-/Abstiegsraten

## Known Limitations und Risiken

- Einmalige Änderung der Gehzeiten aller Bestandstrips (PO akzeptiert); Prod-Bestand ca. 16 Trips (1× `fahrrad_15`, 1× `fahrrad_20`, 1× `hochtour`, Rest ohne Aktivität). Bewertete Stunden und Alarme verschieben sich entsprechend; Prüfung in Staging.
- Mischbetrieb: Ein Schreibpfad ohne `tempo` wird durch die Lazy-Ableitung aufgefangen, solange `activity` stehen bleibt.
- MTB war bisher mit 4 km/h gerechnet; neue MTB-Trips starten mit 12 km/h, Bestand wird nie automatisch zu MTB.
- Viele Alt-Tests hängen an Aktivität und Chips (Liste oben); Drift zwischen den drei Rechnern wird durch die Falltabelle verhindert.
- Der Hook `data_schema_backup.py` löst bei Änderungen an `trip.py`, `loader.py`, `internal/model/*.go` eine Sicherung aus.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0108 (Anpassung von Punkt 2 und 5, Status Angenommen)
- **Rationale:** Die PO-Entscheidung vom 2026-11-20 (DAV-Modell, nur Grundtempo) ändert den Inhalt von ADR-0108 Nr. 2; eine Entscheidung wird nie still geändert, daher Anpassung im ADR selbst, solange es noch „Vorgeschlagen" war.

## Changelog

- 2026-11-20: Doku nachgezogen nach Umsetzung: Implementation Details (Karte als Organismus, Vorlagen-Zuordnung in WeatherMetricsTab), `api_contract.md` (Tempo-Abschnitt und Changelog), `operations_playbook.md` (Migrationsabschnitt #3196), `frontend_components.md`, `architecture.md`, `i18n_glossar.md`, ADR-0108 (Status Akzeptiert)
- 2026-11-20: Initial spec created (v1.0, draft, wartet auf PO-Freigabe der ACs)
