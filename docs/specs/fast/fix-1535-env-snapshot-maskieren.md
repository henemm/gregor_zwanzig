# Mini-Spec: #1535 — Umgebungs-Abbild in Zusicherung maskieren

**Issue:** https://github.com/henemm/gregor_zwanzig/issues/1535
**Track:** Fast Track · **Betroffen:** `tests/tdd/test_issue_1014_live_optin.py`

## Ausgangslage (gemessen, nicht vermutet)

`tests/tdd/test_issue_1014_live_optin.py:86-90` vergleicht zwei Abbilder von `os.environ`
(gefiltert auf `GZ_TELEGRAM_*`) mit **echten Werten** gegen `{}`. Wird die Zusicherung
verletzt, druckt pytest den Diff — und damit den Wert von `GZ_TELEGRAM_TEST_BOT_TOKEN`,
einen aktiven Bot-Zugang, im Klartext.

Einziger Fall im Testbestand: 34 Treffer für `dict(os.environ)`/`os.environ.copy()` in
`tests/`, davon alle übrigen reine Subprocess-Umgebungs-Vorbereitung; die 13 weiteren
`os.environ`-Zusicherungen vergleichen gegen eingespielte Fantasiewerte.

Der Austrittsweg „Claude-Sitzungsprotokoll" ist seit #1537 Scheibe 2 B durch
`secret_output_gate.py` bereits maskiert. Offen bleiben die Wege ohne Hook:
menschliches Terminal, `pytest > logfile`, angehängte Protokolle, Artefaktablagen.

## Was ändert sich

- **Teil A wird eine eigene Testfunktion** `test_live_telegram_enabled_does_not_touch_environ`
  (bisher erste Hälfte von `test_without_optin_all_live_tests_skip_and_env_unchanged`).
  Grund: der Nachweis-Test unten muss sie einzeln aufrufen können, ohne den 240-Sekunden-
  Subprocess-Lauf aus Teil B mitzuziehen.
- **Die Zusicherung vergleicht maskierte Abbilder:** Schlüsselname + SHA-256-Kurz-Hash
  (12 Zeichen) statt Wert. Ein Diff bleibt aussagekräftig (er nennt den geänderten
  Schlüssel und zeigt, dass sich der Wert geändert hat), enthält aber keinen Zugang.
- **`== {}` fällt weg, `before == after` bleibt.** Die Aussage von AC-1 aus
  `docs/specs/modules/issue_1014_telegram_live_optin.md` lautet „`os.environ` bleibt
  unverändert" — das ist `before == after`. Das zusätzliche `== {}` prüft nicht die
  Funktion, sondern den Zufallszustand der Umgebung: es wird rot, sobald irgendeine
  `GZ_TELEGRAM_*`-Variable gesetzt ist, die mit dem Opt-in nichts zu tun hat
  (`GZ_TELEGRAM_TEST_BOT_TOKEN`). Genau dieses Übermaß ist die Ursache dafür, dass der
  Test auf dem Server rot wird und dabei den Zugang druckt.
- **Der prüfrelevante Teil von `== {}` bleibt erhalten:** eine eigene Zusicherung, dass
  keiner der vier **opt-in-relevanten** Schlüssel (`GZ_TELEGRAM_LIVE`,
  `GZ_TELEGRAM_BOT_TOKEN`, `GZ_TELEGRAM_CHAT_ID`, `GZ_TELEGRAM_TEST_CHAT_ID`) gesetzt ist —
  geprüft über **Schlüsselnamen**, nie über Werte.

## Was darf sich nicht ändern

- Teil B (isolierter Subprocess-pytest-Lauf über die Live-Dateien, Proxy-Blockade,
  `_clean_subprocess_env`) bleibt inhaltlich unangetastet.
- AC-1 von #1014 bleibt vollständig gedeckt: „ohne `GZ_TELEGRAM_LIVE` werden alle
  Live-Tests übersprungen und `os.environ` bleibt unverändert."
- Kein Produktivcode wird angefasst — die Änderung liegt ausschließlich in `tests/`.
- Es entsteht **kein** neues Gate und keine neue Pflicht-Regel (PO-Entscheid Intake
  2026-08-10: nur die Stelle fixen, kein Ratschen-Test — Regel-Budget).

## Nachweis-Test (rot vor Fix, grün nach Fix)

Neue Datei `tests/unit/test_env_snapshot_assertions_mask_secrets.py` (nach Verhalten
benannt, nicht nach Issue-Nummer):

Ein Subprocess-pytest-Lauf **nur auf den Teil-A-Testknoten**, mit
`GZ_TELEGRAM_TEST_BOT_TOKEN=<Kennwert>` in der Umgebung. Zwei Zusicherungen:

1. Der Lauf endet mit Exit-Code 0 (die gesetzte Test-Bot-Variable darf den Test nicht
   rot machen — sie sagt nichts über das Opt-in aus).
2. Der **Kennwert taucht in der gesamten Ausgabe nicht auf** — weder bei Erfolg noch
   in einem Fehlerdiff.

Vor dem Fix scheitert beides: `== {}` wird durch die gesetzte Variable verletzt, und
der Diff druckt den Kennwert. Nach dem Fix greift keine der beiden Bedingungen.

Der Kennwert ist ein frei erfundener Zeichenstring, kein echter Zugang.

## Manuelle Test-Schritte

1. `GZ_TELEGRAM_TEST_BOT_TOKEN=KENNWERT-XYZ uv run pytest tests/tdd/test_issue_1014_live_optin.py::test_live_telegram_enabled_does_not_touch_environ -q`
   → grün, Ausgabe enthält `KENNWERT-XYZ` nicht.
2. `uv run pytest tests/unit/test_env_snapshot_assertions_mask_secrets.py -q` → grün.
3. `uv run pytest tests/tdd/test_issue_1014_live_optin.py -q` → unverändertes Verhalten
   für Teil B (Subprocess-Lauf über die Live-Dateien).

## Inline-Test (wird während der Implementierung geschrieben)

- [ ] `tests/unit/test_env_snapshot_assertions_mask_secrets.py` — Kennwert erscheint
      nicht in der Ausgabe, Lauf ist grün trotz gesetzter Test-Bot-Variable
