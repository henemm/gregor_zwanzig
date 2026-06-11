// Issue #619 — pure Helper für E-Mail-Elemente-Konfiguration.
// Spec: docs/specs/modules/issue_619_mail_elements_ui.md
// Exportierte Symbole werden von EditReportConfigSection.svelte und
// issue_619_report_config_write.test.ts genutzt.

/** Alle wählbaren Tages-Summe-Kennzahlen in fester Katalog-Reihenfolge. */
export const DAILY_SUMMARY_METRICS: readonly string[] = [
	'precipitation',
	'wind',
	'visibility',
	'thunder',
	'temperature',
] as const;

/** Default-Auswahl: Regen/Wind/Sicht/Gewitter aktiv, Temperatur aus (AC-2). */
export const DEFAULT_DAILY_SUMMARY_METRICS: readonly string[] = [
	'precipitation',
	'wind',
	'visibility',
	'thunder',
] as const;

/**
 * Fügt eine Metrik hinzu (on=true) oder entfernt sie (on=false).
 * Kein Duplikat beim Hinzufügen. Reihenfolge wird nach DAILY_SUMMARY_METRICS normalisiert.
 */
export function toggleDailySummaryMetric(
	current: string[],
	metric: string,
	on: boolean
): string[] {
	let updated: string[];
	if (on) {
		updated = current.includes(metric) ? [...current] : [...current, metric];
	} else {
		updated = current.filter((m) => m !== metric);
	}
	// Normalisierung: Reihenfolge nach Katalog (stabil)
	return DAILY_SUMMARY_METRICS.filter((m) => updated.includes(m));
}

/** UI-State der Report-Konfig-Felder (Issue #619 + #664 + #722). */
export interface MailElementUi {
	show_stage_stats: boolean;
	show_quick_take_tags: boolean;
	show_stability: boolean;
	show_highlights: boolean;
	daily_summary_metrics: string[];
	/** Issue #664: Metriken-Überblick (ersetzt Quick-Take + Tages-Summe). Default false. */
	show_metrics_summary?: boolean;
	/** Issue #722: E-Mail-Format. Default 'full'. */
	email_format?: 'full' | 'compact';
}

/**
 * Read-Modify-Write: original-Blob als Basis, die Felder darueber mergen.
 * Alle Fremdfelder (change_threshold_*, custom_*, enabled, morning_time, …) bleiben erhalten.
 */
export function buildMailElementWrite(
	original: Record<string, unknown>,
	ui: MailElementUi
): Record<string, unknown> & MailElementUi {
	return {
		...original,
		show_stage_stats: ui.show_stage_stats,
		show_quick_take_tags: ui.show_quick_take_tags,
		show_stability: ui.show_stability,
		show_highlights: ui.show_highlights,
		daily_summary_metrics: ui.daily_summary_metrics,
		show_metrics_summary: ui.show_metrics_summary ?? false,
		email_format: ui.email_format ?? 'full',
	};
}

// ── Issue #693: neue pure Helper ────────────────────────────────────────────

/** Zentrale Label-Map für Tages-Summe-Kennzahlen (Deutsch). Unbekannt → ''. */
export function dailySummaryMetricLabel(id: string): string {
	const labels: Record<string, string> = {
		precipitation: 'Niederschlag',
		wind: 'Wind',
		visibility: 'Sicht',
		thunder: 'Gewitter',
		temperature: 'Temperatur',
	};
	return labels[id] ?? '';
}

/**
 * Aktive IDs in Katalog-Reihenfolge zu deutschen Labels auflösen,
 * unbekannte IDs ignorieren, mit ' · ' verbinden.
 * Leere/keine gültige Auswahl → 'Keine'.
 */
export function dailySummaryMetricsSummary(ids: string[]): string {
	const labels = DAILY_SUMMARY_METRICS
		.filter((m) => ids.includes(m))
		.map((m) => dailySummaryMetricLabel(m))
		.filter((l) => l.length > 0);
	return labels.length > 0 ? labels.join(' · ') : 'Keine';
}

/**
 * Zählt aktive Boolean-Schalter der Gruppe A (Inhalts-Bausteine).
 * daily_summary_metrics zählt NICHT mit.
 */
export function countActiveContentModules(ui: MailElementUi): number {
	return [
		ui.show_stage_stats,
		ui.show_quick_take_tags,
		ui.show_metrics_summary ?? false,
		ui.show_stability,
		ui.show_highlights,
	].filter(Boolean).length;
}

/** Beschreibungen für die 5 Inhalts-Bausteine (Gruppe A). */
export const CONTENT_MODULE_DESCRIPTIONS: Record<string, { label: string; description: string }> = {
	show_stage_stats: {
		label: 'Etappen-Kennzahlen',
		description: 'Distanz, Auf-/Abstieg und maximale Höhe der Etappe als Zahlenraster.',
	},
	show_quick_take_tags: {
		label: 'Quick-Take-Chips',
		description: 'Farbige Schlagwort-Pillen oben, z. B. „Trocken", „Windig".',
	},
	show_metrics_summary: {
		label: 'Metriken-Überblick',
		description: 'Ersetzt Quick-Take-Chips und Tages-Summe durch eine farbige Pille je aktiver Metrik.',
	},
	show_stability: {
		label: 'Großwetterlage',
		description: 'Einordnung der Wetterstabilität, z. B. „stabile Hochdrucklage".',
	},
	show_highlights: {
		label: 'Zusammenfassung',
		description: 'Kurzer Fließtext mit den wichtigsten Wetter-Highlights des Tages.',
	},
};
