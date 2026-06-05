// Issue #301 Lieferung B — Subscription-Helfer.
//
// Reines Verschieben der zuvor inline im Subscriptions-Panel
// lebenden Hilfsfunktionen, damit AutoReportCard.svelte sie nutzt
// und die Logik isoliert per node:test gedeckt ist (keine Mocks).
//
// Spec: docs/specs/modules/issue_301b_auto_reports_overview.md (§1)

import type { Subscription, ComparePreset } from '../../types.js';

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

// Issue #459 — ComparePreset-Helfer für das Auto-Briefings-Sidepanel.
// Spec: docs/specs/modules/issue_459_auto_briefings_sidepanel.md (§2)

/** ComparePreset → lesbares Zeitplan-Label. */
export function presetScheduleLabel(preset: ComparePreset): string {
	if (preset.schedule === 'daily') {
		return `Täglich ${preset.hour_from}–${preset.hour_to} Uhr`;
	}
	if (preset.schedule === 'weekly') return 'Wöchentlich';
	return 'Manuell';
}

/** ISO-Timestamp → kurzes deutsches Datum (de-DE) | "Noch kein Versand" wenn leer/ungültig. */
export function formatLastSent(iso?: string | null): string {
	if (!iso) return 'Noch kein Versand';
	const d = new Date(iso);
	if (isNaN(d.getTime())) return 'Noch kein Versand';
	return d.toLocaleDateString('de-DE', {
		day: '2-digit',
		month: '2-digit',
		year: 'numeric'
	});
}

// Issue #472 — ComparePreset-Status-Ableitung + Orte-Label für die Listenansicht.
// Spec: docs/specs/modules/issue_472_compare_list_restore.md (§2 + §6)

/** ComparePreset → Status (rein frontend-seitig abgeleitet). */
export function deriveStatusFromPreset(p: ComparePreset): CompareStatus {
	if (!p.name || p.location_ids.length === 0) return 'draft';
	if (p.schedule === 'manual') return 'paused';
	return 'active';
}

/** ComparePreset → "N Orte" */
export function presetLocationsLabel(p: ComparePreset): string {
	return `${p.location_ids.length} ${p.location_ids.length === 1 ? 'Ort' : 'Orte'}`;
}

// Issue #488 — Kebab-Aktionen für die Compare-Kachel.
// Spec: docs/specs/modules/issue_488_compare_tile_atoms.md §1
//
// Die Kebab-Komponente emittiert nur `onSelect(id)` — die Elternkomponente
// ist für API-Calls und Confirm-Dialoge zuständig. `danger: true` markiert
// destruktive Aktionen (Löschen) für rote Texteinfärbung im Menü.

export type CompareAction = { id: string; label: string; danger?: boolean };

export function compareActions(status: CompareStatus): CompareAction[] {
	if (status === 'draft') {
		return [
			{ id: 'setup', label: 'Setup fortsetzen' },
			{ id: 'delete', label: 'Löschen', danger: true }
		];
	}
	// 'active' und 'paused' liefern dieselbe Liste (Issue #611: + Archivieren)
	return [
		{ id: 'pause', label: 'Pausieren' },
		{ id: 'send', label: 'Briefing jetzt senden' },
		{ id: 'preview', label: 'Vorschau öffnen' },
		{ id: 'edit', label: 'Bearbeiten' },
		{ id: 'archive', label: 'Archivieren' },
		{ id: 'delete', label: 'Löschen', danger: true }
	];
}
