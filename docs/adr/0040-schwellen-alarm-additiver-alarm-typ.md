# ADR-0040: Der nutzerkonfigurierte Schwellen-Alarm ist ein additiver zweiter Alarm-Typ neben dem Abweichungs-Wächter

- **Status:** Akzeptiert
- **Datum:** 2026-08-01
- **Bezug:** GitHub-Issue #1444 (Scheibe 1), Spec `docs/specs/modules/feat_1444_s1_schwellen_alarm.md`; berührt ADR-0009 (Alerts als Abweichungs-Wächter), ADR-0013 (`threshold` ist Δ-Sensitivität), ADR-0016 (amtliche Warnungen als additiver Typ), ADR-0021 (geteilte `DeviationAlertEngine`)

## Kontext

**ADR-0009 hat absolute Schwellen ausdrücklich verworfen** — mit der Begründung,
eine Warnung „bei Wind > 50 km/h" feuere bei jedem ohnehin bekannten
Schlechtwetter und erzeuge Alarm-Müdigkeit statt Signal. Seit #816 ist der
vorhandene Absolut-Pfad (`_detect_absolute_changes()`) im Versandweg deshalb
nicht defekt, sondern **bewusst stillgelegt** (`include_absolute=False`).
ADR-0013 führt ihn als Known Limitation und formuliert die Bedingung für eine
Rückkehr: *„Vor einer Reaktivierung von Absolut-Regeln muss dieser Pfad einen
eigenen Render-Vertrag bekommen."*

Dem steht ein belegter Betriebsbefund gegenüber. Der Trip „KHW 403"
(Karnischer Höhenweg, AT/IT) lief sechs Wochen mit gesetzten Wertebereichen
(`corridors[]` mit `notify: true` auf Gewitter > 0, Regen > 1 mm, Böen > 20
km/h, Temperatur min/max) und erzeugte **keinen einzigen** Gewitter- oder
Regen-Alarm. Zwei Ursachen, beide strukturell:

1. `corridor.notify` wurde von keinem Dienst gelesen — die Konfigurationsfläche
   existierte, die Wirkung nie. #1425 S2c hat daraufhin das UI-Versprechen
   entfernt statt die Funktion zu bauen; die Lücke blieb.
2. Der Abweichungs-Wächter meldet nur Vorhersage-**Sprünge**. Bei konstant
   hoher Gefahr — Alpen-Hochsommer mit täglichem Gewitterrisiko — ist er
   strukturell stumm. Im Flachland mit durchziehenden Fronten wirkte derselbe
   Wächter gut; das bestätigt die Diagnose, statt ihr zu widersprechen.

Damit steht die Annahme von ADR-0009 einer gegenläufigen Erfahrung gegenüber:
Die dort beschriebene Alarm-Müdigkeit ist real, aber sie ist nicht das einzige
Versagensmuster. **Stille bei bekannter, anhaltender Gefahr** ist das andere —
und für einen Wanderer, der über den Weitermarsch entscheidet, das gefährlichere.

## Entscheidung

ADR-0009 wird **nicht zurückgenommen**. Der Abweichungs-Wächter bleibt
unverändert das Standardverhalten für Alarme.

Daneben tritt ein **zweiter, additiver Alarm-Typ**: der nutzerkonfigurierte
**Schwellen-Alarm**. Er meldet, wenn die Vorhersage im aktiven Etappenfenster
eine vom Nutzer selbst gesetzte Grenze reißt — unabhängig davon, ob sich die
Vorhersage geändert hat. Vorbild für die Konstruktion ist ADR-0016 (amtliche
Warnungen als additiver externer Typ): ein eigener Auslöser, gebündelt in
dieselbe Nachricht, ohne den bestehenden Pfad umzubauen.

Die Abgrenzung, die ADR-0009 wahrt:

1. **Kein systemseitiger Absolutwert.** Der Schwellen-Alarm feuert
   ausschließlich dort, wo der Nutzer selbst eine Grenze gesetzt hat
   (`corridors[].notify == true`). Es gibt keine eingebauten „warne bei Wind >
   50 km/h"-Vorgaben. Der Nutzer, der keine Grenze setzt, erlebt exakt das
   Verhalten von vor dieser Entscheidung.
2. **Entprellung ist Teil der Entscheidung, nicht Beiwerk.** Die von ADR-0009
   befürchtete Alarm-Müdigkeit wird nicht in Kauf genommen, sondern konstruktiv
   ausgeschlossen: gemeldet wird eine gerissene Grenze **einmal**; erneut erst
   bei Verschärfung (ordinal: nächste Stufe; stetig: Abstand um mindestens die
   Katalog-Änderungsempfindlichkeit) oder nach zwischenzeitlicher Entspannung.
3. **Eigener Render-Vertrag** — die von ADR-0013 gestellte Bedingung wird
   erfüllt, nicht umgangen. Der Schwellen-Treffer wird **nicht** als
   `WeatherChange` mit `old_value = 0.0` durch den Δ-Renderer geschleust; er
   bekommt einen eigenen Ereignistyp und einen eigenen Wortlaut („deine Grenze
   X ist gerissen — jetzt Y"). `AlertEvent.threshold` bleibt damit unangetastet
   die Δ-Sensitivitätsschwelle.
4. **Eine Nachricht.** Schlagen beide Wächter im selben Lauf an, entsteht eine
   gebündelte Meldung, keine zwei Zustellungen. Ruhezeiten, Cooldown und
   Tages-Obergrenze gelten gemeinsam.

## Verworfene Alternativen

- **Den stillgelegten Absolut-Pfad (`_detect_absolute_changes`) reaktivieren
  und aus den Korridoren speisen.** Naheliegend, weil vorhanden. Verworfen aus
  zwei Gründen: Eine `AlertRule` kennt **eine** Grenze und **eine** Richtung,
  ein Wertebereich hat **zwei** und ist einseitig offen (`[null, 20]`) — die
  Abbildung wäre verlustbehaftet. Und der Pfad trägt die von ADR-0013 benannte
  Render-Inkompatibilität (`old_value = 0.0`) in sich; ihn einzuschalten hieße,
  genau den dort dokumentierten Fehler wieder einzuführen.
- **ADR-0009 ersetzen und Alarme generell auf absolute Schwellen umstellen.**
  Verworfen: Die dort beschriebene Alarm-Müdigkeit ist ein echtes, belegtes
  Muster. Der Betriebsbefund widerlegt ADR-0009 nicht, er ergänzt es um eine
  zweite Wetterlage. Zwei Wächter mit klar getrennten Aufgaben bilden beide
  Lagen ab; einer allein keine.
- **Nur das UI-Versprechen aus #1425 S2c wieder einblenden.** Verworfen, das
  wäre die Umkehrung des ursprünglichen Fehlers: ein Versprechen ohne Funktion.

## Konsequenzen

- **Positiv:** Die seit #1231 bestehende Konfigurationsfläche wird endlich
  wirksam. Bei anhaltender Gefahr entsteht ein Signal, wo bisher Stille war.
  Der Nutzer bestimmt die Grenze selbst — das Produkt maßt sich keine
  allgemeingültige Gefahrenschwelle an.
- **Negativ / Preis:** Zwei Alarm-Typen bedeuten zwei Melde-Gedächtnisse
  (getrennte Schlüsselräume) und einen zweiten Render-Vertrag über alle vier
  Ausgabewege (E-Mail, Telegram, SMS, Betreff). Die Meldungslogik ist damit
  breiter zu pflegen als zuvor.
- **Folgepflichten:** Jede weitere Größe, die alarmfähig wird, muss in **beiden**
  Wächtern betrachtet werden. Der Auswertungs-Baustein ist bewusst ohne
  Trip-Wissen geschnitten (ADR-0021), damit der Ortsvergleich denselben Wächter
  bekommen kann, ohne ihn nachzubauen — eine Compare-eigene Zweitfassung wäre
  ein Verstoß gegen die Trip/Compare-Teilungsregel.
- **Nicht abgedeckt:** Der Radar-Akut-Alarm (#1310) beobachtet echte Echos kurz
  vor dem Ereignis und bleibt ein eigener Weg. Ebenso unberührt bleiben
  amtliche Warnungen (ADR-0016) — sie ersetzen keinen nutzergesetzten
  Schwellwert und werden von ihm nicht ersetzt.
