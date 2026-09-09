---
entity_id: public_host
type: bugfix
created: 2026-09-09
updated: 2026-09-09
status: draft
version: "1.0"
workflow: fix-2272-python-public-host
tags: [config, staging, links]
---

# Öffentliche Basis-URL (public_host) für den Python-Core

## Approval

- [ ] Approved

## Purpose

Der Python-Core verlinkt in Briefing-Mails und Telegram-Antworten an sechs Stellen
in drei Dateien fest auf `https://gregor20.henemm.com`. Auf Staging zeigen diese
Links damit fälschlich auf die Produktion. Ein gemeinsam genutzter Konfigurationswert
löst die Verlinkung von der Produktionsadresse und macht sie umgebungsabhängig.

## Source

- **File:** `src/app/config.py`
- **Identifier:** `class Settings`, neue Funktionen `resolve_public_host`/`resolve_public_url`

> **Schicht-Hinweis:** Diese Spec betrifft ausschließlich den **Python-Core**
> (`api/`, `src/services/`, `src/app/`) — keine Go-/Frontend-Dateien. Die Go-Seite
> hat `GZ_PUBLIC_HOST` bereits über `internal/config/config.go:39` (Issue #2200/#2130,
> geliefert 09.09.2026); dieser Fix verdrahtet dieselbe Umgebungsvariable zusätzlich
> in den Python-Core.

## Estimated Scope

- **LoC:** ~+60/-10
- **Files:** 5 Code-Dateien (Python) + 1 Doku-Datei (`.env.example`) + 1 neue Testdatei
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `Settings` (`src/app/config.py`) | module | Trägt das neue Feld `public_host`, von praktisch allen Services konsumiert |
| `TripReportRequest.trip_url` (`src/services/notification_service.py:87`) | DTO-Feld | Bleibt `str \| None = None` — Fail-closed-Wert ist bereits eine gültige Eingabe (siehe Implementation Details) |
| `internal/config/config.go:39` (Go-API) | Referenz, keine Code-Abhängigkeit | Liest **dieselbe** Umgebungsvariable `GZ_PUBLIC_HOST` mit `envconfig.Process("GZ", ...)` — beide Prozesse teilen sich den Wert, aber jeder mit eigenem Default-Verhalten (siehe Known Limitations) |

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|--------------|
| `src/app/config.py` | MODIFY | Neues Feld `public_host: Optional[str] = Field(default=None, ...)` (kein Default) + Helper `resolve_public_host(settings) -> Optional[str]` und `resolve_public_url(settings, path: str) -> Optional[str]` |
| `src/services/trip_report_scheduler.py` | MODIFY | Zeile 1830: `trip_url=resolve_public_url(self._settings, f"/trips/{trip.id}")` statt Literal — Rückgabewert kann `None` sein, `TripReportRequest.trip_url` ist bereits `Optional[str]` |
| `src/services/trip_command_processor.py` | MODIFY | Zeile 1772 (`_show_columns_info`, volle Basis-URL ohne Pfad) und Zeile 1863 (`_show_config`, volle URL mit `/trips/{id}`) — Ad-hoc `Settings()`-Zugriff nach Muster `api/main.py:145`, Helper liefert `None` bei fehlendem Wert |
| `src/services/inbound_telegram_reader.py` | MODIFY | Zeilen 188, 208, 315 — Fließtext-Erwähnung des bloßen Hosts; `settings` liegt an allen drei Stellen bereits als Parameter/Attribut der aufrufenden Methode vor, kein Ad-hoc-Zugriff nötig |
| `api/routers/health.py` | MODIFY | `public_host` über denselben Helper (`resolve_public_host(Settings())`) in die JSON-Antwort aufnehmen |
| `.env.example` | MODIFY | Bestehenden Kommentarblock bei `GZ_PUBLIC_HOST` (Zeilen 25–33) um einen Satz ergänzen: dieselbe Variable wird jetzt auch vom Python-Core gelesen (`env_prefix="GZ_"`, `src/app/config.py:113`) — **keine zweite `GZ_PUBLIC_HOST`-Zeile**, das wäre ein Duplikat |
| `tests/test_public_host_links.py` (neu) | CREATE | Kern-Tests, deterministisch, ohne Netz — rendert die sechs Ausgabestellen und die Health-Antwort mit gesetztem und mit fehlendem `public_host` |

**Nicht Teil dieses Codes (`.env.tpl` bewusst NICHT geändert):** `.env.tpl` enthält
ausschließlich 1Password-`op://`-Referenzen für Secrets (7 Zeilen, nur SMTP-Werte).
`GZ_PUBLIC_HOST` ist kein Secret und folgt dort nicht dem bestehenden Muster — eine
Ergänzung würde eine Konvention einführen, die im restlichen `.env.tpl` nicht existiert.

**Nicht Teil dieser Spec (separater Ops-Schritt nach Deploy):** Die tatsächlichen Werte
in `/home/hem/gregor_zwanzig/.env` und `/home/hem/gregor_zwanzig_staging/.env` auf dem
Server eintragen — diese Dateien sind nicht versioniert, kein Code-Change, kein
PR-Bestandteil.

## Implementation Details

**Verworfene Ansätze (nicht erneut zur Diskussion, siehe `docs/context/fix-2272-python-public-host.md`):**
- Kein Fallback auf `https://gregor20.henemm.com` bei fehlendem Wert — das wäre
  derselbe Bug mit einer Log-Zeile.
- Kein Fail-Fast im Konstruktor/Field-Validator von `Settings` — 89 Testdateien
  instanziieren `Settings()` ohne `GZ_PUBLIC_HOST`, ein `raise` dort führt zu
  flächendeckendem Rot im Kern-Testlauf.

**Ansatz — Fail-closed an den Wirkstellen, ein gemeinsamer Helper:**

```
resolve_public_host(settings) -> Optional[str]
    value = settings.public_host
    return value.rstrip("/") if value else None
    # Normalisierung (Advisor-Review): ein trailing Slash in GZ_PUBLIC_HOST
    # wuerde sonst Doppel-Slashes in resolve_public_url erzeugen UND macht
    # die Mutation "Health liest GZ_PUBLIC_HOST unabhaengig selbst statt
    # ueber den Helper" (Known Limitations, Punkt 8) erst tatsaechlich
    # pruefbar: ein direkter os.environ.get()-Bypass in health.py liefert
    # den ROHEN Wert (mit Slash), der gemeinsame Helper den normalisierten —
    # AC-6 vergleicht beide und faellt bei einer solchen Abweichung durch.

resolve_public_url(settings, path: str) -> Optional[str]
    host = resolve_public_host(settings)
    return f"{host}{path}" if host else None
```

Drei Ausgabeformen aus derselben Quelle:
1. **Volle URL mit Pfad** (`resolve_public_url`): `trip_report_scheduler.py:1830`
   (`/trips/{trip.id}`), `trip_command_processor.py:1863` (`/trips/{trip.id}`).
2. **Volle Basis-URL ohne Pfad** (`resolve_public_url(settings, "")` bzw.
   `resolve_public_host(settings)` direkt, je nach Formulierung):
   `trip_command_processor.py:1772` — der bestehende Text ist bereits eine URL mit
   Schema (`https://gregor20.henemm.com`), keine bloße Host-Erwähnung.
3. **Bloßer Host in Fließtext** (`resolve_public_host` + `urlsplit(...).netloc`,
   falls der Wert ein Schema enthält): `inbound_telegram_reader.py:188,208,315` —
   Muster `"...im Account-Bereich auf {host})."`.

Fehlt `public_host` (Helper liefert `None`), entfällt an jeder der sechs Stellen
**genau der Host-/Link-Anteil**, der Rest des Satzes bleibt stehen (Details je
Stelle: siehe Acceptance Criteria AC-1 bis AC-6). Kein Platzhalter-Text, kein
Produktions-String.

`TripReportRequest.trip_url` (`src/services/notification_service.py:87`) ist
bereits `str | None = None` deklariert; der HTML-Renderer prüft bereits
`if trip_url:` (`src/output/renderers/email/html.py:555`) und lässt den
Deep-Link-Block bei `None` vollständig weg — hier ist **kein** Renderer-Code
zu ändern, nur die Werterzeugung an `trip_report_scheduler.py:1830`.

`api/routers/health.py` ruft **denselben** `resolve_public_host(Settings())`
auf wie die Render-Stellen — keine zweite, unabhängige Ableitung (sonst prüft
das Health-Feld nur sich selbst, nicht die tatsächlich wirksame Config an den
Versandstellen).

## Expected Behavior

- **Input:** Umgebungsvariable `GZ_PUBLIC_HOST` (gesetzt oder fehlend), gelesen
  über `Settings(env_prefix="GZ_")` als `settings.public_host`.
- **Output:** Sechs Text-/Link-Ausgabestellen (2× Mail-Body via `trip_url`,
  4× Telegram-`confirmation_body`/Nachrichtentext) sowie `GET /health` liefern
  bei gesetztem Wert konsistent denselben Host; bei fehlendem Wert entfällt an
  allen sechs Stellen der Host-/Link-Anteil, niemals erscheint
  `gregor20.henemm.com` als eingebrannter Literal.
- **Side effects:** Keine. Reine Text-/Konfigurationsänderung, kein
  Datenmodell, keine Persistenz, kein Auth-Pfad.

## Test Plan

**Schicht:** Kern (deterministisch, ohne Netz/Live-Dienste) — keine Live-E2E-Marker nötig, alle sechs Ausgabestellen und der Health-Endpoint sind rein lokal renderbar.

**Testdatei:** `tests/test_public_host_links.py` (neu, Name nach Verhalten)

**12 Testfälle, gruppiert nach den sechs Wirkstellen + Health:**

| # | Codepfad | Fall | Erwartung |
|---|---|---|---|
| 1 | `trip_report_scheduler.py:1830` | `GZ_PUBLIC_HOST` gesetzt | Mail-Body enthält Staging-Host-URL, nicht `gregor20.henemm.com` (AC-1) |
| 2 | `trip_report_scheduler.py:1830` | `GZ_PUBLIC_HOST` fehlt | `trip_url` ist `None`, Deep-Link-Block entfällt im HTML (AC-5) |
| 3 | `trip_command_processor.py:1863` (`_show_config`) | gesetzt | `confirmation_body` enthält vollständige Staging-URL (AC-2) |
| 4 | `trip_command_processor.py:1863` | fehlt | Link-Zeile entfällt exakt wie spezifiziert, keine Leerzeile-Doppelung (AC-5) |
| 5 | `trip_command_processor.py:1772` (`_show_columns_info`) | gesetzt | `confirmation_body`-Zeile enthält Staging-Basis-URL (AC-3) |
| 6 | `trip_command_processor.py:1772` | fehlt | Text endet auf Punkt statt Doppelpunkt+URL-Zeile (AC-5) |
| 7 | `inbound_telegram_reader.py:188` | gesetzt | Nachrichtentext enthält bloßen Staging-Host (AC-4) |
| 8 | `inbound_telegram_reader.py:188` | fehlt | Klammerzusatz entfällt, Klammer bleibt geschlossen (AC-5) |
| 9 | `inbound_telegram_reader.py:208` | gesetzt | Fehlermeldung enthält bloßen Staging-Host (AC-4) |
| 10 | `inbound_telegram_reader.py:208` | fehlt | Adressteil entfällt (AC-5) |
| 11 | `inbound_telegram_reader.py:315` | gesetzt/fehlt | wie 188 (gleicher Nachrichtenbaustein) (AC-4/AC-5) |
| 12 | `GET /health` | gesetzt vs. fehlend, plus Quervergleich mit Fall 1 | `public_host` im JSON identisch zum Mail-Body-Host (gesetzt, AC-6) bzw. `null` (fehlend, AC-7) |

**Mutations-Gegenprobe (verweist auf Known Limitations, Punkt „Mutations-Erwartung"):** Jede der acht dort gelisteten Verfälschungen muss mindestens einen der obigen 12 Testfälle rot machen — insbesondere Fall 12 fängt eine Health-Ableitung, die nicht denselben Helper wie Fall 1 nutzt.

## Acceptance Criteria

- **AC-1:** Given `GZ_PUBLIC_HOST=https://staging.gregor20.henemm.com` ist gesetzt, When ein Trip-Report für einen Trip mit `id="abc"` über `trip_report_scheduler.py` gebaut wird, Then enthält `TripReportRequest.trip_url` exakt `"https://staging.gregor20.henemm.com/trips/abc"` und der gerenderte Mail-Body (HTML) enthält den Deep-Link mit diesem Host, nicht mit `gregor20.henemm.com`.
  - Test: `trip_report_scheduler`-Aufruf mit gesetzter `GZ_PUBLIC_HOST` und Prüfung des gerenderten HTML-Bodys auf den Staging-Host; zusätzlich Prüfung, dass der String `gregor20.henemm.com` NICHT im Body vorkommt.

- **AC-2:** Given `GZ_PUBLIC_HOST=https://staging.gregor20.henemm.com` ist gesetzt, When `TripCommandProcessor()._show_config(trip)` für einen Trip mit `id="abc"` aufgerufen wird, Then enthält `confirmation_body` exakt `"https://staging.gregor20.henemm.com/trips/abc"` als Link und nicht `gregor20.henemm.com`.
  - Test: Direkter Aufruf von `_show_config` mit gepatchter `Settings()`-Quelle (Env-Var gesetzt), Assertion auf den vollständigen `confirmation_body`-Text.

- **AC-3:** Given `GZ_PUBLIC_HOST=https://staging.gregor20.henemm.com` ist gesetzt, When `TripCommandProcessor()._show_columns_info()` aufgerufen wird, Then enthält `confirmation_body` die Zeile `"https://staging.gregor20.henemm.com"` (volle Basis-URL, kein Pfad-Suffix) statt `"https://gregor20.henemm.com"`.
  - Test: Direkter Aufruf von `_show_columns_info` mit gesetzter Env-Var, Assertion auf den vollständigen `confirmation_body`-Text inklusive der einleitenden Zeile `"Spalten-Konfiguration ist nur im Trip-Editor möglich:"`.

- **AC-4:** Given `GZ_PUBLIC_HOST=https://staging.gregor20.henemm.com` ist gesetzt, When `InboundTelegramReader` für einen unregistrierten Chat (`user_id == "default"`) die Registrierungs-Nachricht baut (Zeile 188) UND bei fehlendem aktivem Trip die Fehlermeldung baut (Zeile 208) UND bei einem Callback-Query für einen unregistrierten Chat die Nachricht bearbeitet (Zeile 315), Then enthält der jeweilige Nachrichtentext an allen drei Stellen `"staging.gregor20.henemm.com"` als bloßen Host (ohne Schema, im bestehenden Fließtext-Muster) und nicht `"gregor20.henemm.com"`.
  - Test: Drei einzelne Testfälle, je einer pro Codepfad (188/208/315), mit gesetzter Env-Var und Assertion auf den vollständigen versendeten/editierten Nachrichtentext.

- **AC-5:** Given `GZ_PUBLIC_HOST` ist NICHT gesetzt, When alle sechs Ausgabestellen aus AC-1 bis AC-4 durchlaufen werden, Then erscheint an keiner der sechs Stellen `"gregor20.henemm.com"` in irgendeiner Form (weder als volle URL noch als bloßer Host) UND der jeweils verbleibende Satzrest ist exakt der spezifizierte Degradations-Text:
  - `trip_report_scheduler.py:1830`: `TripReportRequest.trip_url` ist `None`, der HTML-Renderer lässt den Deep-Link-Block vollständig weg (bereits existierendes Verhalten von `if trip_url:` in `src/output/renderers/email/html.py:555`, keine Änderung dort nötig).
  - `trip_command_processor.py:1863` (`_show_config`): `confirmation_body` lautet `"Einstellungen für '{trip.name}':\n\nDort kannst du Zeitplan, Kanäle und Alarm-Schwellen anpassen."` — die Link-Zeile entfällt vollständig, keine Leerzeile-Doppelung.
  - `trip_command_processor.py:1772` (`_show_columns_info`): `confirmation_body` lautet nur noch `"Spalten-Konfiguration ist nur im Trip-Editor möglich."` — Doppelpunkt wird zu Punkt, die URL-Zeile entfällt.
  - `inbound_telegram_reader.py:188`: Text lautet `"...Sende /start gefolgt von deinem Token (zu finden im Account-Bereich)."` — der Klammerzusatz `"auf gregor20.henemm.com"` entfällt, die Klammer bleibt sinnvoll geschlossen.
  - `inbound_telegram_reader.py:208`: Text lautet `"Kein aktiver Trip gefunden. Erstelle oder aktiviere einen Trip."` — der Adressteil `" auf gregor20.henemm.com"` entfällt.
  - `inbound_telegram_reader.py:315`: identischer Text wie 188 (gleicher Nachrichtenbaustein).
  - Test: Sechs Testfälle (einer je Stelle) mit `monkeypatch.delenv("GZ_PUBLIC_HOST", raising=False)`, Assertion auf den exakten Ausgabetext.

- **AC-6:** Given `GZ_PUBLIC_HOST=https://staging.gregor20.henemm.com/` ist gesetzt (bewusst MIT trailing Slash), When `GET /health` aufgerufen wird, Then enthält die JSON-Antwort das Feld `"public_host": "https://staging.gregor20.henemm.com"` (normalisiert, OHNE Slash) — identisch mit dem Host, der in AC-1 im gerenderten Mail-Body erscheint (derselbe Helper-Aufruf inkl. Normalisierung, geprüft durch Vergleich der beiden Werte im selben Testlauf statt zweier unabhängiger Literale).
  - Test: Ein Testfall setzt `GZ_PUBLIC_HOST` MIT trailing Slash, ruft sowohl `GET /health` als auch den `trip_report_scheduler`-Aufruf aus AC-1 auf und vergleicht `health_response["public_host"]` mit dem im Mail-Body gefundenen (normalisierten) Host per Gleichheits-Assertion. Ein Health-Endpoint, der `GZ_PUBLIC_HOST` unabhängig vom Helper liest (Mutation 8), liefert den ROHEN Wert mit Slash und fällt durch.

- **AC-7:** Given `GZ_PUBLIC_HOST` ist NICHT gesetzt, When `GET /health` aufgerufen wird, Then enthält die JSON-Antwort `"public_host": null` (kein Fallback auf `gregor20.henemm.com`, kein fehlendes Feld).
  - Test: `monkeypatch.delenv`, Aufruf von `GET /health`, Assertion auf `public_host is None` im JSON.

## Known Limitations

- **Geteilte Variable, unterschiedliches Fail-Verhalten:** Go (`internal/config/config.go:39`) behält seinen Default `https://gregor20.henemm.com` — fehlt `GZ_PUBLIC_HOST`, liefert Go weiterhin (stillschweigend) die Produktionsadresse, während der Python-Core (dieser Fix) den Link-/Host-Anteil komplett weglässt. Zwei unterschiedliche Reaktionen auf denselben fehlenden Wert sind eine bewusste, im Advisor-Review bestätigte Asymmetrie dieses Fixes und werden hier NICHT vereinheitlicht (Go-seitige Änderung wäre ein eigenes Ticket).
- **`.env`-Ladeweg unterscheidet sich zwischen Go und Python:** Die Go-Systemd-Units (`gregor-api.service`, `gregor-api-staging.service`) laden `GZ_PUBLIC_HOST` über inline `Environment=` in der versionierten Unit-Datei. `gregor-python.service`/`gregor-python-staging.service` laden dagegen über `EnvironmentFile=/home/hem/gregor_zwanzig[_staging]/.env` (nicht versioniert). Ein Eintrag in der einen Quelle bewirkt NICHT automatisch den anderen Prozess — beide `.env`-Dateien müssen als separater Ops-Schritt gepflegt werden (siehe Scope, „Nicht Teil dieser Spec").
- **Mutations-Erwartung (für den Adversary, `implementation-validator`):** Folgende Verfälschungen MÜSSEN je mindestens einen Test rot machen:
  1–6. Revert einer einzelnen der sechs Aufrufstellen (AC-1 bis AC-5) auf den `gregor20.henemm.com`-Literal.
  7. Wiedereinführen eines Fallbacks auf `https://gregor20.henemm.com` in `resolve_public_host`/`resolve_public_url` bei fehlendem Wert.
  8. Eine einzelne Stelle (insbesondere `api/routers/health.py`) leitet den Host **unabhängig** vom gemeinsamen Helper ab (z. B. eigener `os.environ.get("GZ_PUBLIC_HOST")`-Zugriff) — muss durch AC-6 (Wertevergleich zwischen Health-Antwort und tatsächlich gerendertem Mail-Body im selben Testlauf, nicht zwei unabhängige Literale) rot werden.
- **Spec-Entscheidung: `INTENTIONAL_CONSTANT_SUCCESS`-Ratsche für `_show_columns_info`/`_show_config` geöffnet (nachträglich, während `/70-deploy` durch CI-Rot entdeckt).** `tests/test_success_status_guard.py` (Issue #1405) flaggt eine Funktion als Klasse-1-Fund, sobald sie vor dem `return` einen echten Aufruf tätigt UND danach unbedingt `CommandResult(success=True, ...)` behauptet. Vor #2272 hatten beide Methoden GAR KEINEN Aufruf vor dem `return` (strukturell exempt, wie `api/routers/health.py`); `resolve_public_host`/`resolve_public_url` macht sie jetzt zu echten Klasse-1-Kandidaten. Bewertung: **kein Bug** — beide Methoden sind rein informative, schreibfreie Antworten ohne Fehlerpfad; `None` als Rückgabe (GZ_PUBLIC_HOST nicht konfiguriert, fail-closed) ändert ausschließlich den Text, nie ob der Befehl erfolgreich verarbeitet wurde. Eine echte Störung bei `Settings()` würde eine Exception werfen, nie bis zum `return` durchreichen. Zwei Einträge in `INTENTIONAL_CONSTANT_SUCCESS` und in der fest verdrahteten `_APPROVED_EXCEPTIONS`-Menge (Zuwachs dort ist laut Kommentar dort ausdrücklich eine Spec-Entscheidung — hiermit getroffen), mit dem exakten, wortlautgesperrten Begründungstext:
  > „Rein informative Antwort ohne Fehlerpfad, kein fachlicher Erfolgsstatus — resolve_public_host/resolve_public_url liefert None nur bei nicht konfiguriertem GZ_PUBLIC_HOST (fail-closed) und ändert damit allein den Text, nie ob das Kommando verarbeitet wurde (dokumentiert im Docstring)"

  Betroffene Fundorte: `src/services/trip_command_processor.py::_show_columns_info::0` und `::_show_config::0`. Analog zur bestehenden `_WEBHOOK_ACK`-Ausnahme (gleiche Datei, Zeile ~272) — Wortlaut-Sperre nach demselben Muster (`test_webhook_ack_is_documented_exception_not_silent_pass`, Zeile ~3246) ergänzen, damit der Text nicht unbemerkt driftet.

- **Ad-hoc-`Settings()` in `trip_command_processor.py` ist bewusst, kein Fix-Bedarf:** Die beiden zustandslosen Methoden (`_show_config`, `_show_columns_info`) instanziieren `Settings()` frisch statt einen nutzerbezogenen `settings`-Parameter durchzureichen. `public_host` ist ein Umgebungswert (ein Wert pro Prozess/Environment), kein nutzerbezogener Wert — die frische Instanziierung liest bei jedem Aufruf dieselbe `.env`, das ist korrekt und beabsichtigt. **Kein** Umbau zu einem durchgereichten Settings-Objekt an diesen vier Aufrufstellen (Advisor-Review).
- **Ops-Reihenfolge außerhalb dieses Codes:** `GZ_PUBLIC_HOST` muss vor dem Prod-Deploy dieses Fixes in `/home/hem/gregor_zwanzig/.env` (`https://gregor20.henemm.com`) und in `/home/hem/gregor_zwanzig_staging/.env` (`https://staging.gregor20.henemm.com`) eingetragen werden — sonst verschwinden die Produktions-Links vollständig (Fail-closed greift dort identisch). Kein Code-/PR-Bestandteil, siehe Scope.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reine Konfigurations- und Text-Renderingänderung ohne neues
  Entscheidungsfeld (kein Kanal, kein Provider, kein Datenmodell, kein
  Auth-Paradigma) — fällt nicht unter die in `docs/adr/README.md` gelisteten
  ADR-pflichtigen Kategorien.

## Changelog

- 2026-09-09: Initial spec created
