---
entity_id: fix_2794_s3a_teil4b_befunde
type: bugfix
created: 2026-11-12
updated: 2026-11-12
status: draft
version: "1.0"
workflow: fix-2794-s3a-teil4b-befunde
tags: [hub, reiter, uebersicht, texte, mockup, handy, epic-2791, issue-2794]
---

# Einstellungen neu S3a, Teil 4b: Fix-Loop zu den Mockup-Abweichungen (#2794)

## Approval

- [ ] Approved

## Purpose

Der Fresh-Eyes-Abgleich auf Staging (Stand bf071a33c) hat nach Teil-PR 4b vier Abweichungen vom Mockup Fassung 3 und einen Nebenbefund gefunden. Diese Spec behebt sie, damit Issue #2794 gegen das Mockup abgenommen werden kann: kurzer Reiter-Name „Etappen“, vollständige Pill-Leiste am Handy, volle Kartenbreite in der Hub-Übersicht, eine ehrliche Metrik-Zahl auf der Karte „Wetter“ der Orts-Vergleiche und ein korrekter deutscher Titel „Alarme · letzte 24 h“.

Quelle der Befunde: `docs/context/fix-2794-s3a-teil4b-befunde.md`. Vorgänger-Spec: `docs/specs/modules/feat_2794_s3a_teil4_entfernen.md`. Die neuen Kriterien beginnen bei AC-1 dieser Spec und gelten zusätzlich zu den Kriterien der Vorgänger-Specs.

## Source

- **Frontend (Reiter, B1/B2):** `frontend/src/lib/components/shared/subscriptionTabs.ts`, `frontend/src/lib/components/trip-detail/TripTabs.svelte`, `frontend/src/lib/components/mobile/MTabBar.svelte`
- **Frontend (Übersicht, B3/B4):** `frontend/src/lib/components/shared/hub-uebersicht/HubUebersicht.svelte`, `hubUebersichtModell.ts`, `frontend/src/lib/components/shared/wetter-tab/wetterZustand.ts` (nur lesen), `frontend/src/lib/components/trip-detail/HubOverview.svelte` (Muster zum Laden der Vorlagen), `frontend/src/lib/utils/cockpitHelpers568.ts`
- **Texte (B1, B4, B5):** `frontend/src/lib/i18n/messages/{de,en}/{aktionen,home,vergleich,bausteine}.json`, Verwendung `frontend/src/routes/+page.svelte` (Zeilen 292 und 362)
- **Doku:** `docs/reference/i18n_glossar.md` (nur lesen)
- **Identifier:** `REITER_DEFINITION` (subscriptionTabs.ts), `badges.etappen` (TripTabs.svelte), Pill-Leiste `MTabBar`, Karten-Grid in `HubUebersicht`, Wetter-Karte in `hubUebersichtModell` (`wertebereicheKarte`), `standAusAbo` (wetterZustand.ts), `setupStepCompare` (cockpitHelpers568.ts); Katalog-Schlüssel `aktionen.reiter.etappen` (neu), `aktionen.reiter.etappen_wegpunkte`, `home.aktion.pausentag_ziel`, `vergleich.hub.wertebereiche_kurz`, `vergleich.hub.wertebereiche_lang`, `bausteine.alarme.titel`

> **Schicht-Hinweis:** Alles Frontend (SvelteKit). Go-API und Python-Core bleiben unberührt.
>
> **Trip/Ortsvergleich-Teilung (PFLICHT, #1170, Epic #2345):** Reiterleiste und Hub-Übersicht bleiben geteilter Code (`context="route"|"vergleich"`). Es entsteht keine neue Komponente mit Pendant; die Zählung der Karte „Wetter“ nutzt dieselbe Funktion wie der Reiter Wetter.
>
> **Mandantentrennung:** Es entsteht kein neuer Datenweg; es werden nur bereits geladene Nutzerdaten gelesen. Bestandsdaten (alte `ideal_ranges`) werden nur gelesen, nie verändert (ADR-0101).
>
> **Kanäle:** Keine Änderung an Briefing- oder Alarm-Inhalt in E-Mail · Telegram · SMS · Premium-SMS.

## Estimated Scope

- **LoC:** ca. +120/-60 ohne Testanpassungen
- **Files:** ca. 12 Produktivdateien, ca. 12 Testdateien, 4 mitgelieferte Staging-Dateien
- **Effort:** medium (Risiko MEDIUM: viele Tests mit festem Wortlaut; B4 ändert die Startseiten-Checkliste für Orts-Vergleiche)

## Scope

**Im Scope:** B1 bis B5, Nachziehen aller Tests mit altem Wortlaut oder Layout, Mitliefern der Staging-Specs aus Teil 4b, Soll/Ist-Bild gegen Mockup (ADR-0112) für Trip und Orts-Vergleich, Desktop und Handy.

**Nicht im Scope:**
- #2913 (Seitenkopf): „Senden“ statt „Test schicken ▾“, Kennzeile, Aktivitäts-/Vorlage-Knöpfe, Pfad „Orts-Vergleiche /“, abgeschnittener Pfad am Handy.
- #1199 (Sammel): Listenlayout „AKTIV3 Etappen“, „tägl. 06“, „Senden“ gegen „Briefing senden“.
- Umbenennung der Eyebrow „Versand“ (bleibt, siehe B3).

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| frontend/src/lib/i18n/messages/{de,en}/aktionen.json | MODIFY | Neuer Schlüssel `aktionen.reiter.etappen` („Etappen“ / „Stages“); `etappen_wegpunkte` bleibt |
| frontend/src/lib/components/shared/subscriptionTabs.ts | MODIFY | Trip-Reiter nutzt `aktionen.reiter.etappen` |
| frontend/src/lib/i18n/messages/{de,en}/home.json | MODIFY | `home.aktion.pausentag_ziel` → „→ Etappen“ / „→ Stages“ |
| frontend/src/lib/components/mobile/MTabBar.svelte | MODIFY (nur falls Messung es verlangt) | Pill-Innen- und Zwischenabstände; Wischen bleibt Fallback |
| frontend/src/lib/components/shared/hub-uebersicht/HubUebersicht.svelte | MODIFY | Grid `repeat(auto-fit, minmax(280px, 1fr))`; Vorlagen/Katalog für den Vergleich bereitstellen |
| frontend/src/lib/components/shared/hub-uebersicht/hubUebersichtModell.ts | MODIFY | Karte „Wetter“ zählt `standAusAbo('vergleich', …).auswahl`; „—“ ohne Vorlagen |
| frontend/src/lib/i18n/messages/{de,en}/vergleich.json | MODIFY | Texte der Karte „Wetter“ neu, echter Singular/Plural, ohne „Idealbereich“ und „Markierung, kein Score“ |
| frontend/src/lib/utils/cockpitHelpers568.ts | MODIFY | `setupStepCompare`, Schritt Wetter, nach gewählten Metriken |
| frontend/src/lib/i18n/messages/{de,en}/bausteine.json | MODIFY | DE `bausteine.alarme.titel` = „Alarme · letzte 24 h“ |
| frontend/src/lib/i18n/__tests__/deutsch_unveraendert.test.ts | MODIFY | Ratsche bewusst auf „→ Etappen“ und „Alarme · letzte 24 h“ nachziehen |
| Unit-Tests: shared/__tests__/subscription_tabs_resolve.test.ts, shared/__tests__/hub_reiter_gemeinsame_aufloesung.test.ts, trip-detail/__tests__/trip_hub_sprache.test.ts, trip-detail/__tests__/f9KatalogAnker.ts, compare/__tests__/f10KatalogAnker.ts, shared/hub-uebersicht/__tests__/, molecules/issue_578_molecules_organisms.test.ts | MODIFY | Wortlaut bewusst anpassen, nicht löschen |
| frontend/src/lib/components/compare/__tests__/fixtures/hub_uebersicht_charakterisierung.json | MODIFY | Charakterisierung bewusst nachziehen (Grid, Wetter-Zahl und -Text) |
| e2e: issue-616-trip-one-surface.spec.ts, issue-302-trip-detail-redesign.spec.ts, trip-detail-tabs.spec.ts, issue-269-mobile-trip-tabs.spec.ts, compare-hub-fidelity-s8c.spec.ts, hub-versand-briefing-zeiten.spec.ts | MODIFY | Reiter-Wortlaut und Layout bewusst nachziehen |
| frontend/e2e/s3a2794-teil4b-staging.spec.ts, frontend/e2e/s3a2794-teil4b-bilder.staging.spec.ts | CREATE (mitliefern) | Bisher nicht eingecheckte Staging-Specs aus Teil 4b |
| frontend/playwright.2794-s3a4b.staging.config.ts, frontend/playwright.2794-s3a4b-bilder.staging.config.ts | CREATE (mitliefern) | Zugehörige Playwright-Konfigurationen |

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `standAusAbo` (`wetter-tab/wetterZustand.ts`) | function | Einzige Quelle der gewählten Metriken, geteilt mit Reiter Wetter |
| `trip-detail/HubOverview.svelte` | component | Muster zum Laden von Vorlagen und Katalog |
| `TripTabs.svelte` (badges.etappen) | component | Bestehender Zähler am Reiter Etappen |
| i18n-Kataloge und Ratsche `deutsch_unveraendert.test.ts` | catalog | Zweisprachigkeit (ADR-0104), Wortlaut-Ratsche |
| `docs/reference/i18n_glossar.md` | doc | Begriffe „Alarme“, „Versand“, „Zustellung“ |
| `docs/specs/modules/mobile_tab_leisten_mtabbar.md` | spec | Wisch-Verhalten und Mindest-Trefferhöhe |
| Mockup `docs/context/einstellungen_neu/seiten/mockup-hub-fassung3.html` | design | Bild-Soll (Z. 168, 305-320, 579), ADR-0112 |

## Implementation Details

**B1 Reiter-Label.** Neuer Katalog-Schlüssel `aktionen.reiter.etappen` („Etappen“ / „Stages“). `subscriptionTabs.ts` verweist für den Trip-Reiter darauf; Desktop-Leiste und Handy-Pill-Leiste lesen beide dort. `aktionen.reiter.etappen_wegpunkte` bleibt unverändert für die Bereichsüberschrift im Reiter (Mockup Z. 579). Der Zähler am Reiter (`TripTabs.svelte`, Zahl der Etappen) entspricht dem Mockup „Etappen 4“ und bleibt unverändert. `home.aktion.pausentag_ziel` wird „→ Etappen“ / „→ Stages“, weil es auf den Reiter verweist.

**B2 Handy-Leiste.** Nach B1 wird auf Staging bei 360, 375 und 390 px (DE und EN) gemessen. Passen die vier Pills noch nicht ohne Wischen, werden Innen- und Zwischenabstände der Pills in `MTabBar.svelte` reduziert. Mindest-Trefferhöhe 44 px, `overflow-x`-Wisch-Fallback und die Regel „aktiver Reiter immer voll sichtbar“ bleiben.

**B3 Karten-Grid.** In `HubUebersicht.svelte` wird `1fr 1fr` durch `repeat(auto-fit, minmax(280px, 1fr))` ersetzt (Mockup-Muster `.two`). Eine einzelne Karte füllt die Zeile; drei Karten brechen ohne leere Hälfte um. Die Handy-Darstellung (`hub-summary-row-mobile`) bleibt unverändert. Eyebrow „Versand“ bleibt, weil das Glossar Versand als Abschnitt des Reiters Zustellung führt und das Sprungziel genau dieser Abschnitt ist.

**B4 Karte „Wetter“ und Checkliste.** `hubUebersichtModell.ts` zählt die Metriken über `standAusAbo('vergleich', preset, vorlagen).auswahl`, nicht mehr über `ideal_ranges`. Vorlagen und Katalog werden wie in `HubOverview.svelte` geladen. Ohne geladene Vorlagen oder bei Ladefehler zeigt die Karte „—“ statt einer Zahl (wie Trip-Zähler U4). Neue Texte:
- DE kurz: „{count} Metriken im Briefing“, Singular „1 Metrik im Briefing“; lang analog, ohne „Idealbereich“ und „Markierung, kein Score“.
- EN entsprechend mit echtem Singular und Plural.

`setupStepCompare` in `cockpitHelpers568.ts` ist synchron und kennt keine Vorlagen. Regel für den Schritt Wetter: erledigt, wenn `display_config.active_metrics` nicht leer ist ODER keine Liste gespeichert ist (dann gilt die Vorlage, also sind Metriken vorhanden); offen nur bei ausdrücklich leerer Liste. So laufen Reiter Wetter und Checkliste nicht auseinander. Alte `ideal_ranges` werden nicht mehr ausgewertet und nie verändert.

**B5 Alarme-Titel.** DE `bausteine.alarme.titel` = „Alarme · letzte 24 h“; EN bleibt „Alerts · last 24 h“. Der Titel erscheint auf der Startseite (`routes/+page.svelte:362`).

**Mitliefern.** Die vier Staging-Dateien werden unverändert in den Fix aufgenommen.

## Expected Behavior

- **Input:** Nutzer öffnet Trip- und Orts-Vergleich-Seiten auf Desktop und Handy sowie die Startseite, DE und EN.
- **Output:** Reiter „Etappen“ mit Zähler, vollständige Pill-Leiste am Handy, Übersichtskarten ohne halbleere Reihen, korrekte Metrik-Zahl mit Singular/Plural, Checkliste passend zum Reiter Wetter, Titel „Alarme · letzte 24 h“.
- **Side effects:** Keine Datenänderung; Tests mit altem Wortlaut sind bewusst angepasst.

## Test Plan

### Automated Tests (TDD RED)

Kern-Schicht (Unit, `node --test`, deterministisch):
- [ ] Katalog: Reiter-Label des Trips löst in DE zu „Etappen“, in EN zu „Stages“ auf; Bereichsüberschrift bleibt „Etappen & Wegpunkte“ / „Stages & waypoints“.
- [ ] `home.aktion.pausentag_ziel` ergibt „→ Etappen“ (DE) und „→ Stages“ (EN); Ratsche `deutsch_unveraendert` entsprechend nachgezogen.
- [ ] Modell der Übersicht: Vergleich mit 3 gewählten Metriken liefert Zahl 3 aus `standAusAbo`, mit 1 Metrik den Singulartext, ohne Vorlagen „—“.
- [ ] Modell: Vergleich mit Profil ohne `ideal_ranges`, aber mit Vorlage-Metriken, zeigt nicht mehr 0.
- [ ] `setupStepCompare`: `active_metrics` nicht leer ⇒ erledigt; keine Liste gespeichert ⇒ erledigt; ausdrücklich leere Liste ⇒ offen; `ideal_ranges` ohne Einfluss.
- [ ] Katalogtexte der Karte „Wetter“ enthalten weder „Idealbereich“ noch „Markierung, kein Score“; Plural-Formen `one` und `other` unterscheiden sich in DE und EN.
- [ ] `bausteine.alarme.titel` DE = „Alarme · letzte 24 h“; Glossar-Wächter bleibt grün.
- [ ] Charakterisierungs-Fixture der Hub-Übersicht neu geschrieben (Grid-Regel, Wetter-Zahl und -Text).

Live-E2E / Staging (nur in `/e2e-verify`, Playwright):
- [ ] Messung der Pill-Leiste bei 360/375/390 px, DE und EN: Bounding-Box jeder der vier Pills liegt vollständig innerhalb der Leiste; Höhe mindestens 44 px.
- [ ] Desktop-Übersicht Trip: Versand-Karte füllt die Zeile (Breite ≥ 90 % des Rasters); Orts-Vergleich: keine Karte allein in halber Breite neben leerer Hälfte.
- [ ] Reiter-Leiste Trip zeigt „Etappen“ mit Zahl; Soll/Ist-Bild gegen Mockup für Trip und Orts-Vergleich, Desktop und Handy.
- [ ] Startseite zeigt „Alarme · letzte 24 h“.
- [ ] Angepasste Alt-E2E (`issue-616`, `issue-302`, `trip-detail-tabs`, `issue-269`, `compare-hub-fidelity-s8c`, `hub-versand-briefing-zeiten`) laufen mit neuem Wortlaut grün.

## Acceptance Criteria

- **AC-1:** Given ein Nutzer öffnet einen Trip auf dem Desktop (DE) / When er die Reiterleiste ansieht / Then heißt der Reiter „Etappen“ (nicht „Etappen & Wegpunkte“), und die Überschrift des Bereichs im Reiter lautet weiterhin „Etappen & Wegpunkte“.
  - Test: Nutzersicht Trip-Detail, Leistenbeschriftung und Bereichsüberschrift per Playwright lesen.

- **AC-2:** Given die Sprache ist Englisch / When der Nutzer die Reiterleiste eines Trips ansieht / Then heißt der Reiter „Stages“ und der Hinweis auf der Startseite zum Pausentag „→ Stages“; in Deutsch lautet dieser Hinweis „→ Etappen“.
  - Test: Katalogauflösung beider Sprachen und Startseite im Browser.

- **AC-3:** Given ein Trip mit vier Etappen / When der Nutzer die Reiterleiste ansieht (Desktop und Handy) / Then zeigt der Reiter „Etappen“ den Zähler 4 wie im Mockup, und der Zähler ist unverändert gegenüber dem Stand vor dem Fix.
  - Test: Zähler am Reiter im Browser lesen, Wert gegen Etappenzahl vergleichen.

- **AC-4:** Given ein Trip auf einem Handy mit 360, 375 oder 390 px Breite (DE und EN) / When die Pill-Leiste erscheint / Then sind alle vier Pills (Übersicht, Etappen, Wetter, Zustellung bzw. Overview, Stages, Weather, Delivery) ohne Wischen vollständig sichtbar, jede mindestens 44 px hoch.
  - Test: Playwright misst die Bounding-Box jeder Pill relativ zur Leiste bei allen drei Breiten und beiden Sprachen.

- **AC-5:** Given eine Pill-Leiste, die bei sehr langen Beschriftungen oder Zählern nicht mehr passt / When der Nutzer wischt / Then lässt sich die Leiste weiterhin seitlich verschieben, und der aktive Reiter ist immer vollständig sichtbar.
  - Test: Playwright mit schmaler Breite, Wischen und Sichtbarkeit des aktiven Reiters prüfen.

- **AC-6:** Given die Übersicht eines Trips auf dem Desktop / When der Nutzer sie öffnet / Then nimmt die Karte „Versand“ die volle Breite der Zeile ein statt nur die Hälfte.
  - Test: Playwright misst die Kartenbreite gegen die Rasterbreite.

- **AC-7:** Given die Übersicht eines Orts-Vergleichs auf dem Desktop mit den drei Karten Orte, Wetter und Versand / When der Nutzer sie öffnet / Then steht keine Karte allein in halber Breite neben einer leeren Hälfte; die Karten füllen jede Zeile, und die Handy-Darstellung der Übersicht bleibt unverändert.
  - Test: Playwright misst Kartenpositionen auf Desktop und Handy.

- **AC-8:** Given ein Orts-Vergleich mit drei im Briefing gewählten Metriken, aber ohne gespeicherte alte Idealbereiche / When der Nutzer die Übersicht öffnet / Then zeigt die Karte „Wetter“ „3 Metriken im Briefing“ (nicht 0), und dieselbe Zahl steht im Reiter Wetter als gewählt.
  - Test: Vergleich mit Metrikauswahl anlegen, Karte und Reiter im Browser vergleichen.

- **AC-9:** Given ein Orts-Vergleich mit genau einer gewählten Metrik / When der Nutzer die Karte „Wetter“ ansieht / Then lautet der Text „1 Metrik im Briefing“ (DE) bzw. „1 metric in the briefing“ (EN), mit echtem Singular; bei mehreren Metriken steht der Plural.
  - Test: Karte in beiden Sprachen im Browser lesen.

- **AC-10:** Given die Vorlagen konnten nicht geladen werden / When der Nutzer die Karte „Wetter“ ansieht / Then steht dort „—“ statt einer erfundenen Zahl, und weder „Idealbereich“ noch „Markierung, kein Score“ erscheint irgendwo in der Karte (Desktop und Handy).
  - Test: Ladefehler simulieren (Unit-Modell), sichtbaren Text prüfen.

- **AC-11:** Given ein Orts-Vergleich mit gewählten Metriken oder ohne gespeicherte Liste (Vorlage gilt) / When die Startseite die Einrichtungs-Checkliste zeigt / Then gilt der Schritt Wetter als erledigt; nur bei einer ausdrücklich leeren Metrikliste steht er auf offen.
  - Test: Unit-Test `setupStepCompare` mit drei Fällen und Startseite im Browser.

- **AC-12:** Given ein Orts-Vergleich mit alten gespeicherten Idealbereichen / When die Übersicht und die Checkliste angezeigt werden / Then bleiben die gespeicherten Bestandsdaten unverändert, sie werden nur gelesen.
  - Test: Preset vor und nach dem Öffnen von Übersicht und Startseite vergleichen (kein Schreibzugriff).

- **AC-13:** Given die Startseite in Deutsch / When der Nutzer den Alarm-Baustein ansieht / Then lautet die Überschrift „Alarme · letzte 24 h“; in Englisch bleibt sie „Alerts · last 24 h“.
  - Test: Startseite in beiden Sprachen im Browser lesen.

- **AC-14:** Given die fertige Umsetzung auf Staging / When Soll/Ist-Bilder gegen Mockup Fassung 3 für Trip und Orts-Vergleich, Desktop und Handy erstellt werden / Then zeigen sie keine der Abweichungen B1 bis B4 mehr und gehen als Bild an den PO.
  - Test: Bildabgleich (ADR-0112) und Fresh-Eyes-Prüfung auf Staging.

- **AC-15:** Given die vier bisher nicht eingecheckten Staging-Dateien aus Teil 4b / When der Fix ausgeliefert wird / Then liegen sie im Repository, und die Staging-Prüfung für Teil 4b läuft damit ohne fehlende Dateien durch.
  - Test: `/e2e-verify` führt die Staging-Specs mit den Konfigurationen aus.

## Definition of Done

- [ ] AC-1 bis AC-15 grün in ihrer Schicht, Kern-Schicht zu 100 % grün, alle 6 CI-Checks grün.
- [ ] Adversary-Verdict VERIFIED inklusive Mutations-Gegenprobe.
- [ ] Messung der Handy-Pill-Leiste (360/375/390 px, DE und EN) auf Staging belegt AC-4.
- [ ] `/e2e-verify` auf Staging grün, Prod-Deploy mit Selftest Exit 0.
- [ ] Soll/Ist-Bild gegen Mockup Fassung 3 (Trip und Orts-Vergleich, Desktop und Handy) an den PO geliefert (AC-14); danach darf Issue #2794 geschlossen werden.

## Known Limitations

- Die Übersicht ist im Mockup „nicht ausgearbeitet“; B3 folgt nur dem Grid-Muster `.two`, nicht einem konkreten Bild.
- Die Checkliste kennt keine Vorlagen; bei fehlender Liste gilt „erledigt“ als bewusste Annäherung an die Reiter-Logik.
- Seitenkopf-Themen (#2913) und Listenlayout (#1199) bleiben offen.

## Risiken

- Viele Tests schreiben „Etappen & Wegpunkte“ oder das alte Layout fest; sie werden bewusst angepasst, nicht gelöscht. Die Bereichsüberschrift im Reiter darf dabei nicht mit umbenannt werden.
- B2 ist nur durch Messung abgeschlossen; ohne Messung auf Staging gilt der Befund als offen.
- B3: Die Trip-Übersicht mit nur einer Karte sieht anders aus; beide Kontexte sind im Bild zu prüfen.
- B4: Weichen Reiter und Checkliste in der Zählregel auseinander, zeigt die Startseite „Wetter offen“ trotz gewählter Metriken. Deshalb gilt die oben festgelegte Regel.
- Ratsche `deutsch_unveraendert.test.ts` und Charakterisierungs-Fixture sind bewusst anzupassen; jede weitere Änderung dort ist ein Befund.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reiner Fix nach bestehenden ADRs (0104 zweisprachig, 0109 Reiterstruktur, 0112 Bildabnahme); keine neue Entscheidungsfläche.

## Changelog

- 2026-11-12: Initial spec created (Fix-Loop zu Teil-PR 4b, Befunde B1 bis B5)
