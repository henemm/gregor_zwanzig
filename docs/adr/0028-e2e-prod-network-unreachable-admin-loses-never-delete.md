# ADR-0028: Prod-Datenbaum wird für E2E netzwerkseitig unerreichbar; `admin` verliert den NEVER_DELETE-Schutz aus #1265

- **Status:** Akzeptiert (PO-Freigabe 2026-07-16)
- **Datum:** 2026-07-16
- **Bezug:** GitHub-Issue #1284, Spec `docs/specs/modules/fix_1284_admin_prod_testdata.md`,
  Kontext `docs/context/fix-1284-e2e-leichen-prod.md`. Verändert die Schutzliste aus
  `docs/specs/modules/issue_1265_prod_testdata_cleanup.md` (dort `NEVER_DELETE` inkl. `admin`).

## Kontext

Playwright-E2E-Läufe schreiben seit Monaten unbemerkt in den Produktiv-Datenbaum: die
lokale `baseURL` (`localhost:4173`) besteht den bestehenden Prod-URL-Guard, proxyt aber über
`vite.config.ts` gegen Port 8090 (Prod-Go-Server), weil der Guard nur den Hostnamen der
baseURL prüft, nicht das tatsächliche API-Ziel. Login-Defaults in `helpers.ts`/`global.setup.ts`
fallen beide auf `admin`/`test1234` zurück, sobald die passenden Env-Variablen nicht gesetzt
sind (zwei verschiedene Variablennamen, keine davon wird im CI/lokalen Lauf konsistent
exportiert). Ergebnis: 153 Vergleichs-Abos mit `@example.com`-Empfängern im Konto `admin`,
133 davon täglich um 06:00 fällig. `admin` überlebte die #1265-Bereinigung, weil es dort
explizit als „echtes Konto" in `NEVER_DELETE` geführt wurde — der Name enthält kein „test"/„tdd"
und wird auch von `IsTestUserID` nicht erkannt. Zwei Reparaturen konkurrierten: pro-Spec-Teardown
in den 13 betroffenen Test-Dateien, oder eine Isolation des Datenbaums über `GZ_DATA_DIR`.

## Entscheidung

Wir schließen das Leck an der Netzwerk-Wurzel statt an den einzelnen Test-Spezifikationen:
Das Proxy-Ziel für `/api` in `frontend/vite.config.ts` zeigt künftig standardmäßig auf den
dauerhaft laufenden Staging-Go-Server (Port 8091) statt auf Prod (Port 8090), gesteuert über
eine geteilte Konstante (`frontend/e2e/apiProxyTarget.ts`), die sowohl `vite.config.ts` als
auch der erweiterte `prodUrlGuard.ts` importieren. Ein expliziter Override
(`GZ_E2E_API_PROXY_TARGET`) bleibt möglich, ist aber nicht der Default. Damit landet jeder
Standard-`npx playwright test`-Lauf unabhängig von Spec-Auswahl und Login-Konto auf Staging.

Zusätzlich verliert das Konto `admin` seinen `NEVER_DELETE`-Status aus #1265: der gesamte
`data/users/admin/`-Baum (inklusive `user.json`) wird als Testmuell gelöscht (PO-Entscheid
2026-07-16, „Ski Tirol" eingeschlossen). Ohne `user.json` fällt `admin` aus `ListUserIDs()`
und wird vom Scheduler nicht mehr aufgerufen — kein Login mehr unter `admin`/`test1234`
möglich, was als erwünschter Nebeneffekt gilt, nicht als Kollateralschaden.

## Verworfene Alternativen

- **Pro-Spec-Teardown (`afterAll`/`afterEach`) in den 13 betroffenen Test-Dateien** — PO
  verworfen: zerbrechlich, ein abgebrochener Lauf räumt nicht auf, jede neue Spec muss es
  erneut korrekt implementieren. Löst zudem nicht das Grundproblem (Prod bleibt erreichbar).
- **Isolation über `GZ_DATA_DIR`** — technisch nicht tragfähig: `scheduler_dispatch_service.py:141`
  hardcodet `data_root = "data"` und ignoriert die Variable; der Dispatch-Pfad, der die
  Compare-Presets versendet, würde weiterhin gegen den Prod-Baum laufen, egal welcher
  Datenbaum dem restlichen Prozess vorgegaukelt wird.
- **`playwright.config.ts` komplett auf Remote-Staging umstellen (baseURL ändern)** — verworfen:
  kappt den lokalen `webServer`/Build-Schritt; der Default-Lauf testet dann nicht mehr den
  lokal gebauten Stand. Größerer Verhaltensbruch als nötig, um das Leck zu schließen.
- **`admin` in `NEVER_DELETE` belassen, nur Daten unter dem Konto leeren** — verworfen:
  `admin` bliebe als 0-Presets-Konto bestehen und bleibt von der `IsTestUserID`-Heuristik
  abhängig, die den Namen nicht erkennt — das Loch würde sich beim nächsten E2E-Lauf wieder
  füllen, ohne dass ein struktureller Fix greift.

## Konsequenzen

- **Positiv:** Der Standard-E2E-Lauf kann keinen Prod-Schaden mehr anrichten, unabhängig
  davon, welche Spec läuft oder unter welchem Konto sie sich einloggt. Der Fix sitzt an
  einer einzigen Stelle (geteilte Konstante) statt verteilt über 13 Testdateien.
- **Negativ / Preis:** Wer lokal bewusst gegen einen anderen Port testen will (z.B. echtes
  Prod-Debugging), muss aktiv `GZ_E2E_API_PROXY_TARGET` setzen. Ein künftig neu angelegtes
  Konto namens `admin` wäre wieder ungeschützt, weil `IsTestUserID` das Profil-Flag
  `is_test_user` bewusst nicht liest (Known Limitation, unverändert seit #1265).
- **Folgepflichten:** Der Wurzel-Fix deckt nur den Playwright-Pfad ab. Neun Python-Tests
  zeigen weiterhin per Default auf Prod-Ports (`GO_BASE=localhost:8090` u.ä.) — das ist
  Testsuite-Hygiene mit bestehender Heimat (#1196), nicht Teil dieser Entscheidung.
  `start-preview.sh` lädt weiterhin die Prod-`.env` samt Live-Secrets in den Testprozess —
  eigenes Sicherheitsrisiko, eigenes Issue, hier nicht behoben.
