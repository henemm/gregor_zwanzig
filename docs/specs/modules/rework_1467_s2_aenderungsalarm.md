---
entity_id: rework_1467_s2_aenderungsalarm
type: refactor
created: 2026-08-03
updated: 2026-08-04
status: draft
version: "1.2"
tags: [alerts, trip, compare, epic-1458, issue-1467, s2]
---

# Vorhersage-Änderungsalarm: eine Ablaufsteuerung für Trip und Ortsvergleich (Issue #1467 Scheibe S2, Epic #1458 Teil 2)

## Approval

- [x] Approved — PO-„go" 2026-08-03 (23 ACs, sechs Arbeitsgänge)

## Purpose

Trip und Ortsvergleich werten Vorhersage-Änderungen bereits über denselben Auswertungskern
(`DeviationAlertEngine`, ADR-0021) aus — aber die **Ablaufsteuerung darüber** ist zweimal
gebaut und an vier Stellen unbegründet unterschiedlich: der Ortsvergleich kennt weder Telegram
noch SMS für Änderungsalarme (`channels={"email"}` fest verdrahtet), prüft Ruhezeiten erst
NACH dem Wetterabruf statt davor, kennt keinen Gedächtnis-Reset beim Briefing-Versand (der
Trip hat ihn seit #816) und sendet aus pausierten oder archivierten Vergleichen weiterhin
Alarme, obwohl der amtliche Alarm-Pfad (`compare_official_alert.py`, #1233) diesen Riegel
längst hat.

Diese Scheibe zieht die Ablaufsteuerung — nicht den Auswertungskern — für den Δ-Wetter-Pfad
zusammen, in **sechs unabhängig auslieferbaren Arbeitsgängen**. Nutzersichtbarer Gewinn:
Ortsvergleich-Änderungsalarme gehen künftig auch per Telegram (eine Sprechblase je Ort) und
SMS (Orte numerisch kodiert), der Ortsvergleich bekommt den Gedächtnis-Reset beim
Briefing-Versand, und stillgelegte Vergleiche schweigen wirklich. Die Bedienung für Telegram/
SMS existiert im Alarme-Tab bereits (`AlertChannelPicker`,
`frontend/src/lib/components/shared/AlarmeTab.svelte:295`) und ist heute wirkungslos — diese
Scheibe repariert einen vorhandenen, stummen Schalter, baut keinen neuen.

Sie ist die **zweite** von vier Scheiben in #1467 (S1 „Alarm-Kennung" live seit `49cf1c22`) und
betrifft ausschließlich den Δ-Wetter-Pfad. Nowcast (S3, `compare_radar_alert.py`) und amtliche
Warnungen (S4, `compare_official_alert.py`) werden **nicht** umgebaut — zwei Arbeitsgänge
reichen aus fachlich zwingenden Gründen dennoch in diese Dateien hinein (AG1 Kanal-Resolver-
Delegation, verhaltensgleich; AG6 Pausiert/Archiviert-Riegel, PO-Vorgabe „grundsätzlich").

**Leitsatz für alle sechs Arbeitsgänge:** Der gefährlichste Fehler ist der ausbleibende Alarm.
Zielmarke ist „Verhalten unverändert", außer den ausdrücklich in dieser Spec benannten
Änderungen.

## Source

- **File:** `src/services/compare_alert.py`
- **Identifier:** `class CompareAlertService`, Methode `check_all_compare_presets()`

Betroffene Schicht: ausschließlich **Python-Core** (`src/services/`,
`src/output/renderers/alert/`). Kein Go-Code, kein Frontend-Code — die Bedienoberfläche
(`AlertChannelPicker` im Alarme-Tab) existiert bereits und wird durch diese Scheibe erst
wirksam.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `rework_1467_s1_alarm_kennung` | module | Vorgänger-Scheibe (live, `49cf1c22`) — `entity_id`/`entity_type` sind hier bereits Pflicht in `alert_log.append_entry()` |
| `DeviationAlertEngine` | module | Geteilter Auswertungskern (ADR-0021) — wird NICHT angefasst |
| `AlertStateService` | module | Melde-Gedächtnis, `reset()` schont `official_alert:`-Schlüssel seit #1460 P2 |
| `ThrottleStore` | module | Sperrzeit-Zähler, Scope `compare_preset` (`throttle_store.py:39`) |
| `alert_daily_limit` | module | Tages-Obergrenze, nutzerweit |
| `NotificationService` | module | Kanal-Fan-out E-Mail/Telegram/SMS |
| `feat_864_859_alert_presets` | module | Empfindlichkeitsstufen je Metrik — einzige Alarm-Steuerung, hier unverändert |
| `feat_1459_alert_protokoll` | module | Protokoll-Felder (`effective_channels`/`sent_channels`/`reachable_channels`) |

## Estimated Scope

- **LoC:** grob 150–220 Produktivcode über sechs Arbeitsgänge (3 neue kleine Module + 6
  geänderte Dateien), ~350–550 Tests ⇒ **die Scheibe als Ganzes liegt deutlich über dem
  250er-Budget**, einzelne Arbeitsgänge (AG1–AG4, AG6) i. d. R. darunter oder knapp darüber,
  AG5 (Anker+Gedächtnis-Baustein, zwei Aufrufer, zwei Dateien) am ehesten darüber.
  `loc_limit_override` je Arbeitsgang mit PO-Freigabe einholen, analog S1.
- **Files:** 3 neu (`compare_alert_channels.py`, `alert_briefing_anchor.py`,
  `compare_alert_guard.py`), 7 geändert, mehrere neue/erweiterte Testdateien.
- **Effort:** high (sechs Arbeitsgänge, davon zwei mit echter Datenwirkung).
- **Risiko:** MEDIUM–HOCH — der Trip-Hauptpfad bleibt unberührt bis auf den geteilten
  Anker+Gedächtnis-Baustein (AG5); die größte Gefahr ist der stille ausbleibende Alarm (s.
  Risiken unten).

## Ist-Stand — vier Unterschiede zwischen Trip und Ortsvergleich (gemessen)

| | Trip (`trip_alert.py`) | Ortsvergleich (`compare_alert.py`) |
|---|---|---|
| **Kanäle** | `_effective_alert_channels()` `:1155-1207` — Regel-Override, sonst `alert_channels`, sonst Briefing-Erbe, SMS-Tier-Gate `:1205` | fest `{"email"}` `:246` |
| **Ruhezeiten** | doppelt: explizit vor allem (`:205` `if self._is_quiet_hours(...)`), zusätzlich in der Engine (`deviation_alert_engine.py:243`) | nur in der Engine — nach Sperrzeit-Lesen (`:112`) und Tages-Obergrenze-Lesen (`:118`) |
| **Gedächtnis-Reset beim Briefing** | ja, `trip_report_scheduler.py:972` → `_reset_alert_state_after_briefing()` `:1036-1042` → `AlertStateService.reset(trip.id)` | nein — repo-weit genau ein `AlertStateService.reset()`-Aufruf, und der ist der Trip-Reset |
| **Gedächtnis-Kennung** | `trip.id` (eine Datei je Trip) | `f"{preset_id}:{location_id}"` (`compare_alert.py:196`, eine Datei je Preset × Ort) |

Zusätzlich unbegründet unterschiedlich (nicht in der Ursprungstabelle, in der Analyse
gemessen): **pausierte/archivierte Ortsvergleiche senden weiterhin** — der Riegel
(`preset["schedule"] == "manual"` bzw. `preset["archived_at"]`) existiert nur in
`compare_official_alert.py:84-89` (#1233), nicht in `compare_alert.py` oder
`compare_radar_alert.py` (verifiziert: kein Treffer für `archived_at`/`schedule` in beiden
Dateien).

**Bereits gleich:** Sperrzeit über `ThrottleStore` (nur anderer Scope-String), Tages-Obergrenze
`alert_daily_limit`, Protokoll `alert_log.append_entry()` (identische Feldmenge seit S1),
Auswertungskern `DeviationAlertEngine`, Empfänger ausschließlich aus den Konto-Settings
(#1452).

**Wortgleich dupliziert** über drei Compare-Dateien: `_load_presets()`
(`compare_alert.py:327`, `compare_radar_alert.py:203`, `compare_official_alert.py:274`) —
byte-identisch. Nahezu identisch: `_notification_service_for()`, Kanal-Resolver
(`compare_official_alert.py:250-258` und `scheduler_dispatch_service.py:275-292`, funktional
identisch), Preset-Schleifenkopf, Kennungsschema `f"{preset_id}:{loc_id}"`.

## Implementation Details

### AG1 — Kanal-Ermittlung zusammenlegen

Der Compare-Kanal-Resolver existiert bereits **zweimal**: `compare_official_alert.py:250-258`
(`_effective_channels`) und `scheduler_dispatch_service.py:275-292`
(`_effective_compare_channels`) — funktional identisch (E-Mail immer; Telegram/SMS nur bei
Preset-Opt-in UND globaler Nutzer-Fähigkeit, SMS zusätzlich mit `sms_allowed()`). Ein neues
Modul `src/services/compare_alert_channels.py` (~30 Zeilen) hält die EINE Fassung; beide
Bestandsstellen delegieren. `compare_alert.py:246` (`channels={"email"}`) bekommt in AG4 die
dritte Aufrufstelle.

Regel (unverändert übernommen): E-Mail immer aktiv; Telegram nur bei
`preset["send_telegram"]` UND `settings.can_send_telegram()`; SMS nur bei
`preset["send_sms"]` UND `settings.can_send_sms()` UND `sms_allowed(user_id)`. Gelesen wird aus
dem Preset-**Dict** (`preset.get(...)`), nicht aus dem Dataclass-Feld — ein Zugriff aufs
Dataclass-Feld wäre stumm bei E-Mail-only, wenn der Aufrufer nur das Rohdict pflegt
(Risiko R4).

### AG2 — Ruhezeiten vor die Erkennung

`compare_alert.py::_check_one_preset` liest Sperrzeit (`:112`) und Tages-Obergrenze (`:118`)
bereits VOR dem Wetterabruf; die Ruhezeit-Prüfung (`DeviationAlertEngine.is_quiet_hours`)
sitzt bislang erst IN der Engine (`deviation_alert_engine.py:243`, NACH dem Fetch in
`_evaluate_one_location` `:194`). Sie wird vorgezogen, Muster
`compare_official_alert.py:105-113`. Sperrzeit und Tages-Obergrenze werden während der
Ruhezeit ohnehin nur *gelesen*, geschrieben wird erst nach erfolgreichem Versand
(`compare_alert.py:158-159`) — das Vorziehen verschiebt keine Zählung, spart nur den
Wetterabruf.

### AG3 — Darstellung der Kurznachrichten (Renderer + Dispatch-Mechanik)

Betrifft `src/output/renderers/alert/render.py` (`_sms_token` `:585-588`, `render_telegram`
`:549-582`) sowie `src/services/notification_service.py`
(`send_multi_location_deviation_alert` `:516-552`, `_dispatch_alert_message` `:1026ff`).

**Gemessener Befund:** `to_multi_point_alert_message()`
(`src/output/renderers/alert/project.py:179-221`) setzt bei mehreren Orten pro `AlertEvent`
zwar bereits ein `location_label` (`:215`), aber `AlertMessage.location_label` UND
`AlertMessage.trip_short` tragen BEIDE denselben zusammengesetzten Namensstring
(`collective_label = ", ".join(...)`, `:217-220`) — die SMS-Kopfzeile
(`render.py:594-595`/`:613-614`, `head = f"{trip} {location_label}: "`) zeigt die Ortsliste
dadurch **zweimal**, und `_sms_token()` nutzt das per-Event-`location_label` gar nicht — die
einzelnen Token tragen keine Ortszuordnung.

- **SMS:** Orte werden als **Zahl** geführt (PO E2), nicht ausgeschrieben. Die Zahl ist die
  1-basierte Position des Ortes in der konfigurierten Ortsliste des Vergleichs
  (`preset["location_ids"]`), identisch zur Spaltenreihenfolge der Vergleichs-E-Mail. Die
  Zuordnung Name→Position wird vom Aufrufer (Compare-Alarm-Pfad, der die Ortsliste kennt)
  gebaut und der SMS-Renderfunktion als neuer optionaler Parameter mitgegeben — ohne diesen
  Parameter (alle anderen Aufrufer: Trip, Radar-Onset, amtlich) bleibt das bisherige Verhalten
  unverändert. **Korrektur 2026-08-04 (PO, umgesetzt in `e9f23605`):** Der Ortsname entfällt
  in der Alarm-Kurznachricht **vollständig** — nicht nur die Doppelung. Ist die
  Positions-Zuordnung gesetzt, trägt der Text ausschließlich die Werte-Token
  (`'2:+R45 1:+R30'`); das gilt auch für den Ein-Ort-Fall (`'+R30'` statt
  `'Graz Graz: +R30'`), der über einen eigenen Kopf-Zweig läuft. Begründung: die
  Positionszahl **ist** die Ortsangabe; ein Kopf, der die Namen wiederholt, verbraucht genau
  das Zeichenbudget, das die Kodierung freischaufeln soll (gemessen: 12 von 25 Zeichen im
  Mehr-Orte-Fall, 11 von 15 im Ein-Ort-Fall). Die Alarm-Kurznachricht ist **nicht** von
  `docs/reference/sms_format.md` §2/§3.1 erfasst — der dort vorgeschriebene Header `{Name}:`
  gilt für die Briefing-Token-Zeile, ein anderes Format.
- **Telegram:** **eine Nachricht je Ort** (PO E2, „Sprechblase pro Ort") statt einer
  gebündelten. Der Renderer bekommt eine zweite Funktion, die bei mehreren
  Orts-Gruppen (`multi=True`-Fall aus `project.py:202`) je Ortsname eine eigene, in sich
  vollständige Telegram-Nachricht liefert; bei genau einer Gruppe bleibt das Ergebnis
  byte-identisch zum bisherigen `render_telegram()` (Einzel-Ort-Regressions-Invariante, analog
  `project.py:193-195`). `send_multi_location_deviation_alert()` reicht diese Liste an
  `_dispatch_alert_message()` durch, die für den Telegram-Kanal — **nur für den
  Deviation-Alert-Pfad**, nicht für Radar-Onset oder amtlich (S3/S4, unverändert) — je Element
  einen eigenen Sink-Aufruf macht statt eines einzigen.
- **E-Mail bleibt unverändert gebündelt** — eine Mail mit allen Orten, unverändert über
  `render_alert_email()`.

⚠️ **Bewusste Abweichung von #1170:** #1170 legte fest, dass alle gleichzeitig getriggerten
Orte EINES Presets in EINE Mail gebündelt werden (E-Mail-Flut-Problem). Diese Bündelung bleibt
für E-Mail (und SMS) unverändert bestehen. Für Telegram gilt ab dieser Scheibe eine
**kanalspezifische** Ausnahme — PO-Vorgabe für Lesbarkeit auf dem Handy, kein Widerruf von
#1170: die Datenerhebung/-auswertung bleibt gebündelt (ein Lauf, eine `AlertMessage`), nur der
Telegram-**Versand** splittet sich am Ende in mehrere Sink-Aufrufe.

Diese Arbeit ist bewusst **vor** AG4 eingeordnet (noch keine Nutzerwirkung, da
`compare_alert.py` bis AG4 weiterhin `{"email"}` fest verdrahtet hat) — die Wirkungs-ACs dieser
Scheibe rufen `NotificationService` direkt mit einem `telegram`-Kanal an, unabhängig vom
Compare-Cron-Pfad, damit die Mechanik bewiesen ist, bevor sie live geschaltet wird.

### AG4 — Telegram und SMS für Ortsvergleich-Änderungsalarme scharf schalten

`compare_alert.py:246` (`channels={"email"}`) wird durch den Resolver aus AG1 ersetzt. Die
Bedienung existiert bereits — im Alarme-Tab des Ortsvergleichs steht der geteilte
`AlertChannelPicker` (`AlarmeTab.svelte:295`), der im `context === 'vergleich'`-Zweig auf
`wiz.sendTelegram`/`wiz.sendSms` schreibt (`:186-187`), kommentiert bei `:168-170` „bindet an
bestehende `send_telegram`/`send_sms`". Der Nutzer kann Telegram für Ortsvergleich-Alarme heute
einschalten und bekommt trotzdem nur E-Mail — S2 repariert einen vorhandenen, wirkungslosen
Schalter, führt keinen neuen ein.

⚠️ **Der einzige Bestandstest, der `{"email"}` festschreibt:**
`tests/tdd/test_issue_1169_compare_alert_consumer.py:645`
(`assert telegram_sink.send_count() == 0`), Absicht zusätzlich im Modul-Docstring `:13-14`
(„beweist, dass Compare-Alerts NIE Telegram bedienen") und im Test-Docstring `:591-594` verankert
(„zu keinem Zeitpunkt wird Telegram/SMS bedient (E-Mail-only, B2)"). **Alle drei Stellen** müssen
in dieser Scheibe geändert werden — sonst bleibt eine False-Negative-Doku im Code stehen, die
das neue Verhalten als Bug beschreibt. Die Datei trägt `pytestmark = pytest.mark.email` `:70`
und nutzt echtes IMAP + einen echten lokalen Telegram-HTTP-Server (kein Mock).

### AG5 — Vergleichs-Bezugspunkt und Melde-Gedächtnis als EIN geteilter Baustein

PO wörtlich: „Beide Dienste sollen sich natürlich gleich verhalten. Verwende zwingend den
gleichen Code."

**Ist-Stand:** Der Trip hält Δ-Anker-Schreiben UND Gedächtnis-Reset gemeinsam unter
`if not on_demand` (`trip_report_scheduler.py:959-972`): Snapshot-Save `:963-964`, danach
`_reset_alert_state_after_briefing(trip.id)` `:972` → `AlertStateService.reset()` `:1040`. Der
Ortsvergleich schreibt seinen Δ-Anker **bedingungslos** — `_write_compare_alert_snapshots()`
(`scheduler_dispatch_service.py:447-468`), aufgerufen sowohl im Daily-Lauf
(`send_one_compare_preset:410`) als auch beim Handversand (`send_compare_preset:443` →
`send_one_compare_preset`) — und leert das Gedächtnis **gar nicht**: repo-weit gibt es genau
einen `AlertStateService.reset()`-Aufruf, den des Trips.

**Konsequenz (Korrektur der Ursprungsannahme, gemessen):** Die Trip-Regel lautet nicht „kein
Reset bei Handversand", sondern **„Anker und Gedächtnis werden immer zusammen behandelt, unter
derselben Bedingung"**. Ein wörtlich kopiertes `if not on_demand` um NUR den Reset (Anker bliebe
bedingungslos) erzeugte *neuer Anker + altes Gedächtnis* — die Kombination, die einen echten
Alarm verschluckt (`deviation_alert_engine.py:191-205`, `_filter_against_alert_state` prüft
gegen den absoluten `last_reported_value`; ein frischer Anker ohne Gedächtnis-Reset lässt kleine
Änderungen seit dem letzten — jetzt überschriebenen — Vergleichspunkt für immer verschwinden).

**Baustein:** neues Modul `src/services/alert_briefing_anchor.py` mit einer Funktion, die
`on_demand`, eine Liste betroffener `entity_id`s (Trip: `[trip.id]`; Compare: `[f"{preset_id}:
{loc.id}" for loc in locations]`) und eine Anker-Schreibfunktion entgegennimmt: bei
`on_demand=True` passiert nichts (weder Anker noch Reset); sonst wird zuerst der Anker
geschrieben, danach für jede `entity_id` `AlertStateService.reset()` aufgerufen.
`trip_report_scheduler.py:959-972` und `scheduler_dispatch_service.py` (neuer Parameter
`on_demand: bool = False` an `send_one_compare_preset`, `send_compare_preset` ruft mit
`on_demand=True` auf) delegieren beide dorthin.

Der Reset läuft über **alle** Orte des Presets (nicht nur die getriggerten) — ein still
übersprungener Ort behielte sein altes Gedächtnis und würde nach dem nächsten Briefing nie
wieder melden (Risiko R3). `AlertStateService.reset()` schont `official_alert:`-Schlüssel
bereits seit #1460 P2 (`alert_state.py:90-97`) — das gilt unverändert für beide Entitätstypen.

**Nebenbefund für S3 (hier nicht behoben):** `compare_radar_alert.py:180` schreibt einen
`radar_onset`-Schlüssel in dieselbe Zustandsdatei (`f"{preset_id}:{loc.id}"`). Der Schlüssel
wird repo-weit nirgends gelesen — der neue Reset löscht ihn wie jeden anderen
Nicht-`official_alert:`-Schlüssel, folgenlos, aber S3 muss das wissen, bevor dort mit dem
Schlüssel gearbeitet wird.

### AG6 — Pausierte und archivierte Ortsvergleiche schweigen

PO wörtlich: „Pausierte und archivierte Ortsvergleiche dürfen grundsätzlich nichts senden. Sie
sind ja pausiert beziehungsweise archiviert. Sie sollen sich so verhalten, als würde es sie im
System nicht geben."

Der Riegel (`preset["schedule"] == "manual"` → pausiert, nicht senden; `preset["archived_at"]`
gesetzt → nicht senden) existiert heute nur in `compare_official_alert.py:84-89` (#1233).
`compare_alert.py` und `compare_radar_alert.py` haben ihn nicht. Neues, kleines Modul
`src/services/compare_alert_guard.py` mit einer reinen Funktion `is_silenced(preset: dict) ->
bool`, angewendet als früher Guard in allen drei `_check_one_preset`-Methoden (bzw. dem
Preset-Schleifenkopf von `check_all_compare_presets`). `compare_official_alert.py` delegiert
dorthin statt der Inline-Prüfung — verhaltensgleich, keine Regression.

Die Anwendung im Nowcast-Pfad (`compare_radar_alert.py`, formal S3) wird bewusst
**vorgezogen**: die PO-Vorgabe ist ausdrücklich grundsätzlich, die Änderung je Datei ist eine
einzelne Guard-Zeile, und ein Riegel nur im halben Bestand wäre genau der inkonsistente
Zustand, den diese Scheibe beseitigen soll. Richtung der Verhaltensänderung: **weniger**
Meldungen — anders als bei allen anderen Risiken dieser Scheibe hier ausdrücklich gewollt.

**Belegter Schadensfall (gemessen 2026-08-04 in Produktivdaten).**
`data/users/henning/alert_log.json` enthält genau EINEN Ortsvergleich-Alarm der gesamten
Historie: `cp-eb6ba0b239d90e37`, `sent_at 2026-08-04T04:00:26Z`, `reason forecast_change`
(Böen, MODERATE, per E-Mail). Dasselbe Preset trägt `paused_at 2026-07-31T20:08:12` — der
Alarm ging **vier Tage nach dem Pausieren** raus. AG6 behebt einen belegten Fehler, kein
theoretisches Risiko.

**Was „pausiert" heißt — PO-Entscheidung 2026-08-04 (präzisiert AC-20).**
Die Oberfläche leitet den Status in `frontend/src/lib/components/compare/subscriptionHelpers.ts:83-88`
ODER-verknüpft ab: `paused_at` gesetzt ODER `schedule == "manual"` ⇒ Beschriftung „pausiert".
Der Riegel folgt **dieser** Vorlage, damit Anzeige und Verhalten nicht auseinanderlaufen.
Vorgelegt wurde die Alternative „nur ausdrücklich per Knopf Pausiertes schweigt"; der PO hat
sich für die Deckungsgleichheit mit der Anzeige entschieden.

⚠️ **Sofort sichtbare Betriebsfolge, dem PO vor der Freigabe genannt:** alle fünf realen
Ortsvergleiche tragen heute `schedule="manual"` (vier davon ohne `paused_at` — sie haben nie
einen Zeitplan bekommen). Nach dem Deploy sendet damit **zunächst kein Ortsvergleich mehr
Alarme**, bis einem davon ein Zeitplan gegeben wird. Bewusst nicht technisch abgefedert (keine
Übergangsregel, kein Bestandsschutz) — eine Ausnahme würde genau die Zweideutigkeit
konservieren, die diese Scheibe beseitigt.

**DRY-Befund vor der AC-Freigabe (#1481 Baustein B).** Dieselbe Frage wird heute an **vier**
Stellen beantwortet, und keine zwei gleich:

| Stelle | prüft | Zweck |
|---|---|---|
| `compare_slot_scheduler.py:76-79` | `schedule`, `archived_at` | Briefing-Fälligkeit |
| `scheduler_dispatch_service.py:66-68` | `archived_at`, `paused_at` **oder** `schedule` | Auto-Pause („schon stillgelegt?") |
| `compare_official_alert.py:88-93` | `schedule`, `archived_at` | amtlicher Alarm |
| `subscriptionHelpers.ts:83-88` | `paused_at` **oder** `schedule`, plus `draft` | Anzeige-Status |

`is_silenced()` darf keine fünfte Fassung werden. Verbindlich abgelöst wird
`compare_official_alert.py` (AC-28). `compare_slot_scheduler.py` zieht mit.

**Korrektur 2026-08-04 (Anlass: Adversary-Fund F001, Runde 1) — gemessene Wirkung im
Briefing-Weg.** Der frühere Satz an dieser Stelle („dort ist `paused_at` neu, wirkt aber
praktisch nicht, weil `end_date` unmittelbar davor separat geprüft wird") war eine Annahme
statt einer Messung und ist in beiden Hälften falsch: der Guard steht in
`compare_slot_scheduler.py:78-83` **vor** der `end_date`-Prüfung (`:85-89`), und beide sind
ohnehin unabhängige Bedingungen. Gemessen gilt: **`paused_at` legt im Briefing-Weg
tatsächlich still** — ein Preset mit gesetztem `paused_at`, aktivem `schedule` und gültigem
`end_date` in der Zukunft ist ab jetzt nicht mehr fällig und bekommt auch **kein reguläres
Ortsvergleich-Briefing** mehr, nicht nur keine Alarme. Das ist fachlich gewollt (PO-Vorgabe
„als würde es sie im System nicht geben") und bleibt so. Bewacht wird die Wirkung seit
diesem Fix durch das Testpaar
`tests/tdd/test_compare_alert_paused_archived_silent.py::test_paused_preset_is_not_due_for_regular_compare_briefing`
(pausiert ⇒ nicht fällig) und `::test_active_preset_with_same_fixture_is_due_for_regular_compare_briefing`
(identische Fixture ohne `paused_at` ⇒ fällig). Vorher wurde die gezielte Neutralisierung
genau dieses Anteils (`is_silenced({**preset, "paused_at": None})`) von **keinem** der 42
einschlägigen Tests gefangen; jetzt macht sie genau den ersten der beiden Tests rot
(1 Fehlschlag von 44).

**Nachtrag 2026-08-04 (Anlass: Adversary-Fund F003, Runde 3) — beide Slots getrennt bewacht.**
`presets_due_for_hour` entscheidet für Morgen- und Abend-Slot in zwei **unabhängigen** Zweigen
(`compare_slot_scheduler.py:101-104`, KL-5). Das obige Testpaar verdrahtete nur den
Morgen-Slot; eine Verfälschung, die den Riegel ausschließlich im Abend-Zweig neutralisiert
(Morgen-Zweig unberührt), rutschte deshalb durch alle 44 Tests. Die Fixture `_briefing_preset`
nimmt jetzt den Slot als Parameter (`slot="morning"|"evening"`, eine Fixture statt einer
Zweitfassung), und **jeder** der beiden Slots hat sein eigenes Paar aus Nachweis
(`::test_paused_preset_is_not_due_for_evening_compare_briefing`) und Gegenprobe
(`::test_active_preset_is_due_for_evening_compare_briefing`, fällig mit Zieldatum **Folgetag**).
Die Zusicherung ist damit an **beiden** Stellen geprüft, an denen sie wirkt. Der
ausgelieferte Produktivcode war und bleibt an dieser Stelle korrekt — es fehlte allein der
Wächter; gemessen: die Abend-Mutation macht genau den neuen Abend-Nachweis rot (1 Fehlschlag
von 46), Morgen-Paar und Abend-Gegenprobe bleiben grün.

`scheduler_dispatch_service.py:66-68` bleibt **bewusst unverändert**: dort bedeutet der
`continue` „schon stillgelegt, nicht erneut schreiben", nicht „nicht senden" — gleiche
Bedingung, andere Aussage.

## Invarianten (gelten über alle sechs Arbeitsgänge)

- **Der gefährlichste Fehler ist der ausbleibende Alarm.** Zielmarke: Verhalten unverändert
  außer den ausdrücklich in dieser Spec benannten Punkten.
- Der Trip-Δ-Pfad `trip_alert.py::check_and_send_alerts` wird NICHT umgebaut — einzige
  Ausnahme: der geteilte Anker+Gedächtnis-Baustein aus AG5.
- **Amtliche Eskalation bleibt ohne Zeit-Cooldown** (`compare_official_alert.py:10-19`, Befund
  aus #1233/F002). Ein stilles Angleichen an den Trip-Cooldown wäre „Alarm bleibt aus".
- Datenbeschaffung wird NICHT fusioniert — Trip und Compare holen weiterhin getrennt Wetter.
- Compare-eigen bleiben: Orte statt Etappen, transponierte Übersicht, Compare-Mail-Template,
  Empfänger ausschließlich aus Konto-Settings (#1452 — `preset.empfaenger` bleibt inert),
  Ortszeit-Bezug (#1383).
- Mandantentrennung: jeder Arbeitsgang mit ZWEI verschiedenen Nutzern verifiziert, `user_id`
  nie auf `"default"` zurückfallen lassen.
- Bestandsdaten: Read-Modify-Write mit Merge, nie Replace.
- Testpolitik: kein Mock-Theater, keine Dateiinhalt-Checks als Verhaltensnachweis. Tests über
  echte Senken/Dateisystem-Nähte (Vorbild: `test_issue_1169_compare_alert_consumer.py`, echter
  lokaler Telegram-HTTP-Server, echtes IMAP-Postfach).
- Testdateien nach VERHALTEN benennen, nie nach Issue-Nummer (neue Dateien).

## Nicht-Ziele / bewusst unverändert

- Nowcast (`compare_radar_alert.py`) und amtliche Warnungen (`compare_official_alert.py`)
  werden **nicht** vollständig in einen gemeinsamen Ablauf gezogen — nur AG1
  (Kanal-Resolver-Delegation, verhaltensgleich) und AG6 (Pausiert/Archiviert-Riegel,
  PO-Vorgabe) reichen bewusst in diese Dateien hinein. Alles andere bleibt S3/S4.
- Kein neuer Kanal-Schalter im Frontend — `AlertChannelPicker` existiert bereits.
- Keine Änderung an Empfindlichkeitsstufen, Schwellen, `metric_alert_levels` oder am
  #961-Filter.
- Keine Änderung an `entity_type`-Vokabular (bleibt `"trip"`/`"compare"`, S1).
- Kein neuer Go-Endpunkt, kein neuer Cron-Job — `api/routers/scheduler.py` (zwei Endpunkte) und
  `internal/scheduler/scheduler.go` (zwei `*/15`-Jobs) bleiben unangetastet.
- Radar-Onset- und amtliche Telegram-Nachrichten bleiben gebündelt (bewusst NICHT auf
  „eine je Ort" umgestellt — das wäre S3/S4-Scope).
- **Der Handversand prüft den Stilllegungs-Riegel NICHT — PO-Entscheidung 2026-08-04, Anlass
  Adversary-Fund F002 (Runde 1).** `src/services/scheduler_dispatch_service.py:425-458`
  (`send_compare_preset`, Endpunkt `POST /api/scheduler/compare-presets/{id}/send`) ruft
  `is_silenced()` an keiner Stelle auf; `src/app/loader.py:291-330` (`load_compare_presets`)
  filtert pausierte/archivierte Presets nicht heraus. Ein pausierter oder archivierter
  Ortsvergleich kann damit weiterhin per Knopf zugestellt werden — **das bleibt so**.
  Begründung: der Knopf ist eine ausdrückliche Nutzerhandlung, der Riegel richtet sich gegen
  das **automatische** Senden. Dieselbe Linie wie AG5, wo genau dieser Endpunkt bewusst
  `on_demand=True` übergibt. Kein Code, kein AC, keine offene Lücke.

## Risiken

| | Risiko | Test, der es fängt |
|---|---|---|
| **R1** | Telegram/SMS trugen keine Ortszuordnung; SMS-Kopf zeigte die Ortsliste doppelt | AG3 AC-7/AC-8: SMS trägt Ortsnummern je Ereignis, Telegram nennt je Nachricht genau einen Ortsnamen |
| **R2** | Anker+Gedächtnis-Kopplung könnte einen echten Alarm verschlucken, wenn nur der Reset, nicht aber der Anker bedingt gemacht wird (oder umgekehrt) | AG5 AC-15/AC-19: ein starker Ausschlag nach Handversand bzw. nach geplantem Briefing löst zuverlässig aus |
| **R3** | Reset muss über ALLE Orte des Presets laufen und `official_alert:`-Schlüssel schonen; ein still übersprungener Ort meldet danach nie wieder | AG5 AC-16 (3 Orte, alle zurückgesetzt), AC-17 (amtlicher Schlüssel bleibt) |
| **R4** | Resolver liest aus `preset.raw` bzw. Dataclass-Feld statt Rohdict ⇒ stumm E-Mail-only, unsichtbare Nicht-Änderung; fehlendes Feld darf nie als „an" gelten | AG1 AC-2, AG4 AC-11: fehlender Schlüssel ⇒ kein Telegram, über beide Aufrufer |
| **R5** | Ruhezeit mit nur einem gesetzten Feld darf nicht dauerhaft unterdrücken | AG2 AC-5 |
| **R6** (neu, gemessen) | `test_success_status_guard.py:1523-1530`/`:1782-1786` verankert `compare_alert.py::check_all_compare_presets` per Pfad+Ordinal (`datei::funktion::ordinal`) samt erwarteter `try/except`-Zahl. Strukturelle Änderungen (Ruhezeit-Vorziehen, Guard-Aufruf) können die Ordinal-Zählung verschieben und den Wächter fälschlich auslösen | Wächter-Lauf nach jedem Arbeitsgang; bei Verschiebung Ordinal-Schlüssel aktualisieren, nicht den Wächter aufweichen |

## Betroffene Dateien

| Datei | Art | Arbeitsgang | Beschreibung |
|---|---|---|---|
| `src/services/compare_alert_channels.py` | CREATE | AG1 | Der EINE Compare-Kanal-Resolver |
| `src/services/compare_alert_guard.py` | CREATE | AG6 | `is_silenced(preset)` — Pausiert/Archiviert-Riegel; ODER-verknüpft nach Vorlage `subscriptionHelpers.ts:83-88` |
| `src/services/alert_briefing_anchor.py` | CREATE | AG5 | Geteilter Baustein Anker-Schreiben + Gedächtnis-Reset, `on_demand`-Gate |
| `src/services/compare_alert.py` | MODIFY | AG2, AG4, AG6 | Ruhezeit vor Fetch; `channels={"email"}` → Resolver; früher Guard-Aufruf |
| `src/services/compare_radar_alert.py` | MODIFY | AG6 | Guard-Aufruf ergänzt |
| `src/services/compare_official_alert.py` | MODIFY | AG1, AG6 | Delegation an Resolver + Guard statt Inline-Code, verhaltensgleich |
| `src/services/scheduler_dispatch_service.py` | MODIFY | AG1, AG5 | Delegation an Resolver; `send_one_compare_preset`/`send_compare_preset` nutzen den Anker+Gedächtnis-Baustein mit `on_demand`-Flag |
| `src/services/trip_report_scheduler.py` | MODIFY | AG5 | `:959-972` delegiert an den geteilten Baustein statt eigener Inline-Logik |
| `src/output/renderers/alert/render.py` | MODIFY | AG3 | `_sms_token`/`render_sms` mit optionaler Orts-Positions-Kodierung; neue Per-Ort-Telegram-Renderfunktion |
| `src/services/notification_service.py` | MODIFY | AG3 | `send_multi_location_deviation_alert`/`_dispatch_alert_message`: Telegram-Fan-out je Ort NUR im Deviation-Alert-Pfad |
| `tests/tdd/test_issue_1169_compare_alert_consumer.py` | MODIFY | AG4 | Assertion `:645`, Modul-Docstring `:13-14`, Test-Docstring `:591-594` — E-Mail-only-Festschreibung entfernen/umschreiben |
| `src/services/compare_slot_scheduler.py` | MODIFY | AG6 | `:78-83` delegiert an `is_silenced` (vor der `end_date`-Prüfung `:85-89`). `paused_at` wirkt hier **tatsächlich**: ein pausierter Ortsvergleich bekommt auch kein reguläres Briefing mehr — bewacht durch das F001-Testpaar, s. AG6-Text |
| `tests/tdd/test_compare_alert_quiet_hours_precedes_fetch.py` | MODIFY | AG6 | Fixture `:142` `schedule: "manual"` → aktiver Zeitplan (sonst blockt der Riegel den Test) |
| `tests/tdd/test_compare_alert_metric_gating.py` | MODIFY | AG6 | Fixture `:110`, dito |
| `tests/tdd/test_compare_radar_alert.py` | MODIFY | AG6 | Fixture `:88`, dito |
| `tests/tdd/test_issue_1170_compare_alert_config.py` | MODIFY | AG6 | **Nachtrag 2026-08-04** — zwei Preset-Builder trugen `schedule: "manual"`, zwei Tests wurden durch den Riegel rot (`sent=0` statt 1). Prüfen Empfindlichkeitsstufen + Bündelung, also weiterhin gültige Zusicherungen ⇒ aktiver Zeitplan |
| `tests/tdd/test_issue_1169_compare_alert_consumer.py` | MODIFY | AG4, **AG6** | AG6-Nachtrag: Preset-Builder auf aktiven Zeitplan. ⚠️ Datei trägt `pytestmark = pytest.mark.email` und läuft nur in der Live-Schicht (`/e2e-verify`) — die Korrektur ist **statisch abgeleitet, nicht durch einen Testlauf belegt**. Beim E2E-Lauf gegenprüfen |
| `tests/test_success_status_guard.py` | MODIFY (bedingt) | AG2, AG6 | Ordinal-Schlüssel nachziehen, falls Strukturänderung sie verschiebt. **AG6: Bedingung trat NICHT ein** — Wächter ohne Änderung grün (gemessen 2026-08-04) |

## Testplan

Je Arbeitsgang mindestens ein neuer, verhaltensbenannter Testfall; Mandantentrennung wird pro
Arbeitsgang mit einem zweiten Nutzer stichprobenartig mitgeprüft (nicht jedes AC einzeln
dupliziert).

- **AG1** — `tests/tdd/test_compare_alert_channels.py` (neu): Resolver direkt sowie über beide
  Bestandsaufrufer. Bestandssuiten (`test_compare_official_alert.py`,
  Kanal-Tests in `scheduler_dispatch_service`-Suiten) müssen unverändert grün bleiben.
- **AG2** — `tests/tdd/test_compare_alert_quiet_hours_precedes_fetch.py` (neu): Fetch-Spion
  zählt Aufrufe; Cooldown-/Tageslimit-Zähler vorher/nachher verglichen.
- **AG3** — `tests/tdd/test_alert_render_multi_location_messages.py` (neu): SMS-Zahlenkodierung
  + 140-Zeichen-Grenze, Telegram-Per-Ort-Liste, E-Mail-Bündelung unverändert (Golden-Vergleich
  gegen bestehende gerenderte Struktur).
- **AG4** — `tests/tdd/test_compare_alert_channel_delivery.py` (neu) für die Wirkungs-ACs;
  **zwingend** `tests/tdd/test_issue_1169_compare_alert_consumer.py` an den drei genannten
  Stellen umschreiben (nicht nur die Assertion — sonst widerspricht die Doku dem neuen
  Verhalten).
- **AG5** — `tests/tdd/test_compare_briefing_anchor_and_memory_reset.py` (neu), Vorbild
  `test_alert_state_briefing_reset.py:151` (AC-20-Muster „amtliche Einträge überleben"). Deckt:
  kein Alarm bei unverändertem Wert nach Briefing, Alarm bei starkem Ausschlag, alle Orte
  zurückgesetzt, Handversand ändert nichts, zweiter Nutzer unberührt.
- **AG6** — `tests/tdd/test_compare_alert_paused_archived_silent.py` (neu): pausiert/archiviert
  für beide Pfade (Δ-Wetter, Nowcast), beide Merkmale einzeln (AC-20 Fall b!), Fetch-Spion für
  AC-20b, aktives Preset desselben Nutzers meldet weiter, Verdrahtungstests für AC-28.
  **Zwingend mitzuziehen — vier Bestandsfixtures führen ein Preset mit `schedule: "manual"`
  und erwarten einen Alarm; sie werden durch den Riegel rot:**
  `test_compare_alert_quiet_hours_precedes_fetch.py:142`,
  `test_compare_alert_metric_gating.py:110`, `test_compare_radar_alert.py:88`,
  `test_compare_preset_send.py:63` (Handversand — voraussichtlich nicht betroffen, prüfen).
  Jeder dieser Tests prüft eine **andere**, weiterhin gültige Zusicherung ⇒ die Fixture wird
  auf einen aktiven Zeitplan korrigiert. **Verboten:** den Riegel abschwächen oder den Test
  löschen, um sie grün zu bekommen.
- Nach jedem Arbeitsgang: `python3 .claude/hooks/workflow.py status` (LoC-Budget) und ein
  gezielter Lauf von `tests/test_success_status_guard.py` (Ordinal-Drift, R6).

## Acceptance Criteria

**AG1 — Kanal-Ermittlung zusammenlegen**

- **AC-1:** Given ein Compare-Preset mit `send_telegram: true` und telegramfähigen
  Konto-Settings, When `compare_official_alert.py::check_all_compare_presets()` über den neuen
  gemeinsamen Resolver läuft, Then wird — wie vor dem Umbau — eine Telegram-Nachricht an der
  Telegram-Senke zugestellt.
  - Test: echter lokaler Telegram-Sink, `send_count() == 1` vor und nach der Umstellung.

- **AC-2:** Given ein Compare-Preset OHNE den Schlüssel `send_telegram` (fehlt ganz im Dict),
  When der gemeinsame Resolver über `compare_official_alert.py` ODER
  `scheduler_dispatch_service.py::send_one_compare_preset` ausgewertet wird, Then bleibt der
  Telegram-Kanal in der tatsächlichen Zustellung aus.
  - Test: Preset-Fixture ohne den Schlüssel, `telegram_sink.send_count() == 0` über beide Pfade.

- **AC-3:** Given die volle Bestands-Testsuite beider betroffenen Dateien
  (`compare_official_alert.py`, `scheduler_dispatch_service.py`), When sie nach der
  Konsolidierung läuft, Then bleiben alle bisherigen Tests unverändert grün — kein Test wird
  angepasst, um den Umbau nachträglich zu „reparieren".
  - Test: `uv run pytest tests/tdd/test_compare_official_alert.py` und die
    Dispatch-Kanal-Tests, Diff der Testdateien = 0 Zeilen.

**AG2 — Ruhezeiten vor die Erkennung**

- **AC-4:** Given ein Compare-Preset mit aktiver Ruhezeit (z. B. 22:00–07:00) und aktueller
  Ortszeit 23:00, When `CompareAlertService.check_all_compare_presets()` läuft, Then wird
  `CompareLocationWeatherSource.fetch()` für keinen Ort dieses Presets aufgerufen (0 Aufrufe).
  - Test: Fetch-Spion (Zähl-Seam, kein Mock) auf `weather_source`, Aufrufzähler nach dem Lauf
    prüfen.

- **AC-5:** Given ein Preset, bei dem nur `alert_quiet_from` gesetzt ist und
  `alert_quiet_to` fehlt, When der Lauf zu einer beliebigen Uhrzeit erfolgt, Then wird der
  Alarm trotz des unvollständigen Ruhezeit-Felds ausgelöst und zugestellt.
  - Test: Preset mit nur einem Ruhezeit-Feld, auslösende Wetteränderung, Mail kommt an.

- **AC-6:** Given ein Alarm, der wegen aktiver Ruhezeit unterdrückt wird, When der Lauf beendet
  ist, Then sind weder der Sperrzeit-Zähler (`ThrottleStore`, Scope `compare_preset`) noch die
  Tages-Obergrenze (`alert_daily_limit`) für dieses Preset verändert.
  - Test: Zähler-Snapshot vor/nach dem unterdrückten Lauf, exakte Gleichheit.

**AG3 — Darstellung der Kurznachrichten**

- **AC-7:** Given ein gebündelter Änderungsalarm für zwei Orte (Position 1 und 2 in der
  konfigurierten Ortsliste des Presets) mit je einer Metrik-Änderung, When die SMS gerendert
  wird, Then enthält der Text für jedes Ereignis die Ortsposition als Zahl statt eines
  ausgeschriebenen Ortsnamens, und die Gesamtlänge bleibt ≤140 Zeichen.
  - Test: `render_sms()` mit Positions-Mapping aufrufen, Text auf Ziffern statt Namen und
    Länge prüfen.
  - **Verschärft 2026-08-04 (PO, `e9f23605`):** Der Text enthält **gar keinen** Ortsnamen
    mehr — auch keinen Kopf mit der Ortsliste und keinen Vergleichsnamen. Gilt ebenso für den
    Ein-Ort-Fall. Nachgewiesen durch `tests/tdd/test_alert_sms_location_positions.py`
    (K-1/K-2) und live auf Staging am ausgelieferten Renderer.

- **AC-7b (neu 2026-08-04, PO):** Given einen Ortsvergleich, dessen Ortsliste sich geändert
  hat (ein Ort gelöscht), When der nächste Änderungsalarm gerendert wird, Then ist die
  Positionszahl der 1-basierte Index in der **aktuellen** Liste — die folgenden Orte rücken
  auf, es bleibt keine Lücke. Unverändert zählt ein Ort mit, der noch in der Liste steht und
  nur diesmal nicht ausgelöst hat (sonst sprängen die Zahlen von Lauf zu Lauf).
  PO wörtlich: *„die nummer soll immer die Reihenfolge darstellen. Wenn ein Ort gelöscht wird,
  rücken die anderen nach, das ist kein Fehler sondern für den User nachvollziehbares
  Verhalten."* Ersetzt die am 2026-08-03 eingeführte Gegen-Zusicherung.

- **AC-7c (neu 2026-08-04, PO):** Given einen Ortsvergleich mit
  `display_config.telegram_style="kurzform"` (#1260), When ein Änderungsalarm für mehrere Orte
  ausgelöst wird, Then geht **EINE gemeinsame** Telegram-Nachricht mit dem Kurznachrichten-Text
  raus — kein Fan-out je Ort. Bei `"rich"` oder fehlendem Wert bleibt es bei einer Sprechblase
  je Ort (AC-8). Begründung: die Ortsnummer ergibt nur im gemeinsamen Text Sinn, und die beiden
  anderen Kurzstil-Pfade (Trip, amtlich) senden ebenfalls genau eine.
  🔴 **Der Schalter war auf diesem Pfad wirkungslos** — und blosses Durchreichen hätte nicht
  gereicht: `if telegram_groups:` (`notification_service.py:1175`) steht **vor** dem
  Kurzform-Zweig (`:1192`), und der Ortsvergleich-Änderungsalarm setzt `telegram_groups` seit
  AG3a immer. Kurzform hat jetzt Vorrang. Die Stil-Auflösung liegt an EINER Stelle
  (`compare_alert_channels.effective_compare_telegram_style`, ADR-0021);
  `compare_official_alert.py` delegiert nur noch.

- **AC-8:** Given ein gebündelter Änderungsalarm für drei Orte, When der Telegram-Versand über
  `NotificationService.send_multi_location_deviation_alert()` mit einem echten lokalen
  Telegram-Sink erfolgt, Then kommen an der Senke genau drei einzelne Nachrichten an, jede mit
  dem ausgeschriebenen Namen genau eines Ortes.
  - Test: echter lokaler HTTP-Sink, drei empfangene Requests, je einer trägt einen der drei
    Ortsnamen und keinen anderen.

- **AC-9:** Given denselben gebündelten Alarm für drei Orte, When die E-Mail gerendert wird,
  Then bleibt sie EINE einzelne Mail mit allen drei Orten — unverändert gegenüber dem Stand vor
  dieser Scheibe.
  - Test: Golden-Vergleich der gerenderten E-Mail-Struktur (Anzahl Ortsblöcke, keine
    Aufsplittung) vor/nach dem Umbau.

- **AC-24:** Given ein gebündelter Änderungsalarm für zehn Orte, When der Telegram-Versand
  läuft, Then kommen zehn einzelne Nachrichten an der Senke an — es gibt **keine** Obergrenze,
  ab der wieder gebündelt wird (PO-Entscheidung E-AG3-1, Kontingent-Risiko benannt und
  angenommen).
  - Test: zehn Orte, `telegram_sink.send_count() == 10`.

- **AC-25:** Given einen Telegram-Fan-out über drei Orte, bei dem die **zweite** Zustellung
  fehlschlägt, When der Versand läuft, Then wird die dritte Nachricht trotzdem zugestellt
  (kein Abbruch der Serie), der Nutzer erhält einen Hinweis auf die unvollständige Zustellung,
  und das Alarm-Protokoll weist Telegram NICHT als vollständig zugestellt aus.
  - Test: Senke, die beim zweiten Aufruf wirft; danach 2 erfolgreiche Zustellungen + 1 Hinweis;
    `notif_result.telegram_fully_sent is False`; Protokolleintrag entsprechend.
    Muster: `notification_service.py:359-382` + `_send_telegram_incomplete_hint()` `:395` (#1370).

- **AC-26:** Given einen Trip-Änderungsalarm, einen Trip-Radar-Alarm und einen
  Ortsvergleich-Radar-Alarm, When sie nach dem Umbau versendet werden, Then bleibt es bei
  jeweils EINER Telegram-Nachricht — der Fan-out greift ausschließlich im
  Ortsvergleich-Änderungs-Pfad.
  - Test: je ein Versand über die drei anderen Einstiege, `telegram_sink.send_count() == 1`.
    Begründung: alle vier Pfade laufen durch dieselbe `_dispatch_alert_message()`
    (`notification_service.py:1026`), es gibt kein Feld, das „Ortsvergleich" markiert —
    der Fan-out muss über einen neuen, defaultierten Parameter laufen, gesetzt nur in
    `send_multi_location_deviation_alert()` (`:544-552`).

**AG4 — Telegram/SMS für Ortsvergleich scharf schalten**

- **AC-10:** Given ein Compare-Preset mit `send_telegram: true` und telegramfähigen
  Konto-Settings, When `CompareAlertService.check_all_compare_presets()` einen Änderungsalarm
  für einen Ort auslöst, Then kommt an der Telegram-Senke genau eine Zustellung mit dem
  Ortsnamen an.
  - Test: echter Telegram-Sink, `send_count() == 1`, Inhalt trägt den Ortsnamen.

- **AC-11:** Given ein Preset OHNE den Schlüssel `send_telegram`, When derselbe Alarm ausgelöst
  wird, Then bleibt die Telegram-Senke unberührt (0 Zustellungen) — E-Mail bleibt einziger
  Kanal, wie vor dieser Scheibe.
  - Test: `telegram_sink.send_count() == 0`, E-Mail wurde zugestellt.

- **AC-12:** Given ein Preset mit `send_sms: true` bei einem Free-Tier-Nutzer, When ein Alarm
  ausgelöst wird, Then bleibt die SMS-Senke unberührt (0 Zustellungen).
  - Test: Free-Tier-Nutzer-Fixture, `sms_sink.send_count() == 0`.

- **AC-13:** Given ein Alarm mit E-Mail- und Telegram-Zustellung, When der Eintrag im
  Alarm-Protokoll geschrieben wird, Then listet `effective_channels` beide Kanäle und
  `sent_channels`/`reachable_channels` spiegeln die tatsächliche Zustellung wider.
  - Test: `alert_log`-Datei nach dem Lauf laden, Feldwerte prüfen.

**AG5 — Anker + Gedächtnis als EIN geteilter Baustein**

- **AC-14:** Given ein Ortsvergleichs-Preset mit einem Ort, dessen Wert sich seit dem letzten
  geplanten Briefing NICHT verändert hat, When der geplante Briefing-Versand läuft und danach
  der Änderungsalarm-Check, Then wird für diesen unveränderten Wert KEIN Alarm ausgelöst.
  - Test: `send_one_compare_preset` (Daily-Pfad) gefolgt von `CompareAlertService`-Lauf,
    keine E-Mail/Telegram-Zustellung für den unveränderten Ort.

- **AC-15:** Given denselben Ablauf, aber der Wert ändert sich nach dem Briefing stark (über
  der Schwelle), When der nächste Änderungsalarm-Check läuft, Then wird der Alarm ausgelöst
  und zugestellt.
  - Test: wie AC-14, aber mit Δ über der Schwelle — Zustellung erfolgt.

- **AC-16:** Given ein Preset mit DREI Orten, When der geplante Briefing-Reset läuft, Then sind
  die Änderungs-Schlüssel in den Zustandsdateien ALLER drei Orte (`f"{preset_id}:
  {location_id}"`) zurückgesetzt.
  - Test: drei Zustandsdateien vorbelegen, nach dem Reset alle drei auf leer (bzw. nur
    `official_alert:`-Reste) prüfen.

- **AC-17:** Given eine Zustandsdatei mit einem `official_alert:`-Schlüssel und einem
  Änderungs-Schlüssel, When der Briefing-Reset für diesen Ort läuft, Then bleibt der
  `official_alert:`-Eintrag unverändert erhalten und nur der Änderungs-Eintrag verschwindet.
  - Test: Vorbild `test_alert_state_briefing_reset.py:151` (AC-20-Muster), auf den Compare-Pfad
    übertragen.

- **AC-18:** Given zwei Nutzer mit gleichnamigem Preset (identische `preset_id`), When Nutzer A
  ein Briefing versendet, Then bleibt das Melde-Gedächtnis des gleichnamigen Presets von
  Nutzer B unverändert.
  - Test: zwei Datenverzeichnisse, kreuzweiser Vergleich der Zustandsdateien.

- **AC-19:** Given ein Handversand (`send_compare_preset`, Einzelversand-Endpunkt), When er
  ausgeführt wird, Then wird WEDER der Δ-Anker neu gesetzt NOCH das Melde-Gedächtnis geleert —
  UND ein danach auftretender starker Ausschlag löst beim nächsten regulären Check trotzdem
  einen Alarm aus.
  - Test: Snapshot- und Zustandsdatei vor/nach Handversand vergleichen (unverändert), danach
    Δ über Schwelle simulieren, Alarm muss ausgelöst werden.

- **AC-27:** Given einen Trip mit vorbelegtem Melde-Gedächtnis und gesetztem Δ-Anker, When ein
  geplantes Briefing (`on_demand=False`) über den neuen geteilten Baustein läuft, Then sind
  Anker und Gedächtnis danach in **exakt** demselben Zustand wie vor dem Umbau — Reset für
  genau **eine** Kennung (`trip.id`, nicht mehr und nicht weniger), `official_alert:`-Schlüssel
  erhalten, Anker vor Reset geschrieben. Und bei `on_demand=True` bleibt beides unangetastet.
  - Test: die sieben Bestandstests aus `tests/tdd/test_alert_state_briefing_reset.py` bleiben
    **unverändert** grün (keine Zeile angefasst) — plus ein neuer Test, der den Datei-Zustand
    nach dem geplanten Briefing gegen einen an `f938159b` gemessenen Goldwert vergleicht und
    die Zahl der Reset-Aufrufe zählt. Ohne die Zählung bliebe unbemerkt, wenn der Baustein den
    Trip versehentlich wie ein Preset über mehrere Kennungen zurücksetzt.
  - Mutations-Gegenprobe (Pflicht): Reset **vor** den Anker ziehen · zweite Kennung
    hinzufügen · `on_demand` beim Trip-Aufruf hart auf `False` verdrahten — jede dieser drei
    Verfälschungen MUSS mindestens einen Test rot machen.

**AG6 — Pausierte und archivierte Ortsvergleiche schweigen**

- **AC-20:** Given ein Ortsvergleichs-Preset, das die Oberfläche als „pausiert" beschriftet —
  also `paused_at` gesetzt ODER `schedule: "manual"`, jeweils für sich genügend — und einer
  auslösenden Wetteränderung, When `CompareAlertService.check_all_compare_presets()` läuft,
  Then wird KEIN Änderungsalarm versendet.
  - Test: **drei** Presets nacheinander — (a) nur `schedule="manual"`, (b) nur `paused_at`
    gesetzt bei aktivem `schedule`, (c) beides gesetzt. In allen drei Fällen auslösender
    Δ-Wert, keine Zustellung auf keinem Kanal. Fall (b) ist der eigentliche Prüfstein: er
    fällt durch, wenn der Riegel nur auf `schedule` liest.

- **AC-20b:** Given dasselbe pausierte Preset, When der Änderungsalarm-Lauf es erreicht, Then
  wird für dieses Preset **kein Wetterabruf ausgelöst** — der Riegel greift vor der
  Datenbeschaffung, nicht erst vor dem Versand.
  - Test: Fetch-Spion zählt Aufrufe (Muster `test_compare_alert_quiet_hours_precedes_fetch.py`
    aus AG2); Zähler bleibt bei 0. Ohne dieses AC wäre der Riegel erfüllbar, indem nur der
    Versand unterdrückt wird — dann verbrauchen pausierte Vergleiche weiter Abruf-Kontingent
    (#1329) und die Zusicherung „als würde es sie nicht geben" wäre nur halb wahr.

- **AC-21:** Given dasselbe pausierte Preset mit einem auslösenden Radar-Nowcast, When
  `CompareRadarAlertService.check_all_compare_presets()` läuft, Then wird KEIN Nowcast-Alarm
  versendet.
  - Test: pausiertes Preset, Onset-Bedingung erfüllt, keine Zustellung.

- **AC-22:** Given ein archiviertes Preset (`archived_at` gesetzt) mit auslösender Bedingung,
  When beide Alarm-Checker (Δ-Wetter und Nowcast) laufen, Then wird in KEINEM der beiden Pfade
  ein Alarm versendet.
  - Test: archiviertes Preset, beide Checker nacheinander, keine Zustellung.

- **AC-23:** Given ein aktives (nicht pausiertes/archiviertes) Preset desselben Nutzers mit
  derselben auslösenden Bedingung, When beide Checker laufen, Then wird der Alarm wie gewohnt
  versendet.
  - Test: zweites, aktives Preset in derselben Fixture, Zustellung erfolgt — Beweis, dass der
    Riegel nicht zu breit greift.

- **AC-28:** Given die Stilllegungs-Regel („pausiert oder archiviert"), When irgendein
  Alarmpfad sie auswertet, Then stammt die Antwort aus **genau einer** Fassung
  (`compare_alert_guard.is_silenced`) — `compare_official_alert.py` hält keine eigene
  Inline-Prüfung mehr.
  - Test: Verdrahtungstest je Aufrufer nach dem Muster aus AG1 — das `is_silenced`-Symbol wird
    **im verbrauchenden Modul** ersetzt; baut eine Stelle wieder eigene Logik, wird der Test
    rot. Zusätzlich: das amtliche Bestandsverhalten (`test_compare_official_alert.py`, AC-4
    aus #1233) bleibt unverändert grün — die Ablösung ist verhaltensgleich.
  - Nicht Teil dieses AC: `scheduler_dispatch_service.py:66-68` (andere Aussage, s. AG6-Text).

## Known Limitations

- **AG6 / F004 (LOW, bewusst offen — Adversary Runde 4).** Der Stilllegungs-Riegel im
  Briefing-Weg ist je Slot einzeln bewacht (Morgen und Abend, s. F003), aber nicht für den
  Fall **beider gleichzeitig aktiver Slots** (KL-5). Eine Verfälschung, die `paused_at`
  ausschließlich in dieser Kombination neutralisiert, rutscht durch alle 46 Tests.
  **Kein Fix** — der ausgelieferte Code hat genau EINEN uniformen Guard vor der
  Slot-Auflösung (`compare_slot_scheduler.py:78-83`) und keine Kombinations-Sonderbehandlung;
  eine solche Mutation wäre kein plausibler Refactoring-Unfall wie F001/F003, sondern müsste
  bewusst neu eingeführt werden. Der Adversary hat sie selbst als Überabsicherung eingestuft.
  Sollte dort je eine Fallunterscheidung nach Slot-Kombination entstehen, ist dieser Test
  nachzuziehen.
- Die SMS-Ortsnummer ist nur innerhalb EINES Presets stabil und deckungsgleich mit der
  Vergleichs-E-Mail-Spaltenreihenfolge zum Sendezeitpunkt. Ändert der Nutzer die Ortsliste
  zwischen zwei Meldungen, kann sich die Nummer für einen Ort verschieben — analog zum
  bestehenden Verhalten der E-Mail-Spalten, kein neues Risiko.
- Die Telegram-Aufteilung „eine Nachricht je Ort" gilt in dieser Scheibe **ausschließlich** für
  den Δ-Wetter-Pfad. Radar-Onset (S3) und amtliche Warnungen (S4) bleiben gebündelt, bis diese
  Scheiben eine eigene PO-Entscheidung dazu einholen.
- `compare_radar_alert.py:180` schreibt weiterhin einen nirgends gelesenen
  `radar_onset`-Schlüssel in dieselbe Zustandsdatei, die der neue Reset-Baustein anfasst — der
  Schlüssel wird beim Reset mitgelöscht (folgenlos, aber für S3 zu dokumentieren).
- `entity_type` bleibt bei `"trip"`/`"compare"` (S1) — keine Erweiterung für den neuen
  Baustein-Namensraum.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue — diese Scheibe setzt die bereits dokumentierten Entscheidungen um
  (ADR-0021 Engine-Extraktion, ADR-0043 Relevanzfilter) und die PO-Vorgabe „Trip/Compare
  möglichst viel Code teilen" (CLAUDE.md, mehrfach bekräftigt). Kein neues Architekturprinzip.
- **Rationale:** Die Ablaufsteuerung bleibt bewusst als „Ortsvergleich zieht an den
  bestehenden Trip-Ablauf heran, ergänzt um einen echten Sammelbaustein" gebaut (Variante B der
  Analyse), nicht als neuer Hüll-Service über beiden Pfaden (Variante A) — letztere hätte den
  Trip-Hauptpfad ohne Nutzergewinn angefasst und wäre das höhere Risiko für den ausbleibenden
  Alarm gewesen.

## Changelog

- 2026-08-03: Initiale Spec. Sechs Arbeitsgänge nach PO-Entscheidungen E2–E5
  (`docs/context/rework-1467-s2-aenderungsalarm.md`) zugeschnitten, jeder für sich
  auslieferbar. Zeilenangaben gegen den Ist-Stand vom 2026-08-03 verifiziert.
- 2026-08-03: **AG2 umgesetzt** (AC-4/5/6, `src/services/compare_alert.py`). Ruhezeit-Prüfung
  vor den Wetterabruf gezogen (Muster `compare_official_alert.py:105-113`), dieselbe geteilte
  Funktion `DeviationAlertEngine.is_quiet_hours()`. Adversary (4 Runden, VERIFIED) fand und
  behob zwei Befunde: (1) ein unbrauchbarer Ruhezeit-Wert (z. B. `"25:00"`) ließ den neuen
  Riegel ungefangen werfen und brach den gesamten Preset-Lauf des Nutzers ab statt nur den
  einen Ort zu überspringen — jetzt `try/except`, unbrauchbarer Wert gilt als „keine Ruhezeit
  gesetzt" (sichere Richtung: lieber eine Meldung zu viel als eine verschluckte) und wird per
  `logger.warning` inkl. Ausnahmetyp protokolliert; (2) `except ValueError` allein reichte
  nicht — Nicht-String-Werte (Zahl, Liste, Bool, Dict) werfen `TypeError` und kamen weiterhin
  durch, jetzt `except Exception`.

- 2026-08-04 (v1.1, `e9f23605`): **PO-Korrektur an AG3b.** (1) Der Ortsname entfaellt in der
  Alarm-Kurznachricht vollstaendig statt nur der Doppelung — auch im Ein-Ort-Fall; die
  Positionszahl IST die Ortsangabe (AC-7 verschaerft). (2) Beim Loeschen eines Ortes ruecken
  die folgenden Nummern nach; die am 2026-08-03 eingefuehrte Gegen-Zusicherung
  („unaufloesbare Kennung behaelt ihren Platz") faellt samt Test (AC-7b, ersetzt sie).
  (3) `display_config.telegram_style="kurzform"` wirkt jetzt auch auf dem
  Aenderungsalarm-Pfad und sendet EINE gemeinsame Nachricht; der Kurzform-Zweig hat Vorrang
  vor dem Fan-out je Ort (AC-7c). Stil-Aufloesung DRY in `compare_alert_channels.py`.
  Adversary VERIFIED, 7 von 7 Kern-Mutationen gefangen. Staging-Nachweis ueber
  Telegram-Kurzform: 1 Nachricht bei „kurzform" gegen 2 bei „rich".

- 2026-08-04 (v1.2): **AG6 praezisiert vor der Umsetzung**, drei Messungen am Ist-Stand
  (`3acc8515`) und eine PO-Entscheidung. (1) **AC-20 ODER-verknuepft** — „pausiert" ist, was
  die Oberflaeche als pausiert beschriftet (`subscriptionHelpers.ts:83-88`): `paused_at`
  gesetzt ODER `schedule == "manual"`, jedes fuer sich genuegend. Der alte Wortlaut las nur
  `schedule` und haette ein per Knopf pausiertes Preset ohne Zeitplan-Umstellung
  durchgelassen. PO-Entscheidung 2026-08-04 gegen die vorgelegte Alternative „nur
  ausdruecklich Pausiertes schweigt"; die Betriebsfolge (alle fuenf realen Ortsvergleiche
  schweigen zunaechst) wurde vor der Entscheidung genannt. (2) **AC-20b neu** — der Riegel
  greift vor dem Wetterabruf, nicht erst vor dem Versand; ohne dieses AC waere die Zusicherung
  „als wuerde es sie nicht geben" durch reine Versandunterdrueckung scheinbar erfuellbar.
  (3) **AC-28 neu** — genau EINE Fassung der Stilllegungs-Regel, belegt per Verdrahtungstest;
  Anlass ist der Reuse-Befund, dass dieselbe Frage heute an vier Stellen unterschiedlich
  beantwortet wird (#1481 Baustein B, Pruefung vor der AC-Freigabe). (4) Vier Bestandsfixtures
  mit `schedule: "manual"` werden durch den Riegel rot und sind als Pflichtarbeit benannt —
  Fixture korrigieren, nicht den Riegel abschwaechen. **Belegter Schadensfall** ergaenzt: der
  einzige Ortsvergleich-Alarm der Historie ging vier Tage nach dem Pausieren des Presets raus.

- 2026-08-04 (v1.2, Fortschreibung nach Adversary-Runde 1 zu AG6): zwei Korrekturen, **kein
  Produktivcode geaendert**. (1) **F001 (MEDIUM) behoben** — der Satz „dort ist `paused_at`
  neu, wirkt aber praktisch nicht, weil `end_date` unmittelbar davor separat geprueft wird"
  war eine Annahme statt einer Messung und in beiden Haelften falsch: der Guard steht
  `compare_slot_scheduler.py:78-83` VOR der `end_date`-Pruefung (`:85-89`), und beide sind
  unabhaengige Bedingungen. Ersetzt durch die gemessene Wirkung: `paused_at` legt im
  Briefing-Weg tatsaechlich still (kein reguläres Ortsvergleich-Briefing mehr fuer ein
  pausiertes Preset) — fachlich gewollt, bleibt so. Neu bewacht durch das Testpaar
  `test_paused_preset_is_not_due_for_regular_compare_briefing` /
  `test_active_preset_with_same_fixture_is_due_for_regular_compare_briefing` in
  `tests/tdd/test_compare_alert_paused_archived_silent.py`. Mutations-Beleg: die gezielte
  Neutralisierung `is_silenced({**preset, "paused_at": None})` in `presets_due_for_hour` liess
  vorher alle 42 einschlaegigen Tests gruen und macht jetzt genau diesen einen Test rot (1 von
  44); die vollstaendige Entfernung des `paused_at`-Zweigs aus `is_silenced` faengt jetzt 6
  statt 5 Tests. (2) **F002 (LOW) als PO-Entscheidung festgehalten** — der Handversand
  (`scheduler_dispatch_service.py:425-458`, `POST /api/scheduler/compare-presets/{id}/send`)
  prueft den Riegel bewusst NICHT; ausdrueckliche Nutzerhandlung schlaegt den Riegel gegen
  automatisches Senden, dieselbe Linie wie `on_demand=True` in AG5. Eingetragen unter
  „Nicht-Ziele / bewusst unveraendert", damit es nicht als offene Luecke wiederkehrt.

- 2026-08-04 (v1.2, Fortschreibung nach Adversary-Runde 3 zu AG6): **F003 (MEDIUM) behoben,
  reine Testarbeit — kein Produktivcode geaendert.** Der F001-Fix wurde in Runde 3 bestaetigt,
  liess aber eine Luecke derselben Fehlerklasse offen: die Fixture `_briefing_preset`
  verdrahtete `evening_enabled=False` fest und pruefte damit nur den Morgen-Slot, waehrend
  `presets_due_for_hour` Morgen- und Abend-Slot unabhaengig entscheidet (`:101-104`, KL-5).
  Eine Verfaelschung, die den Riegel ausschliesslich im Abend-Zweig neutralisiert, rutschte
  durch alle 44 Tests. Behoben durch einen **Slot-Parameter an derselben Fixture**
  (`slot="morning"|"evening"`, keine Zweitfassung) plus dem zweiten Paar
  `test_paused_preset_is_not_due_for_evening_compare_briefing` (pausiert ⇒ nicht faellig) /
  `test_active_preset_is_due_for_evening_compare_briefing` (identische Fixture ohne
  `paused_at` ⇒ faellig, Zieldatum Folgetag). Mutations-Beleg: der Guard nur im Abend-Zweig
  durch `is_silenced({**preset, "paused_at": None})` ersetzt (Morgen-Zweig unberuehrt) macht
  genau den neuen Abend-Nachweis rot (1 von 46); Morgen-Paar und Abend-Gegenprobe bleiben
  gruen. Nach Rueckspielen der Sicherungskopie 42 von 42 gruen
  (`test_compare_alert_paused_archived_silent.py` + `test_compare_preset_slot_dispatch.py`).
