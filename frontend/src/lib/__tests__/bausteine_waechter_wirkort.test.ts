// doc-compliance-test
// Issue #2913, Fix-Loop 1 (Adversary F001, F004, F005, F007) — Bausteine-Wächter (ADR-0112).
// Ergänzt bausteine_waechter.test.ts: prüft die Regeln DORT, wo sie wirken — im Lauf `waechterLauf`
// über einen echten Fixture-Baum (Dateien auf der Platte) — und schließt belegte Umgehungen.
// Quellcode ist hier Gegenstand der Regel (Ausnahme der Test-Politik wie harte_farben_waechter).
//
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --experimental-test-module-mocks --test src/lib/__tests__/bausteine_waechter_wirkort.test.ts
import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, mkdirSync, writeFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, dirname } from 'node:path';
import {
	pruefeSeitenDatei,
	zaehleTokenVerstoesse,
	waechterLauf,
	istUtility,
	fremderKomponentenImport,
	begruendungReicht,
	KONFIG,
	type Konfig
} from './bausteine_waechter_regeln.ts';

const SEITE = 'routes/trips/[id]/wetter/+page.svelte';
const BAUSTEIN = 'lib/components/molecules/NeueZeile.svelte';
const SAUBER = `<script lang="ts">
	import Card from '$lib/components/atoms/Card.svelte';
	import { t } from '$lib/i18n';
</script>

<Card>{t('aktionen.reiter.wetter')}</Card>
`;
const mitStyle = (css: string) => `<div class="z"></div>\n<style>\n\t.z { ${css} }\n</style>\n`;
const regelA = (text: string) => pruefeSeitenDatei(SEITE, text).filter((v) => v.regel === 'a');

// ---------------------------------------------------------------- F001: waechterLauf über einen Fixture-Baum

/** Sauberer Fixture-Baum: eine Bestandsseite, ein Bestands-Baustein mit genau 2 Token-Verstößen, eine Scope-Seite. */
function baum(extra: Record<string, string> = {}): { wurzel: string; konfig: Konfig } {
	const wurzel = mkdtempSync(join(tmpdir(), 'bausteine-wirkort-'));
	const dateien: Record<string, string> = {
		'routes/alt/+page.svelte': '<div class="alt" style="margin: 7px">Bestand</div>\n',
		'lib/components/atoms/Alt.svelte': mitStyle('padding: 12px; color: #333;'),
		'lib/components/atoms/Sauber.svelte': mitStyle('padding: var(--g-s-2);'),
		'routes/neu/+page.svelte': SAUBER,
		...extra
	};
	for (const [rel, text] of Object.entries(dateien)) {
		mkdirSync(dirname(join(wurzel, rel)), { recursive: true });
		writeFileSync(join(wurzel, rel), text);
	}
	const konfig: Konfig = {
		SEITEN_SCOPE: ['routes/neu/+page.svelte'],
		FREIGEGEBENE_KOMPOSITIONEN: [],
		BESTAND: ['routes/alt/+page.svelte'],
		BESTAND_OBERGRENZE: 1,
		AUSNAHMEN: { 'lib/components/atoms/Alt.svelte': { n: 2, grund: 'Bestand vor ADR-0112' } }
	};
	return { wurzel, konfig };
}
function lauf(extra: Record<string, string>, aendern: (k: Konfig) => Konfig = (k) => k): string[] {
	const { wurzel, konfig } = baum(extra);
	try {
		return waechterLauf(wurzel, aendern(konfig));
	} finally {
		rmSync(wurzel, { recursive: true, force: true });
	}
}

describe('F001: waechterLauf wirkt auf Regel (b), Ratsche, AUSNAHMEN, BESTAND und SEITEN_SCOPE', () => {
	test('sauberer Fixture-Baum ist grün (Gegenprobe)', () => {
		assert.deepEqual(lauf({}), []);
	});
	test('neue Baustein-Datei mit padding: 12px ohne AUSNAHMEN-Eintrag ⇒ rot (Start bei 0)', () => {
		const f = lauf({ 'lib/components/molecules/Neu.svelte': mitStyle('padding: 12px;') });
		assert.ok(f.some((x) => x.includes('lib/components/molecules/Neu.svelte') && /Regel \(b\)/.test(x)), JSON.stringify(f));
	});
	test('neue Baustein-Datei in organisms mit style:-Direktive ⇒ rot', () => {
		const f = lauf({ 'lib/components/organisms/Neu.svelte': '<div style:color="#c45a2a">x</div>\n' });
		assert.ok(f.some((x) => x.includes('organisms/Neu.svelte')), JSON.stringify(f));
	});
	test('Ist-Stand über dem AUSNAHMEN-Eintrag ⇒ rot', () => {
		const f = lauf({ 'lib/components/atoms/Alt.svelte': mitStyle('padding: 12px; color: #333; margin: 3px;') });
		assert.ok(f.some((x) => x.includes('atoms/Alt.svelte') && x.includes('Obergrenze 2')), JSON.stringify(f));
	});
	test('Ist-Stand unter dem Eintrag ⇒ grün (keine Anhebung verlangt)', () => {
		assert.deepEqual(lauf({ 'lib/components/atoms/Alt.svelte': mitStyle('padding: 12px;') }), []);
	});
	test('AUSNAHMEN-Eintrag für eine nicht existierende Datei ⇒ rot', () => {
		const f = lauf({}, (k) => ({ ...k, AUSNAHMEN: { ...k.AUSNAHMEN, 'lib/components/atoms/Weg.svelte': { n: 1, grund: 'alt' } } }));
		assert.ok(f.some((x) => x.includes('atoms/Weg.svelte') && x.includes('AUSNAHMEN')), JSON.stringify(f));
	});
	test('neue Datei unter routes/ ohne Eintrag ⇒ rot; unter lib/components/shared ebenso', () => {
		const f = lauf({ 'routes/fremd/+page.svelte': SAUBER, 'lib/components/shared/X.svelte': '<p>x</p>\n' });
		assert.ok(f.some((x) => x.includes('routes/fremd/+page.svelte')), JSON.stringify(f));
		assert.ok(f.some((x) => x.includes('lib/components/shared/X.svelte')), JSON.stringify(f));
	});
	test('BESTAND über der Obergrenze ⇒ rot', () => {
		const f = lauf({ 'routes/zwei/+page.svelte': SAUBER }, (k) => ({ ...k, BESTAND: [...k.BESTAND, 'routes/zwei/+page.svelte'] }));
		assert.ok(f.some((x) => x.includes('Obergrenze 1')), JSON.stringify(f));
	});
	test('verwaister BESTAND-Eintrag ⇒ rot', () => {
		const f = lauf({}, (k) => ({ ...k, BESTAND: [...k.BESTAND, 'routes/weg/+page.svelte'], BESTAND_OBERGRENZE: 2 }));
		assert.ok(f.some((x) => x.includes('routes/weg/+page.svelte') && x.includes('existiert nicht')), JSON.stringify(f));
	});
	test('doppelter BESTAND-Eintrag ⇒ rot', () => {
		const f = lauf({}, (k) => ({ ...k, BESTAND: [...k.BESTAND, ...k.BESTAND], BESTAND_OBERGRENZE: 2 }));
		assert.ok(f.some((x) => x.includes('doppelt')), JSON.stringify(f));
	});
	test('SEITEN_SCOPE-Konsistenz: Überschneidung mit BESTAND, Baustein im Scope, fehlende Datei ⇒ je rot', () => {
		const ueber = lauf({}, (k) => ({ ...k, SEITEN_SCOPE: [...k.SEITEN_SCOPE, 'routes/alt/+page.svelte'] }));
		assert.ok(ueber.some((x) => x.includes('SEITEN_SCOPE und BESTAND')), JSON.stringify(ueber));
		const baustein = lauf({}, (k) => ({ ...k, SEITEN_SCOPE: [...k.SEITEN_SCOPE, 'lib/components/atoms/Sauber.svelte'] }));
		assert.ok(baustein.some((x) => x.includes('gehören nicht in SEITEN_SCOPE')), JSON.stringify(baustein));
		const fehlt = lauf({}, (k) => ({ ...k, SEITEN_SCOPE: [...k.SEITEN_SCOPE, 'routes/gibtsnicht/+page.svelte'] }));
		assert.ok(fehlt.some((x) => x.includes('routes/gibtsnicht') && x.includes('existiert nicht')), JSON.stringify(fehlt));
	});
	test('Scope-Seite mit Verstoß im Lauf ⇒ Regel (a) rot; Bestandsseite mit style= bleibt grün', () => {
		const f = lauf({ 'routes/neu/+page.svelte': SAUBER + '<div style="color: red">x</div>\n' });
		assert.ok(f.some((x) => x.includes('routes/neu/+page.svelte') && /\(a\)/.test(x)), JSON.stringify(f));
		assert.ok(!f.some((x) => x.includes('routes/alt')), 'Bestand bleibt unberührt');
	});
});

// ---------------------------------------------------------------- F004: Umgehungen von Regel (a)

describe('F004: Umgehungen von Regel (a) sind geschlossen', () => {
	const mit = (zusatz: string) => SAUBER.replace('<Card>', `<Card>\n\t${zusatz}`);
	test('<svelte:element this="button"> ⇒ rot', () => {
		assert.ok(regelA(mit('<svelte:element this="button">x</svelte:element>')).length > 0);
	});
	test('<style> in <svelte:head> ⇒ rot', () => {
		const t = SAUBER + '\n<svelte:head><style>.a { color: red; }</style></svelte:head>\n';
		assert.ok(regelA(t).some((v) => v.art.includes('style')), JSON.stringify(regelA(t)));
	});
	test('{@html …} ⇒ rot', () => {
		assert.ok(regelA(mit('{@html roh}')).some((v) => v.art.includes('@html')));
	});
	test('Spread mit class bzw. style ⇒ rot; Spread ohne class/style bleibt erlaubt', () => {
		assert.ok(regelA(mit('<div {...{ class: "flex" }}>x</div>')).length > 0);
		assert.ok(regelA(mit('<div {...{ style: "a:b" }}>x</div>')).length > 0);
		assert.deepEqual(regelA(SAUBER.replace('<Card>', '<Card {...props}>')), []);
	});
	const umgehungen = [
		"import Foo from '$lib/components/atoms/../shared/Foo.svelte';",
		"import { Foo } from '../../../../lib/components/shared';",
		"import { Foo } from '$lib/components/shared';",
		"import Foo from '$lib/components/molecules/../../components/ui/btn/Btn.svelte';"
	];
	for (const imp of umgehungen) {
		test(`Import-Trick rot: ${imp}`, () => {
			const t = SAUBER.replace('<script lang="ts">', `<script lang="ts">\n\t${imp}`);
			assert.ok(regelA(t).some((v) => v.art.includes('import')), JSON.stringify(regelA(t)));
		});
	}
	test('Importe im <script module> werden geprüft', () => {
		const t = `<script module lang="ts">\n\timport Foo from '$lib/components/shared/Foo.svelte';\n</script>\n` + SAUBER;
		assert.ok(regelA(t).some((v) => v.art.includes('shared/Foo')), JSON.stringify(regelA(t)));
	});
	test('fremderKomponentenImport: Normalisierung und erlaubte Ziele', () => {
		assert.equal(fremderKomponentenImport(SEITE, '$lib/components/atoms/../shared/Foo.svelte'), 'lib/components/shared/Foo.svelte');
		assert.equal(fremderKomponentenImport(SEITE, '$lib/components/organisms/../atoms/Btn.svelte'), null);
		assert.equal(fremderKomponentenImport(SEITE, '$lib/api'), null);
		assert.equal(fremderKomponentenImport(SEITE, '$lib/components/shared/Foo.svelte', ['$lib/components/shared/Foo.svelte']), null);
	});
	// Fix-Loop 2 (Adversary F010): die Whitelist endet an der Ordnergrenze — „atomsEvil“ ist kein atoms.
	test('Whitelist mit Ordner-Abschluss: atomsEvil/moleculesX/organisms2 sind fremd, atoms und atoms/… erlaubt', () => {
		for (const q of ['$lib/components/atomsEvil/Foo.svelte', '$lib/components/moleculesX', '$lib/components/organisms2/Bar.svelte']) {
			assert.equal(fremderKomponentenImport(SEITE, q), q.replace('$lib/', 'lib/'), q);
		}
		assert.equal(fremderKomponentenImport(SEITE, '$lib/components/atoms'), null);
		assert.equal(fremderKomponentenImport(SEITE, '$lib/components/atoms/'), null);
		assert.equal(fremderKomponentenImport(SEITE, '$lib/components/molecules/Field.svelte'), null);
	});
	test('Import aus atomsEvil im Seiten-Fixture ⇒ rot (auch relativ)', () => {
		for (const imp of ["import Foo from '$lib/components/atomsEvil/Foo.svelte';", "import { Foo } from '../../../../lib/components/atomsEvil';"]) {
			const t = SAUBER.replace('<script lang="ts">', `<script lang="ts">\n\t${imp}`);
			assert.ok(regelA(t).some((v) => v.art.includes('atomsEvil')), JSON.stringify(regelA(t)));
		}
	});
	const tailwind = ['table-fixed', 'caption-bottom', 'transform-gpu', 'backface-hidden', 'mask-b-from-50%', 'field-sizing-content', 'scheme-dark', 'wrap-anywhere', 'contain-layout', 'prose', '@container', 'md:@container'];
	for (const k of tailwind) {
		test(`Tailwind erkannt: ${k}`, () => {
			assert.equal(istUtility(k), true);
			assert.ok(regelA(mit(`<div class="${k}">x</div>`)).length > 0);
		});
	}
	test('eigene Klassennamen bleiben erlaubt', () => {
		for (const k of ['hub-kopf', 'metrik-zeile', 'vorlage']) assert.equal(istUtility(k), false, k);
	});
});

// ---------------------------------------------------------------- F005: Teilregeln von Regel (b)

describe('F005: Teilregeln von Regel (b) einzeln bewacht', () => {
	const rot: Array<[string, string]> = [
		['Farbfunktion rgb()', 'color: rgb(10, 20, 30);'],
		['Farbfunktion hsl()', 'background: hsl(20 50% 40%);'],
		['Farbname', 'color: red;'],
		['Farbname in Kurzschreibweise border', 'border: 1px solid red;'],
		['Farbname in box-shadow', 'box-shadow: 0 0 0 var(--g-s-1) black;'],
		['Variable außerhalb --g-*', 'color: var(--fremd);'],
		['padding: 1px (1-px-Ausnahme nur für Rahmen)', 'padding: 1px;'],
		['Großschreibung PADDING: 12PX', 'PADDING: 12PX;'],
		['Custom Property mit Ziffern --g-s-2: 12px', '--g-s-2: 12px;'],
		['rem-Maß', 'gap: 1.5rem;']
	];
	for (const [name, css] of rot) {
		test(`rot: ${name}`, () => {
			const v = zaehleTokenVerstoesse(BAUSTEIN, mitStyle(css));
			assert.ok(v.length > 0 && v[0].regel === 'b', `${css}: ${JSON.stringify(v)}`);
		});
	}
	const gruen: Array<[string, string]> = [
		['Rahmen 1px mit Token-Farbe', 'border-bottom: 1px solid var(--g-rule);'],
		['Kommentar mit Hex wird neutralisiert', '/* früher #ff0000 und 12px */ color: var(--g-ink);'],
		['Viewport-Einheiten', 'min-height: 100vh;'],
		['Zeitangaben', 'transition: opacity 150ms ease;']
	];
	for (const [name, css] of gruen) {
		test(`grün: ${name}`, () => {
			assert.deepEqual(zaehleTokenVerstoesse(BAUSTEIN, mitStyle(css)), []);
		});
	}
	test('@media-Präludium wird nicht als Deklaration gezählt', () => {
		const t = '<div class="z"></div>\n<style>\n@media (max-width: 760px) { .z { gap: var(--g-s-2); } }\n</style>\n';
		assert.deepEqual(zaehleTokenVerstoesse(BAUSTEIN, t), []);
	});
	test('style=-Attribut in Bausteinen zählt', () => {
		const v = zaehleTokenVerstoesse(BAUSTEIN, '<div style="padding: 12px; color: var(--g-ink)">x</div>\n');
		assert.equal(v.length, 1, JSON.stringify(v));
	});
	test('style:-Direktive in Bausteinen zählt, auch mit dynamischem px', () => {
		assert.equal(zaehleTokenVerstoesse(BAUSTEIN, '<div style:background="#fff">x</div>\n').length, 1);
		assert.equal(zaehleTokenVerstoesse(BAUSTEIN, '<div style:width="{w}px">x</div>\n').length, 1);
		assert.deepEqual(zaehleTokenVerstoesse(BAUSTEIN, '<div style:padding="var(--g-s-2)">x</div>\n'), []);
	});
	test('Tailwind-Arbitrary-Werte mit Maß oder Hex zählen, Token-Werte nicht', () => {
		assert.equal(zaehleTokenVerstoesse(BAUSTEIN, '<div class="p-[12px]">x</div>\n').length, 1);
		assert.equal(zaehleTokenVerstoesse(BAUSTEIN, '<div class="text-[#333]">x</div>\n').length, 1);
		assert.deepEqual(zaehleTokenVerstoesse(BAUSTEIN, '<div class="p-[var(--g-s-2)]">x</div>\n'), []);
	});
});

// ---------------------------------------------------------------- F007: Randlücken

describe('F007: Parse-Fehler, exempt-Folgeverstoß, Begründungslänge, Bestands-Konstanten', () => {
	test('nicht parsebare Seiten-Datei ⇒ Verstoß (nicht still grün)', () => {
		const v = pruefeSeitenDatei(SEITE, '<div>{#if a}</div>');
		assert.ok(v.length > 0 && v[0].art.includes('nicht parsebar'), JSON.stringify(v));
	});
	test('audit:exempt ohne Begründung erzeugt zusätzlich einen exempt-Verstoß', () => {
		const v = pruefeSeitenDatei(SEITE, SAUBER.replace('<Card>', '<Card>\n\t<!-- audit:exempt -->\n\t<div style="height: 3px">x</div>'));
		assert.ok(v.some((x) => x.regel === 'a'), 'Verstoß bleibt');
		assert.ok(v.some((x) => x.regel === 'exempt'), 'eigener exempt-Verstoß fehlt');
	});
	test('zu kurze Begründung reicht nicht; echte Begründung reicht', () => {
		assert.equal(begruendungReicht('ok'), false);
		assert.equal(begruendungReicht('a b c'), false);
		assert.equal(begruendungReicht('weil so'), false);
		assert.equal(begruendungReicht('Kartenbibliothek verlangt feste Höhe'), true);
		const kurz = SAUBER.replace('<Card>', '<Card>\n\t<!-- audit:exempt: ok -->\n\t<div style="height: 3px">x</div>');
		assert.ok(pruefeSeitenDatei(SEITE, kurz).some((x) => x.regel === 'exempt'));
	});
	test('BESTAND_OBERGRENZE ist genau die Länge des Bestands und steigt nie über den Start (204)', () => {
		assert.equal(KONFIG.BESTAND_OBERGRENZE, KONFIG.BESTAND.length);
		assert.ok(KONFIG.BESTAND_OBERGRENZE <= 204, 'Startwert 2026-11-10: 204 — die Obergrenze darf nur sinken');
	});
	test('AUSNAHMEN-Summe steigt nie über den Start (398 Verstöße in 39 Dateien, Neuzählung Fix-Loop 1)', () => {
		const summe = Object.values(KONFIG.AUSNAHMEN).reduce((s, e) => s + e.n, 0);
		assert.ok(summe <= 398, `AUSNAHMEN-Summe ${summe} > Start 398`);
		assert.ok(Object.keys(KONFIG.AUSNAHMEN).length <= 39);
	});
	test('BESTAND ohne Duplikate, SEITEN_SCOPE ohne Bausteine', () => {
		assert.equal(new Set(KONFIG.BESTAND).size, KONFIG.BESTAND.length);
		assert.ok(!KONFIG.SEITEN_SCOPE.some((s) => /^lib\/components\/(atoms|molecules|organisms)\//.test(s)));
	});
});
