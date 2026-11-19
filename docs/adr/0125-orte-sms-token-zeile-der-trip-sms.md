# ADR-0125: Orte-SMS und Orte-Kurzstil in der Token-Schreibweise der Trip-SMS

- **Status:** Akzeptiert
- **Datum:** 2026-11-19
- **Bezug:** Issue #3172, Spec `docs/specs/modules/feat_3172_orte_sms_token_zeile.md`. **Löst ab:** die Zellform der Orte-SMS aus `docs/specs/modules/compare_kanal_metriken.md` §3 (S5b, PO-Freigabe 2026-07-29: „Eine 1:1-Nutzung von `_truncate`/`Token`/`TokenLine` selbst ist NICHT vorgesehen“), den Zähler `?N` (`sms_format.md` §5b, #1405 S3) und den Platzmangel-Zähler `+N` im Ortsteil (#1362 S5b). **Präzisiert:** ADR-0124 Nr. 3 (Kürzung vom Listenende) und Nr. 10 (Name „Orte“) für die Orte-SMS. **Löst teilweise ab:** ADR-0124 Nachtrag 1 (SMS-Kopf `{Ort} TT.MM.:` bei genau einem Ort) und die Ortsnamen in der Orte-SMS aus #3163.

## Kontext

`docs/reference/sms_format.md` nennt sich im Kopf „Single Source of Truth für die kompakte
Token-Zeile, die in allen Channels identisch verwendet wird“. Für Orte wurde das nie
umgesetzt: Seit #1362 S5b (2026-07-29) baut die Orte-SMS je Größe eine Zelle „Kürzel Leerzeichen
Wert mit Einheit“ aus den Formatierern der Nur-Text-Mail (`W 13 km/h`, `FL -5C`, `WD 33`), ohne
`@Stunde`, ohne Klammer-Spitze, mit den Zählern `+N` (verdrängt) und `?N` (kein Wert). Die Trip-SMS
schreibt dieselben Größen als Token (`W21@13`, `G26@10(31@13)`, `R-`, `PR53%@13`, `TH:-`). Der
Telegram-Kurzstil der Orte sendet denselben Text wie die Orte-SMS. Der PO hat am 2026-11-19
festgestellt, dass es nur eine Schreibweise geben soll, und die Token-Zeile der Trip-SMS als die
abschließend definierte bestätigt.

## Entscheidung

1. Die Orte-SMS (und damit Premium-SMS und Telegram-Kurzstil der Orte, die denselben Text senden)
   schreibt je Ort die **Token-Zeile der Trip-SMS**: dieselben Kürzel, dieselbe Wert-Syntax und
   dieselbe Hervorhebung nach der Abo-Ampel (`sms_format.md` §2–§5), gebaut über denselben
   Token-Baukasten (`output/tokens/builder.py::build_token_line`). Eine zweite Formatierung für
   Orte gibt es nicht mehr.
2. **Orte werden durchgezählt, nicht ausgeschrieben** (PO-Vorgabe 2026-11-19: „Die Orte dürfen in
   der SMS NICHT ausgeschrieben werden … O1: xxx O2: xxxx muss reichen“). Ortsteil = `O{n}: {Token}`
   wie das Etappen-Präfix `E{n}:` der Trip-SMS (§3.1); n = Platz in der Reihenfolge des Abos
   (gezählt über alle Orte, auch solche ohne Daten; entfallene Orte nummerieren nie um). Der Kopf
   lautet immer `Orte TT.MM.:`, auch bei genau einem Ort (`Orte 19.11.: O1: …`); ein Ort ohne Daten
   ist `O2: n/a`, lauter Orte ohne Daten ergeben `Orte: keine Daten`. Trenner `; ` zwischen Orten,
   ` +k Orte` und ` X?` am Ende bleiben. Die Ortsnamen stehen in Mail und Telegram-Normalstil; die
   Legende der Karte „Was steht wo“ erklärt `O1`.
3. **Leer- und Fehlwerte wie im Trip:** `-` = geprüft und unauffällig (unter Gelb, kein Regen,
   kein Gewitter), `?` = kein Wert vorhanden (Datenlücke). Die Zähler `?N` und `+N` im Ortsteil
   entfallen; was nicht passt, fällt wie im Trip still vom Listenende (§6).
4. **Kürzung:** alle gezeigten Orte tragen gleich viele Listenzeilen, gekürzt vom Listenende;
   erst wenn je Ort nur noch die erste Listenzeile steht, entfallen Orte (` +k Orte`, Orte ohne
   amtliche Warnung zuerst). Amtliche Warnungen (`!`-Block) und `X?` fallen zuletzt bzw. nie.
5. **Nacht `N`/`FN` und Folgetag `TH+:` entfallen bei Orten.** Ein Orte-Abo bewertet ein
   Tagesfenster am Ort; es gibt kein Etappenziel mit Nacht und keinen Folgetag im Bericht (der
   Folgetag steht im 3-Tages-Ausblick der Mail). Die Gewitter-Zeile bei Orten ist `TH:` allein.
6. Auswahl und Reihenfolge der Token kommen unverändert aus der SMS-Spalte der Tabelle „Was steht
   wo“ (ADR-0124); Roh/Einfach wirkt wie im Trip (`CT:SCT@13`).

## Verworfene Alternativen

- **Alte Zellform beibehalten und nur `-0C`/`WD 33` reparieren** — widerspricht der PO-Vorgabe
  „eine Schreibweise für alle“ und dem Kopfsatz von `sms_format.md`.
- **Volle Ortsnamen (#3163) oder auf 10 Zeichen gekürzte Namen** — volle Namen sprengen bei
  mehreren Orten das 160-Zeichen-Budget (PO 2026-11-19); gekürzte Namen kosten ebenfalls bis zu
  10 Zeichen je Ort und machen Orte mit gleichem Anfang ununterscheidbar.
- **`+N` als Platzmangel-Zähler behalten** — die Trip-SMS kennt ihn nicht; er wäre eine zweite
  Grammatik nur für Orte.
- **`N` und `TH+:` für Orte aus zusätzlichen Abrufen bilden** — braucht Daten, die das Orte-Abo
  heute nicht holt, und kostet je Ort rund 10 Zeichen im 153-Zeichen-Budget.

## Konsequenzen

- **Positiv:** Ein Leser, der die Trip-SMS kennt, liest die Orte-SMS ohne neue Regeln; `-0C` und
  die Windrichtung als Gradzahl verschwinden (Temperaturen ganzzahlig gerundet, Windrichtung als
  Himmelsrichtung `WD:NW`).
- **Negativ / Preis:** `@h(max@h)` ist länger als die alte Zelle, wenn Werte ab Gelb liegen; bei
  drei und mehr Orten stehen dann weniger Größen je Ort. Verdrängte Größen sind nicht mehr als
  `+N` gezählt (wie im Trip). Die Karte „Was steht wo“ zeigt keinen Rest-Zähler mehr.
- **Folgepflichten:** Änderungen an der Token-Grammatik gelten ab jetzt für Trip und Orte; der
  Orte-Pfad darf keine eigene Formatierung mehr einführen (ein Pendant wäre ein Verstoß wie #1170).
