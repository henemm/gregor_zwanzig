# Context: fix-3092-put-unbekannte-felder (Issue #3092)

## Request Summary
Beim Speichern eines Orts-Vergleichs (PUT `/api/compare/presets/{id}`) und eines Trips verwirft der
Go-Schreibpfad Top-Level-Felder, die das Go-Modell nicht kennt (Nebenbefund #3047 p10). Verstoß gegen
ADR-0101 (Read-Modify-Write mit Merge, niemals Replace). Ziel: unbekannte Top-Level-Felder bleiben bei
jedem Go-Save erhalten, für Ortsvergleich und Trip, Test mit zwei Nutzern.

## Root Cause (belegt)
- `internal/store/compare_preset.go:244` `SaveComparePreset`: `json.MarshalIndent(p)` des Structs →
  `writeFileLogged` schreibt die Datei komplett neu. Was beim Laden in `model.ComparePreset` keinen
  Platz hatte, ist weg.
- `internal/store/trip.go:283` `SaveTrip`: identisches Muster (`MarshalIndent(trip)` → Vollschreiben).
- Beide Funktionen sind die einzigen Schreib-Seams (alle Go-Schreiber rufen sie: PUT, State-PATCH,
  Briefing-PUT `?kind=vergleich`, Weather-Config-PUT …, ~15 Aufrufstellen). Fix am Store-Seam schützt
  alle Wege.

## Existing Pattern (Vorbild)
- `internal/store/user.go:146-200` `saveUserLocked` + `userJSONKeys()` (#2687, ADR-0101): vorhandene
  Datei als `map[string]json.RawMessage` lesen, alle dem Modell bekannten Schlüssel (per Reflection aus
  den json-Tags) entfernen, Modell-Map darüberlegen, schreiben. Unlesbare/fehlende Datei → Modellstand.
  Bekannte, aber geleerte Felder (omitempty) verschwinden korrekt, weil nur UNBEKANNTE Schlüssel der
  Altdatei überleben.
- Test-Vorbild: `internal/store/user_saveuser_merge_test.go` (`zukunftsfeld`).

## Related Files
- `internal/store/compare_preset.go` (SaveComparePreset)
- `internal/store/trip.go` (SaveTrip)
- `internal/store/user.go` (userJSONKeys — verallgemeinerbar auf beliebigen Struct-Typ)
- neue Tests: `internal/store/*_unbekannte_felder_test.go` und/oder Handler-Test PUT mit zwei Nutzern
- Modelle `internal/model/trip.go`, `internal/model/compare_preset.go`: keine `json:"-"`-Felder, keine
  eigenen (Un)MarshalJSON → Reflection über json-Tags reicht.

## Dependencies / Dependents
- Python schreibt dieselben `briefings/<id>.json` (ADR-0083, gemeinsame Sperre) — Python-Seite nicht im
  Scope (Issue nennt Go-PUT).
- `kind` wird von beiden Saves unbedingt gesetzt; bleibt bekannter Schlüssel.

## Risks
- Eingebettete/anonyme Struct-Felder würden von einer naiven Reflection übersehen → prüfen (Modelle
  haben keine, aber Helper sollte es nicht falsch machen).
- Pfad: Merge muss dieselbe Datei lesen, die geschrieben wird (`briefings/<id>.json`), unter der
  bestehenden Briefing-Sperre (ADR-0083) — Saves laufen bereits unter Handler-Sperre.
- Größenprüfung `pruefeEntityGroesse` muss auf den gemergten Inhalt laufen.
- Nur Top-Level; verschachtelte unbekannte Felder (z. B. in stages) sind nicht Gegenstand des Issues.
- Schema-Dateien in `internal/store/store.go`/`internal/model/*.go` lösen Backup-Hook aus — Fix liegt
  in `internal/store/trip.go`/`compare_preset.go`/`user.go`.

## Analysis

**Type:** Bugfix (Datenverlust-Risiko, ADR-0101-Verstoß)

### Befunde (bug-intake, belegt)
- Laden typisiert: `store/compare_preset.go:147,196`, `store/trip.go:196,252`; Schreiben Vollersatz:
  `compare_preset.go:266-273`, `trip.go:332-340`.
- Schreibwege SaveTrip: `handler/trip.go:327,608,703,784`, `handler/weather_config.go:126`,
  `store/migrate_1257.go:44`, `store/migrate_1258.go:102`. SaveComparePreset: `handler/compare_preset.go:303,463,596`,
  `handler/briefing_subscription.go:297`, `store/migrate_1258.go:143`. Alle laufen über die zwei Seams → Fix dort deckt alle ab.
- Bereits verlustfrei: `store/briefing_placements.go:64` (Roh-Map-RMW), `SaveBriefing` (raw-Hülle), Python `save_trip`
  (`_deep_merge_preserve_unknown`). Python schreibt keine Presets.
- Altfelder (#3277, `src/app/loader.py` ALTFELDER): Spec feat_3277 legt fest „kein Go-Strip auf Schreibwegen, Altfelder bleiben
  bis zum nächsten Python-Save“ → Go-Merge, der sie erhält, ist spec-konform.
- **Falle:** bekannte, aber geleerte omitempty-Felder (paused_at, archived_at, letzter_versand, end_date, …) dürfen NICHT aus der
  Altdatei wiederaufleben → zuerst alle Modell-Schlüssel (Reflection über json-Tags) aus der Roh-Map löschen, dann Modell-Map
  darüberlegen (wie `user.go:182-187`).
- Nur Top-Level; display_config etc. werden als Ganzes vom Modell geschrieben (Go-Legacy-Bereinigung in display_config bleibt wirksam).

### Varianten
| Variante | Dateien | LoC (ca.) | Abdeckung | Risiko |
|---|---|---|---|---|
| A: Roh-Merge-Helper am Store-Seam (SaveTrip + SaveComparePreset), `userJSONKeys` zu generischem `jsonKeysOf(type)` verallgemeinert | 3 Prod + 2 Test | ~60 Prod + ~150 Test | alle Go-Schreibwege | gering, bewährtes Muster |
| B: Merge nur im PUT-Handler | 2 | ~40 | nur PUT, State-PATCH/Weather/Briefing-PUT verlieren weiter | Lücke bleibt |
| C: `Extra map[string]json.RawMessage` im Modell mit eigenem (Un)MarshalJSON | 2 Modelle | ~120 | alle | hoch: Modelländerung, Schema-Hook, JSON-Antworten ändern sich |

**Empfehlung: A.**

### Affected Files
- MODIFY `internal/store/user.go` (userJSONKeys → generischer Helper; Verhalten SaveUser unverändert) — oder CREATE `internal/store/raw_merge.go`
- MODIFY `internal/store/trip.go` (SaveTrip: Merge vor Schreiben, Größenprüfung auf Ergebnis)
- MODIFY `internal/store/compare_preset.go` (SaveComparePreset: dito)
- CREATE Tests: Store-Ebene (unbekanntes Feld bleibt, geleertes bekanntes Feld bleibt weg, kaputte Altdatei → Modellstand) +
  Handler-PUT Ortsvergleich und Trip mit zwei Nutzern (Feld bei Alice bleibt, Bob unberührt/isoliert).

### Scope/Risk
~5 Dateien, ~210 LoC inkl. Tests. Risiko mittel (zentraler Schreibpfad), abgefedert durch bewährtes Muster und bestehende Store-Tests.

### Open Questions
Keine (technisch; PO-Entscheid nicht nötig).
