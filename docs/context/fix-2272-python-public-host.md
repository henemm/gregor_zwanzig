# Context: fix-2272-python-public-host

## Request Summary
Der Python-Core verlinkt in Briefing-Mails und Telegram-Antworten fest auf
`https://gregor20.henemm.com` (6 Fundstellen, 3 Dateien) — auf Staging zeigen
Briefing-Links damit fälschlich auf die Produktion. Ein `GZ_PUBLIC_HOST`-
Konfigurationswert (analog Go-Seite, #2200/#2130) soll eingeführt und alle
sechs Stellen darauf umgestellt werden — inklusive der beiden Produktions-
und Staging-Units.

## Related Files

| Datei | Zeile(n) | Relevanz |
|---|---|---|
| `src/app/config.py` | `Settings`-Klasse ab Zeile 100 | Neues Feld `public_host` einführen, `GZ_`-Präfix greift automatisch |
| `src/services/trip_report_scheduler.py` | 1830 | `trip_url=f"https://gregor20.henemm.com/trips/{trip.id}"` — Klasse hält `self._settings` (Konstruktor, Zeile 418), also direkt verfügbar |
| `src/services/trip_command_processor.py` | 1772 (`_show_columns_info`), 1863 (`_show_config`) | Zwei Literale — Klasse ist **zustandslos**, wird überall als `TripCommandProcessor().process(msg)` instanziiert (4 Aufrufer: `inbound_email_reader.py:181`, `inbound_telegram_reader.py:249/278/335`, `inbound_sms_reader.py:260`), hält kein `settings`-Feld |
| `src/services/inbound_telegram_reader.py` | 188, 208, 315 | Fließtext-Erwähnungen (`"...auf gregor20.henemm.com)."`, `"...auf gregor20.henemm.com"`) — Konstruktor nimmt keine Settings entgegen, `settings` kommt erst als Parameter von `poll_and_process(settings)` |
| `api/routers/health.py` | ganze Datei (9 Zeilen) | Aktueller Health-Endpoint liefert nur `{"status": "ok", "version": ...}` — Kandidat, um den wirksamen `public_host` von außen messbar zu machen (Lehre aus #2200: „wirksame Config von außen über `/api/health` messen") |
| `internal/config/config.go:39` | `PublicHost string \`envconfig:"PUBLIC_HOST" default:"https://gregor20.henemm.com"\`` | Go-Referenz — **Default ist selbst die Produktionsadresse**, exakt die Falle, vor der das Issue warnt. Python-Seite darf diesen Default NICHT kopieren |
| `henemm-infra/systemd/gregor-python.service` | `EnvironmentFile=/home/hem/gregor_zwanzig/.env` | Prod-Unit lädt Config **nicht** über inline `Environment=` (anders als die Go-Units!), sondern über eine externe `.env`-Datei |
| `henemm-infra/systemd/gregor-python-staging.service` | `EnvironmentFile=/home/hem/gregor_zwanzig_staging/.env` | Staging-Unit, gleiches Muster |
| `/home/hem/gregor_zwanzig/.env` (Server, nicht versioniert) | — | Enthält aktuell **keinen** `GZ_PUBLIC_HOST`-Eintrag (geprüft: `grep -c GZ_` findet 44 andere Variablen) |
| `/home/hem/gregor_zwanzig_staging/.env` (Server, nicht versioniert) | — | Ebenfalls kein `GZ_PUBLIC_HOST`-Eintrag |

## Existing Patterns

- **Settings-Feld mit `GZ_`-Präfix:** `src/app/config.py` — `pydantic_settings.BaseSettings` mit `env_prefix="GZ_"`. Neues Feld folgt dem Muster von z.B. `mail_server_hostname` (Zeile 219–222): `Field(default=..., description="... (env: GZ_...)")`.
- **Ad-hoc-Settings-Zugriff ohne Konstruktor-State:** `api/main.py:145` (`Settings().core_shared_secret`) und `dispatch_orchestrator.py:228`/`scheduler_dispatch_service.py:647` (`Settings().with_user_profile(user_id)`) — zeigen, wie zustandslose Stellen (wie `TripCommandProcessor`, `InboundTelegramReader`-Konstruktor) an einen Config-Wert kommen, ohne dass er als Parameter durchgereicht wird.
- **Zwei Render-Formen nötig:** `trip_report_scheduler.py`/`trip_command_processor.py:1863` bauen eine **volle URL** (`{public_host}/trips/{id}`), `trip_command_processor.py:1772` und die drei `inbound_telegram_reader.py`-Stellen sind **Fließtext mit bloßem Host** (`"...auf gregor20.henemm.com"` ohne Schema). Eine Konfigurationsquelle, zwei Ausgabeformen.
- **Go-Ableitungsmuster (`internal/config/webauthn.go`):** liest `PublicHost`, leitet daraus Host-Anteil ab (`deriveFromPublicHost`) — zeigt, wie man aus einer vollen URL den bloßen Host für Fließtext gewinnt (URL parsen, Host-Komponente).
- **Health-Endpoint als Messpunkt:** Go-Seite exponiert `PublicHost` bisher **nicht** über `/api/health` (geprüft, kein Treffer in `internal/router/health*.go` außerhalb Tests) — d.h. kein Vorbild zu kopieren, sondern für Python-Core neu zu entscheiden.

## Dependencies

- **Upstream:** `Settings`-Klasse wird von praktisch allen Services genutzt (Provider, Renderer, Scheduler) — ein neues Feld mit sinnvollem Default ist risikoarm, solange bestehende Tests, die `Settings()` ohne `GZ_PUBLIC_HOST` instanziieren, nicht auf einen zufälligen Produktions-Default treffen (siehe Risiko unten).
- **Downstream:** Sechs Aufrufstellen in drei Dateien binden die Konfiguration an gerenderten Text (Mail-Body via `TripReportRequest.trip_url`, Telegram-`confirmation_body`).

## Existing Specs
- Keine dedizierte Spec zu `public_host`/Link-Konfiguration im Python-Core gefunden (`docs/specs/`). Verwandtes ADR: keines — reine Konfigurationsergänzung, kein Entscheidungsfeld im Sinne der ADR-Liste.

## Risks & Considerations

- **Default-Falle (zentrale Warnung des Issues):** Ein Default, der zufällig `https://gregor20.henemm.com` ist, macht einen fehlenden `.env`-Eintrag unsichtbar — exakt der Fehler, den #2200 auf der Go-Seite fixte. Der Default muss so gewählt sein, dass ein fehlender Wert **auffällt** (z.B. Fallback auf den fest verdrahteten String bleibt für Prod-Robustheit denkbar, aber dann muss ein anderer Mechanismus — z.B. Health-Feld oder Log-Warnung — die fehlende Staging-Konfiguration sichtbar machen; Spec-Entscheidung).
- **Produktion nicht vergessen:** Da `gregor-python.service` denselben `EnvironmentFile`-Mechanismus nutzt wie Staging, muss `GZ_PUBLIC_HOST=https://gregor20.henemm.com` **auch** in `/home/hem/gregor_zwanzig/.env` eingetragen werden — sonst regressiert die Produktion, sobald der Default nicht mehr automatisch die Prod-Adresse ist.
- **`.env`-Dateien sind nicht versioniert** — anders als bei der Go-Seite (inline `Environment=` in der versionierten Unit) ist der Eintrag hier ein **manueller Server-Eingriff** in zwei Dateien außerhalb jedes Git-Repos. Das muss in der Spec als Deployment-Schritt festgehalten werden, nicht nur als Code-Änderung.
- **Zwei Aufrufer-Klassen ohne Settings-Zugriff:** `TripCommandProcessor` (zustandslos, 4 Aufrufer) und `InboundTelegramReader.__init__` (Settings kommt erst zur Laufzeit über `poll_and_process(settings)`, nicht im Konstruktor) — beide brauchen einen Weg an den Wert zu kommen, ohne die bestehenden Aufrufer-Signaturen unnötig zu verändern (Ad-hoc-`Settings()`-Zugriff wie bei `core_shared_secret` ist das etablierte Muster).
- **Messbarkeit an der Wirkstelle (Lehre aus #2130/#2200):** Ein Test, der nur das Settings-Feld prüft, deckt die eigentliche Textausgabe nicht ab — sechs Stellen brauchen sechs eigene Bewachungen (gerenderte Mail, gerenderter Telegram-Text), sonst „Naht gebaut ≠ Naht verdrahtet".
- **Nebenbefund aus dem Issue (nicht Teil dieses Fixes):** Auth-Mails auf Staging generell nicht zustellbar (Egress-Wächter #1337) — bereits in #1199 notiert, hier nicht erneut aufgreifen.

## Betroffene Nutzer/Datenpfade
Kein datenbewegender Endpoint, keine Multi-User-Persistenzänderung — reine Konfigurations- und Text-Renderingänderung. Der Multi-User-Test-Zwang (zwei Nutzer) aus CLAUDE.md gilt hier nicht.

## Analysis

### Type
Bug (nutzersichtbares Fehlverhalten: Staging-Briefing-Links zeigen auf Produktion).
Fan-out-Agenten entfallen — die Ermittlung in `/10-context` hat bereits alle
sechs Fundstellen, beide betroffenen Klassen-Konstruktoren und die
Systemd-/`.env`-Lage stellenscharf geklärt; ein zweiter Rundgang würde nur
wiederholen.

### Affected Files (with changes)

| File | Change Type | Description |
|---|---|---|
| `src/app/config.py` | MODIFY | Neues Feld `public_host: Optional[str]` (kein Produktions-Default — Default-Falle aus #2200 vermeiden) |
| `src/services/trip_report_scheduler.py` | MODIFY | Zeile 1830: `trip_url` aus `self._settings.public_host` statt Literal bauen |
| `src/services/trip_command_processor.py` | MODIFY | Zeile 1772 (Fließtext-Host) und 1863 (volle URL) — Ad-hoc-`Settings()`-Zugriff, da Klasse zustandslos |
| `src/services/inbound_telegram_reader.py` | MODIFY | Zeilen 188, 208, 315 — Fließtext-Host, Konstruktor hält keine Settings, Ad-hoc-Zugriff oder Ableitung aus dem bereits vorhandenen `settings`-Parameter der jeweiligen Methode |
| `api/routers/health.py` | MODIFY (optional, Spec-Entscheidung) | `public_host` in Health-Antwort aufnehmen, damit die wirksame Config von außen messbar ist (Lehre #2200) |
| `tests/...` (neue/erweiterte Testdatei, Name nach Verhalten) | CREATE/MODIFY | Rendert Mail-Body/Telegram-Text/Health-Antwort mit gesetztem `GZ_PUBLIC_HOST` und prüft: (a) Staging-Host erscheint, (b) `gregor20.henemm.com` als bloßes Literal erscheint NICHT; zusätzlich: Wert **fehlt** ⇒ kein Link/Host-Fließtext an der jeweiligen Stelle — je Aufrufstelle einzeln, sonst bleiben Stellen ungedeckt |
| `.env.example`, `.env.tpl` | MODIFY | `GZ_PUBLIC_HOST` nach dem Muster von `GZ_CORE_SHARED_SECRET` ergänzen (versioniert, Teil des Commits) |
| `/home/hem/gregor_zwanzig/.env` (Server, außerhalb Git) | OPS | `GZ_PUBLIC_HOST=https://gregor20.henemm.com` ergänzen — **vor** dem Prod-Deploy dieses Fixes, sonst verschwinden Produktions-Links (Fail-closed) |
| `/home/hem/gregor_zwanzig_staging/.env` (Server, außerhalb Git) | OPS | `GZ_PUBLIC_HOST=https://staging.gregor20.henemm.com` ergänzen |

### Scope Assessment
- Dateien (Code): 5 (`config.py` + 3 Service-Dateien + `health.py`)
- Dateien (Test): 1 neue oder erweiterte Testdatei
- Geschätztes LoC-Delta: ~+60/-10 (unter dem 250-LoC-Limit, `docs/`/Ops-Dateien zählen nicht mit)
- Risk Level: **LOW** — reine Text-/Config-Änderung, kein Datenmodell, kein Auth-Pfad, kein Breaking Change an DTOs

### Technical Approach

**Korrektur nach Advisor-Gegenprobe:** Ein Fallback auf den Produktions-String
bei fehlendem `GZ_PUBLIC_HOST` (ursprünglich geplant, mit `logger.warning`)
ist **funktional derselbe Fehler**, den das Issue beschreibt — nur mit einer
Log-Zeile, die niemand liest. Fehlender Wert ⇒ Produktions-Link auf Staging,
exakt der gemeldete Bug. Verworfen.

Ebenfalls verworfen: harter Fail-Fast in `Settings.__init__`/Field-Validator
(Vorbild `_resend_default_deny`). Geprüft: **89 Testdateien** instanziieren
`Settings()` ohne `GZ_PUBLIC_HOST` — ein Raise dort würde den Kern-Testlauf
flächendeckend rot fahren. Die Durchsetzung gehört an die Wirkstellen, nicht
in den Konstruktor.

1. `Settings.public_host: Optional[str] = Field(default=None, description="Öffentliche Basis-URL für Nutzer-Links (env: GZ_PUBLIC_HOST, #2272) — kein Default, fehlender Wert ist ein Konfigurationsfehler")`.
2. **Ein gemeinsamer Helper** (z.B. `resolve_public_host(settings) -> Optional[str]` und `resolve_public_url(settings, path) -> Optional[str]` in `config.py`), den **alle** sechs Aufrufstellen UND `api/routers/health.py` benutzen — keine zweite Ableitung, sonst "Prüfwerkzeug auf beiden Seiten prüft nichts". Fehlt der Wert: Helper liefert `None`.
3. **Fail-closed an den Render-Stellen:** liefert der Helper `None`, wird **kein** Link/Host-Fließtext ausgegeben (Zeile/Satzteil entfällt oder durch neutralen Hinweis ersetzt) — eine fehlende Angabe ist sichtbar kaputt, eine falsche Angabe (Prod-Link auf Staging) ist unsichtbar kaputt. Bewusste Abkehr vom Go-Muster (das degradiert bei fehlendem Wert nur die Passkey-Ableitung, nicht auf sichtbare Nutzer-Ausgabe).
4. Zwei Ausgabeformen aus demselben Helper-Ergebnis: volle URL (`f"{public_host}/trips/{trip.id}"`) für 2 Stellen, bloßer Host (URL-Host-Anteil, z.B. via `urlsplit(...).netloc`) für 4 Fließtext-Stellen.
5. `trip_report_scheduler.py`: `self._settings` ist vorhanden, Helper direkt aufrufbar.
6. `trip_command_processor.py` und `inbound_telegram_reader.py`: Ad-hoc `Settings()`-Zugriff nach dem `core_shared_secret`-Muster (`api/main.py:145`) — kein Umbau der bestehenden zustandslosen Aufrufer-Signaturen.
7. `api/routers/health.py`: `public_host` über **denselben Helper** in die Antwort aufnehmen — macht die Staging-Validierung nach Deploy von außen messbar, ohne eine zweite Wahrheit zu schaffen.
8. **`.env.example` und `.env.tpl` sind versioniert** (`git ls-files` bestätigt) — `GZ_PUBLIC_HOST` dort nach dem Muster von `GZ_CORE_SHARED_SECRET` (Zeile 17 in `.env.example`) ergänzen. Das ist der einzige Commit-Teil der Config-Änderung; die eigentlichen Werte bleiben Server-Ops.
9. Ops-Schritt (kein Commit, kein PR, außerhalb jedes Repos): beide `.env`-Dateien auf dem Server direkt editieren. Reihenfolge: Staging-`.env` zuerst (Nachweis vor Prod), **Prod-`.env` zwingend vor dem Prod-Deploy dieses Fixes** — sonst verschwinden Produktions-Links komplett (Fail-closed greift dort genauso).

### Dependencies
- Kein Fremdmodul, keine neue Bibliothek.
- `TripReportRequest.trip_url` (DTO-Feld) bleibt unverändert in Form, nur die Quelle des Werts ändert sich — keine Signaturänderung nach außen.
- Downstream: E-Mail-Renderer und Telegram-Renderer konsumieren `trip_url`/`confirmation_body` unverändert (kein Renderer-Code betroffen, nur die Werterzeugung).

### Open Questions
- [x] Default-Strategie geklärt (nach Advisor-Korrektur): **kein** Fallback auf die Produktionsadresse, **kein** Fail-Fast im Konstruktor (89 Tests betroffen) — Fail-closed an den sechs Render-Stellen und im Health-Endpoint, über einen einzigen gemeinsamen Helper. Keine weitere Rückfrage nötig.
- [x] Health-Feld `public_host` aufnehmen — ja, aber zwingend über denselben Helper wie die Render-Stellen (keine zweite Ableitung).
- [x] `.env.example`/`.env.tpl` sind versioniert und werden mitgeliefert — kein offener Punkt mehr.
