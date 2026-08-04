// TDD RED — Bugfix "Sende-Dialog nennt das tatsaechliche Versandziel".
// Spec: docs/specs/modules/fix_1471_sende_dialog_ziel.md — AC-1 (Dialog-Teil),
// AC-3/AC-4 (Bestaetigen-Knopf gesperrt), AC-5 (Profil kommt aus dem Server-Load).
//
// Warum AST statt Dateiinhalt-Grep: dieses Repo hat kein vitest/jsdom
// ("test": node --test). Statt eines verbotenen String-Greps wird die Komponente
// mit dem ECHTEN Svelte-5-Compiler geparst und der Baum inspiziert.
// Vorbild: lib/components/shared/__tests__/alarme_tab_catalog_prop_structure.test.ts
// AUSDRUECKLICH KEIN Vorbild: routes/page-server.bug395.test.ts (readFileSync + Regex).
//
// RED heute: die Sende-Dialog-`description` lautet
//   'An ' + (sendTarget?.empfaenger?.length ?? 0) + ' Empfaenger senden?'
// es gibt kein `disabled`-Attribut und kein `data.profile`.
//
// Pfadregel #1409: alle Pfade relativ zu DIESER Datei.
//
// Ausfuehrung:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --test \
//     src/routes/compare/__tests__/compare_send_dialog_target.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { parse } from 'svelte/compiler';

const here = dirname(fileURLToPath(import.meta.url));
const PAGE = join(here, '..', '+page.svelte');
const ast: any = parse(readFileSync(PAGE, 'utf-8'), { modern: true });

/** Alle Knoten eines Subtrees, die ein Praedikat erfuellen. */
function collect(subtree: unknown, pred: (n: any) => boolean): any[] {
	const found: any[] = [];
	(function visit(node: unknown): void {
		if (node === null || typeof node !== 'object') return;
		if (Array.isArray(node)) return void node.forEach(visit);
		const n = node as Record<string, any>;
		if (pred(n)) found.push(n);
		for (const key of Object.keys(n)) {
			if (key === 'parent') continue;
			visit(n[key]);
		}
	})(subtree);
	return found;
}

const identifiers = (t: unknown): Set<string> =>
	new Set(collect(t, (n) => n.type === 'Identifier' && typeof n.name === 'string').map((n) => n.name));

const stringLiterals = (t: unknown): string[] =>
	collect(t, (n) => n.type === 'Literal' && typeof n.value === 'string').map((n) => n.value);

/** name → Initialisierer/Rumpf der Top-Level-Deklarationen des Instance-Scripts. */
function localBindings(): Map<string, unknown> {
	const map = new Map<string, unknown>();
	for (const n of (ast.instance?.content?.body ?? []) as any[]) {
		if (n.type === 'VariableDeclaration') {
			for (const d of n.declarations) {
				if (d.id?.type === 'Identifier' && d.init) map.set(d.id.name, d.init);
			}
		} else if (n.type === 'FunctionDeclaration' && n.id?.name) {
			map.set(n.id.name, n.body);
		}
	}
	return map;
}

/**
 * Identifier eines Ausdrucks, aufgeloest ueber lokale Variablen/Funktionen.
 * Ohne das wuerde `description={ziel.text}` die dahinterliegende Herkunft
 * verbergen — die Behauptung "der Text stammt aus dem geteilten Baustein"
 * waere dann nicht pruefbar.
 */
function identifiersDeep(expr: unknown, tiefe = 4): Set<string> {
	const binds = localBindings();
	const gesehen = new Set<string>();
	let front = identifiers(expr);
	for (let i = 0; i < tiefe; i++) {
		const naechste = new Set<string>();
		for (const name of front) {
			if (gesehen.has(name)) continue;
			gesehen.add(name);
			const b = binds.get(name);
			if (b) for (const m of identifiers(b)) if (!gesehen.has(m)) naechste.add(m);
		}
		if (naechste.size === 0) break;
		front = naechste;
	}
	return gesehen;
}

/** Attribut-Knoten einer Komponenten-Instanz (statisch oder Ausdruck). */
const attr = (inst: any, name: string): any =>
	(inst.attributes ?? []).find((a: any) => a.type === 'Attribute' && a.name === name);

/**
 * Der JS-Ausdruck HINTER `name={...}` — nicht nur der Attribut-Knoten.
 * Ohne ihn liesse sich nur pruefen, WOHER ein Wert stammt, nicht was er BEDEUTET:
 * `disabled={sendZiel.deliverable}` (Umkehrung von AC-3/AC-4) stammt aus derselben
 * Quelle wie `disabled={!sendZiel.deliverable}` und waere sonst ununterscheidbar.
 */
function attrExpression(inst: any, name: string): any {
	const a = attr(inst, name);
	const wert = Array.isArray(a?.value) ? a.value[0] : a?.value;
	return wert?.type === 'ExpressionTag' ? wert.expression : undefined;
}

const componentInstances = (name: string): any[] =>
	collect(ast.fragment, (n) => n.type === 'Component' && n.name === name);

// Der Sende-Dialog ist der ConfirmDialog, dessen `open` von `sendTarget` abhaengt.
const sendDialogs = componentInstances('ConfirmDialog').filter((i) =>
	identifiers(attr(i, 'open')).has('sendTarget')
);

describe('Struktur-Vorbedingung', () => {
	test('genau ein ConfirmDialog haengt an `sendTarget`', () => {
		assert.equal(
			sendDialogs.length,
			1,
			`Erwartet: genau ein Sende-Dialog in ${PAGE}. Gefunden: ${sendDialogs.length}. ` +
				'Ohne eindeutigen Prueflig sagt dieser Test nichts aus.'
		);
	});
});

describe('AC-1 (Dialog): die Empfaenger-Zaehlung ist aus dem Dialogtext verschwunden', () => {
	test('die `description` liest `empfaenger` nicht mehr', () => {
		const desc = attr(sendDialogs[0], 'description');
		assert.ok(desc, 'Der Sende-Dialog hat kein `description`-Attribut.');
		assert.equal(
			identifiers(desc).has('empfaenger'),
			false,
			'Die Dialog-Beschreibung liest weiterhin `sendTarget.empfaenger` — dieses Feld ist ' +
				'seit #1452 strukturell inert und dauerhaft leer, die Aussage also immer falsch (AC-1).'
		);
	});

	test('im Dialogtext steht keine Empfaenger-Zaehlung als Literal mehr', () => {
		const literale = stringLiterals(attr(sendDialogs[0], 'description'));
		const treffer = literale.filter((s) => /Empf(ä|ae)nger/i.test(s));
		assert.deepEqual(
			treffer,
			[],
			`Die Dialog-Beschreibung enthaelt weiterhin Empfaenger-Text-Bausteine: ` +
				`${JSON.stringify(treffer)} (AC-1).`
		);
	});

	test('der Dialogtext stammt aus dem geteilten Baustein `sendTargetLabel`', () => {
		const tiefe = identifiersDeep(attr(sendDialogs[0], 'description'));
		assert.ok(
			tiefe.has('sendTargetLabel'),
			'Die Dialog-Beschreibung leitet sich nicht (auch nicht mittelbar) aus ' +
				'`sendTargetLabel()` ab. Ohne den geteilten Baustein entstuende der Ziel-Text ' +
				`erneut inline. Aufgeloeste Namen: ${[...tiefe].sort().join(', ')} (AC-1).`
		);
		// Herkunft allein genuegt nicht: `description={sendZiel.deliverable}` kaeme aus
		// derselben Quelle und zeigte dem Nutzer "true"/"false" als Versandziel an.
		const flach = identifiers(attr(sendDialogs[0], 'description'));
		assert.ok(
			flach.has('text'),
			'Die Dialog-Beschreibung zeigt nicht das `text`-Feld aus `sendTargetLabel()` an, ' +
				`sondern: ${[...flach].sort().join(', ')} (AC-1).`
		);
	});

	test('`sendTargetLabel` wird aus dem geteilten versand-tab-Ordner importiert', () => {
		const quellen: string[] = (ast.instance?.content?.body ?? [])
			.filter((n: any) => n.type === 'ImportDeclaration')
			.filter((n: any) =>
				n.specifiers.some((s: any) => s.local?.name === 'sendTargetLabel' || s.imported?.name === 'sendTargetLabel')
			)
			.map((n: any) => String(n.source.value));
		assert.ok(
			quellen.some((q) => q.includes('shared/versand-tab/sendTargetLabel')),
			'`sendTargetLabel` wird nicht aus `$lib/components/shared/versand-tab/` importiert — ' +
				`die Funktion muss geteilt liegen, damit ein kuenftiger Trip-Sofortversand andocken ` +
				`kann. Gefundene Import-Quellen: ${JSON.stringify(quellen)}.`
		);
	});
});

describe('AC-3 / AC-4: nicht zustellbar → der Bestaetigen-Knopf ist gesperrt', () => {
	test('der Sende-Dialog reicht ein `disabled`-Attribut durch', () => {
		assert.ok(
			attr(sendDialogs[0], 'disabled'),
			'Der Sende-Dialog setzt kein `disabled` — ohne das bleibt der Senden-Knopf auch dann ' +
				'druckbar, wenn nachweislich nichts zugestellt wird (AC-3/AC-4). `ConfirmDialog` ' +
				'hat die Prop bereits (molecules/ConfirmDialog.svelte:20,36,60).'
		);
	});

	test('die Sperre haengt an derselben Ableitung wie der Ziel-Text', () => {
		const dis = attr(sendDialogs[0], 'disabled');
		assert.ok(dis, 'kein `disabled`-Attribut vorhanden');
		const tiefe = identifiersDeep(dis);
		assert.ok(
			tiefe.has('sendTargetLabel'),
			'Das `disabled` leitet sich nicht aus `sendTargetLabel()` ab — Text und Sperre koennten ' +
				`dann auseinanderlaufen (Dialog erklaert "geht nicht", Knopf bleibt aktiv). ` +
				`Aufgeloeste Namen: ${[...tiefe].sort().join(', ')} (AC-3/AC-4).`
		);
	});

	// Die beiden Behauptungen darueber pruefen nur die HERKUNFT des Werts — sie bleiben
	// gruen, wenn die Bedeutung verdreht wird.
	//
	// Die Frage wird deshalb UMGEDREHT: nicht "erkenne ich jede Verdreh-Form?" (das ist
	// bodenlos — `!x` faengt man, `!!x` schon nicht mehr), sondern "welche Form ist hier
	// ueberhaupt erlaubt?". Erlaubt ist genau ein nackter Feldzugriff auf das
	// Sperr-Flag. Jede Verdrehung braucht zwingend einen Operator (`!`, `!!`, `&&`,
	// Vergleich) oder ein Literal — und faellt damit durch, ohne dass dieser Test die
	// Verdreh-Form vorher kennen muss. Die BEDEUTUNG von `gesperrt` prueft
	// sendTargetLabel.test.ts als echten Verhaltenstest.
	const NUR_FELDZUGRIFF = new Set(['MemberExpression', 'Identifier']);

	test('`disabled` ist ein nackter Feldzugriff auf `gesperrt` — ohne jeden Operator', () => {
		const ausdruck = attrExpression(sendDialogs[0], 'disabled');
		assert.ok(ausdruck, 'Der Sende-Dialog reicht keinen `disabled`-Ausdruck durch.');

		const typen = [
			...new Set(collect(ausdruck, (n) => typeof n.type === 'string').map((n) => n.type))
		].sort();
		assert.deepEqual(
			typen.filter((t) => !NUR_FELDZUGRIFF.has(t)),
			[],
			`Der \`disabled\`-Ausdruck enthaelt mehr als einen Feldzugriff: ${typen.join(', ')}. ` +
				'Erlaubt ist ausschliesslich `disabled={<x>.gesperrt}`. Sobald dort gerechnet wird ' +
				'(`!`, `!!`, `&&`, Vergleich, Literal), laesst sich die Sperre verdrehen, ohne dass ' +
				'ein Test es merkt — die Negation gehoert in sendTargetLabel(), nicht ins Template ' +
				'(AC-3/AC-4).'
		);

		const ids = identifiers(ausdruck);
		assert.ok(
			ids.has('gesperrt'),
			'`disabled` bindet nicht das Sperr-Flag `gesperrt`, sondern: ' +
				`${[...ids].sort().join(', ')}. \`disabled={sendZiel.deliverable}\` waere die exakte ` +
				'Umkehrung: gesperrt wenn zustellbar, frei wenn nachweislich nichts ankommt (AC-3/AC-4).'
		);
		assert.ok(
			identifiersDeep(ausdruck).has('sendTargetLabel'),
			`Das Sperr-Flag stammt nicht aus \`sendTargetLabel()\`. Aufgeloeste Namen: ` +
				`${[...identifiersDeep(ausdruck)].sort().join(', ')} (AC-3/AC-4).`
		);
	});

	test('der Loesch-Dialog bleibt unberuehrt (kein `disabled` dazugekommen)', () => {
		const del = componentInstances('ConfirmDialog').filter((i) =>
			identifiers(attr(i, 'open')).has('deleteTarget')
		);
		assert.equal(del.length, 1, 'Loesch-Dialog nicht eindeutig gefunden.');
		assert.equal(
			attr(del[0], 'disabled'),
			undefined,
			'Der Loesch-Dialog hat ein `disabled` bekommen — der Fix betrifft nur den Sende-Dialog.'
		);
	});
});

describe('AC-5 (Seiten-Teil): das Profil kommt aus dem Server-Load, nicht aus einem Default', () => {
	test('die Seite liest `data.profile`', () => {
		const zugriffe = collect(
			ast.instance,
			(n) =>
				n.type === 'MemberExpression' &&
				n.object?.type === 'Identifier' &&
				n.object.name === 'data' &&
				n.property?.name === 'profile'
		);
		assert.ok(
			zugriffe.length >= 1,
			'`+page.svelte` liest kein `data.profile` — das Konto-Profil muss aus dem Server-Load ' +
				'(Auth-Kontext des angemeldeten Nutzers) kommen, nie aus einem Default (AC-5).'
		);
	});
});
