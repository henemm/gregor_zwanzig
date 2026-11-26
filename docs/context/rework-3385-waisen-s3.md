# Context: rework-3385-waisen-s3

## Request Summary
Scheibe S3, die letzte Scheibe der Waisen-Löschung (#3385, Epic #3122, aus #3366): Alle Dateien der Gruppe S3 in `BEKANNTE_WAISEN` werden gelöscht, das sind 7 versand-tab-Dateien. Danach gibt es keine bekannten Waisen mehr; `OBERGRENZE_WAISEN` geht von 7 auf 0, die Liste ist leer. Dazu kommen:
- die toten Exporte in `versandVergleichSpeicherung` und `weatherMetricsCompareSave` (Nebenbefund aus #3020)
- die Adversary-Findings aus #3384: F001 Kopfkommentar „<=“ in `waisen_waechter.test.ts:16`; F002 die Cooldown-Rückrichtung am echten Editor (`hub_geteilte_felder_cooldown_quiet_konsistent.test.ts:42`)

## Related Files
- Analyse S3: `docs/context/rework-3366-waisen-loeschen.md`. Die größte Kopplung liegt bei Prüfstand f6, der `EINGEFROREN`-Liste und den 3 Katalogfällen in `tests/fixtures/einstellung_gleich_mail/fallliste_editor.json`, die auf `versand_telegram_je_kontext.test.ts` verweisen.
- Wächter und Lösch-Nachweis wie in #3383/#3384.
- Ratschen:
  - BESTAND 167
  - ein_katalog 422
  - ink4
  - Katalogschlüssel
  - Elementliste
  - E2E-Zählwerte, falls eine Browser-Spec nur Waisen importiert

## Existing Patterns
Vorbild sind #3383 (PR #3387) und #3384 (PR #3388):
- Messen nach dem Löschen.
- Tests mit lebendem Anteil umbauen.
- Projektwerkzeuge für Goldens und Elementliste.
- svelte-check-Baseline vorher.
- Die Katalogfälle der Mail-Fallliste dürfen nur auf existierende Tests verweisen (`test_einstellung_gleich_mail_fallliste.py`).

## Risks & Considerations
- Die Fälle in `fallliste_editor.json` sind die Einstellung-gleich-Mail-Nachweise (#3020). Wenn ein Verweis wegfällt, muss der Fall auf einen lebenden Test umgehängt werden (gruen) oder begründet als ausnahme laufen. Er darf nicht still verschwinden.
- `EinstellTabelle.svelte` und `.claude/hooks` werden nicht angefasst. Browser-Specs gehören zu #3374, außer sie importieren eine gelöschte Datei.
