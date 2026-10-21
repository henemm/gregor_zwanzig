# ADR-0094: Zwei Test-Schichten: deterministischer Kern und Live-E2E

- **Status:** Akzeptiert (rückwirkend dokumentiert 2026-10-21 — gelebter Stand seit Commit `ad637d57c`, „Test-Zweischicht", PO-go 2026-07-09)
- **Datum:** 2026-10-21
- **Bezug:** CLAUDE.md §„Test-Politik: Zwei Schichten", Commit `ad637d57c` (2026-07-09), Issue #1477 (Breitlauf-Sperre), `pyproject.toml` `[tool.pytest.ini_options].markers`, `tests/conftest.py` (Offline-Fixture, `live`-Marker), Commit `f7c542cc0` (pytest-socket, #1196/#1337), `docs/reference/gates_und_ratschen.md`; löst ADR-0006 Entscheidung Punkt 1 teilweise ab

## Kontext

ADR-0006 Punkt 1 (ADR-0006:18-19) verlangt für E-Mail- und API-Verhalten **echte** Aufrufe:
„E-Mail-Tests senden echte Mails … API-Tests machen echte API-Calls." Gelebt wird seit dem
2026-07-09 etwas anderes (Commit `ad637d57c`, PO-go): eine **Zwei-Schichten-Politik**. Der
Commit-Gate-Testlauf kommt ohne Netz aus. Echte Aufrufe laufen nur noch in einer markierten
Live-Schicht.

Zwei Befunde haben diese Trennung erzwungen:
- Ein unmarkierter Test reicht für **echten Versand an Produktiv-Empfänger** (#1477). Deshalb ist
  `uv run pytest` ohne benannte Testdateien gesperrt.
- Ein Testlauf, der live gegen Open-Meteo geht, erschöpft das Rate-Limit der Server-IP. Deshalb
  bekommt jeder nicht als `live` markierte Test in `tests/conftest.py` die Offline-Fixture.

ADR-0006 wurde dabei nicht fortgeschrieben, nur der Bezug-Kopf auf „Zwei Schichten" umbenannt
(Doku-Audit 2026-10, Punkt 1b).

## Entscheidung

1. **Kern-Schicht (deterministisch).** Sie läuft ohne Netz, ohne Live-Dienste und ohne echte
   Postfächer. **Aufgezeichnete** echte API- und Mail-Daten als versionierte Fixtures sind
   ausdrücklich erwünscht. Der Kern läuft bei jedem Testlauf und ist das Commit-Gate. Er muss
   zu 100 % grün sein. Ein roter Test wird sofort gefixt oder gelöscht, wenn er veraltetes
   Verhalten prüft. Er bleibt nie als „vorbestehend rot" liegen. Den Netz-Ausgang bewacht
   pytest-socket (`--disable-socket`, `f7c542cc0`).
2. **Live-E2E-Schicht.** Hier laufen echte API-Calls, echte Staging-Mails über IMAP und
   Playwright gegen Staging. Die Tests tragen die Marker `live`, `email` oder `staging`
   (`pyproject.toml`). Sie laufen nur in `/e2e-verify` bzw. beim Deploy. Ein Flake wird
   wiederholt. Erst reproduzierbares Scheitern ist ein Befund (#1199 bzw. #1196).
3. **Was bleibt aus ADR-0006 unverändert:**
   - das **Mock-Theater-Verbot**: `Mock()`, `patch()` und `MagicMock`, die nur die eigene Annahme
     zurückspiegeln, beweisen nichts;
   - das Verbot von Dateiinhalt-Checks als Verhaltensnachweis (Ausnahme `# doc-compliance-test`);
   - die Pflicht zum Bug-Nachweis aus Nutzersicht (rot vor Fix, grün danach). Dieser Test liegt
     in der Live-Schicht, wenn er Staging braucht, sonst im Kern;
   - ADR-0006 Punkt 2 vollständig: E2E gegen Staging nach dem Push, nie durch lokalen Neustart.
     Dazu gehören das Prod-Deploy-Hard-Gate mit `.claude/e2e_verified/<sha>.json` und der
     Post-Deploy-Selftest.
4. **Grenze zwischen Fixture und Mock:** Eine Fixture aus **aufgezeichneten echten** Daten ist
   kein Mock-Theater. Sie spiegelt die reale Antwort der Gegenseite, nicht die Annahme des
   Testautors. Erfundene Antworten bleiben Mock-Theater.

## Verworfene Alternativen

- **ADR-0006 wörtlich durchsetzen (alle Mail- und API-Tests echt):** verworfen. Echte Aufrufe im
  Commit-Gate machen den Kern netzabhängig und nicht deterministisch. Sie belasten das
  Provider-Kontingent. Sie haben echten Versand an Produktiv-Empfänger möglich gemacht (#1477).
- **Mocks im Kern zulassen:** verworfen. Damit kehrte genau das falsche Sicherheitsgefühl zurück,
  gegen das ADR-0006 geschrieben ist. Der Kern nutzt aufgezeichnete echte Daten, keine erfundenen
  Antworten.

## Konsequenzen

- **Positiv:**
  - Der Commit-Gate-Lauf ist schnell, deterministisch und ohne Außenwirkung.
  - Echtes Verhalten wird weiter nachgewiesen, aber an einem kontrollierten Ort, nämlich gegen
    Staging nach dem Push.
- **Negativ / Preis:**
  - Fixtures können veralten, wenn sich die Gegenseite ändert. Das fängt nur die Live-Schicht.
  - Ein grüner Kern ist kein Verhaltensnachweis gegen echte Dienste. „E2E bestanden" bleibt an
    Staging und den Mail-Validator gebunden.
- **Folgepflichten:**
  - Neue Tests mit Netz- oder Versandwirkung tragen einen Live-Marker.
  - Die Mechanik der Breitlauf-Sperre und der Ausnahmen steht in
    `docs/reference/gates_und_ratschen.md`.
