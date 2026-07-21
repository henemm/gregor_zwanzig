---
entity_id: issue_457_compare_email_tags
type: module
created: 2026-05-30
updated: 2026-05-30
status: draft
version: "1.0"
issue: 457
tags: [compare, email, winner-tags, per-recipient, error-handling, python]
---

# Issue #457 — Compare-E-Mail: Winner-Tags + Per-Empfänger-Fehlerbehandlung

## Approval

- [ ] Approved

## Purpose

Erweitert den bestehenden Compare-E-Mail-Renderer (`compare_html.py`) um einen profilabhängigen Winner-Tag-Generator, der den Score-Badge mit kontextspezifischen Begründungs-Pills (good/warn/info) ergänzt. Parallel wird die Fehlerbehandlung in `EmailOutput.send()` auf Einzel-Empfänger-Granularität gehoben, sodass ein SMTP-Fehler bei einem Empfänger die anderen nicht blockiert.

## Source

- **EDIT:** `src/output/renderers/email/compare_html.py` — neue private Funktion `_generate_winner_tags()` + `_render_tag()`, Integration in Winner-Card (~+55 LoC)
- **EDIT:** `src/outputs/email.py` — `EmailOutput.send()` bei mehreren Empfängern pro Empfänger individuell senden mit try/except (~+22 LoC)
- **EDIT:** `tests/tdd/test_compare_html_email.py` — neue Test-Klasse für Tag-Assertions (~+65 LoC)
- **NEU:** `tests/tdd/test_issue_457_email_per_recipient.py` — Tests für Per-Empfänger-Fehlerbehandlung (~+45 LoC)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `LocationResult` (`src/app/user.py`) | intern | Eingabe-DTO für `_generate_winner_tags()`: snow_depth_cm, snow_new_cm, sunny_hours, wind_max, gust_max, cloud_avg, above_low_clouds, temp_max |
| `ActivityProfile` (`src/app/profile.py`) | intern | Profil-Dispatch für Tag-Regeln (WINTERSPORT / WANDERN / SUMMER_TREKKING / ALLGEMEIN) |
| `ComparisonResult` (`src/app/user.py`) | intern | Wird an `render_compare_html()` übergeben; `.winner`-Property als Eingabe für `_generate_winner_tags()` |
| `design_tokens.py` (`src/output/renderers/email/design_tokens.py`) | intern | Farbkonstanten (werden für Matrix und Footer genutzt); Tag-Farben sind eigene Inline-Hex-Werte, NICHT aus design_tokens |
| `EmailOutput` (`src/outputs/email.py`) | intern | Versandkanal — wird um Per-Empfänger-Logik erweitert |

## Implementation Details

### §1 `_generate_winner_tags()` in `compare_html.py`

**Signatur:**

```python
def _generate_winner_tags(
    winner: LocationResult,
    profile: Optional[ActivityProfile],
) -> list[tuple[str, str]]:
    """Gibt bis zu 4 (tone, label)-Tupel zurück. Priorität: good > warn > info."""
```

**Tag-Regeln je Profil (Priorität: good > warn > info, max 4 Tags):**

WINTERSPORT:
- `snow_depth_cm >= 100` → `("good", "Schneehöhe {x:.0f} cm")`
- `snow_depth_cm >= 50` (nur wenn kein good-Schneehöhe-Tag) → `("info", "Schneehöhe {x:.0f} cm")`
- `snow_new_cm >= 10` → `("good", "+{x:.0f} cm Neuschnee")`
- `snow_new_cm >= 3` (nur wenn kein good-Neuschnee-Tag) → `("info", "+{x:.0f} cm Neuschnee")`
- `above_low_clouds == True` → `("good", "Über den Wolken")`
- `sunny_hours >= 6` → `("good", "{x} h Sonne")`
- `wind_max > 40` → `("warn", "Wind {x:.0f} km/h")`
- `gust_max > 60` → `("warn", "Böen {x:.0f} km/h")`

WANDERN:
- `sunny_hours >= 7` → `("good", "{x} h Sonne")`
- `sunny_hours >= 4` (nur wenn kein good-Sonne-Tag) → `("info", "{x} h Sonne")`
- `wind_max > 40` → `("warn", "Wind {x:.0f} km/h")`
- `cloud_avg >= 80` → `("warn", "Stark bewölkt")`
- `temp_max in 5..22°C` → `("good", "Temp. {x:.0f}°C")`

SUMMER_TREKKING und ALLGEMEIN:
- `sunny_hours >= 6` → `("good", "{x} h Sonne")`
- `wind_max > 30` → `("warn", "Wind {x:.0f} km/h")`
- `cloud_avg < 30` → `("good", "Gering bewölkt")`

**Hinweis:** `precip_mm` und `thunder_level` sind NICHT auf `LocationResult` — keine Regen- oder Gewitter-Tags implementieren.

**Maximierung:** Nach Sammlung aller passenden Tags werden good-Tags zuerst aufgelistet, dann warn, dann info. Die Liste wird auf 4 Einträge gekürzt.

**Wenn `winner` None oder Profil None:** Leere Liste zurückgeben, kein Fehler.

### §2 `_render_tag()` in `compare_html.py`

**Signatur:**

```python
def _render_tag(tone: str, label: str) -> str:
    """Rendert einen einzelnen Tag als Inline-CSS-Pill-HTML-String."""
```

**Tag-Farben (Inline-Hex, NICHT aus design_tokens.py):**

| tone | bg | fg | border |
|------|----|----|--------|
| good | `#dcf2e1` | `#14532d` | `#86c89a` |
| warn | `#fde6cc` | `#7c2d12` | `#f0a060` |
| info | `#dde8f3` | `#1e3a5f` | `#8aacd0` |

**HTML-Ausgabe je Tag:**
```html
<span style="display:inline-block;padding:2px 8px;border-radius:12px;font-size:12px;font-weight:600;background:{bg};color:{fg};border:1px solid {border};">{label}</span>
```

### §3 Integration in Winner-Card (`compare_html.py`)

In der bestehenden Winner-Card-Sektion, direkt nach dem Score-Badge:

```html
<div style="display:flex;gap:6px;flex-wrap:wrap;margin-top:8px;">
  {_render_tag(tone, label) for tone, label in tags}
</div>
```

- Tags werden nur gerendert wenn `_generate_winner_tags()` eine nicht-leere Liste zurückgibt
- Der umgebende `<div>`-Container wird bei leerer Liste weggelassen (kein leerer Flex-Container)

### §4 Per-Empfänger-Fehlerbehandlung in `EmailOutput.send()` (`email.py`)

**Aktueller Stand:** `server.sendmail(from_addr, recipients, msg.as_string())` — alle Empfänger in einem Call.

**Neue Logik (nur wenn `len(recipients) > 1`):**

```python
# Einzelner Empfänger: Verhalten unverändert (ein sendmail-Call)
if len(recipients) == 1:
    server.sendmail(from_addr, recipients, msg.as_string())
else:
    # Mehrere Empfänger: pro Empfänger individueller Call
    for recipient in recipients:
        try:
            server.sendmail(from_addr, [recipient], msg.as_string())
        except smtplib.SMTPException as exc:
            logger.error("SMTP-Fehler für Empfänger %s: %s", recipient, exc)
            # Kein Re-raise — nächster Empfänger wird trotzdem versucht
```

- Die SMTP-Verbindung (inkl. `starttls` + `login`) wird einmalig pro Versandlauf geöffnet — nicht pro Empfänger.
- Return-Type bleibt `None` (Protocol-konform, kein Breaking Change für Trip-Briefings).
- Retry-Logik (OSError-Backoff) bleibt auf den Verbindungsaufbau beschränkt, wird nicht pro Empfänger wiederholt.
- Die äußere `smtplib.SMTPException`-Behandlung (Permanent-Fehler ohne Retry) bleibt für den Verbindungsaufbau erhalten.

### §5 Tests

**Erweiterung `tests/tdd/test_compare_html_email.py`:**

Neue Klasse `TestWinnerTags`:
- `test_ac1_wintersport_schneehöhe_tag`: `LocationResult` mit `snow_depth_cm=120`, Profil WINTERSPORT → Tag `("good", "Schneehöhe 120 cm")` enthalten
- `test_ac1_tags_in_html`: `render_compare_html()` mit Winner + Profil → HTML enthält `#dcf2e1` (good-Tag-Farbe) und `Schneehöhe`
- `test_ac1_max_4_tags`: 6 passende Bedingungen → Liste hat genau 4 Einträge, Reihenfolge good > warn > info
- `test_ac1_keine_tags_bei_none_winner`: `result.winner=None` → kein Pill-Container im HTML
- `test_ac1_wandern_temp_tag`: `temp_max=18`, Profil WANDERN → `("good", "Temp. 18°C")`

**Neue Datei `tests/tdd/test_issue_457_email_per_recipient.py`:**

Klasse `TestPerRecipientSend` (kein SMTP, kein Mock, nur Logik via Subklasse):
- `test_ac5_einzelner_empfänger_unverändert`: `recipients=["a@b.com"]` → `sendmail` einmal mit kompletter Liste aufgerufen (Verhalten unverändert)
- `test_ac5_mehrere_empfänger_individuell`: `recipients=["a@b.com", "b@c.com"]` → `sendmail` zweimal aufgerufen, je mit einzelner Adresse
- `test_ac5_fehler_blockt_nicht`: erster Empfänger wirft `SMTPException` → zweiter Empfänger wird trotzdem versucht, kein Re-raise nach außen

**Hinweis:** Tests dürfen SMTPException-Verhalten über echte SMTP-Interaktion mit dem Stalwart-Testserver prüfen, NICHT über `Mock()`. Wenn eine Verbindung zu einem nicht-existenten Empfänger einen SMTP-Fehler erzeugt, kann das als echter Test-Trigger verwendet werden.

### §6 LoC-Schätzung

| Datei | Inhalt | LoC-Delta |
|-------|--------|-----------|
| `src/output/renderers/email/compare_html.py` | `_generate_winner_tags`, `_render_tag`, Winner-Card-Integration | +55 |
| `src/outputs/email.py` | Per-Empfänger-Schleife mit try/except | +22 |
| `tests/tdd/test_compare_html_email.py` | Klasse `TestWinnerTags` mit 5 Tests | +65 |
| `tests/tdd/test_issue_457_email_per_recipient.py` | Klasse `TestPerRecipientSend` mit 3 Tests | +45 |
| **Summe** | | **~187 LoC** |

Kein LoC-Override nötig (Limit: 250).

## Expected Behavior

- **Input für `_generate_winner_tags`:** `LocationResult` mit Metrikfeldern (snow_depth_cm, snow_new_cm, sunny_hours, wind_max, gust_max, cloud_avg, above_low_clouds, temp_max), optionales `ActivityProfile`
- **Output von `_generate_winner_tags`:** Liste von max. 4 `(tone, label)`-Tupeln, sortiert good > warn > info. Leere Liste wenn `winner` oder `profile` None.
- **Output von `render_compare_html`:** Unveränderter HTML-String mit Winner-Card; falls Tags vorhanden, enthält die Winner-Card zusätzlich einen Flex-Container mit Inline-CSS-Pills
- **Side effects `EmailOutput.send`:** Bei mehreren Empfängern wird pro Empfänger ein separater `sendmail`-Call ausgeführt. SMTP-Fehler einzelner Empfänger werden per `logger.error()` protokolliert und unterbrechen die Schleife für diesen Empfänger nicht die restlichen Empfänger. Return bleibt `None`.

## Acceptance Criteria

**AC-1:** Given ein `ComparisonResult` mit Winner-Location (`snow_depth_cm=120`, `sunny_hours=7`) und `profile=WINTERSPORT` / When `render_compare_html()` aufgerufen wird / Then enthält das zurückgegebene HTML einen Pill-Container mit mindestens einem good-Tag (`background:#dcf2e1`) und dem Label "Schneehöhe 120 cm" direkt nach dem Score-Badge in der Winner-Card.
  - Test: (populated after /tdd-red)

**AC-2:** Given ein `ComparisonResult` mit Winner-Location und `profile=WANDERN`, `temp_max=18`, `wind_max=45` / When `_generate_winner_tags()` aufgerufen wird / Then liefert die Funktion genau die Tupel `("good", "Temp. 18°C")` und `("warn", "Wind 45 km/h")`, good-Tags vor warn-Tags gelistet, und maximal 4 Tupel gesamt.
  - Test: (populated after /tdd-red)

**AC-3:** Given ein `ComparisonResult` bei dem 6 Tag-Bedingungen zutreffen / When `_generate_winner_tags()` aufgerufen wird / Then gibt die Funktion exakt 4 Tupel zurück (Kürzung nach Sortierung good > warn > info), kein fünfter Tag.
  - Test: (populated after /tdd-red)

**AC-4:** Given ein `ComparisonResult` mit `result.winner = None` / When `render_compare_html()` aufgerufen wird / Then enthält das HTML keinen Pill-Container (kein `display:flex`-div mit Tag-Farben) und wirft keine Exception.
  - Test: (populated after /tdd-red)

**AC-5:** Given `EmailOutput.send()` mit `to=["a@example.com", "b@example.com"]` und der SMTP-Server wirft beim ersten Empfänger eine `SMTPException` / When `send()` aufgerufen wird / Then wird der zweite Empfänger trotzdem per separatem `sendmail`-Call versucht, der Fehler des ersten Empfängers wird per `logger.error()` geloggt, und `send()` wirft keine Exception nach außen.
  - Test: (populated after /tdd-red)

## Known Limitations

- **Keine Regen- und Gewitter-Tags:** `precip_mm` und `thunder_level` existieren nicht auf `LocationResult` — diese Metriken können nicht als Tags gerendert werden, auch wenn sie fachlich sinnvoll wären. Erweiterung erfordert vorgelagerte Datenmodell-Änderung.
- **Fehlende Empfänger-Bestätigung:** Die Per-Empfänger-Logik loggt Fehler, gibt aber keine Rückmeldung an den Aufrufer welche Empfänger erfolgreich waren. Ein partieller Ausfall ist für den Aufrufer nicht unterscheidbar von einem vollständigen Erfolg.
- **Tag-Farben nicht aus design_tokens:** Die drei Tag-Tonfärbungen (good/warn/info) verwenden eigene Inline-Hex-Werte, die nicht in `design_tokens.py` verwaltet werden. Bei Design-System-Updates müssen die Farben in `compare_html.py` manuell nachgezogen werden.
- **above_low_clouds-Tag nur für WINTERSPORT:** Das `above_low_clouds`-Feld ist nur für das WINTERSPORT-Profil als Tag-Bedingung definiert. Für andere Profile ist es nicht relevant und wird ignoriert.

## Changelog

- 2026-05-30: Initial spec — Issue #457. Winner-Tag-Generator `_generate_winner_tags()` mit profilspezifischen Regeln (max 4 Tags, good > warn > info), Inline-CSS-Pill-Renderer, Per-Empfänger-Fehlerbehandlung in `EmailOutput.send()`. ~187 LoC, kein LoC-Override.
