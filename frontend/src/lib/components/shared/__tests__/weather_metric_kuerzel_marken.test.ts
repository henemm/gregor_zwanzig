// TDD RED — Issue #1719 Scheibe S4: die Zeile im Bereich "Reihenfolge" traegt
// ZWEI beschriftete Marken, und die Kurzform-Marke zeigt ALLE Kuerzel, die der
// Nutzer in der zugestellten Nachricht wirklich liest.
//
// Spec: docs/specs/modules/fix_1719_s4_kuerzel_vereinheitlichung.md
//   AC-5 (zwei beschriftete Marken) · AC-6 (alle Kuerzel, Quelle /api/sms-symbols)
//   AC-7 (dieselben Marken in den drei Vergleichs-Editoren, Quelle sms_code)
//   AC-8 (der Bestandswaechter aus #1453 bleibt gruen)
//   AC-9 (keine leere oder erfundene Marke)
//
// Gemessener Ist-Stand (WeatherV2Reihenfolge.svelte:97-113): die Zeile zeigt
// zwei Marken, aber
//   * ohne sichtbare Beschriftung ("Mail" steht nur im `title`-Attribut),
//   * ohne Testid — geometrisch pruefen (AC-10..AC-13) laesst sich so nichts,
//   * und die zweite Marke zeigt `m.sms_code`, also die ALARM-Stammdaten
//     (#914). Bei "Gefuehlte Temperatur" steht dort `TF`, waehrend die
//     Trip-SMS `FK FD WC` sendet; bei "Nacht-Tiefsttemperatur" steht `TN`,
//     waehrend die SMS `N` sendet. Das Kuerzel `N`, das der Nutzer wirklich
//     bekommt, ist im gesamten Editor nirgends aufloesbar.
//
// Grund fuer AST statt DOM: dieses Repo hat kein vitest/jsdom (package.json
// "test": node --test). Der Test parst die Komponenten mit dem ECHTEN
// Svelte-5-Compiler — kein verbotener Dateiinhalt-Vergleich.
//
// Der geometrische Nachweis ("die Marke ist auch WIRKLICH lesbar") gehoert
// nicht hierher: er braucht einen echten Browser und steht in
// frontend/e2e/kuerzel-marken-sichtbar.staging.spec.ts (AC-10..AC-14).
//
// Ausfuehrung:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --test \
//     src/lib/components/shared/__tests__/weather_metric_kuerzel_marken.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { readFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { parse } from 'svelte/compiler';

const here = dirname(fileURLToPath(import.meta.url));
const SHARED = join(here, '..');
const REIHENFOLGE = join(SHARED, 'weather-metrics-tab', 'WeatherV2Reihenfolge.svelte');
// Pfadregel #1409: alles relativ zur eigenen Testdatei — nie ueber einen festen
// Hauptrepo-Pfad, sonst prueft der Test aus dem Worktree die unveraenderte
// Hauptrepo-Kopie und meldet falsches Gruen.
const FRONTEND = resolve(here, '..', '..', '..', '..', '..');

/** Testids, unter denen die beiden Marken auffindbar sein muessen. Sie sind
 *  kein Selbstzweck: der Browser-Nachweis (AC-10) misst je Aufloesung die
 *  Geometrie GENAU dieser Elemente. Ohne stabilen Anker gibt es keinen. */
const MAIL_BADGE = 'wm2-mail-badge';
const KURZFORM_BADGE = 'wm2-kurzform-badge';

type Knoten = Record<string, any>;

function parseComponent(path: string): any {
	return parse(readFileSync(path, 'utf-8'), { modern: true });
}

/** Tiefensuche mit Elternkette — die brauchen wir, um "die Marke steht in
 *  einem {#if}" und "die Beschriftung steht neben der Marke" zu pruefen. */
function walk(node: unknown, visit: (n: Knoten, eltern: Knoten[]) => void, eltern: Knoten[] = []): void {
	if (node === null || typeof node !== 'object') return;
	if (Array.isArray(node)) {
		node.forEach((n) => walk(n, visit, eltern));
		return;
	}
	const n = node as Knoten;
	if (n.type) visit(n, eltern);
	const kette = n.type ? [...eltern, n] : eltern;
	for (const key of Object.keys(n)) {
		if (key === 'parent' || key === 'loc') continue;
		walk(n[key], visit, kette);
	}
}

/** Alle Namen, die ein Teilbaum liest: Bezeichner UND Objekt-Eigenschaften
 *  (`m.sms_code` liefert 'm' und 'sms_code'). */
function geleseneNamen(subtree: unknown): Set<string> {
	const namen = new Set<string>();
	walk(subtree, (n) => {
		if (n.type === 'Identifier' && typeof n.name === 'string') namen.add(n.name);
		if (n.type === 'MemberExpression' && !n.computed && n.property?.type === 'Identifier') {
			namen.add(n.property.name);
		}
	});
	return namen;
}

/** Alle Textbausteine eines Teilbaums, zusammengezogen. */
function textVon(subtree: unknown): string {
	const teile: string[] = [];
	walk(subtree, (n) => {
		if (n.type === 'Text' && typeof n.data === 'string') teile.push(n.data);
	});
	return teile.join(' ').replace(/\s+/g, ' ').trim();
}

function attributWert(n: Knoten, name: string): string | null {
	for (const a of n.attributes ?? []) {
		if (a.type !== 'Attribute' || a.name !== name) continue;
		const v = Array.isArray(a.value) ? a.value : [a.value];
		const literal = v.find((x: Knoten) => x?.type === 'Text');
		return literal ? String(literal.data) : '';
	}
	return null;
}

/** Das Element mit `data-testid={testid}` samt seiner Elternkette. */
function findeMarke(ast: any, testid: string): { knoten: Knoten; eltern: Knoten[] } | null {
	let treffer: { knoten: Knoten; eltern: Knoten[] } | null = null;
	walk(ast.fragment, (n, eltern) => {
		if (n.type !== 'RegularElement') return;
		if (attributWert(n, 'data-testid') !== testid) return;
		if (!treffer) treffer = { knoten: n, eltern };
	});
	return treffer;
}

// ═══════════════════════════════════════════════════════════════════════════
// AC-5 — zwei beschriftete Marken je Zeile
// ═══════════════════════════════════════════════════════════════════════════

describe('AC-5: die Zeile traegt zwei beschriftete, auffindbare Marken', () => {
	for (const [testid, beschriftung, zweck] of [
		[MAIL_BADGE, 'Mail', 'die englische Fachkurzform der Mail-Stundentabelle (z.B. "Feels")'],
		[KURZFORM_BADGE, 'Kurzform', 'alle Kuerzel, die SMS und Telegram senden (z.B. "FK FD WC")']
	] as const) {
		test(`Marke "${beschriftung}" ist unter data-testid="${testid}" auffindbar`, () => {
			const ast = parseComponent(REIHENFOLGE);
			const marke = findeMarke(ast, testid);
			assert.ok(
				marke,
				`AC-5 FAIL (RED): WeatherV2Reihenfolge.svelte hat kein Element mit ` +
					`data-testid="${testid}" — ${zweck}. Ohne stabilen Anker kann der ` +
					`Browser-Nachweis (AC-10: fuenf Sichtbarkeits-Bedingungen in 14 ` +
					`Aufloesungen) die Marke nicht messen. Heute traegt die Zeile zwei ` +
					`Marken ohne Testid und ohne sichtbare Beschriftung (nur ` +
					`title-Attribut, WeatherV2Reihenfolge.svelte:102-111).`
			);
		});

		test(`Marke "${beschriftung}" ist sichtbar beschriftet, nicht nur per title`, () => {
			const ast = parseComponent(REIHENFOLGE);
			const marke = findeMarke(ast, testid);
			assert.ok(
				marke,
				`AC-5 FAIL (RED): keine Marke "${testid}" — ohne sie gibt es auch keine ` +
					`Beschriftung zu pruefen (Ursache s. Test darueber).`
			);
			const eigenerText = textVon(marke.knoten);
			const eltern = marke.eltern[marke.eltern.length - 1];
			const umfeld = eltern ? textVon(eltern.fragment ?? eltern) : '';
			assert.ok(
				eigenerText.includes(beschriftung) || umfeld.includes(beschriftung),
				`AC-5 FAIL (RED): die Marke "${testid}" traegt nirgends die sichtbare ` +
					`Beschriftung "${beschriftung}". Gefunden: eigener Text ${JSON.stringify(eigenerText)}, ` +
					`Umfeld ${JSON.stringify(umfeld)}. Ein Kuerzel ohne Beschriftung ist ` +
					`nicht aufloesbar — der Nutzer weiss nicht, ob "TF" in seiner Mail ` +
					`oder in seiner SMS steht.`
			);
		});
	}
});

// ═══════════════════════════════════════════════════════════════════════════
// AC-6 — die Kurzform-Marke zeigt ALLE Kuerzel der Groesse
// ═══════════════════════════════════════════════════════════════════════════

describe('AC-6: die Kurzform-Marke zeigt alle Kuerzel, nicht nur das erste', () => {
	test('die Marke rendert eine Liste (Schleife oder join), keinen Einzelwert', () => {
		const ast = parseComponent(REIHENFOLGE);
		const marke = findeMarke(ast, KURZFORM_BADGE);
		assert.ok(marke, `AC-6 FAIL (RED): keine Marke "${KURZFORM_BADGE}" — s. AC-5.`);

		let listenform = false;
		walk(marke!.knoten, (n) => {
			if (n.type === 'EachBlock') listenform = true;
			if (
				n.type === 'CallExpression' &&
				n.callee?.type === 'MemberExpression' &&
				n.callee.property?.type === 'Identifier' &&
				n.callee.property.name === 'join'
			) {
				listenform = true;
			}
		});
		assert.ok(
			listenform,
			`AC-6 FAIL (RED): die Kurzform-Marke rendert einen Einzelwert. ` +
				`"Gefuehlte Temperatur" traegt drei Kuerzel (FK FD WC) und "Gewitter" ` +
				`zwei (TH TH+) — ein skalares Feld kann davon nur eines zeigen, und ` +
				`die uebrigen bleiben unaufloesbar.`
		);
	});
});

// ═══════════════════════════════════════════════════════════════════════════
// AC-9 — keine leere und keine erfundene Marke
// ═══════════════════════════════════════════════════════════════════════════

describe('AC-9: eine Groesse ohne Kuerzel bekommt gar keine Marke', () => {
	test('die Kurzform-Marke haengt an einer Bedingung ueber ihrer eigenen Quelle', () => {
		const ast = parseComponent(REIHENFOLGE);
		const marke = findeMarke(ast, KURZFORM_BADGE);
		assert.ok(marke, `AC-9 FAIL (RED): keine Marke "${KURZFORM_BADGE}" — s. AC-5.`);

		const inhalt = geleseneNamen(marke!.knoten);
		const bedingungen = marke!.eltern
			.filter((e) => e.type === 'IfBlock')
			.map((e) => geleseneNamen(e.test));
		assert.ok(
			bedingungen.length > 0,
			`AC-9 FAIL (RED): die Kurzform-Marke steht in keinem {#if}. Eine Groesse ` +
				`ohne Kuerzel bekaeme dann eine leere Marke — "Kurzform" mit nichts ` +
				`dahinter ist schlechter als gar keine Marke.`
		);
		const passend = bedingungen.some((b) => [...b].some((name) => inhalt.has(name)));
		assert.ok(
			passend,
			`AC-9 FAIL: die Bedingung prueft etwas anderes als die Marke anzeigt ` +
				`(Bedingung liest ${JSON.stringify(bedingungen.map((b) => [...b]))}, ` +
				`Marke liest ${JSON.stringify([...inhalt])}). Dann kann eine leere Marke ` +
				`erscheinen, obwohl die Bedingung wahr ist.`
		);
	});
});

// ═══════════════════════════════════════════════════════════════════════════
// AC-6 / AC-7 — die Quelle richtet sich nach der Flaeche
//
// Spec Abschnitt 3: der Touren-Editor zeigt die TRIP-SMS-Kuerzel
// (/api/sms-symbols, deckt Mehrfach-Token und Grammatik ab), die drei
// Vergleichs-Editoren das Register-Kuerzel (`sms_code`) — die Vergleichs-SMS
// rendert aus `get_sms_code()`. Eine flaechenblinde Korrektur wuerde den
// Vergleich falsch machen.
// ═══════════════════════════════════════════════════════════════════════════

/** Namen, die eine `<WeatherV2Reihenfolge …>`-Einbettung erreicht: alles aus
 *  ihren Attributwerten plus — einen Schritt tief — alles aus der Herleitung
 *  der dort genannten Bezeichner. Zwei Bauarten sind damit gleich gueltig:
 *  die Kuerzel als EIGENE Eigenschaft uebergeben oder sie in die bestehende
 *  `metricById`-Zuordnung einweben. Der Test schreibt keine von beiden vor. */
function erreichteNamen(datei: string, waehle: (attrs: Set<string>) => boolean): Set<string> | null {
	const ast = parseComponent(datei);
	let ziel: Knoten | null = null;
	walk(ast.fragment, (n) => {
		if (n.type !== 'Component' || n.name !== 'WeatherV2Reihenfolge') return;
		const attrNamen = new Set<string>(
			(n.attributes ?? [])
				.filter((a: Knoten) => a.type === 'Attribute')
				.map((a: Knoten) => String(a.name))
		);
		if (waehle(attrNamen) && !ziel) ziel = n;
	});
	if (!ziel) return null;

	const direkt = geleseneNamen((ziel as Knoten).attributes);
	const alle = new Set(direkt);
	walk(ast.instance?.content?.body, (n) => {
		if (n.type !== 'VariableDeclarator') return;
		const name = n.id?.type === 'Identifier' ? n.id.name : null;
		if (!name || !direkt.has(name)) return;
		for (const gelesen of geleseneNamen(n.init)) alle.add(gelesen);
	});
	return alle;
}

describe('AC-6: der Touren-Editor speist die Kurzform-Marke aus /api/sms-symbols', () => {
	test('die Touren-Einbettung erreicht den Kuerzel-Katalog des Backends', () => {
		// Die Touren-Einbettung ist die einzige mit `offColumns` (#1719 S3:
		// "Aus in diesem Kanal" gibt es nur im Trip-Kanal-Reiter).
		const erreicht = erreichteNamen(join(SHARED, 'WeatherMetricsTab.svelte'), (attrs) =>
			attrs.has('offColumns')
		);
		assert.ok(erreicht, 'Touren-Einbettung von WeatherV2Reihenfolge nicht gefunden');
		const quellen = ['metricSymbols', 'smsSymbols', 'sms_symbols'];
		assert.ok(
			quellen.some((q) => erreicht!.has(q)),
			`AC-6 FAIL (RED): die Touren-Einbettung erreicht keine der Quellen ` +
				`${quellen.join('/')} — der Editor zeigt also weiter die ALARM-Stammdaten ` +
				`(sms_code) statt der Kuerzel, die die Trip-SMS wirklich sendet. ` +
				`WeatherMetricsTab.svelte laedt /api/sms-symbols bereits und haelt das ` +
				`Ergebnis in \`metricSymbols\` (Zeile ~171) — es kommt nur nie in der ` +
				`Zeile an. Erreichbar ist heute: ${JSON.stringify([...erreicht!].sort())}`
		);
	});
});

describe('AC-7: die drei Vergleichs-Editoren speisen die Marke aus dem Register', () => {
	for (const [name, datei, waehle] of [
		[
			'Vergleichs-Uebersicht',
			'WeatherMetricsTab.svelte',
			(attrs: Set<string>) => !attrs.has('offColumns')
		],
		['Vergleichs-Stundenverlauf', 'CompareHourlyLayoutControls.svelte', () => true],
		['Vergleichs-Ausblick', 'CompareOutlookLayoutControls.svelte', () => true]
	] as const) {
		test(`${name}: die Zeile erreicht das Register-Kuerzel (sms_code)`, () => {
			const erreicht = erreichteNamen(join(SHARED, datei), waehle);
			assert.ok(erreicht, `${name}: WeatherV2Reihenfolge-Einbettung nicht gefunden`);
			assert.ok(
				erreicht!.has('sms_code'),
				`AC-7 FAIL: ${name} erreicht kein \`sms_code\`. Die Vergleichs-SMS ` +
					`rendert aus \`get_sms_code()\` (comparison.py) — eine Zeile ohne ` +
					`diese Quelle koennte nur ein Kuerzel zeigen, das der Vergleich nie ` +
					`sendet. Erreichbar: ${JSON.stringify([...erreicht!].sort())}`
			);
		});
	}
});

// ═══════════════════════════════════════════════════════════════════════════
// AC-8 — der Bestandswaechter aus #1453 bleibt gruen
//
// Er prueft heute die ANWESENHEIT von `label`/`col_label`/`sms_code` in allen
// vier Editoren. Stellt S4 die Kurzform-Marke auf eine andere Quelle um, faellt
// er — genau darauf zielt AC-8: er muss MITGEZOGEN werden (Erwartung an die
// neue Quelle anpassen), nicht entschaerft und nicht geloescht.
// ═══════════════════════════════════════════════════════════════════════════

describe('AC-8: der Bestandswaechter aus #1453 laeuft weiterhin gruen', () => {
	test('weather_metric_name_forms_visible.test.ts besteht', () => {
		const ergebnis = spawnSync(
			process.execPath,
			[
				'--import',
				'./test-lib-loader.mjs',
				'--experimental-strip-types',
				'--test',
				'src/lib/components/shared/__tests__/weather_metric_name_forms_visible.test.ts'
			],
			{ cwd: FRONTEND, encoding: 'utf-8' }
		);
		assert.equal(
			ergebnis.status,
			0,
			`AC-8 FAIL: der Bestandswaechter aus #1453 ist rot (Exit ${ergebnis.status}). ` +
				`Er prueft, dass alle VIER Editoren die Namensformen tragen. Nach der ` +
				`Umstellung auf die neue Kurzform-Quelle ist seine Erwartung anzupassen ` +
				`— nicht seine Pruefung zu lockern.\n${ergebnis.stdout}\n${ergebnis.stderr}`
		);
	});
});
