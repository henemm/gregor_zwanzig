# Context: feature-2913-scheibe-c

## Request Summary
Scheibe (c) aus dem Arbeitsplan von #2913 (Epic #2791): Im Reiter **Wetter** (Trip und Orts-Briefing, ein Code) die Abschnitte **„Nicht im Briefing“, Amtliche Warnungen, Radar-Regen und Anpassen (Tagesfenster)** lückenlos nach Mockup Fassung 3 aus Design-System-Bausteinen bauen (ADR-0112), alte Bausteine in derselben Scheibe löschen, auf Staging in DE/EN nachweisen.

Vorgänger: Schritt 1–2 (ADR-0112 + Wächter, PR #2918), Bausteine Teil 1/2 (`feat_2913_s3_bausteine`, PR #2929/#2930, live `f7d08f430`). Laut Issue-Kommentar vom 2026-11-11 stehen Scheiben (c)–(e) und die Elementliste DE/EN aus; Spec K-6/Known Limitations verschieben `AnpassenKarte` (roher Button) und `WarnungenRadarKarte` (roher Switch) ausdrücklich in Scheibe (c).

## Soll (Mockup `docs/context/einstellungen_neu/seiten/mockup-hub-fassung3.html`, `viewWetter()` ab Z.440)
1. **Metrik-Karte, letzte Zeile (Z.517) „Nicht im Briefing:“** — eine waagrechte Zeile `.more` (CSS Z.135): gedämpftes Label 12,5px, rechts daneben Chips `+ <Metrik>` (`.chip` Z.136, Pille 12,5px). Quelle der Chips: `removed` (Z.446, Katalog-Metriken mit `!on`) **und** `c.off` (Metriken außerhalb der Vorlage; Klick meldet „würde mit den Grenzen der Vorlage hinzugefügt“, Z.646).
2. **Karte Warnungen/Radar (Z.519–522)**, zwei `.lrow`-Zeilen (CSS Z.140–145), Titel + Hinweis + Schalter rechts:
   - „Amtliche Warnungen“ — „im Briefing und als Alarm, sobald sie dein Gebiet betreffen“, Schalter `sw('official')`.
   - „Radar-Regen“ — „Alarm, wenn in der nächsten Stunde Regen auf deine Etappe/deine Orte zukommt“; im Mockup bei **Trip und Orte** (Trip mit Notiz N1 = #2800).
   - Schalter `sw()` Z.355: `button role=switch aria-checked`, 36×20 (CSS Z.81–84, disabled Z.196), Logik Z.648.
3. (Dazwischen Z.523–532 „Inhalt je Kanal und Fläche“ — gehört zu S3b #2795 / Scheibe (d), nicht zu (c).)
4. **Letzte Karte „Anpassen“ (Z.534–536)**: Aufklapper `details.adv` mit „＋/－“ (CSS Z.164–167); Inhalt `.lrow` „Tagesfenster“, Hinweis „Welche Stunden bewertet werden“, zwei Uhrzeit-Eingaben `06:00` – `20:00` (aria-label von/bis).

## Related Files
| File | Relevance |
|------|-----------|
| `frontend/src/lib/components/shared/WetterTab.svelte` | Dünne Seite (SEITEN_SCOPE), reicht an `WetterTabInhalt` durch |
| `frontend/src/lib/components/organisms/wetter-tab/WetterTabInhalt.svelte` | Z.49 `MIT_RADAR = {route:false, vergleich:true}`; Z.170 `hinzufuegen`, Z.201–205 `nichtIm`, Z.274–287 Einbindung der drei Organismen |
| `organisms/wetter-tab/NichtImBriefing.svelte` | nutzt `ChipLeiste`; Titel über Chips (column, Z.35–41) statt in einer Zeile; `c.off` fehlt; Testids `wetter-nicht-im-briefing(-plus-<id>)`, `wetter-hinzugefuegt-meldung` |
| `organisms/wetter-tab/WarnungenRadarKarte.svelte` | Zeilen = `Einstellungszeile`, Schalter = **rohes** `<button role=switch>` (Z.21–25) mit eigenem CSS `.wt-switch/.wt-track/.wt-knopf`; Testids `wetter-warnungen-schalter`, `wetter-radar-schalter` |
| `organisms/wetter-tab/AnpassenKarte.svelte` | **roher** `<button>` als Aufklapper (Z.20–23, `aria-expanded`, Testids `wetter-anpassen-karte`/`-aufklappen`); Inhalt `shared/weather-metrics-tab/DayWindowCard.svelte` (Select-Atom, BESTAND) statt zwei Uhrzeit-Eingaben |
| `shared/wetter-tab/wetterZustand.ts:30–38` | Zustand `auswahl`, `warnungenAn`, `radarAn`, `tagesfenster{start,end}` |
| `shared/wetter-tab/ampelSchreiben.ts` | Speichern: Trip Z.119–135 (`official_alerts_enabled`, `official_warnings`, `report_config.day_window_*_hour`; Metriken über `/weather-config`, Z.56–72), Vergleich Z.157–168 (+`radar_alert_enabled`, `day_window_*` top-level) |
| `shared/wetter-tab/amtlicheWarnungen.ts:4–36` | ODER-Lese-Regel, Doppelschreiben |
| `atoms/Switch.svelte` | `role=switch`, `aria-checked`, `onchange` vorhanden; **`data-testid="switch"` fest verdrahtet (Z.73), keine Attribut-Durchreichung**; Größen sm/md/lg (lg 44×26) — Mockup 36×20 |
| `molecules/Einstellungszeile.svelte`, `molecules/ChipLeiste.svelte`, `molecules/UhrzeitFeld.svelte` | passende vorhandene Moleküle |
| `frontend/src/lib/__tests__/bausteine_waechter_regeln.ts` | `SEITEN_SCOPE` Z.504–507, `FREIGEGEBENE_KOMPOSITIONEN` Z.510, `BESTAND` ab Z.513 (Obergrenze 204, Z.721), `AUSNAHMEN` Z.724–765 |
| `frontend/src/lib/__tests__/bausteine_waechter{,_wirkort}.test.ts` | Wächter (node --test) |
| `claude-code-handoff/current/jsx/atoms.jsx` | `Switch` Z.211, `Btn` Z.126, `SectionH` Z.396; **kein Aufklapper** im Handoff |

## Existing Patterns
- Organismen werden aus Atomen/Molekülen gebaut; rohe Controls sind in Bausteinen formal erlaubt (Regel b prüft nur Tokens), aber K-6 verlangt den Umbau für diese Scheibe.
- Atom-Erweiterungen in Teil 2 (Input `ampel`, Segmented `farbe`) als optionale Props, rückwärtskompatibel; dasselbe Muster für `Switch` (testid/aria-Durchreichung, Größe 36×20) und einen neuen Aufklapper.
- Trip/Orte teilen alles über `context="route"|"vergleich"` (ADR-0097, #1170); keine Compare-eigene Komponente.
- Prüf-Anker bleiben stabil (K-7): `wetter-warnungen-schalter`, `wetter-radar-schalter`, `wetter-anpassen-*`, `wetter-nicht-im-briefing*`.

## Dependencies
- Upstream: Atome `Switch`, `Btn`, `Input`; Moleküle `Einstellungszeile`, `ChipLeiste`, `UhrzeitFeld`; i18n `frontend/src/lib/i18n/messages/{de,en}/wetter.json` (`wetter.warnungen.*`, `wetter.radar.*`, `wetter.radar.deine_orte`); Logik-Module `shared/wetter-tab/*.ts`.
- Downstream: Hub und Anlege-Kette Trip (`TripTabs`/`TripNewEditor`) und Orts-Briefing (`CompareTabs`/`CompareNewEditor`); Backend-Felder Go `internal/model/trip.go` (Z.139/143/149, Struct Z.201–204), `internal/model/compare_preset.go` (Z.53/60/86/90/151), `internal/handler/trip.go` Z.291–295; Python `src/app/trip.py` Z.209–214, `src/app/models.py` Z.444–445/1189–1190, `src/services/compare_radar_alert.py`.
- Weitere Nutzer des `Switch`-Atoms (Änderung muss rückwärtskompatibel sein; in Phase 2 per Grep aufzählen).

## Existing Specs
- `docs/specs/modules/feat_2913_s3_bausteine.md` — K-6, K-7, Known Limitations Z.264/272, Z.68 (Aufklapper `details.adv` als Baustein der Scheiben c–e)
- `docs/specs/modules/feat_2794_s3a_teil3_wetter.md` — fachliche Quelle der vier Abschnitte (Datenfluss, AC-20 Warn-Lese-Regel, Radar nur Vergleich bis S8)
- `docs/specs/modules/feat_2794_s3a_reiter_wetter.md` — Gesamt-Spec Reiter Wetter
- `docs/specs/modules/einstellungen_neu_neustart_adr_waechter_elementliste.md` — Wächter + Elementliste
- ADR-0112, ADR-0111, ADR-0097, ADR-0095, ADR-0096

## Tests
- Unit: `frontend/src/lib/components/organisms/__tests__/wetter_tab_{bausteine,anker_tap,barrel,i18n,ort}.test.ts`, `shared/__tests__/s3a2794_teil3_*`.
- Staging: `frontend/playwright.2794-s3a3.staging.config.ts` (seriell, Setup `fix-1895-modus-rueckbau.staging.setup.ts`); relevant `frontend/e2e/s3a2794-teil3-{karten,nicht-im-briefing,design,englisch,dialog}.spec.ts`, Helfer `s3a2794-teil3.helpers.ts`.
- Elementliste aus dem Mockup (Schritt 2 von #2913) und unabhängiger Prüf-Agent `mockup-bildpruefer` (ADR-0112, max. zwei Runden je Scheibe).

## Risks & Considerations
- **Radar-Regen beim Trip:** Mockup zeigt die Zeile auch für Trips, die Fachlogik dafür ist S8 (#2800, noch offen: Datenfeld am Trip, Etappen-Orte zur Uhrzeit, Nowcast-Begrenzung, Kanal-Zustellung, Mail-Validator). Ein Schalter ohne Wirkung wäre irreführend. Abgrenzung in Phase 2 klären: Scheibe (c) baut die Zeile als Baustein, für Trips bleibt sie aus, bis #2800 liefert — oder #2800 wird in diese Scheibe gezogen (Produktumfang deutlich größer, Backend + Alarm-Pfad).
- **`c.off` in „Nicht im Briefing“** (Metriken außerhalb der Vorlage, Hinweis „würde mit den Grenzen der Vorlage hinzugefügt“) fehlt heute — prüfen, ob `ampelModell.ts` die Vorlagen-Grenzen für solche Metriken liefert.
- **Tagesfenster:** Mockup zwei Uhrzeit-Eingaben (`HH:MM`), Datenmodell speichert ganze Stunden (`day_window_*_hour`). UhrzeitFeld muss auf Stundenraster begrenzt werden, sonst Datenverlust/Rundung. `DayWindowCard` (BESTAND) danach löschen, falls keine weiteren Nutzer — BESTAND-Ratsche senken.
- **Switch-Atom:** Erweiterung um testid/Attribut-Durchreichung und Größe 36×20 darf bestehende Nutzer (fester testid `switch`) nicht brechen.
- **Neuer Aufklapper-Baustein** fehlt im Handoff; muss einmal im System (Molekül) entstehen und wird in Scheiben (d)/(e) wiederverwendet.
- Staging-Nachweis mit zwei Nutzern (Warn-/Radar-/Tagesfenster-Speichern ist datenbewegend), DE und EN, Trip und Orts-Briefing; Read-Modify-Write beim Speichern unverändert lassen (#102).
- Keine Logikänderung an Renderer/Alarm-Engine in dieser Scheibe (außer falls #2800 einbezogen wird).

## Analysis

### Type
Feature (Oberflächen-Scheibe nach ADR-0112, kein Backend, keine Fachlogik-Änderung)

### Befunde aus der Untersuchung (2026-11-11)
- **Switch-Atom** (`atoms/Switch.svelte`): Größe `md` ist bereits 36×20 (= Mockup), `role=switch` + `aria-checked` + `onchange` vorhanden. Es fehlt nur die Testid-Durchreichung (fest `data-testid="switch"`, Z.73) und eine Tapfläche ≥ 44 px (Element ist 20 px hoch). Kein Test/E2E fragt `data-testid="switch"` ab; einziger Bezug `frontend/src/app.css:880-881`. Nutzer: `AlertChannelPicker`, `ChannelRow`, `BriefingScheduleRow`, `WeatherV2Kanaele`, `KontoSheet`, `_design-system`-Seite → Erweiterung als optionale Props rückwärtskompatibel.
- **Aufklapper:** kein Disclosure-Baustein in `atoms/`/`molecules/` → neues Molekül nötig (wird in Scheiben d/e wiederverwendet).
- **Tagesfenster:** `DayWindowCard` (Select, Stunden 0–23, Über-Mitternacht erlaubt, Ende ≠ Start via `versand-tab/dayWindowClamp.ts`, Hinweis `day-window-wrap-hint`). `UhrzeitFeld` hat Stunde+Minute, kein Stundenraster-Modus; einziger Nutzer `edit/StageTimeField.svelte`. `DayWindowCard` wird außer von `AnpassenKarte` nur noch vom nicht mehr gerenderten `WeatherMetricsTab` importiert (TripTabs/TripNewEditor rendern `WetterTab`, Erwähnungen nur in Kommentaren) → Löschen von `DayWindowCard` hängt am Rückbau von `WeatherMetricsTab` (nicht Teil dieser Scheibe).
- **E2E mit Select-Bedienung des Tagesfensters** (müssen migriert werden): `frontend/e2e/speicherung-ueberlebt-neuladen.spec.ts:517-543`, `daywindow-shared-both-contexts.spec.ts:98-177`, `daywindow-schedule-control.spec.ts:95-173`; Helfer-Map `s3a2794-teil3.helpers.ts:62-71` (tagVon/tagBis). Unit: `shared/weather-metrics-tab/__tests__/day_window_card.test.ts`, `wertebereiche_sprache.test.ts:301`.
- **Prüf-Anker in Nutzung:** `wetter-warnungen-schalter` (Klick in `issue-1117-official-alerts-content-tab.spec.ts:78`, `hub-konfliktschutz-zwei-kontexte.spec.ts:274`), `wetter-radar-schalter` (`f005_radar_nur_vergleich.test.ts:158-160`), `wetter-nicht-im-briefing-plus-<id>` (mehrere E2E + `wetter_tab_anker_tap.test.ts:209` `data-size="tap"`), `wetter-anpassen-aufklappen`.
- **`c.off` im Mockup** (`mockup-hub-fassung3.html:295/307/517/646`): feste Namensliste, Klick zeigt nur „würde mit den Grenzen der Vorlage hinzugefügt (Mockup)“, nichts wird gespeichert. Die App führt bereits **alle** gruppierten Katalog-Metriken, die nicht gewählt sind, in einer Chip-Liste (`WetterTabInhalt.svelte:201-205`) — das deckt `removed` und `off` zusammen ab. Metriken ohne Vorlagenzeile bekommen offene Grenzen und `alarm_ab: never` (`ampelModell.ts:51`, Spiegel `src/app/ampel.py:159-173`); Vorlagen-Grenzen für Fremd-Metriken gibt es nicht.
- **Radar beim Trip:** kein `radar_alert_enabled` am Trip (Go/Python), Issue #2800 (S8) offen; Spec `feat_2794_s3a_teil3_wetter.md` AC-21 und Known Limitation Z.295: Trip zeigt die Zeile nicht bis S8. Mockup-Text „deine Etappe“ gehört zu #2800.
- **i18n:** vorhanden `wetter.nicht_im_briefing.*`, `wetter.warnungen.*`, `wetter.radar.*` (`deine_orte`), `wetter.anpassen.{titel,tagesfenster,von,bis}`. Fehlt: Hinweis „Welche Stunden bewertet werden“ (Elementliste Z.180 `luecke: true`) und der Über-Mitternacht-Hinweis im `wetter`-Namensraum (heute `wertebereiche.tagesfenster.ueber_mitternacht`).

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `frontend/src/lib/components/atoms/Switch.svelte` | MODIFY | optionale Props `testid` (Default `switch`) und Tapfläche ≥ 44 px (unsichtbare Trefferfläche), rückwärtskompatibel |
| `frontend/src/lib/components/molecules/Aufklapper.svelte` | CREATE | `details`/`summary`, Titel + „＋/－“ (Mockup `.adv`, CSS Z.164–167), `aria-expanded` gespiegelt, Testids durchgereicht, Inhalt als Snippet |
| `frontend/src/lib/components/molecules/UhrzeitFeld.svelte` | MODIFY | optionaler Stundenraster-Modus (Minute fest `00`, nicht editierbar; Wert `HH:00`) |
| `frontend/src/lib/components/molecules/index.ts` | MODIFY | Export `Aufklapper` |
| `frontend/src/lib/components/organisms/wetter-tab/WarnungenRadarKarte.svelte` | MODIFY | roher Schalter + `.wt-switch/.wt-track/.wt-knopf`-CSS weg → `Switch` (md, Testids erhalten) |
| `frontend/src/lib/components/organisms/wetter-tab/AnpassenKarte.svelte` | MODIFY | roher Button weg → `Aufklapper`; Inhalt `Einstellungszeile` „Tagesfenster“ + Hinweis + zwei `UhrzeitFeld` (Stundenraster), Clamp über `dayWindowClamp.ts`, Über-Mitternacht-Hinweis; kein Import von `DayWindowCard` mehr |
| `frontend/src/lib/components/organisms/wetter-tab/NichtImBriefing.svelte` | MODIFY | eine waagrechte Zeile (Label links, Chips daneben, umbrechend, Mockup `.more` Z.135) |
| `frontend/src/lib/i18n/messages/{de,en}/wetter.json` | MODIFY | `wetter.anpassen.hinweis` („Welche Stunden bewertet werden“ / EN), Über-Mitternacht-Hinweis im `wetter`-Namensraum |
| `frontend/src/lib/__tests__/bausteine_waechter_regeln.ts` | MODIFY | neues Molekül ist regelkonform; keine BESTAND-Senkung (DayWindowCard bleibt bis WeatherMetricsTab-Rückbau) |
| `frontend/src/lib/components/organisms/__tests__/wetter_tab_*.test.ts`, `molecules/__tests__/*` | CREATE/MODIFY | RED-Tests: keine rohen Controls in den drei Organismen, Switch-Testid, Aufklapper, Stundenraster, Clamp |
| `frontend/e2e/{speicherung-ueberlebt-neuladen,daywindow-shared-both-contexts,daywindow-schedule-control}.spec.ts`, `s3a2794-teil3.helpers.ts` | MODIFY | Tagesfenster-Bedienung von Select auf Uhrzeitfeld umstellen |

### Scope Assessment
- Files: ~14 (davon ~5 Produktivcode, Rest Tests/E2E/i18n)
- Estimated LoC: +350/-180 (Produktivcode ca. +200/-120)
- Risk Level: MEDIUM — reine Oberfläche, aber datenbewegend (Warnungen, Radar, Tagesfenster werden gespeichert) und drei bestehende E2E-Abläufe müssen auf die neue Bedienung umziehen.

### Technical Approach
1. **Atom/Molekül zuerst** (rückwärtskompatibel, Muster aus Teil 2): `Switch` bekommt `testid` + Tapfläche; neues Molekül `Aufklapper`; `UhrzeitFeld` bekommt einen Stundenraster-Modus. Bestehende Nutzer unverändert.
2. **Organismen umbauen:** `WarnungenRadarKarte` → `Einstellungszeile` + `Switch`; `AnpassenKarte` → `Aufklapper` + `Einstellungszeile` + zwei `UhrzeitFeld`; `NichtImBriefing` → einzeilig. Alle rohen Controls und das zugehörige Eigen-CSS in derselben Scheibe löschen (ADR-0112).
3. **Fachlogik unverändert:** Speichern über `ampelSchreiben.ts`/`wetterZustand.ts` bleibt (Read-Modify-Write, #102); Tagesfenster weiter ganze Stunden, Über-Mitternacht erlaubt, Ende ≠ Start (`clampDayWindowEndHour`, ADR-0035, PO-Entscheidung #1361/#1372).
4. **Abgrenzungen (Tech-Lead-Entscheidungen, keine PO-Frage nötig, weil frühere Entscheidungen gelten):**
   - Radar-Zeile beim Trip bleibt aus, bis #2800 (S8) liefert — Spec AC-21 + Known Limitation; ein Schalter ohne Wirkung wäre irreführend.
   - `c.off` wird nicht als Attrappe nachgebaut: die App zeigt bereits alle nicht gewählten Katalog-Metriken als Chips; die Mockup-Meldung „mit den Grenzen der Vorlage“ beschreibt eine Funktion, die es nicht gibt (Fremd-Metriken bekommen offene Grenzen). Known Limitation in der Spec.
   - `DayWindowCard` bleibt bestehen, solange `WeatherMetricsTab` existiert (wird nicht mehr gerendert); dessen Rückbau ist eigene Arbeit → Nebenbefund-Issue.
5. **Nachweis:** Unit-RED (node --test) → Staging-E2E DE/EN, Trip und Orts-Briefing, zwei Nutzer für Speichern; Elementliste-Abgleich für die vier Abschnitte; `mockup-bildpruefer` (max. zwei Runden).

### Dependencies
- Upstream: `atoms/Switch`, `molecules/{Einstellungszeile,ChipLeiste,UhrzeitFeld}`, `versand-tab/dayWindowClamp.ts`, i18n `wetter.json`.
- Downstream: alle Switch-Nutzer (`AlertChannelPicker`, `ChannelRow`, `BriefingScheduleRow`, `WeatherV2Kanaele`, `KontoSheet`, Design-System-Seite), `StageTimeField` (UhrzeitFeld), `WetterTabInhalt` (bindet die drei Organismen ein), Hub + Anlege-Kette Trip/Orts-Briefing.

### Open Questions
- keine offene Produktfrage (Radar-Trip und `c.off` durch frühere Entscheidungen/Specs geklärt, siehe Technical Approach 4).
