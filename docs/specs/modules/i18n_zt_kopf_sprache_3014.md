---
entity_id: i18n_zt_kopf_sprache_3014
type: bugfix
created: 2026-11-15
updated: 2026-11-15
status: draft
version: "1.0"
workflow: fix-3014-zt-kopf-sprache
tags: [i18n, telegram, adr-0104, epic-2644]
---

# Telegram-Segmenttabelle: Zeitspalten-Kopf folgt der Kontosprache (#3014)

## Approval

- [ ] Approved

## Purpose

Der Kopf der Zeitspalte in der schmalen Telegram-Segmenttabelle ist fest "Zt" verdrahtet und erscheint auch bei englischen Konten. Er soll über den Textkatalog der Kontosprache folgen (Deutsch "Zt", Englisch "Hr"), damit das englische Telegram-Briefing und das englische Startseiten-Bild kein deutsches Kürzel mehr zeigen (ADR-0104, Epic #2644).

## Source

- **File:** `src/output/renderers/narrow.py`
- **Identifier:** `_narrow_table` (Zeile `headers = ["Zt"] + compact_labels`; einziger Aufrufer in `render_telegram_bubbles`, reicht `lang` bereits durch)

Schicht: Python-Core (Renderer, Katalog unter `src/i18n/messages/`). Kein Frontend-Code und keine Go-API betroffen; das Startseiten-Bild ist ein statisches Asset.

Querschnitt:
- **Trip/Ortsvergleich-Teilung:** kein neuer Baustein, keine Pendant-Frage. Die E-Mail-Stundentabelle des Ortsvergleichs hat ihren eigenen Schlüssel (`vergleich.stunden.zeit`) und bleibt unberührt.
- **Mandantentrennung:** keine Nutzerdaten bewegt, kein Endpoint betroffen.
- **Kanäle:** betroffen ist nur Telegram im Normalstil (Briefing und Befehlsantworten mit Segmenttabelle). E-Mail hat eine eigene Stundentabelle; SMS, Premium-SMS und Telegram-Kurzstil laufen über `report.sms_text` und nie durch `narrow.py`. Inhalt und Zeilenform bleiben gleich, nur der Kopftext ist sprachabhängig.

## Estimated Scope

- **LoC:** ca. +40/-5
- **Files:** 9
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/i18n` (`t`) | module | Auflösung des Katalogschlüssels nach Kontosprache |
| `src/i18n/messages/de/telegram.json`, `en/telegram.json` | catalog | neuer Schlüssel `telegram.tabelle.zeit` |
| `src/output/renderers/narrow.py` | module | `_narrow_table`, `_TG_TABLE_WIDTH = 32` |
| `scripts/landing_screenshots.py` | script | erzeugt `frontend/static/landing/en/briefing-telegram.png` neu (Spec `startseite_en_bilder_2777`) |
| `docs/specs/modules/i18n_skalenwoerter_lang_2784.md` | spec | Vorgänger, führte "Zt" fälschlich als sprachneutrales Kürzel |
| `tests/fixtures/metric_tokens_frozen.json` | fixture | Beleg, dass "Zt" kein Protokoll-Token ist (unverändert) |

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `src/output/renderers/narrow.py` | MODIFY | `headers = [t("telegram.tabelle.zeit", lang)] + compact_labels` |
| `src/i18n/messages/de/telegram.json` | MODIFY | `"telegram.tabelle.zeit": "Zt"` |
| `src/i18n/messages/en/telegram.json` | MODIFY | `"telegram.tabelle.zeit": "Hr"` |
| `tests/tdd/test_3014_zt_kopf_sprache.py` | CREATE | RED-Test: EN-Kopf beginnt mit "Hr", DE bleibt "Zt", keine Zeile über 32 Zeichen |
| `tests/tdd/test_2784_skalenwoerter_lang.py` | MODIFY | EN-Kopf-Erwartung "Zt" wird "Hr" |
| `tests/golden/telegram_briefing/briefing_normalstil.en.txt` | MODIFY | zwei Kopfzeilen "Zt" wird "Hr" |
| `frontend/static/landing/en/briefing-telegram.png` | MODIFY | neu erzeugt mit `scripts/landing_screenshots.py` |
| `docs/reference/telegram_format.md` | MODIFY | Zeitspalten-Kopf als sprachabhängig dokumentieren (Abschnitt Stufenwörter #2784) |
| `docs/specs/modules/i18n_skalenwoerter_lang_2784.md` | MODIFY | Hinweis: "Zt" war fälschlich als Kürzel geführt, siehe #3014 |

### Estimated Changes

- Files: 9
- LoC: +40/-5

## Implementation Details

Einordnung: "Zt" ist kein Protokoll-Token. Es steht nicht in `metric_tokens_frozen.json` und ist keine Metrik, sondern ein fest verdrahtetes deutsches Wortkürzel. Sprachfest ist laut ADR-0104 nur die Kurzform (SMS, Premium-SMS, Telegram-Kurzstil); die Segmenttabelle ist Telegram-Normalstil, deren Nachbartexte (`Segment`, `Finish`, `Summary`) bereits übersetzt sind. Also gilt: Nutzertext, nur über den Katalog.

Ansatz: neuer Katalogschlüssel `telegram.tabelle.zeit` (de "Zt", en "Hr"), in `_narrow_table` per `t(key, lang)` aufgelöst. Die Metrik-Spaltenköpfe (`compact_label`) bleiben unübersetzt.

Breitenbefund: `_TG_TABLE_WIDTH = 32`. Die englische Golden-Zeile `12 12.0 22 32 0.2 none  15 2800` ist 31 Zeichen lang. "Time" würde die Zeitspalte um 2 Zeichen verbreitern (33 Zeichen) und einen harten Umbruch mitten in der Datenzeile auslösen. Daher die 2-Zeichen-Form "Hr": Zeitzellen sind 2-stellig ("08"), die Spaltenbreite bleibt 2, das Layout bleibt bis auf den Kopf byte-gleich. "Hr" kollidiert mit keinem `compact_label` (HU, HP, TH usw.); "h" wurde verworfen, weil es wie eine Einheit statt wie ein Spaltenname wirkt. Passend zu ADR-0104: wo wenig Platz ist, steht die englische Fachkurzform.

Deutsch bleibt byte-gleich (DE-Golden, `golden_berichte.json`, Tests mit `startswith("Zt ")`). Der Entwickler bestätigt per gezieltem Testlauf, dass keiner dieser bestehenden Tests mit `lang="en"` läuft. Das EN-Startseiten-Bild wird nach der Codeänderung mit `scripts/landing_screenshots.py` neu erzeugt.

## Expected Behavior

- **Input:** Segmenttabelle im Telegram-Normalstil, gerendert mit `lang="en"` bzw. `lang="de"`
- **Output:** Kopfzeile beginnt bei Englisch mit "Hr", bei Deutsch mit "Zt"; Metrik-Kürzel unverändert; keine Zeile länger als 32 Zeichen
- **Side effects:** neues EN-Startseiten-Bild; keine Datenänderung

## Test Plan

### Automated Tests (TDD RED)

- [ ] Test 1: GIVEN ein Briefing mit Segmenttabelle / WHEN mit `lang="en"` gerendert / THEN beginnt die Kopfzeile mit "Hr" und enthält kein "Zt"
- [ ] Test 2: GIVEN dasselbe Briefing / WHEN mit `lang="de"` gerendert / THEN beginnt die Kopfzeile unverändert mit "Zt"
- [ ] Test 3: GIVEN englisches Briefing mit breitester Datenzeile / WHEN gerendert / THEN ist keine Tabellenzeile länger als 32 Zeichen
- [ ] Test 4: GIVEN der Katalog / WHEN de und en geladen werden / THEN existiert `telegram.tabelle.zeit` in beiden Sprachen (Paritätstest)
- [ ] Test 5: GIVEN `test_2784_skalenwoerter_lang.py` und die EN-/DE-Golden-Dateien / WHEN gezielt gelaufen / THEN grün, DE-Golden unverändert

## Acceptance Criteria

- **AC-1:** Given ein Konto mit Sprache Englisch und ein Briefing mit Segmenttabelle / When das Telegram-Briefing im Normalstil erzeugt wird / Then beginnt die Kopfzeile jeder Segmenttabelle mit "Hr" und das deutsche Kürzel "Zt" kommt nirgends in der Nachricht vor.
  - Test: Rendern mit `lang="en"`, Kopfzeile der Tabelle prüfen (Nutzersicht der Telegram-Nachricht)

- **AC-2:** Given ein Konto mit Sprache Deutsch / When dasselbe Telegram-Briefing erzeugt wird / Then beginnt die Kopfzeile weiterhin mit "Zt" und die Nachricht ist byte-gleich zum bisherigen deutschen Stand.
  - Test: Rendern mit `lang="de"`, Vergleich gegen die bestehende DE-Golden-Datei

- **AC-3:** Given ein englisches Briefing mit der breitesten Datenzeile (alle Spalten belegt) / When die Segmenttabelle erzeugt wird / Then ist keine Tabellenzeile länger als 32 Zeichen und es entsteht kein Umbruch mitten in einer Datenzeile.
  - Test: Rendern mit `lang="en"`, Länge jeder Tabellenzeile gegen `_TG_TABLE_WIDTH` prüfen

- **AC-4:** Given die Startseite für englische Besucher / When das Telegram-Beispielbild betrachtet wird / Then zeigt die Tabelle im Bild "Hr" statt "Zt".
  - Test: Bild mit `scripts/landing_screenshots.py` neu erzeugen und die zugrunde liegende Telegram-Beispielnachricht (`telegram_html()`) auf "Hr" prüfen; das Bild selbst per Sichtprüfung

- **AC-5:** Given die Spaltenköpfe der Messwerte (T, W, G, R, TH, VS, FZ) / When ein englisches oder deutsches Briefing erzeugt wird / Then bleiben diese Kürzel in beiden Sprachen unübersetzt und identisch.
  - Test: Kopfzeile mit `lang="en"` und `lang="de"` rendern, Metrik-Kürzel nach dem Zeitspalten-Kopf vergleichen

## Definition of Done

- AC-1 bis AC-5 erfüllt, RED-Tests vorher rot und nachher grün belegt.
- Mutationsprobe vom Adversary rot nachgewiesen (Kopf wieder fest auf "Zt" bzw. EN-Katalogwert auf "Time" gesetzt).
- EN-Golden und `test_2784_skalenwoerter_lang.py` nachgezogen, DE-Golden byte-gleich.
- EN-Startseiten-Bild neu erzeugt und gesichtet; `telegram_format.md` und Spec #2784 richtiggestellt.
- Alle 6 CI-Checks am PR grün, Staging-Telegram-Briefing auf Englisch zeigt "Hr".

## Known Limitations

- "Hr" ist eine Kurzform und bewusst kein "Time": die 32-Zeichen-Tabellenbreite lässt keinen längeren Kopf zu.
- Weitere Sprachen außer Deutsch und Englisch existieren nicht; kommt eine hinzu, braucht sie einen eigenen 2-Zeichen-Eintrag im Katalog.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue; folgt ADR-0104
- **Rationale:** ADR-0104 legt fest, dass der Telegram-Normalstil der Kontosprache folgt und nur Protokoll-Token sprachfest sind. Diese Änderung wendet die bestehende Regel auf ein übersehenes Textstück an.

## Changelog

- 2026-11-15: Initial spec created (Issue #3014)
