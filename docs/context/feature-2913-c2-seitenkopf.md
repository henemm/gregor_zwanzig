# Context: feature-2913-c2-seitenkopf

## Request Summary
Scheibe c2 aus Arbeitsplan #2913: Seitenkopf des Editor-Hubs (Trip + Orts-Vergleich, geteilter Code) nach
`docs/context/einstellungen_neu/seiten/mockup-hub-fassung3.html`: Profil-Zeile entfällt (Vorlage ersetzt das Profil),
Tempo zieht in den Reiter Etappen, Kopfzeilen (Brotkrumen, Eyebrow, Titel+Status-Pill, Meta, Kebab, „Test schicken ▾“),
Reiterleiste und Vorlage-Karte nach Mockup. Ziel: die 92 Besitzer-Einträge `#2913-c2` in
`docs/context/einstellungen_neu/elementliste_besitzer.json` können entfallen, Abgleich DE/EN bleibt Exit 0.

## Mockup (Soll)
| Bereich | Mockup-Zeilen | Inhalt |
|---|---|---|
| Leiste `.crumbs` | 228–242, Menü `renderMenu` 368ff | „Trips / **Name**“ bzw. „Orte / **Name**“; rechts Kebab ⋮ „Weitere Aktionen“ + „Test schicken ▾“ (Trip: Morgen-/Abend-Briefing, Orte: Orts-Briefing) |
| Kopf | 244, `renderHead` 358–365, `CTX` 310–313, `PILL` 326 | Eyebrow („Trip · Mallorca“ / „Orte · Münsterland“), h1 + Status-Pill (fertig/aktiv/Entwurf/pausiert/archiviert; Entwurf + „Aktivieren“), Meta („23.–26. Februar 2026 · 4 Etappen · 31,5 km · ↑1.737 m“ / „3 Orte · Vergleichstabelle · Morgen-Briefing 07:00“) |
| Reiterleiste | 245, 363 | Übersicht · Etappen (4) · Wetter · Zustellung bzw. Übersicht · Orte (3) · Wetter · Zustellung, `aria-current`, Zähler-Badge |
| Vorlage-Karte | 508–512, Picker 454–465, Liste 319, Notiz 253 | Eyebrow „Vorlage“, „{Name} ▾ unverändert / N Abweichung(en)“, „Als eigene Vorlage speichern“, „Auf „X“ zurücksetzen“; Gruppen Vorlagen/Eigene; „Name der Vorlage ersetzt das Profil und steht im Kopf der Mail“ |
| Tempo (Etappen) | `viewEtappen` 577–587 | Abschnittskopf „Etappen & Wegpunkte“ + „Das Tempo bestimmt die Gehzeiten …“; Karte Fortbewegung (zu Fuß/Rad/MTB/Ski), „Tempo flach 4,0 km/h“, „Aufstieg 300 Hm/h“, „Gilt für alle Etappen, je Etappe überschreibbar“; je Etappe „Gehzeit h:mm“ + „Tempo ändern“ |

Kein Name-/Region-Bearbeiten, keine Profil-Chips im Mockup. Mockup ist nur DE; EN aus `elementliste.json` (Lücken → #2968).

## Related Files (Ist)
| File | Relevance |
|------|-----------|
| `frontend/src/lib/components/shared/hub-kopf/HubKopf.svelte` | geteilter Kopf, `data-seite="hub"`/`data-abschnitt="kopf"`, Brotkrumen 76–79, „Senden“ 81–86, Kebab 87, bindet SubscriptionHeader (93) |
| `frontend/src/lib/components/shared/subscription-header/SubscriptionHeader.svelte` | Name/Region bearbeiten (122–142), Profil-Chips 151–158, Profil-Knopf mobil 170–175, `Field` inkl. `'profile'` |
| `frontend/src/lib/components/trip-detail/TripHeader.svelte` 141–190 | Trip-Bindung: `profile={trip.activity}`, Eyebrow=Datum, StatusSchild + „läuft seit Tag N“, Meta km/↑m, Mobil-Stat-Kacheln |
| `frontend/src/routes/compare/[id]/+page.svelte` 172–177, 364ff | Vergleich-Bindung: Profil-Optionen, `profile={currentPreset.profil}`, Meta „· N Orte“ |
| `frontend/src/lib/components/trip-detail/TripTabs.svelte` 186–199 · `compare/CompareTabs.svelte` 690–702 | Reiterleiste (Wrapper `reiterleiste` um `MTabBar`) |
| `frontend/src/lib/components/organisms/wetter-tab/VorlageKarte.svelte` | Vorlage-Karte existiert (`data-abschnitt="vorlage"`), in `WetterTabInhalt.svelte:236` |
| `frontend/src/lib/components/edit/EditStagesPanelNew.svelte` 203–206 | Ankunftszeiten über `activityToSpeed(activityType)`; keine Tempo-UI |
| `frontend/src/lib/utils/naismith.ts:29` · `internal/model/naismith.go:36` · `internal/store/trip.go:313` | Tempo heute nur aus `trip.activity` abgeleitet (fahrrad_15/20/25, sonst 4,0 km/h) |
| `frontend/e2e/elementliste_abgleich_logik.ts` · `elementliste-abgleich.staging.spec.ts` · `scripts/elementliste_abgleich.ts` | Ganzseiten-Abgleich; `npm run elementliste:abgleich -- --abnahme|--strict` (nur gegen Staging) |
| `frontend/src/lib/i18n/messages/{de,en}/*.json` | `aktionen.kopf.*`, `trip.aktivitaet.*`, `trip.kopf.*`, `bausteine.profil.*`, `wetter.vorlage.*`, `listen.*`, `vergleich.hub.*`, `home.tage.laeuft_seit` |

## Existing Patterns
- Trip/Vergleich teilen Kopf, Reiter, Wetter-Tab (ADR-0097, `context="route"|"vergleich"`); neue Elemente nur als geteilte Bausteine.
- ADR-0112: Oberfläche ausschließlich aus Design-System-Bausteinen (`frontend/src/lib/components/{atoms,molecules,organisms}`), Wächter `bausteine_waechter*.test.ts`. Passende Atome: Eyebrow, Pill, Btn, Segmented, Input, Card, SectionH, Stat; Moleküle SubscriptionKebab, Field; StatusSchild, MTabBar.
- Abgleich-Marker: `data-seite="hub"`, `data-abschnitt=kopf|reiterleiste|vorlage|…`; für Etappen fehlt `tempo` (ggf. `abschnittskopf`).
- Vorlagen: eigene (`internal/model/metric_preset.go`, ADR-0106) + System (`/api/templates` → Python), Frontend `wetterTabLaden.ts`, `anlegeVorbelegung.ts`.

## Dependencies
- Upstream: `trip.activity` (Go `internal/model/trip.go:132`, Handler `trip.go:452`), Vergleich `profil` (`compare_preset.go:26`, `IsValidProfile`, Python `models.py:1330`), i18n-Katalog, Design-System-Atome.
- Downstream von `activity`/`profil`: Tempo/Ankunftszeiten (TS+Go), Vorlage-Vorbelegung beim Anlegen (`WeatherMetricsTab.svelte:661–680`), Aggregations-Profil (`wizardHelpers.ts`), Mail-Eyebrow aus Profil (`profile_signature.py:103–109`, `compare_html.py:1449`), `corridorEditorState.ts:526`.

## Existing Specs
- `docs/specs/modules/feat_2913_abgleich_ganzseite.md` (Marker, AC-11..14), `feat_2913_scheibe_c_wetter_rest.md`, `feat_2913_s3_bausteine.md`
- `rework_2837_s1_hub_kopf.md`, `rework_2837_s1b_status_profil.md`, `rework_2845_hub_reiterleiste.md`
- `feat_2794_s3a_reiter_wetter.md` (+teil2..4, Vorlage-Karte), `feat_1273_s2_compare_hub_name_region_profil.md`, `activity_profile.md`
- ADR-0097, ADR-0112

## Bestehende Tests (betroffen)
Unit: `shared/hub-kopf/__tests__/*`, `shared/__tests__/subscription_header_*.test.ts`, `aktionsmodell_seiten_bindung.test.ts`, `trip-detail/__tests__/trip_header_status_profil.test.ts`, `compare/__tests__/issue_491_*`, `issue_493_*`, `vergleich_nutzt_gemeinsame_aktionen.test.ts`, `routes/compare/__tests__/bug_589_breadcrumb_links.test.ts`, `lib/__tests__/elementliste_abgleich_ganzseite.test.ts`, `bausteine_waechter*.test.ts`, `i18n/__tests__/keine_hartkodierten_nutzertexte.test.ts`.
E2E: `hub-kopf-aufbau`, `hub-kopf-bearbeiten`, `hub-kopf-paritaet-compare-trip`, `trip-hub-kopf-region-aktivitaet`, `compare-editor-fidelity-s8d`, `mobile-ux-messung`, `issue-344-wetter-profile`.

## Risks & Considerations
- **Profil entfernen ≠ Daten löschen:** `activity`/`profil` speisen Tempo, Mail-Eyebrow und Vorbelegung. Profil-Zeile weg darf keine Bestandsdaten verlieren (Read-Modify-Write); Mail-Kopf soll laut Mockup den Vorlagennamen zeigen — eigene Frage, ob in c2 oder separat (Mail-Pfad → Validator-Pflicht).
- **Tempo braucht ein Datenfeld:** heute nur abgeleitet. Mockup verlangt Fortbewegung + Tempo flach + Aufstieg, je Etappe überschreibbar → neues Schema (Go+Python+TS, Naismith in beiden Sprachen) oder in c2 nur „Fortbewegung + Tempo flach“ über das bestehende `activity`. Scope-Entscheidung in der Analyse.
- Name/Region bearbeiten fehlt im Mockup — Entfernen nimmt eine bestehende Funktion weg (Abgleich mit PO-Vorgaben/früheren Specs nötig).
- „Test schicken ▾“-Menü gehört laut Triage zu #2797; c2 nur Beschriftung/Platz im Kopf.
- Viele Unit-/E2E-Tests binden an Profil-Chips und „Senden“; müssen mitgezogen, nicht gelöscht werden ohne Ersatz.
- EN-Texte: Mockup DE-only; neue Schlüssel in beide Kataloge (ADR-0104), EN-Lücken #2968.
- Abgleich läuft nur gegen Staging; Abschluss = Besitzer-Einträge c2 entfernt und `--abnahme` Exit 0 DE+EN.

## Analysis

### Type
Feature (Oberflächen-Scheibe c2 aus Arbeitsplan #2913, Epic #2791)

### Tech-Lead-Entscheidungen (keine PO-Frage nötig, aus bestehenden Vorgaben abgeleitet)
1. **Zuschnitt c2 = Kopf + Reiterleiste + Vorlage-Karte.** Profil-Zeile weg, Fortbewegung/Tempo im Reiter Etappen,
   Orte-`profil` → Vorlagenname (Kopf, Versand, Mail-Kopf) und Migration gehören laut freigegebenem Scheibenplan
   (`docs/context/einstellungen_neu.md` §10) und Issue-Text vollständig zu **#2796 (S4, ADR-0108)**. Variante „nur
   Oberfläche über `activity`“ würde #2796 halb vorwegnehmen (8 activity-Werte vs. 4 Segmente, keine Migration, keine
   persistenten Tempo-Felder) und einen Funktionsverlust riskieren → verworfen. Profil-Chip bleibt bis #2796.
   Konsequenz: Besitzer-Einträge `#2913-c2`, die Profil-Wegfall, Tempo-Karte (`abschnitt=tempo`, Reiter etappen) oder
   den Satz „Name der Vorlage ersetzt das Profil und steht im Kopf der Mail“ betreffen, werden auf `#2796` umgehängt
   (Grund: „Scheibe S4, Datenmodell+Migration“), nicht gelöscht.
2. **Name/Region bleiben inline bearbeitbar** (Inventar `einstellungen_neu.md` §3.3 K1/K2 „abgedeckt – Kopf“, angenommen;
   feat_1273_s2: Hub einzige Bearbeiten-Fläche). Stift im Ruhezustand nur als Icon mit aria-label; sichtbare
   Zusatztexte im Bearbeiten-Zustand als Ausnahme mit Spec-Verweis (Abgleich-Logik `elementliste_abgleich_logik.ts`
   Z. 123–140, `leseAusnahmen` Z. 503ff).
3. **„Test schicken ▾“**: in c2 nur Beschriftung/Platz (Prop `sendLabel`, testid `subscription-hub-send` bleibt);
   Menü bleibt bei #2797 (8 Besitzer-Einträge unverändert).
4. Der Vergleichs-Profil-Default bei Neuanlage ist mit (1) keine c2-Frage.

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `frontend/src/lib/components/shared/hub-kopf/HubKopf.svelte` | MODIFY | Brotkrumen „Trips/Orte / **Name**“, Eyebrow, h1+Status-Pill, Meta, Kebab, Knopf „Test schicken ▾“ (Beschriftung) |
| `frontend/src/lib/components/shared/subscription-header/SubscriptionHeader.svelte` | MODIFY | Ruhezustand nach Mockup (Titel/Eyebrow/Meta), Stift als Icon; Profil-Teil unverändert (bis #2796) |
| `frontend/src/lib/components/trip-detail/TripHeader.svelte` | MODIFY | Eyebrow „Trip · Region“, Meta „Datum · N Etappen · km · ↑m“, Pill-Zustände |
| `frontend/src/routes/compare/[id]/+page.svelte` | MODIFY | Eyebrow „Orte · Region“, Meta „N Orte · Vergleichstabelle · Briefing HH:MM“ |
| `frontend/src/lib/components/trip-detail/TripTabs.svelte`, `compare/CompareTabs.svelte` | MODIFY | Zähler-Badge Etappen (N)/Orte (N) über vorhandenes `MTabBar.badge` |
| `frontend/src/lib/components/organisms/wetter-tab/VorlageKarte.svelte` | MODIFY | Texte/Gruppen nach Mockup Z. 508–512, 454–465 (ohne Mail-Kopf-Satz → #2796) |
| `frontend/src/lib/i18n/messages/{de,en}/*.json` | MODIFY | neue Schlüssel DE+EN (EN aus `elementliste.json`, Lücken #2968) |
| `docs/context/einstellungen_neu/elementliste_besitzer.json` | MODIFY | c2-Einträge entfernen; Profil/Tempo/Mail-Satz → `#2796` umhängen |
| Ausnahmen-Datei des Abgleichs | MODIFY | Name/Region-Bearbeiten-Texte mit Spec-Verweis |
| Tests: `hub_kopf_baustein.test.ts`, `hub_kopf_seiten_paritaet.test.ts`, `subscription_header_*`, `trip_header_status_profil.test.ts`, `compare_hub_fidelity.test.ts`, E2E `hub-kopf-aufbau`, `hub-kopf-paritaet-compare-trip` (Z. 398 „Senden“), `hub-kopf-bearbeiten` | MODIFY | mitziehen, nicht löschen |
| `docs/specs/modules/feat_2913_c2_seitenkopf.md` | CREATE | Spec mit ACs |

### Scope Assessment
- Files: ~10 Quelle + ~10 Tests; Estimated LoC: +350/-150; nur Frontend + Doku/Daten des Abgleichs
- Risk Level: LOW–MEDIUM (geteilter Kopf Trip+Vergleich, viele Tests binden an Kopf-Texte; keine Datenänderung)

### Technical Approach
Umbau der bestehenden geteilten Bausteine (ADR-0097/0110/0112), keine Neubauten, keine Schema-Änderung. Reihenfolge:
Kopf → Reiterleiste → Vorlage-Karte → Besitzerliste/Ausnahmen → Abgleich `--abnahme` DE+EN gegen Staging (Exit 0)
→ Soll/Ist-Bild an PO.

### Dependencies
MTabBar (`badge`), StatusSchild/Pill, Eyebrow, SubscriptionKebab; i18n-Katalog; Abgleich-Skripte (`npm run elementliste:abgleich`).
Downstream unverändert: `activity`/`profil` (Naismith, Vorlagen-Auflösung, Mail-Signatur) — bleibt #2796.

### Befunde gegen den Plan
- Abnahme nur gegen Staging prüfbar.
- Ziel „92 Einträge entfallen“ wird bewusst nur für den c2-Anteil erreicht; Rest sichtbar auf #2796/#2797 umgehängt.

### Open Questions
- keine PO-Fragen offen
