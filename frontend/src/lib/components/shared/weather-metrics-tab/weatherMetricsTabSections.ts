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
const ROUTE_ONLY_SECTIONS = ['sms_schwellen', 'report_config', 'nachtblock'] as const;

// Issue #1360/#1361/#1368/#1720: 'stundenverlauf' (nur Vergleich) und 'ausblick' (beide
// Kontexte) waren die Bedienflaechen fuer Stundenverlauf bzw. 3-Tages-Ausblick.
// Issue #3276 (Spec-AC-38, ADR-0124): im Ortsvergleich entfallen beide ersatzlos --
// Stellen, Formate und Ausblick-Berichte stellt der Nutzer nur noch in der Tabelle
// „Was steht wo" ein. 'stundenverlauf' gibt es damit nicht mehr; 'ausblick' bleibt
// bis #3297 im Trip (Position unveraendert: nach den route-eigenen Abschnitten,
// vor 'official_alerts').
const ROUTE_TRAILING_SECTIONS = ['ausblick'] as const;
const SHARED_TRAILING_SECTIONS = ['official_alerts'] as const;

export function weatherMetricsTabSections(context: WeatherMetricsContext, bereich: WeatherMetricsBereich = 'alles'): string[] {
	const sections: string[] = ['grundauswahl', 'layout_kanal'];
	if (context === 'route') sections.push(...ROUTE_ONLY_SECTIONS, ...ROUTE_TRAILING_SECTIONS);
	sections.push(...SHARED_TRAILING_SECTIONS);
	if (bereich === 'alles') return sections;
	return sections.filter((s) => ZUSTELLUNGS_SECTIONS.includes(s) === (bereich === 'zustellung'));
}

// Issue #2794 S3a (Teil-PR 2): `bereich` ist ein reiner Darstellungsfilter. Der Reiter
// Wetter zeigt die Wetter-Abschnitte, der Reiter Zustellung die Zustellungs-Abschnitte;
// beide disjunkt, Vereinigung = alles (kein Element verschwindet). Ohne `bereich` = alles.
// 'reihenfolge' heisst seitdem 'layout_kanal' (Layout je Kanal); 'nachtblock' ist der
// Nacht-Block der Trip-Mail (#1721, nur route, daher in ROUTE_ONLY_SECTIONS).
export type WeatherMetricsBereich = 'wetter' | 'zustellung' | 'alles';

// Issue #2794 S3a (Teil-PR 3, Spec §6 e): die SMS-Schwellen (#624) sind Kanal-Inhalt und
// wandern in den Bereich Zustellung — der Reiter Wetter mountet keine Metrik-Oberflaeche mehr.
// Issue #3276: 'stundenverlauf' entfaellt; 'ausblick' kommt nur noch im Trip vor.
const ZUSTELLUNGS_SECTIONS: readonly string[] = ['layout_kanal', 'ausblick', 'report_config', 'nachtblock', 'sms_schwellen'];
