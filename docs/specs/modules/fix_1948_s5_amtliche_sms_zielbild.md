---
entity_id: fix_1948_s5_amtliche_sms_zielbild
type: feature
created: 2026-08-20
updated: 2026-08-20
status: draft
version: "1.0"
tags: [alarm, sms, official-alert, format]
---

# Amtliche Warn-SMS-Zielbild (Zweig b) — #1948 Scheibe S5

## Approval

- [ ] Approved

## Purpose

Die eigenständige amtliche Warn-SMS trägt heute ein Sonderformat, das nur
dieser eine Renderer spricht: `KHW403 AMT GELB1/3: TH Do12-22, ges.Route`
(gemessene Ist-Basislinie, Fall 1). Sie zieht auf dieselbe Grammatik um, die
Trip-Briefing-SMS und (seit S4) der Nowcast-Alarm bereits sprechen —
Ortskopf, Gefahren-Kürzel mit Stufenbuchstabe, Zeitfenster:

| | |
|---|---|
| heute | `KHW403 AMT GELB1/3: TH Do12-22, ges.Route` |
| nach S5 | `Seg 4: !TH:L 12-22` |
| zweite Warnung dazu | `Seg 4: !TH:L 12-22 HT:L` |
| Ziel-Segment, orange | `Ziel: !TH:M 15-21` |

(PO-Zielbild-Tabelle 2026-08-20, nicht verhandelbar.) Der Trip-/Preset-Name
(`sms_prefix`, „KHW403") und das Sonderformat `AMT {WORT}{Pos}/3` verschwinden
ersatzlos — das amtliche Format folgt künftig dem **Phänomen**, nicht mehr der
Quelle (Konzept-Leitsatz, `docs/analysis/alarm-format-konzept-2026-08.md`
Abschnitt 1).

## Source

- **File:** `src/output/renderers/alert/official_alerts.py`
- **Identifier:** `render_official_alert_sms()` (Z. 2038-2124)

Begleitend: `build_official_alert_notices()`/`build_compare_official_alert_notices()`
(Z. 2139-2198/2201-2257, „Seg"-Abkürzung statt „S"), `src/output/renderers/alert/render.py`
(`_ascii_alert_location()`, Z. 1014-1018, dieselbe Abkürzung für Nowcast/Onset/Trip-Δ-SMS),
`src/services/notification_service.py` (6 Aufrufer verlieren `sms_prefix`),
`src/services/validator_render_service.py` (1 Aufrufer + Vorbedingungs-Durchreichung),
`api/routers/validator.py` (Segment-Feld an zwei DTOs nachgezogen).

## Estimated Scope

- **LoC:** ~120–160 (Renderer-Kernumbau + Abkürzungs-Helfer + sechs
  Aufrufer-Signaturen + DTO-Ergänzung, unter dem 250-LoC-Workflow-Limit)
- **Files:** 5 Produktivdateien (`official_alerts.py`, `render.py`,
  `notification_service.py`, `validator_render_service.py`,
  `api/routers/validator.py`) + 1 Snapshot-Fixture bewusst neu erzeugt +
  8–10 Bestandstestdateien fortgeschrieben
- **Effort:** high (Risk Level HIGH — nutzersichtbarer Alarmpfad, alle vier
  Kanäle des amtlichen Zweigs, Snapshot-Fixture, geteilte SMS-Ortssprache)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `OfficialAlertNotice` | dataclass (`official_alerts.py:137-177`) | trägt `alert`, `sms_scope`, `scope_label`, `scope_ids` — Quelle des Ortskopfs und der Pro-Token-Ortszusätze |
| `_sort_notices()` | function (`official_alerts.py:828-834`) | Sortierreihenfolge (Stufe absteigend) — unverändert, wird unangetastet weiterverwendet |
| `_uniform_scope()` | function (`official_alerts.py:1313-1332`) | entscheidet „ein gemeinsamer Kopf" vs. „jeder Token trägt seinen eigenen Ortszusatz" — unangetastet, trägt jetzt die GESAMTE Verzweigung (die alte Stufe-Verzweigung entfällt, s. Implementation Details) |
| `_tag_time()` / `_tag_hour()` | function (`official_alerts.py:1896-1937`) | Zeitfenster-Formatierung — änderbar; braucht die neue „Wochentag nur wenn nicht heute"-Regel (PO-Entscheid 3) |
| `_sms_pack()` / `_sms_leading_variants()` / `_sms_pack_with_fallback()` | function (`official_alerts.py:1940-2035`) | Zeichenbudget-Kette — änderbar; Token-Joiner wechselt von `" + "` auf `" "` (Zielbild zeigt kein `+` mehr zwischen Tokens) |
| `hazard_symbols.LEVEL_LETTERS` | dict (`hazard_symbols.py:34`) | Dringlichkeits-Tabelle (nur L/M/H) — **TABU**, s. Randbedingung 1 |
| `hazard_symbols.LEVELLESS_HAZARDS` | frozenset (`hazard_symbols.py:70`) | genau `{"access_ban"}` — steuert den stufenlosen `CL`-Token |
| `hazard_symbols.sms_symbol_for()` | function (`hazard_symbols.py:40-65`) | einziger Kürzel-Katalog, inkl. Fallback für unbekannte Gefahrenarten |
| `format_segment_reference()` / `format_alert_location()` | function (`segments.py:32-74`, `:91-111`) | gemeinsame Ortssprache aller Alarmarten — Quelle von `"Segment N"`/`"🏁 Ziel"`/km-Rückfall, auf der die neue `"Seg N"`-Abkürzung aufsetzt |
| `_ascii_alert_location()` | function (`render.py:1014-1018`) | einziger Konsument über alle SMS-only-Kopfstellen (Onset-, Trip-Δ-, Onset-Shift-SMS) — Ort der geteilten `"Seg"`-Abkürzung, damit sie nicht zweimal implementiert wird |
| `alert_urgency.urgency_from_official_level()` | function (`src/services/alert_urgency.py:24-29`) | Dringlichkeits-Ableitung aus `LEVEL_LETTERS`; stürzt mit `KeyError` ab, würde `LEVEL_LETTERS[1]` ergänzt (Randbedingung 1) |
| `build_official_alert_notices()` / `build_compare_official_alert_notices()` | function (`official_alerts.py:2139-2198`, `:2201-2257`) | bauen `sms_scope` — hier ändert sich die eine Zeile `.replace("Segment ", "S")` → `.replace("Segment ", "Seg ")` |
| `OnsetPayload` / `OfficialAlertPayload` / `NowcastFramesPayload` | Pydantic-DTO (`api/routers/validator.py:226-234`, `:237-250`, `:259-264`) | Vorbedingung aus S4 (`issuecomment-5351380856`): `OnsetPayload`/`NowcastFramesPayload` fehlt das Segment-Feld, das `OfficialAlertPayload` längst trägt |
| `notification_service` Aufrufer | (`src/services/notification_service.py:910,931,950,1206,1241,1264`) | sechs Aufrufer (Trip Telegram-Kurzstil/SMS/Premium-SMS, Compare dito) verlieren das `sms_prefix`-Argument |
| `validator_render_service._render_official_preview` | (`src/services/validator_render_service.py:210`) | Preview-Pfad, verliert ebenfalls `sms_prefix` (heilt zugleich den Nebenbefund: hier fehlte bislang `.replace(" ", "")`) |

## Implementation Details

**Ein Bau-Pfad statt zwei** (Technischer Ansatz der Analyse-Phase): Der
heutige Renderer verzweigt in „einheitliche Stufe" (gemeinsamer
`AMT {WORT}{Pos}/3`-Kopf) und „gemischte Stufen" (Stufenwort je Token). Im
Zielformat trägt **jedes** Token seinen Stufenbuchstaben selbst (`TH:L`) — die
Stufen-Verzweigung verliert ihren Zweck für die Token-Darstellung und
entfällt. Übrig bleibt **eine** Verzweigung, die bereits existiert:
`_uniform_scope()` entscheidet, ob alle Warnungen denselben betroffenen
Umfang haben. Ist das so, trägt die Nachricht **einen** gemeinsamen Ortskopf
(„Seg 4: ", „Ziel: "); sonst entfällt der Kopf, und jedes Token trägt seinen
eigenen Ortszusatz (unverändertes Bestandsverhalten aus dem heutigen
Mixed-Scope-Zweig, nur mit der neuen Token-Grammatik). Der bisherige
`suffix`-Mechanismus (Ort am Satzende, `", ges.Route"`) wird dadurch
überflüssig — die Ortsfunktion wandert vollständig in den Kopf.

**GRÜN→`-` als eigene, additive Darstellungstabelle** (Randbedingung 1,
gemessen): `hazard_symbols.LEVEL_LETTERS` bleibt exakt `{2: "L", 3: "M", 4: "H"}`
— eine Ergänzung um `1: "-"` lässt `alert_urgency.urgency_from_official_level(1)`
mit `KeyError: '-'` abstürzen, weil `_LETTER_TO_URGENCY` (`alert_urgency.py:20`)
nur `L`/`M`/`H` kennt. Die vierstufige SMS-Darstellungsleiter lebt deshalb als
eigene, lokale Konstante ausschließlich im SMS-Renderer, gekapselt in einem
kleinen Token-Helfer (`hazard_symbols.LEVEL_LETTERS` bleibt dabei unberührt):

```python
_SMS_LEVEL_LETTERS: dict[int, str] = {1: "-", 2: "L", 3: "M", 4: "H"}


def _sms_hazard_token(alert: "OfficialAlert", time_part: str) -> str:
    """`{Kuerzel}:{Stufe}[ {Zeit}]`; `access_ban` bleibt blank (LEVELLESS_HAZARDS)."""
    symbol = sms_symbol_for(alert.hazard)
    if alert.hazard in LEVELLESS_HAZARDS:
        return symbol
    letter = _SMS_LEVEL_LETTERS.get(alert.level, "H")
    token = f"{symbol}:{letter}"
    return f"{token} {time_part}" if time_part else token
```

Der Renderer-Rumpf selbst baut auf `_sms_hazard_token`, `_uniform_scope` und
der bestehenden Rückfallkette (`_sms_leading_variants`/`_sms_pack_with_fallback`,
unverändert wiederverwendet) auf:

```python
def render_official_alert_sms(
    notices: list["OfficialAlertNotice"], *, limit: int = 140,
    tz: "ZoneInfo | None" = None,
) -> str:
    """Ortskopf einmal bei `_uniform_scope`, sonst Ortszusatz je Token.
    `sms_prefix` ist ersatzlos entfallen."""
    from .render import _ascii

    ordered = _sort_notices(notices)
    uniform_scope = _uniform_scope(ordered)
    leading = ordered[0]

    tokens = [
        _sms_hazard_token(n.alert, _tag_time(n.alert, tz))
        + ("" if uniform_scope else f" {n.sms_scope}")
        for n in ordered
    ]
    head = _ascii(f"{leading.sms_scope}: " if uniform_scope else "")
    tokens = [_ascii(t) for t in tokens]

    leading_time = "" if leading.alert.hazard in LEVELLESS_HAZARDS else _tag_time(leading.alert, tz)
    leading_variants = [
        f"!{v}" for v in _sms_leading_variants(
            _sms_hazard_token(leading.alert, ""), leading_time,
            "" if uniform_scope else leading.sms_scope,
        )
    ]
    return _sms_pack_with_fallback(head, leading_variants, tokens[1:], limit, "")
```

Begründung der Bausteinwahl:

- **`sort_notices`/`_uniform_scope` unangetastet** — beide sind laut
  Risikoanalyse Bausteine, die auch Betreff/Headline/Quelle-Box mitspeisen
  (`_uniform_scope` docstring nennt selbst Betreff und Headline als
  Mit-Konsumenten); ein Verhaltenswechsel dort würde ungefragt drei weitere
  Stellen mitändern.
- **`_sms_leading_variants`/`_sms_pack_with_fallback` unverändert
  wiederverwendet** — die bestehende Rückfallkette (Ort weglassen → Zeit
  weglassen → nur Kürzel) bleibt die Sicherheitsgarantie für die schwerste
  Warnung, jetzt nur mit dem neuen Token als `code`-Argument statt des alten
  `_hazard_display(...)[1]`. Das „!" wird ERST nach der Variantenbildung
  vorangestellt, damit die Rückfallkette selbst unverändert bleibt.
- **`_sms_pack`s Joiner wechselt von `" + "` auf `" "`** — das Zielbild zeigt
  keine `+`-Verkettung mehr zwischen Tokens (`Seg 4: !TH:L 12-22 HT:L`), nur
  noch das bestehende `+N`-Omission-Suffix bei Überlänge bleibt unverändert.
- **`build_official_alert_notices`/`build_compare_official_alert_notices`:
  eine Zeile geändert** — `.replace("Segment ", "S")` wird zu
  `.replace("Segment ", "Seg ")`. `sms_scope` wird ausschließlich vom
  SMS-Renderer gelesen (kein HTML-/Telegram-rich-/Plain-Mail-Konsument), die
  Änderung ist damit gefahrlos lokal.
- **`_ascii_alert_location()` bekommt dieselbe Abkürzung** (Pflichtinhalt
  „Seg-Kurzform gilt für ALLE Alarm-SMS-Zweige"): die Funktion ist
  ausschließlich SMS-only-Konsument (vier Aufrufstellen in `render.py`:
  Z. 273 Onset-Shift-SMS, Z. 457/459/461 Onset-SMS, Z. 941 Trip-Δ-SMS) — die
  Abkürzung an EINER Stelle trifft automatisch alle vier, ohne Email/
  Telegram-rich/Betreff zu berühren (die nutzen `_km_str`/`_km_str_onset`,
  nicht `_ascii_alert_location`).

**Zeitfenster statt Beginnstunde, Wochentag nur wenn nicht heute.**
`_tag_time` bleibt bei der Fenster-Darstellung (`13-22`, nicht `@13`) — bei
einer amtlichen Warnung ist das Ende sicherheitsrelevant, und das Budget ist
mit gemessen max. 49 % Auslastung nicht knapp (Entscheidungstabelle der
Analyse-Phase). Neu ist die Wochentag-Regel (PO-Entscheid 3): Beginnt die
Gültigkeit am heutigen Tag (verglichen in der übergebenen `tz`), entfällt der
Wochentag-Präfix ersatzlos — Ist-Fall 1 (`Do12-22`, aufgezeichnet an einem
Donnerstag) wird zu `12-22` im Zielbild. Beginnt die Gültigkeit an einem
anderen Tag, bleibt der Wochentag-Präfix wie bisher stehen (unverändertes
Bestandsverhalten). **Testfalle (Muster aus S4 übernommen):** ein fixer
Goldstring für den „heute"-Fall wäre wanduhr-abhängig rot, sobald der Testlauf
über Mitternacht hinausreicht — der Test braucht einen Vergleich gegen
`datetime.now(tz)` statt eines eingefrorenen Wochentagskürzels.

## Expected Behavior

- **Input:** `list[OfficialAlertNotice]`, gebaut von `build_official_alert_notices`
  (Trip) oder `build_compare_official_alert_notices` (Ortsvergleich) — beide
  Flächen rufen dieselbe `render_official_alert_sms`-Funktion ohne
  `sms_prefix`.
- **Output:** bei einheitlichem Umfang `{Ortskopf}: !{Token1} {Token2} …`
  (Ortskopf = `sms_scope`, z. B. „Seg 4", „Ziel", „ges.Route"); bei
  uneinheitlichem Umfang `!{Token1 mit eigenem Ortszusatz} {Token2 mit
  eigenem Ortszusatz} …` ohne gemeinsamen Kopf. Jeder Token hat die Form
  `{Kürzel}:{Stufe}[ {Zeitfenster}]`, `access_ban` blank ohne Doppelpunkt.
  Kein `AMT`, kein Trip-/Preset-Name, keine `{WORT}{Pos}/3`-Notation mehr.
- **Side effects:** keine — reine Renderer-Formatierung; kein
  Datenmodell-Wandel außer der additiven DTO-Ergänzung an `OnsetPayload`/
  `NowcastFramesPayload` (Vorbedingung, s. AC-15).

## Acceptance Criteria

- **AC-1:** Given eine amtliche Gewitterwarnung, deren betroffener Umfang exakt
  Segment 4 ist (`sms_scope` heute „S4") / When `render_official_alert_sms`
  über den einheitlichen Umfang gerendert wird / Then lautet der Ortskopf exakt
  „Seg 4: " statt des bisherigen Kurzcodes „S4", identisch zur PO-Zielbild-Tabelle.
  - Test: Unit-Test gegen `render_official_alert_sms` mit konstruierter
    `OfficialAlertNotice`, Substring-Vergleich auf „Seg 4: " und Abwesenheit von „S4".

- **AC-2:** Given eine amtliche Warnung, deren betroffener Umfang ausschließlich
  das Zielsegment ist (`sms_scope="Ziel"`, wie bereits von `build_official_alert_notices`
  geliefert) / When dieselbe Nachricht gerendert wird / Then lautet der Kopf
  exakt „Ziel: ", dieselbe Ortssprache, die Trip-Briefing und Nowcast-Alarm
  bereits für das Zielsegment verwenden.
  - Test: Unit-Test, Substring-Vergleich auf „Ziel: " am Nachrichtenanfang.

- **AC-3:** Given zwei Warnungen mit exakt demselben betroffenen Segment-Umfang
  (Gewitter gelb und Hitze gelb am selben Segment) / When beide zu einer
  Kurznachricht zusammengefasst werden / Then trägt die Ausgabe genau EIN „!"
  unmittelbar vor dem ersten Token, kein zweites „!" vor dem zweiten Token,
  und beide Tokens sind durch genau ein Leerzeichen getrennt.
  - Test: Unit-Test, `sms.count("!") == 1` und Regex-Prüfung, dass das „!"
    direkt vor dem ersten Kürzel-Token steht, nicht davor oder danach versetzt.

- **AC-4:** Given drei separat konstruierte Warnungen der amtlichen Stufen
  gelb (2), orange (3) und rot (4), jeweils derselbe Gefahrenart / When jede
  einzeln über `render_official_alert_sms` gerendert wird / Then trägt der
  jeweilige Token exakt den Buchstaben L, M bzw. H direkt nach dem
  Doppelpunkt, entsprechend PO-Entscheid „Warnstufen-Mapping Option 1".
  - Test: drei Unit-Tests (oder ein parametrisierter Test), die je einen
    festen Level-Wert gegen den erwarteten Buchstaben prüfen.

- **AC-5 (Wächter):** Given eine amtliche Warnung der Stufe GRÜN (1) UND ein
  direkter Aufruf von `alert_urgency.urgency_from_official_level(1)` im selben
  Testlauf / When beide Pfade nacheinander ausgeführt werden / Then liefert
  die SMS-Darstellung den Buchstaben „-" für GRÜN, UND
  `urgency_from_official_level(1)` liefert weiterhin „LOW" ohne `KeyError`,
  weil `hazard_symbols.LEVEL_LETTERS` von dieser Scheibe nicht angefasst wird.
  - Test: Wächter-Unit-Test, der beide Funktionen im selben Testkörper
    aufruft — ein Mutant, der `1: "-"` in `LEVEL_LETTERS` einschleust, muss
    diesen Test mit `KeyError` rot werden lassen (Mutations-Gegenprobe).

- **AC-6:** Given eine amtliche Warnung mit `hazard="access_ban"`
  (Zugangssperre, ein binärer Zustand ohne Schweregrad) / When sie in die
  Kurznachricht gerendert wird / Then erscheint das Kürzel „CL" blank, ohne
  Doppelpunkt, ohne Stufenbuchstaben und ohne Zeitangabe, egal welche `level`
  die Warnung trägt.
  - Test: Unit-Test mit `level` auf mehrere Werte durchgetestet (2/3/4),
    erwartet in jedem Fall exakt den Substring „CL" ohne „CL:" oder Zeitteil.

- **AC-7:** Given eine Gewitterwarnung mit Gültigkeit von 12:00 bis 22:00 an
  einem anderen Kalendertag als dem heutigen Testlauf-Tag / When der
  Zeit-Token über `_tag_time` gerendert wird / Then zeigt er das vollständige
  Fenster („12-22") inklusive Wochentag-Präfix, nicht nur die Beginnstunde
  und nicht das `@`-Beginn-Format der Trip-Briefing-Vorhersage-Tokens.
  - Test: Unit-Test gegen `_tag_time` mit einem `valid_from`/`valid_to`-Paar,
    dessen Datum bewusst auf den Folgetag des Testlaufs gesetzt wird.

- **AC-8:** Given dieselbe Gewitterwarnung wie in der Ist-Basislinie (Fall 1),
  deren Gültigkeit exakt am heutigen Wochentag beginnt / When der Zeit-Token
  gerendert wird / Then entfällt der Wochentag-Präfix ersatzlos — die Ausgabe
  lautet „12-22" statt des bisherigen „Do12-22", während Minuten weiterhin
  zweistellig blieben, sobald sie ungleich „:00" sind.
  - Test: Unit-Test, der `valid_from`/`valid_to` relativ zu `datetime.now(tz)`
    konstruiert (kein eingefrorener Goldstring, s. Wanduhr-Testfalle), und
    prüft, dass kein zweibuchstabiges Wochentagskürzel vor der Stunde steht.

- **AC-9:** Given einen Trip mit dem Namen „KHW 403" und mindestens eine
  amtliche Warnung / When `render_official_alert_sms` ohne `sms_prefix`-Argument
  aufgerufen wird (die Signatur trägt den Parameter nicht mehr) / Then
  enthält die Ausgabe an keiner Stelle den Trip-Namen, weder als Präfix noch
  als Teilstring, weil der Trip-/Preset-Name ersatzlos entfallen ist.
  - Test: Unit-Test, `"KHW403" not in sms` und `"KHW 403" not in sms` geprüft.

- **AC-10:** Given einen aktiven Trip-Alarm mit genau einer Segment-Warnung /
  When `notification_service.send_official_alert` den SMS-Kanal über den
  echten Dispatch-Pfad bedient / Then entspricht der versendete Text der
  Ortskopf-Kürzel-Stufe-Zeit-Grammatik dieser Scheibe statt des alten
  AMT-Formats — der Nachweis läuft über den echten Aufrufer, nicht nur den
  isolierten Renderer.
  - Test: Integrationstest über `send_official_alert` mit einem `sms_sink`,
    der den finalen Text abfängt; Substring-Prüfung auf das neue Kopf-Format
    und Abwesenheit von „AMT".

- **AC-11:** Given einen Ortsvergleich-Alarm mit derselben Warnungsstruktur
  wie in AC-10 / When `_dispatch_compare_official_sms` den SMS-Kanal bedient
  / Then entspricht der versendete Text exakt derselben Grammatik wie im
  Trip-Fall aus AC-10, weil beide Flächen dieselbe `render_official_alert_sms`-
  Funktion aufrufen und keine zweite Renderer-Kopie entsteht.
  - Test: Vergleichstest — Trip- und Compare-Ergebnis mit strukturell
    identischer Eingabe (bis auf `scope_kind`) auf identisches Token-Format
    geprüft (Teilungs-Invariante).

- **AC-12:** Given eine amtliche Warnung, gerendert einmal über den
  Telegram-Kurzstil (`telegram_style="kurzform"`) und einmal über den
  SMS-Kanal, beide aus demselben Dispatch-Aufruf / When beide Texte
  verglichen werden / Then sind sie byte-identisch, weil der Kurzstil
  denselben `render_official_alert_sms`-Aufruf nutzt — das ist gewollte
  Parität, kein Regressionsfall (anders als in S4, wo der Kurzstil beim
  alten Format blieb).
  - Test: Fortschreibung von `test_telegram_kurzstil_trip_alert.py`/
    `test_telegram_kurzstil_compare_official_alert.py` auf das neue Format,
    Assertion `telegram_body == sms_text` bleibt bestehen.

- **AC-13 (TABU-Wächter):** Given dieselben Warnungen einmal vor und einmal
  nach der S5-Umstellung des SMS-Renderers / When Betreff
  (`render_official_alert_subject`), E-Mail-HTML (`render_warn_block`),
  Klartext-Mail (`render_official_alert_mail_plain`) und die ausführliche
  Telegram-Vorlage (`render_official_alert_telegram`) gerendert werden /
  Then bleiben alle vier Ausgaben byte-identisch zum Vor-S5-Zustand, weil
  `_LEVEL_WORDS`, `_LEVEL_POSITION`, `_hazard_display`, `_sort_notices` und
  `_uniform_scope` von dieser Scheibe nicht verändert werden.
  - Test: Bestehende Regressionstests für die vier Kanäle laufen unverändert
    grün (Verhaltensnachweis); Snapshot-Fixture bestätigt Betreff/E-Mail/
    Telegram-rich als unveränderte Felder (s. AC-16).

- **AC-14:** Given sowohl eine amtliche Warnung mit Segment-Umfang als auch
  ein Nowcast-Onset-Alarm mit Segment-Kennung, deren Ortskopf jeweils auf
  dasselbe Segment zeigt / When beide über ihre jeweilige SMS-Renderfunktion
  gerendert werden / Then verwenden beide identisch die Kurzform „Seg" statt
  „Segment" im Kopf, während die zugehörige E-Mail und das ausführliche
  Telegram für dasselbe Segment weiterhin „Segment" ausgeschrieben zeigen.
  - Test: Vergleichstest über beide Renderer (`render_official_alert_sms` und
    den S4-Onset-Renderer) mit strukturell gleichem Segment-Input, plus
    Gegenprobe, dass der zugehörige E-Mail-Renderer „Segment" unverändert zeigt.

- **AC-15 (Vorbedingung aus S4):** Given einen Preview-Aufruf über
  `POST /api/trips/{id}/alert-preview` mit einem `onset`- oder
  `nowcast_frames`-Payload, der ein Segment benennt (`segment_id`/`segment_ids`)
  / When der Payload in ein `OnsetEvent` übersetzt wird (Onset-Zweig ~Z. 117,
  Frame-Replay ~Z. 253 in `validator_render_service.py`) / Then trägt das
  resultierende `OnsetEvent` dasselbe Segment, das `OfficialAlertPayload`
  schon heute über `segment_ids` transportiert — die Lücke aus S4
  (`issuecomment-5351380856`) ist geschlossen, obwohl S5 selbst sie nicht
  spürt.
  - Test: Endpunkt-Test gegen `POST /api/trips/{id}/alert-preview` mit einem
    `onset`-Payload, der ein `segment_id`-Feld trägt; Antwortfeld-Nachweis,
    dass der gerenderte Ortskopf das übergebene Segment nennt statt auf den
    km-Rückfall zu fallen.

- **AC-16:** Given den bewusst neu erzeugten Snapshot
  `tests/fixtures/official_alert_render_snapshot_1944.json` mit dem neuen
  `trip_sms`/`compare_sms`-Format / When `test_official_alert_output_unchanged.py`
  erneut gegen diesen Snapshot läuft / Then bleiben die drei unveränderten
  Kanäle (Betreff, E-Mail, Telegram-rich) weiterhin exakter byte-genauer
  Regressionsschutz — nur `trip_sms`/`compare_sms` zeigen das neue Format.
  - Test: bestehender Snapshot-Test, Fixture bewusst mit dem neuen Renderer
    neu erzeugt (kein manuelles Goldstring-Editing), vier Kanäle geprüft.

- **AC-17:** Given eine amtliche Warnung mit einem `hazard`-Wert außerhalb des
  zehnteiligen Katalogs (`HAZARD_SMS_SYMBOLS`), aber bekannter Stufe orange
  (3) / When sie über `render_official_alert_sms` gerendert wird / Then
  trägt das Fallback-Kürzel aus `sms_symbol_for` trotzdem den Stufenbuchstaben
  „M" — nur der Gefahrentyp ist unbekannt, die Schwere bleibt bekannt und
  wird nicht unterdrückt.
  - Test: Unit-Test mit synthetischem `hazard="thunder_squall"` (Kollisions-
    Kandidat laut `sms_format.md` Sz.4c), Substring-Prüfung auf „:M" nach dem
    dreistelligen Fallback-Kürzel.

## Known Limitations

- **Nur `thunderstorm` und `extreme_heat` in Stufe 2 (gelb) sind mit echten
  Aufzeichnungen verifizierbar.** Von 50 echten Prod-Mitschnitten
  (2026-08-20, Kärnten/KHW) enthält keiner gemischte Stufen, Stufe 3/4,
  `access_ban` oder Warnungen mit uneinheitlichem Segment-Umfang. AC-3/AC-4
  (Stufen orange/rot)/AC-6/AC-17 sind deshalb ausschließlich über
  konstruierte Fixtures und Unit-Tests verifizierbar, nicht über einen
  echten End-to-End-Mitschnitt.
- **Uneinheitlicher Umfang ohne gemeinsamen Kopf ist eine Design-Ableitung,
  keine literale PO-Vorlage.** Die vier PO-Zielbild-Beispiele decken
  ausschließlich den einheitlichen-Umfang-Fall ab. Für den Fall
  „verschiedene Warnungen betreffen verschiedene Segmente" leitet diese Spec
  aus dem bestehenden Code-Verhalten ab, dass der gemeinsame Kopf entfällt
  und jedes Token seinen eigenen Ortszusatz trägt (analog zum heutigen
  Mixed-Scope-Zweig) — ohne dass der PO eine konkrete Ausgabe-Zeichenkette
  für diesen Fall freigegeben hat. Sollte sich das als falsch erweisen, ist
  das ein Nachtrag für eine Folge-Scheibe, kein Bruch dieser Spec.
- **Zeichenbudget ist im realen Betrieb zu maximal 49 % ausgelastet**
  (Minimum 41, Median 42,5, Maximum 68 von 140 Zeichen, gemessen an 27
  eindeutigen echten Warnungen). Kein einziges Token wurde je gedroppt. Die
  Kürze ist damit ausdrücklich KEIN Argument für Formatentscheidungen dieser
  Scheibe — falls später jemand Kürze als Begründung heranzieht, widerspricht
  das der gemessenen Basislinie.
- **Wanduhr-Abhängigkeit im Weekday-Test (AC-8).** Ein fester Goldstring für
  den „heute"-Fall wäre zeitabhängig rot, sobald der Testlauf über
  Mitternacht bzw. über einen Wochentagswechsel hinausreicht — Präzedenz aus
  S4 (`docs/specs/modules/fix_1948_s4_nowcast_sms_zielbild.md`, „Testfalle —
  Wanduhr-Abhängigkeit"). Der Test muss relativ zu `datetime.now(tz)`
  konstruiert werden.

## Nicht Teil dieser Scheibe

- **Vigilance-Tokens (`HR:`/`TH:` nach §3.3)** — andere Formatfamilie
  (Météo-France, nicht `official_alerts`), von dieser Scheibe nicht berührt.
- **Compare-Editor/-UI** — reine Renderer-Formatänderung, keine
  Oberflächen-Änderung; die Ortsvergleich-Themen bleiben unabhängig davon
  wie bisher zurückgestellt.
- **Doku-Lücke `sms_format.md` §3.4c (`flood`/`FL` fehlt in der
  Kürzel-Tabelle)** — vorbestehende, unabhängige Dokumentationslücke, kein
  Renderer-Bug; gehört in eine separate Doku-Korrektur, nicht in diese Spec.
- **„#1929-Sperrzone"-Vermerke** in `alarm_testeinspeisung.md`,
  `feat_1944_warn_mitschnitt_herkunft.md`, `api_contract.md` — #1929 ist seit
  2026-08-18 geschlossen, die Vermerke sind veraltet und gehören in einer
  Doku-Nachziehrunde aufgelöst, nicht als Code-Änderung dieser Scheibe.
- **`tests/test_output_timezone_guard.py`s Ausnahmeliste** — Parallel-Session
  `#1727 S5g` schreibt die ordinal-indizierte Liste (`_tag_time`,
  `render_official_alert_sms`) strukturell um; diese Scheibe zieht ihre
  eigenen Ordinale nach, ändert aber nicht die Listenstruktur selbst.
- **S6 (Telegram-Parität)** — die ausführliche Telegram-Vorlage
  (`render_official_alert_telegram`) bleibt in dieser Scheibe unverändert
  (AC-13); ein etwaiger weiterer Angleich ist nicht Teil von S5.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reine Renderer-Formatänderung plus eine additive DTO-Ergänzung
  (Segment-Feld an `OnsetPayload`/`NowcastFramesPayload`), innerhalb eines
  bereits PO-freigegebenen Konzepts (`docs/analysis/alarm-format-konzept-2026-08.md`).
  Kein neues Datenmodell, keine neue Architekturentscheidungsfläche (kein
  neuer Kanal, kein neuer Provider, keine Persistenz-Änderung). Präzedenz:
  S4 (`fix_1948_s4_nowcast_sms_zielbild.md`) traf dieselbe Einschätzung für
  den strukturell gleichartigen Nowcast-Umbau.

## Changelog

- 2026-08-20: Initial spec created (S5 des Alarm-Format-Konzepts #1948, Zweig
  b amtliche Warn-SMS-Zielbild).
