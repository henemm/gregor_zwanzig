# Mini-Spec: Wintersport-Werte in der Trip-Briefing-SMS anschließen (#1450)

## Was ändert sich
- `build_token_line()` (`src/output/tokens/builder.py`): das Profil-Gate vor dem Wintersport-Block entfällt. Schneehöhe (SD), Neuschnee (NS24+), Schneefallgrenze (SL), Lawinenstufe (AV) und gefühlte Temperatur (WC) werden künftig für **jeden** Trip erzeugt — genau wie Regen, Wind, Gewitter usw. Sichtbarkeit steuert allein die normale Metrik-Auswahl im Editor (aktiviert/deaktiviert, Schwellwert). Keine Sonderbedingung "nur bei Wintersport-Trip".
- Der dadurch überflüssige `profile`-Parameter (und der lokale `Profile`-Typ in `dto.py`) entfällt; die Legacy-CLI (`src/app/cli.py`) verliert das jetzt sinnlose `profile="wintersport"`-Argument.
- Irreführender Kommentar in `sms_trip.py:410-412` wird korrigiert (er behauptet fälschlich, die Werte würden schon unterdrückt).
- Neuer Test über den echten Versandpfad (`SMSTripFormatter.format_sms()`): Schneehöhe erscheint im SMS-Text, wenn im Trip aktiviert und Schneedaten vorhanden sind. Bisher gab es dafür keinen Test — das ist der eigentliche Bug-Nachweis.

## Was darf sich nicht ändern
- Verdrängungsreihenfolge bei 160-Zeichen-Knappheit: existiert bereits (`DROP_ORDER` in `render.py`) und lässt Wintersport-Werte zuerst weichen, bevor sicherheitsrelevante Werte wie Regen/Wind/Gewitter verdrängt werden. Wird nicht angefasst.
- Abwahl im Editor (#944): wer eine Metrik deaktiviert, sieht sie weiterhin nicht in der SMS.
- Eigene Schwellwerte pro Metrik (#873), inkl. invertierter Logik bei der Schneefallgrenze (hoch = irrelevant).
- Der Mail-Pfad — dort erscheinen die Werte bereits korrekt, bleibt unverändert.

## Manuelle Test-Schritte (Staging)
1. Trip mit aktivierter Schneehöhe + Schneefallgrenze anlegen/bearbeiten.
2. Briefing-SMS auslösen (Testmail/Vorschau) — SD/SL erscheinen im Text, wenn die Vorhersage Schneedaten liefert.
3. Metrik im Editor deaktivieren → Werte verschwinden wieder aus der SMS.
4. Schwellwert setzen ("nur ab 10 cm anzeigen") → Token erscheint nur bei Überschreitung.

## Inline-Test (wird während Implementierung geschrieben)
- [ ] `SMSTripFormatter.format_sms()` liefert das SD-Token, wenn die Metrik aktiviert ist und die Vorhersage Schneedaten enthält (Bug-Nachweis: rot vor dem Fix, grün danach).
- [ ] `test_issue_944_disabled_metrics_sms.py` bleibt grün und ist nach dem Fix nicht mehr vakuum (Abwahl unterdrückt jetzt einen Token, der tatsächlich entstehen würde).
