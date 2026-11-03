# ADR-0107: „Orte“ statt „Ortsvergleich“ — ein Orts-Briefing gilt ab einem Ort, die Vergleichstabelle ab zwei, ohne Rangfolge

- **Status:** Vorgeschlagen
- **Datum:** 2026-11-03
- **Bezug:** Epic „Einstellungen neu“ (Scheibe S6), Kontext `docs/context/einstellungen_neu.md` §2.1, §2.2 (Karte `ein_ort`); berührt `.claude/hooks/email_spec_validator.py` (`min_locations: int = 3`, Zeilen 1096 und 1129; Prüfung Zeile 980), das Compare-Mail-Template, `docs/reference/mail_validators.md` und CLAUDE.md §„Mail-Validatoren“ (≥3 Orte); **bestätigt** ADR-0097 (Code-Teilung Trip/Ortsvergleich) und ADR-0095 (Kanal-Parität)

## Kontext

Der Ortsvergleich ist heute als Vergleich gebaut: Die Mail ist eine Vergleichstabelle, und der Mail-Validator verlangt mindestens drei Orte. Der PO will ausdrücklich **kein Ranking** und einen Bericht für **einen einzigen Ort** (Schritt 1, 2026-11-03). Wer nur wissen will, wie das Wetter auf seiner Hütte oder in seinem Heimatort wird, muss heute einen Vergleich mit Füllorten anlegen.

## Entscheidung

1. Das Produkt heißt in Oberfläche, Menü und Mails **„Orte“** (EN „Locations“). Ein Abo hat **1..n Orte**.
2. **Ein Ort** ergibt ein **Orts-Briefing**: dieselben Metriken, dieselbe Ampel, dieselben Kanäle wie beim Vergleich, aber ohne Vergleichstabelle. Ab **zwei Orten** kommt die Vergleichstabelle dazu.
3. **Kein Ranking**, kein Score, keine Rangfolge der Orte (B7 bleibt entfallen).
4. Jeder Kanal beantwortet die Frage auch für einen Ort (ADR-0095): E-Mail, Telegram, SMS, Premium-SMS.
5. Der Mail-Validator des Pfads prüft die Ortszahl gegen die Ortszahl des Abos (≥1), nicht gegen eine feste Untergrenze von 3. Der Ein-Ort-Fall wird ein eigener, validierter Mail-Zustand.
6. Interne Bezeichner (`compare`, `vergleich`, `ComparePreset`, Route `/compare`) dürfen bleiben. Umbenannt wird, was Nutzer sehen.

## Verworfene Alternativen

- **„Ortsvergleich“ bleibt, ein Ort ist ein Sonderfall:** Der Name verspricht einen Vergleich, den es bei einem Ort nicht gibt.
- **Zwei Dinge („Orts-Briefing“ und „Ortsvergleich“) mit demselben Editor:** zwei Listen und zwei Einstiege für dasselbe Datenmodell, entgegen dem Ziel „so einfach wie möglich“.

## Konsequenzen

- **Positiv:** Der häufige Fall „ein Ort“ braucht keine Füllorte mehr. Ein Begriff, eine Liste.
- **Negativ / Preis:** Compare-Mail-Template, Telegram-/SMS-Renderer und Validator brauchen den Ein-Ort-Zweig. Texte, Glossar (bisher „Ortsvergleich = location comparison“) und CLAUDE.md müssen nachgezogen werden.
- **Folgepflichten:** Validator und Mail-Template werden nur zusammen geändert (Lehre #1381/#1404/#1420). CLAUDE.md §„Mail-Validatoren“ verliert die Angabe „≥3 Orte“. Alle Texte in DE und EN (ADR-0104).
