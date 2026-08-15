// Issue #1311, Scheibe C1 von Epic #1301 — geteilter Wetter-Metriken-Tab
// (Trip UND Ortsvergleich). Pure-Function-Kern fuer WeatherMetricsTab.svelte:
// welche Abschnitte je Kontext sichtbar sind (Vorbild: alarme-tab/alarmeTabSections.ts).
//
// Spec: docs/specs/modules/compare_weather_metrics_tab.md
//   (Implementation Details Abschnitt 1, AC-1, AC-6, AC-8)
//
// D2-Fix-Loop 2 (Scheibe D2 von #1301, Staging-Befund BROKEN, AC-6): neuer
// Abschnitt 'official_alerts' — anders als die uebrigen ROUTE_ONLY_SECTIONS
// fuer BEIDE Kontexte sichtbar. Grund: der Amtliche-Warnungen-Toggle im
// geteilten Alarm-Tab entfaellt (D2 Punkt 1-5); fuer bestehende Vergleiche
// (Hub `/compare/{id}/edit` -> 307 auf den Hub, CompareInhaltSection nur im
// Anlege-Wizard erreichbar) ist der Hub-Tab "Wetter-Metriken" die einzige
// erreichbare Inhalt-Heimat fuer `official_alerts_enabled`.
// Spec: docs/specs/modules/d2_1301_official_alerts_single_control.md § Punkt 6, AC-6

// Issue #1359 Scheibe 1: 'reihenfolge' ist NICHT mehr route-exklusiv. Der
// Ortsvergleich braucht dieselbe Reihenfolge-Steuerung wie der Trip — die
// Listenposition in `display_config.active_metrics` bestimmt seit #1335/#1359
// die Zeilenfolge in HTML-Mail, Klartext und Telegram und (ueber das
// SMS-Budget) sogar, WELCHE Metriken die SMS erreichen. Damit hat der
// Abschnitt im Vergleich echte Mail-Wirkung und ist keine Attrappe (AC-8).
// Behandlung wie 'official_alerts' unten: beide Kontexte.
// Loest ab: compare_weather_metrics_tab.md § ROUTE_ONLY_SECTIONS (2026-07-18)
// Spec: docs/specs/modules/compare_metric_order.md § "Abgeloeste Festlegung"

export type WeatherMetricsContext = 'route' | 'vergleich';

// 'sms_schwellen'/'report_config' bleiben route-exklusiv: fuer sie gibt es im
// Vergleich keine Mail-Wirkung (Attrappen-Verbot).
// Issue #1728 Scheibe 2 (DEC-8): 'auswertungen' ist ENTFERNT, nicht mehr nur
// route-exklusiv. Der Bedienabschnitt "05 — Auswertungen" (Trip-Kontext)
// entfaellt ersatzlos — der zugrunde liegende Mechanismus
// (`MetricConfig.aggregations`) wirkt seit Scheibe 1
// (feat_1728_s1_temp_aufloesung) an keinem Trip-Ausgabeort mehr. Vormals hier
// (Issue #1357/#1411): 'auswertungen' war route-exklusiv, weil der Vergleich
// `display_config.metrics[].aggregations` nicht liest; diese Unterscheidung
// ist mit dem Wegfall des Abschnitts hinfaellig.
const ROUTE_ONLY_SECTIONS = ['sms_schwellen', 'report_config'] as const;

// Issue #1360 (Scheibe S1a von Epic #1372): 'stundenverlauf' ist die neue
// Heimat der Stundenverlauf-Steuerung — der Reiter "Layout" des Ortsvergleichs
// ist aufgeloest. Position: NACH 'reihenfolge', VOR 'official_alerts' (erst
// welche Tageswerte und in welcher Folge, dann der Stundenverlauf).
// Geteilt vorbereitet, in dieser Scheibe aber NUR im Vergleich aktiv: der Trip
// hat heute keine Stundenverlauf-Steuerung, sie nachzuruesten ist nicht Teil
// dieser Scheibe (Spec § Known Limitations).
const COMPARE_ONLY_SECTIONS = ['stundenverlauf'] as const;

// Issue #1361 Befund 2/#1368 (S3 Scheibe A von Epic #1372): 'ausblick' ist die
// Bedienflaeche des 3-Tages-Ausblicks (Spaltenauswahl + Reihenfolge; im
// Vergleich zusaetzlich der Ein/Aus-Schalter).
// Issue #1720 S1: fuer BEIDE Kontexte. Hier stand bis 2026-08-14 "der Trip
// bekommt bewusst keine Ausblick-Auswahlflaeche (Spec § Out of Scope)" — das
// war die ZUSCHNITTGRENZE der Lieferung #1361/#1368 ("das Epic betrifft
// ausschliesslich den Ortsvergleich"), keine Produktentscheidung; die
// Verkuerzung zu "bewusst keine" las sich wie eine dauerhafte Festlegung.
// #1720 loest sie ausdruecklich ab (PO-Auftrag 2026-08-14). Position: im
// Vergleich unveraendert direkt nach 'stundenverlauf', im Trip nach den
// route-eigenen Abschnitten — in beiden Faellen vor 'official_alerts'.
// 'stundenverlauf' bleibt compare-exklusiv (der Trip hat keine
// Stundenverlauf-Steuerung; das nachzuruesten ist nicht Teil der Scheibe).
const SHARED_TRAILING_SECTIONS = ['ausblick', 'official_alerts'] as const;

// Issue #1361/#1372 S1b: 'tagesfenster' ist NICHT kontext-exklusiv — beide
// Seiten teilen sich ab jetzt EIN Tagesfenster (dieselbe Bedienfläche, gleiche
// Position). Beim Trip zieht die Steuerung damit aus dem Versand-Reiter hierher
// (PO-Entscheidung: "Welche Stunden bewertet werden, ist eine Inhalts- und
// keine Versandfrage").
export function weatherMetricsTabSections(context: WeatherMetricsContext): string[] {
	const sections: string[] = ['grundauswahl', 'reihenfolge', 'tagesfenster'];
	if (context === 'route') sections.push(...ROUTE_ONLY_SECTIONS);
	if (context === 'vergleich') sections.push(...COMPARE_ONLY_SECTIONS);
	sections.push(...SHARED_TRAILING_SECTIONS);
	return sections;
}
