# ADR-0046: Kanal-Schwelle regelt AUF WELCHEM WEG eine Meldung ankommt — nicht OB (ergänzt ADR-0043)

- **Status:** Akzeptiert (PO-„go" 2026-08-05)
- **Datum:** 2026-08-05
- **Bezug:** Issue #1461 (Epic #1458 Scheibe S3, Teilscheibe S3b-2a), Spec
  `docs/specs/modules/feat_1461_s3b2a_kanal_schwelle.md`; **ergänzt** ADR-0043
  (Empfindlichkeitsstufe als einziger Alarm-Regler); nutzt die von ADR-0043/S3a
  eingeführte Dringlichkeitsskala (`services.alert_urgency`, `LOW`/`MODERATE`/
  `HIGH`)

## Kontext

ADR-0043 legt fest, dass die Empfindlichkeitsstufe der **einzige** Regler
dafür ist, **ob** eine Wetterlage überhaupt eine Meldung wert ist — die
verworfene Alternative dort lautet wörtlich: „Zwei Regler für dieselbe Frage
sind für den Nutzer nicht erklärbar."

Issue #1461 bringt eine andere, bisher ungeregelte Frage: eine Satelliten-SMS
kostet Geld und Akku, eine E-Mail nichts — dieselbe, bereits ausgelöste
Meldung rechtfertigt auf dem einen Kanal eine Nachricht und auf dem anderen
nicht. Der PO-Wunsch (2026-08-02) ist ausdrücklich **kein** fester Vorgabewert:
„auf Telegram alles, auf Satelliten-SMS nur höchste Dringlichkeit."

Eine naive Umsetzung hätte einen zweiten Regler neben der Empfindlichkeitsstufe
gebaut, der ebenfalls über „meldenswert oder nicht" entscheidet — genau die
Konstellation, die ADR-0043 als nicht erklärbar verworfen hat. Die Analyse zu
S3b-2a zeigt: das ist vermeidbar, weil die Frage eine **andere** ist.

Eine zweite Falle war bereits einmal real: Am 2026-06-09 (rote Linie #638)
wurde eine Dringlichkeits-Auswahl aus der Oberfläche entfernt, weil eine
Einstellung das Gegenteil ihres Versprechens tat — der Nutzer stellte einen
Alarm ein und bekam nie einen, weil ein früher Ausstieg im Alarm-Protokoll
eine vollständig unterdrückte Meldung spurlos verschwinden ließ.

## Entscheidung

**Die Kanal-Schwelle ist ein von der Empfindlichkeitsstufe unabhängiger
Regler auf einer anderen Entscheidungsebene:**

| Regler | Beantwortet | Ort der Wirkung |
|---|---|---|
| Empfindlichkeitsstufe (ADR-0043) | **OB** eine Lage meldenswert ist | Auslösung der Meldung |
| Kanal-Schwelle (dieses ADR) | **AUF WELCHEM WEG** eine bereits ausgelöste Meldung ankommt | Kanal-Auflösung je Alarm-Typ, VOR dem Versand |

Konkret: je Alarm-Kanal (E-Mail · Telegram · SMS) stellt der Nutzer eine
Dringlichkeits-Schwelle (`LOW`/`MODERATE`/`HIGH`, Startwert `LOW`) ein. Eine
ausgelöste Meldung erreicht einen Kanal nur, wenn ihre Dringlichkeit die dort
eingestellte Schwelle erreicht oder übertrifft
(`services.alert_channel_threshold.split_by_threshold()`, Rangvergleich über
`services.alert_urgency.meets_or_exceeds()` — dieselbe Rangordnung wie
ADR-0043/S3a, keine zweite Skala).

**Die rote Linie #638 wird strukturell verhindert, nicht durch Disziplin:**
das an das Protokoll übergebene Kanal-Set bleibt das **rohe**, unveränderte
Opt-in des Nutzers — nur der tatsächliche Versand wird gefiltert. Eine durch
die Schwelle komplett unterdrückte Meldung landet dadurch weiterhin im
Alarm-Protokoll (neuer Grund `below_channel_threshold`) und erscheint im
nächsten Briefing als nicht zugestellt (die S3b-1-Sichtbarkeit, #1461).

**Die bereits bestehende, bisher feste `MIN_SMS_LEVEL`-Schwelle (Stufe 3,
orange) geht in derselben Einstellung auf, statt als zweite, unsichtbare
Schwelle danebenzustehen.** `MIN_SMS_LEVEL` filtert amtliche Warnungen im
SMS-/Telegram-**Bericht** (nicht im Alarm-Versand) und bildet begrifflich
bereits „Schwelle `MODERATE`" über dieselbe Stufen-Tabelle
(`hazard_symbols.LEVEL_LETTERS`) ab, die auch die Kanal-Schwelle nutzt — PO-
Entscheidung 2026-08-05, gegen die ursprüngliche Tech-Lead-Empfehlung, beide
getrennt zu halten. Konkret bedeutet das für den Trip-Bericht (`sms_trip.py`,
`narrow.py`): Startwert `LOW` ⇒ der Bericht zeigt künftig auch **gelbe**
(Stufe 2) amtliche Warnungen, die er vorher nie zeigte, während der
Alarm-**Versand** dadurch unverändert bleibt — „mehr Information ist nie ein
Sicherheitsproblem, weniger schon". Galt zunächst nur für Trip-Berichtspfade;
Ortsvergleichs-Berichte zogen mit S3b-2b nach (s. Nachtrag unten) — auch dort
gilt jetzt die Startschwelle „gering" statt der vormals festen Stufe 3.

## Verworfene Alternativen

- **Kanal-Schwelle als zweite Empfindlichkeitsstufe.** Verworfen: das wäre
  exakt der von ADR-0043 verworfene Doppelregler für dieselbe Frage. Die
  Kanal-Schwelle beantwortet eine andere Frage und ersetzt keinen Teil der
  Empfindlichkeitsstufe.
- **Filter an der geteilten Versand-Naht (`notification_service.
  _dispatch_alert_message()`).** Verworfen: zwei Alarm-Wege (amtliche
  Warnungen, Trip UND Ortsvergleich) laufen an dieser Naht vorbei und blieben
  ungefiltert. Die Schwelle greift stattdessen an den Stellen, an denen das
  Kanal-Set je Alarm-Typ **entsteht**.
- **Naiver Filter auf das Kanal-Set, das ans Protokoll geht.** Verworfen:
  reproduziert #638 — eine vollständig unterdrückte Meldung würde spurlos
  verschwinden, weil der frühe Ausstieg bei leerem Kanal-Set
  (`alert_log.append_entry()`) dann fälschlich greift.

## Konsequenzen

- **Positiv:** Der Nutzer bekommt die gewünschte Kontrolle („teuren Kanal nur
  bei hoher Dringlichkeit"), ohne dass ADR-0043s Prinzip „ein Regler für die
  Auslösefrage" verletzt wird. Die rote Linie #638 ist strukturell
  ausgeschlossen, nicht nur getestet.
- **Negativ / Preis:** Zwei unabhängige Regler-Ebenen (Auslösung, Zustellweg)
  erhöhen die Erklärungslast der Oberfläche — wird über die Beispielangabe im
  Picker und die Sichtbarkeit unterdrückter Meldungen im Briefing (S3b-1)
  abgefangen, nicht über einen dritten Mechanismus.
- **Folgepflicht:** Jede neue Stelle, die ein Kanal-Set für den **Versand**
  auflöst (heute: `TripAlertService._effective_alert_channels()` plus die
  Radar-Inline-Kopie), muss die Schwelle ebenfalls anwenden — sonst bleibt sie
  für den betroffenen Alarm-Typ wirkungslos, ohne dass der Nutzer das sieht
  (das exakte Risiko, das die Radar-Inline-Kopie in dieser Scheibe war).
- **Scope dieser Scheibe (S3b-2a):** nur Trips. Der Ortsvergleich hat noch
  kein Pendant zum Datenfeld und folgt als S3b-2b — bis dahin ändert sich am
  Ortsvergleich nichts.
- **Nachtrag (S3b-2b, 2026-08-06):** der Ortsvergleich hat nachgezogen —
  dasselbe Datenfeld (`AlertChannelThresholdsConfig`, kein neuer Typ) jetzt
  zusätzlich auf `ComparePreset`, an denselben drei Nahtstellen-Familien
  (Δ-Änderungsalarm, amtliche Warnung, Regenradar). Der Regenradar-Alarm des
  Ortsvergleichs war bis dahin hart auf `{"email"}` verdrahtet — diese
  Scheibe stellt ihn auf denselben Kanal-Resolver um (Verhaltensänderung,
  eigenes AC). **Zusätzlich geht auch beim Ortsvergleich die bisher feste
  `MIN_SMS_LEVEL`-Berichtsschwelle (Stufe 3, orange) in der Startschwelle
  „gering" auf** — derselbe Wechsel wie oben für den Trip-Bericht
  beschrieben, jetzt auch für `comparison.py` (`render_compare_sms`/
  `render_compare_telegram`); der Alarm-Versand bleibt davon unberührt (Details
  `docs/reference/sms_format.md` §2). Damit ist die oben offengelassene
  Scope-Lücke geschlossen; Issue #1461 ist mit S3b-2b vollständig
  abgeschlossen. Spec: `docs/specs/modules/feat_1461_s3b2b_compare_kanal_schwelle.md`.
