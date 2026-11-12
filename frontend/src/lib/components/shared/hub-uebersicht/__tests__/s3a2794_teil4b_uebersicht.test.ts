// TDD RED — Issue #2794 S3a, Teil-PR 4b: Übersicht U3/U4 (AC-32).
// Spec: docs/specs/modules/feat_2794_s3a_teil4_entfernen.md („Schritt 4b", „Präzisierungen")
//
// ── VERTRAG (hier festgelegt, Phase 6 baut danach; alles in hubUebersichtModell.ts) ──
//
//   U3: deriveVergleichKennzahlen(...).wertebereicheKarte
//         .eyebrow   === tr('aktionen.reiter.wetter')   (Reiter „Wetter", nicht mehr „Wertebereiche")
//         .sprungziel === { tab: 'wetter' }
//
//   U4: export function tripAlarmAbText(trip: Trip, vorlagen: VorlagenAmpeln | null,
//                                       eig: Record<string, MetrikEigenschaften> | null): string
//         Zähler des Reiters Wetter auf DERSELBEN aufgelösten Ampel:
//         alarmZaehler(standAusAbo('route', trip, vorlagen).ampel, .auswahl, eig) —
//         „{ausloesend} von {alarmfaehig} Metriken lösen einen Alarm aus" (EN „… of … metrics trigger an alert"),
//         vorlagen oder eig === null (Ladefehler) ⇒ „—", nie eine geratene Zahl.
//
//       export function tripWetterAlarmAktiv(trip: Trip, vorlagen?: VorlagenAmpeln | null,
//                                            eig?: Record<string, MetrikEigenschaften> | null): boolean
//         bisherige Quellen (Preset, Stufen, Regeln, alert_on_changes) ODER Ampel-Alarmquelle
//         des Servers (src/services/trip_alert.py ampel_alarmquelle_aktiv): nur wenn
//         display_config.ampel gesetzt, mindestens eine aktive, alarmfähige Metrik mit
//         „Alarm ab" ≠ never auf der aufgelösten Ampel. Einparametriger Aufruf bleibt gültig.
//
// Die Erwartung für „aktiv" kommt NICHT aus diesem Test, sondern aus der echten
// Python-Funktion (Paritäts-Prüfung über load_trip_from_dict): die Übersicht darf nie
// „aus" zeigen, während der Server alarmiert, und nie „an", wenn er es nicht tut.
//
//   cd frontend && npm test -- src/lib/components/shared/hub-uebersicht/__tests__/s3a2794_teil4b_uebersicht.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { execFileSync } from 'node:child_process';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { live } from '../../wetter-tab/__tests__/wetterTabDaten.ts';

const HIER = dirname(fileURLToPath(import.meta.url));
const FRONTEND = resolve(HIER, '..', '..', '..', '..', '..', '..');
const REPO = resolve(FRONTEND, '..');
const SHARED = resolve(HIER, '..', '..');
const basis = pathToFileURL(FRONTEND + '/').href;
register(pathToFileURL(join(FRONTEND, 'test-env-dynamic-private-stub-hooks.mjs')).href, basis);
register(pathToFileURL(join(FRONTEND, 'test-app-environment-stub-hooks.mjs')).href, basis);

type Json = any; // eslint-disable-line @typescript-eslint/no-explicit-any
const lade = async (p: string): Promise<Json> => import(pathToFileURL(p).href);
const modell = () => lade(join(HIER, '..', 'hubUebersichtModell.ts'));
const ampelModell = () => lade(join(SHARED, 'wetter-tab', 'ampelModell.ts'));
const wetterZustand = () => lade(join(SHARED, 'wetter-tab', 'wetterZustand.ts'));
const i18n = () => lade(join(FRONTEND, 'src', 'lib', 'i18n', 'index.ts'));

async function umgebung() {
	const am = await ampelModell();
	const d = live();
	return { vorlagen: am.vorlagenAusTemplates(d.templates), eig: am.eigenschaftenAusKatalog(d.metrics) };
}

/** Trip ohne alle bisherigen Alarmquellen — einzige mögliche Quelle ist die Ampel. */
function trip(dc: Record<string, unknown>): Json {
	return {
		id: 't-2794-4b',
		name: 'Ampel-Übersicht',
		stages: [{ id: 'T1', name: 'Tag 1', date: '2099-07-01', waypoints: [{ id: 'G1', name: 'Start', lat: 47.0, lon: 11.0, elevation_m: 1000 }] }],
		report_config: { enabled: true, alert_on_changes: false },
		alert_rules: [],
		display_config: { trip_id: 't-2794-4b', ...dc }
	};
}

const gust = (enabled = true) => ({ metric_id: 'gust', enabled });
const FAELLE: Record<string, Json> = {
	'ohne ampel-Schlüssel (Altbestand)': trip({ metrics: [gust()] }),
	'nur Vorlage „allgemein" (Böen Alarm ab Orange)': trip({ metrics: [gust()], ampel: { template: 'allgemein' } }),
	'Böen „Alarm ab" nie': trip({ metrics: [gust()], ampel: { template: 'allgemein', metrics: { gust: { alarm_ab: 'never' } } } }),
	'Böen Alarm ab Rot': trip({ metrics: [gust()], ampel: { template: 'allgemein', metrics: { gust: { alarm_ab: 'red' } } } }),
	'Böen abgewählt': trip({ metrics: [gust(false)], ampel: { template: 'allgemein', metrics: { gust: { enabled: false, alarm_ab: 'orange' } } } })
};

/** Erwartung aus der echten Server-Regel (Python), nicht aus einer Frontend-Kopie. */
function serverAktiv(): Record<string, boolean> {
	const PY = [
		'import sys, json',
		"sys.path.insert(0, 'src'); sys.path.insert(0, '.')",
		'from app.loader import load_trip_from_dict',
		'from services.trip_alert import ampel_alarmquelle_aktiv',
		'faelle = json.loads(sys.stdin.read())',
		'print(json.dumps({k: bool(ampel_alarmquelle_aktiv(load_trip_from_dict(v))) for k, v in faelle.items()}))'
	].join('\n');
	const out = execFileSync('uv', ['run', 'python3', '-c', PY], { cwd: REPO, encoding: 'utf-8', input: JSON.stringify(FAELLE) });
	return JSON.parse(out.trim().split('\n').pop()!);
}

describe('AC-32 U3: Karte der Wertebereiche im Orts-Briefing nennt den Reiter Wetter', () => {
	test('Eyebrow = Reitername „Wetter", Sprungziel = Reiter wetter', async () => {
		const m = await modell();
		const { tr } = await i18n();
		const preset = { id: 'cp', name: 'V', location_ids: [], profil: 'wandern', display_config: { ideal_ranges: { gust: {} } } };
		const k = m.deriveVergleichKennzahlen(preset, 'active', null, []).wertebereicheKarte;
		assert.deepEqual(k.sprungziel, { tab: 'wetter' });
		assert.equal(k.eyebrow, tr('aktionen.reiter.wetter'), `Eyebrow nennt noch den alten Reiter: „${k.eyebrow}"`);
	});
});

describe('AC-32 U4: Alarm-Zeile der Trip-Übersicht = „Alarm ab"-Zähler des Reiters Wetter', () => {
	test('tripAlarmAbText existiert', async () => {
		assert.equal(typeof (await modell()).tripAlarmAbText, 'function', 'tripAlarmAbText(trip, vorlagen, eig) fehlt im Modell');
	});

	for (const [name, t] of Object.entries(FAELLE)) {
		test(`${name}: Zahlen wie der Reiter Wetter (alarmZaehler auf standAusAbo)`, async () => {
			const m = await modell();
			const { vorlagen, eig } = await umgebung();
			const stand = (await wetterZustand()).standAusAbo('route', t, vorlagen);
			const z = (await ampelModell()).alarmZaehler(stand.ampel, stand.auswahl, eig);
			const text: string = m.tripAlarmAbText(t, vorlagen, eig);
			if (z.art === 'zaehler') {
				assert.match(text, new RegExp(`^${z.werte.ausloesend} von ${z.werte.alarmfaehig} Metriken lösen einen Alarm aus`), text);
			} else {
				assert.ok(!/\d/.test(text) || text === '—', `keine alarmfähige Metrik, aber Zahl geraten: „${text}"`);
			}
			assert.ok(!text.includes('Δ'), `„bei Δ" steht noch in der Zeile: „${text}"`);
		});
	}

	test('Ladefehler der Vorlagen ⇒ „—", nie eine geratene Zahl', async () => {
		const m = await modell();
		const { eig } = await umgebung();
		assert.equal(m.tripAlarmAbText(FAELLE['nur Vorlage „allgemein" (Böen Alarm ab Orange)'], null, eig), '—');
		assert.equal(m.tripAlarmAbText(FAELLE['nur Vorlage „allgemein" (Böen Alarm ab Orange)'], {}, null), '—');
	});
});

describe('AC-32 U4: „Alarm aktiv" folgt der Server-Regel ampel_alarmquelle_aktiv', () => {
	test('Parität je Fall mit der echten Python-Funktion', async () => {
		const m = await modell();
		const { vorlagen, eig } = await umgebung();
		const soll = serverAktiv();
		assert.equal(soll['nur Vorlage „allgemein" (Böen Alarm ab Orange)'], true, 'Fixtur-Schutz: Server muss für die reine Vorlage alarmieren');
		assert.equal(soll['ohne ampel-Schlüssel (Altbestand)'], false, 'Fixtur-Schutz: ohne ampel-Schlüssel alarmiert der Server nicht');
		const abweichung = Object.keys(FAELLE).filter((k) => m.tripWetterAlarmAktiv(FAELLE[k], vorlagen, eig) !== soll[k]);
		assert.deepEqual(abweichung, [], `Übersicht weicht vom Server ab: ${abweichung.map((k) => `${k} (Server ${soll[k]})`).join('; ')}`);
	});

	test('einparametriger Aufruf bleibt gültig (bisherige Quellen unverändert)', async () => {
		const m = await modell();
		assert.equal(m.tripWetterAlarmAktiv(FAELLE['ohne ampel-Schlüssel (Altbestand)']), false);
		assert.equal(m.tripWetterAlarmAktiv({ ...FAELLE['ohne ampel-Schlüssel (Altbestand)'], report_config: { alert_on_changes: true } }), true);
	});
});
