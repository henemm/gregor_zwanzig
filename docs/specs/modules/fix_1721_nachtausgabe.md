---
entity_id: fix_1721_nachtausgabe
type: feature
created: 2026-11-02
updated: 2026-11-02
status: draft
version: "1.0"
workflow: fix-1721-nachtausgabe
tags: [trip, mail, nacht, wetter-metriken, show_night_block, kuerzel-legende, epic-2259]
---

# Nachtausgabe: Schalter fuer die Nacht-Stundentabelle (Issue #1721)

## Approval

- [ ] Approved

## Purpose

Die Trip-Mail enthaelt eine Nacht-Stundentabelle ("Nacht am Ziel"), die der Nutzer heute nicht abschalten kann, obwohl das Backend das Feld `display_config.show_night_block` laengst auswertet. Diese Spec gibt dem Feld einen Schalter im Wetter-Metriken-Reiter des Trips und haelt fest, dass die beiden anderen Punkte aus #1721 (Spalte `N`, Kuerzel `FN`) bereits durch #2136 bzw. #1888 behoben sind und nur noch einen Nachweis brauchen.

## Source

- **Frontend (neu):** `frontend/src/lib/components/shared/WeatherMetricsTab.svelte` (Schalter, nur `context="route"`)
- **Frontend (Nutzlast):** `frontend/src/lib/components/shared/pickEigenfelder.ts` (`WETTER_DISPLAY_KEYS`), `frontend/src/lib/types.ts` (`DisplayConfig`)
- **Backend (unveraendert, nur Beleg):** `src/output/renderers/trip_report.py:166-168` (Gate), `src/services/segment_weather.py` (`night_weather_needed`), `src/app/models.py:655`/`:829`, `src/app/loader.py:1088`/`:1615`/`:1832`
- **Identifier:** `show_night_block`

> Hinweis zum Fundort: Der Wetter-Metriken-Reiter liegt unter `frontend/src/lib/components/shared/WeatherMetricsTab.svelte` (nicht im Unterordner `weather-metrics-tab/`; dort liegen nur Hilfsmodule wie `kuerzelLegende.ts`).

## Befund (am Code geprueft, 2026-11-02)

| Punkt aus #1721 | Stand | Beleg |
|---|---|---|
| 1 Schalter `show_night_block` | Echte Luecke. Backend wertet aus, Frontend hat kein Bedienelement. | `trip_report.py:168` (`if night_weather and dc.show_night_block`); `loader.py:1088` (Laden, Default `True`), `:1832` (Speichern). Im Frontend kommt das Feld nur in Tests vor, in keiner `.svelte`-Datei. |
| 2 Ausblick-Spalte `N` | Behoben durch #2136, kein Code. | `outlook.py:225-245`: Spaltenkoepfe `Temp min`/`Temp max` aus `col_label` plus `aggregation_label_de`; Werte `temp_lo`/`temp_hi` (Tages-Minimum/-Maximum, `outlook.py:263-266`). Die Legende "Nacht-Tief" gibt es nicht mehr. Beschriftung und Inhalt stimmen ueberein. Es fehlt nur der Nachweis an der zugestellten Mail. |
| 3 `FN` erklaert | Behoben durch #1888, kein Code. | `WeatherMetricsTab.svelte:1935-1939` bindet `wind_chill_night` ein; `kuerzelLegende.ts` leitet die Legende aus dem Katalog ab; `metricKuerzelLegende.test.ts` prueft, dass `FN` mit dem Registerlabel erklaert wird. `kuerzel-legende-lesbar.staging.spec.ts` fuehrt `wind_chill_night` in `TRIP_METRIKEN`, prueft aber nur allgemein "jeder Marken-Block erklaert seine Kuerzel", nicht ausdruecklich den Text zu `FN`. Dafuer kommt ein gezielter Klickpfad dazu (AC-8). |

**Trip/Ortsvergleich:** Die Nacht-Stundentabelle gibt es nur im Trip. `_extract_night_rows` wird ausschliesslich in `trip_report.py` gerufen; der Ortsvergleich-Renderer kennt keinen Nachtblock (`loader.py:1615` schreibt das Feld bei Orten nur mit, ohne Wirkung). Es gibt also kein Compare-Pendant, der Schalter darf deshalb im geteilten Reiter nur bei `context="route"` erscheinen. Das ist die dokumentierte Begruendung fuer die einseitige Anlage (Pendant-Sperre).

**Go-Durchreichung:** `internal/handler/config_merge.go` (`mergeConfigMap`) fuehrt Read-Modify-Write schluesselweise aus (mitgesendete Schluessel ueberschreiben, fehlende bleiben). `show_night_block` kommt in `internal/` und `cmd/` nicht vor; das Feld laeuft als unbekannter Schluessel generisch durch. Das bestaetigt ein Go-Test (AC-6, Teil des Testplans).

**Nutzlast-Waechter:** `pickEigenfelder.ts` legt je Reiter fest, welche `display_config`-Schluessel er senden darf (`WETTER_DISPLAY_KEYS`). Der Test `trip_reiter_nutzlast_nur_eigene_felder.test.ts` (Liste in `keineFremdschluessel`, Zeile ~60) behauptet heute, dass `show_night_block` von keinem Reiter je gesendet wird. Diese Zusicherung wird bewusst geaendert: Der Wetter-Metriken-Reiter wird Eigentuemer des Feldes; alle anderen Reiter senden es weiterhin nie. `pick_eigenfelder_kernregel.test.ts` (Zeile ~95, Fremdschluessel-Fall) bleibt gueltig, weil er mit eigener Auswahlliste arbeitet.

## Estimated Scope

- **LoC:** ca. +130 / -10 (ueberwiegend Test)
- **Files:** 6 bis 8 (Svelte-Reiter, `pickEigenfelder.ts`, `types.ts`, Nutzlast-Waechter-Test, ein Go-Test, neuer E2E-Klickpfad samt Staging-Setup-Datei)
- **Effort:** low bis medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `night_weather_needed()` (`segment_weather.py`) | Funktion | Geteilte Entscheidung "Nachtdaten beschaffen" fuer Versand und Vorschau (#1484 AC-8); bleibt unveraendert |
| `config_merge.go` | Go-Merge | Read-Modify-Write beim Speichern, haelt `show_night_block` bei Teil-PUT |
| `briefing_mail_validator.py` | Validator | Trip-Briefing-Mail gegen Stalwart-Staging |
| `fix_2136_outlook_col_label.md`, `fix_1888_e6b_kuerzel_legende.md` | Specs | Grundlage von Punkt 2 und 3 |
| `feat_1484_night_temp_metric.md`, `briefing_parity_night_thunder.md` | Specs | Nacht-Metriken und Gewitter-Nachtsatz |

## Implementation Details

**Schalter (nur Trip):**

- Im Wetter-Metriken-Reiter (`WeatherMetricsTab.svelte`) erscheint, nur wenn `context === 'route'`, ein Schalter mit der Beschriftung **"Nacht-Stundentabelle in der Mail zeigen"**. Im Ortsvergleich (`context === 'vergleich'`) wird er nicht gerendert (nicht nur versteckt).
- Anfangswert: gespeicherter Wert `trip.display_config.show_night_block`; fehlt das Feld (Alt-Trip), gilt `true` (wie `loader.py:1088`). Im Anlegemodus (`createMode`) ebenfalls `true`.
- Umlegen zaehlt als Nutzergeste (setzt `userTouched`, damit das Speicher-Gate `weatherSaveGate` durchlaesst) und nutzt den bestehenden Speicherpfad des Reiters.
- `show_night_block` wird in `WETTER_DISPLAY_KEYS` aufgenommen und in `buildWeatherPayload()` mitgegeben, aber nur, wenn der Nutzer den Schalter bedient hat oder ein gespeicherter Wert existiert (sonst `undefined`, der Schluessel wird nicht gesendet). So bekommt ein Alt-Trip ohne Feld beim Speichern anderer Reiter-Inhalte keinen neuen Wert, und die Go-Seite (`mergeConfigMap`) behaelt den Bestand. `false` ist ein bewusster Wert und geht durch (Loesch-Semantik wie bei den uebrigen Eigenfeldern).
- `DisplayConfig` in `types.ts` bekommt `show_night_block?: boolean`.
- Hilfetext unter dem Schalter (eine Zeile): "Betrifft nur die Stundentabelle. Nacht-Tiefstwert und Gewitter-Hinweis fuer die Nacht bleiben, wenn du sie gewaehlt hast."

**Backend:** keine Aenderung. `trip_report.py` blendet die Tabelle bei `show_night_block=False` aus; `night_weather_needed()` beschafft die Nachtdaten weiter, sobald `temperature_night`, `wind_chill_night` oder `thunder` aktiv ist, sodass `N`, `FN` und der Gewitter-Nachtsatz erhalten bleiben.

**Kanaele:** Betroffen ist allein die Nacht-Stundentabelle der E-Mail (Voll und Kompakt). Telegram, SMS und Premium-SMS haben keine Nacht-Stundentabelle; der Schalter aendert dort nichts. Die Nacht-Metriken und der Gewitter-Nachtsatz erreichen unveraendert alle vier Kanaele (Paritaet, ADR-0095).

**Mandantentrennung:** Es gilt die `user_id` aus dem Auth-Kontext; der Schalter wird je Trip des angemeldeten Nutzers gespeichert (`data/users/<user_id>/trips/`).

## Expected Behavior

- **Input:** Nutzer oeffnet den Wetter-Metriken-Reiter eines Trips, legt den Schalter um und speichert.
- **Output:** Der Wert steht in `display_config.show_night_block` des Trips; die naechste zugestellte Trip-Mail zeigt die Nacht-Stundentabelle genau dann, wenn der Schalter an ist.
- **Side effects:** Keine. Andere `display_config`-Schluessel, andere Trips und andere Nutzer bleiben unberuehrt.

## Acceptance Criteria

**AC-1:** Given ein angemeldeter Nutzer mit einem Trip / When er im Trip den Reiter "Wetter-Metriken" oeffnet / Then sieht er den Schalter "Nacht-Stundentabelle in der Mail zeigen", und im Editor eines Ortsvergleichs ist dieser Schalter im selben Reiter nicht vorhanden.
- Test: frontend/e2e/trip-night-block-schalter.staging.spec.ts (Klickpfad Trip + Ortsvergleich)

**AC-2:** Given ein Trip ohne gespeichertes Feld `show_night_block` (Alt-Trip) / When der Nutzer den Reiter oeffnet / Then steht der Schalter auf "an", und nach dem Speichern einer anderen Einstellung (z.B. andere Metrik) bleibt die Nacht-Stundentabelle in der naechsten Mail erhalten.
- Test: frontend/e2e/trip-night-block-schalter.staging.spec.ts (Alt-Trip) + node-test pickEigenfelder

**AC-3:** Given ein Trip mit Schalter "an" / When der Nutzer den Schalter ausschaltet, speichert und die Seite neu laedt / Then steht der Schalter nach dem Neuladen weiterhin auf "aus", und beim Oeffnen eines anderen Reiters und Zurueckkehren bleibt er aus.
- Test: frontend/e2e/trip-night-block-schalter.staging.spec.ts (Umlegen, Speichern, Neuladen)

**AC-4:** Given ein Trip mit Schalter "aus" / When die Trip-Mail (Voll-Format) zugestellt wird und im Test-Postfach liegt / Then enthaelt sie keine Nacht-Stundentabelle ("Nacht am Ziel"), und bei Schalter "an" desselben Trips enthaelt die zugestellte Mail diese Tabelle; `briefing_mail_validator.py` endet in beiden Faellen mit Exit 0.
- Test: zugestellte Staging-Mail + briefing_mail_validator.py (Exit 0, beide Zustaende)

**AC-5:** Given ein Trip mit Schalter "aus", gewaehlter Metrik "Nacht-Tiefsttemperatur" und aktivem Gewitter / When die Trip-Mail zugestellt wird / Then zeigt sie weiterhin den Nacht-Tiefstwert (Kuerzel `N`) und den Gewitter-Nachtsatz, nur die Stundentabelle fehlt.
- Test: zugestellte Staging-Mail, gezielte Pruefung auf N und Gewitter-Nachtsatz

**AC-6:** Given zwei verschiedene Nutzer mit je einem Trip / When Nutzer A den Schalter ausschaltet und speichert / Then bleibt der Trip von Nutzer B auf "an", und ein Teil-Speichern ohne `show_night_block` (z.B. aus einem anderen Reiter) laesst den gespeicherten Wert von Nutzer A unveraendert (Go-API, Read-Modify-Write mit Merge).
- Test: frontend/e2e/trip-night-block-schalter.staging.spec.ts (zwei Nutzer) + Go-Test config_merge_structure_test.go

**AC-7:** Given der Trip-Mail-Ausblick mit der Standardspalten-Auswahl / When die Mail zugestellt wird / Then tragen die Temperatur-Spalten die Koepfe "Temp min" und "Temp max", ihre Werte entsprechen dem Tages-Minimum und -Maximum der jeweiligen Etappe, und weder die Spalte "N" noch die Legende "Nacht-Tief" kommen im Ausblick vor.
- Test: zugestellte Staging-Mail, Pruefung der Ausblick-Koepfe und Werte

**AC-8:** Given ein Trip mit gewaehlter Metrik "Gefuehlte Nacht-Tiefsttemperatur" (`wind_chill_night`) / When der Nutzer im Browser den Wetter-Metriken-Reiter oeffnet / Then zeigt die Kuerzel-Legende einen Eintrag `FN` mit der Erklaerung "Gefuehlte Nacht-Tiefsttemperatur" (Text aus dem Katalog).
- Test: frontend/e2e/trip-night-block-schalter.staging.spec.ts (Metrik waehlen, Legende zeigt FN)

## Testplan

Es gibt keine Mock-Theater-Tests; jede Zusicherung wird dort geprueft, wo sie wirkt.

1. **Echter Browserlauf mit Klickpfad (PO-Leitplanke "KRITISCH"):** neue Datei `frontend/e2e/trip-night-block-schalter.staging.spec.ts` (mit `.staging.setup.ts`), gegen Staging mit Staging-Login:
   - AC-1: Trip-Editor zeigt den Schalter; Ortsvergleich-Editor zeigt ihn nicht.
   - AC-2/AC-3: Alt-Trip ohne Feld steht auf "an"; ausschalten, speichern, neu laden: bleibt "aus"; Stand per API gegengelesen (`display_config.show_night_block === false`).
   - AC-6: zweiter Testnutzer (eigene Session), eigener Trip bleibt "an"; Teil-Speichern ohne das Feld erhaelt den Wert.
   - AC-8: Metrik `wind_chill_night` waehlen, Legende zeigt `FN` samt Erklaerungstext.
2. **Mail-Nachweis gegen Stalwart-Staging:** Trip-Briefing mit Schalter "aus" und "an" ueber den echten Versandweg ausloesen, zugestellte Mail im Test-Postfach pruefen mit `uv run python3 .claude/hooks/briefing_mail_validator.py` (Exit 0) und gezielter Pruefung auf "Nacht am Ziel" (AC-4), `N`/Gewitter-Nachtsatz (AC-5) sowie auf die Ausblick-Koepfe "Temp min"/"Temp max" mit Tages-Min/Max-Werten (AC-7).
3. **Verhaltenstests (keine Dateiinhalt-Checks):**
   - `node --test`: `buildWeatherPayload` sendet `show_night_block` nur bei gesetztem oder gespeichertem Wert; Alt-Trip ohne Feld sendet es nicht; `false` geht durch.
   - Nutzlast-Waechter `trip_reiter_nutzlast_nur_eigene_felder.test.ts`: `show_night_block` ist nur im Wetter-Metriken-Reiter erlaubt, in Versand, Alarme usw. weiterhin nie.
   - Go: `config_merge_structure_test.go` um einen Fall `show_night_block=false` erweitern (Teil-PUT ohne das Feld erhaelt es, PUT mit dem Feld setzt es).
   - Python: bestehende Tests `test_briefing_parity_night_thunder.py` und `night_weather_needed` bleiben unveraendert gruen.
4. **Renderer-Gate:** Da kein Renderer (`trip_report.py`, `outlook.py`) geaendert wird, loest das Renderer-Commit-Gate nicht aus; der Mail-Nachweis in Punkt 2 wird trotzdem gefahren, weil AC-4, AC-5 und AC-7 daran haengen.

## Nicht-Ziele

- Keine Aenderung an Renderern, `night_weather_needed()` oder dem Datenmodell.
- Kein Nacht-Schalter im Ortsvergleich (kein Nachtblock dort).
- `confidence_pct` bleibt unberuehrt (Issue #710).
- Keine neue Beschriftung der Ausblick-Spalten; die Koepfe aus #2136 gelten.

## Known Limitations

- Der Schalter steuert nur die Nacht-Stundentabelle der Trip-Mail. Nacht-Metriken (`N`, `FN`) und der Gewitter-Nachtsatz bleiben bewusst unabhaengig davon.
- Der Ortsvergleich hat keine Nacht-Stundentabelle und bekommt deshalb keinen Schalter (siehe Nicht-Ziele).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Es wird ein bestehendes Feld (`show_night_block`) bedienbar gemacht; keine neue Datenmodell-, Kanal- oder Provider-Entscheidung. ADR-0095 (Kanal-Paritaet) wird nur referenziert, der Schalter wirkt kanalunabhaengig auf die Mail-Tabelle.

## Changelog

- 2026-11-02: Initial erstellt (Issue #1721, Epic #2259)
