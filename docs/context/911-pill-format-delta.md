# Übersicht: METRIKEN-ÜBERBLICK Pill-Textformat — IST vs. Vorlage (#911 Issue 7)

Issue 7 verlangt im Wortlaut nur korrekte **Abstände** (→ in #911 umgesetzt, AC-7).
Der SOLL-Screenshot zeigt darüber hinaus ein **anderes Pill-Textformat**. Das ist
**nicht** Teil von #911 — hier dokumentiert für eine Folge-Entscheidung.

Quelle der IST-Pills: `build_metrics_summary_pills(...)`. Vorlage: `EmailMetricsSummary`
in `docs/design-requests/issue_911_mail_vorschau/screen-output-preview.jsx`.

## Delta-Tabelle (IST → SOLL)

| Metrik | IST | SOLL (Vorlage) |
|--------|-----|----------------|
| Temperatur / Gefühlt | **eine** Pill „Gefühlt 18-27 °C" | **zwei** Pills: „8–11°C · Max 15:00" (Temp) + „gef. min 6.6°C · 13:00" (Gefühlt), je mit Min/Max-Zeit |
| Wind | „Wind ab 13:00 · Spitze 12 km/h um 14:00" | „Wind max 12 km/h (11:00)" bzw. bei Schwelle „Wind >thr km/h ab HH · max X (HH)" |
| Böen | „Böen ab 10:00 · Spitze 27 km/h um 14:00" | „Böen max 25 km/h (12:00)" / „Böen >thr ab HH · max X (HH)" |
| Regen (mm) | „kein Regen" | „Regen ab 11:00 · 7.3 mm" / „kein Regen" |
| Regenwahrscheinlichkeit | „Regenrisiko ab 13:00 · 33 %" | „Regen-W. >50% ab 12:00 · max 68% (13:00)" / „Regen-W. max X% (HH)" |
| Gewitter | „kein Gewitter" | „Gewitter max 5% (12:00)" / „Gewitter >thr% ab HH" / „kein Gewitter" |
| Bewölkung | „Bewölkung 0-100 %" | „60–95% bewölkt · Max 12:00" |
| Sicht | „gute Sicht" | „Sicht <2 km ab 08:00 · min 1.2 km (08:00)" / „Sicht min X km (HH)" |
| UV | „UV bis 7" | „UV max 2.4 (14:00)" |
| Nullgradgrenze | „0°-**Grenze** 4230-4430 m" | „0°-**Linie** 2.310–2.550 m · Max 15:00" |
| Feuchte | (n/a) | „Feuchte >90% ab 12:00 · max 95% (12:00)" / „Feuchte X–Y% · Max HH" |
| Taupunkt | (n/a) | „Taupunkt min 5.8°C (08:00)" |
| Tiefe Wolken | „Tiefe Wolken 0-82 %" | „Tiefer Wolken max 80% (12:00)" |
| Sonne | (n/a) | „88 min Sonne" |

## Muster der Vorlage
Einheitlich „<Metrik> max/min <Wert> (<HH:00>)"; bei aktiver Schwelle
„<Metrik> >thr ab <HH> · max <Wert> (<HH>)". Eine Pill pro Metrik (Temp+Gefühlt getrennt).

## Aufwand / Risiko
Betrifft die **gemeinsame** Pill-Logik (`build_metrics_summary_pills`) — wirkt auf Inhalt,
nicht nur Optik. Daher bewusst als eigener Workflow, nicht in #911.
