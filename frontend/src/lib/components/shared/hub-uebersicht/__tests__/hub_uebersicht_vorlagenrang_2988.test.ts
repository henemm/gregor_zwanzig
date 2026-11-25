// #2988 S3 (F001): die Trip-Uebersicht waehlt die Vorlage wie Python: `ampel.template` vor `preset_name` vor
// `profil`. Spec: docs/specs/modules/rework_2988_ampel_ableitung.md (Uebersichten bleiben in S3 gleich).
// Erwartung aus echtem Python (`aufgeloestVon`); die Vorlagen der Faelle zeigen nachweislich verschiedene Zahlen.
// Nur der Trip: die Wetter-Karte des Ortsvergleichs zaehlt bei geladenem Katalog die Auswahl, nicht die Ampel
// (die Vorlagen-Wahl ist dort nicht sichtbar), ihren Titel rechnet `aboVorlagenName` (vorlage_statt_profil_2796).
//
//   cd frontend && npm test -- src/lib/components/shared/hub-uebersicht/__tests__/hub_uebersicht_vorlagenrang_2988.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { aufgeloestVon, live } from '../../wetter-tab/__tests__/wetterTabDaten.ts';

const HIER = dirname(fileURLToPath(import.meta.url));
const FRONTEND = resolve(HIER, '..', '..', '..', '..', '..', '..');
const basis = pathToFileURL(FRONTEND + '/').href;
register(pathToFileURL(join(FRONTEND, 'test-env-dynamic-private-stub-hooks.mjs')).href, basis);
register(pathToFileURL(join(FRONTEND, 'test-app-environment-stub-hooks.mjs')).href, basis);

type Json = any; // eslint-disable-line @typescript-eslint/no-explicit-any
const m: Json = await import(pathToFileURL(join(HIER, '..', 'hubUebersichtModell.ts')).href);
const am: Json = await import(pathToFileURL(join(HIER, '..', '..', 'wetter-tab', 'ampelModell.ts')).href);
const { standAusAbo }: Json = await import(pathToFileURL(join(HIER, '..', '..', 'wetter-tab', 'wetterZustand.ts')).href);
const d = live();
const VORLAGEN: Json = am.vorlagenAusTemplates(d.templates);
const EIG: Json = am.eigenschaftenAusKatalog(d.metrics);

type Wahl = { template?: string; preset_name?: string; profil?: string };
/** Trip ohne andere Alarmquellen; Auswahl fest, nur die Vorlage entscheidet ueber „Alarm ab“. */
function trip(w: Wahl, metriken: string[]): Json {
	return {
		id: 't-2988',
		name: 'Rang',
		stages: [],
		report_config: { enabled: true, alert_on_changes: false },
		alert_rules: [],
		...(w.profil ? { profil: w.profil } : {}),
		display_config: {
			metrics: metriken.map((metric_id) => ({ metric_id, enabled: true })),
			ampel: w.template ? { template: w.template } : {},
			...(w.preset_name ? { preset_name: w.preset_name } : {})
		}
	};
}
function soll(t: Json): Json {
	const stand = standAusAbo('route', t, aufgeloestVon(t), {}, { eig: EIG });
	return am.alarmZaehler(stand.ampel, stand.auswahl, EIG);
}
const text = (t: Json): string => m.tripAlarmAbText(t, VORLAGEN, EIG);

const ALLE = Object.keys(VORLAGEN.allgemein.metrics);
const ausloesend = (template: string, metriken: string[]): number => Number(soll(trip({ template }, metriken)).werte?.ausloesend ?? 0);
const aktiv = (id: string, metrik: string): boolean => ausloesend(id, [metrik]) > 0;
/** Zwei Vorlagen, deren Zahl sich untereinander und von „allgemein“ unterscheidet. */
function zweiVerschiedene(): [string, string] {
	const zahlen = new Map<number, string>([[ausloesend('allgemein', ALLE), 'allgemein']]);
	for (const id of Object.keys(VORLAGEN).sort()) if (!zahlen.has(ausloesend(id, ALLE))) zahlen.set(ausloesend(id, ALLE), id);
	const [, a, b] = [...zahlen.values()];
	assert.ok(a && b, `Messaufbau: keine zwei Vorlagen mit eigener Zahl (${JSON.stringify([...zahlen])})`);
	return [a, b];
}
const [A, B] = zweiVerschiedene();
const FAELLE: [string, Wahl, string][] = [
	['nur_template', { template: A }, A],
	['nur_preset_name', { preset_name: A }, A],
	['nur_profil', { profil: A }, A],
	['template_vor_preset_name', { template: A, preset_name: B }, A],
	['template_vor_profil', { template: A, profil: B }, A],
	['preset_name_vor_profil', { preset_name: A, profil: B }, A],
	['preset_name_vor_profil_umgekehrt', { preset_name: B, profil: A }, B],
	['template_vor_preset_name_vor_profil', { template: B, preset_name: A, profil: A }, B],
	['nichts_gesetzt_allgemein', {}, 'allgemein']
];

describe('F001 (#2988): Rangfolge der Vorlagen-Wahl in der Alarm-Zeile der Trip-Übersicht', () => {
	test('messaufbau_zahlen_unterscheiden_sich', () => {
		const zahlen = ['allgemein', A, B].map((id) => text(trip({ template: id }, ALLE)));
		assert.equal(new Set(zahlen).size, 3, JSON.stringify(zahlen));
	});
	for (const [name, w, vorlage] of FAELLE) {
		test(`alarm_zeile_${name}`, () => {
			const t = trip(w, ALLE);
			assert.equal(aufgeloestVon(t).vorlage_id, vorlage, 'Messaufbau: Python wählt eine andere Vorlage');
			const z = soll(t);
			assert.equal(z.art, 'zaehler');
			assert.match(text(t), new RegExp(`^${z.werte.ausloesend} von ${z.werte.ausgewaehlt} Metriken lösen einen Alarm aus`));
		});
	}
});

// „Wetter-Alarm aktiv“: eine Metrik, die die eine Vorlage alarmiert und die andere nicht.
describe('F001 (#2988): Rangfolge in „Wetter-Alarm aktiv“', () => {
	/** Vorlage, Metrik: nur `vorlage` unterscheidet sich von `allgemein` in „loest aus“. */
	const PAARE = Object.keys(VORLAGEN).flatMap((id) => ALLE.filter((x) => aktiv(id, x) !== aktiv('allgemein', x)).map((x) => [id, x] as const));
	test('messaufbau_paar_vorhanden', () => assert.ok(PAARE.length > 0));
	const [V, X] = PAARE[0] ?? ['allgemein', 'gust'];
	const G = 'allgemein';
	const RAENGE: [string, Wahl, string][] = [
		['nur_template', { template: V }, V],
		['nur_preset_name', { preset_name: V }, V],
		['nur_profil', { profil: V }, V],
		['template_vor_preset_name', { template: V, preset_name: G }, V],
		['template_vor_preset_name_umgekehrt', { template: G, preset_name: V }, G],
		['preset_name_vor_profil', { preset_name: V, profil: G }, V],
		['preset_name_vor_profil_umgekehrt', { preset_name: G, profil: V }, G]
	];
	for (const [name, w, vorlage] of RAENGE) {
		test(`aktiv_${name}`, () => {
			const t = trip(w, [X]);
			assert.equal(aufgeloestVon(t).vorlage_id, vorlage, 'Messaufbau: Python wählt eine andere Vorlage');
			assert.equal(m.tripWetterAlarmAktiv(t, VORLAGEN, EIG), aktiv(vorlage, X));
		});
	}
});
