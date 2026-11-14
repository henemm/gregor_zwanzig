---
entity_id: feat_2913_c2_seitenkopf
type: feature
created: 2026-11-13
updated: 2026-11-14
status: draft
version: "1.2"
workflow: feature-2913-c2-seitenkopf
fix_loop_workflow: feature-2980-c2-bildabgleich-r1
fix_loop_issue: 2980
fix_loop2_workflow: feature-3003-c2-kopf-rest
fix_loop2_issue: 3003
issue: 2913
tags: [einstellungen-neu, seitenkopf, hub, reiterleiste, vorlage-karte, abgleich, epic-2791, issue-2913, issue-2980, issue-3003, bildabgleich]
---

# Scheibe c2: Seitenkopf des Editor-Hubs (Trip + Orts-Vergleich) nach Mockup

## Approval

- [ ] Approved

## Purpose

Der Hub-Kopf von Trip und Orts-Vergleich (Brotkrumen, Eyebrow, Titel mit Status-Pill, Meta-Zeile, Reiterleiste, Vorlage-Karte) weicht vom freigegebenen Mockup `mockup-hub-fassung3.html` ab; der Ganzseiten-Abgleich führt dafür 92 Besitzer-Einträge `#2913-c2`. Diese Scheibe bringt den geteilten Kopf auf Mockup-Stand (DE und EN), damit die c2-Einträge entfallen und `--abnahme` für den Kopf Exit 0 liefert.

Fix-Loop Runde 1 (#2980): Der `mockup-bildpruefer` fand nach der ersten Umsetzung acht optische Abweichungen (Knopf-Farbe, Handy-Reiter, Kennzahlenzeile, Meta-Schrift, Status-Pill, Kopfband/Brotkrumen, Vorlage-Karte, Abschnittskopf Wetter). Der Abschnitt „Fix-Loop Bildabgleich Runde 1 (#2980)“ weiter unten (AC-16 ff.) behebt sie und legt zwei PO-Entscheidungen vom 13.11.2026 fest (Handy-Reiter wie Mockup, Kennzahlenzeile am Handy entfällt).

Nachtrag #3003 (Rest aus Bildabgleich Runde 2): Drei Rest-Abweichungen bleiben nach #2980: der Vorlagen-Wähler im Wetter-Reiter hat den Inhalt oben am Rahmen statt mittig, der Abstand zwischen „Vorlage“ und Wähler-Text ist am Handy zu klein, und die Reiterleiste am Handy ist linksbündig und enger als im Mockup, statt die volle Breite zu füllen. Der Nachtrag „Rest Bildabgleich Runde 2 (#3003)“ (AC-32 ff.) behebt sie. PO-Entscheidung vom 14.11.2026: Die Höhe des Vorlagen-Wählers richtet sich nach der Bedienart (Maus: Mockup-Höhe ca. 38 px, Finger: mindestens 44 px), nicht nach der Bildschirmbreite.

## Source

- **File:** `frontend/src/lib/components/shared/hub-kopf/HubKopf.svelte`
- **Identifier:** `HubKopf` (mit `SubscriptionHeader`, `TripHeader`, `TripTabs`, `CompareTabs`, `VorlageKarte`, `routes/compare/[id]/+page.svelte`)
- **Schicht:** ausschließlich Frontend (`frontend/src/...`) plus Doku-Daten des Abgleichs (`docs/context/einstellungen_neu/`). Kein Go-API-, kein Python-Core-Code, keine Schema-Änderung.

> **Querschnitts-Prüfpunkte:**
> - **Trip/Orte-Teilung (ADR-0097):** Alle Änderungen liegen in den geteilten Bausteinen (`HubKopf`, `SubscriptionHeader`, `VorlageKarte`) oder in den bestehenden Paaren `TripTabs`/`CompareTabs` und `TripHeader`/Compare-Seite, jeweils mit gleicher Logik und `context="route"|"vergleich"`. Kein neuer Baustein mit einseitigem Pendant. Der Nachtrag #3003 ändert nur `VorlageKarte` und `MTabBar`, beide geteilt.
> - **Mandantentrennung:** Es werden keine Nutzerdaten bewegt und kein Endpoint geändert (nur Darstellung). Zwei-Nutzer-Test entfällt; die Isolation bleibt unberührt und wird im E2E-Lauf mit dem vorhandenen Staging-Konto lediglich nicht verletzt. Das gilt auch für den Fix-Loop #2980 und den Nachtrag #3003: reine Optik (CSS und Markup), keine Daten, kein Endpoint.
> - **Kanäle:** Kein Briefing- oder Alarm-Inhalt ändert sich; E-Mail, Telegram, SMS und Premium-SMS sind nicht betroffen (Mail-Kopf-Satz bleibt bei #2796).

## Scope

### In Scope

1. **Kopfleiste:** Brotkrumen „Trips / **Name**“ bzw. „Orte / **Name**“, Kebab „Weitere Aktionen“, Knopf mit Beschriftung „Test schicken ▾“ (nur Beschriftung, kein neues Menü; Menü bleibt #2797).
2. **Kopf:** Eyebrow „Trip · Region“ bzw. „Orte · Region“, h1 mit Status-Pill (fertig, aktiv, Entwurf mit „Aktivieren“, pausiert, archiviert), Meta-Zeile nach Mockup (Trip: „Datum · N Etappen · km · ↑m“; Orte: „N Orte · Vergleichstabelle · Briefing HH:MM“).
3. **Reiterleiste:** Zähler-Badge „Etappen (N)“ / „Orte (N)“, `aria-current` am aktiven Reiter.
4. **Vorlage-Karte:** Texte und Gruppen (Vorlagen / Eigene) nach Mockup, ohne den Satz „Name der Vorlage ersetzt das Profil und steht im Kopf der Mail“.
5. **Name/Region** bleiben inline bearbeitbar; im Ruhezustand nur Stift-Icon mit `aria-label`.
6. **Abgleich-Daten:** c2-Besitzer-Einträge entfernen; Einträge zu Profil-Wegfall, Tempo-Karte (`abschnitt=tempo`) und Mail-Kopf-Satz auf `#2796` umhängen (Grund „Scheibe S4, Datenmodell+Migration“); sichtbare Bearbeiten-Texte von Name/Region als Ausnahme mit Verweis auf diese Spec.
7. Neue Nutzertexte DE und EN im Katalog (ADR-0104); EN aus `elementliste.json`.
8. **Fix-Loop Bildabgleich Runde 1 (#2980):** acht optische Korrekturen (Akzent-Knopf, Handy-Reiter als Text-Reiter mit Unterstrich, Wegfall der Kennzahlenzeile am Handy, Meta-Zeile Mono, gefüllte Status-Pill, Kopfband/Brotkrumen/Kebab, Vorlage-Karte, Abschnittskopf Wetter), ADR-0118 und Bildprüfer Runde 2 (AC-16 bis AC-31).
9. **Nachtrag Rest Bildabgleich Runde 2 (#3003):** Vorlagen-Wähler mittig ausgerichtet, seitliches Polster 12 px, Höhe nach Bedienart (Maus ca. 38 px wie Mockup, Finger mindestens 44 px), dadurch mehr Luft zwischen Eyebrow „Vorlage“ und Wähler-Text, Reiterleiste am Handy füllt die volle Breite; Präzisierung der Regel K-5 / AC-40 auf Fingerbedienung (AC-32 bis AC-35).

### Nicht-Ziele (ausdrücklich)

- Profil-Zeile/Profil-Chip bleiben bis #2796 (S4, ADR-0108); keine Entfernung, keine Migration.
- Tempo-Karte im Reiter Etappen (Fortbewegung, Tempo flach, Aufstieg, Gehzeit je Etappe): #2796.
- Mail-Kopf zeigt weiter das Profil; Vorlagenname im Mail-Kopf: #2796.
- „Test schicken“-Menü (Morgen-/Abend-Briefing): #2797; die 8 dortigen Besitzer-Einträge bleiben.
- Keine Datenmodell- oder Schema-Änderung (`activity`, `profil` unverändert, Read-Modify-Write unberührt).
- Aus #2980 „Andere Besitzer“ (bleiben bei ihren Issues, nicht Teil des Fix-Loops): Mail-Kopf/Profil/Tempo-Karte (#2796), „Test schicken“-Menü (#2797), Kennzahlen-/Metrik-Themen (#2954), App-Rahmen (Navigation, Seitenrahmen außerhalb des Hubs), Variante V16 des Mockups, EN-Wortlaut des Vorlagennamens (Folge-Issue, Lücke in `elementliste.json`).
- Aus #3003 außerhalb des Umfangs (andere Besitzer, bleiben bei ihren Issues): Punkte zu #2796, #2981 und #2954, der App-Rahmen sowie die bekannte, bewusste Kontrast-Abweichung am Knopf „Test schicken“ (`--g-accent-deep`, siehe AC-16). Das Btn-Atom (`Btn.svelte`) bleibt unverändert; die Desktop-Reiterleiste bleibt unverändert. Alle anderen Touch-Ziele im Wetter-Reiter bleiben bei ≥ 44 px unverändert; nur der Vorlagen-Wähler folgt bei Mausbedienung der Mockup-Höhe.

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `frontend/src/lib/components/shared/hub-kopf/HubKopf.svelte` | MODIFY | Brotkrumen, Eyebrow, Titel+Pill, Meta, Kebab, Knopf „Test schicken ▾“; Fix-Loop: Knopf `accent`, Kopfband Mono/uppercase, kein Zurück-Pfeil am Handy, Umbruch statt Kürzung, Kebab ghost, Meta Mono 13 px |
| `frontend/src/lib/components/shared/subscription-header/SubscriptionHeader.svelte` | MODIFY | Ruhezustand nach Mockup, Stift als Icon mit aria-label; Profil-Teil unverändert |
| `frontend/src/lib/components/shared/status-schild/StatusSchild.svelte` | MODIFY | Fix-Loop: Pill gefüllt ohne Rahmen, aktiv = good, sonst neutral |
| `frontend/src/lib/components/trip-detail/TripHeader.svelte` | MODIFY | Eyebrow „Trip · Region“, Meta-Zeile, Pill-Zustände; Fix-Loop: Kennzahlenzeile `mobile-metrics` entfernen, Brotkrumen-Name = voller Tripname |
| `frontend/src/routes/compare/[id]/+page.svelte` | MODIFY | Eyebrow „Orte · Region“, Meta „N Orte · Vergleichstabelle · Briefing HH:MM“; Fix-Loop: nur prüfen (läuft über HubKopf/StatusSchild) |
| `frontend/src/lib/components/mobile/MTabBar.svelte` | MODIFY | Fix-Loop: Handy-Pillen entfernen, Text-Reiter mit Unterstrich, wischbar, 44 px Tippfläche; #3003: Handy-Reiter `flex: 1 0 auto`, Inhalt zentriert (volle Leistenbreite) |
| `frontend/src/lib/components/trip-detail/TripTabs.svelte` | MODIFY | Zähler-Badge Etappen (N) über `MTabBar.badge` |
| `frontend/src/lib/components/compare/CompareTabs.svelte` | MODIFY | Zähler-Badge Orte (N) über `MTabBar.badge` |
| `frontend/src/lib/components/organisms/wetter-tab/VorlageKarte.svelte` | MODIFY | Texte/Gruppen nach Mockup, ohne Mail-Kopf-Satz; Fix-Loop: Wähler-Optik, „▾ unverändert“ Mono, Speichern-Knopf mittig; #3003: Wähler `align-items: center` statt `baseline`, seitliches Polster 12 px, Höhe nach Bedienart (Basis wie Mockup ca. 38 px, unter `@media (pointer: coarse)` `min-height: var(--g-tap-min)`) |
| `frontend/src/lib/components/organisms/wetter-tab/WetterTabInhalt.svelte` | MODIFY | Fix-Loop: Abschnittskopf Wetter (68ch, 13 px, Trennlinie) |
| `docs/adr/0118-handy-reiter-unterstrich-und-akzent-aktion.md` | CREATE | Fix-Loop: neues ADR (Dateiname endgültig im Developer-Schritt, Nummer 0118 fest) |
| `docs/adr/0109-*.md`, `0110-*.md`, `0111-*.md`, `docs/adr/README.md` | MODIFY | Fix-Loop: Status „Teilweise abgelöst durch ADR-0118“ in Datei und Index, konsistent nach `tests/test_adr_index_drift.py` |
| `docs/specs/modules/mobile_tab_leisten_mtabbar.md` | MODIFY | Fix-Loop: Handy-Optik Unterstrich; Pillen-AC als überholt markieren |
| `frontend/src/lib/i18n/messages/de/*.json`, `en/*.json` | MODIFY | neue Schlüssel DE+EN |
| `docs/context/einstellungen_neu/elementliste_besitzer.json` | MODIFY | c2-Einträge entfernen bzw. auf `#2796` umhängen |
| `docs/context/einstellungen_neu/elementliste_besitzer.json` → Liste `ausnahmen` (gelesen von `leseAusnahmen`) | MODIFY | Name/Region-Bearbeiten-Texte mit Verweis auf diese Spec; Fix-Loop: bewusste Abweichung Knopf-Fläche `--g-accent-deep` |
| `frontend/src/lib/components/shared/hub-kopf/__tests__/*`, `shared/__tests__/subscription_header_*.test.ts`, `trip-detail/__tests__/trip_header_status_profil.test.ts`, `compare/__tests__/compare_hub_fidelity.test.ts`, `routes/compare/__tests__/bug_589_breadcrumb_links.test.ts` | MODIFY | an neue Texte/Struktur anpassen, nicht ersatzlos löschen |
| `mobile/__tests__/s3a2794_mtabbar_leiste_soll.test.ts`, `status_schild*.test.ts`, `StatusSchild.atomic.test.ts`, `hub_kopf_baustein.test.ts`, `hub_kopf_seiten_paritaet.test.ts`, `subscription_header_einmal_gerendert.test.ts`, `tripStatusFinishedDraft.test.ts` | MODIFY | Fix-Loop: bewusst auf neues Soll ziehen (Pillen-Optik, Status-Optik, Kürzel, Zurück-Pfeil) |
| `frontend/e2e/hub-kopf-aufbau.spec.ts`, `hub-kopf-paritaet-compare-trip.spec.ts` (Knopf „Senden“ → „Test schicken“), `hub-kopf-bearbeiten.spec.ts`, `trip-hub-kopf-region-aktivitaet.spec.ts`, `issue-269-mobile-trip-tabs.spec.ts` | MODIFY | mitziehen |
| `frontend/src/lib/components/trip-detail/TripHeader.mobile-metrics.test.ts` | DELETE | Fix-Loop: Kennzahlenzeile #416 entfällt (PO-Entscheidung 13.11.2026), ersatzlos gedeckt durch AC-19 |
| `frontend/src/lib/components/shared/hub-kopf/__tests__/hub_kopf_c2_mockup.test.ts` | CREATE (c2) / MODIFY (Fix-Loop) | Unit-Tests (node --test), in c2 angelegt; Fix-Loop: um AC-16 bis AC-28 erweitern |
| `frontend/e2e/hub-kopf-c2-mockup.staging.spec.ts` | CREATE (c2) / MODIFY (Fix-Loop) | E2E-Prüfung gegen Staging (Playwright), in c2 angelegt; Fix-Loop: mitziehen |
| `frontend/e2e/hub-kopf-c2-bildabgleich.staging.spec.ts` | CREATE (#2980) / MODIFY (#3003) | Fix-Loop: Aufnahmen für Bildprüfer Runde 2 (Mockup per file:// und Staging, 1280×900 und 390×844, Trip/Orte, DE/EN, Reiter Wetter), Vorbild `fix2913-metrikliste-mockup.staging.spec.ts`; #3003: gemessene Geometrie (Wähler mittig; Höhe 38±2 px bei Maus 1280×900, ≥ 44 px bei Touch-Emulation 390×844; Reiter füllen Leiste; kein Überlauf bei 360 px) |
| `frontend/src/lib/components/shared/hub-kopf/__tests__/hub_kopf_c2_bildabgleich.test.ts` | MODIFY | #3003: Kern-Zusicherungen (node --test, keine Mocks) zu Wähler-Ausrichtung, Höhe nach Bedienart und Handy-Reiter-Verteilung |
| `frontend/e2e/s3a2794-teil3-design.spec.ts` | MODIFY | #3003: Wächter für AC-40 (Funktion `zuKleineZiele`) an die Bedienart anpassen: 44-px-Messung läuft in einem Kontext mit Fingerbedienung (Playwright `hasTouch`/`isMobile`, damit `pointer: coarse` gilt); im Mausdurchlauf folgt der Vorlagen-Wähler der Mockup-Höhe, alle anderen Ziele bleiben ≥ 44 px |
| `docs/specs/modules/feat_2794_s3a_teil3_wetter.md` | MODIFY | #3003: nur ein kurzer Vermerk „AC-40 präzisiert durch #3003 (Bedienart)“ mit Datum 2026-11-14, sonst keine Änderung |

## Estimated Scope

- **LoC:** ca. +350 / −150 (Basis c2); Fix-Loop #2980 zusätzlich ca. +250 / −120; Nachtrag #3003 zusätzlich ca. +80 / −10 (davon ca. 60 Tests)
- **Files:** ca. 10 Quelle + 10 Tests (Basis); Fix-Loop zusätzlich ca. 6 Komponenten, 4 ADR/Spec-Dateien, ca. 10 Tests; #3003: 2 Komponenten, 3 Testdateien, 2 Specs (diese und der Vermerk in `feat_2794_s3a_teil3_wetter.md`)
- **Effort:** medium (Risiko niedrig bis mittel: geteilter Kopf, viele Tests binden an Kopf-Texte und alte Optik); #3003 für sich: Risiko niedrig, nur Frontend

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `MTabBar` (`badge`), `StatusSchild`/`Pill`, `Eyebrow`, `Btn`, `SubscriptionKebab` | Design-System-Bausteine (ADR-0112) | einzige zulässige Bausteine; Wächter `bausteine_waechter*.test.ts` |
| `docs/context/einstellungen_neu/seiten/mockup-hub-fassung3.html` | Soll | Z. 228–245, 310–326, 358–365, 454–465, 508–512; Fix-Loop zusätzlich Z. 34–71, 90–92, 442; #3003: `.picker` (padding 8px 12px, align-items:center), `.tab` (13 px/500), `.tabs-in` (width 100 %) |
| `docs/context/einstellungen_neu/elementliste.json` | Soll-Texte | EN-Texte (Lücken: #2968) |
| `docs/context/einstellungen_neu/elementliste_besitzer.json` | Daten | Besitzer-Einträge |
| `feat_2913_abgleich_ganzseite.md` | Spec | Besitzer-Mechanik, `--abnahme`, Marker `data-seite="hub"` |
| `rework_2837_s1_hub_kopf.md`, `rework_2845_hub_reiterleiste.md`, `feat_1273_s2_compare_hub_name_region_profil.md`, `mobile_tab_leisten_mtabbar.md`, `_archive/modules/issue_416_mobile_trip_kennzahlen.md` | Specs | Vorgänger; Name/Region-Bearbeiten am Hub bleibt; MTabBar-Optik und #416-Kennzahlen werden durch #2980 teilweise bzw. ganz abgelöst; #3003 respektiert dort die 44-px-Tippfläche (#2284) und das Scroll-Band (#1231) |
| `feat_2794_s3a_teil3_wetter.md` (AC-40), `feat_2913_s3_bausteine.md` (K-5, `Btn size="tap"`) | Specs | Quelle der Regel K-5 / AC-40; wird durch #3003 auf Fingerbedienung präzisiert (Vermerk in der Spec, kein ADR) |
| ADR-0109, ADR-0110, ADR-0111 | ADR | werden durch ADR-0118 teilweise abgelöst (Handy-Pillen, Hauptaktion Ink) |
| `.claude/agents/mockup-bildpruefer.md` | Agent | Bildabgleich, nur Mockup-Bild, Staging-Bild und Elementlisten-Auszug, maximal 2 Runden |
| Design-Tokens `app.css` (`--g-accent`, `--g-accent-deep`, `--g-paper`, `--g-paper-deep`, `--g-ink`, `--g-ink-2`, `--g-ink-3`, `--g-rule`, `--g-rule-soft`, `--g-good`, `--g-font-mono`, `--g-text-sm`, `--g-size-10px`, `--g-tap-min`) | Tokens | nur Tokens statt Rohwerte (Wächter) |
| Issue #2796 (S4, ADR-0108) | Abhängigkeit | übernimmt Profil, Tempo, Mail-Kopf-Satz |
| Issue #2797 | Abhängigkeit | übernimmt „Test schicken“-Menü |
| i18n-Katalog (ADR-0104) | Katalog | neue Nutzertexte nur dort |
| `s3a2794_mtabbar_leiste_soll.test.ts`, `s3a2794-teil3-design.spec.ts` | Wächter-Tests | bleiben grün: vier DE-Reiter passen bei 360 px (#2794 B2), Tippflächen ≥ 44 px im Wetter-Reiter bei Fingerbedienung (AC-40, K-5, präzisiert durch #3003; der zweite Wächter wird angepasst, siehe Affected Files) |

## Implementation Details

Umbau der bestehenden geteilten Bausteine, keine Neubauten, Reihenfolge: Kopf, Reiterleiste, Vorlage-Karte, Besitzerliste/Ausnahmen, Abgleich-Abnahme.

1. **Kopf:** `HubKopf` rendert Brotkrumen (Elternlink „Trips“/„Orte“, Name als aktuelles Element), Knopf mit Beschriftung aus Prop `sendLabel` („Test schicken ▾“; testid `subscription-hub-send` bleibt), Kebab. `SubscriptionHeader` zeigt Eyebrow („Trip · Region“/„Orte · Region“), h1 mit Status-Pill und Meta-Zeile; der Stift ist im Ruhezustand ein Icon mit `aria-label`, Texte des Bearbeiten-Zustands (Speichern/Abbrechen/Feldnamen) bleiben und werden als Abgleich-Ausnahme geführt.
2. **Meta:** Trip aus Datum, Etappenzahl, km, ↑m; Orte aus Ortezahl, „Vergleichstabelle“, Briefing-Zeit. Zahlen locale-formatiert (DE „31,5 km“, EN „31.5 km“).
3. **Reiterleiste:** `badge` am Reiter Etappen/Orte mit Anzahl; Zähler ändert sich mit der Datenmenge; aktiver Reiter trägt `aria-current`.
4. **Vorlage-Karte:** Texte nach Mockup, Gruppen „Vorlagen“/„Eigene“; Mail-Kopf-Satz entfällt in c2.
5. **Abgleich-Daten:** Skript/Hand-Edit am Besitzer-JSON; `verweis` auf `#2796` mit Grund „Scheibe S4, Datenmodell+Migration“ für Profil-Wegfall, Tempo, Mail-Kopf-Satz. Ausnahmen-Eintrag für Name/Region-Bearbeiten-Texte mit Spec-Verweis.
6. **Tests:** bestehende Tests an neue Texte/Struktur anpassen (Knopf „Senden“ → „Test schicken“), nicht löschen.
7. **Fix-Loop #2980 (Runde 1):** Alles im geteilten Baustein (ADR-0097), nur Tokens (Wächter). Technische Eckpunkte:
   - Knopf: `Btn variant="accent"` mit Fläche `--g-accent-deep`. Das Mockup-Orange `#c45a2a` mit weißer 12-px-Schrift erreicht nur ca. 4,3:1 und verfehlt WCAG-AA; Design-Leitprinzip „hoher Kontrast gewinnt“ (PO-bestätigt 2026-05-25, #2879). Bewusste, dokumentierte Abweichung, im Soll/Ist-Bild offen benannt.
   - Großschreibung (Kopfband, Eyebrow, Pill) nur per CSS `text-transform`; der Text im DOM bleibt unverändert (Tests mit `innerText` beachten).
   - Brotkrumen am Handy: kein Zurück-Pfeil, Elternlabel bleibt Link, Umbruch (`overflow-wrap:anywhere`, `min-width:0`) statt Ellipsis; Brotkrumen-Name ist der volle Name (`trip.name`), kein Kürzel.
   - `StatusSchild` wird global gefüllt ohne Rahmen; einzige Konsumenten sind `TripHeader` und die Compare-Seite. Zuordnung nach Mockup Z. 326: aktiv = good, alles andere neutral; `data-status` bleibt.
   - `MTabBar`: Handy-Media-Query ohne Pillen, gleiche Optik wie Desktop; Band wischbar (Scroll-Snap/Fade bleiben), Tippfläche ≥44 px (#2284).
   - `WetterTabInhalt`: lokaler Kopf `.wt-kopf` bekommt Mockup-Maße; kein `SectionH`, daher keine Seiteneffekte.
   - Reihenfolge: ADR-0118 und ACs, Tests rot, CSS/Markup, Staging, Bildaufnahmen, `mockup-bildpruefer` Runde 2 (letzte Runde), Soll/Ist-Bild an den PO.
8. **Nachtrag #3003 (Rest Runde 2):** reine CSS-Änderungen in zwei geteilten Bausteinen, Btn-Atom bleibt unverändert.
   - Ursache Wähler: `Btn size="tap"` hat `padding: 0 14px; min-height: 44px`, und `VorlageKarte` überschreibt per `.wt-picker :global([data-slot='btn'])` auf `align-items: baseline`; dadurch sitzt der Text direkt unter dem oberen Rahmen. Fix: `align-items: center` und seitliches Polster 12 px (wie Mockup `.picker`).
   - Höhe nach Bedienart (PO-Entscheidung Henning, 2026-11-14, nach visueller Erklärung): Das Mockup misst für den Wähler ca. 38 px (`.picker`: padding 8px 12px, align-items:center). Die Höhe richtet sich nach der Bedienart, nicht nach der Bildschirmbreite: Bei Mausbedienung (`@media (pointer: fine)`, Laptop/Desktop) folgt der Wähler der Mockup-Höhe ca. 38 px (Toleranz ±2 px); bei Fingerbedienung (`@media (pointer: coarse)`, Handy, Tablet, Touch-Laptop) hat er mindestens 44 px Tippfläche (`min-height: var(--g-tap-min)`, K-5, #2284). In beiden Fällen steht der Inhalt vertikal mittig (oben ≈ unten ±2 px) bei seitlichem Polster 12 px. Begründung: Die Bildschirmbreite sagt nichts über die Bedienart (ein Tablet quer ist breit, wird aber mit dem Finger bedient); die Abfrage der Bedienart (`pointer`) ist etablierte Praxis für Tippflächen. Damit ist die 44-px-Höhe keine bewusste Abweichung vom Mockup mehr: Bei Maus ist die Mockup-Höhe erfüllt, bei Finger gilt 44 px.
   - Folge für K-5 / AC-40 (#2794): Die Regel wird präzisiert auf „Touch-Ziele ≥ 44 px bei Fingerbedienung“. Der Wächter `frontend/e2e/s3a2794-teil3-design.spec.ts` (Funktion `zuKleineZiele`) prüft bisher alle Ziele im Wetter-Reiter auf ≥ 44 px, auch im Desktop-Durchlauf. Er wird so angepasst, dass die 44-px-Messung in einem Kontext mit Fingerbedienung läuft (Playwright `hasTouch`/`isMobile`, dort gilt `pointer: coarse`); im Mausdurchlauf darf der Vorlagen-Wähler der Mockup-Höhe folgen. Alle anderen Ziele bleiben unverändert bei ≥ 44 px. In `feat_2794_s3a_teil3_wetter.md` kommt ausschließlich der Vermerk „AC-40 präzisiert durch #3003 (Bedienart)“ mit Datum 2026-11-14 hinzu; AC-40 selbst wird dort nicht umgeschrieben.
   - ADR-Prüfung: K-5 steht in keinem ADR. Fundstellen sind nur die Specs `feat_2913_s3_bausteine.md` (Zeile „K-5 Touch-Ziele“, `Btn size="tap"`) und `feat_2794_s3a_teil3_wetter.md` (AC-40); ADR-0118 nennt die 44-px-Tippfläche nur für die Handy-Reiter (#2284), das bleibt unberührt (Reiter sind Touch-Ziele, `MTabBar` ändert seine Höhe nicht). Deshalb reicht der Spec-Vermerk, ein neues oder ablösendes ADR ist nicht nötig.
   - Ursache Eyebrow-Abstand: Der Gap von 6 px (`.wt-picker-wrap`) entspricht bereits dem Mockup; sichtbar waren nur 6 px + Rahmen bis zum oben klebenden Text (ca. 7 px), im Mockup 6 + 1 + 8 = 15 px. Die Mittig-Ausrichtung behebt den Abstand mit; kein eigener Eingriff am Gap. Rechenprobe bei Fingerbedienung (44 px Höhe, Text ca. 20 px Zeilenhöhe): ca. 12 px Luft über dem Text plus 6 px Gap, zusammen ca. 18 px und damit über den geforderten 12 px (AC-33). Die Messung bei 390×844 läuft in Touch-Emulation.
   - Ursache Reiter: `MTabBar` setzt mobil (<900 px) `flex-shrink: 0` mit Polster `--g-s-2 --g-size-10px` und Schrift `--g-text-sm` (13 px); vier Reiter ergeben ca. 330 px, linksbündig, Lücke rechts. Fix: `flex: 1 0 auto` plus zentrierter Inhalt, sodass die Reiter bei Platz auf die volle Leistenbreite wachsen. Schrift bleibt 13 px (Mockup-Token identisch), Mindestpolster 10 px (16 px Polster würde bei 360 px überlaufen und #2794 B2 verletzen). Bei Überbreite (EN, 360 px, viele Reiter) greift weiter das bestehende Scroll-Band mit Fade und Scroll-Snap. Wirkt in Trip und Vergleich gleich (geteilte Komponente).

## Expected Behavior

- **Input:** geöffneter Trip bzw. Orts-Vergleich (Hub), Sprache DE oder EN, Desktop oder Mobil.
- **Output:** Kopf, Reiterleiste und Vorlage-Karte entsprechen dem Mockup; Abgleich meldet für diese Bereiche keine Abweichung ohne Besitzer.
- **Side effects:** keine Datenänderung; nur Besitzer-/Ausnahmen-Daten des Abgleichs.

## Test Plan

### Automated Tests (TDD RED)

- [ ] Unit (node --test) `hub_kopf_c2_mockup.test.ts`: GIVEN Trip-Daten mit Region/Datum WHEN Kopf gerendert THEN Eyebrow „Trip · Region“, Meta „Datum · N Etappen · km · ↑m“; analog Orte.
- [ ] Unit: GIVEN Status entwurf/aktiv/pausiert/archiviert/fertig WHEN Pill gerendert THEN passende Beschriftung, bei Entwurf „Aktivieren“ (DE und EN).
- [ ] Unit: GIVEN 4 Etappen bzw. 3 Orte WHEN Reiterleiste gerendert THEN Badge 4 bzw. 3 und `aria-current` am aktiven Reiter.
- [ ] Unit: GIVEN Vorlage-Karte WHEN gerendert THEN Gruppen Vorlagen/Eigene, kein Mail-Kopf-Satz.
- [ ] Unit: GIVEN Katalog WHEN neue Schlüssel geprüft THEN DE und EN vollständig (`keine_hartkodierten_nutzertexte`, Katalog-Parität).
- [ ] Unit: GIVEN Besitzerliste WHEN geladen THEN kein Eintrag mit Verweis `#2913-c2`; Umgehängte tragen `#2796`.
- [ ] E2E (Playwright, Staging) `hub-kopf-c2-mockup.staging.spec.ts`: Trip und Vergleich, DE und EN, Desktop und Mobil: Kopf, Badge, Vorlage-Karte sichtbar nach Mockup; Name inline ändern bleibt möglich.
- [ ] E2E/Abgleich: `npm run elementliste:abgleich -- --abnahme` gegen Staging, Exit 0 für DE und EN.
- [ ] Bestehende Tests (Liste unter Affected Files) angepasst und grün; Wächter `bausteine_waechter*` grün.

### Fix-Loop #2980 (Runde 1)

Reine Optik: Komponenten-Tests mit `node --test` (gerenderte Struktur, Klassen/Attribute und aufgelöste Token, kein Dateiinhalt-Check außer Marker `# doc-compliance-test` für ADR/Index) und Playwright-Aufnahmen gegen Staging (berechnete Stile aus dem Browser).

- [ ] Unit: GIVEN `HubKopf` gerendert WHEN Knopf „Test schicken ▾“ geprüft THEN Variante `accent` (Fläche `--g-accent-deep`), nicht `primary` (AC-16).
- [ ] Unit: GIVEN `MTabBar` im Handy-Zustand WHEN gerendert THEN Text-Reiter ohne Pillen-Klassen, aktiver Reiter mit Unterstrich `--g-accent`, Grundlinie `--g-rule` (AC-17); Tippfläche ≥44 px, Band mit horizontalem Scrollen (AC-18).
- [ ] Unit: GIVEN `TripHeader` am Handy WHEN gerendert THEN kein `mobile-metrics`-Block (AC-19); Meta-Zeile Mono 13 px `--g-ink-3` (AC-20).
- [ ] Unit: GIVEN `StatusSchild` mit allen fünf Zuständen WHEN gerendert THEN gefüllt ohne Rahmen, aktiv = good, sonst neutral (AC-21); Kontrastrechnung Hell/Dunkel ≥4,5:1 (AC-22).
- [ ] Unit: GIVEN Kopfband WHEN gerendert THEN Mono 11 px, uppercase per CSS, DOM-Text unverändert, Name `--g-ink` 500, voller Name, kein Zurück-Pfeil am Handy (AC-23, AC-24); Kebab ghost mit Rahmen `--g-rule`, 44 px (AC-25).
- [ ] Unit: GIVEN `VorlageKarte` und `WetterTabInhalt` WHEN gerendert THEN Wähler, „▾ unverändert“, Speichern-Knopf mittig und Abschnittskopf nach Mockup-Maßen (AC-26, AC-27, AC-28).
- [ ] Python/Doku (`# doc-compliance-test`): `tests/test_adr_index_drift.py` grün mit ADR-0118 und Teilablösungs-Vermerken in 0109/0110/0111 (AC-29).
- [ ] Zu ändernde Bestandstests (nicht löschen): `s3a2794_mtabbar_leiste_soll.test.ts`, `issue-269-mobile-trip-tabs.spec.ts`, `status_schild*.test.ts`, `StatusSchild.atomic.test.ts`, `hub_kopf_baustein.test.ts`, `hub_kopf_c2_mockup.test.ts`, `hub_kopf_seiten_paritaet.test.ts`, `subscription_header_einmal_gerendert.test.ts`, `tripStatusFinishedDraft.test.ts`, `hub-kopf-aufbau.spec.ts`, `hub-kopf-c2-mockup.staging.spec.ts`.
- [ ] Zu entfernender Bestandstest: `TripHeader.mobile-metrics.test.ts` (Kennzahlenzeile #416 entfällt laut PO, AC-19).
- [ ] E2E (Playwright, Staging) `hub-kopf-c2-bildabgleich.staging.spec.ts`: acht Zustände aufnehmen und berechnete Stile prüfen (AC-30); danach `mockup-bildpruefer` Runde 2.
- [ ] Wächter `bausteine_waechter*.test.ts` grün (Tokens, `68ch` relativ zulässig).

### Nachtrag #3003 (Rest Bildabgleich Runde 2)

Reine Optik, keine Mocks: Kern-Test mit `node --test`, gemessene Geometrie im Browser gegen Staging.

- [ ] Kern (node --test) `hub_kopf_c2_bildabgleich.test.ts`: GIVEN `VorlageKarte` WHEN Wähler-Stilregeln aufgelöst THEN `align-items: center` (nicht `baseline`) und seitliches Polster 12 px (AC-32); GIVEN `VorlageKarte` WHEN die Regeln unter `@media (pointer: coarse)` aufgelöst THEN `min-height: var(--g-tap-min)` für den Wähler, und ohne diese Regel (Maus) keine 44-px-Mindesthöhe (AC-32); GIVEN `MTabBar` WHEN Handy-Regel aufgelöst THEN Reiter `flex: 1 0 auto`, Inhalt zentriert, Schrift `--g-text-sm`, Mindestpolster `--g-size-10px` (AC-34).
- [ ] E2E (Staging) `hub-kopf-c2-bildabgleich.staging.spec.ts`, Maus: GIVEN Wetter-Reiter in Trip und Orten, DE und EN, 1280×900 mit Maus (`pointer: fine`) WHEN Wähler gemessen THEN Höhe 38 ±2 px und Abstand Rahmen-oben bis Text ≈ Text bis Rahmen-unten (±2 px) (AC-32).
- [ ] E2E (Staging) gleiche Datei, Finger: GIVEN Wetter-Reiter in Trip und Orten, DE und EN, 390×844 mit Touch-Emulation (`hasTouch`/`isMobile`, `pointer: coarse`) WHEN Wähler gemessen THEN Höhe ≥ 44 px und Abstand oben ≈ unten (±2 px) (AC-32); Unterkante Eyebrow bis Oberkante Wähler-Text ≥ 12 px bei gleichem Gap von 6 px (AC-33).
- [ ] E2E (Staging) gleiche Datei: GIVEN Handy 390 px, Trip und Orte, DE und EN WHEN Reiterleiste gemessen THEN rechte Kante letzter Reiter ≈ rechtes Leistenende (±2 px); GIVEN 360 px DE THEN kein Überlauf der vier Reiter (AC-34).
- [ ] Bestehende Wächter grün: `s3a2794_mtabbar_leiste_soll.test.ts` (B2, 360 px), `s3a2794-teil3-design.spec.ts` (AC-40, Tippflächen ≥ 44 px, nach Anpassung an die Bedienart in einem Kontext mit Fingerbedienung gemessen), `bausteine_waechter*.test.ts`.
- [ ] Abnahme: acht Staging-Aufnahmen, `mockup-bildpruefer`, Soll/Ist-Bild an den PO (AC-35).

## Definition of Done

Fertig ist Scheibe c2, wenn Kopfleiste (Brotkrumen, Kebab, „Test schicken ▾“), Kopf (Eyebrow, Titel mit Status-Pill, Meta-Zeile), Reiterleiste mit Zähler und Vorlage-Karte von Trip-Hub und Orts-Vergleich-Hub ausschließlich aus Design-System-Bausteinen bestehen (Wächter grün), auf Staging in DE und EN der Elementliste des Mockups entsprechen, keine Besitzer-Einträge `#2913-c2` mehr existieren (Profil/Tempo/Mail-Kopf-Satz sichtbar auf #2796 umgehängt, Menü bei #2797), `npm run elementliste:abgleich -- --abnahme` für DE und EN mit Exit 0 endet, Name/Region für zwei verschiedene Nutzer nach Neuladen erhalten bleiben, der `mockup-bildpruefer` nach höchstens zwei Runden keine offene Abweichung meldet und Henning ein Soll/Ist-Bild des Kopfs bekommen hat (AC-1 bis AC-31). Der Nachtrag #3003 ist fertig, wenn zusätzlich AC-32 bis AC-35 auf Staging gemessen erfüllt sind (Vorlagen-Wähler bei Maus ca. 38 px wie im Mockup, bei Fingerbedienung mindestens 44 px, jeweils mittig), der Wächter `s3a2794-teil3-design.spec.ts` an die Bedienart angepasst und grün ist und Henning das Soll/Ist-Bild bekommen hat.

## Acceptance Criteria

- **AC-1:** Given ein Trip ist im Hub geöffnet (Desktop, DE) / When die Kopfleiste betrachtet wird / Then zeigt sie die Brotkrumen „Trips / <Tripname>“, ein Kebab-Menü „Weitere Aktionen“ und den Knopf „Test schicken ▾“, und der Name in den Brotkrumen führt nicht zurück auf sich selbst, „Trips“ führt zur Trip-Liste.
  - Test: E2E am Trip-Hub: Brotkrumen-Link „Trips“ klicken, Liste erscheint; Knopfbeschriftung geprüft.

- **AC-2:** Given ein Orts-Vergleich ist im Hub geöffnet (Desktop, DE) / When die Kopfleiste betrachtet wird / Then zeigt sie „Orte / <Vergleichsname>“, das Kebab-Menü „Weitere Aktionen“ und den Knopf „Test schicken ▾“, und „Orte“ führt zur Vergleichs-Liste.
  - Test: E2E am Vergleichs-Hub, gleiche Prüfung wie AC-1; Gleichheit mit Trip über `hub-kopf-paritaet-compare-trip`.

- **AC-3:** Given ein Trip mit Region „Mallorca“, vier Etappen, Datum, Strecke und Aufstieg / When der Kopf betrachtet wird / Then steht über dem Titel „Trip · Mallorca“, der Titel trägt eine Status-Pill, und die Meta-Zeile lautet im Format „Datum · 4 Etappen · km · ↑m“.
  - Test: Unit (Kopf mit Fixture) plus E2E am Staging-Trip; Zahlenformat DE „31,5 km“.

- **AC-4:** Given ein Orts-Vergleich mit Region und drei Orten / When der Kopf betrachtet wird / Then steht über dem Titel „Orte · <Region>“ und die Meta-Zeile lautet „3 Orte · Vergleichstabelle · Briefing HH:MM“ (Zeit des konfigurierten Briefings).
  - Test: Unit mit Vergleichs-Fixture plus E2E am Staging-Vergleich.

- **AC-5:** Given ein Trip bzw. Vergleich im Zustand Entwurf, aktiv, pausiert, archiviert oder fertig / When der Titel betrachtet wird / Then zeigt die Status-Pill den passenden Zustand, und im Entwurf bietet der Kopf „Aktivieren“ an; Trip und Vergleich verhalten sich gleich.
  - Test: Unit über alle fünf Zustände für beide Kontexte; E2E: Entwurf aktivieren, Pill wechselt auf „aktiv“.

- **AC-6:** Given ein Trip mit vier Etappen bzw. ein Vergleich mit drei Orten / When die Reiterleiste betrachtet wird / Then lauten die Reiter „Übersicht · Etappen (4) · Wetter · Zustellung“ bzw. „Übersicht · Orte (3) · Wetter · Zustellung“, und der gerade aktive Reiter ist als aktuell markiert (`aria-current`).
  - Test: E2E liest Reiter-Beschriftungen und `aria-current` in beiden Kontexten; Unit für Badge-Zähler.

- **AC-7:** Given ein Trip, dem eine Etappe hinzugefügt wird / When die Reiterleiste neu angezeigt wird / Then steht im Reiter Etappen die neue Anzahl (Zähler folgt den Daten).
  - Test: E2E mit Seed-Trip: Etappe ergänzen, Badge wechselt von N auf N+1; analog Ort im Vergleich.

- **AC-8:** Given der Hub eines Trips oder Vergleichs mit Reiter Wetter / When die Vorlage-Karte betrachtet wird / Then zeigt sie die Überschrift „Vorlage“, den Namen der gewählten Vorlage mit Zustand „unverändert“ bzw. „N Abweichung(en)“, die Aktionen „Als eigene Vorlage speichern“ und „Auf „<Vorlage>“ zurücksetzen“, die Auswahl gliedert sich in „Vorlagen“ und „Eigene“, und der Satz „Name der Vorlage ersetzt das Profil und steht im Kopf der Mail“ erscheint nicht.
  - Test: E2E in Trip und Vergleich: Auswahl öffnen, Gruppen und Texte prüfen, Satz abwesend; Unit für Abweichungszähler.

- **AC-9:** Given ein Trip oder Vergleich im Hub / When Name oder Region geändert werden sollen / Then zeigt der Ruhezustand nur ein Stift-Symbol mit Beschriftung für Screenreader, ein Klick öffnet die Bearbeitung, und nach Speichern erscheinen neuer Name und Region in Brotkrumen, Titel und Eyebrow, ohne dass andere Felder (inkl. Profil) verloren gehen.
  - Test: E2E `hub-kopf-bearbeiten` (Trip und Vergleich): Name ändern, speichern, Seite neu laden, Wert und unverändertes Profil bleiben.

- **AC-10:** Given die Oberfläche ist auf Englisch gestellt / When Trip-Hub und Vergleichs-Hub geöffnet werden / Then erscheinen Brotkrumen, Eyebrow, Pill, Meta-Zeile, Reiter, Vorlage-Karte und Knopf „Send test ▾“ (EN-Wortlaut in `elementliste.json` als Lücke markiert, `text_en: null`; Übersetzung legt diese Scheibe fest und meldet sie an #2968) vollständig auf Englisch ohne deutsche Reste, Protokoll-Token bleiben unübersetzt.
  - Test: E2E in EN für beide Kontexte; Unit Katalog-Parität DE/EN.

- **AC-11:** Given ein Handy-Viewport (Mobil) / When Trip-Hub und Vergleichs-Hub geöffnet werden / Then bleiben Brotkrumen, Titel mit Pill, Reiterleiste mit Badge und „Test schicken ▾“ erreichbar und ohne horizontales Überlaufen bedienbar, auch mit langem Namen.
  - Test: E2E mit Mobil-Viewport (`mobile-ux-messung`), Trip und Vergleich, kein Seiten-Scrollen quer.

- **AC-12:** Given die c2-Besitzer-Einträge sind bearbeitet / When die Besitzerliste geprüft wird / Then enthält sie keinen Eintrag mit Verweis `#2913-c2` mehr; Einträge zu Profil, Tempo-Karte und Mail-Kopf-Satz verweisen auf `#2796` (Grund „Scheibe S4, Datenmodell+Migration“) und nichts davon ist gelöscht; die 8 Einträge für das „Test schicken“-Menü bleiben bei #2797.
  - Test: Unit liest die Besitzerliste als Daten, Anzahl und Verweise geprüft (Doku-Daten; Testdatei trägt Pflicht-Marker `# doc-compliance-test`).

- **AC-13:** Given Staging mit dem Stand dieser Scheibe / When `npm run elementliste:abgleich -- --abnahme` für DE und EN läuft / Then endet der Lauf jeweils mit Exit 0, und eine absichtlich verfälschte Kopf-Beschriftung (Gegenprobe) macht ihn rot.
  - Test: Abgleich-Lauf gegen Staging, Exit-Code DE und EN; Mutations-Gegenprobe per String-Ersetzung am Kopf-Text.

- **AC-14:** Given zwei verschiedene Nutzer mit eigenen Trips und Vergleichen / When beide ihren Hub öffnen / Then sieht jeder nur eigene Namen, Regionen und Zähler; diese Scheibe ändert keinen Endpoint und keine gespeicherten Daten.
  - Test: E2E mit zwei Staging-Nutzern: Brotkrumen und Zähler zeigen je nur die eigenen Daten; Datenstand vor/nach unverändert.

- **AC-15:** Given ein Nutzer im Hub / When der Ruhezustand geprüft wird / Then bleiben Profil-Zeile bzw. Profil-Chip unverändert sichtbar (Entfernung gehört zu #2796), und Tempo/Ankunftszeiten rechnen unverändert.
  - Test: E2E: Profil-Chip vorhanden und änderbar in Trip und Vergleich; Unit `trip_header_status_profil` unverändert grün.

### Fix-Loop Bildabgleich Runde 1 (#2980)

Grundlage: acht Abweichungen des `mockup-bildpruefer` (Runde 1) und zwei PO-Entscheidungen vom 13.11.2026 (Handy-Reiterleiste wie Mockup; Kennzahlenzeile am Handy entfällt). Die ACs AC-1 bis AC-15 gelten unverändert weiter; keine davon wird inhaltlich überholt (AC-6 und AC-11 gelten mit der neuen Reiter-Optik weiter, die Pillen-Optik stand in keiner AC dieser Spec). Alle ACs gelten für Trip und Orts-Vergleich gleichermaßen (geteilte Bausteine, ADR-0097), in DE und EN.

- **AC-16:** Given ein Trip oder Orts-Vergleich ist im Hub geöffnet (Desktop und Handy, DE und EN) / When der Knopf „Test schicken ▾“ betrachtet wird / Then ist er als Akzent-Knopf (`Btn variant="accent"`) mit Fläche `--g-accent-deep` und heller Schrift dargestellt statt schwarz (Ink), und der Kontrast von Schrift zu Fläche beträgt mindestens 4,5:1 (bewusste, dokumentierte Abweichung vom Mockup-Orange `#c45a2a`, das weiß nur ca. 4,3:1 erreicht).
  - Test: Unit prüft Variante `accent` und aufgelöste Fläche; E2E liest die berechnete Hintergrundfarbe im Browser und rechnet das Kontrastverhältnis; Abweichung steht in der Ausnahmenliste des Abgleichs.

- **AC-17:** Given ein Handy-Viewport (390 px) mit Trip-Hub oder Vergleichs-Hub / When die Reiterleiste betrachtet wird / Then erscheinen die Reiter als Text-Reiter ohne Pillen-Hintergrund: inaktiv `--g-ink-3` mit Schriftgewicht 500, aktiv `--g-ink` mit Gewicht 600 und einem 2 px starken Unterstrich in `--g-accent`, darunter eine durchgehende Grundlinie in `--g-rule`; auf dem Desktop sieht die Leiste identisch aus.
  - Test: E2E bei 390×844 und 1280×900 liest berechnete Farben, Gewichte und Unterstrich-Stärke des aktiven und eines inaktiven Reiters; Unit auf `MTabBar` ohne Pillen-Klassen.

- **AC-18:** Given ein Handy-Viewport mit mehr Reitern, als nebeneinander passen / When die Reiterleiste benutzt wird / Then lässt sich die Leiste seitlich wischen, jeder Reiter hat eine Tippfläche von mindestens 44 px Höhe, und der aktive Reiter bleibt sichtbar bzw. wird in den sichtbaren Bereich gescrollt.
  - Test: E2E bei 390×844: Reiter-Höhe ≥44 px gemessen, Leiste scrollbar (scrollWidth > clientWidth bei langen Beschriftungen), Wisch/Scroll bringt letzten Reiter ins Bild; gilt für Trip und Orte (geteilter `MTabBar`).

- **AC-19:** Given ein Trip-Hub am Handy / When der Kopf betrachtet wird / Then erscheint keine Kennzahlenzeile „Etappe · Briefing · Start in“ mehr (Anforderung #416 ist durch diese PO-Entscheidung abgelöst), während Desktop und Orts-Vergleich keine solche Zeile zeigen und die Meta-Zeile aus AC-3/AC-4 erhalten bleibt.
  - Test: E2E bei 390×844 am Trip-Hub: Element `mobile-metrics` fehlt und der Text „Start in“ steht nicht im Kopf; Bestandstest `TripHeader.mobile-metrics.test.ts` ist ersatzlos entfernt.

- **AC-20:** Given ein Trip oder Orts-Vergleich im Hub / When die Meta-Zeile unter dem Titel betrachtet wird / Then ist sie in Monospace-Schrift mit 13 px und Farbe `--g-ink-3` gesetzt (nicht mehr Sans in `--g-ink-2`), Inhalt und Zahlenformat bleiben wie in AC-3 und AC-4.
  - Test: E2E liest berechnete Schriftfamilie, Größe und Farbe der Meta-Zeile in beiden Kontexten und beiden Sprachen; Unit auf Klasse/Token.

- **AC-21:** Given ein Trip oder Vergleich in einem der Zustände fertig, aktiv, Entwurf, pausiert oder archiviert / When die Status-Pill am Titel betrachtet wird / Then ist sie gefüllt ohne Rahmen (Mono 11 px, Großschreibung per CSS), „aktiv“ als grüne Pill (`--g-good` auf hellgrünem Grund), alle anderen Zustände neutral (`--g-ink-3` auf `--g-paper-deep`), der Text im DOM bleibt unverändert und `data-status` bleibt erhalten.
  - Test: Unit über alle fünf Zustände (Ton, kein Rahmen, DOM-Text unverändert); E2E liest berechnete Rahmenbreite 0 und Hintergrundfarbe der Pill in Trip und Vergleich.

- **AC-22:** Given Hell- und Dunkelmodus / When die neutrale Status-Pill betrachtet wird / Then beträgt der Kontrast von Schrift zu Grund mindestens 4,5:1; reicht `--g-ink-3` auf `--g-paper-deep` im Dunkelmodus dafür nicht, verwendet die neutrale Pill `--g-ink-2` und der Grund ist im Abgleich vermerkt.
  - Test: Unit rechnet das Kontrastverhältnis aus den aufgelösten Tokens für beide Modi und beide Pill-Töne.

- **AC-23:** Given ein Trip oder Orts-Vergleich im Hub (Desktop und Handy) / When die Kopfleiste (Brotkrumen) betrachtet wird / Then ist sie in Mono 11 px mit Großschreibung (nur per CSS, DOM-Text unverändert) in `--g-ink-3` gesetzt, der aktuelle Name steht in `--g-ink` mit Gewicht 500, und die Leiste trägt unten die Linie `--g-rule-soft`.
  - Test: E2E liest berechnete Schrift, Farben und Rahmen der Brotkrumen; Unit bestätigt, dass der DOM-Text nicht in Großbuchstaben gewandelt wird.

- **AC-24:** Given ein Handy-Viewport mit einem langen Trip- oder Vergleichsnamen / When die Brotkrumen betrachtet werden / Then steht dort der volle Name (kein Kürzel wie `shortcode`), es gibt keinen Zurück-Pfeil, der Name wird nicht mit Auslassungspunkten gekürzt, sondern bricht um, und die Seite läuft nicht horizontal über.
  - Test: E2E bei 390×844 mit Seed-Trip mit sehr langem Namen: Brotkrumen-Text gleich vollem Namen, kein Element `back-mobil`, `scrollWidth` der Seite gleich Viewport-Breite; analog Vergleich.

- **AC-25:** Given ein Trip oder Orts-Vergleich im Hub / When das Kebab-Menü „Weitere Aktionen“ betrachtet wird / Then ist es ein Ghost-Knopf (transparenter Grund) mit Rahmen in `--g-rule`, am Handy mit mindestens 44 px Tippfläche, und steht in der Reihenfolge vor dem Knopf „Test schicken ▾“.
  - Test: E2E liest berechneten Rahmen und Hintergrund sowie Höhe/Breite ≥44 px bei 390×844; DOM-Reihenfolge Kebab vor „Test schicken“ (AC aus c2 bleibt).

- **AC-26:** Given der Reiter Wetter im Hub eines Trips oder Vergleichs / When die Vorlage-Karte betrachtet wird / Then hat der Vorlagen-Wähler einen Rahmen in `--g-rule`, den Grund `--g-paper` und den Namen in 15 px mit Gewicht 600, und der Zusatz „▾ unverändert“ bzw. „▾ N Abweichung(en)“ steht in Mono 11 px `--g-ink-3`.
  - Test: E2E liest berechnete Stile des Wählers und des Zusatzes in Trip und Vergleich, DE und EN; Unit auf `VorlageKarte`.

- **AC-27:** Given die Vorlage-Karte im Reiter Wetter / When die Aktion „Als eigene Vorlage speichern“ neben dem Wähler betrachtet wird / Then ist sie vertikal mittig zur Karte ausgerichtet (Kartenzeile mit `align-items:center`), auch wenn die Spalte links eine Eyebrow „Vorlage“ trägt, und am Handy bleibt der Knopf bedienbar ohne horizontales Überlaufen.
  - Test: E2E misst die vertikale Mitte von Knopf und Karte (Abweichung ≤2 px) bei 1280×900 und 390×844; Bildvergleich im Bildprüfer.

- **AC-28:** Given der Reiter Wetter im Hub eines Trips oder Vergleichs / When der Abschnittskopf mit Überschrift und Erklärtext betrachtet wird / Then ist der Erklärtext höchstens 68ch breit, 13 px groß in `--g-ink-3`, und unter dem Abschnittskopf liegt eine Trennlinie in `--g-rule-soft` mit 12 px Abstand darüber.
  - Test: E2E liest berechnete Breite, Schrift, Farbe und untere Linie des Abschnittskopfs; Unit auf `WetterTabInhalt`-Kopf.

- **AC-29:** Given die Entscheidungen dieses Fix-Loops / When die Architektur-Dokumentation geprüft wird / Then existiert ADR-0118 (Handy-Reiter als Text-Reiter mit Unterstrich, „Test schicken ▾“ als Akzent-Hauptaktion mit Fläche `--g-accent-deep`, Kennzahlenzeile #416 entfällt), ADR-0109, ADR-0110 und ADR-0111 sind als „Teilweise abgelöst durch ADR-0118“ vermerkt, und `tests/test_adr_index_drift.py` ist grün, weil Datei-Status und Index-Zeile derselben Statusklasse angehören.
  - Test: `tests/test_adr_index_drift.py` grün (Doku-Test, Marker `# doc-compliance-test`); Gegenprobe: Index-Status von 0111 verfälscht macht den Test rot.

- **AC-30:** Given Staging mit dem Stand des Fix-Loops / When der `mockup-bildpruefer` in Runde 2 (letzte Runde) die acht Zustände Trip und Orte × DE und EN × 1280×900 und 390×844, jeweils Reiter Wetter, gegen das Mockup und den Elementlisten-Auszug vergleicht / Then bleibt keine offene c2-Abweichung übrig; nicht-c2-Abweichungen („Andere Besitzer“) sind benannt und gehören zu #2796, #2797, #2954, App-Rahmen, V16 oder dem Folge-Issue zum EN-Vorlagennamen, und die bewusste Abweichung der Knopf-Fläche (`--g-accent-deep`) ist offen im Soll/Ist-Bild für Henning genannt.
  - Test: Playwright-Aufnahmen von Mockup (file://) und Staging je Zustand, Prüfer-Verdikt Runde 2 liegt als Artefakt vor; Henning erhält ein Soll/Ist-Bild.

- **AC-31:** Given zwei verschiedene Nutzer mit eigenen Trips und Vergleichen / When beide den Hub mit der neuen Optik öffnen / Then sehen beide dieselbe Optik, und jeder sieht nur die eigenen Namen und Zähler; der Fix-Loop ändert reine Darstellung (CSS und Markup), keinen Endpoint und keine gespeicherten Daten.
  - Test: bestehender E2E-Lauf mit zwei Staging-Nutzern aus AC-14 bleibt grün; Datenstand vor/nach unverändert (Zwei-Nutzer-Test für neue Optik nicht nötig, da keine Daten bewegt werden).

### Nachtrag Rest Bildabgleich Runde 2 (#3003)

Grundlage: drei Rest-Abweichungen aus dem `mockup-bildpruefer` Runde 2 nach #2980 (Vorlagen-Wähler, Abstand Eyebrow zu Wähler, Reiterleiste am Handy) und die PO-Entscheidung vom 14.11.2026 zur Höhe des Wählers nach Bedienart. AC-1 bis AC-31 gelten unverändert weiter; keine davon wird geändert. Alle ACs gelten für Trip und Orts-Vergleich gleichermaßen (geteilte Bausteine `VorlageKarte` und `MTabBar`, ADR-0097), in DE und EN. Außerhalb des Umfangs bleiben Punkte anderer Besitzer aus Issue #3003 (#2796, #2981, #2954, App-Rahmen, die bewusste Kontrast-Abweichung am Knopf „Test schicken“).

- **AC-32:** Given der Reiter Wetter im Hub eines Trips oder Orts-Vergleichs (DE und EN) / When der Vorlagen-Wähler mit Vorlagenname und „▾ unverändert“ betrachtet wird / Then steht dieser Inhalt in beiden Bedienarten vertikal mittig im Knopf (Abstand zum oberen Rand und zum unteren Rand unterscheiden sich um höchstens 2 px) bei seitlichem Polster von 12 px wie im Mockup, und die Höhe richtet sich nach der Bedienart: bei Mausbedienung (`pointer: fine`, zum Beispiel 1280×900) beträgt sie wie im Mockup ca. 38 px (±2 px), bei Fingerbedienung (`pointer: coarse`, zum Beispiel Handy 390×844 mit Touch) mindestens 44 px Tippfläche (K-5, #2284); die Bildschirmbreite entscheidet darüber nicht.
  - Test: E2E (Staging) misst Wähler-Rahmen und Textbox im Browser in Trip und Orten, DE und EN: bei 1280×900 mit Maus Höhe 38 ±2 px, bei 390×844 mit Touch-Emulation (`hasTouch`/`isMobile`) Höhe ≥ 44 px, jeweils Abstand oben ≈ unten (±2 px) und Polster 12 px; Kern-Test auf `align-items: center` und auf eine Regel unter `pointer: coarse` mit `min-height` aus `--g-tap-min`; der angepasste Wächter `s3a2794-teil3-design.spec.ts` bleibt grün.

- **AC-33:** Given der Reiter Wetter im Hub am Handy (390×844 mit Touch-Emulation, Trip und Orts-Vergleich, DE und EN) / When der Abstand zwischen der Überschrift „Vorlage“ bzw. „Template“ und dem Wähler-Text betrachtet wird / Then liegt zwischen der Unterkante der Überschrift und der Oberkante des Wähler-Textes mindestens 12 px freier Raum, der durch die Mittig-Ausrichtung aus AC-32 entsteht (gerechnet ca. 18 px: 6 px Gap, 1 px Rahmen und ca. 11 px Luft im Knopf über dem Text), während der Gap zwischen Überschrift und Wähler wie im Mockup 6 px bleibt.
  - Test: E2E (Staging) bei 390×844 in Touch-Emulation misst Unterkante der Eyebrow bis Oberkante der Wähler-Textbox (≥ 12 px) und den unveränderten Gap von 6 px, in Trip und Orten, DE und EN.

- **AC-34:** Given ein Handy-Viewport unter 900 px, Trip-Hub oder Orts-Vergleichs-Hub (geteilte Reiterleiste `MTabBar`), DE und EN / When die Reiterleiste bei 390 px betrachtet wird / Then wachsen die Reiter auf die volle Leistenbreite (Inhalt zentriert), die rechte Kante des letzten Reiters liegt auf dem rechten Leistenende (±2 px), die Schrift bleibt 13 px und das Mindestpolster 10 px; bei Überbreite (zum Beispiel 360 px mit langen oder vielen Reitern) bleibt das bestehende seitliche Scroll-Band mit Fade unverändert, die vier DE-Reiter laufen bei 360 px nicht über (#2794 B2), und Unterstrich, Zähler und Trennlinie der Reiter sowie die Desktop-Reiterleiste sehen unverändert aus.
  - Test: E2E (Staging) misst bei 390 px die rechte Kante des letzten Reiters gegen das Leistenende in Trip und Orten, DE und EN, und bei 360 px DE `scrollWidth` gegen `clientWidth` der vier Reiter; Kern-Test auf `flex: 1 0 auto`, Schrift `--g-text-sm` und Polster `--g-size-10px`; Wächter `s3a2794_mtabbar_leiste_soll.test.ts` bleibt grün.

- **AC-35:** Given Staging mit dem Stand dieses Nachtrags / When die acht Zustände Reiter Wetter, Trip und Orte, DE und EN, 1280×900 (Maus) und 390×844 (Touch-Emulation) aufgenommen und vom `mockup-bildpruefer` gegen das Mockup verglichen werden / Then meldet der Prüfer für Wähler-Lage, Wähler-Höhe (bei Maus Mockup-Höhe, bei Finger 44 px Tippfläche), Abstand Eyebrow zu Wähler und Reiter-Verteilung keine offene c2-Abweichung, nicht-c2-Punkte sind ihren Besitzern zugeordnet (#2796, #2981, #2954, App-Rahmen, Kontrast „Test schicken“), und Henning erhält ein Soll/Ist-Bild, in dem Wähler-Höhe und Mittig-Ausrichtung als erfüllt gezeigt sind.
  - Test: Playwright-Aufnahmen der acht Zustände auf Staging (Desktop mit Maus, Handy mit Touch-Emulation), Prüfer-Verdikt als Artefakt, Soll/Ist-Bild an den PO; Zwei-Nutzer-Test nicht nötig, weil reine Darstellung ohne Datenbewegung (wie AC-31).

## Known Limitations

- Mockup ist nur Deutsch; EN-Lücken in `elementliste.json` sind #2968 zugeordnet, fehlende EN-Texte werden im Katalog sinnvoll ergänzt und dort vermerkt.
- „Test schicken ▾“ ist in c2 nur Beschriftung; das Menü mit Morgen-/Abend-Briefing kommt mit #2797.
- Profil-Zeile, Tempo-Karte und Mail-Kopf-Satz weichen bis #2796 vom Mockup ab (sichtbar als umgehängte Besitzer-Einträge).
- Abnahme ist nur gegen Staging prüfbar (nicht lokal, nicht Prod).
- Knopf-Fläche „Test schicken ▾“ ist bewusst `--g-accent-deep` statt Mockup-`--g-accent` (WCAG-AA); der Bildprüfer meldet das als Farbabweichung, sie ist dokumentiert und dem PO offen genannt.
- Der Bildprüfer-Fix-Loop ist nach Runde 2 beendet; verbleibende Abweichungen gehen als eigene Issues weiter, nicht in eine dritte Runde.
- Die Höhe des Vorlagen-Wählers folgt der Bedienart (Maus ca. 38 px wie im Mockup, Finger mindestens 44 px; PO-Entscheidung 14.11.2026, #3003). Geräte, die beide Eingabearten melden (zum Beispiel Touch-Laptop), werden vom Browser nach der primären Eingabeart eingeordnet; die Messung auf Staging deckt die beiden Reinfälle (Maus 1280×900, Touch 390×844) ab.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** Basis c2: keine neue; berührt ADR-0097 (Teilung Trip/Vergleich), ADR-0104 (Zweisprachigkeit), ADR-0108 (Profil → Vorlage, bleibt #2796), ADR-0112 (Design-System-Bausteine). **Fix-Loop #2980: neues ADR-0118** (Handy-Reiter Unterstrich, Akzent-Hauptaktion „Test schicken ▾“, Kennzahlenzeile #416 entfällt); ADR-0109, ADR-0110 und ADR-0111 werden dadurch teilweise abgelöst (Teil Handy-Pillen bzw. „Hauptaktion Ink“ für diesen Knopf) und tragen den Vermerk „Teilweise abgelöst durch ADR-0118“, Index nach `tests/test_adr_index_drift.py` konsistent. **Nachtrag #3003:** kein neues ADR; reine Feinabstimmung innerhalb von ADR-0118. Die Regel K-5 / AC-40 (Touch-Ziele ≥ 44 px, #2284) steht in keinem ADR (Prüfung per Suche in `docs/adr` nach „44“, „Touch-Ziel“, „tap“, „K-5“: einziger Treffer ist die 44-px-Tippfläche der Handy-Reiter in ADR-0118, die unberührt bleibt), sondern nur in den Specs `feat_2913_s3_bausteine.md` und `feat_2794_s3a_teil3_wetter.md`. Die Präzisierung auf Fingerbedienung wird deshalb als Vermerk „AC-40 präzisiert durch #3003 (Bedienart)“ in `feat_2794_s3a_teil3_wetter.md` festgehalten; ein ablösendes ADR ist nicht nötig.
- **Rationale:** Basis c2 ist eine reine Darstellungsanpassung innerhalb bestehender Entscheidungen. Der Zuschnitt (Profil/Tempo/Mail-Kopf bei #2796) folgt dem freigegebenen Scheibenplan `docs/context/einstellungen_neu.md` §10; eine „nur Oberfläche über `activity`“-Variante wurde verworfen, weil sie #2796 halb vorwegnähme und Bestandsdaten gefährdete. Der Fix-Loop weicht bewusst von ADR-0109/0110/0111 ab, weil der PO am 13.11.2026 die Mockup-Optik für Handy-Reiter bestätigt hat; Entscheidungen werden nie still rückgängig gemacht, daher das neue ADR.

## Changelog

- 2026-11-13: Initial spec created (Scheibe c2, Arbeitsplan #2913)
- 2026-11-13: Erweitert um Fix-Loop Bildabgleich Runde 1 (#2980): AC-16 bis AC-31 (Akzent-Knopf, Handy-Reiter Unterstrich, Kennzahlenzeile entfällt, Meta Mono, gefüllte Status-Pill, Kopfband/Brotkrumen/Kebab, Vorlage-Karte, Abschnittskopf Wetter, ADR-0118, Bildprüfer Runde 2, Zwei-Nutzer-Begründung); Nicht-Ziele „Andere Besitzer“ übernommen; AC-1 bis AC-15 unverändert, keine überholt. Status bleibt Entwurf, Freigabe der neuen ACs steht aus.
- 2026-11-14: Nachtrag Rest Bildabgleich Runde 2 (#3003): AC-32 bis AC-35 (Vorlagen-Wähler mittig, Höhe nach Bedienart: Maus ca. 38 px wie Mockup, Finger mindestens 44 px, PO-Entscheidung Henning; Abstand Eyebrow zu Wähler am Handy, Handy-Reiterleiste füllt volle Breite, Abnahme mit Soll/Ist-Bild); Präzisierung von K-5 / AC-40 auf Fingerbedienung mit Anpassung des Wächters `s3a2794-teil3-design.spec.ts` und Vermerk in `feat_2794_s3a_teil3_wetter.md`; AC-1 bis AC-31 unverändert. Status bleibt Entwurf, Freigabe der neuen ACs steht aus.
