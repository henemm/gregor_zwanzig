# ADR-0079: Der Betriebsstatus-Endpunkt wird per Maschinen-Token geschützt, nicht per Loopback-Ausnahme oder Admin-Session

- **Status:** Akzeptiert
- **Datum:** 2026-09-28
- **Bezug:** GitHub-Issue #2155 (Scheibe S2, Epic #2138), Spec
  `docs/specs/modules/admin_rolle_s2_status_token.md`, baut auf ADR-0078
  (Admin-Rolle über ENV-Liste) und ADR-0075 (Go-Status bleibt Aggregat)

## Kontext

`GET /api/scheduler/status` ist seit jeher ohne Anmeldung erreichbar und liefert
globale Betriebsdaten (Job-Zeiten, Fehlertexte, Zählwerte über alle Nutzer). Der externe
Monitor `henemm-infra/scripts/check-gregor20.sh` fragt ihn alle 5 Minuten ab und wertet
Job-Zeiten und Health-Blöcke aus — er läuft als Cron-Job auf dem Server, ohne Nutzer,
ohne Browser, ohne Sitzung. Diese Offenheit soll enden, ohne den Monitor zu brechen.

Zwei naheliegende Alternativen zur Anmeldepflicht wurden geprüft und verworfen (siehe
unten). Es fehlte bislang ein Mechanismus, der einem anmeldungslosen, aber
vertrauenswürdigen Aufrufer Zugriff gewährt, ohne die Anmeldepflicht für alle anderen
aufzuweichen.

## Entscheidung

1. **Ein geteiltes Geheimnis im Header `X-GZ-Status-Token`** schützt ausschließlich
   `GET /api/scheduler/status`. Konfiguriert über `GZ_STATUS_TOKEN` (Config-Feld
   `StatusToken`, Muster `AdminUserIDs`). Der Monitor schickt das Token bei jedem
   Aufruf mit.
2. **Vergleich sha256 beider Seiten + `subtle.ConstantTimeCompare`.** Beide Werte
   werden vor dem Vergleich gehasht (feste Länge, kein Seitenkanal über die
   Rohlänge), der Hash-Vergleich läuft konstantzeitig.
3. **Fail-closed.** Ist kein Token konfiguriert, ist der Endpunkt für JEDE Anfrage
   gesperrt — kein Rückfall auf „öffentlich wie bisher". Ein Start ohne
   `GZ_STATUS_TOKEN` erzeugt einen einmaligen Hinweis im Log, keinen Absturz.
4. **Der Prüfort ist eine eigene Route-Middleware** (`RequireStatusToken`), angewandt
   per `r.With(...)` exakt auf diese eine Route — kein Sonderfall in der globalen
   `AuthMiddleware`, kein zweiter Weg, wie der Endpunkt „öffentlich" verlassen werden
   könnte.
5. **Eine gültige Nutzer-Sitzung ersetzt das Token nicht.** Der Endpunkt bleibt
   bewusst außerhalb des Sitzungsmodells — er beantwortet keine nutzerbezogene Frage
   (dafür gibt es jetzt `GET /api/scheduler/status/me`, s. u.), sondern eine
   Betriebsfrage, die nur der Betreiber-Monitor stellt.
6. **`GET /api/scheduler/status/me` ist ein separater, sitzungsauthentifizierter
   Endpunkt** für die Konto-Karte — kein Sonderfall der token-geschützten Route,
   sondern ein eigener Pfad mit eigenem, auf den aufrufenden Nutzer verengtem DTO.
   Das verletzt ADR-0075 Punkt 5 nicht: Dort ist festgehalten, dass der (token- oder
   admin-lesbare) **Aggregat**-Status niemals Nutzerkennungen führen darf. `/status/me`
   führt keine fremden Kennungen — es liefert einem angemeldeten Nutzer ausschließlich
   seine eigenen Daten, adressiert implizit über seine eigene Sitzung, wie jeder andere
   nutzerbezogene Endpunkt der API auch.

## Verworfene Alternativen

- **Loopback-Ausnahme (Anfragen von `localhost` bleiben ungeschützt).** Verworfen: Die
  SvelteKit-Durchleitung (`frontend/.../api/[...path]/+server.ts`) erreicht die Go-API
  ebenfalls über `localhost` — ein Loopback-Kriterium kann den externen Cron-Monitor
  nicht von einer ganz gewöhnlichen, aus dem Browser kommenden Anfrage unterscheiden.
  Der bestehende `localhost_guard.go` ist aus genau diesem Grund für andere Zwecke
  gebaut (lehnt `X-Forwarded-*` ab) und für diesen Fall ungeeignet.
- **Admin-Session (der Monitor meldet sich mit einem Admin-Konto an).** Verworfen: Ein
  Cron-Skript, das eine Session offen hält oder bei jedem Lauf neu einloggt, bräuchte
  ein Passwort im Klartext auf dem Server, Cookie-Handling und wäre von der
  Session-Widerrufsliste (ADR-0060) abhängig — ein Widerruf oder eine
  Session-Ablauf-Änderung würde den Monitor unbeabsichtigt lahmlegen. Ein reines
  Maschinen-Geheimnis ohne Sitzungs-Semantik ist die einfachere, robustere Grenze
  zwischen „Betreiber-Werkzeug" und „Nutzer-Feature" — dieselbe Trennung, die
  ADR-0078 zwischen Admin-Rolle (Menschen mit Sitzung) und Betrieb zieht.
- **`GET /api/scheduler/status` einfach hinter `RequireAdmin` legen.** Verworfen aus
  demselben Grund wie die Admin-Session-Alternative: Der Monitor ist kein
  angemeldeter Nutzer und soll keiner werden müssen, nur um weiter zu funktionieren.

## Konsequenzen

- **Positiv:** Der Status-Endpunkt ist nicht mehr öffentlich lesbar, ohne dass der
  Monitor eine Sitzung führen muss. Die Grenze ist eng (eine Route, ein Header, ein
  Konfigurationswert) und dadurch leicht zu prüfen und zu rotieren (ein Wert in zwei
  `.env`-Dateien ändern, kein Migrationscode).
- **Negativ / Preis:** Ein weiteres Geheimnis muss verteilt und geheim gehalten werden
  (Prod- und Staging-`.env`, Cron-User-lesbar). Rollout-Reihenfolge ist strikt: Der
  Monitor muss das Token schon senden, BEVOR die Route geschützt wird, sonst entsteht
  ein blinder Fleck im Monitoring (Readiness-Verstoß).
- **Folgepflichten:** Jede künftige Änderung an `/api/scheduler/status` (neue Felder,
  neue Konsumenten) muss diese Trennung respektieren — ein Konsument mit Nutzerkontext
  gehört auf `/status/me` oder eine künftige Admin-Route, niemals auf die
  token-geschützte Route. Token-Rotation braucht keinen Code, nur einen neuen Wert in
  beiden `.env`-Dateien plus Dienst-Neustart (kein Hot-Reload).
