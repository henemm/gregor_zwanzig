# Context: fix-3193-vorlage-abweichung-minimal

Issue #3193 (Kommentar 20.11.2026), Epic #2913 (Reiter Wetter). Workflow `fix-3193-vorlage-abweichung-minimal`.
Stand der Analyse: Worktree-HEAD 9836e0819; `origin/main` 92b752fa6 ist Nachfolger, in den betroffenen Dateien
(`frontend/src/lib/components/shared/wetter-tab/`, `organisms/wetter-tab/`, `frontend/e2e/s3a2794-teil3-vorlage.spec.ts`) ohne Unterschied.

## Request Summary

Auf Staging sind in `frontend/e2e/s3a2794-teil3-vorlage.spec.ts` AC-11/AC-13 (Vorlagenwechsel „Übernehmen“) und
AC-12/AC-28 („Auf ‚Vorlage‘ zurücksetzen“) für Trip und Orts-Vergleich rot. Nach Wechsel/Zurücksetzen speichert der
Reiter eine nicht leere `display_config.ampel.metrics` (Trip: abgeleitete Kinder `enabled:true`; Vergleich:
`temperature_night: {enabled:false}`), im Vergleich zeigt der Picker „1 Abweichung“ statt „unverändert“ und der
Zurücksetzen-Knopf bleibt dauerhaft stehen (Klick wirkungslos). Ursache: Zähler, Abweichungsmenge und Speicherweg
messen gegen **verschiedene Vergleichsbasen**. Ziel: eine einheitliche Basis „Vorlage im Kontext“.

## Related Files

| Datei | Rolle |
|---|---|
| `frontend/src/lib/components/shared/wetter-tab/wetterZustand.ts` | Bearbeitungsstand: `nurAusgebbar` (:83), `mengeVon` (:115-117), `vorlageImKontext` (:121-126, privat), `abweichungenVon` (:130-138), `mitVorlage` (:142-146), `mitEigenerVorlage` (:149-155) |
| `frontend/src/lib/components/shared/wetter-tab/wetterTabSpeicherung.ts` | Speicherweg: `tripNutzlast` (:70 `vorlage: v[s.vorlageId]`), `vergleichNutzlast` (:88 `vorlage: o.vorlagen()[s.vorlageId]`) |
| `frontend/src/lib/components/shared/wetter-tab/ampelSchreiben.ts` | `abweichungsMenge` (:39-56, minimale Menge gegen die übergebene Basis), `tripSpeicherPayload` (:149), `vergleichSpeicherPayload` (:208), `tripMetriken`/`kinderAusdruecklich` (:67-97) |
| `frontend/src/lib/components/shared/wetter-tab/ampelModell.ts` | `AUSWAHL_ABLEITUNG` (:453), `auswahlMitAbgeleiteten` (:440), `ausgebbarTeilen`/`ANGEBOTS_FILTER` (:365, :519), `vergleichsKatalogIds` (:468), `zuruecksetzen` (:542), `zaehleAbweichungenGegen` (:149) |
| `frontend/src/lib/components/organisms/wetter-tab/WetterTabInhalt.svelte` | Verdrahtung: `signatur` (:109, `mengeVon`), `abweichungen` (:217, `abweichungenVon`), `anzeigeMenge` (:218, `mengeVon` → „Abweichend von der Vorlage“-Satz je Zeile), `aboAmpel` (:229, `verschmelzen(roh, mengeVon)` → Dialog „Als eigene Vorlage speichern“), `onUebernehmen`/`onZuruecksetzen` (:270/:272) |
| `frontend/src/lib/components/trip-detail/metricsEditor.ts` | `DERIVED_METRIC_RULES` (:316): `temperature` → `temperature_night`, `temperature_day_low/high`; `wind_chill` → `wind_chill_night`, `wind_chill_day_low/high` |
| `src/app/ampel_templates.py` | Systemvorlagen (SSOT, `/api/templates`); alle außer „allgemein“ schalten `temperature_night` ein, keine schaltet `temperature_day_*`/`wind_chill_*` ein |
| `src/output/renderers/compare_metric_catalog.py` | Vergleichs-Katalog (`/api/compare/metrics`); enthält `temperature_night` **nicht** |
| `frontend/e2e/s3a2794-teil3-vorlage.spec.ts` | rote E2E-Fälle (Z. 96/101/103, 145/150/151) |
| `frontend/e2e/s3a2794-teil3.helpers.ts` | `seedWetter` (:136), `aktiveDerVorlage` (:129), `abgeleiteteKinder` (:126), `auswahlImStand` (:178) |
| `frontend/src/lib/components/shared/wetter-tab/__tests__/p15_abweichung_abgeleitete_kinder.test.ts` | Kern-Test des Zählers (Trip: Kinder keine Abweichung; Vergleich: nur Laden + „−“, kein Zurücksetzen) |
| `frontend/src/lib/components/shared/wetter-tab/__tests__/ac26_einstellung_gleich_ausgabe.test.ts` | E6-Tests (:226-255): Vergleich-Vorlage nur ausgebbare Größen; gesperrter Bestandseintrag bleibt erhalten |
| `frontend/src/lib/components/shared/wetter-tab/__tests__/ampelSchreiben.test.ts` | `ac12_zuruecksetzen_schreibt_null_abweichungen` (:370) — misst nur gegen die rohe Vorlage, ohne Kontext |

## Existing Patterns

- **Kontext als Daten-Tabelle, nicht als Weiche** (`AUSWAHL_ABLEITUNG`, `ANGEBOTS_FILTER`, `AUSWAHL_QUELLE`, `MAIL_STANDARD`; Ratsche `context_herkunft_zweige_eingefroren`). Eine kontextabhängige Basis gehört ebenso in eine Tabelle `Record<Kontext, …>`.
- **`vorlageImKontext`** existiert bereits (p15, f8e918b57) und wird nur vom Zähler benutzt — das ist der Kern der Diskrepanz.
- **Minimale, vollständige Abweichungsmenge** (`abweichungsMenge`): `ampel` wird vom Server als Ganzes ersetzt; Felder nur bei Abweichung.
- **Kern-Tests im echten Instanz-Skript** von `WetterTabInhalt.svelte` (Prüfstand `svelteInstanzPruefstand.ts`, Daten aus echten Python-Funktionen, `wetterTabDaten.ts`); kein Mock.

## Dependencies

- Upstream: `/api/templates` (Python `AMPEL_TEMPLATES`), `/api/compare/metrics` (Python-Katalog → `altSchluessel`, `katalogIds` im Reiter), `/api/metrics`.
- Downstream des gespeicherten `ampel`: Python `verschmelzen`/Ampel-Auswertung nutzt aus `ampel.metrics.<id>` nur Grenzen und `alarm_ab` — `enabled` steuert **nicht** die Ausgabe (Auswahl kommt aus `metrics[]`/`active_metrics`). `deviation_count` (Python) und `zaehleAbweichungen` (Frontend) werden produktiv nirgends angezeigt (nur Paritätstests). Alarme-Reiter (`AlertMetricLevelTable` via `alarmAbAnzeige.ts`) liest nur `alarm_ab`. Hub-Übersicht zählt Metriken/Alarme über `standAusAbo`, keine Abweichungen.
- Frontend-intern: `aboAmpel` → Dialog „Als eigene Vorlage speichern“ (gespeicherte Ampel der eigenen Vorlage); `mitEigenerVorlage` leitet beim Anwenden die Auswahl wieder über `AUSWAHL_ABLEITUNG`/`nurAusgebbar` ab.

## Existing Specs/ADRs

- `docs/specs/modules/feat_2794_s3a_teil3_wetter.md`: §Datenfluss Z. 130 („`display_config.ampel` (nur Abweichungen)“), Z. 144/149 (Tech-Lead-Entscheidung: `ampel.metrics.<id>.enabled` **als minimale Abweichung von der Vorlage**; „Vorlagenwechsel und Zurücksetzen setzen die Auswahl aus den Vorlagen-`enabled`-Werten **und leeren die Abweichungen**“), Z. 208 (Test-Hinweis „Zurücksetzen liefert Abweichungsmenge null“), AC-11/AC-12/AC-13/AC-28 (Z. 204-238). ⇒ Die Testerwartung `ampel.metrics == {}` ist fachlich die freigegebene Regel, nicht veraltet.
- `docs/specs/modules/feat_3047_einstellung_gleich_mail_pruefkatalog.md`, Nachtrag Runde 7 (Z. 304 ff.) mit Befunden `docs/artifacts/feat-3047/runde7_befunde.md`: **E6** (Orte: Vorlagen-Auswahl nur ausgebbare Größen, gespeicherte nicht ausgebbare stehen gesperrt) und **E7/p5c** (Trip: Kinder wie Python abgeleitet, beim Schreiben ausdrücklich aus, wenn abgewählt). Eingeführt ff9d4f44d / d3b18daa2; f8e918b57 (p15) stellte nur den Zähler auf `vorlageImKontext` um.
- `docs/specs/modules/feat_3111_wetter_dialoge_mockup.md` AC-6 (Verlust-Satz „Deine N Abweichungen …“ — Zahl kommt aus demselben `abweichungen`).
- ADR-0095 (Kanal-Parität) nicht berührt: `enabled` in `ampel` ändert keine Ausgabe.

## Risks

- **Bestandsdaten mit Rausch-Einträgen** (bereits gespeichert seit d3b18daa2): Trip `{temperature_day_low/high, wind_chill_*: {enabled:true}}`, Vergleich `{temperature_night: {enabled:false}}`. Mit der einheitlichen Basis zählen sie als 0 Abweichungen (lokal nachgestellt, s. Analysis) und verschwinden beim nächsten Speichern von selbst. Keine Migration nötig; die Einträge sind informationsleer (gleich der Ableitung bzw. nicht ausgebbar). Der Laden-Pfad löst kein Speichern aus (`gemeldet = signatur(stand)`), es wird also nichts ohne Nutzeraktion umgeschrieben.
- **Vergleichsbasis falsch eingeschränkt**: würde man im Vergleich die nicht ausgebbaren Vorlagen-Metriken einfach auf `enabled:false` setzen, zeigte ein Bestands-Orts-Briefing mit `temperature_night` in `active_metrics` (E6: bleibt gesperrt erhalten; so seedet auch die E2E-Spec) beim Laden „1 Abweichung“ — bricht AC-10 und p15 `vergleich_nach_vorlage_wandern_null_abweichungen`. Die Basis muss nicht ausgebbare Größen **neutral** behandeln (s. Technical Approach).
- **`aboAmpel` für eigene Vorlagen**: bleibt `verschmelzen(roh, menge)`, enthält nach dem Fix die Kinder nicht mehr ausdrücklich (`enabled` aus der Rohvorlage). Unkritisch, weil `mitEigenerVorlage` sie über `AUSWAHL_ABLEITUNG` wieder ableitet; zu prüfen bzw. konsequent auf dieselbe Basis umstellen.
- **Trip/Vergleich-Code-Teilung (Gate)**: Fix muss in der geteilten Datei als Kontext-Tabelle erfolgen, keine Pendant-Funktion.

## Analysis

### Type: Bug

Echter Produktfehler (nicht veraltete Spec) für die `ampel`-Menge und den Vergleichs-Zähler; zusätzlich sind zwei Auswahl-Erwartungen der E2E-Spec durch E6/E7 überholt (s. Befunde gegen den Plan).

### Root Cause

Drei Stellen vergleichen den Stand mit drei verschiedenen Basen:

| Stelle | Basis | Datei:Zeile |
|---|---|---|
| Zähler (Picker, Verlust-Satz AC-11, Knopf AC-12) | `vorlageImKontext(context, roh)` — Trip: Rohvorlage + abgeleitete Kinder an; Vergleich: Rohvorlage | `wetterZustand.ts:130-137` |
| Menge (Signatur, „Abweichend“-Satz, `aboAmpel`) | Rohvorlage | `wetterZustand.ts:115-117` |
| Speichern | Rohvorlage | `wetterTabSpeicherung.ts:70` (Trip), `:88` (Vergleich) → `ampelSchreiben.ts:149/:208` → `abweichungsMenge` `:39` |

Die Auswahl dagegen wird bei Wechsel/Zurücksetzen kontextbezogen gebildet: `mitVorlage` `wetterZustand.ts:145` = `nurAusgebbar(context, AUSWAHL_ABLEITUNG[context](vorlage.enabled))`.

- **Trip (route):** `AUSWAHL_ABLEITUNG.route` (`ampelModell.ts:453` → `auswahlMitAbgeleiteten`) fügt `temperature_day_low/high` (und bei Vorlagen mit `wind_chill` auch `wind_chill_night/_day_low/_day_high`) zur Auswahl hinzu. `abweichungsMenge(roh, …)` sieht diese Kinder als „hinzugefügt“ (`ampelSchreiben.ts:30`, Rohvorlage `enabled:false`/keine Zeile) und schreibt sie als `{enabled:true}`. Der Zähler misst gegen `vorlageImKontext` und zeigt 0. Lokal nachgestellt: nach Zurücksetzen auf Alpen-Trekking Zähler 0, gespeichert `{temperature_day_low, temperature_day_high, wind_chill_night, wind_chill_day_low, wind_chill_day_high: {enabled:true}}`; nach Wechsel auf Wandern `{temperature_day_low, temperature_day_high: {enabled:true}}` (= Staging-Befund). Bemerkung: Schon beim bloßen Laden eines Trips „nach Vorlage“ liefert `mengeVon` diese fünf Einträge; sie werden beim nächsten beliebigen Speichern (z. B. eine Alarmstufe) mitgeschrieben.
- **Orts-Vergleich (vergleich), jetzt belegt:** `temperature_night` ist in allen Systemvorlagen außer „allgemein“ eingeschaltet, steht aber nicht im Vergleichs-Katalog. `nurAusgebbar` (`wetterZustand.ts:83-86`, via `ausgebbarTeilen`/`ANGEBOTS_FILTER.vergleich`, `ampelModell.ts:365/:519`) nimmt es bei `mitVorlage` aus der Auswahl. `vorlageImKontext('vergleich')` (`wetterZustand.ts:121-126`) lässt die Rohvorlage unverändert (`temperature_night.enabled:true`), also ist das Fehlen in der Auswahl für **Zähler und Menge** eine Abweichung `{enabled:false}`. Lokal nachgestellt: Zurücksetzen → Zähler 1, gespeichert `{temperature_night:{enabled:false}}`; Wechsel auf Wandern → Zähler 1, gleiche Menge; neu geladen bleibt der Zähler 1 → Zurücksetzen-Knopf steht dauerhaft, Klick ändert nichts (Endlosschleife für den Nutzer).

Wegwerf-Nachstellung: `/tmp/claude-1000/-home-hem-gregor-zwanzig/7a8960eb-7126-4b2a-86ef-33b398712053/scratchpad/repro.ts` (Ist), `…/variante.ts` (Fix-Variante), Daten aus den echten Python-Funktionen (`…/dump.py` → `daten.json`); Lauf: `cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types <skript> <daten.json>`.

### Affected Files (with changes)

| Datei | Änderung |
|---|---|
| `frontend/src/lib/components/shared/wetter-tab/wetterZustand.ts` | `vorlageImKontext` zur **einen** exportierten Basis machen (Signatur erweitert um Auswahl + Katalog-IDs bzw. `alt`), Kontext-Tabelle `BASIS_IM_KONTEXT: Record<Kontext, …>`; `mengeVon(s, vorlagen, context, alt)` und `abweichungenVon` messen beide dagegen (Zähler = `zaehleAbweichungenGegen(basis, mengeVon(...))`) |
| `frontend/src/lib/components/shared/wetter-tab/wetterTabSpeicherung.ts` | `tripNutzlast`/`vergleichNutzlast`: `vorlage:` = Basis im Kontext statt `v[s.vorlageId]` (`:70`, `:88`) |
| `frontend/src/lib/components/organisms/wetter-tab/WetterTabInhalt.svelte` | Aufrufe `mengeVon` (`:109`, `:218`, `:229`) mit `context`/`altSchluessel`; `aboAmpel` auf `verschmelzen(basis, menge)` oder bewusst Rohvorlage (s. Risks) |
| `frontend/src/lib/components/shared/wetter-tab/__tests__/` | neuer Kern-Test (RED) im Instanz-Prüfstand: Zurücksetzen/Wechsel → gespeicherte Nutzlast `ampel` ohne `metrics`, beide Kontexte, Zähler 0; Vergleich zusätzlich Bestand mit gesperrtem `temperature_night` lädt mit 0; Altbestand mit Rausch-Einträgen zählt 0 |
| `frontend/e2e/s3a2794-teil3-vorlage.spec.ts` | Auswahl-Erwartungen Z. 103/151 an E6/E7 angleichen (s. Befunde) |

`ampelSchreiben.ts` (`abweichungsMenge`) bleibt unverändert — sie rechnet korrekt gegen die übergebene Basis.

### Scope Assessment

Frontend-only, 3 Quelldateien + 1 Kern-Test + 1 E2E-Spec, geschätzt ≤ 60 LoC Produktcode. Keine API-/Python-/Go-Änderung, kein Schema, keine Migration.

### Technical Approach

Eine einheitliche Vergleichsbasis „Vorlage im Kontext“ für Zähler, Menge und Speichern:

- **route:** wie heute `vorlageImKontext`: Rohvorlage, dazu jedes abgeleitete Kind eines aktiven Elters `enabled:true` (`AUSWAHL_ABLEITUNG.route`). Ein bewusstes „−“ an einem Kind bleibt Abweichung `{enabled:false}` (geprüft).
- **vergleich:** Rohvorlage, nicht ausgebbare Größen (`!katalogIds.has(id)`) **neutral**: ihr `enabled` in der Basis folgt der aktuellen Auswahl, d. h. weder Weglassen (E6-Filter bei Wechsel/Zurücksetzen) noch ein gesperrt erhaltener Bestandseintrag zählt als Abweichung. Grenzen/`alarm_ab` dieser Zeilen werden weiter verglichen. Ohne bekannten Katalog (Ladefehler) bleibt die Basis die Rohvorlage, analog `nurAusgebbar`.
- Umsetzung als Kontext-Tabelle in `wetterZustand.ts`, exportiert; `mengeVon`, `abweichungenVon`, `tripNutzlast`, `vergleichNutzlast` nutzen ausschließlich sie. Der Zähler zählt die Menge, die gespeichert wird (eine Rechnung statt zwei).

Lokal mit den echten Vorlagen/Katalog nachgerechnet (`variante.ts`): Laden (Seed inkl. `temperature_night`) 0 / `{}`; Zurücksetzen 0 / `{}`; Wechsel Wandern 0 / `{}`; „−“ Böen 1 / `{gust:{enabled:false}}`; Trip „−“ `temperature_day_low` 1; Altbestand mit Rausch-Einträgen lädt mit 0 (heute im Vergleich 1) — beide Kontexte.

### Befunde gegen den Plan

1. **E2E-Auswahl-Erwartung Trip veraltet (E7/p5c):** `tripMetriken`/`kinderAusdruecklich` (`ampelSchreiben.ts:67-97`) schreibt die gewählten abgeleiteten Kinder seit p5c ausdrücklich in `metrics[]` (Tech-Lead-Entscheidung, Ausgabe gleich). `auswahlImStand('route', …)` enthält sie deshalb; Z. 103/151 erwarten nur `aktiveDerVorlage` → bleibt nach dem `ampel`-Fix rot. Angleichen mit dem vorhandenen Helfer: `[...aktiveDerVorlage(v), ...abgeleiteteKinder(kind, aktiveDerVorlage(v))]` (Menge, sortiert).
2. **E2E-Auswahl-Erwartung Vergleich veraltet (E6):** Nach Wechsel/Zurücksetzen fehlt `temperature_night` in `active_metrics` gewollt; Z. 103/151 erwarten es. Angleichen: Vorlagen-Aktive geschnitten mit `/api/compare/metrics`-`metric_id`s. Im Vergleich scheitert der Lauf heute schon vorher an Z. 96/145 („1 Abweichung“).
3. Die Erwartung `ampel.metrics == {}` (Z. 101/150) ist **richtig** (feat_2794 Z. 144/149/208, Tech-Lead-Entscheidung „minimale Abweichung“, „leeren die Abweichungen“).
4. `ampelSchreiben.test.ts:370` (`ac12_zuruecksetzen_schreibt_null_abweichungen`) misst nur gegen die Rohvorlage mit Rohauswahl und konnte den Fehler deshalb nicht fangen; der neue Kern-Test muss über `mitVorlage` + `tripNutzlast`/`vergleichNutzlast` gehen (wo es wirkt).
5. Kein weiterer Abweichungszähler betroffen: Hub-Übersicht zählt keine Abweichungen, `zaehleAbweichungen`/`deviation_count` sind produktiv ungenutzt, Alarme-Reiter liest nur `alarm_ab`. Der Verlust-Satz (AC-11) nutzt denselben `abweichungen`-Wert und wird mit dem Fix im Vergleich ebenfalls korrekt.
6. Worktree-HEAD (9836e0819) liegt hinter `origin/main` (92b752fa6); betroffene Dateien identisch, vor der Umsetzung vorspulen.

### Open Questions

Keine Produktfrage offen. Regel „nur Abweichungen speichern, Zurücksetzen leert sie“ ist freigegeben (feat_2794), E6/E7 sind bestehende Tech-Lead-Entscheidungen aus #3047; die Neutralität nicht ausgebbarer Größen im Vergleich folgt direkt aus E6.
