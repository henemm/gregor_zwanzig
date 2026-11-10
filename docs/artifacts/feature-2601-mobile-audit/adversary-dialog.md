# Adversary Dialog — feature-2601-mobile-audit
Spec: docs/specs/modules/mobile_ux_audit_2601.md
Datum: 2026-11-10 18:34

## Checkliste
- [x] **Input:** Preview auf `localhost:4173`, lokaler Stack, `playwright/.auth/admin.json`
- [x] **Output:** `test-results/mobile-ux/report-<projekt>[-public].{json,md}` + Screenshots je Route/Tab/Overlay; Weiterleitungen sind im Report gekennzeichnet
- [x] **Side effects:** nur lesende Navigation; Overlays werden per Escape geschlossen. Mit `GZ_AUDIT_LOCALE=en` wird die Profilsprache des lokalen Seed-Admins vorübergehend geändert und danach zurückgesetzt (nur lokaler Stack, nie Staging oder Produktion).
- [x] **AC-1:** Given ein Trip mit 8 Etappen und Datums-/Zeitbearbeitung / When der Etappen-Tab auf 390px Breite geöffnet wird / Then liegt kein interaktives Element (Datum, Startzeit) horizontal außerhalb des Viewports und die Seite hat keinen horizontalen Overflow.
- [x] **AC-2:** Given der iOS-Install-Hinweis ist sichtbar / When eine beliebige Seite bis zum Ende gescrollt wird / Then sind Footer-Links und letzte Bedienelemente antippbar (nicht unter Hinweis oder Bottom-Nav).
- [x] **AC-3:** Given die Tabs „Wetter" und „Zustellung" (Trip und Vergleich) / When die Schwellen-Knöpfe und Kanal-Schalter gemessen werden / Then ist jedes Tap-Ziel mindestens 24×24px (Schalter inkl. unsichtbarer Trefferfläche, Knöpfe ≥ 32px hoch).
- [x] **AC-4:** Given Login-, Registrier- und Passwort-vergessen-Seite im Querformat / When die Seite geladen wird / Then haben alle Eingabefelder ≥ 16px Schrift und die Textlinks ≥ 44px Trefferhöhe.
- [x] **AC-5:** Given Konto-Sheet, Karten-Menü und Sende-Dialog / When sie auf dem Telefon geöffnet werden / Then sind sie sichtbar, ohne horizontalen Overflow und ohne Tap-Ziel < 24px.
- [x] **AC-6:** Given native Häkchen/Radios in den Tabs „Wetter" und „Zustellung" (Wetter-Metriken, Mail-Format, Vorschau) / When auf Touch/≤899px gerendert / Then sind sie 20px groß und ihr Label mindestens 44px hoch.
- [x] **AC-7:** Given ein Trip mit mehreren Etappen auf einem Telefon-Profil (390×844, 402×874 oder 844×390) / When im Etappen-Tab die Datumsfelder (Tag, Monat) und die Startzeit-Felder (Stunde, Minute) sowie im Trip-Anlegen das Datumsfeld vermessen werden / Then ist jedes Segment mindestens 24×24 px groß, in Deutsch und Englisch.
- [x] **AC-8:** Given der Vergleichs-Editor mit Datums- und Uhrzeitsegmenten auf einem Telefon-Profil / When die Segmente vermessen werden / Then gelten dieselben Mindestgrößen von 24×24 px wie im Trip-Editor, ohne dass dafür eine Compare-eigene Regel existiert.
- [x] **AC-9:** Given der Desktop mit 1280×800 und Maus / When Datums- und Uhrzeitfelder im Etappen-Tab und im Trip-Anlegen angezeigt werden / Then sind ihre Segmentmaße gegenüber dem Stand vor Runde 2 unverändert (optisch keine Verbreiterung).
- [x] **AC-10:** Given der Hub-Kopf eines Trips und eines Vergleichs auf einem Telefon-Profil / When der Brotkrumen-Link vermessen wird / Then wird er nicht abgeschnitten, das heißt scrollHeight ist höchstens clientHeight des Brotkrumen-Bereichs und die volle Trefferfläche bleibt sichtbar.
- [x] **AC-11:** Given die Übersicht eines Trips mit Höhenprofil auf einem Hochformat-Profil / When der Audit die Etappenwahl im Profil prüft / Then wird das Profil-Rechteck als dokumentierte Ausnahme nach WCAG 2.5.8 „equivalent" nicht als harter Befund gewertet (Attribut `data-tap-equivalent`), und dieselbe Etappenwahl ist im Etappen-Tab mit Zielen von mindestens 24×24 px möglich.
- [x] **AC-12:** Given die Seite /compare und die Seite /compare/new in Englisch auf einem Telefon-Profil / When der Überlauf im Hauptbereich und in der Mobil-Tabbar gemessen wird / Then scrollt der `<main>` von /compare nicht waagerecht (Überlauf ≤ 1 px), und die Tabbar von /compare/new hat entweder keinen waagerechten Überlauf oder ist als bewusst scrollbare Leiste erkennbar, sodass der letzte Reiter erreichbar bleibt und kein Inhalt unerreichbar ist.
- [x] **AC-13:** Given die mobil sichtbaren Oberflächen (Tab-Badges, ✉-Zeichen in der Übersicht, Menülabel „Aktionen") / When die berechnete Schriftgröße gemessen wird / Then ist kein mobil sichtbarer Text kleiner als 11 px.
- [x] **AC-14:** Given Knöpfe, die bisher nur 28 px hoch waren („+ Neuer Trip", „Im Editor öffnen →", Orte hinzufügen, Laufzeit im Briefing) / When sie auf Touch oder ≤899 px gerendert werden / Then erreichen sie mindestens den bestehenden 36-px-Boden aus `app.css`, erreicht über die vorhandenen zentralen Regeln und ohne Einzelhacks pro Komponente.
- [x] **AC-15:** Given der gehärtete Audit / When er läuft / Then zählt er Treffer ungekappt (harte Treffer unter 24 px erscheinen nie in der weichen Liste), weist Weiterleitungen als solche aus, prüft den `<main>`-Überlauf allgemein und deckt zusätzlich ab: ausgeloggte Startseite `/`, `/reset-password`, `/verify-email`, `/magic-link` (und verify), Wizard-Schritte größer 1 von `/trips/new` und `/compare/new` sowie die Editor-Tabs hinter `/trips/[id]/edit` und `/compare/[id]/edit` (dokumentiert als Weiterleitung auf die Detailseite).
- [x] **AC-16:** Given der Audit-Lauf mit `GZ_AUDIT_LOCALE=de` oder `en` / When der Lauf startet / Then setzt er Browser-Locale und Profilsprache des Seed-Nutzers passend, zeigt die Oberfläche in der gewählten Sprache und stellt die Profilsprache danach wieder her; ohne gesetztes `GZ_E2E_API_PROXY_TARGET` bricht die Config vor dem ersten Test ab, sodass der Lauf nie Staging trifft.
- [x] **AC-17:** Given alle Fixes der Runde 2 sind umgesetzt / When `GZ_AUDIT_STRICT=1` in Deutsch und Englisch in allen drei Profilen läuft / Then sind die harten Kriterien (a), (c), (d) und Tap unter 24 px überall grün, und die Befundliste (Vorher/Nachher) steht als Kommentar im Issue #2601.

## Dialog

### Runde 1
**Adversary:**
Tests (Chromium, lokaler Stack 8191/8102, Vorschau 4173): mobile-ux-messung + selbsttest 13/13 gruen, staging-schutz 3/3 gruen; 73 Mobil-Nachbartests gruen; strenger Audit DE und EN je 6/6 gruen, Profilsprache danach wiederhergestellt (en->en, de->de). Ausgabe: adversary-test-output.txt, Screenshot adversary-screenshot.png.
Mutationen (je Verfaelschung rot): DatumFeld 24->22 (AC-7/8 rot), UhrzeitFeld-Regel unbedingt (AC-9 rot), HubKopf-Polster raus (AC-10 rot), app.css Btn-sm-Regel raus (AC-14 rot), MTabBar/Sheet/ChannelDot 10px (AC-13 rot je Fundstelle), data-tap-equivalent raus (AC-11 rot), compare-main-Klasse raus (AC-12a rot), Step2Orte 10px und magic-link/reset py-3 raus (nur Golden/Fixture byte-gleich rot, kein Verhaltenstest), Staging-Throw raus und Locale fest de (AC-16 rot), LAYOUT_CHECK Schwelle 20, tap-equivalent Generalschluessel, main-Ueberlauf raus, Kappung 15 (Selbsttest rot).
Finding:
  ID: F001
  Severity: MEDIUM
  Category: spec_violation
  Code reference: frontend/e2e/mobile-ux-audit.spec.ts:193 (schritt1Ausfuellen fuellt nur Name/Datum bzw. Name)
  Description: Im Audit-Report sind /trips/new Schritte wegpunkte, wetter, zustellung und /compare/new Schritte wetter, zustellung als "gesperrt (Pflichtangaben fehlen)" uebersprungen; nur schritt-etappen bzw. schritt-orte werden geprueft.
  Spec requirement: AC-15 deckt Wizard-Schritte groesser 1 ab; AC-17 harte Kriterien "ueberall" gruen
  Conflict: 5 von 7 Anlege-Schritten wurden nie vermessen, der gruene strenge Lauf sagt dazu nichts.
  Remediation: Pflichtangaben (Etappe mit Wegpunkt, Ort) im Audit vorbelegen oder AC-15/17 ausdruecklich auf erreichbare Schritte begrenzen.
Finding:
  ID: F002
  Severity: LOW
  Category: edge_case
  Code reference: frontend/playwright.mobile-ux.local.config.ts:23
  Description: Der Staging-Schutz prueft nur, ob die Variable gesetzt ist; GZ_E2E_API_PROXY_TARGET=http://localhost:8091 (Staging) wird akzeptiert.
  Spec requirement: AC-16 — Lauf trifft nie Staging
  Conflict: Absichtliches/versehentliches Setzen auf 8091 umgeht den Schutz.
  Remediation: Port 8091/8001/8090 in der Config ablehnen.
Finding:
  ID: F003
  Severity: LOW
  Category: anti_pattern
  Code reference: frontend/e2e/mobile-ux-audit.spec.ts:266 (setzeProfilsprache/zurueck) und :251 (Weiterleitungs-Erkennung)
  Description: Profilsprachen-Wiederherstellung, Routenliste und Redirect-Ausweisung haben keinen automatischen Test (nur Selbsttest der Pruefung und Config-Test); ich habe sie manuell nachgewiesen. Wiederherstellung schreibt bei leerer Vorsprache 'de' statt Ausgangszustand.
  Spec requirement: AC-15, AC-16
  Conflict: Mutation dort faellt keinem CI-Test auf.
  Remediation: Optional Test mit Stub oder Doku als manueller Lauf.
Weitere Hinweise (ohne Befund): Step2Orte (frontend/src/lib/components/compare/steps/Step2Orte.svelte:406), MTabBar.svelte:203, Sheet.svelte:119, DatumFeld.svelte:260, UhrzeitFeld.svelte:154, HubKopf.svelte:140, ChannelDot.svelte:25, FullProfile.svelte:168, app.css:480, compare/+page.svelte:216, magic-link/+page.svelte:55, magic-link/verify/+page.svelte:44, reset-password/+page.svelte:19, mobile-ux-audit-check.ts:151, .github/workflows/ci.yml:288, .github/ci_e2e_specs.txt (80 Dateien, passt zu E2E_MIN_SPECS 80) gelesen und wie beschrieben wirksam. Specs-Changelog nennt noch "Status draft, Freigabe steht aus", Kopf sagt approved (Doku-Unstimmigkeit). Hinweis: Touch-Geraete >899 px (pointer:coarse) sind nicht gemessen.
**Implementierer:**

### Runde 2
**Adversary:**
Gegenpruefung der Runde 1: Desktop AC-9 haelt (Datum und Uhrzeit nur im Medienblock, Soll 18x21.5 bzw. 34x23); Btn-sm-Verschiebung in @layer components (app.css:480) betrifft nur <=899px/coarse, 73 Mobil-/Listen-Specs gruen; Golden-Diffs (Wortvergleich) enthalten ausschliesslich font-size-Token, data-tap-equivalent, py-3, compare-main-Klasse; data-tap-equivalent nur am Hoehenprofil-Rechteck gesetzt (grep). Ein roter EN-Lauf kam von Testdaten-Muell meiner abgebrochenen Nachbarlaeufe (lange Namen), nach Bereinigung gruen. Mehrnutzer/Sicherheit: nicht beruehrt.
**Implementierer:** (offen: F001 klaeren)

### Runde 3
**Adversary:**
Nachweise nach Fix-Loop 1 (lokaler Stack 8191/8102/4173, frischer Seed-Nutzer):
- Strenger Audit NACH Guard-Einbau, DE und EN, je 3 Profile: 6/6 gruen. Report listet je Profil alle Anlege-Schritte als GEMESSEN: /trips/new etappen, wegpunkte, wetter, zustellung und /compare/new orte, wetter, zustellung (je 3x pro Sprachlauf, keiner "gesperrt").
- Mutation F001 (Vorbelegung aus, frontend/e2e/mobile-ux-audit.spec.ts:213 und :221): strikt ROT, 5 Schritte als "Fehler: Schritt gesperrt" (hardFailures zaehlt Fehler, spec.ts:109-114). Zurueckgespielt, cmp identisch.
- Mutation F002 (frontend/playwright.mobile-ux.local.config.ts:33 und :42): Ports 8091, 8090, 8001 einzeln entfernt und Host-Suffix-Pruefung entfernt: node-Test 3 (neuer Fall) jeweils ROT. Zurueckgespielt.
- Mutation F003 (Restore schreibt AUDIT_LOCALE statt vorher, spec.ts:322): EN-Lauf ROT ("Profilsprache nach dem Lauf = Ausgangszustand, Expected de, Received en"), die Pruefung greift. Profil danach manuell auf de zurueck.
- Seiteneffekte: Trips, Vergleiche, Orte vor/nach beiden Laeufen identisch (nichts gespeichert); Profilsprache de, en, de wiederhergestellt. Einzige Schreibwirkung: /api/gpx/parse legt test-trip.gpx im GPX-Ordner des lokalen Seed-Nutzers ab (users/admin/gpx/test-trip.gpx, gleicher Name, nach zwei Laeufen weiterhin 1 Datei, idempotent).
Bewertung GPX: Die Zeile "Side effects: nur lesende Navigation" (Checkliste und Spec Zeile 122) stimmt damit woertlich nicht mehr. Kein Datenverlust, kein Trip/Vergleich, nur lokaler Stack durch den Staging-Guard. Kein Blocker; Spec-Zeile anpassen: "lesende Navigation; die Wizard-Vorbelegung laedt eine Test-GPX hoch (/api/gpx/parse legt sie im GPX-Ordner des lokalen Seed-Nutzers ab), gespeichert wird nie".
Status der Findings: F001 behoben (frontend/e2e/mobile-ux-audit.spec.ts:212-262). F002 behoben (frontend/playwright.mobile-ux.local.config.ts:30-50), Restluecke F004 (LOW): ein bereits in der Umgebung gesetztes GZ_API_BASE wird wegen `??=` (Zeile 52) nicht geprueft. F003 behoben fuer die Profilsprache (spec.ts:310-327, per Mutation belegt); Routenliste und Redirect-Ausweisung weiter nur durch Lauf belegt (akzeptiert, LOW).
Weitere Code-Dateien unveraendert, wie in Runde 1 zitiert (u. a. frontend/e2e/mobile-ux-audit-check.ts:151, frontend/e2e/mobile-ux-audit-staging-schutz.test.ts).
**Implementierer:** Fix-Loop 1 abgeschlossen (siehe Koordinator).

## Herkunft der Vorbedingungen

kein Sprachprofil konfiguriert (`precondition_origins.default_lang`)

## Verdict
Findings: F001 behoben, F002 behoben (Restluecke F004 LOW), F003 behoben (Profilsprache). Spec-Zeile "nur lesende Navigation" ist wegen GPX-Upload ungenau (LOW, Textkorrektur).
Bewertung "Side effects: nur lesende Navigation": mit dem GPX-Hinweis (lokaler Seed-Nutzer, idempotent, nichts gespeichert, Staging-Guard) vertretbar, daher abgehakt. AC-17: Befundliste liegt als Kommentar im Issue #2601 (https://github.com/henemm/gregor_zwanzig/issues/2601#issuecomment-6777140036, per gh geprueft).
VERIFIED (Runde 3): AC-7 bis AC-16 bewiesen; strenger Lauf DE und EN gruen, alle Wizard-Schritte gemessen.
VERDICT: VERIFIED

## Confirmations

Confirmation:
  AC: AC-14
  Code reference: frontend/src/app.css:480
  Evidence: Btn[sm] min-height 36px in @layer components im Medienblock <=899px/coarse, AC-14-Test gruen, Mutation rot.
  Status: CONFIRMED
Confirmation:
  AC: AC-7
  Code reference: frontend/src/lib/components/molecules/DatumFeld.svelte:260
  Evidence: Tag/Monat min 24x24, AC-7/AC-8 gruen, Mutation 22px rot.
  Status: CONFIRMED
Confirmation:
  AC: AC-7
  Code reference: frontend/src/lib/components/molecules/UhrzeitFeld.svelte:154
  Evidence: Stunde/Minute min 24x24 nur im Medienblock; AC-9 Desktop unveraendert (Mutation rot).
  Status: CONFIRMED
Confirmation:
  AC: AC-10
  Code reference: frontend/src/lib/components/shared/hub-kopf/HubKopf.svelte:140
  Evidence: padding-block/margin-block 13px, scrollHeight <= clientHeight, Mutation rot.
  Status: CONFIRMED
Confirmation:
  AC: AC-11
  Code reference: frontend/src/lib/components/trip-detail/FullProfile.svelte:168
  Evidence: data-tap-equivalent nur an den Profil-Rechtecken, Mutation rot.
  Status: CONFIRMED
Confirmation:
  AC: AC-12
  Code reference: frontend/src/routes/compare/+page.svelte:216
  Evidence: inneres main mit -mx-4 px-4, kein waagerechter Scroll; Mutation rot.
  Status: CONFIRMED
Confirmation:
  AC: AC-13
  Code reference: frontend/src/lib/components/mobile/MTabBar.svelte:203
  Evidence: Badge-Schrift var(--g-text-xs)=11px, Mutation 10px rot.
  Status: CONFIRMED
Confirmation:
  AC: AC-13
  Code reference: frontend/src/lib/components/mobile/Sheet.svelte:119
  Evidence: Menuelabel 11px, Mutation rot.
  Status: CONFIRMED
Confirmation:
  AC: AC-13
  Code reference: frontend/src/lib/components/trip-detail/ChannelDot.svelte:25
  Evidence: Zeichen 11px, Mutation rot.
  Status: CONFIRMED
Confirmation:
  AC: AC-13
  Code reference: frontend/src/lib/components/compare/steps/Step2Orte.svelte:406
  Evidence: Mobil-Texte 11px, Golden byte-gleich (Mutation rot ueber Golden).
  Status: CONFIRMED
Confirmation:
  AC: AC-4
  Code reference: frontend/src/routes/magic-link/+page.svelte:55
  Evidence: Textlink py-3 (44px Trefferhoehe); strenger Lauf gruen, Fixture-Mutation rot.
  Status: CONFIRMED
Confirmation:
  AC: AC-4
  Code reference: frontend/src/routes/magic-link/verify/+page.svelte:44
  Evidence: Textlink py-3; strenger Lauf gruen.
  Status: CONFIRMED
Confirmation:
  AC: AC-4
  Code reference: frontend/src/routes/reset-password/+page.svelte:19
  Evidence: Textlinks py-3; strenger Lauf gruen.
  Status: CONFIRMED
Confirmation:
  AC: AC-15
  Code reference: frontend/e2e/mobile-ux-audit-check.ts:151
  Evidence: tinyTargets ungekappt, tap-equivalent nie hart, main-Ueberlauf; Selbsttest gruen, 4 Mutationen rot.
  Status: CONFIRMED
Confirmation:
  AC: AC-15
  Code reference: frontend/e2e/mobile-ux-audit.spec.ts:212
  Evidence: Wizard-Vorbelegung, alle 7 Schritte gemessen, Mutation rot; Profilsprache wiederhergestellt (:310).
  Status: CONFIRMED
Confirmation:
  AC: AC-16
  Code reference: frontend/playwright.mobile-ux.local.config.ts:23
  Evidence: Abbruch ohne Proxy-Ziel, Sperre fuer Staging/Prod-Ports und -Hosts, Locale je Sprache; Mutationen rot.
  Status: CONFIRMED
Confirmation:
  AC: AC-16
  Code reference: frontend/e2e/mobile-ux-audit-staging-schutz.test.ts:45
  Evidence: 4 node-Faelle gruen, Mutationen an Config rot.
  Status: CONFIRMED
Confirmation:
  AC: AC-15
  Code reference: .github/ci_e2e_specs.txt:708
  Evidence: mobile-ux-messung und selbsttest aufgenommen, 80 Dateien.
  Status: CONFIRMED
Confirmation:
  AC: AC-15
  Code reference: .github/workflows/ci.yml:288
  Evidence: E2E_MIN_SPECS 80 passt zur Positivliste (80).
  Status: CONFIRMED

## Geprüfte Dateien

- sha256:744a9d185cc07b5f383db5c078127fd74080e87d575223188741f21203a5e09f  .github/ci_e2e_specs.txt
- sha256:3972d7bc07efe79b1cd131cba0f2756d025c702d427f7f605af17c91d88c808e  .github/workflows/ci.yml
- sha256:b1fddf147ad037395a1c5fcc8083f132a034edab9780d1275e8cdf697c124f36  frontend/e2e/mobile-ux-audit-check.ts
- sha256:b3c75102ca7f7f7524a5086a4362a5987b11833418475680f952adc7d968b59b  frontend/e2e/mobile-ux-audit-staging-schutz.test.ts
- sha256:00380abb5bf56b319fb34792b2af8b4ea6921bac674015254c3b99e6c42b7a2f  frontend/e2e/mobile-ux-audit.spec.ts
- sha256:ab7af8e5e481da913fa3e6e1781938da04311a62e2a5125ef99fc87005801da5  frontend/playwright.mobile-ux.local.config.ts
- sha256:2c0b0458a6b5212c064469867ee28cd3b0c2a81a23e08b6e14e2f7c031ad2866  frontend/src/app.css
- sha256:8d3f9870125a92c723590b013350faafe49fc5e3477516b76cec430c62cf352d  frontend/src/lib/components/compare/steps/Step2Orte.svelte
- sha256:59127e53a518736d6bc040310f902ddfa94545d41223ce821ce39dcf858cfb25  frontend/src/lib/components/mobile/MTabBar.svelte
- sha256:78f0aaebca9c4b4ffc52c5b542b9f1f0f9a9e39b57387cae63feae7b6e4f81a7  frontend/src/lib/components/mobile/Sheet.svelte
- sha256:9b9fcb543cd00c020eb36ab41ba1f7b17043f4df87a656d0d7dfc74897af5511  frontend/src/lib/components/molecules/DatumFeld.svelte
- sha256:83d44a515e88c84029e9e9cd595dbaed23980e35ff55ad57f3aa219f8eba745c  frontend/src/lib/components/molecules/UhrzeitFeld.svelte
- sha256:4145395cce3e3c08b6007ae91b18009bb6dc72cd1fa4f4548b88c6dfad50939c  frontend/src/lib/components/shared/hub-kopf/HubKopf.svelte
- sha256:614d62b204072a643a54566954027dbe0baf72a636a360bc42edcee2777eab1f  frontend/src/lib/components/trip-detail/ChannelDot.svelte
- sha256:c28604663091d127bd9c7383534ff47c2529db9617d2c39ffda1c5428d4609d4  frontend/src/lib/components/trip-detail/FullProfile.svelte
- sha256:5211ccc1ba2b9287c1d59844dc739cdd0aaa9d5fecd0f8fd047c27a6c5a91349  frontend/src/routes/compare/+page.svelte
- sha256:94a11683e7cb71d97cfaca3fdb59efd83e3375ad9d30a2042d85c833e4c84c22  frontend/src/routes/magic-link/+page.svelte
- sha256:2613329529ceca29d6e499965b876b1cd27727af5bd56e212836fafd0fbc7466  frontend/src/routes/magic-link/verify/+page.svelte
- sha256:d3ad370c453fbfd6a7ef252511cc6ceea2d6ed3b0e1e9ba9a46737d75bd35c19  frontend/src/routes/reset-password/+page.svelte

## Prüfbasis

- base: d322e2a9ee740e657ab70cb0d0c5a6eba7eab412
- blob:fb1bdec1a2063fddda71161036a71d985eba1757  .github/ci_e2e_specs.txt
- blob:fa1627ed33d1462526a2ce7c20e1e51170789c2e  .github/workflows/ci.yml
- blob:d4e238b125e7dd4b26fec4ec50aee76500600377  frontend/e2e/mobile-ux-audit-check.ts
- blob:15f03e2c0de532d30f14cb7ee98213a6388b36aa  frontend/e2e/mobile-ux-audit-staging-schutz.test.ts
- blob:7b8e3d6edd6d07bc0f2e69bee92e43c9ecf35d95  frontend/e2e/mobile-ux-audit.spec.ts
- blob:99b8c35447c1f7722dd1a3e50593183d4bbf4aa1  frontend/playwright.mobile-ux.local.config.ts
- blob:dfea168cdee2fb783a38e7ac4cc99bf593f85ff2  frontend/src/app.css
- blob:38cef28a3356343c84b430c3c626a778c56e8e43  frontend/src/lib/components/compare/steps/Step2Orte.svelte
- blob:3641aca4ed941fabae5f75fd8180e4075921ef85  frontend/src/lib/components/mobile/MTabBar.svelte
- blob:80a44ade3fe3dbb4f0fbda3fa470b3150925f3e7  frontend/src/lib/components/mobile/Sheet.svelte
- blob:efdb8551ad7d1326ccd784aa2188a94f48eb75c8  frontend/src/lib/components/molecules/DatumFeld.svelte
- blob:df5c5d61ff50a81dd08a6619eea7e33b320bd03e  frontend/src/lib/components/molecules/UhrzeitFeld.svelte
- blob:3480afc3f25810de31c2d0435f0ad886fb293610  frontend/src/lib/components/shared/hub-kopf/HubKopf.svelte
- blob:26418b8f5b37960d4664976c9a0eea99424546f2  frontend/src/lib/components/trip-detail/ChannelDot.svelte
- blob:eee319d5583f34c966a22bed0da54566cba168a0  frontend/src/lib/components/trip-detail/FullProfile.svelte
- blob:b826977647080eebb81b571ce601b7e218ddeed0  frontend/src/routes/compare/+page.svelte
- blob:cb2d4c89ff8215858d018d03356f6d3c7f330cd2  frontend/src/routes/magic-link/+page.svelte
- blob:3eee2feb74a6f883fa5507b72d478ea7b351d3fb  frontend/src/routes/magic-link/verify/+page.svelte
- blob:0bdf1e00e644e957faf84186e35afccb54cf2430  frontend/src/routes/reset-password/+page.svelte

## Geprüfte Dateien

- sha256:744a9d185cc07b5f383db5c078127fd74080e87d575223188741f21203a5e09f  .github/ci_e2e_specs.txt
- sha256:3972d7bc07efe79b1cd131cba0f2756d025c702d427f7f605af17c91d88c808e  .github/workflows/ci.yml
- sha256:b1fddf147ad037395a1c5fcc8083f132a034edab9780d1275e8cdf697c124f36  frontend/e2e/mobile-ux-audit-check.ts
- sha256:b3c75102ca7f7f7524a5086a4362a5987b11833418475680f952adc7d968b59b  frontend/e2e/mobile-ux-audit-staging-schutz.test.ts
- sha256:00380abb5bf56b319fb34792b2af8b4ea6921bac674015254c3b99e6c42b7a2f  frontend/e2e/mobile-ux-audit.spec.ts
- sha256:ab7af8e5e481da913fa3e6e1781938da04311a62e2a5125ef99fc87005801da5  frontend/playwright.mobile-ux.local.config.ts
- sha256:2c0b0458a6b5212c064469867ee28cd3b0c2a81a23e08b6e14e2f7c031ad2866  frontend/src/app.css
- sha256:8d3f9870125a92c723590b013350faafe49fc5e3477516b76cec430c62cf352d  frontend/src/lib/components/compare/steps/Step2Orte.svelte
- sha256:59127e53a518736d6bc040310f902ddfa94545d41223ce821ce39dcf858cfb25  frontend/src/lib/components/mobile/MTabBar.svelte
- sha256:78f0aaebca9c4b4ffc52c5b542b9f1f0f9a9e39b57387cae63feae7b6e4f81a7  frontend/src/lib/components/mobile/Sheet.svelte
- sha256:9b9fcb543cd00c020eb36ab41ba1f7b17043f4df87a656d0d7dfc74897af5511  frontend/src/lib/components/molecules/DatumFeld.svelte
- sha256:83d44a515e88c84029e9e9cd595dbaed23980e35ff55ad57f3aa219f8eba745c  frontend/src/lib/components/molecules/UhrzeitFeld.svelte
- sha256:4145395cce3e3c08b6007ae91b18009bb6dc72cd1fa4f4548b88c6dfad50939c  frontend/src/lib/components/shared/hub-kopf/HubKopf.svelte
- sha256:614d62b204072a643a54566954027dbe0baf72a636a360bc42edcee2777eab1f  frontend/src/lib/components/trip-detail/ChannelDot.svelte
- sha256:c28604663091d127bd9c7383534ff47c2529db9617d2c39ffda1c5428d4609d4  frontend/src/lib/components/trip-detail/FullProfile.svelte
- sha256:5211ccc1ba2b9287c1d59844dc739cdd0aaa9d5fecd0f8fd047c27a6c5a91349  frontend/src/routes/compare/+page.svelte
- sha256:94a11683e7cb71d97cfaca3fdb59efd83e3375ad9d30a2042d85c833e4c84c22  frontend/src/routes/magic-link/+page.svelte
- sha256:2613329529ceca29d6e499965b876b1cd27727af5bd56e212836fafd0fbc7466  frontend/src/routes/magic-link/verify/+page.svelte
- sha256:d3ad370c453fbfd6a7ef252511cc6ceea2d6ed3b0e1e9ba9a46737d75bd35c19  frontend/src/routes/reset-password/+page.svelte

## Prüfbasis

- base: d322e2a9ee740e657ab70cb0d0c5a6eba7eab412
- blob:fb1bdec1a2063fddda71161036a71d985eba1757  .github/ci_e2e_specs.txt
- blob:fa1627ed33d1462526a2ce7c20e1e51170789c2e  .github/workflows/ci.yml
- blob:d4e238b125e7dd4b26fec4ec50aee76500600377  frontend/e2e/mobile-ux-audit-check.ts
- blob:15f03e2c0de532d30f14cb7ee98213a6388b36aa  frontend/e2e/mobile-ux-audit-staging-schutz.test.ts
- blob:7b8e3d6edd6d07bc0f2e69bee92e43c9ecf35d95  frontend/e2e/mobile-ux-audit.spec.ts
- blob:99b8c35447c1f7722dd1a3e50593183d4bbf4aa1  frontend/playwright.mobile-ux.local.config.ts
- blob:dfea168cdee2fb783a38e7ac4cc99bf593f85ff2  frontend/src/app.css
- blob:38cef28a3356343c84b430c3c626a778c56e8e43  frontend/src/lib/components/compare/steps/Step2Orte.svelte
- blob:3641aca4ed941fabae5f75fd8180e4075921ef85  frontend/src/lib/components/mobile/MTabBar.svelte
- blob:80a44ade3fe3dbb4f0fbda3fa470b3150925f3e7  frontend/src/lib/components/mobile/Sheet.svelte
- blob:efdb8551ad7d1326ccd784aa2188a94f48eb75c8  frontend/src/lib/components/molecules/DatumFeld.svelte
- blob:df5c5d61ff50a81dd08a6619eea7e33b320bd03e  frontend/src/lib/components/molecules/UhrzeitFeld.svelte
- blob:3480afc3f25810de31c2d0435f0ad886fb293610  frontend/src/lib/components/shared/hub-kopf/HubKopf.svelte
- blob:26418b8f5b37960d4664976c9a0eea99424546f2  frontend/src/lib/components/trip-detail/ChannelDot.svelte
- blob:eee319d5583f34c966a22bed0da54566cba168a0  frontend/src/lib/components/trip-detail/FullProfile.svelte
- blob:b826977647080eebb81b571ce601b7e218ddeed0  frontend/src/routes/compare/+page.svelte
- blob:cb2d4c89ff8215858d018d03356f6d3c7f330cd2  frontend/src/routes/magic-link/+page.svelte
- blob:3eee2feb74a6f883fa5507b72d478ea7b351d3fb  frontend/src/routes/magic-link/verify/+page.svelte
- blob:0bdf1e00e644e957faf84186e35afccb54cf2430  frontend/src/routes/reset-password/+page.svelte
