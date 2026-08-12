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
const LIB = resolve(here, '..', '..', '..');
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

/** Die Bauteile, die ein Editor unmittelbar rendert: er selbst plus jede
 *  direkt eingebundene Svelte-Komponente. Mehr Tiefe braucht es nicht — was
 *  der Nutzer in diesem Reiter sieht, haengt entweder im Reiter selbst oder in
 *  einem Bauteil, das er unmittelbar einbindet (Muster aus dem Bestands-
 *  waechter weather_metric_name_forms_visible.test.ts).
 *
 *  Wichtig fuer AC-7: die Frage lautet "zeigt DIESE Flaeche beide Marken?",
 *  nicht "steht irgendwo im Repo eine Datei, die sie zeigt". Baut jemand fuer
 *  den Vergleich ein eigenes Zeilen-Bauteil (Verstoss gegen die Trip/Compare-
 *  Teilungs-Invariante), faellt das hier auf, statt still durchzugehen. */
function anzeigeflaechen(datei: string): string[] {
	const pfad = join(SHARED, datei);
	const ast = parseComponent(pfad);
	const pfade = [pfad];
	for (const stmt of (ast?.instance?.content?.body as any[]) ?? []) {
		if (stmt.type !== 'ImportDeclaration') continue;
		const quelle = String(stmt.source?.value ?? '');
		if (!quelle.endsWith('.svelte')) continue;
		pfade.push(
			quelle.startsWith('$lib/')
				? join(LIB, quelle.slice('$lib/'.length))
				: resolve(dirname(pfad), quelle)
		);
	}
	return pfade;
}

/** Sucht eine Marke in einer Menge von Anzeigeflaechen. */
function findeMarkeInFlaechen(
	pfade: string[],
	testid: string
): { pfad: string; knoten: Knoten; eltern: Knoten[] } | null {
	for (const pfad of pfade) {
		let ast: any;
		try {
			ast = parseComponent(pfad);
		} catch {
			continue; // nicht aufloesbarer Import: fuer diese Frage unerheblich
		}
		const treffer = findeMarke(ast, testid);
		if (treffer) return { pfad, ...treffer };
	}
	return null;
}

/** Die eine Zusicherung hinter AC-5 UND AC-7: die Flaeche traegt beide Marken,
 *  unter auffindbarer Testid und mit sichtbarer Beschriftung. Beide ACs
 *  verlangen wortgleich dasselbe ("tragen die Zeilen ebenfalls beide Marken")
 *  — deshalb EINE Pruefung, an verschiedenen Flaechen angewandt, statt zweier
 *  Formulierungen, die auseinanderlaufen koennen. */
function pruefeBeideMarken(pfade: string[], kontext: string, ac: string): void {
	for (const [testid, beschriftung, zweck] of [
		[MAIL_BADGE, 'Mail', 'die englische Fachkurzform der Mail-Stundentabelle (z.B. "Feels")'],
		[KURZFORM_BADGE, 'Kurzform', 'alle Kuerzel, die der Kanal dieser Flaeche sendet']
	] as const) {
		const marke = findeMarkeInFlaechen(pfade, testid);
		assert.ok(
			marke,
			`${ac} FAIL (RED): ${kontext} zeigt keine Marke mit data-testid="${testid}" ` +
				`— ${zweck}. Durchsucht: ${JSON.stringify(pfade.map((p) => p.split('/').pop()))}. ` +
				`Heute traegt die Zeile zwei Marken ohne Testid und ohne sichtbare ` +
				`Beschriftung (nur title-Attribut, WeatherV2Reihenfolge.svelte:102-111). ` +
				`Ohne stabilen Anker kann auch der Browser-Nachweis (AC-10/AC-13: fuenf ` +
				`Sichtbarkeits-Bedingungen in 14 Aufloesungen) nichts messen.`
		);
		const eigenerText = textVon(marke.knoten);
		const eltern = marke.eltern[marke.eltern.length - 1];
		const umfeld = eltern ? textVon(eltern.fragment ?? eltern) : '';
		assert.ok(
			eigenerText.includes(beschriftung) || umfeld.includes(beschriftung),
			`${ac} FAIL (RED): ${kontext} — die Marke "${testid}" traegt nirgends die ` +
				`sichtbare Beschriftung "${beschriftung}" (eigener Text ` +
				`${JSON.stringify(eigenerText)}, Umfeld ${JSON.stringify(umfeld)}). Ein ` +
				`Kuerzel ohne Beschriftung ist nicht aufloesbar — der Nutzer weiss nicht, ` +
				`ob "TF" in seiner Mail oder in seiner SMS steht.`
		);
	}
}

// ═══════════════════════════════════════════════════════════════════════════
// AC-5 — zwei beschriftete Marken je Zeile
// ═══════════════════════════════════════════════════════════════════════════

describe('AC-5: die Zeile des Touren-Editors traegt zwei beschriftete Marken', () => {
	test('beide Marken sind auffindbar und sichtbar beschriftet', () => {
		pruefeBeideMarken([REIHENFOLGE], 'der Touren-Editor', 'AC-5');
	});
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

// AC-7 hat ZWEI Halbsaetze, und der erste ist der, der die Arbeit bewacht:
// "Then tragen die Zeilen ebenfalls BEIDE MARKEN, und die Kurzform-Marke zeigt
// das Register-Kuerzel". Ein Test, der nur den zweiten prueft (erreicht die
// Flaeche `sms_code`?), ist heute schon gruen — `compare_metric_catalog.py:309`
// reicht das Feld seit #1453 durch — und kann die Umstellung nicht bewachen.
const VERGLEICHSFLAECHEN = [
	[
		'Vergleichs-Uebersicht',
		'WeatherMetricsTab.svelte',
		(attrs: Set<string>) => !attrs.has('offColumns')
	],
	['Vergleichs-Stundenverlauf', 'CompareHourlyLayoutControls.svelte', () => true],
	['Vergleichs-Ausblick', 'CompareOutlookLayoutControls.svelte', () => true]
] as const;

describe('AC-7: die drei Vergleichs-Editoren tragen ebenfalls beide Marken', () => {
	for (const [name, datei] of VERGLEICHSFLAECHEN) {
		test(`${name}: die Zeile traegt beide beschrifteten Marken`, () => {
			// Dieselbe Zusicherung wie AC-5 fuer den Touren-Editor — angewandt auf
			// die Bauteile, die GENAU DIESE Flaeche rendert.
			pruefeBeideMarken(anzeigeflaechen(datei), name, 'AC-7');
		});
	}
});

// ═══════════════════════════════════════════════════════════════════════════
// AC-6 / AC-7 — die QUELLE der Kurzform-Marke, je Flaeche (Adversary Runde 2,
// F002)
//
// Der Waechter darunter prueft nur, ob eine Flaeche `sms_code` IRGENDWIE
// erreicht — das tut sie ueber `metricById` auch dann noch, wenn die
// Kurzform-Marke laengst aus der falschen Quelle gespeist wird. Gemessen: der
// Adversary hat die Vergleichs-Einbettung auf die TRIP-Quelle umgebogen, alle
// 11 Tests blieben gruen. Das ist genau der Fehler, den diese Scheibe behebt —
// falsche Quelle, falsches Kuerzel —, nur auf der anderen Flaeche.
//
// Deshalb hier: nicht "erreicht die Flaeche sms_code?", sondern "woraus wird
// GENAU DIE `kuerzelById`-Eigenschaft gespeist?".
// ═══════════════════════════════════════════════════════════════════════════

/** Namen, unter denen die TRIP-SMS-Kuerzel (/api/sms-symbols) reisen. */
const TRIP_QUELLEN = ['metricSymbols', 'smsSymbols', 'sms_symbols'];
/** Der Name, unter dem das Register-Kuerzel des Vergleichs reist. */
const REGISTER_QUELLE = 'sms_code';

/** Namen, die AUSSCHLIESSLICH ueber die `kuerzelById`-Eigenschaft einer
 *  Einbettung erreichbar sind — die dort genannten Bezeichner plus, einen
 *  Schritt tief, alles aus ihrer Herleitung. Bewusst NICHT ueber alle
 *  Eigenschaften: `metricById` traegt `sms_code` ohnehin mit, und genau das
 *  machte den Waechter darunter blind. */
function kuerzelQuelle(
	datei: string,
	waehle: (attrs: Set<string>) => boolean
): Set<string> | null {
	const ast = parseComponent(join(SHARED, datei));
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
	const attr = ((ziel as Knoten).attributes ?? []).find(
		(a: Knoten) => a.type === 'Attribute' && a.name === 'kuerzelById'
	);
	if (!attr) return null;

	const direkt = geleseneNamen(attr);
	const alle = new Set(direkt);
	walk(ast.instance?.content?.body, (n) => {
		if (n.type !== 'VariableDeclarator') return;
		const name = n.id?.type === 'Identifier' ? n.id.name : null;
		if (!name || !direkt.has(name)) return;
		for (const gelesen of geleseneNamen(n.init)) alle.add(gelesen);
	});
	return alle;
}

describe('AC-6/AC-7: die Kurzform-Marke wird je Flaeche aus der RICHTIGEN Quelle gespeist', () => {
	test('Touren-Editor: aus /api/sms-symbols, NICHT aus dem Register', () => {
		const quelle = kuerzelQuelle('WeatherMetricsTab.svelte', (attrs) =>
			attrs.has('offColumns')
		);
		assert.ok(quelle, 'AC-6 FAIL: die Touren-Einbettung uebergibt kein `kuerzelById`.');
		assert.ok(
			TRIP_QUELLEN.some((q) => quelle!.has(q)),
			`AC-6 FAIL: die Kurzform-Marke des Touren-Editors wird nicht aus ` +
				`${TRIP_QUELLEN.join('/')} gespeist. Der Editor zeigte dann die ` +
				`ALARM-Stammdaten statt der Kuerzel, die die Trip-SMS wirklich sendet — ` +
				`bei "Gefuehlte Temperatur" ein "TF" statt "FK FD WC", bei ` +
				`"Nacht-Tiefsttemperatur" ein "TN", das in KEINER SMS vorkommt. ` +
				`Erreichbar: ${JSON.stringify([...quelle!].sort())}`
		);
		assert.ok(
			!quelle!.has(REGISTER_QUELLE),
			`AC-6 FAIL: die Kurzform-Marke des Touren-Editors wird (auch) aus ` +
				`\`${REGISTER_QUELLE}\` gespeist. Das ist die Quelle des VERGLEICHS; ` +
				`die Trip-SMS rendert aus SMS_MULTI_SYMBOLS_BY_METRIC / ` +
				`SMS_SYMBOL_BY_METRIC. Erreichbar: ${JSON.stringify([...quelle!].sort())}`
		);
	});

	for (const [name, datei, waehle] of VERGLEICHSFLAECHEN) {
		test(`${name}: aus dem Register, NICHT aus den Trip-SMS-Kuerzeln`, () => {
			const quelle = kuerzelQuelle(datei, waehle);
			assert.ok(quelle, `AC-7 FAIL: ${name} uebergibt kein \`kuerzelById\`.`);
			assert.ok(
				quelle!.has(REGISTER_QUELLE),
				`AC-7 FAIL: die Kurzform-Marke von ${name} wird nicht aus ` +
					`\`${REGISTER_QUELLE}\` gespeist. Die Vergleichs-SMS rendert aus ` +
					`\`get_sms_code()\` (comparison.py:625) — die Marke zeigte dann ein ` +
					`Kuerzel, das der Vergleich nie sendet. ` +
					`Erreichbar: ${JSON.stringify([...quelle!].sort())}`
			);
			const trip = TRIP_QUELLEN.filter((q) => quelle!.has(q));
			assert.deepEqual(
				trip,
				[],
				`AC-7 FAIL: die Kurzform-Marke von ${name} wird aus der TRIP-Quelle ` +
					`gespeist (${trip.join(', ')}). Trip und Vergleich senden aus ` +
					`VERSCHIEDENEN Tabellen; eine flaechenblinde Quelle macht den ` +
					`Vergleich falsch — genau der Fehler, den diese Scheibe behebt, nur ` +
					`auf der anderen Flaeche.`
			);
		});
	}
});

describe('AC-7: die Kurzform-Marke des Vergleichs speist sich aus dem Register', () => {
	for (const [name, datei, waehle] of VERGLEICHSFLAECHEN) {
		test(`${name}: die Zeile erreicht das Register-Kuerzel (sms_code)`, () => {
			// INVARIANTEN-WAECHTER, heute gruen und absichtlich so: die Datengrundlage
			// steht seit #1453. Er bewacht, dass die Umstellung sie nicht mitreisst —
			// eine flaechenblinde Korrektur auf die Trip-SMS-Kuerzel wuerde den
			// Vergleich falsch machen (er sendet aus `get_sms_code()`, comparison.py).
			// KEIN Nachweis, dass AC-7 erfuellt ist; das leistet der Test darueber.
			const erreicht = erreichteNamen(join(SHARED, datei), waehle);
			assert.ok(erreicht, `${name}: WeatherV2Reihenfolge-Einbettung nicht gefunden`);
			assert.ok(
				erreicht!.has('sms_code'),
				`AC-7 FAIL: ${name} erreicht kein \`sms_code\`. Eine Zeile ohne diese ` +
					`Quelle koennte nur ein Kuerzel zeigen, das der Vergleich nie sendet. ` +
					`Erreichbar: ${JSON.stringify([...erreicht!].sort())}`
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
		// GEMESSEN 2026-08-12 (GREEN-Phase): OHNE die folgende Env-Bereinigung
		// meldet dieser Test IMMER `status === 0`. Node vererbt an das Kind
		// `NODE_TEST_CONTEXT` (gesetzt, weil DIESE Datei selbst unter
		// `node --test` laeuft); in dieser Betriebsart schreibt der Laeufer TAP
		// an den Elternprozess und beendet sich mit 0, auch wenn Tests scheitern.
		// Beleg: derselbe Aufruf liefert direkt `exit=1`, mit
		// `NODE_TEST_CONTEXT=child-v8` gesetzt `exit=0`.
		// Der Waechter war damit ein Waechter, der nichts bewacht — er war auch
		// in der RED-Phase gruen, waehrend die geprueften vier Editoren rot waren.
		const kindUmgebung = { ...process.env };
		delete kindUmgebung.NODE_TEST_CONTEXT;
		const ergebnis = spawnSync(
			process.execPath,
			[
				'--import',
				'./test-lib-loader.mjs',
				'--experimental-strip-types',
				'--test',
				'src/lib/components/shared/__tests__/weather_metric_name_forms_visible.test.ts'
			],
			{ cwd: FRONTEND, encoding: 'utf-8', env: kindUmgebung }
		);
		// Zweiter, unabhaengiger Beleg: der Laeufer MUSS eine Bilanz gedruckt
		// haben. Ein Kind, das gar nicht erst startet, waere sonst "bestanden".
		assert.match(
			ergebnis.stdout ?? '',
			/^# fail 0$/m,
			`AC-8 FAIL: der Bestandswaechter meldet keine Null-Bilanz.\n` +
				`${ergebnis.stdout}\n${ergebnis.stderr}`
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
