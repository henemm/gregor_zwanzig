# Context: feat-3306-tabelle-orte-anlegen

## Request Summary
Issue #3306 (Teil C von #3041, Epic #3122): Beim Anlegen eines Ortsvergleichs steht im Schritt „Wetter“ die Tabelle „Was steht wo“ samt Schaltern (Stundenverlauf, Telegram-Kurzstil; Ausblick über `outlook_reports` der Tabelle). `CompareNewEditor` übernimmt `display_config.placements`, `hourly_enabled` und `display_config.telegram_style` in den einen Anlege-POST. Nach dem Anlegen zeigt der Reiter Wetter genau diesen Stand. Zwei Nutzer. Pendant zu #3305 (Trip, live), gemeinsamer Code mit `context="vergleich"`, keine neue Komponente (Gate #1170).

Grundlage: `docs/context/feat-3041-tabelle-beim-anlegen.md` (Gesamtanalyse) und die #3305-Umsetzung (`docs/specs/modules/feat_3305_tabelle_trip_anlegen.md`).

## Related Files
| File | Relevance |
|------|-----------|
| `frontend/src/lib/components/compare-new/CompareNewEditor.svelte` | `wetterAbo` (Z.161-176, ohne `location_ids`/`hourly_enabled`/`telegram_style`), `handleWetterAnlegeStand` Z.181, `<WetterTab context="vergleich" … createMode>` Desktop Z.515, Mobil Z.568, POST `speichereNeuenVergleich` Z.324 → `legeVergleichAn(api, wiz, {ampel, auswahl})` |
| `frontend/src/lib/components/compare/compareEditorSave.ts` | `baueVergleichAnlegeRumpf` Z.587-634 (Rumpf aus `buildNewComparePresetPayload` + Wetter-Ampel/Auswahl), `legeVergleichAn` Z.642 |
| `frontend/src/lib/components/organisms/wetter-tab/WetterTabInhalt.svelte` | Kartengate `{#if createMode ? !!onAnlegeKarte : aboId}` Z.322; Props `karteStart`, `onAnlegeKarte` (aus #3305, schon kontextneutral); `entwurf={() => abo()}` |
| `frontend/src/lib/components/shared/WetterTab.svelte` | reicht `karteStart`/`onAnlegeKarte` durch (in #3305 bereits für beide Kontexte) |
| `frontend/src/lib/components/shared/wetter-tab/wasStehtWoSpeicherung.ts` | `KarteAnlegeStand {placements, felder, felderStart}`, `felderNutzlast('vergleich', neu, alt)` → `{hourly_enabled?, display_config?.telegram_style}` (nur Geändertes) |
| `frontend/src/lib/components/trip-new/TripNewEditor.svelte` / `tripNewLogic.ts` (`mitKarte`) | Vorbild der Verdrahtung (#3305) |
| `src/services/placements_view_service.py` | `build_placements_preview('vergleich', draft)` → `_entwurf_preset` + `_orte_abo_aus`; Orte nur aus `location_ids` des Entwurfs im Bestand des angemeldeten Nutzers; ohne Orte: keine Beispielwerte (`_Muster(sms=None)`) |
| `internal/handler/compare_preset.go:307` | POST ruft `anlageTabelle`: mitgeschickte `placements.rows` bleiben, sonst Erstanlage beim Kern |

## Existing Patterns
- #3305: Editor hält `karteStand` (überlebt Schrittwechsel und Desktop/Mobil), reicht `karteStart`/`onAnlegeKarte` an beide WetterTab-Stellen, Payload-Funktion mischt `placements` + `felderNutzlast(kind, felder, felderStart)` per Read-Modify-Write in den Rumpf, nur wenn `karte` gesetzt ist.
- `baueVergleichAnlegeRumpf` hat bereits den Parameter `wetter` für Reiter-Wetter-Stand → dort `karte?: KarteAnlegeStand` ergänzen (eine getestete Funktion, #3276 F-ADV1).

## Dependencies
- Upstream: Vorschau-Endpunkt (#3304, live), Karte im Anlege-Modus (#3305, live), Go-Anlage übernimmt mitgeschickte Tabelle (#3237).
- Downstream: E2E `hub-anlegen-ablauf.spec.ts` (AN-6: genau ein POST), `compare_new_editor_postet_einmal`, `feat3276_vergleich_ohne_altfelder.test.ts` (POST ohne Altschlüssel, `hourly_enabled`/`telegram_style` sind **keine** Altschlüssel), Wächterliste `bausteine_waechter_regeln.ts`.

## Analysis (kombiniert, Score 2)

### Befund: Entwurf der Vorschau ohne Orte
`wetterAbo` trägt keine `location_ids`. Die Vorschau würde dann ohne Orte rechnen (keine Beispielwerte in Mail/Telegram/SMS, `location_count` 0). Der Schritt „Orte“ liegt vor „Wetter“ → `location_ids: wiz.pickedIds` in den Entwurf. Ebenso `hourly_enabled: wiz.hourlyEnabled` und `display_config.telegram_style: wiz.telegramStyle`, damit die Schalter mit dem Stand des Feldsatzes starten (der Altblock im Schritt Zustellung kann sie bis #3307 ebenfalls setzen). Fremde/unbekannte Orts-IDs verwirft der Kern (#3304) — Cross-User sicher.
Prüfen: `wetterAbo` geht auch in `anlegeSpeicherer` — die zusätzlichen Felder dürfen den gemeldeten Wetter-Stand nicht verändern (Meldung trägt nur Ampel/Auswahl/Alarm/Tagesfenster).

### Affected Files
| File | Change | Description |
|------|--------|-------------|
| `frontend/src/lib/components/compare/compareEditorSave.ts` | MODIFY | `wetter.karte?: KarteAnlegeStand` → `display_config.placements` + `felderNutzlast('vergleich', …)` (hourly_enabled top-level, telegram_style in display_config) Read-Modify-Write in den Rumpf; ohne `karte` unverändert |
| `frontend/src/lib/components/compare-new/CompareNewEditor.svelte` | MODIFY | `karteStand` + `handleKarteStand`; `karteStart`/`onAnlegeKarte` an beiden WetterTab-Stellen; `karte: karteStand` an `legeVergleichAn`; `wetterAbo` um `location_ids`, `hourly_enabled`, `telegram_style` ergänzen |
| Tests (`node --test`, E2E) | CREATE | Rumpf mit/ohne Karte; Verdrahtung Editor; E2E Anlegen → Hub zeigt Stand; zwei Nutzer (Orte des anderen nicht in Vorschau) |

Kein Backend-Change erwartet (Vorschau `kind=vergleich` liest `_entwurf_preset`; Preset-Entwurf hat kein Datumsfeld wie die Trip-Etappen in #3305 — trotzdem in RED mit frühem Entwurf gegen den Kern prüfen: ohne `name`, ohne `schedule`, mit leerer `location_ids`).

### Scope
- 2 Produktionsdateien, ca. +40–70 LoC; Tests ca. 4 Dateien.
- Risiko LOW–MEDIUM: Datenverlust, wenn die Karte sichtbar ist, ihr Stand aber nicht im POST ankommt; Doppel-POST (AN-6).

### Risks & Considerations
- Karte nie zeigen, ohne dass ihr Stand im POST landet (Warnung PR #3042).
- `hourly_enabled`/`telegram_style` doppelt einstellbar (Karte + Altblock im Schritt Zustellung) bis #3307 — Karte gewinnt nur bei Änderung gegenüber ihrem Start (wie #3305).
- Keine Altschlüssel in den POST (#3276 AC-1).
- Zwei Nutzer: Vorschau nimmt Orte nur aus dem eigenen Bestand; POST nutzt Auth-Nutzer.

### Open Questions
- keine (Anlegen = Bearbeiten, PO-Vorgabe; Verhalten = #3305).

### Nachprüfung Analyse
- `anlegeSpeicherer('vergleich')` meldet aus `display_config` nur `ampel`, `active_metrics` (und Tabelle über `mitPlacements`) — zusätzliche Entwurfsfelder (`location_ids`, `hourly_enabled`, `telegram_style`) im `wetterAbo` verändern den gemeldeten Wetter-Stand nicht. `handleWetterAnlegeStand` verwirft `placements` weiterhin; die Tabelle reist allein über `karteStand`.
- Technischer Ansatz: genau Muster #3305; Type Feature; Risiko LOW–MEDIUM.
