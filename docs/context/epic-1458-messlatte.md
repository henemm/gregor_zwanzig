# Context: epic-1458-messlatte

## Request Summary

Das Epic #1458 („Alerts neu ordnen") hat alle fünf Scheiben geliefert. Offen ist genau ein
Punkt seiner eigenen Erledigt-Liste: der **Messlatte-Nachweis** — *„Juni 76 · Juli 31 ·
August (bis 02.) 3 Meldungen. Ziel ist weniger Wiederholung, nicht weniger echte Warnung —
mit den Daten aus #1459 belegen."* Diese Arbeit soll den Nachweis erbringen und daraus
ableiten, ob das Epic schließt oder Folgetickets bekommt.

## Umfang gegen `origin/main` gemessen (nicht gegen die Beschreibung vom Anlegetag)

| Scheibe | Issue | Stand |
|---|---|---|
| Protokoll | #1459 | geschlossen, live **2026-08-02** (`161db8bb`) |
| Relevanzfilter T1 | #1460 | geschlossen, live **2026-08-03** (`8f2053f9`) |
| Ablaufsteuerungen zusammenlegen | #1467 | geschlossen — S2 AG5 **08-04**, S3 **08-08**, S4a/S4b-1 **08-16** |
| Schwelle je Kanal | #1461 | geschlossen |
| Bedienung / Ortsvergleich | #1462 / #1463 | geschlossen 08-06 (beide beim Aufschlagen bereits erfüllt) |
| Vorgänger | #1444 | geschlossen 08-03 |
| E6 Beobachtbarkeit | → **#1948** | läuft in **anderer Sitzung** — hier nicht anfassen |

## Related Files

| Datei | Relevanz |
|---|---|
| `src/services/alert_log.py` | **Einzige** Schreibfunktion des Protokolls; definiert das gesamte Vokabular und den Aufbau |
| `src/services/alert_log.py:239` | Weiche `entries` vs. `not_delivered` — Kern der Messfalle M1 |
| `src/services/alert_log.py:242-254` | `_append()` — Read-Modify-Write der ganzen Datei, **keine Rotation, keine Kappung** |
| `src/services/alert_log.py:337-341` | Vermerk: ein Alarm-Lauf erzeugt **bis zu drei** Einträge; `DEDUP_WINDOW = 2 min` — Kern der Messfalle M2 |
| `src/services/alert_log.py:45-61` | Vollständiges Grund-Vokabular (unten ausgeschrieben) |
| `internal/store/log.go` | Lesepfad Go: `AlertCountByEntity()` zählt **Einträge**, nicht Kanäle; `not_delivered` wird **nie** gelesen (D4) |
| `docs/specs/modules/feat_1459_alert_protokoll.md` | Spec der Protokoll-Scheibe, inkl. der offenen Lücke O3 |
| `docs/context/konzept-1458-alerts-zweck.md` | Technische Landkarte des Epics vom 2026-08-02 |

## Datenlage

| Ort | Befund |
|---|---|
| `/var/lib/gregor/users/henning/alert_log.json` | 76 627 Bytes, zuletzt 2026-08-17 18:52 — **die einzige belastbare Quelle** |
| `…/users/steffi/alert_log.json` | endet 2026-07-02 — kein August, für den Vorher/Nachher-Vergleich unbrauchbar |
| `…/users/default/alert_log.json` | endet 2026-07-12 — dito |
| `/home/hem/gregor_zwanzig/data/users/` | enthält **kein** `alert_log.json`; Prod liest aus `GZ_DATA_DIR=/var/lib/gregor` (systemd `gregor-api`) |

**Der Nachweis ist damit eine Ein-Nutzer-Messung** (`henning`). Das ist keine Schwäche der
Arbeit, sondern die Datenlage — muss aber im Ergebnis stehen.

Rohauszählung (Stand 2026-08-17 20:35):

| Liste | Juni | Juli | August (bis 17.) | Summe |
|---|---|---|---|---|
| `entries` | 76 | 31 | 50 | 157 |
| `not_delivered` | 0 | 0 | 68 | 68 |

## Existing Patterns

- **Ein Schreibmodul, zwei Schreibpfade.** `append_entry()` (nach Zustellversuch) und
  `append_suppressed_entry()` (vor dem Versand abgewiesen, #1467 S3). Letzterer schreibt
  ausschließlich nach `not_delivered` und **nur aus den beiden Nowcast-Pfaden** — Vorhersage-
  Änderung und amtliche Warnung protokollieren ihre Unterdrückungen bis heute **nicht**
  (offene Lücke O3 in `feat_1459_alert_protokoll.md`).
- **Zusammenfassen beim Lesen, nie im Protokoll** (`alert_log.py:337-341`). Das Protokoll ist
  bewusst roh; jede Auswertung muss selbst zusammenfassen.
- **Vokabular ist bewusst ein freier String, kein Enum** (`:40-44`), damit neue Gründe additiv
  dazukommen. Folge: die Grundmenge hat über die Epic-Laufzeit **gewachsen**.

**Auslöser einer Meldung** (`reason` des Eintrags): `forecast_change` · `nowcast` ·
`official_alert`

**Gründe einer Nicht-Zustellung** (`channels_not_sent[].reason`): `channel_disabled` ·
`delivery_failed` · `quiet_hours` · `daily_limit` · `cooldown` · `below_channel_threshold`
(#1461) · `event_duplicate` (#1467 S4b-1)

## Risks & Considerations

**M1 — `entries` und `not_delivered` sind nicht dieselbe Größe, und die zweite Liste gibt es
erst seit August.** Juni/Juli haben 0 Einträge in `not_delivered`, weil die Liste damals nicht
existierte — nicht, weil nichts unterdrückt wurde. Ein Vergleich „76 → 118" behauptet eine
Verdopplung, die reine Buchführung ist; ein Vergleich „76 → 50" behauptet eine Halbierung, die
ebenso wenig belegt ist.

**M2 — Ein Eintrag ist keine Nachricht.** Ein Alarm-Lauf erzeugt bis zu drei Einträge
(Vorhersage, Radar, amtlich sind drei getrennte `append_entry()`-Aufrufe, Millisekunden
auseinander). Im Juni war faktisch ein Melder aktiv, im August drei. Die Eintragszahl steigt
also allein durch die Quellenzahl, ohne dass der Nutzer eine Nachricht mehr bekäme. Die
Auswertung **muss** über `DEDUP_WINDOW` (2 min) auf Vorfälle zusammenfassen, bevor sie zählt.

**M3 — Die Wirkung des Epics ist erst seit 2026-08-16 vollständig live.** Die letzte Scheibe
(#1467 S4b-1, quellenübergreifende Entdopplung) ging gestern in Betrieb. Ein „August"-Zeitraum
ist damit kein einheitlicher Zustand, sondern eine Treppe. Sinnvolle Schnitte: **vor 08-02**
(Altzustand), **08-04 bis 08-15** (Relevanzfilter + Kanal-Schwelle live), **ab 08-16**
(vollständig).

**M4 — Ungleiche Vergleichsbasis.** Juni umfasst laut Epic-Text drei Touren; August ist
KHW-Vorbereitung mit intensiver Test- und Staging-Aktivität. Wetterlage, Tourenzahl und
Testverkehr unterscheiden sich. Eine Zahl allein trägt die Aussage nicht — die Auswertung
braucht eine Größe, die gegen diese Störgrößen robust ist (Kandidat: Anteil wiederholter
Meldungen an allen Meldungen, statt absolute Meldungszahl).

**M5 — Das Ziel ist zweiseitig.** „Weniger Wiederholung, **nicht** weniger echte Warnung."
Ein Rückgang der Gesamtzahl allein ist deshalb **kein** Erfolgsnachweis — er könnte genauso
die Fehlerlage sein, vor der #638 warnt. Beide Seiten brauchen je einen eigenen Beleg.

**M6 — Keine Rotation.** `_append()` schreibt die volle Datei ohne Kappung. Ältere Monate sind
also **nicht** abgeschnitten; der Vergleich ist insoweit vollständig.

## Abgrenzung zu anderen Sitzungen

- **#1948** (Sitzung `1948`) besitzt Format und Beobachtbarkeit der Alarm-Nachrichten (E6).
- **#1945**, **#1493** sind eigene laufende Alarm-Stränge.
- Diese Sitzung fasst **keine** Alarm-Laufzeitdateien an (`trip_alert.py`, `compare_alert.py`,
  `alert_log.py`, Alarme-Reiter). Der Nachweis ist eine Auswertung, kein Umbau.

---

# Analysis

## Type

**Feature** — Nachweis- und Auswertungsarbeit. Kein Bug, kein Produktivcode zu erwarten.

## Korrekturen an der Kontext-Phase (alle belegt, alle zu meinen Ungunsten)

**M2 ist entkräftet.** Ich hatte vermutet, die Eintragszahl steige allein durch die Quellenzahl.
Zwei unabhängige Belege sagen das Gegenteil:
- Die Faltung auf Nutzer-Vorfälle ergibt **1,01 / 1,00 / 1,00** Zeilen pro Vorfall — die drei
  Quellen feuern in der Praxis praktisch nie gleichzeitig.
- Schon im Altstand schrieben **alle drei** Quellen ins Protokoll: `trip_alert.py:323`
  (Vorhersage-Änderung), `:978` (Radar), `:1210` (amtliche Warnung), Stand `161db8bb~1`.

**M1 ist kleiner als gedacht.** `alert_log.json` existiert seit `31d7a366` (2026-05-27, #393),
nicht erst seit #1459. Es gab **nie** eine Datei-Migration, nur sieben additive Feld-
Erweiterungen. Die Juni-Zahlen sind unverfälschte Rohdaten. Neu ist allein die Liste
`not_delivered` — der Mengenvergleich der `entries` ist damit zulässig.

**Zeilen mit Vorfällen verwechselt (nachgetragen 2026-08-18).** Ich hatte `event_duplicate`
mit **4** gezählt und daraus abgeleitet, die quellenübergreifende Entdopplung wirke. Die 4 sind
Protokoll**zeilen**: je Vorfall werden zwei Kanäle gesperrt (E-Mail + Telegram). Es sind
**2 Vorfälle**. Gefunden hat das nicht mein eigener Durchgang, sondern eine **externe
Methodik-Prüfung** — mein Zählskript summierte `channels_not_sent`-Einträge, die restliche
Auswertung zählte durchweg Vorfälle. Derselbe Fehler wäre bei jedem Sperrgrund möglich, denn
**jeder** Grund erzeugt pro Vorfall so viele Zeilen, wie Kanäle betroffen sind. **Lehre: bei
jeder Zahl aus dem Protokoll ausdrücklich mitschreiben, ob sie Zeilen oder Vorfälle zählt.**

## Messergebnis

### Mengenvergleich (zulässig, aber störanfällig)

| Monat | Zeilen | Alarmtage | Alarme je Alarmtag |
|---|---|---|---|
| Juni | 76 | 12 | 6,3 |
| Juli | 31 | 14 | 2,2 |
| August (bis 17.) | 50 | 16 | 3,1 |

**Kein Trend.** Die Schwankung folgt Wetter- und Tourenlage, nicht der Liefer-Treppe des
Epics — der stärkste Rückgang (Juni→Juli) liegt einen ganzen Monat **vor** der ersten Scheibe.

### Zeitstruktur-Kennzahl (auch im Altformat verfügbar)

Abstand zum vorigen Alarm desselben Empfängers:

| Phase | N | Median (min) | ≤20 min | ≤60 min |
|---|---|---|---|---|
| A bis 08-01 | 106 | 150 | 10,4 % | 27,4 % |
| C 08-04..08-15 | 33 | 179 | 6,1 % | 24,2 % |
| D ab 08-16 | 9 | 75 | 11,1 % | 22,2 % |

*Nenner ist die Zahl der **Paare** (Alarme mit Vorgänger derselben Entität innerhalb der
Phase), nicht die Zeilenzahl; jede Phase wird eigenständig gerechnet. Nur `entries`,
`not_delivered` ausgeschlossen.*

Deutet auf Besserung in Phase C, **trägt aber keinen Nachweis**: Phase D hat n = 9.

**Nachtrag 2026-08-18 — die ≤60-Minuten-Spalte ist als Kennzahl K1' brauchbar.** Sie braucht
den fehlenden Wert **nicht** und reicht bis Juni zurück: **27,4 % (vor 08-02) → 24,2 %
(08-04..08-15) → 22,2 % (ab 08-16)** — monoton fallend. Schwaches Signal (5 Prozentpunkte
Spanne, n = 9 in Phase D, Störgrößen aus Wetter- und Tourenlage ungefiltert), aber **gerichtet
und nicht bloß Rauschen**: die ≤20-Minuten-Spalte derselben Messung läuft **nicht** monoton
(10,4 % → 6,1 % → 11,1 %).

**Messfalle M7 — `not_delivered` niemals ungefiltert mitzählen.** `quiet_hours` und `cooldown`
schreiben bei **jedem** Poll-Zyklus (15 min) eine Zeile, ohne dass der Nutzer je etwas sieht —
sichtbar am 17.08. zwischen 18:07 und 18:52 mit vier `quiet_hours`-Zeilen in Folge. Dieselbe
Rechnung naiv über **beide** Listen ergibt für 08-04..08-17 **69,4 %** statt 24,2 %/22,2 %:
Das misst die Prüftaktung des Schedulers, nicht das Nutzererlebnis. **Wertlos.**

### Was die Bremsen belegbar tun

Gebuchte Sperrgründe — jede Unterdrückung ist einzeln protokolliert:

| Grund | Phase C (08-04..08-15) | Phase D (ab 08-16) | Herkunft |
|---|---|---|---|
| | Vorfälle *(Zeilen)* | Vorfälle *(Zeilen)* | |
| `quiet_hours` | **48** *(96)* | **4** *(8)* | Bestand |
| `channel_disabled` | **31** *(48)* | **10** *(20)* | Bestand |
| `cooldown` | **8** *(18)* | **6** *(12)* | Bestand |
| `below_channel_threshold` | **7** *(7)* | **0** *(0)* | **#1461** |
| `event_duplicate` | **0** *(0)* | **2** *(4)* | **#1467 S4b-1** |

> **Fußnote zur Einheit (korrigiert 2026-08-18).** Die ursprüngliche Tabelle zählte
> **Protokollzeilen**, nicht Vorfälle — ein Vorfall erzeugt so viele Zeilen, wie Kanäle
> gesperrt wurden (typisch zwei: E-Mail + Telegram). Bei `event_duplicate` wurde daraus
> fälschlich „4×"; richtig sind **2 Vorfälle × 2 gesperrte Kanäle = 4 Zeilen**. Der Fehler war
> **nicht** auf `event_duplicate` beschränkt: er betraf jede Zeile der Tabelle außer
> `below_channel_threshold` (dort ist die Sperre einkanalig, Zeilen = Vorfälle). Die Tabelle
> führt jetzt beide Einheiten, fett die Vorfälle.

Komplett unterdrückte Vorfälle (`not_delivered`, 68 gesamt): 52× `quiet_hours`, 14× `cooldown`,
2× `event_duplicate`. **Vor #1459 waren diese 68 Vorgänge spurlos.**

**Die Entdopplung hat die Wiederholung nicht verhindert (Korrektur 2026-08-18).** Die beiden
`event_duplicate`-Vorfälle liegen am 2026-08-17 um 14:52 und 15:52 UTC, Empfänger `5f534011`,
beide `reason=nowcast`. Sie tragen die Aussage „die Entdopplung wirkt" auch inhaltlich nicht.
Tagesverlauf 17.08. (UTC): 13:52 **zugestellt** (Nowcast, `thunder,max`) → 14:07/14:22 `cooldown` → 14:52
`event_duplicate` → 15:07 **erneut zugestellt** (Nowcast, `thunder,max`) → 15:22/15:37
`cooldown` → 15:52 `event_duplicate`. **Die Wiederholung kam durch.** Den Takt bestimmt der
Cooldown, nicht die Entdopplung.

Dazu: beide Treffer sind **Nowcast gegen Nowcast**. Der Mechanismus ist laut
`alert_log.py:53-56` für den **quellenübergreifenden** Fall gedacht (Nowcast ↔ amtlich); am
17.08. gibt es im Protokoll gar keinen `official_alert`-Eintrag. Das dokumentierte Muster ist
damit **nicht bestätigt** — aber auch nicht widerlegt: zwei Treffer sind zu wenig. **Offener
Punkt.**

**Keine Quelle ist verstummt:** Phase C `forecast_change` 20 / `official_alert` 10 /
`nowcast` 5; Phase D 4 / 3 / 3.

### Der entscheidende Befund

Wiederholungsquote im Neuzustand — Anteil zugestellter Vorfälle, die binnen 24 h dieselbe
fachliche Aussage (`reason` + `metrics` + `hazards`) am selben Empfänger wiederholen:

| Phase | Vorfälle | Wiederholungen | Quote |
|---|---|---|---|
| C 08-04..08-15 | 35 | 24 | 68,6 % |
| D ab 08-16 | 10 | 5 | 50,0 % |
| **C+D ab 08-04** | **45** | **30** | **66,7 %** |

Aufschlüsselung der 30 Wiederholungen: Median-Abstand **328 min (5,5 h)**, keine unter 20 min,
nur 3 unter 60 min, 13 über 6 h. Inhaltlich: **17× `forecast_change` / `thunder,max`**,
8× `official_alert` / `thunderstorm`, Rest einzeln.

**Das ist kein Dauerfeuer** — die Bremsen gegen Bursts greifen. Es sind über den Tag verteilte
Meldungen zu derselben Größe (fast immer Gewitter).

**Ob das echte Wiederholung ist, kann das Protokoll nicht beantworten.** `metrics` hält
`metric_id` + `aggregation` fest (`alert_log.py:226-229`) — also *welche Größe*, aber **nicht
welchen Wert**. Ob 17× Gewitter siebzehn echte Stufenwechsel waren oder siebzehnmal dieselbe
Aussage, ist aus dem Protokoll **nicht auflösbar**.

## Schlussfolgerung

**Die Messlatte ist in ihrer Formulierung nicht *präzise* beantwortbar — und zwar aus einem
einzigen, präzise benennbaren Grund:** das Protokoll führt bis heute nicht den **Wert** der
gemeldeten Größe.

> **Korrektur 2026-08-18.** Die ursprüngliche Formulierung „strukturell nicht beantwortbar"
> war zu stark. Sie gilt für die Wiederholungsfrage in der Form, die die alte Messlatte
> verlangt — dort fehlt der Wert und daran ändert sich nichts. Sie gilt **nicht** für die
> Frage insgesamt: die Kennzahl K1' (≤60-Minuten-Abstand, `not_delivered` ausgeschlossen)
> beantwortet sie grob, ohne Protokoll-Erweiterung und bis Juni zurück. Richtig ist:
> **„nicht ohne Protokoll-Erweiterung *präzise* messbar."** #1459 hat Befund B3 („nicht nachvollziehbar, worüber gemeldet wurde") nur zur Hälfte
geschlossen: die Größe kam dazu, der Wert nicht. Genau der Wert entscheidet aber, ob eine
zweite Meldung Wiederholung oder neue Information ist.

Drei weitere Gründe stützen dasselbe Ergebnis:
1. Vor dem 02.08. fehlt zusätzlich die Größe — eine Rückrechnung auf Juni ist ausgeschlossen.
   Die naive Kontrollprobe liefert dort 85 %, aber das ist ein **Artefakt**: im Altformat
   fallen alle Signaturen auf `(None, (), ())` zusammen, also zählt fast alles als
   Wiederholung. **Diese Zahl darf nicht als Vergleich verwendet werden.**
2. Der akute Schmerz B1 war nur vom 01.08. bis 03.08. live (#1444 S1 → #1460). Die „84
   Nachrichten über sechs Wochen" waren eine Hochrechnung, kein gemessener Bestand — es gibt
   kein „Vorher".
3. Der Vollzustand läuft seit 2026-08-16: 1,5 Tage, 10 zugestellte Alarme.

**Was das Epic dennoch belegbar erreicht hat:** vier eigenständige Bremsen, jede mit gebuchtem
Grund, 68 vormals spurlose Vorgänge jetzt sichtbar, keine verstummte Quelle. Der Nachweis
gelingt über die gebuchten Sperrgründe — nicht über einen Mengenvergleich.

## Technical Approach (Empfehlung)

Die Messlatte **ersetzen**, nicht erzwingen:

- **Kennzahl 1' (weniger Wiederholung, sofort messbar):** Anteil zugestellter Alarme mit
  ≤60 min Abstand zum vorigen zugestellten Alarm derselben Entität, `not_delivered`
  **ausgeschlossen**. Basislinie **27,4 % vor dem Epic → 22,2 % danach**. Keine Abhängigkeit
  von der Protokoll-Erweiterung. Ergänzt K1, ersetzt sie nicht — sie überbrückt die Zeit bis
  #1954. *(ergänzt 2026-08-18)*
- **Kennzahl 1 (weniger Wiederholung, präzise):** Wiederholungsquote wie oben, mit dem Wert in
  der Signatur. Basislinie **66,7 %** ab 08-04 festhalten. Voraussetzung: das Protokoll muss
  den Wert mitschreiben — kleine additive Erweiterung von `alert_log.py`, kein Schemabruch.
- **Kennzahl 2 (nicht weniger echte Warnung):** je Auslöser mindestens ein zugestellter Alarm
  je Kalenderwoche mit Alarmlage. Heute schon erfüllt und ohne Änderung messbar.

Umfang, wenn nur dokumentiert und gebucht wird: **0 LoC Produktivcode**, Doku + Issue-Kommentar.
Umfang mit der Protokoll-Erweiterung: ~20–40 LoC in `alert_log.py` plus Aufrufer — das wäre
aber eine **eigene Scheibe**, nicht Teil dieses Nachweises.

## Scope Assessment

- Files: 1 (dieses Dokument) + Issue-Kommentar
- Estimated LoC: +0 Produktivcode
- Risk Level: **LOW**

## PO-Entscheidungen 2026-08-17

| Frage | Entscheid |
|---|---|
| **F1** Messlatte | **Ersetzen + Epic schließen.** Zwei prospektiv messbare Kennzahlen, Basislinie 66,7 % festhalten, Befund als Kommentar ans Epic. |
| **F2** Wert ins Protokoll | **Ja — eigenes Issue anlegen.** Additive Erweiterung, ~20–40 LoC. Nicht Teil dieses Nachweises. |
| **F3** Ruhezeit vs. akute Gefahr | **Eigenes Issue, `priority:high`.** Vor dem KHW-Abmarsch. |

## Open Questions (beantwortet, Historie)

- [x] **F1 — Ersatz-Messlatte annehmen?** Die Erledigt-Liste des Epics enthält ein Kriterium,
      das strukturell nicht erfüllbar ist. Ersetzen und Epic schließen, oder Epic offen halten,
      bis das Protokoll den Wert führt?
- [ ] **F2 — Wert ins Protokoll?** Eigene Scheibe, klein und additiv. Ohne sie bleibt die
      Wiederholungsfrage dauerhaft unbeantwortbar.
- [ ] **F3 — Nebenbefund Ruhezeit vs. akute Gefahr.** `check_nowcast_gate`
      (`src/services/alert_gate.py:143`) prüft die Ruhezeit zuerst und **ohne Gewitter-
      Ausnahme**; beide Nowcast-Pfade laufen dadurch (`trip_alert.py:1120`,
      `compare_radar_alert.py:145`). Gemessen: 52 Vorfälle komplett unterdrückt, 48 davon
      nachts 02–06 Uhr Ortszeit. #1310 hat den Akut-Override nur für die **Briefing**-Sperre
      gebaut. PO-Vorgabe 4 lautet „akute Gefahr muss durchkommen". **Nicht verifiziert**, ob
      unter den 52 konvektive Lagen waren — unterdrückte Einträge tragen `metrics: []`
      (Lücke O3). Eigenes Issue?

## Existing Specs

- `docs/specs/modules/feat_1459_alert_protokoll.md` — Protokoll-Schema, Lücke O3
- `docs/specs/modules/rework_1467_s1_alarm_kennung.md` — `entity_id`/`entity_type`
- `docs/specs/modules/feat_1461_s3a_alarm_dringlichkeit.md` — Dringlichkeits-Ableitung
- `docs/specs/modules/trip_alert.md` — Status „Approved", beschreibt laut #1464 einen
  überholten Stand
