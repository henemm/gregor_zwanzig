# Mini-Spec: #882 — Email: PAUSE im Footer + SKIP

## Was ändert sich

### 1. `src/services/trip_command_processor.py`
- `_BARE_KEYWORD_MAP`: `"pause" → "pause"` und `"skip" → "skip"` eintragen
- `_VALID_COMMANDS`: `"pause"` und `"skip"` hinzufügen
- Dispatch-Kette (Z. 316–329): `elif key == "pause": return self._apply_pause(trip, value, msg.user_id)` und `elif key == "skip": return self._apply_skip(trip, msg.user_id)` ergänzen
- Kommentar Z. 77 aktualisieren (nicht mehr "Entfernt")

### 2. `src/output/renderers/email/html.py`
- Footer-Block (nach Z. 718, vor WEITER): zwei neue Zeilen einfügen:
  ```
  PAUSE [2d / 12h] – Briefings für Dauer unterbrechen
  SKIP              – Nächstes Briefing überspringen
  ```

## Was darf sich nicht ändern

- `_apply_pause` und `_apply_skip` Methoden: keine Änderung — funktionieren bereits korrekt
- Alle anderen Kommandos und ihre Reihenfolge im Footer
- `skip_next`-Persistenz und Scheduler-Logik

## Acceptance Criteria

**AC-1:** Given eine Briefing-Email, When der Nutzer die Antwort-Kommandos-Sektion liest, Then ist `PAUSE [2d / 12h]` dort aufgeführt

**AC-2:** Given eine eingehende Email-Antwort mit Text `SKIP`, When der Reply-Handler sie verarbeitet, Then wird `skip_next=True` gesetzt und eine Bestätigungs-Email verschickt

**AC-3:** Given `skip_next=True`, When das planmäßige Briefing ausgelöst wird, Then wird es übersprungen und `skip_next` auf `False` zurückgesetzt (bereits im Scheduler implementiert — Regressions-Check)

## Manuelle Test-Schritte

1. Staging-App öffnen → Trip-Briefing-Mail öffnen → Footer-Block prüfen: PAUSE und SKIP vorhanden
2. Reply mit `SKIP` senden → Bestätigungsmail kommt an
3. Nächster Briefing-Slot: kein Versand, Flag danach weg

## Inline-Test (wird während Implementierung geschrieben)

- [ ] `test_pause_keyword_routed`: `PAUSE 2d` wird zu `_apply_pause` dispatcht
- [ ] `test_skip_keyword_routed`: `SKIP` wird zu `_apply_skip` dispatcht, `skip_next=True` im gespeicherten Trip
