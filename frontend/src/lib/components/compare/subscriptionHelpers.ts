// Issue #301 Lieferung B — Subscription-Helfer.
//
// Reines Verschieben der zuvor inline im Subscriptions-Panel
// lebenden Hilfsfunktionen, damit AutoReportCard.svelte sie nutzt
// und die Logik isoliert per node:test gedeckt ist (keine Mocks).
//
// Spec: docs/specs/modules/issue_301b_auto_reports_overview.md (§1)

import type { Subscription } from '../../types.js';

// Konvention 0=Montag (authoritativ: SubscriptionForm.svelte:19 +
// subscriptions/+page.svelte:19). NICHT Sonntag-first.
const WEEKDAYS = ['Montag', 'Dienstag', 'Mittwoch', 'Donnerstag', 'Freitag', 'Samstag', 'Sonntag'];

/** Subscription → lesbares Schedule-Label (z.B. "Täglich 07:00"). */
export function scheduleLabel(sub: Subscription): string {
	if (sub.schedule === 'daily_morning') return 'Täglich 07:00';
	if (sub.schedule === 'daily_evening') return 'Täglich 18:00';
	if (sub.schedule === 'weekly') return `Wöchentlich ${WEEKDAYS[sub.weekday ?? 0] ?? ''}`;
	return sub.schedule;
}

/** Subscription → "Alle Orte" | "N Orte". */
export function locationsLabel(sub: Subscription): string {
	if (!sub.locations || sub.locations.length === 0 || sub.locations[0] === '*') return 'Alle Orte';
	return `${sub.locations.length} Orte`;
}

/** ISO-Timestamp → formatierte Zeit (de-AT) | leerer String wenn fehlend/ungültig. */
export function formatLastRun(ts: string | undefined): string {
	if (!ts) return '';
	const d = new Date(ts);
	if (isNaN(d.getTime())) return '';
	return new Intl.DateTimeFormat('de-AT', {
		day: '2-digit',
		month: '2-digit',
		year: 'numeric',
		hour: '2-digit',
		minute: '2-digit'
	}).format(d);
}

// Issue #439 — Status-Ableitung für die Übersichtsseite.
// Rein Frontend; kein Backend-Feld. Spec §2 (issue_439_compare_uebersicht.md).
export type CompareStatus = 'active' | 'paused' | 'draft';

export const STATUS_MAP = {
	active: { label: 'aktiv',    dot: 'var(--g-accent)' },
	paused: { label: 'pausiert', dot: 'var(--g-ink-3)'  },
	draft:  { label: 'draft',    dot: 'var(--g-ink-4)'  },
} as const;

export function deriveStatus(sub: Subscription): CompareStatus {
	if (!sub.name || sub.locations.length === 0) return 'draft';
	if (!sub.enabled) return 'paused';
	return 'active';
}
