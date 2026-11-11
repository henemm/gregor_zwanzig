// doc-compliance-test
// TDD RED — Issue #2913 (Epic #2791): ADR-0112 „Oberflächen nur aus Design-System-Bausteinen".
// Spec: docs/specs/modules/einstellungen_neu_neustart_adr_waechter_elementliste.md — AC-1 bis AC-7.
//
// Quellcode ist hier GEGENSTAND der Regel (Ausnahme der Test-Politik wie harte_farben_waechter /
// ink4_waechter). Die Regeln selbst liegen in `bausteine_waechter_regeln.ts` (gleicher Ordner), damit
// sie gegen echte Fixture-Texte UND gegen den echten Quellbaum laufen — kein Mock.
//
// Vertrag des Regel-Moduls (vom Developer umzusetzen, hier festgelegt):
//   type Verstoss = { datei: string; regel: 'a' | 'b' | 'neu' | 'exempt' | 'bestand'; zeile: number; art: string; meldung: string }
//   pruefeSeitenDatei(datei, text): Verstoss[]            — Regel (a) Aufbau
//   zaehleTokenVerstoesse(datei, text): Verstoss[]        — Regel (b) Tokens (nur <style> von Bausteinen)
//   pruefeRatsche(ist: Record<string, number>, ausnahmen: Record<string, {n:number; grund:string}>): string[]
//   pruefeNeueDateien(svelteDateien: string[], seitenScope: string[], bestand: string[]): string[]
//   pruefeBestandsliste(bestand: string[], vorhandene: string[], obergrenze: number): string[]
//   waechterLauf(srcWurzel, konfig): string[]             — alle Regeln über einen Baum (Pfade relativ zu src/)
//   KONFIG: { SEITEN_SCOPE, FREIGEGEBENE_KOMPOSITIONEN, BESTAND, BESTAND_OBERGRENZE, AUSNAHMEN }
//
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --experimental-test-module-mocks --test src/lib/__tests__/bausteine_waechter.test.ts
import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, mkdirSync, writeFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import {
	pruefeSeitenDatei,
	zaehleTokenVerstoesse,
	pruefeRatsche,
	pruefeNeueDateien,
	pruefeBestandsliste,
	waechterLauf,
	KONFIG
} from './bausteine_waechter_regeln.ts';

const FRONTEND_SRC = join(fileURLToPath(new URL('.', import.meta.url)), '..', '..');
const SEITE = 'routes/trips/[id]/wetter/+page.svelte';
const BAUSTEIN = 'lib/components/molecules/NeueZeile.svelte';

const SAUBERE_SEITE = `<script lang="ts">
	import Card from '$lib/components/atoms/Card.svelte';
	import Btn from '$lib/components/atoms/Btn.svelte';
	import Field from '$lib/components/molecules/Field.svelte';
	import { t } from '$lib/i18n';
	let { data } = $props();
</script>

<Card>
	<Field label={t('aktionen.reiter.wetter')} />
	<Btn onclick={() => {}}>{t('aktionen.reiter.zustellung')}</Btn>
</Card>
`;

function regelA(text: string) {
	return pruefeSeitenDatei(SEITE, text).filter((v) => v.regel === 'a');
}

// ---------------------------------------------------------------- AC-1
describe('AC-1: Regel (a) — kein <style>, kein style=, keine Tailwind-Utilities in Seiten-Dateien', () => {
	test('saubere Seite ist grün', () => {
		assert.deepEqual(pruefeSeitenDatei(SEITE, SAUBERE_SEITE), []);
	});

	const verstoesse: Array<[string, string]> = [
		['<style>-Block', SAUBERE_SEITE + '\n<style>\n\t.x { padding: var(--g-s-2); }\n</style>\n'],
		['<style lang="postcss">', SAUBERE_SEITE + '\n<style lang="postcss">.x{}</style>\n'],
		['style=-Attribut', SAUBERE_SEITE.replace('<Card>', '<Card>\n\t<div style="margin-top: 8px">x</div>')],
		['style={…}-Ausdruck', SAUBERE_SEITE.replace('<Card>', '<Card>\n\t<div style={`width:${w}px`}>x</div>')],
		['style:-Direktive', SAUBERE_SEITE.replace('<Card>', '<Card>\n\t<div style:color="var(--g-ink)">x</div>')],
		['Tailwind-Utilities statisch', SAUBERE_SEITE.replace('<Card>', '<Card>\n\t<div class="flex items-center gap-2 p-4">x</div>')],
		['Tailwind-Utility im Ausdruck', SAUBERE_SEITE.replace('<Card>', '<Card>\n\t<div class={`mt-2 ${aktiv ? "font-bold" : ""}`}>x</div>')],
		['Tailwind per class:-Direktive', SAUBERE_SEITE.replace('<Card>', '<Card>\n\t<div class:hidden={zu}>x</div>')],
		['Tailwind-Utility auf Baustein-Komponente', SAUBERE_SEITE.replace('<Card>', '<Card class="w-full rounded-lg">')]
	];
	for (const [name, text] of verstoesse) {
		test(`rot: ${name} — nennt Datei und Regel (a)`, () => {
			const v = regelA(text);
			assert.ok(v.length > 0, `${name} wurde nicht erkannt`);
			assert.equal(v[0].datei, SEITE);
			assert.match(v[0].meldung, /\(a\)/, 'Meldung muss Regel (a) nennen');
			assert.ok(v[0].meldung.includes(SEITE), 'Meldung muss die Datei nennen');
			assert.ok(v[0].zeile >= 1, 'Zeilennummer muss gesetzt sein');
		});
	}

	test('eigene, nicht-utility Klassennamen bleiben erlaubt', () => {
		const t = SAUBERE_SEITE.replace('<Card>', '<Card>\n\t<section class="hub-kopf">x</section>');
		assert.deepEqual(regelA(t), []);
	});
});

// ---------------------------------------------------------------- AC-2
describe('AC-2: Regel (a) — keine rohen Formular-/Tabellen-Elemente, Importe nur aus Baustein-Ordnern', () => {
	for (const el of ['button', 'input', 'select', 'textarea', 'table']) {
		test(`rot: rohes <${el}>`, () => {
			const roh =
				el === 'input'
					? '<input type="text" bind:value={x} />'
					: `<${el} class="hub-kopf">x</${el}>`;
			const v = regelA(SAUBERE_SEITE.replace('<Card>', `<Card>\n\t${roh}`));
			assert.ok(v.some((x) => x.art.includes(el)), `<${el}> nicht erkannt: ${JSON.stringify(v)}`);
		});
	}

	test('grün: dieselbe Seite mit Baustein-Komponenten statt rohen Elementen', () => {
		const t = SAUBERE_SEITE.replace(
			'<Card>',
			"<Card>\n\t<Btn variant=\"ghost\">x</Btn>\n\t<Field label=\"x\" />"
		);
		assert.deepEqual(regelA(t), []);
	});

	test('Komponente <Btn> ist kein rohes Element, <button> mit Attributen schon', () => {
		const t = SAUBERE_SEITE.replace('<Card>', '<Card>\n\t<button\n\t\ttype="button"\n\t\tonclick={() => {}}>x</button>');
		assert.ok(regelA(t).some((x) => x.art.includes('button')), 'mehrzeiliges <button> muss erkannt werden');
	});

	const fremdImporte = [
		"import Foo from '$lib/components/shared/Foo.svelte';",
		"import { Button } from '$lib/components/ui/button';",
		"import Bar from './Bar.svelte';",
		"import Baz from '../../trip-detail/Baz.svelte';",
		"import Qux from '$lib/components/trip-detail/waypoints/ProfileEditor.svelte';"
	];
	for (const imp of fremdImporte) {
		test(`rot: Fremd-Import ${imp}`, () => {
			const t = SAUBERE_SEITE.replace('<script lang="ts">', `<script lang="ts">\n\t${imp}`);
			const v = regelA(t);
			assert.ok(v.some((x) => x.art.includes('import')), `Import nicht erkannt: ${imp}`);
		});
	}

	test('grün: Nicht-Komponenten-Importe ($lib/i18n, $lib/api, Stores) sind erlaubt', () => {
		const t = SAUBERE_SEITE.replace(
			'<script lang="ts">',
			"<script lang=\"ts\">\n\timport { api } from '$lib/api';\n\timport { page } from '$app/state';"
		);
		assert.deepEqual(regelA(t), []);
	});

	test('grün: Import aus organisms und index-Bündel der Baustein-Ordner', () => {
		const t = SAUBERE_SEITE.replace(
			'<script lang="ts">',
			"<script lang=\"ts\">\n\timport { Pill } from '$lib/components/atoms';\n\timport X from '$lib/components/organisms/X.svelte';"
		);
		assert.deepEqual(regelA(t), []);
	});
});

// ---------------------------------------------------------------- AC-3
describe('AC-3: Regel (b) — neue Baustein-Dateien nur über var(--g-*)-Tokens (Start bei 0)', () => {
	const mitStyle = (css: string) => `<div class="z"><slot /></div>\n<style>\n\t.z { ${css} }\n</style>\n`;

	const verboten = [
		'padding: 12px;',
		'gap: 0.5rem;',
		'font-size: 14px;',
		'font-size: 0.875rem;',
		"font-family: 'Inter', sans-serif;",
		'color: #333;',
		'background: #ffffff;',
		'border-radius: 6px;',
		'box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);',
		'margin: 2px 0;',
		'color: var(--g-ink, #222);'
	];
	for (const css of verboten) {
		test(`rot: ${css}`, () => {
			const v = zaehleTokenVerstoesse(BAUSTEIN, mitStyle(css));
			assert.ok(v.length > 0, `nicht erkannt: ${css}`);
			assert.equal(v[0].regel, 'b');
		});
	}

	const erlaubt = [
		'margin: 0;',
		'border: 1px solid var(--g-rule);',
		'width: 100%;',
		'grid-template-columns: 1fr 2fr auto;',
		'height: auto;',
		'padding: var(--g-s-2) var(--g-s-4);',
		'gap: calc(var(--g-s-2) * 2);',
		'max-width: min(100%, calc(var(--g-s-20) * 10));',
		'color: var(--g-ink);',
		'font-family: var(--g-font-ui);',
		'font-size: var(--g-text-sm);',
		'border-radius: var(--g-r-2);',
		'box-shadow: var(--g-shadow-1);'
	];
	for (const css of erlaubt) {
		test(`grün: ${css}`, () => {
			assert.deepEqual(zaehleTokenVerstoesse(BAUSTEIN, mitStyle(css)), []);
		});
	}

	test('neue Baustein-Datei mit Verstoß und ohne AUSNAHMEN-Eintrag macht den Lauf rot', () => {
		const ist = { [BAUSTEIN]: zaehleTokenVerstoesse(BAUSTEIN, mitStyle('padding: 12px;')).length };
		const fehler = pruefeRatsche(ist, {});
		assert.ok(fehler.some((f) => f.includes(BAUSTEIN)));
	});
});

// ---------------------------------------------------------------- AC-4
describe('AC-4: Ratsche AUSNAHMEN darf nur sinken', () => {
	const datei = 'lib/components/atoms/Card.svelte';
	const ausnahmen = { [datei]: { n: 5, grund: 'Bestand ADR-0112' } };

	test('rot: Ist-Stand höher als der Eintrag', () => {
		const f = pruefeRatsche({ [datei]: 6 }, ausnahmen);
		assert.ok(f.some((x) => x.includes(datei)), JSON.stringify(f));
	});
	test('rot: neue Datei mit Verstößen, die nicht in AUSNAHMEN steht', () => {
		const f = pruefeRatsche({ [datei]: 5, 'lib/components/atoms/Neu.svelte': 1 }, ausnahmen);
		assert.ok(f.some((x) => x.includes('Neu.svelte')), JSON.stringify(f));
	});
	test('grün: Ist-Stand gleich', () => {
		assert.deepEqual(pruefeRatsche({ [datei]: 5 }, ausnahmen), []);
	});
	test('grün: Ist-Stand niedriger (bereinigt) — keine Anhebung verlangt', () => {
		assert.deepEqual(pruefeRatsche({ [datei]: 2 }, ausnahmen), []);
	});
	test('echte AUSNAHMEN: jeder Eintrag hat einen Grund und n > 0', () => {
		for (const [d, e] of Object.entries(KONFIG.AUSNAHMEN)) {
			assert.ok(e.n > 0, `${d}: n muss > 0 sein (sonst Eintrag löschen)`);
			assert.ok(e.grund && e.grund.trim().length >= 3, `${d}: Grund fehlt`);
		}
	});
});

// ---------------------------------------------------------------- AC-5
describe('AC-5: Neue-Datei-Regel — jede Seiten-/Komponenten-Datei außerhalb der Baustein-Ordner ist erfasst', () => {
	test('rot: nicht eingetragene Datei; grün, sobald in SEITEN_SCOPE', () => {
		const dateien = ['routes/neu/+page.svelte', 'lib/components/atoms/Btn.svelte', 'routes/alt/+page.svelte'];
		const rot = pruefeNeueDateien(dateien, [], ['routes/alt/+page.svelte']);
		assert.ok(rot.some((x) => x.includes('routes/neu/+page.svelte')), JSON.stringify(rot));
		assert.ok(!rot.some((x) => x.includes('atoms/Btn.svelte')), 'Baustein-Ordner sind nicht betroffen');
		assert.ok(!rot.some((x) => x.includes('routes/alt')), 'Bestand ist erfasst');
		assert.deepEqual(pruefeNeueDateien(dateien, ['routes/neu/+page.svelte'], ['routes/alt/+page.svelte']), []);
	});

	test('Bestandsliste darf nur sinken: über der Obergrenze oder mit verwaisten Einträgen rot', () => {
		const vorhandene = ['routes/a/+page.svelte', 'routes/b/+page.svelte'];
		assert.deepEqual(pruefeBestandsliste(['routes/a/+page.svelte'], vorhandene, 2), []);
		assert.ok(pruefeBestandsliste(vorhandene, vorhandene, 1).length > 0, 'über Obergrenze muss rot sein');
		assert.ok(
			pruefeBestandsliste(['routes/weg/+page.svelte'], vorhandene, 5).some((x) => x.includes('routes/weg')),
			'verwaister Eintrag muss rot sein (Liste soll sinken)'
		);
	});

	test('Fixture-Baum: eingetragene Datei wird nach Regel (a) geprüft, nicht eingetragene ist rot', () => {
		const wurzel = mkdtempSync(join(tmpdir(), 'bausteine-waechter-'));
		try {
			const schreibe = (rel: string, text: string) => {
				mkdirSync(dirname(join(wurzel, rel)), { recursive: true });
				writeFileSync(join(wurzel, rel), text);
			};
			schreibe('lib/components/atoms/Btn.svelte', '<button><slot /></button>\n');
			schreibe('routes/scope/+page.svelte', SAUBERE_SEITE + '\n<style>.x{}</style>\n');
			schreibe('routes/fremd/+page.svelte', SAUBERE_SEITE);
			const konfig = {
				...KONFIG,
				SEITEN_SCOPE: ['routes/scope/+page.svelte'],
				BESTAND: [],
				BESTAND_OBERGRENZE: 0,
				AUSNAHMEN: {}
			};
			const fehler = waechterLauf(wurzel, konfig);
			assert.ok(fehler.some((f) => f.includes('routes/fremd/+page.svelte')), 'nicht eingetragen → rot');
			assert.ok(
				fehler.some((f) => f.includes('routes/scope/+page.svelte') && /\(a\)/.test(f)),
				'eingetragen mit <style> → Regel (a) rot'
			);
			assert.ok(!fehler.some((f) => f.includes('atoms/Btn.svelte')), 'Baustein darf rohes <button> enthalten');
		} finally {
			rmSync(wurzel, { recursive: true, force: true });
		}
	});
});

// ---------------------------------------------------------------- AC-6
describe('AC-6: audit:exempt nur mit Begründung', () => {
	test('grün: Verstoß mit audit:exempt und Begründung (Vorzeile)', () => {
		const t = SAUBERE_SEITE.replace(
			'<Card>',
			'<Card>\n\t<!-- audit:exempt: Kartenbibliothek verlangt feste Höhe am Container -->\n\t<div style="height: 300px">x</div>'
		);
		assert.deepEqual(pruefeSeitenDatei(SEITE, t), []);
	});
	test('grün: Begründung in derselben Zeile', () => {
		const t = SAUBERE_SEITE.replace(
			'<Card>',
			'<Card>\n\t<div style="height: 300px"><!-- audit:exempt — Kartenbibliothek verlangt feste Höhe --></div>'
		);
		assert.deepEqual(pruefeSeitenDatei(SEITE, t), []);
	});
	test('rot: audit:exempt ohne Begründung', () => {
		const t = SAUBERE_SEITE.replace(
			'<Card>',
			'<Card>\n\t<!-- audit:exempt -->\n\t<div style="height: 300px">x</div>'
		);
		const v = pruefeSeitenDatei(SEITE, t);
		assert.ok(v.length > 0, 'ohne Begründung darf nichts toleriert werden');
		assert.ok(v.some((x) => x.regel === 'exempt' || x.regel === 'a'));
	});
	test('audit:exempt wirkt nur auf die eigene bzw. folgende Zeile, nicht auf die ganze Datei', () => {
		const t = SAUBERE_SEITE.replace(
			'<Card>',
			'<Card>\n\t<!-- audit:exempt: Kartenbibliothek verlangt feste Höhe -->\n\t<div style="height: 300px">x</div>\n\t<p>y</p>\n\t<div style="color: red">z</div>'
		);
		assert.ok(regelA(t).length > 0, 'zweiter Verstoß weiter unten muss rot bleiben');
	});
	test('Baustein-Datei: Token-Verstoß mit begründetem audit:exempt zählt nicht', () => {
		const t = '<div class="z"></div>\n<style>\n\t/* audit:exempt: Switch-Knopf weiß laut Spec #2400 */\n\t.z { background: #ffffff; }\n</style>\n';
		assert.deepEqual(zaehleTokenVerstoesse(BAUSTEIN, t), []);
	});
});

// ---------------------------------------------------------------- AC-7
describe('AC-7: echter Quellbaum ist grün, ohne Bestand zu ändern', () => {
	test('waechterLauf(src, KONFIG) liefert keine Fehler', () => {
		const fehler = waechterLauf(FRONTEND_SRC, KONFIG);
		assert.deepEqual(fehler, [], fehler.slice(0, 20).join('\n'));
	});
	test('KONFIG.SEITEN_SCOPE startet ohne Bestandsdateien (Bestand und Scope überschneiden sich nicht)', () => {
		const ueberschneidung = KONFIG.SEITEN_SCOPE.filter((d: string) => KONFIG.BESTAND.includes(d));
		assert.deepEqual(ueberschneidung, []);
	});
	test('Bestand ist nicht leer erfasst und Obergrenze = Länge (Ist-Stand)', () => {
		assert.ok(KONFIG.BESTAND.length > 50, 'heutiger Bestand umfasst die vorhandenen Seiten/Komponenten');
		assert.ok(KONFIG.BESTAND.length <= KONFIG.BESTAND_OBERGRENZE);
	});
	test('Baustein-Ordner mit Verstößen sind in AUSNAHMEN erfasst (Ratsche startet beim Ist-Stand)', () => {
		assert.ok(Object.keys(KONFIG.AUSNAHMEN).length > 0, 'Bestand der Bausteine enthält heute harte Werte');
		for (const d of Object.keys(KONFIG.AUSNAHMEN)) {
			assert.match(d, /^lib\/components\/(atoms|molecules|organisms)\//, `${d}: AUSNAHMEN nur für Baustein-Ordner`);
		}
	});
});
