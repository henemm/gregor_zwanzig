---
entity_id: issue_952_onset_alert_fidelity
type: module
created: 2026-07-02
updated: 2026-07-02
status: draft
version: "1.0"
tags: [alert, radar, onset, telegram, sms, design-fidelity]
---

# Onset-/Radar-Alert-Fidelity (Issue #952, reopened)

## Approval

- [x] Approved (PO 'go', 2026-07-02 — inkl. beider Empfehlungen aus Open Questions)

## Purpose

Der kanonische Alert-Renderer (`src/output/renderers/alert/render.py`) hat zwei Zweige —
Deviation (`msg.source is None`) und Onset (`msg.source is not None`). #952/#957 haben nur
den Deviation-Zweig auf Design-Tokens/Vorlagen-Struktur gebracht; die Onset-Mails
(„Regen in X Min") sind weiterhin Ad-hoc-HTML ohne Marken-Tokens, mit Float-Rauschen in
km-Werten, einem doppelten/verirrten Zeit-Satz in der Intensitäts-Zeile und einem rohen
`**fett**`-Telegram-Text ohne echtes Bold. Zusätzlich fehlt der SMS-Versand im Radar-Pfad
vollständig, obwohl der Renderer (`_render_sms_onset`) bereits existiert und getestet ist.
Diese Spec bringt den Onset-Zweig auf dieselbe Design-Fidelity wie den Deviation-Zweig
(Vorbild `render_email` Z.185-244), behebt die Formatfehler, aktiviert SMS im Radar-Pfad,
und schafft einen realistischen E2E-Verifikationsweg für einen praktisch nicht auf Abruf
auslösbaren Pfad.

## Source

- **File:** `src/output/renderers/alert/render.py` (Onset-Renderer),
  `src/services/trip_alert.py` (`check_radar_alerts`), `src/outputs/telegram.py`
  (`TelegramOutput.send`), `api/routers/validator.py` (Alert-Preview #918)
- **Identifier:** `_render_email_onset`, `_render_telegram_onset`, `_render_subject_onset`,
  `_render_sms_onset`, `render_email`, `render_telegram`, `TripAlertService.check_radar_alerts`,
  `TelegramOutput.send`, `alert_preview`

> **Schicht-Hinweis (Template-Pflicht):** Alle betroffenen Dateien liegen im Python-Backend
> (`src/services/`, `src/output/`, `src/outputs/`) bzw. im FastAPI-Router (`api/routers/`).
> Kein Frontend-/Go-Anteil in dieser Spec.

## Estimated Scope

- **LoC:** +150 / −40 (Limit 250 reicht, knapp)
- **Files:** 6 (`render.py`, `trip_alert.py`, `telegram.py`, `validator.py`, +2 Testdateien
  neu/erweitert)
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `output/renderers/email/design_tokens.py` | Upstream | G_ACCENT/G_INK/FONT_UI/FONT_DATA für Onset-E-Mail-HTML |
| `output/renderers/alert/model.py` (`AlertMessage`, `OnsetEvent`, `km_span`) | Upstream | Datenmodell, unverändert |
| `services/radar_service.py` (`NowcastResult.intensity_label`, `source_label`) | Upstream | kurzes Intensitäts-Label — bereits vorhanden, wird aktuell verworfen |
| `services/trip_alert.py::_get_radar_service` (DI-Seam, Konstruktor-Param `radar_service=`) | Upstream | Fake-Radar-Seam für E2E-Beweis |
| `outputs/sms.py::SMSOutput` | Upstream | SMS-Versand-Client, Vorbild `_send_alert` Z.989-996 |
| `app/config.py::Settings.can_send_sms/_email/_telegram` | Upstream | Kanal-Gates |
| `api/routers/validator.py::alert_preview` (#918) | Downstream | muss Onset-Zweig rendern können |
| 8 `TelegramOutput.send`-Caller (Briefings, Bot-Antworten, Deviation-Alert) | Downstream | Signaturänderung MUSS rückwärtskompatibel sein |

## Implementation Details

### 1. E-Mail-Onset auf Design-Tokens (Vorlage Zeilen 298-333)

`_render_email_onset()` (render.py:69-92) baut aktuell Ad-hoc-HTML
(`font-family:sans-serif`, `#555`, Zeile 84/87) — kein `design_tokens`-Import, kein
Verdikt-Badge, kein umrandeter Datenblock, keine Cooldown-Box. SOLL (Vorlage Z.298-333):

- **Verdikt-Badge** (Vorlage Z.311): accent-getönter Badge `Radar-Nowcast`
  (`background:{G_ACCENT} bei 12% Alpha}`, `color:{G_ACCENT}`) — analog Deviation-Badge
  (render.py Z.237-239), aber Accent- statt Danger/Success-Ton, da Onset kein Δ ist.
- **H1** (Vorlage Z.312): `{label} in {onset_minutes} Min` (unverändert vom heutigen Text,
  nur jetzt mit `FONT_UI`/`G_INK` statt Ad-hoc-Style — Vorbild render.py Z.236).
- **Datenblock, 3 Zeilen** (Vorlage Z.314-327, Vorbild `_datablock_single`
  render.py:159-177 + Rendering-Loop Z.214-224):
  1. `Wo & wann` → `km {a}–{b} · ab {onset_time}` (mono/`FONT_DATA`)
  2. `Intensität` → `{intensity_label}` (kurzes Label, s. Punkt 3 unten)
  3. `Quelle` → `{source_label}`
- **Cooldown-Box** (Vorlage Z.329): eigener Block mit `border-left:4px solid {G_ACCENT}`
  (analog `.means`-Klasse der Vorlage), Text
  `Cooldown: Du erhältst diese Warnung höchstens einmal in {cooldown_display}.` — nur wenn
  `msg.cooldown_display` gesetzt ist (bestehende Optionalität erhalten).
- **Fußzeile** (Vorlage Z.331): `Stand: heute {stand_at} · Quelle: {source_label}` — HEUTE
  fälschlich `Stand: heute {stand_at} · km {a}–{b} · Quelle: {source_label}` (render.py:74);
  die Vorlage hat KEINE km-Angabe in der Fußzeile (die steht bereits in Datenblock-Zeile 1).
- Plain-Text-Variante bleibt äquivalent zur HTML-Struktur (wie bisher, Zeilen mit Label:Value).

### 2. km-Rundung konsistent (Betreff/Body/Telegram/SMS)

`_render_subject_onset` (Z.65) rundet bereits mit `int(e.km_from)`/`int(e.km_to)`
(Truncation, nicht Rundung — abweichend von `_km_str`s `int(round())`). `_render_email_onset`
(Z.73-74) und `_render_telegram_onset` (Z.98) interpolieren `e.km_from`/`e.km_to` roh (Float)
→ „km 9.8–15.200000000000001". SOLL: alle vier Renderer nutzen `int(round(e.km_from))`/
`int(round(e.km_to))` — neuer Helper `_km_str_onset(e)` (analog `_km_str_events`,
render.py:180-182), von Subject/Email/Telegram gemeinsam genutzt. `_render_sms_onset`
rundet bereits korrekt (Z.108) — bleibt unverändert.

### 3. Intensitäts-Label ohne Satz-Duplikat

`check_radar_alerts` (trip_alert.py:792-797) füllt `OnsetEvent.intensity_label` heute mit
`radar_svc.format_now_text(result, tz=tz, include_source=False)` — ein ganzer Satz
(„leichter Regen ab ca. 13:10 (in ~10 Min).") plus Suffix `, im Briefing nicht angekündigt`.
Der Renderer hängt selbst nochmal `ab {onset_time}` an (render.py:73) →
„…ab ca. 13:10 (in ~10 Min)., im Briefing nicht angekündigt ab 13:10".

SOLL: `OnsetEvent.intensity_label = result.intensity_label` (kurzes Label, z.B.
„leichter Regen" — `radar_service.py:62`, bereits vorhanden, kein `radar_service`-Umbau
nötig). Der `format_now_text`-Aufruf (Z.793) entfällt ersatzlos für die Label-Befüllung.

Die Briefing-Kontext-Info („im Briefing nicht angekündigt" / „jetzt akut") hat in der
Vorlage keinen vorgesehenen Platz (s. Open Questions) — Entscheidung fällt der PO bei
Spec-Freigabe; Default-Implementierung dieser Spec: **als vierte Datenblock-Zeile**
`Briefing → nicht angekündigt` bzw. `Briefing → bereits angekündigt` (nur E-Mail, nicht
Telegram/SMS — dort bleibt es bei den zwei/einer Vorlagen-Zeile(n)).

### 4. Telegram: echtes Bold statt `**`, kein `[Betreff]`-Duplikat

Betrifft BEIDE Zweige (Onset UND Deviation, da beide `**` nutzen — render.py:99/257).

- `TelegramOutput.send()` (`src/outputs/telegram.py:50-96`) stellt heute IMMER
  `[{subject}]\n\n` voran (Z.67) und sendet ohne `parse_mode` → `**` erscheint wörtlich.
  SOLL: zwei neue optionale Parameter mit Default = heutiges Verhalten:
  ```python
  def send(
      self, subject: str, body: str, reply_markup: dict | None = None,
      *, parse_mode: str | None = None, suppress_subject_line: bool = False,
  ) -> int | None:
  ```
  - `parse_mode="HTML"` → `payload["parse_mode"] = "HTML"` zusätzlich zu `text`.
  - `suppress_subject_line=True` → `message = body` (kein `[{subject}]\n\n`-Präfix).
  - Beide Defaults `None`/`False` → Payload und Text-Bau bit-identisch zum heutigen Code
    (Vollständigkeits-Beweis: 8 Bestands-Caller rufen ohne diese Parameter).
- Renderer (`_render_telegram_onset` UND `render_telegram`) liefern KEIN `**...**` mehr,
  sondern `<b>{_esc(...)}</b>` (HTML-Tags, `_esc()` escaped bereits `&<>` — Z.302-303,
  ausreichend für Telegram-HTML-Mode, das nur `<>&` maskiert haben muss).
- Aufrufer in `trip_alert.py` (Onset Z.840, Deviation Z.981) rufen künftig mit
  `parse_mode="HTML", suppress_subject_line=True`.
- **ADR-Hinweis:** `parse_mode=HTML` (nicht MarkdownV2) ist eine kanalweite
  Formatierungsentscheidung mit Tragweite über diese Spec hinaus (Begründung: MarkdownV2
  hat 18 escape-pflichtige Zeichen, Trip-Namen mit `.`/`-`/`(` würden sonst 400-Fehler der
  Bot-API auslösen). Ob dafür ein eigenes ADR in `docs/adr/` angelegt wird, entscheidet der
  Orchestrierer bei Implementierung — diese Spec dokumentiert nur die Entscheidung selbst.

### 5. SMS-Versand im Radar-Pfad (`check_radar_alerts`)

`check_radar_alerts` (trip_alert.py:654-846) versendet aktuell nur E-Mail (Z.821-834) und
Telegram (Z.836-842). `_render_sms_onset` existiert (render.py:104-110) und ist getestet,
wird aber nie aufgerufen. SOLL, Vorbild `_send_alert`-SMS-Ast (trip_alert.py:989-996):

```python
if self._settings.can_send_sms() and config and getattr(config, "send_sms", False):
    delivered = True
    try:
        from outputs.sms import SMSOutput
        SMSOutput(self._settings).send(subject=subject, body=render_sms(_alert_msg))
    except Exception as e:
        logger.error(f"Radar alert SMS failed for {trip.id}: {e}")
```

- **Gate-Erweiterung** (Z.766-770): `can_email`/`can_telegram`-Check wird um `can_sms`
  ergänzt — `if not can_email and not can_telegram and not can_sms: continue`. Ein Trip mit
  NUR SMS aktiv darf nicht mehr komplett übersprungen werden (heutiger Bug: Alert geht bei
  reiner SMS-Konfiguration gar nicht raus, weil Zeile 768 das nicht vorsieht).
- `render_sms` muss in trip_alert.py importiert werden (Z.788-790 Import-Block erweitern).

### 6. Alert-Preview-Endpoint (#918) — Onset-Zweig

`alert_preview` (`api/routers/validator.py:264-307`) baut aktuell AUSSCHLIESSLICH
Deviation-`AlertMessage` via `to_alert_message(changes, ...)` — es gibt keinen Codepfad, der
eine Onset-`AlertMessage` synthetisch erzeugt. SOLL: `AlertPreviewBody` bekommt ein neues
optionales Feld `onset: OnsetPayload | None = None`; ist es gesetzt, wird `OnsetEvent` +
`AlertMessage(source=..., cooldown_display=...)` direkt konstruiert (analog
`_make_onset_msg`-Testhelper aus `test_issue_919_radar_alert_canonical.py`) statt über
`to_alert_message`. Response-Shape (`subject/email_html/email_plain/telegram/sms`) bleibt
identisch — nur der Konstruktionspfad verzweigt.

```python
class OnsetPayload(BaseModel):
    onset_minutes: int
    onset_time: str
    km_from: float
    km_to: float
    is_convective: bool
    intensity_label: str
    source_label: str
    cooldown_display: str | None = None

class AlertPreviewBody(BaseModel):
    changes: list[ChangePayload] = Field(default_factory=list)
    segment_times: list[SegmentTimePayload] = Field(default_factory=list)
    onset: OnsetPayload | None = None
```

Validierung: genau einer von `onset` ODER (`changes` UND `segment_times`) MUSS gesetzt sein
— sonst `HTTPException(422)`.

## Expected Behavior

- **Input:** Radar-Nowcast-Ergebnis (`NowcastResult`) mit Onset-Ereignis über dem
  Alarm-Schwellwert (`radar_alert_due`), Trip mit mindestens einem aktiven Kanal
  (E-Mail/Telegram/SMS).
- **Output:** E-Mail nach Vorlagen-Struktur (Badge/H1/Datenblock/Cooldown-Box/Fußzeile,
  Design-Tokens), Telegram mit echtem Bold ohne `[Betreff]`-Zeile, SMS mit `R!`/`TH!`-Token
  — konsistent gerundete km-Werte über alle vier Kanäle.
- **Side effects:** `check_radar_alerts` versendet künftig auch SMS (bei aktiviertem
  Kanal) — zusätzlicher Versandpfad, zusätzliche `SMSOutput.send`-Aufrufe, zusätzliche
  Kosten pro SMS (seven.io) bei aktivierten SMS-Trips mit Radar-Alerts.

## Acceptance Criteria

- **AC-1:** Given eine Onset-`AlertMessage` (`source` gesetzt) / When `render_email(msg)`
  aufgerufen wird / Then enthält das HTML einen `G_ACCENT`-getönten Verdikt-Badge mit Text
  „Radar-Nowcast", eine H1 „{Label} in {N} Min", einen 3-zeiligen Datenblock (Wo & wann /
  Intensität / Quelle) im `FONT_DATA`-Stil analog `_datablock_single`, eine Cooldown-Box mit
  `border-left:4px solid {G_ACCENT}` (wenn `cooldown_display` gesetzt) und eine Fußzeile
  „Stand: heute {stand_at} · Quelle: {source_label}" OHNE km-Angabe.
  - Test: `render_email()` direkt mit konstruierter Onset-`AlertMessage` aufrufen, HTML auf
    Vorhandensein von Badge/H1/Datenblock/Cooldown/Fußzeile-Struktur UND auf Abwesenheit der
    alten Ad-hoc-Styles (`font-family:sans-serif`, `color:#555`) prüfen — Plausibilität, nicht
    reine String-Presence.

- **AC-2:** Given ein `OnsetEvent` mit `km_from=9.8, km_to=15.200000000000001` / When
  Betreff, E-Mail-Body, Telegram und SMS gerendert werden / Then zeigen alle vier Kanäle
  identisch `km 10–15` (kein Float-Rauschen, keine Nachkommastellen, kein Rundungs-Drift
  zwischen Kanälen).
  - Test: alle vier Renderer mit demselben `OnsetEvent` aufrufen, `re.search(r"km \d+–\d+", ...)`
    extrahieren und auf Gleichheit über alle vier Outputs prüfen.

- **AC-3:** Given `NowcastResult.intensity_label = "leichter Regen"` / When
  `check_radar_alerts` ein `OnsetEvent` baut und rendert / Then enthält die E-Mail-Zeile
  „Intensität" exakt „leichter Regen" (kein Satz mit „ab ca.", kein doppeltes „ab {time}",
  kein „im Briefing nicht angekündigt"-Anhängsel in derselben Zeile).
  - Test: `check_radar_alerts()` mit Fake-Radar-Seam (garantiert-nasses `NowcastResult`,
    `intensity_label="leichter Regen"`) durchlaufen lassen, gerenderte E-Mail (`_mail_sink`)
    auf die exakte Intensitäts-Zeile prüfen.

- **AC-4:** Given `TelegramOutput.send(subject, body, parse_mode="HTML",
  suppress_subject_line=True)` / When die Nachricht gebaut wird / Then fehlt das
  `[{subject}]\n\n`-Präfix, der Payload enthält `parse_mode: "HTML"`, und der Renderer-Output
  enthält `<b>...</b>` statt `**...**` — geprüft für BEIDE Zweige (Onset UND Deviation).
  - Test: `render_telegram()` für Onset- UND Deviation-`AlertMessage` aufrufen, auf `<b>` statt
    `**` prüfen; `TelegramOutput.send`-Payload-Konstruktion (ohne echten HTTP-Call) auf
    fehlendes Präfix + `parse_mode`-Feld prüfen.

- **AC-5:** Given die 8 Bestands-Caller von `TelegramOutput.send` (Briefings via
  `trip_report_scheduler.py`, Bot-Antworten via `inbound_telegram_reader.py` ×5, sowie beide
  Alert-Zweige VOR dieser Änderung aufgerufen ohne die neuen Parameter) / When `send()` ohne
  `parse_mode`/`suppress_subject_line` aufgerufen wird / Then ist die gebaute Nachricht
  bit-identisch zum Verhalten vor dieser Änderung (`[{subject}]\n\n{body}`, kein
  `parse_mode`-Feld im Payload).
  - Test: `send()` ohne die neuen Parameter mit denselben Fixture-Werten wie ein
    Bestandstest (z.B. bestehender Telegram-Send-Test) aufrufen, Payload-Dict exakt mit dem
    dokumentierten Alt-Verhalten vergleichen.

- **AC-6:** Given ein Trip mit ausschließlich SMS als aktivem Alert-Kanal (`send_email=False,
  send_telegram=False, send_sms=True` im `report_config`) / When `check_radar_alerts()` ein
  fälliges Onset-Ereignis findet / Then wird `SMSOutput.send()` mit dem Ergebnis von
  `render_sms(msg)` (`GR20 km5-18: R!12`-Format) aufgerufen, UND der Alert wird NICHT mehr
  komplett übersprungen (heutiger Bug: Z.766-770-Gate kennt nur email/telegram).
  - Test: `check_radar_alerts()` mit Fake-Radar-Seam + `mail_sink`/SMS-Sink-Doppel und
    SMS-only-Trip durchlaufen lassen; prüfen, dass der SMS-Sink genau einmal mit dem
    korrekten Token-Text aufgerufen wurde und `delivered=True` gesetzt wurde (kein
    Early-Continue).

- **AC-7:** Given `POST /api/trips/{trip_id}/alert-preview` mit Body `{"onset": {...}}`
  (statt `changes`/`segment_times`) / When der Endpoint aufgerufen wird / Then liefert die
  Response `subject/email_html/email_plain/telegram/sms` für den Onset-Zweig (nicht
  Deviation) — analog zum bestehenden Deviation-Preview, aber mit Onset-typischem Inhalt
  (`Radar-Nowcast`-Badge, `R!`/`TH!`-SMS-Token).
  - Test: echter HTTP-Call gegen den FastAPI-TestClient/Staging-Endpoint mit Onset-Payload,
    Response-JSON auf `Radar-Nowcast` in `email_html` und `!` im `sms`-Feld prüfen.

- **AC-8:** Given beide Renderer-Zweige (Deviation UND Onset) / When derselbe
  Test-Parametrisierungslauf (`@pytest.mark.parametrize("source", [None, "Radar (DWD)"])`)
  über `render_subject`/`render_email`/`render_telegram`/`render_sms` läuft / Then bestehen
  BEIDE Zweige dieselben strukturellen Mindestanforderungen (kein Crash, kein leerer String,
  km-Format konsistent) — verhindert strukturell, dass ein Zweig gefixt wird und der andere
  vergessen wird (Root Cause dieses Issues laut Analyse).
  - Test: neue Datei `tests/tdd/test_952_onset_alert_fidelity.py`, Parität-Testklasse mit
    beiden `source`-Werten.

- **AC-9:** Given ein Fake-Radar-Seam (`TripAlertService(radar_service=<echte Subklasse mit
  get_nowcast() → garantiert-nasses NowcastResult>)`, KEIN `Mock()`/`patch()`) / When
  `check_radar_alerts()` gegen Staging läuft / Then wird eine echte E-Mail an
  `gregor-test@henemm.com` zugestellt (IMAP-Beweis: Badge-Text, Datenblock-Struktur,
  gerundete km-Werte im Body) UND eine echte Telegram-Nachricht über den Staging-Bot
  verifiziert (fette erste Zeile sichtbar, kein `[Betreff]`-Duplikat).
  - Test: E2E-Test rot vor Fix (heutige Ad-hoc-HTML-Struktur/`**`-Literale/Float-km
    nachweisbar), grün nach Fix (Vorlagen-Struktur nachweisbar) — Vorbild
    `tests/tdd/test_773_alert_e2e.py` (Fake-Seam-Pattern, IMAP-Verifikation).

## Known Limitations

- Die Briefing-Kontext-Info („im Briefing nicht angekündigt"/„jetzt akut") bekommt in dieser
  Spec eine vierte Datenblock-Zeile NUR in der E-Mail — die Design-Vorlage sieht dafür
  keinen Platz vor; falls der PO bei Freigabe „weglassen" statt „vierte Zeile" wählt, entfällt
  Punkt 3 der Implementation Details ersatzlos (kein AC hängt zwingend an der vierten Zeile).
- Issue #931 (km-Rundung inkonsistent, offen) wird durch AC-2 voraussichtlich mit erledigt —
  beim Abschluss dieser Spec gegenprüfen und ggf. schließen.
- Issue #954 (Telegram-Fußzeile im Briefing veraltet) ist bewusst NICHT im Scope dieser Spec.
- Float-Quelle in `src/services/trip_segments.py:150,156` (kumulative Float-Addition) wird
  NICHT angefasst — Fix ist bewusst renderer-seitig (`int(round())`), nicht an der Quelle.

## Non-Goals

- Deviation-E-Mail-Layout wird NICHT verändert (bereits #952/#957-fidelity-konform).
- `src/services/trip_segments.py` (Float-Quelle der km-Werte) wird NICHT angefasst.
- Issue #954 (Telegram-Fußzeile Briefing) ist separater Scope, hier nicht enthalten.
- MarkdownV2 als Telegram-Format wird NICHT eingeführt — HTML ist die getroffene Wahl.

## Test-Plan

| Datei | Änderung | Grund |
|---|---|---|
| `tests/tdd/test_issue_919_radar_alert_canonical.py` | MODIFY (Format-Assertions) | AC-2/AC-3/AC-4 ändern das erwartete Onset-Text-Format (km-Rundung, kein `**`, kurzes Intensitäts-Label) |
| `tests/tdd/test_952_alert_mail_design_fidelity.py` | MUSS GRÜN BLEIBEN | Deviation-Zweig unverändert (Regressions-Wächter) |
| `tests/tdd/test_957_alert_mail_literal_structure.py` | MUSS GRÜN BLEIBEN | Deviation-Literal-Struktur unverändert |
| `tests/tdd/test_914_slice4_alert_sms_dispatch.py` | MUSS GRÜN BLEIBEN | Deviation-SMS-Dispatch unverändert; neuer Radar-SMS-Test daneben, kein Umbau dieser Datei |
| `tests/tdd/test_952_onset_alert_fidelity.py` | CREATE | AC-1/AC-2/AC-3/AC-6/AC-8 — Renderer-Unit-Tests + Parität-Test (source=None/gesetzt) + Radar-SMS-Dispatch-Test (Fake-Seam, `mail_sink`) |
| `tests/tdd/test_952_onset_alert_e2e.py` | CREATE | AC-9 — Fake-Radar-Seam-E2E gegen Staging (IMAP + Telegram-Beweis) |
| `api/routers/validator.py` — zugehöriger Test (z.B. `tests/tdd/test_918_*` oder neu) | MODIFY/CREATE | AC-7 — Onset-Preview-Payload-Test |

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine (Empfehlung: Orchestrierer prüft, ob `parse_mode=HTML` als
  kanalweite Telegram-Formatierungsentscheidung ein eigenes ADR in `docs/adr/` verdient —
  s. Implementation Details Punkt 4)
- **Rationale:** Diese Spec selbst ist ein Fidelity-/Bugfix ohne neue Architektur-Grundsatz-
  entscheidung; die einzige potenziell ADR-würdige Einzelentscheidung (HTML- statt
  MarkdownV2-Parse-Mode für Telegram) ist inhaltlich dokumentiert, ihre Formalisierung als
  ADR ist optional und liegt beim Orchestrierer.

## Open Questions (PO-Entscheidung bei Freigabe)

> **ENTSCHIEDEN (PO 'go' 2026-07-02):** Beide Empfehlungen angenommen — Badge-Text ist
> nur `Radar-Nowcast`; Briefing-Kontext-Info kommt als vierte Datenblock-Zeile in die E-Mail.

- [x] **Badge-Text:** Vorlage (Zeile 311) lautet wörtlich `Radar-Nowcast · kein Δ, kein
      Pfeil`. Wirkt der Zusatz „· kein Δ, kein Pfeil" wie eine Design-Doc-Annotation (Erklärung
      für den Leser der Vorlage, nicht für den E-Mail-Empfänger) oder soll er wörtlich in der
      Produktions-Mail erscheinen? **Empfehlung: nur `Radar-Nowcast`** — der Zusatz erklärt dem
      Design-Vorlagen-Leser die Abgrenzung zum Deviation-Badge, ist aber für den
      E-Mail-Empfänger ohne Kontext (der nie einen Δ/Pfeil-Badge gesehen hat) bedeutungslos.
- [ ] **Briefing-Kontext-Info:** Vorlage sieht keinen Platz für „im Briefing nicht
      angekündigt"/„jetzt akut" vor. **Empfehlung: als vierte Datenblock-Zeile aufnehmen**
      (`Briefing → nicht angekündigt` / `Briefing → bereits angekündigt`), da fachlich
      wertvoll im Sinne der Abweichungs-Wächter-Produktvision (Alert meldet Abweichung vom
      letzten Briefing-Stand) — auch wenn die Vorlage sie nicht zeigt.

## Changelog

- 2026-07-02: Initial spec created (Issue #952 reopened, Onset-Zweig-Diagnose aus
  `docs/context/fix-952-onset-alert-fidelity.md`)
