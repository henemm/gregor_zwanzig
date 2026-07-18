---
entity_id: compare_dispatch_observability_telegram_guard
type: module
created: 2026-07-18
updated: 2026-07-18
status: draft
version: "1.0"
tags: [compare, dispatch, observability, telegram, guard, bugfix, issue-1290, issue-1288, epic-1301]
---

<!-- Scheibe E von Epic #1301: E1 (#1290) Compare-Dispatch-Observability + E2 (#1288) Telegram-Empfaenger-Guard -->

# E-Paket „Betrieb & Sicherheit" — Compare-Dispatch-Observability + Telegram-Guard (E1+E2)

## Approval

- [ ] Approved

## Purpose

Zwei gebündelte Backend-Fixes (PO-sanktioniertes Kleinbündel, Epic #1301
Scheibe E):

**E1 (#1290):** Der Compare-Daily-Versand-Endpoint (`/api/scheduler/compare-presets-daily`)
meldet `status:"ok"` selbst dann, wenn 100 % der fälligen Presets scheitern —
belegt im Prod-Journal 2026-07-16 mit 133 von 133 Fehlschlägen. Ursache: die
Rückgabe trägt kein `failed`-Feld, obwohl Trip-Reports (#766/#1012) dasselbe
Problem bereits über `{status, count, failed}` gelöst haben. Das externe
Monitoring (`check-gregor20.sh`) und der Go-Scheduler-Status
(`/api/scheduler/status`) können einen kompletten Compare-Ausfall dadurch
nicht von einem normalen leeren Lauf unterscheiden.

**E2 (#1288):** `TelegramOutput.send` postet `chat_id` ungeprüft an die Bot-API.
E-Mail hat seit #1147/#1219/#1235 eine harte, bedingungslose Empfänger-Guard-Linie
(`email.py`) — Telegram hat kein Äquivalent. Konkretes Risiko: `Settings.for_testing()`
setzt `telegram_chat_id` auf `telegram_test_chat_id or telegram_chat_id` — ist
`GZ_TELEGRAM_TEST_CHAT_ID` nicht gesetzt, sendet ein Test-Modus-Aufruf
(z. B. `channel_test_service.py:25`, das `.for_testing()` unabhängig vom
`user_id` erzwingt) klaglos an die Prod-Chat-ID.

**Zusammenspiel:** Ein von E2 im Test-Modus blockierter Compare-Telegram-Versand
soll über E1s neues `failed`-Feld sichtbar werden. Dieses Zusammenspiel ist
KEIN Selbstläufer — s. Implementation Details E2, Abschnitt „Interlock" für
die dafür nötige, eng begrenzte Zusatzänderung.

## Source

- **E1 File:** `api/routers/scheduler.py:129-138` (`trigger_compare_presets_daily`),
  `src/services/dispatch_orchestrator.py:96-155` (`CompareDispatchStrategy`),
  `src/services/scheduler_dispatch_service.py:118-146` (`run_compare_presets_daily`)
- **E2 File:** `src/output/channels/telegram.py:112-199` (`TelegramOutput.send`),
  `src/services/notification_service.py:655-668` (`send_compare_report`, Telegram-Zweig)

> Schicht: Python-Core/Domain-Backend (`api/`, `src/services/`, `src/output/`) —
> kein Go-/Frontend-Bezug. Go (`internal/scheduler/scheduler.go:322,344-347`)
> parst `Failed` bereits generisch aus jeder Endpoint-Antwort und braucht
> KEINE Änderung, sobald Python das Feld liefert.

## Estimated Scope

- **LoC:** ~70-90 (Kern) + Tests
- **Files:** 5 Quelldateien (`telegram.py`, `dispatch_orchestrator.py`,
  `scheduler_dispatch_service.py`, `api/routers/scheduler.py`,
  `notification_service.py`) + 3 Bestandstest-Dateien mit Anpassungsbedarf
  (s. Bestandstest-Audit) + neue Testdatei(en) für Guard + Endpoint-`failed`
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `api/routers/scheduler.py:40-44` (`trigger_trip_reports`) | Vorbild E1 | `sent, failed = ...`; `status = "partial" if failed > 0 else "ok"`; `{status, count, failed}` — E1 kopiert dieses Muster 1:1 für Compare |
| `src/services/dispatch_orchestrator.py:33-79` (`TripDispatchStrategy`) | Vorbild E1 | `self._failed`-Zähler + `result() -> (sent, failed)`-Tupel — `CompareDispatchStrategy` bekommt dasselbe Muster |
| `src/output/channels/email.py:27-110,415-512` | Vorbild E2 | `OutputConfigError`, bedingungsloser Guard direkt in `send()`, VOR MIME-Bau/Dial |
| `src/app/config.py:141,163,212-238` | Datenquelle E2 | `is_test_mode`, `telegram_test_chat_id`, `for_testing()`/`with_user_profile()` setzen `telegram_chat_id` auf `telegram_test_chat_id or telegram_chat_id` — genau diese Fallback-Lücke schließt der Guard |
| `src/app/config.py:30-48` (`is_test_user_id`) | Datenquelle E2 | Name-Heuristik + Profil-Flag `is_test_user` — wirkt bereits VOR dem Guard über `with_user_profile`s `force_test`, kein eigener Aufruf im Guard nötig |
| `src/services/scheduler_dispatch_service.py:273-291` (`_effective_compare_channels`) | Kontext E2 | E-Mail ist bei Compare-Presets IMMER aktiv — es gibt keinen „nur Telegram"-Preset; relevant für die Interlock-Analyse (s. u.) |
| `src/services/notification_service.py:655-668` | Interlock E1×E2 | Telegram-Fehler werden hier per-Kanal fail-soft geschluckt (Issue #1270 AC-5) — ohne gezielte Ausnahme für `OutputConfigError` bleibt ein Guard-Block für E1 unsichtbar, solange E-Mail (immer aktiv) erfolgreich ist |
| `src/services/user_tier.py:6-14` (`sms_allowed`) | Kontext (Known Limitations) | SMS ist über den `tier`-Default (`free`) bereits strukturell eingeschränkt — kein äquivalentes Leck wie bei Telegram |
| `internal/model/test_user.go` | Kontext (Known Limitations) | Go `IsTestUserID`/`IsTestUserIDSubstringOnly` liest das Profil-Flag bewusst NICHT — Asymmetrie zu Python, wird hier NICHT angeglichen (Python bleibt der einzige Versand-Enforcement-Punkt) |

## Implementation Details

### E1 — Compare-Dispatch meldet `failed`

```python
# src/services/dispatch_orchestrator.py — CompareDispatchStrategy
class CompareDispatchStrategy:
    def __init__(self, settings, user_id, data_root=None):
        ...
        self._success = 0
        self._failed = 0  # NEU

    def empty_result(self) -> tuple[int, int]:   # war: -> int: return 0
        return (0, 0)

    def dispatch_one(self, item) -> None:
        ...
        if _dispatch_due_preset(...):
            self._success += 1
        else:
            self._failed += 1  # NEU — _dispatch_due_preset faengt bereits
                                # jede Exception (ValueError/Exception) und
                                # liefert False; Fehler-Isolation bleibt
                                # UNVERAENDERT (kein Abbruch der Schleife)

    def result(self) -> tuple[int, int]:  # war: -> int: return self._success
        return (self._success, self._failed)
```

```python
# src/services/scheduler_dispatch_service.py — run_compare_presets_daily
# Signatur/Docstring: Rueckgabetyp int -> tuple[int, int] (sent, failed).
# Der Funktionskoerper selbst aendert sich NICHT — er delegiert bereits an
# run_briefing_dispatch("vergleich", ...), das jetzt automatisch das neue
# CompareDispatchStrategy.result()-Tupel durchreicht.
```

```python
# api/routers/scheduler.py — trigger_compare_presets_daily (Z. 129-138)
@router.post("/compare-presets-daily")
def trigger_compare_presets_daily(hour: Optional[int] = None, user_id: str = Query(...)):
    sent, failed = run_compare_presets_daily(user_id, hour=hour)
    status = "partial" if failed > 0 else "ok"
    return {"status": status, "count": sent, "failed": failed}
```

Go (`internal/scheduler/scheduler.go:322,344-347`) bleibt **unveraendert** —
es parst `Failed` bereits generisch aus jeder Endpoint-Antwort.

### E2 — Harter Telegram-Guard

```python
# src/output/channels/telegram.py
from output.channels.base import OutputConfigError, OutputError  # OutputConfigError NEU

class TelegramOutput:
    def _guard_test_mode_chat_id(self) -> None:
        """Bedingungsloser Guard (Issue #1288, Vorbild email.py #1219): im
        Test-Modus (is_test_mode=True — gesetzt durch for_testing()/
        with_user_profile() bei Staging ODER is_test_user_id()) ist
        AUSSCHLIESSLICH die konfigurierte Test-Chat-ID erlaubt. Faengt genau
        die Fallback-Luecke aus config.py:225,237 ab: fehlt
        telegram_test_chat_id, bleibt telegram_chat_id sonst unveraendert
        die Prod-ID.
        """
        if not self._settings.is_test_mode:
            return
        test_chat_id = self._settings.telegram_test_chat_id
        chat_id = self._settings.telegram_chat_id
        if not test_chat_id or chat_id != test_chat_id:
            raise OutputConfigError(
                "telegram",
                f"Test-Modus aktiv, aber chat_id={chat_id!r} ist nicht die "
                "konfigurierte Test-Chat-ID (GZ_TELEGRAM_TEST_CHAT_ID) — "
                "Versand blockiert (Issue #1288).",
            )

    def send(self, subject, body, ...):
        self._guard_test_mode_chat_id()  # NEU, erste Zeile im Methodenkoerper —
                                          # VOR jedem httpx.post
        ...
```

Der Guard sitzt zentral in `send()` — jeder Aufrufer (Trip-Briefing,
Compare-Briefing, Alerts, `channel_test_service.py`, Bot-Antworten) profitiert
automatisch, ohne dass ein Aufrufer die Prüfung selbst einbauen müsste
(gleiches Prinzip wie der E-Mail-Guard).

### E2 — Interlock mit E1 (zwingend, sonst wirkungslos für Compare)

`notification_service.py:655-668` fängt in `send_compare_report` JEDE
`Exception` aus dem Telegram-Kanal fail-soft ab (Issue #1270 AC-5, bewusst:
transiente Telegram-Fehler sollen E-Mail/SMS nicht mitreissen). Da E-Mail bei
Compare-Presets **immer** aktiv ist (`_effective_compare_channels`,
Zeile 279-281) und `send_one_compare_preset` den `NotificationResult` gar
nicht auswertet, würde ein Guard-Block **ohne Zusatzänderung** exakt wie ein
transienter Telegram-Fehler geschluckt — `_dispatch_due_preset` sähe Erfolg,
E1s `failed`-Feld bliebe bei 0. Das widerspräche der Zielsetzung „Guard-Block
wird über E1 sichtbar".

Minimal-invasive Lösung: `OutputConfigError` (permanente Fehlkonfiguration,
bisher nirgends aus `TelegramOutput.send` geworfen) wird im Telegram-Zweig
GEZIELT re-raised, statt geschluckt zu werden — transiente `OutputError`
(Netzwerk/Timeout/HTTP-Fehler) bleiben unverändert fail-soft:

```python
# src/services/notification_service.py — send_compare_report, Telegram-Zweig
if "telegram" in effective_channels and self._settings.can_send_telegram():
    try:
        ...
        sent_channels.append("telegram")
    except OutputConfigError:
        raise  # NEU — permanente Fehlkonfiguration darf NICHT im
               # Fail-Soft-Netz verschwinden (Issue #1288/#1290 Interlock)
    except Exception as e:
        logger.error(f"Compare report telegram failed for {subject!r}: {e}")
```

Der re-raiste Fehler propagiert unverändert (kein Fangen in
`send_one_compare_preset`) bis zu `_dispatch_due_preset`
(`scheduler_dispatch_service.py:107-110`), dessen bestehender
`except Exception`-Zweig ihn wie jeden anderen Preset-Fehler fängt und `False`
liefert — E1s neuer `_failed`-Zähler greift dadurch ohne weitere Änderung.

**Bewusst NICHT im Scope:** `notification_service.py`s Trip-Telegram-Zweige
(Zeilen 266-303, `send_trip_report`) bekommen dieselbe `OutputConfigError`-
Sonderbehandlung NICHT — das ist eine separate Rückgabe-/Outcome-Logik
(`_send_trip_report_outcome`), deren Interaktion mit einem Guard-Block hier
nicht auditiert wurde. Ein Trip-Telegram-Guard-Block bleibt nach diesem Fix
möglicherweise ebenso unsichtbar im `#766`-Zähler wie zuvor — das ist eine
bewusste Scope-Grenze, kein Nebenbefund für ein neues Issue (SMS/E-Mail bei
Trip bleiben unberührt zustellbar, kein Datenverlust-/Sicherheitsrisiko).

## Expected Behavior

**E1**
- **Input:** POST `/api/scheduler/compare-presets-daily?user_id=...&hour=...`
- **Output:** `{"status": "ok"|"partial", "count": <int>, "failed": <int>}` —
  identisches Schema zu `/trip-reports`. `status="partial"` GENAU dann, wenn
  `failed > 0` (keine neue Schwelle, 1:1 Trip-Semantik).
- **Side effects:** keine neuen — Fehler-Isolation je Preset (#1207) bleibt
  byte-für-byte unverändert, nur die Zählung/Rückgabe wird ergänzt.

**E2**
- **Input:** `TelegramOutput(settings).send(...)`, `settings.is_test_mode`
  und `settings.telegram_chat_id`/`telegram_test_chat_id` wie vom Aufrufer
  aufgelöst (i. d. R. über `with_user_profile`/`for_testing`).
- **Output:** normaler Versand (message_id) wenn kein Test-Modus ODER
  Test-Modus mit korrekter Test-Chat-ID; `OutputConfigError` (kein HTTP-Call)
  wenn Test-Modus mit abweichender/fehlender Test-Chat-ID.
- **Side effects:** verhindert einen realen Bot-API-Call bei Fehlkonfiguration;
  bei Compare-Presets propagiert dieser Fehler zusätzlich bis in E1s
  `failed`-Zähler (s. Interlock oben).

## Acceptance Criteria

**E1 (#1290)**

- **AC-1:** Given alle fälligen Compare-Presets eines Laufs scheitern
  (z. B. jedes Preset hat nicht auflösbare `location_ids`, analog
  Bestandstest #649) / When der Scheduler `/api/scheduler/compare-presets-daily`
  aufruft / Then liefert die Antwort NICHT mehr `status="ok"`, sondern
  `status="partial"` mit `failed` = Anzahl der fälligen, gescheiterten Presets
  und `count=0` — heute (rot vor Fix) liefert der Endpoint `{"status":"ok","count":0}`
  ohne jeden Hinweis auf den 100%-Ausfall.
  - Test: Fälliges Preset mit garantiert scheiterndem Pfad (leere
    `location_ids` oder kein Empfänger, Vorbild `test_issue_649_compare_daily_dedup.py`)
    anlegen, Endpoint aufrufen, `status`/`count`/`failed` im JSON prüfen.

- **AC-2:** Given ein Lauf mit gemischtem Ausgang (mind. ein erfolgreiches,
  mind. ein gescheitertes fälliges Preset) / When der Endpoint aufgerufen
  wird / Then liefert die Antwort `count` = Anzahl erfolgreicher und `failed`
  = Anzahl gescheiterter Presets, `status="partial"`.
  - Test: zwei fällige Presets (eines auflösbar, eines nicht auflösbar),
    Endpoint-Antwort auf exakte `count`/`failed`-Werte prüfen.

- **AC-3:** Given ein Lauf ohne jeden Fehlschlag (0 gescheiterte Presets,
  inkl. dem Fall „keine fälligen Presets") / When der Endpoint aufgerufen
  wird / Then bleibt `status="ok"` wie bisher und `failed=0` — reiner
  Regressionsschutz, keine neue Schwelle.
  - Test: Bestandstest-Szenarien ohne fällige/mit ausschließlich manuellen
    Presets weiterhin grün, zusätzlich `failed == 0` explizit prüfen.

- **AC-4:** Given drei fällige Presets, von denen eines eine Exception wirft
  (korrupte/nicht auflösbare Daten) / When der Lauf durchläuft / Then werden
  die beiden übrigen Presets trotzdem verarbeitet (Fehler-Isolation #1207
  bleibt unverändert) — das kaputte Preset erhöht nur `failed`, bricht den
  Lauf nicht ab.
  - Test: drei Presets (mittleres bricht), prüfen dass beide intakten Presets
    weiterhin `count` erhöhen und `failed == 1` bleibt, keine Exception nach
    außen dringt.

**E2 (#1288)**

- **AC-5:** Given `Settings.is_test_mode == True` (z. B. Staging oder
  Test-User) UND `telegram_chat_id` zeigt (fälschlich, weil
  `telegram_test_chat_id` fehlt oder abweicht) auf die Prod-Chat-ID / When
  `TelegramOutput.send(...)` aufgerufen wird / Then wird der Versand hart mit
  `OutputConfigError` verweigert — KEIN POST an die Bot-API. Heute (rot vor
  Fix) postet `send()` ungeprüft.
  - Test: Boundary-Sink auf `httpx.post` (Vorbild
    `test_bug599_telegram_persistent.py:94`, `monkeypatch.setattr(httpx, 'post', ...)`)
    registrieren; `Settings` mit `is_test_mode=True` und
    `telegram_chat_id=<Prod-ID>`, `telegram_test_chat_id=""` bauen; `send()`
    aufrufen; `OutputConfigError` erwarten UND belegen, dass der Sink NIE
    aufgerufen wurde. Kein Live-Telegram, kein echter Bot-API-Call.

- **AC-6:** Given Test-Modus UND `telegram_chat_id == telegram_test_chat_id`
  (korrekt konfiguriert) / When `send()` aufgerufen wird / Then funktioniert
  der Versand unverändert (kein Guard-Block) — bestehende
  Staging-/Live-Opt-in-Flows (`GZ_TELEGRAM_LIVE=1`, `tg-live-e2e`-Nutzer)
  bleiben lauffähig.
  - Test: Boundary-Sink liefert eine `ok:true`-Antwort; `Settings` mit
    `is_test_mode=True`, `telegram_chat_id=telegram_test_chat_id=<Test-ID>`;
    `send()` liefert `message_id`, kein `OutputConfigError`.

- **AC-7:** Given ein als Test-Nutzer erkanntes Konto (`is_test_user_id`
  greift — Namens-Heuristik ODER Profil-Flag `is_test_user=True`) mit einer
  im Profil hinterlegten Prod-Chat-ID / When `Settings().with_user_profile(user_id)`
  gebildet und darüber `send()` aufgerufen wird / Then greift dieselbe Sperre
  wie in AC-5 — kein Sonderfall für den profilbasierten Erkennungsweg
  gegenüber dem direkten `is_test_mode`-Flag.
  - Test: echten isolierten Test-User mit `is_test_user=True`-Profil und
    `telegram_chat_id`-Override anlegen, `with_user_profile()` aufrufen,
    `send()` gegen Boundary-Sink prüfen — Block erwarten.

- **AC-8:** Given ein fälliges Compare-Preset im Test-Modus, dessen
  Telegram-Chat-ID vom Guard blockiert wird, während E-Mail (bei Compare
  immer aktiver Kanal) erfolgreich verschickt wird / When der Compare-Daily-
  Lauf dieses Preset verarbeitet / Then propagiert der `OutputConfigError`
  aus dem sonst fail-soften Telegram-Zweig von `send_compare_report` heraus,
  `_dispatch_due_preset` fängt ihn wie jeden anderen Preset-Fehler, und das
  Preset zählt in E1s `failed`-Feld — der Guard-Block bleibt NICHT wie ein
  transienter Telegram-Fehler unsichtbar.
  - Test: `send_one_compare_preset`/`_dispatch_due_preset` mit
    `is_test_mode=True`-Settings aufrufen, deren `telegram_chat_id` auf eine
    Prod-ID zeigt (Compare-Preset mit `send_telegram=True`); Boundary-Sink
    auf `httpx.post` beweist, dass kein realer POST erfolgt; Rückgabe
    `False` bzw. Erhöhung des `failed`-Zählers im umgebenden
    `run_compare_presets_daily`-Aufruf prüfen.

## Bestandstest-Audit (Pflichtabschnitt)

**E1 — MUSS geändert werden** (Rückgabetyp von `run_compare_presets_daily`/
`run_briefing_dispatch("vergleich", ...)` wechselt von `int` auf
`tuple[int, int]`):

| Datei:Zeile | Aktuelle Erwartung | Aktion |
|---|---|---|
| `tests/tdd/test_dispatch_orchestrator.py:226-244` (`test_vergleich_dispatch_returns_compare_count_format`) | `assert result == 0` / `assert not isinstance(result, tuple)` — dokumentiert explizit die #1207-Entscheidung „KEINE Vereinheitlichung mit dem Trip-Tupel" | **MUSS umgestellt werden** auf `result == (0, 0)` / `isinstance(result, tuple)`, analog zum direkt darüberstehenden `test_route_dispatch_returns_trip_tally_format`. Docstring muss die Revision begründen (E1/#1290) — exakt dasselbe Präzedenzmuster wie die 2s-Delay-Revision in derselben Datei (PO-Entscheidung 2026-07-16, dort ebenfalls dokumentiert). Kein stiller Umbau. |
| `tests/tdd/test_issue_461_compare_preset_dispatch.py:239` (`test_manual_presets_are_always_skipped`) | `assert isinstance(count, int)` | Auf `sent, failed = _run_compare_presets_daily(...)` umstellen, `isinstance(sent, int)` + `isinstance(failed, int)` |
| `tests/tdd/test_issue_461_compare_preset_dispatch.py:254` (`test_empty_location_ids_logged_not_crashed`) | `assert isinstance(result, int)` | dito, zusätzlich `failed == 1` als Verhaltensnachweis für den fehlerhaften Preset ergänzen (bisher nur implizit "error_count") |
| `tests/tdd/test_issue_461_compare_preset_dispatch.py:268` (`test_no_daily_presets_returns_zero`) | `assert result == 0` | `assert result == (0, 0)` |
| `tests/tdd/test_issue_461_compare_preset_dispatch.py:280` (`test_missing_presets_file_returns_zero`) | `assert result == 0` | `assert result == (0, 0)` |
| `tests/tdd/test_issue_649_compare_daily_dedup.py:105,131,148,167` | je `assert count == 0` (4×) | je auf `assert count == (0, 0)` umstellen (Rückgabewert bleibt semantisch "keine Erfolge", jetzt als Tupel) |
| `tests/tdd/test_issue_461_compare_preset_dispatch.py:290-319` (Endpoint-Tests `test_endpoint_exists_and_returns_200`, `test_endpoint_count_is_integer`) | `data["status"] == "ok"`, `"count" in data`, `isinstance(resp.json()["count"], int)` | **KEINE Änderung nötig** — `count` bleibt ein `int` (der `sent`-Teil des Tupels), `status` bleibt `"ok"` bei 0 fälligen Presets. Ergänzend könnte `"failed" in data` geprüft werden (optional, kein Rot-Risiko). |

**E2 — Audit ohne Umstellungsbedarf** (grep über alle
`TelegramOutput(`-Konstruktoraufrufe in `tests/`):
`test_952_onset_alert_e2e.py`, `test_issue_671_bot_menu_autoset.py`,
`test_issue_686_telegram_functional_live.py`, `test_issue_1001_telegram_bubbles.py`,
`test_telegram_output.py`, `test_issue_976_telegram_live_truncation.py`,
`test_952_onset_alert_fidelity.py`, `_telegram_live_fixture.py`,
`test_issue_645_telegram_outputerror_arity.py`, `test_issue_650_telegram_foundation.py`,
`test_telegram_html_escaping.py`. In JEDER dieser Dateien wird `Settings(...)`
direkt mit expliziten `telegram_bot_token`/`telegram_chat_id`-Feldern gebaut,
OHNE `is_test_mode=True` zu setzen (Default `False`) — der neue Guard greift
ausschließlich bei `is_test_mode == True` und bleibt daher für alle
bestehenden Tests wirkungslos. Auch `_telegram_live_fixture.py:58-65`
(`staging_live_settings()`, Live-Opt-in-Pfad `GZ_TELEGRAM_LIVE=1`) konstruiert
`Settings` direkt ohne `is_test_mode` und bleibt unberührt.

## Known Limitations

- **Go-Asymmetrie (bewusst, nicht behoben):** `internal/model/test_user.go`
  (`IsTestUserID`) liest das Profil-Flag `is_test_user` NICHT — nur Python
  über `is_test_user_id()` tut das. Python bleibt der alleinige
  Versand-Enforcement-Punkt (Go fasst keine Nutzer-JSONs an); diese
  Asymmetrie besteht unverändert weiter und wird hier NICHT angeglichen.
- **SMS bereits strukturell sicher:** `user_tier.sms_allowed()` gated SMS über
  den `tier`-Default `free` — es gibt kein äquivalentes „Test-Modus schickt an
  Prod"-Leck wie bei Telegram, daher kein SMS-Guard in diesem Fix.
- **Keine Retro-Reparatur historischer `ok`-Läufe:** Die im Prod-Journal
  2026-07-16 dokumentierten 133/133-Fehlschläge bleiben rückwirkend als `ok`
  stehen — E1 wirkt nur auf künftige Läufe.
- **Telegram-Guard-Interlock nur für Compare, nicht für Trip:** Die
  `OutputConfigError`-Sonderbehandlung in `notification_service.py` wird
  gezielt nur im Compare-Zweig (`send_compare_report`) eingebaut. Trips
  Telegram-Zweige (`send_trip_report`, Zeilen 266-303) bekommen sie NICHT —
  ein Trip-Telegram-Guard-Block bleibt daher möglicherweise weiterhin
  unsichtbar im bestehenden `#766`-Fehlerzähler. Bewusste Scope-Grenze
  (kein audit­iertes Nebenbefund-Risiko, kein Datenverlust/Sicherheitsrisiko
  bei Trip — E-Mail/SMS bleiben zustellbar).
- **Guard prüft NICHT `is_test_user_id` direkt:** Der Guard in `TelegramOutput.send`
  liest ausschließlich `settings.is_test_mode` — dieses Flag wird bereits VOR
  dem Guard von `for_testing()`/`with_user_profile()` korrekt aus
  `is_test_user_id()`/`env=="staging"` abgeleitet (AC-7 belegt das). Ein
  direkter `TelegramOutput`-Aufruf mit einem roh, ohne `with_user_profile`
  gebauten `Settings`-Objekt (`is_test_mode=False` per Default, egal welcher
  `user_id` gemeint war) wird vom Guard NICHT erfasst — das ist identisch zum
  bestehenden E-Mail-Guard-Verhalten (Guard prüft Zustand, nicht Herkunft).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Beide Fixes kopieren ein bereits etabliertes Muster
  (E1: Trip-Reports' `{status, count, failed}`-Vorbild aus #766/#1012; E2:
  E-Mails bedingungsloser `OutputConfigError`-Guard aus #1147/#1219/#1235)
  auf eine zweite, bisher ungeschützte/nicht-beobachtete Stelle. Kein neues
  strukturelles Muster, kein neuer Dienst, keine neue Konfigurationsoption.
  Die einzige neue Design-Entscheidung — `OutputConfigError` im
  Compare-Telegram-Fail-Soft-Netz gezielt re-raisen (Interlock E1×E2) — ist
  eine chirurgisch begrenzte Ausnahme von einer bestehenden Regel (#1270
  AC-5), keine neue Architektur.

## Changelog

- 2026-07-18: Initial spec erstellt — Issues #1290 (E1) + #1288 (E2),
  Scheibe E von Epic #1301
