# ADR-0116: Premium-SMS-Rückkanal — eindeutige Zuordnung, längerer Code ohne Ablauf, Mitteilung statt PIN, getrennte Kontingente

- **Status:** Akzeptiert
- **Datum:** 2026-11-13
- **Bezug:** GitHub-Issue #2961 („Sicherheits-Härtung nach Review 2026-11", Welle 2), Spec
  `docs/specs/modules/security_haertung_2026_11_premium_sms_rueckkanal.md`; ergänzt
  [ADR-0049](0049-premium-sms-vierter-kanal.md) (Premium-SMS als vierter Kanal) und
  [ADR-0095](0095-kanal-paritaet-jeder-kanal-jede-frage.md) (jeder Kanal beantwortet jede Frage);
  löst Akzeptanzkriterium AC-2 der Spec `fix_2328_premium_sms_rueckkanal_kollision.md` in einem
  Teilsatz ab („der andere Nutzer bleibt unverändert")

## Kontext

Unterwegs schicken Nutzer Befehle per Satelliten-Nachricht (Garmin inReach) an eine Dienstnummer.
Garmin vergibt die Absendernummern aus einem **rotierenden Pool**: dieselbe Nummer kann später einem
anderen Gerät gehören. Das Konto einer Nachricht wird über (a) die gelernte Rückadresse (30 Tage
gültig, jede Nachricht frischt auf) oder (b) einen Verknüpfungscode im Text bestimmt.

Das Sicherheits-Review 2026-11 fand:

1. Ein gespeicherter frischer Treffer entschied **vor** einem mitgeschickten Code. Hatte ein
   früherer Nutzer die Nummer noch frisch gespeichert, landete die Nachricht des neuen Inhabers samt
   gültigem Code beim falschen Konto; dieselbe Nummer konnte mehreren Konten gehören, und Antworten
   und Alarme gingen an das Gerät eines Fremden.
2. Der Code hatte einen kleinen Schlüsselraum (`XX` + 3 Buchstaben + 3 Ziffern ≈ 6,2 Mio.; im Code
   stand irrtümlich „2,75e10"), lief nicht ab und wurde nur global gebremst.
3. Die Zuordnung über die Absendernummer ist das einzige Merkmal einer Nachricht; zustandsändernde
   Befehle (Briefings stoppen/pausieren, Ruhetag, Startdatum) brauchen keinen weiteren Nachweis.
4. Befehlsantworten und Alarme teilten **einen** Tageszähler (Antwort-Grenze = Limit + 3,
   Alarm-Grenze = Limit). Ein reger Rückkanal konnte das Alarm-Kontingent aufbrauchen.
5. Es gab keinen Weg, ein Gerät zu trennen, ohne den Code zu erneuern.

## Entscheidung

1. **Gültiger Code gewinnt immer.** Enthält die Nachricht einen Code, prüft Go ihn zuerst (nach
   der Bremse). Passt er zu genau einem Konto, ist das das Ziel — auch gegen einen frischen Treffer
   eines anderen Kontos. Ein falscher Code zählt als Fehlversuch, kippt aber die bestehende
   eindeutige Zuordnung des Absenders nicht (Vertipper).
2. **Eine Rückadresse gehört höchstens einem Konto.** Lernt Konto X die Nummer N, entfernt der
   Store N bei allen anderen Konten (Read-Modify-Write mit Merge, nur die zwei Rückadress-Felder;
   Vorbild Eindeutigkeit der Telegram-`chat_id`). Ausgehend sendet `PremiumSmsRecipient.for_user`
   nur, wenn N genau diesem Konto gehört; Bestandsdaten mit Doppelbelegung werden gesperrt
   (`premium_sms_no_reply_address`, bis die nächste Nachricht mit Code neu zuordnet).
3. **Code länger, aber mehrfach verwendbar und ohne Ablauf.** Neue Codes: `XX` + 5 Buchstaben +
   3 Ziffern ohne verwechselbare Zeichen (I/L/O/0/1), Schlüsselraum 23⁵ · 8³ ≈ 3,3 Mrd. (≥ 10⁹).
   Bestandscodes bleiben gültig (kein Zwangstausch); der Eingang erkennt beide Längen. Der Code
   läuft **bewusst nicht ab** und ist mehrfach verwendbar: unterwegs ist er der einzige Weg, ein
   Gerät ohne Web-Zugang neu zu verknüpfen (Garmin vergibt die Nummer je Gespräch neu, die
   gelernte Adresse verfällt nach 30 Tagen). „Code erneuern" im Konto entwertet den alten.
4. **Zweistufige Bremse.** 3 Fehlversuche je Absendernummer und gleitender Stunde (damit ein
   einzelner Absender das gemeinsame Budget nicht für alle verbraucht) und 30 Fehlversuche je
   Stunde insgesamt als Obergrenze (vorher 10). Die Absendernummer ist keine Identität; die globale
   Stufe bleibt die Sicherheitsgrenze. Bei 30/h braucht vollständiges Durchprobieren neuer Codes
   rund 12.500 Jahre, für Bestandscodes rund 24 Jahre — jeder Versuch ist eine bezahlte
   Satelliten-SMS.
5. **Mitteilung statt PIN.** Kein zusätzlicher PIN je Nachricht (Bedienbarkeit unterwegs: jedes
   Zeichen wird mühsam getippt und kostet). Stattdessen löst jeder per Premium-SMS **erfolgreich
   ausgeführte zustandsändernde** Befehl (`pause`, `stop`/`abbruch`, `weiter`, `ruhetag`,
   `startdatum`, `skip`) eine kurze Mitteilung auf den anderen eingerichteten Kanälen aus: E-Mail
   an die bestätigte Adresse und Telegram, falls verbunden — was, wann, über welchen Kanal, wie
   man es zurücknimmt, und was zu tun ist, wenn man es nicht war. Texte über den Katalog (DE/EN),
   fail-soft, über die vorhandenen Versandwege mit Empfängerschutz, höchstens 10 je Nutzer und
   UTC-Tag. Lesende Befehle lösen nichts aus; ein Wächter-Test verlangt, dass jeder Befehl
   eingestuft ist.
6. **Getrennte Kontingente.** Antworten auf eingehende Befehle zählen in den eigenen Tageszähler
   `premium_sms_reply` (Premium: 15/Tag, free/standard: 0). Ein erschöpftes Antwort-Kontingent
   sperrt keine Alarme und umgekehrt. Bestehende Zählerdateien bleiben lesbar (fehlendes Feld = 0).
7. **Verbindung trennen.** `DELETE /api/auth/premium-sms-reply` (Kennung nur aus dem
   Auth-Kontext) löscht Rückadresse und Zeitstempel; der Code bleibt bis zum Erneuern. Die
   Konto-Karte bietet dafür einen Knopf mit Rückfrage.

## Verworfene Alternativen

- **PIN je Nachricht.** Verlässlicher Nachweis, aber unterwegs teuer und fehleranfällig; die
  Mitteilung macht Missbrauch sichtbar und umkehrbar, ohne jede Nachricht zu verlängern.
- **Code mit Ablauf oder Einmal-Code.** Würde Nutzer ohne Web-Zugang nach Verfall der Rückadresse
  aussperren.
- **Bremse nur je Absendernummer.** Die Nummer ist fälschbar bzw. rotiert; allein wäre sie keine
  Grenze.
- **Gemeinsamer Zähler mit größerer Reserve.** Löst den Zielkonflikt Antwort gegen Alarm nicht.

## Konsequenzen

- **Positiv:** Keine Antworten oder Alarme mehr an ein fremdes Gerät nach Nummernwechsel; der neue
  Inhaber kann sich mit Code sofort selbst zuordnen; fremde Änderungen werden sichtbar; Alarme
  bleiben unabhängig vom Rückkanal-Verkehr zustellbar.
- **Negativ / Preis:** Kosten je Nutzer und Tag können bis zu 15 Antworten über dem bisherigen
  Deckel liegen. Bestandscodes sind bei der angehobenen globalen Bremse schwächer geschützt als
  neue (Empfehlung: erneuern). Das Ziehen der Nummer bei anderen Konten durchsucht alle Konten
  (Anzahl klein). Die Kontoanzeige des Tageskontingents zeigt Antworten (`reply_used`/
  `reply_limit`) erst, wenn die Oberfläche sie aufnimmt.
- **Folgepflichten:** Wer die Befehlsliste erweitert, stuft den Befehl in
  `src/services/premium_sms_aenderungshinweis.py` ein (Wächter-Test). Code-Format in Go
  (`premium_sms_link_code.go`) und Python (`inbound_sms_reader.py::_LINK_CODE_PATTERN`) gemeinsam
  ändern.
