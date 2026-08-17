---
entity_id: fix_1714_compare_alert_briefing_reset
type: bugfix
created: 2026-08-17
updated: 2026-08-17
status: draft
workflow: fix-1714-compare-alert-dedup
---

# Fix #1714: Ortsvergleich-Briefing vermerkt gezeigte amtliche Warnungen nicht im Melde-Gedächtnis

## Approval

- [ ] Approved

## Purpose

Das Ortsvergleich-Briefing (`send_one_compare_preset`) zeigt amtliche Warnungen im
versendeten Bericht an, schreibt sie aber nie ins Melde-Gedächtnis
(`official_alert:`-Namensraum). Der unabhängige, alle 15 Minuten laufende
Ortsvergleich-Alarm-Checker (`compare_official_alert.py`) kennt diese Warnungen deshalb
nicht als „bereits gemeldet" und verschickt dieselbe, unveränderte Warnung kurz danach
erneut als eigenständigen Alarm. Der Trip-Pfad hat exakt diese Lücke bereits seit #1614
Teil 1 geschlossen (`trip_report_scheduler.py:1638-1645`, ruft den geteilten Baustein
`record_official_alerts_reported()` aus `alert_briefing_anchor.py` auf). Diese Spec
verdrahtet das fehlende Compare-Gegenstück — kein neuer Mechanismus, reine Nutzung eines
bereits geteilten, produktiv erprobten Bausteins.

## Source

- **File:** `src/services/scheduler_dispatch_service.py`
- **Identifier:** `send_one_compare_preset` (Zeile 350, Versandblock ab Zeile 546)

## Estimated Scope

- **LoC:** ~15-20 Produktivcode, ~150-220 Tests
- **Files:** 2 (1 MODIFY, 1 CREATE)
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `services.alert_briefing_anchor.record_official_alerts_reported` | function | Bereits bestehende, geteilte Schreib-Logik fürs Melde-Gedächtnis (`official_alert:`-Namensraum). Signatur `(*, user_id, entity_id, alerts)`, fail-soft No-Op bei leerer `alerts`-Liste. Wird hier nur ZUSÄTZLICH aufgerufen, nicht verändert. |
| `services.notification_service.NotificationService.send_compare_report` | method | Liefert `NotificationResult` mit `.sent: bool`. Rückgabewert wird am Aufrufort aktuell verworfen und muss erfasst werden. |
| `services.comparison_parallel.run_comparison_parallel` (Ergebnis `result.locations`) | data | Liefert je Ort ein `LocationResult` mit `.official_alerts: list[OfficialAlert]` und `.location.id` — Quelle für die im Briefing tatsächlich gezeigten Warnungen. |
| `services.compare_official_alert._detect` | function (Lesepfad, unverändert) | Lädt denselben State-Namensraum über `AlertStateService(user_id).load(f"{preset_id}:{loc_id}")` — profitiert automatisch von den neuen Einträgen, kein eigener Code-Wechsel nötig. |

## Implementation Details

Tatsächliche Code-Struktur in `send_one_compare_preset` (verifiziert, weicht leicht vom
Trip-Vorbild-Muster ab): der `try`-Block (Zeile 546-569) umschließt AUSSCHLIESSLICH den
`send_compare_report`-Aufruf. Der `except`-Zweig (570-575) vermerkt den Fehlschlag,
ruft `_anchor_and_reset()` für den Fehlerfall auf und wirft weiter (`raise`). Erst NACH
dem try/except, im ungestörten Erfolgspfad, steht der zweite, unbedingte
`_anchor_and_reset()`-Aufruf (Zeile 577). Ein Exception-Pfad erreicht Zeile 577 nie —
genau deshalb muss die neue Record-Logik VOR diese Zeile, nicht in den `try`-Block
selbst (der an dieser Stelle bereits verlassen ist):

```python
try:
    send_result = NotificationService(settings, user_id).send_compare_report(
        subject=subject, html_body=html_body, text_body=text_body,
        telegram_text=..., sms_text=..., recipients=empfaenger,
        effective_channels=..., compare_hourly_enabled=opts.hourly_enabled,
        mail_sink=mail_sink, sms_sink=sms_sink, telegram_sink=telegram_sink,
    )
except Exception as exc:
    record_briefing_dispatch_failure(...)
    _anchor_and_reset()
    raise

if send_result.sent and not on_demand:
    from services.alert_briefing_anchor import record_official_alerts_reported
    for loc_result in result.locations:
        if loc_result.official_alerts:
            record_official_alerts_reported(
                user_id=user_id,
                entity_id=f"{preset_id}:{loc_result.location.id}",
                alerts=loc_result.official_alerts,
            )

_anchor_and_reset()
```

- `send_result` (statt `result` — der Name `result` ist bereits durch das
  Comparison-Engine-Ergebnis aus `run_comparison_parallel` belegt).
- Kennungs-Schema pro Ort: `f"{preset_id}:{loc_result.location.id}"` — identisch zum
  bereits etablierten Anker-Kennungs-Schema in `_anchor_and_reset()` (Zeile 526), NICHT
  `preset_id` allein (das ist für die Briefing-Protokoll-Kennung reserviert).
- `on_demand`-Gate zwingend: Handversand (`send_compare_preset`, immer
  `on_demand=True`) darf das Melde-Gedächtnis nicht anfassen (#1007/#1467 S2 AG5,
  identisch zum Trip-Ad-hoc-Pfad).
- `send_result.sent`-Gate zwingend: ein fehlgeschlagener oder kanalloser Versand darf
  eine nie zugestellte Warnung nicht fälschlich als „gemeldet" markieren.
- **Kein Eingriff in `compare_official_alert.py`** (`_detect`/`_record_state` bleiben
  unverändert) — die im Issue erwähnte Refactoring-Frage („Kopie durch geteilte Fassung
  ersetzen") ist explizit NICHT Teil dieser Scheibe (Nebenbefund für #1199).
- **Kein Eingriff in `official_alert_state_key()`** — das Schlüsselformat bleibt
  unangetastet (Koordination mit paralleler #1657-Arbeit an derselben Datei-Familie).

## Expected Behavior

- **Input:** Ein Compare-Preset wird über `send_one_compare_preset` versendet
  (Daily-Loop oder Einzelversand), mindestens ein Ort trägt gezeigte amtliche
  Warnungen (`loc_result.official_alerts`).
- **Output:** Bei erfolgreichem, nicht-ad-hoc Versand wird für jeden Ort mit gezeigten
  Warnungen ein Eintrag im Melde-Gedächtnis (`official_alert:`-Namensraum,
  `AlertStateService`) unter der Kennung `f"{preset_id}:{loc.id}"` geschrieben.
- **Side effects:** Der nächste Lauf von `compare_official_alert.py::_detect()` für
  denselben Ort liest diesen Eintrag und unterdrückt eine unveränderte Warnung als
  Doppelmeldung — bereits bestehende Lesepfad-Logik, kein Code-Wechsel dort nötig.

## Acceptance Criteria

- **AC-1:** Given ein Compare-Briefing wurde erfolgreich (`send_result.sent=True`,
  `on_demand=False`) mit einer amtlichen Warnung für einen Ort versendet, When der
  nächste Lauf von `compare_official_alert.py` für denselben Ort mit unveränderter
  Warnung (gleiches Level) läuft, Then meldet der Checker diese Warnung NICHT erneut
  als eigenständigen Alarm.
  - Test: `test_briefing_meldet_unveraenderte_amtliche_warnung_danach_nicht_erneut` (Compare-Spiegelung des Trip-Vorbilds) — Kern-Regressionsschutz gegen den im Issue beschriebenen Doppelversand.

- **AC-2:** Given dieselbe Ausgangslage wie AC-1 (Warnung bereits im Melde-Gedächtnis
  vermerkt), When die Warnung danach auf ein höheres Level eskaliert, Then meldet
  `compare_official_alert.py` die eskalierte Warnung weiterhin als neuen Trigger.
  - Test: `test_eskalierte_warnung_wird_trotz_bereits_gemeldeter_unveraenderter_warnung_weiterhin_gemeldet` — verhindert stille Unterdrückung echter Verschärfung durch den neuen Doppelversand-Schutz.

- **AC-3:** Given ein Handversand über `send_compare_preset` (immer `on_demand=True`,
  #1007) liefert dieselbe amtliche Warnung, When der Versand abgeschlossen ist, Then
  bleibt das Melde-Gedächtnis für den betroffenen Ort unverändert — kein neuer Eintrag
  im `official_alert:`-Namensraum.
  - Test: `test_ad_hoc_abruf_schreibt_das_melde_gedaechtnis_amtlicher_warnungen_nicht` — bestehende Read-only-Garantie für Handversand darf durch die neue Schreiblogik nicht verletzt werden.

- **AC-4:** Given der Versand des Compare-Briefings schlägt fehl (Exception aus
  `NotificationService.send_compare_report`, `except`-Zweig greift), When
  `send_one_compare_preset` durchläuft, Then wird für keinen Ort ein Eintrag im
  Melde-Gedächtnis geschrieben — eine nie zugestellte Warnung bleibt für den
  Alarm-Checker weiterhin meldepflichtig.
  - Test: `test_fehlgeschlagener_versand_schreibt_das_melde_gedaechtnis_nicht` — verhindert, dass ein fehlgeschlagener Versand eine Warnung fälschlich als „gemeldet" stumm schaltet.

- **AC-5:** Given zwei verschiedene Nutzer (`user_id`) mit je einem Preset und je einer
  identischen amtlichen Warnung für denselben Ort, When für Nutzer A das Briefing
  erfolgreich versendet wird, Then bleibt das Melde-Gedächtnis von Nutzer B davon
  vollständig unberührt.
  - Test: `test_zwei_nutzer_bleiben_im_melde_gedaechtnis_getrennt` — Mandantentrennung, CLAUDE.md-Pflicht bei jedem nutzerbezogenen, datenbewegenden Pfad.

- **AC-6:** Given ein Preset mit zwei Orten, von denen nur EINER eine amtliche Warnung
  im Briefing zeigt, When das Briefing erfolgreich versendet wird, Then wird
  ausschließlich für den Ort mit gezeigter Warnung ein Eintrag geschrieben — ein
  bestehender Melde-Gedächtnis-Eintrag des anderen Ortes bleibt unverändert, nicht
  überschrieben oder gelöscht.
  - Test: `test_zwei_orte_im_preset_beeinflussen_sich_im_melde_gedaechtnis_nicht_gegenseitig` — R3-Analogie aus `write_anchor_and_reset_memory`-Docstring, verhindert versehentliches Cross-Orts-Überschreiben.

- **AC-7:** Given ein Preset, dessen Briefing für keinen Ort amtliche Warnungen zeigt
  (leere `official_alerts`-Liste je Ort), When das Briefing erfolgreich versendet wird,
  Then löst der neue Codepfad KEINEN Schreibzugriff auf das Melde-Gedächtnis aus.
  - Test: `test_preset_ohne_gezeigte_warnungen_loest_keinen_schreibzugriff_aus` — Fail-soft No-Op, spiegelt das bestehende Leer-Listen-Verhalten von `record_official_alerts_reported` selbst; kein unnötiger State-Write.

## Known Limitations

- **Kein Eingriff in `compare_official_alert.py::_record_state`.** Die dort bestehende
  Inline-Kopie derselben Schreib-Logik bleibt unangetastet — ein mögliches Refactoring
  zur Vereinheitlichung ist im Issue als offene Frage genannt, aber bewusst nicht Teil
  dieser Scheibe (Empfehlung: Nebenbefund-Issue #1199).
- **Kein Eingriff in das Schlüsselformat.** `official_alert_state_key()` wird von
  dieser Spec nicht verändert — eine parallele Session arbeitet zeitgleich an #1657 an
  genau dieser Funktion; diese Scheibe ändert nur die Schreibhäufigkeit/-quelle, nicht
  das Schlüsselformat selbst.
- **Zwei Aufrufstellen von `send_one_compare_preset`.** Der Fix sitzt in der
  gemeinsamen Funktion (Daily-Loop `run_compare_presets_daily` UND Einzelversand
  `send_compare_preset`) — wirkt dadurch für den Daily-Loop-Pfad automatisch, für den
  Einzelversand-Pfad greift korrekt das `on_demand`-Gate (kein Schreibzugriff dort).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reine Verdrahtung eines bereits bestehenden, geteilten Bausteins
  (`record_official_alerts_reported`, eingeführt mit #1614 Teil 1) an eine bislang
  fehlende Aufrufstelle — kein neuer Mechanismus, kein neues Datenmodell, keine neue
  Architekturentscheidung.

## Changelog

- 2026-08-17: Initial spec created.
