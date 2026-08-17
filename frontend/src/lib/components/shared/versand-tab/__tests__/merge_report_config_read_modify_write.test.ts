// Issue #1738 Fix-Loop 1 — Findings F001 (Replace statt Merge) und F002 (der
// Schutzmechanismus war unbewacht).
//
// Warum dieser Test hier und nicht als Render-Test von /trips/new: der gesamte
// bisherige Versand-Testbestand rendert ueber `svelte/server`s `render()`, und
// dort laufen `$effect` und `onMount` NIE (im Repo dokumentiert in
// shared/__tests__/weather_metrics_tab_create_mode_callback.test.ts:5). Die
// Merge-Regel war damit nur dort geprueft, wo der Code steht — nicht dort, wo
// sie wirkt: der Adversary nahm den Guard (M2) und den Live-Read (M3) wieder
// heraus, ohne dass einer von 2677 Tests rot wurde.
//
// Geprueft wird deshalb die reine Funktion `../mergeReportConfig.ts`, die beide
// Schreiber (VersandTab.svelte, EditReportConfigSection.svelte) benutzen —
// inklusive der Abfolge ZWEIER Laeufe, also genau der Situation, die es auf
// /trips/new erstmals gibt (beide Komponenten dauerhaft nebeneinander auf
// demselben bind:reportConfig).
//
// Spec: docs/specs/modules/fix_1738_trips_new_versand_tab.md — AC-3, AC-6.
// CLAUDE.md, Daten-Schema-Reworks: Read-Modify-Write mit Merge, niemals
// Replace (BUG-DATALOSS-GR221).
//
// Pfadregel #1409: der Pruefling wird relativ zu DIESER Datei aufgeloest.
//
// Ausfuehrung:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --test src/lib/components/shared/versand-tab/__tests__/merge_report_config_read_modify_write.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { join, dirname } from 'node:path';

import { mergeReportConfig } from '../mergeReportConfig.ts';

const HERE = dirname(fileURLToPath(import.meta.url));
const versandTabCode = readFileSync(join(HERE, '..', '..', 'VersandTab.svelte'), 'utf-8');
const mailInhaltCode = readFileSync(
	join(HERE, '..', '..', '..', 'edit', 'EditReportConfigSection.svelte'),
	'utf-8'
);

/** Ein Write-Back-Lauf von VersandTab (Kanaele + Zeitplan gehoeren ihm immer).
 *  Argumentform 1:1 wie in VersandTab.svelte. */
function versandTabRun(
	snapshot: Record<string, unknown>,
	live: Record<string, unknown> | undefined,
	own: Record<string, unknown>
) {
	return mergeReportConfig({ snapshot, live, own });
}

/** Ein Write-Back-Lauf von EditReportConfigSection auf /trips/new: Mail-Inhalt
 *  gehoert ihm, Kanaele/Zeitplan NICHT (showChannels/showSchedule = false —
 *  die zeigt dort der Nachbar VersandTab). Argumentform 1:1 wie in der
 *  Komponente. */
function mailInhaltRun(
	snapshot: Record<string, unknown>,
	live: Record<string, unknown> | undefined,
	own: Record<string, unknown>,
	channels: Record<string, unknown>,
	schedule: Record<string, unknown>
) {
	return mergeReportConfig({
		snapshot,
		live,
		own,
		showSchedule: false,
		schedule,
		showChannels: false,
		channels
	});
}

describe('mergeReportConfig — Read-Modify-Write statt Replace', () => {
	test('der lebende Blob schlaegt den veralteten Mount-Schnappschuss', () => {
		// F001-Kern: der Schnappschuss stammt von onMount, der lebende Blob
		// enthaelt bereits die Aenderung des Nachbarn. Wer nur den Schnappschuss
		// als Basis nimmt, loescht sie.
		const merged = mergeReportConfig({
			snapshot: { email_format: 'full' },
			live: { email_format: 'compact' },
			own: { send_email: true }
		});
		assert.equal(merged.email_format, 'compact');
	});

	test('der Schnappschuss traegt den ersten Lauf, bevor onMount gelaufen ist', () => {
		const merged = mergeReportConfig({
			snapshot: { email_format: 'compact', change_threshold_wind: 7 },
			live: undefined,
			own: { send_email: true }
		});
		assert.equal(merged.email_format, 'compact');
		assert.equal(merged.change_threshold_wind, 7);
		assert.equal(merged.send_email, true);
	});

	test('eigene Felder gewinnen gegen Schnappschuss und lebenden Blob', () => {
		const merged = mergeReportConfig({
			snapshot: { send_premium_sms: false },
			live: { send_premium_sms: false },
			own: { send_premium_sms: true }
		});
		assert.equal(merged.send_premium_sms, true);
	});

	test('unbekannte Bestandsfelder ueberleben aus beiden Quellen', () => {
		const merged = mergeReportConfig({
			snapshot: { change_threshold_rain: 3 },
			live: { change_threshold_wind: 11, custom_unknown_flag: 'x' },
			own: { send_sms: true }
		});
		assert.equal(merged.change_threshold_rain, 3);
		assert.equal(merged.change_threshold_wind, 11);
		assert.equal(merged.custom_unknown_flag, 'x');
	});

	test('Kanal-Felder bleiben aussen vor, solange die Instanz keine Kanaele zeigt', () => {
		// Gegenprobe zu Mutation M2: ohne diesen Guard schreibt die
		// Mail-Inhalt-Karte fremde Kanal-Felder mit und setzt den Nachbarn zurueck.
		const merged = mergeReportConfig({
			snapshot: {},
			live: { send_premium_sms: true, send_telegram: true },
			own: { email_format: 'compact' },
			showChannels: false,
			channels: { send_premium_sms: false, send_telegram: false }
		});
		assert.equal(merged.send_premium_sms, true);
		assert.equal(merged.send_telegram, true);
	});

	test('Kanal-Felder werden geschrieben, sobald die Instanz die Kanaele zeigt', () => {
		// Positivkontrolle: der Guard darf den Schreibpfad nicht generell abwuergen
		// (sonst waere der Test oben auch bei kaputtem Helfer gruen).
		const merged = mergeReportConfig({
			snapshot: {},
			live: { send_premium_sms: true },
			own: {},
			showChannels: true,
			channels: { send_premium_sms: false }
		});
		assert.equal(merged.send_premium_sms, false);
	});

	test('Zeitplan-Felder bleiben aussen vor, solange die Instanz keinen Zeitplan zeigt', () => {
		const merged = mergeReportConfig({
			snapshot: {},
			live: { morning_time: '05:30:00', morning_enabled: true },
			own: {},
			showSchedule: false,
			schedule: { morning_time: '07:00:00', morning_enabled: false }
		});
		assert.equal(merged.morning_time, '05:30:00');
		assert.equal(merged.morning_enabled, true);
	});

	test('Zeitplan-Felder werden geschrieben, sobald die Instanz den Zeitplan zeigt', () => {
		const merged = mergeReportConfig({
			snapshot: {},
			live: { morning_time: '05:30:00' },
			own: {},
			showSchedule: true,
			schedule: { morning_time: '07:00:00' }
		});
		assert.equal(merged.morning_time, '07:00:00');
	});
});

describe('/trips/new — zwei Schreiber auf demselben report_config (AC-3, AC-6)', () => {
	test('Mail-Format ueberlebt einen nachfolgenden Kanal-Klick in VersandTab', () => {
		// Reproduktion des gemeldeten Verlustpfads (F001), Nutzersicht:
		// 1. Mail-Format auf "Kompakt" stellen, 2. danach Premium-SMS anhaken,
		// 3. speichern -> beides muss im Blob stehen.
		const mailSnapshot = { change_threshold_wind: 9 };
		const versandSnapshot = { change_threshold_wind: 9 };

		// Schritt 1: Mail-Inhalt-Karte schreibt email_format = compact.
		const nachMailKlick = mailInhaltRun(
			mailSnapshot,
			{ change_threshold_wind: 9 },
			{ email_format: 'compact', show_outlook: false },
			{ send_email: true, send_premium_sms: false },
			{ morning_time: '07:00:00' }
		);
		assert.equal(nachMailKlick.email_format, 'compact');

		// Schritt 2: VersandTab schreibt Premium-SMS zurueck — sein eigener
		// Schnappschuss ist zu diesem Zeitpunkt veraltet (kennt email_format nicht).
		const nachKanalKlick = versandTabRun(versandSnapshot, nachMailKlick, {
			send_email: true,
			send_telegram: false,
			send_sms: false,
			send_premium_sms: true,
			morning_time: '07:00:00'
		});

		assert.equal(
			nachKanalKlick.email_format,
			'compact',
			'email_format darf durch den Kanal-Klick nicht verloren gehen (AC-6)'
		);
		assert.equal(nachKanalKlick.show_outlook, false, 'Inhaltsbaustein bleibt erhalten (AC-6)');
		assert.equal(nachKanalKlick.send_premium_sms, true, 'Premium-SMS ist gesetzt (AC-3)');
		assert.equal(nachKanalKlick.change_threshold_wind, 9, 'unbekanntes Bestandsfeld bleibt');
	});

	test('Premium-SMS ueberlebt einen nachfolgenden Klick in der Mail-Inhalt-Karte', () => {
		// Die Gegenrichtung — dieselbe Fehlerklasse, andere Reihenfolge.
		const nachKanalKlick = versandTabRun({}, {}, {
			send_email: true,
			send_telegram: false,
			send_sms: false,
			send_premium_sms: true
		});

		const nachMailKlick = mailInhaltRun(
			{},
			nachKanalKlick,
			{ email_format: 'compact' },
			{ send_email: true, send_telegram: false, send_sms: false, send_premium_sms: false },
			{ morning_time: '07:00:00' }
		);

		assert.equal(nachMailKlick.send_premium_sms, true, 'Premium-SMS bleibt gesetzt (AC-3)');
		assert.equal(nachMailKlick.email_format, 'compact');
	});
});

// Die Aufrufstelle selbst ist ohne DOM-Harness nicht ausfuehrbar (siehe Kopf).
// Source-Inspection-Muster wie in
// trip-new/__tests__/trip_new_editor_weather_metrics_wiring.test.ts: geprueft
// wird, dass beide Schreiber den Helfer mit den RICHTIGEN Argumenten fuettern —
// ein korrekter Helfer, der den Mount-Schnappschuss als `live` bekommt, waere
// exakt der Fehler F001 in neuem Gewand.
describe('Verdrahtung: beide Schreiber uebergeben den lebenden Blob', () => {
	test('VersandTab.svelte liest reportConfig live (untrack), nicht den Schnappschuss', () => {
		const call = versandTabCode.match(/mergeReportConfig\(\{[\s\S]*?\n\t\t\}\)/);
		assert.ok(call, 'VersandTab.svelte ruft mergeReportConfig nicht auf');
		assert.match(
			call[0],
			/live:\s*untrack\(\(\)\s*=>\s*reportConfig\)/,
			'VersandTab uebergibt keinen Live-Read von reportConfig als `live` — mit dem ' +
				'veralteten onMount-Schnappschuss loescht der naechste Write-Back die ' +
				'Mail-Inhalt-Einstellungen des Nachbarn (F001)'
		);
	});

	test('EditReportConfigSection.svelte liest reportConfig live (untrack)', () => {
		const call = mailInhaltCode.match(/mergeReportConfig\(\{[\s\S]*?\n\t\t\}\)/);
		assert.ok(call, 'EditReportConfigSection.svelte ruft mergeReportConfig nicht auf');
		assert.match(
			call[0],
			/live:\s*untrack\(\(\)\s*=>\s*reportConfig\)/,
			'EditReportConfigSection uebergibt keinen Live-Read von reportConfig als `live` ' +
				'— Kanal-/Zeitplanwerte des Nachbarn gingen sonst verloren (F001)'
		);
	});

	test('EditReportConfigSection reicht die echten Sichtbarkeits-Flags durch', () => {
		const call = mailInhaltCode.match(/mergeReportConfig\(\{[\s\S]*?\n\t\t\}\)/);
		assert.ok(call, 'EditReportConfigSection.svelte ruft mergeReportConfig nicht auf');
		// Kurzschreibweise `showSchedule,` / `showChannels,` = die Props selbst.
		// Ein fest verdrahtetes `true` waere der zweite Schreibpfad auf fremde
		// Felder, den der Guard gerade verhindern soll (Mutation M2).
		assert.match(
			call[0],
			/\bshowSchedule,/,
			'showSchedule wird nicht als Prop durchgereicht — Zeitplan-Felder wuerden auch ' +
				'dann geschrieben, wenn diese Instanz gar keinen Zeitplan zeigt'
		);
		assert.match(
			call[0],
			/\bshowChannels,/,
			'showChannels wird nicht als Prop durchgereicht — Kanal-Felder wuerden auch dann ' +
				'geschrieben, wenn diese Instanz gar keine Kanaele zeigt (Mutation M2)'
		);
	});
});

// ── Finding F003: die Disjunktheit der Feldgruppen ──────────────────────────
//
// `own` wird IMMER geschrieben, `schedule`/`channels` nur bei gesetztem Flag.
// Taucht ein Feld in beiden Gruppen auf, gewinnt fuer dieses eine Feld wieder
// der unbedingte Pfad — also F001 zurueck, nur feldweise und noch leiser.
// Heute sind beide Aufrufstellen disjunkt; unbewacht faellt die naechste
// Feldverschiebung niemandem auf.
//
// Bewusst als Aufrufstellen-Pruefung und NICHT als Laufzeit-Wache in
// mergeReportConfig(): eine Laufzeit-Wache lauft nur, wenn jemand die Funktion
// aufruft — und die Aufrufstellen in den beiden .svelte-Dateien fuehrt kein
// Test je aus (kein DOM-Harness, siehe Kopf). Sie wuerde die Ueberschneidung
// genau dort verschlafen, wo sie entsteht, und dabei wie ein Schutz aussehen.

/** Schluessel der obersten Ebene eines benannten Objekt-Arguments im
 *  mergeReportConfig-Aufruf. Klammer-Zaehlung statt Regex, damit verschachtelte
 *  Literale und Arrays nicht mitzaehlen. */
function groupKeys(callText: string, group: string): string[] {
	const at = callText.indexOf(`${group}: {`);
	if (at === -1) return [];
	const open = callText.indexOf('{', at);
	let depth = 0;
	let close = -1;
	for (let i = open; i < callText.length; i++) {
		if (callText[i] === '{') depth++;
		else if (callText[i] === '}') {
			depth--;
			if (depth === 0) {
				close = i;
				break;
			}
		}
	}
	assert.ok(close > open, `Gruppe ${group} ist nicht geschlossen — Extraktor defekt`);
	const keys: string[] = [];
	let nested = 0;
	for (const raw of callText.slice(open + 1, close).split('\n')) {
		const line = raw.trim();
		if (nested === 0 && !line.startsWith('//')) {
			const m = line.match(/^([A-Za-z_$][\w$]*)\s*[:,]/);
			if (m) keys.push(m[1]);
		}
		for (const ch of raw) {
			if (ch === '{' || ch === '[') nested++;
			else if (ch === '}' || ch === ']') nested--;
		}
	}
	return keys;
}

function mergeCall(code: string, label: string): string {
	const call = code.match(/mergeReportConfig\(\{[\s\S]*?\n\t\t\}\)/);
	assert.ok(call, `${label} ruft mergeReportConfig nicht auf`);
	return call[0];
}

describe('F003: unbedingte und bedingte Feldgruppen bleiben disjunkt', () => {
	test('der Schluessel-Extraktor findet die Gruppen wirklich (Positivkontrolle)', () => {
		// Ohne diese Kontrolle waeren die Disjunktheits-Tests unten auch dann
		// gruen, wenn der Extraktor nichts findet — eine leere Menge ist mit
		// jeder anderen disjunkt.
		const call = mergeCall(mailInhaltCode, 'EditReportConfigSection.svelte');
		const own = groupKeys(call, 'own');
		const schedule = groupKeys(call, 'schedule');
		const channels = groupKeys(call, 'channels');
		assert.ok(own.includes('email_format'), `own-Gruppe nicht erkannt: ${own.join(',')}`);
		assert.ok(
			schedule.includes('morning_time'),
			`schedule-Gruppe nicht erkannt: ${schedule.join(',')}`
		);
		assert.ok(
			channels.includes('send_email'),
			`channels-Gruppe nicht erkannt: ${channels.join(',')}`
		);
	});

	test('EditReportConfigSection: kein Feld steht gleichzeitig in own und einer bedingten Gruppe', () => {
		const call = mergeCall(mailInhaltCode, 'EditReportConfigSection.svelte');
		const own = new Set(groupKeys(call, 'own'));
		for (const group of ['schedule', 'channels']) {
			const doppelt = groupKeys(call, group).filter((k) => own.has(k));
			assert.deepEqual(
				doppelt,
				[],
				`Feld(er) ${doppelt.join(', ')} stehen in own UND in ${group}. own wird immer ` +
					`geschrieben — damit landet das Feld auch dann im Blob, wenn diese Instanz die ` +
					`zugehoerigen Bedienelemente gar nicht zeigt, und ueberschreibt den Nachbarn (F001/F003).`
			);
		}
	});

	test('VersandTab: kein Feld steht gleichzeitig in own und einer bedingten Gruppe', () => {
		const call = mergeCall(versandTabCode, 'VersandTab.svelte');
		const own = new Set(groupKeys(call, 'own'));
		assert.ok(own.has('send_email'), `own-Gruppe nicht erkannt: ${[...own].join(',')}`);
		for (const group of ['schedule', 'channels']) {
			const doppelt = groupKeys(call, group).filter((k) => own.has(k));
			assert.deepEqual(
				doppelt,
				[],
				`Feld(er) ${doppelt.join(', ')} stehen in own UND in ${group} (F003).`
			);
		}
	});
});
