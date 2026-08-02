# Context: #1459 — Alert-Protokoll hält fest, WORUM es ging

Scheibe 1 von 5 im Epic **#1458**. Zielmodell und Gesamtzusammenhang:
`docs/context/konzept-1458-alerts-zweck.md`.

## Request Summary

`alert_log.json` soll zusätzlich festhalten: **welche Wettergröße** eine Meldung ausgelöst
hat, **welcher der drei Gründe** aus dem Zielmodell greift, und **welche Kanäle die Meldung
bekommen haben — und welche nicht, mit Begründung.**

## Ist-Stand (gemessen 2026-08-02)

### Was heute geschrieben wird

`trip_alert.py:721 _append_alert_log(trip_id, changes_count, severity)` schreibt je Meldung:

```json
{"trip_id": "...", "sent_at": "<ISO-UTC>", "changes_count": 3, "severity": "MODERATE"}
```

Drei Schreibstellen, alle in `trip_alert.py`:

| Zeile | Anlass | severity |
|---|---|---|
| `:323` | Vorhersage-Änderung **und/oder** gerissener Grenzwert | aus `eval_result.severity` |
| `:978` | Radar-/Nowcast-Meldung | fest `"HIGH"` |
| `:1210` | Amtliche Warnung | fest `"MODERATE"` |

### Befund: Der Ortsvergleich protokolliert gar nicht

`compare_alert.py`, `compare_radar_alert.py`, `compare_official_alert.py` schreiben **keinen**
Protokolleintrag (verifiziert: keine Fundstelle außer `logger`-Aufrufen). Ortsvergleich-Alarme
sind heute vollständig unsichtbar.

### Wer liest

Ausschließlich Go, read-only: `internal/store/log.go:54 LoadAlertLog()` →
`GET /api/cockpit/status`, `GET /api/archive/stats`.

Struktur `internal/store/log.go:43-48`:

```go
type AlertLogEntry struct {
    TripID       string `json:"trip_id"`
    SentAt       string `json:"sent_at"`
    ChangesCount int    `json:"changes_count"`
    Severity     string `json:"severity"`
}
```

`encoding/json` ignoriert unbekannte Felder → **additive Erweiterung ist sicher**, solange
die vier bestehenden Felder unverändert bleiben. Fail-soft ist schon da: Bei kaputtem JSON
liefert `LoadAlertLog` eine leere Liste statt eines Fehlers (`:66-72`).

## Warum das die erste Scheibe ist

1. **Messbarkeit.** Die Ausgangsbeobachtung des PO („sechs Wochen keine Gewitter-Warnung")
   ist heute weder belegbar noch widerlegbar. Es gab 107 Meldungen (Juni 76, Juli 31),
   aber nicht, wovon sie handelten. Ohne diese Angabe lässt sich der Erfolg der Scheiben
   #1460–#1463 nicht von ruhigerem Wetter unterscheiden.
2. **Sicherheitsleine für #1461.** Dort werden Meldungen je Kanal bewusst unterdrückt.
   Genau so ein stilles Unterdrücken war der Defekt in **#638**: „Info" bedeutete intern
   `MINOR`, der Filter versendete erst ab `MODERATE` — der Nutzer stellte einen Alarm ein
   und bekam nie einen. Deshalb muss **schon jetzt** vorgesehen sein, eine *Nicht*-Zustellung
   festzuhalten, nicht nur einen Erfolg.

## Related Files

| Datei | Änderung |
|---|---|
| `src/services/trip_alert.py:721` | MODIFY — Signatur und Rumpf von `_append_alert_log` |
| `src/services/trip_alert.py:323/978/1210` | MODIFY — die drei Aufrufstellen |
| `src/services/compare_alert.py` | MODIFY — protokolliert bisher gar nicht |
| `src/services/compare_radar_alert.py` | MODIFY — dito |
| `src/services/compare_official_alert.py` | MODIFY — dito |
| `internal/store/log.go` | ggf. MODIFY — nur falls Go die neuen Felder ausliefern soll |

## Dependencies

- **Upstream:** `corridor_threshold.CorridorHit.metric`, `WeatherChange.metric`,
  `OfficialAlert.hazard`, `NowcastResult` — die Quellen der Wettergröße.
- **Downstream:** Go liest read-only. Keine weiteren Konsumenten.

## Risks & Considerations

1. **Nur additiv.** Vier bestehende Felder unverändert, sonst brechen Cockpit und Archiv.
2. **Bestandsdaten.** Read-Modify-Write; alte Einträge ohne die neuen Felder müssen weiter
   lesbar bleiben (die Go-Seite ist bereits fail-soft).
3. **Zwei Namensräume für Wettergrößen** (`corridor_threshold.py:32`) — die protokollierte
   Bezeichnung muss eindeutig und über beide Namensräume stabil sein, sonst ist das
   Protokoll später nicht auswertbar. Siehe #1455, gleiches Muster wie #1257.
4. **Feldname `trip_id` bei Ortsvergleich-Einträgen** — dort ist die Kennung eine
   Preset-ID. Entweder dasselbe Feld mitbenutzen (Go zählt dann Ortsvergleiche als Touren)
   oder ein zusätzliches Feld. **Designentscheidung für die Spec.**
5. **Mandantentrennung** — mit zwei verschiedenen Nutzern prüfen.
6. **Kein Geheimnis ins Protokoll** — Kanalangaben als Kanalname (`email`/`telegram`/`sms`),
   nie Empfängeradressen.

## Open Questions für die Spec

- [ ] Wie werden Ortsvergleich-Einträge gekennzeichnet, ohne die Go-Zählung zu verfälschen?
- [ ] Ein Eintrag je Meldung mit Kanalliste, oder ein Eintrag je Kanal?
- [ ] Welche Begründungen für eine Nicht-Zustellung sind zu unterscheiden (Ruhezeit,
      Tageslimit, Cooldown, Kanal aus, künftig Kanal-Schwelle)?
