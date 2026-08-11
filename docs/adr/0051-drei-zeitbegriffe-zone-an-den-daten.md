# ADR-0051: Drei Zeitbegriffe statt einem — die Zone gehört an die Daten, nicht an den Server

- **Status:** Vorgeschlagen
- **Datum:** 2026-08-11
- **Bezug:** Analyse `docs/analysis/zeitzonen-architektur-2026-08.md`; ADR-0044 (wird Spezialfall dieser Regeln), ADR-0035 (Tagesfenster als Zeitraum — unberührt); Issues #21, #400/#401, #856, #1280, #1345, #1378, #1383, #1399, #1402, #1470, #1667, #1697

## Kontext

Seit April 2026 sind neun Zeitzonen-Issues geschlossen worden; #1470 und #1697 waren die zehnte
und elfte Runde derselben Fehlerklasse. Jede Runde hat eine Aufrufstelle korrigiert und dabei
festgestellt, dass weitere offen bleiben — #1697 nennt zwölf.

Die Bestandsaufnahme (Analyse-Papier, alle Zahlen dort nachgemessen) fand nicht einen Fehler,
sondern **vier nebeneinander laufende Uhren** ohne Zuständigkeitsregel:

| Uhr | entscheidet heute |
|---|---|
| `Europe/Vienna` (6 Verdrahtungen über alle drei Stacks) | Fälligkeit eines Briefings, Ruhezeit, Tageszähler-Reset |
| `Etc/UTC` als geerbte Prozess-Zeitzone (40 × `date.today()`, 10 × `datetime.now()` ohne Zone) | welcher Kalendertag gemeint ist |
| Ortszone des Trips (`services/trip_day.py`) | nur der Alarm-Pfad, seit #1697 |
| Browser-Zone | Anzeige — dort ebenfalls auf Wien festgenagelt |

Wien ist die Heimatzone des Betreibers und steht im Code, weil der Betreiber dort wohnt.
`Etc/UTC` steht im Code, weil der Server zufällig so konfiguriert ist. Beide beantworten keine
fachliche Frage.

Wirkung, gemessen für ein auf 07:00 gestelltes Morgen-Briefing am 20.08.2026: Korsika 07:00
(richtig), Neuseeland 17:00, PCT 22:00 **am Vorabend** mit dem Inhalt des folgenden
Weltzeit-Tages. Die in Wien ausgewertete Ruhezeit 22:00–07:00 liegt in Neuseeland auf
08:00–17:00 Ortszeit — still während des Wandertags, laut die ganze Nacht. Das Produkt ist auf
genau einer Zone richtig, und das aus Versehen: Paris und Wien sind dieselbe Zone.

Der bestehende Zeitzonen-Wächter (#1402) greift, sein Geltungsbereich ist aber `src/output/**` —
er bewacht die **Darstellung** einer Uhrzeit. Die wiederkehrenden Fehler sitzen in der
**Entscheidung**: welcher Tag gemeint ist, ob ein Versand fällig ist, ob Ruhezeit gilt, wann ein
Zähler kippt. Für diese Schicht gibt es keine Regel und keinen Wächter.

ADR-0044 hat für „heute"/„morgen" bereits die richtige Antwort gegeben. Sie galt aber nur für
diese eine Frage, und deshalb musste sie in #1697 erneut einzeln durchgesetzt werden.

## Entscheidung

Das Projekt übernimmt das Modell, das `java.time`, Noda Time und `Temporal` gemeinsam haben:
**drei Zeitbegriffe**, die heute alle „datetime" heißen.

| Begriff | Bedeutung | im Produkt |
|---|---|---|
| **Zeitpunkt** (*instant*) | ein Punkt auf der Weltzeitlinie, ohne Zone eindeutig | Versand-Zeitstempel, Messwert-Zeitstempel, Protokolleinträge |
| **Kalenderzeit** (*civil*) | Wanduhr-/Kalenderangabe **ohne** Zone, allein bedeutungslos | `morning_time: "07:00"`, Etappendatum, Ruhezeit-Fenster |
| **Zone** | IANA-Kennung | `Europe/Paris` — aus Wegpunkt-Koordinaten bzw. `SavedLocation.timezone` |

Daraus gelten drei Regeln:

> **Regel 1 — Vergangenes ist ein Zeitpunkt, Geplantes ist Kalenderzeit plus Zone.**
> Ein Ereignis, das stattgefunden hat, wird als UTC-Zeitpunkt gespeichert. Ein *künftiger* Termin
> wird **nie** als vorausberechneter UTC-Zeitpunkt gespeichert, sondern als Wanduhrzeit plus
> Zonen-Kennung — Zonenregeln ändern sich, und der Nutzer meint „07:00 bei mir", nicht „05:00 in
> Greenwich".

> **Regel 2 — Die Zone gehört an die Daten, nicht an den Server.**
> Zuständig ist die Zone des Gegenstands, über den geredet wird: beim Trip die des Wegpunkts,
> beim Ort die des Orts. Eine Server-, Betreiber- oder Browser-Zone ist in **keiner** fachlichen
> Frage die richtige Antwort.

> **Regel 3 — Keine Umgebungsuhr.**
> `date.today()`, `datetime.now()` ohne `tz`, `time.Local` und `new Date()` ohne explizite Zone
> sind im Produktivcode verboten. „Jetzt" wird als Zeitpunkt-Parameter hereingereicht.

**ADR-0044 wird dadurch nicht abgelöst, sondern eingeordnet:** „heute"/„morgen" bestimmen sich
nach der Ortszeit — das ist Regel 2, angewandt auf die Frage nach dem Kalendertag. Die dort
beschriebene Anker-Auflösung (Etappe des Weltzeit-Tages) und die Ausnahme für **Dauern** („die
nächsten zwölf Stunden" bleibt eine UTC-Addition) gelten unverändert weiter.

**ADR-0035 bleibt unberührt.** Es regelt das Tagesfenster als *Zeitraum*; hier geht es um die
Zuständigkeit einer Uhr.

**Die Hausnorm aus #1345 bleibt gültig:** Wetterdaten tragen weiterhin zonenlose UTC-Zeitstempel.
Das ist Regel 1, Fall „Zeitpunkt" — die Ortszeit entsteht erst bei Auswertung und Beschriftung.

### Zwei Folgesätze, die aus den Regeln zwingend folgen

**Die Fälligkeitsfrage wird umgekehrt.** Statt „es ist 07:00 in Wien — welche Trips passen?"
(eine globale Uhr, N Trips) gilt „für jeden Trip: wie spät ist es in *seiner* Zone?". Der Cron
liefert nur noch einen Zeitpunkt, keine Stunde. Damit verschwindet die Wien-Konstante, statt
einen weiteren Sonderfall danebenzustellen.

**Stundengleichheit ist als Fälligkeitsprüfung unzulässig.** Gemessen: Europe/Paris hat am
29.03.2026 keine Ortsstunde 02 (Tag = 23 h) und am 25.10.2026 zwei davon (25 h);
Australia/Lord_Howe hat 24,5-Stunden-Tage. Ein auf 02:00 gestelltes Briefing entfiele einmal im
Jahr ersatzlos und ginge einmal doppelt raus. An ihre Stelle tritt **Fälligkeit plus
Idempotenz-Schlüssel**: fällig, wenn die Ortsstunde die konfigurierte erreicht oder überschritten
hat und für `(trip_id, ortstag, slot)` noch nichts vermerkt ist. Ein Mechanismus deckt damit
fehlende Stunde, doppelte Stunde, ausgefallenen Tick und Scheduler-Neustart ab.

## Verworfene Alternativen

- **Alles bei Weltzeit lassen.** Konsistent und umstellungs-immun, für den Nutzer aber falsch —
  bereits in ADR-0044 verworfen, hier unverändert.
- **Alles bei `Europe/Vienna` lassen** (Ist-Zustand des Versandpfads). Nur für Mitteleuropa
  richtig, und auch dort nicht ganz: Weltzeit-Tag und Ortstag fallen auf Korsika bei 2 von 24
  Konfig-Stunden auseinander. Bindet das Produkt an den Wohnort des Betreibers.
- **Eine Nutzer-Zeitzonen-Einstellung.** In ADR-0044 verworfen — der Wanderer ist unterwegs, nicht
  zu Hause. Bleibt verworfen; die Zone kommt aus den Wegpunkten.
- **Weiter Aufrufstelle für Aufrufstelle.** Der Ist-Zustand seit April: elf Runden, jede mit
  eigenem Nachweis, und die Restliste wächst schneller, als sie schrumpft.
- **Eigene Zeit-Typen einführen** (Wrapper-Klassen `Instant`/`CivilTime` wie in Noda Time). Der
  sauberste Weg, aber ein Umbau quer durch drei Stacks mit hunderten Aufrufstellen und ohne
  Zwischenstand. Verworfen zugunsten der Wächter-Lösung, die denselben Fehler mechanisch fängt,
  ohne jede Signatur anzufassen. Bei erneutem Rückfall trotz Wächter wieder aufzugreifen.

## Konsequenzen

**Positiv**

- Die Fehlerklasse wird strukturell erkennbar statt Aufrufstelle für Aufrufstelle: Regel 3 ist
  rein syntaktisch prüfbar, Regel 2 an festen Zonen-Literalen.
- Sechs Wien-Verdrahtungen und die geerbte Prozess-Zeitzone entfallen — das Produkt funktioniert
  außerhalb Mitteleuropas, ohne dass für jede Zone nachgebessert wird.
- Der Versand wird gegen Sommerzeit-Umstellungen, verpasste Ticks und Neustarts durch **einen**
  Mechanismus robust, nicht durch drei Sonderfälle.

**Negativ / Preis**

- Wer eine Bezugsgröße von Weltzeit auf Ortszeit umstellt, holt sich die Sommerzeit-Frage neu ins
  Haus (ADR-0044). Beide Wechseltage sind Pflichtfälle jeder betroffenen Scheibe — geprüft auf
  die Häufigkeit *jeder einzelnen Stunde*, nicht auf die Zeilenzahl.
- Ein Ortstag hat nicht immer 24 Stunden. Signaturen mit `hours: int` sind damit falsch
  (ADR-0044, unverändert).
- Die Zonen-Auflösung kostet: `TimezoneFinder` lädt ~12 MB. Bereits als Lazy-Singleton gelöst
  (`utils/timezone.py`), aber je Trip statt je Lauf aufgerufen — Auflösungen sind zu bündeln.
- Der Bestand (40 × `date.today()`) verschwindet nicht auf einmal. Er wird als
  `KNOWN_VIOLATIONS`-Liste sichtbar, die nur schrumpfen darf.

**Folgepflichten**

- Jede neue Zeitentscheidung nennt ihre Zone aus den Daten. Eine feste Zone im Produktivcode ist
  ein Befund, kein Stilfrage.
- Der Wächter aus #1402 wird auf `src/services/**` und `api/**` ausgedehnt (Fundmuster:
  Umgebungsuhr, feste Zone, unaufgelöstes `.hour`/`.date()`); die Ausnahmeliste darf nur kleiner
  werden.
- „Ist die Zusicherung an der Stelle geprüft, an der sie **wirkt**?" gilt hier besonders: #1697
  fand dreimal in Folge korrekten Produktivcode ohne jeden Wächter. Jede Aufrufstelle, die einen
  Ortstag rechnet, braucht ihre eigene Mutations-Gegenprobe.

**Bewusst offen**

- Trips über mehrere Zeitzonen: Restfehler = Zonendifferenz zweier benachbarter Etappen
  (ADR-0044, PO-Entscheidung, unverändert).
- Trips ohne Wegpunkte: bestehender UTC-Rückfall, sichtbar gekennzeichnet (`local_stamp`).
