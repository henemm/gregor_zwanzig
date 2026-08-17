// TDD RED — Issue #1738: "Premium-SMS-Schalter verschwindet auf /trips/new,
// wenn die SMS-Wetter-Metrik ausgeblendet wird."
// Spec: docs/specs/modules/fix_1738_trips_new_versand_tab.md — AC-1, AC-2, AC-3.
//
// NUTZERSICHT: Wer im Metriken-Tab einen Wetter-Kanal abwaehlt, verliert im
// Zeitplan-Tab den Zugang zum zugehoerigen VERSAND-Kanal — bei Premium-SMS
// doppelt verschachtelt (EditReportConfigSection.svelte:377 + :401). Premium-SMS
// ist auf der Huette der einzige empfangbare Kanal (ADR-0049).
//
// Gemessen wird am ECHTEN serverseitigen Render der echten Anlege-Komponente
// (svelte/server), nicht am Quelltext und nicht an einer Attrappe.
// Renderharness + Test-Seam: ./tripNewSsr.mjs.
//
// RED heute:
//   - Die Vorbedingung schlaegt fehl, solange TripNewEditor keine
//     `stateOverride`-Prop hat: der Zeitplan-Tab ist im Test nicht erreichbar.
//   - Danach bleiben AC-1/AC-2/AC-3 rot, weil die Kanal-Bloecke aus
//     EditReportConfigSection kommen und dort in `{#if weatherVisible.*}`
//     haengen; bei allen drei Wetter-Kanaelen aus ersetzt zusaetzlich der
//     Leerzustand `briefings-channel-empty` den gesamten Zeitplan.
//
// Ausfuehrung:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/components/trip-new/__tests__/trip_new_versandkanaele_unabhaengig_von_metriken.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import {
	renderTripNew,
	assertTabOffen,
	countTestid,
	checkboxInputTag,
	hatAttribut
} from './tripNewSsr.ts';
import { buildCreateTripPayload } from '../tripNewLogic.ts';

type WetterKanaele = { email: boolean; telegram: boolean; sms: boolean };

const KANAL_TESTIDS = ['channel-email', 'channel-telegram', 'channel-sms', 'channel-premium-sms'];

/** /trips/new mit offenem Zeitplan-Tab, breite Ansicht. */
function zeitplan(channels: WetterKanaele, reportConfig?: Record<string, unknown>): string {
	const html = renderTripNew({
		activeTab: 'zeitplan',
		isMobileViewport: false,
		channels,
		reportConfig
	});
	assertTabOffen(html, 'zeitplan');
	return html;
}

const ALLE_AN: WetterKanaele = { email: true, telegram: true, sms: true };

// ─── AC-1 ────────────────────────────────────────────────────────────────────

describe('AC-1: Premium-SMS bleibt erreichbar, wenn der Wetter-Kanal SMS abgewaehlt ist', () => {
	test('premium_sms_zeile_ueberlebt_abgewaehlten_wetterkanal_sms', () => {
		const ohneSms = zeitplan({ email: true, telegram: true, sms: false });

		assert.equal(
			countTestid(ohneSms, 'channel-premium-sms'),
			1,
			'AC-1: Mit abgewaehltem Wetter-Kanal SMS fehlt die Premium-SMS-Zeile im Zeitplan-Tab. ' +
				'Eine Anzeige-Einstellung fuer Wetter-Metriken versteckt damit den einzigen Kanal, ' +
				'der auf der Huette ankommt (ADR-0049).'
		);
	});

	test('premium_sms_schaltbarkeit_haengt_nicht_an_der_metrik_auswahl', () => {
		// Gegenprobe statt absoluter Behauptung: ob die Checkbox ueberhaupt
		// anklickbar ist, entscheidet das Tarif-/Rueckadress-Profil — NICHT die
		// Metrik-Auswahl. Also muss der Deaktiviert-Zustand in beiden Faellen
		// derselbe sein.
		const mitSms = zeitplan(ALLE_AN);
		const ohneSms = zeitplan({ email: true, telegram: true, sms: false });

		assert.equal(
			hatAttribut(checkboxInputTag(ohneSms, 'channel-premium-sms'), 'disabled'),
			hatAttribut(checkboxInputTag(mitSms, 'channel-premium-sms'), 'disabled'),
			'AC-1: Die Bedienbarkeit des Premium-SMS-Schalters aendert sich mit der ' +
				'Wetter-Metrik-Auswahl — sie darf nur vom Profil abhaengen.'
		);
	});
});

// ─── AC-2 ────────────────────────────────────────────────────────────────────

describe('AC-2: alle vier Versandkanaele sind von jeder Metrik-Auswahl unabhaengig', () => {
	const KOMBINATIONEN: Array<[string, WetterKanaele]> = [
		['alle Wetter-Kanaele an', ALLE_AN],
		['E-Mail abgewaehlt', { email: false, telegram: true, sms: true }],
		['Telegram abgewaehlt', { email: true, telegram: false, sms: true }],
		['SMS abgewaehlt', { email: true, telegram: true, sms: false }],
		['alle abgewaehlt', { email: false, telegram: false, sms: false }]
	];

	for (const [name, channels] of KOMBINATIONEN) {
		test(`alle_vier_kanalzeilen_vorhanden__${name.replace(/\W+/g, '_')}`, () => {
			const html = zeitplan(channels);
			for (const testid of KANAL_TESTIDS) {
				assert.equal(
					countTestid(html, testid),
					1,
					`AC-2 (${name}): Die Zeile "${testid}" fehlt im Zeitplan-Tab (oder steht doppelt ` +
						'darin). Die Sichtbarkeit eines VERSAND-Kanals darf an keiner Metrik-Auswahl ' +
						'haengen.'
				);
			}
		});
	}

	test('zeitplan_bleibt_bedienbar_wenn_kein_wetterkanal_gewaehlt_ist', () => {
		// Positivkontrolle zur Kombination "alle abgewaehlt": heute ersetzt der
		// Leerzustand briefings-channel-empty den kompletten Zeitplan, der Nutzer
		// kann die Sendezeit seines Kanals dann gar nicht mehr einstellen.
		const html = zeitplan({ email: false, telegram: false, sms: false });
		assert.equal(
			countTestid(html, 'morning-master-switch'),
			1,
			'AC-2: Ohne aktive Wetter-Metrik-Kanaele verschwindet der Briefing-Zeitplan aus dem ' +
				'Zeitplan-Tab — das Metrik-Gating darf den Versand-Bereich nicht mehr abschalten.'
		);
	});
});

// ─── AC-3 ────────────────────────────────────────────────────────────────────

describe('AC-3: gesetzte Versandkanaele bleiben gesetzt, egal welche Wetter-Kanaele aktiv sind', () => {
	test('angehakte_kanaele_werden_beim_rendern_nicht_still_zurueckgesetzt', () => {
		const html = zeitplan(
			{ email: false, telegram: false, sms: false },
			{ send_email: true, send_telegram: true, send_sms: true, send_premium_sms: true }
		);

		for (const testid of KANAL_TESTIDS) {
			assert.equal(
				hatAttribut(checkboxInputTag(html, testid), 'checked'),
				true,
				`AC-3: "${testid}" ist in report_config eingeschaltet, wird aber nicht angehakt ` +
					'gerendert. Der Nutzer sieht einen Kanal als aus, den er eingeschaltet hat — und ' +
					'der Write-Back schreibt das "aus" anschliessend fest (syncSendFlags).'
			);
		}
	});

	test('speicher_payload_traegt_send_premium_sms_unabhaengig_von_den_wetterkanaelen', () => {
		// Zweite Haelfte derselben Zusicherung, eine Ebene tiefer: der
		// Speicher-Payload. Diese Haelfte ist heute bereits gruen — der
		// Payload-Bauer hat nie auf Kanaele gefiltert. Sie steht hier als
		// Gegenprobe, damit ein kuenftiges Gating im Speicherpfad auffliegt.
		const payload = buildCreateTripPayload({
			name: 'Karnischer Hoehenweg',
			startDate: '2026-09-01',
			stages: [{ id: 1, name: 'Etappe 1' }],
			channels: { email: false, telegram: false, sms: false },
			reportConfig: { send_premium_sms: true }
		});

		assert.equal(
			payload.report_config?.send_premium_sms,
			true,
			'AC-3: send_premium_sms erreicht den angelegten Trip nicht, obwohl der Schalter gesetzt ist.'
		);
	});
});
