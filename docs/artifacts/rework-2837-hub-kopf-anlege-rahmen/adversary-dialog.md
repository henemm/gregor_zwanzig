# Adversary Dialog — rework-2837-hub-kopf-anlege-rahmen
Spec: docs/specs/modules/rework_2837_s1_hub_kopf.md
Datum: 2026-11-07 22:44

## Checkliste
- [x] **Input:** `context`, Trip bzw. Vergleich (Name, Kürzel, Status, Region, Profil), Sende- und Kebab-Aktionen als Props.
- [x] **Output:** gleiche Leiste und gleicher Titelblock für beide Arten; sichtbarer Unterschied nur in der Whitelist (Entscheidung 8).
- [x] **Side effects:** keine. „Senden" öffnet nur den Dialog; Kebab-Aktionen bleiben unverändert an die Seiten gebunden.
- [x] **AC-1:** Given ein aktiver Trip und ein aktiver Ortsvergleich im Desktop-Fenster (1440 px) / When der Nutzer jeweils die Detailseite öffnet / Then sitzt „Senden" bei beiden an derselben Stelle in der Leiste ganz oben rechts neben dem Menü, mit schwarzem Hintergrund und weißer Schrift, und kein „Senden" steht mehr neben der Überschrift.
- [x] **AC-2:** Given Trip und Ortsvergleich auf dem Handy (390 px) / When der Nutzer die Detailseite öffnet / Then steht in der Leiste links der Zurück-Pfeil und rechts „Senden" (schwarz, mindestens 44 px hoch) und das Menü, bei beiden an derselben Stelle.
- [x] **AC-3:** Given ein Ortsvergleich im Entwurf und ein Trip im Entwurf / When der Nutzer die Detailseite öffnet / Then steht beim Vergleich „Setup abschließen" genau an der Stelle von „Senden", und beim Trip ist „Senden" an dieser Stelle gesperrt (sichtbar deaktiviert).
- [x] **AC-4:** Given ein Trip mit Kürzel und ein Ortsvergleich / When der Nutzer die Detailseite auf dem Computer öffnet / Then zeigt der Pfad oben „Trips / Kürzel" bzw. „Orts-Vergleiche / Name", der vordere Teil ist ein Link zur jeweiligen Liste, der hintere kein Link, und das Wort „Hub" kommt nirgends mehr vor.
- [x] **AC-5:** Given ein Trip ohne Kürzel / When der Nutzer die Detailseite öffnet / Then zeigt der Pfad „Trips / Name des Trips" (Name statt Kürzel), und ein sehr langer Name wird in der Leiste abgeschnitten statt umzubrechen.
- [x] **AC-6:** Given Trip und Ortsvergleich mit Status aktiv, pausiert und Entwurf / When der Nutzer die Detailseite bei 1440 und 390 px öffnet / Then steht der Status bei beiden als Badge in der Titelzeile neben dem Namen, es gibt keine eigene Statuszeile mehr, und beim Trip steht „Tag x von y" bzw. beim Vergleich die Laufzeit daneben.
- [x] **AC-7:** Given Trip und Ortsvergleich auf dem Handy / When der Nutzer das Menü (drei Punkte) betrachtet / Then sind die Punkte bei beiden senkrecht angeordnet, und ein Tippen öffnet bei beiden dasselbe Aktionsmenü.
- [x] **AC-8:** Given ein Trip mit langem Namen, Status-Badge und Zusatz „Tag x von y" auf dem Handy (390 px) / When der Nutzer die Detailseite öffnet / Then läuft nichts aus dem Bild (kein waagerechtes Scrollen), das Badge bleibt vollständig lesbar, und der Titel darf umbrechen, ohne die Leiste zu verschieben.
- [x] **AC-9:** Given Trip und Ortsvergleich / When der Nutzer den Titelblock vergleicht / Then sind Region-Platzhalter („—" bei leerer Region), Profil und Speicher-Anzeige im Kopf gleich aufgebaut, und die Titelgröße ist bei beiden gleich (38 px).
- [x] **AC-10:** Given ein Trip mit Zählern an den Reitern und ein Ortsvergleich mit Zähler am Orte-Reiter / When der Nutzer die Reiterleiste bei 1440 und 390 px betrachtet / Then sind die Zähler bei beiden grau-neutral (heller Grund, dunkelgraue Schrift), keiner ist orange gefüllt, und der aktive Reiter bleibt orange unterstrichen.
- [x] **AC-11:** Given Trip und Ortsvergleich / When die Seiten gerendert werden / Then gibt es pro Seite genau einen Kopf (ein `SubscriptionHeader`, eine Breadcrumb), und „Senden" öffnet nur den Sende-Dialog und versendet nichts.
- [x] **AC-12:** Given die Umsetzung / When die Doku geprüft wird / Then liegen ADR-0110 („Löst ab": #2284 S1 Entscheidung 6, S2 Entscheidungen 7/8), der Eintrag in `docs/adr/README.md`, die „Abgelöst durch"-Hinweise in beiden alten Specs und der nachgezogene Wortlaut in `design_system.md:64` (Accent = Weiter/Aktiv, Hauptaktion = Ink) vor.
- [x] **AC-13:** Given neue und verschobene Nutzertexte (Breadcrumb-Elternteil, Aria-Labels, Status-Zusatz) / When die Oberfläche auf Deutsch und auf Englisch gerendert wird / Then erscheinen alle Texte über den Katalog in beiden Sprachen, und Protokoll-Token (Kürzel) bleiben unübersetzt.
- [x] **AC-14:** Given die Seiten der Editoren (`/trips/new`, `/compare/new`) und die Profil-Auswahl / When S1 geliefert ist / Then sind sie unverändert (kein Konflikt mit #2792).
- [x] **AC-15:** Given (Abschluss) S1 ist auf Staging / When ein Fresh-Eyes-Prüfer ohne Vorwissen das Screenshot-Paar Hub-Kopf Desktop 1440 px und Mobil 390 px (Trip gegen Vergleich) vergleicht / Then findet er keinen Unterschied außer der fachlichen Whitelist (Datum, Kürzel, km/Hm, „Tag x von y", Kacheln, Orte-Anzahl, Entwurfs-Regel), und das Paar liegt als Kommentar im Epic #2345.

## Dialog

### Runde 1
**Adversary:**
Testlauf (benannte Dateien, volle Ausgabe in docs/artifacts/rework-2837-hub-kopf-anlege-rahmen/adversary-test-output.txt): 291 pass, 0 fail (hub_kopf_seiten_paritaet, issue_491_compare_detail, vergleich_hub_sprache, TripStatusBadge.atomic, tripStatusFinishedDraft, compare_detail, hub_uebersicht_trip_ssr).

Mutations-Gegenprobe (String-Ersetzung, Sicherung im Scratchpad bak/, danach per md5sum identisch zurueckgesetzt, kein git checkout/stash/reset):
- M1 Vergleich zurueck auf CompareStatusPill: 11 Tests rot (u.a. "+page.svelte nutzt im Kopf den geteilten HubStatusBadge", "beide Koepfe tragen den geteilten Baustein", active/paused/draft de+en, Golden hub_seite.de). GEFANGEN an der Wirkstelle (SSR beider Seiten).
- M2 Ton paused warning -> info im HubStatusBadge: 3 rot ("paused (de/en): gleiche Pill (Ton warning ...)", "AC-3: paused bleibt auf warning gemappt"). GEFANGEN.
- M3 data-outlined entfernt: 7 rot (active/paused/draft de+en, "AC-2: Pill hat data-outlined"). GEFANGEN.
- M4 profileLabel beim Trip entfernt (TripHeader): 2 rot ("route (de/en): direkt nach dem Region-Stift steht Trekking"). GEFANGEN.
- M5 Wortschluessel paused -> listen.status.paused im geteilten Baustein: 3 rot (paused de/en, Golden hub_seite.de). GEFANGEN. Zweite Variante M5b (nur der Trip-Wrapper mappt paused auf archived): 2 rot (paused de/en). GEFANGEN.
- M6 data-hub-status-badge entfernt: 4 rot (u.a. "beide Koepfe tragen den geteilten Baustein", AC-6 route+vergleich). GEFANGEN.
- M7 Vergleichsseite uebergibt festen Status active: 5 rot (paused/draft de+en, Golden). GEFANGEN.
Alle sieben Familien rot, keine ueberlebende Mutation.

Wirkstelle: Die Tests rendern die echten Seiten routes/trips/[id] und routes/compare/[id] serverseitig und vergleichen Trip gegen Vergleich im selben Zustand (aktiv, pausiert, Entwurf; de und en) mit festem erwartetem Ton und Wort aus trip.status.*. Das ist die Stelle, an der die Zusicherung wirkt.

Regressionen: CompareStatusPill bleibt unveraendert, wird nur noch in Liste/f10Pruefstand genutzt. testid trip-detail-status-badge bleibt (TripStatusBadge ist duenner Wrapper), e2e trip-detail-actions, issue-336-status-dedup, compare-hub-fidelity-s8c lesen textContent und bleiben stimmig. data-status steht jetzt auch im Trip-Kopf; e2e hub-versand-inline-bearbeiten nutzt [data-status]:visible nur fuer kind vergleich (Werte active/paused unveraendert). Wort-Gleichheit DE/EN: beide Koepfe nutzen ueber HubStatusBadge dieselben Schluessel trip.status.*; Tests laufen je de und en.

**Implementierer:** (kein Einwand, keine Findings)

### Runde 2
**Adversary:**
Zweiter Durchgang gezielt auf Luecken:
1. HP-15 (E2E, lief nicht lokal): misst am geteilten Merkmal data-hub-status-badge (nicht an der Huelle) im Zustand pausiert Trip gegen Vergleich per getComputedStyle (text-transform, Schrift, Farben, Rahmen) plus Wort und Profil per following-sibling::span[1] des Region-Stifts. Das passt zum Markup SubscriptionHeader.svelte (Profil-span direkt nach dem Stift). Bewertung: misst das Richtige. Einschraenkung (LOW, F001): nur Zustand pausiert, und die Box-Groesse (Breite/Hoehe) wird nicht verglichen.
2. Wrapper: der Vergleich setzt das Schild in span.flex-shrink-0, der Trip direkt in hub-kopf-status. Kein belegter Unterschied, nur nicht gemessen (in F001 enthalten).
3. Zusatz neben dem Schild (Trip "Tag x von y", Vergleich Laufzeit-Hinweis) liegt auf der Whitelist.
4. Spec-Changelog 2026-11-07 dokumentiert die Abweichung von "unveraendert wiederverwendet" und benennt AC-15 als bindend; CompareStatusPill unveraendert.
5. Mutationsdateien alle per md5sum identisch zur Sicherung.

**Implementierer:** (nichts zu erwidern)

**Findings:**
Finding:
  ID: F001
  Severity: LOW
  Category: edge_case
  Code reference: frontend/e2e/hub-kopf-paritaet-compare-trip.spec.ts:253
  Description: HP-15 vergleicht das Status-Schild nur im Zustand pausiert und nur ueber Stil-Eigenschaften, nicht ueber Breite/Hoehe; Ton aktiv/Entwurf ist nur im SSR-Test (data-tone) gesichert, nicht als berechnete Farbe.
  Spec requirement: AC-15 — kein sichtbarer Unterschied ausser Whitelist
  Conflict: Ein CSS-Unterschied, der nur aktiv/Entwurf oder die Box-Groesse betrifft, bliebe unentdeckt. Kein Unterschied belegt.
  Remediation: HP-15 ueber die drei Zustaende laufen lassen und boundingBox-Groesse mitvergleichen.

**Confirmations:**
Confirmation:
  AC: AC-6
  Code reference: frontend/src/lib/components/shared/hub-kopf/__tests__/hub_kopf_seiten_paritaet.test.ts:192
  Evidence: Status genau einmal als geteiltes Schild in der Titelzeile (hub-kopf-status) bei beiden Arten; Mutationen M1, M6, M7 rot. Quellen: frontend/src/lib/components/shared/hub-kopf/HubStatusBadge.svelte:41, frontend/src/lib/components/trip-detail/TripStatusBadge.svelte:19, frontend/src/routes/compare/[id]/+page.svelte:359.
  Status: CONFIRMED
Confirmation:
  AC: AC-9
  Code reference: frontend/src/lib/components/trip-detail/TripHeader.svelte:84
  Evidence: profileLabel wird berechnet und an HubKopf uebergeben (TripHeader.svelte:156); Test hub_kopf_seiten_paritaet.test.ts:225 (de+en); Mutation M4 rot. Vergleichsseite: frontend/src/routes/compare/[id]/+page.svelte:174. Weitere Pruefstellen: frontend/src/lib/components/compare/__tests__/issue_491_compare_detail.test.ts:57, frontend/src/lib/components/compare/__tests__/vergleich_hub_sprache.test.ts:127, frontend/src/lib/components/trip-detail/TripStatusBadge.atomic.test.ts:26, frontend/src/lib/components/trip-detail/__tests__/tripStatusFinishedDraft.test.ts:27.
  Status: CONFIRMED
Confirmation:
  AC: AC-15
  Code reference: frontend/e2e/hub-kopf-paritaet-compare-trip.spec.ts:253
  Evidence: Trip und Vergleich rendern identisches Schild (Ton, Outline, Wort, Attribute); E2E HP-15 misst Trip gegen Vergleich (nicht lokal gelaufen, CI). Staging-Hilfskonfiguration frontend/playwright.2837.staging.config.ts:1 (nur zitiert, nicht bewertet).
  Status: CONFIRMED
Confirmation:
  AC: AC-1 bis AC-14
  Code reference: frontend/src/lib/components/shared/hub-kopf/__tests__/hub_kopf_seiten_paritaet.test.ts:84
  Evidence: Verweis auf fruehere Runde (adversary-dialog-s1-runde1.md, VERIFIED); der Fix beruehrt nur Status-Schild und Profil-Label, Testlauf 291 gruen.
  Status: CONFIRMED
Confirmation:
  AC: AC-15
  Code reference: frontend/src/lib/components/shared/hub-kopf/HubStatusBadge.svelte:41
  Evidence: Gemeinsames Pill mit data-outlined, data-status, data-hub-status-badge; Mutationen M2 (Ton), M3 (data-outlined), M5 (Wortschluessel), M6 (Merkmal) alle rot.
  Status: CONFIRMED
Confirmation:
  AC: AC-15
  Code reference: frontend/src/lib/components/trip-detail/TripStatusBadge.svelte:19
  Evidence: Duenner Wrapper um HubStatusBadge, testid trip-detail-status-badge bleibt; Mutation Wrapper mappt paused auf archived rot; E2E-Specs mit dieser testid lesen textContent und bleiben stimmig.
  Status: CONFIRMED
Confirmation:
  AC: AC-6
  Code reference: frontend/src/routes/compare/[id]/+page.svelte:359
  Evidence: Vergleich rendert HubStatusBadge mit seinem Status; Mutationen M1 (zurueck auf CompareStatusPill) und M7 (fester Status active) rot.
  Status: CONFIRMED
Confirmation:
  AC: AC-15
  Code reference: frontend/src/lib/components/compare/__tests__/issue_491_compare_detail.test.ts:57
  Evidence: Test verlangt HubStatusBadge in +page.svelte und kein CompareStatusPill; bei Mutation M1 rot.
  Status: CONFIRMED
Confirmation:
  AC: AC-13
  Code reference: frontend/src/lib/components/compare/__tests__/vergleich_hub_sprache.test.ts:126
  Evidence: Englischer Vergleichs-Hub nutzt Woerter aus trip.status.*; bei M1, M5 und M7 rot (Golden hub_seite.de und EN-Test).
  Status: CONFIRMED
Confirmation:
  AC: AC-15
  Code reference: frontend/src/lib/components/trip-detail/TripStatusBadge.atomic.test.ts:26
  Evidence: Prueft Ton-Zuordnung und data-outlined am gemeinsamen Baustein; M2 und M3 rot.
  Status: CONFIRMED
Confirmation:
  AC: AC-15
  Code reference: frontend/src/lib/components/trip-detail/__tests__/tripStatusFinishedDraft.test.ts:27
  Evidence: Liest TONE_MAP/LABEL_MAP aus HubStatusBadge (Entwurf, Fertig); Gesamtlauf 291 gruen.
  Status: CONFIRMED
Confirmation:
  AC: AC-15
  Code reference: frontend/playwright.2837.staging.config.ts:1
  Evidence: Ungetrackte Staging-Hilfsdatei, nur zitiert, nicht bewertet.
  Status: CONFIRMED

## Herkunft der Vorbedingungen

kein Sprachprofil konfiguriert (`precondition_origins.default_lang`).

## Verdict

═══════════════════════════════════════
VERDICT: VERIFIED
═══════════════════════════════════════

Mit LOW-Hinweis F001. Tests 291 pass, 0 fail; 8 Mutationen, alle gefangen.

## Geprüfte Dateien

- sha256:69b69f1a355107b5f85e3b1c3a1492122126879dc98cd3271ff8a4a8bf0a8b1e  frontend/e2e/hub-kopf-paritaet-compare-trip.spec.ts
- sha256:e17dd773e6b345dbbadc2743053ad4a53903ccf56404880fd05a8a373961bde9  frontend/playwright.2837.staging.config.ts
- sha256:d719fd539a10676cc62b1dfd4abf83aa7b975e38f0cf3879d4fdbf3206fb2635  frontend/src/lib/components/compare/__tests__/issue_491_compare_detail.test.ts
- sha256:23de9f527e6490a1276d1fad9deef6934a28e5c0312a1a98a6a6550e70c054ea  frontend/src/lib/components/compare/__tests__/vergleich_hub_sprache.test.ts
- sha256:725ecb4be7f93f6efaa0085cc94b185ee53e188035836355ec21fde52f5fff36  frontend/src/lib/components/shared/hub-kopf/HubStatusBadge.svelte
- sha256:29b1f2198ebe2d8974accab790750556e465e387be7aa03fd8c4bca8772985ff  frontend/src/lib/components/shared/hub-kopf/__tests__/hub_kopf_seiten_paritaet.test.ts
- sha256:464c5a243b81f9e962cfd36a813308735a65def2f59eb38c7f83ba4a0a5f585b  frontend/src/lib/components/trip-detail/TripHeader.svelte
- sha256:4c48ded7a16d0f555bb68c747477cefefa949caedb18dff3c78536c2b288474a  frontend/src/lib/components/trip-detail/TripStatusBadge.atomic.test.ts
- sha256:afc2f783b8139f390a36796b325f1ee5afcb5cd3f33159cf7d3529ff6e638bab  frontend/src/lib/components/trip-detail/TripStatusBadge.svelte
- sha256:55949758f29ced247c938b6026b1737ee7a463660be113e26a45af120a024cb6  frontend/src/lib/components/trip-detail/__tests__/tripStatusFinishedDraft.test.ts
- sha256:fa66083de6776f3e1c726a4119b9e2c85c0dd1fa552a2f3977b9dfe234a94397  frontend/src/routes/compare/[id]/+page.svelte

## Prüfbasis

- base: 22f4cd7fa566a486655d27b5dcfc362d10bf3d66
- blob:472c0750f874a8b9450a51e16ff5aa07a1a4c2f3  frontend/e2e/hub-kopf-paritaet-compare-trip.spec.ts
- blob:ec2ff258526b5c6388aa63e3c217b2566abf3579  frontend/playwright.2837.staging.config.ts
- blob:b0bb35f60d6866a1e7d0b7a81a00dbfce24c039d  frontend/src/lib/components/compare/__tests__/issue_491_compare_detail.test.ts
- blob:2b1ea4b39b50a320e5f2565a6109196fd7fc60f2  frontend/src/lib/components/compare/__tests__/vergleich_hub_sprache.test.ts
- blob:9e1213ec10e9a069be719d8ba517629565caaf6b  frontend/src/lib/components/shared/hub-kopf/HubStatusBadge.svelte
- blob:bf139cd6f19c2c63b3f9d11b80120d7c224506e5  frontend/src/lib/components/shared/hub-kopf/__tests__/hub_kopf_seiten_paritaet.test.ts
- blob:1b967d8b893094adaa13577ccc35a25bc3ea5e59  frontend/src/lib/components/trip-detail/TripHeader.svelte
- blob:a369d291b60afdc7517752a3771deb8ecc0adba9  frontend/src/lib/components/trip-detail/TripStatusBadge.atomic.test.ts
- blob:21e85772a1d11bdacde9b80530933e6b91a0e6d7  frontend/src/lib/components/trip-detail/TripStatusBadge.svelte
- blob:7f7220194aa6e8c2eb13d608d4d89fc7c2d04a6e  frontend/src/lib/components/trip-detail/__tests__/tripStatusFinishedDraft.test.ts
- blob:ec2ebb9ebbbe1046b5e69f0989ca64e341cab740  frontend/src/routes/compare/[id]/+page.svelte
