// Pruefstand-Helfer (KEINE Testdatei) — Issue #2727 (Epic #2345, DoD-1).
// Spec: docs/specs/modules/feat_2727_compare_wizardstate_abloesen.md (AC-5, AC-7, AC-8, AC-22)
//
// Das ECHTE Instanz-Skript von `compare-new/CompareNewEditor.svelte` wird ueber
// `standardwerteEditorPruefstand.editorUmgebung` ausgewertet — OHNE `getContext`-Saat.
// Startwerte kommen nur ueber die Props, die auch die Seite `/compare/new` setzt:
//   * `stateOverride` (Reiter/Besuchs-Flags + Startwerte name/region/activityProfile/pickedIds),
//   * `vorlage` (einmalige Vorbelegung aus `/compare/new?from=<id>`),
//   * `locations`.
// Alle uebrigen Felder werden so geaendert, wie der Nutzer sie aendert: ueber die
// Rueckrufe des Prop-Buendels, das der Editor SELBST an seine Reiter haengt
// (`versand={versandPropsAus(…)}`, `{...wetterMetrikenPropsAus(…)}` usw.). Der Name
// der Zustandsvariable im Editor ist damit egal — gemessen wird die Verdrahtung.
//
// Netzgrenze: `globalThis.fetch` wird aufgezeichnet (der Editor spricht ueber das
// echte `$lib/api`). Navigation: `goto` wird in der Saat aufgezeichnet — das setzt
// einen statischen `import { goto } from '$app/navigation'` voraus (Muster
// TripNewEditor.svelte:11); den bindet der Pruefstand nicht und nimmt die Saat.
//
// Pfadregel #1409: relativ zu DIESER Datei.

import { COMPARE_EDITOR, editorUmgebung, type EditorUmgebung } from './standardwerteEditorPruefstand.ts';
import { findeKomponenten, attributAusdruck, werte, type Knoten } from './svelteInstanzPruefstand.ts';

export const MATCH_MEDIA = {
	matchMedia: () => ({ matches: false, addEventListener() {}, removeEventListener() {} })
};

export interface Anfrage {
	url: string;
	methode: string;
	kopf: Record<string, string>;
	koerper: Knoten | null;
	roh: string;
}

/** Zeichnet alle fetch-Aufrufe auf; POST /api/compare/presets antwortet mit `{id}`. */
export function fetchMitschnitt(antwortId = 'cmp-neu'): {
	anfragen: Anfrage[];
	presetPosts: () => Anfrage[];
	abbauen: () => void;
} {
	const anfragen: Anfrage[] = [];
	const original = globalThis.fetch;
	globalThis.fetch = (async (input: unknown, init?: { method?: string; body?: unknown; headers?: unknown }) => {
		const url = String(input);
		const methode = (init?.method ?? 'GET').toUpperCase();
		const roh = init?.body === undefined ? '' : String(init.body);
		let koerper: Knoten | null = null;
		try {
			koerper = roh ? (JSON.parse(roh) as Knoten) : null;
		} catch {
			koerper = null;
		}
		anfragen.push({ url, methode, kopf: { ...((init?.headers as Record<string, string>) ?? {}) }, koerper, roh });
		if (url.includes('/api/compare/presets') && methode === 'POST') {
			return new Response(JSON.stringify({ id: antwortId }), {
				status: 201,
				headers: { 'content-type': 'application/json' }
			});
		}
		return new Response('[]', { status: 200, headers: { 'content-type': 'application/json' } });
	}) as typeof globalThis.fetch;
	return {
		anfragen,
		presetPosts: () => anfragen.filter((a) => a.methode === 'POST' && a.url.includes('/api/compare/presets')),
		abbauen: () => {
			globalThis.fetch = original;
		}
	};
}

export interface VergleichEditor extends EditorUmgebung {
	gotos: string[];
}

/** Instanz-Umgebung des Anlege-Editors — ohne Context, nur mit Props. */
export async function vergleichEditor(opts: {
	stateOverride?: Knoten;
	vorlage?: Knoten | null;
	locations?: Knoten[];
	extra?: Knoten;
}): Promise<VergleichEditor> {
	const gotos: string[] = [];
	const e = await editorUmgebung(COMPARE_EDITOR, {
		stateOverride: opts.stateOverride,
		vorlage: opts.vorlage,
		locations: opts.locations ?? [],
		goto: async (url: unknown) => {
			gotos.push(String(url));
		},
		window: MATCH_MEDIA,
		...(opts.extra ?? {})
	});
	return Object.assign(e, { gotos });
}

/** Die vier Startwerte, die ueber `stateOverride` gesaet werden duerfen, sind im Editor angekommen. */
export const VERTRAG_FEHLT_EDITOR =
	'VERTRAG FEHLT (#2727): CompareNewEditor uebernimmt name/pickedIds nicht aus `stateOverride` ' +
	'(lokaler Zustand ohne getContext) — nameOk/orteOk bleiben unwahr.';

/** Wertet das Prop-Buendel der ERSTEN Einbettung von `komponente` im Editor aus:
 *  `attribut` gesetzt ⇒ `attribut={…}`; sonst die Spread-Attribut-Form `{...xPropsAus(…)}`. */
export function buendelAus(e: EditorUmgebung, komponente: string, attribut?: string): Knoten {
	const einbettung = findeKomponenten(e.ast, komponente)[0];
	if (!einbettung) throw new Error(`Messaufbau: <${komponente}> nicht im Anlege-Editor eingebettet.`);
	let ausdruck: string | null = null;
	if (attribut) {
		ausdruck = attributAusdruck(einbettung, e.quelle, attribut);
	} else {
		for (const a of (einbettung.attributes ?? []) as Knoten[]) {
			if (a.type !== 'SpreadAttribute') continue;
			const text = e.quelle.slice(a.expression.start, a.expression.end);
			if (/PropsAus\s*\(/.test(text)) {
				ausdruck = text;
				break;
			}
		}
	}
	if (!ausdruck) throw new Error(`Messaufbau: <${komponente}> traegt kein Prop-Buendel ${attribut ?? '{...xPropsAus()}'}.`);
	return werte(ausdruck, e.u) as Knoten;
}
