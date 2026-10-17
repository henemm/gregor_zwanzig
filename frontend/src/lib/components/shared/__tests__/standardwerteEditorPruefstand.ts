// Pruefstand fuer „Mit Standardwerten speichern" (Onboarding S3, Issue #2521).
// KEINE Testdatei — Hilfsfunktionen fuer die Tests
//   standardwerte_gate.test.ts, standardwerte_knopf_geteilt.test.ts,
//   trip-new/__tests__/standardwerte_payload_paritaet_trip.test.ts,
//   compare-new/__tests__/standardwerte_payload_paritaet_compare.test.ts
// Spec: docs/specs/modules/onboarding_standardwerte_hilfe.md
//
// Baut auf `svelteInstanzPruefstand.ts` auf: das ECHTE Instanz-Skript einer
// .svelte-Datei wird gegen gesaete Props ausgewertet. Ergaenzt um drei Dinge,
// die die Standardwerte-Zusicherungen brauchen:
//   1. `onMount`/`beforeNavigate` SAMMELN ihre Rueckrufe (wie `$effect` im
//      Basis-Pruefstand) — ausgefuehrt wird nur, was der Test ausdruecklich will.
//   2. `derivedNeu()` rechnet alle `$derived`-Deklarationen in Quelltext-
//      Reihenfolge neu aus. Die Basis-Umgebung friert jede Herleitung beim Aufbau
//      ein; nach einem Mount (Katalog geladen) waere ein Gate sonst veraltet.
//   3. `knopfEinbettungen()` liefert die Einbettungen des geteilten Knopfs
//      `StandardwerteSpeichernKnopf` (AST, kein Textmuster).
//
// Pfadregel #1409: alle Pfade relativ zu DIESER Datei.

import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import {
	umgebungFuer,
	effekteVon,
	findeKomponenten,
	attributAusdruck,
	ohneTypen,
	werte,
	type Knoten
} from './svelteInstanzPruefstand.ts';

const HIER = dirname(fileURLToPath(import.meta.url));
export const COMPONENTS = resolve(HIER, '..', '..');
export const SHARED = resolve(HIER, '..');
export const TRIP_EDITOR = join(COMPONENTS, 'trip-new', 'TripNewEditor.svelte');
export const COMPARE_EDITOR = join(COMPONENTS, 'compare-new', 'CompareNewEditor.svelte');
export const KNOPF_DATEI = join(SHARED, 'StandardwerteSpeichernKnopf.svelte');
export const KNOPF_NAME = 'StandardwerteSpeichernKnopf';

export interface EditorUmgebung {
	ast: Knoten;
	quelle: string;
	u: Knoten;
	mounts: Array<() => unknown>;
	navigationsWaechter: Array<(nav: Knoten) => unknown>;
}

/** Instanz-Umgebung eines Editors mit sammelnden onMount/beforeNavigate. */
export async function editorUmgebung(datei: string, saat: Knoten): Promise<EditorUmgebung> {
	const mounts: Array<() => unknown> = [];
	const navigationsWaechter: Array<(nav: Knoten) => unknown> = [];
	const basis: Knoten = {
		untrack: (fn: () => unknown) => fn(),
		onMount: (fn: () => unknown) => {
			mounts.push(fn);
		},
		beforeNavigate: (fn: (nav: Knoten) => unknown) => {
			navigationsWaechter.push(fn);
		},
		goto: async () => {},
		$bindable: (v: unknown) => v
	};
	const { ast, quelle, u } = await umgebungFuer(datei, { ...basis, ...saat }, { jsAlsTs: true });
	// onMount(...)/beforeNavigate(...) stehen als Ausdrucks-Anweisungen im Skript —
	// die Basis-Umgebung wertet nur Deklarationen aus. Registriert (nicht
	// ausgefuehrt) werden sie hier, in Quelltext-Reihenfolge.
	for (const stmt of (ast.instance?.content?.body as Knoten[]) ?? []) {
		if (stmt.type !== 'ExpressionStatement') continue;
		const aufruf = stmt.expression as Knoten | undefined;
		if (aufruf?.type !== 'CallExpression') continue;
		const name = (aufruf.callee as Knoten)?.name;
		if (name !== 'onMount' && name !== 'beforeNavigate') continue;
		try {
			werte(ohneTypen(quelle, aufruf), u);
		} catch {
			/* eine nicht auswertbare Registrierung fehlt dann LAUT beim Aufrufer */
		}
	}
	return { ast, quelle, u, mounts, navigationsWaechter };
}

/** Fuehrt alle gesammelten onMount-Rueckrufe aus (Fehler einzelner Rueckrufe,
 *  z. B. `window.matchMedia`, werden geschluckt) und alle `$effect`s. */
export async function mountenUndWarten(e: EditorUmgebung): Promise<void> {
	for (const fn of e.mounts) {
		try {
			fn();
		} catch {
			/* Browser-API fehlt serverseitig */
		}
	}
	let effekte: Array<() => void> = [];
	try {
		effekte = effekteVon(e.ast, e.quelle, e.u);
	} catch {
		effekte = [];
	}
	for (const fn of effekte) {
		try {
			fn();
		} catch {
			/* s. o. */
		}
	}
	await ruhe();
}

/** Laesst alle anstehenden Promise-Ketten auslaufen. */
export async function ruhe(): Promise<void> {
	for (let i = 0; i < 20; i++) await new Promise((r) => setTimeout(r, 0));
}

/** Rechnet alle `$derived(...)`/`$derived.by(...)`-Deklarationen neu aus. */
export function derivedNeu(e: EditorUmgebung): void {
	for (const stmt of (e.ast.instance?.content?.body as Knoten[]) ?? []) {
		if (stmt.type !== 'VariableDeclaration') continue;
		for (const d of stmt.declarations as Knoten[]) {
			if (d.id?.type !== 'Identifier' || !d.init || d.init.type !== 'CallExpression') continue;
			const c = d.init.callee as Knoten;
			const istDerived =
				(c?.type === 'Identifier' && c.name === '$derived') ||
				(c?.type === 'MemberExpression' && (c.object as Knoten)?.name === '$derived');
			if (!istDerived) continue;
			try {
				e.u[d.id.name] = werte(ohneTypen(e.quelle, d.init), e.u);
			} catch {
				/* s. o. */
			}
		}
	}
}

/** Alle Einbettungen des geteilten Standardwerte-Knopfs im Markup. */
export function knopfEinbettungen(ast: Knoten): Knoten[] {
	return findeKomponenten(ast, KNOPF_NAME);
}

/** Wert des Attributs `name` an einer Knopf-Einbettung, ausgewertet in `u`. */
export function knopfAttribut(einbettung: Knoten, e: EditorUmgebung, name: string): unknown {
	const ausdruck = attributAusdruck(einbettung, e.quelle, name);
	if (ausdruck === null) throw new Error(`Knopf-Einbettung ohne Attribut \`${name}\`.`);
	return werte(ausdruck, e.u);
}

/** Literalwert des Attributs `testid` (statisches Attribut oder Ausdruck). */
export function knopfTestid(einbettung: Knoten, e: EditorUmgebung): string | null {
	for (const a of (einbettung.attributes ?? []) as Knoten[]) {
		if (a.type !== 'Attribute' || a.name !== 'testid') continue;
		if (Array.isArray(a.value)) return a.value.map((t: Knoten) => t.data ?? '').join('');
		if (a.value?.type === 'ExpressionTag') return String(werte(e.quelle.slice(a.value.expression.start, a.value.expression.end), e.u));
	}
	return null;
}

/** Quelle des Imports, unter dem `lokalerName` im Instanz-Skript gebunden ist. */
export function importQuelle(ast: Knoten, lokalerName: string): string | null {
	for (const stmt of (ast.instance?.content?.body as Knoten[]) ?? []) {
		if (stmt.type !== 'ImportDeclaration') continue;
		for (const s of (stmt.specifiers ?? []) as Knoten[]) {
			if (s.local?.name === lokalerName) return String(stmt.source?.value ?? '');
		}
	}
	return null;
}

/** Loest eine Import-Quelle einer Komponentendatei auf einen Dateipfad auf. */
export function importPfad(datei: string, quelle: string): string {
	if (quelle.startsWith('$lib/')) return resolve(COMPONENTS, '..', quelle.slice('$lib/'.length));
	return resolve(dirname(datei), quelle);
}
