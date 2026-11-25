// TDD (Regressionswaechter) — Issue #1433: je Trip-Reiter landet JEDES bedienbare
// Feld nach dem Umbau auf Teilfeld-Nutzlasten auf dem Server — inklusive der
// Loeschfaelle (leere Auswahl, leere Liste, false). Schutz gegen den stillen
// Fehler „ein Eigen-Schluessel wurde in der Allowlist vergessen und wird nicht
// mehr gespeichert".
//
// Spec: docs/specs/bugfix/trip_mehrreiter_konfliktschutz.md — §2 (Tabelle),
//       §2 Regel 2 (Loeschsemantik), AC-11 bis AC-15, AC-17.
//
// Hinweis zum Status: diese Datei ist VOR der Umsetzung weitgehend gruen (die
// heutige Vollkopie schreibt auch die Eigenfelder) — sie soll NACH der Umsetzung
// gruen BLEIBEN und faengt jeden vergessenen Eigen-Schluessel. Sie ist ein
// Waechter, kein Bug-Nachweis (den liefern W1/W2 und die Nutzlast-Datei).
//
// Gemessen: der SERVER-Stand im Ersatz-Server (Go-Merge) nach dem Speichern ueber
// den ECHTEN Reiter (Instanz-Skript + echtes `api`). Frischer Stand, kein Konflikt.
//
// Issue #2284 S2 (AC-17): Kopf (Name, NEU Region) ueber `TripHeader.onSaveField`
// (Pruefstand `kopfReiter`); Tempo seit #3196 ueber den Reiter Etappen (`tempoReiter`).
//
// Ausfuehren:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --experimental-test-module-mocks --test \
//     src/lib/components/trip-detail/__tests__/trip_reiter_roundtrip_jedes_feld.test.ts

import { test, describe, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';

import { api } from '../../../api.ts';
import { clearEtagRegistry } from '../../../etagRegistry.ts';
import { createFakeTripServer, type FakeTripServer } from '../../../__tests__/fakeTripServer.ts';
import * as P from './tripMehrreiterPruefstand.ts';

let server: FakeTripServer;
const SEED = P.vollerTrip();

beforeEach(async () => {
	clearEtagRegistry();
	server = createFakeTripServer({ merge: true });
	server.install();
	server.seed(P.TRIP_ID, P.vollerTrip());
	await api.get(P.TRIP_PFAD);
});
afterEach(() => server.restore());

const stand = () => server.stand(P.TRIP_ID);
const dc = () => stand().display_config as Record<string, unknown>;
const rc = () => stand().report_config as Record<string, unknown>;

/** Python-eigene Schluessel duerfen sich bei KEINEM Reiter aendern. */
function pythonEigenesUnveraendert(): void {
	const seedRc = SEED.report_config as Record<string, unknown>;
	for (const k of P.PYTHON_EIGEN_REPORT) {
		assert.deepEqual(rc()[k], seedRc[k], `report_config.${k} ist Python-eigen und darf nie veraendert werden`);
	}
}

describe('Alarme (AC-11, AC-17)', () => {
	test('Kanal einschalten (SMS)', async () => {
		const a = P.neuerAufbau();
		const r = await P.alarmeReiter(a);
		r.kanalUmschalten('sms');
		await P.fertig(a.ctl);
		assert.deepEqual(stand().alert_channels, { email: true, telegram: true, sms: true, premium_sms: false });
		pythonEigenesUnveraendert();
	});

	test('Kanal AUSschalten (E-Mail): false kommt an', async () => {
		const a = P.neuerAufbau();
		const r = await P.alarmeReiter(a);
		r.kanalUmschalten('email');
		await P.fertig(a.ctl);
		assert.equal((stand().alert_channels as Record<string, unknown>).email, false);
	});

	test('Kanal-Schwelle (Telegram)', async () => {
		const a = P.neuerAufbau();
		const r = await P.alarmeReiter(a);
		r.schwelleAendern('telegram', 'LOW');
		await P.fertig(a.ctl);
		assert.deepEqual(stand().alert_channel_thresholds, { email: 'LOW', telegram: 'LOW', sms: 'MODERATE', premium_sms: 'HIGH' });
	});

	test('Abkuehlzeit', async () => {
		const a = P.neuerAufbau();
		const r = await P.alarmeReiter(a);
		r.cooldownAendern(30);
		await P.fertig(a.ctl);
		assert.equal(stand().alert_cooldown_minutes, 30);
	});

	test('Ruhezeiten', async () => {
		const a = P.neuerAufbau();
		const r = await P.alarmeReiter(a);
		r.ruhezeitAendern('23:00', '06:00');
		await P.fertig(a.ctl);
		assert.equal(stand().alert_quiet_from, '23:00');
		assert.equal(stand().alert_quiet_to, '06:00');
	});

	test('Amtliche Warnungen aus: enabled=false, sources bleiben (Server-Merge)', async () => {
		const a = P.neuerAufbau();
		const r = await P.alarmeReiter(a);
		r.amtlicheWarnungenUmschalten(false);
		await P.fertig(a.ctl);
		assert.deepEqual(stand().official_warnings, { enabled: false, sources: ['meteoalarm'] });
	});

	test('Alarm-Empfindlichkeit: metric_alert_levels aktualisiert, display_config sonst unberuehrt', async () => {
		const a = P.neuerAufbau();
		const r = await P.alarmeReiter(a);
		r.empfindlichkeitAendern('wind', 'sensibel');
		await P.fertig(a.ctl);
		const seedDc = SEED.display_config as Record<string, unknown>;
		assert.deepEqual(dc().metric_alert_levels, {
			...(seedDc.metric_alert_levels as object),
			wind: 'sensibel'
		});
		assert.deepEqual({ ...dc(), metric_alert_levels: undefined }, { ...seedDc, metric_alert_levels: undefined });
	});
});

// Wertebereiche Desktop/Mobile (AC-12, AC-17): #2794 S3a Teil-PR 4a (AC-31) mit dem
// CorridorEditor entfernt — die Grenzen schreibt der Reiter Wetter.

// #3297/#3020: „Wetter-Metriken (AC-13)“ und „Versand (AC-14)“ prueften shared/WeatherMetricsTab bzw.
// trip-detail/BriefingScheduleTab (geloescht, nirgends gemountet).

describe('Kopf, Tempo, Etappen (AC-15)', () => {
	test('Name', async () => {
		const a = P.neuerAufbau();
		const k = await P.kopfReiter(a);
		await k.umbenennen('Neuer Name');
		assert.equal(stand().name, 'Neuer Name');
	});

	// #3196: Tempo (Reiter Etappen) statt Aktivitaet (Kopf); activity bleibt als Altfeld.
	test('Tempo (#3196)', async () => {
		const a = P.neuerAufbau();
		const t = await P.tempoReiter(a);
		await t.aendern({ fortbewegung: 'rad', grundtempo_kmh: 18 });
		assert.deepEqual(stand().tempo, { fortbewegung: 'rad', grundtempo_kmh: 18 });
		assert.equal(stand().activity, 'trekking');
	});

	test('Etappen', async () => {
		const a = P.neuerAufbau();
		const e = await P.etappenReiter(a);
		e.speichern([{ id: 'T1', name: 'Umbenannt', date: '2026-10-10', waypoints: [] }]);
		await P.fertig(a.ctl);
		assert.equal((stand().stages as Array<{ name: string }>)[0].name, 'Umbenannt');
	});
});

// Issue #2284 S2 (AC-2, AC-3, AC-6, AC-17): Region ist neues Eigenfeld des Kopfs
// (`TripHeader.onSaveField('region', …)`); Name/Region nacheinander lassen
// jedes andere Feld des Trips unveraendert.
describe('#2284 S2: Kopf-Region und die Kopf-Folge Name ⇒ Region', () => {
	test('Region setzen', async () => {
		const a = P.neuerAufbau();
		const k = await P.kopfReiter(a);
		await k.regionAendern('Alpen Nord');
		assert.equal(stand().region, 'Alpen Nord');
		assert.equal(k.geschlossen.region, 1, 'gespeichert ⇒ der Kopf schliesst das Feld');
	});

	test('Region leeren: der Leerstring kommt an (Go: omitempty laesst den Schluessel fallen)', async () => {
		const a = P.neuerAufbau();
		const k = await P.kopfReiter(a);
		await k.regionAendern('');
		assert.equal(stand().region ?? '', '', 'die alte Region „Korsika" darf nicht stehen bleiben');
		assert.equal(k.geschlossen.region, 1);
	});

	test('AC-6: nacheinander Name, Region — danach ist ALLES uebrige unveraendert', async () => {
		const a = P.neuerAufbau();
		const vorher = stand();
		const k = await P.kopfReiter(a);
		await k.umbenennen('Neuer Name');
		await k.regionAendern('Alpen Nord');
		assert.deepEqual(stand(), { ...vorher, name: 'Neuer Name', region: 'Alpen Nord' });
		pythonEigenesUnveraendert();
	});
});
