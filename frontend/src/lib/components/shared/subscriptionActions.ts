// Issue #2278 (Epic #2345 P3) — EINE Aktionsquelle und EINE Lebenszyklus-Schicht fuer
// Trip UND Ortsvergleich, fuer Liste, Hub und Mobil. Reine Funktionen, node:testbar.
// Spec: docs/specs/modules/feat_2278_aktionsmodell.md (AC-1, AC-6, AC-8, AC-12)

import type { ComparePreset, Trip } from '../../types.js';
import { deriveTripStatus } from '../../utils/tripStatus.ts';
import { deriveStatusFromPreset } from '../compare/subscriptionHelpers.ts';
import type { SubscriptionKind } from './subscriptionTabs.ts';

export type SubscriptionLifecycle = 'draft' | 'active' | 'paused' | 'archived';
export type SubscriptionSurface = 'list' | 'hub' | 'mobile';

export type SubscriptionActionId =
	| 'pause'
	| 'resume'
	| 'send'
	| 'preview'
	| 'alarms'
	| 'weather'
	| 'edit'
	| 'archive'
	| 'unarchive'
	| 'delete'
	| 'continue-setup';

export interface SubscriptionAction {
	id: SubscriptionActionId;
	label: string;
	danger?: boolean;
}

const A: Record<SubscriptionActionId, SubscriptionAction> = {
	pause: { id: 'pause', label: 'Pausieren' },
	resume: { id: 'resume', label: 'Fortsetzen' },
	send: { id: 'send', label: 'Senden' },
	preview: { id: 'preview', label: 'Vorschau' },
	alarms: { id: 'alarms', label: 'Alarme' },
	weather: { id: 'weather', label: 'Wetter-Metriken' },
	edit: { id: 'edit', label: 'Bearbeiten' },
	archive: { id: 'archive', label: 'Archivieren' },
	unarchive: { id: 'unarchive', label: 'Reaktivieren' },
	delete: { id: 'delete', label: 'Löschen', danger: true },
	'continue-setup': { id: 'continue-setup', label: 'Setup fortsetzen' }
};

const ids = (...i: SubscriptionActionId[]): SubscriptionAction[] => i.map((id) => ({ ...A[id] }));

/**
 * Aktionen je Art/Status/Flaeche. Die Art (`kind`) aendert das Ergebnis bewusst NICHT:
 * beide Arten teilen dieselbe Tabelle (AC-6). Hub-Kebab = nur Lebenszyklus (Senden ist
 * der Primaerknopf); Archivieren steht nicht in Liste/Mobil (Liste blendet Archiviertes aus).
 */
export function subscriptionActions(
	_kind: SubscriptionKind,
	status: SubscriptionLifecycle,
	surface: SubscriptionSurface
): SubscriptionAction[] {
	const hub = surface === 'hub';
	switch (status) {
		case 'draft':
			return hub ? ids('delete') : ids('continue-setup', 'delete');
		case 'archived':
			return ids('unarchive', 'delete');
		case 'paused':
			return hub
				? ids('resume', 'archive', 'delete')
				: ids('resume', 'send', 'preview', 'alarms', 'weather', 'edit', 'delete');
		default:
			return hub
				? ids('pause', 'archive', 'delete')
				: ids('pause', 'send', 'preview', 'alarms', 'weather', 'edit', 'delete');
	}
}

/**
 * Lebenszyklus-Schicht: duenner Wrapper auf die bestehenden Ableitungen
 * (`deriveTripStatus`, `deriveStatusFromPreset`), die UNVERAENDERT bleiben.
 * Trip: geplant/aktiv/fertig zaehlen als `active` (Datumsphase ist kein Lebenszyklus).
 */
export function subscriptionLifecycle(
	kind: SubscriptionKind,
	obj: Trip | ComparePreset,
	now: Date = new Date()
): SubscriptionLifecycle {
	if (obj.archived_at != null) return 'archived';
	if (kind === 'trip') {
		const s = deriveTripStatus(obj as Trip, now);
		if (s === 'draft' || s === 'paused' || s === 'archived') return s;
		return 'active';
	}
	return deriveStatusFromPreset(obj as ComparePreset);
}
