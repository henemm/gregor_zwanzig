// Issue #2795 S3b, Teilschritt 1b — Fix-Loop 1 (Adversary Runde 1, F006; Mutationen M10, M28).
// Spec: docs/specs/modules/feat_2795_s3b_teil1_zustellung.md — AC-36 (GET /api/auth/profile genau
// einmal je Aufruf des Reiters).
//
// Der Reiter laedt das Profil EINMAL (ZustellungTab, onMount). Seit #3154 traegt der Uebergangsblock
// keine Metrik-Oberflaeche (WeatherMetricsTab) mehr, die eine zweite Ladestelle waere. WeatherMetricsTab
// laedt weiter nur dann selbst, wenn die Prop `profil` `undefined` ist (Anlegeseiten). Die Zahl der
// Abrufe im Browser zaehlt zusaetzlich die E2E-Spec s3b2795-zustellung-kanaele.spec.ts.
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
import { werte } from './svelteInstanzPruefstand.ts';

const HIER = dirname(fileURLToPath(import.meta.url));
const KOMP = join(HIER, '..', '..');
const DATEI = {
	zustellung: join(KOMP, 'shared', 'zustellung-tab', 'ZustellungTab.svelte'),
	// #3036: Uebergangsblock aufgeloest — der Beispiel-Alarm ist der Abschnitt am Ende.
	beispiel: join(KOMP, 'organisms', 'zustellung-tab', 'BeispielAlarm.svelte'),
	panel: join(KOMP, 'shared', 'WetterMetrikenVersandPanel.svelte'),
	wmt: join(KOMP, 'shared', 'WeatherMetricsTab.svelte')
};

const PROFIL = { mail_to: 'a@example.com', telegram_chat_id: '4711' };

describe('AC-36 (F006): im Reiter Zustellung genau eine Profil-Ladestelle', () => {
	// #3154 (#3122 B3b, Spec feat_3122_was_steht_wo.md Teil B Nr. 14): der Uebergangsblock traegt keine
	// Metrik-Oberflaeche mehr. Statt der Durchreich-Kette ZustellungTab -> Uebergangsblock -> Panel ->
	// WeatherMetricsTab gilt: ZustellungTab laedt das Profil genau einmal, und unter ihm laedt niemand nach.
	const profilAbrufe = (datei: string): number => {
		const { ast } = svelteAst(datei);
		return [...aufrufe(ast.instance?.content), ...aufrufe(ast.fragment)].filter(
			(a) => (a.callee as Knoten)?.name === 'fetch' && (a.arguments?.[0] as Knoten)?.value === '/api/auth/profile'
		).length;
	};

	test('f006_zustellungtab_laedt_das_profil_genau_einmal', () => {
		assert.equal(profilAbrufe(DATEI.zustellung), 1, 'ZustellungTab: nicht genau eine Profil-Ladestelle');
		const { ast, quelle } = svelteAst(DATEI.zustellung);
		assert.equal(einbettungenMitWeichen(ast, quelle, ['BeispielAlarm']).length, 1, 'Messaufbau: ZustellungTab bettet den Beispiel-Alarm nicht genau einmal ein');
		assert.equal(einbettungenMitWeichen(ast, quelle, ['WetterMetrikenVersandPanel', 'WeatherMetricsTab']).length, 0, 'ZustellungTab bettet die Metrik-Oberflaeche ein (zweite Profil-Ladestelle)');
	});

	test('f006_beispiel_alarm_laedt_kein_profil_und_traegt_keine_metrik_oberflaeche', () => {
		assert.equal(profilAbrufe(DATEI.beispiel), 0, 'Beispiel-Alarm laedt das Profil selbst');
		const { ast, quelle } = svelteAst(DATEI.beispiel);
		assert.equal(einbettungenMitWeichen(ast, quelle, ['WetterMetrikenVersandPanel', 'WeatherMetricsTab']).length, 0, 'Beispiel-Alarm traegt die Metrik-Oberflaeche (#3154)');
	});

	// #3297/#3020: Fall WeatherMetricsTab-Profil entfaellt (Datei geloescht).
});
