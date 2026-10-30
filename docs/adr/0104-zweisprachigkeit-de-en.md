# ADR-0104: Zweisprachigkeit Deutsch/Englisch — Sprache am Nutzer, Kataloge je Schicht, Protokoll-Token nie übersetzen

- **Status:** Vorgeschlagen (PO-Rückfragen beantwortet 2026-10-30; Freigabe in Paket S0 #2645)
- **Datum:** 2026-10-30
- **Bezug:** Epic #2644, Plan `docs/features/epic-i18n-de-en.md`, Konventionen `docs/features/epic-i18n-de-en-konventionen.md`, Glossar `docs/reference/i18n_glossar.md`; löst die Streichung von #94 (2026-08-04) ab; ergänzt ADR-0042 (Namensform folgt der Platzgrenze), ADR-0095 (Kanal-Parität), ADR-0101 (Read-Modify-Write)
- **Ergänzt durch:** —

## Kontext

Gregor Zwanzig ist durchgehend deutsch: 256 Svelte-Dateien mit mehreren tausend deutschen
Textzeilen, 535 deutsche String-Literale in den Python-Renderern und -Diensten, 471 in der
Go-API. Ein einziger Textkatalog existiert (#2520, `frontend/src/lib/i18n`, 112 Schlüssel,
nur Deutsch, bewusst „inlang-kompatibel, kein Paraglide"). `UserPreferences.language`
(Python) existiert seit der CLI-Ära, wird aber nirgends gelesen; das Go-Nutzermodell kennt
keine Sprache; `app.html` ist fest `lang="de"`.

Issue #94 („Zweisprachigkeit") wurde 2026-08-04 gestrichen mit dem Hinweis, die Absicht lebe
in ADR-0042 weiter. ADR-0042 hält fest: „Der Dienst soll später international werden", die
SMS-Kürzel sind **bewusst englisch**, und wo wenig Platz ist, steht die englische Fachkurzform.
Die Zielgruppe (Weitwanderer, international unterwegs) spricht Englisch als Fachsprache.

PO-Auftrag 2026-10-30: Webseite **und** Nachrichten (E-Mail, Telegram) sollen Deutsch und
Englisch können; die Umsetzung erledigen Agenten, mechanische Pakete mit Haiku. Rückfragen
(per `AskUserQuestion`) ergaben: Sprache als Konto-Einstellung mit Browser-Vorbelegung;
Umfang zusätzlich Inbound-Befehle, SMS-Freitext, Go-API-Meldungen, Konto-Mails; eigener
Katalog statt Paraglide; Ablage als Epic + Sub-Issues + ADR.

## Entscheidung

1. **Die Sprache ist eine Eigenschaft des Nutzers**, nicht des Kanals, des Empfängers oder
   der Sitzung. Feld `language` ∈ {`de`, `en`} in `data/users/<id>/user.json`, geschrieben von
   der Go-API (`PUT /api/auth/profile`, Register), gelesen von Go **und** Python. Leer oder
   unbekannt bedeutet Deutsch. Jeder Kanal liefert denselben Inhalt in derselben Sprache
   (ADR-0095); es gibt **eine** Auflösungsfunktion je Schicht (`resolve_user_lang`,
   `i18n.FromContext`, `locals.lang`), keinen zweiten Weg.
2. **Nicht angemeldete Besucher und neue Konten** erhalten die Sprache aus Cookie `gz_lang`
   (Umschalter) > `Accept-Language` > Deutsch. Die Registrierung übernimmt diese Sprache ins
   Konto. Es gibt genau zwei Sprachen; weitere brauchen ein neues ADR.
3. **Drei Kataloge, eine Technik:** flache, bereichs-präfixierte Schlüssel in JSON-Dateien
   je Sprache und Bereich (`frontend/src/lib/i18n/messages/{de,en}/<bereich>.json`,
   `src/i18n/messages/{de,en}/<bereich>.json`, `internal/i18n/messages/{de,en}/<bereich>.json`);
   typisierter Zugriff `t(key, …)` mit `{name}`-Platzhaltern, Plural als `.one`/`.other`,
   Laufzeit-Fallback auf Deutsch mit einmaligem Log. **Keine neue Abhängigkeit**, kein
   Paraglide, kein gettext. Ein Paritätstest je Katalog erzwingt identische Schlüsselmengen.
4. **Was nie übersetzt wird** (ADR-0042 Klasse 1 und Eigennamen): `sms_code`,
   `compact_label`, Kürzel, die Spaltenkopf-Kurzform `col_label`, Kanalnamen, Provider-Namen,
   Orts-/Regions-/Département-Namen, Nutzertexte (Trip-Namen), amtliche Warntexte (außer die
   Quelle liefert einen englischen Block, dann wird er bei `en` bevorzugt). Ein Wächter-Test
   friert die Token ein. Die Klasse-2-Formen „voll" (`label_de`/`label_en`) und
   „Alarm-Kurzform" (`alert_label`/`alert_label_en`) werden sprachabhängig; die
   Dreier-Auflösung `Luftfeuchtigkeit · Humid · HU` bleibt in beiden Sprachen bestehen.
5. **Kurzform ist Platzform, nicht Sprache.** Der Telegram-Kurzstil und der
   Premium-SMS-Kanal (#2417, `self._en`) bleiben für `de`- und `en`-Nutzer **vollständig
   englisch wie heute** (Kürzel, Befehlswörter, Kürzel-Legende, Kurzantworten; #2417 AC-4
   „byte-gleich"). Die Nutzersprache wirkt nur in den Langform-Kanälen (E-Mail, Telegram
   Normalstil, SMS-Freitext). Inbound-Befehle werden auf allen Kanälen in beiden Sprachen
   verstanden (Festlegung Spec P10 #2673, konservative Lesart).
6. **Formate:** 24-h-Uhr in beiden Sprachen; Datum DE `Fr 30.10.`, EN `Fri 30 Oct`;
   Dezimaltrennzeichen bleibt der Punkt (SMS-Verträglichkeit); Einheiten metrisch.
7. **Wortwahl:** einfaches Englisch, Fachbegriffe wo sie der Klarheit dienen (PO, ADR-0042).
   Das Glossar `docs/reference/i18n_glossar.md` ist bindend; neue Begriffe zuerst dort.
   Das Produkt kennt keine „Tour" — auch nicht englisch (*trip*, *stage*).
8. **Ratschen:** je Schicht ein Test, der neue hartkodierte Nutzertexte außerhalb des
   Katalogs blockt (Allowlist, die nur schrumpft). Mail-Validatoren lesen den Marker
   `X-GZ-Lang` und bilden Erwartungen aus dem Katalog; nach Abschluss ist der Marker Pflicht.
9. **Bestandsdaten:** Nutzer ohne Feld bleiben deutsch und werden nicht migriert; das Feld
   entsteht per Read-Modify-Write beim ersten Setzen (ADR-0101). Deutsche Ausgaben bleiben
   byte-gleich zur heutigen Ausgabe (Golden-Vergleich je Renderer-Paket).

## Verworfene Alternativen

- **Paraglide/inlang-Compiler** — Tree-Shaking und Pluralregeln wären nett, aber die
  #2520-Entscheidung (kein Paraglide) war bewusst; der Build würde umgestellt, Haiku-Pakete
  müssten eine Fremd-Toolchain bedienen. Der eigene Katalog ist inlang-kompatibel, ein
  späterer Wechsel bleibt möglich.
- **Sprache je Empfänger-Adresse** — widerspricht „Senden heißt an die Empfänger dieses
  Nutzers" und der Kanal-Parität; niemand liest denselben Trip in zwei Sprachen.
- **Web per Browser ohne Speicherung** — Nachrichten könnten nicht folgen; zwei Quellen für
  eine Eigenschaft.
- **Englisch als Default für alle** — ADR-0042 nennt die Internationalisierung als Ziel,
  aber die heutige Nutzerschaft ist deutsch; Browser-Vorbelegung liefert beides ohne Bruch.
- **Übersetzung im Frontend für Backend-Texte** (nur `code` übertragen) — Mails und
  Telegram haben kein Frontend; Backend muss ohnehin sprechen. Der `code` wird zusätzlich
  mitgegeben, damit das Frontend vereinheitlichen kann.
- **Maschinelle Laufzeit-Übersetzung** — unvorhersehbare Fachbegriffe, kein Offline-Betrieb,
  nicht testbar.

## Konsequenzen

- **Positiv:** Internationale Nutzer; Texte an einer Stelle je Schicht statt in 900 Dateien;
  Beschriftungs-Drift (#1381/#1404/#1420) wird durch Katalog + Validator-Kopplung billiger;
  Glossar erzwingt einheitliches Vokabular auch im Deutschen.
- **Negativ / Preis:** Rund 32 Pakete; jede Nutzertext-Änderung berührt zwei Dateien; englische
  Wörter sind oft länger (Layout-Brüche, 160-Zeichen-Grenze); Validatoren und E2E brauchen
  einen zweiten Staging-Nutzer; Golden-Tests müssen gepflegt werden.
- **Folgepflichten:** Neue Nutzertexte nur über Katalog (Ratschen); Glossar vor Katalog;
  Token-Wächter bleibt; jede Mail-Änderung nimmt Validator **und** beide Sprachen in den
  Umfang; `tests/test_claude_md_budget.py` bei der CLAUDE.md-Zeile beachten; Prüfdatum für die
  Ratschen-Allowlists: leer bis Abschluss von Epic #2644, sonst Nebenbefund.
