---
entity_id: fix_1662_versandfehler_nachliefern
type: bugfix
created: 2026-08-10
updated: 2026-08-10
status: draft
version: "1.0"
tags: [briefing, dispatch, retry, issue-1662, observability]
---

# Versandfehler eines Trip-Briefings wird nachgeliefert (Issue #1662)

## Approval

- [x] Approved — Product Owner, 2026-08-10 („Approved"). Freigegeben wurden AC-1 bis AC-13 in der
  hier vorliegenden Fassung, einschließlich der drei Punkte, die von der ursprünglichen
  Issue-Erwartung abweichen: (1) Begrenzung über den Zieltag statt über Fehlertyp oder Zähler,
  (2) ein Vermerk entsteht nur, wenn KEIN Kanal zugestellt hat — ein E-Mail-Ausfall neben
  funktionierender SMS wird nicht nachgeliefert, (3) das reguläre Briefing der Fälligkeitsstunde
  ist der „letzte Versuch", kein separater Nachhol-Versand. Vorausgegangen sind vier
  PO-Entscheidungen vom selben Tag (siehe Kontextdokument).

## Purpose

Scheitert heute der **Versand** eines Trip-Briefings (nicht der Wetterabruf, sondern z.B. ein
E-Mail-Fehler), merkt sich das System das nirgends vor — der bestehende Nachhol-Mechanismus
(#1012) kennt ausschließlich fehlende Wetterdaten. Am 07./08.08.2026 fielen dadurch **zwei**
Briefings desselben Trips komplett aus, unbemerkt bis zum Folgetag. Diese Spec sorgt dafür, dass
ein Versandfehler denselben Vormerk-und-Nachhol-Weg bekommt, den ein bloß unerreichbarer
Wetterdienst schon hat — begrenzt über den Zieltag des Briefings, nicht über einen Zähler oder den
Fehlertyp — und dass ein E-Mail-Fehler künftig nicht mehr SMS und Telegram mit sich reißt.

Vollständige Herleitung, Messungen und die vier PO-Entscheidungen vom 2026-08-10:
`docs/context/fix-1662-versandfehler-nachliefern.md`. Diese Spec wiederholt nichts davon, sondern
zieht den Scope daraus.

## Source

- **File:** `src/services/trip_report_scheduler.py`
- **Identifier:** `TripReportSchedulerService._send_trip_report_outcome` (Fehlerpfad
  `:1033-1042`), `TripReportSchedulerService._process_pending_markers` (`:361-433`)
- Nebendateien: `src/services/notification_service.py` (Kanaltrennung/Zustellbilanz, Zeilen
  354-419), `src/services/alert_briefing_anchor.py` (geteilter Baustein, neben
  `record_briefing_dispatch_failure` `:54-90`)

> **Schicht-Hinweis:** Betroffene Schicht: **Python-Core** (`src/services/`). Kein Go-Code
> nötig — unbekannte JSON-Felder in `pending_briefings.json` werden ignoriert
> (`internal/store/pending_briefings.go:37-40`). Kein Frontend-Code.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `alert_briefing_anchor.record_briefing_dispatch_failure` | function | bestehender fail-soft Diagnose-Schreiber (#1629) — Funktion selbst bleibt unverändert, bekommt aber einen zweiten Aufrufer direkt in `notification_service.py` für den Fall „ein Kanal scheitert, ein anderer liefert" (Zustellbilanz, siehe Implementation Details Punkt 8) |
| `trip_report_scheduler._write_pending_marker` / `_process_pending_markers` | function | bestehender Nachhol-Mechanismus (#1012) — wird um das Feld `reason` und einen neuen Zweig erweitert, Bestandsverhalten (Wetterfehler) bleibt unverändert |
| `notification_service.send_trip_report` | function | Kanal-Reihenfolge E-Mail → SMS → Telegram; alle drei Kanäle werden jetzt fehlertolerant, eine Ausnahme entsteht nur noch anhand der Zustellbilanz am Funktionsende |
| ADR-0018 | decision | Nicht-Kaschieren-Invariante — diese Scheibe erfüllt eine dort bereits vermerkte Folgepflicht, ändert die Entscheidung selbst nicht |
| `fix_1629_briefing_anker_versandfehler` | module | direkte Vorgänger-Spec; liefert den Anker- und Diagnose-Mechanismus, an den hier angeknüpft wird |
| `dispatch_orchestrator.md:95` | module | dokumentierte, PO-getragene Divergenz `pre_pass` Trip (Catch-up) vs. Compare (Auto-Pause) — bleibt in dieser Scheibe unverändert bestehen |

## Estimated Scope

- **LoC:** ~100 Produktivcode (Limit 250)
- **Files:** 3 Produktivdateien (`trip_report_scheduler.py`, `alert_briefing_anchor.py`,
  `notification_service.py`), 1 Testdatei
- **Effort:** medium

## Nicht in dieser Scheibe

- **Teilzustellung im Empfänger-Guard** (`src/output/channels/email.py`) — ein blockierter
  Empfänger reißt weiterhin alle mit. Eigene Scheibe. Nebenbefund: für Trip-Briefings ist `mail_to`
  einwertig (`src/app/config.py:122`), das betrifft also vor allem den Ortsvergleich.
- **Nachhol-Mechanik für den Ortsvergleich** — dort existiert bis heute kein
  Pending-Marker-Mechanismus (`CompareDispatchStrategy.pre_pass` macht nur Auto-Pause). Diese
  Scheibe erweitert bewusst nur den bestehenden Trip-Mechanismus; die Vormerk-Entscheidung selbst
  liegt trotzdem im geteilten Baustein, damit ein künftiger Compare-Nachhol-Mechanismus sie
  wiederverwenden kann.
- **Die Ursache des Guard-Fehlschlags vom 07./08.08.** selbst (warum ein Empfänger an zwei Slots
  keinem Nutzerprofil zugeordnet werden konnte) — ungeklärt, eigenes Thema.
- **Zwei Infrastruktur-Nacharbeiten**, gehen per MQ-Nachricht an `infra`, kein Python-Defekt: (a)
  der Alarmtext in `check-gregor20.sh:199-210` passt nicht auf Versandfehler ("degradierte
  Briefing(s)" bei "0 degradierte Segmente"); (b) die #1629-Felder
  `briefing_dispatch_error_streak_since` / `briefing_dispatch_errors_recent_count` werden von
  niemandem im Script gelesen.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue.
- **Rationale:** Diese Scheibe erfüllt die Nicht-Kaschieren-Invariante aus **ADR-0018** — dort ist
  #1629 bereits als teilweise Erfüllung vermerkt, #1662 schließt die verbleibende Lücke
  (Versandfehler bekommt jetzt zusätzlich einen Nachhol-Weg, nicht nur ein Sichtbarkeits-Signal).
  Es wird keine Entscheidungsfläche berührt: weder Kanal, Provider, Datenmodell/Persistenz-Schema,
  Auth noch Editor-Paradigma ändern sich.

  Die Abkehr von „ein E-Mail-Fehler reißt alle Kanäle mit" ist **keine ADR-Änderung**, sondern die
  Rücknahme einer im Code kommentierten Einzelentscheidung
  (`notification_service.py:813-819` — nicht mehr vorhanden nach dieser Änderung, vormals: „SMTP-
  Ausfall muss sichtbar bleiben, deshalb propagiert E-Mail und reißt SMS/Telegram über die
  Aufrufkette mit"). Diese Begründung ist durch #1629 überholt: Sichtbarkeit eines anhaltenden
  Versandfehlers liefern inzwischen das Diagnose-Journal
  (`users/<uid>/diagnostics/briefing_dispatch_failures.jsonl`) und das wachsende Health-Signal am
  Status-Endpunkt, ab dieser Scheibe zusätzlich der Nachhol-Vermerk selbst. Für diese Sichtbarkeit
  muss kein funktionierender Kanal mehr geopfert werden — im Gegenteil: ein Nutzer mit
  funktionierendem Telegram, aber vorübergehend gestörter E-Mail, soll sein Briefing trotzdem
  bekommen (konkreter Anlass: Garmin-inReach-Weg auf dem Karnischen Höhenweg ab 20.08., #1533).

## Implementation Details

### 1. Neues Markerfeld `reason` unterscheidet Versandfehler von Wetterfehler

`pending_briefings.json` bekommt ein optionales Feld `reason`. Ein Versandfehler-Vermerk trägt
`reason: "dispatch_error"` und eine leere `failed_segment_ids`-Liste. Fehlt das Feld (Bestand,
Wetterfehler-Vermerke), verhält sich alles wie heute — keine Migration nötig.

`_write_pending_marker` (`trip_report_scheduler.py:435-464`) bekommt einen neuen optionalen
Parameter `reason: Optional[str] = None`, der unverändert ins Dict übernommen wird.

### 2. Schreibstelle: ZWEI Ausgänge, EINE geteilte Methode

🔴 **Korrigiert nach Adversary-Befund F001 (2026-08-10).** Ursprünglich sah diese Spec nur den
`except`-Block als Schreibstelle vor. Das deckt den Fall „nichts zugestellt" **nicht vollständig**
ab: Ein vollständig gescheiterter Versand erreicht `_send_trip_report_outcome` auf **zwei** Wegen.

| Ausgang | Wann | Bisher |
|---|---|---|
| Ausnahme (`except Exception as exc:`) | E-Mail ist konfiguriert und scheitert — nur E-Mail reicht einen Fehler nach oben durch | Vermerk wurde geschrieben |
| Rückgabe `"channels_unreachable"` (`if not result.sent:`) | E-Mail ist **nicht** konfiguriert und der einzige Kanal (SMS oder Telegram) scheitert — beide sind fail-soft, es fliegt nichts | 🔴 **kein Vermerk, Briefing still verloren** |

Der zweite Fall ist exakt der Produktivvorfall vom 07./08.08., nur über einen anderen Kanal — und
er trifft den für den Karnischen Höhenweg geplanten Zuschnitt (Premium-SMS auf ein Garmin inReach,
E-Mail aus). Reproduziert vom Adversary mit einem SMS-Gateway auf `127.0.0.1:9`.

**Deshalb hängt der Vermerk nicht mehr an einer geworfenen Ausnahme.** Beide Ausgänge rufen
dieselbe Methode `_mark_briefing_undelivered(trip, report_type, target_date, *, on_demand)`
(`trip_report_scheduler.py:523-546`), die die Ad-hoc-Sperre und die Marker-Parameter
(`reason="dispatch_error"`, leere `failed_segment_ids`, echte `self._user_id` — niemals
`"default"`) an **einer** Stelle hält. Eine Kopie je Ausgang wäre genau die Stelle, an der die
beiden Wege wieder auseinanderlaufen; dieselbe Erwägung, aus der #1629 den Anker in
`_anchor_and_reset` gebündelt hat.

**Verworfen:** bei leerer Zustellbilanz einfach immer eine Ausnahme zu werfen. Das hätte
`"channels_unreachable"` als ehrliches Ergebnis abgeschafft (#1403 AC-4) und den Bestandstest bei
`tests/tdd/test_briefing_anchor_survives_dispatch_failure.py:391` gebrochen.

**Kein Vermerk** entsteht bei `result.no_channel_configured` — dort ist nichts ausgefallen, es war
nichts vorgesehen. Ein Ad-hoc-Abruf (`on_demand=True`) erzeugt ebenfalls keinen Vermerk (#1007).

### 3. Neuer Zweig in `_process_pending_markers`, VOR der Segment-Schnittmenge

Der bestehende Ablauf (`:382-422`) prüft nacheinander: Trip weg/fällig (`:386-388`), keine
Segmente (`:392-395`), dann holt er Wetterdaten und bildet die Schnittmenge mit zuvor
fehlgeschlagenen Segmenten (`:397-406`). Für einen Versandfehler-Vermerk ist `failed_segment_ids`
per Definition leer — die Schnittmenge wäre also immer leer, und die Bestandslogik zöge daraus den
falschen Schluss „jetzt liegen vollständige Daten vor" und würde den Präfix „Aktualisiert — jetzt
mit vollständigen Daten" verwenden (`:422`). Das ist sachlich falsch: Bei einem Versandfehler waren
die Daten nie das Problem.

Deshalb bekommt `reason == "dispatch_error"` einen eigenen Zweig **vor** Zeile 401 (der
Segment-Schnittmengen-Prüfung), der die Wetterdaten-Fehlerprüfung überspringt und stattdessen den
eigenen Nachliefer-Text verwendet (Punkt 5).

### 4. Verfall über den Zieltag, nicht über `attempts` oder den Fehlertyp (PO-Entscheidung 1)

`attempts` wird zwar weiterhin mitgeschrieben (Diagnosewert), aber **nicht** zum
Abbruchkriterium — es wird in der Praxis nirgends gelesen (`trip_report_scheduler.py`, einzige
Fundstelle ist das Inkrement selbst) und ein Zähler kann strukturell ohnehin nicht verlässlich
hochlaufen (Punkt 7). Ebenso wird **nicht** nach Fehlertyp unterschieden (kein
`isinstance(exc, OutputConfigError)`): Die gemessene Produktivhistorie zeigt, dass ausgerechnet der
nominell „dauerhafte" Fehlertyp (Empfänger-Guard, `OutputConfigError`) beim einzigen echten
Vorfall nach rund 13 Stunden von selbst heilte.

Statt dessen: Liegt der Zieltag des Vermerks (`entry["date"]`) vor dem heutigen Tag, verfällt der
Vermerk beim nächsten stündlichen Durchlauf ohne weiteren Zustellversuch — ein Morgen-Briefing ist
am Abend wertlos.

Die eigentliche Vergleichsentscheidung (ist der Zieltag noch aktuell?) ist eine **reine Funktion
ohne I/O**, die neben `record_briefing_dispatch_failure` in
`src/services/alert_briefing_anchor.py:54` ergänzt wird — dort haken heute schon Trip UND
Ortsvergleich ein (geteilter Baustein, Teilungsregel). Sie ist ohne Mock testbar (Datum rein, Bool
raus) und kapselt die Verfallslogik an genau einer Stelle, statt sie im Scheduler zu verstreuen.

### 5. Eigener Nachliefer-Text für Versandfehler

Statt „Aktualisiert — jetzt mit vollständigen Daten" (das für einen Versandfehler falsch wäre —
der Nutzer hat kein „Vorher", das aktualisiert würde) bekommt der Versandfehler-Zweig einen
eigenen, nutzerverständlichen Text im Stil des bestehenden Wetterfehler-Präfixes (`:409-412`,
„Nachgeliefert — der Wetterdienst war um HH:00 nicht erreichbar"). Sinngemäß: „Nachgeliefert — die
Zustellung um HH:00 ist fehlgeschlagen." Kein Technikjargon (keine Exception-Namen, keine
Statuscodes) — der Text erscheint direkt im Briefing, das der Nutzer liest.

### 6. „Letzter Versuch" vor dem Verfall — warum ein separater Nachhol-Lauf zur Fälligkeitsstunde
   nicht funktioniert

Der Nachhol-Versand berechnet die Wetterdaten immer **neu für den aktuellen Zieltag** — der Aufruf
in `_process_pending_markers` (`:427-429`) übergibt bewusst kein `target_date`. Würde ein
Versandfehler-Vermerk in genau der Stunde, in der der Trip ohnehin regulär fällig ist, zusätzlich
über den Catch-up-Pfad sofort nachgeliefert, entstünde eine **zweite, fast inhaltsgleiche
Nachricht** wenige Minuten vor dem regulären Briefing derselben Stunde.

Deshalb wird die bisherige Regel „Trip ist jetzt regulär fällig → Vermerk verfällt sofort und
ersatzlos" (`:386-388`) für Versandfehler-Vermerke geändert: Der Vermerk wird **nicht mehr blind
gelöscht**, sondern bleibt bestehen, bis der reguläre Versand dieser Stunde tatsächlich **gelungen**
ist. Gelingt er, ist der Vermerk gegenstandslos und wird entfernt — der Nutzer bekam sein Briefing
auf dem regulären Weg, keine zusätzliche Nachricht war nötig. Scheitert der reguläre Versand
erneut, bleibt der Vermerk bestehen und wird in der Folgestunde weiter nachgeholt (identisch zum
bisherigen Verhalten bei jedem anderen Fehlschlag).

Das reguläre Briefing dieser Stunde **ist** damit der „letzte Versuch" aus PO-Entscheidung 3 —
gleiche Wirkung wie ein separater finaler Zustellversuch, aber ohne das Doppel-Nachrichten-Risiko.

### 7. Rekursionsschutz ist strukturell, kein Zähler nötig

Der Nachhol-Weg entfernt den Vermerk **vor** dem erneuten Sendeversuch (RMW-Reihenfolge, `:425-428`
bestehendes Muster). Schlägt der erneute Versuch wieder fehl, schreibt derselbe `except`-Block
(Punkt 2) einen **frischen** Vermerk mit `attempts=0`. Ein Zähler könnte deshalb nie über mehrere
Läufe hinweg zuverlässig hochlaufen, selbst wenn man es versuchte — die Zeitgrenze über den Zieltag
braucht dagegen keine Durchreichung zwischen den Funktionen und begrenzt trotzdem zuverlässig.

### 8. Kanaltrennung: Zustellbilanz statt Kanalreihenfolge (PO-Entscheidung 4)

`notification_service.send_trip_report` (`:275-430`) sendet heute in der Reihenfolge E-Mail
(`:354-356`, einziger Kanal ohne `try`) → SMS (`:360-368`, bereits `except Exception`) → Telegram
(fängt bisher nur `OutputError`). Scheitert E-Mail, verlässt die Ausnahme die Funktion sofort —
SMS und Telegram werden dann gar nicht mehr versucht. Ein bloßes `try/except` um den
E-Mail-Aufruf allein löst das nicht: entweder die Ausnahme wird komplett verschluckt (dann feuert
der bestehende `except`-Block bei `trip_report_scheduler.py:1035` nie mehr, und es entstünde weder
Anker (#1629) noch Vermerk), oder sie wird unverändert weitergereicht (dann entstünde ein Vermerk,
obwohl SMS/Telegram bereits zugestellt haben — die Nachlieferung würde diese Kanäle doppeln, genau
das Risiko, das PO-Entscheidung 2 beseitigen sollte).

Auflösung — **Zustellbilanz statt Kanalreihenfolge**:

1. Der E-Mail-Aufruf (`:354-356`) wird in `try/except Exception` gefasst. Der Fehler wird in einer
   lokalen Variable festgehalten und geloggt; `"email"` wird bei einem Fehlschlag NICHT zu
   `sent_channels` hinzugefügt.
2. SMS (`:360-368`) und Telegram laufen unverändert weiter — Telegram wird zusätzlich an beiden
   Stellen (`:386` Kurzform, `:408` Bubble-Schleife) von `except OutputError` auf
   `except Exception` umgestellt.
3. Am Ende der Funktion entscheidet die **Zustellbilanz** (`sent_channels`):
   - Ist `sent_channels` leer (kein einziger konfigurierter Kanal hat zugestellt), wird der
     festgehaltene Fehler am Ende der Funktion erneut ausgelöst. Der bestehende Pfad bei
     `trip_report_scheduler.py:1035` greift dadurch unverändert: Diagnose-Zeile, Anker — und neu
     der Vermerk.
   - Hat mindestens ein Kanal zugestellt, wird KEINE Ausnahme mehr ausgelöst. Der Nutzer hat sein
     Briefing bekommen; eine Nachlieferung würde nur den bereits erfolgreichen Kanal doppeln. Der
     gescheiterte Kanal bleibt trotzdem sichtbar: `record_briefing_dispatch_failure` wird für ihn
     **separat, direkt aus `notification_service.py`** aufgerufen (Diagnose-Journal +
     Health-Signal bleiben nützlich), und er fehlt in `sent_channels`.

**Tragende Invariante:** Ein Vermerk entsteht genau dann, wenn NICHTS zugestellt wurde. Das macht
Doppelzustellung strukturell unmöglich und löst den Konflikt zwischen PO-Entscheidung 2
(keine Doppelzustellung) und PO-Entscheidung 4 (Kanaltrennung) auf, ohne einen der beiden
Grundsätze aufzuweichen.

`src/output/channels/email.py` wird dabei nicht angefasst — Empfänger-Guard und Parity-Ratsche aus
#1412 S2a bleiben unberührt.

## Expected Behavior

- **Input:** ein Trip-Versandlauf (regulär oder Nachhol-Lauf), dessen `NotificationService`-Aufruf
  laut Zustellbilanz scheitert (kein Kanal hat zugestellt).
- **Output:** ein Vermerk mit `reason="dispatch_error"` wird für den echten Nutzer gespeichert
  (außer bei Ad-hoc-Abruf); der stündliche Vorlauf liefert das Briefing nach, sobald möglich, und
  spätestens beim nächsten regulär fälligen Versand; der Vermerk verfällt, sobald sein Zieltag
  vorbei ist, ohne weiteren Versuch. Der bisherige Diagnose- und Anker-Mechanismus (#1629) bleibt
  unverändert aktiv.
- **Side effects:** Ob am Ende ein Versandfehler nach oben durchgereicht wird, hängt jetzt von der
  Zustellbilanz ab (kein Kanal zugestellt ⇒ Ausnahme; mindestens einer ⇒ keine) statt von der
  bloßen Kanalreihenfolge. Ein Telegram-Fehler, der bisher als unerwartete Ausnahme durchgereicht
  wurde, geht jetzt wie jeder andere Kanalfehler in diese Bilanz ein. Kein neuer HTTP-Endpunkt,
  kein neues Journal-Format, keine Schema-Änderung an bestehenden Feldern.

## Acceptance Criteria

- **AC-1:** Given der Versand eines Trip-Briefings scheitert vollständig — kein einziger
  konfigurierter Kanal hat zugestellt (z.B. E-Mail-Fehler ohne weitere aktive Kanäle), When der
  Versandlauf beendet ist, Then liegt für diesen Trip ein Vermerk mit dem Grund „Versandfehler" und
  ohne betroffene Wetterabschnitte unter der echten Nutzerkennung des Trips vor.
  - Test: Versand mit garantiert scheiterndem E-Mail-Kanal und ohne weitere aktive Kanäle
    auslösen, danach den gespeicherten Vermerk des Nutzers lesen und prüfen, dass Grund und leere
    Segmentliste gesetzt sind.

- **AC-2:** Given ein solcher Vermerk existiert, When der stündliche Vorlauf des Schedulers das
  nächste Mal läuft, Then wird das Briefing an den Nutzer zugestellt.
  - Test: Vermerk aus AC-1 anlegen, den stündlichen Vorlauf mit funktionierendem Kanal ausführen,
    prüfen dass ein Briefing tatsächlich beim Nutzer ankommt (Versandergebnis zeigt Erfolg).

- **AC-3:** Given ein nach Versandfehler nachgeliefertes Briefing, When der Nutzer es liest, Then
  nennt der Text einen fehlgeschlagenen Zustellversuch als Grund — ausdrücklich NICHT den
  Bestandstext „jetzt mit vollständigen Daten".
  - Test: den nachgelieferten Text prüfen — er enthält einen Hinweis auf einen gescheiterten
    Versand, nicht den Wetterdaten-Präfix.

- **AC-4:** Given ein Vermerk, dessen Zieltag vor dem heutigen Tag liegt, When der stündliche
  Vorlauf läuft, Then verfällt der Vermerk ohne weiteren Zustellversuch.
  - Test: Vermerk mit einem Zieltag von gestern anlegen, Vorlauf ausführen, prüfen dass kein
    Versand ausgelöst wurde und der Vermerk danach nicht mehr existiert.

- **AC-5:** Given ein Trip ist zur aktuellen Stunde regulär fällig und dieser reguläre Versand
  gelingt, When zusätzlich ein Versandfehler-Vermerk für denselben Trip vorlag, Then ist der
  Vermerk danach verschwunden und der Nutzer erhielt genau eine Nachricht, nicht zwei.
  - Test: Versandfehler-Vermerk anlegen, den Trip zur Fälligkeitsstunde mit funktionierendem Kanal
    regulär versenden lassen, prüfen dass genau eine Zustellung erfolgte und der Vermerk entfernt
    wurde.

- **AC-6:** Given ein Trip ist zur aktuellen Stunde regulär fällig, aber der reguläre Versand
  scheitert erneut, When der Lauf beendet ist, Then bleibt der Vermerk bestehen und wird im
  nächsten stündlichen Durchlauf erneut versucht.
  - Test: Versandfehler-Vermerk anlegen, regulären Versand zur Fälligkeitsstunde erneut scheitern
    lassen, prüfen dass danach weiterhin ein Vermerk für diesen Trip existiert.

- **AC-7:** Given ein Ad-hoc-Abruf (nicht der reguläre Zeitplan) scheitert beim Versand, When der
  Aufruf beendet ist, Then entsteht KEIN Vermerk.
  - Test: Ad-hoc-Versand mit garantiert scheiterndem Kanal auslösen, danach prüfen dass kein
    Vermerk für den Trip existiert.

- **AC-8:** Given E-Mail scheitert, aber SMS und Telegram sind für den Nutzer konfiguriert und
  funktionieren, When der Versandlauf beendet ist, Then gehen SMS und Telegram trotzdem hinaus,
  E-Mail fehlt in der Zustellbilanz, und es entsteht KEIN Vermerk — der Nutzer hat sein Briefing
  bereits über die funktionierenden Kanäle bekommen.
  - Test: Versand mit garantiert scheiterndem E-Mail-Kanal und funktionierenden SMS-/
    Telegram-Kanälen auslösen, prüfen dass SMS und Telegram im Ergebnis als gesendet erscheinen,
    E-Mail fehlt, und dass für diesen Trip anschließend KEIN Vermerk existiert.

- **AC-9:** Given beim Telegram-Versand tritt eine Störung auf, mit der das System bisher nicht
  gerechnet hat, When der Versandlauf beendet ist, Then bricht der gesamte Versand deswegen nicht
  ab — der Telegram-Fehlschlag zählt wie jeder andere Kanalfehler in die Zustellbilanz
  (Implementation Details Punkt 8). Ob der Lauf am Ende als gescheitert gilt, hängt allein daran,
  ob mindestens ein Kanal zugestellt hat.
  - Test: Beim Telegram-Versand eine unerwartete Störung auslösen, während E-Mail oder SMS
    erfolgreich zustellen; prüfen, dass der Lauf normal zu Ende läuft und als erfolgreich gilt.

- **AC-10:** Given ein Wetterfehler-Vermerk (kein Versandfehler), When der stündliche Vorlauf
  läuft, Then verhält sich alles unverändert zum bisherigen Verhalten (#1012) — insbesondere bleibt
  die Regel „ein zuvor fehlendes Segment liefert weiterhin keine Daten → kein erneuter Versand"
  intakt.
  - Test: bestehende #1012-Testfälle für Wetterfehler-Vermerke laufen weiterhin unverändert grün;
    ergänzend ein Regressionstest, der einen Wetterfehler-Vermerk anlegt und prüft, dass die
    Segment-Schnittmengen-Logik weiterhin greift und die neuen Versandfehler-Zweige dabei nicht
    ausgelöst werden.

- **AC-11:** Given ein Versandfehler tritt auf, When der Fehlerpfad läuft, Then werden weiterhin
  sowohl der Wetter-Anker als auch die Diagnose-Zeile geschrieben wie vor dieser Änderung
  (Regressionsschutz für #1629) — der neue Vermerk kommt zusätzlich hinzu, nichts Bestehendes fällt
  weg.
  - Test: Versandfehler auslösen, danach prüfen dass sowohl der Wetter-Snapshot (Anker) als auch
    der Diagnose-Eintrag vorhanden sind, zusätzlich zum neuen Vermerk.

- **AC-12:** Given zwei verschiedene Nutzer haben je einen fehlgeschlagenen Versand, When beide
  Vermerke geschrieben sind, Then landet jeder Vermerk ausschließlich in der Ablage seines eigenen
  Nutzers — kein Nutzer sieht den Vermerk des anderen.
  - Test: Versandfehler für zwei unterschiedliche, echte Nutzerkennungen auslösen, danach die
    Vermerk-Ablage beider Nutzer lesen und prüfen, dass jede ausschließlich den eigenen Eintrag
    enthält.

- **AC-13:** Given E-Mail scheitert, aber SMS wird zugestellt, When der Lauf beendet ist, Then
  entsteht KEIN Vermerk, der gescheiterte E-Mail-Versand ist aber in der Diagnose-Spur festgehalten.
  - Test: Lauf mit scheiterndem E-Mail- und funktionierendem SMS-Kanal ausführen, danach prüfen,
    dass keine Nachlieferung vorgemerkt ist und die Diagnose-Zeile (`briefing_dispatch_failures.jsonl`)
    trotzdem einen Eintrag für den gescheiterten E-Mail-Versand enthält.

## Beobachtbarkeit

Der bestehende Monitor (`henemm-infra/scripts/check-gregor20.sh:199-210`) alarmiert bereits bei
`open_pending_briefings > 0` **und** `oldest_pending_age_hours > 3`. Ein nicht nachgelieferter
Versandfehler-Vermerk meldet sich damit nach drei Stunden über den **bestehenden, bereits
verdrahteten** Weg — ohne neuen Melde-Mechanismus.

Ehrlich benannt: Der Zähler `open_pending_briefings` misst danach **zwei verschiedene Dinge**
gleichzeitig — „Briefing mit unvollständigen Wetterdaten" und „Briefing nicht zugestellt". Der
begleitende Zähler `degraded_segments_total` bleibt bei einem Versandfehler-Vermerk bei 0, weil
`failed_segment_ids` immer leer ist. Das bricht nichts (Go ignoriert unbekannte Felder), verschiebt
aber die Bedeutung des bestehenden Signals — eine Aufschlüsselung nach Grund ist bewusst nicht Teil
dieser Scheibe.

## Testplan

Neue Tests gehören in `tests/tdd/test_briefing_anchor_survives_dispatch_failure.py` — läuft
**offline** (kein `pytest.mark.email`), Helfer `_run_failing_briefing` (`:220`) erzeugt bereits
einen echten `OutputConfigError` über unvollständige SMTP-Konfiguration, kein Mock der eigenen
Logik nötig. **Nicht** in `tests/tdd/test_issue_1012_no_data_guard.py` ablegen — die Datei trägt
`pytest.mark.email` und läuft weder im Standard- noch im CI-Lauf (`pyproject.toml:65` schließt
`email`/`live`/`staging` per Default aus).

## Known Limitations

- **Mehr-Empfänger-Fall bleibt ungelöst:** Ein blockierter Empfänger unter mehreren reißt weiterhin
  alle mit (Teilzustellung ist eigene Scheibe). Für Trip-Briefings praktisch selten relevant, da
  `mail_to` dort einwertig ist.
- **E-Mail-Ausfall neben einem funktionierenden Kanal wird nicht nachgeliefert:** Schlägt E-Mail
  fehl, während SMS oder Telegram zustellen, entsteht bewusst kein Vermerk — der Nutzer hat sein
  Briefing bereits erhalten, eine Nachlieferung würde den funktionierenden Kanal doppeln. Sichtbar
  bleibt der Ausfall über das Diagnose-Journal und die Zustellbilanz, nicht über eine erneute
  Zustellung des ausgefallenen Kanals selbst.
- **Bedeutungsverschiebung eines Bestandssignals:** `open_pending_briefings` heißt nach dieser
  Scheibe zusätzlich „Briefing nicht zugestellt" — siehe Abschnitt „Beobachtbarkeit".
  `degraded_segments_total` unterscheidet die beiden Fälle nicht.
- **Kein neuer Melde-Mechanismus für die #1629-Felder:** `briefing_dispatch_error_streak_since`
  und `briefing_dispatch_errors_recent_count` bleiben unausgewertet im Infra-Monitor — eigene
  Folgearbeit (MQ an `infra`), kein Bestandteil dieser Scheibe.
- 🔴 **Die Diagnose-Spur deckt nur den Ausnahme-Weg ab.** `record_briefing_dispatch_failure`
  (`alert_briefing_anchor.py:54`) wird weiterhin nur geschrieben, wenn der Versand eine Ausnahme
  wirft — also praktisch nur bei E-Mail-Fehlern. Ein SMS-only- oder Telegram-only-Ausfall erzeugt
  einen Nachliefer-Vermerk (und darüber nach drei Stunden den Infra-Alarm), erscheint aber **nicht**
  in `diagnostics/briefing_dispatch_failures.jsonl` und damit nicht im #1629-Health-Signal.
  Bewusste Entscheidung: der Alarm-Weg, der heute tatsächlich einen Leser hat, ist über den Vermerk
  abgedeckt; das #1629-Signal hat derzeit gar keinen (siehe Abschnitt „Beobachtbarkeit"). **Wer das
  Signal später verdrahtet, muss diese Lücke mitschließen** — sonst meldet es weniger, als
  tatsächlich ausfällt. Gehört in dieselbe MQ-Nachricht an `infra`.

## Changelog

- 2026-08-10: Initiale Spec. Scope auf Nachlieferung von Versandfehlern (Trip-Pfad) und
  Kanaltrennung begrenzt. Teilzustellung im Empfänger-Guard sowie Compare-Nachhol-Mechanismus
  ausdrücklich ausgeschlossen, eigene Folge-Issues.
- 2026-08-10 (nach Freigabe): Implementation Details Punkt 2 korrigiert nach Adversary-Befund F001.
  Der Vermerk hängt nicht mehr an einer geworfenen Ausnahme, sondern wird an **beiden** Ausgängen
  eines vollständig gescheiterten Versands über die geteilte Methode `_mark_briefing_undelivered`
  geschrieben — sonst wäre ein SMS-only-Briefing (Garmin-Weg, #1533) weiterhin still verloren
  gegangen. **Die Acceptance Criteria sind unverändert**: AC-1 war von Anfang an allgemein
  formuliert („kein einziger konfigurierter Kanal hat zugestellt"), die ursprünglichen
  Implementation Details erfüllten sie nur unvollständig. Zusätzlich eine Known Limitation zur
  Diagnose-Spur ergänzt, die weiterhin nur den Ausnahme-Weg abdeckt.
