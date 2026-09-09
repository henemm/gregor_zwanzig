---
entity_id: rework_2279_s1_alert_kanal_aufloesung
type: refactor
created: 2026-09-09
updated: 2026-09-09
status: active
version: "1.0"
tags: [alerts, trips, compare, channels]
---

# Eine Alarm-Kanal-Auflösung für Trip und Ortsvergleich (Issue #2279, Scheibe S1, Epic #1374)

## Approval

- [x] Approved (PO „go" 2026-09-09, Tech-Lead-Mandat)

## Purpose

Trip und Ortsvergleich lösen ihre Alarm-Kanäle heute in zwei unabhängigen
Funktionen mit unterschiedlicher Semantik auf (`TripAlertService._effective_alert_channels`
vs. `compare_alert_channels.effective_compare_channels`): unterschiedliche
E-Mail-Regel (Trip: an/aus konfigurierbar; Vergleich: hart an), doppelte
Sendezeit-Readiness-Prüfung nur beim Vergleich, kein gemeinsames Tier-Gate.
Diese Scheibe zieht **eine** Auflösung `effective_alert_channels(subscription,
settings, user_id)` über beide `kind`-Werte (ADR-0023), macht die Trip-Regel
(Override ersetzt vollständig, Regel-Union, Tier-Gates einmal) zur
gemeinsamen Semantik und trennt die verbleibende Compare-Briefing-Auflösung
sauber ab. Sie schließt damit auch die Alarmseite von #2212 (E-Mail beim
Vergleich abschaltbar).

## Source

- **File:** `src/services/alert_channels.py` (neu), `src/services/trip_alert.py:2871-2926`,
  `src/services/compare_alert_channels.py`
- **Identifier:** `effective_alert_channels`, `resolve_alert_channels`,
  `TripAlertService._effective_alert_channels`, `effective_compare_briefing_channels`

Betroffene Schicht: ausschließlich **Python-Core** (`src/services/`). Kein
Go-Code, kein Frontend-Code in dieser Scheibe (siehe Known Limitations).

## Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `src/services/alert_channels.py` | CREATE | Dispatcher `effective_alert_channels` + Adapter `_trip_channel_inputs`/`_compare_channel_inputs` + reiner Kern `resolve_alert_channels` |
| `src/services/trip_alert.py:2871-2926` | MODIFY | `_effective_alert_channels` wird dünner Delegat auf `effective_alert_channels` |
| `src/services/compare_alert.py:111,603` | MODIFY | Aufruf auf `effective_alert_channels(preset, ...)` umgestellt |
| `src/services/compare_official_alert.py:465-471` | MODIFY | `_effective_channels`-Wrapper delegiert an `effective_alert_channels` |
| `src/services/compare_radar_alert.py:169` | MODIFY | Aufruf auf `effective_alert_channels(preset, ...)` umgestellt |
| `src/services/compare_alert_channels.py` | MODIFY | `effective_compare_channels` → `effective_compare_briefing_channels` (Readiness bleibt, Zuständigkeit nur Briefing), alter Name entfernt |
| `src/services/scheduler_dispatch_service.py:29,351-363,588` | MODIFY | Import/Aufruf auf `effective_compare_briefing_channels` umbenannt |
| `tests/tdd/test_compare_alert_channels.py:175-233` | MODIFY | Verdrahtungsnachweise auf die neuen Symbole umgestellt |
| `tests/tdd/test_alert_channel_resolution_parity.py` | CREATE | Parität, Bestand-Identität, Tier-Gates, Settings-Inertheit (AC-1, AC-3, AC-4, AC-5) |
| `tests/tdd/test_compare_alert_email_off.py` | CREATE | Ende-zu-Ende E-Mail-aus über echte Compare-Alarmservices mit Sinks (AC-2) |

## Estimated Scope

- **LoC:** src ≈ +150/−45, tests ≈ +280
- **Files:** 8 (2 neu)
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `services.user_tier.sms_allowed`/`premium_sms_allowed` | module | Tier-Gates, jetzt genau einmal im gemeinsamen Kern |
| `app.trip.Trip`/`AlertRule` | module | Trip-Adapter liest `alert_channels`, `report_config`, `alert_rules` |
| Compare-Preset-Roh-Dict (`preset.raw` via `compare_preset_access`) | module | Compare-Adapter liest `alert_channels`, `send_telegram`/`send_sms`/`send_premium_sms` per `.get(...)` |
| `app.config.Settings` | module | bleibt Teil der Signatur, ist in der Auflösung aber inert (Readiness liegt in `notification_service`) |
| `services.notification_service._dispatch_alert_message`, Radar-/amtlicher Sendepfad | module | unverändert zuständig für Sendezeit-Readiness (`:1663-1774`, `:1214-1232`, `:1320-1345`) |
| `src/services/scheduler_dispatch_service.py` | module | bleibt auf dem Briefing-Resolver (`effective_compare_briefing_channels`), NICHT auf der Alarm-Auflösung |

## Implementation Details

### Kern-Algorithmus (reine Funktion, primitive Eingaben)

`resolve_alert_channels(override: dict | None, inherited: set[str],
rule_channel_sets: list[set[str]], user_id: str) -> set[str]` — Muster
`app/day_window.py:26` (Adapter am Rand, Kern ohne Domänenobjekte):

1. `override` gesetzt ⇒ `inherited` wird durch die im Override truthy
   gesetzten Kanäle **vollständig ersetzt** (auch wenn das Ergebnis leer
   ist — kein `{"email"}`-Default bei explizitem Override).
2. Keine aktiven Regeln in `rule_channel_sets` ⇒ Ergebnis ist der (ggf.
   ersetzte) `inherited`-Anteil.
3. Aktive Regeln vorhanden ⇒ Union je Regel: nicht-leeres `rule.channels`
   gewinnt für diese Regel, sonst fällt die Regel auf `inherited` zurück.
4. Tier-Gates genau einmal am Ende: `sms` raus, wenn nicht
   `sms_allowed(user_id)`; `premium_sms` raus, wenn nicht
   `premium_sms_allowed(user_id)`.

Dies ist wortgleich der heutige Trip-Algorithmus (`trip_alert.py:2898-2926`),
unverändert in den Kern gehoben.

### Dispatcher und Adapter

`effective_alert_channels(subscription, settings, user_id) -> set[str]`
unterscheidet über den Typ von `subscription`:

- `app.trip.Trip` (kind `route`) → `_trip_channel_inputs(trip)` liefert
  `override = trip.alert_channels`, `inherited = _briefing_channels(trip.report_config)`
  mit Legacy-Regel `{"email"}` nur wenn `trip.report_config is None`
  (sonst der tatsächliche `_briefing_channels`-Wert, auch wenn leer),
  `rule_channel_sets = [r.channels for r in trip.alert_rules if r.enabled]`
  in der vom Kern erwarteten Form (aktive Regeln, leere/nicht-leere Sets).
- Compare-Preset-Roh-Dict (kind `vergleich`) → `_compare_channel_inputs(preset)`
  liefert `override = preset.get("alert_channels")` (nur wenn es ein `dict`
  ist, sonst `None`), `inherited = {"email"} ∪ {ch für ch in
  ("telegram","sms","premium_sms") wenn preset.get(f"send_{ch}")}` — E-Mail
  ist beim Vergleich immer im geerbten Anteil, weil der Vergleich noch kein
  eigenständiges `send_email` kennt (KL-6, `versand_tab_vergleich.md`),
  `rule_channel_sets = []` (der Vergleich kennt keine Alarm-Regeln).

Beide Adapter reichen ihre Eingaben unverändert an `resolve_alert_channels`
durch; `settings` und `user_id` wandern nur für das Tier-Gate durch bzw.
bleiben bei `settings` vollständig ungenutzt in der Auflösung selbst.

### `settings` bleibt in der Signatur, ist aber inert

Kein `can_send_*()`-Aufruf in `resolve_alert_channels` oder den Adaptern.
Die Sendezeit-Readiness-Prüfung bleibt vollständig in
`notification_service.py` (`_dispatch_alert_message:1663-1774`,
Radar-Pfad `:1214-1232`, amtlicher Pfad `:1320-1345`) — die Auflösung
entscheidet nur, WELCHE Kanäle fachlich aktiv sind, nicht ob im Moment
zustellbar. Ein Tripwire-Test (Teil von
`test_alert_channel_resolution_parity.py`) belegt: identische
Kanal-Konfiguration liefert mit sendebereiten und mit leeren `Settings`
dasselbe Ergebnis.

### Verdrahtung der Aufrufer

- `TripAlertService._effective_alert_channels(trip)` wird dünner Delegat:
  `return effective_alert_channels(trip, self._settings, self._user_id)`.
  Alle sechs bestehenden Aufrufer (`trip_alert.py:398,550,1070,1669,2504,2721`)
  bleiben unverändert.
- `CompareAlertService` (`compare_alert.py:111,603`),
  `CompareRadarAlertService` (`compare_radar_alert.py:169`) rufen direkt
  `effective_alert_channels(preset, self._settings, self._user_id)`.
- `CompareOfficialAlertService._effective_channels` (`compare_official_alert.py:465-471`)
  bleibt als dünner Wrapper bestehen und delegiert intern an
  `effective_alert_channels` — Verdrahtungsnachweis per `monkeypatch` im
  Verbraucher-Modul (AC-6).

### Umbenennung des Briefing-Resolvers

`src/services/compare_alert_channels.py::effective_compare_channels` wird zu
`effective_compare_briefing_channels`. Die Readiness-Prüfung
(`settings.can_send_telegram()`/`can_send_sms()` + Tier-Gates) bleibt darin
unverändert bestehen — diese Funktion ist ab jetzt ausschließlich für den
Compare-**Briefing**-Versand zuständig (`scheduler_dispatch_service.py:29,351-363,588`).
Der alte Name `effective_compare_channels` verschwindet vollständig aus dem
Repository (`git grep effective_compare_channels` liefert nach Abschluss 0
Treffer). `effective_compare_telegram_style` bleibt unverändert in
derselben Datei — reine Darstellungspräferenz, keine Kanal-Auflösung.

## Expected Behavior

- **Input:** ein `app.trip.Trip` (kind `route`) oder ein Compare-Preset-Roh-Dict
  (kind `vergleich`), ein `Settings`-Objekt (inert), eine `user_id`.
- **Output:** ein `set[str]` aus `{"email","telegram","sms","premium_sms"}` —
  für beide `kind`-Werte nach identischer Semantik (Override/Erbe/Regel-Union/
  Tier-Gates), unabhängig von der aktuellen Sendebereitschaft.
- **Side effects:** keine. `resolve_alert_channels` und die Adapter sind rein
  (keine I/O, kein Zustand). Die Nebenwirkung „Protokolleintrag im
  Unterdrückungs-Log listet beim Vergleich künftig auch nicht-sendebereite
  Opt-in-Kanäle" ist eine sichtbare Folge der entfernten Doppel-Readiness
  (wie beim Trip seit je), keine neue Nebenwirkung dieser Funktion selbst.

## Acceptance Criteria

- **AC-1 (Parität):** Given ein Trip und ein Ortsvergleich mit identischer
  Alarm-Kanal-Konfiguration (`alert_channels` mit jeder der 16 Kombinationen
  aus email/telegram/sms/premium_sms, Nutzer mit Premium-Tier) / When
  `effective_alert_channels` für beide läuft / Then liefert sie für beide
  kinds dieselbe Kanalmenge.
  - Test: parametrisierter Test über 16 Kombinationen × 2 kinds, Assertion
    auf identische resultierende Kanalmenge je Kombination.

- **AC-2 (E-Mail aus):** Given ein Ortsvergleich mit
  `alert_channels.email=false` (Telegram an) / When ein Abweichungs-, Radar-
  oder amtlicher Alarm feuert / Then geht keine E-Mail raus (Mail-Sink bleibt
  leer), Telegram wird zugestellt.
  - Test: je ein Test pro Alarmart über den echten Compare-Alarmservice mit
    Mail-/Telegram-Sinks — Mail-Sink nach dem Lauf leer, Telegram-Sink enthält
    eine Zustellung.

- **AC-3 (Bestand identisch):** Given ein Bestands-Preset OHNE
  `alert_channels` (nur flache `send_telegram/send_sms/send_premium_sms`,
  alle 8 Kombinationen) / When die Auflösung läuft / Then ist das Ergebnis
  identisch zum heutigen Verhalten: E-Mail an plus die eingeschalteten
  Opt-in-Kanäle nach Tier-Gate — ohne Datenänderung am Preset.
  - Test: parametrisierter Test über 8 Kombinationen, Vergleich gegen die
    heutige `effective_compare_channels`-Erwartung (E-Mail immer,
    Opt-in-Kanäle nach Tier-Gate), Preset-Dict bleibt nach dem Lauf
    bytegleich.

- **AC-4 (Tier-Gates einmal):** Given ein Nutzer ohne SMS-/Premium-SMS-Tier
  / When Trip und Ortsvergleich mit eingeschaltetem sms und premium_sms
  aufgelöst werden / Then fehlen beide Kanäle in beiden kinds; das Gate
  existiert nur im gemeinsamen Kern.
  - Test: ein Fall je kind mit Nicht-Premium-Nutzer, beide Kanäle fehlen im
    Ergebnis.
  - Mutations-Gegenprobe (PFLICHT): Tier-Gate im Kern (`resolve_alert_channels`)
    entfernen ⇒ derselbe Test wird für BEIDE kinds rot.

- **AC-5 (Settings inert):** Given identische Kanal-Konfiguration / When die
  Auflösung einmal mit vollständig sendebereiten und einmal mit leeren
  `Settings` läuft / Then ist die Kanalmenge identisch — Sendebereitschaft
  entscheidet ausschließlich die Zustellung.
  - Test: Tripwire — zwei Läufe mit unterschiedlich konfigurierten
    `Settings`-Instanzen (alle `can_send_*` True vs. alle False/leer),
    Ergebnis-Set identisch.

- **AC-6 (Verdrahtung):** Given der Umbau ist fertig / When die drei
  Compare-Alarmservices und der Trip-Service auflösen / Then delegieren sie
  nachweisbar an `effective_alert_channels`, der Compare-Briefing-Versand an
  `effective_compare_briefing_channels`, und `git grep effective_compare_channels`
  liefert 0 Treffer.
  - Test: `monkeypatch` von `effective_alert_channels` im jeweiligen
    Verbraucher-Modul-Namespace (`trip_alert`, `compare_alert`,
    `compare_official_alert`, `compare_radar_alert`) ändert das beobachtete
    Ergebnis je Aufrufer; separat ein Shell-/Repo-Grep-Check auf
    `effective_compare_channels` mit 0 Treffern.

- **AC-7 (Trip unverändert):** Given die bestehenden Trip-Tests
  (`test_trip_alert_channel_precedence.py`, `test_issue_684_alert_email_guard.py`,
  `test_914_slice4_alert_sms_dispatch.py`, `test_issue_1069_tier_channel_gating.py`,
  `test_issue_638_alerts_redesign.py`) / When sie gegen den Delegaten laufen
  / Then bleiben sie ohne Änderung grün (Regel-Override, Legacy-Erbe,
  `report_config=None` ⇒ `{"email"}`).
  - Test: bestehende Suiten unverändert ausführen, keine Regression.

## Mutations-Gegenprobe

Pflicht-Gegenproben, die je einen konkreten AC brechen müssen:

- **(a)** E-Mail im Kern hart auf `True` setzen (statt aus `inherited`
  gelesen) ⇒ AC-2 wird rot (Mail geht trotz `email=false` raus).
- **(b)** Tier-Gate im Kern entfernen ⇒ AC-4 wird rot in **beiden** kinds
  (SMS/Premium-SMS trotz fehlendem Tier zugestellt).
- **(c)** Compare-Adapter liest `preset.get("send_email")` statt der
  E-Mail-immer-Regel ⇒ AC-3 wird rot (Bestands-Presets ohne `send_email`-Key
  verlieren fälschlich die E-Mail).
- **(d)** Eine Readiness-Prüfung (`settings.can_send_*()`) in den Kern
  schmuggeln ⇒ AC-5 wird rot (Ergebnis hängt plötzlich von `Settings` ab).
- **(e)** `compare_official_alert.py` ruft `effective_compare_briefing_channels`
  statt `effective_alert_channels` für Alarme ⇒ AC-6 wird rot (Delegation
  nicht mehr nachweisbar, Readiness-Doppelprüfung kehrt zurück).

## Test-Plan

| AC | Datei | Schicht |
|---|---|---|
| AC-1, AC-3, AC-4, AC-5 | `tests/tdd/test_alert_channel_resolution_parity.py` | Kern |
| AC-2 | `tests/tdd/test_compare_alert_email_off.py` | Kern |
| AC-6 | `tests/tdd/test_compare_alert_channels.py` (angepasst) | Kern |
| AC-7 | bestehende Trip-Suiten unverändert | Kern |

Kern-Schicht, offline, keine Marker. Tests lösen den Prüfling relativ zur
eigenen Testdatei auf (kein fester Hauptrepo-Pfad); Nutzerverzeichnisse über
`app.loader.get_data_dir()`.

## Known Limitations

- **Kein Datenumbau, kein Go-Feld, kein Frontend in dieser Scheibe.** Eine
  Migration der flachen Compare-Felder nach `alert_channels` würde die
  Alarm-Kanäle einfrieren, solange der Compare-Alarme-Tab weiterhin die
  flachen `send_*`-Felder schreibt (Override gewinnt und macht spätere
  Toggle-Änderungen wirkungslos); ein Go-Roundtrip ohne Struct-Feld würde
  einen per API gesetzten `alert_channels`-Key zusätzlich verwerfen
  (BUG-DATALOSS-GR221-Muster). Beides gehört in Scheibe S2 (Folge-Issue):
  Go-Feld `ComparePreset.AlertChannels` + Feld-Level-Merge auf beiden
  PUT-Wegen, Compare-Alarme-Tab auf das Trip-Muster
  (`alarmeDeliveryPayload`), Migration flach → `alert_channels`.
- **Bis S2 ist `alert_channels` beim Vergleich nur per Datei/Test
  erreichbar, kein UI-Pfad.** Der Compare-Alarme-Tab schreibt weiterhin die
  flachen Felder; das ist in dieser Scheibe korrekt, weil der Adapter den
  Bestand ohne gesetztes `alert_channels` identisch zum heutigen Verhalten
  behandelt (AC-3).
- **Sichtbare Nebenwirkung im Unterdrückungs-Protokoll:** `effective_channels`
  listet beim Vergleich künftig auch nicht-sendebereite Opt-in-Kanäle (wie
  beim Trip seit je) — Versand bleibt durch die Sendezeit-Guards in
  `notification_service.py` unverändert korrekt.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue — ADR-0021 (geteilte Alert-Engine) und ADR-0023
  (`kind`-Diskriminierung) gelten unverändert weiter.
- **Rationale:** Diese Scheibe führt keine neue Entscheidungsfläche ein —
  sie hebt einen bereits produktiv gehärteten Kern (Trip-Alarm-Algorithmus)
  auf beide `kind`-Werte, exakt im Sinne von ADR-0021 (ein geteilter Baustein
  statt zweier eigenständiger Prüfketten). Die Kanal-Semantik des Trips wird
  zur gemeinsamen Semantik; keine neue Persistenz-, Auth- oder
  Provider-Entscheidung ist betroffen.

## Changelog

- 2026-09-09: Initial spec created
