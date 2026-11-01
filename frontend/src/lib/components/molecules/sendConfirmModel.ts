// Issue #2278 — Entscheidungslogik des Sende-Dialogs (rein, node:testbar).
// Ziel und Sperre kommen ausschliesslich aus `sendTargetLabel` (AC-3); Morgen/Abend nur beim Trip (AC-4).

import { sendTargetLabel } from '../shared/versand-tab/sendTargetLabel.ts';
import type { SendTargetChannels } from '../shared/versand-tab/sendTargetLabel.ts';
import type { ConnectionProfile } from '../shared/versand-tab/channelConnectionStatus.ts';
import type { SubscriptionKind } from '../shared/subscriptionTabs.ts';
import { tr, type MessageKey } from '../../i18n/index.ts';

export type Berichtsart = 'morning' | 'evening';

// #2660: Schluessel statt Text; die Beschriftung entsteht bei jedem Aufruf in der aktuellen Sprache.
export const BERICHTSART_WAHL: ReadonlyArray<{ value: Berichtsart; labelKey: MessageKey }> = [
	{ value: 'morning', labelKey: 'bausteine.senden_dialog.morgen' },
	{ value: 'evening', labelKey: 'bausteine.senden_dialog.abend' }
];

export interface SendConfirmModel {
	beschreibung: string;
	gesperrt: boolean;
	berichtsartWahl: Array<{ value: Berichtsart; label: string }> | null;
	berichtsart: Berichtsart | undefined;
}

export function sendConfirmModel(
	kind: SubscriptionKind,
	profile: ConnectionProfile | null | undefined,
	sub: SendTargetChannels | null | undefined,
	auswahl?: Berichtsart
): SendConfirmModel {
	const ziel = sendTargetLabel(profile, sub);
	const trip = kind === 'trip';
	return {
		beschreibung: ziel.text,
		gesperrt: ziel.gesperrt,
		berichtsartWahl: trip ? BERICHTSART_WAHL.map((w) => ({ value: w.value, label: tr(w.labelKey) })) : null,
		berichtsart: trip ? (auswahl ?? 'morning') : undefined
	};
}
