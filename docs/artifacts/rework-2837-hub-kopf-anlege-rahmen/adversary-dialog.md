# Adversary Dialog — rework-2837-hub-kopf-anlege-rahmen
Spec: docs/specs/modules/rework_2837_s1_hub_kopf.md
Datum: 2026-11-06 15:17

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
- [x] (Phase-6-Anteil bewiesen: Parität durch Unit-Tests + HP-14 bewacht; Fresh-Eyes-Screenshot-Paar in /e2e-verify nachzuweisen) **AC-15:** Given (Abschluss) S1 ist auf Staging / When ein Fresh-Eyes-Prüfer ohne Vorwissen das Screenshot-Paar Hub-Kopf Desktop 1440 px und Mobil 390 px (Trip gegen Vergleich) vergleicht / Then findet er keinen Unterschied außer der fachlichen Whitelist (Datum, Kürzel, km/Hm, „Tag x von y", Kacheln, Orte-Anzahl, Entwurfs-Regel), und das Paar liegt als Kommentar im Epic #2345.

## Dialog

### Runde 1
**Adversary:** Tests ausgeführt (Artefakt `docs/artifacts/rework-2837-hub-kopf-anlege-rahmen/adversary-test-output.txt`):
Frontend, 22 benannte Dateien = 831 Tests, 0 Fehler; `trip_hub_loeschen.test.ts` separat per Direktlauf 10/10 (siehe F004);
Python-Tests (Doku-Test, ADR-Index, E2E-Paritätswächter): 37 passed. Die Suite wurde um Tests erweitert, die den Prüflingen sonst begegnen
(mtabbar_zaehler_neutral, subscription_kebab_mobil_vertikal, vergleich_hub_sprache, trip_hub_sprache, aktionsmodell_seiten_bindung, bug_589 u. a.).

Mutations-Gegenprobe (String-Ersetzung, externe Sicherung im Scratchpad, nach jeder Mutation `cmp` gegen die Sicherung = identisch; 43 Mutationen):
- GEFANGEN (rot): M1 Senden `accent` (7 Tests, AC-1 Mutation a); M2 MTabBar-Zähler wieder Accent-Füllung (mtabbar_zaehler_neutral, AC-10);
  M3 Status wieder eigene Zeile außerhalb `hub-kopf-status` (AC-6, Golden); M4 Breadcrumb-Kind als Link (AC-4); M5 `{#if context}` im HubKopf ("ein Markup"-Test);
  M6 onSetup-Sprungziel verfälscht (#1743 AC-24); M7 onSelect nicht an Kebab (Bindungstest); M8 mobil nicht an Kebab; M9 meldungen-Slot entfernt (de/en-Sprachtests);
  M10 mobiler Kebab horizontal (Symbol-Tests, mobil 44x44; das Ersatz-Icon war nicht importiert, daher zusätzlich N16 mit echtem gedrehtem Icon, ebenfalls rot per Golden);
  M12 Trip `actions={[]}`; M13 Compare sendMode fest; M14 Compare `mobil` nicht durchgereicht;
  M16 TripHeader reicht onSelect nicht durch (nur im Kette-Block von trip_hub_loeschen rot, siehe F004); M17 Kürzel -> Name (nur Golden f9 und trip_hub_sprache);
  M15 TripHeader reicht `mobil` nicht durch (nur Golden hub_seite.de); M11 Compare-Meldungen wieder nur Desktop (nur Golden); M18/M19 titleSize 30; M20 Trip-Entwurf nicht gesperrt; M21 Laufzeit-Hinweis weg; M24 44-px-Fläche weg (Regex);
  M27 TripStatusBadge weg; N1-N3 onSend No-op in HubKopf bzw. je Seite (Dialog öffnet nicht); N4 `kind` fest (nur Golden); N5/N15 BackLink/Elternteil falsch; N8 Default sendMode setup;
  N9 Kebab-Default mobil; N10 Compare-Status weg; N11/N12 onSheetOpen No-op; N13 sendLabel fest; N14 Compare-Kind fest; N16 Kebab-Icon gedreht (Golden).
- ÜBERLEBT (kein Unit-Test rot): M22 `text-overflow: clip`, M23 `white-space: normal`, M25 `.hub-actions min-width: auto`, M26 Status `flex-shrink: 1` (reines CSS, Pixel/Umbruch);
  N6 Default `mobil=true`, N7 Default `sendDisabled=true` im HubKopf (beide Seiten übergeben die Props immer ausdrücklich: heute funktional äquivalent, siehe F002).
- Erster Lauf (ohne trip_hub_sprache in der Suite) zeigte M15/M17 als überlebend; erst die Aufnahme der Golden-Tests f9 hat sie gefangen. Der AC-4-Test (`text(krumen).includes('GR20')`) ist allein zu schwach, weil der Name "GR20 Nord 2026" das Kürzel enthält (hub_kopf_seiten_paritaet.test.ts:94).

E2E-Bewertung (`frontend/e2e/hub-kopf-paritaet-compare-trip.spec.ts`, NICHT ausgeführt = nur E2E-gedeckt, nicht ausgeführt):
M1/N8 -> HP-1 (`grund === TOKEN_RGB.ink`) würde fangen; M2 -> HP-10 (Zähler-Grund paperDeep, Kontrast); M3 -> HP-6 (Status über Region-Stift, `.status-line` count 0);
M23 -> HP-5/HP-8 (Leistenhöhe gegen kurzen Namen, `scrollWidth <= clientWidth`) würde fangen; M25 wohl nur über HP-8-Scrollbreite; M22 (clip) ist unschädlich (Name bleibt abgeschnitten, AC-5 erfüllt);
M26 (Status schrumpft) wird NICHT sicher gefangen: HP-8 prüft nur, dass die Badge-Box im Bild liegt, nicht dass sie unverkürzt lesbar ist; M10 -> HP-7 (`lucide-ellipsis-vertical`);
M11 (Compare-Meldungen mobil): kein E2E-Schritt prüft Meldungen. Keine E2E-Prüfung ist bislang gelaufen: AC-1, AC-2, AC-5 (abgeschnitten), AC-8, AC-10 (Farben), AC-15 bleiben bis zum Staging-Lauf ungemessen.

Alttest-Prüfung (Diff gegen HEAD gelesen): die 9 Dateien wurden nicht gelockert. `compare_hub_fidelity` AC-12 und `compare_detail` AC-1 sind echte Umkehrungen
(Eyebrow "Hub" bzw. Versalien-Krümel darf nicht mehr vorkommen); `issue_491`/`issue_493` prüfen die Bindung jetzt am HubKopf (Regex auf HubKopf/Kebab; M7/M24 fangen sie);
`versand_sprung` AC-24 löst den echten Klick-Weg Seite -> HubKopf aus (strenger als vorher); `trip_hub_loeschen` plus Kette-Block (strenger); `TripHeader.issue699` Eyebrow = Text zwischen Leiste und h1
(leer davor erzwungen); `trips_breadcrumb_link` rendert den echten TripHeader. `vergleich_nutzt_gemeinsame_aktionen` erweitert FLAECHEN um HubKopf/Kebab (Prüfumfang wächst).

Regression (Step 4): `TripHeader` wird nur von `routes/trips/[id]/+page.svelte` eingebunden; `SubscriptionKebab` außerhalb des HubKopf nur von `organisms/SubscriptionCard.svelte` (Default `mobil=false`, unverändert; N9 fängt einen Default-Flip);
`MTabBar` nur von TripTabs und CompareTabs (beide gewollt neutral). AC-14: der Arbeitsbaum-Status zeigt keine Änderung an trips/new, compare/new, compare-new, trip-new, Profil.
Pendant-Gate: einzige neue Komponente `shared/hub-kopf/HubKopf.svelte` (unter shared/); keine neue Datei mit Trip-/Compare-Pendant.
Goldens f9/f10 (Wort-Diff gelesen): nur beabsichtigte Änderungen (Hub-Krümel weg, `data-variant="primary"`, Status im Titelblock, Hub-Kopf-Gerüst); nichts Inhaltliches verschwunden.

**Implementierer:** (nicht anwesend, Kontextisolation)

### Runde 2
**Adversary:** Zweiter Durchgang gezielt auf Whitelist-Parität (Entscheidung 8) und auf die Stelle, an der die Zusicherung WIRKT (Seiten statt Baustein): die Mutationen N1-N16 liefen an den Seiten
(`routes/trips/[id]/+page.svelte`, `routes/compare/[id]/+page.svelte`) und im Zwischenstück `TripHeader.svelte`, nicht nur im HubKopf. Ergebnis: alle Verdrahtungen sind gedeckt;
Lücken nur bei CSS (E2E-only), bei Defaults und bei `mobil`/Meldungen/Kürzel, die nur das byte-gleiche Golden fängt. Paritätsabweichung, die kein Test kennt: Der Vergleich wickelt den HubKopf in
`<div class="pb-4 desktop:pb-0 desktop:[border-bottom:1px_solid_var(--g-rule)]">` (compare/[id]/+page.svelte:359), der Trip in `<header class="trip-header">` mit `padding: 0 0 18px` und
Zeilenabstand 0.5rem und ohne Trennlinie (TripHeader.svelte, Style-Block). Damit hat der Vergleich auf dem Desktop eine 1-px-Linie unter dem Kopf, der Trip nicht, und der Abstand unter dem Titelblock
ist verschieden. Die Spec nennt weder Linie noch Abstand in der Whitelist (kein Treffer für border/Linie/Abstand/padding in der Spec).
Ebenfalls geprüft: Entwurf/Archiv-Sperre (N7/M20 gefangen), `sendMode` nur im Vergleich-Entwurf, Leisten-testid `trip-detail-breadcrumb-bar` als Wrapper (kein Layoutunterschied), Kürzel-Fallback (Go-Modell `omitempty`, daher kein leeres Kürzel im Pfad).
**Implementierer:** (nicht anwesend)

### Runde 3
**Adversary:** Nachprüfung der Behebung von F001 und F003 (geänderte Dateien dieser Runde: HubKopf.svelte, TripHeader.svelte, routes/compare/[id]/+page.svelte, hub_kopf_seiten_paritaet.test.ts, issue_582_compare_design_fidelity.test.ts, 6 Goldens). Alle Angaben des Developers am Code geprüft:
- F001 behoben, belegt: `HubKopf.svelte:165-172` trägt `.hub-kopf-titel { padding: 22px 40px 16px }` (mobil `16px`) und am Desktop `.hub-kopf { border-bottom: 1px solid var(--g-rule) }` für beide Arten; der Compare-Wrapper ist entfernt (`compare/[id]/+page.svelte:363-364`, `<HubKopf>` steht ohne Wrapper); `TripHeader.svelte` hat kein `.trip-header`-Padding/-Margin mehr (Style-Block ab Zeile 193); das neue Snippet `unten` (HubKopf.svelte:114, TripHeader.svelte:172) trägt km/Hm und die Mobil-Kacheln des Trips.
- F003 behoben: `kindKruemel()` (hub_kopf_seiten_paritaet.test.ts:60) vergleicht exakt (`assert.equal`, AC-4 "GR20" / "Skitouren Tirol", AC-5 "GR20 Nord 2026").
- Die neue Paritätsprüfung (describe "Unterkante", 4 Tests) ist keine Tautologie: sie läuft über die echt gerenderte Seite (Markup-Vorfahren der HubKopf-Wurzel `data-kind`) und über das mit `compile()` erzeugte CSS der Seite und Hülle. Sie schlug bei R1, R2, R3, R4, R12 rot an. Sie sieht aber nur Vorfahren-Wrapper, nicht CSS innerhalb des HubKopf selbst (R6).

Mutations-Gegenprobe Runde 3 (14 Mutationen, Sicherung im Scratchpad, nach jeder `cmp` identisch; Suite 23 Dateien, 835 Tests):
- GEFANGEN: R1 Compare-Wrapper mit Linie zurück (Paritätstest Markup + Golden f10); R2 Wrapper nur Padding; R12 Wrapper mit Inline-Style-Padding; R3 `.trip-header`-Padding/-Margin zurück (Paritätstest CSS + Golden f9); R4 `.trip-header`-Linie zurück; R5 Linie im HubKopf entfernt (issue_582 AC-4b); R7 Linie nur für Trip (`[data-kind="route"]`, AC-4b); R13 Breakpoint der Linie 900 -> 1200 (AC-4b); R8 `unten` wird nicht gerendert und R9 Snippet beim Trip entfernt (km/Hm fehlt: #699-Meta-Test, trip_hub_sprache, Goldens); R10 Breadcrumb-Kind mit Zusatztext "(Hub)" und R11 Zusatz-Span (exakter Kind-Vergleich, 7-12 Tests rot; ohne F003-Fix wäre R11 durch `includes` durchgerutscht).
- ÜBERLEBT (kein Unit-Test rot): R6 Abstand nur beim Vergleich per kind-Selektor im HubKopf (`.hub-kopf[data-kind="vergleich"] .hub-kopf-titel { padding-bottom: 0 }`); R14 mobiles `.hub-kopf-titel`-Padding unten 16 -> 0 (wirkt auf beide Arten gleich, nur Darstellung).
- E2E-Lage: Die E2E-Spec enthält keinerlei Prüfung von Unterkante/Linie/Abstand (kein Treffer für border/padding/Unterkante). R6 und R14 sind also auch nicht E2E-gedeckt.

Regression: Höhenbudget Trip mobil (AC-13, "Etappen-Liste oben <= 474 px") wird nur von `frontend/e2e/trip-hub-kopf-region-aktivitaet.spec.ts` gemessen, nicht ausgeführt; im Unit-Bereich gibt es keinen Höhentest. Der Zeilenabstand 0.5rem zwischen Titelblock und km/Hm-Zeile entfiel mit `.trip-header`; ob der Titelblock selbst einen Abstand liefert, ist nur im Browser sichtbar. Doppelte Linie zur Reiterleiste: Linie `.hub-kopf` (--g-rule) und Reiter-Unterstrich (MTabBar) liegen an verschiedenen Rändern, bei Trip und Vergleich jetzt identisch aufgebaut; keine Doppelung im Quelltext erkennbar (visuell nur E2E/Screenshot).
**Implementierer:** (nicht anwesend)

### Runde 4
**Adversary:** Nachprüfung der Schließung von F006. Produktcode unverändert (`cmp` HubKopf, TripHeader, Compare-Seite gegen die Sicherung der Runde 3 identisch), geändert wurden nur Tests: `hub_kopf_baustein.test.ts` (describe "Entscheidung 1 / F006 — keine Optik nach Art", 3 Tests) und E2E HP-14.
- Unit-Test CSS (`hub_kopf_baustein.test.ts:269`): kompiliert das echte HubKopf-CSS und verbietet Selektoren mit `data-kind`, `[kind`, `.route/.vergleich/.trip/.compare`, `.kind-`, `.context-`. Der Test ist nicht tautologisch: er liest das reale Stylesheet. Der Messaufbau-Assert (`.hub-kopf` vorhanden) verhindert einen Leerlauf.
- Unit-Test Markup (`:278`): rendert HubKopf als route und vergleich (Desktop und mobil) und vergleicht `tag|class|style` jedes Elements. Fängt Klassen und Inline-Styles, die von `context` abhängen.
- Neue Mutationen, alle rot: S1 (R6 erneut, `.hub-kopf[data-kind="vergleich"] .hub-kopf-titel`), S2 (`:global([data-kind=vergleich])`), S3 (Inline-Style abhängig von `context`), S4 (`class:eng={context==='vergleich'}` plus `:global`), S5 (Klasse `{context}` plus `:global(.vergleich…)`), S7 (`style:padding-bottom` abhängig von `context`). Suite 23 Dateien = 838 Tests. Nach jeder Mutation `cmp` identisch.
- Nicht geprüft (theoretisch): Klasse oder Prop (`extraClass`), die nur eine Seite setzt. Nach Vorgabe gedeckt durch den Seiten-Wrapper-Test (Runde 3) und E2E HP-14.
- E2E HP-14 (`hub-kopf-paritaet-compare-trip.spec.ts:213-250`, nicht ausgeführt): `unterkante()` misst per `getComputedStyle` die Wurzel (`ancestor::*[@data-kind][1]` der Leiste, das ist `.hub-kopf`: border-bottom Breite/Art/Farbe) und `.hub-kopf-titel` (padding-bottom) sowie den Abstand Wurzel-Unterkante zur Reiterleiste (`[data-slot="segmented"][role="tablist"]`, ±4 px) bei 1440 und 390 px, beide Arten, plus Desktop 1px solid. Die Selektoren treffen die Zielelemente, die R6 verändert; R6, S2-S5, S7 und ein Wrapper-Padding (R2) würden dort rot. Das schließt die Lücke aus Runde 3, bleibt aber bis zum Staging-Lauf ungemessen.
**Implementierer:** (nicht anwesend)

## Herkunft der Vorbedingungen

kein Sprachprofil konfiguriert (`precondition_origins.default_lang`)

## Structured Findings

Finding:
  ID: F001
  Severity: MEDIUM (BEHOBEN in Runde 3, nachgeprüft)
  Category: spec_violation
  Code reference: frontend/src/routes/compare/[id]/+page.svelte:359
  Description: Der Vergleich umschließt den HubKopf mit `desktop:[border-bottom:1px_solid_var(--g-rule)]` und `pb-4`; der Trip-Kopf (`frontend/src/lib/components/trip-detail/TripHeader.svelte`, `.trip-header { padding: 0 0 18px }`) hat keine Trennlinie und anderen Abstand.
  Spec requirement: Entscheidung 8 / AC-15 — außer der Whitelist kein sichtbarer Unterschied zwischen Trip und Vergleich.
  Conflict: Linie und Abstand stehen nicht in der Whitelist; kein Test (auch E2E nicht) misst sie. Im Browser nicht verifiziert, deshalb AMBIGUOUS statt BROKEN.
  Remediation: Wrapper beider Seiten identisch bauen (Linie/Abstand in HubKopf oder in beiden gleich) oder die Linie ausdrücklich in die Whitelist aufnehmen; E2E um Vergleich der Kopf-Unterkante erweitern.

Finding:
  ID: F002
  Severity: LOW
  Category: anti_pattern
  Code reference: frontend/src/lib/components/shared/hub-kopf/HubKopf.svelte:59
  Description: Defaults `mobil = false` und `sendDisabled = false` im HubKopf: ein Flip auf `true` bleibt ohne rote Tests (N6, N7), weil beide Seiten die Props immer ausdrücklich übergeben. Heute funktional äquivalent; wirkt bei einem dritten Verwender ohne Props.
  Spec requirement: AC-3 / AC-7 (Verhalten gilt für jeden Verwender des Bausteins).
  Conflict: Default-Werte sind ungeprüft.
  Remediation: Baustein-Test mit weggelassenen Props (Default-Render) ergänzen.

Finding:
  ID: F003
  Severity: LOW (Teil Kürzel-Vergleich BEHOBEN in Runde 3; Rest mobil/Meldungen/kind nur Golden)
  Category: edge_case
  Code reference: frontend/src/lib/components/trip-detail/TripHeader.svelte:146
  Description: Das Durchreichen von `{mobil}` TripHeader -> HubKopf (M15), das Kürzel im Pfad (M17, TripHeader.svelte:140; der AC-4-Test nutzt `includes`, der Name enthält das Kürzel), die Compare-Meldungen in jeder Breite (compare/[id]/+page.svelte:397, M11) und `kind` (N4) fängt nur das byte-gleiche Golden, das sich durch Neuerzeugung leicht anpassen lässt. Der Kette-Block prüft onSelect/onSheetOpen, nicht `mobil`.
  Spec requirement: AC-4/AC-5 (Kürzel), AC-7 (Trip mobil: Tippen öffnet dasselbe Aktionsblatt), Whitelist-Parität Meldungen.
  Conflict: Zusicherung am Golden statt an der Wirkstelle.
  Remediation: AC-4-Test auf exakten Kind-Text prüfen (`===` "GR20"); Kette-Block um `mobil` erweitern (mobiler Kebab ist Knopf, kein Dropdown); Meldungstest mit `sendMsg` in beiden Breiten.

Finding:
  ID: F004
  Severity: LOW
  Category: anti_pattern
  Code reference: frontend/src/routes/trips/[id]/__tests__/trip_hub_loeschen.test.ts:160
  Description: `npm test -- <Pfad mit [id]>` führt unter Node 22.22 0 Tests aus (maskiert als `[[]id]`, `[id]`, Wildcard: immer `# tests 0`). Direktlauf `node ... <datei>` liefert 10/10 inkl. Kette-Block; M16 wird nur dort rot. CI ruft `npm test` ohne Pfad auf und findet die Datei, der benannte Lauf nicht.
  Spec requirement: Test-Politik (benannte Dateien müssen wirklich laufen).
  Conflict: Der vorgegebene benannte Lauf ist für diese Datei ein stiller Leerlauf.
  Remediation: Datei in einen Ordner ohne Klammern legen oder im Runbook den Direktlauf nennen.

Finding:
  ID: F005
  Severity: LOW
  Category: edge_case
  Code reference: frontend/src/lib/components/shared/hub-kopf/HubKopf.svelte:127
  Description: CSS-Zusicherungen (AC-5 Ellipsis/nowrap, AC-8 Umbruch/min-width, Status-Badge nicht schrumpfen) haben keinen Unit-Test (M22, M23, M25, M26 überleben). E2E HP-5/HP-8 würde M23 und M25 fangen, M26 vermutlich nicht. Nur E2E-gedeckt, nicht ausgeführt.
  Spec requirement: AC-5, AC-8.
  Conflict: Bis zum Staging-E2E ungemessen.
  Remediation: E2E-Lauf abwarten; HP-8 um Badge-Mindestbreite erweitern.

Finding:
  ID: F006
  Severity: LOW (BEHOBEN in Runde 4, nachgeprüft)
  Category: edge_case
  Code reference: frontend/src/lib/components/shared/hub-kopf/HubKopf.svelte:165
  Description: Die Zusicherung "Unterkante und Abstand gleich bei Trip und Vergleich" ist nur gegen Wrapper außerhalb des HubKopf geprüft. Ein kind-abhängiger Selektor im HubKopf selbst (R6: `.hub-kopf[data-kind="vergleich"] .hub-kopf-titel { padding-bottom: 0 }`) lässt alle Unit-Tests grün; die E2E-Spec misst weder Linie noch Abstand. Aktuell besteht kein Unterschied (Quelltext gelesen), die Wache ist nur lückenhaft.
  Spec requirement: Entscheidung 8 / AC-15 — kein sichtbarer Unterschied außer der Whitelist.
  Conflict: Parität der Kopf-Unterkante wird nirgends gemessen, wo sie wirkt (im Browser).
  Remediation: In der E2E-Spec Unterkante des Kopfs (`boundingBox` der `hub-kopf-leiste`-Wurzel unten bis Reiterleiste, Randfarbe) für beide Arten vergleichen, oder im Paritätstest alle `[data-kind]`-Selektoren im HubKopf-CSS mit Rahmen/Abstand verbieten.

## Confirmations (Stand Runde 4, Zeilen am aktuellen Stand geprüft)

Confirmation: AC-1 — Btn `variant="primary"` in `hub-kopf-leiste`, kein zweites Senden neben dem Titel; M1/N8 rot. Pixel/Farbe/Position nur E2E HP-1 (nicht ausgeführt).
  Code reference: frontend/src/lib/components/shared/hub-kopf/HubKopf.svelte:85
  Code reference: frontend/src/routes/trips/[id]/+page.svelte:318
  Status: CONFIRMED

Confirmation: AC-2 — mobil `min-height: 44px` für Leisten-Knöpfe, Zurück-Pfeil in der Leiste, mobiler Kebab 44x44; M24 rot. Höhe gemessen nur E2E HP-2.
  Code reference: frontend/src/lib/components/shared/hub-kopf/HubKopf.svelte:194
  Code reference: frontend/src/lib/components/molecules/SubscriptionKebab.svelte:23
  Status: CONFIRMED

Confirmation: AC-3 — `sendMode==='setup'` zeigt Setup auf dem Senden-Platz; Trip-Senden im Entwurf gesperrt; M6/M13/M20/N8 rot.
  Code reference: frontend/src/lib/components/shared/hub-kopf/HubKopf.svelte:81
  Code reference: frontend/src/routes/compare/[id]/+page.svelte:369
  Code reference: frontend/src/routes/trips/[id]/+page.svelte:319
  Status: CONFIRMED

Confirmation: AC-4 — Elternteil als Link, Kind als Span, kein "Hub"; Katalogschlüssel `vergleich.hub.krumel`/`eyebrow` in beiden Sprachen entfernt; M4/M5/N14/N15/R10/R11 rot (Kind exakt geprüft).
  Code reference: frontend/src/lib/components/shared/hub-kopf/HubKopf.svelte:75
  Code reference: frontend/src/lib/i18n/messages/de/vergleich.json:36
  Status: CONFIRMED

Confirmation: AC-5 — `crumb={trip.shortcode ?? trip.name}`: Name statt Kürzel; M17 rot. Abschneiden (Ellipsis) nur E2E (F005).
  Code reference: frontend/src/lib/components/trip-detail/TripHeader.svelte:140
  Code reference: frontend/src/lib/components/shared/hub-kopf/HubKopf.svelte:127
  Status: CONFIRMED

Confirmation: AC-6 — Status im `badges`-Snippet der Titelzeile, keine eigene Statuszeile; M3/M27/N10 rot.
  Code reference: frontend/src/lib/components/shared/hub-kopf/HubKopf.svelte:111
  Code reference: frontend/src/lib/components/trip-detail/TripHeader.svelte:167
  Status: CONFIRMED

Confirmation: AC-7 — mobiler Kebab ist ein Knopf mit vertikalem Symbol und öffnet bei beiden dasselbe Aktionsblatt; M10/M14/N11/N12 rot, `mobil`-Durchreichung des Trips nur per Golden (F003-Rest).
  Code reference: frontend/src/lib/components/molecules/SubscriptionKebab.svelte:23
  Code reference: frontend/src/lib/components/trip-detail/TripHeader.svelte:146
  Status: CONFIRMED

Confirmation: AC-8 — `.hub-actions` schrumpfbar, Pfad nowrap/ellipsis; keine Unit-Absicherung (F005). Nur E2E-gedeckt, nicht ausgeführt.
  Code reference: frontend/src/lib/components/shared/hub-kopf/HubKopf.svelte:151
  Status: CONFIRMED

Confirmation: AC-9 — beide Arten `titleSize={38}`; M18/M19 rot.
  Code reference: frontend/src/lib/components/trip-detail/TripHeader.svelte:157
  Code reference: frontend/src/routes/compare/[id]/+page.svelte:384
  Status: CONFIRMED

Confirmation: AC-10 — Zähler `--g-paper-deep`/`--g-ink-3` für alle Größen, Compare-Tabs nur Kommentar angepasst; M2 rot. Gerenderte Farbe nur E2E HP-10.
  Code reference: frontend/src/lib/components/mobile/MTabBar.svelte:143
  Code reference: frontend/src/lib/components/compare/CompareTabs.svelte:676
  Status: CONFIRMED

Confirmation: AC-11 — `onclick -> onSend`, die Seiten öffnen nur den Dialog; genau ein `SubscriptionHeader` im HubKopf; N1-N3 rot.
  Code reference: frontend/src/lib/components/shared/hub-kopf/HubKopf.svelte:85
  Code reference: frontend/src/routes/trips/[id]/+page.svelte:318
  Code reference: frontend/src/routes/compare/[id]/+page.svelte:371
  Status: CONFIRMED

Confirmation: AC-12 — ADR-0110, README-Zeile, "Abgelöst durch" in beiden alten Specs, `design_system.md`; Python-Tests 37 grün.
  Code reference: docs/adr/0110-hub-kopf-und-anlege-rahmen-ein-baustein.md:1
  Status: CONFIRMED

Confirmation: AC-13 — Texte über den Katalog in beiden Sprachen, Hub-Schlüssel entfernt; Sprachtests grün, M9/M21/N13 rot.
  Code reference: frontend/src/lib/i18n/messages/en/vergleich.json:36
  Code reference: frontend/src/lib/i18n/messages/de/vergleich.json:36
  Status: CONFIRMED

Confirmation: AC-14 — `/trips/new`, `/compare/new` und Profil-Auswahl im Arbeitsbaum unverändert (kein Eintrag in der Änderungsliste).
  Code reference: frontend/src/routes/trips/new/+page.svelte:1
  Status: CONFIRMED

Confirmation: AC-15 — Parität der Unterkante hergestellt und durch Unit-Test plus E2E HP-14 bewacht; Screenshot-Paar entsteht erst nach Staging.
  Code reference: frontend/src/lib/components/shared/hub-kopf/HubKopf.svelte:168
  Status: DEFERRED

## Verdict

═══════════════════════════════════════
VERDICT: VERIFIED
═══════════════════════════════════════
Die Implementierung hat die Gegenprobe überstanden. F001, F003 (Kürzel) und F006 sind behoben und durch Mutationen belegt (Runde 3: R1-R5, R7-R13; Runde 4: S1-S5, S7, alle rot; kein realistischer Umgehungsversuch über Selektor, `:global`, Klasse, Inline-Style oder `style:`-Direktive überlebt).
Überlebende Mutationen gesamt (bewertet): reine CSS-Darstellungsdetails mit E2E-Deckung oder ohne fachliche Wirkung: M22/M23/M25/M26 (AC-5/AC-8, E2E HP-5/HP-8, M26 nur teilweise), R14 (mobiles Padding unten für beide Arten gleich; HP-14 misst padding-bottom des Titelblocks und fängt es nur als Gleichheit, nicht als Absolutwert, daher nur als Darstellungsdetail gewertet), N6/N7 (Defaults, von beiden Seiten immer gesetzt).
Offene LOW-Punkte (keine Blocker): F002 (Defaults ungeprüft), F003-Rest (mobil-Durchreichung, Compare-Meldungen, kind nur per Golden), F004 (Pfad mit [id] läuft über `npm test <Pfad>` leer, CI findet die Datei), F005 (CSS nur E2E).
Nur E2E-gedeckt, nicht ausgeführt: AC-1, AC-2, AC-5 (Ellipsis), AC-8, AC-10 (Farben), HP-14 (Unterkante/Abstand), Höhenbudget Trip mobil (trip-hub-kopf-region-aktivitaet.spec.ts), AC-15 (Screenshot-Paar nach Staging).
Tests: Frontend 838 passed, 0 failed (23 benannte Dateien), trip_hub_loeschen direkt 10 passed, Python-Tests 37 passed. Regressions: keine gefunden.
Working Tree: identisch zum Stand vor Runde 4 (cmp gegen alle 9 Sicherungen, Status und Diff identisch zu den Vorher-Snapshots).
Voraussetzung für die Freigabe: Der E2E-Lauf (HP-1 bis HP-14) in /e2e-verify gegen Staging steht aus.

## Geprüfte Dateien

- sha256:8a742d1f34ed18de0569b771e6e26f7a3f17e6382791e4bf97172a1587da60c4  docs/adr/0110-hub-kopf-und-anlege-rahmen-ein-baustein.md
- sha256:5eed439430de92432d1e5ad7bc5d8b268eb4a891b3ba0e71224a320de9c34d6e  frontend/src/lib/components/compare/CompareTabs.svelte
- sha256:d7ee1ebcfcf6580a350ca6e42fb8a2cf5423cc729343a1b03d315ef98a2b5d49  frontend/src/lib/components/mobile/MTabBar.svelte
- sha256:7010ac15f22c4d5ee34fe6e06c8165e1e81b94a4a4874273ef404421cc53cd5e  frontend/src/lib/components/molecules/SubscriptionKebab.svelte
- sha256:55542252b7b1c112a87f5858dbe9a85c486dd098c943c703d54756f1c38ba738  frontend/src/lib/components/shared/hub-kopf/HubKopf.svelte
- sha256:f8b4ee79617370265d1d2b5aba1c18f7c439e15a24f0ce386a00929bf767b23e  frontend/src/lib/components/trip-detail/TripHeader.svelte
- sha256:99af4f3451f8fa1a53db8264ea98079f3aec4808921e9f7c239f1e4ae6daa9c2  frontend/src/lib/i18n/messages/de/vergleich.json
- sha256:9df73387116db0c4d8e05f5e445bba1d252c94e02e5ee6f6021044a4bd80d8b7  frontend/src/lib/i18n/messages/en/vergleich.json
- sha256:24cc4e75d23a1498cff6ef254416a190d2c0a3aa49eb8e6b35c615cc6800e1b8  frontend/src/routes/compare/[id]/+page.svelte
- sha256:023db0d32f61f642cd68f1ce25b06d72c9945d8444a87aea47e82d5682da712a  frontend/src/routes/trips/[id]/+page.svelte
- sha256:b84c7575bac03e110ee6d78856bd8852ec912f85d8f0a976a192bbc4726893c2  frontend/src/routes/trips/[id]/__tests__/trip_hub_loeschen.test.ts
- sha256:20c5db28ddb18b84711f13bbd6f3b6700607fae9519e6ef8f920a98a41596fb0  frontend/src/routes/trips/new/+page.svelte

## Prüfbasis

- base: 2b7f45ba3e536ff268f385d87d31889cb8fd03cf
- blob:f5337ba760ac8f2b40a9ef7ca291e2a97817e93d  docs/adr/0110-hub-kopf-und-anlege-rahmen-ein-baustein.md
- blob:e502b5966a37fc95496eb4c0f22c18d82f792ddc  frontend/src/lib/components/compare/CompareTabs.svelte
- blob:2ac56429c2e2cd0a83581f1dadb9f5e4be6731dd  frontend/src/lib/components/mobile/MTabBar.svelte
- blob:674427dd64104b3c7b197665427dfea02f4fd531  frontend/src/lib/components/molecules/SubscriptionKebab.svelte
- blob:abc926a1fb26c89ba4909d0fe332efee4d17b4dc  frontend/src/lib/components/shared/hub-kopf/HubKopf.svelte
- blob:566fdd10eca73d964f12ed4ae5a1ddc1dbc7807c  frontend/src/lib/components/trip-detail/TripHeader.svelte
- blob:9515e07925200c7a31cd2d63d3d9e4515e79088d  frontend/src/lib/i18n/messages/de/vergleich.json
- blob:e8d4e740ae0fec4f8c7533c5627a7c5105c1899b  frontend/src/lib/i18n/messages/en/vergleich.json
- blob:5d3d7136159da45cf52da68d6fe061ae43ffda20  frontend/src/routes/compare/[id]/+page.svelte
- blob:e255dbfb07d3f3f304108d992891d61b304ba89a  frontend/src/routes/trips/[id]/+page.svelte
- blob:5c9151d6ee8c652517bcd11f6cff18e8ad41594b  frontend/src/routes/trips/[id]/__tests__/trip_hub_loeschen.test.ts
- blob:79be62647658b160bd51a23b4657017adac7e60f  frontend/src/routes/trips/new/+page.svelte
