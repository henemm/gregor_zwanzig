# Context: rework-1467-s2-aenderungsalarm

**Issue:** #1467 Scheibe S2 (Epic #1458, Teil 2 von #1460)
**Vorgänger:** S1 live in Produktion (`49cf1c22`) — `entity_id` + `entity_type` ersetzen `trip_id`/`preset_id`
**Track:** Full Process (Intake 5/6)

## Request Summary

Die Ablaufsteuerung für **Vorhersage-Änderungs-Alarme** von Trip und Ortsvergleich wird zu
einer zusammengelegt, parametriert über den Kontext (Etappen vs. Orte). Nutzersichtbarer
Gewinn: Ortsvergleich-Änderungsalarme gehen künftig auch per **Telegram und SMS** (heute fest
nur E-Mail), und der Ortsvergleich bekommt erstmals den **Gedächtnis-Reset beim
Briefing-Versand**.

## Related Files

| Datei | Relevanz |
|---|---|
| `src/services/trip_alert.py` (1221 Z.) | Trip-Pfad. Δ-Prüfung `check_and_send_alerts()` `:142-313`, Kanal-Resolver `_effective_alert_channels()` `:1155-1207`, Briefing-Kanal-Erbe `_briefing_channels()` `:1209-1221`. **Nur der Δ-Teil gehört zu S2** — Nowcast (S3) und amtlich (S4) liegen in derselben Datei |
| `src/services/compare_alert.py` (330 Z.) | Ortsvergleich-Pfad, vollständig S2. `check_all_compare_presets()` `:80-162`, `_build_eval_config()` `:229-248` mit **`channels={"email"}` `:246`** |
| `src/services/deviation_alert_engine.py` (262 Z.) | Bereits geteilter Auswertungskern (ADR-0021). Beide Pfade rufen `evaluate()`. **Wird nicht angefasst** |
| `src/services/notification_service.py` | `send_multi_location_deviation_alert()` `:516-552` (Compare, gebündelt) → `_dispatch_alert_message()` `:1029ff`. **Gemessen: rendert bereits E-Mail `:1056`, Telegram `:1057`, SMS `:1058`** |
| `src/services/compare_official_alert.py` | `_effective_channels()` `:250-258` — **fertiger Compare-Kanal-Resolver, existiert schon** (E-Mail immer, Telegram/SMS bei Preset-Opt-in + globaler Fähigkeit) |
| `src/services/trip_report_scheduler.py` | Trip-Briefing-Reset: Aufruf `:972`, Implementierung `_reset_alert_state_after_briefing()` `:1036-1042` → `AlertStateService.reset(trip.id)` |
| `src/services/scheduler_dispatch_service.py` | Compare-Briefing-Versand `send_one_compare_preset()` `:295-412`. Symmetrische Stelle für den fehlenden Reset: `:410-412`, direkt neben `_write_compare_alert_snapshots()` `:447` |
| `src/services/alert_state.py` | `AlertStateService`: `load` `:53`, `save` `:65`, `reset` `:73`. Seit #1460 P2 schont `reset()` Schlüssel mit Präfix `official_alert:` `:90-97` |
| `src/services/alert_log.py` | `append_entry()` `:124-142` — seit S1 `entity_id`+`entity_type` kw-only Pflicht |
| `src/services/throttle_store.py` | `:36` — Scopes `trip`, `radar`, `compare_preset` |
| `api/routers/scheduler.py` | Zwei getrennte Endpunkte: `/alert-checks` `:45-57` (Trip), `/compare-alert-checks` `:70-77` (Ortsvergleich) |
| `internal/scheduler/scheduler.go` | Zwei getrennte Cron-Jobs `*/15`: `alert_checks` `:145`, `compare_alert_checks` `:151` |
| `src/app/models.py` | `ComparePreset` `:900-968` — `send_telegram` `:947`, `send_sms` `:948`. **Kein `alert_channels`** |
| `internal/model/compare_preset.go` | `SendTelegram` `:91`, `SendSms` `:92` — laut Kommentar `:84-85` das Kanal-Opt-in, Default falsy = E-Mail-only |

## Existing Patterns

- **ADR-0021 (Engine-Extraktion):** `DeviationAlertEngine` ist bereits location-generisch und
  kennt keinen Trip. Beide Pfade speisen sie über `AlertEvaluationConfig`. Der Umbau von S2
  liegt **oberhalb** der Engine — in der Ablaufsteuerung, nicht in der Auswertung.
- **Trip/Compare-Teilung (PO-Vorgabe):** ein Code, Parameter `context`. Eine
  Compare-eigene Zweitfassung zu einem existierenden Trip-Pendant ist per Default ein Verstoß.
- **Kanal-Erbe vom Briefing:** Trip erbt bei fehlendem `alert_channels` die Briefing-Kanäle aus
  `report_config` (`trip_alert.py:1180/1192`). Der Ortsvergleich hat das Pendant bereits —
  `send_telegram`/`send_sms` am Preset, ausgewertet in `compare_official_alert.py:250-258`.
- **Gedächtnis-Reset beim Briefing** (#816 B): Briefing = neue stabile Vergleichsreferenz ⇒
  Melde-Gedächtnis leeren. Bisher nur Trip.
- **Read-Modify-Write mit Merge** bei allen Persistenz-Berührungen (BUG-DATALOSS-GR221).

## Ist-Stand: die vier Unterschiede zwischen den beiden Pfaden (gemessen)

| | Trip (`trip_alert.py`) | Ortsvergleich (`compare_alert.py`) |
|---|---|---|
| **Kanäle** | `_effective_alert_channels()` `:1155` — Regel-Override, sonst `alert_channels`, sonst Briefing-Erbe, SMS-Tier-Gate `:1205` | **fest `{"email"}` `:246`** |
| **Ruhezeiten** | **doppelt**: explizit vor allem `:205`, zusätzlich in der Engine `deviation_alert_engine.py:243` | **nur** in der Engine, also nach Sperrzeit + Tages-Obergrenze |
| **Gedächtnis-Reset beim Briefing** | ja, `trip_report_scheduler.py:972` | **nein** — repo-weit gibt es genau einen `AlertStateService.reset()`-Aufruf, und der ist der Trip-Reset |
| **Gedächtnis-Kennung** | `trip.id` (eine Datei je Trip) | `f"{preset_id}:{location_id}"` (eine Datei je Preset × Ort) |

**Gleich sind bereits:** Sperrzeit über `ThrottleStore` (nur anderer Scope-String),
Tages-Obergrenze `alert_daily_limit` (beide importiert und geprüft),
Protokoll `alert_log.append_entry()` (identische Feldmenge seit S1),
Auswertungskern `DeviationAlertEngine`, Empfänger ausschließlich aus den Konto-Settings.

**Wortgleich dupliziert** über die drei Compare-Dateien: `_load_presets()`
(`compare_alert.py:327`, `compare_radar_alert.py:203`, `compare_official_alert.py:274`) —
byte-identisch verifiziert. Nahezu identisch: `_notification_service_for()`
(`:311`/`:183`/`:260`, Unterschied nur im Log-Präfix), Preset-Schleifenkopf, Orts-Auflösung,
Konstante `_DEFAULT_COOLDOWN_MINUTES = 120`, Kennungsschema `f"{preset_id}:{loc_id}"`.

## Dependencies

**Upstream** (was der geänderte Code benutzt): `DeviationAlertEngine`, `AlertStateService`,
`ThrottleStore`, `alert_daily_limit`, `alert_log`, `NotificationService`,
`AlertEvaluationConfig`, `CompareWeatherSnapshotService`, `TripSegmentWeatherAdapter`,
`load_all_trips` / `load_compare_presets`.

**Downstream** (was auf den Code zeigt): `api/routers/scheduler.py` (zwei Endpunkte),
`internal/scheduler/scheduler.go` (zwei Cron-Jobs), `src/services/scheduler_dispatch_service.py`
(Compare-Briefing, künftig Reset-Aufrufer), Alarm-Protokoll → Cockpit/Archiv-Statistik (Go).

## Existing Specs

| Spec | Bezug |
|---|---|
| `docs/specs/modules/rework_1467_s1_alarm_kennung.md` | Vorgänger-Scheibe, 12 ACs — Kennung + Typ |
| `docs/specs/modules/rework_1460_t1_relevanzfilter.md` | v1.2, 34 ACs — Relevanz-Filter, ADR-0043 |
| `docs/specs/modules/issue_1168_alert_engine_extract.md` | Engine-Extraktion (ADR-0021) |
| `docs/specs/modules/issue_1169_compare_alert_consumer.md` | Ortsvergleich als zweiter Engine-Konsument |
| `docs/specs/modules/feat_864_859_alert_presets.md` | Empfindlichkeitsstufen je Metrik — die einzige Alarm-Steuerung (#946) |
| `docs/specs/modules/feat_1459_alert_protokoll.md` | v1.5, 16 ACs — Protokoll-Felder |
| ADR-0021, ADR-0043 | Engine geteilt; Relevanz-Filter löst ADR-0040 ab |

## Risks & Considerations

1. **Der gefährlichste Fehler ist der ausbleibende Alarm.** Ein Umbau, der eine Meldung
   verschluckt, fällt niemandem auf. Zielmarke der Scheibe ist „Verhalten unverändert, außer
   den drei ausdrücklich gewollten Änderungen".
2. **Telegram und SMS gehen künftig echt raus.** Bisher war der Ortsvergleich stumm auf diesen
   Kanälen. Aus der Sicht des Nutzers ist das eine spürbare Verhaltensänderung —
   sie ist gewollt (PO-Zuschnitt), muss aber an das **bestehende Opt-in**
   (`send_telegram`/`send_sms` am Preset) gebunden sein, nicht an einen neuen Schalter.
   Sonst schaltet der Umbau bei allen Nutzern ungefragt Kanäle scharf.
   Das SMS-Tier-Gate (`sms_allowed()`) muss dabei greifen wie beim Trip.
3. **Der Gedächtnis-Reset trifft mehrere Dateien.** Compare hält eine Zustandsdatei je
   Preset × Ort. Ein Reset muss über alle Orte des Presets laufen — und darf, wie beim Trip
   seit #1460 P2, die `official_alert:`-Schlüssel **nicht** mitlöschen (sonst meldet eine
   fortbestehende amtliche Warnung nach jedem Briefing erneut).
4. **Der On-Demand-Fall.** Beim Trip ist der Reset ausdrücklich auf den geplanten Versand
   beschränkt (`if not on_demand`, #1007). Für den Ortsvergleich existiert ein manueller
   Einzelversand (`send_compare_preset()` `:417`) — dieselbe Unterscheidung ist zu treffen,
   sonst löscht jede Testmail das Gedächtnis.
5. **Ruhezeiten-Reihenfolge ändert sich für den Ortsvergleich** (künftig vor der Erkennung).
   Das spart Abrufe, kann aber die Zählung von Sperrzeit/Tages-Obergrenze verschieben —
   in der Spec festzuschreiben, welche Reihenfolge gilt.
6. **Kontingent open-meteo:** Der Ortsvergleich-Lauf holt frisches Wetter je Ort. Wird die
   Ruhezeit-Prüfung vorgezogen, sinkt der Abruf — erwünscht, aber ein Test darf nicht
   versehentlich Live-Abrufe auslösen.
7. **Nicht einebnen (Regressionsgefahr):** Datenbeschaffung bleibt getrennt; Bündelung aller
   getriggerten Orte in EINE Nachricht (#1170) bleibt; Empfänger bleiben Konto-Settings
   (#1452, `preset.empfaenger` ist inert); Ortszeit-Bezug (#1383) bleibt;
   Compare-Mail-Template bleibt compare-eigen.
8. **Abgrenzung zu S3/S4:** Nowcast (`compare_radar_alert.py`) und amtlich
   (`compare_official_alert.py`) werden in dieser Scheibe **nicht** eingezogen. Wird beim
   Hochziehen geteilter Bausteine deren Verhalten mitverändert, ist das ein Verstoß gegen den
   Zuschnitt — besonders: **amtliche Eskalation bleibt ohne Zeit-Cooldown**.
9. **Mandantentrennung:** mit zwei verschiedenen Nutzern verifizieren, `user_id` nie auf
   `"default"` zurückfallen lassen.
10. **Zeilenbudget:** Das Issue schätzt für alle vier Scheiben zusammen 650–950 Zeilen Python.
    S2 ist der größte Einzelanteil; das 250er-Budget wird voraussichtlich nicht reichen und
    braucht eine ausdrückliche Freigabe.

## Analysis

### Type
Rework (Feature-Track, kein Bug)

### Drei Korrekturen an den Annahmen oben (gemessen in der Analyse-Phase)

1. **Der Compare-Kanal-Resolver existiert nicht einmal, sondern zweimal.** Neben
   `compare_official_alert.py:250-258` gibt es `scheduler_dispatch_service.py:275-291`
   (`_effective_compare_channels()`) — funktional identisch, der Docstring dort nennt die
   andere Kopie ausdrücklich. Würde `compare_alert.py` einfach „den vorhandenen" benutzen,
   entstünde die dritte Kopie. **Die Extraktion ist damit nicht Kür, sondern der Anlass.**
2. **Risiko 5 oben (Ruhezeit-Vorziehen verschiebt Zähler) trifft nicht zu.** In
   `compare_alert.py:112/118` werden Sperrzeit und Tages-Obergrenze nur *gelesen*; geschrieben
   wird erst nach erfolgreichem Versand (`:158-159`). Während der Ruhezeit liefert die Engine
   `triggered=False` und der Lauf endet in `continue` (`:127`) — es wird schon heute nichts
   gezählt. Einziger messbarer Effekt des Vorziehens: **weniger Wetterabrufe**.
3. **Risiko 4 oben (On-Demand) ist anders gelagert.** Beim Trip stehen Anker-Schreiben und
   Reset gemeinsam unter `if not on_demand` (`trip_report_scheduler.py:959-972`). Beim
   Ortsvergleich schreibt `_write_compare_alert_snapshots()` (`scheduler_dispatch_service.py:447`)
   den Δ-Anker **bedingungslos**, auch beim Handversand. Die Trip-Regel lautet also nicht
   „nicht bei Handversand", sondern **„Gedächtnis leeren, wenn der Anker neu gesetzt wird"**.
   Ein wörtlich kopiertes `if not on_demand` erzeugt beim Ortsvergleich *neuer Anker + altes
   Gedächtnis* — genau die Kombination, die einen echten Alarm verschluckt
   (`deviation_alert_engine.py:191-205` filtert gegen absolute `last_reported_value`).

### Zwei Befunde, die in der Ist-Tabelle fehlten

4. **Die Bedienung für die neuen Kanäle existiert bereits — und ist heute wirkungslos.**
   Im Alarme-Tab des Ortsvergleichs steht der `AlertChannelPicker` („Alert-Kanäle", Zeilen
   „Telegram"/„SMS"/„Email", `AlarmeTab.svelte:295`, geteilt mit dem Trip). Er schreibt auf
   `send_telegram`/`send_sms` (`AlarmeTab.svelte:186-187`), ausdrücklich kommentiert
   `:168-170` „vergleich: bindet an bestehende `send_telegram`/`send_sms`". **Der Nutzer kann
   heute Telegram für Alarme einschalten und bekommt trotzdem nur E-Mail.** Dieselben zwei
   Felder bedient zusätzlich der Versand-Tab als Briefing-Kanäle
   (`VersandTab.svelte:234-247`) — beim Ortsvergleich gibt es also, anders als beim Trip
   (`trip.alert_channels` vs. `report_config.send_*`), **keine Trennung** zwischen
   Briefing- und Alarm-Kanälen.
5. **Pausierte und archivierte Ortsvergleiche senden heute weiterhin Änderungsalarme.**
   `compare_alert.py` hat weder einen `schedule=="manual"`- noch einen `archived_at`-Riegel;
   `compare_official_alert.py:84-89` hat beide. Ein gemeinsamer Ablauf, der die amtlichen
   Riegel mitzieht, würde Alarme **verstummen lassen** — Verhaltensänderung in die
   gefährliche Richtung.

### Technischer Ansatz — Empfehlung

Abgewogen wurden (A) ein neuer gemeinsamer Ablauf-Service für Trip + Ortsvergleich und
(B) den Ortsvergleich an den bestehenden Trip-Ablauf heranziehen.

**Empfehlung: B, erweitert um genau einen echten Sammelbaustein.** Begründung:

- Der Auswertungs**kern** ist über `DeviationAlertEngine` (ADR-0021) bereits geteilt. Was
  zwischen Trip und Ortsvergleich übrig bleibt, ist echter Kontext-Unterschied: 1 Einheit mit
  n Etappen und einer Zustandsdatei gegen n Einheiten mit n Zustandsdateien, ein Versand gegen
  gebündelten Versand, vier historische Aktivitäts-Riegel (`trip_alert.py:179-202`, Sedimente
  aus #222/#846/#946/#1460) gegen keinen. Variante A wäre eine Hülle über zwei Strategien.
- **Die wirklich wortgleiche Doppelung liegt nicht zwischen Trip und Compare, sondern zwischen
  den drei Compare-Dateien** (`_load_presets()` byte-identisch in allen dreien,
  `_notification_service_for()` bis auf den Log-Präfix, Kanal-Resolver, Schleifenkopf).
- Variante A bräuchte 900–1200 Zeilen und würde den Trip-Hauptpfad anfassen, ohne dass ein
  Nutzer etwas davon hätte — hohes Risiko für den ausbleibenden Alarm gegen null Gewinn.
- B bereitet S3/S4 besser vor: danach teilen sich alle drei Compare-Dienste Loader, Resolver
  und Ruhezeit-Riegel, und S3/S4 können ihre Preset-Schleifen zu **einem** Compare-Läufer
  zusammenziehen, der sauber gegen den Trip-Läufer steht.
- Zugeständnis an das Ziel „eine Ablaufsteuerung", billig und beweisbar verlustfrei: die
  **Torfolge** Ruhezeit → Sperrzeit → Tages-Obergrenze ist nach dieser Scheibe in beiden
  Pfaden identisch und lässt sich als ~20-zeilige reine Funktion herausziehen, die
  `trip_alert.py:205-217` und `compare_alert.py:108-120` gemeinsam aufrufen.

### Affected Files

| Datei | Art | Beschreibung |
|---|---|---|
| `src/services/compare_alert_channels.py` | CREATE | Der EINE Compare-Kanal-Resolver (~30 Z.) |
| `src/services/compare_alert.py` | MODIFY | Ruhezeit-Riegel vorziehen; `channels={"email"}` `:246` durch Resolver ersetzen |
| `src/services/scheduler_dispatch_service.py` | MODIFY | Delegation statt eigener Resolver-Kopie; `_reset_compare_alert_state()` neben `_write_compare_alert_snapshots()` `:447` |
| `src/services/compare_official_alert.py` | MODIFY | Nur Delegation, keine Verhaltensänderung (S4-Datei — bestehende Tests müssen unverändert grün bleiben) |
| `src/output/renderers/alert/render.py` | MODIFY (bedingt) | Nur falls Ortszuordnung in Telegram/SMS beschlossen wird |
| `tests/tdd/test_issue_1169_compare_alert_consumer.py` | MODIFY | Enthält den einzigen Test, der `{"email"}` festschreibt (`:645`) |

### Scope Assessment

- Dateien: 4 sicher + 1 bedingt + Tests
- Quellcode: ~65 Zeilen netto ohne Optionen, ~110 mit Renderer-Korrektur und Tor-Baustein
- Tests: ~300 bis ~460 Zeilen
- **Risiko: MEDIUM** (Trip-Hauptpfad bleibt unberührt; die Datenwirkung liegt allein im Reset)
- **250-Zeilen-Budget:** reicht für die Scheibe als Ganzes nicht (~370–570 inkl. Tests),
  wohl aber für jeden einzelnen Arbeitsgang des Schnitts unten

### Reihenfolge (nach jedem Schritt lauffähig)

| AG | Inhalt | Nutzerwirkung |
|---|---|---|
| **AG1** | Kanal-Resolver zusammenlegen, drei Aufrufer delegieren. Δ-Pfad bleibt vorerst `{"email"}` | keine — alle Bestandstests müssen unverändert grün sein, das ist der Beweis der Verlustfreiheit |
| **AG2** | Ruhezeiten vor die Erkennung ziehen | keine sichtbare; spart Wetterabrufe |
| **AG3** | Telegram/SMS scharf schalten (die eine Zeile `:246`) | **ab hier merkt der Nutzer etwas** |
| **AG4** | Gedächtnis-Reset beim Briefing des Ortsvergleichs | tiefste Datenwirkung, deshalb zuletzt und in eigener Datei |
| AG5 (optional) | Gemeinsamer Tor-Baustein Ruhezeit/Sperrzeit/Obergrenze für Trip + Compare | keine — reiner Umbau |

### Risiken (mit Testauftrag)

| | Risiko | Test, der es fängt |
|---|---|---|
| **R1** | Telegram/SMS tragen **keine Ortszuordnung**: `render.py:585-588` (`_sms_token`) und `:549-580` (`render_telegram`) kennen kein `location_label` je Ereignis; in der SMS steht die Ortsliste sogar doppelt im Kopf (`:612-614`). Bei drei Orten bekommt der Nutzer Werte ohne Zuordnung | Bündel-Alarm 2 Orte × 2 Metriken → jeder Ortsname höchstens einmal in der SMS; Telegram nennt zu jeder Metrikzeile den Ort |
| **R2** | Reset entkoppelt Gedächtnis und Anker (s. Korrektur 3) | Handversand, danach ein Wert weit über der Schwelle → Alarm MUSS rausgehen. Gegenprobe: nach geplantem Briefing meldet ein unveränderter Wert nicht erneut |
| **R3** | Reset muss über **alle** Orte des Presets laufen und `official_alert:`-Schlüssel schonen; ein still übersprungener Ort meldet danach nie wieder | Preset mit 3 Orten, in einem zusätzlich ein `official_alert:`-Schlüssel → alle 3 Änderungs-Schlüssel weg, der amtliche bleibt; gleichnamiges Preset eines **zweiten** Nutzers unberührt |
| **R4** | Resolver liest aus `preset.raw` (`loader.py:340-348`). Zugriff auf das Dataclass-Feld statt aufs Rohdict ⇒ stumm bei E-Mail-only, unsichtbare Nicht-Änderung. Fehlendes Feld darf nie als „an" gelten | `send_telegram: true` → genau eine Telegram-Nachricht; Preset **ohne** den Schlüssel → `{"email"}`; `send_sms: true` bei Free-Tier → kein SMS |
| **R5** | Ruhezeit mit nur einem gesetzten Feld darf nicht dauerhaft unterdrücken | ein Feld gesetzt → Alarm geht raus; 22:00–07:00 um 23:00 → kein Alarm **und** Wetter-Quelle null Mal aufgerufen |

**Nebenbefund (S3-relevant, nicht hier beheben):** `compare_radar_alert.py:180` schreibt
`radar_onset` in dieselbe Zustandsdatei. Der Schlüssel wird repo-weit nirgends gelesen, heute
also folgenlos — S3 muss aber wissen, dass der Reset ihn löscht.

### Testnetz (Ist-Stand)

- **Der einzige Test, der `{"email"}` festschreibt:** `test_issue_1169_compare_alert_consumer.py:645`
  (`telegram_sink.send_count() == 0`). Absicht zusätzlich im Modul-Docstring `:14-15` und im
  Test-Docstring `:591-594` verankert — alle drei mitziehen. ⚠️ Die Datei trägt
  `pytestmark = pytest.mark.email` (`:70`), nutzt echtes IMAP und einen lokalen Telegram-Server.
- Briefing-Reset des Trips ist gut abgedeckt: `test_alert_state_briefing_reset.py` (7 Tests),
  darunter `:151` „amtliche Einträge überleben den Reset" und `:466` Kopplung des
  Schlüsselpräfix an den Reset-Filter.
- Trip-Kanal-Resolver: `test_trip_alert_channel_precedence.py` (4 Tests) +
  `test_issue_1069_tier_channel_gating.py:369` (SMS-Tier-Gate).
- 7 Testdateien steuern `CompareAlertService` direkt an, 22 erwähnen ihn.
- Zwei Struktur-Wächter mit Pfad-Literalen ziehen mit: `tests/test_success_status_guard.py:1523-1530`
  und `:1782-1786` verankern `compare_alert.py::check_all_compare_presets` samt erwarteter
  `try/except`-Zahl.
- `pyproject.toml:56` schließt `email`/`live`/`staging` per Default aus — ein nacktes `pytest`
  löst keine echten Versände aus.

### PO-Entscheidungen (2026-08-03) — alle vier beantwortet

**E2 — Ortszuordnung in den Kurznachrichten: ✅ entschieden, weiter als vorgeschlagen.**
> „SMS brauchen eine numerische Kodierung des Ortsnamens. Ansonsten geht hier zu viel Platz für
> die einzelnen Namen verloren. Der Vorschlag für Telegramm ist eine Sprechblase pro Ort."

- **SMS:** Orte werden **als Zahl** geführt, nicht ausgeschrieben. Ableitung (Spec-Vorschlag,
  Freigabe am AC-Gate): 1-basierte Position in der konfigurierten Ortsliste des Vergleichs —
  identisch zur Spaltenreihenfolge der Vergleichs-E-Mail, damit die Zahl lernbar und über
  Meldungen hinweg stabil ist. Der doppelte Ortslisten-Kopf (`render.py:612-614`) entfällt.
- **Telegram:** **eine Nachricht je Ort** („Sprechblase pro Ort") statt einer gebündelten.
  ⚠️ Das weicht bewusst von der Bündelungs-Entscheidung #1170 ab — dort galt „alle
  getriggerten Orte in EINE Nachricht". Die Abweichung ist **kanalspezifisch**: E-Mail bleibt
  gebündelt (eine Mail mit Vergleichsmatrix), Telegram wird je Ort aufgeteilt, SMS bleibt
  gebündelt mit Zahlenkodierung. Gehört als ausdrückliches AC in die Spec, nicht als
  Nebeneffekt.

**E3 — Handversand: ✅ entschieden, aber anders als beide angebotenen Optionen.**
> „Beide Dienste sollen sich natürlich gleich verhalten. Verwende zwingend den gleichen Code."

Konsequenz, gemessen: Der Trip hält Anker-Schreiben **und** Gedächtnis-Reset gemeinsam unter
`if not on_demand` (`trip_report_scheduler.py:959-972`). Der Ortsvergleich schreibt seinen
Δ-Anker **bedingungslos** (`scheduler_dispatch_service.py:410`, auch bei
`send_compare_preset()` `:443`). „Gleicher Code" heißt also: **ein geteilter Baustein, der
Anker und Gedächtnis zusammen behandelt, mit derselben Bedingung für beide Dienste** — beim
Handversand wird künftig auch beim Ortsvergleich **weder** der Anker neu gesetzt **noch** das
Gedächtnis geleert. Das ist eine zusätzliche Verhaltensänderung am Compare-Ankerschreiber
gegenüber dem ursprünglichen Zuschnitt und muss als eigenes AC stehen.

**E4 — Pausierte/archivierte Ortsvergleiche: ✅ angleichen, weiter als vorgeschlagen.**
> „Pausierte und archivierte Ortsvergleiche dürfen grundsätzlich nichts senden. Sie sind ja
> pausiert beziehungsweise archiviert. Sie sollen sich so verhalten, als würde es sie im
> System nicht geben."

Gemessen: Der Riegel (`schedule == "manual"` bzw. `archived_at` gesetzt) existiert **nur** in
`compare_official_alert.py:84-89` (aus #1233). Weder `compare_alert.py` noch
`compare_radar_alert.py` haben ihn. „Grundsätzlich" ⇒ der Riegel wird als geteilter Baustein
gebaut und in **allen drei** Compare-Alarmpfaden angewendet — auch im Nowcast-Pfad, der
formal zu S3 gehört. Begründung für das Überschreiten der Scheiben-Grenze: die PO-Vorgabe
ist ausdrücklich grundsätzlich, die Änderung je Datei ist eine Delegationszeile, und ein
Riegel nur im halben Bestand wäre genau der Zustand, den diese Scheibe beseitigen soll.
Richtung: **weniger** Meldungen — ausdrücklich gewollt, deshalb mit eigenem AC belegt.

**E5 — Zuschnitt: ✅ vier kleine Schritte nacheinander, keine Budget-Ausnahme.**

### Angepasste Reihenfolge (nach den PO-Entscheidungen)

| AG | Inhalt | Nutzerwirkung |
|---|---|---|
| **AG1** | Kanal-Ermittlung zusammenlegen; drei Aufrufer delegieren | keine — Bestandstests unverändert grün = Beweis der Verlustfreiheit |
| **AG2** | Ruhezeiten vor die Erkennung ziehen | keine sichtbare; spart Wetterabrufe |
| **AG3** | Kurznachrichten-Darstellung: SMS-Zahlenkodierung, Telegram je Ort eine Nachricht | noch keine — Renderer-Vorarbeit, bevor der Kanal scharf ist |
| **AG4** | Telegram/SMS für Änderungsalarme scharf schalten | **ab hier merkt der Nutzer etwas** |
| **AG5** | Anker + Gedächtnis als EIN geteilter Baustein für Trip und Ortsvergleich | tiefste Datenwirkung |
| **AG6** | Riegel „pausiert/archiviert schweigt" für alle drei Compare-Alarmpfade | weniger Meldungen aus stillgelegten Vergleichen |

Reihenfolge-Begründung: AG3 **vor** AG4, damit die allererste echte Telegram-/SMS-Meldung
bereits lesbar ist. AG5 und AG6 zuletzt, weil sie Daten bzw. Meldungsmenge berühren und
einzeln zurücknehmbar bleiben müssen.

---

## Nachtrag AG5 — Ist-Stand am 2026-08-04 nachgemessen

Vor dem Start von AG5 gegen `main` (`f938159b`) neu gemessen, weil die Zeilenangaben oben
vom 2026-08-03 stammen und AG3b/AG4 seither vier Commits hinzugefügt haben.

**Struktur unverändert, Zeilennummern verschoben:**

| Zusicherung | Stand 03.08. | gemessen 04.08. |
|---|---|---|
| Einziger `AlertStateService.reset()`-Aufruf im Produktivcode ist der des Trips | ja | **bestätigt** — `trip_report_scheduler.py:1040`, repo-weit sonst nur `warn_egress.py:96` (anderes Objekt, `_fetch_failure_sink`) |
| Trip koppelt Anker + Reset unter `if not on_demand` | `:959-972` | **unverändert** `:959` / `:972` |
| Ortsvergleich schreibt den Anker bedingungslos | `:410` / `:443` / `:447-468` | verschoben auf `:406` / `:413` / `:443` |
| `send_one_compare_preset` kennt kein `on_demand` | ja | **bestätigt** — kein Treffer im Modul |

⇒ Die Analyse aus dem Hauptteil gilt unverändert; AG3b/AG4 haben den AG5-Bereich nicht
berührt. Der einzige Unterschied sind die Zeilennummern — die Implementierung muss sich an
den **Funktionsnamen** orientieren, nicht an den Zeilenangaben der Spec.

**Zusätzlicher Befund: die Abnahmekriterien AC-14..AC-19 decken den Trip-Pfad nicht ab.**
AG5 baut `trip_report_scheduler.py` um (Delegation an den neuen Baustein), aber alle sechs
Kriterien prüfen ausschließlich den Ortsvergleich. Damit fehlt genau die Invariante, die
AG3b als AC-26 gebraucht hat („die anderen Pfade bleiben byte-identisch"). Ergänzt als
**AC-27**, PO-Freigabe 2026-08-04.
