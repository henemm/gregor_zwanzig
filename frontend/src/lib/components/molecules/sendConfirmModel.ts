// Issue #2278 — Entscheidungslogik des Sende-Dialogs (rein, node:testbar).
// Ziel und Sperre kommen ausschliesslich aus `sendTargetLabel` (AC-3); Morgen/Abend nur beim Trip (AC-4).

import { sendTargetLabel } from '../shared/versand-tab/sendTargetLabel.ts';
import type { SendTargetChannels } from '../shared/versand-tab/sendTargetLabel.ts';
import type { ConnectionProfile } from '../shared/versand-tab/channelConnectionStatus.ts';
import type { SubscriptionKind } from '../shared/subscriptionTabs.ts';

export type Berichtsart = 'morning' | 'evening';

export const BERICHTSART_WAHL: ReadonlyArray<{ value: Berichtsart; label: string }> = [
	{ value: 'morning', label: 'Morgen' },
	{ value: 'evening', label: 'Abend' }
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
		berichtsartWahl: trip ? BERICHTSART_WAHL.map((w) => ({ ...w })) : null,
		berichtsart: trip ? (auswahl ?? 'morning') : undefined
	};
}
