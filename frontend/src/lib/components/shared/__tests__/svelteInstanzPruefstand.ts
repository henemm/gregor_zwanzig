// Pruefstand: wertet das Instanz-Skript einer .svelte-Datei gegen eine
// gesaete Prop-Umgebung aus und liest die Attribut-Ausdruecke ECHTER
// Einbettungen.
//
// Herkunft: wortgleich aus dem F007-Abschnitt von `metricKuerzelLegende.test.ts`
// (Issue #1888 E6b) herausgezogen, dort als lokale Hilfsfunktionen entstanden.
// Issue #2276 S6b braucht denselben Mechanismus fuer eine ZWEITE Zusicherung
// (Wertprop-Verdrahtung des Stundenverlaufs) — deshalb hier als eigenes Modul
// statt ein zweites Mal abgeschrieben. Die Fassung in metricKuerzelLegende.test.ts
// bleibt unangetastet (eine Testdatei aus einer anderen zu importieren wuerde
// deren Tests ein zweites Mal ausfuehren).
//
// WARUM ueberhaupt so: die Frontend-Kernsuite ist SSR-only (`node --test` +
// `svelte/server`, kein DOM). Ereignisse und `$effect` laufen dort nie. Was
// sich trotzdem deterministisch messen laesst, ist die ECHTE Herleitung des
// Instanz-Skripts: seine Importe, seine Funktionsdeklarationen, seine
// `$derived`-Ausdruecke — ausgefuehrt mit gesaeten Props. Damit wird nicht
// geprueft, ob ein Bezeichner im Quelltext steht, sondern was der Code mit
// den Props TUT.
//
// Pfadregel #1409: Aufrufer loesen Dateipfade relativ zur EIGENEN Testdatei
// auf, nie ueber einen festen Hauptrepo-Pfad.

import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { pathToFileURL } from 'node:url';
import { parse } from 'svelte/compiler';

export type Knoten = Record<string, any>;

/** Wertet einen Quelltext-Ausdruck gegen eine Umgebung aus. */
export function werte(ausdruck: string, umgebung: Knoten): unknown {
	return new Function('u', `with (u) { return (${ausdruck}); }`)(umgebung);
}

/** Der Quelltext eines Knotens OHNE TypeScript-Annotationen — `new Function`
 *  versteht kein TS, und die Herleitungen der Komponenten sind typisiert.
 *  Ausgeblendet wird per AST (Zeichen durch Leerzeichen ersetzt, Offsets
 *  bleiben gueltig), nicht per Textmuster — geraten wird hier nichts. */
export function ohneTypen(quelle: string, knoten: Knoten): string {
	const loecher: [number, number][] = [];
	function lauf(n: unknown): void {
		if (n === null || typeof n !== 'object') return;
		if (Array.isArray(n)) {
			n.forEach(lauf);
			return;
		}
		const k = n as Knoten;
		for (const feld of ['typeAnnotation', 'returnType', 'typeParameters', 'typeArguments']) {
			const t = k[feld] as Knoten | undefined;
			if (t && typeof t.start === 'number') loecher.push([t.start, t.end]);
		}
		if (
			(k.type === 'TSAsExpression' || k.type === 'TSSatisfiesExpression') &&
			k.expression &&
			k.typeAnnotation
		) {
			loecher.push([k.expression.end, k.typeAnnotation.end]);
		}
		if (k.type === 'TSNonNullExpression' && k.expression) loecher.push([k.expression.end, k.end]);
		for (const key of Object.keys(k)) {
			if (key !== 'parent' && key !== 'loc') lauf(k[key]);
		}
	}
	lauf(knoten);
	// Issue #2276 S6c: `split('')` statt `[...quelle]`. Der Spread zerlegt nach
	// CODE-POINTS, die AST-Offsets zaehlen aber UTF-16-Einheiten — jedes Zeichen
	// ausserhalb der BMP (z. B. ein 🔴 im Kommentar oberhalb) verschiebt den
	// Ausschnitt um eins. In `AlarmeTab.svelte` schnitt das genau die oeffnende
	// `$`-Stelle des `$effect`-Aufrufs ab: der Rumpf liess sich nicht mehr
	// uebersetzen (SyntaxError) — die Zusicherung IM Effekt waere unmessbar
	// geblieben.
	const zeichen = quelle.split('');
	for (const [a, b] of loecher) for (let i = a; i < b && i < zeichen.length; i++) zeichen[i] = ' ';
	return zeichen.slice(knoten.start, knoten.end).join('');
}

/** Baut die Umgebung einer Komponentendatei: Runen-Attrappen, ihre ECHTEN
 *  Modul-Importe und ihre eigenen Deklarationen, der Reihe nach ausgewertet.
 *  Was sich nicht auswerten laesst, bleibt weg — fehlt es spaeter, scheitert
 *  der Ausdruck LAUT (keine stille Entwarnung). */
export async function umgebungFuer(
	datei: string,
	saat: Knoten
): Promise<{ ast: Knoten; quelle: string; u: Knoten; effekte: Array<() => void> }> {
	const quelle = readFileSync(datei, 'utf-8');
	const ast: Knoten = parse(quelle, { modern: true });
	const u: Knoten = { ...saat };
	const derived = ((v: unknown) => v) as Knoten;
	derived.by = (fn: () => unknown) => fn();
	u.$derived = derived;
	u.$state = (v: unknown) => v;
	u.$props = () => ({});
	// `$effect` SAMMELT seine Rueckrufe, statt sie zu verwerfen (Issue #2276
	// S6b Fix-Loop, Adversary-Finding F001): eine Attrappe `() => {}` macht
	// jede Zusicherung IM Effekt-Rumpf unbeobachtbar — der Rumpf laeuft nie,
	// also faengt auch keine Mutation darin ein Test. Registriert werden die
	// Rueckrufe von `effekteVon()`; ausgefuehrt werden sie vom Aufrufer.
	const effekte: Array<() => void> = [];
	const effektAttrappe = ((fn: () => void) => {
		effekte.push(fn);
	}) as Knoten;
	// `$effect.pre` / `$effect.root` verhalten sich fuer die Messung gleich.
	effektAttrappe.pre = effektAttrappe;
	effektAttrappe.gesammelt = effekte;
	u.$effect = effektAttrappe;

	for (const stmt of (ast.instance?.content?.body as Knoten[]) ?? []) {
		if (stmt.type !== 'ImportDeclaration') continue;
		const q = String(stmt.source?.value ?? '');
		if (q.endsWith('.svelte')) continue;
		const spec = q.startsWith('.')
			? pathToFileURL(resolve(dirname(datei), q)).href
			: q.startsWith('$lib/')
				? q
				: null;
		if (!spec) continue;
		// Gebunden wird NUR, was diese Deklaration wirklich nennt — und Typ-Importe
		// binden zur Laufzeit gar nichts (Adversary F008 aus #1888: sonst liefert
		// der Typ-Import die Bindung nach, die der gebrochene Wert-Import verlor).
		if (stmt.importKind === 'type') continue;
		let mod: Knoten | null = null;
		try {
			mod = (await import(spec)) as Knoten;
		} catch {
			mod = null;
		}
		if (!mod) continue;
		for (const s of (stmt.specifiers ?? []) as Knoten[]) {
			if (s.importKind === 'type') continue;
			const lokal = s.local?.name as string | undefined;
			if (!lokal || lokal in u) continue;
			if (s.type === 'ImportNamespaceSpecifier') {
				u[lokal] = mod;
				continue;
			}
			const her = s.type === 'ImportDefaultSpecifier' ? 'default' : (s.imported?.name ?? lokal);
			if (her in mod) u[lokal] = mod[her];
		}
	}
	// Funktionsdeklarationen zuerst — sie werden in JS gehoben, und die
	// Herleitungen rufen sie auf.
	for (const stmt of (ast.instance?.content?.body as Knoten[]) ?? []) {
		if (stmt.type !== 'FunctionDeclaration' || stmt.id?.type !== 'Identifier') continue;
		if (stmt.id.name in u) continue;
		try {
			u[stmt.id.name] = new Function(
				'u',
				`with (u) { ${ohneTypen(quelle, stmt)}\n return ${stmt.id.name}; }`
			)(u);
		} catch {
			/* s.o. */
		}
	}
	for (const stmt of (ast.instance?.content?.body as Knoten[]) ?? []) {
		if (stmt.type !== 'VariableDeclaration') continue;
		for (const d of stmt.declarations as Knoten[]) {
			if (d.id?.type !== 'Identifier' || !d.init || d.id.name in u) continue;
			try {
				u[d.id.name] = werte(ohneTypen(quelle, d.init), u);
			} catch {
				/* s.o. */
			}
		}
	}
	return { ast, quelle, u, effekte };
}

/** Nennt der Teilbaum irgendwo den Bezeichner `name`? (AST, kein Textmuster.) */
function nenntBezeichner(knoten: unknown, name: string): boolean {
	if (knoten === null || typeof knoten !== 'object') return false;
	if (Array.isArray(knoten)) return knoten.some((k) => nenntBezeichner(k, name));
	const k = knoten as Knoten;
	if (k.type === 'Identifier' && k.name === name) return true;
	for (const key of Object.keys(k)) {
		if (key === 'parent' || key === 'loc') continue;
		if (nenntBezeichner(k[key], name)) return true;
	}
	return false;
}

/** Registriert die `$effect(...)`-Aufrufe des Instanz-Skripts gegen die
 *  Umgebung `u` und gibt ihre Rueckrufe in Quelltext-Reihenfolge zurueck —
 *  AUSGEFUEHRT wird nichts, das entscheidet der Aufrufer.
 *
 *  `nennt` grenzt auf die Effekte ein, die einen bestimmten Bezeichner
 *  referenzieren (AST-Auswahl, kein Textmuster) — damit muss zum Messen
 *  EINER Zusicherung nicht das ganze Effekt-Geflecht einer Komponente
 *  auswertbar sein.
 *
 *  Anders als `umgebungFuer` schluckt diese Funktion NICHTS: scheitert die
 *  Registrierung, scheitert sie LAUT. Eine still leere Liste waere die
 *  gefaehrlichste Form von Gruen — der Aufrufer fuehrt dann nichts aus und
 *  seine Zusicherung trifft ins Leere. */
export function effekteVon(
	ast: Knoten,
	quelle: string,
	u: Knoten,
	nennt?: string
): Array<() => void> {
	const gesammelt = (u.$effect as Knoten)?.gesammelt as Array<() => void> | undefined;
	if (!Array.isArray(gesammelt)) {
		throw new Error(
			'Pruefstand: `u.$effect` sammelt nicht — die Umgebung stammt nicht aus `umgebungFuer()`.'
		);
	}
	const vorher = gesammelt.length;
	for (const stmt of (ast.instance?.content?.body as Knoten[]) ?? []) {
		if (stmt.type !== 'ExpressionStatement') continue;
		const aufruf = stmt.expression as Knoten | undefined;
		if (aufruf?.type !== 'CallExpression') continue;
		const callee = aufruf.callee as Knoten;
		const istEffekt =
			(callee?.type === 'Identifier' && callee.name === '$effect') ||
			(callee?.type === 'MemberExpression' &&
				(callee.object as Knoten)?.type === 'Identifier' &&
				(callee.object as Knoten).name === '$effect');
		if (!istEffekt) continue;
		if (nennt && !nenntBezeichner(aufruf.arguments, nennt)) continue;
		werte(ohneTypen(quelle, aufruf), u);
	}
	return gesammelt.slice(vorher);
}

/** Alle Einbettungen der Komponente `name` im Markup — in Quelltext-Reihenfolge. */
export function findeKomponenten(ast: Knoten, name: string): Knoten[] {
	const treffer: Knoten[] = [];
	function lauf(node: unknown): void {
		if (node === null || typeof node !== 'object') return;
		if (Array.isArray(node)) {
			node.forEach(lauf);
			return;
		}
		const n = node as Knoten;
		if (n.type === 'Component' && n.name === name) treffer.push(n);
		for (const key of Object.keys(n)) {
			if (key !== 'parent' && key !== 'loc') lauf(n[key]);
		}
	}
	lauf(ast.fragment);
	return treffer;
}

/** Der Quelltext des Attribut-Ausdrucks `name` an einer Einbettung, oder
 *  `null`, wenn das Attribut fehlt. */
export function attributAusdruck(einbettung: Knoten, quelle: string, name: string): string | null {
	for (const a of (einbettung.attributes ?? []) as Knoten[]) {
		if (a.type !== 'Attribute' || a.name !== name) continue;
		const v = a.value;
		if (v?.type === 'ExpressionTag') return quelle.slice(v.expression.start, v.expression.end);
		// Kurzform `{metricById}` — der Wert IST der Bezeichner.
		return name;
	}
	return null;
}

/** Alle gesetzten Attributnamen einer Einbettung (fuer Abwesenheits-Aussagen). */
export function attributNamen(einbettung: Knoten): string[] {
	return ((einbettung.attributes ?? []) as Knoten[])
		.filter((a) => a.type === 'Attribute')
		.map((a) => String(a.name));
}
