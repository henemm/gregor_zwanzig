# Context: deliver-2860-alarm-ab-migration

## Request Summary
Serverseitige Auslieferung von #2793 S2 (Epic #2791): Migration der Alt-Alarmstufen nach `ampel.metrics.<id>.alarm_ab` auf Staging und Prod, danach S2b (Alarme lesen `alarm_ab`) mergen, auf Staging verifizieren, nach Prod deployen. Kein neuer Code in diesem Workflow; Code bauen Cloud-Sitzungen (S2a = PR #2857, gemergt 2026-11-08, Merge-Commit `4df182f`; S2b folgt vom Branch `claude/vigilant-babbage-ebij4r`).

## Freigegebene Spec
- `docs/specs/modules/feat_2793_s2_alarm_stufenwechsel.md` v1.1, `status: approved` (PO-Freigabe 2026-11-08). Kein neuer Spec-Text nötig, dieser Workflow liefert sie aus.
- Kontext der Cloud-Sitzung: `docs/context/feat-2793-s2-alarm-stufenwechsel.md`.

## Related Files
| File | Relevance |
|------|-----------|
| `scripts/migrate_2793_alarm_ab.py` | Migrationsskript (Probelauf ohne Flag, `--execute`, `--root`, `--backup-dir`, Default `<root>/../.backups`); Exit 0 = ok, 1 = Dateien offen/gesperrt, 2 = ungültige Ampel + Altstufen |
| `/var/lib/gregor-staging/users` | Staging-Nutzerdaten (Migrationsziel 1) |
| `/var/lib/gregor/users` | Prod-Nutzerdaten (Migrationsziel 2), Zugriff per `sudo -n -u claude-gregor` |
| `api/routers/validator.py` | Render-Route zum Auslösen echter Abweichungs-Alarme auf Staging |
| `.claude/hooks/briefing_mail_validator.py`, `email_spec_validator.py`, `radar_alert_mail_validator.py`, `official_alert_mail_validator.py` | Regressionsnachweis der Mailpfade (geteilter Alarm-Renderer), je `de`/`en` |
| `deploy-gregor-prod.sh`, `prod_selftest.py` | Prod-Deploy + Selftest (Hard Gate) |

## Verbindliche Reihenfolge (aus #2860)
1. S2a gemergt ✅ (Kommentar 2026-11-08 15:18).
2. Migration Staging: Probelauf → Bericht lesen → `--execute` → Kontroll-Lauf (Pflicht: Exit 0 + „Nichts zu tun“).
3. Migration Prod: dieselben drei Läufe mit `--root /var/lib/gregor/users`. Tabelle je Umgebung als Kommentar in #2793 (Vorbild S1b-Kommentar in #2792).
4. Unmittelbar vor S2b-Merge Prod-Kontroll-Lauf erneut (Gate laut Spec). S2b-PR mit 6 grünen Checks mergen → Staging-Poll → `/e2e-verify` DE+EN (Abweichungs-Alarme Trip + Ortsvergleich, Token-Suffix `:Y>O`, <160 Zeichen, Briefing-Validatoren Exit 0, UI-Reiter nur lesbar, AC-19) → `deploy-gregor-prod.sh` → `prod_selftest.py` Exit 0 → Kommentar + Close #2793 und #2860.

## Dependencies
- Upstream: S2b-PR der Cloud-Sitzung (Stand 2026-11-08: noch nicht angelegt). Schritte 2–3 hängen NICHT davon ab, Schritt 4 schon.
- Downstream: S3a #2794 (UI „Alarm ab“), S9 #2801, S8 #2800 bauen auf `alarm_ab` als Auslöser auf.

## Risks & Considerations
- **Reihenfolge-Risiko:** S2b vor der Migration ⇒ Nutzer mit „sensibel/entspannt/aus“ bekommen still die Vorlage. Darum Kontroll-Lauf direkt vor dem Merge.
- **Datenverlust:** Skript schreibt nur `alarm_ab` + Merker `alarm_ab_migration`, `metric_alert_levels` bleibt; tar.gz-Sicherung je Nutzer. Read-Modify-Write-Pflicht (CLAUDE.md) vom Skript erfüllt laut S2a-Review.
- **Laufende Dienste:** gleichzeitige Schreiber (Scheduler) ⇒ Exit 1 möglich, dann wiederholen.
- **Exit 2:** Dateien mit ungültiger Ampel von Hand prüfen, Ergebnis im Kommentar festhalten.
- **Kein Mail-Validator für `deviation-alert`:** Nachweis über echt zugestellte Mails im Stalwart-Postfach (Nebenbefund #1199). Staging-Mailweg-Problem #2774 beachten.
- **Prod-Daten-Zugriff:** Skript muss als `claude-gregor` laufen (Dateieigentümer), sonst Rechte-/Owner-Probleme.
- Nachts 22:00–02:30 UTC ist der CI-`test`-Job strukturell rot (Memory).

## Analysis

### Type
Feature-Auslieferung (Betrieb). Kein neuer Code, keine neue Spec: Spec `feat_2793_s2_alarm_stufenwechsel.md` v1.1 ist freigegeben. Phase 3 verweist nur auf sie.

### Probeläufe 2026-11-08 (nur lesend, nichts geschrieben)
Rohberichte: Scratchpad der Sitzung (`staging_probe.txt`, `prod_probe.txt`); Zahlen hier gesichert.

| Umgebung | Nutzer | wird geändert | unverändert | Konflikte | „ersetzt“ | ungültige Ampel (Exit 2) | Exit |
|---|---|---|---|---|---|---|---|
| Staging | 123 Verzeichnisse | 5 | 8 | 0 | 0 | 0 | 0 |
| Prod | 4 (default, henning, steffi, validator-issue110) | 4 (alle `henning`: `5f534011`, `74de939c`, `cp-ac57aa1e29c65649`, `cp-eb6ba0b239d90e37`) | 18 | 0 | 0 | 0 | 0 |

Prod-Abbildung plausibel geprüft: `off`→`never`, `standard`→`orange` (= Vorgabe „allgemein“), `entspannt`→`red`, `sensibel` bei Gewitter →`orange` (Deckel), CAPE/Nullgradgrenze/Feuchte bleiben erhalten (P1/D4/ADR-0010). Die PO-Trips werden nur umgeschrieben, nicht inhaltlich verändert: seine Wahl bleibt wirksam, `metric_alert_levels` bleibt stehen.

### Ausführung (festgestellt, nicht erneut herausfinden)
- **Als Dateieigentümer laufen**, sonst gehören die atomar ersetzten Dateien `hem`:
  - Staging: `sudo -n -u gregor-staging /home/hem/gregor_zwanzig_staging/.venv/bin/python /home/hem/gregor_zwanzig_staging/scripts/migrate_2793_alarm_ab.py --root /var/lib/gregor-staging/users [--execute]`
  - Prod: `sudo -n -u claude-gregor /home/hem/gregor_zwanzig/.venv/bin/python /home/hem/gregor_zwanzig/scripts/migrate_2793_alarm_ab.py --root /var/lib/gregor/users [--execute]`
- `uv run` und `sudo -D` scheitern am Worktree-Wächter der Sitzung; der direkte venv-Python mit absolutem Skriptpfad funktioniert (Skript löst `src/` über `__file__` auf).
- Beide Checkouts tragen das Skript (Staging-Health `5031f56`, enthält S2a `4df182f`). Prod läuft noch `938045c`; für die Migration egal, das Skript nutzt Code aus dem Checkout.
- Sicherungsziele existieren und sind schreibbar: `/var/lib/gregor-staging/.backups`, `/var/lib/gregor/.backups`.

### Affected Files
| File | Change Type | Description |
|------|-------------|-------------|
| `/var/lib/gregor-staging/users/*/briefings/*.json` (5) | MODIFY (Daten) | `ampel.metrics.<id>.alarm_ab` + Merker |
| `/var/lib/gregor/users/henning/briefings/*.json` (4) | MODIFY (Daten) | dito |
| Repo | – | keine Code-Änderung in diesem Workflow; S2b-PR kommt von der Cloud-Sitzung |

### Scope Assessment
- Repo-Dateien: 0 (nur dieses Kontext-Dokument). LoC: 0.
- Risk Level: MEDIUM. Daten-Migration auf Prod (mit Sicherung, Rücknahme per tar.gz) und anschließend Umschaltung der Alarmlogik (S2b) für alle vier Kanäle.

### Technical Approach
1. Staging `--execute`, Kontroll-Lauf (Exit 0 + „Nichts zu tun“).
2. Prod `--execute`, Kontroll-Lauf. Kommentar in #2793 mit obiger Tabelle + Sicherungspfaden.
3. Warten auf S2b-PR (Branch `claude/vigilant-babbage-ebij4r`). Direkt vor dem Merge Prod-Kontroll-Lauf erneut (neue Abos seit der Migration bekommen keine Altstufen mehr, aber Gate laut Spec).
4. Merge → Staging-Poll → `/e2e-verify` (Umfang laut #2860 Schritt 4) → `deploy-gregor-prod.sh` → `prod_selftest.py` → Kommentare, Close #2793 und #2860.

### Dependencies
- Schritte 1–2 sofort möglich. Schritt 3/4 blockiert, bis der S2b-PR existiert (Stand 2026-11-08: nicht angelegt).

### Nebenbefunde (→ #1199)
- Staging (2 Testnutzer-Dateien): `snow_new_sum_cm=off` und `sunny_hours_h=off` als „unbekannter Schlüssel“ erhalten. `_ALT_ALERT_LEVEL_KEYS` kennt `snow_new_sum_cm` → `fresh_snow` nicht. Heute wirkt dieser Schlüssel ebenfalls nicht, also keine Verschlechterung; auf Prod nicht vorhanden.

### Open Questions
- keine (keine Produktfrage; Reihenfolge und Gates stehen in #2860 und der freigegebenen Spec)
