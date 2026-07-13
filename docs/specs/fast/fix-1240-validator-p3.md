# Mini-Spec: fix-1240-validator-p3

Issue #1240 — Mail-Prüfregel P-3 verlangt `Gültig:` bedingungslos und würde nach der PO-Entscheidung aus #1238 korrekte Warn-Mails blockieren.

## Was ändert sich

- `.claude/hooks/official_alert_mail_validator.py`, Regel **P-3**: Die **bedingungslose Anwesenheits-Pflicht** der `Gültig:`-Zeile entfällt.
- Stattdessen prüft P-3 die **Plausibilität**, wenn die Zeile da ist: eine vorhandene `Gültig:`-Zeile muss einen echten Zeitraum tragen (Wochentag + Datum, ggf. Uhrzeit oder „ganztägig"). Ein leeres `Gültig:` oder `Gültig: unbekannt` ist ein **Fehler**.
- Damit wird die Regel im praktisch relevanten Fall **strenger**, nicht schwächer: Der Zustand, den #1238 beanstandet („Gültig: unbekannt"), fällt jetzt beim Prüfer durch, statt durchgewinkt zu werden.

**Warum die Anwesenheit nicht mehr erzwingbar ist:** Präfektur-Zugangssperren (`massif_closure.py`) und Waldbrand-Tagesstufen (`meteo_forets.py`) liefern keine `valid_from`/`valid_to`. Eine Alarm-Mail, die ausschließlich solche Warnungen enthält, trägt zu Recht keine `Gültig:`-Zeile. Der Prüfer sieht nur den Mail-Text und kann „Renderer hat die Zeile vergessen" nicht von „Quelle liefert keine Zeiten" unterscheiden — die Anwesenheit ist deshalb kein taugliches Prüfkriterium mehr, der **Inhalt** dagegen sehr wohl.

## Was darf sich nicht ändern

- P-1 (Verdict-Zeile mit N≥1), P-2 (Warnstufe), P-4 (Quelle + „abgerufen bei"), P-5 („Stand: heute"-Footer) bleiben unverändert.
- Eine Mail mit korrekten Zeitangaben (GeoSphere/Vigilance) muss weiterhin bestehen.
- Der Aufruf-Vertrag des Hooks (Exit-Codes, `--mail-type`) bleibt unverändert.

## Manuelle Test-Schritte

1. Prüfer gegen eine Warn-Mail **mit** Zeitangabe laufen lassen → Exit 0.
2. Prüfer gegen eine Warn-Mail **ohne** jede `Gültig:`-Zeile laufen lassen → Exit 0 (vorher: P-3-Fehler).
3. Prüfer gegen eine Warn-Mail mit `Gültig: unbekannt` laufen lassen → **Fehler** P-3 (vorher: bestanden).

## Inline-Test (wird während der Implementierung geschrieben)

- [ ] `tests/tdd/test_official_alert_mail_validator.py`: Zeile fehlt vollständig → bestanden
- [ ] dito: `Gültig: unbekannt` → P-3-Fehler
- [ ] dito: `Gültig: Sa 12.07. · 15:00–21:00` → bestanden (Non-Regression)
