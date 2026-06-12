# Context: Bug #775 — E-Mail-Interaktion „Trip nicht gefunden"

## Request Summary
Nutzerin antwortet auf eine Briefing-Mail mit `jetzt`; System antwortet
`[Hermannsweg_mit_Astrid_2026] Trip nicht gefunden`, obwohl der Trip existiert
(gespeichert als `Hermannsweg mit Astrid 2026`, mit Leerzeichen). PO-Hinweis:
„Überlege, ob der Trip-Name ideal ist oder es eher eine Trip-ID geben muss."

## Root Cause (empirisch verifiziert)
Der Mail-Betreff `[Trip Name] Etappe — Morgen — …` enthält einen Em-Dash `—`
(non-ASCII). Beim Versand RFC-2047-**Q-encoded** Python den ganzen Betreff:

```
Subject: =?utf-8?q?=5BHermannsweg_mit_Astrid_2026=5D_Etappe_1_=E2=80=94_Morgen…?=
```

Im Q-Encoding ist **Leerzeichen = `_` (Underscore)** und `[`=`=5B`, `]`=`=5D`.
Beim Reply entstehen zwei Fehlerpfade im Inbound-Reader:

| Szenario | Empfangener Betreff | Verhalten heute |
|----------|--------------------|-----------------|
| **A (latent, still-encoded)** | `Re: =?utf-8?q?=5B…=5D…?=` | `msg.get("Subject")` dekodiert **nicht** → Regex `\[…\]` findet kein `[` (es ist `=5B`) → **Mail still ignoriert**, Nutzer bekommt gar keine Antwort |
| **C (real beobachtet)** | `Re: [Hermannsweg_mit_Astrid_2026] …` (Client dekodiert Q, lässt `_` literal) | Regex extrahiert `Hermannsweg_mit_Astrid_2026` (Underscores) → Lookup `trip.name.lower() == trip_name.lower()` schlägt fehl (Leerzeichen ≠ Underscore) → **„Trip nicht gefunden"** |

Beweis siehe Roundtrip-Test in der Analyse: Python erzeugt exakt diese
Q-Kodierung; mit Underscores schlägt der exakte Namensvergleich fehl.

## Related Files
| File | Relevanz |
|------|----------|
| `src/services/inbound_email_reader.py:103` | `msg.get("Subject")` **ohne** `decode_header` → Szenario A |
| `src/services/inbound_email_reader.py:171-175` | `_extract_trip_name` Regex `\[(.+?)\]` |
| `src/services/inbound_email_reader.py:230-236` | `_find_trip_id` — exakter `.lower()`-Match, keine WS/Underscore-Normalisierung → Szenario C |
| `src/services/trip_command_processor.py:352-357` | `_find_trip` — **identische** fragile Lookup-Logik, 4× aufgerufen |
| `src/output/subject.py:103` | `head = f"[{trip_name}] {stage_name}"` — Betreff trägt den freien Namen |
| `src/outputs/email.py:46,69` | `msg["Subject"] = subject` → Python Q-encodet non-ASCII-Betreff beim Senden |
| `src/app/trip.py:172` / `internal/model/trip.go:88` | Trip-Modell: hat stabile `id` (z.B. `34ab4f37`) **und** freien `name` |
| `data/users/steffi/trips/34ab4f37.json` | echter betroffener Trip (`"name": "Hermannsweg mit Astrid 2026"`) |

## Bestehende Muster
- **#768 / 7a28a95d**: IMAP-E2E dekodiert RFC-2047-Subject (`decode_header`) **vor**
  `[TEST]`-Prüfung — exakt dasselbe Em-Dash-Problem, dort schon gelöst. Der
  Inbound-**Reader** hat diesen Fix aber nie bekommen.
- Trip hat bereits eine stabile `id` (8-stelliges Hex, Dateiname `<id>.json`).

## Dependencies
- Upstream (Betreff-Erzeugung): `subject.py` → `outputs/email.py` (Q-Encoding)
- Downstream (Kommando-Ausführung): `inbound_email_reader` → `TripCommandProcessor`
  (zweiter Lookup mit demselben fragilen Namen weitergereicht via `InboundMessage.trip_name`)

## Existing Specs
- `docs/specs/modules/inbound_command_channels.md` v1.1 (Inbound-Reader)

## Risks & Considerations
- Bereits versendete Mails in Postfächern tragen **nur den Namen** (kein ID-Token);
  ein reiner „Trip-ID-im-Betreff"-Fix hilft diesen Mails nicht.
- Betreff hat 78-Zeichen-Limit mit Truncation-Kaskade, die den Trip-Präfix als
  **erstes** wegwirft → eine ID im Präfix ist kein verlässlicher Primärschlüssel.
- Zwei Lookups müssen konsistent tolerant werden (Reader **und** Processor), sonst
  scheitert das Kommando im zweiten Schritt erneut.
- TDD-Lücke: Bestehende Inbound-Tests nutzten saubere ASCII-Betreffs ohne Em-Dash,
  daher trat das Q-Encoding-Artefakt nie auf. Der neue Test MUSS den echten
  Roundtrip (Em-Dash → MIME-Serialisierung → Reply → Extraktion → Lookup) abbilden.
