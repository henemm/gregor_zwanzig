# Mini-Spec: #1048 F005 — absturzsicherer Name-Fallback

## Was ändert sich
- `src/services/official_alerts/base.py`: In `get_official_alerts_for_location` der Fallback zur Namens-Ermittlung nutzt bei Ausnahme **keinen Attributzugriff** mehr. Statt `repr(source.__class__.__name__)` (kann bei sabotiertem `__getattribute__`/`__class__` selbst werfen) ein statischer String, z. B. `"unbekannte Quelle"`.
- Damit gilt die Docstring-Garantie „wirft selbst nie" absolut, auch bei einer bösartig manipulierten Quelle.

## Was darf sich nicht ändern
- Normalverhalten: bei intakten Quellen wird weiterhin `str(source.name)` als Name geloggt.
- Fail-soft-Semantik: eine ausgefallene Quelle blockiert nie die anderen; Rückgabe unverändert.
- Kein anderes Modul, keine Signatur-Änderung.

## Manuelle Test-Schritte
1. Eine Quelle registrieren, deren `name`-Property UND jeder Attributzugriff eine Exception wirft.
2. `get_official_alerts_for_location(lat, lon)` aufrufen → kein Absturz, andere Quellen laufen, Warnung mit statischem Fallback-Namen geloggt.

## Inline-Test (wird während Implementierung geschrieben)
- [ ] Test: hostile Source (`name` wirft + `__getattribute__` sabotiert) → `get_official_alerts_for_location` wirft nicht, liefert Alerts der intakten Quellen, loggt Warnung. Kein Mock — echtes hostiles Objekt.
