---
entity_id: feat_2284_s2_trip_kopf
type: feature
created: 2026-10-03
updated: 2026-10-03
status: draft
version: "1.0"
tags: [trip-hub, compare-hub, kopf, shared, paritaet, save-chip]
workflow: feat-2284-s2-trip-kopf
---

# Trip-Hub-Kopf auf den geteilten Baustein `SubscriptionHeader`, Speicher-Chip im Baustein (Issue #2284 Scheibe S2)

## Approval

- [ ] Approved

## Purpose

Zweite Scheibe von #2284 (Epic #2345, Etappe P2: Hub-Kopf-Parität Trip und Ortsvergleich). In S1 wurde der
Kopf des Vergleich-Hubs auf den geteilten Baustein `SubscriptionHeader` umgestellt. Jetzt zieht der
Trip-Hub nach. Heute kann man beim Trip nur den Namen im Kopf ändern; die **Region lässt sich gar nicht
ändern**, die **Aktivität versteckt sich als Auswahlliste im Etappen-Reiter**, und der Speicher-Chip hängt
in jedem Hub an einer anderen Stelle im Code.

Nach S2 gilt für beide Hubs dasselbe:

- Name, Region und Aktivität (beim Vergleich: Aktivitätsprofil) werden im Kopf bearbeitet, mit demselben
  Baustein und denselben Bedienelementen.
- Der Speicher-Chip wird **vom Baustein** gezeigt, in beiden Hubs gleich.

### Was der PO nach S2 anders sieht (bewusst freizugeben)

1. **Aktivität wandert.** Im Etappen-Reiter des Trips verschwindet die Auswahlliste „AKTIVITÄT". Die
   Aktivität steht stattdessen im Kopf als Reihe aus **8 Kacheln** (Trekking, Skitour, Hochtour,
   Klettersteig, MTB, Fahrrad 15, 20 und 25 km/h). Ein Klick auf eine Kachel speichert sofort.
2. **Die kleine Zeile über dem Trip-Namen (Eyebrow) zeigt nur noch den Datumsbereich.** Bisher stand dort
   „REGION · DATUM". Die Region steht jetzt in einer eigenen Zeile unter dem Namen und ist per Stift
   änderbar.
3. **Der Kopf wird auf dem Handy höher, die Karte im Etappen-Reiter dadurch kleiner.** Die 8 Kacheln
   brechen bei 375 px Breite auf mehrere Zeilen um. Die Karte im Etappen-Reiter behält bei 375x667 px
   mindestens **200 px** Höhe (siehe AC-13; der Wert ist eine Annahme und wird im RED-Schritt gegen die
   gemessene Ist-Höhe kalibriert, nach unten wird er nicht ohne Rückfrage korrigiert).
4. **Der Speicher-Chip** (unten rechts, fest am Bildschirmrand) sieht in beiden Hubs gleich aus und läuft
   gleich ab („Speichere…", dann „Gespeichert HH:MM"). Seine Position am Bildschirm ändert sich nicht.
5. **Region leeren zeigt „—"** statt einer leeren Zeile, in **beiden** Hubs (siehe Entscheidung 13).

## Source

- **Frontend (Pfade relativ zu `frontend/src/`):**
  `lib/components/shared/subscription-header/SubscriptionHeader.svelte` (MODIFY),
  `lib/types.ts` (MODIFY: `ACTIVITY_TYPE_OPTIONS`),
  `lib/components/trip-detail/TripHeader.svelte` (MODIFY: mountet den Baustein),
  `lib/components/trip-detail/TripTabs.svelte` (MODIFY: Aktivitäts-Auswahlliste raus, `activityType` reaktiv),
  `lib/components/compare/CompareTabs.svelte` (MODIFY: Chip-Mount und Import raus),
  `routes/compare/[id]/+page.svelte` (MODIFY: `saveController={hubSaveCtl}` am Baustein),
  `routes/trips/[id]/+page.svelte` (MODIFY nur falls `TripHeader` die Seiten-Props anders braucht)
- **Go-API (nur Test):** `internal/handler/trip_region_test.go` (MODIFY: Zwei-Nutzer-Fall)
- **Identifier:** `SubscriptionHeader`, `titleTestid`, `saveController`, `namePrefix`, `onSaveField`,
  `ACTIVITY_TYPE_OPTIONS`, `trip-detail-h1`, `trip-region-edit-toggle|edit|save|save-error`,
  `trip-profil-option-{activity}`, `trip-profil-save-error`, `save-indicator`

> **Schicht-Hinweis:** ausschließlich **Frontend** plus ein Go-Test. Kein neuer Endpoint, kein Schema-
> Eingriff: `PUT /api/trips/{id}` trägt `region` (`internal/handler/trip.go:260`) und `activity` (`:261`)
> bereits im Patch-DTO und mergt nur gesendete (non-nil) Felder (`:397-403`). Python-Core und Mail-Renderer
> sind nicht berührt (kein Renderer liest `trip.region`), daher kein Mail-Validator im Umfang.

## Entscheidungen

Verbindlich aus der Analyse (`docs/context/feat-2284-s2-trip-kopf.md`, Abschnitt „Analysis").

1. **`trip-detail-h1` über optionalen Prop.** Der Baustein bekommt `titleTestid` (Trip:
   `'trip-detail-h1'`, Vergleich: nicht gesetzt ⇒ keine testid). Das ist ein Prop, kein `kind`-Zweig. Die
   Ratschen-Specs 724/714/336/616 bleiben unverändert (724 liest die Überschrift vor dem Öffnen und nach
   Erfolg, 714 vor dem Öffnen).
2. **Shortcode-Präfix** (Mono/Akzent vor dem Trip-Namen) über neues optionales Snippet `namePrefix`, im
   Baustein **innerhalb** der Überschrift gerendert. Ein Entfall wäre eine Funktionsänderung ohne Not.
3. **Bearbeitungsmodus wie beim Vergleich:** Die Eingabe ersetzt die Überschrift (Parität zu S1). Beim Trip
   stand die Überschrift bisher über dem Eingabefeld; das entfällt.
4. **Eyebrow nur Datumsbereich** (`eyebrow`-Snippet). Region steht inline in der Region-Zeile. Kein
   Ratschen-Spec prüft die Region in der Eyebrow (gemessen per Grep in `frontend/e2e`).
5. **Aktivität = Kachelreihe des Bausteins** (S1-Entscheidung 5). Keine neue Darstellungsvariante.
6. **Neue Konstante `ACTIVITY_TYPE_OPTIONS`** in `lib/types.ts` (Muster `ACTIVITY_PROFILE_OPTIONS`, inkl.
   Vollständigkeitsprüfung gegen `ActivityType`). Labels aus dem heutigen Etappen-Reiter (`TripTabs.svelte`):
   Trekking, Skitour, Hochtour, Klettersteig, MTB, Fahrrad (15 km/h), Fahrrad (20 km/h), Fahrrad (25 km/h).
   Die abweichenden Labels in `TripNewEditor` bleiben unberührt (kein S2-Thema).
7. **`TripHeader` bleibt Hülle.** `<header class="trip-header">`, Status-Zeile
   `trip-detail-status-supplement`, Meta-Zeile `trip-detail-meta` (km/Hm) und Mobil-Kacheln
   `trip-header-mobile-metrics` bleiben (Spec 336 bewacht sie). Die Hülle mountet den Baustein.
8. **Status und Meta außerhalb des Bausteins.** Das `meta`-Snippet des Bausteins rendert in der Region-Zeile
   und verschwindet beim Region-Bearbeiten; `badges`/`meta` bleiben beim Trip daher leer.
9. **Konflikt-Schlüssel vereinheitlicht** auf `kopf-name` / `kopf-region` / `kopf-profil` (bisher Trip:
   `'kopf'` und `'aktivitaet'`). Gemessen: beide alten Schlüssel kommen in `frontend/src` nur an den zwei
   Save-Aufrufen vor; kein Test und keine Dedup-Logik liest sie.
10. **Kein `imWiederholen`-Guard beim Trip.** Der Vergleich braucht ihn, weil eine neue `preset`-Referenz
    `CompareTabs` neu aufbaut. Beim Trip baut `trip = updated` nichts neu auf (Neuaufbau nur über
    `{#key uebernommeneFassung}`, der Kopf liegt außerhalb davon). Status quo seit #1433; AC-9 belegt es mit
    einem Test.
11. **`regionMaxLength` = 60** auch beim Trip (Backend prüft keine Länge; gleicher Wert wie im Vergleich).
12. **Chip-API: Prop `saveController?`.** Der Baustein rendert `<SaveIndicator controller={saveController}>`
    selbst und bleibt ohne `api`-Import. Vergleich übergibt `hubSaveCtl`, Trip übergibt `tripSaveCtl`.
    Chip-Mount in `CompareTabs.svelte` (samt Import) und in `TripHeader.svelte` entfallen im **selben
    Commit** (sonst zwei Chips im DOM; `feat-880` verlangt genau einen).
13. **Region leeren: Normalisierung im Baustein, nicht am Trip-Mount.** Der Baustein zeigt
    `{region || '—'}` (statt `region ?? '—'`). Begründung: Das Leeren sendet `{region: ""}`; Go setzt den
    Leerstring, `omitempty` lässt den Schlüssel in der Datei fallen. Der Seitenstand direkt nach dem
    Speichern enthält aber noch `""` ⇒ der Baustein würde eine leere Zeile zeigen. Eine Normalisierung am
    Trip-Mount (`region={trip.region || undefined}`) behebt das nur für den Trip, der Vergleich hätte
    denselben Fehler weiter. **Beleg, dass die Änderung im Baustein sicher ist:** Weder eine
    `compare-hub-*.spec.ts` noch ein `subscription_header_*.test.ts` sichert eine **leere Zeile** bei
    `region=""` zu (Grep nach leerem Erwartungstext, `—`-Vergleichen und `region: ''` in allen Kopf-Tests:
    kein Treffer); das einzige Region-Verhalten dort sind Eingabe, `maxlength` und Fehlermeldung. Das
    Bearbeitungsfeld wird weiter aus dem **rohen** `region` befüllt (`region ?? ''`), nie aus „—". Diese
    Entscheidung ersetzt die Analyse-Notiz „am Trip-Mount normalisieren"; eine Stelle, kein Sonderweg.
    Die Abweichung betrifft S1-AC-12 (Vergleich-Verhalten unverändert) nicht, weil der Vergleich bei
    `region=""` bisher eine leere Zeile zeigte, die nirgends zugesichert war; sie ist eine bewusste
    Verbesserung und wird im Vergleich mitgeprüft (AC-3).

## Zuordnung zum Issue und Abweichungen vom Zielbild

| Issue-AC | Abgedeckt durch | Bemerkung |
|---|---|---|
| Issue-AC-1: Region im Trip-Hub per Stift änderbar, nach Reload persistiert | AC-2, AC-3, AC-6, AC-7, AC-8, AC-9 | Region inline im Kopf; Leeren mit „—" |
| Issue-AC-2: Chip in beiden Hubs gleiche Position, gleicher Verlauf | AC-10, AC-11 | Ein Chip, vom Baustein gerendert |
| Issue-AC-3: Versand-Reiter ohne zweiten Speichern-Knopf | **S3, nicht S2** | |
| Issue-AC-4: explizites `context=` an allen Mounts | **S3 bzw. S6, nicht S2** | |

Weitere Abweichungen vom Issue-Zielbild:

- **Kebab/Lifecycle-Aktionen im Kopf** sind nicht Teil von S2 (Aktionsmodell → #2278); S2 liefert keinen
  befüllten `actions`-Slot.
- **Rückbau der Wrapper** `AlarmeScheduleTab`/`BriefingScheduleTab` ist S3.
- Das Issue sagt „Aktivität im Kopf" nicht ausdrücklich; sie wandert hier mit, weil der Baustein ein
  Profil/Aktivitäts-Feld kennt und der Trip es sonst nirgends im Kopf hätte (Analyse, Entscheidung 5).

## Acceptance Criteria

**AC-1:** Given ein Nutzer öffnet einen Trip im Trip-Hub (Desktop 1280 px) When er den Stift am Namen
(`trip-name-edit-toggle`) klickt, einen neuen Namen eingibt und speichert (`trip-name-save`) Then zeigt die
Überschrift mit `data-testid="trip-detail-h1"` sofort den neuen Namen (der Shortcode-Präfix bleibt
davor erhalten), und nach einem Neuladen der Seite steht der Name unverändert dort, weil `PUT
/api/trips/{id}` ihn gespeichert hat.

**AC-2:** Given ein Nutzer öffnet einen Trip im Trip-Hub When er den Stift an der Region
(`trip-region-edit-toggle`) klickt, „Alpen Nord" eingibt und speichert (`trip-region-save`) Then steht die
Region sofort in einer eigenen Zeile unter dem Namen, nach einem Neuladen unverändert dort, und die kleine
Zeile über dem Namen (Eyebrow) zeigt **nur den Datumsbereich**, nicht mehr „REGION · DATUM"; die Region
kommt in der Eyebrow nicht vor.

**AC-3:** Given ein Trip (und getrennt ein Ortsvergleich) hat eine gesetzte Region When der Nutzer die
Region-Eingabe leert und speichert Then zeigt die Region-Zeile den Platzhalter „—" (nicht eine leere
Zeile), nach dem Neuladen ebenfalls „—", und beim Trip blenden die Startseite (Home-Hero) und die
Trip-Liste die Region vollständig aus (kein „—", kein leerer Punkt); der gleiche Platzhalter erscheint im
Kopf des Vergleich-Hubs, weil die Normalisierung im Baustein liegt. Erneutes Öffnen des Bearbeitungsfelds
zeigt ein **leeres** Feld, nicht „—".

**AC-4:** Given ein Trip mit gesetzter Aktivität „Trekking" When der Nutzer den Trip-Hub öffnet Then zeigt
der Kopf eine Reihe aus genau **8 Kacheln** (`trip-profil-option-trekking`, `-skitour`, `-hochtour`,
`-klettersteig`, `-mtb`, `-fahrrad_15`, `-fahrrad_20`, `-fahrrad_25`), die Kachel „Trekking" trägt
`data-selected="true"`, und im Etappen-Reiter existiert **kein** Element `edit-activity-dropdown` mehr;
klickt der Nutzer „Skitour", ist diese Kachel sofort die einzige mit `data-selected="true"` und nach dem
Neuladen weiter gewählt. Ein Trip ohne gespeicherte Aktivität zeigt alle Kacheln ungewählt.

**AC-5:** Given der Trip-Hub ist im Etappen-Reiter geöffnet und zeigt Etappen mit Ankunftszeiten When der
Nutzer im Kopf die Aktivität von „Trekking" auf „Skitour" wechselt Then ändern sich die Ankunftszeiten der
Etappen **ohne Neuladen und ohne Reiterwechsel** auf die Werte für Skitour (gleicher Trip, anderes
Tempo-Modell), weil die Aktivität im Etappen-Reiter reaktiv aus dem aktuellen Trip gelesen wird und nicht
nur beim ersten Anzeigen.

**AC-6:** Given ein Trip mit gesetzten Werten für Name, Region, Aktivität, Etappen, Zeitplan und Kanäle
When der Nutzer nacheinander nur den Namen, nur die Region und nur die Aktivität ändert Then enthält jeder
gesendete `PUT /api/trips/{id}` **ausschließlich** den einen Schlüssel `{name}` bzw. `{region}` bzw.
`{activity}` (exakte Schlüsselmenge per Mitschnitt, kein Spread des Seiten-Trips), und ein `GET` danach
liefert alle übrigen Felder (Etappen, Waypoints, Zeitplan, Kanäle, Metriken, Alarme) unverändert.

**AC-7:** Given Nutzer A besitzt einen Trip und Nutzer B ist mit eigener Sitzung angemeldet When B `PUT
/api/trips/{id von A}` mit genau dem Rumpf sendet, den der Kopf schickt (`{"region":"fremd"}`) Then
antwortet die API mit 404, A's Trip-Datei ist danach **byte-gleich** zu vorher (kein Schreiben, kein
Anlegen unter B), und A liest beim GET weiterhin seine alte Region; A kann seine Region weiterhin ändern.
(Go-Handler-Test mit zwei echten Nutzern; Analogon zu S1-AC-11.)

**AC-8:** Given der Speicherversuch scheitert (PUT antwortet 500 mit `{"error":"Serverfehler"}`) When der
Nutzer im Trip-Hub Name oder Region speichert bzw. eine Aktivitäts-Kachel klickt Then erscheint die
Fehlermeldung mit `role="alert"` unter dem jeweiligen Feld (`trip-name-save-error`,
`trip-region-save-error`, `trip-profil-save-error`; Text aus `error`, sonst „Speichern fehlgeschlagen"),
bei Name und Region bleibt die Eingabe **offen** mit dem eingetippten Wert, bei der Aktivität bleibt die
zuvor gespeicherte Kachel die einzige mit `data-selected="true"`, und der serverseitige Wert ist
unverändert.

**AC-9:** Given eine andere Sitzung hat den Trip inzwischen geändert (PUT antwortet 412) When der Nutzer
im Trip-Hub Name, Region oder Aktivität speichert Then bleibt das Feld offen ohne eigene Fehlermeldung, der
Speicher-Chip zeigt „Nochmal speichern" (`data-state="conflict"`) mit **einem** Eintrag je Feld unter den
Schlüsseln `kopf-name`, `kopf-region` bzw. `kopf-profil`, und ein Klick auf „Nochmal speichern" sendet nur
das Eigenfeld erneut, schließt das Feld bei Erfolg und ersetzt dabei den Seitenstand, **ohne** die Reiter
neu aufzubauen (ein im Etappen-Reiter geöffneter Zustand bleibt erhalten, solange der Retry läuft). Dieses
Verhalten entspricht dem #1433-Konfliktschutz (AC-10, AC-15, AC-18 der Spec `trip_mehrreiter_konfliktschutz`)
und gilt für `region` als neues Eigenfeld gleichermaßen.

**AC-10:** Given der Trip-Hub oder der Vergleich-Hub ist geöffnet (Desktop 1280 px und Mobil 375 px) When
die Seite geladen ist Then existiert im DOM **genau ein** Element `save-indicator` (`locator.count() ===
1`, ohne `:visible`-Filter), es hat `position: fixed` (per `getComputedStyle`), und es steht an
derselben Bildschirmposition (unten rechts, mobil über der unteren Navigation) wie vor der Umstellung; der
Chip wird vom Kopf-Baustein gerendert, nicht mehr von `CompareTabs` bzw. `TripHeader`.

**AC-11:** Given der Nutzer ändert in einem der beiden Hubs ein Kopf-Feld (Trip: Region; Vergleich:
Profil) When der Speichervorgang läuft und endet Then durchläuft der Chip in beiden Hubs dieselbe Folge
`data-state` `saving` ⇒ `idle` mit dem Text „Gespeichert HH:MM" nach Abschluss, am selben Controller des
jeweiligen Hubs (Trip: `tripSaveCtl`, Vergleich: `hubSaveCtl`); nach einer Versand-Änderung im Trip
(Spec 616) steht der Chip weiter auf `idle`.

**AC-12:** Given der Nutzer ist offline (Browser ohne Netz) When der Trip-Hub geöffnet ist Then sind die
neuen Kopf-Bedienelemente (`trip-region-edit-toggle`, alle `trip-profil-option-*`) gesperrt (`disabled`),
wie bisher die Aktivitäts-Auswahlliste; die Spec `pwa-offline-sperre-und-mandant` zeigt für die Aktivität
auf den neuen Ort (Kachel statt Auswahlliste), die Aussage „offline gesperrt" bleibt erhalten.

**AC-13:** Given ein Trip ist im Etappen-Reiter bei Viewport 375x667 px (Mobil) geöffnet When die Seite
geladen ist Then ist der Kopf höher als vor S2 (die 8 Aktivitäts-Kacheln brechen mehrzeilig um und die
Region-Zeile kommt hinzu), die Karte im Etappen-Reiter (`.mobile-editor`) hat dennoch eine gemessene Höhe
von mindestens **200 px** (entspricht dem Mindestwert `MOBILE_EDITOR_MIN_HEIGHT_PX` des Editors), alle
Kacheln und der Stift an der Region sind ohne horizontales Scrollen erreichbar, und die Mindest-Tippfläche
bleibt 44 px. Die 200 px sind eine Annahme (Mindestwert des Editors); wird sie im RED-Schritt als
Tautologie erkannt (Karte liegt schon vorher auf dem Mindestwert), wird zusätzlich die gemessene Differenz
Kopfhöhe nachher minus vorher im Testprotokoll ausgewiesen, damit der PO die Größenordnung sieht.

**AC-14:** Given der Trip-Kopf wurde auf den Baustein umgestellt When die CI-Ratschen-Specs
`issue-724-trip-name-save-error`, `issue-714-trip-ui-polish`, `issue-616-trip-one-surface` und
`issue-336-status-dedup` **ohne Änderung an den Spec-Dateien** gegen den CI-Stack laufen Then sind alle
grün; dafür bleiben `trip-detail-h1`, `<header class="trip-header">`, `trip-detail-status-supplement`,
`trip-detail-meta`, `trip-header-mobile-metrics` sowie `trip-name-edit-toggle|edit|save|save-error` im
Trip-Kopf erhalten. Einzige Specs, die umgestellt werden dürfen, sind die zwei Nicht-Ratschen-Specs
`pwa-offline-sperre-und-mandant.spec.ts` (`:216-222`, `:410-416`) und
`feat-1461-s3b2b-compare-kanal-schwelle.spec.ts` (`:385-391`): Auslöser/Ziel wechselt von
`edit-activity-dropdown` auf `trip-profil-option-*`, Prüfaussage unverändert.

**AC-15:** Given der Vergleich-Hub nach der Chip-Verlagerung When die Specs `compare-hub-name-region-profil`,
`compare-hub-inline-edit`, `compare-hub-save-chip`, `compare-hub-fidelity-s8c` und `compare-hub-kopf-einmal`
unverändert laufen Then sind sie so grün wie vor der Umstellung (bekannte, kopfunabhängige Rote aus S1
bleiben in #1196 gebucht, Nachweis per Vorher-Lauf), und jede Kopf-testid existiert im Vergleich genau
einmal.

**AC-16:** Given der Baustein `SubscriptionHeader` wird serverseitig (SSR) mit den erweiterten Props
gerendert When er einmal mit `titleTestid="trip-detail-h1"`, `namePrefix`-Snippet und `saveController`
(Trip-Satz) und einmal ohne diese Props (Vergleich-Satz) gerendert wird Then trägt nur der Trip-Satz die
testid `trip-detail-h1` und den Präfix innerhalb der Überschrift, `save-indicator` erscheint pro Ausgabe
genau einmal mit Controller und gar nicht ohne Controller, beide Ausgaben haben dieselbe Gerüststruktur
(keine Markup-Verzweigung nach `kind`), und `region=""` wird als „—" gezeigt, `region=undefined` ebenfalls,
`region="Nord"` als „Nord".

**AC-17:** Given die #1433-Tests des Trips (`trip_kopf_aktivitaet_melden_konflikt`,
`trip_reiter_roundtrip_jedes_feld`, `trip_reiter_nutzlast_nur_eigene_felder`,
`trip_konflikt_schreibt_seitenstand_fort`) und die Quelltextprüfungen `TripHeader.issue699/spacing/
mobile-metrics.test.ts` When der `node --test`-Kern läuft Then sind alle grün, der Harness
`tripMehrreiterPruefstand.ts` ruft für Kopf und Aktivität nun `onSaveField` auf (nicht mehr
`makeNameSaveHandler`/`handleActivityChange`), **keine bisherige Zusicherung ist gestrichen** (jede alte
Aussage steht weiter in einem Test), und die `TripHeader.*.test.ts` prüfen Verhalten (gerendertes DOM:
Eyebrow nur Datum, Mobil-Kacheln, Abstände) statt Quelltext-Zeichenketten.

## Test-Plan

**Kern (deterministisch, `node --test`, SSR-Harness wie in S1):**

| Testdatei (nach Verhalten benannt) | Deckt |
|---|---|
| `shared/__tests__/subscription_header_kontextneutral.test.ts` (erweitern) | AC-16 (`titleTestid`, `namePrefix`, Chip genau einmal bzw. gar nicht, `region`-Normalisierung „—") |
| `shared/__tests__/subscription_header_einmal_gerendert.test.ts` (erweitern) | AC-10 (Trip-Satz: jede Kopf-testid und `save-indicator` genau einmal) |
| `trip-detail/__tests__/tripMehrreiterPruefstand.ts` + die vier #1433-Tests | AC-6, AC-8, AC-9, AC-17 (auf `onSaveField` umgehängt; Zusicherungen erhalten, Schlüssel `kopf-*`) |
| `trip-detail/TripHeader.issue699/spacing/mobile-metrics.test.ts` | AC-17 (Quelltext ⇒ Verhalten) |

SSR führt keine Klick-Handler aus; Speicher-, Fehler- und Konfliktpfade werden deshalb im E2E bewiesen,
nicht im SSR.

**Go:** `internal/handler/trip_region_test.go` um den Zwei-Nutzer-Fall erweitern (AC-7), orientiert an
`TestUpdateTripHandler_TenantIsolation_ETagNotSharedAcrossUsers` (`trip_etag_ifmatch_test.go:236`).

**Live-E2E (Playwright, CI-Stack/Staging):** Neue Datei `frontend/e2e/trip-hub-kopf-region-aktivitaet.spec.ts`
(AC-1 bis AC-6, AC-8 bis AC-13), **in `.github/ci_e2e_specs.txt` aufnehmen**. PUT-Mitschnitt per
`page.route` mit exakter Schlüsselmenge (AC-6). Fehler per `page.route` 500 (AC-8), 412 (AC-9). Chip-Zählung
und `position: fixed` in beiden Hubs und beiden Viewports (AC-10). Kartenhöhe bei 375x667 (AC-13). Alle
Specs arbeiten gegen Wegwerf-Trips/-Vergleiche, nie gegen Daten des PO (insbesondere nicht gegen den
Trip des PO; Trip-Konfiguration des PO bleibt unberührt). Für AC-9 mit Nutzer-Isolation: ein Trip des
Testnutzers, kein Zugriff auf fremde Daten.

**Mutations-Gegenprobe für den Adversary (Pflicht, per String-Ersetzung mit externer Sicherungskopie):**
(a) `if kind === 'trip'`-Zweig ins Baustein-Markup ⇒ AC-16 rot. (b) In `TripHeader` den PUT-Rumpf auf
`{...trip, region}` verfälschen ⇒ AC-6 rot (und AC-17-Nutzlasttest). (c) `region || '—'` zurück auf
`region ?? '—'` ⇒ AC-3 und AC-16 rot. (d) `activityType` in `TripTabs` zurück auf Mount-`$state` ⇒ AC-5
rot. (e) Chip zusätzlich in `CompareTabs` belassen ⇒ AC-10 rot (Zählung ohne `:visible`). (f)
Konflikt-Schlüssel `kopf-region` auf `kopf-name` setzen ⇒ AC-9 rot (zwei Felder teilen einen Eintrag).
(g) Mandanten-Test: `s.WithUser(...)` im Handler durch festen Nutzer ersetzen ⇒ AC-7 rot. (h)
`titleTestid` entfernen ⇒ Ratschen-Spec 724/714 rot. Leitfrage: wird die Zusicherung dort geprüft, wo sie
WIRKT (Browser, Datei auf der Platte), nicht nur dort, wo der Code steht?

**Verifikation nach Merge:** Staging-Auto-Deploy abwarten, Ratschen-Specs und `compare-hub-*` gegen
Staging, Hub von Hand in beiden Viewports ansehen (Eyebrow, Region-Zeile, Kacheln, Karte mobil). Kein
Mail-Renderer berührt ⇒ kein Mail-Validator. Neue Befehle über Kanäle sind nicht berührt.

## Risiken

| Risiko | Gegenmaßnahme |
|---|---|
| **Veraltete Ankunftszeiten**, weil `TripTabs` die Aktivität nur beim ersten Anzeigen liest | `activityType = $derived(trip?.activity)`; AC-5; Mutation (d) |
| **Doppel-Chip** während des Umzugs | Beide Mounts im selben Commit entfernt; AC-10 zählt ohne `:visible`; `feat-880` |
| **`position: fixed` bricht**, falls ein Vorfahr `transform`/`filter` trägt | Gemessen: keiner (`<main>` hat `position:relative;overflow:hidden`, beschneidet `fixed` nicht); AC-10 belegt per `getComputedStyle` |
| **Chip wandert beim Vergleich aus dem `{#key uebernommeneFassung}`-Bereich** (kein Neuaufbau mehr) | Verhaltensneutral, `SaveIndicator` hat keinen lokalen JS-Zustand (Dimming per CSS-Animation); AC-11 |
| **Mobil höherer Kopf, kleinere Karte** | AC-13 mit 200-px-Schwelle, Höhenzuwachs im Testprotokoll ausgewiesen, vom PO bei Freigabe zu sehen |
| **Datenverlust durch Spread** (Fehlerklasse #2375/#2381) | PUT-Rumpf nur Eigenfeld; AC-6; Mutation (b) |
| **Fremdzugriff** über den neuen Region-Rumpf | AC-7 (Zwei-Nutzer-Test), Handler nutzt `s.WithUser(middleware.UserIDFromContext(...))` |
| **Ratschen-Specs 724/714/336/616 brechen** | Anker bleiben (Entscheidungen 1, 7); AC-14 verlangt unveränderte Spec-Dateien |
| **Offline-Sperre** greift nur in `<main>` | Neue Knöpfe liegen darin; AC-12 |
| **`regionMaxLength`/Aktivität leeren** | Aktivität leeren entfällt (Kacheln kennen keinen leeren Zustand); Region 60 Zeichen wie Vergleich |
| **Parallelarbeit mit S3** (fasst `TripTabs.svelte` ebenfalls an) | S3 nicht parallel starten |
| **LoC knapp unter dem Limit** | Vorab `workflow.py status` prüfen; Tests/Specs/Docs zählen nicht |

## Out of Scope

Gehört weiter zu #2284 bzw. zum Epic und folgt zeitlich danach, ist hier **nicht** abgespalten:

- **S3 (#2284):** Rückbau der Trip-Hüllen `AlarmeScheduleTab` und `BriefingScheduleTab` samt totem Knopf
  (Issue-AC-3), explizites `context=` an allen Mounts (Issue-AC-4, mit S6).
- **S4:** gemeinsamer `VTLaufzeit`-Baustein. **S5:** ein Ladeweg für den `metricsCatalog`.
- **#2278:** Aktionsmodell (Kebab/Lifecycle-Aktionen); der `actions`-Slot bleibt leer.
- **`TripNewEditor`-Aktivitäts-Labels** (z. B. „Alpen-Trekking" vs. „Trekking"): kein S2-Thema.
- **Aktivität leeren:** wird nicht angeboten.

## Betroffene Dateien und Umfang

| Datei | Änderung |
|---|---|
| `frontend/src/lib/components/shared/subscription-header/SubscriptionHeader.svelte` | MODIFY, ca. +25 (`titleTestid`, `saveController`, `namePrefix`, `region \|\| '—'`) |
| `frontend/src/lib/types.ts` | MODIFY, ca. +12 (`ACTIVITY_TYPE_OPTIONS`) |
| `frontend/src/lib/components/trip-detail/TripHeader.svelte` | MODIFY, ca. ±100 (Baustein-Mount, `onSaveField`, Namens-Markup und Chip raus, Eyebrow nur Datum) |
| `frontend/src/lib/components/trip-detail/TripTabs.svelte` | MODIFY, ca. −35 (Auswahlliste und Handler raus, `$derived`) |
| `frontend/src/lib/components/compare/CompareTabs.svelte` | MODIFY, ca. −6 (Chip und Import) |
| `frontend/src/routes/compare/[id]/+page.svelte` | MODIFY, ca. +2 |
| Tests, E2E, `ci_e2e_specs.txt`, Go-Test | zählen nicht gegen das LoC-Limit |

Schätzung Produktivcode **ca. 190-220 brutto** in 6 Dateien, unter dem Limit von 250 ⇒ keine Teilung.
Risiko MEDIUM (zentrale Kopf-Komponente beider Hubs, Speicherweg mit Konfliktschutz).

## Abhängigkeiten

| Entity | Type | Purpose |
|--------|------|---------|
| `SubscriptionHeader` (S1, `feat_2284_s1_subscription_header`) | Upstream | Baustein; Entscheidungen 1-8 gelten weiter |
| `ui/SaveIndicator.svelte`, `saveStatusStore` (`createSaveStatus`) | Upstream | Chip und Controller, unverändert |
| `shared/tripSpeicherung.ts` (`baueTripSpeicherung`, `speichereOderMeldeKonflikt`) | Upstream | Speicherweg mit If-Match und Konfliktmeldung, unverändert |
| Go `UpdateTripHandler` (`internal/handler/trip.go`) | Upstream (unverändert) | Merge nur gesendeter Felder, Mandantentrennung |
| `trip_mehrreiter_konfliktschutz` (#1433) | Kontext | AC-10, AC-15, AC-18 gelten für den neuen Weg |
| `feat_880_autosave_overlay` | Kontext | Genau ein `save-indicator`, `position: fixed` |
| `feat_1273_s2_compare_hub_name_region_profil` | Kontext | Vorlage der Verhaltens-ACs |
| `docs/context/feat-2284-s2-trip-kopf.md` | Kontext | Analyse und 12 Entscheidungen |

## Changelog

- 2026-10-03: Initial spec created (Scheibe S2 von #2284, Epic #2345 Etappe P2)
