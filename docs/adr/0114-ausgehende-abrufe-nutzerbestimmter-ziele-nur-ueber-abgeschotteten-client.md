# ADR-0114: Ausgehende Abrufe nutzerbestimmter Ziele nur über einen abgeschotteten Client; Kennungen zum Core immer kodiert; Mengenbremsen je Nutzer

- **Status:** Akzeptiert
- **Datum:** 2026-11-12
- **Bezug:** GitHub-Issue #2961 („Sicherheits-Härtung nach Review 2026-11"), Spec
  `docs/specs/modules/security_haertung_2026_11_go_schnittstellen.md`; ergänzt
  [ADR-0062](0062-python-core-authentifiziert-gegenueber-go.md) (Dienstgeheimnis am
  `http.DefaultTransport`), [ADR-0003](0003-multi-tenant-isolation.md) (Mandantentrennung beim
  Weiterreichen an den Core) und [ADR-0092](0092-nutzer-testmail-an-bestaetigte-profiladresse.md)
  („eine Mail pro Klick")

## Kontext

Das Sicherheits-Review 2026-11 fand an der Go-API drei Muster, die über den Einzelfall hinaus
gelten:

1. **Ausgehende Abrufe.** Die Ortsauflösung ruft geteilte Kartenlinks ab, um der Weiterleitung zu
   folgen. Ob eine Eingabe ein Kartenlink ist, wurde nur an Teilzeichenketten erkannt; abgerufen
   wurde danach die komplette Eingabe samt Weiterleitungen über den gemeinsamen
   `http.DefaultTransport`. An genau diesem Transport hängt seit ADR-0062 das Dienstgeheimnis für
   den Python-Core (gefiltert auf Host und Port des Cores). Ein vom Nutzer bestimmtes Ziel darf
   weder interne Adressen erreichen noch je ein Dienstgeheimnis tragen.
2. **Kennungen im Pfad.** Mehrere Proxy-Routen setzen die Kennung aus dem URL-Pfad per
   Zeichenketten-Verkettung in die Python-URL. Eine Kennung mit Query- oder Fragment-Zeichen
   verändert dann die Bedeutung der Upstream-URL; die Mandantentrennung (`user_id` aus der
   Sitzung) hing allein daran, dass `appendUserID` zufällig zuletzt schreibt.
3. **Interaktive Auslöser ohne Obergrenze.** Testnachricht, Handversand, Wettervergleich und
   Vorschauen lösen je Klick teure Arbeit oder echte Zustellungen aus (ADR-0092: „eine Mail pro
   Klick"), ohne Grenze je Nutzer.

Randbedingung: Rund zwanzig Aufrufstellen bauen `&http.Client{Timeout: …}` ohne eigenen Transport
und verlassen sich darauf, dass `coreauth` das Geheimnis anhängt (ADR-0062 Regel 1).

## Entscheidung

1. **Nutzerbestimmte Ziele nur über Erlaubnisliste und abgeschotteten Client.** Jede Stelle, die
   eine vom Nutzer (mit)bestimmte URL abruft, prüft sie vorab streng (URL-Parser, nur `https`,
   Host exakt gegen eine Erlaubnisliste) und prüft jede Weiterleitung gegen dieselbe Liste
   (höchstens fünf). Der Abruf läuft über einen eigenen Client mit **eigenem Transport**: ohne
   Dienstgeheimnis, ohne Umgebungs-Proxy, mit einer Adresssperre im Dial-Control-Hook, die an der
   tatsächlich aufgelösten IP Loopback-, private, Link-Local-, CGNAT-, Multicast- und reservierte
   Netze (IPv4, IPv6, IPv4-mapped) ablehnt, und mit begrenzten Antwortköpfen. Der Staging-
   Egress-Wächter wird von diesem Client je Anfrage selbst gefragt
   (`egress.HTTPAllowed`). Heute betrifft das genau den Google-Maps-Zweig des Resolvers
   (`internal/resolver/safefetch.go`); feste Anbieter-Hosts (Open-Meteo, Komoot-API, Nominatim,
   Open-Elevation) bleiben unberührt. Testöffnungen gibt es nur über `export_test.go`, nie über
   Umgebungsvariablen.
2. **Das Dienstgeheimnis bleibt am `DefaultTransport` (ADR-0062 Regel 1 unverändert).** Der Umbau
   auf „nur ausdrücklich gebaute Core-Clients tragen den Header" hätte alle rund zwanzig
   Aufrufstellen berührt, und eine vergessene Stelle fiele erst im Betrieb als 401 auf. Stattdessen
   gilt: Abrufe nutzerbestimmter Ziele laufen **ausschließlich** über den abgeschotteten Client aus
   Punkt 1, der das Geheimnis strukturell nicht tragen kann. Ein Test belegt das am Empfänger
   (ein Resolver-Abruf auf die Core-Adresse findet ohne Testöffnung gar nicht statt und trägt mit
   Testöffnung keinen Header).
3. **Kennungen werden beim Weiterreichen an den Core immer kodiert.** Jede Pfad-Kennung wird vor
   dem Weiterreichen mit `store.ValidEntityID` geprüft (400, auch auf den Alt-Routen) und als
   Pfadsegment mit `url.PathEscape` eingesetzt; Query-Werte entstehen über `url.Values`. Das
   Kennungsmuster sperrt zusätzlich ASCII-Steuerzeichen sowie `?`, `#` und `%`. Leerzeichen
   bleiben aus Bestandsschutz zulässig; die Python-Seite (`VALID_ENTITY_ID_RE`) ist noch nicht
   verschärft — Go ist strenger, nie lockerer.
4. **Mengenbremsen je Nutzer für interaktive Auslöser in Go.** Gleitendes Zeitfenster je Nutzer,
   429 im bestehenden Fehlerformat mit `Retry-After` und Katalogtext DE/EN: Testnachricht 10/h,
   Handversand (alle drei Routen gemeinsam) 20/h, Ortsauflösung 30/min, GPX-Upload 30/h,
   Wettervergleich, Etappenwetter und Vorschauen je 60/min bei höchstens vier gleichzeitigen
   schweren Abrufen je Nutzer. Admins und `GZ_QUOTA_EXEMPT_USER_IDS` sind ausgenommen (dieselbe
   Policy wie die Mengen-Quoten), im Fixture-Modus sind die Bremsen nicht eingehängt. Das ergänzt
   ADR-0092 („eine Mail pro Klick") um eine Obergrenze; der Zustand liegt im Arbeitsspeicher.

## Verworfene Alternativen

- **Header nur an ausdrücklich gebauten Core-Clients (Umbau aller Aufrufstellen)** — sauberer,
  aber eine vergessene Stelle bricht still die Core-Anbindung; in dieser Welle zu breit. Bleibt
  Option, falls weitere Abrufe nutzerbestimmter Ziele hinzukommen.
- **Adresssperre nur vor dem Abruf per DNS-Auflösung** — verworfen: zwischen Prüfung und
  Verbindung kann der Name anders auflösen (DNS-Rebinding); geprüft wird deshalb im Dial-Hook.
- **Env-Schalter zum Abschalten der Sperre für Tests** — verworfen: ein Schalter, den Tests
  setzen können, kann auch eine Fehlkonfiguration in Produktion setzen.
- **Kennungsmuster als strenge ASCII-Liste** — verworfen: Bestandsorte tragen Umlaute im Slug
  (ADR-Kontext #2140).

## Konsequenzen

- **Positiv:** Ein Kartenlink kann weder interne Dienste erreichen noch das Dienstgeheimnis
  mitnehmen; eine Kennung kann die Upstream-URL nicht mehr umdeuten; teure oder zustellende
  Klicks haben je Nutzer eine Obergrenze.
- **Negativ / Preis:** Geteilte Kartenlinks funktionieren nur noch über https und die gelisteten
  Google-Hosts; ein neuer Kurzlink-Dienst braucht einen Listeneintrag. Mengenbremsen sind
  prozesslokal und überleben keinen Neustart. Staging-E2E-Konten ohne Admin-/Ausnahme-Status
  können in die Bremse laufen, wenn ein Lauf mehr als 20 Handversände je Stunde auslöst.
- **Folgepflichten:** Jede neue Stelle, die eine nutzerbestimmte URL abruft, nutzt den
  abgeschotteten Client (oder einen gleichwertigen mit eigenem Transport). Jede neue Proxy-Route
  mit Pfad-Kennung nutzt `coreKennung` (Prüfung + Kodierung). Neue interaktive Auslöser mit
  Zustellung oder teurem Abruf bekommen eine Bremse in `NutzerBremsen`. Die Python-Seite des
  Kennungsmusters ist nachzuziehen (eigener Auftrag).
