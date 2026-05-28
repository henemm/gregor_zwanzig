# User-Story: Orts-Vergleich

## Wer ist der Nutzer?

Jemand, der seinen Aufenthalt in einem Urlaubsgebiet — einer Berghütte, einem Skiort, einem Wandertal — vorbereitet. Weil er vor Ort keinen bequemen Zugang zu Wetterinfos hat (langsames Internet), oder weil er einfach den Komfort eines persönlichen täglichen Wetterbriefings schätzt. Er kennt seine Alternativen (Skigebiet oder Gletscher, Wanderung im Tal oder Gipfelbesteigung) und möchte jeden Morgen auf einen Blick sehen, was die bessere Option für den Tag ist.

## Was will er?

Jeden Morgen eine E-Mail in der Inbox, die ihm klar sagt: **„Option X ist heute am besten — weil…"** Er schaut während des Urlaubs nicht auf die Website.

## Wie bereitet er das vor?

**Einmalig, vor dem Urlaub:**

1. Er legt seine Kandidaten an — die Orte, zwischen denen er üblicherweise wählt (z.B. 3–5 Wanderziele in seiner Urlaubsregion)
2. Er wählt das Aktivitätsprofil (Wandern, Skitour, Wintersport…) und bestimmt, welche Wetter-Metriken für ihn relevant sind und was für ihn ideale Werte bedeuten — in welchem Bereich ist die Temperatur angenehm, ab welcher Windstärke wird es kritisch, wie viel Regen ist noch akzeptabel
3. Er richtet ein tägliches Briefing ein: jeden Morgen eine E-Mail mit dem aktuellen Tages-Ranking

**Gelegentlich, wenn nötig:**

Vielleicht fällt ihm noch ein Ziel ein, das er ergänzen will. Oder er will das Profil anpassen. Das soll in unter einer Minute gehen — ohne sich wieder in alles einarbeiten zu müssen.

## Was bedeutet das für das Design?

Der interaktive Vergleich auf der Website ist keine eigenständige Funktion — er ist die **Vorschau beim Einrichten**. Der Nutzer gibt seine Orte ein, sieht sofort wie das Ergebnis aussehen würde, und richtet dann das tägliche Briefing ein.

- **Alles auf einmal sichtbar** (Empfehlung + Tabelle) — er will beim Einrichten sofort prüfen, ob das Ergebnis plausibel wirkt
- **Ortsauswahl:** Einmalig befüllt, danach kaum angefasst; schnelles Hinzufügen/Entfernen einzelner Orte muss reibungslos gehen
- **Mobile:** Horizontales Scrollen in der Vergleichstabelle — für gelegentliche Justierungen vom Handy
- **Kernfrage, die das Design beantworten muss:** Wie führt man den Nutzer vom „Orte einrichten" direkt zum „Briefing aktivieren", ohne dass er zwei getrennte Konzepte (Vergleich vs. Abo) unterscheiden muss?
