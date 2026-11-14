// Issue #2795 S3b, Teilschritt 1b — Fix-Loop 1 (Adversary Runde 1, F006; Mutationen M10, M28).
// Spec: docs/specs/modules/feat_2795_s3b_teil1_zustellung.md — AC-36 (GET /api/auth/profile genau
// einmal je Aufruf des Reiters).
//
// Der Reiter laedt das Profil EINMAL (ZustellungTab, onMount) und reicht es ueber den
// Uebergangsblock und den Panel-Baustein an WeatherMetricsTab. WeatherMetricsTab laedt nur dann
// selbst, wenn die Prop `profil` `undefined` ist (Anlegeseiten). Damit im montierten Reiter genau
// ein Abruf entsteht, muss die Kette (1) einen Wert liefern, der NIE `undefined` ist (vor dem Laden
// `null`, danach das Profil), (2) die Prop unterwegs nicht abfangen und (3) WeatherMetricsTab muss
// sie tatsaechlich auswerten. Die Zahl der Abrufe im Browser zaehlt zusaetzlich die E2E-Spec
// s3b2795-zustellung-kanaele.spec.ts.
//
// Messweise: AST der ECHTEN Komponenten (svelte/compiler); die Ausdruecke am Wirkort werden
// AUSGEWERTET (svelteInstanzPruefstand.werte), nicht nur gelesen.
//
//   cd frontend && npm test -- src/lib/components/shared/__tests__/s3b2795_zustellung_profil_einmal.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

import { svelteAst, einbettungenMitWeichen, propNamen, aufrufe, type Knoten } from './s3a2794Ast.ts';
import { attributAusdruck, werte } from './svelteInstanzPruefstand.ts';

const HIER = dirname(fileURLToPath(import.meta.url));
const KOMP = join(HIER, '..', '..');
const DATEI = {
	zustellung: join(KOMP, 'shared', 'zustellung-tab', 'ZustellungTab.svelte'),
	uebergang: join(KOMP, 'organisms', 'zustellung-tab', 'UebergangBlock.svelte'),
	panel: join(KOMP, 'shared', 'WetterMetrikenVersandPanel.svelte'),
	wmt: join(KOMP, 'shared', 'WeatherMetricsTab.svelte')
};

const PROFIL = { mail_to: 'a@example.com', telegram_chat_id: '4711' };

describe('AC-36 (F006): das eine Profil erreicht WeatherMetricsTab — nie undefined', () => {
	test('f006_zustellungtab_reicht_vor_und_nach_dem_laden_einen_wert_nie_undefined', () => {
		const { ast, quelle } = svelteAst(DATEI.zustellung);
		const ub = einbettungenMitWeichen(ast, quelle, ['UebergangBlock']);
		assert.equal(ub.length, 1, 'Messaufbau: ZustellungTab bettet den Uebergangsblock nicht genau einmal ein');
		const ausdruck = attributAusdruck(ub[0].knoten, quelle, 'profil');
		assert.ok(ausdruck, 'ZustellungTab reicht kein profil an den Uebergangsblock — WeatherMetricsTab laedt dann selbst (zweiter Abruf)');
		for (const [fall, u, soll] of [
			['vor dem Laden', { profilGeladen: false, profil: null }, null],
			['geladen', { profilGeladen: true, profil: PROFIL }, PROFIL],
			['geladen, Abruf gescheitert', { profilGeladen: true, profil: null }, null]
		] as const) {
			const wert = werte(ausdruck!, { ...u });
			assert.notEqual(wert, undefined, `${fall}: profil ist undefined — WeatherMetricsTab ruefe /api/auth/profile selbst ab`);
			assert.deepEqual(wert, soll, `${fall}: falscher Wert ${JSON.stringify(wert)}`);
		}
	});

	test('f006_uebergangsblock_und_panel_fangen_profil_nicht_ab_und_streuen_weiter', () => {
		for (const [datei, ziel] of [
			[DATEI.uebergang, 'WetterMetrikenVersandPanel'],
			[DATEI.panel, 'WeatherMetricsTab']
		] as const) {
			const { ast, quelle } = svelteAst(datei);
			assert.ok(!propNamen(ast).includes('profil'), `${datei}: profil wird abgefangen statt weitergereicht`);
			const e = einbettungenMitWeichen(ast, quelle, [ziel]);
			assert.equal(e.length, 1, `Messaufbau: ${ziel} nicht genau einmal in ${datei}`);
			assert.ok(
				((e[0].knoten.attributes ?? []) as Knoten[]).some((a) => a.type === 'SpreadAttribute'),
				`${datei}: ${ziel} bekommt die Rest-Props nicht gestreut — profil kaeme nicht an`
			);
		}
	});

	test('f006_weathermetricstab_laedt_nur_ohne_profil_prop_selbst', async () => {
		const { ast, quelle } = svelteAst(DATEI.wmt);
		assert.ok(propNamen(ast).includes('profil'), 'WeatherMetricsTab nimmt keine Prop profil');
		const abrufe = aufrufe(ast.instance?.content).filter(
			(a) => (a.callee as Knoten)?.name === 'fetch' && (a.arguments?.[0] as Knoten)?.value === '/api/auth/profile'
		);
		assert.equal(abrufe.length, 1, `Messaufbau: erwartet genau eine Profil-Ladestelle in WeatherMetricsTab, gefunden ${abrufe.length}`);
		// Die umschliessende Bedingung finden: ConditionalExpression, deren alternate den Abruf enthaelt.
		let bedingung: Knoten | null = null;
		(function lauf(n: unknown): void {
			if (bedingung || n === null || typeof n !== 'object') return;
			if (Array.isArray(n)) return n.forEach(lauf);
			const k = n as Knoten;
			if (k.type === 'ConditionalExpression' && k.alternate.start <= abrufe[0].start && abrufe[0].end <= k.alternate.end) {
				bedingung = k;
				return;
			}
			for (const [f, v] of Object.entries(k)) if (f !== 'parent' && f !== 'loc' && f !== 'metadata') lauf(v);
		})(ast.instance?.content);
		assert.ok(bedingung, 'WeatherMetricsTab ruft /api/auth/profile bedingungslos ab — im Reiter Zustellung zweiter Abruf');
		const test = quelle.slice((bedingung as Knoten).test.start, (bedingung as Knoten).test.end);
		const nimmtProp = quelle.slice((bedingung as Knoten).consequent.start, (bedingung as Knoten).consequent.end);
		assert.equal(werte(test, { profil: null }), true, 'profil=null (Abruf im Reiter gescheitert) loest einen zweiten Abruf aus');
		assert.equal(werte(test, { profil: PROFIL }), true, 'ein uebergebenes Profil loest einen zweiten Abruf aus');
		assert.equal(werte(test, { profil: undefined }), false, 'ohne Prop (Anlegeseiten) laedt WeatherMetricsTab nicht mehr selbst');
		assert.deepEqual(await werte(nimmtProp, { profil: PROFIL, Promise }), PROFIL, 'der Zweig mit Prop liefert nicht das uebergebene Profil');
	});
});
