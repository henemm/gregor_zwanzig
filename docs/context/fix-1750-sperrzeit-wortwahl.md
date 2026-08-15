# Context: fix-1750-sperrzeit-wortwahl

Issue: [#1750](https://github.com/henemm/gregor_zwanzig/issues/1750) „Sperrzeiten in E-Mail ergeben keinen Sinn"
Mit-erledigt: [#1800](https://github.com/henemm/gregor_zwanzig/issues/1800) (zweite Frage — Anzeige/Wortwahl)
Erhoben: 2026-08-15 · Basis `origin/main` `57e36375`

## Request Summary

Der Briefing-Abschnitt „NICHT BEI DIR ANGEKOMMEN" ist für den Nutzer nicht deutbar: er nennt
`premium_sms` als Rohnamen, und die beiden Sperrgründe heißen dort „Ruhezeit" und „Sperrzeit" —
zwei im Deutschen fast gleichbedeutende Wörter für völlig verschiedene Sachverhalte, die
zudem **keiner** Beschriftung in der Oberfläche entsprechen. Zusätzlich steht die Frage im
Raum, ob unterdrückte Regenradar-Meldungen dort überhaupt gelistet werden sollen.

## Related Files

| Datei | Relevanz |
|---|---|
| `src/output/renderers/email/undelivered_hint.py` | **Der Prüfling.** `_CHANNEL_LABELS:31`, `_REASON_LABELS:35-42`, `_TRIGGER_LABELS:45-49`, `_line():80-86` |
| `src/output/renderers/email/html.py:61,1636` | Aufrufer 1 — Trip-HTML |
| `src/output/renderers/email/plain.py:45,360` | Aufrufer 2 — Trip-Klartext |
| `src/output/renderers/email/compact.py:38,285` | Aufrufer 3 — Kurzfassung, `ascii_safe=True` |
| `src/output/renderers/email/compare_html.py:1668` | Aufrufer 4 — Vergleichs-HTML |
| `src/output/renderers/comparison.py:40,396` | **Aufrufer 5 — im Modul-Docstring nicht erwähnt** (Vergleichs-Klartext) |
| `src/services/alert_log.py:45-59,131-135,359-380,383-449` | Grund-Konstanten, `_channels_not_sent`, `_missed_channels`, `read_undelivered` |
| `src/services/alert_gate.py:143-156` | Einzige Stelle, die `quiet_hours`/`cooldown`/`daily_limit` als Grund erzeugt |
| `src/services/trip_alert.py:1026`, `src/services/compare_radar_alert.py:162` | Einzige zwei Stellen, die eine Unterdrückung überhaupt protokollieren — **beide Radar** |
| `src/services/alert_briefing_anchor.py:233-251` | Zeitfenster: seit dem letzten Briefing; ohne Anker leere Liste |
| `frontend/src/lib/components/alerts-tab/AlertCooldownCard.svelte:11` | Beschriftung in der Oberfläche: **„Cooldown"** |
| `frontend/src/lib/components/alerts-tab/AlertQuietHoursCard.svelte:32` | Beschriftung in der Oberfläche: **„Stille Stunden"** |
| `src/output/renderers/alert/render.py:200-206` | Alarm-Mail nennt dieselbe Sperre **„Cooldown"** |
| `tests/tdd/test_alert_undelivered_hint.py` | 26 Tests, Hauptabsicherung des Bausteins |
| `tests/tdd/test_alert_channel_threshold.py:1018,1023` · `tests/tdd/test_compare_alert_channel_threshold.py:1043` | Einzige Tests, die Grund-Wortlaute wörtlich festnageln (`"unter Schwelle"`, `"Versand fehlgeschlagen"`, `"Schwelle"`) |

## Messung am Produktivkonto (2026-08-15, `/var/lib/gregor/users/henning/alert_log.json`)

| Quelle | Menge | Auslöser | Nicht-Zustell-Gründe | Kanäle |
|---|---|---|---|---|
| `not_delivered` | 56 Vorfälle (09.08.–13.08.) | **100 % `nowcast`** | 96× `quiet_hours`, 18× `cooldown` | email 56, telegram 56, **premium_sms 2** |
| `entries` | 49 Kanal-Einträge | `forecast_change`, `official_alert`, `nowcast` | 42× `channel_disabled` (wird beim Lesen verworfen), 7× `below_channel_threshold` | sms 29, **premium_sms 19**, telegram 1 |

Sichtbar wird davon: 56 Radar-Vorfälle + 7 Schwellen-Fälle (SMS). Die `premium_sms`-Einträge
tragen heute ausschließlich `channel_disabled` (unsichtbar) bzw. `cooldown` (2 sichtbar) —
die Rohnamen-Zeile aus der Meldung ist damit reproduziert.

Ist-Ausgabe des Bausteins (nachgestellt mit echten Werten, `render_undelivered_plain`):

```
NICHT BEI DIR ANGEKOMMEN

  11.08. 17:45 · Amtliche Warnung · SMS nicht zugestellt (unter Schwelle)
  11.08. 17:37 · Regenradar · E-Mail, Telegram, premium_sms nicht zugestellt (Sperrzeit)
  11.08. 16:52 · Regenradar · E-Mail, Telegram nicht zugestellt (Ruhezeit)
```

## Die drei Befunde

### B1 — `premium_sms` hat keinen deutschen Namen (Spec-Verstoß, nicht nur Lücke)

`_CHANNEL_LABELS:31` kennt drei Kanäle; `alert_log._ALL_CHANNELS:59` kennt seit #1701 vier.
Der Rückfall `.get(c, c)` (`:83`) schreibt den technischen Schlüssel in die Nutzerzeile.
ADR-0049 legt die Außen-Schreibweise **„Premium-SMS"** fest; `feat_1701` §D4 hat dasselbe
Mapping bereits in `notification_service.py` nachgetragen — `undelivered_hint.py` wurde dabei
übersehen und wird in keiner Premium-SMS-Spec genannt.

**Zweite, noch ungedeckte Hälfte:** `_REASON_LABELS` kennt die Premium-SMS-Sperrcodes
`premium_sms_no_reply_address` / `premium_sms_reply_address_stale`
(`src/output/channels/premium_sms.py:41-42`) ebenfalls nicht. Träte einer auf, stünde dort
`Premium-SMS nicht zugestellt (premium_sms_no_reply_address)` — das verletzt AC-5 aus
`feat_1461_s3b2a_kanal_schwelle.md` („verständlicher, deutscher Grund — **kein interner
Bezeichner**") wörtlich. Am Produktivkonto heute nicht aufgetreten, also latent.

### B2 — Drei Wörter für zwei Sachverhalte, keines davon deckungsgleich

| Sachverhalt | Oberfläche (dort stellt der Nutzer es ein) | Alarm-Mail | Briefing-Abschnitt |
|---|---|---|---|
| Uhrzeitfenster ohne Alarme | **„Stille Stunden"** | — | **„Ruhezeit"** |
| Mindestabstand zwischen zwei Alarmen | **„Cooldown"** | **„Cooldown"** | **„Sperrzeit"** |

Der Nutzer stellt „Stille Stunden" ein und liest „Ruhezeit"; er stellt „Cooldown" ein und liest
„Sperrzeit". Kein Wort in der Mail führt zu der Einstellung zurück, die den Fall verursacht hat —
das ist die eigentliche Unverständlichkeit, nicht bloß die Ähnlichkeit der zwei Wörter.

Fachlich (Quelle: `docs/specs/_archive/modules/issue_181_alert_cooldown_quiet_hours.md`):
`quiet_hours` = Zeitfenster „HH:MM–HH:MM" in Ortszeit, in dem nichts gesendet wird;
`cooldown` = Mindestabstand in Minuten seit der letzten **zugestellten** Meldung derselben Sache.

### B3 — Die Liste kann per Konstruktion fast nur Regenradar enthalten

`quiet_hours`/`cooldown`/`daily_limit` werden ausschließlich über `append_suppressed_entry()`
protokolliert, und das rufen genau zwei Stellen — beide Radar (`trip_alert.py:1026`,
`compare_radar_alert.py:162`). Der Vorhersage-Änderungs- und der Amtliche-Warnung-Pfad brechen
bei einer Unterdrückung mit `return False` ab, **ohne** zu protokollieren (`trip_alert.py:247`,
`compare_alert.py:159`) — in `alert_log.py:281-284` als Lücke O3 ausgewiesen.

Die 100-%-Radar-Quote ist damit kein Zufall der letzten Woche, sondern strukturell. Wer nach
Auslöser filtert, leert den Abschnitt heute praktisch vollständig — mit Ausnahme der
`below_channel_threshold`-Fälle aus dem `entries`-Zweig.

## Existing Patterns

- **Grund-basierte Filterung gibt es schon:** `channel_disabled` wird beim Lesen verworfen
  (`alert_log.py:376`), weil ein abgeschalteter Kanal kein Vorfall ist. Ein Filter für B3
  hätte hier sein Vorbild — und dieselbe Stelle.
- **Wortlisten sind nicht dupliziert:** Die deutschen Gründe existieren genau einmal
  (`undelivered_hint.py:35-42`). Kein Klassen-Problem über mehrere Dateien.
- Der Baustein bedient bewusst Trip **und** Ortsvergleich (kein `trip_`/`compare_`-Präfix,
  Teilungs-Invariante, Pendant-Sperre #1481 B).

## Dependencies

- **Upstream:** `services.alert_log.read_undelivered()` → `alert_briefing_anchor.undelivered_since_last_briefing()` → `notification_service.py:336` (Trip) bzw. `scheduler_dispatch_service.py:472` (Compare)
- **Downstream:** fünf Render-Pfade (s.o.). Kein Go-, kein Frontend-, kein API-Verbraucher.

## Existing Specs

| Spec | Rolle |
|---|---|
| `docs/specs/modules/feat_1461_s3b1_briefing_sichtbarkeit.md` (v1.2, PO-go 2026-08-05) | Leitspec des Abschnitts. AC-1 nennt „SMS" wörtlich, AC-2 „alle drei Kanalnamen", AC-6 Deckelung auf 5 Zeilen |
| `docs/specs/modules/feat_1461_s3b2a_kanal_schwelle.md` | **AC-5: deutscher Grund, kein interner Bezeichner** — die Regel, gegen die B1 verstößt |
| `docs/specs/modules/feat_1459_alert_protokoll.md` (v1.5) | Schema + Grund-Katalog O2, `reason` bewusst freier String |
| `docs/adr/0049-premium-sms-vierter-kanal.md` | Kanalname `premium_sms`, Außen-Schreibweise „Premium-SMS" |
| `docs/specs/_archive/modules/issue_181_alert_cooldown_quiet_hours.md` | Ursprungsdefinition beider Sperren |

**Kein Dokument legt die deutschen Wortlaute der Gründe fest** — sie stehen nur im Code. Eine
Umbenennung berührt daher keine freigegebene Zusicherung außer AC-5 (die sie erfüllt, nicht bricht).

## Risks & Considerations

1. **Wächter-Loch:** „Ruhezeit", „Sperrzeit" und „Tageslimit" sind heute von **keinem** Test
   als Zeichenkette geprüft — sie ließen sich wortlos ändern, ohne dass etwas rot wird. Nur
   „unter Schwelle" und „Versand fehlgeschlagen" sind abgesichert. Der Fix muss diese Lücke
   mitschließen, sonst bewacht auch die neue Wortwahl nichts.
2. **Renderer-Commit-Gate #811:** `undelivered_hint.py` liegt in `src/output/renderers/email/`
   → Commit blockt bis `tests/tdd/test_issue_811_mode_matrix.py` grün **und** ein
   `briefing_mail_validator.py`-Lauf gegen eine echt zugestellte Staging-Mail bestanden ist.
3. **Fünf Aufrufer, nicht vier** — der Modul-Docstring ist unvollständig. Ein Nachweis, der nur
   die vier genannten Pfade prüft, lässt den Compare-Klartext (`comparison.py:396`) ungeprüft.
4. **Testliterale:** `_CHANNEL_LABELS`-Wortlaute sind load-bearing
   (`test_alert_undelivered_hint.py:397-399,448,623`) — ein Umbenennen von „E-Mail"/„Telegram"/
   „SMS" bricht diese Tests. Ein reines *Hinzufügen* von `premium_sms` bricht nichts.
5. **Dedup-Fenster gleitend:** `DEDUP_WINDOW = 2 Min` gruppiert gegen `gruppen[-1]["at"]`, nicht
   gegen den Gruppenstart — eine dichte Radar-Kette (alle 7-8 Min am Produktivkonto) verschmilzt
   NICHT, aber eine dichtere schon; `trigger` gewinnt dabei der jüngste Eintrag. Nicht Teil
   dieses Fixes, aber beim Nachweis zu beachten.
6. **B3 ist eine Produktentscheidung, keine technische.** Filtert man nach Auslöser, verschwindet
   die Information über unterdrücktes Radar vollständig — das kollidiert mit dem Grundsatz, dass
   der Nutzer entscheidet, was für ihn wichtig ist. Alternativen (zusammenfassen statt streichen,
   nach Grund statt nach Auslöser filtern) gehören in die Spec-Freigabe.

## Offene PO-Entscheidungen (für `/30-write-spec`)

- **E1 Wortwahl:** Mail übernimmt die Oberflächen-Wörter („Stille Stunden" / „Cooldown")?
  Oder beide Seiten bekommen neue, selbsterklärende deutsche Wörter (Frontend dann im Scope)?
  Oder die Mail beschreibt statt zu benennen?
- **E2 Umfang der Liste:** Radar-Unterdrückungen weiter einzeln listen, zusammenfassen
  („12× Regenradar während der Stillen Stunden") oder ganz weglassen?
