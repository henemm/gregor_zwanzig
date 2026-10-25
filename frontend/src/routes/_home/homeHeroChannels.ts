// Issue #2346 S3 (AC-12) — Kanalzeile des Startseiten-Heros, beide kinds aus den
// Opt-in-Flags, nie aus `empfaenger` (#1452). Trip: heroKanaele (Slot-Regel wie
// der Versand, #2422 S3); Vergleich: presetChannels (E-Mail ohne Opt-out).

import { presetChannels } from '$lib/components/compare/subscriptionHelpers.js';
import type { SubscriptionKind } from '$lib/components/shared/subscriptionTabs.js';
import type { ComparePreset, Trip } from '$lib/types.js';
import { heroKanaele } from './cockpitHelpers.js';

export function homeHeroChannels(kind: SubscriptionKind, sub: Trip | ComparePreset): string[] {
	return kind === 'trip'
		? heroKanaele((sub as Trip).report_config)
		: presetChannels(sub as ComparePreset);
}
