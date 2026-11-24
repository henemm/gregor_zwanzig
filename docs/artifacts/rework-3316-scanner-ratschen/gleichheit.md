# Gleichheitsnachweise (#3316, AC-5, AC-7, AC-8)

Einmaliger Lauf am 2026-11-24. ALT = `origin/main` (per `git show` gesichert), NEU = Arbeitsbaum. Beide Fassungen werden im
selben Prozess geladen und laufen über denselben Baum. Verglichen werden thunder-Funde als
(Datei, Zeile, Regel, Symbol, Detail) inklusive Reihenfolge.

## Einordnung

- Regel D hat im echten Baum 0 Funde, alt wie neu. Diese Gleichheit beweist den Filter NICHT. Den Beweis liefern
  gepflanzte Verstöße (AC-2 im Dauertest und der Trenner-Lauf unten).
- `ALTLASTEN` ist leer, deshalb zusätzlich ein Vergleich mit einem künstlichen Eintrag.
- Zeilentrennung: `_kommentarblock_ueber` bekommt `source.splitlines()` (trennt auch an VT, FF, FS, GS, RS, NEL, LS, PS).
  Der Filter trennt mit `split("\n")`, also gröber: jede `splitlines`-Zeile liegt ganz in einer Filterzeile, Text hinter `#`
  dort liegt auch hinter der ersten `#` hier. Der Trenner-Lauf prüft elf Trenner.
- Filterwort ohne Leerraum und ohne `#`: Zusammenfügen und Ersetzen von `#` durch Leerzeichen kann kein Wort neu bilden.
- Laufzahl: `scan_tree` mit Wurzel `src/` läuft im Test-Lauf der neuen Datei 3-mal (AC-12, Rohlauf, Marker-Lauf), in der
  alten 4-mal; mit Wurzel `tests/` je einmal (gezählt per Hilfs-Plugin, das `scan_tree` umhüllt, Ausgabe am Ende).

## Ausgabe

```
-- thunder: Backend-Bestaende
Rohlauf: 9 Funde
ohne Basislinie: alt 0 / neu 0 / gleich (inkl. Reihenfolge, Zeile, Detail): True
ohne Whitelist: alt 9 / neu 9 / gleich (inkl. Reihenfolge, Zeile, Detail): True
AC-12 Standard: alt 0 / neu 0 / gleich (inkl. Reihenfolge, Zeile, Detail): True
fremder Marker: alt 2 / neu 2 / gleich (inkl. Reihenfolge, Zeile, Detail): True

-- thunder: Basislinie NICHT leer (kuenstlicher Altlast-Eintrag, da ALTLASTEN leer ist)
ohne Whitelist: alt 8 / neu 8 / gleich: True

-- thunder: Regel D auf tests/
alt (A+D, ungefiltert) 0 / neu (D, gefiltert) 0 / gleich: True
besucht 1946, rglob-Soll 1946, geparst 414

-- thunder: gepflanzte Vielfalt je Zeilentrenner, alt ungefiltert gegen neu gefiltert
1540 Dateien, Funde alt 663 / neu 663 / gleich: True
Quelltext direkt (ohne Zeilenende-Umwandlung): 663 mit Fund, davon vom Filter verworfen: 0

-- repo_path: _module_constants alt gegen neu
1946 Dateien, 7986 Konstanten, Abweichungen (Werte oder Schluessel-Reihenfolge): 0
scan_for_hardcoded_repo_paths(tests/): alt 0 / neu 0 / gleich: True

-- user_id: gefiltert gegen ungefiltert
mit Marker-Duldung: alt [] / neu []
ohne Marker-Duldung: alt 8 / neu 8 / gleich (inkl. Reihenfolge): True
   tests/test_loader_requires_user_id.py:63 save_trip(...)
   tests/test_loader_requires_user_id.py:79 get_snapshots_dir(...)
   tests/test_loader_requires_user_id.py:104 load_trip(...)
   tests/test_loader_requires_user_id.py:123 load_trip(...)
   tests/test_loader_requires_user_id.py:159 load_trip(...)
   tests/test_notification_service_requires_identity.py:79 NotificationService(...)
   tests/test_notification_service_requires_identity.py:120 NotificationService(...)
   tests/test_trip_command_processor_requires_user_id.py:26 InboundMessage(...)
Dateien ohne Selbstdatei: 1945 geparst: 732

-- Laufzahl scan_tree (Hilfs-Plugin)
NEU scan_tree-Laeufe mit Wurzel src/: 3
NEU scan_tree-Laeufe mit Wurzel tests/: 1
NEU 121 passed, 2 warnings in 6.58s
ALT scan_tree-Laeufe mit Wurzel src/: 4
ALT scan_tree-Laeufe mit Wurzel tests/: 1
ALT 79 passed, 2 warnings in 13.14s
```
