# ADR-0095: Kanal-Parität: Jeder Kanal beantwortet jede Frage, und Alarme gibt es auf allen Kanälen

- **Status:** Akzeptiert (rückwirkend dokumentiert 2026-10-21 — gelebter Stand seit PO-Korrektur der Empfangslage 2026-09-05, Commit `11eb37077`)
- **Datum:** 2026-10-21
- **Bezug:**
  - CLAUDE.md §Projekt-Überblick („Alle vier Kanäle sind gleichrangig relevant", „Premium-SMS-Reichweite")
  - Commit `11eb37077` (2026-09-05, „Empfangslage korrigiert — unvorhersehbar statt ‚auf der Hütte nur Satellit'")
  - Epic #2133, Issue #1701 (Premium-SMS im Alarm- und Vergleichspfad, S2b, Commit `c91a08448`), Issue #2275 (Premium-SMS im Ortsvergleich-Briefing, Commit `cba919546`), Issue #1533 (Paritäts-Audit)
  - Code: `src/services/alert_channels.py`, `src/services/alert_channel_threshold.py`, `internal/model/trip.go` (`AlertChannelsConfig`/`AlertChannelThresholdsConfig`)
- **Teilweise Ablösung:**
  - ADR-0049: nur die Begründung „einziger Kanal ohne Netz" (0049:22-23, :105, :118) und der Satz „bis dahin ausdrücklich kein Alarm-Kanal" (0049:114-115)
  - ADR-0046: nur die Kanalliste „E-Mail · Telegram · SMS" (0046:46)

## Kontext

ADR-0049 (2026-08-10) begründet den vierten Kanal Premium-SMS so: Das Satellitengerät sei
unterwegs „oft der einzige erreichbare Empfangsweg" (0049:22). E-Mail und Telegram bräuchten Netz,
das „genau dort fehlt, wo das Briefing gebraucht wird". Bis zur Scheibe S2b sollte Premium-SMS
„ausdrücklich kein Alarm-Kanal" sein (0049:115). ADR-0046 (2026-08-05) führt die Kanal-Schwelle
„je Alarm-Kanal (E-Mail · Telegram · SMS)" ein (0046:46), also für drei Kanäle.

Beides ist überholt:

1. **Die Empfangslage ist unvorhersehbar** (PO-Korrektur 2026-09-05, Commit `11eb37077`). Auf der
   Hütte gibt es eher WLAN als Satellit, weil Satellit freien Himmel braucht und im Gebäude nicht
   zuverlässig trägt. Auf dem Pass gibt es normalen Handyempfang, dort werden E-Mail und Telegram
   gelesen. Die frühere Fassung „auf der Hütte nur Satellit, dort kommt nur Premium-SMS an" war
   laut CLAUDE.md falsch.
2. **Premium-SMS ist Alarm-Kanal geworden.** #1701 S2b (Commit `c91a08448`) hat sie in den Alarm-
   und den Vergleichspfad gebracht. #2275 (Commit `cba919546`) hat sie als Versandkanal ins
   Ortsvergleich-Briefing verdrahtet. Laut CLAUDE.md gilt sie heute in Trip **und**
   Ortsvergleich für alle Alarmarten, Regen- und Radar-Alarme eingeschlossen. Die Kanal-Auflösung
   ist dabei geteilt (Paritäts-Audit #1533).
3. Die Kanal-Schwelle trägt seit #1701 S2b ein viertes Feld `PremiumSms`
   (`internal/model/trip.go`, Kommentar „ADR-0046-Pflicht D6").

Keines der beiden ADRs wurde fortgeschrieben (Doku-Audit 2026-10, Punkte 1c/1d).

## Entscheidung

1. **Alle vier Kanäle sind gleichrangig: E-Mail · Telegram · SMS · Premium-SMS.** Kein Kanal
   ersetzt einen anderen. Weil niemand vorher weiß, welcher Weg gerade trägt, auch der Wanderer
   nicht, muss **jeder Kanal jede Frage beantworten können**. Die Form darf je Kanal verschieden
   sein, der Inhalt muss derselbe sein (Epic #2133). „Der Nutzer schaltet unterwegs den Kanal um"
   ist keine Lösung.
2. **Alarme können jeden der vier Kanäle erreichen** (#1701). Das gilt für alle Alarmarten
   (Δ-Abweichung, amtliche Warnung, Regen-/Radar-Alarm) und in beiden Flächen (Trip und
   Ortsvergleich). Alle Pfade laufen über dieselbe Auflösung
   `services.alert_channels.effective_alert_channels()` → `resolve_alert_channels()`, deren
   Kanalliste `_ALL_CHANNELS = ("email", "telegram", "sms", "premium_sms")` ist
   (`src/services/alert_channels.py:26`; dieselbe Liste in `src/services/alert_log.py:97`).
3. **„Alle Kanäle" heißt alle vom Nutzer gewählten Kanäle, nicht Zwangsversand auf alle vier.**
   Welche Kanäle ein Alarm tatsächlich erreicht, entscheiden weiterhin drei Dinge:
   - das Kanal-Opt-in des Nutzers (`AlertChannelsConfig`, vier `*bool`-Felder);
   - die Tarif-Gates am Ende der Auflösung: `sms_allowed()` und `premium_sms_allowed()`
     (`alert_channels.py`, Schritt 5);
   - die Kanal-Schwelle aus ADR-0046.
4. **Die Kanal-Schwelle aus ADR-0046 bleibt und gilt jetzt für vier Kanäle.**
   - `AlertChannelThresholdsConfig` führt `Email`, `Telegram`, `Sms` und `PremiumSms` mit
     demselben Feld-Merge-Muster (`internal/model/trip.go:232-237`). Trip und Ortsvergleich
     teilen den Typ (`internal/model/compare_preset.go:115`).
   - `split_by_threshold()` (`src/services/alert_channel_threshold.py:20`) prüft jeden Kanal
     des Opt-ins generisch. Ohne gesetzten Wert gilt der Startwert `LOW`.
   - Angewendet wird sie an allen sechs Nahtstellen: Trip-Δ (`trip_alert.py:3060`), Trip-Radar
     (`:2757`), Trip-amtlich (`:3385`), Ortsvergleich-Δ (`compare_alert.py:387`),
     Ortsvergleich-amtlich (`compare_official_alert.py:326`) und Ortsvergleich-Radar
     (`compare_radar_alert.py:404`).
   - Das Prinzip aus ADR-0046 („die Schwelle regelt den WEG, nicht das OB") gilt unverändert.
     Auch die Sicherung gegen die rote Linie #638 gilt unverändert: Das rohe Opt-in geht ans
     Protokoll, gefiltert wird nur der Versand.
5. **Premium-SMS bleibt ein eigener Kanal.** Gültig bleiben aus ADR-0049 der feste Absender, die
   gelernte Rückadresse mit 30-Tage-Frist, fail-closed, das eigene Tier-Gate und der gemeinsame
   seven.io-Transport. Abgelöst ist nur die Begründung „einziger Weg ohne Netz". Die Begründung
   ist jetzt: einer von vier gleichrangigen Wegen bei unvorhersehbarer Empfangslage.

## Verworfene Alternativen

- **Kanal-Rangfolge nach Empfangslage, etwa „unterwegs nur Premium-SMS":** verworfen. Die Prämisse
  ist falsch (PO-Korrektur 2026-09-05), und das System kann die Empfangslage nicht kennen.
- **E-Mail/Telegram als nachrangig behandeln:** verworfen. CLAUDE.md: „Wer daraus folgert,
  E-Mail/Telegram sind nachrangig, liegt falsch."
- **Alarm zwangsweise auf alle vier Kanäle, ohne Opt-in und Schwelle:** verworfen und nie
  gelebt. Das widerspräche ADR-0046 (der Nutzer bestimmt den Weg) und dem Tarif-Gate aus ADR-0049.
  Außerdem würde es teure Satelliten-SMS ohne Zustimmung auslösen.

## Konsequenzen

- **Positiv:**
  - Ein Kanal-Satz und eine Auflösung für alle Alarmarten und beide Flächen.
  - Eine neue Alarmart erbt die vier Kanäle und die Schwelle, wenn sie an
    `effective_alert_channels()` und `split_by_threshold()` andockt.
- **Negativ / Preis:**
  - Jede kanalgebundene Fähigkeit muss viermal gedacht werden.
  - Bekannte Paritätslücken sind nicht durch dieses ADR geschlossen:
    - Die normale SMS hat keinen Befehlseingang (Doku-Audit 2026-10, Punkt 6).
    - Die Verlässlichkeits-Aussage fehlt in SMS und Premium-SMS (ADR-0093).
    - Drei Specs schreiben noch „drei Kanäle" als Soll fest (Doku-Audit Punkt 4).
- **Folgepflichten:**
  - Jede neue Stelle, die ein Kanal-Set für den Versand auflöst, nutzt die geteilte Auflösung
    und wendet die Kanal-Schwelle an (Folgepflicht aus ADR-0046, jetzt für vier Kanäle).
  - Eine harte Dreier-Kanalliste ist ein Defekt.
  - Neue Inhalte, die nur ein Kanal trägt, brauchen eine Begründung in der Spec, warum die
    anderen Kanäle dieselbe Frage anders beantworten.
