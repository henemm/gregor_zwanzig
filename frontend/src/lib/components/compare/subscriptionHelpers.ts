// Issue #301 Lieferung B — Subscription-Helfer.
//
// Reines Verschieben der zuvor inline im Subscriptions-Panel
// lebenden Hilfsfunktionen, damit AutoReportCard.svelte sie nutzt
// und die Logik isoliert per node:test gedeckt ist (keine Mocks).
//
// Spec: docs/specs/modules/issue_301b_auto_reports_overview.md (§1)

import type { ComparePreset, ActivityProfile } from '../../types.js';

// Konvention 0=Montag. NICHT Sonntag-first.
const WEEKDAYS = ['Montag', 'Dienstag', 'Mittwoch', 'Donnerstag', 'Freitag', 'Samstag', 'Sonntag'];

// Issue #439 — Status-Ableitung für die Übersichtsseite.
// Rein Frontend; kein Backend-Feld. Spec §2 (issue_439_compare_uebersicht.md).
export type CompareStatus = 'active' | 'paused' | 'draft';

export const STATUS_MAP = {
	active: { label: 'aktiv',    dot: 'var(--g-accent)' },
	paused: { label: 'pausiert', dot: 'var(--g-ink-3)'  },
	draft:  { label: 'draft',    dot: 'var(--g-ink-4)'  },
} as const;

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

/**
 * Date → kompakter Versand-String "D.M. HH:00" | "manuell" wenn null.
 *
 * Issue #647 — DRY: vorher lokal in CompareStatusRow.svelte dupliziert.
 * Wird in der Home-Compare-Outbox (homeCompareTimeline) und im Compare-Hero
 * wiederverwendet.
 */
export function formatNextSend(d: Date | null): string {
	if (!d) return 'manuell';
	const pad = (n: number) => String(n).padStart(2, '0');
	return `${d.getDate()}.${d.getMonth() + 1}. ${pad(d.getHours())}:00`;
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

/**
 * Kanalanzahl → "N Kanäle" (Singular bei genau 1: "1 Kanal").
 *
 * Design-Fidelity 2026-07 Fix 1 — konsolidiert die zuvor duplizierte
 * Singular/Plural-Ternary aus CompareTabs.svelte:248 und
 * compare/[id]/+page.svelte:204 an einer Stelle.
 */
export function channelCountLabel(n: number): string {
	return `${n} ${n === 1 ? 'Kanal' : 'Kanäle'}`;
}

// Issue #488 — Kebab-Aktionen für die Compare-Kachel.
// Spec: docs/specs/modules/issue_488_compare_tile_atoms.md §1
//
// Die Kebab-Komponente emittiert nur `onSelect(id)` — die Elternkomponente
// ist für API-Calls und Confirm-Dialoge zuständig. `danger: true` markiert
// destruktive Aktionen (Löschen) für rote Texteinfärbung im Menü.

// Issue #582 — Kachel-Helfer für die Compare-Liste (Design-Fidelity 1:1).
// Spec: docs/specs/modules/issue_582_compare_list_fidelity.md

// Inline-Map statt Import aus types.ts (vermeidet value-Import-Auflösungsproblem
// bei node --experimental-strip-types, das .js nicht auf .ts mappt).
const PROFILE_LABELS: Record<string, string> = {
	allgemein:       'Allgemein',
	wintersport:     'Wintersport',
	wandern:         'Wandern',
	summer_trekking: 'Sommer-Trekking',
};

/**
 * ActivityProfile-Key → lesbares deutsches Label.
 * Case-insensitive: "SUMMER_TREKKING" == "summer_trekking" → "Sommer-Trekking".
 * Leeres/unbekanntes profil → "" (kein Platzhalter; Kachel zeigt nur "N Orte").
 */
export function presetProfileLabel(profil: ActivityProfile | string | undefined): string {
	if (!profil) return '';
	return PROFILE_LABELS[String(profil).toLowerCase()] ?? '';
}

/**
 * ComparePreset → kompaktes Rhythmus-Kurzlabel für die Kachel (AC-5).
 * Unterscheidet sich von presetScheduleLabel (#459 Sidepanel-Lang-Label):
 *   daily   → "tägl. HH" (zweistellige Stunde, kein –bis)
 *   weekly  → Wochentag-Name
 *   manual  → "manuell"
 */
export function presetTileScheduleLabel(preset: ComparePreset): string {
	if (preset.schedule === 'daily') {
		const h = String(preset.hour_from).padStart(2, '0');
		return `tägl. ${h}`;
	}
	if (preset.schedule === 'weekly') {
		return WEEKDAYS[preset.weekday ?? 0] ?? 'wöchentl.';
	}
	return 'manuell';
}

/**
 * ISO-Timestamp → relatives deutsches Label.
 *   heute        → "heute"
 *   gestern      → "gestern"
 *   diese Woche  → Wochentag-Name
 *   ältere Daten → "vor N Wochen"
 *   undefined    → ''
 */
export function relativeLastSent(iso: string | undefined): string {
	if (!iso) return '';
	const d = new Date(iso);
	if (isNaN(d.getTime())) return '';

	const now = new Date();
	// Tages-Differenz ohne Uhrzeit
	const diffMs = now.setHours(0, 0, 0, 0) - new Date(d).setHours(0, 0, 0, 0);
	const diffDays = Math.round(diffMs / (1000 * 60 * 60 * 24));

	if (diffDays <= 0) return 'heute';
	if (diffDays === 1) return 'gestern';
	if (diffDays < 7) return WEEKDAYS[d.getDay() === 0 ? 6 : d.getDay() - 1] ?? 'diese Woche';
	const weeks = Math.floor(diffDays / 7);
	return `vor ${weeks} ${weeks === 1 ? 'Woche' : 'Wochen'}`;
}

/** Kanal-Keys aus empfaenger + channel_layouts. Signal NIEMALS (PO #610). */
export function presetChannels(preset: ComparePreset): string[] {
	const result: string[] = [];
	// E-Mail: mind. ein Eintrag mit "@"
	// Jede Adresse mit "@" gilt als E-Mail. Signal-Block läuft ausschließlich
	// über den channel_layouts-Key-Allowlist (ALLOWED-Map unten) — nicht via
	// Substring-Match auf Adressen, der legitime Adressen wie signal@firma.com sperrt.
	if (preset.empfaenger.some((e) => e.includes('@'))) {
		result.push('Email');
	}
	// Sonstige Kanäle aus display_config.channel_layouts
	const layouts = (preset.display_config as Record<string, unknown> | undefined)
		?.channel_layouts as Record<string, unknown> | undefined;
	if (layouts) {
		const ALLOWED: Record<string, string> = { telegram: 'Telegram', sms: 'SMS' };
		for (const key of Object.keys(layouts)) {
			const label = ALLOWED[key.toLowerCase()];
			if (label && !result.includes(label)) result.push(label);
		}
	}
	return result;
}

export type CompareAction = { id: string; label: string; danger?: boolean };

export function compareActions(status: CompareStatus): CompareAction[] {
	if (status === 'draft') {
		return [
			{ id: 'setup', label: 'Setup fortsetzen' },
			{ id: 'delete', label: 'Löschen', danger: true }
		];
	}
	// Issue #626: Toggle-Label kontextabhängig; Issue #627: 'send' wieder aufgenommen.
	// Issue #1256 Scheibe 1: 'archive' entfernt (Soll molecules.jsx:1018-1027) —
	// Archivieren ist ab Scheibe 3 exklusiv Teil der Hub-Header-Lifecycle-Liste
	// (compareLifecycleActions()), nicht mehr Teil des Listen-Kebabs.
	const pauseLabel = status === 'paused' ? 'Aktivieren' : 'Pausieren';
	return [
		{ id: 'pause', label: pauseLabel },
		{ id: 'send', label: 'Briefing jetzt senden' },
		{ id: 'preview', label: 'Vorschau öffnen' },
		{ id: 'edit', label: 'Bearbeiten' },
		{ id: 'delete', label: 'Löschen', danger: true }
	];
}

// Issue #1229 — Compare-Hub Briefing-Zeiten (Slot-basiert statt Rhythmus-Sprache).
// Spec: docs/specs/modules/issue_1229_monitor_hub.md (AC-3, Edge Cases)

/**
 * ComparePreset → lesbares Briefing-Zeiten-Label ("Morgen 06:30 · Abend 18:00").
 *
 * Format-Vorbild: mock-locations.jsx:123/148/173/197. Backend liefert
 * `HH:MM:SS` — wird auf `HH:MM` gekürzt. Kein aktiver Slot bzw. Alt-Preset
 * ohne die Slot-Felder (undefined) → "—", nie ein verwaister Trennpunkt.
 */
export function presetBriefingTimesLabel(preset: ComparePreset): string {
	const toHHMM = (t?: string) => (t ?? '').slice(0, 5);
	const parts: string[] = [];
	if (preset.morning_enabled) parts.push(`Morgen ${toHHMM(preset.morning_time)}`);
	if (preset.evening_enabled) parts.push(`Abend ${toHHMM(preset.evening_time)}`);
	return parts.length > 0 ? parts.join(' · ') : '—';
}

/**
 * Berechnet den naechsten { schedule, previous_schedule }-Zustand beim Pause-Toggle.
 *
 * - Pausieren (schedule != 'manual'): setzt schedule='manual', merkt altes schedule.
 * - Reaktivieren (schedule == 'manual'): stellt previous_schedule wieder her (Fallback 'daily').
 *
 * Issue #631 — Wochen-Rhythmus ueber Pause hinweg erhalten.
 */
export function computePauseToggle(preset: {
	schedule: string;
	previous_schedule?: string;
}): { schedule: string; previous_schedule?: string } {
	if (preset.schedule !== 'manual') {
		return { schedule: 'manual', previous_schedule: preset.schedule };
	}
	const restored = preset.previous_schedule || 'daily';
	return { schedule: restored, previous_schedule: preset.previous_schedule };
}
