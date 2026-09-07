# ADR-0062: Der Python-Core authentifiziert den Aufrufer selbst — gemeinsames Geheimnis statt Netzwerk-Vertrauen

- **Status:** Akzeptiert (Issue #2142, Blocker aus Epic #2138)
- **Datum:** 2026-09-07
- **Bezug:** löst [ADR-0015](0015-dual-stack-zielarchitektur.md) **Regel 2** in dem Punkt ab,
  dass der Python-Core „keine eigene Auth" bekommt (alle übrigen Regeln von ADR-0015 bleiben
  unverändert gültig); ergänzt [ADR-0030](0030-session-auth-hmac-cookie.md)/[ADR-0060](0060-dauerhafte-anmeldung-mit-widerrufsliste.md)
  (Nutzer-Auth am Go-Rand) um die Dienst-zu-Dienst-Ebene;
  Spec `docs/specs/bugfix/core_shared_secret_auth.md`,
  Kontext `docs/context/fix-2142-core-auth-shared-secret.md`

## Kontext

ADR-0015 hält als Regel 2 fest: „Der Python-Core bekommt keine eigene Auth und keine neuen
direkt exponierten Endpoints; er bleibt hinter dem Go-Proxy." Die Zusicherung dahinter war
**Netzwerk-Isolation**: Wer den Core nicht erreichen kann, braucht dort auch keine Auth.

Issue #2142 zeigt, dass diese Zusicherung nicht dort steht, wo sie wirken müsste. Das gesamte
Anti-Spoofing steckt in einer einzigen Go-Funktion (`internal/handler/proxy.go`,
`appendUserID`), die eine client-gelieferte `user_id` durch die authentifizierte ersetzt. Wer
den Python-Core direkt anspricht — ein beliebiger lokaler Prozess auf demselben Server —,
umgeht diese Stelle vollständig: mit frei gewählter `?user_id=` liest er fremde Daten,
verschickt fremde Briefings und löst über `POST /api/internal/telegram-webhook` gefälschte
Telegram-Kommandos für ein fremdes Konto aus.

Vorab gemessen: Beide Dienste binden heute nur auf Loopback (`ss -ltnp`), der Angriff ist also
nicht aus dem Netz erreichbar. Das entwertet den Befund nicht — die Loopback-Bindung steht
ausschließlich in der systemd-Unit (Repo `henemm-infra`, nicht im Anwendungs-Repo). Sie ist
damit eine **Betriebszusicherung, keine Code-Zusicherung**, und genau die Annahme, die
Epic #2138 für den Mehrnutzer-Betrieb ausräumt.

## Entscheidung

Der Python-Core **authentifiziert seinen Aufrufer selbst**. Go und Python teilen ein
gemeinsames Geheimnis aus derselben Umgebungsvariablen `GZ_CORE_SHARED_SECRET`; Go sendet es
bei jeder Anfrage an den Core als Header `X-GZ-Core-Auth` mit, der Core erzwingt es auf jedem
Endpoint.

Damit gilt ADR-0015 Regel 2 in ihrem Auth-Teil nicht mehr. Was **unverändert** bleibt: der
Python-Core bekommt weiterhin **keine neuen direkt exponierten Endpoints** und bleibt hinter
dem Go-Proxy; die Nutzer-Auth (Sitzungen, Mandantentrennung) bleibt vollständig in Go. Die
neue Prüfung ist eine **Dienst-zu-Dienst-Auth**, keine Nutzer-Auth — sie beantwortet
ausschließlich die Frage „stammt diese Anfrage von unserer Go-API?".

Daraus folgende Regeln:

1. **Go sendet, nicht die einzelne Aufrufstelle.** Ein umhüllender Transport auf
   `http.DefaultTransport` (`internal/coreauth`) setzt den Header — gefiltert auf **Host und
   Port** aus `cfg.PythonCoreURL`. Keine der 20 Aufrufstellen wird angefasst, die 21. ist
   automatisch mit abgedeckt. An jedes andere Ziel (Open-Meteo, Google Maps, Komoot,
   BetterStack) geht das Geheimnis **nicht** mit.
2. **Installationsreihenfolge ist eine Zusicherung.** `coreauth.Install` läuft **vor**
   `egress.Install`. Der Egress-Wächter stellt bei `Uninstall` den vorgefundenen Transport
   zeiger-identisch wieder her; umgekehrt installiert verschwände der Auth-Header dabei still.
3. **Python erzwingt in einer Middleware, nicht im `lifespan`.** Der `lifespan` läuft in 64 von
   66 Testdateien nicht mit — eine Prüfung dort wäre für fast die ganze Testsuite unwirksam.
   Die Durchsetzung sitzt in einer `@app.middleware("http")` auf Modulebene.
4. **Fail-closed, niemals offen.** Fehlender oder falscher Header → **401**. Geheimnis im
   Prozess gar nicht konfiguriert → **503** statt unauthentifizierter Durchlass (dasselbe
   Muster wie `telegram_webhook.go`, „webhook not configured"). Ein Fail-Fast beim Start
   sichert die Go-Seite zusätzlich ab (`config.ValidateCoreSharedSecret`, Mindestlänge 32
   Zeichen, Ausnahme nur für den isolierten CI-Stack).
5. **Genau eine Ausnahme: `/health`.** Go ruft diesen Pfad selbst ohne Header ab und
   `ci-stack.sh` pollt ihn als Boot-Prüfung, bevor überhaupt etwas konfiguriert sein kann. Der
   Endpoint liefert keine Nutzerdaten. Jede weitere Ausnahme braucht ein eigenes ADR.
6. **Defense in Depth am Telegram-Webhook.** Das gemeinsame Geheimnis allein genügt dort
   nicht: Wer es kennt, könnte sonst Kommandos für ein fremdes Konto auslösen. Der Core prüft
   deshalb zusätzlich `X-Telegram-Bot-Api-Secret-Token` gegen `TELEGRAM_WEBHOOK_SECRET`; Go
   reicht dieses Secret beim Weiterleiten mit.
7. **Kein Testlauf-Bypass.** Die Testsuite wird zentral mit dem gültigen Header versorgt
   (autouse-Fixture in `tests/conftest.py`), die Prüfung selbst bleibt scharf. Ein eigener
   Test fragt bewusst ohne Header an und erwartet 401 — ohne ihn wäre die Fixture der blinde
   Fleck.

## Verworfene Alternativen

- **Alles beim Alten lassen und auf die Loopback-Bindung vertrauen** — verworfen: Die Bindung
  steht in einem fremden Repo und ist damit keine Zusicherung dieses Codes. Netzwerk-Isolation
  als einziger Schutz ist genau die Annahme, die Epic #2138 ausräumt.
- **Ein Bind-Guard, der `127.0.0.1` im Startpfad erzwingt** (Punkt 2 des Issues) — als eigenes
  Folge-Ticket **abgetrennt**, nicht verworfen. Es gibt kein `uvicorn.run()` im Repo; die
  saubere Bauform wäre ein repo-eigener Einstiegspunkt plus Umstellung der systemd-Units im
  Repo `henemm-infra` — eine Abhängigkeit über Repo-Grenzen hinweg. Mit scharfem Geheimnis ist
  der Bind-Guard nur noch zweite Verteidigungslinie.
- **Ein gemeinsames Client-Paket in Go statt eines umhüllenden Transports** — verworfen: 17
  eigenständige Clients mit 17 unterschiedlichen Timeouts müssten umgebaut werden, jeder
  Umbau eine Gelegenheit, ein Timeout zu verfälschen. Einzelpflaster an den 20 Aufrufstellen
  scheitern am selben Punkt und bieten keinen strukturellen Schutz gegen die 21. Stelle.
- **Prüfung im `lifespan`-Hook statt in einer Middleware** — verworfen, weil messbar
  wirkungslos für 64 von 66 Testdateien. Dasselbe Muster hat schon einmal falsches Grün
  geliefert.
- **Ein Soft-Enforce-Schalter für den Übergang** — verworfen: Die feste Reihenfolge „erst Go
  sendet, dann Python erzwingt" lässt gar kein Fenster entstehen, in dem ein Schalter nötig
  wäre. Er wäre außerdem ein Fremdkörper (`src/app/config.py` hat sich bewusst gegen solche
  Ausnahmen in `Settings` entschieden) und müsste später wieder ausgebaut werden.
- **mTLS oder signierte Anfragen zwischen den Prozessen** — verworfen für diesen Schnitt:
  deutlich höherer Betriebsaufwand (Zertifikatsverwaltung, Rotation) ohne zusätzlichen Schutz
  gegen das hier behandelte Angriffsbild. Beide Prozesse laufen auf demselben Host, der
  Transportweg ist nicht das Risiko.

## Konsequenzen

- **Betriebsschritt vor jedem Code-Merge:** `GZ_CORE_SHARED_SECRET` muss von Hand in die
  Staging- **und** die Prod-`.env` eingetragen werden. `deploy-gregor-prod.sh` fasst diese
  Dateien nicht an — ein vergessener Eintrag zeigt sich nicht beim Deploy-Lauf, sondern erst
  beim nächsten Prozessneustart: die Go-API startet dann nicht mehr (Fail-Fast). Entlastend:
  Go und Python lesen je Umgebung dieselbe Datei, die beiden Seiten können nicht auseinanderlaufen.
- **Grenze des Schutzes:** Das Geheimnis schützt gegen einen beliebigen lokalen Prozess, nicht
  gegen einen Angreifer, der die `.env` selbst lesen kann — der hat ohnehin alle dort
  hinterlegten Zugangsdaten.
- **Fernwirkung:** Ein künftiger Go-Client mit eigenem `Transport` verliert den Header still.
  Dagegen steht der Sweep-Test über `chi.Router.Walk()`, der alle registrierten Routen
  selbsttätig aufzählt und an einem Fake-Python-Core misst, was dort tatsächlich ankommt.
- **Bereits laufende Prozesse** ändern ihr Verhalten nicht rückwirkend — der Schutz wirkt erst
  beim nächsten Prozessstart nach dem Eintragen des Geheimnisses.
