---
entity_id: fix_1752_radar_folgt_alarm_kanaelen
type: module
created: 2026-08-12
updated: 2026-08-12
status: draft
version: "1.0"
tags: [radar, nowcast, alarm, channel, trip, alert_rules]
---

<!-- Issue #1752 -- Scheibe B zu #1745 (Scheibe A: Premium-SMS in der
     Alarm-Kanal-Auswahl, live seit c28f794b). Kontext-Grundlage:
     docs/context/fix-1752-radar-folgt-alarm-kanaelen.md (Phase 1+2
     zusammengefuehrt, Basis-Commit bc7dc418). Formatvorbild:
     docs/specs/modules/fix_1745_a_alarm_kanal_premium_sms_ui.md. -->

# Radar-/Regen-Alarme folgen dem Alarm-Kanal-Satz (Scheibe B zu #1745)

## Approval

- [x] Approved — PO, 2026-08-12 („freigabe", Klartext). Freigegeben ist der Wortlaut dieser
  Fassung mit sieben Kriterien, einschließlich der drei ausdrücklich benannten Folgen:
  SMS kommt für Regen-Alarme des KHW-Trips hinzu (Schwelle `HIGH`), Regen-Alarme gehorchen
  künftig auch einzelnen Alarm-Regeln (D4), und das Alarm-Protokoll bekommt Einträge, wo bisher
  spurlos abgebrochen wurde (D5).

## Purpose

Regen-/Radar-Alarme lösen ihre Kanäle heute **ausschließlich** aus dem Trip-Briefing
(`trip.report_config`) auf und lesen `trip.alert_channels`/`trip.alert_rules` nie. Wer im
Alarme-Reiter Kanäle abweichend vom Briefing einstellt oder eine Alarm-Regel mit eigenem
Kanal anlegt, ändert damit für Regen-Alarme **nichts** — das betrifft alle vier Kanäle, nicht
nur Premium-SMS. Diese Scheibe stellt Regen-Alarme auf denselben Auflösungsweg um, den
Gewitter-, Änderungs- und amtliche Alarme bereits nutzen (`_effective_alert_channels()`), und
schließt damit die letzte abweichende Stelle im Trip-Alarmsystem.

## Bewusst nicht in dieser Scheibe

- **Der Ortsvergleich.** Der Compare-Radar-Pfad wurde bereits mit #1461 S3b-2b auf den
  regulären Compare-Kanal-Resolver (`effective_compare_channels()`) umgestellt — siehe
  ADR-0021, Nachtrag 2026-08-06. Diese Scheibe zieht ausschließlich den Trip-Pfad nach.
- **Die Oberfläche.** Der Alarme-Reiter kennt Premium-SMS bereits seit #1745 Scheibe A
  (`c28f794b`, live). Diese Scheibe ändert kein Frontend — sie sorgt nur dafür, dass ein dort
  gesetzter Haken auch für Regen-Alarme wirkt, nicht nur für Gewitter-/Änderungs-/amtliche
  Alarme.
- **Der Horizont-Guard selbst und die Segmentwahl** (`trip_alert.py:908-951`, Issue #1697/#822/
  #1667 S3). Bleiben unverändert; die Kanalberechnung wird lediglich **hinter** den Guard
  gehängt (D3), nicht in ihn eingegriffen.
- **Ein Wrapper, der die bisherige `can_send_*()`-Vorfilterung erhält.** Ausdrücklich
  verworfen: er würde die Duplikat-Falle nur verschieben, nicht schließen — genau der Zustand,
  der diesen Bug erzeugt hat (zwei leicht unterschiedliche Kanal-Ableitungen für denselben
  Trip).

## Source

- **File:** `src/services/trip_alert.py`
- **Identifier:** `class TripAlertService`, Methode `check_radar_alerts()` (Aufrufer),
  Methode `_radar_effective_channels()` (entfällt), Methode `_effective_alert_channels()`
  (Zielfunktion, unverändert)

Betroffene Stellen (Zeilen gemessen gegen Basis-Commit `bc7dc418`):

| Zeile(n) | Heute | Nach dieser Scheibe |
|---|---|---|
| `trip_alert.py:826-856` | `_radar_effective_channels()` — löst **nur** aus `report_config` auf | entfällt ersatzlos |
| `trip_alert.py:936-951` | Horizont-Guard (#1697 AC-4) | unverändert, bleibt VOR der Kanalberechnung |
| `trip_alert.py:953` (neu davor) | — | neue lokale Variable `effective_channels = self._effective_alert_channels(trip)` |
| `trip_alert.py:987` | `effective_channels=self._radar_effective_channels(trip)` im Unterdrückungs-Protokoll | `effective_channels=effective_channels` (geteilte Variable) |
| `trip_alert.py:1061` | `if not self._radar_effective_channels(trip):` | `if not effective_channels:` |
| `trip_alert.py:1109` | `effective_channels = self._radar_effective_channels(trip)` | Zeile entfällt (Wert bereits vorhanden) |
| `trip_alert.py:1111-1113` | zweiter Leer-Check (nachgemessen toter Code, s. Kontextdokument) | entfällt |
| `trip_alert.py:1123-1125` | `split_by_threshold(effective_channels, ...)` | unverändert — liest jetzt die geteilte Variable statt des dritten `_radar_effective_channels()`-Aufrufs |

## Estimated Scope

- **LoC (Produktivcode):** ≈ -35 netto in `trip_alert.py` (eine ~31-zeilige Methode entfällt
  vollständig, eine Zuweisung wandert an eine neue Stelle, zwei Aufrufstellen werden auf die
  geteilte Variable umgehängt, ein toter Leer-Check entfällt — die Datei schrumpft).
- **LoC (Tests):** ≈ 280 NEU (eine neue Testdatei, sieben Tests + Testaufbau; **keine**
  bestehende Testdatei wird verändert — R1 im Kontextdokument bestätigt, dass keine der 30
  Testdateien, die `check_radar_alerts()` aufrufen, `alert_channels`/`alert_rules` setzt).
- **Files:** 1 MODIFY (`src/services/trip_alert.py`) + 1 CREATE
  (`tests/unit/test_radar_alert_channel_resolution.py`).
- **Effort:** low-medium. Die Produktivcode-Änderung ist reine Konsolidierung (die
  Zielfunktion `_effective_alert_channels()` existiert bereits und wird nicht verändert) — der
  eigentliche Aufwand liegt in der Testabdeckung der bislang komplett unbelegten Kombination
  „Radar + `alert_channels`/`alert_rules`" (R1).
- **LoC-Limit-Hinweis:** Produktiv- und Testzeilen zusammen dürften das Default-Limit
  250/Workflow überschreiten (Tests allein ≈ 280 Zeilen) — `loc_limit_override` bei
  Implementierungsbeginn wahrscheinlich nötig, endgültige Zahl erst nach der TDD-RED-Phase
  sicher.
- **Risiko:** LOW für die Produktivänderung selbst (reines Umhängen auf eine bereits geprüfte
  Funktion). MEDIUM für die Testarbeit — die Blindstelle R1 bedeutet, dass ein grüner
  Bestandslauf nichts beweist (s. „Warum ein grüner Testlauf hier nichts beweist" unten).

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `docs/specs/modules/feat_1701_alarm_premium_sms.md` | Vorgänger-Spec, live | `_effective_alert_channels()` ist bereits die Zielfunktion für Gewitter-/Änderungs-/amtliche Alarme — wird hier NICHT verändert, nur an eine vierte Stelle angeschlossen |
| `docs/specs/modules/fix_1745_a_alarm_kanal_premium_sms_ui.md` | Vorgänger-Scheibe (Scheibe A), live seit `c28f794b` | Oberfläche schreibt bereits `alert_channels`/`alert_rules[].channels` inkl. `premium_sms` — diese Scheibe schließt den Radar-Pfad an denselben Datenbestand an |
| `docs/adr/0021-shared-deviation-alert-engine.md` | ADR (Nachtrag, keine neue) | Compare-Radar-Präzedenz (#1461 S3b-2b, Nachtrag 2026-08-06) — dieselbe Umstellung, andere Fläche |
| `docs/adr/0046-alarm-kanal-schwelle.md` | ADR | Schwellenpflicht — bleibt erfüllt, `split_by_threshold` sitzt unverändert auf der (jetzt geteilten) Variable |
| `tests/helpers/nowcast_gate_fixtures.py::make_trip/settings_no_channel_reachable/read_log/entries_for/write_user_tier` | Test-Baustein, ungeändert wiederverwendet | Trip-Skelett + Log-Lesehelfer für alle sieben neuen Tests |
| `tests/unit/test_alert_channel_premium_sms.py` | Muster (nicht importiert) | Vorbild für den „ausschließlich neuer Weg"-Testaufbau (Schritt-0-Guard-Lehre, s.u.) |
| `src/services/alert_log.py::append_entry/_channels_not_sent` | module, gelesen, nicht verändert | liefert die beobachtbare Kanal-Klassifikation (`channel_disabled`/`delivery_failed`/`below_channel_threshold`), auf der alle sieben ACs aufsetzen |

## Implementation Details

### Diff-Plan (eine Datei, `src/services/trip_alert.py`)

1. `_radar_effective_channels()` (`:826-856`) vollständig löschen.
2. In `check_radar_alerts()` unmittelbar **nach** dem Horizont-Guard (`:936-951`, D3) und
   **vor** dem `check_nowcast_gate(...)`-Aufruf (`:963-973`) eine lokale Variable einführen:
   `effective_channels = self._effective_alert_channels(trip)`.
3. `:987` (Unterdrückungs-Protokoll): `effective_channels=self._radar_effective_channels(trip)`
   → `effective_channels=effective_channels`.
4. `:1061` (erster Leer-Check, bleibt bestehen — nur die zweite Stelle ist tot):
   `if not self._radar_effective_channels(trip):` → `if not effective_channels:`.
5. `:1109`: die Zeile `effective_channels = self._radar_effective_channels(trip)` entfällt
   ersatzlos (Wert liegt bereits aus Schritt 2 vor).
6. `:1111-1113` (zweiter Leer-Check): entfällt ersatzlos — nachgemessen toter Code (reine
   Funktion, `trip` bleibt zwischen den beiden Checks unverändert, Docstring sagt es selbst).
7. `:1123-1125` (`split_by_threshold`) bleibt strukturell unverändert — liest jetzt dieselbe,
   einmalig berechnete Variable statt eines dritten Funktionsaufrufs.

Kein zweiter Aufrufort in der Codebasis ruft `_radar_effective_channels()` auf (per Grep
bestätigt); die Löschung ist folgenlos für andere Module. Ein Docstring-Verweis in
`docs/features/architecture.md` erwähnt die Methode namentlich — das ist eine Doku-, keine
Code-Referenz (s. Known Limitations).

### Testaufbau (Muster für alle sieben neuen Tests)

- Trip-Skelett über `tests.helpers.nowcast_gate_fixtures.make_trip()` — die Etappe deckt
  bereits den ganzen Tag ab (00:00–23:59 an `TRIP_LAT`/`TRIP_LON`, UTC±0), der Horizont-Guard
  greift daher nicht. `alert_channels`/`alert_channel_thresholds`/`alert_rules` werden auf dem
  zurückgegebenen `Trip`-Objekt **direkt gesetzt** — `make_trip()` selbst braucht dafür KEINE
  Erweiterung (nachgemessen: `Trip.alert_channels` ist ein normales, nach Konstruktion
  beschreibbares Feld, `tests/unit/test_alert_channel_premium_sms.py::_base_trip` nutzt exakt
  dasselbe Muster).
- Der Trip wird **nicht** über `save_trip()`/Disk-Rundlauf eingespeist — `save_trip()`
  serialisiert `alert_channels`/`alert_rules`/`alert_channel_thresholds` nicht (nachgemessen,
  `nowcast_gate_fixtures.py:405-434`). Stattdessen: `monkeypatch.setattr(app.loader,
  "load_all_trips", lambda **kw: [trip])` — dasselbe Muster wie
  `test_alert_channel_premium_sms.py`.
- **Kanal-Erreichbarkeit wird bewusst NICHT über echte Transport-Stubs geprüft**, sondern über
  die im Alarm-Protokoll persistierte Kanal-Klassifikation (`channels_not_sent`, s.
  `alert_log.py:113-137`): jeder der vier Kanäle bekommt dort **immer** einen Eintrag mit
  Grund `channel_disabled` (nicht im rohen Opt-in enthalten), `delivery_failed` (im Opt-in,
  aber technisch nicht zugestellt) oder `below_channel_threshold` (im Opt-in, aber unter der
  Dringlichkeits-Schwelle). Diese Dreiteilung erlaubt, „wurde der Kanal korrekt AUFGELÖST"
  von „wurde er tatsächlich ZUGESTELLT" zu trennen, ohne Stub-Server — genau die Trennung, die
  die sieben ACs brauchen. `settings_no_channel_reachable()` macht dabei bewusst **gar keinen**
  Kanal technisch erreichbar: ob überhaupt ein Protokoll-Eintrag entsteht, hängt dadurch
  ausschließlich von der Kanal-**Auflösung**, nie von einem zufällig passierbaren
  Erreichbarkeits-Nebenpfad ab (Lehre aus „Schritt 0" unten).
- **`write_user_tier(uid, "standard")` ist Pflicht** vor jedem Testlauf, der den Kanal `sms`
  im Ergebnis erwartet — `sms_allowed()` liefert `False`, solange kein `user.json` existiert
  (`user_tier.py:9-20`); ohne diesen Schritt filtert das SMS-Tier-Gate den Kanal am Ende von
  `_effective_alert_channels()` still wieder heraus, unabhängig vom Testergebnis, das eigentlich
  geprüft werden soll.
- **`reset_radar_cache()` zwischen Tests**, sofern mehrere Tests dieselbe Koordinate
  (`TRIP_LAT`/`TRIP_LON`) verwenden — der Frame-Cache ist ein Prozess-Singleton mit 300s TTL
  (Vorbild `test_nowcast_suppression_logging.py`).
- **Lehre aus „Schritt 0"** (`test_alert_channel_premium_sms.py:298-376`, s. auch Kontextdokument
  „Was die Analyse übersehen hatte"): mindestens ein Test dieser Spec (AC-1, AC-6) darf sich
  NICHT auf einen zufällig ebenfalls konfigurierten, technisch erreichbaren Zweitkanal
  verlassen, der einen vorgelagerten Guard passierbar macht. Deshalb `settings_no_channel_reachable()`
  als Standard-Settings für alle Kanal-Auflösungs-Tests — kein Kanal ist je zufällig
  "mit-erreichbar".

  🔴 **Ausnahme AC-5, in der RED-Phase gemessen und korrigiert (2026-08-12).** Mit
  `settings_no_channel_reachable()` liefert auch die **alte** Ableitung ein leeres Set, der Trip
  bliebe still, und AC-5 wäre **strukturell grün, ohne irgendetwas zu bewachen** — per Sonde
  nachgewiesen (1 passed vor jeder Änderung). AC-5 läuft deshalb mit `settings_email_only()`:
  erst wenn das Briefing technisch erreichbar ist, wird der geprüfte Widerspruch „Briefing an,
  Alarme-Reiter komplett aus" überhaupt sichtbar. Das deckt sich mit dem Given der AC („das
  Trip-Briefing ist davon unberührt"); die Pflichtnennung oben gilt ausdrücklich nur AC-1/AC-6.
  **Merksatz: ein Test, der nicht rot werden KANN, ist kein Nachweis.**

## Entscheidungen (D1–D6)

- **D1 — Ein Auflösungsweg.** Radar folgt `trip.alert_channels` wie alle anderen Alarmtypen;
  Fallback auf die Briefing-Kanäle (`_briefing_channels(report_config)`) nur, wenn
  `alert_channels` **nie gesetzt** wurde (`None`). Kein Einfrieren des Ist-Zustands, keine
  Migration — Bestandstrips ohne je gespeicherte Alarme-Reiter-Auswahl verhalten sich
  unverändert (AC-2).
- **D2 — Kanal-Set einmal berechnen.** Eine lokale Variable, **nach** dem Horizont-Guard
  (`:936-951`), wiederverwendet an allen drei bisherigen Aufrufstellen. Der zweite Leer-Check
  (`:1111-1113`) entfällt — nachgemessen toter Code (reine Funktion ohne Seiteneffekt zwischen
  beiden Checks, Docstring bestätigt es selbst).
- **D3 — Der Horizont-Guard bleibt vorgelagert.** Die Kanalberechnung darf **nicht** vor
  `:936-951` gezogen werden, sonst wird für zeitlich irrelevante Segmente die
  `alert_rules`-Union unnötig ausgewertet. Kein eigener Test in dieser Spec (s. Known
  Limitations) — Absicherung ist Code-Review, das Endergebnis für ein zeitlich aktives Segment
  wäre bei vertauschter Reihenfolge identisch.
- **D4 — Radar erbt die `alert_rules`-Union mit.** Das ist eine echte Bedeutungserweiterung
  über „Quelle wechseln" hinaus (AC-7) — jede Alternative (eigene Fassung ohne Regel-Teil)
  wäre die zweite, leicht abweichende Kopie, die diese Scheibe beseitigt.

  🔴 **Präzisierung, in der RED-Phase aufgefallen und am Code nachgemessen
  (`trip_alert.py:1534-1542`, 2026-08-12).** Die Regel-Kanäle **ergänzen** den Alarme-Reiter
  nicht, sie **ersetzen** ihn je Regel:

  ```
  ohne aktive Regeln          → Alarme-Reiter (bzw. Briefing-Fallback)
  mit aktiven Regeln          → Union ÜBER DIE REGELN, je Regel:
        Regel hat eigene Kanäle  → diese
        Regel hat keine          → Alarme-Reiter
  ```

  Folge: Der Alarme-Reiter-Anteil fällt **nur dann vollständig weg, wenn ALLE aktiven Regeln
  eigene Kanäle tragen**. Hat auch nur eine Regel keine, bleibt er über diese erhalten. Der
  RED-Bericht formulierte das zu grob („bei mindestens einer Regel mit Kanälen wird der geerbte
  Anteil komplett verworfen") — das gilt nur bei genau einer aktiven Regel, wie im Test-Aufbau.
  **Wer „Union aus Alarme-Reiter + Regel" liest, baut etwas anderes.**

  Für den KHW-Trip folgenlos: vier aktive Regeln, **alle** mit leerer Kanalliste ⇒ Ergebnis ist
  exakt der Alarme-Reiter. Die Semantik ist vorbestehend (#638) und wird hier **nicht** geändert
  — Radar übernimmt sie nur mit.
- **D5 — Zustellung ändert sich nicht, Beobachtbarkeit schon.** `_dispatch_alert_message`
  wiederholt `can_send_*()` (`notification_service.py:1388,1404,1485`), Premium-SMS bewusst
  ohne Vorprüfung (`:1499`). Wo heute `:1061` **ohne** Protokolleintrag abbricht (weil die alte
  Funktion Erreichbarkeit bereits Teil der Auflösung macht), entsteht nach dieser Scheibe ein
  `alert_log`-Eintrag mit leerem `sent_channels` (AC-6) — eine gewollte
  Nachvollziehbarkeits-Verbesserung, kein neuer Defekt.
- **D6 — Kein neues ADR.** Nachtrag zu ADR-0021; Präzedenz ist #1461 S3b-2b, wo dieselbe
  Umstellung im Ortsvergleich bereits ohne neue ADR vollzogen wurde. ADR-0046
  (Schwellenpflicht) bleibt erfüllt: `split_by_threshold` sitzt unverändert bei `:1123-1125`
  auf derselben (jetzt geteilten) Variable.

## Expected Behavior

- **Input:** Ein Nutzer hat im Alarme-Reiter eines Trips eine Kanal-Auswahl und/oder
  Dringlichkeits-Schwellen gesetzt, die vom Trip-Briefing abweichen — oder eine Alarm-Regel mit
  eigenem Kanal angelegt. Ein Regenradar-Alarm wird für diesen Trip ausgelöst
  (`check_radar_alerts()`, Scheduler-getrieben).
- **Output:** Der Regen-Alarm berücksichtigt dieselbe Kanal-Auswahl, die auch Gewitter-,
  Änderungs- und amtliche Alarme berücksichtigen — inklusive der Dringlichkeits-Schwelle je
  Kanal und der Kanal-Overrides einzelner Alarm-Regeln. Hat der Nutzer den Alarme-Reiter nie
  angefasst, verhält sich der Regen-Alarm unverändert wie bisher (Briefing-Fallback, D1).
- **Side effects:** Das Alarm-Protokoll (`alert_log.json`) enthält für Regen-Alarme ab jetzt
  auch Einträge für Kanäle, die im Alarme-Reiter aktiv, aber technisch (noch) nicht erreichbar
  sind (D5) — vorher brach der Lauf an dieser Stelle spurlos ab. Kein Feld-Schema-Wechsel, keine
  Migration, keine Änderung am Ortsvergleich oder an der Oberfläche.

## Acceptance Criteria

- **AC-1:** Given ein Nutzer hat im Alarme-Reiter eines Trips die Kanäle abweichend vom
  Trip-Briefing eingestellt — Telegram ist im Briefing aktiv, im Alarme-Reiter aber bewusst
  ausgeschaltet, dafür SMS im Alarme-Reiter angeschaltet / When ein Regen-Alarm für diesen Trip
  ausgelöst wird / Then richtet sich der Regen-Alarm nach der Alarme-Reiter-Einstellung — er
  berücksichtigt SMS, nicht Telegram — genau wie Gewitter-, Änderungs- und amtliche Alarme das
  bereits heute tun.
  - Prüfort: das persistierte Alarm-Protokoll (`alert_log.json`) — konkret die
    Kanal-Aufschlüsselung des Eintrags (`channels_not_sent`), nicht nur der Rückgabewert einer
    internen Funktion. Settings ohne jeden erreichbaren Kanal (`settings_no_channel_reachable()`),
    damit kein zufällig erreichbarer Zweitkanal die Aussage verwässert.
  - Test: `tests/unit/test_radar_alert_channel_resolution.py::test_radar_alert_channels_override_report_config_when_alert_channels_set` (neu)
  - Mutation: Radar liest weiterhin (auch nur teilweise) `report_config` statt ausschließlich
    der aus `alert_channels` abgeleiteten Menge — Telegram erschiene dann mit Grund
    `delivery_failed` (= "war konfiguriert") statt `channel_disabled` (= "war ausgeschaltet").

- **AC-2:** Given ein Bestandstrip hat im Alarme-Reiter NIE eine eigene Kanal-Auswahl
  gespeichert (`alert_channels` ist technisch ungesetzt) und im Trip-Briefing ist Telegram
  aktiv / When ein Regen-Alarm ausgelöst wird / Then verhält sich der Regen-Alarm wie bisher —
  er übernimmt die Briefing-Kanäle als Ersatzwert, für diesen Bestandstrip ändert sich nichts.
  - Prüfort: Alarm-Protokoll, Kanal-Aufschlüsselung — Gegenprobe zu AC-1 (Fallback statt
    Override).
  - Test: `tests/unit/test_radar_alert_channel_resolution.py::test_radar_alert_channels_fall_back_to_briefing_when_alert_channels_unset` (neu)
  - Mutation: der Fallback bei `alert_channels is None` bricht (z.B. weil der neue Code
    fälschlich ein leeres Dict statt der echten Fallback-Kette annimmt) — Telegram erschiene
    trotz aktivem Briefing-Flag als `channel_disabled`.

- **AC-3:** Given ein Nutzer hat im Alarme-Reiter für SMS eine hohe Dringlichkeits-Schwelle
  eingestellt (nur "hoch" soll durchkommen) und SMS als Regen-Alarm-Kanal aktiviert / When ein
  Regen-Alarm mit NIEDRIGER Dringlichkeit (leichter, nicht-konvektiver Regen) ausgelöst wird /
  Then wird SMS nicht tatsächlich angesteuert — im Protokoll erscheint SMS als "unter der
  eingestellten Schwelle", nicht als "ausgeschaltet" oder "technisch fehlgeschlagen": ein
  Nutzer, der SMS bewusst nur für dringende Fälle reserviert hat, bekommt bei geringer
  Dringlichkeit korrekt keine SMS — die Schwelle wirkt weiterhin, auch nach der Umstellung.
  - Prüfort: `channels_not_sent`-Grund des SMS-Eintrags im Alarm-Protokoll
    (`REASON_BELOW_THRESHOLD`).
  - Test: `tests/unit/test_radar_alert_channel_resolution.py::test_radar_alert_below_threshold_channel_uses_shared_channel_set` (neu)
  - Mutation: die Dringlichkeits-Schwelle wird weiterhin auf dem alten,
    Briefing-basierten Kanal-Set angewendet statt auf die aus dem Alarme-Reiter aufgelöste
    Menge — SMS taucht dann gar nicht als "aktiv, aber unter Schwelle" auf, sondern als
    `channel_disabled` (die Schwellen-Prüfung läuft ins Leere, weil SMS dort nie ankommt).

- **AC-4:** Given ein Regen-Alarm wird durch die Ruhezeit blockiert, BEVOR überhaupt ein
  Wetterabruf stattfindet, und ein Kanal ist ausschließlich über den Alarme-Reiter (nicht über
  das Briefing) aktiviert / When diese Unterdrückung protokolliert wird / Then zeigt der
  Unterdrückungs-Eintrag denselben Kanal, den ein tatsächlicher Versand angesteuert hätte — das
  Unterdrückungs-Protokoll und der eigentliche Versand dürfen nicht auf unterschiedlichen
  Kanal-Listen beruhen.
  - Prüfort: `not_delivered`-Eintrag mit `reason="nowcast"` und Gate-Grund "Ruhezeit" im
    Alarm-Protokoll — die Stelle VOR dem eigentlichen Versand (`:987`), nicht der Versand
    selbst.
  - Test: `tests/unit/test_radar_alert_channel_resolution.py::test_radar_alert_suppressed_entry_matches_dispatch_channel_set` (neu)
  - Mutation: nur die Versand-Stelle (`:1061`/`:1109`) wird auf die geteilte Variable
    umgestellt, die Unterdrückungs-Protokollierung (`:987`) bleibt bei der alten (entfernten
    oder erneut kopierten) Auflösung — bei blockierter Ruhezeit entsteht dann entweder gar kein
    Eintrag oder ein Eintrag mit einem anderen Kanal als dem, den der Versand angesteuert
    hätte.

- **AC-5:** Given ein Nutzer hat im Alarme-Reiter ALLE vier Kanäle für Alarme ausgeschaltet,
  das Trip-Briefing ist davon unberührt / When ein Regen-Alarm ausgelöst würde / Then bleibt
  der Trip vollständig still — kein Protokoll-Eintrag, keine Sperrzeit wird in Gang gesetzt;
  ein bewusst stummgeschalteter Trip erzeugt kein Rauschen im Archiv.
  - Prüfort: Alarm-Protokoll (kein Eintrag für diese Trip-Kennung, weder `entries` noch
    `not_delivered`) UND die Sperrzeit-Ablage (`throttle_state.json`, Scope `radar`) — beide
    müssen unverändert bleiben.
  - Test: `tests/unit/test_radar_alert_channel_resolution.py::test_radar_alert_stays_silent_when_all_trip_channels_off` (neu)
  - Mutation: der jetzt entfernte, zweite Leer-Check (`:1111-1113`) wird gestrichen, dabei aber
    versehentlich der verbliebene erste Leer-Check (`:1061`) auf eine andere (nicht-geteilte)
    Variable umgehängt — trotz vollständig ausgeschalteter Kanäle entstünde dann ein Eintrag
    und/oder ein Sperrzeit-Eintrag.

- **AC-6:** Given ein Nutzer hat im Alarme-Reiter einen Kanal für Regen-Alarme aktiviert, der
  gerade technisch nicht erreichbar ist (z.B. kein Telegram-Bot hinterlegt) / When ein
  Regen-Alarm ausgelöst wird / Then hinterlässt der Versuch einen nachvollziehbaren
  Protokoll-Eintrag ("Kanal war aktiv, aber technisch nicht erreichbar") statt spurlos zu
  verschwinden wie bisher — eine gewollte Verbesserung der Nachvollziehbarkeit (D5), kein neuer
  Fehler.
  - Prüfort: `not_delivered`-Eintrag mit Kanal-Grund `delivery_failed` statt `channel_disabled`
    im Alarm-Protokoll. Settings ohne jeden erreichbaren Kanal
    (`settings_no_channel_reachable()`) — derselbe "Schritt 0"-Aufbau wie bei AC-1, hier aber
    als Nachweis, dass die neue Auflösung NICHT mehr selbst nach Erreichbarkeit filtert.
  - Test: `tests/unit/test_radar_alert_channel_resolution.py::test_radar_alert_logs_configured_but_unreachable_channel` (neu)
  - Mutation: die Kanal-Auflösung prüft weiterhin (wie die alte, entfernte Funktion) selbst die
    technische Erreichbarkeit als Teil der Auflösung, statt das dem Versand zu überlassen — der
    Kanal gälte dann schon an der Auflösungsstelle als "aus", der erste Leer-Check (`:1061`)
    bräche wieder wortlos ab, kein Eintrag entstünde.

- **AC-7:** Given ein Trip hat eine aktive Alarm-Regel mit einem eigenen, vom
  Standard-Kanalsatz abweichenden Kanal (z.B. nur SMS für genau diese Regel), während der
  Alarme-Reiter selbst einen anderen Kanal (E-Mail) eingeschaltet hat / When ein Regen-Alarm
  ausgelöst wird / Then berücksichtigt der Regen-Alarm den Kanal der Regel — genau wie
  Gewitter-, Änderungs- und amtliche Alarme das bereits tun; Regen-Alarme sind keine Ausnahme
  von den Alarm-Regeln mehr.
  - Prüfort: Kanal-Aufschlüsselung im Alarm-Protokoll — der Standard-Kanal (E-Mail) trägt
    `channel_disabled`, der Regel-Kanal (SMS) trägt `delivery_failed`.
  - Test: `tests/unit/test_radar_alert_channel_resolution.py::test_radar_alert_channels_follow_active_alert_rule_override` (neu)
  - Mutation: die neue Auflösungsstelle ruft eine eigene, abgespeckte Fassung ohne den
    Regel-Union-Teil auf, statt `_effective_alert_channels()` unverändert zu verwenden — der
    Regel-Kanal bliebe unberücksichtigt, stattdessen gälte weiterhin nur `alert_channels`
    (E-Mail).

## Warum ein grüner Testlauf hier nichts beweist

Alle 30 Bestands-Testdateien, die `check_radar_alerts()` aufrufen, wurden gegen alle Dateien mit
`alert_rules`-Zuweisung gekreuzt (Kontextdokument, R1): **keine einzige Kombination**. Jede
bestehende Radar-Vorlage steuert ihre Kanäle ausschließlich über `report_config` — genau der
Fall, in dem alte und neue Auflösungsfunktion identisch antworten. Ein Funktionswechsel allein
macht deshalb keinen einzigen Bestandstest rot; der komplette Bestand bliebe grün, selbst wenn
die Umstellung nie stattgefunden hätte (Regression: ersatzloses Streichen der Änderung).

Diese Spec ist deshalb bewusst so aufgebaut, dass **ausschließlich** die sieben neuen Tests
die eigentliche Zusicherung tragen — sie sind der einzige Ort, an dem "Radar folgt
`alert_channels`/`alert_rules`" beobachtbar geprüft wird. Ohne sie bewiese ein grüner
CI-Lauf nur, dass nichts kaputtgegangen ist — nicht, dass etwas repariert wurde.

## Mutations-Gegenprobe

| AC | Gezielte Verfälschung | Test, der dadurch rot werden MUSS |
|---|---|---|
| AC-1 | Radar liest (teilweise) weiterhin `report_config` statt ausschließlich `alert_channels` | `test_radar_alert_channels_override_report_config_when_alert_channels_set` |
| AC-2 | Fallback bei `alert_channels is None` entfällt/bricht | `test_radar_alert_channels_fall_back_to_briefing_when_alert_channels_unset` |
| AC-3 | Kanal-Schwelle (`split_by_threshold`) wird auf die alte, nicht-geteilte Variable angewendet | `test_radar_alert_below_threshold_channel_uses_shared_channel_set` |
| AC-4 | Unterdrückungs-Protokoll (`:987`) bleibt bei der alten Auflösung, nur der Versand wird umgestellt | `test_radar_alert_suppressed_entry_matches_dispatch_channel_set` |
| AC-5 | Der verbliebene erste Leer-Check (`:1061`) wird beim Entfernen des zweiten (`:1111-1113`) auf eine falsche Variable umgehängt | `test_radar_alert_stays_silent_when_all_trip_channels_off` |
| AC-6 | Die neue Auflösung prüft weiterhin selbst `can_send_*()`-Erreichbarkeit statt das dem Versand zu überlassen | `test_radar_alert_logs_configured_but_unreachable_channel` |
| AC-7 | Die Auflösungsstelle nutzt eine eigene Fassung ohne `alert_rules`-Union statt `_effective_alert_channels()` unverändert | `test_radar_alert_channels_follow_active_alert_rule_override` |

## Known Limitations

- **Der zweite, jetzt entfernte Leer-Check war bereits vor dieser Scheibe toter Code.** Seine
  Entfernung ändert das Verhalten nicht, nur die Lesbarkeit — AC-5 sichert die Stelle trotzdem
  ab, weil genau dort (D2) ein Refactoring-Fehler am leichtesten passiert.
- **Der Compare-Radar-Pfad ist NICHT Teil dieser Scheibe** (bereits mit #1461 S3b-2b
  umgestellt) — keine Doppelarbeit, aber auch kein erneuter Nachweis hier.
- **D5s neue `not_delivered`-Einträge sind für Bestandstrips ein sichtbarer Unterschied im
  Archiv** (mehr Einträge als vorher, sobald ein Nutzer im Alarme-Reiter einen technisch noch
  nicht erreichbaren Kanal aktiviert) — kein Datenverlust, aber ein Verhaltenszuwachs, den ein
  Support-Ticket ohne dieses Dokument für einen Fehler halten könnte.
- **`docs/features/architecture.md` erwähnt `_radar_effective_channels()` namentlich**
  (per Grep gefunden) — wird durch diese Scheibe nicht aktualisiert (reine Doku-Pflege, kein
  Code); Nebenbefund-Kandidat für #1199, falls es auffällt.
- **Ein Nachtrag zu ADR-0021** (analog dem Compare-Nachtrag vom 2026-08-06) ist inhaltlich
  fällig, aber nicht Teil dieser Spec-Datei — bei der Implementierung nachtragen, nicht in
  dieser Phase (Schreibrecht ist auf die Spec beschränkt).
- **D3 (Reihenfolge Horizont-Guard vor Kanalberechnung) ist nicht durch einen eigenen Test
  abgesichert.** Eine versehentliche Vertauschung würde keinen der sieben neuen Tests rot
  machen — das Endergebnis für ein zeitlich aktives Segment ist bei beiden Reihenfolgen
  identisch, nur die Arbeitslast für zeitlich übersprungene Segmente unterscheidet sich.
  Absicherung ist hier Code-Review (Implementation Details, Schritt 2), nicht Testabdeckung.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue. Nachtrag zu ADR-0021 empfohlen (s. Known Limitations).
- **Rationale:** Diese Scheibe wendet ein bereits etabliertes Architekturprinzip — ein
  geteilter Kanal-Resolver für alle Alarmtypen einer Fläche, siehe ADR-0021 Nachtrag
  2026-08-06 für den Ortsvergleich — symmetrisch auf den letzten noch abweichenden Trip-Pfad
  an. Keine neue Entscheidung, keine Abweichung von einer bestehenden.

## Changelog

- 2026-08-12: Initial spec erstellt — Issue #1752, Scheibe B zu #1745 (Radar-/Regen-Alarme
  folgen dem Alarm-Kanal-Satz).
