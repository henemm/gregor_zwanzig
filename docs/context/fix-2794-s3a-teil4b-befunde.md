# Context: fix-2794-s3a-teil4b-befunde

## Request Summary
Fix-Loop zu S3a Teil-PR 4b (#2794): Fresh-Eyes-Abgleich auf Staging (bf071a33c, Kommentar 12.11. 14:16) fand vier Abweichungen vom Mockup Fassung 3 plus einen Nebenbefund. Issue #2794 bleibt bis zur Behebung offen. Zusätzlich mitzuliefern: die noch nicht in `main` liegenden Staging-Specs `frontend/e2e/s3a2794-teil4b-staging.spec.ts`, `s3a2794-teil4b-bilder.staging.spec.ts` und ihre Configs (untracked im Worktree).

## Befunde, Ursache, Soll

### B1 — Trip-Reiter heißt „Etappen & Wegpunkte“ statt „Etappen“
- Ursache: `frontend/src/lib/components/shared/subscriptionTabs.ts:46` → `trip: { id: 'etappen', label: 'aktionen.reiter.etappen_wegpunkte' }`. Desktop-Leiste und MTabBar beide über `trip-detail/TripTabs.svelte:191`.
- Katalog: `de/aktionen.json:26` „Etappen & Wegpunkte“, `en/aktionen.json:26` „Stages & waypoints“.
- Soll (Mockup `docs/context/einstellungen_neu/seiten/mockup-hub-fassung3.html:311`): Reiter „Etappen“ mit Zähler 4; die **Bereichsüberschrift im Reiter** bleibt „Etappen & Wegpunkte“ (Mockup Z. 579). Orte: „Orte [3]“ (Z. 313).
- Weitere Nutzung des Strings: `de/home.json:22` `home.aktion.pausentag_ziel` „→ Etappen & Wegpunkte“ (eigener Schlüssel, Ziel-Hinweis auf den Reiter → mitziehen prüfen).
- Tests mit heutigem Wortlaut: `shared/__tests__/subscription_tabs_resolve.test.ts:51-54`, `shared/__tests__/hub_reiter_gemeinsame_aufloesung.test.ts:231`, `trip-detail/__tests__/trip_hub_sprache.test.ts:112`, `trip-detail/__tests__/f9KatalogAnker.ts:31`; e2e `issue-616-trip-one-surface.spec.ts:26,87`, `issue-302-trip-detail-redesign.spec.ts:71-78`, `trip-detail-tabs.spec.ts:10`, `issue-269-mobile-trip-tabs.spec.ts:83,96-114,159`.

### B2 — Trip Handy: vierter Reiter „Zustellung“ abgeschnitten
- `frontend/src/lib/components/mobile/MTabBar.svelte:155-200` (`max-width: 899px`): `overflow-x:auto`, Snap, Fade-Maske 16px, Pills `flex-shrink:0`, min-height 44px.
- Spec `docs/specs/modules/mobile_tab_leisten_mtabbar.md:97-101,124`: Wischen ist erlaubtes Verhalten, aktiver Reiter immer voll sichtbar. Issue-Text S3a: „Mobil bleibt die Pill-Leiste“.
- Hauptursache vermutlich B1 (langes Label). Hypothese: Mit „Etappen“ passen vier Pills bei 375/390px ohne Wischen — **muss gemessen werden** (Playwright, 360/375/390px). Reicht das nicht: Abstände/Padding der Pills anpassen, nicht die Wisch-Fähigkeit entfernen (Fallback für EN/lange Zähler).

### B3 — Übersicht Desktop: Karte „Versand“ nur halb breit
- `frontend/src/lib/components/shared/hub-uebersicht/HubUebersicht.svelte:162` Grid `1fr 1fr`; Z. 163 `{#each [orteKarte, wertebereicheKarte]}` mit `{#if}`, Z. 175-182 fest Versand-Karte. Vergleich: Orte, Wetter, Versand → Versand allein in Reihe 2. Trip: vermutlich nur Versand (nicht geprüft).
- Mobil Z. 140-156 eigene Zeilen (`hub-summary-row-mobile`), nicht betroffen.
- Mockup: Übersicht „nicht ausgearbeitet“, keine Vorgabe. Muster im Mockup: `.two{grid-template-columns:repeat(auto-fit,minmax(280px,1fr))}` (Z. 168).
- Eyebrow „Versand“ aus `bausteine.checkliste.versand`. Reiter heißt inzwischen „Zustellung“ → Begriffsfrage (Glossar „Versand“ = Abschnitt der Zustellung, siehe Nachtrag AC-49).
- Festschreibung: `compare/__tests__/fixtures/hub_uebersicht_charakterisierung.json` (`1fr 1fr`, Versand-Karte, „2 Metriken mit Idealbereich“); e2e `compare-hub-fidelity-s8c.spec.ts`, `hub-versand-briefing-zeiten.spec.ts`. Spec `docs/specs/modules/feat_2682_hub_uebersicht_geteilt.md`.

### B4 — Orts-Übersicht, Karte „Wetter“: „0 Metriken mit Idealbereich“ / mobil „0 Metriken · Markierung, kein Score“
- Ursache Zahl: `hubUebersichtModell.ts:289-298` zählt `Object.keys(preset.display_config?.ideal_ranges ?? {}).length` — die **alten Idealbereiche**, nicht die gewählten Metriken/Ampel-Grenzen des neuen Reiters Wetter. Profil „wandern“ ohne gespeicherte `ideal_ranges` → 0. `types.ts:763`: neues Feld additiv neben `ideal_ranges` (Dual-Write #1231).
- Gleiche Altlogik: `frontend/src/lib/utils/cockpitHelpers568.ts:82,95-107` (`setupStepCompare`: Wetter gilt nur bei nicht leeren `ideal_ranges` als erledigt) → Checkliste kann fälschlich „Wetter offen“ zeigen.
- Texte: `de/vergleich.json:26-29` `vergleich.hub.wertebereiche_kurz.one/other` „{count} Metriken · Markierung, kein Score“ (one = other, Pluralfehler), `wertebereiche_lang` „{count} Metriken mit Idealbereich — …“; en analog. Alte Begriffe („Idealbereich“, „Markierung, kein Score“ = B7 bewusst entfallen).
- Soll-Richtung: Zahl der Metriken im Briefing, analog zur Trip-Übersicht U4 (Zähler des Reiters Wetter, schon in Teil 4b gebaut: „x von y Metriken lösen einen Alarm aus“) und zur Vorlagen-Kurzbeschreibung im Mockup („10 Metriken · Regen, Sonne, UV“, Z. 319). Gleiche Quelle wie im Reiter Wetter verwenden (Trip/Vergleich teilen Code).
- Tests: `compare/__tests__/f10KatalogAnker.ts:51-52`, Charakterisierungs-Fixture, `shared/hub-uebersicht/__tests__/`.

### B5 (Nebenbefund) — DE `bausteine.alarme.titel` = „Alerts · letzte 24 h“
- `de/bausteine.json:41`, en `Alerts · last 24 h`. Einzige Nutzung `organisms/AlertsCard.svelte:37`; AlertsCard in keiner Route verwendet (nur `organisms/index.ts`, `molecules/issue_578_molecules_organisms.test.ts`, `lib/__tests__/bausteine_waechter_regeln.ts`). Glossar Z. 8-9/19-21: deutsch „Alarme“, „Alert…“ im DE-UI unerwünscht (ADR-0111). Kommentar sagte „Startseite“ — Verwendung auf der Startseite gegen Staging gegenprüfen (evtl. anderer Schlüssel). Kleiner Textfix.

## Nicht in diesem Fix-Loop (zugeordnet)
- #2913 (Seitenkopf): „Senden“ statt „Test schicken ▾“, Kennzeile, Aktivitäts-/Vorlage-Knöpfe, Pfad „Orts-Vergleiche /“, abgeschnittener Pfad am Handy.
- #1199 (Sammel): Listenlayout „AKTIV3 Etappen“, „tägl. 06“, „Senden“ vs. „Briefing senden“.

## Existing Patterns
- Reiter-Definition zentral in `subscriptionTabs.ts`, Labels nur über Katalog-Schlüssel (de+en, ADR-0104); Trip/Vergleich teilen Leiste und Übersicht (`context="route"|"vergleich"`, Pendant-Sperre).
- Übersicht über reines Modell `hubUebersichtModell.ts` + Darstellung `HubUebersicht.svelte`; Teil 4b hat dort schon den Wetter-Zähler für den Trip (U4) eingeführt → für B4 wiederverwenden.
- Abnahme UI: Soll/Ist-Bild gegen Mockup an den PO, Fresh-Eyes, mockup-bildpruefer (ADR-0112).

## Dependencies
- Upstream: i18n-Kataloge `frontend/src/lib/i18n/{de,en}/*.json`, Glossar `docs/reference/i18n_glossar.md`, Preset-/Profil-Datenmodell (`display_config`, neues Ampel-Feld).
- Downstream: Desktop-Reiterleiste, MTabBar, Hub-Übersicht Trip + Orte, Startseite-Checkliste (`cockpitHelpers568`), viele e2e-/Unit-Tests mit festem Wortlaut (Liste oben).

## Existing Specs
- `docs/specs/modules/feat_2794_s3a_teil4_entfernen.md` (Teil 4b, Phase 8 abgeschlossen) — Fix-Loop-Spec kann hier ergänzen oder eigene kleine Spec.
- `feat_2794_s3a_teil2_leiste.md`, `rework_2845_hub_reiterleiste.md`, `mobile_tab_leisten_mtabbar.md`, `feat_2682_hub_uebersicht_geteilt.md`.

## Risks & Considerations
- Viele Tests schreiben „Etappen & Wegpunkte“ fest; bewusst anpassen, nicht löschen. Bereichsüberschrift im Reiter bleibt laut Mockup „Etappen & Wegpunkte“ — nicht mit umbenennen.
- B2 nur durch Messung abschließen (mehrere Handybreiten, DE und EN; EN-Label „Stages“).
- B3: Grid auf `auto-fit/minmax` kann Trip-Übersicht (nur eine Karte?) anders aussehen lassen — beide Kontexte im Bild prüfen.
- B4: Zählquelle muss dieselbe wie im Reiter Wetter sein; Checkliste `cockpitHelpers568` mitziehen, sonst zeigt die Startseite „Wetter offen“ trotz gewählter Metriken. Bestandsdaten mit alten `ideal_ranges` nur lesen, nicht verändern.
- Untracked Staging-Specs/Configs aus Teil 4b mit in den Fix-PR aufnehmen (sonst blockt `finish` des alten Workflows weiter).

## Analysis

### Type
Bug (Fix-Loop zu Teil-PR 4b, Abweichungen vom Mockup Fassung 3)

### Nachgeprüfte Fakten (12.11.2026, Phase 2)
- B3 betrifft **beide** Kontexte: `HubUebersicht.svelte:162` Grid `1fr 1fr`; Trip hat weder `orteKarte` noch `wertebereicheKarte` (nur Vergleich setzt sie, `hubUebersichtModell.ts:326-327`) ⇒ auf dem Trip steht die Versand-Karte allein in halber Breite, im Vergleich allein in Reihe 2.
- B4 Zählquelle: Der Reiter Wetter liest die Auswahl über `standAusAbo(context, abo, vorlagen).auswahl` (`wetter-tab/wetterZustand.ts:68-82` → `auswahlLesen`, `ampelModell.ts:367`): Vergleich = `display_config.active_metrics` (dedupliziert, Alt-/Neuformat), fehlt die Liste ⇒ aktive Metriken der aufgelösten Ampel. Die Übersicht zählt dagegen `ideal_ranges` (`hubUebersichtModell.ts:290`). Vorlagen/Katalog lädt die Trip-Übersicht schon in `trip-detail/HubOverview.svelte:60-64` (gleiches Muster für Vergleich wiederverwenden).
- B4 Texte: `de/vergleich.json:26-29` one = other („{count} Metriken …“), Altbegriffe „Idealbereich“, „Markierung, kein Score“.
- B5: `bausteine.alarme.titel` wird **doch** auf der Startseite verwendet: `routes/+page.svelte:362` (nicht nur in der toten `AlertsCard`). Textfix wirkt also sichtbar.
- B1 Folge: `home.aktion.pausentag_ziel` („→ Etappen & Wegpunkte“) auf der Startseite `routes/+page.svelte:292` verweist auf den Reiter ⇒ auf „→ Etappen“ mitziehen; Schlüssel steht in `i18n/__tests__/deutsch_unveraendert.test.ts:38` (Ratsche bewusst anpassen).

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| frontend/src/lib/i18n/messages/{de,en}/aktionen.json | MODIFY | Reiter-Label Trip „Etappen“/„Stages“ (neuer Schlüssel oder Wert ändern; Bereichsüberschrift „Etappen & Wegpunkte“ bleibt) |
| frontend/src/lib/components/shared/subscriptionTabs.ts | MODIFY | Trip-Reiter auf kurzen Label-Schlüssel |
| frontend/src/lib/i18n/messages/{de,en}/home.json | MODIFY | `home.aktion.pausentag_ziel` → „→ Etappen“ |
| frontend/src/lib/components/mobile/MTabBar.svelte | MODIFY (nur falls Messung es verlangt) | Pill-Abstände; Wischen bleibt Fallback |
| frontend/src/lib/components/shared/hub-uebersicht/HubUebersicht.svelte | MODIFY | Grid `repeat(auto-fit, minmax(280px, 1fr))`; Vorlagen/Katalog für Vergleich-Zähler bereitstellen |
| frontend/src/lib/components/shared/hub-uebersicht/hubUebersichtModell.ts | MODIFY | Wetter-Karte zählt `standAusAbo('vergleich', …).auswahl.length`; „—“ bei Ladefehler wie U4 |
| frontend/src/lib/i18n/messages/{de,en}/vergleich.json | MODIFY | Texte Wetter-Karte neu, korrekter Plural, ohne „Idealbereich“/„kein Score“ |
| frontend/src/lib/utils/cockpitHelpers568.ts | MODIFY | `setupStepCompare` Schritt Wetter: erledigt nach gewählten Metriken statt `ideal_ranges` |
| frontend/src/lib/i18n/messages/{de,en}/bausteine.json | MODIFY | `bausteine.alarme.titel` DE „Alarme · letzte 24 h“ |
| Tests (Unit + e2e, Liste im Kontextteil oben) + Charakterisierungs-Fixture | MODIFY | Wortlaut/Layout bewusst nachziehen |
| frontend/e2e/s3a2794-teil4b-*.staging.spec.ts + playwright.2794-s3a4b*.config.ts | CREATE (mitliefern) | untracked Staging-Specs aus Teil 4b |

### Scope Assessment
- Files: ca. 12 Produktivdateien + ca. 12 Testdateien
- Estimated LoC: +120/-60 (ohne Testanpassungen)
- Risk Level: MEDIUM — viele Tests mit festem Wortlaut; B4 ändert die Startseiten-Checkliste (Wetter erledigt/offen) für Orts-Vergleiche.

### Technical Approach
1. **B1:** eigener kurzer Katalog-Schlüssel für das Reiter-Label (z. B. `aktionen.reiter.etappen` = „Etappen“/„Stages“); `etappen_wegpunkte` bleibt für die Bereichsüberschrift. Zähler wie Mockup („Etappen 4“) nur, wenn die Leiste ihn heute schon für Orte führt — sonst nicht in diesem Fix (Mockup-Abgleich in Phase 3 festlegen).
2. **B2:** nach B1 auf Staging messen (360/375/390 px, DE und EN). Passen vier Pills nicht ohne Wischen: Pill-Innenabstand/Abstand reduzieren, Zielgröße 44 px und Wisch-Fallback bleiben (Spec `mobile_tab_leisten_mtabbar.md`).
3. **B3:** Grid auf `auto-fit/minmax(280px,1fr)` (Mockup-Muster `.two`) ⇒ eine einzelne Karte nimmt die volle Breite, drei Karten brechen sauber um. Beide Kontexte im Bild prüfen.
4. **B4:** Zählung aus derselben Funktion wie der Reiter Wetter (`standAusAbo('vergleich', preset, vorlagen).auswahl`), Vorlagen/Katalog wie `HubOverview.svelte` laden; ohne Vorlagen „—“. Neue Texte: kurz „{count} Metriken im Briefing“, lang analog ohne Altbegriffe, je mit echtem Singular. Checkliste `setupStepCompare` auf dieselbe Regel (gewählte Metriken vorhanden). Bestandsdaten nur lesen.
5. **B5:** DE-Wert „Alarme · letzte 24 h“; alter Unit-Test `issue_578…test.ts:336-338` auf neuen Wortlaut.
6. Staging-Specs aus Teil 4b mitliefern.

### Befunde gegen den Plan
- Checkliste `setupStepCompare` ist synchron und hat keine Vorlagen; fehlt `active_metrics`, gilt im Reiter die Vorlagen-Auswahl. Für die Checkliste reicht daher: erledigt, wenn `active_metrics` nicht leer ODER keine Liste gespeichert (Vorlage gilt ⇒ Metriken vorhanden). Das genau so in die Spec schreiben, damit Reiter und Checkliste nicht auseinanderlaufen.
- Eyebrow „Versand“ der Karte bleibt (Glossar: Versand = Abschnitt im Reiter Zustellung; Sprungziel ist genau dieser Abschnitt) — kein Umbenennen.

### Dependencies
- Katalog-Ratsche `deutsch_unveraendert.test.ts`, Pendant-Sperre (geteilter Code Trip/Vergleich), Mockup Fassung 3 als Bild-Soll (ADR-0112).

### Open Questions
- keine Produktfrage offen: Wortlaut folgt Mockup und Glossar; Zähler am Etappen-Reiter wird in der Spec gegen das Mockup entschieden.
