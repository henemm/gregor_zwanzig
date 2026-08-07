---
entity_id: fix_1555_nowcast_alert_priority
type: bugfix
created: 2026-08-07
updated: 2026-08-07
status: implemented
workflow: fix-1555-nowcast-alert-priority
version: "1.0"
tags: [issue-1555, alerts, epic-1067, follow-up-1070]
---

# NowCast-Alarme bekommen reservierten Vorrang im geteilten Tagesbudget

## Approval

- [x] Approved

## Purpose

`is_allowed()` (`src/services/alert_daily_limit.py`) reserviert innerhalb des
bestehenden, geteilten Tages-Alarmbudgets (Free 2/Standard 4/Premium
unbegrenzt, #1070) einen Mindestanteil ausschließlich für akute
NowCast-Alarme (`reason="nowcast"`). Vorhersage-Abweichungs-Alarme
(`reason="forecast_change"`) dürfen diesen reservierten Anteil nicht mehr
belegen. Grund: 0 von 118+ Alarm-Log-Einträgen system-weit trugen bislang
`"reason": "nowcast"` — Deviation-Alarme verbrauchten das Budget faktisch
immer zuerst und akute Gefahrenmeldungen wurden dadurch strukturell nie
zugestellt (#1555).

## Source

- **File:** `src/services/alert_daily_limit.py`
- **Identifier:** `is_allowed(user_id, now, reason=None)`

> **Schicht-Hinweis:** Alle Code-Änderungen liegen im Python-Core unter
> `src/services/` (FastAPI-Domain-Backend). Keine Go-/Frontend-Änderung.
> Kein Eingriff in `internal/scheduler/scheduler.go` (Cron-Reihenfolge ist
> wirkungslos, s. Known Limitations).

## Estimated Scope

- **LoC:** ~100-170 (Code ~20-35, Spec-Ergänzung ~15-30, Tests ~60-100)
- **Files:** 6 (4 Produktionscode, 1 Spec, 1 Testdatei)
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/services/alert_daily_limit.py` | module | Ort der Reserve-Logik selbst (`is_allowed`) |
| `src/services/user_tier.py` | module | Liefert unverändert `daily_alert_limit(user_id)` (Free 2/Standard 4/Premium `None`) — Basis der Reserve-Berechnung |
| `src/services/trip_alert.py` | module | 3 bestehende `is_allowed()`-Aufrufstellen bekommen `reason=` |
| `src/services/compare_alert.py` | module | 1 bestehende Aufrufstelle (Compare-Deviation) bekommt `reason="forecast_change"` |
| `src/services/compare_official_alert.py` | module | 1 bestehende Aufrufstelle (Compare-Official) — unverändertes Verhalten, kein Reserve-Grund |
| `docs/specs/modules/alert_daily_limit.md` | spec | Bestehende #1070-Spec — additiv um Reserve-Regel ergänzen, nicht ersetzen |
| `data/users/<user_id>/alert_daily_count.json` | data | Geteilter Zähler bleibt unverändertes Format (`{"date", "count"}`), keine Migration |

## Implementation Details

**`src/services/alert_daily_limit.py::is_allowed()`** bekommt einen
optionalen dritten Parameter `reason: str | None = None`:

- `reason is None` oder `reason != "forecast_change"` (also u.a.
  `"nowcast"`, `"official_alert"`, unbekannte Werte): Altverhalten
  unverändert — Prüfung gegen das volle `limit` aus `daily_alert_limit()`.
  Das ist die Rückwärtskompatibilitäts-Garantie: ein Aufruf ohne `reason`
  verhält sich exakt wie vor dieser Änderung.
- `reason == "forecast_change"` UND `limit` ist nicht `None`: Prüfung gegen
  `limit - RESERVE` statt `limit`, wobei `RESERVE` aus einer festen Tabelle
  je `limit`-Wert kommt: `limit=2` → `RESERVE=1` (Obergrenze für
  `forecast_change` wird `1`), `limit=4` → `RESERVE=2` (Obergrenze wird
  `2`). Kein anderer `limit`-Wert ist heute über `user_tier.daily_alert_limit`
  erreichbar (nur `2`, `4`, `None`); die Reserve-Tabelle deckt exakt diese
  beiden endlichen Werte ab.
- `reason == "forecast_change"` UND `limit is None` (Premium): keine
  Reserve — Premium bleibt für alle Gründe unbegrenzt, `is_allowed` liefert
  weiterhin sofort `True` ohne Zähler-Load.
- `load()` und `increment()` bleiben komplett unverändert — beide kennen
  keinen `reason`, schreiben/lesen weiterhin denselben flachen
  `{"date", "count"}`-Zähler. `nowcast` und `forecast_change` erhöhen
  denselben Zähler; die Reserve wirkt ausschließlich als eine niedrigere
  Vergleichs-Obergrenze für den `forecast_change`-Pfad, nicht als getrennter
  Zählerstand.

**Aufrufstellen (`reason=` ergänzen, kein anderer Code-Pfad geändert):**

| Datei:Zeile | Alarmart | `reason=` |
|---|---|---|
| `src/services/trip_alert.py:221` (`check_and_send_alerts`, Deviation) | Vorhersage-Abweichung | `"forecast_change"` |
| `src/services/trip_alert.py:761` (`check_radar_alerts`, Radar/NowCast) | Akute Gefahr | `"nowcast"` |
| `src/services/trip_alert.py:1169` (Official-Only-Pfad) | amtliche Warnung | unverändert (kein `reason` oder `reason="official_alert"` — beides prüft gegen das volle `limit`) |
| `src/services/compare_alert.py:145` (Compare-Deviation) | Vorhersage-Abweichung | `"forecast_change"` |
| `src/services/compare_official_alert.py:136` (Compare-Official) | amtliche Warnung | unverändert |

**Wo die Zusicherung tatsächlich WIRKT (Mutations-Gegenprobe-relevant):**
Die Reserve wirkt ausschließlich dort, wo `is_allowed()` mit
`reason="forecast_change"` tatsächlich aufgerufen wird — nicht dort, wo die
Reserve-Tabelle im Modul steht. Ein an einer der beiden
Deviation-Aufrufstellen (`trip_alert.py:221` bzw. `compare_alert.py:145`)
vergessenes `reason=`-Argument fällt still auf Altverhalten zurück: kein
Fehler, keine Ausnahme, einfach keine Reserve an dieser Stelle — der Bug aus
#1555 wäre an genau dieser Stelle unbemerkt reproduziert. Tests müssen daher
gegen die echten Aufrufstellen in `trip_alert.py`/`compare_alert.py` laufen
(reale `TripAlertService`/`CompareAlertService`-Läufe wie im bestehenden
AC-5-Test aus `test_issue_1070_daily_alert_limit.py`), nicht nur gegen
`alert_daily_limit.is_allowed()` isoliert — ein isolierter Modultest würde
ein vergessenes `reason=` an der Aufrufstelle nicht sehen.

## Expected Behavior

- **Input:** `user_id`, `now` (UTC), optional `reason` (`"forecast_change"`
  oder `None`/anderer Wert), Nutzer-Tier aus `user.json`, aktueller
  Tageszählerstand.
- **Output:** `is_allowed()` liefert `True`/`False` wie bisher — Rückgabetyp
  und Signatur-Grundverhalten unverändert, nur die Vergleichs-Obergrenze
  ändert sich bedingt.
- **Side effects:** keine neuen — `increment()`/`load()` unverändert, kein
  neues State-File, kein Schemawechsel an `alert_daily_count.json`.

## Acceptance Criteria

- **AC-1:** Given ein Free-Nutzer (`limit=2`) hat am aktuellen Vienna-Tag
  noch keinen Alarm erhalten (`count=0`) / When ein `forecast_change`-Alarm
  ausgelöst wird / Then wird er zugestellt, weil `count=0 < 1` (reduzierte
  Obergrenze für `forecast_change` bei `limit=2`).
  - Test: `alert_daily_count.json` mit `count=0` (oder keine Datei) vorseeden,
    echten `check_and_send_alerts`-Lauf über `TripAlertService` für einen
    Free-Nutzer ausführen, Assert über tatsächlichen Versand (`mail_sink`
    gefüllt) und resultierenden Zählerstand `count=1`.

- **AC-2:** Given ein Free-Nutzer (`limit=2`) hat am aktuellen Vienna-Tag
  bereits 1 `forecast_change`-Alarm erhalten (`count=1`, insgesamt wären laut
  Gesamtlimit `2` noch 1 Slot frei) / When ein weiterer
  `forecast_change`-Alarm ausgelöst wird / Then wird er unterdrückt (Reserve
  greift: `count=1` ist nicht `< 1`), aber ein `nowcast`-Alarm für denselben
  Nutzer im selben Zustand wird trotzdem noch zugestellt (`count=1 < 2`, dem
  vollen Limit).
  - Test: Zählerdatei auf `count=1` vorseeden, echten
    `check_and_send_alerts`-Lauf ausführen → Assert `mail_sink` bleibt leer,
    Zähler bleibt `1`; danach echten `check_radar_alerts`-Lauf für denselben
    `user_id` (anderer Trip) ausführen → Assert Versand erfolgt, Zähler auf
    `2`. Beweist die Vorrang-Wirkung, nicht nur die Reserve-Zahl isoliert.

- **AC-3:** Given ein Standard-Nutzer (`limit=4`) hat am aktuellen Vienna-Tag
  bereits 2 `forecast_change`-Alarme erhalten (`count=2`) / When ein dritter
  `forecast_change`-Alarm ausgelöst wird / Then wird er unterdrückt (Reserve
  greift: `count=2` ist nicht `< 2`), aber ein `nowcast`-Alarm im selben
  Zustand wird trotzdem noch zugestellt (`count=2 < 4`).
  - Test: analog AC-2 mit Standard-Tier und Zählerstand `2`; echter Lauf über
    beide Pfade, Assert über `mail_sink`-Inhalt und Zählerstand nach jedem
    Schritt.

- **AC-4:** Given ein Premium-Nutzer (`limit=None`) hat am aktuellen
  Vienna-Tag bereits 6 Alarme jeglicher Art erhalten / When sowohl ein
  `forecast_change`- als auch ein `nowcast`-Alarm ausgelöst werden / Then
  werden beide zugestellt, weil für Premium unverändert kein Tageslimit und
  damit auch keine Reserve gilt.
  - Test: Zählerdatei mit `count=6` vorseeden, Premium-Tier setzen, echte
    Läufe für beide Pfade ausführen; Assert `mail_sink` enthält beide neuen
    Einträge, kein Deckel greift.

- **AC-5:** Given ein bestehender Aufruf von
  `alert_daily_limit.is_allowed(user_id, now)` OHNE `reason`-Argument (wie
  vor dieser Änderung) / When er gegen einen Zählerstand geprüft wird, der
  zwischen der reduzierten und der vollen Obergrenze liegt (z.B. Free,
  `count=1`) / Then verhält er sich exakt wie vor dieser Änderung — geprüft
  gegen das volle `limit`, hier `1 < 2` → `True` — und nicht wie der
  reduzierte `forecast_change`-Pfad.
  - Test: `is_allowed(uid, now)` direkt ohne drittes Argument aufrufen bei
    `count=1`, Free-Tier; Assert `True`. Zusätzlich MUSS der bestehende Test
    `test_ac5_cross_path_daily_limit_shared_between_radar_and_deviation`
    (`tests/tdd/test_issue_1070_daily_alert_limit.py:463-536`) unverändert
    grün bleiben — er ruft die Aufrufstellen über die reale
    `TripAlertService` auf, nicht `is_allowed()` isoliert, und verankert
    damit die Rückwärtskompatibilität an der Stelle, wo sie wirkt.

- **AC-6:** Given der Compare-Pfad (`compare_alert.py`) befindet sich im
  selben Zählerstand wie in AC-2 beschrieben (Free, `count=1`,
  `forecast_change` bereits einmal versendet) / When ein weiterer
  Compare-`forecast_change`-Alarm für dasselbe Preset ausgelöst wird / Then
  wird er ebenso unterdrückt wie im Trip-Pfad — dieselbe Reserve-Regel gilt
  identisch für Compare.
  - Test: echten `CompareAlertService`-Lauf (oder äquivalente Funktion aus
    `compare_alert.py`) mit vorgeseedetem Zähler `count=1` und Free-Tier
    ausführen; Assert kein Versand, Zähler bleibt `1` — analog zum
    bestehenden Compare-AC-6-Test aus #1213 in
    `test_issue_1070_daily_alert_limit.py`, falls dort ein passendes Vorbild
    existiert, sonst neu nach demselben Muster wie AC-2.

## Known Limitations

- **`compare_radar_alert.py` bleibt ungebudgetiert:** Dieser Compare-NowCast-
  Pfad ruft `alert_daily_limit` heute gar nicht auf (weder mit noch ohne
  `reason`). Das ist eine bereits vor diesem Workflow bestehende
  Inkonsistenz — bewusst NICHT Teil dieses Fixes, um Scope-Explosion zu
  vermeiden. Dokumentiert hier, ggf. Sammel-Eintrag in #1199.
- **Cron-Reihenfolge ist wirkungslos:** `internal/scheduler/scheduler.go`
  registriert Deviation/Official- und Radar-Checks als zwei unabhängige
  `robfig/cron`-Jobs in getrennten Goroutinen. Ein Vertauschen der
  Registrierungsreihenfolge hätte keinen Effekt auf die tatsächliche
  Ausführungsreihenfolge und ist deshalb kein Lösungsansatz — die Reserve im
  geteilten Zähler ist der einzige wirksame Hebel.
- **`official_alert` bleibt unreserviert (PO-Entscheidung 2026-08-07):**
  Amtliche Warnungen laufen über einen eigenen, unabhängigen
  Trigger-Pfad (`check_official_alert_triggers()`) und wurden bewusst NICHT
  in die Reserve aufgenommen, obwohl die technische Analyse dies als
  gleichwertige Option vorschlug. Keine offene Frage — abschließend
  entschieden.
- **Feste Reserve-Tabelle statt Formel:** Die Reserve-Werte (1 bei `limit=2`,
  2 bei `limit=4`) sind als explizite Tabelle statt als generische Formel
  (z.B. `limit // 2`) implementiert, weil `user_tier.daily_alert_limit` heute
  ausschließlich `2`, `4` oder `None` liefert. Sollte künftig ein neues Tier
  mit anderem `limit`-Wert eingeführt werden, muss die Tabelle explizit
  erweitert werden — ein unbekannter `limit`-Wert würde sonst stillschweigend
  keine Reserve anwenden (Fallback-Verhalten muss beim Erweitern geprüft
  werden, ist in diesem Fix nicht Gegenstand, da heute nicht erreichbar).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reine additive Erweiterung des bestehenden, in
  `docs/specs/modules/alert_daily_limit.md` bereits als ADR-frei
  eingestuften #1070-Mechanismus (JSON-Read-Modify-Write-Zähler,
  `user_tier.py`-Fassade). Es entsteht kein neuer Architektur-Layer, kein
  neues Persistenzformat, keine neue Kanal- oder Provider-Entscheidung — nur
  ein optionaler Funktionsparameter mit eng begrenzter interner
  Verzweigungslogik in einem bereits etablierten Modul.

## Changelog

- 2026-08-07: Initial spec created
- 2026-08-07: Implemented, Adversary VERIFIED, live in Prod (`939e8c54`, PR #1565), Issue #1555 geschlossen
