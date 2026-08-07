# Herkunft dieser Mobile-Design-Vorlage

Diese Dateien stammen aus **PR #275 („Mobile-Audit 2026-05-20")**, der nie gemergt wurde und
am 2026-08-07 geschlossen worden ist. Die Vorlage selbst war davon unabhängig gültig — sie
wurde hier nachträglich gerettet, weil sie sonst nur im Diff eines geschlossenen PR gelegen
hätte.

Die zugehörige README beschreibt eine Ordnerstruktur (`project/…`), die es so nie gab. Sie ist
als Beschreibung der Vorlage zu lesen, nicht als Wegweiser durch dieses Verzeichnis.

## Was hier NICHT liegt — und warum

| Nicht übernommen | Grund |
|---|---|
| `mobile-shell.jsx` | inhaltlich **identisch** bereits unter `docs/design-requests/issue_15_atomic_design/spec/mobile-shell.jsx` |
| `screen-metrics-editor-mobile.jsx` | identisch bereits unter `docs/design/epic_331_output_layout/` |
| `screen-output-preview-mobile.jsx` | identisch bereits unter `docs/design/epic_331_output_layout/` |
| `screen-waypoint-editor-mobile.jsx` | das Repo führt unter `docs/design-requests/` eine **neuere, umfangreichere** Fassung (21,7 kB gegen 15,5 kB) — die ältere hier abzulegen hätte eine irreführende Dublette erzeugt |
| `docs/reference/design_system.md` | 🔴 die PR-Fassung ist vom Mai; an der Datei hängen seither **fünf Commits** (u.a. Farbkorrektur #277, Token-Aufräumen #541/#543/#544, Doku-Konsolidierung #1341). Ein Übernehmen hätte diese Arbeit zurückgedreht |
| 97 Screenshots, `audit/`-Werkzeug | Momentaufnahme vom Mai, **vor** den daraus abgeleiteten Korrekturen; alle acht Befund-Issues (#267–#274) sind erledigt. Bleiben im Diff des geschlossenen PR #275 dauerhaft einsehbar |

## Wofür die Vorlage taugt

Sie ist das **Soll-Bild** für die mobile Ansicht (Primärziel 375 px, sekundär 414/768) und
ausdrücklich eine Erweiterung des Desktop-Designs — keine neuen Muster, keine neuen Tokens.
Die `.jsx`-Dateien sind Entwurfsartefakte aus dem Design-Werkzeug, **kein lauffähiger Code**
(das Frontend ist Svelte). Sie dienen dem Abgleich „sieht die gebaute Ansicht so aus wie
vorgesehen", nicht der Übernahme.

Verbindlich für Kontrast- und Lesbarkeitsfragen bleibt `docs/reference/design_system.md` in
seiner **aktuellen** Fassung, nicht die `tokens-reference.css` hier — letztere ist der Stand
vom Mai.
