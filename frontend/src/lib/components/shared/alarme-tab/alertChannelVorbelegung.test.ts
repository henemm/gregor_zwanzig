// TDD RED — Issue #2801 (Epic #2791 S9): Alarm-Dringlichkeit je Kanal, Vorbelegung
// E-Mail/Telegram „gering“ (LOW), SMS „mittel“ (MODERATE), Premium-SMS „hoch“ (HIGH).
// Spec: docs/specs/modules/feat_2801_alarm_schwelle_vorbelegung_je_kanal.md — Test Plan T9, T10, T11
// (Frontend-Seite), T12. Python-Seite: tests/tdd/test_2801_alarm_schwelle_vorbelegung.py.
//
// RED heute: alertChannelState.ts belegt jeden Kanal mit dem Einzelwert 'LOW' vor
// (DEFAULT_CHANNEL_THRESHOLD), zustellungModell.ts faellt auf 'LOW' zurueck, der Premium-Hinweis
// sagt noch „vorerst … eigene Auswahl kommt später“.
//
// Reine Logik-Tests (keine Mocks, kein DOM): echte Funktionen mit echten Ein-/Ausgabewerten
// (ADR-0020). T11/T12 lesen Fixture bzw. Kataloge als DATEN.
// doc-compliance-test (nur T11-Paritaets-Fixture und T12-Katalogtexte)
//
//   cd frontend && npm test -- src/lib/components/shared/alarme-tab/alertChannelVorbelegung.test.ts

import { test, describe, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

import { resolveAlertChannelThresholds, resolveChannelThreshold } from './alertChannelState.ts';
import { initialCreateTripAlarmState } from '../../trip-new/tripNewLogic.ts';
import { alarmePropsAus, type AlarmeZustandsQuelle } from '../../compare/alarmePropsAus.ts';
import {
	dringlichkeitVon,
	dringlichkeitZelle,
	kanalStatus,
	standAusPreset,
	standAusTrip
} from '../zustellung-tab/zustellungModell.ts';
import { zustellungNutzlast } from '../zustellung-tab/zustellungSpeicherung.ts';
import { presetVoll, profilAllesVerbunden, tripVoll } from '../zustellung-tab/__tests__/zustellungTabDaten.ts';
import { locale } from '../../../i18n/index.ts';

const HIER = dirname(fileURLToPath(import.meta.url));
const REPO = resolve(HIER, '..', '..', '..', '..', '..', '..');
const MESSAGES = resolve(HIER, '..', '..', '..', 'i18n', 'messages');

const ERWARTET = { email: 'LOW', telegram: 'LOW', sms: 'MODERATE', premium_sms: 'HIGH' } as const;
const kopie = <T>(x: T): T => JSON.parse(JSON.stringify(x));

afterEach(() => locale.set('de'));

// ── T9: eine Quelle, Neuanlage Trip und Orts-Vergleich ─────────────────────────

describe('T9 / AC-6: resolveAlertChannelThresholds() liefert die Vorbelegung je Kanal', () => {
	test('ohne Bestand (undefined, null, {}): email LOW, telegram LOW, sms MODERATE, premium_sms HIGH', () => {
		for (const leer of [undefined, null, {}]) {
			assert.deepEqual(
				resolveAlertChannelThresholds(leer),
				ERWARTET,
				`Vorbelegung ohne Bestand (${JSON.stringify(leer)}) muss je Kanal gelten`
			);
		}
	});

	test('ausdruecklich gesetztes LOW bleibt LOW, nicht gesetzte Kanaele behalten ihre Vorbelegung', () => {
		const s = resolveAlertChannelThresholds({ sms: 'LOW' });
		assert.equal(s.sms, 'LOW', 'gesetztes LOW fuer SMS darf nicht auf MODERATE springen');
		assert.equal(s.premium_sms, 'HIGH', 'Premium-SMS ohne Wert: Vorbelegung HIGH');
		assert.equal(s.email, 'LOW');
		assert.equal(resolveAlertChannelThresholds({ premium_sms: 'LOW' }).premium_sms, 'LOW');
	});

	test('Fix-Loop F005: jeder gesetzte Wert (LOW, MODERATE, HIGH) bleibt auf jedem Kanal unveraendert', () => {
		const kanaele = ['email', 'telegram', 'sms', 'premium_sms'] as const;
		for (const kanal of kanaele) {
			for (const gesetzt of ['LOW', 'MODERATE', 'HIGH'] as const) {
				assert.equal(resolveChannelThreshold(gesetzt, kanal), gesetzt, `${kanal}=${gesetzt}`);
				const s = resolveAlertChannelThresholds({ [kanal]: gesetzt });
				for (const andere of kanaele) {
					assert.equal(s[andere], andere === kanal ? gesetzt : ERWARTET[andere], `${kanal}=${gesetzt}: ${andere}`);
				}
			}
		}
	});

	test('unbekannter oder leerer Wert gilt wie nicht gesetzt (Vorbelegung des Kanals)', () => {
		const s = resolveAlertChannelThresholds({ sms: 'gering', premium_sms: '' });
		assert.equal(s.sms, 'MODERATE');
		assert.equal(s.premium_sms, 'HIGH');
	});

	test('Neuanlage Trip: initialCreateTripAlarmState() traegt die Vorbelegung je Kanal', () => {
		assert.deepEqual(initialCreateTripAlarmState().channelThresholds, ERWARTET);
	});

	test('Neuanlage Orts-Vergleich: erste Stufenwahl schreibt die Vorbelegung der uebrigen Kanaele (ein Code)', () => {
		const wiz: AlarmeZustandsQuelle = {};
		alarmePropsAus(wiz).onThresholdChange('email', 'HIGH');
		assert.deepEqual(
			wiz.channelThresholds,
			{ ...ERWARTET, email: 'HIGH' },
			'die nicht gewaehlten Kanaele muessen dieselben Startwerte tragen wie beim Trip'
		);
	});

	test('Fix-Loop F004: unbekannter Bestandswert bleibt bei einer anderen Stufenwahl erhalten (kein stiller Wertverlust)', () => {
		const wiz: AlarmeZustandsQuelle = { channelThresholds: { sms: 'ZUKUNFT' } };
		alarmePropsAus(wiz).onThresholdChange('email', 'HIGH');
		assert.deepEqual(wiz.channelThresholds, { email: 'HIGH', telegram: 'LOW', sms: 'ZUKUNFT', premium_sms: 'HIGH' });
	});

	test('Orts-Vergleich mit Bestand {sms: LOW}: eine andere Stufenwahl laesst das gesetzte LOW stehen', () => {
		const wiz: AlarmeZustandsQuelle = { channelThresholds: { sms: 'LOW' } };
		alarmePropsAus(wiz).onThresholdChange('telegram', 'MODERATE');
		assert.deepEqual(wiz.channelThresholds, { email: 'LOW', telegram: 'MODERATE', sms: 'LOW', premium_sms: 'HIGH' });
	});
});

// ── T10: Zustellung-Modell und Speichern ─────────────────────────────────────

describe('T10 / AC-7 / AC-8: Zustellung zeigt die Vorbelegung und speichert nur angezeigte Werte', () => {
	test('dringlichkeitVon(): fehlender Wert = Vorbelegung des Kanals, gesetztes LOW bleibt', () => {
		assert.equal(dringlichkeitVon(undefined, 'email'), 'LOW');
		assert.equal(dringlichkeitVon({}, 'telegram'), 'LOW');
		assert.equal(dringlichkeitVon(undefined, 'sms'), 'MODERATE');
		assert.equal(dringlichkeitVon({}, 'premium_sms'), 'HIGH');
		assert.equal(dringlichkeitVon({ sms: 'LOW' }, 'sms'), 'LOW');
		assert.equal(dringlichkeitVon({ premium_sms: 'gering' }, 'premium_sms'), 'HIGH', 'Unbekanntes = nicht gesetzt');
	});

	test('Trip und Orts-Vergleich ohne alert_channel_thresholds: Stand zeigt gering/gering/mittel/hoch', () => {
		const trip = tripVoll();
		delete trip.alert_channel_thresholds;
		const preset = presetVoll();
		delete preset.alert_channel_thresholds;
		assert.deepEqual(standAusTrip(trip).dringlichkeit, ERWARTET);
		assert.deepEqual(standAusPreset(preset).dringlichkeit, ERWARTET);
	});

	test('Zelle der Kanaltabelle zeigt bei fehlendem Wert die Vorbelegung (SMS mittel, Premium hoch)', () => {
		const trip = tripVoll({ alert_channels: { email: true, telegram: true, sms: true, premium_sms: true } });
		delete trip.alert_channel_thresholds;
		const stand = standAusTrip(trip);
		const st = kanalStatus(profilAllesVerbunden());
		const sms = dringlichkeitZelle('sms', stand, st);
		const premium = dringlichkeitZelle('premium_sms', stand, st);
		assert.equal(sms.art === 'segment' && sms.wert, 'MODERATE');
		assert.equal(premium.art === 'segment' && premium.wert, 'HIGH');
	});

	test('Fix-Loop F003: Zelle mit lueckenhaftem Stand (Kanal fehlt in dringlichkeit) zeigt die Vorbelegung des Kanals', () => {
		const trip = tripVoll({ alert_channels: { email: true, telegram: true, sms: true, premium_sms: true } });
		const stand = standAusTrip(trip);
		const lueckenhaft = { ...stand, dringlichkeit: { email: 'HIGH' } } as unknown as typeof stand;
		const st = kanalStatus(profilAllesVerbunden());
		const wert = (k: 'email' | 'telegram' | 'sms' | 'premium_sms') => {
			const z = dringlichkeitZelle(k, lueckenhaft, st);
			return z.art === 'segment' ? z.wert : z.art;
		};
		assert.deepEqual(
			{ email: wert('email'), telegram: wert('telegram'), sms: wert('sms'), premium_sms: wert('premium_sms') },
			{ email: 'HIGH', telegram: 'LOW', sms: 'MODERATE', premium_sms: 'HIGH' }
		);
	});

	for (const kontext of ['route', 'vergleich'] as const) {
		test(`${kontext}: Aenderung nur eines Kanals sendet die angezeigten Werte, kein Wert springt`, () => {
			const roh = kontext === 'route' ? tripVoll() : presetVoll();
			delete roh.alert_channel_thresholds;
			const vorher = kontext === 'route' ? standAusTrip(roh) : standAusPreset(roh);
			const jetzt = kopie(vorher);
			jetzt.dringlichkeit.email = 'HIGH';
			const n = zustellungNutzlast(kontext, vorher, jetzt);
			assert.deepEqual(n.alarme?.alert_channel_thresholds, { ...ERWARTET, email: 'HIGH' });
		});

		test(`${kontext}: ohne Dringlichkeitsaenderung wird alert_channel_thresholds nicht gesendet`, () => {
			const roh = kontext === 'route' ? tripVoll() : presetVoll();
			delete roh.alert_channel_thresholds;
			const vorher = kontext === 'route' ? standAusTrip(roh) : standAusPreset(roh);
			const jetzt = kopie(vorher);
			jetzt.alarme.premium_sms = !jetzt.alarme.premium_sms;
			const n = zustellungNutzlast(kontext, vorher, jetzt);
			assert.ok(n.alarme && !('alert_channel_thresholds' in n.alarme), JSON.stringify(n.alarme));
		});
	}
});

// ── T11: Paritaet Python ↔ Frontend ───────────────────────────────────────────

describe('T11 / AC-13: Frontend-Vorbelegung = Python-Vorbelegung (Paritaets-Fixture)', () => {
	test('resolveAlertChannelThresholds(undefined) gleich tests/fixtures/alarm_schwelle_vorbelegung_2801.json', () => {
		const fixture = JSON.parse(readFileSync(join(REPO, 'tests', 'fixtures', 'alarm_schwelle_vorbelegung_2801.json'), 'utf8'));
		assert.deepEqual(fixture, ERWARTET, 'Fixture weicht von der Spec ab');
		assert.deepEqual(resolveAlertChannelThresholds(undefined), fixture);
	});
});

// ── T12: Texte DE/EN ──────────────────────────────────────────────────────────

const katalog = (lang: string, bereich: string): Record<string, string> =>
	JSON.parse(readFileSync(join(MESSAGES, lang, `${bereich}.json`), 'utf8'));

describe('T12 / AC-9: Hinweis Premium-SMS und Fusszeile Zustellung in DE und EN', () => {
	test('Hinweis Premium-SMS unter „Was steht wo“ hat den neuen Wortlaut', () => {
		assert.equal(katalog('de', 'wetter')['wetter.wsw.kanal.premium_hinweis'], 'Die Premium-SMS bekommt denselben Inhalt wie die SMS.');
		assert.equal(katalog('en', 'wetter')['wetter.wsw.kanal.premium_hinweis'], 'The Premium SMS gets the same content as the SMS.');
	});

	test('„eigene Auswahl kommt später“ steht in keinem Katalog mehr (DE und EN)', () => {
		for (const bereich of ['wetter', 'zustellung']) {
			for (const [lang, muster] of [['de', /eigene Auswahl kommt später|vorerst denselben/i], ['en', /separate selection comes later|for now/i]] as const) {
				const treffer = Object.entries(katalog(lang, bereich)).filter(([k, v]) => k.includes('premium') && muster.test(v));
				assert.deepEqual(treffer, [], `${lang}/${bereich}: alter Premium-Satz noch vorhanden`);
			}
		}
	});

	test('Fusszeile der Kanal-Tabelle nennt die Vorbelegung und dass eine eigene Wahl gilt', () => {
		const de = katalog('de', 'zustellung')['zustellung.legende'];
		const en = katalog('en', 'zustellung')['zustellung.legende'];
		assert.match(de, /mittel/);
		assert.match(de, /hoch/);
		assert.match(de, /jederzeit|selbst|eigene/i, `DE-Fusszeile muss sagen, dass eine eigene Wahl gilt: ${de}`);
		assert.match(en, /moderate/i);
		assert.match(en, /high/i);
		assert.match(en, /any ?time|your own|yourself/i, `EN-Fusszeile muss sagen, dass eine eigene Wahl gilt: ${en}`);
	});
});
