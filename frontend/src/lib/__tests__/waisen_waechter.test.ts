// # doc-compliance-test
// Waisen-Wächter — Issue #3366 (Nachlauf #3297, Epic #3122).
// Spec: docs/specs/modules/rework_3366_waisen_waechter_layout_tab.md (AC-1 bis AC-4, AC-8)
//
// Architektur-Wächter über den echten Importgraphen (wie bausteine_waechter_regeln.ts und
// altfeld_namen_sperre.test.ts), kein Dateiinhalt-Check als Verhaltensnachweis; das Nutzerverhalten
// belegt die Frontend-Suite (AC-7).
//
// Waise = Nicht-Test-Datei unter frontend/src/lib, die von keiner Wurzel transitiv erreicht wird.
// Wurzeln: alle Nicht-Test-Dateien unter frontend/src/routes/ und frontend/src/*.ts (hooks,
// service-worker). Kanten: `import … from`, `export … from`, Seiteneffekt-`import '…'`,
// dynamisches `import('…')`, `import.meta.glob`, `new URL(…, import.meta.url)`.
// Auflösung: Alias `$lib`, relative Pfade, `.js`→`.ts`, `.svelte`, Barrels (`index.*`).
// Dateien unter `__tests__/`, `*.test.*`, `*.spec.*` sind weder Wurzel noch Aufrufer.
//
// Ratsche: Waisen (ohne AUSNAHMEN) == BEKANNTE_WAISEN, BEKANNTE_WAISEN.length <= OBERGRENZE_WAISEN.
// Die Liste darf nur schrumpfen: jede Löschscheibe streicht ihre Einträge und senkt die Konstante im
// selben Commit. Ein neuer Eintrag geht nur, wenn jemand OBERGRENZE_WAISEN sichtbar erhöht.
//
// #3383 S1 (Spec docs/specs/modules/rework_3383_waisen_s1.md, AC-3/AC-4): Gruppe S1 gestrichen,
// OBERGRENZE_WAISEN 26. RED vor der Löschung S1: die 14 S1-Dateien existieren noch und stehen bewusst
// nicht mehr in BEKANNTE_WAISEN; Selbstnachweis (e) ist rot, bis die Wächterlogik die Array-Form von
// import.meta.glob laut meldet.
//
// Ausführen (aus frontend/):
//   npm test -- src/lib/__tests__/waisen_waechter.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { existsSync, mkdirSync, mkdtempSync, readdirSync, readFileSync, rmSync, statSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join, posix, relative } from 'node:path';
import { fileURLToPath } from 'node:url';

const SRC = fileURLToPath(new URL('../../', import.meta.url)); // frontend/src/

/** Begründete Konventionsdateien, die keinen Aufrufer brauchen (getrennt von der Ratsche). */
export const AUSNAHMEN: Record<string, string> = {
	'lib/index.ts': 'SvelteKit-Konventionsdatei für den Alias $lib (Gerüst des Frameworks), Entscheidung Tech Lead #3366'
};

/** Bekannte Waisen (Ratsche, darf nur schrumpfen). Löschung je Scheibe: S1 #3383, S3 #3385, S4 #3384. */
export const BEKANNTE_WAISEN: string[] = [
	// S4 #3384: compare/edit/mobile/utils
	'lib/components/compare/AddReportCard.svelte',
	'lib/components/compare/CreateGroupDialog.svelte',
	'lib/components/compare/LocationPreviewMap.svelte',
	'lib/components/compare/layoutPreviewRows.ts',
	'lib/components/compare/versandPropsAus.ts',
	'lib/components/compare/wetterMetrikenPropsAus.ts',
	'lib/components/edit/EditRouteSection.svelte',
	'lib/components/edit/EditWeatherSection.svelte',
	'lib/components/edit/WeatherSummaryCard.svelte',
	'lib/components/edit/weatherSummary.ts',
	'lib/components/mobile/DrawerGroup.svelte',
	'lib/components/mobile/DrawerItem.svelte',
	'lib/components/mobile/NavIcon.svelte',
	'lib/components/trip-detail/waypoints/WaypointPin.svelte',
	'lib/utils/alertMetricCatalogIds.ts',
	'lib/utils/horizonHelpers.ts',
	'lib/utils/naturalSort.ts',
	'lib/utils/rightColumn.ts',
	'lib/utils/weatherEmoji.ts',
	// S1 #3383 gelöscht (14 Einträge, Lösch-Nachweis trip_pfad_altfeld_loeschnachweis_3297.test.ts)
	// S3 #3385: versand-tab
	'lib/components/shared/versand-tab/VTBriefingChannels.svelte',
	'lib/components/shared/versand-tab/VTLaufzeitRoute.svelte',
	'lib/components/shared/versand-tab/VTLaufzeitVergleich.svelte',
	'lib/components/shared/versand-tab/VTNextBriefing.svelte',
	'lib/components/shared/versand-tab/VTSchedulePlan.svelte',
	'lib/components/shared/versand-tab/channelContactLabel.ts',
	'lib/components/shared/versand-tab/vtBriefingChannelsText.ts'
];

/**
 * Feste Obergrenze (Literal, Muster BESTAND_OBERGRENZE): 56 Waisen − 15 gelöscht (#3366 S2) − lib/index.ts = 40;
 * − 14 gelöscht (#3383 S1) = 26 (19 S4 + 7 S3).
 */
export const OBERGRENZE_WAISEN = 26;

const istTest = (rel: string) => /(^|\/)__tests__\//.test(rel) || /\.(test|spec)\.(ts|js|mjs)$/.test(rel);
const ENDUNGEN = ['.svelte', '.ts', '.js', '.mjs', '.svelte.ts', '.svelte.js'];
const KANTE =
	/(?:from\s*|import\s*\(\s*|import\s+|require\(\s*)['"]([^'"]+)['"]|import\.meta\.glob\(\s*['"]([^'"]+)['"]|new URL\(\s*['"]([^'"]+)['"]\s*,\s*import\.meta\.url/g;

/** Alle Quelldateien (.svelte/.ts/.js/.mjs) unter src, relativ mit `/`. */
function alleDateien(src: string): string[] {
	const aus: string[] = [];
	const lauf = (dir: string) => {
		for (const name of readdirSync(dir)) {
			const voll = join(dir, name);
			if (statSync(voll).isDirectory()) {
				if (name !== 'node_modules') lauf(voll);
			} else if (/\.(svelte|ts|js|mjs)$/.test(name)) {
				aus.push(relative(src, voll).split('\\').join('/'));
			}
		}
	};
	lauf(src);
	return aus;
}

/** Glob-Muster (`**`, `*`, `?`, `{a,b}`) als Regex über relative Pfade. */
function globRegex(muster: string): RegExp {
	let r = '';
	for (let i = 0; i < muster.length; i++) {
		const c = muster[i];
		if (c === '*' && muster[i + 1] === '*') {
			r += '.*';
			i++;
			if (muster[i + 1] === '/') i++;
		} else if (c === '*') r += '[^/]*';
		else if (c === '?') r += '[^/]';
		else if (c === '{') r += '(';
		else if (c === '}') r += ')';
		else if (c === ',') r += '|';
		else r += c.replace(/[.+^$()|[\]\\]/g, '\\$&');
	}
	return new RegExp(`^${r}$`);
}

/** Modulpfad → relative Basis (ohne Endungsprobe) oder null (Paket). */
function basis(spez: string, von: string): string | null {
	if (spez.startsWith('$lib/')) return posix.normalize('lib/' + spez.slice(5));
	if (spez === '$lib') return 'lib';
	if (spez.startsWith('.')) return posix.normalize(posix.join(posix.dirname(von), spez));
	return null;
}

function aufloesen(spez: string, von: string, menge: Set<string>): string | null {
	const b = basis(spez, von);
	if (b === null) return null;
	const kandidaten = [b, b.endsWith('.js') ? b.slice(0, -3) + '.ts' : b];
	for (const e of ENDUNGEN) kandidaten.push(b + e);
	for (const e of ENDUNGEN) kandidaten.push(`${b}/index${e}`);
	return kandidaten.find((k) => menge.has(k)) ?? null;
}

function kanten(src: string, rel: string, dateien: string[], menge: Set<string>): string[] {
	const text = readFileSync(join(src, rel), 'utf8');
	// Fail-closed (#3383 AC-4 e): die Array-Form würde KANTE still übergehen und Ziele als Waise melden.
	if (/import\.meta\.glob\(\s*\[/.test(text)) {
		throw new Error(`${rel}: Array-Form von import.meta.glob nicht unterstützt — Wächterlogik ergänzen`);
	}
	const aus: string[] = [];
	for (const m of text.matchAll(KANTE)) {
		if (m[2] !== undefined) {
			const b = basis(m[2], rel);
			if (b === null) continue;
			const re = globRegex(b);
			aus.push(...dateien.filter((d) => re.test(d)));
			continue;
		}
		const ziel = aufloesen(m[1] ?? m[3], rel, menge);
		if (ziel) aus.push(ziel);
	}
	return aus;
}

/** Kern: alle Waisen unter `lib/` (relativ zu src, sortiert), ohne Ausnahmenfilter. */
export function findeWaisen(src: string): string[] {
	const dateien = alleDateien(src);
	const menge = new Set(dateien);
	const wurzeln = dateien.filter((d) => !istTest(d) && (d.startsWith('routes/') || (!d.includes('/') && d.endsWith('.ts'))));
	const gesehen = new Set(wurzeln);
	const stapel = [...wurzeln];
	while (stapel.length > 0) {
		const d = stapel.pop()!;
		for (const z of kanten(src, d, dateien, menge)) {
			if (!gesehen.has(z) && !istTest(z)) {
				gesehen.add(z);
				stapel.push(z);
			}
		}
	}
	return dateien.filter((d) => d.startsWith('lib/') && !istTest(d) && !gesehen.has(d)).sort();
}

/** Ratsche: liefert die Fehlermeldungen (leer = grün). */
export function pruefeRatsche(
	src: string,
	waisen: string[],
	bekannte: string[],
	ausnahmen: Record<string, string>,
	obergrenze: number
): string[] {
	const fehler: string[] = [];
	const istWaise = new Set(waisen);
	const gelistet = new Set(bekannte);
	for (const w of waisen) {
		if (w in ausnahmen || gelistet.has(w)) continue;
		fehler.push(`${w}: neue Waise ohne Aufrufer aus routes/ — löschen oder anbinden (nicht still in BEKANNTE_WAISEN aufnehmen)`);
	}
	for (const b of bekannte) {
		if (!existsSync(join(src, b))) fehler.push(`${b}: existiert nicht mehr — aus der Liste streichen und OBERGRENZE_WAISEN senken`);
		else if (!istWaise.has(b)) fehler.push(`${b}: ist wieder erreichbar — aus der Liste streichen und OBERGRENZE_WAISEN senken`);
	}
	if (bekannte.length > obergrenze) {
		fehler.push(`BEKANNTE_WAISEN hat ${bekannte.length} Einträge, OBERGRENZE_WAISEN ist ${obergrenze} — die Liste darf nur schrumpfen`);
	}
	if (new Set(bekannte).size !== bekannte.length) fehler.push('BEKANNTE_WAISEN enthält doppelte Einträge');
	for (const [a, grund] of Object.entries(ausnahmen)) {
		if (!existsSync(join(src, a))) fehler.push(`${a}: Ausnahme existiert nicht mehr — aus AUSNAHMEN streichen`);
		if (grund.trim().length < 20) fehler.push(`${a}: Ausnahme ohne ausreichende Begründung`);
	}
	return fehler;
}

describe('#3366 AC-1/AC-8, #3383 AC-3: Waisen-Wächter gegen den echten Baum', () => {
	test('Waisenmenge (ohne AUSNAHMEN) ist genau BEKANNTE_WAISEN ohne Gruppe S1 und hält OBERGRENZE_WAISEN 26', () => {
		const fehler = pruefeRatsche(SRC, findeWaisen(SRC), BEKANNTE_WAISEN, AUSNAHMEN, OBERGRENZE_WAISEN);
		assert.deepEqual(fehler, [], fehler.join('\n'));
	});
});

/**
 * Erfundener Mini-Baum (Selbstnachweis), liefert das src-Verzeichnis.
 * `f001`: zusätzliche Dateien für die Kantenarten aus Finding F001 (#3383 AC-4 a–d).
 * `arrayGlob`: eine Route mit der nicht unterstützten Array-Form von `import.meta.glob` (#3383 AC-4 e).
 */
function miniBaum(opt: { f001?: boolean; arrayGlob?: boolean } = {}): string {
	const wurzel = mkdtempSync(join(tmpdir(), 'waisen-waechter-'));
	const src = join(wurzel, 'src');
	const datei = (rel: string, inhalt: string) => {
		mkdirSync(dirname(join(src, rel)), { recursive: true });
		writeFileSync(join(src, rel), inhalt);
	};
	datei('hooks.server.ts', "import { h } from '$lib/hookHelfer.js';\n");
	datei('routes/+page.svelte', "<script>import { Echt } from '$lib/barrel';\nconst d = import('./lazy.js');</script>\n");
	datei('routes/lazy.ts', "export * from '../lib/dynamisch';\n");
	datei('lib/hookHelfer.ts', 'export const h = 1;\n');
	datei('lib/barrel/index.ts', "export { default as Echt } from './Echt.svelte';\n");
	datei('lib/barrel/Echt.svelte', '<p>echt</p>\n');
	datei('lib/dynamisch.ts', 'export const d = 1;\n');
	datei('lib/erfundeneWaise.ts', 'export const w = 1;\n');
	datei('lib/nurTest.ts', 'export const t = 1;\n');
	datei('lib/__tests__/nurTest.test.ts', "import { t } from '../nurTest.js';\n");
	datei('lib/index.ts', '// Konvention\n');
	if (opt.f001) {
		// (a) dynamischer Import, eigene Datei, ohne `export * from` dazwischen
		datei('routes/dyn/+page.ts', "export const load = () => import('$lib/nurDynamisch.js');\n");
		datei('lib/nurDynamisch.ts', 'export const n = 1;\n');
		// (b) import.meta.glob (String-Form): passende Dateien erreichbar, nicht passende bleiben Waise
		datei('routes/glob/+page.ts', "export const module = import.meta.glob('$lib/glob/*.ts');\n");
		datei('lib/glob/a.ts', 'export const a = 1;\n');
		datei('lib/glob/b.ts', 'export const b = 1;\n');
		datei('lib/glob/nicht.svelte', '<p>passt nicht zum Muster</p>\n');
		// (c) new URL('…', import.meta.url)
		datei('routes/url/+page.ts', "export const u = new URL('../../lib/perUrl.ts', import.meta.url);\n");
		datei('lib/perUrl.ts', 'export const p = 1;\n');
		// (d) nur von Testdateien unter routes/ importiert
		datei('routes/foo/__tests__/x.test.ts', "import { r } from '../../../lib/nurRoutesTest.js';\n");
		datei('routes/foo/y.test.ts', "import { r2 } from '$lib/nurRoutesTest2';\n");
		datei('lib/nurRoutesTest.ts', 'export const r = 1;\n');
		datei('lib/nurRoutesTest2.ts', 'export const r2 = 1;\n');
	}
	if (opt.arrayGlob) {
		datei('routes/arr/+page.ts', "export const module = import.meta.glob(['$lib/arr/*.ts']);\n");
		datei('lib/arr/c.ts', 'export const c = 1;\n');
	}
	return src;
}

/** Mini-Baum bauen, Funktion ausführen, Baum sicher entfernen. */
function mitMiniBaum<T>(opt: { f001?: boolean; arrayGlob?: boolean }, f: (src: string) => T): T {
	const src = miniBaum(opt);
	try {
		return f(src);
	} finally {
		rmSync(dirname(src), { recursive: true, force: true });
	}
}

describe('#3366 AC-2/AC-3/AC-4: Selbstnachweis am erfundenen Mini-Baum', () => {
	test('Kern: erfundene Waise und nur-von-Test erreichte Datei sind Waisen; Barrel, dynamisch und hooks erreichbar', () => {
		const src = miniBaum();
		try {
			assert.deepEqual(findeWaisen(src), ['lib/erfundeneWaise.ts', 'lib/index.ts', 'lib/nurTest.ts']);
		} finally {
			rmSync(dirname(src), { recursive: true, force: true });
		}
	});

	test('AC-2: nicht gelistete Waise macht rot und nennt den Pfad', () => {
		const src = miniBaum();
		try {
			const fehler = pruefeRatsche(src, findeWaisen(src), ['lib/nurTest.ts'], AUSNAHMEN, 1);
			assert.equal(fehler.length, 1, fehler.join('\n'));
			assert.match(fehler[0], /^lib\/erfundeneWaise\.ts: neue Waise/);
		} finally {
			rmSync(dirname(src), { recursive: true, force: true });
		}
	});

	test('AC-2: Eintrag in die Liste ohne Erhöhen der Obergrenze bleibt rot', () => {
		const src = miniBaum();
		try {
			const fehler = pruefeRatsche(src, findeWaisen(src), ['lib/nurTest.ts', 'lib/erfundeneWaise.ts'], AUSNAHMEN, 1);
			assert.equal(fehler.length, 1, fehler.join('\n'));
			assert.match(fehler[0], /OBERGRENZE_WAISEN ist 1/);
			assert.deepEqual(pruefeRatsche(src, findeWaisen(src), ['lib/nurTest.ts', 'lib/erfundeneWaise.ts'], AUSNAHMEN, 2), []);
		} finally {
			rmSync(dirname(src), { recursive: true, force: true });
		}
	});

	test('AC-3: gelisteter, aber erreichbarer und gelisteter, nicht vorhandener Eintrag melden "aus der Liste streichen"', () => {
		const src = miniBaum();
		try {
			const bekannte = ['lib/nurTest.ts', 'lib/erfundeneWaise.ts', 'lib/barrel/Echt.svelte', 'lib/gibtsNicht.ts'];
			const fehler = pruefeRatsche(src, findeWaisen(src), bekannte, AUSNAHMEN, 4);
			assert.equal(fehler.length, 2, fehler.join('\n'));
			assert.match(fehler[0], /^lib\/barrel\/Echt\.svelte: ist wieder erreichbar — aus der Liste streichen/);
			assert.match(fehler[1], /^lib\/gibtsNicht\.ts: existiert nicht mehr — aus der Liste streichen/);
		} finally {
			rmSync(dirname(src), { recursive: true, force: true });
		}
	});
});

// #3383 AC-4 (Finding F001 aus #3366): jede Kantenart und der Test-Ausschluss unter routes/ einzeln
// bewiesen; die Array-Form von import.meta.glob ist nicht unterstützt und muss laut rot werden.
describe('#3383 AC-4: Selbstnachweis F001 am erfundenen Mini-Baum', () => {
	test('exakte Mini-Baum-Liste mit den F001-Dateien', () => {
		const waisen = mitMiniBaum({ f001: true }, findeWaisen);
		assert.deepEqual(waisen, [
			'lib/erfundeneWaise.ts',
			'lib/glob/nicht.svelte',
			'lib/index.ts',
			'lib/nurRoutesTest.ts',
			'lib/nurRoutesTest2.ts',
			'lib/nurTest.ts'
		]);
	});

	test('(a) dynamischer Import macht die Zieldatei erreichbar', () => {
		const waisen = mitMiniBaum({ f001: true }, findeWaisen);
		assert.ok(!waisen.includes('lib/nurDynamisch.ts'), 'lib/nurDynamisch.ts gilt trotz import(…) als Waise');
	});

	test('(b) import.meta.glob macht die passenden Dateien erreichbar, nicht passende bleiben Waise', () => {
		const waisen = mitMiniBaum({ f001: true }, findeWaisen);
		assert.ok(!waisen.includes('lib/glob/a.ts'), 'lib/glob/a.ts gilt trotz glob als Waise');
		assert.ok(!waisen.includes('lib/glob/b.ts'), 'lib/glob/b.ts gilt trotz glob als Waise');
		assert.ok(waisen.includes('lib/glob/nicht.svelte'), 'Datei außerhalb des Glob-Musters gilt als erreichbar');
	});

	test("(c) new URL('…', import.meta.url) gilt als Verweis", () => {
		const waisen = mitMiniBaum({ f001: true }, findeWaisen);
		assert.ok(!waisen.includes('lib/perUrl.ts'), 'lib/perUrl.ts gilt trotz new URL(…, import.meta.url) als Waise');
	});

	test('(d) nur von Testdateien unter routes/ importiert gilt als Waise', () => {
		const waisen = mitMiniBaum({ f001: true }, findeWaisen);
		assert.ok(waisen.includes('lib/nurRoutesTest.ts'), 'routes/foo/__tests__/x.test.ts zählt als Wurzel oder Aufrufer');
		assert.ok(waisen.includes('lib/nurRoutesTest2.ts'), 'routes/foo/y.test.ts zählt als Wurzel oder Aufrufer');
	});

	test('(e) Array-Form von import.meta.glob wird laut rot statt still übergangen', () => {
		assert.throws(
			() => mitMiniBaum({ arrayGlob: true }, findeWaisen),
			/Array-Form von import\.meta\.glob nicht unterstützt — Wächterlogik ergänzen/
		);
	});
});
