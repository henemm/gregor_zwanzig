# Mutationsnachweis TDD RED — Rework #3020 (R1, R1b)

Workflow `rework-3020-pruefungen-und-waisen`, Phase TDD RED, 25.11.2026.
Spec: `docs/specs/modules/rework_3020_pruefungen_wiederherstellen.md`.

Verfahren je Mutation: Datei nach `/tmp/claude-1000/-home-hem-gregor-zwanzig/f54b53b5-b98a-45c6-9fc2-f81d68bd3405/scratchpad/mut/` kopiert, sha256 vorher festgehalten, Mutation per eindeutiger String-Ersetzung (`str.replace`, Treffer genau 1), Testlauf, Datei aus der Kopie zurückgeschrieben, sha256 geprüft. Abschlussprüfung `sha256sum -c` über alle 12 berührten Produktionsdateien: alle `OK`; `git status` zeigt keine geänderte Produktionsdatei.

## R1b — Katalog-Wächter (Python)

Die Tests AC-1, AC-2, AC-16 und AC-3 (Erkennung) sind heute rot, weil der lebende Wächter den Fehler hat (`${key}` wird zu `.+`). Der heutige Code IST die Mutation aus der Spec („Platzhalter wieder als `.+`“).

Gegenprobe (vorübergehende Korrektur, zurückgesetzt, sha256 OK): in `_vitest_titel_gefunden` nur Vorlagen mit festem Textanteil zulassen (`… for v in _VITEST_TEMPLATE_GANZ.findall(quelle) if _TEMPLATE_PLATZHALTER.sub("", v).strip()`).

| Test | heute | mit Korrektur des Wächters |
|---|---|---|
| `test_ac1_erfundener_titel_ohne_datei_wird_trotz_platzhalter_vorlage_rot` | rot | grün |
| `test_ac2_vorlage_mit_festem_anteil_trifft_reine_platzhalter_vorlage_nie` | rot | grün |
| `test_ac16_nur_faelle_mit_fehlendem_ziel_werden_rot` | rot | grün |
| `test_ac3_alte_verweise_der_26_faelle_erkennt_der_waechter_als_fehlend` | rot (0 von 26 erkannt) | grün (26 erkannt) |
| `test_ac3_katalog_verweist_jeden_der_26_faelle_ehrlich` | rot | rot (Katalog-Korrektur ist Phase GREEN) |
| `test_ac3_nur_ein_bericht_faelle_sind_ausnahme_mit_3065` | rot | rot (Katalog-Korrektur ist Phase GREEN) |
| `test_ac4_katalogfall_telegram_nur_tageswert_verweist_gruen_auf_kartentest` | rot | rot (Katalogfall fehlt, Phase GREEN) |

## R1 — Go (`go test ./internal/store/ -run Rework3020`)

| # | Test | Mutation (Datei: alt → neu) | Ergebnis |
|---|---|---|---|
| G1 | `TestRework3020_SkipNextBleibtBeimSpeichernOhneFeld_ZweiNutzer` (AC-5) | `internal/handler/trip.go`: `existing.ReportConfig = mergeConfigMap(existing.ReportConfig, *req.ReportConfig)` → `existing.ReportConfig = *req.ReportConfig` | rot |
| G2 | `TestRework3020_AltTripOhneNightBlockBleibtOhneFeld_ZweiNutzer` (AC-9) | `internal/handler/trip.go`: nach dem DisplayConfig-Merge `existing.DisplayConfig["show_night_block"] = true` angehängt | rot |
| G3 | `TestRework3020_SpeichernOhneAenderungErhaeltMetrikFlags_ZweiNutzer` (AC-12), `TestRework3020_TeilUpdateAusblickUndWarnungswerteErhaeltUebrigeFelder_ZweiNutzer` (AC-17) | `internal/handler/trip.go`: `existing.DisplayConfig = mergeConfigMap(existing.DisplayConfig, *req.DisplayConfig)` → `existing.DisplayConfig = *req.DisplayConfig` | beide rot |
| G4 | `TestRework3020_WarnungswerteUndAusblickJeNutzerGetrennt` (AC-17, Store) und alle vier übrigen | `internal/store/store.go` `WithUser`: `copy.UserID = userId` → `_ = userId` (Mandantentrennung aufgehoben) | alle fünf rot |

## R1 — Frontend (`node --test`)

| # | Test (Datei) | Mutation | Ergebnis |
|---|---|---|---|
| F1a | AC-6 Zustellung (`shared/__tests__/rework_3020_trip_nutzlast_ohne_skip_next.test.ts`) | `zustellungSpeicherung.ts`: `verpacke(felder)` → `verpacke({ ...felder, skip_next: null })` | Test 1 rot |
| F1b | AC-6 Karte (dieselbe Datei) | `wasStehtWoSpeicherung.ts`: `{ report_config: rc }` → `{ report_config: { ...rc, skip_next: null } }` | Test 2 rot |
| F2a | AC-7 Flush (`zustellung-tab/__tests__/rework_3020_zustellung_ifmatch_keepalive.test.ts`) | `zustellungSpeicherung.ts`: `client.put<unknown>(pfad, nutzlast, init)` → ohne `init` | Flush-Test rot |
| F2b | AC-7 If-Match/Antwort-Stempel (dieselbe Datei) | `api.ts`: `if (serializedWrite) setKnownEtag(tripId, etag);` → `if (serializedWrite) void 0;` | Stempel-Test rot |
| F3 | AC-8 (`wetter-tab/__tests__/rework_3020_nachtblock_schalter.test.ts`) | `wasStehtWoSpeicherung.ts`: `show_night_block: b.show_night_block !== false` → `=== true` | AC-8 rot (dazu AC-10b) |
| F4 | AC-9 (dieselbe Datei) | `wasStehtWoSpeicherung.ts`: `const dc = nurGeaendert(neu, alt, ['show_night_block'])` → `const dc = { show_night_block: neu.show_night_block }` | AC-9, AC-10a, AC-10b rot |
| F5a | AC-10b (dieselbe Datei) | `wasStehtWoSpeicherung.ts` `erstelleFelderSpeicherung`-catch: `aktuell = { ...bezug }; o.onFehler?.(e, { ...bezug });` → `o.onFehler?.(e, { ...aktuell });` | AC-10b rot |
| F5b | AC-10a (dieselbe Datei) | `wasStehtWoSpeicherung.ts`: Zeile `if (!Object.keys(rumpf).length) return;` entfernt | AC-10a rot |
| F7a | AC-15 Karte (`organisms/__tests__/rework_3020_karte_schalter.test.ts`) | `wasStehtWoSpeicherung.ts`: `show_stability: b.show_stability !== false` → `b.show_outlook !== false` | drei AC-15-Tests rot |
| F7b | AC-15 mailInhaltKonstanten (dieselbe Datei) | `mailInhaltKonstanten.ts`: Baustein-Schlüssel `show_stability` → `show_outlook` | AC-15-Konstanten-Test rot |
| F8a | AC-13 (`zustellung-tab/__tests__/rework_3020_premium_sms_schaltbar.test.ts`) | `zustellungModell.ts`: `premium_sms_reply_state === 'fresh'` → `!== 'stale'` | „kein Handler (nie_gemeldet)“ rot, beide Kontexte |
| F8b | AC-13 (dieselbe Datei) | `KanalTabelle.svelte`: `disabled={st.briefingGesperrt}` → `disabled={false}` | „kein Handler“ rot, beide Fälle, beide Kontexte |
| F9a | AC-14 vergleich (`zustellung-tab/__tests__/rework_3020_defaults_gleich_auslieferung.test.ts`) | `compareEditorSave.ts`: `send_premium_sms: fields.sendPremiumSms,` → `send_premium_sms: true,` | Vergleich-Test rot |
| F9b | AC-14 route (dieselbe Datei) | `reportConfigPayload.ts`: `evening_enabled: z.evening_enabled,` → `!z.evening_enabled` | Trip-Test rot |
| F10a | AC-17 Ausblick (`wetter-tab/__tests__/rework_3020_ausblick_warnungswerte_nutzlast.test.ts`) | `wasStehtWoStand.ts` `mitAusblick`: Filter `berichte[b]` → `b === 'evening'` | beide Ausblick-Tests rot |
| F10b | AC-17 Warnungswerte (dieselbe Datei) | `alarmeDeliveryPayload.ts`: `{ metric_alert_levels: … }` → `{ show_outlook: true, metric_alert_levels: … }` | Warnungswerte-Test rot |

## Nachtrag Fix-Loop (Adversary AMBIGUOUS: F001, F003, F004)

Verfahren wie oben: Sicherung nach `/tmp/claude-1000/-home-hem-gregor-zwanzig/f54b53b5-b98a-45c6-9fc2-f81d68bd3405/scratchpad/mut2/`, sha256 vorher, Mutation als eindeutige String-Ersetzung (Edit-Werkzeug), Testlauf, Rückschreiben aus der Kopie, `sha256sum -c` OK für alle vier Dateien (`saveStatusStore.svelte.ts` 1e60829d…, `compareHubPersistenz.ts` 5c98fcd1…, `zustellungModell.ts` fb48b2fd…, `zustellungSpeicherung.ts` 8f4c0b9c…); `git status` ohne geänderte Produktionsdatei.

| # | Test (Datei) | Mutation | Ergebnis |
|---|---|---|---|
| F11a | F001 (`shared/__tests__/rework_3020_vergleich_parallele_schreiber.test.ts`) | `saveStatusStore.svelte.ts` `schedule`: `if (this._pendingFn && this._pendingOwner !== owner) {` → `if (false && this._pendingFn && …) {` (fremder Slot wird verdrängt) | beide Reihenfolge-Tests rot |
| F11b | F001 (dieselbe Datei) | `compareHubPersistenz.ts` `createPutQueue`: `const run = tail.then(fn);` → `const run = fn();` (keine Schlange) | „fremder Hub-Schreiber läuft“ rot (zuerst ohne diesen Fall grün geblieben: der Controller reiht die eigenen Vorgänge schon nacheinander; Fall deshalb ergänzt) |
| F11c | F001 (dieselbe Datei) | `zustellungSpeicherung.ts`: `await (opt.enqueueHubWrite ? opt.enqueueHubWrite(lauf) : lauf());` → `await lauf();` | „Wetter, dann Zustellung“ und „fremder Hub-Schreiber“ rot |
| F12a | F003 AC-14 (`zustellung-tab/__tests__/rework_3020_defaults_gleich_auslieferung.test.ts`) | `zustellungModell.ts` `cooldownVon`: Rückfall `COOLDOWN_STANDARD` → `0` | route und vergleich rot |
| F12b | F003 AC-14 (dieselbe Datei) | `zustellungModell.ts`: `const STILLE_VON_STANDARD = '22:00';` → `'21:00'` | route und vergleich rot |
| F13 | F004 AC-13 (`zustellung-tab/__tests__/rework_3020_premium_sms_schaltbar.test.ts`) | `zustellungModell.ts` `premiumStatus`: `if (p.premium_sms_reply_state === 'stale') {` → `if (false && …) {` (Rückfall „nie gemeldet“) | „verfallene Rückadresse (stale)“ rot, beide Kontexte |

### Wiederholung F11a–c nach Merge von origin/main (fdb1ddaac, enthält #3379 / 4ba927c14)

Nach dem Merge waren alle vier F001-Fälle rot, auch die Vorbedingung. Ursache war die veraltete Testverdrahtung, kein Produktfehler: #3379 ändert die Signatur von `standAusAbo(context, abo, aufgeloest, …)`. Ampel und Vorlagen-ID kommen jetzt fertig aus der Server-Auflösung; vorher stand an dieser Stelle `vorlagen`. Der Test übergab weiter `vorlagen`, dadurch war der Wetter-Stand ohne Ampel. Der Test hydriert jetzt wie f003 mit `aufgeloestVon(seite)` (echtes Python). Danach sind alle Zusicherungen unverändert 4/4 grün, also geht keine Änderung verloren.
Sicherung `…/scratchpad/mut3/`, sha256 vorher = nachher (`sha256sum -c` OK): saveStatusStore 1e60829d…, compareHubPersistenz 5c98fcd1…, zustellungSpeicherung 8f4c0b9c….

| # | Mutation | Ergebnis |
|---|---|---|
| F11a | `schedule`: fremder Slot wird verdrängt | 3 von 4 rot (beide Reihenfolgen, fremder Hub-Schreiber) |
| F11b | `createPutQueue`: `const run = fn();` | „fremder Hub-Schreiber läuft“ rot |
| F11c | `zustellungSpeicherung.ts` ohne `enqueueHubWrite` | 2 von 4 rot |

## Ohne Mutation rot (echter Befund, nicht behoben)

| Test | Befund |
|---|---|
| `organisms/__tests__/rework_3020_karte_schalter.test.ts` › „Anlegen (createMode): die Karte zeigt keinen Nachtblock-Schalter“ (AC-11) | Die Karte zeigt im Anlegen alle Trip-Blöcke, also auch den Nachtblock-Schalter (`WasStehtWoKarte.svelte`, `{#if k.tripBloecke}` ohne `createMode`-Bedingung). #3305 bedient ihn im Anlegen ausdrücklich (`was_steht_wo_karte_anlegen_3305.test.ts`: `k.u.feld('show_night_block', false)`, der Anlege-POST trägt die Differenz). AC-11 widerspricht damit dem freigegebenen Verhalten von #3305; zu klären, ob AC-11 gilt (Schalter im Anlegen ausblenden) oder AC-11 durch #3305 abgelöst ist. |
