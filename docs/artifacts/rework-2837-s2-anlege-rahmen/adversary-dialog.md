# Adversary Dialog — rework-2837-s2-anlege-rahmen
Spec: docs/specs/modules/rework_2837_s2_anlege_rahmen.md
Datum: 2026-11-08 15:45

## Checkliste
- [x] **Input:** `context`, Namen und Zustand des Editors (Name, bereit zum Abschluss, Standardwerte erlaubt), Callbacks `onCancel`, `onFinish`.
- [x] **Output:** gleicher Rahmen für beide Arten; sichtbarer Unterschied nur in der Whitelist.
- [x] **Side effects:** keine im Rahmen. Speichern, Autosave und Anlegen bleiben im jeweiligen Editor und ändern sich nicht.
- [x] **AC-1:** Given der Nutzer öffnet `/trips/new` und `/compare/new` auf dem Computer (1440 px) / When die Seite geladen ist / Then zeigt der Pfad oben „Trips / Neuer Trip“ bzw. „Orts-Vergleiche / Neuer Vergleich“, der vordere Teil ist ein Link zur Liste, der hintere kein Link, und beim Vergleich steht kein separater „Abbrechen“-Knopf mehr in der Kopfleiste.
- [x] **AC-2:** Given der Nutzer ist im Trip-Assistenten mit einer Eingabe auf dem Computer / When er den vorderen Teil des Pfades („Trips“) anklickt / Then verlässt er den Assistenten ohne Speichern und landet auf `/trips`, und es entsteht kein neuer Trip.
- [x] **AC-3:** Given der Nutzer öffnet beide Assistenten auf dem Handy (390 px) / When er den Kopf betrachtet / Then steht links ein Zurück-Pfeil mit dem Elternteil-Namen aus dem Katalog („Trips“ bzw. „Orts-Vergleiche“), und ein Tippen führt beim Trip ohne Speichern auf `/trips`, beim Vergleich auf `/compare`.
- [x] **AC-4:** Given beide Assistenten in Deutsch und in Englisch auf Computer und Handy / When der Nutzer das Eyebrow-Label über dem Titel liest / Then steht dort „Neuer Trip“ / „Neuer Vergleich“ (en: „New trip“ / „New comparison“), auf dem Computer und auf dem Handy derselbe Text, und niemals „Neue Trip“.
- [x] **AC-5:** Given beide Assistenten auf dem Computer / When der Nutzer den unteren Fuß betrachtet / Then steht „Abbrechen“ (`Btn ghost`) bei beiden unten links, und es gibt in der Kopfleiste keinen Abbrechen-Knopf.
- [x] **AC-6:** Given der Nutzer hat im Trip-Assistenten Eingaben gemacht / When er „Abbrechen“ oder Zurück wählt / Then wird nichts gespeichert und er landet auf `/trips`; wählt er dagegen eine andere Navigation (z. B. Menü) und der Trip ist bereit, bleibt das Autosave-Verhalten wie heute unverändert.
- [x] **AC-7:** Given der Nutzer ist im Vergleichs-Assistenten mit Eingaben / When er „Abbrechen“ wählt oder die Seite verlässt / Then landet er bei Abbrechen auf `/compare`, es wird kein Vergleich und kein Entwurf angelegt, und angelegt wird nur beim Klick auf „Briefing aktivieren“.
- [x] **AC-8:** Given beide Assistenten auf dem Computer im letzten Schritt / When der Nutzer den Fuß betrachtet / Then steht die Hauptaktion unten rechts, schwarz (Ink) mit weißer Schrift, beim Trip „Trip speichern“ und beim Vergleich „Briefing aktivieren“, und beim Vergleich sitzt „Briefing aktivieren“ nicht mehr oben in der Kopfleiste.
- [x] **AC-9:** Given ein Assistent, bei dem der Abschluss noch nicht möglich ist / When der Nutzer die Hauptaktion betrachtet / Then ist sie sichtbar abgeblendet und nicht anklickbar, und sie wird anklickbar, sobald der Abschluss möglich ist.
- [x] **AC-10:** Given beide Assistenten auf dem Computer / When der Nutzer den Fuß betrachtet / Then steht „Mit Standardwerten speichern“ bei beiden im Fuß neben der Hauptaktion (nicht in der Kopfzeile), zusammen mit dem Hinweistext zum Abschluss.
- [x] **AC-11:** Given beide Assistenten in einem Zwischenschritt / When der Nutzer „Weiter“ betrachtet / Then ist „Weiter“ bei beiden ein orangefarbener Knopf (`Btn accent`), der im gesperrten Zustand allein durch das gemeinsame Abgeblendet-Aussehen erkennbar ist (keine zusätzliche Inline-Deckkraft), mit Hinweistext daneben.
- [x] **AC-12:** Given der Trip-Assistent auf Computer und Handy / When der Nutzer den Abschluss betrachtet / Then heißt die Hauptaktion auf beiden „Trip speichern“ (nicht mehr „Speichern“ auf dem Handy), und im Vergleich bleibt „Briefing aktivieren“ auf beiden.
- [x] **AC-13:** Given beide Assistenten auf dem Handy (390 px) / When der Nutzer die Fußleiste betrachtet / Then sitzt sie unverändert über der Navigation mit demselben Abstand wie heute (`navClearance`), und nichts ist verdeckt.
- [x] **AC-14:** Given der Rahmen im Quelltext / When beide Editoren gerendert werden / Then entsteht der Aufbau aus **einem** Markup (`AnlegeRahmen`), `context` wählt nur Textschlüssel, Elternteil-Link, Datenmarke und Testid-Präfix, und es gibt keine Komponente mit Pendant in `trip-new/` oder `compare-new/`.
- [x] **AC-15:** Given neue und verschobene Nutzertexte (Elternteil, Eyebrow, Abbrechen, Abschluss-Texte) / When die Oberfläche auf Deutsch und Englisch gerendert wird / Then erscheinen alle Texte über den Katalog in beiden Sprachen, und es bleibt kein hart kodierter Nutzertext.
- [x] **AC-16:** Given bestehende Tests und Automatisierungen / When der Umbau fertig ist / Then bestehen die Selektoren `trip-new-save-btn`, `tn-desktop-footer`, `compare-editor-activate`, `compare-editor-standardwerte`, `trip-new-continue-etappen`, `compare-editor-continue-orte` weiter, und neu ist nur der Fuß-Wrapper `cm-desktop-footer` analog `tn-desktop-footer`.
- [x] **AC-17:** Given der Nutzer startet einen Assistenten mit einer Vorlage (`?from=`) / When er `/trips/new?from=…` bzw. `/compare/new?from=…` öffnet / Then sind die Felder wie vor dem Umbau vorbelegt, und der Rahmen sieht aus wie ohne Vorlage.
- [x] **AC-18:** Given der Vergleichs-Assistent (Hülle mit `TopoBg` und waagerecht scrollender Leiste) auf dem Computer / When der Nutzer bei langem Inhalt scrollt oder das Fenster klein ist / Then bleibt der Fuß mit Abbrechen und Hauptaktion am unteren Fensterrand sichtbar und erreichbar.
- [x] **AC-19:** Given die Umsetzung / When die Testsuite läuft / Then sind alle divergenz-verankernden Tests aus dem Test Plan umgedreht und nicht gelöscht, die neuen Tests (Unit-Test des Rahmens, E2E `anlege-rahmen-paritaet.spec.ts`) sind grün, und die Pflicht-Mutationen werden von mindestens einem Test gefangen.
- [x] **AC-20:** Given die Doku / When sie nach der Lieferung geprüft wird / Then enthält ADR-0110 den Nachtrag „S2 umgesetzt“ (kein neues ADR), und die Whitelist dieser Spec ist die einzige Liste erlaubter Abweichungen.
- [x] **AC-21:** Given (Abschluss) S2 ist auf Staging / When ein Fresh-Eyes-Prüfer ohne Vorwissen das Screenshot-Paar Anlege-Rahmen Computer 1440 px und Handy 390 px (Trip gegen Vergleich) vergleicht / Then findet er keinen Unterschied außer der Whitelist (Schritt-Inhalte, Abschluss-Text mit Hinweis, Profil-Auswahl), und das Paar liegt als Kommentar im Epic #2345.

## Dialog

### Runde 1
**Adversary:**
Basislauf: 12 benannte Frontend-Testdateien 694/694 gruen, Wächter-pytest gruen; zusätzlich (versehentlich ohne Dateiliste) die gesamte Frontend-Suite: 8093 Tests, 8088 pass, 0 fail, 5 skipped (`adversary-test-output.txt`).

Confirmation: AC-1, AC-4, AC-14 — CONFIRMED
  Code reference: frontend/src/lib/components/shared/anlege-rahmen/AnlegeRahmen.svelte:46 (ART-Datentabelle, einzige context-Stelle), frontend/src/lib/components/shared/anlege-rahmen/AnlegeRahmen.svelte:60 (`data-kind={context}`), frontend/src/lib/components/shared/anlege-rahmen/AnlegeRahmen.svelte:64 (Elternteil als `<a>`, Kind als `<span>`), frontend/src/lib/components/shared/anlege-rahmen/AnlegeRahmen.svelte:70 (Eyebrow aus Katalog). Kein `if context` im Markup (Mutation M24-artig und Unit-Test AC-14 bestätigen).
Confirmation: AC-5, AC-8, AC-9, AC-10 — CONFIRMED
  Code reference: frontend/src/lib/components/shared/anlege-rahmen/AnlegeRahmen.svelte:80-86 (Fuß: Abbrechen `ghost` links, Hinweis+Standardwerte+Hauptaktion `primary` rechts, `disabled={!canFinish}`); Aufrufer frontend/src/lib/components/trip-new/TripNewEditor.svelte:559-572, frontend/src/lib/components/compare-new/CompareNewEditor.svelte:455-466.
Confirmation: AC-11 — CONFIRMED
  Code reference: frontend/src/lib/components/trip-new/TripNewEditor.svelte:705 (Btn accent, nur `disabled`, keine Inline-Deckkraft), frontend/src/lib/components/compare-new/CompareNewEditor.svelte:548.
Confirmation: AC-12 — CONFIRMED
  Code reference: frontend/src/lib/components/trip-new/TripNewEditor.svelte:564 und frontend/src/lib/components/trip-new/TripNewEditor.svelte:1244 (beide `trip.anlegen.speichern`, Handy nicht mehr `aktionen.speichern`).
Confirmation: AC-3 (Textteil), AC-15 — CONFIRMED
  Code reference: frontend/src/lib/components/compare-new/CompareNewEditor.svelte:597 (mobiler Zurück-Label `listen.vergleiche.titel`), frontend/src/lib/components/trip-new/TripNewEditor.svelte:1 ff. i18n: frontend/src/lib/i18n/messages/de/trip.json:230 „Neuer Trip“, frontend/src/lib/i18n/messages/en/trip.json:230 „New trip“; `trip.anlegen.titel` entfernt, keine Restverwendung (grep leer).
Confirmation: AC-13 — CONFIRMED
  Code reference: frontend/src/lib/components/trip-new/TripNewEditor.svelte:1236 und frontend/src/lib/components/compare-new/CompareNewEditor.svelte:694 (mobile EditorStickyFooter unverändert, navClearance-Test `compare_new_footer_nav_clearance` grün).
Confirmation: AC-16 — CONFIRMED
  Code reference: Selektoren `trip-new-save-btn` (frontend/src/lib/components/trip-new/TripNewEditor.svelte:565), `compare-editor-activate` (frontend/src/lib/components/compare-new/CompareNewEditor.svelte:461), `trip-new-continue-etappen` (frontend/src/lib/components/trip-new/TripNewEditor.svelte:705), `compare-editor-continue-orte` (frontend/src/lib/components/compare-new/CompareNewEditor.svelte:548), Fuß `tn-/cm-desktop-footer` über frontend/src/lib/components/shared/anlege-rahmen/AnlegeRahmen.svelte:80.
Confirmation: AC-19, AC-20 — CONFIRMED
  Code reference: docs/adr/0110-hub-kopf-und-anlege-rahmen-ein-baustein.md (Nachtrag „S2 umgesetzt“, kein neues ADR); umgedrehte Tests geändert, nicht gelöscht (`git show --stat 7493cc962`). Nicht abgeschwächte Außer-RED-Änderungen: frontend/src/lib/components/trip-detail/__tests__/f9KatalogAnker.ts:301 (Key `titel` entfernt, `neuer_trip` auf „Neuer Trip“), frontend/src/lib/components/trip-detail/__tests__/trip_hub_sprache.test.ts:103 (Erwartung „Neue Trip anlegen“ -> „Neuer Trip“: Teilstring, aber Golden bleibt über Byte-Gleichheitstest gebunden), frontend/src/lib/components/compare/__tests__/vergleich_hub_sprache.test.ts:307-310 (verschärft: Elternteil muss je Render mindestens 2× vorkommen).
Nur auf Staging belegbar (E2E, Proxy zeigt lokal auf Staging): AC-2, AC-3 (Navigation), AC-6, AC-7, AC-17, AC-18, AC-21. Die Datei frontend/e2e/anlege-rahmen-paritaet.spec.ts ist syntaktisch gültig (`playwright --list`: 36 Tests) und prüft an der Wirkstelle (echter Browser, Request-Zähler `postZaehler`, boundingBox): AR-2/AR-3 (Zähler 0 nach Pfad-/Zurück-Klick), AR-6 Abbrechen UND Menü-Autosave, AR-7 (Abbrechen, Menü, genau 1 POST bei „Briefing aktivieren“). Nicht gelaufen — Risiko: erst /e2e-verify.

Mutations-Gegenprobe (String-Ersetzung, Sicherung im Scratchpad bak/, nach jeder Mutation `cmp` identisch):
| # | Mutation | Ergebnis |
|---|---|---|
| M1 | Hauptaktion frontend/src/lib/components/shared/anlege-rahmen/AnlegeRahmen.svelte:86 `primary`->`accent` | rot (12; Unit-only: AC-8/AC-9 route+vergleich) |
| M2 | Abbrechen-Knopf entfernt/verschoben frontend/src/lib/components/shared/anlege-rahmen/AnlegeRahmen.svelte:82 | rot (15) |
| M4 | de/trip.json „Neuer Trip“->„Neue Trip“ | rot (AC-1, AC-4, Sprache) |
| M5 | Trip `{onCancel}` nicht übergeben frontend/src/lib/components/trip-new/TripNewEditor.svelte:561 | rot (3, nur Golden; Verhalten „kein Autosave“ nur E2E) |
| M7 | Inline-Deckkraft am Weiter frontend/src/lib/components/trip-new/TripNewEditor.svelte:705 | rot (AC-11 Test) |
| M8 | Vergleich `canFinish={true}` | rot (7) |
| M9/M9b | Trip `canFinish` ohne `ready` | rot (5, Golden) |
| M10 | Vergleich cancelHref „/compare“->„/“ | rot (4) |
| M11 | Vergleich testidPrefix cm->tn | rot (10) |
| M12 | Handy „Speichern“ statt „Trip speichern“ frontend/src/lib/components/trip-new/TripNewEditor.svelte:1244 | rot (AC-12-Test) |
| M13 | Vergleich Handy-Zurück-Label alt | rot (5) |
| M14/M15 | Standardwerte/Hinweis im Vergleich immer/nie | rot (2/4) |
| M16 | Vergleich Weiter wieder `quiet` im gesperrten Zustand | rot (3) |
| M17 | ART.vergleich.href -> /trips | rot (7) |
| M19 | TopoBg-Deckkraft | rot (7) |
| M20/M21 | mobile Weiter `accent`->`primary` | rot (1 je, Golden) |
| M6/M22 | Fuß nur für route (Syntaxbruch, ungültige Mutante) | Suite bricht (nicht aussagekräftig); ersatzweise M8/M11 |
| M18 | `e.preventDefault()` in elternKlick frontend/src/lib/components/shared/anlege-rahmen/AnlegeRahmen.svelte:55 entfernt | **grün (694/694)** |
| M23 | `onclick={onFinish}` an Hauptaktion frontend/src/lib/components/shared/anlege-rahmen/AnlegeRahmen.svelte:86 entfernt | **grün (694/694)** |
Betriebsvorfall: zwei Mutationsläufe wurden durch `head`/`timeout` vor dem Restore abgebrochen und lieferten für 1-2 Folgeläufe kontaminierte Zahlen; M7, M9, M12 wurden sauber wiederholt. Endzustand per `cmp` gegen Sicherung byte-gleich, `git diff --stat` (unstaged) leer, `git diff --cached --stat` unverändert 25 Dateien.

Finding F001: M23
  Severity: LOW
  Category: edge_case
  Code reference: frontend/src/lib/components/shared/anlege-rahmen/AnlegeRahmen.svelte:86
  Description: `onclick={onFinish}` an der Hauptaktion kann fehlen, ohne dass ein Unit- oder SSR-Test rot wird (SSR sieht keine Handler).
  Spec requirement: AC-19 — Pflicht-Mutationen müssen von mindestens einem Test gefangen werden; Output/Side effects: Speichern und Anlegen bleiben wirksam.
  Conflict: Die Zusicherung „Klick löst Speichern/Aktivieren aus“ sitzt nur im E2E (AR-7c für den Vergleich; Trip über issue-661-/standardwerte-Specs, nicht in der neuen AR-Datei). Lokal nicht nachweisbar.
  Remediation: Im /e2e-verify gezielt AR-7c plus einen Trip-Speichern-Klick (`trip-new-save-btn`) mit Request-Zähler abwarten; optional im Unit-Test den Rahmen per `mount` mit Klick prüfen.

Finding F002: M18
  Severity: LOW
  Category: edge_case
  Code reference: frontend/src/lib/components/shared/anlege-rahmen/AnlegeRahmen.svelte:53-58
  Description: Ohne `preventDefault` ruft der Pfad-Link `onCancel` UND folgt dem href (`/trips`) — doppelte Navigation; kein Test unterscheidet das (Endzustand identisch, nur potenzielle Autosave-Race beim Link-Folgen).
  Spec requirement: AC-2/AC-6 — Verlassen ohne Speichern.
  Conflict: Falls `intentionalCancel` nicht vor der Link-Navigation wirkt, könnte Autosave dennoch feuern; AR-2 prüft zwar „0 POSTs“, aber nur auf Staging und nur im Endzustand.
  Remediation: Kein Blocker; AR-2 im /e2e-verify zwingend grün sehen.

**Implementierer:**
(Runde 1: kein separater Implementiererkanal; Fixlauf nicht nötig, siehe Runde 2.)

### Runde 2
**Adversary:**
Gezielte Gegenprüfung der Stellen, die der Nutzer erreicht:
- Handy-Pfad: `.cm-desktop`/`.tn-desktop` werden per `display:none !important` ausgeblendet; die neue Inline-Angabe `display:flex` am `.cm-desktop` überstimmt das nicht (`!important` gewinnt) — kein Doppel-Rendering auf 390 px.
- Trip-Fehlerbanner existiert doppelt (Desktop im Rahmen, mobil `tn-mobile`), je eine Ansicht per CSS ausgeblendet — kein sichtbares Duplikat.
- Trip: zusätzlich zur Seiten-`TopoBg` (Zeile 554) trägt der Rahmen eine eigene `TopoBg` im Kopf; optisch doppelte Topo-Schicht, gewollt laut Developer-Meldung (Angleichung an Vergleich), kein Spec-Verstoß.
- Kein hart kodierter Nutzertext im Rahmen; Abbrechen aus `aktionen.abbrechen`, Platzhalter aus `trip.anlegen.kein_name`.
- Goldens f9/f10 wurden neu erzeugt: kein Beweis allein; die Verhaltens-Tests (AC-8/9/11/12) laufen gegen die DOM-Struktur unabhängig vom Golden und wurden von M1u/M7/M12 gefangen.
Ergebnis: keine weiteren Findings. Nur LOW F001/F002 offen, beide in /e2e-verify abzusichern.
**Implementierer:**
(entfällt — keine Fixes nötig.)

## Herkunft der Vorbedingungen

kein Sprachprofil konfiguriert (`precondition_origins.default_lang`)

## Verdict: VERIFIED

(mit zwei LOW-Hinweisen F001/F002). Tests lokal: 694/694 in den benannten Dateien, volle Frontend-Suite 8088 pass / 0 fail / 5 skipped, Wächter-pytest grün. 21 Mutationen, alle bis auf M18 (nahezu äquivalent) und M23 (Handler nur im E2E prüfbar) rot. E2E-only-Punkte (AC-2, AC-3-Navigation, AC-6, AC-7, AC-17, AC-18, AC-21) sind erst auf Staging belegbar; die E2E-Datei sichert sie an der Wirkstelle zu, ist aber nicht gelaufen.

## Geprüfte Dateien

- sha256:b50d590de7198b485ae65cafacb4185548086799a66780cc25168a6daebcbc0f  docs/adr/0110-hub-kopf-und-anlege-rahmen-ein-baustein.md
- sha256:2da65f6d278a7bbeee5f1bb9efad21b9fc6a10c626c57a3348e1c49ef80657ae  frontend/src/lib/components/compare-new/CompareNewEditor.svelte
- sha256:465261b2043d62fae54aa0782544faf531b31568a70c4f3a4587fed531d96743  frontend/src/lib/components/shared/anlege-rahmen/AnlegeRahmen.svelte
- sha256:6e2e4e90caaf79acee4dc2688e777d3190980ac3672f80716e882dce79abc929  frontend/src/lib/components/trip-new/TripNewEditor.svelte

## Prüfbasis

- base: 4df182f706c77467cbf74a3ea944a462c9eab365
- blob:d4e1fd2b83b0ae03af01a6d17202a9abe4b94e35  docs/adr/0110-hub-kopf-und-anlege-rahmen-ein-baustein.md
- blob:715c491e8b3f0160f917057a4a7f4e0a5c246ca1  frontend/src/lib/components/compare-new/CompareNewEditor.svelte
- blob:beb518cce4d080bab79f58960ec2e1a9b02435a1  frontend/src/lib/components/shared/anlege-rahmen/AnlegeRahmen.svelte
- blob:5b50fa823883fc99c6c70cf57c3066371b911c61  frontend/src/lib/components/trip-new/TripNewEditor.svelte
