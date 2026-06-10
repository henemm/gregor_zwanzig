// Issue #687 — Pure-Function-Extraktion der Kanal-Vererbungs- und Toggle-Logik.
// Analog AlertCard.svelte (#638): leere/fehlende rule.channels => erbt aktive Briefing-Kanäle.
// Spec: docs/specs/modules/issue_687_alert_editor_soll_ist.md

import type { AlertRule } from '$lib/types';

/**
 * Liefert die effektiven Kanäle für eine Regel.
 * Leere oder fehlende rule.channels => erbt alle aktiven Briefing-Kanäle (Vererbung).
 * Explizite rule.channels => werden unverändert zurückgegeben (neues Array).
 */
export function effectiveAlertChannels(rule: AlertRule, activeChannels: string[]): string[] {
	if (rule.channels && rule.channels.length > 0) {
		return [...rule.channels];
	}
	return [...activeChannels];
}

/**
 * Schaltet einen Kanal in der Regel um (immutabel).
 * Grundlage ist stets effectiveAlertChannels (materialisiert Vererbung beim ersten Toggle).
 * Original-Regel wird NICHT mutiert.
 */
export function toggleAlertChannel(rule: AlertRule, ch: string, activeChannels: string[]): AlertRule {
	const current = effectiveAlertChannels(rule, activeChannels);
	const idx = current.indexOf(ch);
	if (idx >= 0) {
		current.splice(idx, 1);
	} else {
		current.push(ch);
	}
	return { ...rule, channels: current };
}
