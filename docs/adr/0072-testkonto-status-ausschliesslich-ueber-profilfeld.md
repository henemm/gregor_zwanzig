# ADR-0072: Der Testkonto-Status eines Nutzers kommt ausschließlich aus dem Profilfeld `is_test_user` — die Namens-Heuristik entfällt ersatzlos

- **Status:** Akzeptiert (löst die Known Limitation aus ADR-0028 „Konsequenzen" ab)
- **Datum:** 2026-09-18
- **Bezug:** GitHub-Issue #2152 (Epic #2138), Spec `docs/specs/modules/testkonto_profilfeld.md`

## Kontext

Ob ein Konto ein Testkonto ist, entschied bisher in Go (`model.IsTestUserID`,
`mail.IsTestUser`) und Python (`is_test_user_id`) eine Namens-Heuristik: enthält
die Nutzer-ID „test" oder „tdd" (case-insensitive), gilt sie als Testkonto.
Testkonten werden vom Scheduler-Fan-out übersprungen, aus Adress-Eigentum und
Chat-ID-Zuordnung ausgenommen und im Mail-Versand auf Test-SMTP geroutet.

Die Heuristik traf in beide Richtungen falsch: Ein echter Nutzer namens
„protester" oder „mattdd" bekam stumm keinen Versand mehr (False Positive), die
tatsächlichen Projekt-Testkonten `admin` (Playwright) und `validator-issue110`
liefen als echte Nutzer mit (False Negative — von ADR-0028 vorhergesagt). Das
Profilfeld `is_test_user` existierte nur in Python als Leser; im Go-Modell fehlte
es, und `SaveUser` verschluckte es bei jedem Speichern.

## Entscheidung

1. **Profilfeld als einzige Quelle.** `model.User` trägt `IsTestUser bool`
   (`json:"is_test_user,omitempty"`). Testkonto ist genau, wessen Profil dieses
   Feld auf `true` setzt — in Go `model.IsTestAccount(u *User)`, in Python
   `is_test_user_id(user_id, data_dir)`. Beide lesen dasselbe Feld.
2. **Eine feste Ausnahme.** Die dokumentierte Telegram-E2E-Fixture-ID
   `tg-live-e2e` bleibt Testkonto auch ohne Feld (case-insensitive, Issue #1013).
3. **Kein Fallback auf den Namen.** Fehlt das Feld, ist das Konto ein echter
   Nutzer. Ein „Heuristik, wenn Feld fehlt" hätte „protester" weiterhin gefangen.
   `IsTestUserID` und `IsTestUserIDSubstringOnly` sind entfernt, nicht
   deprecated.
4. **Flag bei der Anlage setzen.** `POST /api/auth/register` akzeptiert das
   optionale Feld `is_test_user`; `scripts/setup-validator-user.sh` übergibt es.
   Ohne Setzen an der Anlagestelle reißt der Schutz bei jedem neuen Testkonto.
5. **Ein Prädikat für alle Pfade.** Auch das Mail-Routing (`mail.IsTestUser`)
   nimmt jetzt das geladene Profil. Die frühere Sonderbehandlung, `tg-live-e2e`
   im Mail-Pfad NICHT als Testkonto zu führen (#1265 Fix-Loop 1), entfällt.
6. **Fehlerpolitik je Leseort.** Im Scheduler-Fan-out ist ein unlesbares Profil
   fail-open (Nutzer wird bedient, mit Log) — ein Ladefehler darf keinen echten
   Nutzer stumm schalten. `forEachRealAccount` bleibt fail-closed (Fehler bricht
   ab), weil dort ein übersehenes Konto die Adress-Eindeutigkeit kippen würde.
   Weil die Klassifikation dort jetzt das geladene Profil braucht, steht das
   Laden vor dem Überspringen: eine unlesbare `user.json` bricht seither auch
   beim Fixture-Konto `tg-live-e2e` ab, das früher rein per Namen übersprungen
   wurde. Bewusste Verhaltensänderung — was sich nicht lesen lässt, lässt sich
   nicht als Testkonto einstufen.

## Verworfene Alternativen

- **409 bei Registrierung mit „test"/„tdd" im Namen (Vorschlag aus dem Ticket).**
  Verworfen: blockiert Projekt-Testkonten am Registrierungspfad und entscheidet
  weiter auf der falschen Quelle (Name statt Flag).
- **Heuristik als Fallback behalten, wenn das Feld fehlt.** Verworfen: erhält
  genau den False Positive, den dieses ADR beseitigt (Bestandsprofile haben das
  Feld nicht).
- **Migrations-Skript für Bestandskonten.** Verworfen: Staging trägt nur
  `default`, `tg-live-e2e`, `validator-issue110`; das Fixture-Konto ist
  Konstante. Der Prod-Bestand wird im Deploy-Schritt gegen die alte Heuristik
  geprüft und nur bei echtem Treffer einmalig per Datei nachgetragen.

## Konsequenzen

- **Positiv:** Ein Nutzer wird nie mehr wegen seines Namens stumm geschaltet;
  Testkonten mit neutralem Namen (`admin`, `validator-issue110`) lassen sich
  korrekt kennzeichnen. Go und Python tragen dasselbe Prädikat.
- **Negativ / Preis:** Ein Konto, das bisher zufällig über die Heuristik als
  Testkonto lief und weiterhin so behandelt werden soll, braucht das Feld manuell
  — sonst kippt es beim Deploy von „übersprungen" auf „bedient". Die
  Registrierung ist öffentlich: jeder kann sich mit `is_test_user: true` selbst
  zum Testkonto erklären (kein Fan-out, kein Adress-Eigentum) — dieselbe Lücke
  bestand bisher über einen Namen mit „test"; keine Verschlechterung, aber kein
  Schutz.
- **Folgepflichten:** Jedes neue Projekt-Testkonto muss mit `is_test_user: true`
  angelegt werden (Register-Body). Wer ein weiteres festes Fixture-Konto
  braucht, erweitert `IsTestAccount`/`is_test_user_id` symmetrisch in beiden
  Schichten. ADR-0028 bleibt in Kraft; nur seine Known Limitation ist abgelöst.
  `docs/specs/modules/password_reset_mail.md` (Known Limitation „IsTestUser
  substring match") ist mit diesem ADR revidiert.
