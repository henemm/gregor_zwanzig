// Issue #2277 S5 — reine Lade-Funktion der Karte "E-Mail-Inhalt" (MailInhaltCard.svelte).
// Aus dem Baustein ausgelagert, damit die Restore-Logik (typeof-Pruefungen, Defaults,
// Bestandsfelder) ohne onMount/$effect testbar ist (Kern-Suite ist SSR-only).

import { DEFAULT_DAILY_SUMMARY_METRICS } from './mailInhaltKonstanten.ts';

export interface MailZustand {
	email_format: 'full' | 'compact';
	show_outlook: boolean;
	show_stage_stats: boolean;
	show_yesterday_comparison: boolean;
	// Bestandsdaten-Erhalt: nicht im UI gezeigt, aber im Read-Modify-Write benoetigt.
	show_compact_summary: boolean;
	wind_exposition_min_elevation_m: number | null;
	show_quick_take_tags: boolean;
	show_stability: boolean;
	show_highlights: boolean;
	daily_summary_metrics: string[];
	show_metrics_summary: boolean;
}

const bool = (v: unknown, vorgabe: boolean): boolean => (typeof v === 'boolean' ? v : vorgabe);

/** Zustand der Karte aus dem gespeicherten report_config-Blob; fehlende/falsch typisierte Felder -> Default. */
export function ladeMailZustand(blob: object | null | undefined): MailZustand {
	const c = (blob ?? {}) as Record<string, unknown>;
	return {
		email_format: c.email_format === 'compact' || c.email_format === 'full' ? c.email_format : 'full',
		show_outlook: bool(c.show_outlook, true),
		show_stage_stats: bool(c.show_stage_stats, true),
		show_yesterday_comparison: bool(c.show_yesterday_comparison, true),
		show_compact_summary: bool(c.show_compact_summary, true),
		wind_exposition_min_elevation_m:
			typeof c.wind_exposition_min_elevation_m === 'number' ? c.wind_exposition_min_elevation_m : null,
		show_quick_take_tags: bool(c.show_quick_take_tags, true),
		show_stability: bool(c.show_stability, true),
		show_highlights: bool(c.show_highlights, true),
		daily_summary_metrics: Array.isArray(c.daily_summary_metrics)
			? [...(c.daily_summary_metrics as string[])]
			: [...DEFAULT_DAILY_SUMMARY_METRICS],
		show_metrics_summary: bool(c.show_metrics_summary, false),
	};
}
