---
entity_id: fix-2757-staging-register-id
type: fix
created: 2026-11-02
status: draft
workflow: fix-2757-staging-register-id
issue: 2757
---

# Mini-Spec: fix-2757-staging-register-id

## Ausgangslage
Seit #2194 (E-Mail als Login-Kennung) vergibt `POST /api/auth/register` bei Nicht-Testkonten
die Nutzer-ID selbst (`u-<8hex>`) und ignoriert den mitgeschickten `username`.
`.claude/tools/staging_befehl_pruefen.py` (`StagingApi.registriere`, Z. 358–377) arbeitet aber mit
dem selbst gewählten Namen `gzp-<tag>` weiter → `verify-email/staging-token` liefert
`HTTP 404 (unknown user)`. Der einzige Prüfweg für E-Mail-Befehle über den echten Mail-Eingang ist kaputt.
Die CI blieb grün, weil der Fake in `tests/tdd/test_staging_befehl_pruefweg.py` (`_antwort`, Z. ~957)
das Konto unter dem gesendeten Namen anlegt und die zurückgegebene `id` nirgends prüft.

## Was ändert sich
- `registriere` übernimmt die `id` aus der Register-Antwort als Nutzerkennung für alle Folgeschritte
  (staging-token, verify-email, Login, Konto-Löschen). Fehlt die `id` in der Antwort → klare `StagingFehler`-Meldung.
- Der Fake in `test_staging_befehl_pruefweg.py` bildet das echte Server-Verhalten nach: Register legt das Konto
  unter einer eigenen, vom gesendeten Namen verschiedenen `u-…`-ID an und gibt diese zurück.
- Aufräumen auf Staging: das verwaiste Konto mit E-Mail `gregor-test+021545-49c8ba79@henemm.com` wird gelöscht.

## Was darf sich nicht ändern
- Reihenfolge Helfer-Login → register → staging-token → verify-email → login → … → delete bleibt.
- Genau ein Registrierungsversuch; bei 429 kein Löschversuch (bestehende Tests bleiben grün).
- Keine Änderung an Produktiv-Code (Go/Python-Core) und an Prod-Daten.

## Acceptance Criteria
**AC-1:** Given der Staging-Server vergibt bei der Registrierung eine eigene ID `u-…`, When `staging_befehl_pruefen` einen Wegwerf-Nutzer anlegt, Then verwenden staging-token, verify-email, Login und Konto-Löschen genau diese ID und nicht den selbst gewählten Namen `gzp-…`.
**AC-2:** Given der Test-Fake antwortet wie der echte Server mit einer abweichenden ID, When das Werkzeug den gesendeten Namen weiterverwendet (alter Code), Then wird mindestens ein Test in `test_staging_befehl_pruefweg.py` rot.
**AC-3:** Given die Register-Antwort enthält keine `id`, When das Werkzeug registriert, Then bricht es mit einer verständlichen Fehlermeldung ab, ohne mit einem erfundenen Namen weiterzuarbeiten.
**AC-4:** Given Staging, When `staging_befehl_pruefen --szenario alle` läuft, Then laufen alle Szenarien (A, B, C, D, D2) durch und der Wegwerf-Nutzer ist danach gelöscht.
**AC-5:** Given das verwaiste Staging-Konto `gregor-test+021545-49c8ba79@henemm.com`, When aufgeräumt wird, Then existiert es auf Staging nicht mehr.

## Manuelle Test-Schritte
1. `uv run pytest tests/tdd/test_staging_befehl_pruefweg.py` — grün mit Fix, rot mit altem `registriere`.
2. Gegen Staging: `--szenario alle` ausführen, PASS für alle Szenarien, kein Restkonto.
3. Staging-Nutzerliste: Konto mit obiger E-Mail ist weg.

## Inline-Test (wird während Implementierung geschrieben)
- [ ] Fake vergibt eigene `u-…`-ID; Test prüft, dass Folgeaufrufe diese ID tragen (AC-1/AC-2)
- [ ] Test: Register-Antwort ohne `id` → Abbruch mit Meldung (AC-3)
