# Context: #1124 Teil B — Compare-Validator Mail-Auswahl

## Betroffener Code
- `.claude/hooks/email_spec_validator.py`, Funktion `_fetch_latest_message()` (Z. 80–108):
  - `imap.search(None, 'ALL')` → `all_ids`; nimmt `all_ids[-1]` (blind neueste Mail).
  - Fetch mit `(RFC822)` → setzt `\Seen`.
- Helper ist NICHT geteilt (nur intern genutzt via `fetch_latest_email()` und
  `_fetch_latest_message()`-Aufrufer in derselben Datei). Briefing-Validator hat eigenen Fetch.
- Test-Postfach-Credential-Priorisierung (#972) in derselben Funktion — bleibt erhalten.

## Umgebung / Nachweis
- Test-Postfach `gregor-test@henemm.com` (Stalwart, IMAP `mail.henemm.com:993`),
  Creds `GZ_TEST_IMAP_*` / `GZ_IMAP_*` aus `.env`.
- Marker-Header wird von `build_mime_message()` gesetzt; seit Teil A (live) tragen echte
  Compare-Mails `X-GZ-Mail-Type: compare`.

## Referenzen
- Issue #1124 (Kommentar #1237-Beleg: falsche Mail geprüft, Zyklen verloren).
- #1247: fehlender Date-Header (separat, nicht Teil dieses Fixes).
- Zwei-Schichten-Testpolitik (CLAUDE.md): aufgezeichnete Header-Fixtures = Kern-Schicht.
