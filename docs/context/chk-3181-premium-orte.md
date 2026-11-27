# Context: chk-3181-premium-orte (Issue #3181)

## Request Summary

Nachkontrolle in Produktion nach #3172 (Orte-SMS in Token-Schreibweise der Trip-SMS, Prod `1a534d4`,
Selftest Exit 0). Telegram/SMS/Mail sind echt zugestellt geprüft; der **Premium-SMS-Empfang** der
Orte-Token-Zeile nicht, weil Staging nur den Sandbox-Schlüssel hat (`GZ_SEVEN_API_KEY` fehlt dort bewusst).
Aufgabe: Orte-Briefing mit **1 Ort** und mit **3 Orten** per Premium-SMS an die zweite seven.io-Nummer
senden und Empfang und Inhalt prüfen: ≤153 Zeichen, Form `O1 … O2 …`, keine Ortsnamen, GSM-7.

Art: reine Prüfung, kein Produktcode erwartet. Ergebnis ist ein Nachweis im Issue. Fällt die Prüfung
durch, entsteht ein eigenes Bug-Issue (nicht in diesem Workflow reparieren).

## Related Files

| Datei | Rolle |
|---|---|
| `src/output/renderers/comparison.py:1136` `render_compare_sms`, `:1173` `_render_compare_sms_body`, `:1098` `ORTE_SMS_MAX_ZEICHEN=160` | Orte-Token-Zeile, Premium-Neukürzung auf 153 |
| `src/output/renderers/channel_layout.py:57` | `premium_sms` = 153 |
| `api/routers/briefings_send.py:160` `POST /api/briefings/{id}/send?user_id=&kind=vergleich&channel=premium_sms` | Handversand eines einzelnen Kanals (#3440) |
| `src/services/notification_service.py:1109-1148` `send_premium_sms` | Versand Ortsvergleich-Premium-SMS (#2275) |
| `src/output/channels/recipient.py:180-237` `PremiumSmsRecipient.for_user` | Empfänger = `premium_sms_reply_to` aus `user.json`, mit Frist `premium_sms_reply_at` |
| `.claude/tools/seven_journal.py` | Lese-Werkzeug seven.io-Journal (`outbound --since`), Schlüssel aus `.env`, Nummern gekürzt |
| `docs/specs/modules/feat_3172_orte_sms_token_zeile.md`, `docs/adr/0125-…` | Soll-Form |
| `docs/reference/sms_format.md` §5b, `premium_sms_format.md:54` | Formdoku |

## Existing Patterns (Vorbild #2275, Kommentar 26.09.2026)

Zustellung Ortsvergleich-Premium-SMS auf Prod wurde so belegt: **temporäres Test-Konto** auf Prod,
ein Test-Preset, **Einzelversand**; im `user.json` des Testkontos Tarif, Rückadresse (zweite Nummer)
und `is_test_user` direkt gesetzt (der Link-Code-Weg liefert Absender `InfoSMS`, unbrauchbar). Nachweis:
seven.io-**Ausgangsjournal** `dlr=DELIVERED` an der zweiten Nummer, Text/Länge/Segment, plus Prod-Log
„premium_sms … über seven.io gesendet“ in derselben Sekunde. Danach Testkonto, Preset, Orte, Rückadresse
vollständig entfernt. Kein anderes Konto berührt.

Prod-Daten: `/var/lib/gregor/users`, Zugriff `sudo -n -u claude-gregor …`; Skripte aus dem Worktree in
der direkten Form `sudo -n -u claude-gregor /home/hem/.local/bin/uv run --project <wt> python <wt>/…`.

## Dependencies

- Prod-Core intern (FastAPI Port 8000) bzw. Go-API; Handversand-Endpunkt mit `user_id` des Testkontos.
- seven.io Prod-Schlüssel (`GZ_SEVEN_API_KEY`, nur Prod-`.env`), Journal-Endpunkt `journal/outbound`.
- Zweite seven.io-Nummer als Empfänger: Nummer aus Konfiguration/Bestand, nie in Doku/Issue ausschreiben.

## Existing Specs

- `feat_3172_orte_sms_token_zeile.md` (Form, Grenzen 160/153, keine Namen).
- #2275 (Premium-SMS als Versandkanal Ortsvergleich).

## Risks

- **Echte PO-Konten nicht anfassen** (`default`, `henning`, `steffi`, `validator-issue110`); Trip-/Orte-Konfiguration des PO tabu.
- **Kosten:** genau 2 Premium-SMS (1 Ort, 3 Orte). Kein Wiederholen ohne Befund.
- **Aufräumen ist Pflicht:** Testkonto vollständig entfernen, sonst bleibt ein Konto mit Rückadresse und Premium-Tarif auf Prod.
- Auto-Mode-Klassifizierer kann Prod-Schreibzugriffe blocken; dann per AskUserQuestion in Alltagssprache freigeben lassen, nicht umgehen.
- Wetterabhängigkeit: Inhalt der Token variiert; geprüft wird Form (O-Nummern, keine Namen, ≤153, GSM-7, 1 Segment) und Zustellung, nicht konkrete Werte.
- Öffentliches Repo: Nummern, Konto-IDs, Schlüssel nie in Doku/Issue.

## Analyse (kombiniert, Score 2)

Ansatz: Prüfskript (nur im Scratchpad/Worktree, nicht ausgeliefert) bzw. Einzelschritte:
1. Vorab Kurzform lokal gegen Prod-Konfiguration rendern (kostenlos): Länge ≤153, GSM-7, keine Namen.
2. Temporäres Prod-Testkonto mit Premium-Tarif, Rückadresse = zweite Nummer, `is_test_user`; zwei Orte-Vergleiche (1 Ort, 3 Orte) mit Kanal Premium-SMS.
3. Je ein Handversand `kind=vergleich&channel=premium_sms`.
4. Nachweis: `seven_journal.py outbound --since <heute>` → zwei Einträge an …902, `dlr=DELIVERED`, Text = erwartete Form, Länge ≤153; Prod-Log-Zeile.
5. Aufräumen, Ergebnis als Kommentar in #3181, Issue schließen bei Erfolg.

## Analysis

**Type:** Prüfung (Nachkontrolle Prod), kein Produktcode. Fällt sie durch → eigenes Bug-Issue.

**Affected Files:** keine Änderung an `src/`/`api/`. Nur Prod-Daten eines temporären Testkontos (anlegen, danach vollständig löschen) und Nachweis im Issue.

**Scope/Risk:** klein; Risiko gering bei striktem Aufräumen. Kosten: genau 2 Premium-SMS.

**Technical Approach (Variante A, Plan-Agent-Empfehlung):**
1. Vorab: Eindeutigkeit der Rückadresse prüfen (`grep premium_sms_reply_to` über alle Prod-`user.json`, maskiert; `_check_reply_address_unique`, `src/output/channels/recipient.py:~215-237`). Steht die zweite Nummer an einem anderen Konto mit gültiger Frist → blockiert; dann stoppen und klären (nicht am PO-Konto ändern).
2. Kostenloser Vorab-Render der Kurzform im Worktree (kein Versand).
3. Testkonto per Datei als `claude-gregor` unter `/var/lib/gregor/users/<chk3181-…>/`: `user.json` mit `tier=premium`, `premium_sms_reply_to` (zweite Nummer), `premium_sms_reply_at` = jetzt − 1 min (RFC3339 UTC, TTL 30 T, `premium_sms.py:50`). **Kein `is_test_user`** (lenkt auf Sandbox-Schlüssel um, `config.py:375-423`, Guard `seven_io_base.py:~139-153`). 3 Orte unter `locations/`, 2 Presets `briefings/` (`kind=vergleich`, 1 bzw. 3 `location_ids`, Tagesfenster 6–18).
4. Versand **im Prod-Core-Prozess** (Herkunftssperre `seven_io_base.py:~155-182`: Worktree-Skripte senden nie echt): `curl` loopback `127.0.0.1:8000/api/briefings/<id>/send?user_id=…&kind=vergleich&channel=premium_sms` mit Header `X-GZ-Core-Auth` (Secret aus Prod-`.env`, nie ausgeben). Antwort `sent_channels:["premium_sms"]`. Bei Fehler abbrechen, nicht wiederholen.
5. Nachweis: `.claude/tools/seven_journal.py outbound --since <heute>` → 2 Einträge an …902, `dlr=DELIVERED`, Text ≤153, `O1 …` (bzw. `O1 … O2 … O3 …`), keine Ortsnamen, GSM-7; Prod-Log „premium_sms … über seven.io gesendet“.
6. Aufräumen: Konto-Ordner komplett entfernen, `find` nach Konto-ID leer, `ls`-Vergleich der Kontenliste vorher/nachher.
7. Ergebnis als Kommentar in #3181 (ohne Nummern/IDs/Schlüssel), Issue schließen.

**Befunde gegen den Plan (eingearbeitet):** `is_test_user` verhindert echten Versand; Worktree-Herkunft schaltet auf Sandbox; Rückadresse muss eindeutig und ≤30 Tage alt sein; Secret-Header Pflicht.

**Open Questions:** keine Produktfrage. Auto-Mode-Klassifizierer kann Prod-Schreibzugriff blocken → dann PO per AskUserQuestion in Alltagssprache um Freigabe bitten.

## Stand bei Übergabe (Phase 5, 27.11.)

- Spec auto-freigegeben (Ampel grün). Phase 5 begonnen.
- RED-Beleg-Idee: `seven_journal.py outbound --since 2026-11-19` als „Nachweis fehlt“; erster Lauf lieferte nur uv-Aufbauzeilen, keine Journalzeilen (`docs/artifacts/chk-3181-premium-orte/journal-vorher.txt`) – Ausgabeformat des Werkzeugs bei leerem Ergebnis prüfen, dann Artefakt registrieren + `mark-red`.
- Danach `/50-implement`: Ablauf laut Spec „Implementation Details“ 1–7 (kein Produktcode, Live-Lauf auf Prod).

## Stand bei Übergabe (Phase 6b, 27.11. 17:05 UTC)

- Live-Lauf auf Prod ERLEDIGT (PO-Freigabe verbraucht): beide Orte-Premium-SMS DELIVERED, 141/151 Zeichen, GSM-7, 1 Segment, `O1 …`, keine Namen. Belege: `docs/artifacts/chk-3181-premium-orte/live-nachweis.txt` (Journal, Log, Aufräumen), Kern-Test `test-run-output.txt` (32 passed, GREEN auto-freigegeben).
- Abweichung AC-2: 2 Zusatz-Alarm-SMS aus Planer `compare_alert_checks` (amtliche Warnung AV2, Vorgabe an) → Prüfaufbau, kein Produktfehler; im Kommentarentwurf offen benannt.
- Prüfkonto entfernt, Kontenliste gleich, Planer-Zustand per Prune bereinigt (17:01Z). NICHT erneut senden.
- Kommentarentwurf für #3181: `docs/artifacts/chk-3181-premium-orte/issue-kommentar.md` (geprüft: keine Nummern/IDs/Schlüssel).
- Nächstes: Adversary (Gerüst `adversary-dialog.md` liegt, Risiko hoch, 2 Runden, keine Pflichtdateien), stamp, qa_gate `--checklist … --infra --no-visual`, Phase 7, dann `/60-validate`; Kommentar posten, Issue schließen; Spec/Kontext/Briefing per PR (Commit war in Phase 6 vor Verdict gesperrt).
