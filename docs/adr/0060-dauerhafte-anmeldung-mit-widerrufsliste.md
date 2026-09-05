# ADR-0060: Dauerhafte Anmeldung mit dateibasierter Liste gültiger Sitzungen (löst ADR-0030 ab)

- **Status:** Akzeptiert
- **Datum:** 2026-09-05
- **Bezug:** löst [ADR-0030](0030-session-auth-hmac-cookie.md) ab · `internal/middleware/auth.go`, `internal/store/sessions.go`, `frontend/src/lib/auth.ts`, `docs/reference/api_contract.md`, Issue #2129 (Scheibe 2 von #2127)

## Kontext

Die Anmeldung lief nach exakt 24 Stunden ab, hart ab dem Login und ohne
Verlängerung bei Nutzung (`MaxAge: 86400` an sechs Ausstellungsstellen,
Prüfung `time.Now().Unix()-ts > 86400`). Auf einer mehrtägigen Tour heißt das:
jeden Tag neu anmelden, bei schlechtem Netz. Der PO hat am 2026-09-05
entschieden, dass die Anmeldung dauerhaft bis zum Abmelden gilt — unter der
Bedingung einer Fern-Abmeldung, die tatsächlich wirkt.

Diese Bedingung war nicht erfüllt. Zwei Befunde aus der Analyse:

1. **Das Abmelden überlebte keinen Neustart.** Die Sperrliste war eine
   prozesslokale `sync.Map`. Nach jedem Deploy — und Deploys sind hier häufig —
   war ein bereits abgemeldetes Cookie wieder gültig. Bei 24 Stunden Laufzeit
   war der Schaden gedeckelt; bei unbefristeter Anmeldung wäre ein einmal
   abgegriffenes Cookie unbegrenzt gültig gewesen.
2. **Der in ADR-0030 genannte Notweg existierte nicht.** ADR-0030 verwarf die
   serverseitige Sitzungsverwaltung mit der Begründung, bei „24h-TTL und
   Passwortwechsel als Notweg" sei sie verzichtbar. Tatsächlich ändert
   `ChangePasswordHandler` nur den Passwort-Hash, ohne jede
   Sitzungs-Invalidierung; für `ResetPasswordHandler` gilt dasselbe. Der Preis,
   den ADR-0030 bewusst zu zahlen glaubte, war also höher als dort angenommen:
   es gab überhaupt keinen wirksamen Widerruf.

## Entscheidung

**Jeder Nutzer führt eine dateibasierte Liste seiner gültigen Anmeldungen.**
Ein Anmelde-Merkmal ist gültig, solange seine Anmelde-Kennung auf dieser Liste
steht — nicht mehr, solange eine Frist läuft.

- **Format:** `{userId}.{sessionId}.{ts}.{sig}`, HMAC-SHA256 über
  `{userId}:{sessionId}:{ts}`. `sessionId` sind 16 Zufallsbytes hex. Keine
  Ablaufprüfung. Die Cookie-Lebensdauer im Browser beträgt mindestens ein Jahr.
- **Ablage:** `data/users/<user_id>/sessions.json`, bewusst **getrennt** vom
  Nutzer-Datensatz. Die 15 bestehenden `SaveUser`-Aufrufer schreiben stets das
  ganze Nutzerobjekt zurück; läge die Liste dort, könnte ein gleichzeitiger
  Profil-Schreiber einen Widerruf überschreiben — und ausgerechnet der Widerruf
  verträgt diesen Verlust nicht. Die Trennung hält die Liste zudem aus dem
  `model.User`-Schema heraus, sodass nicht jede Anmeldung den
  Schema-Backup-Hook auslöst. Konform zu ADR-0031.
- **Nebenläufigkeit:** Pro-Nutzer-Sperre nach dem Vorbild
  `internal/store/briefing_lock.go` (Mutex-Pool auf Paketebene mit
  Referenzzählung). Ein Prozess je Umgebung, daher genügt eine Prozess-Sperre.
- **Kein Zwischenspeicher.** Jede authentifizierte Anfrage liest die Liste
  direkt. Real existierende Nutzerdateien sind 193–433 Byte groß, der Bestand
  umfasst eine Handvoll Nutzer, und es existieren keine Request-Metriken, die
  einen Zwischenspeicher rechtfertigen würden. Vor allem aber: Ein
  Zwischenspeicher wäre ein zweiter Zustandsbehälter, der genau die
  Widerrufs-Zusicherung tragen müsste, auf der die unbefristete Anmeldung
  beruht. Der billigste Weg, ihn nie falsch werden zu lassen, ist, ihn nicht zu
  haben. Nachrüstbar, sobald eine Lastmessung ihn begründet.
- **Zwei Abmelde-Wege:** „Abmelden" entfernt einen Eintrag, „Auf allen Geräten
  abmelden" (`POST /api/auth/logout-all`) leert die Liste. Passwortwechsel,
  Passwort-Zurücksetzen und Kontolöschung leeren sie ebenfalls.
- **Beide Prüfstellen zerlegen von rechts.** Der Go-Dienst zerlegte bisher mit
  `SplitN(".", 3)`, der Frontend-Server war unter #425 AC-7 bereits auf ein
  rechts-verankertes Verfahren umgestellt worden, ohne dass Go nachgezogen
  wurde. Heute nicht ausnutzbar (alle Kennungs-Erzeuger sind punktfrei), aber
  eine strukturelle Divergenz zwischen zwei Stellen, die dasselbe prüfen
  sollen. Wird mit dieser Entscheidung beseitigt.

### Migrationspfad (Folgepflicht aus ADR-0030)

Merkmale im alten dreiteiligen Format bleiben gültig und **behalten ihre
24-Stunden-Grenze**. Bei einem gültigen Alt-Merkmal legt die Middleware
synchron eine Anmelde-Kennung an, trägt sie ein und setzt das neue Cookie über
den `ResponseWriter` nach. Niemand wird durch das Deploy hinausgeworfen. Da
keine neuen Alt-Merkmale mehr ausgestellt werden, verschwindet der Altbestand
binnen 24 Stunden von selbst; der Legacy-Zweig kann danach ersatzlos entfallen.
Nutzer ohne `sessions.json` haben eine leere Liste — kein Migrationsskript.

## Verworfene Alternativen

- **Generationszähler** (eine Zahl je Nutzer, die das Merkmal mitträgt; erhöhen
  = alle abmelden). Billiger zu prüfen und zu speichern, kann aber „nur dieses
  Gerät abmelden" prinzipiell nicht abbilden. Um beide geforderten Abmelde-Arten
  zu erfüllen, bräuchte er zusätzlich eine dauerhafte Sperrliste einzelner
  Merkmale, die bei unbefristeten Merkmalen nie schrumpft — also zwei
  Mechanismen nebeneinander, doppelter Code, doppelte Migration, doppelte Tests
  ohne Gegenwert.
- **Alles beim Alten lassen und nur die Frist verlängern.** Verlagert das
  Problem, statt es zu lösen: ohne wirksamen Widerruf wächst mit jeder
  Fristverlängerung das Zeitfenster eines abgegriffenen Cookies.
- **Widerrufsprüfung auch im Frontend-Server.** Er hat keinen Zugriff auf den
  Nutzer-Datenbestand; eine Rückfrage zum Go-Dienst kostete Wartezeit bei jedem
  Seitenaufbau und bräche die bewusste Trennung, ohne einen echten Schaden
  abzuwenden (siehe Negativ-Konsequenz unten).

## Konsequenzen

- **Positiv:** Anmeldung hält, bis der Nutzer sie beendet — das eigentliche
  Produktziel auf Tour. Abmelden wirkt dauerhaft, auch über Deploys hinweg.
  Ein verlorenes Handy lässt sich fern-abmelden. Passwortwechsel und
  -Zurücksetzen wirken erstmals überhaupt auf bestehende Anmeldungen. Die
  Zerlegungs-Divergenz zwischen den beiden Prüfstellen ist beseitigt.
- **Negativ / Preis:** Ein Dateizugriff je authentifizierter Anfrage, wo bisher
  keiner nötig war. Der Frontend-Server prüft weiterhin nur Signatur und
  Format, nicht die Liste — nach einem Widerruf entsteht dort ein kurzes
  Fenster „Seite lädt, Daten fehlen", bis der nächste Klick auf die
  Anmelde-Seite führt; das entsprach schon dem Verhalten der alten Sperrliste.
  Die Liste wächst je Gerät und wird durch keine Frist mehr geräumt — bei
  unbefristeter Anmeldung ist genau das gewollt.
- **Folgepflichten:** Das Cookie-Format bleibt API-Vertrag — Änderungen nur mit
  neuem ADR und Migrationspfad. Der Legacy-Zweig für dreiteilige Merkmale ist
  nach dem Deploy verzichtbar und soll dann entfernt werden. Beide Prüfstellen
  (Go und Frontend-Server) müssen bei jeder Formatänderung gemeinsam
  ausgeliefert werden; getrennte Deploys sperren Nutzer aus.
