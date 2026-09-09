---
entity_id: feat_2176_luftmasse_statt_gewitteransage
type: feature
created: 2026-09-08
updated: 2026-09-08
status: draft
version: "1.0"
tags: [gewitter, thunder-level, cape, low-level, wortlaut, issue-2176, epic-1419]
---

# Gewitterstufe LOW verliert die Gewitterformulierung — reine Luftmassen-Aussage statt Ereignisbehauptung (Issue #2176)

## Approval

- [ ] Approved

## Purpose

Die Gewitterstufe „leicht" (`ThunderLevel.LOW`) wird heute in allen vier Kanälen als
**Gewitterereignis** formuliert („Leichtes Gewitter möglich ab 14:00", „⚡ Gewitter möglich",
`TH:L@14`), misst aber nachweislich nur eine **labile Luftmasse**: an Trip KHW 403
(24.08.–05.09.2026, 1 582 Zeilen ICON-D2) lag JEDE „leicht"-Messung über der CAPE-Sprosse
(100 %), 73 % ohne jeden Niederschlag. Diese Spec entfernt die Ereignisbehauptung an allen
identifizierten Formulierungsstellen für LOW, ohne den zugrundeliegenden CAPE-Wert unsichtbar
zu machen und ohne die Alarm-Logik zu berühren.

**PO-Entscheidung (Henning, 2026-09-08, final — keine offene Designfrage mehr auf Ebene der
Grundsatzfrage):** `ThunderLevel.LOW` verlässt die vier-stufige, nutzersichtbare Gewitterleiter
(`keine/möglich/wahrscheinlich/akut`, Epic #1419 Abschnitt 9, PO 2026-07-29) vollständig. Diese
vier Stufen beginnen künftig beim heutigen `ThunderLevel.MED`. „leicht" wird eine eigene,
alarmlose Luftmassen-Größe außerhalb dieser Leiter.

**PO-Entscheidung zum Zuschnitt:** #2176 wird **jetzt einzeln** umgesetzt, nicht mit #2178
(CAPE-Leiter für MED/HIGH) gebündelt — s. Known Limitations für die daraus resultierende
Wirkungsgrenze.

## Source

- **File:** `src/output/metric_format.py` (neue geteilte Quelle für die Stufen*aussage*),
  `src/app/thunder_scale.py` (Herkunfts-Suffix), `src/services/trip_report_scheduler.py`,
  `src/output/renderers/{trip_report,day_window,narrow,sms_trip,comparison,compact_summary}.py`,
  `src/output/renderers/email/{helpers,thunder_branch,compare_html}.py`,
  `src/output/renderers/alert/render.py`, `src/output/subject.py`, `src/app/metric_catalog.py`
- **Identifier:** neue Funktionsfamilie `thunder_low_statement()`/`_thunder_low_is_pure_cape()`
  (Arbeitsnamen, `metric_format.py`, s. Implementation Details Punkt 1) neben
  `THUNDER_LABEL_DE`/`thunder_ampel_band()`; angepasst: `_trend_note()`
  (`trip_report_scheduler.py`), `_compute_highlights()` (`trip_report.py`), `_thunder_word()`
  (`alert/render.py`), `_SMS_RISK_LABELS[(THUNDERSTORM, LOW)]` (`sms_trip.py`)

**Schicht:** ausschließlich Python-Core (`src/app/`, `src/services/`, `src/output/`) plus
möglicher Frontend-Nachzug. Cockpit/Compare-Darstellung der Stufenwörter
(`frontend/src/lib/utils/weatherUtils.ts` u. a.) ist Kandidat, Umfang beim Implementieren am
tatsächlich betroffenen Code zu verifizieren (per `grep` auf `THUNDER_LABEL_DE`/analoge
Frontend-Konstante) — s. Dependencies. Kein Go-API-Bezug.

## Estimated Scope

- **LoC:** grob +150/-100 Quellcode (viele kleine Textbausteine, eine neue geteilte Funktion,
  keine strukturelle Änderung) + Anpassung an ~30 Bestandstests + mind. 1 neuer
  kanalübergreifender Wächter-Test — **das Standard-LoC-Limit 250/Workflow ist real gefährdet**;
  `workflow.py set-field loc_limit_override 500` ist Voraussetzung für die Implementierungsphase,
  nicht optional.
- **Files:** ~17 Quelldateien (Liste unten) + ~30 Testdateien (§ Wächter-Tests) + 1 neues ADR.
- **Effort:** high — nicht wegen algorithmischer Komplexität (Risk-Level für die Logik selbst ist
  niedrig, s. AC-5), sondern wegen der Breite: sechs unabhängig formulierte Textstellen plus
  Alarm-SMS-Label plus Ortsvergleich-Vererbung, jede davon ein potenzieller Ort für eine
  übersehene Rücknahme.

### Betroffene Dateien

| File | Change Type | Beschreibung |
|------|-------------|--------------|
| `src/output/metric_format.py` | MODIFY | neue geteilte Funktionsfamilie für die Stufen*aussage* (nicht nur `THUNDER_LABEL_DE`, das Stufenwort selbst bleibt unverändert) |
| `src/app/thunder_scale.py` | MODIFY | `THUNDER_SIGNAL_LABEL_DE`/`thunder_signal_label()` — Herkunfts-Suffix bleibt Trägerin der Herkunftsabhängigkeit (AC-4) |
| `src/app/metric_catalog.py` | PRÜFEN | `MetricDefinition id="thunder"` — `label_de="Gewitter"` bleibt der Metrik-Name (Metrik heißt weiter „Gewitter", nur die LOW-Ausprägung nicht mehr); ggf. Anpassung nötig, wenn Katalogtext selbst „Gewitter" für alle Stufen ausgibt |
| `src/services/trip_report_scheduler.py` | MODIFY | Z. 209-218 (`_trend_note`, „Gewitter möglich" bei jeder Stufe außer kein), Z. 2831-2841 + 3070-3077 (zwei Bauwege, „Leichtes Gewitter möglich ab {hh}:00") |
| `src/output/renderers/trip_report.py` | MODIFY | Z. 572-629 (`⚡ möglich`/`Gewitter möglich`), Z. 758 (`_compute_highlights`, „⚡ Gewitter möglich ab...") |
| `src/output/renderers/email/helpers.py` | MODIFY | Z. 1780-1792 („Gewitter {stufe} ab {hh}:00 · stärkste...") |
| `src/output/renderers/email/thunder_branch.py` | MODIFY | Z. 168-214 (Zweigwähler 3-Tages-Vorschau, „⚡leicht@14"/„leicht @14") |
| `src/output/renderers/email/compare_html.py` | MODIFY | Z. 165-215, 252 — Ortsvergleich erbt dieselbe Formulierung mit |
| `src/output/renderers/day_window.py` | MODIFY | Z. 239-256 (Nacht-Zusatz, „, nachts leichtes Gewitter ab {hh}:00") |
| `src/output/renderers/compact_summary.py` | MODIFY | Z. 613-624 (identisch zu `trip_report.py:572-629`, gemeinsamer Telegram-Pfad) |
| `src/output/renderers/narrow.py` | MODIFY | Z. 255-258 (Telegram-Bubble-Fußzeile, „⚡ {wort}") |
| `src/output/renderers/sms_trip.py` | MODIFY | Z. 100 (`_SMS_RISK_LABELS[(THUNDERSTORM, LOW)] = "Gewitter leicht"`, Alarm-SMS — der einzige Ort, an dem SMS/Premium-SMS heute wörtlich „Gewitter" bei LOW ausgibt), Z. 321-323 (Token-Erzeugung `TH:L`, bleibt mechanisch bestehen) |
| `src/output/renderers/comparison.py` | MODIFY | Z. 75 |
| `src/output/renderers/alert/render.py` | MODIFY | Z. 49-58 (`_thunder_word()`) — liefert heute nur das Stufenwort, Aufrufer außerhalb dieser Datei binden „Gewitter" ggf. selbst hinzu, dort prüfen |
| `src/output/subject.py` | PRÜFEN | Z. 27, SMS-Betreff „Gewitter" — nicht stufenabhängig; prüfen ob LOW allein je den Betreff auslöst |
| `frontend/src/lib/utils/weatherUtils.ts` u. a. | PRÜFEN | Cockpit-/Compare-Konsumenten der Stufenwörter — Umfang beim Implementieren per `grep` verifizieren |
| ~30 Testdateien (§ Wächter-Tests) | MODIFY | Wortlaut-Anpassung an ~30 Stellen, plus mind. 1 neue Testdatei für den kanalübergreifenden Wächter |
| ADR (neu, Arbeitsnummer ADR-0064) | CREATE | löst den betroffenen Satz aus ADR-0048 ab, dokumentiert die Neubeantwortung von Grundsatzfrage 1 aus Epic #1419 |

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| Epic #1419 Abschnitt 9 (PO 2026-07-29) | Produktentscheidung, durch PO 2026-09-08 revidiert | vier nutzersichtbare Gewitterstufen (`keine/möglich/wahrscheinlich/akut`) beginnen künftig bei `MED` statt `LOW` |
| ADR-0048 (`docs/adr/0048-modellabhaengige-schwellen-statt-einer-zahl.md`) | wird im betroffenen Punkt abgelöst durch neues ADR | Satz „CAPE misst Energie, kein Ereignis, und eskaliert nie über LOW" ist bereits durch #1679 (CAPE-Leiter) fachlich überholt und wird durch diese Spec (LOW verlässt die Gewitterleiter komplett) zusätzlich hinfällig |
| `feat_1679_cin_paarung_cape_leiter.md` | Vorarbeit, unverändert gültig | hat den CAPE-Deckel bei LOW bereits fachlich aufgehoben, ohne ADR-0048 nachzuziehen — diese Spec schließt die ADR-Lücke |
| `feat_1474_gewitter_befund_stufen.md` AC-6, AC-11 | wird revidiert | AC-6 (CAPE-Deckel) bereits durch #1679 überholt; AC-11 „jeder Kanal zeigt ein erkennbares 'leicht'" bleibt für das Stufen*wort* gültig, nicht mehr für eine Gewitter-*Ereignis*aussage |
| `fix_2010_2011_gewitter_stufenwoerter.md` | wird revidiert | Telegram zeigt weiterhin `kein/leicht/mittel/hoch` als Wort — die Deutung um „leicht" ändert sich, das Wort selbst nicht |
| `fix_1491_gewitter_ampelkreis.md` AC-7 | offene Design-Detailfrage | bindet Wort UND Hex `#fbeeb8` für LOW — ob die Ampelfarbe für LOW neutral wird, ist NICHT Teil der PO-Entscheidung dieser Spec (s. Known Limitations) |
| `fix_1488_sb_gewitter_mailwort.md` AC-4 | wird revidiert | Bestandsschutz „`thunder_word` liefert bei LOW exakt 'leicht'" — das Stufenwort bleibt (`THUNDER_LABEL_DE` unverändert), nur die umgebende Satzform mit „Gewitter" entfällt |
| `fix_1948_s6_alarm_stufenwort.md` AC-6, AC-7 | zu prüfen, zwei Rollen bleiben getrennt | „leicht" als Alarm-Abstandseinheit vs. als Stufenwort — durch diese Spec nicht direkt berührt, da nur die LOW-*Ereignis*aussage geändert wird |
| `fix_1474b_gewitterschwelle_cockpit.md` | wird revidiert (Frontend) | Cockpit zeigt „leicht" als Gelb, Standardschwelle „ab leicht" |
| `thunder_threshold_katalog.md` | wird revidiert (Beschriftung) | drei wählbare Alarmschwellen `leicht/mittel/hoch` — Alarm-Logik selbst bleibt unverändert (AC-5), nur die Bezeichnung ggf. zu prüfen |
| `fix_1592_s1_cape_modellschwelle.md`, `fix_1592_c2_cape_riskengine.md` | gemeinsam mit ADR-0048 zu revidieren | Deckelungs-Kette „bleibt bei leicht" |
| `fix_1760_cin_vorzeichen.md` | zu prüfen, nicht revidiert | CIN-Dämpfungsbänder nennen „leicht" als Rechenziel des Enum-Werts — bleibt korrekt, weil das Stufenwort unverändert bleibt |
| `feat_1493_gewitter_onset_sichtbar.md` | wird revidiert | Tests binden `endswith("⚡leicht")` |
| `fix_2012_gewitter_stufen_migration.md` | Begründung verliert Bezug, Verhalten unverändert | Alt-3-Stufen-Migration bewusst nicht auf LOW abgebildet |
| `thunder_scale_guard.md` | unverändert | AST-Wächter auf Enum-Namen, wortlautunabhängig — `ThunderLevel.LOW` als Enum-Mitglied bleibt bestehen |
| Issue #2178 | explizit AUSSER Scope | CAPE-Leiter für MED/HIGH — deckt die übrigen 10 von 13 gemessenen Etappentagen ab, s. Known Limitations |
| `src/output/metric_format.py::THUNDER_LABEL_DE`/`thunder_ampel_band()` | wiederverwendete Infrastruktur, unverändert im Kern | Stufenwort und Ampelband bleiben Quelle — diese Spec fügt eine NEUE Quelle für die Aussage hinzu, ersetzt keine bestehende |

## Implementation Details

### 1. Neue geteilte Funktionsfamilie für die Stufen*aussage* (nicht nur das Stufenwort)

`THUNDER_LABEL_DE` liefert bereits das Wort („leicht"). Was fehlt, ist eine geteilte Quelle für
den **fertigen Aussagesatz** bei LOW — heute baut jede der sechs+ Formulierungsstellen ihn selbst
(„Gewitter " + Wort, „⚡ Gewitter möglich ab...", etc.). Analog zum bestehenden Muster in
`email/thunder_branch.py` (vier kanaleigene Formatierer `thunder_cell_html/plain/compact/
telegram`, EIN gemeinsamer Zweigwähler) liefert die neue Funktion **fertige Satzfragmente**,
nicht nur Bausteine, die jeder Aufrufer erneut zusammensetzen müsste — sonst bliebe genau die
Sechsfach-Duplizierung bestehen, die diese Spec beheben soll:

```python
def thunder_low_statement(
    form: str, carriers: Optional[Iterable[str]], cape_jkg: Optional[float] = None,
) -> str:
    """Fertige LOW-Aussage OHNE Gewitterwort, herkunftsabhaengig (#2176).
    form="lang" (E-Mail-/Telegram-Fliesstext) traegt den CAPE-Wert, wenn
    bekannt (AC-2). form="kurz" (Kompakt/Fusszeile) traegt ihn NICHT."""
    if _thunder_low_is_pure_cape(carriers):
        kern = "instabile Luftmasse"
    else:
        kern = "schwaches Signal"
    if form == "lang" and cape_jkg is not None:
        kern += f" (CAPE {cape_jkg:.0f} J/kg)"
    return kern


def _thunder_low_is_pure_cape(carriers: Optional[Iterable[str]]) -> bool:
    """True NUR wenn carriers eine NICHT-LEERE Menge ist und ausschliesslich
    'cape' enthaelt. `None` UND `[]` gelten BEIDE als unbekannte/fehlende
    Herkunft -- KEINE reine Luftmasse (Analogie ADR-0048 Regel 5: unbekannte
    Herkunft ist keine Aussage, nicht 'unauffaellig')."""
    if not carriers:
        return False
    return set(carriers) <= {"cape"}
```

Das exakte deutsche Wortmaterial ("instabile Luftmasse"/"schwaches Signal") ist ein Vorschlag,
kein Bestandteil der Freigabe — bindend sind die ACs (kein „Gewitter"-Wort, CAPE sichtbar,
herkunftsabhängig korrekt), nicht dieser Wortlaut selbst. Das bestehende Stufenwort
(„leicht" aus `THUNDER_LABEL_DE`) bleibt UNVERÄNDERT und wird an Stellen, die kanaltypisch
knapp bleiben müssen (Telegram-Fußzeile, Kompakt-Ausblick), weiterhin allein verwendet — nur
ohne das umgebende „Gewitter"-Wort.

### 2. CAPE-Wert-Sichtbarkeit bei LOW

Die bestehende Highlight-Schwelle (`trip_report.py:841`, „Hohe Gewitterenergie: CAPE {wert}
J/kg") liegt bei 1 000 J/kg, der Ø-CAPE-Wert bei „leicht" bei 587 J/kg — AC-2 ist damit heute
NICHT erfüllt. Verbindlich: der CAPE-Zahlenwert wird direkt in die neue LOW-Aussage eingebettet
(`thunder_low_statement(form="lang", ...)`), NICHT über die bereits vorher bestehende separate
CAPE-Spalte der Stundentabelle (`email/helpers.py:835-841`) gelöst — diese Spalte existierte
schon vor dieser Spec und schließt die von der Analyse benannte Lücke gerade NICHT (s. AC-2).
Die bestehende 1 000-J/kg-Schwelle bedient einen anderen Zweck (Highlight bei SEHR hoher
Energie) und bleibt unverändert bestehen.

### 3. Sechs+ Formulierungsstellen — Umstellung auf die neue Quelle

Jede Zeile aus der Tabelle „Betroffene Dateien" ruft künftig `thunder_low_statement()` (statt
eigener `"Gewitter"`-Strings) auf. Die Herkunfts-Anzeige (`THUNDER_SIGNAL_LABEL_DE`/
`thunder_signal_label()`, bereits vorhanden, bisher nur E-Mail) bleibt unverändert die Trägerin
der zusätzlichen Herkunftsdetails (AC-4) — sie muss NICHT neu gebaut werden, nur weiterhin
angehängt werden, wo ein Kanal Herkunft überhaupt zeigt.

### 4. SMS-/Premium-SMS-Token

`TH:L@14` bleibt mechanisch bestehen (Byte-Budget, `test_sms_fidelity_preview.py:424` bindet die
Baseline) — der Buchstabe `L` ändert nicht seine Kodierung, sondern nur seine **Bedeutung**: er
zeigt weiterhin die Stufe „leicht" an, aber die Legende/Erklärung des Tokens (wo immer sie dem
Nutzer erklärt wird) darf ihn nicht mehr als Gewitterankündigung beschreiben.
`_SMS_RISK_LABELS[(RiskType.THUNDERSTORM, RiskLevel.LOW)]` (`sms_trip.py:100`, heute
`"Gewitter leicht"`, genutzt in der Alarm-SMS) muss auf einen Text ohne „Gewitter" geändert
werden — das ist der EINZIGE Ort, an dem SMS/Premium-SMS heute wörtlich „Gewitter" bei LOW
ausgibt (der Token-Pfad selbst spricht das Wort nie aus, s. AC-3).

### 5. Ortsvergleich erbt mit

`compare_html.py`/`comparison.py` lesen dieselben geteilten Quellen (`THUNDER_LABEL_DE`,
`thunder_ampel_band()`, `thunder_low_statement()`) — das ist keine eigenständige
Ortsvergleich-Arbeit im Sinne der PO-Zurückstellungsregel, sondern eine unvermeidliche Folge der
geteilten Quelle (Pendant-Prinzip). Die Compare-Mail muss trotzdem mit validiert werden.

### 6. ADR

Ein neues ADR (Arbeitsnummer **ADR-0064**, endgültige Nummer beim Anlegen gegen den dann
aktuellen Stand von `docs/adr/` prüfen) löst den Satz „CAPE eskaliert nie über LOW" aus
ADR-0048 im betroffenen Punkt ab (`Status: Abgelöst durch ADR-0064` an der entsprechenden
Stelle in ADR-0048 ergänzen, ADR-0048 selbst bleibt für die übrigen Regeln — modellabhängige
Schwellentabelle — unverändert „Akzeptiert") und dokumentiert die Neubeantwortung von
Grundsatzfrage 1 aus Epic #1419: `ThunderLevel.LOW` ist ab dieser Scheibe kein Mitglied der
vier-stufigen, nutzersichtbaren Gewitterleiter mehr.

## Expected Behavior

- **Input:** ein `ThunderLevel`-Wert je Datenpunkt/Stunde, optional die Trägerliste
  (`thunder_signal_carriers()`, Werte aus `{"wettercode","blitzdichte","cape",
  "blitzpotenzial"}`), der zugrundeliegende `cape_jkg`-Rohwert.
- **Output:** bei `ThunderLevel.LOW` erscheint in keinem der vier Kanäle mehr eine
  Ereignisbehauptung („Gewitter", ⚡ als Ereignis-Symbol); der CAPE-Wert steht direkt an der
  LOW-Aussage (E-Mail, Telegram); bei `MED`/`HIGH` bleibt die bestehende Gewitterformulierung
  unverändert.
- **Side effects:** keine — reine Darstellungsänderung, kein Eingriff in Alarm-Logik
  (`ORDINAL_LEVEL_BOUNDS`/`_ordinal_change_triggers` bleiben unverändert, s. AC-5), kein
  zusätzlicher Datenabruf.

## Acceptance Criteria

- **AC-1 (Kein Gewitterwort bei LOW, alle vier Kanäle — ⚡ als Ereignissymbol vs. als
  Metrik-Kennzeichner getrennt):** Given eine Etappenstunde mit `ThunderLevel.LOW` ohne weiteres
  eskalierendes Signal / When das Trip-Briefing für alle vier Kanäle gerendert wird (E-Mail
  HTML+Klartext+Kompakt, Telegram, SMS, Premium-SMS) / Then enthält keiner der Ausgabetexte für
  DIESE Stunde das Wort „Gewitter" als Ereignisbehauptung, UND das ⚡-Symbol steht nicht
  unmittelbar vor dem Stufenwort/-token dieser LOW-Stunde (Telegram-Fußzeile,
  Klartext-Highlight, Ausblick-Zelle). Als reiner, levelunabhängiger Spalten-/Metrik-
  Kennzeichner (Tabellenkopf, `compact_label` des Katalogeintrags `id="thunder"`) bleibt ⚡
  zulässig — er benennt dort die Metrik, nicht ein Ereignis dieser Stunde.
  - Test: EIN Testlauf rendert alle vier Kanäle aus derselben Fixture-Datenreihe
    (`ThunderLevel.LOW`, `carriers=["cape"]`) und sucht in jedem Kanalergebnis sowohl nach
    „Gewitter" als auch nach „⚡" unmittelbar vor dem Stufenwort/-token dieser Stunde.
  - Gegenprobe: Würde nur EINE der sechs+ Formulierungsstellen (§ Implementation Details Punkt 3)
    übersehen, bliebe dort „Gewitter" stehen — ein Testlauf, der alle Kanäle aus derselben
    Fixture zieht statt getrennter Einzeltests je Kanal, muss das fangen (sonst prüft ein
    grüner Einzeltest je Kanal nicht zwingend dieselbe übersehene Stelle).

- **AC-2 (CAPE-Wert steht AN der LOW-Aussage, nicht nur potentiell in einer Nebenspalte):**
  Given eine Stunde mit `ThunderLevel.LOW` und `cape_jkg=587` (Ø-Messwert, unterhalb der
  bestehenden 1 000-J/kg-Highlight-Schwelle) / When die LOW-Aussage in E-Mail (Highlight-Zeile
  bzw. Ausblick-Tagesfenster) oder Telegram-Fließtext gerendert wird / Then trägt GENAU dieser
  Ausgabetext den CAPE-Zahlenwert (oder eine gerundete, nachvollziehbare Ableitung) — nicht nur
  potentiell erreichbar über die bereits vorher bestehende separate CAPE-Spalte der
  Stundentabelle (`email/helpers.py:835-841`), die laut Analyse die Lücke NICHT schließt. Für
  SMS/Premium-SMS gilt die Ausnahme: aus Platzgründen (160-Zeichen-Budget, analog zur fehlenden
  Herkunftsangabe in AC-4) muss der CAPE-Wert dort NICHT in der Kurzform erscheinen.
  - Test: rendert die LOW-Highlight-Zeile bzw. das Ausblick-Tagesfenster direkt (NICHT die
    Stundentabellen-Spalte) mit `cape_jkg=587`, prüft dass „587" (oder die gerundete Form)
    literal in genau diesem String erscheint.
  - Gegenprobe: Verließe sich die Implementierung ausschließlich auf die schon vorher
    bestehende Stundentabellen-Spalte, bliebe der Wert in der LOW-Aussage SELBST unsichtbar —
    exakt die von der Analyse benannte Lücke; ein Test, der die Spalte statt der Aussage prüft,
    würde das NICHT fangen. Der Test muss deshalb den Aussage-String selbst treffen.

- **AC-3 (Kanalübergreifender Wächter-Test, PFLICHT laut Issue — bindet je Kanal das
  tatsächlich regressionsfähige Artefakt):** Given eine künftige Code-Änderung, die
  versehentlich wieder eine Gewitterformulierung einführt / When der neue Wächter-Test läuft /
  Then schlägt er fehl, weil er PRO KANAL genau das Artefakt prüft, das heute (vor dieser Spec)
  „Gewitter" tatsächlich enthält:
  - **E-Mail:** die sechs Formulierungsstellen aus § Implementation Details Punkt 3.
  - **Telegram:** `narrow.py:255-258` (Bubble-Fußzeile) UND die geteilte Zeile aus
    `compact_summary.py:613-624`/`trip_report.py:572-629`.
  - **SMS:** `_SMS_RISK_LABELS[(RiskType.THUNDERSTORM, RiskLevel.LOW)]`
    (`sms_trip.py:100`, Alarm-SMS) — NICHT der Token-Pfad (`TH:L`), der heute schon nie wörtlich
    „Gewitter" enthält und dessen Prüfung deshalb wirkungslos wäre.
  - **Premium-SMS:** teilt sich `sms_trip.py` vollständig mit SMS (kein eigener Renderer,
    `channels/premium_sms.py` Docstring) — die SMS-Prüfung deckt Premium-SMS mit ab; ein
    separater vierter Test-Arm auf denselben Text ist redundant, nicht zusätzlich beweiskräftig.
  - Test: ein Testmodul mit vier gezielten Assertions (eine je oben benanntem Artefakt, nicht
    vier identischen Volltextsuchen), zusätzlich eine Mutations-Gegenprobe (String-Ersetzung mit
    externer Sicherungskopie, nicht `git checkout`/`stash`/`reset`) an mindestens einer der sechs
    E-Mail-Stellen, die belegt, dass der Test die Rücknahme tatsächlich fängt.
  - Gegenprobe: Ein Test, der bei SMS/Premium-SMS nur den `TH:L`-Token auf „Gewitter" durchsucht,
    wäre am eigenen Encoder vorbeigeprüft (der Token spricht das Wort nie aus) und bestünde auch
    dann, wenn die Alarm-SMS-Legende rückfällig würde — genau der Fehler, den diese AC-Fassung
    durch die Bindung an das RICHTIGE Artefakt verhindert.

- **AC-4 (Herkunftsabhängigkeit — keine pauschal falsche „nur Luftmasse"-Behauptung):** Given
  `ThunderLevel.LOW` entsteht NICHT ausschließlich aus CAPE, sondern (auch) aus Wettercode,
  Blitzdichte oder Blitzpotenzial (`carriers` enthält mehr als nur `"cape"`) / When die
  LOW-Aussage in einem Kanal mit Herkunfts-Anzeige (E-Mail) gerendert wird / Then behauptet der
  Text nicht pauschal eine reine Luftmasse, sondern zeigt (wie heute schon über
  `THUNDER_SIGNAL_LABEL_DE`) den tatsächlichen Signal-Träger.
  - Test: zwei Fixtures — `carriers=["cape"]` (reine Luftmasse) vs. `carriers=["cape",
    "blitzdichte"]` (gemischt) — die E-Mail-Ausgabe unterscheidet sich in der
    Herkunftsangabe zwischen beiden Fällen. Für SMS/Premium-SMS (die heute schon keine
    Herkunft ausgeben) genügt die kanaltypische Kurzform ohne Herkunftsangabe, wie bisher.
  - Gegenprobe: Würde die neue Aussage carrier-unabhängig immer identisch formuliert, wäre sie
    im gemischten Fall sachlich falsch (§2 der Analyse: LOW kann strukturell aus reiner
    Blitzdichte ohne jeden CAPE-Beitrag entstehen) — der Test muss den Unterschied zwischen
    beiden Fixtures fangen.

- **AC-5 (Alarm-Presets bleiben unverändert funktionsfähig):** Given die drei Presets
  `entspannt`/`standard`/`sensibel` und ein Übergang `kein→leicht` bzw. `leicht→kein` / When die
  Alarm-Auswertung (`_ordinal_change_triggers`, `ORDINAL_LEVEL_BOUNDS`) läuft / Then löst KEINES
  der drei Presets einen Sofortalarm für diesen Übergang aus — identisch zum Verhalten vor
  dieser Änderung.
  - Test: bestehender Regressionstest auf `ORDINAL_LEVEL_BOUNDS`/`_ordinal_change_triggers`
    läuft nach dieser Änderung unverändert grün, ergänzt um einen expliziten LOW-Fall.
  - Gegenprobe: Griffe die Darstellungsänderung versehentlich in `alert_preset.py`/
    `weather_change_detection.py` ein (z. B. würde `ThunderLevel.LOW` als Enum-Mitglied entfernt
    statt nur umformuliert), entstünde entweder ein `TypeError` oder ein geändertes
    Alarmverhalten — der Test muss das fangen.

- **AC-6 (MED/HIGH bleiben unverändert Gewitteransagen — Regressionsanker gegen
  Überkorrektur):** Given eine Stunde mit `ThunderLevel.MED` oder `ThunderLevel.HIGH` / When
  alle vier Kanäle rendern / Then bleibt die bestehende Gewitterformulierung („Gewitter
  möglich"/„Gewitter {stufe}"/`TH:M`/`TH:H`) für diese Stufen unverändert erhalten — diese Spec
  ändert ausschließlich `LOW`.
  - Test: identischer Renderlauf wie AC-1, aber mit MED- und HIGH-Fixtures, prüft dass
    „Gewitter" für diese Stufen weiterhin erscheint.
  - Gegenprobe: Würde die neue geteilte Quelle versehentlich pauschal für ALLE Stufen die
    neutrale Aussage liefern statt nur für LOW, verschwände die Gewitteransage auch bei
    MED/HIGH — das würde eine reale Warnung verschlucken. Der Test muss das fangen.

## Known Limitations

- **Wirkungsgrenze auf die Tages-Schlagzeile:** Die Tages-Höchststufe (`max(...,
  key=thunder_ordinal)`, `trip_report_scheduler.py:3061-3077`) entscheidet die
  Tages-Schlagzeile. Von den gemessenen 13 Etappentagen an KHW 403 hatten 9 die Höchststufe
  `hoch` und 1 `mittel` — dort bleibt die Tages-Schlagzeile trotz dieser Scheibe eine
  Gewitteransage, weil an diesen Tagen tatsächlich MED/HIGH vorlag. Nur **3 von 13 Tagen**
  (Höchststufe `leicht`) verlieren die Gewitter-Schlagzeile durch diese Spec. Das ist beabsichtigt
  (PO-Entscheid 2026-09-08), nicht ein Mangel dieser Scheibe — die übrigen 10 Tage adressiert
  #2178 (CAPE-Leiter MED/HIGH), explizit außerhalb dieses Scopes. In Stundentabellen und
  3-Tages-Ausblick wirkt #2176 dagegen stark: 26 % aller Messungen im Trip standen auf „leicht"
  und trugen dort bisher ⚡ plus Gewitterformulierung, auch an Tagen mit Höchststufe „hoch".
- **Ampelfarbe für LOW ist NICHT Teil dieser Entscheidung.** `thunder_ampel_band(LOW)` liefert
  heute „yellow" (`fix_1491_gewitter_ampelkreis.md` AC-7). Ob Gelb bei einer reinen
  Luftmassen-Aussage weiterhin sichtbar bleibt oder neutral wird, hat der PO nur als
  Grundsatzfrage (Wortlaut) entschieden, nicht als Detailfrage der Ampel-Codierung — beim
  Implementieren offenlassen bzw. unverändert lassen, sofern keine gesonderte PO-Antwort vorliegt.
- **Exakter deutscher Wortlaut ist neu.** Es gibt im Repo keinen Präzedenzfall für eine
  „Luftmasse"-Formulierung (etabliert ist bisher „Gewitterenergie" für CAPE selbst). Die ACs
  dieser Spec binden das VERHALTEN (kein „Gewitter"-Wort, CAPE sichtbar, herkunftsabhängig
  korrekt), nicht einen einzelnen literalen Satz — die finale Textform aus Implementation
  Details Punkt 1 ist ein Vorschlag und wird beim Implementieren gegen diese ACs geprüft.
- **MED/HIGH bleiben bei der heutigen Formulierung** („Gewitter möglich"/„Gewitter {stufe}"),
  nicht beim Zielvokabular `möglich/wahrscheinlich/akut` aus Epic #1419 — diese Umbenennung ist
  nicht Teil dieser Scheibe (s. AC-6), sondern folgt mit #2178 oder einer eigenen Scheibe.
  Grundsatzfrage 1 ist mit dieser Spec insofern nur teilweise umgesetzt: die STARTGRENZE der
  Leiter ändert sich (`LOW` raus), die BEZEICHNUNG von MED/HIGH ändert sich noch nicht.
  Nach dieser Spec beschreibt „Gewitter möglich" also weiterhin `MED` (bisher `LOW`+`MED`).
- **Frontend-Umfang unklar bis zur Implementierung.** `weatherUtils.ts` u. a. sind Kandidaten
  (§ Dependencies), der tatsächliche Umfang wird erst mit `grep` auf die betroffenen Konstanten
  am Implementierungsstand verifiziert.
- **CIN-Deckel bleibt unverändert bestehen.** Der CIN-Deckel (`metric_format.py:377-432`) ist
  weiterhin ein Auffangwert für unbekannte Konvektionshemmung, der LOW erzeugen kann, ohne dass
  „echte" Instabilität vorliegt. Diese Spec ändert nur die Darstellung von LOW, nicht sein
  Zustandekommen — das bleibt Gegenstand von #1679/#2178, nicht dieser Scheibe.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** neu, Arbeitsnummer **ADR-0064** (endgültige Nummer beim Anlegen gegen den dann
  aktuellen Stand von `docs/adr/` prüfen) — löst `docs/adr/0048-modellabhaengige-schwellen-statt-einer-zahl.md`
  im betroffenen Punkt ab.
- **Rationale:** ADR-0048 behauptet weiterhin unverändert („Status: Akzeptiert"): „CAPE misst
  Energie, kein Ereignis, und eskaliert nie über LOW." Diese Aussage ist bereits durch #1679
  (CAPE-Leiter, `feat_1679_cin_paarung_cape_leiter.md`) im Code widerlegt, ohne dass ADR-0048
  dafür abgelöst wurde. Diese Spec macht die Formulierung zusätzlich grundsätzlich hinfällig:
  `ThunderLevel.LOW` verlässt die vier-stufige, nutzersichtbare Gewitterleiter komplett
  (Neubeantwortung von Grundsatzfrage 1, Epic #1419 Abschnitt 9, PO 2026-09-08). Das neue ADR
  dokumentiert diese Entscheidung, markiert den betroffenen Satz in ADR-0048 als abgelöst und
  lässt die übrigen Regeln in ADR-0048 (modellabhängige Schwellentabelle, kein stiller
  Rückfall) unverändert in Kraft.

## Changelog

- 2026-09-08: Initial spec created (Issue #2176, Epic #1419), auf Basis der vollständigen
  Analyse `docs/context/feat-2176-luftmasse-statt-gewitteransage.md`.
