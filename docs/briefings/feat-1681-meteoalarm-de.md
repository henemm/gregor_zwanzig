---
spec_file: /home/hem/gregor_zwanzig/.claude/worktrees/majestic-sauteeing-petal/docs/specs/modules/feat_1681_meteoalarm_de.md
spec_sha256: ed07014a7ba6ceb44c6b18e2f98e263fd18f8281ac7d6ed985f00b9cd8fcc822
---

# PO-Briefing: feat-1681-meteoalarm-de

- **Spec:** docs/specs/modules/feat_1681_meteoalarm_de.md
- **Issue:** #1681
- **Erstellt:** 2026-09-19

## Was gebaut wird

Wanderer, deren Tour durch Deutschland führt, bekommen ab jetzt amtliche Unwetterwarnungen des Deutschen Wetterdienstes genauso wie bisher schon für Österreich und Italien — auf allen vier Versandwegen.

## Definition of Done

Fertig ist es, wenn ein Testpunkt in einem deutschen Landkreis mit aktiver amtlicher Warnung diese Warnung mit Stufe, Art und Zeitraum zeigt, ein warnungsfreier deutscher Punkt korrekt als „keine Warnung" (nicht als „nicht abrufbar") erscheint, und ein Ausfall des deutschen Diensts auch nahe der österreichischen Grenze als echter Ausfall erkannt wird statt fälschlich als entwarnte Lage durchzugehen.

## Wie geprüft wird

Automatisierte Tests spielen zehn festgelegte Szenarien gegen eine aufgezeichnete Kopie eines echten deutschen Warn-Feeds durch (aktive Warnung, warnungsfreie Lage, Ausfall, Grenzfall zu Österreich, aufgehobene Warnung, und dass eine deutsche Warnung dieselben vier Versandwege zugewiesen bekommt wie eine österreichische); der tatsächliche Live-Abruf beim echten Dienst und die reale Zustellung an Empfänger werden damit nicht bewiesen, sondern erst in der separaten Prüfung auf der Vorabversion vor der Freischaltung.

## Kritische Anmerkungen

- Die Spec ändert dabei auch bereits produktives Verhalten für Italien und Österreich mit — aufgehobene Warnungen verschwinden künftig aus der Liste aktiver Warnungen —, obwohl das Ticket ausschließlich die Deutschland-Anbindung verlangt hat.
- Der eingebaute Wächter erkennt nur neu auftauchende, unbekannte Warngebiets-Kennungen; wird ein bestehender deutscher Landkreis bei einer künftigen Gebietsreform unter gleicher Kennung neu zugeschnitten, bemerkt das System das nicht und kann eine Warnung stillschweigend der falschen Gegend zuordnen.
- Der Abruf des deutschen Feeds kostet dauerhaft rund 240 MB Datenverkehr pro Tag und Umgebung, weil der Anbieter keine Kompression anbietet — diese Kostenentscheidung wurde in der Spec selbständig getroffen, ohne dass das Ticket dazu etwas vorgegeben hätte.
- Dass die eingebundenen DWD-Geodaten korrekt mit dem vorgeschriebenen Quellenvermerk gekennzeichnet sind, wird nur durch eine Dateiprüfung nachgewiesen, nicht durch einen Verhaltenstest.

## Freigabe-Frage

Sollen die deutschen Unwetterwarnungen wie beschrieben freigeschaltet werden — inklusive der Verhaltensänderung bei aufgehobenen Warnungen für Italien und Österreich, dem dauerhaften Mehrverbrauch von rund 240 MB Datenverkehr pro Tag und der bekannten Einschränkung, dass eine künftige Gebietsreform mit unveränderter Kennung nicht erkannt würde?
