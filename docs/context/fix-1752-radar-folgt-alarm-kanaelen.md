# Context: fix-1752-radar-folgt-alarm-kanaelen

**Issue:** [#1752](https://github.com/henemm/gregor_zwanzig/issues/1752) · Label `bug`, `priority:high`, `session:khw`
**Track:** Full Process (Intake-Summe 4) · **Basis-Commit `bc7dc418`** · Phase 1+2 zusammengeführt 2026-08-12

## Request Summary

Der Radar-/Regen-Alarm löst seine Kanäle ausschließlich aus `trip.report_config` (Briefing-Flags)
auf und liest `trip.alert_channels` nie. Wer im Alarme-Reiter Kanäle abwählt, ändert für
Regen-Alarme **nichts** — das betrifft alle vier Kanäle, nicht nur den neuen. Scheibe B zu #1745,
dessen Scheibe A (Premium-SMS in der Oberfläche) seit `c28f794b` live ist.

## 🔴 Warum Kontext und Analyse hier zusammenfallen

Die vollständige Analyse steht bereits **im Issue-Body** — sie entstand am 2026-08-11 im Zuge von
#1745 Scheibe A. Diese Phase hat sie deshalb nicht wiederholt, sondern **gegen den heutigen Code
zu falsifizieren versucht** (Basis `bc7dc418`, nach #1697, #1667 S3, #1701, #1725, #1745 A).

**Ergebnis: Die Analyse hält vollständig.** Kein inhaltlicher Widerspruch, nur Zeilenverschiebungen.
Das ist ein Befund, kein Formalismus — in dieser Sitzung hat eine vier Tage alte Notiz bereits
einmal zu einer falschen Priorisierung geführt (#1584 war längst behoben). Vgl.
[[reference_aussagen_ueber_eigenen_code_veralten_still]].

## Related Files — heutige Zeilennummern (die der Analyse sind überholt)

| Datei:Zeile | Relevanz | war laut Analyse |
|---|---|---|
| `src/services/trip_alert.py:826` | `_radar_effective_channels()` — löst **nur** aus `report_config` auf | `:826` ✓ |
| `src/services/trip_alert.py:987` | Aufruf 1 — `effective_channels` für `append_suppressed_entry` (Unterdrückungs-Protokoll, **vor** dem Nowcast-Abruf) | `:991` |
| `src/services/trip_alert.py:1061` | Aufruf 2 — Leer-Check, `continue` mit `logger.warning`, **ohne** Protokolleintrag | `:1059` |
| `src/services/trip_alert.py:1109` | Aufruf 3 — Versand-Set | `:1107` |
| `src/services/trip_alert.py:1111-1113` | **zweiter** Leer-Check — nachgemessen **toter Code** (s.u.) | `:1109` |
| `src/services/trip_alert.py:1123-1125` | `split_by_threshold` auf derselben Variable | `:1121`/`:1130` |
| `src/services/trip_alert.py:1493-1548` | `_effective_alert_channels()` — die Zielfunktion | `:1491-1546` |
| `src/services/trip_alert.py:1524-1527` | vier Kanäle im scharfen Zweig | `:1518-1521` |
| `src/services/trip_alert.py:1517`, `:1534-1542` | `active_rules`, Union über `rule.channels` | `:1515`, `:1531-1540` |
| `src/services/trip_alert.py:1544-1547` | Tier-Gates SMS / Premium-SMS | `:1542-1545` |
| `src/services/trip_alert.py:1550-1564` | `_briefing_channels()` — Vererbungszweig, vier Kanäle | `:1548-1562` |
| `src/services/notification_service.py:1388,1404,1485` | `can_send_*()`-Wiederholung beim Versand | **unverändert** |
| `src/services/notification_service.py:1499` | Premium-SMS **ohne** Vorprüfung | **unverändert** |
| 🆕 `src/services/trip_alert.py:936-951` | **Horizont-Guard** aus #1697 AC-4 — neu, in der Analyse nicht enthalten | — |

## Selbst nachgemessen (nicht aus dem Agentenbericht)

**Der zweite Leer-Check (`:1111-1113`) ist toter Code.** Zwischen ihm und dem ersten (`:1061`)
liegen ausschließlich: Cooldown-Formatierung, Label-/Kontextstrings und der Bau von
`RadarAlertRequest`. Keine Zeile schreibt auf `trip`, `trip.report_config` oder `self._settings`;
die Funktion ist rein. Der Docstring sagt es selbst (`:830-834`, seit #1467 S3): „Reine Ableitung
ohne Seiteneffekt, das Ergebnis ist an beiden Stellen identisch."

**Live-Konfiguration KHW 403** (`/api/_internal/trip/5f534011/loaded`):

| Feld | Wert |
|---|---|
| `alert_channels` | `{email: true, telegram: true, sms: true}` — kein `premium_sms` |
| `alert_channel_thresholds` | `{email: LOW, telegram: LOW, **sms: HIGH**}` |
| `report_config` | `send_email: true, send_telegram: true, **send_sms: false**, send_premium_sms: false` |
| `alert_rules` | 4 aktiv, **alle** mit leerer Kanalliste ⇒ erben aus `alert_channels` |

## Was sich für den PO konkret ändert

| Kanal | Regen-Alarm heute | nach der Umstellung |
|---|---|---|
| E-Mail | ✓ | ✓ |
| Telegram | ✓ | ✓ |
| **SMS** | ✗ (Briefing-Flag aus) | **✓ neu** — Schwelle `HIGH`, trifft nur hohe Dringlichkeit |
| Premium-SMS | ✗ | ✗, bis der Haken im Alarme-Reiter gesetzt wird |

Das ist die vom PO am 2026-08-11 ausdrücklich in Kauf genommene Verhaltensänderung.

## Existing Patterns

**Präzedenzfall im Ortsvergleich, bereits vollzogen:** #1461 S3b-2b hat den Compare-Radar-Pfad von
hart `{"email"}` auf den regulären `effective_compare_channels()`-Resolver umgestellt — mit eigenen
ACs und als **Nachtrag zu ADR-0021**, ohne neue ADR. Die Trip-Seite zieht damit nach.

**Es gibt keine ADR, die „Radar folgt Briefing" festschreibt.** Die einzige Begründung ist eine
Known-Limitation-Notiz in der archivierten #1258-Spec, die die Angleichung ausdrücklich als eigenes
Issue ankündigt — dieses hier.

## 🔴 Risiken

**R1 — Die Test-Blindstelle ist real und heute erneut bestätigt.** Alle 30 Testdateien, die
`check_radar_alerts()` aufrufen, wurden gegen alle Dateien mit `alert_rules`-Zuweisung gekreuzt:
**keine einzige Kombination**. Auch die neuen #1701-Premium-SMS-Radartests steuern den Kanal
ausschließlich über `report_config.send_premium_sms`. `test_alarm_zeitfenster_ziel.py:149` setzt
zwar `alert_channels`, aber dieser Trip-Builder speist nur `check_and_send_alerts()`, nicht den
Radar-Pfad. **Ein Funktionswechsel macht damit nichts rot — ein grüner Lauf beweist hier nichts.**

**R2 — Der Horizont-Guard darf nicht überholt werden.** Neu seit #1697 (`:936-951`): Ein Segment,
das erst >60 min in der Zukunft beginnt, führt zu `continue` **vor** allen Kanal-Aufrufen. Eine
Umstellung auf „Kanal-Set einmal berechnen" darf die Berechnung **nicht** vor diesen Guard ziehen —
sonst wird für zeitlich irrelevante Segmente die `alert_rules`-Union ausgewertet. Der Guard selbst
ist rein zeitbasiert und eigens getestet, also kein blinder Wächter.

**R3 — Radar erbt die `alert_rules`-Union mit.** `_effective_alert_channels` legt auf
`alert_channels` zusätzlich die Union nicht-leerer `rule.channels`. Bei KHW folgenlos (alle vier
Regeln leer), aber eine echte Bedeutungserweiterung, die in die ACs gehört.

**R4 — Beobachtbarkeit ändert sich, Zustellung nicht.** `_dispatch_alert_message` wiederholt
`can_send_*()` beim Versand; ein unerreichbarer Kanal wird in beiden Varianten nicht zugestellt.
Wo heute `:1061` **ohne** Protokolleintrag abbricht, entsteht danach ein `alert_log`-Eintrag mit
leerem `sent_channels`. Verbesserung — muss als AC formuliert werden, damit die neuen Einträge
niemand für einen Defekt hält.

## Was die Analyse übersehen hatte (Nachtrag dieser Phase)

**Derselbe Fehler war in dieser Funktion schon einmal produktiv** — und wurde kurz vor der Analyse
behoben: Bis #1701 (`c91a0844`) stand dort ein globaler Bereitschafts-Guard
`if not can_email and not can_telegram and not can_sms: continue`, der einen Trip mit
ausschließlich Premium-SMS verworfen hätte, **bevor** irgendein Kanal-Set aufgelöst wurde. Ersetzt
durch die heutige kanalbasierte Prüfung. Der zugehörige Test heißt sprechend „Schritt 0: der
Radar-Bereitschafts-Guard" (`tests/unit/test_alert_channel_premium_sms.py:298-376`).

**Konsequenz für die Spec:** Nach der Umstellung muss mindestens ein Test eine Konfiguration
prüfen, die **ausschließlich** den neuen Weg nutzt — kein Bestandskanal daneben, der einen Guard
zufällig passierbar macht. Vgl.
[[reference_bereitschafts_guard_bricht_ab_vor_der_kanalaufloesung]].

## Offene Fragen für die Spec

- [ ] Weg (b) — `_radar_effective_channels` entfällt ersatzlos, die drei Aufrufstellen nutzen
      `_effective_alert_channels` — bleibt die Empfehlung. Zu fixieren: Kanal-Set **einmal**
      berechnen (nach dem Horizont-Guard), zweiten Leer-Check streichen.
- [ ] ADR: Nachtrag zu ADR-0021 (Compare-Präzedenz) statt neuer ADR.
