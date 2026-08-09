---
entity_id: collect_send_recipient_isolation
type: bugfix
created: 2026-08-09
updated: 2026-08-09
status: done
version: "1.0"
workflow: "fix-1426-sammelversand-ersatzweg"
tags: [email, sammelversand, smtp, ersatzweg, fehlerbehandlung]
---

# Collect-Send Recipient Isolation

## Approval

- [x] Approved

## Purpose

Sammelversand an mehrere Empfänger (Ortsvergleich-Presets) hat zwei zusammenhängende
Defekte in `EmailOutput._dial_and_send()`: (A) beide Ersatz-Postausgänge brechen beim
ersten abgelehnten Empfänger komplett ab, statt wie der Primärweg jeden Empfänger
einzeln zu behandeln; (B) lehnt der Server *alle* Empfänger ab, meldet `send()`
trotzdem Erfolg, weil kein Erfolgs-Check existiert. Diese Spec vereinheitlicht die
Empfänger-Einfassung für alle drei Versandwege und ergänzt einen zentralen
Erfolgs-Check.

## Source

- **File:** `src/output/channels/email.py`
- **Identifier:** `EmailOutput._dial_and_send()`, `EmailOutput.send()`

## Estimated Scope

- **LoC:** ~100–150 (Code ~40–60, Tests ~60–90)
- **Files:** 2 (`src/output/channels/email.py`, `tests/tdd/test_mail_transport_dial_behaviour.py`)
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/services/notification_service.py` | Aufrufer | Compare-Mehrempfänger-Versand (`to=recipients`, Zeile ~835); propagiert `OutputError` bereits unverändert |
| `src/services/radar_alert_service.py` | Aufrufer | Sendet praktisch immer an genau einen Empfänger — trifft den Ein-Empfänger-Fast-Path, bleibt unverändert |
| `.claude/hooks/renderer_mail_gate.py` (#811) | Commit-Gate | Greift bei jedem Commit, der `email.py` staged — `tests/tdd/test_issue_811_mode_matrix.py` grün + `briefing_mail_validator.py`-Lauf sind Pflichtlauf vor Commit |
| `tests/test_mail_recipient_parity.py` | Struktur-Test | Sucht die Empfänger-Guard-`If` in `send()` als oberste Ebene — liegt VOR der Retry-Schleife, von dieser Änderung unberührt, solange `send()`s Kontrollfluss vor der Schleife unangetastet bleibt |

## Implementation Details

```
_dial_and_send(..., deadline_at) -> None:
    # Parameter `isolate_per_recipient` entfaellt ersatzlos.
    with smtplib.SMTP(...) as server:
        ...
        if len(recipients) == 1:
            server.sendmail(from_addr, recipients, msg.as_string())
            return
        fehler: list[tuple[str, Exception]] = []
        for recipient in recipients:
            try:
                server.sendmail(from_addr, [recipient], msg.as_string())
            except smtplib.SMTPServerDisconnected:
                raise  # unveraendert: Transportabbruch sofort durchreichen,
                       # VOR dem generischen SMTPException-Zweig
            except smtplib.SMTPException as exc:
                logger.error("SMTP-Fehler fuer Empfaenger %s: %s", recipient, exc)
                fehler.append((recipient, exc))
        if len(fehler) == len(recipients):
            raise OutputError(
                "email",
                f"Alle {len(recipients)} Empfaenger abgelehnt: "
                f"{[str(e) for _, e in fehler]}",
            )
```

- Die `if isolate_per_recipient: … else: …`-Verzweigung in der Schleife entfällt zugunsten
  eines einzigen Pfads (der heutigen `True`-Variante). Alle drei Aufrufstellen
  (`send()` Primärweg, `_handle_transient_dial_failure()` beide Ersatzwege) verlieren
  das `isolate_per_recipient=`-Argument.
- `smtplib.SMTPServerDisconnected` bleibt VOR dem generischen `SMTPException`-Zweig und
  wird weiterhin sofort durchgereicht (kein Sammeln) — ein toter Socket ist kein
  Empfänger-Problem.
- Der Erfolgs-Check sitzt zentral am Ende der Schleife in `_dial_and_send()`, nicht an
  den drei Aufrufstellen: nur bei `len(fehler) == len(recipients)` (Totalablehnung)
  wird `OutputError` geworfen. Der Ein-Empfänger-Fast-Path (`len(recipients) == 1`)
  bleibt unverändert — dort propagiert eine Ablehnung schon heute korrekt als Exception.
- Der Primärweg-Aufruf (`send()`, im eigenen try-Block) lässt eine dort geworfene
  `OutputError` unverändert durchlaufen, da kein nachfolgender `except`-Zweig
  `OutputError` matcht (alle sind smtplib-/OSError-spezifisch). Beide Ersatzweg-Aufrufe
  stehen bereits in `except Exception as fb_err: raise OutputError(..., f"fallback also
  failed: {fb_err}")`-Wrappern — eine dort geworfene `OutputError` läuft automatisch
  durch diesen bestehenden Pfad.

## Expected Behavior

- **Input:** `send(..., to=[a, b, c])` mit mehreren Empfängern, einer der drei
  Versandwege (Primär- oder einer der beiden Ersatzwege) aktiv.
- **Output:** Wird mindestens ein Empfänger zugestellt, kehrt `send()` normal zurück
  (kein Fehler) — unabhängig davon, ob der Versand über den Primär- oder einen
  Ersatzweg lief. Werden alle Empfänger abgelehnt, wirft `send()` `OutputError`.
- **Side effects:** Jede einzelne Empfänger-Ablehnung wird weiterhin per
  `logger.error()` geloggt (unverändert). Ein Transportabbruch
  (`SMTPServerDisconnected`) landet weiterhin in `send()`s eigenem Retry-/
  Ersatzweg-Zweig, nicht in der neuen Sammel-Logik.

## Acceptance Criteria

- **AC-1:** Given drei Empfänger, Primärweg schlägt viermal mit `SMTPResponseException`
  (452) fehl, Ersatzweg 1 (4xx-Auslöser) ist konfiguriert und lehnt genau den zweiten
  Empfänger mit `SMTPException` ab / When `send()` aufgerufen wird / Then werden
  Empfänger 1 und 3 auf dem Ersatzweg zugestellt und `send()` wirft NICHT.
  - Test: umgeschriebene Variante von
    `test_ac3_ersatzweg_bricht_beim_ersten_abgelehnten_empfaenger_ab` (Fall
    `ersatzweg-1-4xx`) — statt `pytest.raises(OutputError)` wird jetzt Zustellung an
    Empfänger 0 und 2 sowie normale Rückkehr von `send()` geprüft.

- **AC-2:** Given dieselbe Ausgangslage wie AC-1, aber Primärweg scheitert mit
  `OSError` (Netzfehler) statt 4xx, Ersatzweg 2 (Netzfehler-Auslöser) ist konfiguriert
  und lehnt genau den zweiten Empfänger ab / When `send()` aufgerufen wird / Then
  werden Empfänger 1 und 3 auf dem Ersatzweg zugestellt und `send()` wirft NICHT.
  - Test: umgeschriebene Variante von
    `test_ac3_ersatzweg_bricht_beim_ersten_abgelehnten_empfaenger_ab` (Fall
    `ersatzweg-2-netzfehler`), analog zu AC-1.

- **AC-3:** Given drei Empfänger, Primärweg lehnt ALLE drei mit `SMTPException` ab,
  kein Ersatzweg konfiguriert / When `send()` aufgerufen wird / Then wirft `send()`
  `OutputError`, dessen Meldung alle drei Empfänger-Ablehnungen erkennbar macht.
  - Test: neuer Test (z. B. `test_ac10_primaerweg_totalablehnung_wirft`) — bisher kehrte
    `send()` hier normal zurück (Defekt B), obwohl kein Empfänger erreicht wurde.

- **AC-4:** Given Primärweg scheitert komplett mit Netzfehler, Ersatzweg ist
  konfiguriert, lehnt dort aber ALLE drei Empfänger mit `SMTPException` ab / When
  `send()` aufgerufen wird / Then wirft `send()` `OutputError` mit einer Meldung, die
  den gescheiterten Ersatzweg erkennbar macht (bestehendes
  "fallback also failed"-Format).
  - Test: neuer Test (z. B. `test_ac11_ersatzweg_totalablehnung_wirft`) — bisher gab es
    für diesen Fall keinen Test, `_dial_and_send()` kehrte implizit mit `None` zurück
    und der Ersatzweg-Aufruf in `_handle_transient_dial_failure()` meldete fälschlich
    Erfolg (`return True`).

- **AC-5:** Given ein Transportabbruch (`SMTPServerDisconnected`) während `sendmail()`
  für den zweiten von drei Empfängern auf dem Primärweg / When `send()` aufgerufen
  wird / Then wird für den dritten Empfänger auf DERSELBEN Verbindung kein
  Zustellversuch mehr unternommen, und der Abbruch landet weiterhin in `send()`s
  eigenem `SMTPServerDisconnected`-Zweig (Retry/Ersatzweg) statt in der neuen
  Sammel-/Erfolgs-Logik verschluckt zu werden.
  - Test: bestehender
    `test_f001_primaerweg_reicht_transportabbruch_durch_statt_ihn_zu_verschlucken`
    bleibt unverändert grün (Regressionsnachweis, keine Anpassung nötig).

- **AC-6:** Given die sieben bestehenden Fehlerfälle (Auth-Fehler, 5xx dauerhaft,
  4xx ohne/mit gescheitertem Ersatzweg, sonstiger SMTP-Fehler, Netzfehler ohne/mit
  gescheitertem Ersatzweg) / When `send()` jeweils aufgerufen wird / Then bleiben die
  gemeldeten Fehlertexte wortgleich zum Stand vor diesem Fix.
  - Test: bestehender `test_ac9_fehlermeldungen_bleiben_wortgleich` läuft nach dem Fix
    unverändert grün, ohne dass die erwarteten Meldungs-Strings angepasst werden.

- **AC-7:** Given genau ein Empfänger (Ein-Empfänger-Fast-Path, z. B.
  `radar_alert_service.py`) / When `send()` aufgerufen wird / Then bleibt das
  Verhalten unverändert — eine Ablehnung propagiert weiterhin direkt als Exception,
  ohne durch die neue Sammel-/Erfolgs-Logik zu laufen.
  - Test: bestehender
    `test_ac1_primaerweg_verbindet_mit_konfiguriertem_ziel_in_fester_reihenfolge` bleibt
    unverändert grün.

## Known Limitations

- Kein Staging-Nachweis nötig (Issue-Aussage: der Ersatzweg ist im Betrieb praktisch
  nicht gezielt provozierbar) — die Kern-Schicht-Sink-Tests oben gelten als
  hinreichender Nachweis.
- `radar_alert_service.py` sendet nach heutigem Stand ausschließlich an genau einen
  Empfänger (`mail_settings.mail_to` oder ein einzelner `to`-Override) — nur
  Blast-Radius-Hinweis, kein Anpassungsbedarf in dieser Scheibe.
- Fälle, in denen der Ersatzweg heute wegen Defekt A fälschlich `OutputError` wirft,
  obwohl tatsächlich ≥1 Empfänger zustellbar wäre, werden nach dem Fix zu Erfolg (mit
  Log-Zeile pro abgelehntem Empfänger) — das ist die beabsichtigte Korrektur, senkt
  aber die beobachtbare Fehlerrate aus diesem Pfad für jede Monitoring-Logik, die sich
  darauf verlässt (kein bekannter Konsument tut das).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reine Fehlerbehandlungs-Symmetrisierung innerhalb einer bereits
  bestehenden, einzigen Transport-Funktion (`_dial_and_send()`, seit #1412 S3a der
  eine Ort für alle drei Versandwege) — keine neue Entscheidungsfläche (Kanäle,
  Provider, Datenmodell, Auth), daher kein eigenes ADR nötig.

## Changelog

- 2026-08-09: Initial spec created (Issue #1426)
- 2026-08-09: Implementation completed — `EmailOutput._dial_and_send()` unified recipient handling across all three fallback paths; central success check added for total rejection detection. Status: done
