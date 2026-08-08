# Context: fix-1595-datenwurzel-umzug

**Issue:** [#1595](https://github.com/henemm/gregor_zwanzig/issues/1595)
**Erstellt:** 2026-08-08
**Alle Angaben gemessen** am Stand `main` = `354f57d7`, nicht aus Dokumenten übernommen.

## Request Summary

Die Produktivdaten liegen unter `/home/hem/gregor_zwanzig/data/` — demselben Verzeichnis, in dem alle Claude-Sessions, Tests und Skripte als User `hem` arbeiten. Sie sollen an einen Ort außerhalb des Arbeitsbaums umziehen, damit Testläufe und Sessions sie konstruktiv nicht mehr erreichen können.

## Warum jetzt

Dritter Schaden aus derselben Wurzel:

| Wann | Was |
|---|---|
| #1265 | Testdaten-Müll im Produktiv-Datenbaum, Bereinigung nötig |
| ADR-0028 / #1284 (16.07.) | Playwright-E2E schrieb monatelang unbemerkt in den Prod-Baum: 153 Vergleichs-Abos mit `@example.com`-Empfängern im Konto `admin`, 133 täglich um 06:00 fällig |
| 07.08. (#1595) | Rechte-Drift sperrte den Dienst aus `henning/user.json` aus; Anmeldung einen Tag tot, Meldung „falsches Kennwort" |

ADR-0028 hat den sauberen Weg (`GZ_DATA_DIR`) erwogen und verworfen — Begründung: *„`scheduler_dispatch_service.py:141` hardcodet `data_root = "data"`"*. Nachgemessen sind es **vier** Stellen allein in dieser Datei. Die Entscheidung fiel auf falscher Tatsachengrundlage.

## Ist-Zustand: wie die Datenwurzel heute bestimmt wird

Zentrale, korrekte Auflösung existiert in **beiden** Sprachen und liest **dieselbe** Variable `GZ_DATA_DIR`:

| Sprache | Stelle | Kette |
|---|---|---|
| Python | `src/app/loader.py:1083` `get_data_root()` | `_DATA_ROOT` (Test-Fixture) > `GZ_DATA_DIR` > `Path("data")` |
| Go | `internal/config/config.go:9` `DataDir` | `envconfig.Process("GZ", …)` ⇒ `GZ_DATA_DIR`, Default `"data"` |

**Der Default ist relativ.** Er wird gegen das `WorkingDirectory` des Prozesses aufgelöst — dort sitzt das eigentliche Problem.

## Related Files

### Python-Kern — 12 Stellen legen die Wurzel selbst fest

| Datei:Zeile | Art |
|---|---|
| `src/services/scheduler_dispatch_service.py:148` | `data_root = "data"` |
| `src/services/scheduler_dispatch_service.py:174` | `data_root = "data"` |
| `src/services/scheduler_dispatch_service.py:226` | `data_root = "data"` |
| `src/services/scheduler_dispatch_service.py:454` | `data_root = "data"` |
| `src/services/dispatch_orchestrator.py:100` | `self._data_root = data_root or "data"` |
| `src/app/loader.py:294` | `load_compare_presets(data_root: Union[str, Path] = "data")` |
| `src/app/loader.py:1142` | `list_all_user_ids(data_dir="data")` |
| `src/app/loader.py:1170` | `lookup_user_by_email(data_dir="data")` |
| `src/app/loader.py:1192` | `lookup_user_by_telegram_chat_id(data_dir="data")` |
| `src/output/channels/email.py:239` | `_load_resend_allowlist(data_dir="data")` |
| `src/services/inbound_email_reader.py:220` | Parameter-Default `data_dir="data"` |
| `src/services/inbound_telegram_reader.py:378` | Parameter-Default `data_dir="data"` |

### Go — 2 relevante Stellen

| Datei:Zeile | Art |
|---|---|
| `internal/mail/sender.go:186` | `return "data"` als Fallback |
| `internal/provider/openmeteo/calllog.go:18` | Paket-Variable `filepath.Join("data","diagnostics",…)` — umgeht die Config vollständig |

Unkritisch: `cmd/migrate1257/main.go:15`, `cmd/migrate1258/main.go:15` (Flag-Defaults von Einmal-Werkzeugen).

### Betriebsseite — lag NICHT in der ursprünglichen Inventur

| Ort | Art | Repo |
|---|---|---|
| `deploy-gregor-prod.sh:248` | `cd $REPO_DIR && migrate_1250_briefings.py --root data/users` (relativ) | henemm-infra |
| `auto-deploy-gregor-staging.sh:141` | identisch | henemm-infra |
| `gregor-staging-sweep.sh:25` | `R=/home/hem/gregor_zwanzig_staging/data` (absolut) | henemm-infra |
| `check-gregor20.sh:880-881` | absolute Prod-/Staging-Pfade (neu aus #182) | henemm-infra |
| `scripts/setup_staging_validator_trip.py:35` | **dritte** Variable `GZ_STAGING_DATA_DIR`, Default absolut | gregor_zwanzig |

Cron ruft `setup_staging_validator_trip.py` täglich 04:15 mit `cd /home/hem/gregor_zwanzig` (Prod-Verzeichnis!) und gesetztem `GZ_STAGING_DATA_DIR` auf Staging auf — eine Kreuzung, die beim Umzug bricht, wenn man nur an die Dienste denkt.

## Betriebs-Ist: Zuordnung existiert praktisch nicht

| Dienst | `WorkingDirectory` | `GZ_DATA_DIR` |
|---|---|---|
| `gregor-api` (Prod) | `/home/hem/gregor_zwanzig` | **nicht gesetzt** |
| `gregor-python` (Prod) | `/home/hem/gregor_zwanzig` | **nicht gesetzt** |
| `gregor-api-staging` | `/home/hem/gregor_zwanzig_staging` | gesetzt |
| `gregor-python-staging` | `/home/hem/gregor_zwanzig_staging` | **nicht gesetzt** |

Auch in keiner `.env` gesetzt. **In 3 von 4 Diensten entscheidet allein das Arbeitsverzeichnis**, welchen Datenbestand ein Prozess anfasst.

## Umfang der Daten

79 MB, 280 Einträge, drei Unterbäume: `data/users/`, `data/cache/`, `data/diagnostics/`. Ob `cache/` und `diagnostics/` mitziehen, ist eine Entscheidung der Analyse — `calllog.go:18` schreibt nach `data/diagnostics` an der Config vorbei.

## Existing Specs & ADRs

| Dokument | Bezug |
|---|---|
| ADR-0031 | Legt dateibasierte JSON-Persistenz unter `data/users/{user_id}/` fest. Entscheidet **Format und Struktur, nicht den Ort** — rückwirkend dokumentiert 2026-07-22 als „gelebte Praxis". Der Umzug widerspricht ihr nicht, ergänzt sie aber um eine nie getroffene Ortsentscheidung ⇒ ADR-Nachtrag nötig. |
| ADR-0028 | Verwarf `GZ_DATA_DIR` auf falscher Tatsachengrundlage; wird durch diesen Umbau abgelöst. |
| ADR-0003 | Mandantentrennung — bleibt unberührt. |
| `docs/specs/_archive/modules/issue_1265_prod_testdata_cleanup.md` | Historie, kein Ist-Stand |
| `docs/specs/_archive/modules/fix_1284_admin_prod_testdata.md` | Historie, kein Ist-Stand |

## Dependencies

- **Upstream:** systemd-Units (henemm-infra), `.env`-Dateien, `WorkingDirectory`, Dateirechte/ACLs des Zielorts (Dienst läuft als `claude-gregor`).
- **Downstream:** alle drei Dienste, Scheduler, Anmeldung, Mail-Allowlist, Tier-Auflösung, Inbound-Handler, Deploy- und Sweep-Skripte, `check-gregor20.sh`, Backup.

## Risks & Considerations

1. **Unvollständige Inventur ist das Hauptrisiko.** Die Liste stammt aus Textsuche; ADR-0028 irrte schon einmal, und ein erstes Suchmuster dieser Messung verfehlte bekannte Treffer. Gegenmaßnahme: Der Nachweis kommt nicht aus der Liste, sondern aus einem **Laufzeit-Test auf Staging** mit leerem Zielort — was noch am alten Ort kratzt, meldet sich selbst.
2. **Stiller Zwischenzustand.** Eine nicht umgestellte Stelle findet den alten Pfad leer vor und legt dort möglicherweise neue Daten an, die niemand mehr liest. Deshalb: erst Code umstellen und verifizieren, dann Daten bewegen — nie umgekehrt.
3. **Symlink als Rückfahrkarte, nicht als Lösung.** Ein Verweis am alten Ort hält alles am Laufen, konserviert aber genau die Gefahr (ein Test folgt ihm in die Live-Daten). Nur befristet, mit Enddatum.
4. **Backup war nicht vorhanden.** `backup.sh` sichert `data/` nicht (henemm-infra#184); jüngste Sicherung war 24 Tage alt. Vollsicherung vor Beginn erstellt und verifiziert (280/280 Einträge): `.backups/prod-data-pre-1595-20260808.tar.gz`.
5. **Zwei Repos.** Systemd-Units und Betriebsskripte liegen in henemm-infra — die Auslieferung ist nicht atomar. Reihenfolge muss so gewählt sein, dass jeder Zwischenstand lauffähig bleibt.
6. **Rechte am Zielort.** Der Rechte-Unfall vom 07.08. darf sich nicht wiederholen: Der Zielort braucht Besitzer `claude-gregor` und eine Default-ACL, die dem Dienst Zugriff sichert. `check-gregor20.sh` (#182) überwacht das bereits.
7. **Atomares Schreiben braucht dasselbe Dateisystem.** `writeFileAtomic` legt die tmp-Datei im Zielverzeichnis an — beim Umzug unkritisch, solange der gesamte Datenbaum auf einem Dateisystem liegt.

---

# Analysis

**Typ:** Feature (strukturelle Härtung; kein Produkt-Fehlverhalten, sondern eine nie getroffene Ortsentscheidung)

## Entscheidung 1 — Zielort: `/var/lib/gregor` bzw. `/var/lib/gregor-staging`

Gewählt, weil vier Dinge zusammenfallen:

- **FHS-Standard** für veränderliche Anwendungsdaten. Kein Sonderweg, den Nachfolger erst verstehen müssen.
- **systemd `StateDirectory=gregor`** legt das Verzeichnis an, setzt Besitzer auf den Dienst-User und die Rechte bei jedem Start neu. Damit ist die Rechte-Drift vom 07.08. **strukturell** erledigt, nicht nur überwacht. `StateDirectoryMode=0750` — der Baum enthält Kennwort-Hashes und darf nicht weltlesbar sein.
- **Beide Dienste laufen als `claude-gregor`** (gemessen: `gregor-api` und `gregor-python`) — ein gemeinsames Verzeichnis ist konfliktfrei.
- **Gleiches Dateisystem** wie das Repo (beide `/dev/sda1`): Der Umzug ist ein `mv`, also atomar und sekundenschnell — kein Kopiervorgang, der halbfertig unterbrochen werden kann.

Verworfen: `/home/hem/gregor-data`. Einfacher anzulegen, aber weiterhin im Home-Bereich, ohne Standardbezug und ohne den systemd-Rechte-Automatismus.

## Entscheidung 2 — alle drei Unterbäume ziehen um

`users/`, `cache/` und `diagnostics/` gemeinsam. Ein halb geleertes `data/` im Repo wäre eine Falle für jeden, der später hineinschaut.

**Nebenwirkung, die das Ziel schärft:** Nach dem Umzug enthält `data/` im Repo nur noch die 13 versionierten Test-Fixtures. Ein Test, der relativ auf `data/` zeigt, findet damit genau das, was er finden soll — Fixtures statt Livedaten. Aus dem Unfallort wird ein Fixture-Ordner.

## Entscheidung 3 — eine einzige Quelle für den Pfad

`/etc/gregor/data-prod.env` und `/etc/gregor/data-staging.env` mit `GZ_DATA_DIR=…`, geladen von den systemd-Units (`EnvironmentFile=`) **und** von den Cron-/Betriebsskripten. `/etc/gregor/` existiert bereits (`mail-prod.env`).

Grund: Der Pfad darf nicht an fünf Stellen dupliziert werden — genau das hat die heutige Lage erzeugt. Rechte `644 root:root`; ein Pfad ist keine Geheiminformation, und die Skripte laufen unter verschiedenen Benutzern.

Die dritte Variable `GZ_STAGING_DATA_DIR` (`scripts/setup_staging_validator_trip.py:35`) wird auf dieselbe Quelle zurückgeführt.

## Entscheidung 4 — das Staging-Messverfahren (Kern der Absicherung)

Die Inventur ist der **Startpunkt**, nicht der Nachweis. Textsuche hat in diesem Vorgang bereits zweimal getrogen (ADR-0028: eine statt vier Stellen; erstes Suchmuster verfehlte bekannte Treffer). Der Beweis muss vom laufenden System kommen.

**Stufe A — sanft, 24 Stunden.** Staging-Daten nach `/var/lib/gregor-staging` verschieben, `GZ_DATA_DIR` für alle Staging-Dienste setzen, den alten Ordner umbenennen. Wer den relativen Pfad benutzt, **legt einen neuen `data/`-Ordner an** — dessen Inhalt verrät, wer es war. Der Zeitraum deckt die Cronjobs 04:15 und 04:30 sowie die 05:00-Briefings ab.

**Stufe B — scharf, kurz.** Am alten Ort eine *Datei* namens `data` anlegen (kein Verzeichnis). Jeder Zugriff auf `data/…` scheitert dann mit „Not a directory" — **laut, im Log**, statt still ins Leere zu laufen. Stufe A findet nur die Schreiber; Stufe B findet auch die Leser, die sonst stillschweigend leere Ergebnisse zurückgeben (das Muster „leer ≠ unbekannt" aus #1492).

Erwartetes Ergebnis von Stufe B ist ein kurzzeitig kaputtes Staging. Das ist der Zweck, nicht der Unfall.

## Entscheidung 5 — Reihenfolge und Rückfahrkarte

Code **vor** Daten. Eine nicht umgestellte Stelle fände den alten Pfad sonst leer vor und legte dort möglicherweise still neue Daten an, die niemand mehr liest — der Schaden fiele erst Tage später auf.

Für Produktion: nach dem `mv` ein Symlink `data → /var/lib/gregor` als Rückfahrkarte, **befristet auf 7 Tage**. Er hält im Fehlerfall alles am Laufen, konserviert aber genau die Gefahr (ein Test folgt ihm in die Livedaten) — deshalb mit Enddatum, nicht „bis auf Weiteres".

Rollback unter zwei Minuten: Symlink entfernen, `mv` zurück, `GZ_DATA_DIR` aus der env-Datei nehmen, Dienste neu starten. Sicherung liegt verifiziert vor (`.backups/prod-data-pre-1595-20260808.tar.gz`, 280/280 Einträge).

## Scheibenschnitt

Fünf Scheiben, **jede ein eigener Workflow** — das 250-LoC-Limit ist pro Workflow, und jede Scheibe muss einzeln auslieferbar und einzeln rücknehmbar sein.

| # | Inhalt | Prod-Eingriff | Risiko |
|---|---|---|---|
| **S1** | Staging-Messverfahren (Stufe A + B), Befund dokumentieren | nein | niedrig |
| **S2** | Code umstellen: 14 bekannte Stellen + Funde aus S1 | nein | mittel |
| **S3** | Betrieb: systemd `StateDirectory`, zentrale env-Dateien, 4 Betriebsskripte (zwei Repos) | Staging | mittel |
| **S4** | Prod-Umzug mit Symlink-Rückfahrkarte | **ja** | hoch |
| **S5** | Nachsorge: ADR, Symlink entfernen, Backup aufnehmen (henemm-infra#184) | ja | niedrig |

S1 liefert die Grundlage für S2 — der Umfang von S2 steht erst danach fest.

## Affected Files

| Datei | Änderung | Anmerkung |
|---|---|---|
| `src/services/scheduler_dispatch_service.py` | MODIFY | 4 Stellen |
| `src/services/dispatch_orchestrator.py` | MODIFY | 1 |
| `src/app/loader.py` | MODIFY | 4 (Zeile 1083 bleibt — das ist die zentrale Auflösung) |
| `src/output/channels/email.py` | MODIFY | 1 |
| `src/services/inbound_email_reader.py` | MODIFY | 1 |
| `src/services/inbound_telegram_reader.py` | MODIFY | 1 |
| `internal/mail/sender.go` | MODIFY | Fallback auf Config zurückführen |
| `internal/provider/openmeteo/calllog.go` | MODIFY | Paket-Variable → Config |
| `scripts/setup_staging_validator_trip.py` | MODIFY | dritte Variable zusammenführen |
| `docs/adr/00XX-datenwurzel-ausserhalb-arbeitsbaum.md` | CREATE | neu |
| `docs/adr/0031-…`, `0028-…` | MODIFY | Ergänzung / „abgelöst durch" |
| henemm-infra: 4 Skripte + 4 systemd-Units + 2 env-Dateien | MODIFY/CREATE | eigener PR |

## Scope Assessment

- Dateien: ~14 im Projekt-Repo, ~10 in henemm-infra
- Geschätzt: +150 / −40 LoC im Code (die Masse sind Einzeiler), dazu Betriebs-Konfiguration
- **Risiko: HIGH** — Produktivdaten, Anmeldung, Scheduler, zwei Repos ohne atomare Auslieferung

## Open Questions

Keine fachlichen offen. Zwei Punkte zur Kenntnis für den PO, keine Entscheidungsfragen:

- Staging ist während S1 Stufe B **absichtlich kurzzeitig kaputt**.
- Der Prod-Umzug (S4) braucht wenige Sekunden Dienst-Stillstand.

## Next

`/30-write-spec` — Spezifikation für **S1** (Staging-Messverfahren). Die Folge-Scheiben bekommen eigene Specs, weil ihr Umfang erst nach S1 feststeht.
