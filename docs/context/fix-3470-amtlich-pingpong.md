# Context: fix-3470-amtlich-pingpong (Issue #3470)

## Request Summary

Prod 27.11.2026: Ein Ortsvergleich (Meteoalarm-Region „Stadt Münster") bekam
7 E-Mail-Alarme zur selben amtlichen Kältewarnung (`extreme_cold`, Stufe 2),
zweimal mit identischer `capture_id` im 30-min-Abstand. Vortage: je eine Mail.

Ursache (Intake, reproduziert, Kommentar in #3470): Meteoalarm liefert dieselbe
Warnung als **zwei gleichzeitig gültige, aneinandergrenzende Perioden**
(A = 12–16 Uhr, B = 16–12 Uhr Folgetag). Seit #1657 zählt Berührung als
Überlappung. Ablauf je Lauf:

1. B nicht im Gedächtnis, berührt gemeldetes A → stille Revision → Aufrufer
   **löscht A** (`del state[stale_key]`) und legt B (mit A's `reported_at`) ab.
2. A (noch im Feed) ist nicht mehr im Gedächtnis; Kandidat B beginnt 4 h später
   → „Vorverlegung ≥ 2 h" → A wird **erneut gemeldet**, nach Zustellung wieder
   eingetragen.
3. Nächster Lauf: B wählt wieder A (jüngeres `reported_at`) als Kandidat → 1.

Feed-Reihenfolge B,A: Meldung in jedem Lauf; A,B: jeder zweite Lauf.
Keine Code-Regression der heutigen Deploys: die Logik ist seit #1685/#1657
(Aug. 2026) so; neu ist die Feed-Form (zwei parallele Nachbarperioden).

## Related Files

- `src/output/renderers/alert/official_alerts.py`
  - `official_alert_revision_verdict()` (~Z. 590–735): Kandidatensuche über
    Präfix Identität+Gefahr, Berührung = Überlappung (`<=`, Z. 665), Auswahl
    max(Stufe, reported_at), Containment+6h-Frische-Guard, Eskalation,
    Vorverlegung ≥ 2 h, sonst `(False, stale_key, merged_entry)`.
  - **Kein exakter Schlüsseltreffer vor der Revisionslogik**: steht der eigene
    Schlüssel im State, kann trotzdem ein anderer Kandidat gewählt werden.
  - `official_alert_state_key()` (Z. 545), `_identity_hazard_prefix()` (Z. 564),
    `official_alert_state_entry()`.
- Aufrufer (geteilter Baustein, beide gleich betroffen):
  - `src/services/compare_official_alert.py:_detect` Z. 485–497 (je Ort eigener State,
    `del state_by_loc[loc_id][stale_key]`), Schreiben nach Zustellung Z. 593.
  - `src/services/trip_alert.py` ~Z. 3270–3284 (`check_official_alert_triggers`),
    Schreiben nach Zustellung `src/services/alert_briefing_anchor.py:360`.
- GC/Entwarnung danach: `prune_expired_official` (`services/alert_state.py`),
  `detect_official_allclear` (`services/official_alert_allclear.py`) — arbeiten
  auf dem fortgeschriebenen Gedächtnis; ein nicht mehr gelöschtes A darf keine
  falsche Entwarnung auslösen, solange A im Feed steht (absent-Logik prüfen).

## Existing Patterns / Specs

- `docs/specs/modules/fix_1685_warnfenster_revision.md` — stille Fenster-Revision
  (PO-Entscheidung 2026-08-10).
- `docs/specs/modules/fix_1657_warnfenster_identitaet.md` — Berührung =
  Überlappung, Containment ohne Vorverlegung, 6h-Frische-Guard
  (PO-Entscheidung 2026-08-17). **Bleibt gültig** für echte Neuausgaben, die das
  alte Fenster ersetzen.
- `docs/specs/modules/rework_1467_s4b_entdopplung.md` — Entdopplung.
- Tests: `tests/tdd/test_official_alert_revision_dedup.py` (29 Tests, reine
  Funktion + Aufrufer), `tests/tdd/test_official_alert_cooldown_entkopplung.py`,
  `tests/helpers/official_alert_gate_fixtures.py`.

## Fix-Richtung (aus Intake, in /20-analyse zu schärfen)

1. Exakter Schlüsseltreffer entscheidet vor der Revisionslogik (nur Eskalation
   meldet).
2. Ein Gedächtnis-Eintrag, dessen Warnung **im selben Lauf selbst noch im Feed**
   steht, darf nicht als `stale_key` verbraucht (gelöscht) werden: die
   Nachbarperiode wird still daneben abgelegt (Fortsetzung derselben Gefahr,
   #1657), ohne A zu entfernen. Dafür braucht der Baustein die Menge der
   aktuellen Feed-Schlüssel (neuer optionaler Parameter, beide Aufrufer).
3. Offene Frage für Analyse: soll B (Folgeperiode, berührt A) still bleiben
   (Berührung = dieselbe durchgehende Gefahr) — ja nach #1657; kein neuer
   Produktentscheid nötig.

## Dependencies / Dependents

- Mandantentrennung unberührt (State je Nutzer über `AlertStateService(user_id=…)`).
- Alle vier Kanäle hängen am selben Melde-Entscheid → Fix wirkt kanalübergreifend.
- Bestands-State in Prod enthält Paare {A, B} bzw. {B mit A-reported_at}: nach
  Fix darf A beim ersten Lauf **nicht** nochmals gemeldet werden, wenn B (mit
  frischem `reported_at`) im Gedächtnis liegt → Migrationsfall bedenken
  (Vorverlegung gegen einen Kandidaten, dessen Gegenstück im Feed steht).

## Risks

- Falsche Stille: echte Vorverlegung/Neuausgabe (alte Periode verschwindet aus
  dem Feed) muss weiter gemeldet bzw. als Revision behandelt werden.
- Entwarnung: nicht gelöschte Nachbareinträge müssen beim Verschwinden korrekt
  entwarnt werden, ohne doppelte Entwarnung pro Periode.
- Reihenfolgeabhängigkeit im Feed (A,B vs. B,A) — Tests müssen beide
  Reihenfolgen und Mehrfachläufe abdecken (mind. 3 Läufe, Nachweis „genau eine
  Meldung").
- Trip- und Vergleichspfad gleich behandeln (geteilter Code).

## Analysis

**Type:** Bugfix (Prod, nutzersichtbar: wiederholte Alarm-Mails, alle Kanäle betroffen).

**Root Cause (bestätigt, Bug-Intake):** `official_alert_revision_verdict` sucht Kandidaten auch dann,
wenn der eigene Schlüssel exakt im State steht; Auswahl max(Stufe, reported_at). Aufrufer löschen den
gewählten Kandidaten (`del state[stale_key]`). Bei zwei gleichzeitig gültigen Nachbarperioden A/B löscht
B das gemeldete A; A (weiter im Feed) wird gegen B als „Vorverlegung ≥ 2 h" neu gemeldet; Zustellung
schreibt A mit frischem `reported_at` → gewinnt wieder als Kandidat. Feed B,A: jeder Lauf; Feed A,B
mit State {A}: jeder zweite. State {A,B} ist stabil; Ping-Pong braucht State mit nur einer Periode.
Zweitbefund: `build_official_allclear_notices` (official_alerts.py ~Z.2691) entdoppelt nicht → liegen
A und B im Gedächtnis und verschwinden beide, entstehen zwei gleiche Entwarnungen.

**Affected Files:**
| Datei | Change | Inhalt |
|---|---|---|
| `src/output/renderers/alert/official_alerts.py` | MODIFY | Revision: exakter Treffer zuerst; `feed_keys`-Parameter; `stale_key=None`-Vertrag; Randberührungs-Unterdrückung der Vorverlegung; Entwarnungs-Entdopplung im Notice-Builder |
| `src/services/trip_alert.py` (~Z.3270) | MODIFY | `feed_keys` aus `tagged_alerts`, `pop(stale_key)` nur wenn gesetzt |
| `src/services/compare_official_alert.py` (~Z.485) | MODIFY | `feed_keys` **je Ort**, `pop(stale_key)` nur wenn gesetzt |
| `tests/tdd/test_fix_3470_*.py` | CREATE | Mehrlauf-Simulation (beide Reihenfolgen, Start {A}, {B*}, {}), Trip + Vergleich, Entwarnung |
| `docs/specs/modules/fix_3470_*.md` | CREATE | neue Spec (Nachtrag-Verweis aus fix_1657/fix_1685) |

**Scope/Risk:** ~50 Prod-LoC, ~150 Test-LoC, 3 Quelldateien. Risiko mittel-niedrig: geteilter
Melde-Entscheid aller vier Kanäle; `feed_keys=None` = altes Verhalten (Bestandstests grün).

**Technical Approach (V2, Plan-Agent-Empfehlung, übernommen):**
1. Exakter Schlüsseltreffer (`prev` gesetzt) → `_exact_match_verdict()` (nur Eskalation meldet), keine Kandidatensuche, kein Merge.
2. `feed_keys: frozenset[str] | None = None`. Ist der gewählte Kandidat in `feed_keys`, wird er NICHT gelöscht: Rückgabe `(False, None, merged_entry)` → Aufrufer legt nur neuen Eintrag ab (`if stale_key: state.pop(stale_key, None)`).
3. Vorverlegung wird unterdrückt, wenn Kandidat in `feed_keys` UND reine Randberührung (`alert_vt == cand_vf` oder `cand_vt == alert_vf` nach `_as_aware_utc`, im geschützten try-Block, F001). Echte Neuausgabe (Kandidat nicht mehr im Feed) und echte Innenüberlappung melden weiter wie bisher. Verhindert auch den letzten Doppel-Alarm nach Deploy (Bestandsstate {B mit A.reported_at}, Feed A,B).
4. Eskalation meldet weiterhin immer (auch bei Nachbarn).
5. Vergleich: `feed_keys_by_loc[loc_id]` aus `deduped` über `loc_ids` (nie global).
6. Entwarnungen im Notice-Builder nach Identität+Gefahr(+Ort/Quelle) entdoppeln (old_rank max, new_rank min); `ac`-Liste/State-Senkung unverändert.

Varianten verworfen: V0 nur exakter Treffer (Ping-Pong bleibt bei Feed B,A), V1 ohne Randberührungs-Regel (ein Doppel-Alarm nach Deploy), V3 Vereinigungseintrag (ändert Schlüsselmodell), V4 ohne feed_keys (State-Flackern, schluckt echte Neuausgaben).

**Dependencies:** Entwarnung (`detect_official_allclear`, `_touches` mit `<=`): Nachbar im Feed hält Eintrag „present" → keine falsche Entwarnung. `prune_expired_official` je Eintrag nach `valid_to` → unkritisch. Mandantentrennung unberührt.

**Bekannte, bewusst nicht geänderte Fälle:** Erstauftritt mit leerem State und A+B im selben Lauf → eine Meldung mit beiden Perioden (kein Ping-Pong, Ist-Verhalten). Totes Gedächtnis Z (berührt, nicht im Feed) verfällt per Prune.

**Open Questions:** keine Produktfrage — PO-Entscheidungen #1657 (Berührung = dieselbe Gefahr) und #1685 (stille Revision bei Neuausgabe) bleiben unverändert und werden nur auf den Fall „beide Perioden gleichzeitig im Feed" konsequent angewandt.

## TDD RED (Phase 5) — Hinweise für die Implementierung

- RED: `tests/tdd/test_fix_3470_amtlich_nachbarperioden.py`, 17 rot / 7 grün (grün = Regressionsschutz AC-3, AC-6 Eskalation, AC-8 Herabstufung B,A, AC-9, AC-10 ohne Fenster). Beleg: `docs/artifacts/fix-3470-amtlich-pingpong/test-red-output.txt`.
- Trip-Uhr nicht injizierbar (`check_official_alert_triggers` setzt `now_utc` intern) → Trip-Perioden relativ zur Wanduhr. Vergleich: Modul-`datetime` in `compare_official_alert` eingefroren und je Lauf +15 min (`_VergleichsUhr`).
- `feed_keys` Trip: `frozenset(official_alert_state_key(a) for a, _ in tagged_alerts)` nach `dedupe_official_alerts`.
- `feed_keys` Vergleich: je Ort aus `deduped` über `loc_ids` (dedupe fasst orteübergreifend zusammen); global gebildet → AC-7 rot.
- AC-8: Entdopplung im Notice-Builder `build_official_allclear_notices` (Trip: `(allclears)`, Vergleich: `([ac for ac, _ in pending], id_to_name)`).
- AC-10 naive Zeitstempel: Randberührungs-Prüfung nach `_as_aware_utc` vergleichen.
