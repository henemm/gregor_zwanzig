---
entity_id: fix_1252_1253_kanal_text
type: bugfix
created: 2026-07-13
updated: 2026-07-13
status: draft
workflow: fix-1252-1253-kanal-text-v2
version: "1.0"
tags: [telegram, sms, email, ascii-fold, escaping, adr-0012]
---

<!-- Issues #1252, #1253 -->

# Kanal-Textaufbereitung: Telegram-Auszeichnungen und Zeichenfaltung

## Approval

- [ ] Approved

## Purpose

Zwei gebündelte Kanal-Bugs derselben Klasse (Textaufbereitung vor dem Versand)
beheben:

- **#1252:** Amtliche Warnungen zeigen auf Telegram rohe HTML-Auszeichnungen
  (`<b>…</b>` steht wörtlich in der Nachricht), weil zwei Aufrufer
  (`notification_service.py:538`, `:658`) nie auf `parse_mode="HTML"`
  umgestellt wurden, obwohl ADR-0012 das für alle formatierten
  Telegram-Pfade vorschreibt.
- **#1253:** Ortsnamen mit Akzenten/Umlauten werden auf SMS und im
  E-Mail-Klartext verstümmelt (`Hyères` → `Hyres`, `München` → `Mnchen`),
  weil `render.py::_ascii` Sonderzeichen ersatzlos löscht statt sie gemäß
  `sms_format.md:27` zu falten (`ä→ae`, `ö→oe`, `ü→ue`, `ß→ss`).

Betroffen sind Kernzielgebiete des Produkts (`Hyères`, `Fréjus`,
`Collobrières` — GR20/Korsika/Frankreich); der Fehler trifft dort praktisch
jede Warnung.

## Source

- **File:** `src/output/renderers/alert/official_alerts.py` — `class:_notice_block` (Escaping-Lücke Zeilen 1361-1369)
- **File:** `src/services/notification_service.py` — Zeilen 538, 658 (fehlender `parse_mode`), 703 (rohe Vorkürzung)
- **File:** `src/output/channels/telegram.py` — `class TelegramOutput.send()` (400-Fallback)
- **File:** `src/output/renderers/alert/render.py` — `def _ascii` (Zeile 521)
- **NEU:** `src/utils/ascii_fold.py` — `def fold_ascii(text: str) -> str`

## Estimated Scope

- **LoC:** +85/-25 Produktionscode (klar im 250er-Budget)
- **Files:** 10 (1 neu, 9 geändert) + Testdateien
- **Effort:** medium (Blast Radius hoch — betrifft alle Official-Alert-Ausgabepfade —, aber durch bindende Reihenfolge entschärft)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| ADR-0012 (`docs/adr/0012-telegram-parse-mode-html.md`) | ADR | Bindend für den gesamten Telegram-Teil dieser Spec — `parse_mode`-Default bleibt `None`, HTML+Escaping ist Standard für formatierte Pfade |
| `sms_format.md:27,66` (`docs/reference/sms_format.md`) | Reference | Bindende Faltungs-Konvention (`ä→ae` etc.) und Reihenfolge „zuerst falten, dann kürzen" |
| `src/output/tokens/builder.py::_UMLAUT` | intern | Bestehende korrekte Referenz-Implementierung der Faltung (Vorbild für `fold_ascii`) |
| `src/utils/geo.py` | intern | Bestätigt Konvention: `src/utils/*` ist Leaf-Modul, importiert nichts aus `src/output/*` |
| `tests/tdd/test_952_onset_alert_fidelity.py:616-627` | Test | Muss unverändert grün bleiben — schützt ADR-0012 Punkt 2 bewusst |
| `tests/tdd/test_sms_preview_matches_sent.py:96` | Test | Muss unverändert grün bleiben — garantiert Vorschau == Versand, dadurch wandert der Fix automatisch in die Frontend-Vorschau |
| `tests/tdd/test_official_alert_template_render.py:204` | Test | Muss unverändert grün bleiben (`sms.isascii()`-Guard) |

## Implementation Details

### Reihenfolge-Zwang (bindend, sonst entsteht ein Zeitfenster ohne Netz)

Damit nie ein Zustand entsteht, in dem eine Warnung durch ein übersehenes
Sonderzeichen stillschweigend verschwindet, MÜSSEN die drei Telegram-Schritte
in genau dieser Reihenfolge implementiert und verifiziert werden:

1. **Escaping zuerst** — `official_alerts.py:1361-1369`: `_display_label(n.alert)`,
   `scope_label`, `_format_validity(...)` und `source_label` (:1368) analog
   zum bereits escapten E-Mail-Zweig derselben Datei (:191, :194, :848, :1095)
   durch `_html.escape()` schicken. Voraussetzung für alles Weitere.
2. **400-Fallback danach** — `TelegramOutput.send()` in `telegram.py` muss
   live sein, **bevor** Schritt 3 scharf geschaltet wird. Additive Härtung,
   kein ADR-Konflikt: greift ausschließlich bei
   `parse_mode is not None AND status == 400` — der Altpfad
   (`parse_mode=None`) erreicht diesen Zweig nie, `test_952_...` bleibt daher
   unberührt grün. Beim Nachsenden ohne `parse_mode` müssen die Tags
   gestrippt **und** `html.unescape()` angewendet werden — sonst zeigt der
   Fallback `&amp;` statt `&` (ein kosmetischer Fehler gegen einen anderen
   getauscht).
3. **`parse_mode="HTML"` zuletzt** — nur an den zwei vergessenen Aufrufern
   `notification_service.py:538` (Standalone-Alert) und `:658`
   (Compare-Alert) explizit setzen. Der Default von `TelegramOutput.send()`
   bleibt `None` (ADR-0012 Punkt 2, NICHT anfassen). Die übrigen Pfade
   (`:273` Briefing-Bubbles, `:789` Deviation/Radar-Onset) setzen bereits
   `"HTML"` und sind nicht Teil des Scopes.

### Faltung — Reihenfolge ist die Pointe

Neues Leaf-Modul `src/utils/ascii_fold.py`:

```python
def fold_ascii(text: str) -> str:
    # 1. Umlaut-Digraph-Map ZUERST (ä→ae, ö→oe, ü→ue, ß→ss, Großschreibung analog)
    # 2. DANACH NFKD-Normalisierung + Combining-Marks entfernen (é→e)
    # -> Reihenfolge ist bindend: NFKD zuerst würde ü zu "u" statt "ue"
    #    zerlegen (Verstoss gegen sms_format.md:27)
```

Aufrufer, die auf `fold_ascii` umgestellt werden (eine Quelle, Rest Thin-Wrapper):

- `render.py::_ascii` — bleibt als lokaler Wrapper für die typografischen
  Symbole (`–`, `°`, `↑`, `·`, `⚡`), die kanalspezifisches
  Präsentationsdetail sind und **vor** dem `fold_ascii()`-Aufruf ersetzt
  werden. Buchstaben-Faltung selbst delegiert an `fold_ascii`.
- `email/compact.py::_ASCII_MAP` — Umlaut-Einträge raus, delegiert an
  `fold_ascii` (Akzent-Faltung war hier bereits fehlend, `Hyères` → `Hyres`
  auch im E-Mail-Klartext).
- `tokens/builder.py::_UMLAUT` — raus, delegiert an `fold_ascii` (war die
  einzige bereits korrekte Implementierung, dient als Referenz).
- `sms_trip.py::_sms_stage_prefix` — faltet aktuell gar nicht (`[:10]` roh);
  wird auf „erst falten, dann kürzen" umgestellt.

### Reihenfolge-Falle beim Längen-Budget (trip_short)

`sms_format.md:66` schreibt „zuerst falten" vor. Drei Stellen schneiden
`trip.name[:16]` roh (ungefaltet), **bevor** `render.py:257`/`:496` faltet
und erneut `[:16]` kürzt — die Doppelkürzung frisst Buchstaben, weil `ü→ue`
wächst:

- `notification_service.py:703`
- `radar_alert_service.py:71`
- `validator_render_service.py:108`

Die rohe Vorkürzung entfällt ersatzlos an allen drei Stellen. Geprüft:
`trip_short` ist **nicht** identitätsbildend (nur Anzeigetext, kein
Dedup-/Vergleichs-/Persistenzschlüssel; `AlertMessage.trip_short` trägt
keinen Längenvertrag) — Wegfall der Vorkürzung ist eine reine
Anzeige-Verbesserung, keine Regression. `render.py:498` (`[:24]` auf
`location_label`) ist bereits korrekt (kürzt nach dem Falten) und bleibt
unverändert. `official_alerts.py:1575-1577` faltet bereits vor dem Packen
und dient als Vorbild.

## Expected Behavior

- **Input:** Amtliche Warnung mit Behörden-Feed-Text und Ortsnamen, die
  beliebige Sonderzeichen (`&`, `<`, `é`, `è`, `ü`) tragen können (untrusted
  Upstream-Daten aus Vigilance/MeteoAlarm).
- **Output:** Telegram-Nachricht mit korrekt gerendertem HTML-Fett (kein
  wörtliches `<b>`) und immer zugestellt (nie durch ein Sonderzeichen
  verschluckt); SMS/E-Mail-Klartext mit lesbaren gefalteten Ortsnamen
  (`Hyeres`, `Muenchen`) statt gelöschten Buchstaben.
- **Side effects:** Frontend-Vorschau (SMS/Telegram/Alert) zeigt automatisch
  dasselbe Ergebnis, da `test_sms_preview_matches_sent.py` Vorschau == Versand
  garantiert und beide Pfade durch dieselben Renderer laufen.

## Acceptance Criteria

- **AC-1:** Given eine amtliche Warnung, deren Ortsname oder Behörden-Label
  ein `&` oder `<` enthält / When die Warnung per Telegram versendet wird /
  Then kommt die Warnung beim Empfänger an — sie wird nie stillschweigend
  verschluckt, auch wenn ein Sonderzeichen im Text steckt.
  - Test: Warnung mit `&`/`<` im Ortsnamen über den echten Sendepfad
    schicken, Zustellung verifizieren (kein `OutputError`, keine Exception
    verschluckt den Versand).

- **AC-2:** Given eine amtliche Warnung wird per Telegram versendet / When
  der Empfänger die Nachricht öffnet / Then ist die Kopfzeile fett
  dargestellt — keine sichtbaren Auszeichnungs-Zeichen (`<b>`, `</b>`) im
  Nachrichtentext.
  - Test: Gerenderten Nachrichtentext auf Abwesenheit roher `<b>`/`</b>`-Literale
    im wahrgenommenen (unescapten) Anzeigetext prüfen, bei gleichzeitig fett
    dargestellter Kopfzeile über `parse_mode="HTML"`.

- **AC-3:** Given eine Warnung betrifft den Ort `Hyères` / When die Warnung
  als SMS gesendet wird / Then enthält die SMS `Hyeres` (lesbar,
  wiedererkennbar) statt `Hyres` (verstümmelt).
  - Test: Warnung mit echtem Eingabewert `Hyères` durch den SMS-Renderer
    schicken, Ausgabe auf `Hyeres` prüfen.

- **AC-4:** Given eine Warnung betrifft den Ort `München` / When die Warnung
  als SMS gesendet wird / Then enthält die SMS `Muenchen` statt `Mnchen`.
  - Test: Warnung mit echtem Eingabewert `München` durch den SMS-Renderer
    schicken, Ausgabe auf `Muenchen` prüfen.

- **AC-5:** Given ein Ortsname mit Akzenten/Umlauten / When der
  E-Mail-Klartext gerendert wird / Then erscheint der gefaltete, lesbare Name
  (z.B. `Hyeres`) statt eines verstümmelten oder unvollständig gefalteten
  Namens.
  - Test: Denselben Eingabewert durch den E-Mail-Klartext-Renderer
    (`compact.py`) schicken, Ausgabe auf das gefaltete Ergebnis prüfen.

- **AC-6:** Given ein Nutzer öffnet die Vorschau eines Alerts/einer SMS in
  der App / When die Vorschau angezeigt wird / Then zeigt sie exakt denselben
  Text wie die tatsächlich versendete Nachricht (gefaltete Namen, gerendertes
  Fett, keine rohen Auszeichnungen).
  - Test: `test_sms_preview_matches_sent.py` bleibt grün — Vorschau-Renderer
    und Versand-Renderer liefern identischen Output für denselben Input.

- **AC-7:** Given ein Trip-Name mit Umlaut, der bislang roh auf 16 Zeichen
  vorgekürzt und danach erneut gekürzt wurde / When die SMS gerendert wird /
  Then wird der Name nicht durch doppeltes Kürzen mitten im Wort verstümmelt
  — die Faltung geschieht vor jeder Kürzung.
  - Test: Trip-Namen mit Umlaut nahe der 16-Zeichen-Grenze durch den
    SMS-Titelzeilen-Pfad (`notification_service.py`, `radar_alert_service.py`,
    `validator_render_service.py`) schicken, Ergebnis auf vollständige
    Wörter statt abgeschnittene Buchstaben prüfen.

- **AC-8:** Given eine SMS mit gefalteten Sonderzeichen und Vigilance-/
  Fire-Tokens / When die SMS final zusammengesetzt wird / Then bleibt sie bei
  maximal 160 Zeichen und ist rein ASCII (`sms.isascii()` bleibt wahr).
  - Test: `tests/tdd/test_official_alert_template_render.py:204`
    (`sms.isascii()`-Guard) bleibt unverändert grün.

## Known Limitations

- `TelegramOutput.edit_message_text` (`telegram.py:235`) bekommt weiterhin
  kein `parse_mode` — per Callback editierte Briefings können rohe Tags
  zeigen. Außerhalb des Scopes dieser Spec, Sammel-Eintrag #1199.
- Keine Umstellung auf MarkdownV2 — ADR-0012 hat diese Alternative bereits
  bewertet und verworfen (18 escape-pflichtige Zeichen, hohe
  Fehleranfälligkeit).
- Der 4096-Zeichen-Kürzungspfad (`_truncate_html`, Issue #976) wird in dieser
  Spec nicht umgebaut; er kann theoretisch HTML-Tags mittig abschneiden, ist
  aber ein bekanntes offenes Risiko aus ADR-0012 und nicht Teil dieses Fixes.
- Plaintext-Telegram-Caller (`notification_service.py:333`, `:840`, `:859`,
  `channel_test_service.py:40`) bleiben bei `parse_mode=None` — sie sind von
  der expliziten Umstellung nicht betroffen (ADR-0012 Punkt 2), kein
  Handlungsbedarf.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine (neue)
- **Rationale:** ADR-0012 (Status: Akzeptiert) deckt die Telegram-Seite
  bereits vollständig ab — `parse_mode="HTML"` als Standard für formatierte
  Pfade, `_esc()`/`_html.escape()` als einzige Escaping-Stelle,
  `parse_mode=None`-Default bleibt rückwärtskompatibel. Diese Spec setzt die
  ADR nur an den zwei bislang vergessenen Aufrufern konsequent um; sie trifft
  keine neue Architekturentscheidung. Die Faltungsseite ist durch
  `docs/reference/sms_format.md:27,66` bereits verbindlich spezifiziert
  (Umlaut-Map, Reihenfolge „erst falten, dann kürzen"). Der 400-Fallback ist
  eine additive Härtung ohne Konflikt zu bestehenden Entscheidungen.

## Test Plan

### Automated Tests (TDD RED)

Testdateien werden verhaltensbenannt, NICHT nach Issue-Nummer (Gate blockt
issue-nummerierte Testdateien):

- [ ] `tests/tdd/test_telegram_html_escaping.py` — GIVEN ein Ortsname mit `&`
      im `scope_label` WHEN eine Official-Alert-Telegram-Nachricht gerendert
      wird THEN ist `&` als `&amp;` escaped, nicht wörtlich im HTML-Payload.
- [ ] `tests/tdd/test_telegram_html_escaping.py` — GIVEN dieselbe Nachricht
      WHEN sie über `TelegramOutput.send(parse_mode="HTML")` verschickt wird
      THEN kommt sie zugestellt an (kein `OutputError`), auch bei
      unescaptem Rest-Sonderzeichen im Upstream-Feed (400-Fallback greift).
- [ ] `tests/tdd/test_telegram_400_fallback.py` — GIVEN ein lokaler
      HTTP-Stub-Server antwortet mit Status 400 auf den ersten Sendeversuch
      mit `parse_mode="HTML"` WHEN `send()` erneut ohne `parse_mode` und mit
      gestrippten/unescapten Tags nachsendet THEN zeigt die zweite Anfrage
      lesbaren Klartext (`&` statt `&amp;`, keine `<b>`-Tags).
- [ ] `tests/tdd/test_ascii_folding.py` — GIVEN `fold_ascii("Hyères")` WHEN
      aufgerufen THEN ist das Ergebnis `"Hyeres"`.
- [ ] `tests/tdd/test_ascii_folding.py` — GIVEN `fold_ascii("München")` WHEN
      aufgerufen THEN ist das Ergebnis `"Muenchen"` (nicht `"Munchen"` —
      belegt die bindende Reihenfolge Umlaut-Map vor NFKD).
- [ ] `tests/tdd/test_ascii_folding.py` — GIVEN ein Trip-Name mit Umlaut nahe
      der 16-Zeichen-Grenze WHEN der SMS-Titelzeilen-Pfad rendert THEN ist
      das Ergebnis ein vollständig gefaltetes, nicht doppelt gekürztes Wort.
- [ ] `tests/tdd/test_sms_special_chars.py` — GIVEN eine SMS-Warnung für
      `Hyères` WHEN sie gerendert wird THEN enthält sie `Hyeres`, bleibt
      `isascii()` und ≤160 Zeichen.

### Bestehende Fixtures korrigieren (Testdaten kodierten den Bug als Sollzustand)

- [ ] `tests/tdd/test_official_alert_warn_section.py:59` —
      `sms_scope="nurHyeres"` (der verstümmelte Name als Konstante) auf einen
      echten Eingabewert (`Hyères`) mit erwarteter gefalteter Ausgabe
      (`Hyeres`) umstellen. Ohne diese Korrektur beweist der Test nichts —
      er würde eine Regression suggerieren, wo tatsächlich der Bug behoben
      wird.
- [ ] `tests/tdd/test_official_alert_channel_scope.py:46` — Fixture
      `"hyeres": "Hyeres"` (bereits vorgefalteter Name) um einen zweiten
      Fall mit rohem Eingabewert `"Hyères"` ergänzen, damit der Golden-Test
      die Faltung tatsächlich prüft statt sie zu umgehen.

### Guard-Tests (dürfen NICHT angefasst werden, müssen grün bleiben)

- [ ] `tests/tdd/test_952_onset_alert_fidelity.py:616-627` — prüft
      `parse_mode == "HTML"` für den Onset-Pfad und dass der Altpfad kein
      `parse_mode` setzt (ADR-0012 Punkt 2). Unverändert lassen.
- [ ] `tests/tdd/test_official_alert_template_render.py:204` —
      `sms.isascii()`-Guard.
- [ ] `tests/tdd/test_sms_preview_matches_sent.py:96` — Vorschau == Versand.

### Test-Infrastruktur

Kein `Mock()`/`patch()` für den 400-Fallback-Test — echter lokaler
HTTP-Stub-Server nach Vorbild `test-936-sms-stub-server`.

## Faktenkorrektur (2026-07-13, nach TDD-RED)

Die Analyse behauptete, die Test-Fixtures kodierten den Bug als Sollzustand (`sms_scope="nurHyeres"` als verstümmelte Konstante). **Das ist falsch.** Eine Suche über das gesamte Repository nach einem verstümmelten `Hyres`-Literal ergab: es existiert keines. `nurHyeres` ist korrekt gefaltet und durchläuft lediglich nie den Faltungspfad.

**Die Testlücke ist dennoch real und unverändert die Ursache:** Kein einziger Test speist je einen echten Namen mit Akzent/Umlaut (`Hyères`, `München`) in eine Faltungsfunktion ein — alle Fixtures nutzen bereits vorgefaltete ASCII-Namen. Deshalb konnte der Bug überleben.

**Folge für den Test-Plan:** Die geplante „Fixture-Korrektur" entfällt als eigener Punkt. Stattdessen werden die geteilten Fixture-Konstanten (`LOC_NAMES` in `test_official_alert_channel_scope.py`) NICHT verändert — sie speisen bit-identische Telegram-Goldens, die mit Faltung nichts zu tun haben (Telegram faltet nie, UTF-8). Stattdessen ein **eigenständiger** Test mit lokalem Namens-Dict, der den echten Pfad `build_compare_official_alert_notices` → `render_official_alert_sms` mit roher Eingabe `Hyères` durchläuft.

## Changelog

- 2026-07-13: Initial spec created — Issues #1252, #1253
- 2026-07-13: Faktenkorrektur nach TDD-RED — Fixtures kodieren den Bug NICHT als Konstante; Testlücke (keine rohe Eingabe) bleibt die Ursache. Fixture-Korrektur als Baustein entfernt, eigenständiger Test stattdessen.
