// Issue #2278 (Epic #2345 P3) — EINE Aktionsquelle und EINE Lebenszyklus-Schicht fuer
// Trip UND Ortsvergleich, fuer Liste, Hub und Mobil. Reine Funktionen, node:testbar.
// Spec: docs/specs/modules/feat_2278_aktionsmodell.md (AC-1, AC-6, AC-8, AC-12)

import type { ComparePreset, Trip } from '../../types.js';
import { deriveTripStatus } from '../../utils/tripStatus.ts';
import { deriveStatusFromPreset } from '../compare/subscriptionHelpers.ts';
import type { SubscriptionKind } from './subscriptionTabs.ts';
import { tr, type MessageKey } from '../../i18n/index.ts';

export type SubscriptionLifecycle = 'draft' | 'active' | 'paused' | 'archived';
export type SubscriptionSurface = 'list' | 'hub' | 'mobile';

export type SubscriptionActionId =
	| 'pause'
	| 'resume'
	| 'send'
	| 'alarms'
	| 'weather'
	| 'edit'
	| 'archive'
	| 'unarchive'
	| 'delete'
	| 'continue-setup'
	| 'activate';

export interface SubscriptionAction {
	id: SubscriptionActionId;
	label: string;
	danger?: boolean;
}

// Issue #2658 (i18n F9): die Tabelle traegt nur Kennung, Gefahr-Markierung und den
// Katalog-Schluessel (aktionen.*, wortgleich fuer Trip UND Ortsvergleich); der Text
// entsteht erst beim Aufruf in der aktuellen Sprache. Aufrufer in Komponenten lesen
// dafuer `$locale` (Muster `$derived.by(() => (void $locale, subscriptionActions(…)))`).
const A: Record<SubscriptionActionId, Omit<SubscriptionAction, 'label'> & { key: MessageKey }> = {
	pause: { id: 'pause', key: 'aktionen.pause' },
	resume: { id: 'resume', key: 'aktionen.resume' },
	send: { id: 'send', key: 'aktionen.senden' },
	alarms: { id: 'alarms', key: 'aktionen.alarms' },
	weather: { id: 'weather', key: 'aktionen.weather' },
	edit: { id: 'edit', key: 'aktionen.edit' },
	archive: { id: 'archive', key: 'aktionen.archive' },
	unarchive: { id: 'unarchive', key: 'aktionen.unarchive' },
	delete: { id: 'delete', key: 'aktionen.delete', danger: true },
	'continue-setup': { id: 'continue-setup', key: 'aktionen.continue_setup' },
	// #3443: „Aktivieren“ im Hub-Entwurf — nennt, was fehlt (keine Gefahr, keine Rückfrage).
	activate: { id: 'activate', key: 'aktionen.kopf.aktivieren' }
};

// #3442: im Hub fragen Archivieren und Löschen im Menü nach — Label mit Ellipse („Archivieren …“).
const HUB_KEY: Partial<Record<SubscriptionActionId, MessageKey>> = {
	archive: 'aktionen.kebab.menue_archive',
	delete: 'aktionen.kebab.menue_delete'
};

const ids = (hub: boolean, ...i: SubscriptionActionId[]): SubscriptionAction[] =>
	i.map((id) => {
		const { key, ...rest } = A[id];
		const label = tr((hub && HUB_KEY[id]) || key);
		return { id: rest.id, label, ...(rest.danger ? { danger: true } : {}) };
	});

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
			return hub ? ids(hub, 'activate', 'delete') : ids(hub, 'continue-setup', 'delete');
		case 'archived':
			return ids(hub, 'unarchive', 'delete');
		case 'paused':
			return hub
				? ids(hub, 'resume', 'archive', 'delete')
				: ids(hub, 'resume', 'send', 'alarms', 'weather', 'edit', 'delete');
		default:
			return hub
				? ids(hub, 'pause', 'archive', 'delete')
				: ids(hub, 'pause', 'send', 'alarms', 'weather', 'edit', 'delete');
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
