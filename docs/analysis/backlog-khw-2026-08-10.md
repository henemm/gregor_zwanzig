# Backlog-Analyse & Priorisierung — Karnischer Höhenweg ab 20.08.2026

**Stand:** 2026-08-10 · **82 offene Issues** · Anlass: Wanderung auf dem Karnischen Höhenweg
(Grenzkamm AT/IT) ab dem 20.08., alle Kanäle inkl. Premium-SMS auf dem Garmin inReach.

Dieses Dokument ist eine Momentaufnahme zur Entscheidungsfindung. Die Single Source of Truth
für offene Arbeit bleibt GitHub Issues; die hier vergebenen `session:`-Label sind der
Mechanismus, die Rangfolge unten ist die Empfehlung.

---

## 1. Bedeutung der `session:`-Label (Auslegung, korrekturbedürftig)

Es existieren genau fünf `session:`-Label, alle **ohne Beschreibung**. Ich habe die Bedeutung
aus der bisherigen Verwendung abgeleitet: ein `session:`-Label ist kein Themengebiet, sondern
ein **Arbeitsstrang** — es sagt, welche parallele Sitzung ein Issue besitzt. Das passt zur
Projektregel „Ein Projektordner = höchstens eine Claude-Session" und macht die Forderung nach
*eindeutigen* Labeln erklärbar: genau ein Besitzer je Issue, damit parallele Sitzungen sich
nicht in dieselben Dateien schreiben.

| Label | Arbeitsstrang | Hauptsächlich berührter Code |
|---|---|---|
| `session:khw` | **Liefer-Zug bis 20.08.** — was für die Wanderung stehen muss | Premium-SMS-Kette, Trip-Ablage, Briefing-Ausgabe |
| `session:alarm` | Alarm-Pfad: Auslösung, Zeitfenster, Ruhezeiten, Radar/NowCast | `trip_alert.py`, `weather_change_detection.py`, `alert_log.py`, `radar_service.py` |
| `session:gewitter` | Gewitter-Signale und amtliche Warnungen (Quellen, Schwellen, Stufenskala) | `src/providers/`, `src/services/official_alerts/` |
| `session:taskforce` | Sicherheit, Egress, Secrets, Gates, CI, Testsuite, Altlast-Rückbau | `.claude/hooks/`, `tests/`, `.github/` |
| `session:unity` | Geteilte Quellen: Trip ↔ Ortsvergleich, Datenmodell, Ausgabe-Konsistenz | `components/shared/`, Renderer, `internal/model/` |

**Neue Label habe ich bewusst nicht angelegt** — die fünf reichen für eine kollisionsarme
Aufteilung aller 82 Issues.

> ⚠️ Wenn diese Auslegung nicht stimmt, ist die Zuordnung unten falsch, nicht die Rangfolge.
> Die Rangfolge steht unabhängig von der Label-Frage.

---

## 2. Was für den KHW faktisch gilt (gemessen, nicht vermutet)

Drei Punkte, die die Priorisierung stärker verändern als jede Aufwandsschätzung:

**a) Amtliche Warnungen für AT und IT sind angebunden.**
`src/services/official_alerts/__init__.py:40-41` registriert `MeteoAlarmFeedSource("IT")` und
`MeteoAlarmFeedSource("AT")`, davor `GeoSphereWarnSource` (AT). Für den Grenzkamm ist die
amtliche Warnkette also **vorhanden**. Folge: #1681 (MeteoAlarm DE), #1442 (CH → Skandinavien),
#1440 (DWD-CAP) sind **keine** KHW-Blocker, obwohl drei davon `priority:high` tragen.

> ⚠️ **Gegenläufiger Befund aus #1445, der genau AT+IT trifft:** die MeteoAlarm-REST-API ist auf
> 100 Requests/Tag begrenzt, und eine Index-Auffrischung kostet durch die Pagination **40–160
> Calls für AT+IT** — „das Tageskontingent ist nach 1–2 Zyklen leer". Das sind exakt die beiden
> Länder dieser Tour. #1445 hält zugleich einen **Sofort-Hebel ohne eine Zeile Code** fest:
> *„AT aus der MeteoAlarm-Länderliste nehmen — GeoSphereWarnSource deckt AT ab; halbiert den
> REST-Verbrauch sofort."* Der MQTT-Umbau selbst ist Arbeit für nach der Tour, dieser eine
> Handgriff nicht.

**b) Der DPC-Defekt aus #1648 trifft den KHW nicht.**
`_region_bucket()` (`src/services/radar_service.py:658-668`) prüft die Boxen der Reihe nach:
RADOLAN → **INCA** → DPC → AROME-FR → ICON-D2. Der KHW liegt bei ~46,5–46,8 °N / 12,4–13,5 °O
und damit vollständig in der INCA-Box (46,3–49,1 °N / 9,5–17,2 °O) — DPC wird gar nicht erst
erreicht. #1648 bleibt für den GR20 gravierend, ist aber für diese Tour nicht kritisch.

> **Randbedingung, die zu prüfen ist:** die Grenze liegt bei **46,3 °N**. Jede Etappe, die
> südlich davon verläuft, fällt still auf DPC und verliert damit den NowCast komplett. Beim
> Anlegen der Etappen ist das die einzige geografische Kante, die zählt.

**c) Winterthemen sind für August irrelevant.** #1473 (Lawinenstufe in der SMS) und #1441
(Lawinen-Lageberichte) fallen aus dem Liefer-Zug — im August gibt es keine Lawinenlage.

---

## 3. 🔴 Offene Sachfrage vor allem anderen: stimmt der Zeitraum des Trips?

Aus #1707 und #1708, beide am 2026-08-10 gemessen am Produktivstand:

| `henning/5f534011` („KHW 403") | Zeitraum | `alert_channels` | SMS |
|---|---|---|---|
| `trips/` (tote Ablage) | 2026-08-20 .. 09-01 | `None` | `send_sms: true` |
| `briefings/` (**live, maßgeblich**) | **2026-08-08 .. 08-20** | `{email, telegram, sms}` | **`send_sms: false`** |

Die **tote** Datei trägt den Zeitraum, der zur angekündigten Wanderung passt (ab 20.08.); die
**lebende** endet am 20.08., also am Tag des Aufbruchs. Wenn der Live-Trip nicht umdatiert wird,
läuft die Tour ohne Briefings und ohne Alarme — und zwar völlig geräuschlos, weil ein
abgelaufener Trip nichts meldet.

Ich kann das aus dieser Sitzung nicht nachmessen (kein Zugriff auf `/var/lib/gregor`). **Das ist
die erste Aufgabe vor jeder Code-Arbeit**, und sie dauert fünf Minuten:
`GET :8000/api/_internal/trip/5f534011/loaded?user_id=henning`.

Zweitens: `send_sms: false` im Live-Trip. Für einen Trip, dessen Briefings per (Premium-)SMS
ankommen sollen, ist das die falsche Einstellung.

---

## 4. Rangfolge

### P0 — muss vor dem 20.08. stehen (10 Tage)

| # | Issue | Warum jetzt |
|---|---|---|
| 1 | *(kein Issue)* Trip „KHW 403" umdatieren und Kanäle prüfen | Siehe Abschnitt 3. Ohne das ist alles andere wirkungslos. |
| 2 | **#1701** — Premium-SMS im Alarm- und Vergleichspfad | S2a (Briefing) ist geliefert. Ohne S2b erreicht **kein Alarm** den inReach — das ist der eigentliche Zweck des Kanals unterwegs. |
| 3 | **#1533** — Generalprobe auf dem echten Gerät | Der einzige Beleg, dass die Kette trägt. #1676 hält ausdrücklich fest: dass eine SMS mit numerischem Absender das Gerät erreicht, ist **abgeleitet, nicht bewiesen**. Muss mit Puffer vor dem 20.08. laufen. |
| 4 | **#1671** — Gewitter-Tageswort im Kurzformat aus dem Gehzeit-Aggregat | Das Kurzformat **ist** das Garmin-Format. Dieselbe Wurzel wie #1584: ein Gewitter nach Ankunft steht nicht drin. Auf 160 Zeichen über Satellit ist eine falsche Gewitteraussage der teuerste Fehler im Backlog. |
| 5 | **#1599** — Tagesfenster-Obergrenze: Anzeige rechnet Stunde 19 mit, der Alarm nicht | Ein Gewitter um 19:30 Ortszeit steht im Briefing und löst **keinen** Alarm aus. Alpine Nachmittagsgewitter enden nicht um 19:00. |
| 6 | **#1709** — Wallclock-Ratsche fängt die indirekte Zeitabhängigkeit nicht | Die CI war am Abend des 10.08. für **jede** Lieferung rot. Bei zehn Tagen Restzeit ist ein Liefer-Zug, der abends stehenbleibt, ein Terminrisiko. |
| 7 | **#1707 + #1708** — tote Trip-Ablage | Hat in vier Tagen **zweimal** zu falschen Aussagen über genau diesen Trip geführt und einmal zu einer Änderung an den falschen Daten. Solange sie steht, ist jede Diagnose während der Tour unzuverlässig. |
| 8 | **#1557** — Versand meldet `sent`, obwohl kein Wetter vorlag | Unterwegs ist das Protokoll die einzige Rückmeldung. Ein `sent` ohne Inhalt macht sie wertlos. |

### P1 — sollte vor dem 20.08. stehen, kippt die Tour aber nicht

| Issue | Warum |
|---|---|
| **#1685** + **#1594** | Alarm-Rauschen: Meldungen, die eine Stunde später das Briefing wiederholt. Auf einem kostenpflichtigen Satellitenkanal ist Rauschen nicht kosmetisch. #1685 ist die Regel, #1594 die Bündelung am Ruhezeit-Ende — gehören zusammen gedacht. |
| **#1654** | Rohe Programmnamen `MED`/`HIGH` in der Abend-Mail statt „mittel"/„hoch". Kleiner Fix, direkt sichtbar. |
| **#1670** | Formatdetails Trip-Mail (mobil). Der PO liest die Mail unterwegs auf dem Telefon. |
| **#1667** / **#1697** | Beide gefixt und gemergt (`a93a33e`, `233a101`). **Vor dem Aufbruch schließen oder den Restumfang benennen** — offene Issues zu erledigter Arbeit verstellen in zehn Tagen die Sicht. |
| **#1596** | Stiller Rückfall `premium → free` senkt das Alarm-Tageslimit auf 2. Tritt nur bei unlesbarer `user.json` auf — geringe Wahrscheinlichkeit, aber unterwegs nicht diagnostizierbar. |
| **#1445** (nur der Sofort-Hebel) | AT aus der MeteoAlarm-Länderliste nehmen, weil `GeoSphereWarnSource` Österreich ohnehin abdeckt. Halbiert den REST-Verbrauch für genau die Länder dieser Tour, ohne eine Zeile Code. Der MQTT-Umbau selbst bleibt P2. |

### P2 — nach der Tour

Alles Übrige. Ausdrücklich **heruntergestuft** trotz `priority:high`, weil ohne KHW-Bezug:

- **#1681** (MeteoAlarm DE), **#1442** (CH/Skandinavien), **#1440** (DWD-CAP) — AT/IT sind bereits angebunden (Abschnitt 2a).
- **#1647** (Météo-France 401), **#1507** (MF-Hagel), **#1648** (DPC-NowCast), **#1174** (DPC-Signal IT) — Frankreich/Korsika bzw. DPC-Gebiet; der KHW läuft über INCA (Abschnitt 2b).
- **#1678/#1679/#1680** (Gewitter-Schwellenleitern) — Verbesserung der Einstufung, kein Ausfall. Eine ungeeichte Leiter kurz vor der Tour zu ändern ist eher Risiko als Gewinn.
- **#1473** (Lawinenstufe), **#1441** (Lawinen-Lageberichte) — August.
- **#1702** (Kostenstelle Premium-SMS) — laut #1702 selbst ausdrücklich kein Blocker für #1533.
- Alle Epics (#1230, #1374, #1419, #1435, #1458, #1703) und alle Gate-/Testsuite-Sammelprojekte (#1196, #1197, #1199).

---

## 5. Label-Zuordnung — alle 82 offenen Issues

| Strang | Anzahl | Issues |
|---|---|---|
| `session:khw` | 15 | 1709, 1708, 1707, 1702, 1701, 1676, 1671, 1670, 1654, 1557, 1533, 1473, 1064, 735, 18 |
| `session:alarm` | 15 | 1699, 1697, 1695, 1685, 1667, 1658, 1648, 1599, 1594, 1584, 1539, 1468, 1467, 1458, 1430 |
| `session:gewitter` | 21 | 1681, 1680, 1679, 1678, 1657, 1647, 1581, 1531, 1507, 1506, 1493, 1488, 1480, 1475, 1445, 1443, 1442, 1441, 1440, 1419, 1174 |
| `session:taskforce` | 22 | 1689, 1688, 1640, 1636, 1631, 1617, 1611, 1596, 1593, 1579, 1573, 1490, 1489, 1487, 1369, 1337, 1309, 1225, 1199, 1197, 1196, 929 |
| `session:unity` | 9 | 1703, 1563, 1435, 1433, 1412, 1405, 1374, 1356, 1230 |

Begründungen für die weniger offensichtlichen Zuordnungen:

- **#1488 / #1480 → `gewitter` statt `unity`.** Beide sind fachlich Vereinheitlichungsthemen
  („eine geteilte Quelle für die Stufenskala"), fassen aber genau die Dateien an, an denen der
  Gewitter-Strang ohnehin arbeitet. Zusammen in einem Strang gibt es keinen Merge-Konflikt.
- **#1611 → `taskforce` statt `alarm`.** Trägt `area:alerts`, ist aber ein Egress-Leck: ein Test
  versuchte echten SMTP-Versand. Gehört zur Ausgangs-Sperre, nicht zum Alarm-Pfad.
- **#1445, #1442, #1441, #1440 → `gewitter`.** Quellen für amtliche Warnungen; der Gewitter-Strang
  besitzt `src/services/official_alerts/` bereits über #1681/#1657.
- **#1539 → `alarm`.** Die sequenzielle Verarbeitung ist als Kapazitätsthema formuliert, die
  gemeldete Wirkung sind ausfallende Alarm-Ticks.
- **#1709 bleibt `khw`.** Inhaltlich Test-Infrastruktur, also `taskforce` — aber es blockiert
  genau den Liefer-Zug, der bis zum 20.08. laufen muss. Nach der Tour gehört es nach `taskforce`.

---

## 6. Dubletten und Schließ-Kandidaten

| Issue | Empfehlung |
|---|---|
| **#1707 / #1708** | **Dublette.** Zwei Sitzungen haben denselben Befund im Abstand von fünf Minuten aufgeschrieben. #1708 ist reicher (nennt die vier Fehlwirkungen, die Code-Stellen und die bereits ausgeführte Sofortmaßnahme). Vorschlag: #1707 als Dublette von #1708 schließen, den Dublettenzähler (14 von 14, alle divergent) vorher nach #1708 übernehmen. |
| **#1697** | Gefixt und gemergt (`233a101`, PR #1705). Schließen. |
| **#1667** | S1 und S2 gemergt (`70faaa6`, `a93a33e`). Prüfen, ob Restumfang offen ist — sonst schließen. |
| **#18** | „F9: Satellite Messenger (Garmin inReach)", `status:deferred`. #1676 sagt ausdrücklich: „bleibt deferred — der Premium-SMS-Weg ersetzt die native Integration." Ein Issue, das durch ein anderes ersetzt wurde, gehört geschlossen (`not planned`), nicht aufbewahrt. |
| **#735** | „SMS-Inbound" überschneidet sich mit #1676 S1, und S1 ist geliefert (`04cabd8`). Entweder schließen oder auf den Restumfang (Kommando-Verarbeitung statt nur Rückadresse) zusammenstreichen. |

Ich habe **keins** dieser Issues geschlossen — das ist eine PO-Entscheidung.

---

## 7. Was ich an bestehenden Labeln geändert habe

Neben den 48 neu vergebenen `session:`-Labeln habe ich fehlende `priority:`-Label ergänzt und
drei bestehende Prioritäten bewusst verschoben. Nur diese drei, damit die Änderung nachprüfbar
bleibt:

| Issue | Vorher | Nachher | Grund |
|---|---|---|---|
| #1681 (MeteoAlarm DE) | `high` | `medium` | Deutschland, ohne KHW-Bezug; AT/IT sind angebunden. |
| #1445 (MeteoAlarm MQTT) | `critical` | `high` | Der volle MQTT-Umbau ist in zehn Tagen nicht realistisch. Der Sofort-Hebel daraus steht als P1 in der Rangfolge — er braucht keine `critical`-Markierung am Gesamt-Issue. |
| #1654 (rohe `MED`/`HIGH`) | *(keine)* | `medium` | Nutzersichtbar in jeder Abend-Mail, aber kein Ausfall. |

Alles andere behält seine Priorität; ich habe nur ergänzt, wo keine gesetzt war.
