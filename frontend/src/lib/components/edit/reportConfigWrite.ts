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

/** UI-State der Report-Konfig-Felder (Issue #619 + #664). */
export interface MailElementUi {
	show_stage_stats: boolean;
	show_quick_take_tags: boolean;
	show_stability: boolean;
	show_highlights: boolean;
	daily_summary_metrics: string[];
	/** Issue #664: Metriken-Überblick (ersetzt Quick-Take + Tages-Summe). Default false. */
	show_metrics_summary?: boolean;
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
	};
}
