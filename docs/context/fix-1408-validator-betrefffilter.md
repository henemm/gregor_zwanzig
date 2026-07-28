# Context: fix-1408-validator-betrefffilter

Issue #1408 · erhoben 2026-07-28 aus dem #1404-Nachweislauf

## Request Summary

`.claude/hooks/email_spec_validator.py` nimmt immer die **jüngste** Mail mit
`X-GZ-Mail-Type: compare` aus dem geteilten Test-Postfach. Parallele Sitzungen
schreiben dort ebenfalls hinein. Der Validator kann dadurch eine fremde Mail
prüfen — laut (Exit 1 gegen fremde Daten, gemessen) oder **still** (Exit 0 auf
eine Mail, die nicht aus dem geprüften Stand stammt, und die dann als Nachweis
ins Renderer-Commit-Gate #811 und in die Staging-Attestation eingeht).

## Related Files

| Datei | Relevanz |
|---|---|
| `.claude/hooks/email_spec_validator.py:111-124` | `_select_compare_uid(candidates)` — reine Auswahlfunktion, bereits testbar |
| `.claude/hooks/email_spec_validator.py:127-194` | `_fetch_latest_message(imap=None)` — IMAP-Naht vorhanden; die Auswahl ist dort **inline** wiederholt (174-181), nicht über `_select_compare_uid` |
| `.claude/hooks/email_spec_validator.py:102-108` | `_no_compare_mail_error()` — einheitliche Fehlermeldung, nennt den erwarteten Marker |
| `.claude/hooks/email_spec_validator.py:650-713` | `run_validation(min_locations)` / `main()` — kennen heute keinen Filter-Parameter |
| `.claude/hooks/briefing_mail_validator.py:546-563, 572, 605, 609-612, 685-686, 700-701` | **Vorbild**: `_message_matches()`-Prädikat, `--subject-contains`, Durchreichung, `ValueError` mit sprechender Meldung |
| `tests/tdd/test_compare_validator_mail_selection.py` | Bestehende Suite für genau diese Auswahl, inkl. `_header_bytes()`-Fixture und `_RecordingIMAPFake` — nachnutzen, nicht neu bauen |

## Existing Patterns

- `briefing_mail_validator.py` hat den Filter seit #780 — Prädikat-Funktion
  (`_message_matches`) getrennt von der Schleife, Argument optional mit
  `default=None`, „beide None → True" für Rückwärtskompatibilität, und bei
  keinem Treffer ein `ValueError`, der **nennt wonach gesucht wurde**.
- Der Compare-Validator hat dieselbe Struktur bereits vorbereitet
  (`_select_compare_uid` als reine Funktion, IMAP-Naht in
  `_fetch_latest_message`) — der Filter lässt sich einhängen, ohne die
  Architektur anzufassen.

## Dependencies

- **Aufrufer, die weiter ohne Argumente funktionieren MÜSSEN:**
  `CLAUDE.md:153`, `.claude/commands/e2e-verify.md:98`,
  `.claude/standards/email_formatting.md:191` — alle rufen ohne Filter auf.
  Ein neues Argument muss **optional** sein.
- **Abnehmer des Ergebnisses:** `renderer_mail_gate.py` (Commit-Gate über das
  `_email_validation.yaml`-Log), `staging_gate.py`-Attestation, `/e2e-verify`
  Schritt 3b.

## Zeitstempel — was verfügbar ist

Heute wird **keine** Zeitinformation gelesen. Verfügbar wären:

- **IMAP `INTERNALDATE`** — vom Server vergeben, nicht vom Absender
  beeinflussbar; erfordert ein zusätzliches Fetch-Item.
- **`Date`-Header** — steht bereits im `BODY.PEEK[HEADER]`-Ergebnis, ist aber
  absenderseitig gesetzt.

## Risks & Considerations

- **Rückwärtskompatibilität:** Die drei dokumentierten Aufrufe ohne Argumente
  müssen weiterlaufen. Ein Pflicht-Argument wäre ein Bruch.
- **Eine Alterschranke ist eine neue Blockierbedingung.** Sie kann einen bisher
  grünen Lauf rot machen. Die Fehlermeldung muss deshalb sagen, **welche** Mail
  gewählt wurde, wie alt sie ist, und wie man die Schranke bewusst ausschaltet —
  sonst tauscht man ein stilles Falsch-Grün gegen ein rätselhaftes Rot.
- **Regel-Budget:** Die Schranke ist kein neues Gate, sondern eine
  Korrektheits-Korrektur an einem bestehenden Pflicht-Validator. Trotzdem
  bekommt sie ein Prüfdatum, weil sie eine neue Ablehnungsursache einführt.
- **Dieselbe Lücke besteht in `radar_alert_mail_validator.py:175-208` und
  `official_alert_mail_validator.py:257-299`** (beide ohne Filter, ohne
  Zeitschranke). Sie sind nicht Teil dieser Lieferung: ihre Mail-Typen werden
  nicht von parallelen Compare-Tests erzeugt, das Kollisionsrisiko ist dort
  ungleich kleiner. Als Folgearbeit an #1408 vermerkt, damit es nicht verfällt.
- **Der Adversary-Nachweis muss beide Richtungen zeigen**: die benannte Mail
  wird auch dann gewählt, wenn eine jüngere fremde daneben liegt — und wenn die
  benannte fehlt, wird **hörbar** abgebrochen statt still die nächstbeste
  genommen.
