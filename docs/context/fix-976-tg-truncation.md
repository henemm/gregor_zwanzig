# Context: fix-976-tg-truncation

## Analysis

### Type
Bug (Restfehler aus vorherigem Teilfix)

### Root Cause
`src/output/channels/telegram.py::_truncate_html` hängt HTML-Tags (`result_parts.append(match.group(0))`)
ohne Längenbudget-Prüfung an. Bei dicht gepackten kleinen Tags nahe der `max_len`-Grenze wächst das
Ergebnis über `max_len` (reproduziert: bis 4101 statt max. 4096). Das ist derselbe Fehlermodus
(`>4096 → ok:false`), den der Fix beseitigen soll → unvollständig.

Reproduktion: `('x'*filler + '<b>y</b>')*2000`, filler 1..40, auf 4096 kürzen → len bis 4101.

### Affected Files
| File | Change | Description |
|------|--------|-------------|
| src/output/channels/telegram.py | MODIFY | `_truncate_html`: Budget für öffnendes Tag (+ Schließ-Overhead) vor dem Anhängen prüfen; sonst abbrechen. Harte Invariante `len<=max_len`. |
| tests/tdd/test_telegram_output.py | MODIFY | Regressionstest: filler 1..40, `len<=4096` UND Tag-Balance. |
| tests/tdd/test_issue_976_telegram_live_truncation.py | CREATE | Echter Telegram-Live-Sendetest (>4096 HTML) — beweist API-Annahme (ok:true). GZ_TELEGRAM_LIVE-gated. |

### Scope Assessment
- Files: 1 src + 2 test
- Estimated LoC: ~+35 / -3
- Risk Level: LOW (Truncation-Edge-Case; berührt aber echten Telegram-Sendepfad → Live-Test zwingend)

### Technical Approach
Öffnende Tags nur anhängen, wenn `aktuell + len(open_tag) + (closing_overhead + len(close_of_this_tag)) <= max_len`;
sonst abbrechen und offene Tags sauber schließen. Schließende Tags sind budgetneutral. Plaintext/Kurznachricht
unverändert.

### Dependencies
Keine externen; Basis-Commit 47adccc0 (Kimis Teilfix) im Worktree.

### Open Questions
- Keine.
