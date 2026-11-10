---
entity_id: mobile_ux_audit_2601
type: module
created: 2026-10-22
updated: 2026-11-10
status: approved
version: "1.1"
tags: [mobile, ux, e2e, audit]
---

# Mobile-UX-Audit (#2601)

## Approval

- [x] Approved (v1.1, Runde 2: PO 2026-11-10 „approved", inkl. Höhenprofil-Ausnahme AC-11)

Historie: v1.0 (Runde 1) war freigegeben (PO 2026-10-22: „direkt fixen ohne Freigabe"), geliefert mit PR #2602. v1.1 ergänzt Runde 2 und braucht eine neue Freigabe.

## Purpose

Wiederholbarer Audit aller Routen in drei Smartphone-Profilen (390×844, 402×874, Querformat 844×390), der Erreichbarkeit und Bedienbarkeit prüft, plus die Behebung der dabei gefundenen Befunde. Leitfrage: Ist jedes Bedienelement auf dem Telefon antippbar und lesbar?

Runde 2 (v1.1) misst auf dem Stand nach der Englisch-Migration (Epic #2730) und dem Editor-/Vergleichs-Umbau (#2345, #2837) erneut, jetzt in Deutsch und Englisch, schließt Lücken der Routenliste und behebt die neuen Befunde. Die Befundliste (Vorher/Nachher) steht als Kommentar im Issue #2601.

## Source

- **File:** `frontend/e2e/mobile-ux-audit.spec.ts`, `frontend/playwright.mobile-ux.local.config.ts`
- **Identifier:** `LAYOUT_CHECK`, `auditRoute`, `OVERLAYS`
- **Fixes Runde 1 (Frontend):** `frontend/src/app.css` (Touch-Regeln, `.g-link-tap`, Hinweis-Freihaltung), `StageCardM.svelte`, `StageDateField.svelte`, `StageTimeField.svelte`, `DragHandle.svelte`, `AlertChannelPicker.svelte`, `Select.svelte`, `Stat.svelte`, Login/Register/Forgot-Links, Startseiten-Links, Kleintexte < 11px in mobil sichtbaren Bausteinen
- **Fixes Runde 2 (Frontend):** `molecules/DatumFeld.svelte`, `molecules/UhrzeitFeld.svelte` (Segmente), `shared/hub-kopf/HubKopf.svelte` (Brotkrumen), `trip-detail/FullProfile.svelte` (Attribut `data-tap-equivalent`), `frontend/src/app.css` (Block `@media (max-width: 899px), (pointer: coarse)`), /compare-Seite und `cm-mobile-tabbar` (AnlegeReiter) nach Messung

## Scope

- **Im Umfang (Runde 2):** Audit auf aktuellem Stand in DE und EN, drei Profile (390×844, 402×874, Querformat 844×390), alle Routen aus #2601 plus ausgeloggte Startseite, `/reset-password`, `/verify-email`, `/magic-link` (und verify) und Wizard-Schritte größer 1; Behebung der harten Befunde (Segmentfelder Datum/Uhrzeit, Brotkrumen-Clipping, `<main>`-Überlauf /compare, EN-Tabbar /compare/new) und der weichen Befunde über die zentralen Regeln in `app.css`; Audit-Härtung; Befundliste im Issue.
- **Nicht im Umfang:** EN-Übersetzungslücken (ausgegliedert nach #2919); Safari/WebKit-Eigenheiten (nur Chromium-Emulation); Verbreiterung der Höhenprofil-Etappenrechtecke (dokumentierte Ausnahme, AC-11); Staging- oder Produktionsläufe des Audits.

## Estimated Scope

- **LoC:** Runde 1 ~180; Runde 2 ca. +250…350 / −30 (etwa die Hälfte Audit und Spec). LoC-Override 500 laut Issue #2601.
- **Files:** Runde 1: 38; Runde 2: 9–11
- **Effort:** medium

### Affected Files (Runde 2)

| File | Change Type | Description |
|------|-------------|-------------|
| frontend/src/lib/components/molecules/DatumFeld.svelte | MODIFY | Segmente Tag/Monat mind. 24×24 px (Touch/≤899px), Jahr unverändert |
| frontend/src/lib/components/molecules/UhrzeitFeld.svelte | MODIFY | Segmente Stunde/Minute mind. 24×24 px (Touch/≤899px) |
| frontend/src/lib/components/shared/hub-kopf/HubKopf.svelte | MODIFY | Brotkrumen-Bereich nur horizontal beschneiden, Trip- und Vergleichs-Hub gemeinsam |
| frontend/src/lib/components/trip-detail/FullProfile.svelte | MODIFY | `data-tap-equivalent` am Etappen-Rechteck (WCAG 2.5.8 „equivalent") |
| frontend/src/app.css | MODIFY | 28-px-Knöpfe auf den bestehenden 36-px-Boden, 10-px-Texte auf 11 px |
| frontend/src/routes/compare/+page.svelte, AnlegeReiter (`cm-mobile-tabbar`) | MODIFY (nach Messung) | Überlauf im Hauptbereich; EN-Tabbar: bewusst scrollbar oder Fix |
| frontend/e2e/mobile-ux-audit.spec.ts | MODIFY | Zähler ungekappt, Weiterleitungs-Ausweis, allgemeine main-Überlaufprüfung, neue Routen, Höhenprofil-Ausnahme |
| frontend/playwright.mobile-ux.local.config.ts | MODIFY | `GZ_AUDIT_LOCALE=de\|en`, Abbruch ohne `GZ_E2E_API_PROXY_TARGET` |
| frontend/e2e/issue-2601-*.spec.ts | CREATE | Messtests mit berechneten Größen inkl. Desktop-Gegenprobe 1280×800 |
| docs/specs/modules/mobile_ux_audit_2601.md | MODIFY | diese Fortschreibung (v1.1) |

Querschnitt: Trip und Vergleich teilen die Bausteine DatumFeld, UhrzeitFeld und HubKopf. Es gibt keine Compare-eigenen Sonderfixes. Es werden keine Nutzerdaten bewegt und keine Briefing-/Alarm-Inhalte geändert.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `frontend/e2e/ci-stack.sh` | Script | Offline-Stack (Go + Python) für den lokalen Lauf |
| `frontend/e2e/global.setup.ts` | Setup | Anmeldung + Seed (`playwright/.auth/admin.json`); legt keinen Vergleich an |
| `mobile_tab_leisten_mtabbar` | Spec | Tab-Leiste (44px-Trigger) bleibt unverändert |
| `frontend/src/lib/i18n/resolveLang.ts` | Modul | Sprache: Cookie `gz_lang` > Accept-Language > de; für Angemeldete gilt die Profilsprache |
| `frontend/vite.config.ts` (`API_PROXY_TARGET`) | Config | Vorschau-Proxy; Default zeigt auf Staging, daher Schutz im Audit-Config |
| `mobile_stages_tab_listen_only`, `feat_1256_s8d_mobile_editor_fidelity` | Spec | Etappen-Tab und Editor mobil; Segmentfelder müssen dort ohne Umbruchfehler passen |
| Epic #2345 (Trip/Vergleich-Teilung), #2881 (Segmentbausteine) | Entscheidung | Fixes nur in geteilten Bausteinen; natives `type=date` bleibt verworfen |

## Implementation Details

```
Audit (je Route, je Detail-Tab, je Overlay):
  (a) page-level horizontaler Overflow (Fenster UND <main class="mobile-scroll-pad">)
  (b) überstehende Elemente ohne overflow-x auto/scroll
  (c) interaktive Elemente horizontal außerhalb des Viewports (nicht in h-scrollbarem Container)
  (d) interaktive Elemente am Scroll-Ende unter fixen/sticky Leisten (elementFromPoint)
  (e) Tap-Ziele < 24px (hart) / < 40px (Hinweis); ::after-Trefferflächen zählen mit;
      Inline-Textlinks ausgenommen (WCAG 2.5.8)
  (f) Text < 11px; input/select/textarea < 16px (iOS-Auto-Zoom)
  (g) overflow-hidden-Clipping, scrollbare Mini-Bereiche (Hinweis)
  GZ_AUDIT_STRICT=1 → (a),(c),(d),(e-hart) lassen den Lauf fehlschlagen.

Fixes Runde 1:
  - @media (max-width: 899px), (pointer: coarse): input/select/textarea 16px;
    Häkchen/Radios 20px + Label min-height 44px; Btn[sm] 36px; sonstige <button> 36px;
    Textfelder 40px; segmented-item 36px; Schalter mit ::after-Trefferfläche
  - .g-link-tap: Padding + negativer Rand → 44px Trefferhöhe ohne Layoutänderung
  - body:has(ios-install-hint|passkey-angebot) .mobile-scroll-pad: +72px Freihaltung
  - @media (max-height: 500px): iOS-Install-Hinweis ausgeblendet (Querformat)
  - StageCardM .top/.date-edit: flex-wrap (Zeitfeld ragte auf 390px aus dem Viewport)
  - Kleintexte 9–10.5px → 11px (= --g-text-xs)
```

### Runde 2: Ursachen und Lösungsweg (im Code bestätigt)

Die Messung lief auf HEAD 76ca6e4d9, Deutsch und Englisch, je drei Profile, Chromium. In allen zwölf Läufen waren die harten Kriterien (a), (c), (d) null; hart auffällig war nur „Tap < 24px".

- **Segmente Datum/Uhrzeit (22×26 px):** Ursache ist `[data-segment]{padding:1px 1px}` in `DatumFeld.svelte` und `UhrzeitFeld.svelte`. `StageDateField`/`StageTimeField` sind nur Hüllen, `trip-new` nutzt `DatumFeld groesse="gross"`. Lösung: Segmentbreite per Padding auf mindestens 24 px im Touch-/≤899-px-Fall anheben, nicht per `::after`-Trefferfläche, weil sich benachbarte Segmente sonst überlappen. Natives `type=date` ist verworfen, weil es die Segmentbausteine aus #2881 rückgängig machen würde. Ein Fix in zwei Bausteinen deckt Etappen-Tab, Trip-Anlegen und Vergleichs-Editor ab.
- **Brotkrumen im Hub-Kopf (scrollHeight 30 / clientHeight 17):** Der Link trägt `.g-link-tap` (±13 px Padding/Rand) in einem Container mit `overflow:hidden`, die Trefferfläche wird mitbeschnitten. Lösung in `HubKopf.svelte`: nur horizontal beschneiden (`overflow-x:clip` mit passendem Block-Padding). Wirkt in Trip- und Vergleichs-Hub.
- **Höhenprofil-Etappenwahl (23–24×164 px):** Ein transparentes Rechteck je Etappe in der Breite des Streckenanteils. Verbreitern würde bei 8 und mehr Etappen zu Überlappung und Fehlklicks führen. Lösung: dokumentierte Ausnahme nach WCAG 2.5.8 „equivalent", weil dieselbe Etappenwahl im Etappen-Tab mit ausreichend großen Zielen möglich ist. Das Rechteck trägt `data-tap-equivalent`, der Audit wertet es nicht als harten Befund.
- **Weiche Befunde:** 10-px-Texte (Tab-Badges `trip-detail-tab-badge-*` und `compare-detail-tab-orte`, ✉ in der Übersicht, Menülabel „Aktionen") und 28-px-Knöpfe (u. a. „+ Neuer Trip", `compare-list-new-mobile`, „Im Editor öffnen →", `hub-orte-add`, `briefings-laufzeit`). Lösung nur über die vorhandenen zentralen Regeln in `app.css` im Block `@media (max-width: 899px), (pointer: coarse)` (36-px-Boden, 11-px-Text), keine Einzelhacks.
- **/compare:** ein `<main>` scrollt 16 px waagerecht (374/358), von Check (a) nicht erfasst. **/compare/new nur in EN:** `cm-mobile-tabbar` scrollt waagerecht (378/358). Entscheidung nach Messung der Ursache: entweder Überlauf beheben oder die Leiste bewusst als scrollbar erkennbar machen, sodass der letzte Reiter erreichbar bleibt.
- **Audit-Mängel:** Trefferkappung (15/20/12 je View) und eine Verzweigung in `LAYOUT_CHECK` ließen Treffer unter 24 px in die weiche Liste rutschen (die Zahlen waren Untergrenzen). Die Weiterleitungs-Erkennung `route.startsWith(landed)` verdeckte, dass `/trips/[id]/edit` und `/compare/[id]/edit` per 307 auf die Detailseite leiten.

### Runde 2: Audit-Härtung

- Zähler ungekappt; harte Treffer landen immer in der harten Liste.
- Weiterleitungen werden im Report als solche (mit Status und Ziel) ausgewiesen, nicht als geprüfte Route.
- Prüfung auf waagerechten Überlauf von `<main>` allgemein, nicht nur auf Seitenebene.
- Zusätzliche Routen: ausgeloggte Startseite `/`, `/reset-password`, `/verify-email`, `/magic-link` (und verify), Wizard-Schritte größer 1 von `/trips/new` und `/compare/new`. `/trips/[id]/edit` und `/compare/[id]/edit` werden als Weiterleitung dokumentiert, ihre Editor-Tabs auf der Detailseite geprüft. `/gpx-upload` (301 nach `/trips/new`) bleibt zu Recht übersprungen.
- Tab-Namen: Trip-Detail übersicht / etappen / wetter / zustellung; Vergleich-Detail übersicht / orte / wetter / zustellung (Quelle: `shared/subscriptionTabs.ts`).
- Sprache: `GZ_AUDIT_LOCALE=de|en` setzt Browser-Locale und Profilsprache des Seed-Nutzers (`PUT /api/auth/profile`) und setzt sie nach dem Lauf zurück.
- Staging-Schutz: Die Audit-Config bricht ab, wenn `GZ_E2E_API_PROXY_TARGET` nicht gesetzt ist.

## Expected Behavior

- **Input:** Preview auf `localhost:4173`, lokaler Stack, `playwright/.auth/admin.json`
- **Output:** `test-results/mobile-ux/report-<projekt>[-public].{json,md}` + Screenshots je Route/Tab/Overlay; Weiterleitungen sind im Report gekennzeichnet
- **Side effects:** nur lesende Navigation; Overlays werden per Escape geschlossen. Mit `GZ_AUDIT_LOCALE=en` wird die Profilsprache des lokalen Seed-Admins vorübergehend geändert und danach zurückgesetzt (nur lokaler Stack, nie Staging oder Produktion).

## Acceptance Criteria

Runde 1 (v1.0; AC-3 und AC-6 auf die heutigen Tab-Namen fortgeschrieben):

- **AC-1:** Given ein Trip mit 8 Etappen und Datums-/Zeitbearbeitung / When der Etappen-Tab auf 390px Breite geöffnet wird / Then liegt kein interaktives Element (Datum, Startzeit) horizontal außerhalb des Viewports und die Seite hat keinen horizontalen Overflow.
  - Test: `mobile-ux-audit.spec.ts` (strict) — `offscreenInteractive` und `pageOverflowPx` leer auf `/trips/[id]#etappen`.

- **AC-2:** Given der iOS-Install-Hinweis ist sichtbar / When eine beliebige Seite bis zum Ende gescrollt wird / Then sind Footer-Links und letzte Bedienelemente antippbar (nicht unter Hinweis oder Bottom-Nav).
  - Test: Audit-Check (d) `coveredInteractive` leer auf allen Routen.

- **AC-3:** Given die Tabs „Wetter" und „Zustellung" (Trip und Vergleich) / When die Schwellen-Knöpfe und Kanal-Schalter gemessen werden / Then ist jedes Tap-Ziel mindestens 24×24px (Schalter inkl. unsichtbarer Trefferfläche, Knöpfe ≥ 32px hoch).
  - Test: Audit-Check (e) `tinyTargets` leer auf `#wetter` und `#zustellung`.

- **AC-4:** Given Login-, Registrier- und Passwort-vergessen-Seite im Querformat / When die Seite geladen wird / Then haben alle Eingabefelder ≥ 16px Schrift und die Textlinks ≥ 44px Trefferhöhe.
  - Test: Audit `öffentliche Routen` (landscape): `smallInputs` und `tinyTargets` leer.

- **AC-5:** Given Konto-Sheet, Karten-Menü und Sende-Dialog / When sie auf dem Telefon geöffnet werden / Then sind sie sichtbar, ohne horizontalen Overflow und ohne Tap-Ziel < 24px.
  - Test: Audit `OVERLAYS`-Proben (`konto-sheet`, `karten-menue`, `sende-dialog`).

- **AC-6:** Given native Häkchen/Radios in den Tabs „Wetter" und „Zustellung" (Wetter-Metriken, Mail-Format, Vorschau) / When auf Touch/≤899px gerendert / Then sind sie 20px groß und ihr Label mindestens 44px hoch.
  - Test: Audit-Check (e) auf `#wetter` und `#zustellung`.

Runde 2 (v1.1):

- **AC-7:** Given ein Trip mit mehreren Etappen auf einem Telefon-Profil (390×844, 402×874 oder 844×390) / When im Etappen-Tab die Datumsfelder (Tag, Monat) und die Startzeit-Felder (Stunde, Minute) sowie im Trip-Anlegen das Datumsfeld vermessen werden / Then ist jedes Segment mindestens 24×24 px groß, in Deutsch und Englisch.
  - Test: Playwright-Messtest `issue-2601-*.spec.ts` liest `getBoundingClientRect()` aller Segmente (`stage-date-field`, `stage-start-time-field`, `trip-new-date-input`) in allen drei Profilen.

- **AC-8:** Given der Vergleichs-Editor mit Datums- und Uhrzeitsegmenten auf einem Telefon-Profil / When die Segmente vermessen werden / Then gelten dieselben Mindestgrößen von 24×24 px wie im Trip-Editor, ohne dass dafür eine Compare-eigene Regel existiert.
  - Test: Messtest im Vergleichs-Editor (`context="vergleich"`), identische Schwelle; die Größe stammt aus den geteilten Bausteinen DatumFeld und UhrzeitFeld.

- **AC-9:** Given der Desktop mit 1280×800 und Maus / When Datums- und Uhrzeitfelder im Etappen-Tab und im Trip-Anlegen angezeigt werden / Then sind ihre Segmentmaße gegenüber dem Stand vor Runde 2 unverändert (optisch keine Verbreiterung).
  - Test: Playwright-Gegenprobe bei 1280×800 vergleicht die berechneten Segmentbreiten mit den festen Soll-Werten des Vorzustands.

- **AC-10:** Given der Hub-Kopf eines Trips und eines Vergleichs auf einem Telefon-Profil / When der Brotkrumen-Link vermessen wird / Then wird er nicht abgeschnitten, das heißt scrollHeight ist höchstens clientHeight des Brotkrumen-Bereichs und die volle Trefferfläche bleibt sichtbar.
  - Test: Messtest liest `scrollHeight`/`clientHeight` von `hub-kopf-breadcrumb` in Trip- und Vergleichs-Hub; der Link bleibt antippbar (`elementFromPoint` trifft den Link).

- **AC-11:** Given die Übersicht eines Trips mit Höhenprofil auf einem Hochformat-Profil / When der Audit die Etappenwahl im Profil prüft / Then wird das Profil-Rechteck als dokumentierte Ausnahme nach WCAG 2.5.8 „equivalent" nicht als harter Befund gewertet (Attribut `data-tap-equivalent`), und dieselbe Etappenwahl ist im Etappen-Tab mit Zielen von mindestens 24×24 px möglich.
  - Test: Audit im strengen Modus bleibt auf `#uebersicht` grün; Messtest bestätigt, dass die Etappenwahl im Etappen-Tab ≥ 24 px große Ziele bietet.

- **AC-12:** Given die Seite /compare und die Seite /compare/new in Englisch auf einem Telefon-Profil / When der Überlauf im Hauptbereich und in der Mobil-Tabbar gemessen wird / Then scrollt der `<main>` von /compare nicht waagerecht (Überlauf ≤ 1 px), und die Tabbar von /compare/new hat entweder keinen waagerechten Überlauf oder ist als bewusst scrollbare Leiste erkennbar, sodass der letzte Reiter erreichbar bleibt und kein Inhalt unerreichbar ist.
  - Test: Messtest liest `scrollWidth`/`clientWidth` von `main` und `cm-mobile-tabbar`; der letzte Reiter wird angetippt (bzw. in Sicht gescrollt) und ist erreichbar.

- **AC-13:** Given die mobil sichtbaren Oberflächen (Tab-Badges, ✉-Zeichen in der Übersicht, Menülabel „Aktionen") / When die berechnete Schriftgröße gemessen wird / Then ist kein mobil sichtbarer Text kleiner als 11 px.
  - Test: Audit-Check (f) `smallText` ist in allen drei Profilen in DE und EN leer.

- **AC-14:** Given Knöpfe, die bisher nur 28 px hoch waren („+ Neuer Trip", „Im Editor öffnen →", Orte hinzufügen, Laufzeit im Briefing) / When sie auf Touch oder ≤899 px gerendert werden / Then erreichen sie mindestens den bestehenden 36-px-Boden aus `app.css`, erreicht über die vorhandenen zentralen Regeln und ohne Einzelhacks pro Komponente.
  - Test: Messtest liest die berechnete Höhe der genannten Knöpfe (`trip-list-new-mobile`, `compare-list-new-mobile`, `hub-orte-add`, `briefings-laufzeit`) und erwartet ≥ 36 px.

- **AC-15:** Given der gehärtete Audit / When er läuft / Then zählt er Treffer ungekappt (harte Treffer unter 24 px erscheinen nie in der weichen Liste), weist Weiterleitungen als solche aus, prüft den `<main>`-Überlauf allgemein und deckt zusätzlich ab: ausgeloggte Startseite `/`, `/reset-password`, `/verify-email`, `/magic-link` (und verify), Wizard-Schritte größer 1 von `/trips/new` und `/compare/new` sowie die Editor-Tabs hinter `/trips/[id]/edit` und `/compare/[id]/edit` (dokumentiert als Weiterleitung auf die Detailseite).
  - Test: Der Report enthält je Route Status und Weiterleitungs-Ziel, die neuen Routen erscheinen als geprüft; ein absichtlich 20 px großes Probeelement wird auch jenseits der alten Kappungsgrenze als hart gezählt.

- **AC-16:** Given der Audit-Lauf mit `GZ_AUDIT_LOCALE=de` oder `en` / When der Lauf startet / Then setzt er Browser-Locale und Profilsprache des Seed-Nutzers passend, zeigt die Oberfläche in der gewählten Sprache und stellt die Profilsprache danach wieder her; ohne gesetztes `GZ_E2E_API_PROXY_TARGET` bricht die Config vor dem ersten Test ab, sodass der Lauf nie Staging trifft.
  - Test: Lauf mit `GZ_AUDIT_LOCALE=en` zeigt englische Beschriftungen und Profilsprache `de` danach wieder; Start ohne `GZ_E2E_API_PROXY_TARGET` endet mit Fehlermeldung und ohne einen einzigen Netzwerkzugriff.

- **AC-17:** Given alle Fixes der Runde 2 sind umgesetzt / When `GZ_AUDIT_STRICT=1` in Deutsch und Englisch in allen drei Profilen läuft / Then sind die harten Kriterien (a), (c), (d) und Tap unter 24 px überall grün, und die Befundliste (Vorher/Nachher) steht als Kommentar im Issue #2601.
  - Test: sechs strenge Läufe (DE und EN × drei Profile) enden grün; der Kommentar im Issue #2601 enthält die Gegenüberstellung.

## Definition of Done

- AC-7 bis AC-17 sind durch die genannten Tests bzw. Audit-Läufe nachgewiesen; AC-1 bis AC-6 (Runde 1) bleiben grün.
- Strikter Audit (`GZ_AUDIT_STRICT=1`) ist in DE und EN in allen drei Profilen grün.
- Desktop-Gegenprobe 1280×800 zeigt keine Veränderung an Segmentfeldern und Hub-Kopf.
- Befundliste Runde 2 (Vorher/Nachher) steht als Kommentar in #2601.
- Alle Fixes in einem PR, alle CI-Checks grün, Staging-Verifikation bestanden.

## Test Plan

- **Messtests (Playwright, Kern-Schicht im CI-`e2e`-Job):** `frontend/e2e/issue-2601-*.spec.ts` liest berechnete Größen (`getBoundingClientRect`, computed style) — Segmente Tag/Monat/Stunde/Minute ≥ 24×24 px in Etappen-Tab, Trip-Anlegen und Vergleichs-Editor (AC-7, AC-8); Desktop 1280×800 unverändert (AC-9); Brotkrumen `scrollHeight ≤ clientHeight` in Trip- und Vergleichs-Hub (AC-10); `<main>` auf /compare ohne Überlauf > 1 px, letzter Reiter der EN-Tabbar erreichbar (AC-12); kein sichtbarer Text < 11 px an den Fundstellen (AC-13); Knopfhöhen ≥ 36 px (AC-14).
- **Audit-Lauf (lokal, wiederholbar):** `playwright.mobile-ux.local.config.ts` mit `GZ_AUDIT_LOCALE=de` und `=en`, je drei Profile, Report- und Strikt-Modus (AC-11, AC-15, AC-16, AC-17); Selbsttest der Härtung über ein 20-px-Probeelement jenseits der alten Kappungsgrenze.
- **Kein Mock-Theater, keine Dateiinhalt-Checks;** Nachweis immer über das gerenderte Element.

## Known Limitations

- Nur Chromium-Emulation (kein WebKit in der Umgebung); Safari-spezifisches Rendering bleibt dem Staging-Audit (`playwright.mobile-usability.config.ts`) vorbehalten und ist hier unbeobachtbar.
- Tap-Ziele zwischen 24 und 40px bleiben Hinweise (Runde 1: 116 Stellen, v. a. 32–36px-Chips; Runde 2: 48 Selektoren vor dem Fix) — kein Blocker.
- Nach Runde 2 bleiben keine bewussten 10-px-Texte mehr; falls ein Baustein von Drittanbietern (bits-ui-Menü) den Wert nicht über CSS zulässt, wird das im Report vermerkt.
- Die harten Zahlen aus Runde 2 waren Untergrenzen, weil die Zähler gekappt waren; nach der Audit-Härtung können weitere Treffer sichtbar werden.
- `pointer: coarse` greift auch auf Touch-Laptops größer 899 px; bei den Segmentfeldern ist das harmlos, andere Regeln im Block wirken dort ebenfalls.
- Das Höhenprofil bleibt bei Etappen mit kleinem Streckenanteil unter 24 px breit; das ist die dokumentierte WCAG-2.5.8-Ausnahme mit gleichwertiger Bedienung im Etappen-Tab.
- Englische Übersetzungslücken (Filterchips ALLE/AKTIV/GEPLANT/PAUSIERT/FERTIG, Status „AKTIV", „AKTIONEN", „WETTER-BRIEFING" auf /login) sind kein Mobile-Befund und nach #2919 (Epic #2730) ausgegliedert.
- Der Seed legt keinen Vergleich an; Vergleichs-Routen brauchen einen manuell angelegten Vergleich.

## Laufanleitung (lokal, kurz)

1. Stack auf freien Ports starten: `GZ_CI_STACK_GO_PORT=8191`, `GZ_CI_STACK_PY_PORT=8102` (`frontend/e2e/ci-stack.sh`).
2. Vorschau-Build starten und die Variablen setzen: `GZ_E2E_API_PROXY_TARGET=http://localhost:8191`, `GZ_API_BASE` auf dasselbe Ziel, `GZ_REPO_ENV_FILE=/nonexistent`.
3. Audit mit `frontend/playwright.mobile-ux.local.config.ts` starten, wahlweise mit `GZ_AUDIT_LOCALE=de` oder `en` und für den strengen Lauf mit `GZ_AUDIT_STRICT=1`. Report unter `test-results/mobile-ux/`.

**Sicherheitsfalle:** Der Vorschau-Proxy `/api` zeigt per Default auf `localhost:8091`, und das ist Staging (`vite.config.ts`, `API_PROXY_TARGET`). Ohne `GZ_E2E_API_PROXY_TARGET` darf der Lauf nicht starten; ein erster Versuch traf Staging mit 401 (nichts geschrieben). Vergleichs-Routen brauchen einen vorher manuell angelegten Vergleich, weil der Seed keinen anlegt.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** reine Darstellungs-/Erreichbarkeits-Korrekturen und ein zusätzlicher Nachweis; keine Entscheidungsfläche berührt. Die Ausnahme für das Höhenprofil folgt WCAG 2.5.8 und ist hier dokumentiert.

## Changelog

- 2026-10-22: Erstfassung (#2601), Runde 1, geliefert mit PR #2602.
- 2026-11-10: v1.1 (Runde 2, HEAD 76ca6e4d9, DE und EN × 3 Profile): Tab-Namen in AC-3/AC-6 auf übersicht/etappen/wetter/zustellung aktualisiert; neue AC-7 bis AC-17 (Segmentgrößen, Brotkrumen, Höhenprofil-Ausnahme, /compare-Überlauf, weiche Befunde, Audit-Härtung, Sprache, Staging-Schutz, strenger Lauf); Laufanleitung ergänzt. Status wieder `draft`, Freigabe durch den PO steht aus.
