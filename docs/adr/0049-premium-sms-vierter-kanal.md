# ADR-0049: Premium-SMS (Garmin inReach) ist ein vierter, eigenständiger Kanal `premium_sms` — kein SMS-Sonderfall (schreibt ADR-0004 fort)

- **Status:** Akzeptiert (PO-„freigabe" 2026-08-10)
- **Datum:** 2026-08-10
- **Bezug:** Issue #1676 (Scheibe S2a), Spec
  `docs/specs/modules/feat_1676_s2a_premium_sms_versand.md`; **schreibt
  ADR-0004 fort** („Die unterstützten Kanäle sind nur noch E-Mail · Telegram ·
  SMS"), ohne es zu widerrufen; folgt ADR-0015 (Kanal-Transporte gehören in
  den Python-Kern)

## Kontext

ADR-0004 hat die Kanalliste 2026-06-06 bewusst auf drei Kanäle verengt und
Signal entfernt — mit der ausdrücklichen Folgepflicht: „Neue Features dürfen
Signal nicht als Briefing-Kanal annehmen. Eine Reaktivierung erfordert ein
neues ADR." Dieselbe Folgepflicht trifft jeden **anderen** vierten Kanal: die
Zahl „drei" stand dort nicht als Zufall, sondern als Wartungsgrenze.

Issue #1676 bringt einen Fall, den ADR-0004 nicht kannte. Auf einer
Weitwanderung ist das Satellitengerät (Garmin inReach) unterwegs oft der
einzige erreichbare Empfangsweg — E-Mail und Telegram brauchen Netz, das
genau dort fehlt, wo das Briefing gebraucht wird. Technisch läuft der Versand
über denselben Dienstleister wie die normale SMS (seven.io), fachlich ist es
aber **kein** SMS-Sonderfall:

| | SMS | Premium-SMS (Garmin inReach) |
|---|---|---|
| Absender | frei konfigurierbar (`sms_from`, oft leer) | **fest** unsere Dienstnummer `4916092172595` — nur an sie kann das Gerät antworten |
| Empfänger | vom Nutzer eingetragene Rufnummer (`sms_to`) | **gelernte, veränderliche** Rückadresse aus `user.json`, die Garmin je Gespräch neu vergibt (S1, #1676) |
| Fehlt das Ziel | Kanal gilt als nicht konfiguriert, es passiert schlicht nichts | **muss sichtbar scheitern** — eine Nummer, die Garmin inzwischen einem fremden Gerät zugeteilt hat, kostet Geld und geht an einen Fremden |
| Berechtigung | Tier `standard` **und** `premium` | ausschließlich Tier `premium` |

Die naheliegende Abkürzung wäre gewesen, das als Variante von `SMSOutput` zu
bauen („derselbe Dienstleister, nur ein anderes `from`"). Genau das ist der
Fehler, den dieses ADR ausschließt: die vier Zeilen oben sind vier
unterschiedliche fachliche Regeln. Eine Variante hätte sie in Bedingungen
innerhalb eines Kanals versteckt, wo niemand sie als Kanal-Eigenschaft
wiederfindet — und die Rechte-Ausweitung (`standard` darf plötzlich das
teure Gerät ansprechen) wäre ein stiller Nebeneffekt statt einer
Entscheidung.

## Entscheidung

**Premium-SMS ist ein vierter, eigenständiger Kanal mit dem verbindlichen
Namen `premium_sms`.** Die Kanalliste des Produkts lautet damit:
**E-Mail · Telegram · SMS · Premium-SMS**.

Verbindlich festgelegt:

1. **Der Kanalname ist `premium_sms`** — überall gleich: Klassenname
   `PremiumSmsOutput.name`, Trip-Feld `send_premium_sms`, Schlüssel in
   `NotificationResult.sent_channels`/`blocked_channels`, Eintrag in
   `CHANNEL_LIMITS`, künftige Vorschau-/Alarm-Pfade. Der Name wurde **vor**
   dem Code festgeschrieben, damit er nicht mitten in der Umsetzung wandert.
2. **Fester Absender.** `4916092172595` ist Kanal-Eigenschaft, nicht
   Konfiguration. `sms_from` hat auf diesen Kanal keine Wirkung — das Gerät
   antwortet nur an die Nummer, von der es angesprochen wurde.
3. **Der Empfänger kommt ausschließlich aus der gelernten Rückadresse**
   (`user.json`, geschrieben von S1). `sms_to` wird für diesen Kanal nie
   gelesen; ein Überschreiben per Umgebungsvariable ist gesperrt (Code-Sperre,
   nicht Betriebsdisziplin).
4. **Fail-closed mit sichtbarem Grund.** Fehlt die gelernte Rückadresse oder
   ist sie älter als 30 Tage, geht **keine** Nachricht hinaus, und der Grund
   steht als auswertbares Ergebnisfeld (`blocked_channels`) beim Aufrufer —
   nicht nur in einer Logzeile. Begründung der 30 Tage: eine von Garmin
   inzwischen neu vergebene Nummer nimmt die SMS mit HTTP 200 an, der
   Scheinerfolg wäre von einem echten nicht zu unterscheiden.
5. **Eigenes Tier-Gate.** `premium_sms_allowed()` prüft ausschließlich
   `premium`. Eine Wiederverwendung von `sms_allowed()` (das `standard`
   durchlässt) wäre eine stille Rechte-Ausweitung.
6. **Ein gemeinsamer Transport, zwei Kanäle.** Beide seven.io-Kanäle erben
   Sicherheitssperren und HTTP-Transport aus einer gemeinsamen Basis
   (`SevenIoChannelBase`), statt sie zu kopieren.

## Verworfene Alternativen

- **Variante von `SMSOutput`** (Parameter/Flag „premium"). Technisch am
  dichtesten, verworfen: die vier fachlichen Unterschiede oben würden zu
  `if`-Zweigen im SMS-Kanal, das strengere Tier-Gate wäre nicht mehr als
  Kanal-Eigenschaft erkennbar, und „Absender fest" stünde neben „Absender
  konfigurierbar" in derselben Klasse. PO-Vorgabe war ausdrücklich „eigener
  Kanal, keine Variante".
- **Kopie von `sms.py`** mit angepassten Feldern. Verworfen: die beiden
  Sicherheitssperren (Test-Modus-Sandbox-Key #1336, Herkunftssperre #1476)
  existierten dann zweimal. Der bestehende Paritätstest prüft sie **namentlich
  je Klasse** — eine in der Kopie vergessene Sperre wäre der Testsuite nicht
  aufgefallen. Eine Kopie hätte also genau die Vergessbarkeit verdoppelt, die
  die Sperren verhindern sollen.
- **Rückadresse zusätzlich per `.env`/Konfiguration setzbar** („als
  Notausgang"). Verworfen: eine per Umgebungsvariable auffrischbare
  Verfallsfrist ist keine Frist, und ein per `.env` gesetzter Empfänger
  umgeht die einzige Datenquelle, die weiß, welches Gerät gerade antwortet.
- **ADR-0004 ändern statt fortschreiben.** Verworfen: die Historie soll
  nachvollziehbar bleiben (Regel „das alte ADR nicht löschen"). ADR-0004
  gilt unverändert für **Signal**; nur seine Zahl „drei" wird hier auf vier
  fortgeschrieben.

## Konsequenzen

- **Positiv:** Der einzige Kanal, der unterwegs ohne Netz funktioniert, wird
  regulär bedienbar. Die vier Sonderregeln stehen an einer auffindbaren Stelle
  (Kanal-Klasse) statt als Bedingungen im SMS-Pfad. Die Sicherheitssperren
  gelten für beide seven.io-Kanäle aus einer Quelle.
- **Negativ / Preis:** Jede Stelle, die heute eine harte Dreier-Kanalliste
  führt, ist ab jetzt unvollständig — bekannt und benannt:
  `alert_log.py::_ALL_CHANNELS`, die zweite Kopie in `trip_alert.py`, die
  Kanal-Schwellen aus ADR-0046, `AlertChannelsConfig` in Go und
  `api_contract.md`. S2a rührt sie **nicht** an (nur Trip-Briefing); sie sind
  die Liefer-Position von S2b (#1701). Bis dahin ist Premium-SMS
  ausdrücklich **kein** Alarm-Kanal.
- **Negativ / Preis:** Ein vierter Kanal kostet dauerhaft Pflege — genau der
  Grund, aus dem ADR-0004 die Liste verengt hat. Der Unterschied zu Signal:
  dieser Kanal ist für die Zielgruppe der einzige Weg ohne Netz, nicht der
  vierte Weg mit Netz.
- **Folgepflicht:** Wer eine neue Stelle baut, die ein Kanal-Set auflöst, muss
  `premium_sms` mitführen oder begründen, warum nicht (ADR-0046 hat dieselbe
  Folgepflicht für die Kanal-Schwelle). Kosten-/Kontingentzählung je Kanal
  existiert im Bestand nirgends und ist eigene Arbeit (#1702).
- **Nicht bewiesen durch S2a:** dass eine Premium-SMS tatsächlich auf dem
  Gerät ankommt. Die Herkunftssperre (#1476) erzwingt außerhalb der
  Produktions-Wurzel den Sandbox-Key („sendet nie, kostet nie"), Staging ist
  zusätzlich sandboxiert. Dieser Nachweis gehört zu #1533 und ist bis dahin
  als **offen** auszuweisen, nicht als bestanden.
