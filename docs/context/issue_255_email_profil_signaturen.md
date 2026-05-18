# Context: Email-Profil-Signaturen (Issue #255)

## Request Summary

Für die 4 Aktivitätsprofile (Wintersport, Wandern, Summer-Trekking, Allgemein) ein
verbindliches visuelles Vokabular für E-Mail-Templates festlegen: Eyebrow-Text,
Inline-SVG-Icon und Header-Variante. Ergebnis ist eine Entscheidungs-Tabelle als
GitHub-Kommentar in Issue #255.

## Voraussetzungen & Status

| Issue | Titel | Status |
|-------|-------|--------|
| #238 | Profil-Signaturen im Design-System (Frontend) | CLOSED |
| #240 | Design-Tokens in html.py | CLOSED |
| #241 | ActivityProfile durch Mail-Pipeline | CLOSED |
| #254 | Inventar (Sub-Issue 1 Vorarbeiten) | (committed, nicht geclosed?) |

## Bestehende Implementierung (zu ersetzen/ergänzen)

`src/output/renderers/email/profile_signature.py` enthält bereits:

| Profil | accent_hex | icon (aktuell Emoji) | eyebrow (aktuell) |
|--------|-----------|----------------------|--------------------|
| WINTERSPORT | #4a7fb5 | ❄ (Schneeflocke) | Wintersport |
| WANDERN | #3a7d44 | 🥾 (U+1F97E Wanderschuh) | Wandern |
| SUMMER_TREKKING | #c45a2a | 🏔 (U+1F3D4 Berg) | Sommer-Trekking |
| ALLGEMEIN | #6b675c | ◯ (U+25EF Kreis) | Allgemein |

**Problem:** Emojis in E-Mail-Clients (Outlook, ältere Gmail-Versionen) teils
nicht gerendert oder inkonsistent. Issue #255 fordert Inline-SVG-Icons.

## Anforderungen aus Issue #255

### Ergebnis-Format (Vorlage im Issue)

| Profil | Token | Eyebrow | Icon-SVG-Name | Header-Hintergrund |
|--------|-------|---------|---------------|-------------------|
| WINTERSPORT | `--g-profile-wintersport` | WINTERSPORT · PISTE | snowflake | `--g-paper` |
| WANDERN | `--g-profile-wandern` | WANDERN | boot | `--g-paper` |
| SUMMER_TREKKING | `--g-profile-summer-trekking` | ALPINE TOUR | mountaineer | `--g-paper` |
| ALLGEMEIN | `--g-profile-allgemein` | WETTER-BRIEFING | compass | `--g-paper` |

**Wichtig:** Dies ist die Vorlage — die Werte können/sollten in Phase 2/3 verfeinert werden.

### Constraints

1. Icons müssen als **inline-SVG** in HTML-Mails funktionieren (kein externe URL, kein Icon-Font)
2. Max. **2 visuelle Unterschiede** pro Profil (Marken-Kohärenz)
3. Summer-Trekking nutzt Basis-Akzent `#c45a2a` → muss sich über **Eyebrow + Icon** von
   Allgemein unterscheiden (nicht nur Farbe)
4. **Header-Hintergrund:** Issue schlägt `--g-paper` für alle vor → das wäre eine
   **Umkehrung** der aktuellen Implementierung, die `sig.accent_hex` als Header-BG nutzt

## Related Files

| Datei | Relevanz |
|-------|----------|
| `src/output/renderers/email/profile_signature.py` | Primäre Änderungsdatei: icon-Feld wird SVG |
| `src/output/renderers/email/html.py` | Header-BG evtl. anpassen (Z. 292–293) |
| `src/output/renderers/email/design_tokens.py` | Token-Konstanten für Paper/Ink |
| `docs/reference/design_system_tokens.css` | Profil-Token-Definitionen (#g-profile-*) |
| `docs/reference/design_system.md` | Design-System-Doku, §10 Aktivitätsprofile |
| `frontend/src/lib/utils/profileSignature.ts` | Frontend-Vorbild für Python-Port |
| `tests/tdd/test_email_profile_pipeline.py` | Bestehende Tests für profile_signature |

## Bestehendes Design-System (App.css → design_tokens.py)

Profil-Tokens:
- `--g-profile-wintersport: #4a7fb5` (kühl-blau)
- `--g-profile-wandern: #3a7d44` (wald-grün)
- `--g-profile-summer-trekking: #c45a2a` (alpin-orange = Basis-Akzent)
- `--g-profile-allgemein: #6b675c` (neutral-grau)

Paper-Token: `--g-paper: #f6f4ee` (leicht warmes Off-White)

## Entscheidung: Header-Hintergrund = --g-paper ✓

**Design-Bundle (screen-output-preview.jsx + screen-compare-email.jsx) bestätigt:**
Header = `#fbfaf6` (≈ `--g-paper`), Eyebrow-Text = `#c45a2a` (Accent-Orange), H1 = dunkel.

Die aktuelle Implementierung (farbiger Header) weicht vom Design-Spec ab.
Issue #255 hat recht: Paper-Header ist korrekt.

**Konsequenz für SVG-Icons:** Auf hellem Hintergrund müssen Icons die Profil-Akzentfarbe
verwenden (nicht weiß), z.B. Schneeflocke in `#4a7fb5` (blau) für Wintersport.

## Deliverables

1. **GitHub-Kommentar** in Issue #255: Entscheidungs-Tabelle mit finalen Werten
2. **Code-Änderung** `profile_signature.py`: icon-Feld von Emoji → SVG-String
3. **Eyebrow-Texte** aktualisieren (falls abweichend von aktuell)
4. **Tests** aktualisieren (`test_email_profile_pipeline.py`)

## Risiken

- SVG-Strings in Python-Dataclass können länglich werden → ggf. separate SVG-Konstanten
- Outlook-Kompatibilität von SVG: Gmail + Apple Mail ok, Outlook 2016 nutzt kein SVG
  → Fallback nötig (Unicode-Glyph oder leer)
- Summer-Trekking ↔ Allgemein-Differenzierung: Beide neutral-warm ohne dominante Farbe
  → Eyebrow muss klar unterscheidbar sein ("ALPINE TOUR" vs. "WETTER-BRIEFING")
