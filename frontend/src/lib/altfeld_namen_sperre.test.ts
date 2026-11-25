// # doc-compliance-test
// Feldnamen-Sperre Frontend — Issue #3298 (Epic #3122, Spec-AC-38 zweiter Teil).
// Spec: docs/specs/modules/feat_3298_altfeld_typen_sperre.md (AC-5, AC-6, AC-7; AC-1/AC-8 Zusatz)
// Vorbild: tests/test_altfeld_namen_sperre.py (Backend-Sperre #3277).
//
// Werkzeug-Klasse (Ausnahme `# doc-compliance-test` der Test-Politik): die Sperre liest
// Produktions-Quelltext als DATEN. Dateimenge: rekursiv frontend/src, .ts/.svelte/.js, ohne
// `__tests__/`, `*.test.ts`/`*.spec.ts`, `*Pruefstand.ts`, `*Anker.ts`. Kommentare (`//`, `/* */`,
// `<!-- -->`) zaehlen nicht; Treffer wortgenau (`\bname\b`) auf die zehn Namen aus `ALTFELDER`
// (src/app/loader.py). ERLAUBT = (Datei, Name) -> (Grund >= 20 Zeichen, Ablaufdatum); startet leer.
//
// RED heute (Ist-Stand vor dem Rueckbau): der Scan findet Altnamen in types.ts, pickEigenfelder.ts,
// compareEditorSave.ts, weatherMetricsCompareSave.ts, compareChannelMetricLayouts.ts,
// alarme-/versand-/wertebereicheVergleichSpeicherung.ts; hourlyFriendlyMap.ts existiert noch;
// types.ts kennt noch multi_day_trend_morning/evening.
// Schon GRUEN (Selbstnachweis, gewollt): AC-6 (synthetischer Quelltext) und AC-7 (Abgleich gegen
// ALTFELDER samt Gegenprobe) — sie pruefen das Werkzeug, nicht den Baum.
//
// Ausfuehren (aus frontend/):
//   npm test -- src/lib/altfeld_namen_sperre.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { existsSync, readdirSync, readFileSync, statSync } from 'node:fs';
import { join, relative } from 'node:path';
import { fileURLToPath } from 'node:url';

const SRC = fileURLToPath(new URL('../', import.meta.url)); // frontend/src/
const WURZEL = fileURLToPath(new URL('../../../', import.meta.url)); // Repo-Wurzel

/** Die zehn Altfelder (Spec #3122 Teil A Nr. 8, ADR-0124 Nr. 6) — muss `ALTFELDER` gleichen (AC-7). */
export const ALTFELD_NAMEN: readonly string[] = [
	'channel_layouts',
	'channel_layouts_per_report',
	'channel_active_metrics',
	'outlook_metrics',
	'outlook_metric_formats',
	'hourly_metrics',
	'hourly_metric_formats',
	'show_outlook',
	'multi_day_trend_reports',
	'outlook_enabled'
];

type Ausnahmen = Record<string, { grund: string; ablauf: string }>;

/** (Datei relativ zu frontend/src, Name) -> Grund + Ablaufdatum (ISO). Startet leer (Spec). */
const ERLAUBT: Ausnahmen = {};

const schluesselVon = (datei: string, name: string) => `${datei}::${name}`;
const heuteIso = () => new Date().toISOString().slice(0, 10);

/** Entfernt Block-, HTML- und Zeilenkommentare; Zeilenzahl bleibt erhalten. */
function ohneKommentare(text: string): string {
	const leeren = (s: string) => s.replace(/[^\n]/g, ' ');
	return text
		.replace(/\/\*[\s\S]*?\*\//g, leeren)
		.replace(/<!--[\s\S]*?-->/g, leeren)
		.replace(/(^|[^:'"`])\/\/[^\n]*/g, (_m, vor: string) => vor);
}

/** Verstoesse in einem Quelltext, die keine gueltige Ausnahme deckt: `datei:zeile: name`. */
export function verstoesse(
	quelltext: string,
	datei: string,
	erlaubt: Ausnahmen = ERLAUBT,
	heute: string = heuteIso()
): string[] {
	const muster = new RegExp(`\\b(${ALTFELD_NAMEN.join('|')})\\b`, 'g');
	const out: string[] = [];
	ohneKommentare(quelltext)
		.split('\n')
		.forEach((zeile, i) => {
			for (const m of zeile.matchAll(muster)) {
				const a = erlaubt[schluesselVon(datei, m[1])];
				if (a && a.ablauf >= heute && a.grund.length >= 20) continue;
				out.push(`${datei}:${i + 1}: ${m[1]}`);
			}
		});
	return out;
}

const istAusgenommen = (rel: string) =>
	/(^|\/)__tests__\//.test(rel) ||
	/\.(test|spec)\.[tj]s$/.test(rel) ||
	/Pruefstand\.ts$/.test(rel) ||
	/Anker\.ts$/.test(rel);

function produktionsdateien(): string[] {
	const aus: string[] = [];
	const lauf = (dir: string) => {
		for (const name of readdirSync(dir)) {
			const voll = join(dir, name);
			if (statSync(voll).isDirectory()) {
				if (name !== 'node_modules') lauf(voll);
				continue;
			}
			const rel = relative(SRC, voll).split('\\').join('/');
			if (/\.(ts|js|svelte)$/.test(name) && !istAusgenommen(rel)) aus.push(rel);
		}
	};
	lauf(SRC);
	return aus;
}

/** Die Namen der Liste `ALTFELDER = (...)` aus src/app/loader.py. */
function loaderAltfelder(): string[] {
	const text = readFileSync(join(WURZEL, 'src/app/loader.py'), 'utf8');
	const m = /^ALTFELDER\s*=\s*\(([\s\S]*?)\)/m.exec(text);
	assert.ok(m, 'ALTFELDER in src/app/loader.py nicht gefunden — Abgleich waere leer');
	return [...m[1].matchAll(/["']([a-z_]+)["']/g)].map((x) => x[1]);
}

/** Symmetrische Differenz zweier Namensmengen (leer = identisch). */
function abweichung(a: readonly string[], b: readonly string[]): string[] {
	const sa = new Set(a);
	const sb = new Set(b);
	return [...[...sa].filter((n) => !sb.has(n)), ...[...sb].filter((n) => !sa.has(n))].sort();
}

describe('#3298 AC-5: kein Altname im Frontend-Produktionscode (RED auf Ist-Stand)', () => {
	test('Dateimenge ist nicht trivial (Scan laeuft wirklich ueber frontend/src)', () => {
		const dateien = produktionsdateien();
		assert.ok(dateien.length > 100, `nur ${dateien.length} Produktionsdateien gefunden`);
		assert.ok(dateien.includes('lib/types.ts'), 'lib/types.ts fehlt in der Dateimenge');
		assert.ok(!dateien.some((d) => /__tests__\//.test(d)), '__tests__ darf nicht gescannt werden');
	});

	test('Scan des echten Baums: keine Treffer (Datei:Zeile: Name)', () => {
		const funde: string[] = [];
		for (const rel of produktionsdateien()) {
			funde.push(...verstoesse(readFileSync(join(SRC, rel), 'utf8'), rel));
		}
		assert.deepEqual(funde, [], `Altnamen im Frontend-Produktionscode:\n${funde.join('\n')}`);
	});

	test('jede ERLAUBT-Ausnahme ist gueltig (Grund >= 20 Zeichen, Ablauf nicht ueberschritten)', () => {
		const heute = heuteIso();
		for (const [k, a] of Object.entries(ERLAUBT)) {
			assert.ok(a.grund.length >= 20, `${k}: Grund zu kurz`);
			assert.ok(a.ablauf >= heute, `${k}: Ausnahme abgelaufen (${a.ablauf})`);
		}
	});
});

describe('#3298 AC-6: Selbstnachweis mit synthetischem Quelltext (Werkzeug, schon gruen)', () => {
	const D = 'lib/x.ts';
	const HEUTE = '2026-11-25';

	test('Verstoss erkannt, mit Datei, Zeile und Name', () => {
		assert.deepEqual(verstoesse("const a = 1;\nconst b = p.outlook_enabled;\n", D, {}, HEUTE), [
			`${D}:2: outlook_enabled`
		]);
	});

	test('Name in Zeilen-, Block- und HTML-Kommentar ist kein Treffer', () => {
		const q = '// channel_layouts\n/* hourly_metrics\n outlook_metrics */\n<!-- show_outlook -->\nconst x = 1;';
		assert.deepEqual(verstoesse(q, D, {}, HEUTE), []);
	});

	test('hourly_enabled und laengere Namen loesen nichts aus (wortgenau)', () => {
		const q = "const a = p.hourly_enabled; const b = 'hourly_metrics_x'; const c = foo_outlook_enabled;";
		assert.deepEqual(verstoesse(q, D, {}, HEUTE), []);
	});

	test('channel_layouts_per_report zaehlt einmal als eigener Name, nicht als channel_layouts', () => {
		assert.deepEqual(verstoesse("k = 'channel_layouts_per_report';", D, {}, HEUTE), [
			`${D}:1: channel_layouts_per_report`
		]);
	});

	test('gueltiger ERLAUBT-Eintrag besteht', () => {
		const e = { [schluesselVon(D, 'hourly_metrics')]: { grund: 'Begruendung mit genug Zeichen', ablauf: '2027-02-23' } };
		assert.deepEqual(verstoesse("x = 'hourly_metrics';", D, e, HEUTE), []);
	});

	test('abgelaufener ERLAUBT-Eintrag schlaegt an', () => {
		const e = { [schluesselVon(D, 'hourly_metrics')]: { grund: 'Begruendung mit genug Zeichen', ablauf: '2026-11-24' } };
		assert.deepEqual(verstoesse("x = 'hourly_metrics';", D, e, HEUTE), [`${D}:1: hourly_metrics`]);
	});

	test('zu kurzer Grund wird abgelehnt', () => {
		const e = { [schluesselVon(D, 'hourly_metrics')]: { grund: 'zu kurz', ablauf: '2027-02-23' } };
		assert.deepEqual(verstoesse("x = 'hourly_metrics';", D, e, HEUTE), [`${D}:1: hourly_metrics`]);
	});

	test('Ausnahme gilt nur fuer ihre Datei', () => {
		const e = { [schluesselVon('lib/andere.ts', 'hourly_metrics')]: { grund: 'Begruendung mit genug Zeichen', ablauf: '2027-02-23' } };
		assert.deepEqual(verstoesse("x = 'hourly_metrics';", D, e, HEUTE), [`${D}:1: hourly_metrics`]);
	});
});

describe('#3298 AC-7: Namensliste == ALTFELDER in src/app/loader.py (Werkzeug, schon gruen)', () => {
	test('beide Mengen identisch, zehn Namen', () => {
		const loader = loaderAltfelder();
		assert.equal(loader.length, 10, `ALTFELDER hat ${loader.length} Namen`);
		assert.equal(new Set(ALTFELD_NAMEN).size, 10);
		assert.deepEqual(abweichung(ALTFELD_NAMEN, loader), []);
	});

	test('Gegenprobe: eine synthetisch abweichende Liste wird erkannt', () => {
		const loader = loaderAltfelder();
		assert.deepEqual(abweichung(ALTFELD_NAMEN.filter((n) => n !== 'outlook_enabled'), loader), ['outlook_enabled']);
		assert.deepEqual(abweichung([...ALTFELD_NAMEN, 'neues_altfeld'], loader), ['neues_altfeld']);
	});
});

describe('#3298 AC-1 (Zusatz): types.ts ohne multi_day_trend_morning/evening', () => {
	// Nicht Teil der Sperre (nicht in ALTFELDER); Spec Entscheidung 1: nur aus dem Typ entfernen.
	test('kein multi_day_trend_morning/evening ausserhalb von Kommentaren', () => {
		const funde = ohneKommentare(readFileSync(join(SRC, 'lib/types.ts'), 'utf8'))
			.split('\n')
			.flatMap((z, i) => (/\bmulti_day_trend_(morning|evening)\b/.test(z) ? [`lib/types.ts:${i + 1}`] : []));
		assert.deepEqual(funde, []);
	});
});

describe('#3298 AC-8: hourlyFriendlyMap.ts geloescht, kein Produktionsimport', () => {
	const TOT = 'lib/components/compare/hourlyFriendlyMap.ts';

	test(`geloescht: ${TOT}`, () => {
		assert.equal(existsSync(join(SRC, TOT)), false, `${TOT} existiert noch`);
	});

	test('keine Produktionsdatei importiert hourlyFriendlyMap (statisch oder dynamisch)', () => {
		const muster = /(?:from|import\s*\()\s*['"][^'"]*\/hourlyFriendlyMap(?:\.ts|\.js)?['"]/;
		const funde = produktionsdateien().filter((rel) => muster.test(readFileSync(join(SRC, rel), 'utf8')));
		assert.deepEqual(funde, []);
	});
});
