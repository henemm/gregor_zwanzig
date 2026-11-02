---
entity_id: fix_2612_gpx_upload_id
type: fast
created: 2026-11-02
status: draft
issue: 2612
---

# Mini-Spec: GPX-Upload überschreibt keinen gleichnamigen eigenen Trip mehr

**Issue #2612** (Epic #2138, Datenverlust-Risiko).

## Ursache (belegt)

`frontend/src/routes/gpx-upload/gpxTrip.ts:47-54` (`baueGpxTrip`) bildet die Trip-Kennung
mit `gpxTripId(tripName)` aus dem Trip-Namen. `POST /api/trips` ist ein Upsert (AC-6 aus #2482):
Hat der Nutzer schon einen Trip mit derselben Kennung (z. B. „GR20" → `gr20`), wird dieser
still durch einen Ein-Etappen-Trip ersetzt — samt Etappen, Metriken, Alarm- und
Versandeinstellungen.

Das normale Anlegen (`/trips/new`, `tripNewLogic.ts`) vergibt dagegen eine Zufallskennung
(`crypto.randomUUID().slice(0, 8)`) und kennt das Problem nicht.

## Was ändert sich

- `baueGpxTrip` vergibt die Trip-Kennung wie das normale Anlegen über den geteilten Helfer
  `newId()` aus `frontend/src/lib/components/shared/wizardHelpers.ts` (Trip-Muster, keine
  zweite ID-Logik). Die Etappen-Kennung bleibt `<trip-id>-t1`.
- Die Namensprüfung der Seite (leerer/ungültiger Name → Fehlerhinweis `layout.gpx.fehler_name`,
  heute inline `if (!gpxTripId(tripName))` in `+page.svelte`) wird als prüfbarer Helfer
  `gpxNameFehler(name): MessageKey | null` nach `gpxTrip.ts` gezogen und von der Seite genutzt.
  `gpxTripId` dient danach nirgends mehr als Kennung.

## Bewusste Entscheidung: Duplikate statt Überschreiben

Ein wiederholter Upload mit demselben Namen legt einen **zweiten** Trip an. Das entspricht dem
normalen Anlegen über `/trips/new`, das gleichnamige Trips ebenfalls zulässt (Trip-Muster,
Code-Teilung). Ein Duplikat ist sichtbar und mit einem Klick löschbar; ein still überschriebener
Trip ist unwiederbringlich verloren. Eine Rückfrage „Trip existiert schon – ersetzen?“ ist
ausdrücklich nicht Teil dieses Tickets.
- Der bestehende Test `gpx_upload_sprache.test.ts` prüft die Kennung künftig auf Form
  (8 Zeichen) statt auf den Namens-Slug und vergleicht de/en ohne die Zufallskennung.

## Was darf sich nicht ändern

- Trip-Name bleibt exakt die Nutzereingabe (Randleerzeichen, Umlaute).
- Nutzlast sonst unverändert (eine Etappe mit Name, Datum, Wegpunkten aus dem GPX).
- Weiterleitung nach dem Speichern nutzt weiter die vom Server bestätigte Kennung.
- Server-Upsert von `POST /api/trips` bleibt unverändert (der Trip-Editor speichert darüber).

## Acceptance Criteria

**AC-1:** Given ein Nutzer hat bereits einen Trip namens „GR20" mit mehreren Etappen, When er eine GPX-Datei hochlädt und den neuen Trip ebenfalls „GR20" nennt und speichert, Then hat er danach zwei Trips und der bestehende Trip ist mit allen Etappen und Einstellungen unverändert.

**AC-2:** Given zwei GPX-Uploads mit exakt demselben Trip-Namen, When für beide die Nutzlast gebaut wird, Then tragen sie zwei verschiedene Trip-Kennungen, und keine davon ist aus dem Namen abgeleitet.

**AC-3:** Given ein leerer oder nur aus Sonderzeichen bestehender Trip-Name, When der Nutzer speichert, Then erscheint weiterhin der Hinweis zum ungültigen Namen und es wird nichts gespeichert.

## Manuelle Test-Schritte (Staging)

1. Als Testnutzer einen Trip „GR20" mit ≥2 Etappen anlegen.
2. `/gpx-upload`: GPX hochladen, Name „GR20", speichern.
3. Trip-Liste: zwei Trips „GR20"; der alte hat weiterhin ≥2 Etappen.

## Inline-Test (wird während Implementierung geschrieben)

- [ ] AC-2: zwei `baueGpxTrip`-Aufrufe mit gleichem Namen → verschiedene 8-Zeichen-Kennungen, ≠ Slug (vorher rot).
- [ ] AC-3: `gpxNameFehler('')`, `gpxNameFehler('   ')`, `gpxNameFehler('—!?')` → `layout.gpx.fehler_name`; `gpxNameFehler('GR20 Süd')` → `null`.
- [ ] Bestehender Sprach-Paritätstest bleibt grün (Kennung aus dem Vergleich herausgenommen).
- [ ] AC-1 wird in `/e2e-verify` gegen Staging aus Nutzersicht geprüft.
