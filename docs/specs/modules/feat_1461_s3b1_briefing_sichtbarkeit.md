---
entity_id: feat_1461_s3b1_briefing_sichtbarkeit
type: module
created: 2026-08-05
updated: 2026-08-05
status: draft
version: "1.2"
tags: [alerts, briefing, email, epic-1458, issue-1461]
---

# Briefing zeigt, welche Alarme nicht angekommen sind (#1461 S3b-1)

> **Teilweise überholt durch #1750/#1800 (2026-08-15):** Die Sammelüberschrift
> „NICHT BEI DIR ANGEKOMMEN" entfällt ersatzlos, ersetzt durch zwei eigenständige Blöcke
> „FEHLGESCHLAGEN — da ist etwas schiefgegangen" (Fehler) und „ZURÜCKGEHALTEN — so hast du es
> eingestellt" (Absicht). Die Deckelung aus AC-6 (5 Zeilen) gilt seither **je Block**, nicht mehr
> über die Gesamtliste — siehe die Notiz direkt bei AC-6. Details, Wortlaute und Begründung:
> `docs/specs/modules/fix_1750_zustell_hinweis_klartext.md`. Die übrige Beschreibung dieser Spec
> (Lesefunktion, Zeitanker, Renderer-Einbindung, Entdoppelung, AC-1 bis AC-5, AC-7 bis AC-17)
> bleibt unverändert gültig.

## Approval

- [x] Approved — PO, 2026-08-05 („go"). Deckelung bei 5 Zeilen ohne Widerspruch übernommen.
  Beleg: Kommentar an Issue #1461.

## Purpose

Das Briefing weist am Ende aus, welche Alarm-Meldungen seit dem letzten Briefing einen Kanal
**nicht** erreicht haben. Damit ist Pflicht 2 aus #1461 erfüllt („was ein Kanal nicht bekommen
hat, wird protokolliert **und im nächsten Briefing sichtbar**") — die Voraussetzung dafür, dass
die Kanal-Schwelle aus S3b-2 keine Meldung spurlos verschwinden lassen kann (rote Linie #638).

Heute ist das unmöglich: das Alarm-Protokoll aus #1459 hat sechs Schreibstellen und **null
Leser** auf der Python-Seite.

## Source

- **Datei (neu):** `src/output/renderers/email/undelivered_hint.py`
- **Dateien (geändert):** `src/services/alert_log.py` ·
  `src/services/alert_briefing_anchor.py` · `src/services/notification_service.py` ·
  `src/services/scheduler_dispatch_service.py` · `src/output/renderers/trip_report.py` ·
  `src/output/renderers/email/{__init__,html,plain,compact,compare_html}.py` ·
  `src/output/renderers/comparison.py` (Klartext des Ortsvergleichs, v1.2)
- **Schicht:** Python-Core (`src/services/`, `src/output/`). **Keine** Go-Änderung, **keine**
  Frontend-Änderung.

## Estimated Scope

- **LoC:** ~280–320 inkl. Tests
- **Files:** 11 geändert, 2 neu
- **Effort:** medium

**Korrektur v1.1 (gemessen):** Die Schätzung war deutlich zu niedrig. Allein die Testdatei
`tests/tdd/test_alert_undelivered_hint.py` hat **1367 Zeilen** (23 Tests mit echten
Protokolldateien, keine Attrappen). Produktivcode weiterhin ~300 Zeilen.

**PO-Entscheid 2026-08-05:** Grenze für diesen Arbeitsgang auf **2000** angehoben
(`loc_limit_override 2000`), Begründung: ~1400 der Zeilen sind Tests — also genau das, was die
Änderung überprüfbar macht. Die Alternativen (Tests ausdünnen, nochmals teilen) wurden vorgelegt
und verworfen.

## Dependencies

| Entity | Typ | Zweck |
|---|---|---|
| `feat_1459_alert_protokoll` | liest | Schema `entries` / `not_delivered`, Zusicherungen D1/D4 |
| `rework_1467_s1_alarm_kennung` | liest | `entity_id` + `entity_type` als einzige Kennung |
| `rework_1467_s2_aenderungsalarm` (AG5) | erweitert | `alert_briefing_anchor` = die Naht „ein Briefing ist raus" |
| `feat_1461_s3a_alarm_dringlichkeit` | liest | `severity` je Eintrag |
| `output_channel_renderers` §A1/§A5/§A6 | befolgt | Renderer bleibt rein, Daten kommen als kwarg |
| `app.metric_catalog` | nutzt | Wettergrößen in Klartext |
| `output.metric_format.thunder_ordinal()` | nutzt | ordinale Größen nie roh (#1503/#1474) |

## Implementation Details

### PO-Entscheidungen 2026-08-05

| Frage | Entscheidung |
|---|---|
| Detailtiefe | je Meldung eine Zeile: Zeitpunkt · worum es ging · welcher Kanal · warum |
| Umfang | **beide** Fälle — Totalausfall **und** Teilausfall („E-Mail kam an, SMS nicht") |
| Kanäle | **nur E-Mail.** Telegram-Kurzform und SMS bleiben unberührt |
| Deckelung | **5 Zeilen**, darunter „und N weitere" — *zur Freigabe vorgelegt* |

> **Fortgeschrieben durch #1750 (2026-08-15):** Die Zeile „5 Zeilen" bezog sich hier auf die
> Gesamtliste unter einer Sammelüberschrift. Seit
> `docs/specs/modules/fix_1750_zustell_hinweis_klartext.md` gilt derselbe Zahlenwert
> (`MAX_LINES_PER_BLOCK`) **je Block** getrennt (Fehlgeschlagen/Zurückgehalten) — s. Notiz bei AC-6.

Abgeleitet (Routine, keine Rückfrage): „E-Mail" heißt **beide** Mail-Formate (`full` und
`compact`); Trip und Ortsvergleich bekommen **denselben** Baustein (Teilungs-Gate).

### Drei Bausteine

**1. Lesen** — neue reine Lesefunktion neben `append_entry()` in `alert_log.py`. Liefert für
eine Kennung (`entity_id` + `entity_type`) ab einem Zeitpunkt die Meldungen, die mindestens
einen Kanal nicht erreicht haben. Beide Quellen:

* `entries[*].channels_not_sent` — Teilausfall
* `not_delivered[*]` — Totalausfall (dort ist per Definition jeder Kanal betroffen)

🔴 **Ein vom Nutzer abgeschalteter Kanal ist KEIN Vorfall** (v1.1, gemessen in der RED-Phase).
`alert_log._channels_not_sent()` schreibt für **jeden** Kanal, der nicht in `effective_channels`
steht, einen Eintrag mit Grund `channel_disabled` — bei **jedem erfolgreichen** Alarm. Ein
Nutzer mit nur E-Mail hätte damit in jedem Eintrag zwei solche Einträge, und der Abschnitt
stünde in **jedem** Briefing. Der Grund `channel_disabled` wird deshalb übersprungen; AC-3
spricht ausdrücklich von „jedem **eingeschalteten** Kanal".

Die Abgrenzung ist **`channel_disabled`**, nicht „nur `delivery_failed`": der in S3b-2
hinzukommende Grund „unter der Kanal-Schwelle" ist ein gewolltes Stummschalten und MUSS
erscheinen (Pflicht 1 des Issues) — ebenso `quiet_hours`, `daily_limit`, `cooldown`, sobald
sie geschrieben werden.

Fail-soft wie die Schreibseite: unlesbare Datei ⇒ leeres Ergebnis + Warnung, nie eine Ausnahme
ins Briefing.

**Entdoppelung beim LESEN, nicht im Protokoll.** Ein Lauf kann für **eine** Nutzer-Meldung bis
zu drei Einträge erzeugen (Vorhersage-Änderung, Radar, amtliche Warnung sind drei getrennte
`append_entry`-Aufrufe). Für den Nutzer ist das ein Vorfall. Zusammengefasst wird über
Kennung + Zeitfenster; die betroffenen Kanäle und Gründe werden vereinigt. Am Protokoll selbst
wird **nichts** geändert — dadurch bleibt D4 zwingend gewahrt.

**2. Zeitraum** — `alert_briefing_anchor.write_anchor_and_reset_memory()` ist bereits die
Definition von „ein Briefing ist rausgegangen" und wird in **beiden** Pfaden **nach** dem
Versand gerufen (`trip_report_scheduler.py:983`, `scheduler_dispatch_service.py:413`). Dort
zusätzlich einen Zeitstempel je Kennung fortschreiben. Das Briefing liest den alten Wert,
bevor er überschrieben wird — die Reihenfolge stimmt von selbst.

🔴 **Kennungs-Fallstrick, gemessen:** Der Anker-Baustein bekommt im Compare-Fall
`entity_ids = [f"{preset_id}:{loc.id}", …]` (je Ort); das **Protokoll** schreibt dagegen
`entity_id = preset_id` (`compare_alert.py:193`, `compare_official_alert.py:151`). Der
Briefing-Zeitstempel MUSS unter der **Protokoll-Kennung** abgelegt werden — sonst findet die
Lesefunktion nie einen Treffer und der Hinweis bleibt beim Ortsvergleich dauerhaft leer.

Fehlt der Zeitstempel (erstes Briefing nach Auslieferung, Bestandsnutzer): Rückblick beginnt
**ab jetzt**, nicht über die unbestimmte Vergangenheit.

**3. Anzeigen** — `src/output/renderers/email/undelivered_hint.py`, Bauform 1:1 nach
`unavailable_hint.py` (#1348) und `outlook_state_hint.py` (#1349): eine Prüffunktion, eine
HTML-Fassung, eine Klartext-Fassung; eingebunden in `html.py`, `plain.py`, `compact.py`,
`compare_html.py`. Bewusst **nicht** unter `renderers/alert/` — es ist ein Briefing-Baustein,
kein Alarm-Renderer (Begründung wörtlich im Kopf von `unavailable_hint.py`); so bleibt das
Warn-Renderer-Gate unberührt. Kein `trip_`/`compare_`-Präfix ⇒ Pendant-Sperre (#1481 B)
greift nicht.

Hochkontrastig nach Design-Leitprinzip (`G_BOX_DANGER_BG`/`G_DANGER`, **kein** `G_INK_FAINT`).

**Durchreichung:** `render_email()` sichert bit-identische Ausgabe bei gleicher Eingabe zu und
darf nichts nachladen. Die Daten wandern als expliziter kwarg durch `notification_service` →
`TripReportFormatter.format_email()` → `render_email()`. Ohne kwarg (Vorschau, Golden-Tests,
CLI) verhält sich alles wie bisher.

### Beispiel-Ausgabe (Klartext)

```
NICHT BEI DIR ANGEKOMMEN

  04.08. 18:42 · Gewitter · SMS nicht zugestellt
  04.08. 06:15 · Wind · SMS nicht zugestellt
  05.08. 05:30 · Amtliche Warnung · SMS, Telegram nicht zugestellt
  … und 2 weitere
```

> **Überholt durch #1750 (2026-08-15):** Dieses Beispiel zeigt noch die Sammelüberschrift
> „NICHT BEI DIR ANGEKOMMEN" und die Formulierung „SMS nicht zugestellt". Seit
> `docs/specs/modules/fix_1750_zustell_hinweis_klartext.md` gibt es diese Überschrift nicht mehr
> — stattdessen „FEHLGESCHLAGEN — da ist etwas schiefgegangen" bzw. „ZURÜCKGEHALTEN — so hast du
> es eingestellt", ohne die Formulierung „nicht zugestellt". Die hier gezeigte Zeitform
> `TT.MM. HH:MM` bleibt unverändert gültig.

Zeitform `TT.MM. HH:MM` statt „Gestern/Heute" (v1.2, Begründung aus der GREEN-Phase): „Gestern"
hinge vom Erzeugungszeitpunkt ab und bräche damit die Reinheit des Renderers — gleiche Eingabe
müsste sonst nicht mehr die gleiche Ausgabe liefern. Zusätzlich verlangt AC-15, dass außer dem
Zeitstempel keine Ziffer in der Zeile steht; ein Wortpräfix macht diese Prüfung mehrdeutig.

## Expected Behavior

- **Input:** Alarm-Protokoll des Nutzers (`data/users/<user_id>/alert_log.json`), die Kennung
  des Trips bzw. Presets, der Zeitpunkt des letzten Briefings, die Zeitzone des Briefings.
- **Output:** Ein Abschnitt in HTML- und Klartext-E-Mail (Trip `full`, Trip `compact`,
  Ortsvergleich) — **oder gar nichts**, wenn nichts fehlt.
- **Side effects:** Ein Zeitstempel je Kennung wird nach dem Versand fortgeschrieben. Am
  Alarm-Protokoll (`entries`, `not_delivered`) wird nichts geändert. Am Versandverhalten wird
  nichts geändert.

## Acceptance Criteria

- **AC-1:** Given ein Alarm wurde per E-Mail zugestellt, erreichte aber die SMS nicht /
  When das nächste Briefing des Trips erzeugt wird / Then enthält die Briefing-Mail eine
  Zeile, die den Zeitpunkt in der Zeitzone des Briefings, die betroffene Wettergröße, den
  Kanal „SMS" und den Grund nennt.
  - Test: Protokoll mit einem Eintrag `channels_not_sent=[{sms, delivery_failed}]` anlegen,
    Briefing rendern, alle vier Angaben im erzeugten Text nachweisen.

- **AC-2:** Given eine Alarm-Meldung erreichte **keinen einzigen** Kanal /
  When das nächste Briefing erzeugt wird / Then erscheint sie ebenfalls als Zeile, mit allen
  betroffenen Kanälen.
  - Test: Eintrag unter `not_delivered` anlegen; alle drei Kanalnamen erscheinen in der Zeile.

- **AC-3:** Given seit dem letzten Briefing wurde jede Meldung auf jedem **eingeschalteten**
  Kanal zugestellt / When das Briefing erzeugt wird / Then enthält es **keinerlei**
  Hinweis-Abschnitt — auch keine Überschrift und keine Null-Zeile. Das gilt insbesondere für
  Kanäle, die der Nutzer selbst **abgeschaltet** hat: sie sind kein Vorfall.
  - Test: (a) Protokoll nur mit vollständig zugestellten Einträgen; (b) Ein-Kanal-Nutzer, dessen
    Einträge Telegram und SMS mit Grund `channel_disabled` führen. In beiden Fällen kommt die
    Überschrift im erzeugten Text nicht vor.

- **AC-4:** Given eine nicht zugestellte Meldung wurde in einem früheren Briefing bereits
  ausgewiesen / When das darauffolgende Briefing erzeugt wird / Then erscheint sie **nicht
  erneut**.
  - Test: Zwei Briefings nacheinander erzeugen; die Zeile steht im ersten, nicht im zweiten.

- **AC-5:** Given ein einziger Alarm-Lauf hat wegen gleichzeitiger Vorhersage-Änderung und
  amtlicher Warnung mehrere Protokolleinträge erzeugt, die alle niemanden erreichten /
  When das Briefing erzeugt wird / Then steht dafür **eine** Zeile, nicht mehrere, und die
  betroffenen Kanäle sind darin zusammengefasst.
  - Test: Zwei Einträge derselben Kennung mit demselben Zeitstempel und verschiedenem Grund;
    genau eine Zeile im Ergebnis.

- **AC-6:** Given mehr als fünf Meldungen haben seit dem letzten Briefing einen Kanal nicht
  erreicht / When das Briefing erzeugt wird / Then stehen die fünf jüngsten als Zeilen da,
  gefolgt von einem Hinweis, wie viele weitere es sind.
  - Test: Acht Vorfälle anlegen; fünf Zeilen plus „und 3 weitere" nachweisen.
  - ⚠️ **Abgelöst durch #1750 (2026-08-15)** (`docs/specs/modules/fix_1750_zustell_hinweis_klartext.md`
    AC-12, E6): Die Deckelung gilt nicht mehr über die Gesamtliste, sondern **je Block** getrennt
    (`MAX_LINES_PER_BLOCK`) — ein zurückgehaltener Vorfall wird von der Deckelung des
    Fehlgeschlagen-Blocks nicht mehr verdrängt und umgekehrt. Der hier beschriebene Test (acht
    Vorfälle in einer gemeinsamen Liste) ist als Konstruktion überholt; der Nachweis erfolgt jetzt
    block-getrennt. Ursprünglicher AC-Wortlaut bleibt zur Historie unverändert stehen.

- **AC-7:** Given ein Nutzer bekommt zum ersten Mal ein Briefing, nachdem diese Funktion
  ausgeliefert wurde, und sein Protokoll enthält alte nicht zugestellte Meldungen /
  When das Briefing erzeugt wird / Then wird **keine** dieser Alt-Meldungen ausgewiesen.
  - Test: Protokoll mit Einträgen von vor Tagen, kein gespeicherter Briefing-Zeitpunkt;
    Abschnitt erscheint nicht.

- **AC-8:** Given ein Nutzer ruft ein Briefing selbst ab (kein geplanter Versand) /
  When er danach das nächste geplante Briefing bekommt / Then sind die nicht zugestellten
  Meldungen dort **immer noch** ausgewiesen — der Selbstabruf hat den Zeitraum nicht
  abgeschnitten.
  - Test: Abruf mit `on_demand=True`, danach reguläres Briefing; Zeile ist in beiden enthalten.

- **AC-9:** Given es liegen nicht zugestellte Meldungen vor / When ein Briefing im Format
  `full` **und** eines im Format `compact` erzeugt wird / Then enthalten **beide** den
  Abschnitt.
  - Test: Beide Formate rendern, in beiden nachweisen.

- **AC-10:** Given es liegen nicht zugestellte Meldungen vor / When die Kurznachrichten für
  Telegram und SMS erzeugt werden / Then sind diese Zeichen für Zeichen identisch mit denen
  ohne solche Meldungen.
  - Test: Kurznachricht mit und ohne Vorfälle im Protokoll erzeugen und auf Gleichheit prüfen.

- **AC-11:** Given ein Ortsvergleich hat eine Meldung, die einen Kanal nicht erreicht hat /
  When das Ortsvergleichs-Briefing erzeugt wird / Then erscheint der Abschnitt dort mit
  derselben Zeilenform wie beim Trip — und ist **nicht leer**.
  - Test: Compare-Protokolleintrag unter der Preset-Kennung anlegen, Compare-Mail rendern,
    Zeile nachweisen. Deckt den Kennungs-Fallstrick ab.

- **AC-17:** Given dieselbe Lage wie in AC-11 / When die Ortsvergleichs-Mail erzeugt wird /
  Then enthält **auch ihr Klartext-Teil** den Abschnitt — nicht nur die HTML-Fassung.
  - Test: `render_comparison_text()` mit demselben Protokollstand; Überschrift und Zeile im
    Klartext nachweisen.
  - Begründung (v1.2): Eine Mail hat zwei Fassungen, beide werden zugestellt
    (`scheduler_dispatch_service.py:394` reicht `text_body` mit). Die PO-Entscheidung „nur
    E-Mail" meint die Mail, nicht ihre HTML-Hälfte. Der Pflicht-Validator
    `email_spec_validator.py` liest **ausschließlich** HTML und kann einen Fehler im
    Klartext strukturell nicht fangen — in #1366 blieb dort ein Schalter deshalb dauerhaft
    wirkungslos, bei grünen Tests und grünem Validator. Beim Trip ist die Klartext-Fassung
    (`email/plain.py`) von Anfang an dabei; ohne AC-17 wäre der Ortsvergleich schlechter
    gestellt, was zusätzlich die Teilungs-Invariante verletzt.

- **AC-12:** Given zwei verschiedene Nutzer haben je eigene nicht zugestellte Meldungen /
  When das Briefing des einen erzeugt wird / Then enthält es ausschließlich dessen eigene
  Meldungen.
  - Test: Zwei Nutzerverzeichnisse mit unterscheidbaren Einträgen; Kreuzprüfung in beide
    Richtungen.

- **AC-13:** Given ein Protokoll enthält nicht zugestellte Meldungen / When Cockpit-Kachel und
  Archiv-Statistik abgefragt werden / Then zeigen sie **dieselben Zahlen** wie vor dieser
  Änderung.
  - Test: Zählung vor und nach dem Erzeugen eines Briefings vergleichen (Zusicherung D4).

- **AC-14:** Given die Protokolldatei fehlt oder ist beschädigt / When ein Briefing erzeugt
  wird / Then geht das Briefing vollständig und ohne Fehler raus, nur ohne den Abschnitt.
  - Test: Datei mit unlesbarem Inhalt anlegen; Briefing enthält alle übrigen Abschnitte.

- **AC-15:** Given eine nicht zugestellte Meldung betraf das Gewitter-Niveau /
  When die Zeile erzeugt wird / Then nennt sie die Wettergröße in Worten aus dem Register
  („Gewitter") und enthält außer dem Zeitstempel **keine Ziffer**.
  - Test: Eintrag mit dem Register-Paar der ordinalen Größe; die Bezeichnung steht in der Zeile,
    eine nackte Zahl kommt nicht vor.
  - Präzisierung v1.1 (gemessen in der RED-Phase): Das Protokoll speichert **keinen**
    Gewitter-Wert, nur das Register-Paar, `severity` und `changes_count`. Es gibt daher gar
    keine Stufenzahl zu wandeln; `thunder_ordinal()` hat hier nichts zu tun. Eine Stufenangabe
    in der Zeile setzte voraus, dass die **Schreibseite** den Wert mitschreibt — Schema-Änderung,
    nicht diese Scheibe.

- **AC-16:** Given beliebige Alarm-Lagen / When ein kompletter Alarm- und Briefing-Lauf
  durchläuft / Then wird **kein** Alarm anders verschickt als vor dieser Änderung — gleiche
  Kanäle, gleiche Anzahl.
  - Test: Versandzähler je Kanal vor und nach dem Patch vergleichen.

## Known Limitations

- Die Gründe `quiet_hours`, `daily_limit` und `cooldown` sind im Schema vorgesehen, werden aber
  von **keinem** Aufrufer gesetzt (O3 aus #1459: zum Gate-Zeitpunkt ist der Auslöser noch nicht
  bekannt). Sie können daher heute in keiner Zeile erscheinen. Wer sie sichtbar machen will,
  muss zuerst die Schreibseite nachziehen — nicht Teil dieser Scheibe.
- Die Kurznachricht (Telegram/SMS) weist nichts aus. Wer ausschließlich per SMS liest, erfährt
  von fehlgeschlagenen Zustellungen nichts. PO-Entscheidung 2026-08-05.
- Die Entdoppelung fasst über Kennung und Zeitfenster zusammen. Zwei **echt verschiedene**
  Meldungen derselben Kennung innerhalb desselben Fensters würden ebenfalls zu einer Zeile
  zusammengezogen. Praktisch ausgeschlossen, weil ein Alarm-Lauf pro Kennung höchstens einmal
  je Auslöser protokolliert; für den Nutzer wäre es ohnehin ein Vorfall.
- Der Rückblick reicht nur bis zum letzten Briefing. Wer sein Briefing abschaltet, sieht
  nichts — dann gibt es aber auch kein Briefing, in dem es stehen könnte.
- **Keine Stufen-/Messwerte in der Zeile.** Das Protokoll hält nur fest, *worum* es ging
  (Register-Paar bzw. Gefahrenart), nicht *wie stark*. Die Zeile nennt deshalb „Gewitter", nicht
  „Gewitter hoch". Nachrüstbar nur über die Schreibseite.
- **Ortsvergleich ohne Briefing-Zeitzone.** `render_compare_html()` nimmt kein `tz` — die
  Vergleichs-Mail rechnet je Ort in Ortszeit. Die Zeitzonen-Zusicherung aus AC-1 gilt daher für
  den Trip; beim Ortsvergleich sichert AC-11 nur zu, dass Anlass und Kanal da und die Zeile
  **nicht leer** ist.
- **AC-16 ist nicht als Vorher/Nachher-Vergleich testbar** — ein Testlauf kennt nur einen Stand.
  Nachgewiesen wird stattdessen im selben Lauf: derselbe Alarm für einen Nutzer mit vorbelastetem
  und einen mit leerem Protokoll muss Kanäle, Anzahl, Betreff und Mail-Inhalt gleich lassen,
  **während** nachweislich ein Abschnitt erscheint (sonst bewacht der Test nichts). Dasselbe
  Muster in AC-10, AC-13 und AC-14.
- **AC-13 ist Python-seitig eine Struktur-Zusicherung:** `entries` und `not_delivered` müssen nach
  dem Briefing Feld für Feld unverändert sein. Genau das macht die Go-Zahlen unveränderlich;
  der Go-Store selbst ist aus pytest nicht erreichbar.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Keine Entscheidungsfläche wird verschoben. Kanäle, Provider, Datenmodell,
  Auth und Test-/Deploy-Strategie bleiben unverändert; das Protokoll-Schema wird nur gelesen.
  Der zusätzliche Briefing-Zeitstempel ist additiv und bleibt für Go unsichtbar — dieselbe
  Bauart wie `not_delivered` aus #1459 (dort ebenfalls ohne ADR).

## Changelog

- 2026-08-15: **AC-6 abgelöst durch #1750/#1800**
  (`docs/specs/modules/fix_1750_zustell_hinweis_klartext.md`) — Sammelüberschrift
  „NICHT BEI DIR ANGEKOMMEN" entfällt ersatzlos zugunsten zweier Blöcke „FEHLGESCHLAGEN"/
  „ZURÜCKGEHALTEN"; die 5-Zeilen-Deckelung gilt seither je Block statt über die Gesamtliste.
  Historischer AC-Wortlaut und das alte Klartext-Beispiel bleiben zur Nachvollziehbarkeit
  unverändert stehen, mit Fortschreibungs-Notizen versehen.
- 2026-08-05 (v1.2): AC-17 ergänzt — der **Klartext-Teil** der Ortsvergleichs-Mail bekommt den
  Abschnitt ebenfalls. In der GREEN-Phase war er ausgelassen worden, weil die Dateiliste
  `comparison.py` nicht nannte und AC-11 nur HTML prüft. Beide Fassungen werden zugestellt; der
  Pflicht-Validator liest nur HTML (blinder Fleck, belegt in #1366).
- 2026-08-05 (v1.1): Drei Präzisierungen aus der RED-Phase, alle gemessen — (1) ein vom Nutzer
  abgeschalteter Kanal (`channel_disabled`) ist kein Vorfall, sonst stünde der Abschnitt bei
  jedem Ein-Kanal-Nutzer in jedem Briefing und AC-3 wäre strukturell unerfüllbar; (2) AC-15
  kann keine Stufenzahl unterdrücken, weil das Protokoll keine speichert; (3) Grenzen von
  AC-10/13/14/16 als Nicht-Leerlauf-Nachweis im selben Lauf statt Vorher/Nachher.
- 2026-08-05: Initial spec (v1.0) — auf Basis von `docs/context/feat-1461-s3b1-briefing-sichtbarkeit.md`
