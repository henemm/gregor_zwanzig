---
entity_id: fix_1465_zeitzonen_hausnorm
type: bugfix
created: 2026-08-03
updated: 2026-08-03
status: draft
version: "1.0"
tags: [tests, timezone, drilldown, issue-1465, issue-1196]
workflow: fix-1465-zeitzonen-hausnorm
---

# Fix #1465 — 15 Tests auf die Zeitzonen-Hausnorm ziehen

## Approval

- [x] Approved — 2026-08-03, auf Delegation des PO („Handle als mein Tech Lead der nach
  Best-Practice-Regeln entscheidet"). Reine Testpflege nach einer **dokumentierten,
  unstrittigen** Norm; keine Produktentscheidung enthalten. Der PO hat #1465 zuvor als
  nächsten Schritt bestätigt.

## Purpose

15 Tests in fünf Dateien prüfen ein Zeitzonen-Verhalten, das seit Issue **#1345** nicht
mehr gilt. Das Produkt ist korrekt; die Tests stammen aus `4a389c70` (#652, 2026-06-07)
und wurden bei Einführung der Hausnorm nicht mitgezogen.

Ziel: Die Erwartungen folgen der Norm, ohne dass dabei ein zweiter Fehler mit grün gezogen
wird. Beitrag zum Dach **#1196** (deterministischer Kern grün) — die größte
Einzelursache der Rot-Liste.

## Source

- **Norm:** `src/app/models.py:151-158` — `ForecastDataPoint.__post_init__` konvertiert
  zeitzonenbehaftete Zeitstempel nach UTC und strippt die Zeitzone („Hausnorm naive UTC an
  der Provider-Grenze", #1345).
- **Prüfling unverändert:** `src/services/weather_extractor.py` — die im Ticket ursprünglich
  vermutete Zeile 133 wirft nichts.
- **Betroffen:** `tests/tdd/test_weather_extractor.py` (2),
  `test_command_reply_channel_emoji.py` (5), `test_issue_654_telegram_thunder_drilldown.py` (4),
  `test_issue_667_snapshot_hourly_clip_fix.py` (1),
  `test_issue_704_telegram_interactive_navigation.py` (3).

Vollständige Messung: `docs/context/fix-1465-zeitzonen-hausnorm.md`.

## Estimated Scope

- **LoC:** 0 Produktivcode + ~60–120 Testcode + ~40 Doku. Kein Produktivcode — wer hier
  `models.py` anfasst, hebt die Hausnorm auf.
- **Files:** 5 Testdateien.
- **Effort:** low — die Änderung ist mechanisch, der Aufwand liegt in der Sorgfalt (s. ACs).

## Acceptance Criteria

- **AC-1:** Given die Testvorlagen erzeugen ihre Datenpunkte mit zeitzonenbehafteten
  Zeitstempeln / When ein Test den Rückgabewert des Extraktors vergleicht / Then vergleicht
  er gegen einen **zeitzonenlosen UTC**-Zeitstempel, wie ihn die Hausnorm liefert — und
  nicht mehr gegen einen zeitzonenbehafteten.
  - Test: die 15 heute roten Tests sind grün.

- **AC-2:** Given eine Erwartung wird angepasst / When sie angepasst wird / Then ist
  **belegt**, dass außer der Zeitzone nichts anderes an dieser Erwartung veraltet ist —
  ein blindes Streichen von `tzinfo=timezone.utc` würde einen zweiten Fehler mit grün
  ziehen.
  - Test: keiner automatisierbar; nachzuweisen im Bericht je Fall, mit Angabe des
    verglichenen Werts vor und nach der Anpassung.

- **AC-3:** Given jemand liest künftig eine dieser Vorlagen / When er sich fragt, warum die
  Zeitstempel keine Zeitzone tragen / Then findet er an der Vorlage den Verweis auf die
  Hausnorm (#1345) — nicht nur die geänderte Erwartung.
  - Test: `# doc-compliance-test`-freier Sichtbelege im Bericht; die Vorlagen tragen den
    Verweis als Kommentar.

- **AC-4:** Given die Sanierung ist abgeschlossen / When eine der angepassten Erwartungen
  absichtlich verfälscht wird / Then wird der zugehörige Test rot.
  - Test: Mutations-Gegenprobe an einer Kopie außerhalb des Repos, Ergebnis im Artefakt.
    Ohne diese Hälfte ist „grün" nur Abwesenheit von Prüfung.

- **AC-5:** Given das Produkt folgt der Hausnorm / When die Sanierung läuft / Then bleibt
  `src/app/models.py` **unangetastet** — die Norm wird nicht aufgeweicht, um Tests grün zu
  bekommen.
  - Test: `src/app/models.py` unverändert.

  **⚠️ AC-5 in seiner ursprünglichen Fassung („leerer Diff auf `src/`") ist AUFGEHOBEN
  (2026-08-03, Adversary-Befund F001).** Die Annahme, es handle sich um reine Testpflege,
  war falsch — s. AC-6 bis AC-8. Unangetastet bleibt allein die **Norm selbst**
  (`models.py`); der Fix findet an der anderen Grenze statt.

- **AC-6 (der eigentliche Fehler):** Given ein Nutzer tippt im Telegram-Briefing auf
  „⛈ Gewitter" oder „⏱ Stunden" / When die Anfrage verarbeitet wird / Then bekommt er
  eine Antwort statt eines Absturzes — auch wenn der Zeitstempel der eingehenden
  Nachricht eine Zeitzone trägt und die Wetterdaten keine.
  - Test: `tests/tdd/test_telegram_drilldown_local_time_boundary.py`, Weg vom Knopfdruck
    bis zur Antwort, `received_at` wie im Empfänger gebaut.

  **Nachtrag 2026-08-03.** Die ursprüngliche Ticket-Diagnose und meine erste Korrektur
  lagen beide daneben: 2 der 15 Tests waren Testdrift, **13 reproduzierten einen echten
  Absturz**. Ursache ist eine Naht zwischen zwei je für sich richtigen Regeln —
  `ForecastDataPoint.ts` ist seit #1345 immer zeitzonenlos, `from_time` aus
  `msg.received_at` immer zeitzonenbehaftet, und niemand normalisierte dazwischen.
  Der Fix zieht `from_time` an der Grenze von `drilldown()` auf dieselbe Norm.

- **AC-7 (Ortszeit):** Given der Drilldown zeigt Stundenzeilen / When er sie beschriftet /
  Then stehen dort die Uhrzeiten **am Ort der Tour**, nicht die der Serverzeitzone.
  - Test: Trip auf Korsika, Erwartung unabhängig aus dem zeitzonenbehafteten `now`
    gebildet. Zuvor deutete `pt.ts.astimezone()` einen zeitzonenlosen Zeitstempel als
    Prozess-Zeitzone — auf diesem UTC-Server unauffällig, auf jedem anderen Host falsch.

- **AC-8 (der Wächter sieht wieder hin):** Given ein Eintrag der Scan-Liste des
  Zeitzonen-Wächters zeigt auf einen Pfad, den es nicht gibt / When der Wächter läuft /
  Then schlägt er fehl, statt den Eintrag wortlos zu überspringen.
  - Test: `test_scan_list_paths_all_exist()`.

  **Warum das dazugehört:** Der Wächter führte `src/app/trip_command_processor.py` — die
  Datei liegt unter `src/services/`. `_scan_files()` filtert mit `if p.exists()` und ließ
  den Eintrag stillschweigend fallen. Gemessen am Stand **vor** dem Fix hätte er **beide**
  Ortszeit-Fehler sofort gefunden. Ein Wächter, der nichts findet, weil er nichts ansieht,
  ist immer grün — dasselbe Muster wie bei den zwei Wächtern aus #1435 E3a.

## Known Limitations

- Die Sanierung macht **nur** diese fünf Dateien normkonform. Ob weitere Tests dieselbe
  veraltete Annahme tragen, ohne heute rot zu sein (weil sie den Vergleich nicht anstellen),
  ist **nicht** Teil dieser Lieferung — das wäre eine eigene Erhebung.
- Der Zeitzonen-Wächter `tests/test_output_timezone_guard.py` prüft Produktivcode, nicht
  Testcode. Er hätte diese Drift nie gefangen.

## Nachweisführung

Kein Mailversand, keine Staging-Prüfung nötig: Die Lieferung ändert ausschließlich
Testcode. Nachweis ist der grüne Lauf über die fünf Dateien plus die Mutations-Gegenprobe
aus AC-4.

## Changelog

- 2026-08-03 — angelegt, nachdem die ursprüngliche Ticket-Diagnose („möglicher
  Produktfehler") durch Messung widerlegt wurde.
