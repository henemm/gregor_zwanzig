---
spec_file: docs/specs/modules/rework_2276_s6c_alarme.md
spec_sha256: 3f15107427e82d6da7ee471543abcbfc5351e233fcb1996c89446874d8f37672
---

# PO-Briefing: Alarme-Fläche des Ortsvergleichs auf Wertprops (rework-2276-s6c-alarme)

## Was gebaut wird

Der Alarme-Reiter im Ortsvergleich wird intern umgebaut, ohne sichtbare Änderung. Der
Baustein soll künftig nur noch übergebene Werte lesen statt direkt auf den internen
„Wizard-Speicher" zuzugreifen — Vorarbeit für die Trip/Ortsvergleich-Angleichung (#2276,
Scheibe S6c von sechs). Ob die Fallunterscheidung wirklich verschwindet oder nur umbenannt
wird, prüft diese Scheibe nicht ab.

## Definition of Done

Fertig ist es, wenn Amtliche Warnungen, Metrik-Schwellen, Kanäle, Kurzstil, Cooldown,
Ruhezeiten und Radar-Alarm im Ortsvergleich weiterhin unverändert funktionieren und
gespeichert werden — geprüft im Live-Browser, aber nur am Hub.

## Wie geprüft wird

Ein neuer Live-Browsertest am Hub deckt die Bedienung ab. Die beiden Anlege-Mounts werden
nur strukturell geprüft, nicht durch einen echten Klicktest (Details unter „Wie abgesichert
wird").

## Was sich für dich sichtbar ändert

Nichts. Amtliche Warnungen, Metrik-Schwellen, Kanäle, Kanal-Schwellen, Kurzstil, Cooldown,
Ruhezeiten und Radar-Alarm funktionieren im Ortsvergleich exakt wie heute, inklusive
Speichern und Neuladen. Der Aufwand zahlt sich nicht in einer neuen Funktion aus, sondern
darin, dass der Code danach wartbarer ist und einen Schritt näher an „Trip und Ortsvergleich
sind im Code so ähnlich wie möglich" liegt — eine von dir mehrfach bekräftigte Vorgabe.

## Abweichungen vom Ticket

- **AC-2 des Ursprungstickets** verlangte wörtlich, nach Abschluss des gesamten Umbaus
  (nicht nur dieser Scheibe) verblieben in den geteilten Bausteinen nur noch fachlich
  begründete `context===`-Verzweigungen. Diese Formulierung war, wie bereits in Scheibe S6a
  festgestellt, so nicht direkt zähl- und prüfbar. Seit S6a gilt eine geschärfte Fassung:
  „keine reinen Herkunfts-Verzweigungen (nur Quelle/Ziel unterscheidend) mehr — fachliche
  und optische Unterscheidungen bleiben." **Wichtig für dich:** Die Spec-Datei selbst
  spricht diese Ersetzung nicht offen aus — sie schreibt im Einleitungstext beiläufig
  „S6c zahlt auf AC-2 (HERKUNFT-Abbau) ein", so als wäre das schon immer die
  Ticket-Formulierung gewesen. Dass die ursprüngliche AC-2 unerfüllbar war und durch diese
  Fassung ersetzt wurde, steht nur im begleitenden Analyse-Dokument
  (`docs/context/rework-2276-s6c-alarme.md:18-19`), das dir normalerweise nicht vorgelegt
  wird. Ich habe es dir hiermit trotzdem offengelegt. In der Sache leistet die Spec, was die
  Ticket-AC-2 verlangt hat — eine Liste, die für jede der 18 betroffenen Zeilen einzeln
  begründet, warum sie fällt oder bleibt — nur die Herkunft dieser Ersetzung wird in der Spec
  selbst nicht benannt.
- **Die S6b-Regel „eine Zeile bleibt eine Zeile" wird bewusst gebrochen.** In der vorigen
  Scheibe (S6b) wurde zugesagt, Ratschen-Zeilennummern möglichst stabil zu halten. Hier fällt
  das: weil rund 24 neue Prop-Zeilen ganz oben in der Datei entstehen, verschieben sich
  zwangsläufig alle nachfolgenden Zeilennummern. Die Spec begründet das nachvollziehbar
  (Zeilenzahl künstlich stabil halten wäre Verrenkung, keine Sorgfalt) und weicht auf einen
  inhaltlichen Nachweis aus (Bedingungstext statt Zeilennummer). Das ist eine methodische
  Abweichung vom eigenen Vorgänger-Vorgehen, kein Verstoß gegen das Ticket.
- **Ein Ergebnis der Scheibe ist noch nicht endgültig festgelegt.** Ob am Ende 14 oder nur
  13 der 18 Verzweigungen tatsächlich fallen (eine einzelne Zeile, `:345`, betrifft
  eigentlich den Trip-Pfad und wird nur mitgenommen, weil sich sonst niemand mehr um sie
  kümmert), hängt von einem technischen Beweis ab, der erst in der nächsten Phase
  (Testerstellung) geführt wird. Beide Ausgänge sind in der Spec als zulässig
  dokumentiert. Das heißt: du gibst mit dieser Freigabe kein exaktes Endergebnis frei,
  sondern einen Korridor. Dazu kommt: dass diese eine Zeile (`:345`) überhaupt angefasst
  wird, bricht bereits eine zweite selbstgesetzte Regel aus der Vorgänger-Scheibe S6b —
  „`wiz`-Umstellung und Herkunfts-Abbau werden nie in derselben Änderung gekoppelt". Die
  Spec begründet den Bruch nachvollziehbar (sonst bliebe ein Waisenkind übrig, das niemand
  mehr aufräumt, weil keine spätere Scheibe diese Datei noch anfasst) und benennt ihn offen
  als bewusste Ausnahme — es ist trotzdem der zweite Regelbruch gegenüber dem eigenen
  Vorgänger-Vorgehen in dieser einen Scheibe.

## Wie abgesichert wird

- **Dass sich am Bildschirm nichts ändert**, wird nur an EINER der drei Einbettungen
  wirklich im Browser nachgestellt: am Hub (`/compare/[id]`), wo auch tatsächlich gespeichert
  wird. Dort klickt ein automatisierter Test die Alarm-Einstellungen durch, speichert, lädt
  neu und prüft, dass alles erhalten bleibt.
- **Die beiden Einbettungen auf der Anlege-Seite** (`/compare/new`, Desktop und Mobil) werden
  **nicht** im Browser geprüft, sondern nur strukturell im Code: ein automatisierter Prüfer
  liest den Quelltext und stellt sicher, dass dort weiterhin alle Bedienelemente ankommen.
  Das ist eine schwächere Absicherung als ein echter Klicktest — sie zeigt, dass die
  Verdrahtung korrekt aussieht, nicht dass ein Nutzer dort tatsächlich klicken kann. Das
  Ticket selbst schreibt keinen echten Klicktest an diesen zwei Stellen vor, aber es ist eine
  bewusste Lücke, die die Spec offen benennt.
- **Dass der interne „Speicher-Mechanismus" nur dort aktiv wird, wo er soll** (nicht
  versehentlich im Trip oder auf der leeren Anlege-Seite), wird durch einen technischen
  Test im Hintergrund geprüft, der den entsprechenden Code-Abschnitt gezielt unter drei
  verschiedenen Bedingungen laufen lässt und beobachtet, ob er sich richtig verhält.
- **Nicht abgesichert:** ein echter Nutzer-Klicktest auf der Anlege-Seite (Desktop und
  Mobil). Sollte dort durch diese Umstellung etwas kaputtgehen, würde das nicht durch einen
  automatischen Alarm auffallen, sondern erst durch einen echten Nutzer oder eine spätere
  manuelle Prüfung.

## Kritische Anmerkungen

Vier Punkte, Details unter „Die vier Anmerkungen im Einzelnen": die Absicherungslücke an
der Anlege-Seite ist real; die Spec stuft sich selbst als riskant ein; das zentrale
Nutzenversprechen (Fallunterscheidungen fallen wirklich weg statt nur umbenannt) wird von
den Tests nicht bewiesen; der Umfang liegt am oberen Rand.

## Die vier Anmerkungen im Einzelnen

Ich habe die Zeilenangaben der Spec gegen den tatsächlichen Quelltext geprüft (u. a.
`AlarmeTab.svelte:171-482`, die drei Einbettungsstellen in `CompareTabs.svelte:1044-1054`
und `CompareNewEditor.svelte:396,487`, sowie den Ratschen-Test
`context_herkunft_zweige_eingefroren.test.ts:92-109`). Alle geprüften Stellen stimmen exakt
mit der Spec überein — keine der Stichproben deckt einen Fehler in der Spec-Darstellung auf.

1. **Die Absicherungslücke an der Anlege-Seite ist real, nicht nur behauptet.** Ich habe
   bestätigt: Der dortige Klicktest (`compare-flow-navigation.spec.ts`) existiert zwar im
   Projekt, läuft aber nicht in der automatischen Prüfkette vor jedem Deploy. Sollte diese
   Umstellung an der Anlege-Seite (`/compare/new`) etwas kaputtmachen, fiele das
   voraussichtlich erst auf, wenn jemand dort tatsächlich einen neuen Ortsvergleich anlegt
   und die Alarm-Einstellungen bedient — nicht automatisch beim nächsten Software-Ausliefern.
   Das ist ein bekanntes, seit S2 bestehendes strukturelles Loch in der Prüfkette (nicht neu
   durch diese Scheibe verursacht), aber diese Scheibe verlässt sich für zwei von drei
   Bedienstellen darauf.
2. **Risikoeinstufung „mittel-hoch" ist selbst zugegeben.** Die Spec stuft sich selbst als
   riskanter ein als die Vorgänger-Scheiben (größte Einzeländerung am Ratschen-Wächter
   bisher, 14 Einträge auf einmal), weil ausgerechnet der am wenigsten geprüfte Baustein
   (Alarme, mit drei statt einer Einbettung) dran ist. Das ist eine ehrliche
   Selbsteinschätzung, aber es bedeutet: Wenn hier ein Fehler passiert, wird er
   möglicherweise nicht sofort automatisch entdeckt (siehe Punkt 1).
3. **Das zentrale Nutzenversprechen der Scheibe wird nicht wirklich geprüft.** Der
   „Was gebaut wird"-Abschnitt sagt: 14 Fallunterscheidungen sollen wegfallen — das ist die
   zentrale Behauptung dieser Scheibe. Geprüft wird das aber nur über zwei technische
   Messungen: „gibt es die Textzeile `context===...` noch im Quelltext" (Ratschen-Test) und
   „kommt das Wort `wiz` noch im Baustein vor" (AC-1). Beide Prüfungen würden auch dann grün
   ausschlagen, wenn die Fallunterscheidung nur umbenannt statt wirklich entfernt würde —
   z. B. wenn statt „ist es der Vergleich? dann von dort, sonst von hier lesen" käme „ist der
   neue Wert übergeben? dann den nehmen, sonst den alten" — im Ergebnis dieselbe doppelte
   Quelle, nur ohne das Wort `context` oder `wiz` im Text. Die Spec verbietet ausdrücklich
   nur die Variante „Wertprop wenn da, sonst wiz" (Known Limitations) — eine Variante, die
   stattdessen gegen einen lokalen Ersatzwert prüft, wäre von diesem Verbot nicht erfasst. Ob
   die Umstellung tatsächlich sauber passiert, entscheidet sich also in der Umsetzung und in
   der Prüfung durch den unabhängigen Gegenprüfer (Adversary) danach — nicht schon durch das,
   was diese Spec als Nachweis vorsieht.
4. **Der Umfang für eine Scheibe ist am oberen Rand, aber nicht verkappt zweigeteilt.**
   Geschätzt werden ca. 170 neue und 60 entfallende Code-Zeilen — unter dem intern
   festgelegten Limit von 250, aber „nicht komfortabel" (Formulierung der Spec selbst). Die
   Begründung, warum trotzdem nicht in zwei Scheiben aufgeteilt wird (die teure
   Ratschen-Umstellung müsste sonst zweimal durchlaufen werden), ist nachvollziehbar und
   deckt sich mit dem, wie die vorherigen fünf Scheiben geschnitten wurden.

## Entscheidung, um die es geht

Mit „approved" gibst du frei, dass der Alarme-Baustein im Ortsvergleich intern umgebaut
wird (kein sichtbarer Unterschied für dich oder die Nutzer), wobei zwei von drei
Bedienstellen (die Anlege-Seite) nur strukturell statt durch einen echten Klicktest
geprüft werden, das exakte Endergebnis der Aufräumzahl (13 oder 14 von 18 entfernten
Verzweigungen) erst in der nächsten Phase feststeht, und die vorgesehene Prüfung nicht
unterscheiden kann, ob eine Fallunterscheidung wirklich verschwindet oder nur unter neuem
Namen weiterlebt.
