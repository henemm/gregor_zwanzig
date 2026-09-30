// Issue #2276 Scheibe S6f (Epic #2345) — Persistenz-Haelfte der aufgeloesten
// Compare-Hub-Klebeschicht (Issue #1256 Scheibe 6/7). Alles, was einen
// Hub-PUT baut oder serialisiert: Toggle-Active (Hub UND Liste), Rollback-Snapshot,
// Aktivierungs-Banner-Text und die geteilte Schreibschlange `hubPutQueue`
// (F1: Payload-Bau bleibt im `enqueue()`-Closure, s. Spec
// Design-Entscheidung 4).
//
// Spec: docs/specs/modules/rework_2276_s6f_bridge_umzug.md — AC-1
//
// Funktionskoerper/JSDoc byte-identisch aus der aufgeloesten Bridge
// uebernommen — reiner Umzug, kein Verhalten geaendert.
//
// Kein Browser-/SvelteKit-Import — lauffaehig unter node --experimental-strip-types.
//
// gz-eigenstaendig: Compare-Hub-Orchestrierung (ComparePreset-PUT/-Hydration fuer CompareTabs.svelte), reiner Umzug der aufgeloesten Compare-Klebeschicht; kein Trip-Pendant (Spec rework_2276_s6f_bridge_umzug.md)

import type { ComparePreset } from '../../types.ts';
import { buildComparePresetPartialPayload } from './compareEditorSave.ts';
import type { CompareStatus } from './subscriptionHelpers.ts';
import { computePauseToggle } from './subscriptionHelpers.ts';

/**
 * Deep-Copy-Helfer fuer den Prae-Aktions-Zustand (Edge Case Z.1020, Rollback
 * bei PUT-Fehler). JSON-Rundreise statt structuredClone, damit Svelte-$state-
 * Proxies zuverlaessig in ein reines, unabhaengiges Objekt entpackt werden.
 */
export function snapshotForRollback<T>(value: T): T {
	return JSON.parse(JSON.stringify(value)) as T;
}

/**
 * Reine Payload-Konstruktion fuer den Uebersicht-Tab-Pausieren/Aktivieren-Pfad
 * (`handleToggleActive` in CompareTabs.svelte).
 *
 * Issue #2375: sendet NUR `{ schedule, previous_schedule }` — kein Voll-Spread
 * der (womoeglich veralteten) `preset`-Basis mehr (frueher F007/F005: das
 * Nachfuehren der Baseline war die Krücke gegen genau diesen Spread). `paused_at`
 * leitet der Server aus `schedule` ab. Reine Funktion, kein DOM/Browser-Bezug.
 */
export function buildToggleActivePutPayload(
	preset: ComparePreset,
	schedule: string,
	previousSchedule: string
): { url: string; body: ComparePreset } {
	// Issue #2375: nur der Status — paused_at leitet der Server ab.
	return buildComparePresetPartialPayload(preset.id, {
		schedule,
		previous_schedule: previousSchedule
	});
}

/**
 * Issue #1259 (Read-Modify-Write): Payload-Bau fuer den Vergleichs-LISTEN-
 * Kebab "Pausieren/Aktivieren" — analog `buildToggleActivePutPayload`, aber
 * mit frisch via `getPreset` geladenem Server-Stand statt der eingefrorenen
 * Listen-Prop. Verhindert stillen Server-Datenverlust, wenn Liste und
 * Detail-Hub desselben Vergleichs gleichzeitig offen sind (Multi-Tab).
 * `getPreset` ist injizierbar (kein hartcodiertes `fetch`) fuer
 * DOM-/Browser-freie Kern-Tests.
 */
export async function buildFreshTogglePutPayload(
	presetId: string,
	getPreset: (id: string) => Promise<ComparePreset>
): Promise<{ url: string; body: ComparePreset }> {
	const fresh = await getPreset(presetId);
	const next = computePauseToggle(fresh);
	return buildToggleActivePutPayload(
		fresh,
		next.schedule,
		next.previous_schedule ?? (fresh.schedule !== 'manual' ? fresh.schedule : 'daily')
	);
}

/** Modell der Hub-Aktivierungs-Karte (Soll: `screen-compare-detail.jsx:273-277`
 * + `:313-325`). Die JSX-active-Copy "im konfigurierten Rhythmus" ist eine
 * timeWindow-Stale-Spur (Spec § Umsetzungsregel) und wird NICHT mitkopiert —
 * ersetzt durch "zu den konfigurierten Zeiten". */
export function hubActivationBanner(status: CompareStatus): {
	statusLabel: string;
	text: string;
	cta: string;
	border: string;
	dotTone: 'good' | 'neutral';
} {
	if (status === 'active') {
		return {
			statusLabel: 'Aktiv',
			text: 'Läuft automatisch — unbegrenzt, bis du pausierst. Das Briefing geht zu den konfigurierten Zeiten in die Kanäle.',
			cta: 'Pausieren',
			border: 'var(--g-good)',
			dotTone: 'good'
		};
	}
	if (status === 'paused') {
		return {
			statusLabel: 'Pausiert',
			text: 'Pausiert. Es geht aktuell kein Briefing raus.',
			cta: 'Aktivieren',
			border: 'var(--g-rule)',
			dotTone: 'neutral'
		};
	}
	return {
		statusLabel: 'Entwurf',
		text: 'Noch nicht aktiv. Sobald Orte, Idealwerte und mindestens ein Kanal stehen, kannst du den Vergleich aktivieren.',
		cta: 'Aktivieren',
		border: 'var(--g-accent)',
		dotTone: 'neutral'
	};
}

export interface PutQueue {
	enqueue<T>(fn: () => Promise<T>): Promise<T>;
}

/**
 * Issue #1256 Scheibe 7 Fix-Loop 1 (F002, Adversary CRITICAL): serialisiert
 * ALLE Hub-PUT-Pfade (Orte/Idealwerte/Versand/Toggle-Active) auf EINE
 * gemeinsame Kette, damit zwei schnell aufeinanderfolgende Nutzeraktionen
 * (z. B. Versand-Aenderung + Aktivieren-Klick im selben Versand-Tab) nie
 * zwei parallele, unsynchronisierte `api.put()`-Aufrufe auf dieselbe
 * Ressource ausloesen — der zweite wuerde sonst mit einer veralteten
 * `currentPreset`-Baseline die Aenderung des ersten still ueberschreiben.
 * Payload-Bau MUSS innerhalb des enqueueten `fn` passieren (nicht davor) —
 * nur so liest ein zweiter, spaeter ausgefuehrter Aufruf den frischen
 * `currentPreset`-Stand aus der PUT-Response des ersten. Ein Fehler in `fn`
 * bricht die Kette NICHT ab (die Kette resettet in jedem Fall auf einen
 * aufgeloesten Zustand), sodass nachfolgende Aufrufe trotzdem laufen.
 */
export function createPutQueue(): PutQueue {
	let tail: Promise<void> = Promise.resolve();
	return {
		enqueue<T>(fn: () => Promise<T>): Promise<T> {
			const run = tail.then(fn);
			tail = run.then(
				() => undefined,
				() => undefined
			);
			return run;
		}
	};
}
