# Context: feat-2185-wechselpunkte-ab-jetzt

Issue: #2185 — Scheibe S2 von Epic #2133
Erhoben: 2026-09-07 (Phase 1, Full-Process-Track)

## Request Summary

Ein Ad-hoc-Abruf soll das **verbleibende** Fenster beantworten statt des ganzen Kalendertags,
und einen Verlauf als **Wechselpunkte** darstellen statt als Stunde-für-Stunde-Liste. O-Ton PO
(Epic #2133): „Es ist im Moment neblig und ich will wissen, wann die Wolken sich verziehen."

Beim Nachmessen zerfällt das in zwei unabhängige Befunde, die das Epic als einen bündelt:

- **Teil A — „ab jetzt" fehlt nur den drei Tages-Aggregaten** (`glance`, `heute_gewitter`,
  `timeline_heute`). Sie filtern rein auf den Kalendertag; wer um 15:00 fragt, bekommt den
  Vormittag mitgerechnet.
- **Teil B — der Einzelgrößen-Verlauf ist bereits „ab jetzt" gefenstert** (kam mit S1/#2134),
  listet aber weiter jede Stunde einzeln. **Das ist der eigentliche PO-Fall.**

## Related Files

| Datei | Relevanz |
|---|---|
| `src/services/trip_command_processor.py` | Einzige Produktivdatei. `_aggregate_day` (:1278), `_fmt_glance` (:1355), `_fmt_gewitter` (:1384), `_fmt_timeline` (:1422), `_timeline_buttons` (:1482) tragen Teil A; `_format_drilldown` (:1174) trägt Teil B |
| `src/utils/timezone.py:123-133` | `local_dt` / `local_hour` / `local_fmt` — Ortszeit-Auflösung für Wechselpunkt-Grenzen, unverändert wiederverwendet |
| `src/services/trip_day.py:90-96` | `trip_local_today` — Ortstag-Auflösung, von `_day_window` genutzt |
| `src/app/metric_catalog.py` | Liefert je Größe den bestehenden Formatierer; die Wechselpunkt-Gruppierung nutzt ihn unverändert |

## Existing Patterns

- **`_day_window` (:1133-1172) ist das Referenzmuster für „ab jetzt".** Für `today` liefert es
  bereits `(received_at, +12 h)`. Teil A soll dasselbe Verhalten in `_aggregate_day` tragen —
  nicht neu erfinden.
- **Optionaler Parameter mit `None` als neutralem Element** — exakt die alte Formel, keine
  Einschränkung. So löste S3/#2126 `restrict_to_channel`.
- **Ein Vokabular:** Die „Kategorie" eines Wertes ist der Text, den der bestehende Formatierer
  erzeugt. Keine zweite, pro Metrik gepflegte Bandbreiten-Definition (Epic-Prinzip 1).
- **`received_at` liegt in `_handle_query` bereits vor** und wird nur nicht weitergereicht.

## Dependencies

**Upstream** (was unser Code nutzt): `_day_window`, der Metrik-Katalog-Formatierer aus S1,
die Ortszeit-Helfer, `trip_local_today`.

**Downstream** (was unseren Code nutzt):

- `_format_drilldown` hat **zwei** Aufrufer: `_handle_drilldown` (:965, drei Legacy-Token
  thunder/wind/precip) und `_handle_metric_drilldown` (:1023, jede S1-Katalog-Größe). Eine
  Änderung wirkt auf beide — gewollt, aber die Testlast verdoppelt sich.
- `_aggregate_day` hat **vier** Leser: `_fmt_glance` (:1369, :1370), `_fmt_gewitter` (:1394),
  `_timeline_buttons` (:1487). `_fmt_timeline` filtert **direkt** (:1440), nicht über
  `_aggregate_day` — es braucht denselben Zusatzfilter separat. **Ein halber Fix, der nur
  einen Leser erreicht, ist die naheliegende Mutationsfalle.**
- Kein externer Konsument: die Formatierer werden nur modulintern aufgerufen. Nach außen gehen
  aus dem Modul nur `ACTIONS_BUBBLE_BUTTONS` und `command_rows` — von der Änderung unberührt.
- Eingangswege in `process()`: nur `inbound_email_reader.py:153` (`channel="email"`) und
  `inbound_telegram_reader.py:249/278/335` (`channel="telegram"`). SMS und Premium-SMS
  erreichen den Prozessor heute nicht (das ist S4/#2184).

## Existing Specs

| Spec | Was sie für uns bindend festlegt |
|---|---|
| `docs/specs/modules/feat_2134_adhoc_abruf_metrik_katalog.md` (S1, live) | Abrufwort kommt ausschließlich aus dem Katalog; Formatierer folgt dem Katalogeintrag; AC-17: Datenlücke muss **benannt** werden, nicht schweigen. Nennt „Zeitachse ab jetzt und Wechselpunkte → S2" wörtlich als eigene Scheibe |
| `docs/specs/modules/feat_2126_kanaltreue_adhoc_antwort.md` (S3, PO-freigegeben) | Muster des optionalen Parameters mit neutralem Default |
| `docs/specs/modules/fix_1818_timeline_tagesaufloesung.md` | Schreibt den heutigen Kalendertag-Filter in `_aggregate_day` fest; AC-7/AC-8: ehrliche, lesbare Fehlanzeige bei fehlenden Daten |
| `docs/specs/modules/fix_1470_drilldown_ortszeit.md` | AC-4: Fenstergrenze **und** Zeilenbeschriftung aus derselben Zonenauflösung |
| `docs/specs/modules/fix_1795_timeline_ortszeit.md` | `_fmt_timeline` beschriftet über `local_fmt`, nicht roh |
| `docs/specs/modules/fix_1727_s5a_befehlspfade_ortstag.md` (PO-freigegeben) | Befehlspfade nutzen `trip_local_today`, keine eigene Zonenkopie |
| **`docs/specs/modules/telegram_tier3_drilldown.md`** (**status: live**, PO-„go" 2026-06-08) | 🔴 **Konflikt** — AC-1 sichert eine **stündliche Liste mit ≥6 Zeilen, je Uhrzeit eine** zu. Die Wechselpunkt-Gruppierung macht diese Form-Zusicherung ungültig |

**ADRs:** Zum Antwortformat gibt es keinen. Zur Zeitfenster-Logik: ADR-0044 (Kalendertag nach
Ortszeit), ADR-0035 (Tagesfenster als Zeitraum), ADR-0051 (vorgeschlagen).

## Bewachender Testbestand

Rund 60 Tests über neun Funktionen. Die für die Änderung kritischen Gruppen:

| Gruppe | Fundstellen | Warum kritisch |
|---|---|---|
| **Zeilenzahl festgeschrieben** | `test_issue_654_telegram_thunder_drilldown.py:180`, `:291` (≥6 Zeilen) · `test_telegram_drilldown_local_time_boundary.py:210` · `test_adhoc_abruf_am_telegram_draht.py:254`, `:302` (≥3) | Brechen durch die Gruppierung. Müssen **bewusst umgeschrieben** werden — ein stilles Löschen dreht die Verbesserung später zurück |
| **Volltext-Gleichheit der Antwort** | `test_thunder_origin_trip.py:254`, `:295`, `:352`, `:404`, `:409`, `:433` | `antwort == "⛈ Gewitter heute (…)…"` — brechen bei jeder Formänderung |
| **Direktaufruf mit Positionsargumenten** | `tests/unit/test_ziel_segment_anzeige_invarianz.py:288` (`_fmt_timeline`) | Einziger im ganzen Testbaum; ein neuer Parameter bricht ihn |
| **Ortszeit-/Fenstergrenzen** | `test_timeline_folgt_der_ortszeit.py` (:123, :281, :414, :556, :621, :711, :745) · `test_drilldown_day_window_local_date.py` · `test_telegram_drilldown_local_time_boundary.py` | Bewachen genau die Achse, die Teil A anfasst |
| **Datenlücken ehrlich benennen** | `test_stundenabruf_teilluecken.py:74`, `:118`, `:159` · `test_timeline_tagesgenaue_quellen.py:460`, `:501` · `test_adhoc_metrik_formatierung.py:359`, `:465` | Die Gruppierung darf eine Lücke nicht zu einem Zeitbereich verschmelzen |

**Zeitsteuerung in Tests:** durchweg `freezegun` oder ein durchgereichtes `received_at`, kein
`monkeypatch` auf `datetime.now`. Geteilte Naht: `tests/helpers/adhoc_metrik_fixtures.py:187`,
`:208` (fester `fix.now` → `received_at`) und `tests/tdd/conftest.py:132` (`freeze_time` im
`_anker`-Helfer). Zwei Tests prüfen ausdrücklich, dass der **Anfragezeitpunkt** gilt und nicht
die Systemuhr: `test_timeline_folgt_der_ortszeit.py:745`, `test_befehlspfade_folgen_ortszone.py:624`.

## Risks & Considerations

1. **🔴 Konflikt mit einer live freigegebenen Spec.** `telegram_tier3_drilldown.md` AC-1 fordert
   ≥6 Stundenzeilen. Die Zusicherung meint der Sache nach „man sieht den ganzen Verlauf" und
   drückt das über die Form aus. Wechselpunkte verlieren keine Information (Zeitbereiche sind
   lückenlos), verdichten sie aber. **Die S2-Spec muss diese AC ausdrücklich ablösen** — mit
   dokumentierter Begründung, nicht still. Sonst wird die Verbesserung später „repariert".
2. **Halber Fix bei Teil A.** Vier Leser des Tagesfilters, einer davon (`_fmt_timeline`) filtert
   an anderer Stelle. Die Mutations-Gegenprobe muss jeden Leser einzeln treffen.
3. **`from_time` darf nie für „morgen" gelten** — ein noch nicht begonnener Tag wird durch
   „ab jetzt" nicht eingeschränkt. Ein Test, der nur „heute" prüft, fängt diesen Fehler nicht.
4. **Gruppierung muss auf dem formatierten Wert vergleichen, nicht auf dem Rohwert.** Sonst
   erscheinen zwei gerundet identische Stunden als zwei Bereiche. Braucht einen Test, der die
   Rundungsgrenze gezielt trifft.
5. **Datenlücke ≠ Wert.** Eine Lücke darf nicht in einen Zeitbereich eingeschmolzen werden —
   S1/AC-17 und die Lehre aus #2167 (fehlender Wert vs. echte Null) gelten weiter.
6. **LoC-Risiko real.** Die Schwesterscheibe S3/#2126 hatte dasselbe Profil, schätzte +120–180
   und landete bei +817 — fast alles Testanteil. `loc_limit_override` ist einzuplanen.
7. **Kein Bezug zu S4/#2184.** Die hier geänderten Formatierer erreichen nur E-Mail und
   Telegram; S4 nutzt den `heute`/`morgen`-Pfad. Keine Kollision.

## Nebenbefund (nicht Teil dieser Scheibe)

Der Grundsatz „Antwort geht auf demselben Kanal zurück" ist **nirgends erzwungen** — er steht
als Prosa in `docs/specs/modules/inbound_command_channels.md:90` und als Kommentar in
`inbound_email_reader.py:141`. Kein Wächter würde eine Verletzung bemerken. Gehört als
Checkbox-Zeile nach #1199.

Zweiter Nebenbefund: `_handle_drilldown` (thunder/wind/precip, `:912-977`) prüft an `:953` nur
`res.available`, nicht `_traegt_werte` — eine Größe aus lauter `None` liefert dort zwölf Zeilen
„· keine Daten" statt der benannten Fehlanzeige, die S1/AC-17 für die Katalog-Größen vorschreibt
(`_handle_metric_drilldown:1013`). Inkonsistenz zwischen zwei Zweigen derselben Funktion.

---

## Analysis

### Type

Feature (Scheibe eines Epics), Full-Process-Track.

### 🔴 Kernbefund der Analyse: Teil A ist in der geplanten Form nicht leistbar

Der Spec-Draft wollte `_aggregate_day` einen Filter `p.arrival_time >= from_time` geben. Das
schneidet an der **falschen Größe**:

- `_aggregate_day` aggregiert `TimelinePoint` (`trip_command_processor.py:1288`), nicht
  Stundenpunkte.
- `TimelinePoint` trägt nur `arrival_time` und eine **fertige Etappen-Zusammenfassung**
  (`weather_extractor.py:41-45`) — kein Segment-Anfang, keine Stundenauflösung.

Folge: Eine Etappe, die um 10:00 endet und deren Wetter 06:00–10:00 abdeckt, bleibt bei einer
Anfrage um 09:30 **vollständig** drin (samt Vormittagsregen) und verschwindet bei 10:30
**vollständig**. Bei einer Etappe pro Tag ist das ein Alles-oder-nichts-Schalter — schlechter
als der Ist-Zustand. Die Draft-ACs AC-3 und AC-4 behaupten etwas, das dieser Filter strukturell
nicht leisten kann.

Die ehrliche Variante wäre, die Tageswerte aus den Stundenreihen **neu zu berechnen**
(`precip`, `temp_max`, `wind_max`, `thunder`, `pop`, `hail_flag`, `thunder_signals`), also die
Rechnung zu ersetzen statt zu filtern. Das zieht eine zweite Datenquelle in die Aggregation
(`self._snapshots.load`, `weather_extractor.py:164`) und berührt `fix_1818` direkt (dessen
Kalendertag-Filter und Quellenauflösung), `fix_1795` mittelbar (Ortstag-Filter wandert von
`arrival_time` auf `ts`) sowie die sechs Volltext-Tests in `test_thunder_origin_trip.py`.

**Entscheidung: Teil A wird abgetrennt und als eigenes Ticket geführt.** #2185 liefert Teil B.

### Affected Files (with changes)

| Datei | Änderung | Beschreibung |
|---|---|---|
| `src/services/trip_command_processor.py` | MODIFY | `_format_drilldown` (:1174) gruppiert; Kopfzeile `— stündlich` → `— Verlauf` (:1191) |
| `tests/tdd/test_adhoc_verlauf_wechselpunkte.py` | CREATE | Neue Wächter für Gruppierung, Lücken, Rundungsgrenze, Kanalparität |
| `tests/tdd/test_issue_654_telegram_thunder_drilldown.py` | MODIFY | Zeilenzahl-Zusicherung (:180, :291) durch Abdeckungs-Zusicherung ersetzen |
| `tests/tdd/test_telegram_drilldown_local_time_boundary.py` | MODIFY | dito (:210) |
| `tests/tdd/test_adhoc_abruf_am_telegram_draht.py` | MODIFY | Schwelle `>=3` (:254, :302) ersetzen |
| `docs/specs/modules/telegram_tier3_drilldown.md` | MODIFY | AC-1 als abgelöst markieren (nicht löschen) |

### Technical Approach

1. **Gruppenschlüssel = (formatierter Text, Hagelnotiz-Text).** Nicht der Rohwert — die
   Rundung des bestehenden Formatierers *ist* die Kategorie (Epic-Prinzip „ein Vokabular").
   Die Hagelnotiz im Schlüssel lässt die Gruppe automatisch brechen, wenn sie wechselt.
2. **Fortsetzungsbedingung `ts_next - ts_cur <= 1 h`**, nicht `== 1 h`. Gleichheit bräche bei
   feinerem Raster; die Obergrenze degradiert bei gröberem Raster sauber auf die heutige
   Einzelzeilen-Form — fail-safe statt falsch. **Eine fehlende Stunde beendet die Gruppe** und
   verhindert damit, dass ein Zeitbereich eine Lücke überbrückt.
3. **Fehlende Werte brauchen keine Sonderlogik:** `fmt(None)` erzeugt einen eigenen Text
   („· keine Daten" bzw. „–") und damit einen eigenen Gruppenschlüssel. Die Lücke bleibt
   benannt (S1/AC-17), mehrere Lücken hintereinander werden ehrlich zu einem Bereich.
4. **Zeilenform unverändert:** `f"{zeit}  {wert}"`, optional `· {note}`. Nur das Zeitfeld wird
   bei ≥2 Punkten zu `HH:MM–HH:MM` (beide über `local_fmt`, damit bleibt `fix_1470` AC-4
   gewahrt). Eine Einzelstunde bleibt **zeichengleich** zu heute — das hält jeden Volltext-Test
   grün, dessen Fixture stündlich wechselt.
5. **Kein „ab HH:MM".** Das Fensterende kann über das Ende der gespeicherten Reihe hinausreichen
   (`weather_extractor.py:195`); „ab 14:00" behauptete dann Gültigkeit für Stunden ohne Daten —
   genau die #2167-Falle. Die letzte Gruppe wird wie jede andere geschlossen: `14:00–19:00`.
6. **Kopfzeile `— Verlauf`** statt `— stündlich`. Nachgemessen: kein Test prüft diesen String,
   die Treffer auf „stündlich" im Testbaum sind Kommentare und Docstrings.

### Ablösung der widersprechenden Spec

`telegram_tier3_drilldown.md` (status live, PO-„go" 2026-06-08) AC-1 fordert ≥6 Stundenzeilen.
Ersatz ist **keine zweite Formvorschrift, sondern eine Abdeckungs-Zusicherung**:

> Jeder Zeitpunkt, für den im Antwortfenster ein Datenpunkt vorliegt, ist von genau einer Zeile
> abgedeckt — und keine Zeile deckt einen Zeitpunkt ab, für den keiner vorliegt.

Prüfbar, indem der Test aus den Zeilen die Menge der abgedeckten Stunden rekonstruiert und mit
`res.points` vergleicht. Das ist **stärker** als „≥6 Zeilen" (fängt auch verschluckte Punkte
ganz ohne Gruppierung), erlaubt jede Verdichtung und verbietet genau das Überbrücken einer
Lücke. Die alte AC-1 wird nicht gelöscht, sondern als „abgelöst durch #2185, PO-Entscheid
<Datum>" markiert.

### Scope Assessment

| | Produktivcode | Tests |
|---|---|---|
| **Teil B — diese Scheibe** | +40–60, 1 Datei | +250–400 |
| Teil A ehrlich — eigenes Ticket | +150–250, 1–2 Dateien | +350–500 |

- Risk Level: **MEDIUM**
- `loc_limit_override 500` ist einzuplanen (Testanteil), nicht erst bei Blockade zu beantragen.

### Risiken, nach Schaden sortiert

1. 🟡 **Rundungsgrenze.** Vergleicht die Gruppierung Rohwerte statt Text, erscheinen 3,4 und 3,6
   als zwei Bereiche. Braucht einen Test, der genau diese Grenze trifft — die Hauptfälle fangen
   das nicht.
2. 🟡 **Lücken-Überbrückung.** Der gefährlichste Fehler ist unsichtbar: Das Ergebnis sieht
   korrekt aus. Eigener Wächter zwingend.
3. 🟡 **Zeilenzahl-Wächter** an fünf Stellen. Brechen nur, wenn ihre Fixtures gruppierbare
   Folgestunden haben — müssen **bewusst umgeschrieben** werden, nicht gelöscht.
4. 🟢 **Kanalparität.** `with_emoji = channel == "telegram"` (`:926`, `:1025`, `:1051`) wirkt nur
   in `_thunder_fmt`. Da der Schalter in den Gruppenschlüssel eingeht, gruppieren beide Kanäle
   identisch — konstruktiv gegeben, kostet je einen Nachweis.
5. 🟢 **Länge.** Nur der Telegram-Transport kappt bei 4096 Zeichen; die Gruppierung verkürzt und
   entlastet diese Grenze.

### Open Questions (für die PO-Freigabe in Phase 3)

- [ ] Ablösung der Zeilenzahl-Zusicherung aus `telegram_tier3_drilldown.md` durch die
      Abdeckungs-Zusicherung — bestätigt der PO das ausdrücklich?
- [ ] Kein „ab HH:MM" für die letzte Gruppe, sondern geschlossener Bereich — einverstanden?

