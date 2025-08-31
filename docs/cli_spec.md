# CLI-Spezifikation

## Befehl
python -m src.app.cli [OPTIONS]

## Optionen
- `--report {evening,morning,alert}`: Berichtstyp. Wenn fehlt ⇒ aus Konfiguration lesen.
- `--channel {email,none}`: Ausgabekanal. `none` = keine Nachricht senden (nur Console). Wenn fehlt ⇒ Konfiguration.
- `--dry-run`: niemals senden, nur Console/Debug.
- `--config <pfad>`: explizite Config-Datei (INI/TOML). Wenn fehlt ⇒ Standardpfad (z. B. `./config.ini`).
- `--debug {info,verbose}`: Debug-Ausgabegrad für Console (E-Mail bekommt das definierte Debug-Subset).

## Konfigurations-Priorität
1) CLI-Argumente
2) Environment-Variablen
3) Config-Datei (z. B. `config.ini`)

## Debug-Konsistenz
- Eine zentrale Debug-Struktur (DebugBuffer) sammelt standardisierte Zeilen/Abschnitte.
- Console gibt **alles** aus (je nach `--debug`), E-Mail hängt das fest definierte Subset an.
- Keine Abweichungen im Wortlaut zwischen E-Mail-Debug und Console-Debug-Subset.

## Beispiele
python -m src.app.cli --report evening
python -m src.app.cli --report morning --channel none
python -m src.app.cli --report alert --dry-run --debug verbose
