# Context: fix-2220-telegram-kommando-befunde

Issue: [#2220](https://github.com/henemm/gregor_zwanzig/issues/2220) · Label `bug`, `priority:medium`
Track: Standard (Intake-Summe 3) · abgespalten aus #1199 (Volltriage 2026-09-08)

## Request Summary

Drei Befunde aus der #1199-Volltriage, alle im Pfad der **Telegram-/Premium-SMS-Kommandos**:
falsche Ampelfarben im Telegram-Drilldown (C5-63), inhaltsleere `?–?`-Zeilen in der
Timeline statt einer ehrlichen Datenlücken-Meldung (C5-38), und eine Kanal-Auflösung, die
einen unbekannten Kanalnamen nicht als solchen erkennt (C5-58).

Die Intake-Recherche hat **zwei der drei Kurzbeschreibungen aus dem Issue-Text korrigiert** —
siehe die Abschnitte unten. Die Spec muss die korrigierte Fassung beschreiben, nicht die
Issue-Überschrift.

---

## Befund C5-63 — Ampelfarben im Telegram-Kommando

### Ist-Stand

`src/services/trip_command_processor.py:209`

```python
_BAND_EMOJI = {"green": "⚪", "yellow": "🟢", "orange": "🟡", "red": "🔴"}
```

Die Bandnamen kommen aus der kanonischen Quelle `thunder_ampel_band()`
(`src/output/metric_format.py:307-326`): `NONE→green, LOW→yellow, MED→orange, HIGH→red`.

Drei von vier Einträgen widersprechen ihrem eigenen Schlüssel; `🟠` kommt im Gewitterpfad
nirgends vor. Es ist die **einzige** Stelle im Repo, die einen Bandnamen auf ein Symbol
anderer Farbe abbildet.

### Wo das sichtbar wird

Nur über `_thunder_symbols()` (`:219-224`) → `_thunder_fmt()` (`:301`), und nur bei
`with_emoji = channel == "telegram"` (`:1027`, `:1141`, `:1167`):

| Ausgabe | Emoji? |
|---|---|
| Drilldown Gewitter (`dd_thunder_today|tomorrow`) | ✅ |
| Drilldown Stunden (`dd_hours_today|tomorrow`), Gewitterspalte `:1178-1190` | ✅ |
| Timeline (`_fmt_timeline:1666`) | ❌ — nur das Wort |
| E-Mail / SMS / Premium-SMS | ❌ — nur das Wort (#1222 AC-6) |

**Korrektur zur Issue-Kurzbeschreibung:** Der Titel nennt „Telegram-/Premium-SMS-Kommandos".
Premium-SMS ist von C5-63 **nicht** betroffen (`with_emoji` ist dort False).

### Die eigentliche Divergenz — Kanal gegen Kanal

`docs/reference/renderer_email_spec.md:256` ist Single Source of Truth für die E-Mail:

> Severity-Ampel 🟢🟡🟠🔴 | thunder | Ampelpunkt (**NONE=grün, LOW=gelb, MED=orange, HIGH=rot**);
> keine Aussage (`None`) = „–"

Damit steht dieselbe Gewitterstufe in zwei Kanälen in zwei Farben:

| Stufe | E-Mail | Telegram heute |
|---|---|---|
| NONE („kein") | 🟢 grün | ⚪ weiß |
| LOW („leicht") | 🟡 gelb | 🟢 **grün** |
| MED („mittel") | 🟠 orange | 🟡 **gelb** |
| HIGH („hoch") | 🔴 rot | 🔴 rot |

Die Abweichung geht in die **beruhigende** Richtung: „leicht" liest sich in Telegram als
Entwarnung, „mittel" als eine Stufe harmloser.

### Was das zu einer PO-Entscheidung macht

- `docs/specs/modules/feat_2176_luftmasse_statt_gewitteransage.md:327-332` hat die Farbe für
  LOW **ausdrücklich offengelassen**: „beim Implementieren offenlassen bzw. unverändert
  lassen, sofern keine gesonderte PO-Antwort vorliegt."
- `fix_1491_gewitter_ampelkreis.md:252-255`: der grüne Kreis für NONE in der
  Trip-Stundentabelle ist eine **PO-Entscheidung**; der Ortsvergleich lässt dieselbe Stufe
  bewusst unmarkiert.
- `fix_2010_2011_gewitter_stufenwoerter.md:131` hat die Reihenfolge ⚪/🟢/🟡/🔴 in ein
  Akzeptanzkriterium geschrieben — als übernommenen Bestand, nicht als Entscheidung.
- Herkunft (git `2f1390ac`, #2010/#2011): das frühere `_MAP_EMOJI` war auf **Stufennamen**
  geschlüsselt (`LOW: "🟢 leicht"`). Beim Umschlüsseln auf **Bandnamen** blieb die
  Emoji-Reihenfolge stehen — der Widerspruch wurde dadurch erst sichtbar, verschoben wurde
  nichts.

Zwei in sich stimmige Zielbilder stehen zur Wahl (Entscheidung gehört in die Spec-Freigabe):

- **A — volle Kanalparität:** NONE 🟢, LOW 🟡, MED 🟠, HIGH 🔴. Identisch zur E-Mail.
- **B — ⚪ für NONE behalten:** NONE ⚪, LOW 🟡, MED 🟠, HIGH 🔴. Korrigiert die Verschiebung,
  behält aber die Unterscheidung „weiß = keine Neigung" gegen den amtlichen 🟢 = Warnstufe 1
  (`src/output/renderers/alert/official_alerts.py:44`) — in Telegram stehen beide Skalen
  potenziell nebeneinander.

**🔴 Aufgabe für `/20-analyse` — die Wahl auflösen, NICHT als Menü vorlegen.**
Beide Optionen reparieren LOW/MED identisch; sie unterscheiden sich **nur bei NONE**. Das
einzige Argument für B ist die Verwechslungsgefahr mit der amtlichen Warnstufe 1 (🟢). Zu
prüfen ist deshalb genau eine Frage: **Können die amtlichen Warnstufen-Emojis aus
`official_alerts.py:44` und die Gewitter-Emojis jemals in derselben Telegram-Nachricht
auftreten?** Wenn nein, fällt Bs Begründung weg und A ist die schlichte Antwort (Parität zur
Mail-SSoT; NONE=grün hat der PO in `fix_1491` AC-2 bereits entschieden). Dem PO geht **eine
begründete Empfehlung** zu, die Alternative nur benannt — keine Farbwahl-Frage.

### Testlage (die den Ist-Stand festnagelt)

| Datei:Zeile | Was festgehalten ist |
|---|---|
| `tests/tdd/test_thunder_stage_words_from_canonical_source.py:75-96` | parametrisiert `(NONE,"kein","⚪")`, `(LOW,"leicht","🟢")`, `(MED,"mittel","🟡")`, `(HIGH,"hoch","🔴")` — **zementiert den Ist-Stand** |
| dto. `:213-215` | Stundendrilldown: mindestens eine Zeile endet auf `🟡` („MED") |
| dto. `:221-232` | NONE-Stunde zeigt `—`, nicht `⚪` |
| dto. `:328-340` | Ableitungsnachweis via `monkeypatch.setitem(_THUNDER_AMPEL_BAND, MED, "red")` |
| `tests/tdd/test_issue_654_telegram_thunder_drilldown.py:210` | schwacher `any`-Check über `["kein","mittel","hoch","⚪","🟡","🔴"]` |
| `tests/tdd/test_command_reply_channel_emoji.py:49,206` | bindet nur „Telegram hat einen Kreis, E-Mail/SMS keinen" — keine Stufe |
| `tests/fixtures/thunder_scale_guard_cases/faelle.py.txt:209-219` | bandtreue **Paraphrase**, kein Zitat des Produktivcodes — bindet nichts |

`tests/test_chip_ampel_farben.py:39-80`, `tests/tdd/test_outlook_metric_ampelfarben.py:122-145`
und `tests/tdd/test_thunder_column_ampel.py:187-197` binden die **Mail**-Seite und dürfen sich
nicht ändern.

---

## Befund C5-38 — `?–?`-Zeilen in der Timeline

### Ist-Stand

`TripCommandProcessor._mit_datiertem_rueckfall`, `src/services/trip_command_processor.py:1390-1446`.
Die Entscheidung „Anker behalten oder datierten Snapshot nachziehen" fällt **pro Tag**:

```python
if any(_traegt_tageswerte(timeline.points[i]) for i in tages_idx):
    continue                       # :1425  — alles-oder-nichts
verworfen.update(tages_idx)        # :1433  — verwirft dagegen ALLE Punkte des Tages
```

Die Asymmetrie ist der Kern des Befunds: es gibt keinen Zwischenzustand „einzelne leere
Punkte eines sonst getragenen Tages entfernen".

`_traegt_tageswerte` (`:251-270`) prüft sechs Felder auf `point.metrics`
(`temp_min_c`, `temp_max_c`, `wind_max_kmh`, `precip_sum_mm`, `thunder_level_max`, `pop_max_pct`).

### Betroffene Kommandos

Einziger Aufrufer: `_handle_query` `:910-914`. Betroffen sind `glance`, `heute_gewitter`,
`timeline_heute`, `timeline_morgen` — über **alle drei** Eingangskanäle (Telegram,
E-Mail-Freitext, Premium-SMS via `inbound_sms_reader.py:259-266`).
**Nicht** betroffen: `/heute` und `/morgen` (lösen vor dem Timeline-Aufbau ein volles Briefing
aus, `:889-895`) und sämtliche Drilldowns (eigener Pfad über `WeatherExtractor.drilldown`).

### Verschärfung gegenüber der Issue-Beschreibung

Ein Punkt mit ausschließlich `None`-Metriken rendert nicht nur Fragezeichen
(`_fmt_timeline:1657-1662`, `_fmt_day_agg:1528-1531`):

```
🕐 10:00
   🌡 ?–? °C  💨 ? km/h  🌧 0.0 mm  ⛈ kein
```

`precip` fällt auf `"0.0"` (`else "0.0"`, nicht `"?"`), `t_label` über
`_thunder_words().get(..., "NONE", …)` auf `"kein"`. Die Zeile **behauptet aktiv**
„0,0 mm Regen und kein Gewitter", wo nichts gemessen wurde. Das ist gravierender als eine
Lücke und berührt den Grundsatz „nur Daten, nie Behauptungen über Ungemessenes".
In `_fmt_day_agg` ist `precip` zusätzlich ein Falsy-Check (`if agg.get('precip')`) — `0.0`
und `None` rendern beide `"0.0"`.

### Warum die ehrliche Fehlanzeige nicht greift

`_tagesaussage_ohne_daten` (`:1448-1481`) wird an allen drei Ausgabestellen nur bei **leerer**
Punktliste erreicht (`_fmt_timeline:1645-1653` `if not pts:`, `_fmt_glance:1570-1584`,
`_fmt_gewitter:1598-1602`; `_aggregate_day` gibt `None` nur bei `not points`, `:1495-1497`).
Der Torwächter fragt „Liste nicht leer?", nicht „Liste trägt Werte?". Ein einziger
inhaltsleerer Punkt genügt, um die Fehlanzeige zu verdecken.

### Spec- und Testlage

`docs/specs/modules/fix_1818_timeline_tagesaufloesung.md` formuliert **alle** AC auf
Tagesebene (AC-1 `:121-123`, AC-3 `:134-136`, AC-4 `:141-143`, AC-5 `:148-151`,
AC-7 `:164-166`, AC-8 `:172-175`). Der Mischfall „ein Wegpunkt trägt, die Nachbarn nicht"
ist von dieser Spec **nicht erfasst** — C5-38 ist eine Spec-Lücke, kein Regelbruch.

Zu wahrende Zusicherungen (dürfen durch den Fix nicht brechen):

| Datei:Zeile | Zusicherung |
|---|---|
| `tests/tdd/test_timeline_tagesgenaue_quellen.py:406` | **AC-4**: undatierter Anker schlägt den datierten Snapshot |
| dto. `:530` | **AC-7**: Antwort schreibt nichts und ruft nichts ab |
| dto. `:676` | **F005**: leerer Platzhalter verliert gegen echte Werte |
| dto. `:723` | **F005-Grenzfall**: beide Quellen leer → ehrliche Datenlücke |
| dto. `:763` | **F001 CRITICAL**: Rückfall-Wegpunkt rutscht nicht in den Nachbartag |
| `tests/tdd/test_adhoc_tageswert_ab_anfragezeit.py:558-620` | **#2186**: Rückfall ist genauso ab Anfragezeit gefenstert wie der Anker |

**Messlücke:** beide F005-Tests bauen den Tag mit **genau einem** Wegpunkt
(`_platzhalter_segmente:655-673`). Der Mischfall ist heute nirgends abgedeckt — der
RED-Test muss ihn erzeugen.

---

## Befund C5-58 — unbekannter Kanalname in `_resolve_channel_flags`

### Ist-Stand

`src/services/trip_report_scheduler.py:1719-1765`, Kern `:1747-1753`:

```python
if restrict_to_channel is not None:
    return (restrict_to_channel == "email",
            restrict_to_channel == "sms" and sms_allowed(user_id),
            restrict_to_channel == "premium_sms" and premium_sms_allowed(user_id),
            restrict_to_channel == "telegram")
```

Ein unbekannter Wert ergibt viermal `False`.

### Zwei Korrekturen an der Issue-Beschreibung

**1. Der Titel sagt „fail-open" — es ist das Gegenteil.** Vier `False`-Flags bedeuten:
nichts wird versendet.

**2. „still" stimmt nur für einen der beiden Zweige.** Der Hauptpfad ist nicht stumm:

- `src/services/notification_service.py:533-540` → `no_channel_configured = True`
- `src/services/trip_report_scheduler.py:1630-1633` → `logger.warning("Trip report NOT sent (no channel configured)")`
- dto. `:1701-1704` → `return "no_channels"`
- `src/services/trip_command_processor.py:583-587` → Nutzertext „Keine Versandkanäle für
  diesen Trip aktiv — Briefing nicht gesendet. Kanäle im Trip-Editor aktivieren."

Die tatsächliche Eigenschaft ist damit **Fehlzuschreibung, nicht Stille**: Log und Nutzertext
behaupten beide „kein Kanal im Trip konfiguriert", während die Ursache ein nicht erkannter
Kanalname wäre. `restrict_to_channel` erscheint in keiner der beiden Meldungen.

**Vollständig stumm ist nur der No-Data-Hint-Zweig** (`trip_report_scheduler.py:1399-1418`):
`send_no_data_hint` (`notification_service.py:715-775`) hat pro Kanal nur ein `if send_X:`,
kein Else und keine Bilanz; der Rückgabewert wird an `:1405` nicht einmal zugewiesen.

### 🔴 Die Falle für jeden Fix

Vier `False`-Flags sind bereits ein **legitimer, spezifizierter** Zustand:
`restrict_to_channel="sms"` bei `sms_allowed(user_id) == False` ergibt exakt
`(False, False, False, False)` — das ist `feat_2126` **AC-5** (`:197-207`), zugesichert durch
`tests/tdd/test_kanaltreue_adhoc_antwort.py:563,566-569`.

⇒ Ein Wächter „alle vier False ⇒ Fehler/Warnung" **bricht AC-5**. Unterscheidbar sind die
beiden Wege ausschließlich über eine Prüfung des **Namens**, nicht des Ergebnisses.

### Eintrittswahrscheinlichkeit heute

Alle drei `InboundMessage`-Erzeuger setzen ein hartkodiertes Literal:
`inbound_email_reader.py:176` → `"email"`, `inbound_telegram_reader.py:232,328` → `"telegram"`,
`inbound_sms_reader.py:264` → `"premium_sms"`. Ein unbekannter Name kann heute nur durch eine
**Codeänderung** an einem der Reader entstehen. C5-58 ist damit ein **latenter** Defekt
(Robustheit / künftiger fünfter Kanal), kein aktuell nutzersichtbares Fehlverhalten — das ist
für die Priorisierung innerhalb des Tickets relevant.

### Fehlende Kanonik

Es gibt **kein** Enum und **keine** zentrale Kanalnamen-Konstante. Stattdessen sechs
unabhängige Ad-hoc-Listen: `alert_log.py:85`, `trip_alert.py:2903`,
`channel_layout.py:46-56`, `email/undelivered_hint.py:40-43`, `channels/base.py:119-137`,
`trip_command_processor.py:474`. `InboundMessage.channel` (`:59-66`) ist ein nacktes `str`
ohne `__post_init__`; der Wert kommt ungeprüft bei `_resolve_channel_flags` an.

Etablierte Muster für unbekannte Kanalnamen — drei verschiedene, keins einheitlich:

| Muster | Beispiel |
|---|---|
| strikt (`ValueError`) | `src/output/channels/base.py:137` |
| stiller Fallback | `src/output/renderers/channel_layout.py:134` (Kommentar `:140` benennt es) |
| Fallback auf Rohwert | `src/output/renderers/email/undelivered_hint.py:169` |

Ein `logger.warning` für einen unbekannten Kanalnamen existiert nirgends im Repo.

### Testlage

`tests/tdd/test_kanaltreue_adhoc_antwort.py:464-506, 511-596, 634-713, 748-796` und
`tests/tdd/test_premium_sms_kommandopfad.py:459,478`. Als Literale kommen nur `"sms"`,
`"premium_sms"`, `"telegram"` und `None` vor — **kein Test für einen unbekannten Kanalnamen**.

`docs/specs/modules/feat_2126_kanaltreue_adhoc_antwort.md:263-269` (Known Limitations) sagt
ausdrücklich: „`_resolve_channel_flags` ist so gebaut, dass sie für alle vier Kanalnamen
korrekt auflöst, sobald sie eintreffen können." Der unbekannte Name ist **bewusst nicht
spezifiziert** — auch hier eine Spec-Lücke, kein Regelbruch.

---

## Related Files

| Datei | Relevanz |
|---|---|
| `src/services/trip_command_processor.py` | C5-63 (`:209`, `:219-224`, `:301`) und C5-38 (`:251-270`, `:1390-1446`, `:1521-1554`, `:1629-1697`, `:1448-1481`) |
| `src/services/trip_report_scheduler.py` | C5-58 (`:1719-1765`, Aufrufer `:1399-1402`, `:1806-1808`, Rückgabewege `:1630-1633`, `:1701-1704`) |
| `src/services/notification_service.py` | C5-58 stromabwärts (`:533-540`, `:715-775`) |
| `src/output/metric_format.py` | kanonische Bandquelle (`:307-326`) — **nicht ändern** |
| `docs/reference/renderer_email_spec.md:256` | SSoT der Mail-Farbskala — Zielbild für die Kanalparität |

## Existing Specs

- `docs/specs/modules/fix_1818_timeline_tagesaufloesung.md` — AC auf Tagesebene (C5-38)
- `docs/specs/modules/feat_2186_tagesaggregat_ab_jetzt.md` — Fensterung des Rückfalls
- `docs/specs/modules/feat_2126_kanaltreue_adhoc_antwort.md` — AC-4/AC-5 (C5-58, Falle)
- `docs/specs/modules/feat_1676_s2a_premium_sms_versand.md` — D7, Tier-Gate-Trennung
- `docs/specs/modules/fix_1491_gewitter_ampelkreis.md` — PO-Entscheidung NONE=grün (Mail)
- `docs/specs/modules/feat_2176_luftmasse_statt_gewitteransage.md:327-332` — LOW-Farbe offen
- `docs/specs/modules/fix_2010_2011_gewitter_stufenwoerter.md` — Wörter kanonisch, Emojis nicht
- ADR-0025 — „Lokale Dict-Literale für ThunderLevel sind verboten"

**Für #2220 existiert noch keine Spec.**

## Risks & Considerations

1. **🔴 AC-5-Falle (C5-58):** ein Wächter auf „alle vier Flags False" bricht `feat_2126` AC-5.
   Geprüft werden muss der **Name**, nicht das Ergebnis.
2. **🔴 Bestandstest zementiert den Ist-Stand (C5-63):**
   `test_thunder_stage_words_from_canonical_source.py:75-96` muss mitgeändert werden — das ist
   legitim (er prüft veraltetes Verhalten), aber es muss in der Spec stehen, sonst sieht es
   nach Test-Anpassung-an-den-Code aus.
3. **PO-Entscheidung offen (C5-63):** Zielskala A oder B. Gehört in die Spec-Freigabe, nicht
   in die Implementierung.
4. **Mail-Seite darf sich nicht bewegen:** `test_chip_ampel_farben.py`,
   `test_outlook_metric_ampelfarben.py`, `test_thunder_column_ampel.py`,
   `test_issue_811_mode_matrix.py:29` binden die E-Mail-Ampel.
5. **C5-38 berührt einen dreifach abgesicherten Bereich** (#1818 F001/F005, #2186 AC-1/AC-10).
   Der Fix muss von Tages- auf Punktgranularität wechseln, ohne AC-4 (Anker schlägt Snapshot)
   und F001 (kein Tagesübertritt) zu verletzen.
6. **Die `0.0 mm` / `kein`-Fallbacks (C5-38)** sind eine eigene, größere Fläche: sie behaupten
   Ungemessenes auch außerhalb des Rückfall-Pfads.
   **Entschieden (Intake, nicht erneut aufmachen):** enge Lesart — dieses Ticket repariert die
   Fallbacks **nur dort, wo der Mischfall sie erzeugt**. Die breite Fläche (alle Stellen, an
   denen `precip`/`thunder` bei fehlender Messung eine Zahl bzw. „kein" behaupten) geht als
   Checkbox-Zeile nach **#1199** — kein eigenes Issue, weil über #2220 hinaus kein
   nutzersichtbares Fehlverhalten belegt ist (Nebenbefund-Triage). Die Spec muss diese
   Abgrenzung im Scope-Abschnitt ausdrücklich benennen; LoC-Limit 250.
7. **Kein Adversary-Artefakt zu #1818 vorhanden** (`docs/artifacts/fix-1818-…` fehlt), obwohl
   die Testdoku darauf verweist — die F005-Begründung steht nur in den Testkommentaren.
8. **Premium-SMS ist bei C5-63 nicht betroffen** (kein Emoji), bei C5-38 und C5-58 schon.
   Der Issue-Titel suggeriert etwas anderes.

## Dependencies

- **Upstream:** `thunder_ampel_band()` / `_THUNDER_AMPEL_BAND` (`metric_format.py`),
  `THUNDER_LABEL_DE` (`app/thunder_scale.py`), `WeatherExtractor.timeline_dated`,
  `sms_allowed()` / `premium_sms_allowed()` (`user_tier.py`)
- **Downstream:** Telegram-Drilldown-Ausgaben, Timeline-/Glance-/Gewitter-Antworten auf allen
  drei Eingangskanälen, Briefing-Versand über `send_on_demand_report`

---

# Analysis (Phase 2, 2026-09-09)

### Type

**Bug** — drei unabhängige Befunde, gebündelt in einem Workflow.

---

## Entschieden in dieser Phase: C5-63 Zielskala = **A**

Der Intake hat `/20-analyse` genau eine Frage gestellt: *Können die amtlichen Warnstufen-Emojis
und die Gewitter-Emojis jemals in derselben Telegram-Nachricht auftreten?* Die Antwort ist
**Nein** — und die Begründung für Option B fällt sogar noch eine Ebene tiefer weg.

**1. Die amtliche Stufe 1 (🟢) wird nie gerendert.** Alle Rendering-Pfade filtern vorher auf
`level >= 2`:

| Beleg | Wirkung |
|---|---|
| `src/output/renderers/alert/narrow.py:406` | `alert.level >= _min_level` vor dem Rendern der Bubble |
| `src/output/renderers/alert/comparison.py:801` | dto., `_min_level = min_official_level_for_threshold("LOW")` → 2 |
| `src/app/alert_urgency.py:80-89` | Minimum der Auflösung ist 2, Fallback `MIN_SMS_LEVEL` = 3 |
| `src/app/hazard_symbols.py:34,37` | `LEVEL_LETTERS = {2,3,4}` — Stufe 1 hat keinen Buchstaben |
| `src/output/renderers/alert/official_alerts.py:52` | `_LEVEL_POSITION` kennt nur 2,3,4 — Stufe 1 ergäbe den Kopf „(0/3)", ein nie erreichter Zweig |

`level=1`-Fixtures existieren nur in SMS-/Dedup-Tests, nicht im Telegram-Pfad.

**2. Die beiden Emoji-Sätze können sich strukturell nicht begegnen.**
`src/services/trip_command_processor.py` importiert `official_alerts` **nirgends**. Das
Warnstufen-Emoji wird ausschließlich in `render_official_alert_telegram`
(`official_alerts.py:1839`, Zuweisung `:1891`) emittiert — erreichbar nur über
`narrow.py:416`, `comparison.py:813` und `notification_service.py:1075`. Alle übrigen ~10
Fundstellen von `_LEVEL_WORDS` verwerfen das Emoji ausdrücklich (`_emoji`/`_e`) und nutzen nur
das Wort. Die Drilldown-/Timeline-Formatierer mit `_BAND_EMOJI` liegen auf einem getrennten
Pfad und erzeugen getrennte `CommandResult`-Objekte, also getrennte Nachrichten.

**3. Die Prämisse „A = Parität zur E-Mail" stimmt so nicht mehr — und das stärkt A.**
Die HTML-Mail rendert seit #1222 gar keine Emoji-Glyphen, sondern CSS-Punkte
(`_ampel_dot_css`, `src/output/renderers/email/helpers.py:606-622`, Farbtabelle
`_AMPEL_DOT_COLORS:591-596`). Diese Tabelle ist **auf Bandnamen geschlüsselt und bandtreu**:
`green→grün`, `yellow→gelb`, `orange→orange`, `red→rot`. `renderer_email_spec.md:256` nennt
🟢🟡🟠🔴 nur als Doku-Kurzschrift für die Stufen.

⇒ Damit ist `_BAND_EMOJI` **die einzige Band→Symbol-Tabelle im Repo, deren Symbol dem eigenen
Schlüssel widerspricht.** Die Korrektur ist keine Farbwahl, sondern das Auflösen eines
Selbstwiderspruchs: der Schlüssel `"yellow"` muss ein gelbes Symbol tragen.

**Empfehlung an den PO (eine, nicht zwei):**

```python
_BAND_EMOJI = {"green": "🟢", "yellow": "🟡", "orange": "🟠", "red": "🔴"}
```

Der einzige sichtbare Zusatzeffekt ist NONE ⚪ → 🟢. Das folgt der bereits getroffenen
PO-Entscheidung aus `fix_1491_gewitter_ampelkreis.md:252-255` (grüner Kreis für NONE in der
Trip-Stundentabelle). Option B (⚪ für NONE behalten) hätte als einzige Begründung die
Verwechslung mit dem amtlichen 🟢 gehabt — die ist nach Punkt 1 und 2 gegenstandslos.

---

## Widerspruch im Ticket-Zuschnitt (C5-58)

#2220 wurde aus #1199 abgespalten mit dem Kriterium **„(a) nutzersichtbares Fehlverhalten"**.
C5-58 erfüllt dieses Kriterium nach eigener Recherche **nicht**: alle drei `InboundMessage`-
Erzeuger setzen hartkodierte Literale, ein unbekannter Kanalname kann heute nur durch eine
Codeänderung entstehen. Es ist ein **latenter** Robustheitsdefekt.

**Bewertung:** Nachträgliches Zurückgeben nach #1199 kostet mehr Workflow-Overhead als der
Fix selbst (~20–35 LoC, Risiko LOW). Empfehlung: **im Ticket belassen**, aber in der Spec
ausdrücklich als Robustheitsfix ohne belegtes Nutzersymptom kennzeichnen — damit #2220 später
nicht als Präzedenz zitiert wird, dass latente Befunde eigene Issues bekommen.

---

## Affected Files (with changes)

| File | Change Type | Description |
|------|-------------|-------------|
| `src/services/trip_command_processor.py` | MODIFY | C5-63: `_BAND_EMOJI` (`:209`) bandtreu setzen · C5-38: `_mit_datiertem_rueckfall` (`:1390-1446`) von Tages- auf Punktgranularität |
| `src/services/trip_report_scheduler.py` | MODIFY | C5-58: Namens-Guard + `logger.warning` vor dem Return (`:1747-1753`) |
| `tests/tdd/test_thunder_stage_words_from_canonical_source.py` | MODIFY | `:75-96` zementiert den Ist-Stand — auf Zielskala A umstellen |
| `tests/tdd/test_timeline_tagesgenaue_quellen.py` | MODIFY | RED-Nachweis Mischfall + neue Mehrpunkt-Tag-Fixture |
| `tests/tdd/test_kanaltreue_adhoc_antwort.py` | MODIFY | RED-Nachweis unbekannter Kanalname; AC-5 muss grün bleiben |

Vollständigkeit der Testlage geprüft: `grep -rl "🟢\|🟡\|⚪" tests/` findet 16 Dateien; außer
den drei bereits im Intake genannten sind alle Mail-seitig und dürfen sich nicht bewegen.

## Scope Assessment

| Befund | LoC (netto) | Risiko | Begründung |
|---|---|---|---|
| C5-63 | ~15–25 | **LOW** | isolierte Wertekorrektur, ein Dict + Testanpassung |
| C5-58 | ~20–35 | **LOW** | additiver Guard, Rückgabewert unverändert |
| C5-38 | ~90–160 | **MEDIUM** | dreifach abgesicherter Bereich (#1818 F001/F005, #2186), Punkt-Zuordnung ist echte Entwurfsarbeit, Messlücke muss zuerst geschlossen werden |
| **Gesamt** | **~125–220** | | Limit 250 reicht voraussichtlich, aber knapp |

**LoC-Hinweis:** C5-38 ist der Posten mit Sprengpotenzial. Falls das Limit fällt, ist
`workflow.py set-field loc_limit_override 500` der vorgesehene Weg — **nicht** den Fix künstlich
verengen.

## Technical Approach

**Reihenfolge: C5-58 → C5-63 → C5-38.** Die beiden kleinen, unabhängigen Fixes zuerst; sie
schaffen Klarheit über das verbleibende LoC-Budget, bevor die aufwändige Punkt-Zuordnung
beginnt.

**C5-63 —** Dict lokal lassen, nur die Werte korrigieren. Kein Umzug nach `metric_format.py`:
ADR-0025 Entscheidung 3 (`docs/adr/0025-…:71-72`) verbietet **ThunderLevel-Enum-geschlüsselte**
Zahlenskalen (Muster `_TH_VAL`), nicht bandnamen-geschlüsselte Symboltabellen. `_BAND_EMOJI` ist
strukturell identisch zum bereits akzeptierten `_AMPEL_DOT_COLORS` (`email/helpers.py:591`) —
Band→Visual-Symbol lebt im konsumierenden Renderer-Modul. Ein Umzug bräche dieses Muster.

**C5-58 —** Menge der vier bekannten Kanalnamen neben `_resolve_channel_flags`, davor
`if restrict_to_channel not in <Menge>: logger.warning(...)`. **Der Rückgabewert bleibt
unverändert** `(False, False, False, False)` — geändert wird nur die Beobachtbarkeit. Damit ist
die AC-5-Falle umschifft: geprüft wird der **Name**, nicht das Ergebnis
(`feat_2126` AC-5, `test_kanaltreue_adhoc_antwort.py:563`).
Gegen `ValueError`: der Aufrufer müsste einen bisher tolerierten Zustand hart behandeln —
unverhältnismäßig für einen latenten Defekt. Gegen ein Kanal-Enum: Cross-Cutting-Refactoring
über sechs Ad-hoc-Listen, eine Größenordnung über dem Nutzen, und ohne Deckung im Regel-Budget.

**C5-38 —** Pro Tag die tragenden Anker-Punkte behalten und nur die **einzelnen
nicht-tragenden** Punkte durch den passenden Punkt des datierten Snapshots ersetzen; trägt auch
der nicht, fällt der Punkt weg. Die drei Ausgabestellen (`_fmt_timeline:1642-1653`,
`_fmt_glance:1571-1586`, `_fmt_gewitter:1599-1602`) müssen **nicht** angefasst werden: sie
prüfen bereits „Liste leer?" und rufen dann `_tagesaussage_ohne_daten` — ein leergefegter Tag
erzeugt die ehrliche Fehlanzeige von selbst.

Zusicherungen bleiben wahrbar: AC-4 hängt an `:1425` (`any(...)` → `continue`), das unverändert
bleibt; F001 am Tagesfilter `local_dt(...).date() == target_date` (`:1424`, `:1437`), ebenfalls
unverändert; F005 und #2186 hängen an `from_time`-Fenster und `_traegt_tageswerte`, die
wiederverwendet statt geändert werden.

## Scope-Abgrenzung (wörtlich in die Spec übernehmen)

Dieses Ticket repariert die `0.0 mm` / `kein`-Fallbacks **nur dort, wo der Mischfall sie
erzeugt**. Die breite Fläche — alle Stellen, an denen `precip`/`thunder` bei fehlender Messung
eine Zahl bzw. „kein" behaupten — geht als Checkbox-Zeile nach **#1199**; kein eigenes Issue,
weil über #2220 hinaus kein nutzersichtbares Fehlverhalten belegt ist.

Technisch ist diese Abgrenzung von selbst eingehalten, nicht bloß Absichtserklärung: durch die
Punkt-Entfernung steht der leere Punkt gar nicht mehr in der Liste, `_fmt_timeline:1665` und
`_fmt_day_agg:1550` bleiben unberührt.

## Dependencies

Unverändert gegenüber dem Intake-Abschnitt oben. Ergänzend als **nicht zu ändern** markiert:
`_ampel_dot_css`/`_AMPEL_DOT_COLORS` (`email/helpers.py:591-622`) und der gesamte
`official_alerts.py`-Pfad.

## Open Questions

Keine PO-Fragen offen. Die Farbwahl A/B ist oben aufgelöst und geht als **Empfehlung**, nicht
als Menü, in die Spec-Freigabe.

Eine technische Entwurfsfrage ist in der Spec zu klären (**keine PO-Frage**):

- [ ] **C5-38 Punkt-Zuordnung:** Wie werden Anker-Punkt und Snapshot-Punkt einander zugeordnet
      — über `arrival_time` oder über den Index? Beide Listen stammen aus verschiedenen
      Snapshot-Läufen; bei zwischenzeitlich geänderter Routenstruktur ist Index-Gleichheit nicht
      garantiert. Das ist der eigentliche Entwurfsaufwand und der Treiber der LoC-Schätzung.

## Nebenbefund (→ #1199, kein eigenes Issue)

`send_no_data_hint` (`notification_service.py:715-775`) ist vollständig stumm — pro Kanal nur
`if send_X:`, kein Else, keine Bilanz; der Rückgabewert wird bei
`trip_report_scheduler.py:1405` nicht einmal zugewiesen. Kosmetisch/Observability, kein
belegtes Nutzersymptom.
