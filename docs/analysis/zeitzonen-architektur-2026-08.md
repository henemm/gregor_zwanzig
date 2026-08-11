# Zeitzonen-Architektur: warum dieselbe Fehlerklasse zum zehnten Mal auftritt

- **Datum:** 2026-08-11
- **Anlass:** PO-Auftrag — „Das Thema ist schon eine Million mal gelöst worden. Recherchiere das."
- **Bezug:** ADR-0044, Issues #21, #400/#401, #856, #1280, #1345, #1378, #1383, #1399, #1402, #1470, #1667, #1697
- **Status:** Recherche-Ergebnis. Entscheidungsteil als **ADR-0051** (Status `Vorgeschlagen`),
  Umsetzung als Epic **#1722** mit den Scheiben #1723–#1727.

## Der Befund in einem Satz

Es gibt keinen Zeitzonen-Bug, es gibt **vier Uhren** im Produktivcode — und keine Regel, welche
davon in welcher Frage zuständig ist. Jede Einzelbehebung ordnet eine Aufrufstelle einer Uhr zu;
die nächste Aufrufstelle beginnt die Debatte von vorn.

## Die vier Uhren, gemessen

| Uhr | Wo verdrahtet | Was sie entscheidet |
|---|---|---|
| `Europe/Vienna` | `internal/config/config.go:20`, `api/routers/scheduler.py:34`, `scheduler_dispatch_service.py:164`, `alert_daily_limit.py:23`, `deviation_alert_engine.py:31`, `frontend/.../account/+page.svelte:269` | Wann ein Briefing fällig ist · wann Ruhezeit gilt · wann der Tageszähler kippt |
| `Etc/UTC` (Prozess-Zeitzone) | 40 × `date.today()`, 10 × `datetime.now()` ohne Zone | Welcher Tag des Trips gemeint ist |
| Ortszone des Trips | `services/trip_day.py` (ADR-0044) | Nur im Alarm-Pfad, seit #1697 |
| Browser-Zone | Frontend | Anzeige — dort ebenfalls auf Wien festgenagelt |

`Europe/Vienna` ist eine feste Konstante ohne fachliche Herleitung — keine Stelle im Code leitet
sie aus einer Eigenschaft des Trips, des Orts oder des Nutzers ab. Sie deckt sich **zufällig** mit
der Zone des Betreibers; das macht sie nicht richtig, es erklärt nur, warum der Fehler bisher
niemandem auffiel. `Etc/UTC` steht im Code, weil der Server zufällig so konfiguriert ist —
`date.today()` nennt keine Zone, es erbt die des Prozesses.

### Was das für den Nutzer heißt

Nutzer stellt „Morgenbriefing 07:00" ein. Gemessen für den 20.08.2026:

| Zone | Trip | Ankunft Ortszeit | Versatz | Inhalt-Tag | Ortstag |
|---|---|---|---|---|---|
| Europe/Paris | Korsika / GR20 | 07:00 | ±0 h | 2026-08-20 | 2026-08-20 |
| Atlantic/Canary | La Palma | 06:00 | −1 h | 2026-08-20 | 2026-08-20 |
| America/Denver | Colorado Trail | 23:00 | −8 h | 2026-08-20 | **2026-08-19** |
| America/Los_Angeles | PCT | 22:00 | −9 h | 2026-08-20 | **2026-08-19** |
| Pacific/Auckland | Te Araroa | 17:00 | +10 h | 2026-08-20 | 2026-08-20 |
| Asia/Kathmandu | Annapurna | 10:45 | +3,75 h | 2026-08-20 | 2026-08-20 |

Das „Morgenbriefing" erreicht den PCT-Wanderer um 22:00 am Vorabend — mit dem Inhalt des
folgenden Weltzeit-Tages. Auf Korsika stimmt es, weil Paris und Wien dieselbe Zone sind. **Das
Produkt ist auf genau einer Zone richtig, und zwar aus Versehen.**

Dieselbe Rechnung für die Ruhezeit `22:00–07:00`, die in Wien ausgewertet wird:

| Zone | Ruhe liegt am Ort tatsächlich von–bis |
|---|---|
| Europe/Paris | 22:00–07:00 ✓ |
| Atlantic/Canary | 21:00–06:00 |
| America/Los_Angeles | 13:00–22:00 |
| Pacific/Auckland | **08:00–17:00** — still während des Wandertags, laut die ganze Nacht |
| Asia/Kathmandu | 01:45–10:45 |

Der Alarm-Tageszähler kippt entsprechend um 15:00 (PCT) bzw. 10:00 (Neuseeland) Ortszeit — also
mitten am Wandertag.

### Auch in Mitteleuropa nicht folgenlos

Auf Korsika (UTC+2 im Sommer) fallen Weltzeit-Tag und Ortstag bei **2 von 24** möglichen
Konfig-Stunden auseinander (00:00 und 01:00). Das ist keine exotische Randlage: `#1697` hat
für den Alarm-Pfad nachgemessen, dass Mitteleuropa jede Nacht zwei Stunden betroffen ist.

## Warum die Einzelbehebungen nicht tragen

Neun Zeitzonen-Issues sind geschlossen (#21 April, #400/#401 Mai, #856 Juni, #1280/#1378/#1383/
#1399/#1402 Juli), #1470 und #1697 sind die zehnte und elfte Runde. Der Wächter aus #1402 ist
gut gebaut und greift — aber sein Geltungsbereich ist `src/output/**` plus eine Liste von
Messaging-Dateien. Er bewacht die **Darstellung** einer Uhrzeit.

Die wiederkehrenden Fehler sitzen in der **Entscheidung**: welcher Tag gemeint ist, ob ein
Versand fällig ist, ob gerade Ruhezeit gilt, wann ein Zähler kippt. Für diese Schicht existiert
kein Wächter — deshalb ist jede korrigierte Aufrufstelle in `#1697` einzeln gehärtet worden, und
deshalb steht im selben Commit „nicht in dieser Scheibe: die weiteren zwölf Fundstellen".

## Das Modell, das die Sache anderswo löst

Der Stand der Technik (`java.time`, Noda Time, `temporal` in JS; in Python `datetime` +
`zoneinfo`) trennt **drei Begriffe**, die im Projekt heute alle „datetime" heißen:

| Begriff | Bedeutung | Beispiel im Produkt |
|---|---|---|
| **Zeitpunkt** (*instant*) | ein Punkt auf der Weltzeitlinie, eindeutig | „wann ging die Mail raus", Messwert-Zeitstempel |
| **Kalenderzeit** (*civil / local*) | Wanduhr- oder Kalenderangabe **ohne** Zone, allein bedeutungslos | „07:00", „2026-08-20", Etappendatum |
| **Zone** | IANA-Kennung | `Europe/Paris` |

Daraus folgen drei Regeln, und alle drei sind mechanisch prüfbar:

**Regel 1 — Vergangenes ist ein Zeitpunkt, Geplantes ist Kalenderzeit + Zone.**
Ein Protokolleintrag wird als UTC-Zeitpunkt gespeichert. Ein *künftiger* Termin wird **nie** als
vorausberechneter UTC-Zeitpunkt gespeichert, sondern als Wanduhrzeit plus Zonen-Kennung. Grund:
Zonenregeln ändern sich (Regierungen schaffen Sommerzeit ab), und der Nutzer meint „07:00 bei
mir", nicht „05:00 in Greenwich". Das Produkt speichert `morning_time: "07:00"` — richtig — und
wertet es dann in einer fremden Zone aus, was die Regel wieder aufhebt.

**Regel 2 — Die Zone gehört an die Daten, nicht an den Server.**
Zuständig ist die Zone des Gegenstands, über den geredet wird: bei einem Trip die des Wegpunkts,
bei einem Ort die des Orts. `SavedLocation` hat bereits ein `Timezone`-Feld; `Trip`/`Stage` haben
keins und lösen über Koordinaten auf (`trip_day.py`). Eine Server- oder Betreiberzone ist in
keiner fachlichen Frage die richtige Antwort.

**Regel 3 — Keine Umgebungsuhr.**
`date.today()`, `datetime.now()` ohne Zone und `time.Local` sind verboten; „jetzt" wird als
Parameter hereingereicht. Das Projekt kann das schon: `alert_daily_limit.py` schreibt es sich
ausdrücklich vor („`now` ist durchgehend Funktionsparameter"), `#1697` reicht `now_utc` durch den
ganzen Lauf. Es gilt nur nirgends verbindlich.

## Übertragung auf Gregor Zwanzig

### Der eine Umbau, der die Wien-Konstante entfernt

Heute (`trip_report_scheduler.py:345-358`) fragt der Versand:

> Es ist 07:00 **in Wien** — welche Trips haben 07:00 konfiguriert?

Eine globale Uhr, N Trips. Richtig wäre die Umkehrung:

> Für jeden Trip: wie spät ist es **in seiner** Zone — passt das zu seiner Konfiguration?

Der Cron tickt weiter stündlich; er liefert nur noch einen Zeitpunkt, keine Stunde mehr. Die
Schleife über die Trips existiert bereits (`_collect_due_trips`) — der Stundenvergleich wandert
hinein, und die Zone kommt aus derselben Quelle, die der Alarm-Pfad seit #1697 benutzt
(`trip_day.trip_local_today` / `display_tz`). Das **löscht** die Wien-Konstante, statt einen
weiteren Sonderfall danebenzustellen.

Dasselbe gilt unverändert für Ruhezeit (`deviation_alert_engine`), Tageszähler
(`alert_daily_limit`) und den Ortsvergleich (dort liefert `SavedLocation.timezone` die Zone
direkt).

### Stundengleichheit ist als Fälligkeitsprüfung falsch

Gemessen an echten Umstellungstagen:

| Zone | Datum | Tageslänge | fehlende Ortsstunde | doppelte Ortsstunde |
|---|---|---|---|---|
| Europe/Paris | 2026-03-29 | 23,0 h | **02** | — |
| Europe/Paris | 2026-10-25 | 25,0 h | — | **02** |
| America/Los_Angeles | 2026-03-08 | 23,0 h | **02** | — |
| Pacific/Auckland | 2026-09-27 | 23,0 h | **02** | — |
| Australia/Lord_Howe | 2026-04-05 | 24,5 h | — | **01** |

Mit `konfigurierte_stunde == aktuelle_stunde` heißt das: ein auf 02:00 gestelltes Briefing
**entfällt ersatzlos** am Frühjahrs-Umstellungstag und geht am Herbsttag **zweimal** raus. Das
ist keine Randnotiz — es ist die Fehlerklasse, die ADR-0044 unter „Wer eine Bezugsgröße von
Weltzeit auf Ortszeit umstellt, holt sich die Sommerzeit-Frage neu ins Haus" bereits benannt hat.

Die übliche Lösung ersetzt Gleichheit durch **Fälligkeit plus Idempotenz-Schlüssel**:

- fällig, wenn `ortszeit_stunde >= konfigurierte_stunde` **und** für `(trip_id, ortstag, slot)`
  noch nichts vermerkt ist;
- nach Versand wird genau dieser Schlüssel vermerkt.

Ein Mechanismus deckt damit vier Fälle ab: fehlende Stunde (nachgeholt), doppelte Stunde (nur
einmal), ausgefallener Tick, Scheduler-Neustart. Die „pending marker" im Scheduler sind bereits
die Hälfte davon — es fehlt der Ortstag im Schlüssel.

### Der Wächter muss von der Darstellung in die Entscheidung wandern

`tests/test_output_timezone_guard.py` ist die richtige Bauform (AST-Ratsche, `KNOWN_VIOLATIONS`
darf nur schrumpfen). Zu erweitern ist der Geltungsbereich auf `src/services/**` und `api/**`,
mit diesen Fundmustern:

1. `date.today()` und `datetime.now()` ohne `tz`-Argument — die Umgebungsuhr;
2. `ZoneInfo("Europe/Vienna")` (und jede feste Zone) außerhalb von Testdateien und
   Provider-Anfragen — eine geratene Zone;
3. `.hour` / `.date()` auf einem Zeitstempel, der nicht nachweislich durch eine Zonen-Auflösung
   gegangen ist — der eigentliche Fehler von #1470 und #1697.

Muster 1 und 2 sind heute ohne Kontextwissen entscheidbar. Muster 3 ist die interessante und
die teuerste Prüfung; sie sollte einer eigenen Scheibe vorbehalten bleiben, nicht die ersten
beiden aufhalten.

## Vorgeschlagene Schnittfolge

| Scheibe | Inhalt | Warum in dieser Reihenfolge |
|---|---|---|
| **S0** (#1722) | ADR: die drei Regeln beschließen, ADR-0044 als Spezialfall darunter einordnen | Ohne beschlossene Regel bleibt jede Scheibe Geschmacksfrage |
| **S1** (#1723) | Wächter-Ausweitung, Muster 1+2, Bestand als `KNOWN_VIOLATIONS` | Stoppt den Zuwachs sofort, ohne eine Zeile Produktivcode zu bewegen |
| **S2** (#1724) | Fälligkeit umkehren: Stundenvergleich je Trip in seiner Zone; Wien-Konstante fällt | Der eine Umbau mit der größten Nutzerwirkung |
| **S3** (#1725) | Gleichheit → Fälligkeit + Idempotenz-Schlüssel `(trip, ortstag, slot)` | Setzt S2 voraus; ohne S2 gibt es keinen Ortstag |
| **S4** (#1726) | Ruhezeit, Tageszähler, Ortsvergleichs-Slots auf die Ortszone | Gleiche Wurzel, eigene Nutzerwirkung, eigener Nachweis |
| **S5** (#1727) | Restliche `date.today()`-Fundstellen; `KNOWN_VIOLATIONS` schrumpft auf null | Aufräumen, wenn die Regel schon trägt |

Der offene Briefing-Pfad aus #1697 (`_get_target_date`, `_get_active_trips`, `save_dated`) ist
Teil von S2/S5 — er sollte **nicht** vorher einzeln behoben werden, sonst entsteht die zwölfte
Einzelbehebung.

## Was bewusst offen bleibt

**Trips über mehrere Zeitzonen.** ADR-0044 hat das entschieden (Anker = Etappe des
Weltzeit-Tages, Restfehler = Zonendifferenz zweier benachbarter Etappen). Dieses Papier ändert
daran nichts.

**Eine Nutzer-Zeitzonen-Einstellung.** ADR-0044 hat sie verworfen: der Wanderer ist unterwegs,
nicht zu Hause. Bleibt verworfen — die Zone kommt aus den Wegpunkten. Für Trips **ohne**
Wegpunkte bleibt der bestehende UTC-Rückfall, sichtbar gekennzeichnet (`local_stamp`).

**Anzeige im Frontend.** Die Wien-Verdrahtung in `account/+page.svelte` ist derselbe Fehler, aber
im Anzeigepfad und ohne Versandwirkung. Gehört in S4 oder später, nicht in die kritische Kette.
