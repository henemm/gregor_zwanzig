// TDD RED — Issue #1738, Struktur-Zusicherungen der Migration.
// Spec: docs/specs/modules/fix_1738_trips_new_versand_tab.md — AC-4, AC-5, AC-6, AC-7.
//
// Die Trip-Anlage soll ihren Versand-Bereich aus EINEM geteilten Baustein beziehen statt aus einer
// zweiten Kanal-Implementierung (Teilungsregel CLAUDE.md, Epic #1230, #1199). Gemessen wird am
// serverseitigen Render der echten Anlege-Komponente — nicht am Quelltext. Renderharness + Test-Seam:
// ./tripNewSsr.ts.
//
// Issue #1743 (feat_1743_reiter_aufraeumen, AC-8/AC-19): kein Reiter „Versand" mehr.
//
// #3332 (D1 von #3307, Spec feat_3332_zustellung_anlegen_trip.md, AC-1/AC-10): der geteilte Baustein ist
// jetzt der Reiter Zustellung — derselbe wie im Hub (Anlegen = Bearbeiten) — im Schritt Zustellung, statt
// des Alt-Panels mit Versand-Abschnitt (`versand-tab`). Die Zusicherungen gelten fuer ihn: genau eine
// Implementierung, genau eine Instanz je Ansicht im richtigen Baum, Laufzeit mit abgeleitetem Enddatum.
// Die Mail-Inhalt-Karte entfaellt (Hub-Paritaet); das E-Mail-Format bedient die Karte „Was steht wo“ im
// Reiter Wetter (Wirkung im POST: trip_anlegen_zustellung_verdrahtung_3332, AC-10).
//
// Ausfuehrung:
//   cd frontend && npm test -- src/lib/components/trip-new/__tests__/trip_new_zeitplan_tab_nutzt_geteilten_versand_baustein.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import {
	renderTripNew,
	assertTabOffen,
	countTestid,
	outerHtml,
	visibleText,
	bereichVon,
	type TripNewStateOverride
} from './tripNewSsr.ts';

const ALLE_AN = { email: true, telegram: true, sms: true };

function zeitplan(extra: TripNewStateOverride = {}): string {
	const html = renderTripNew({
		activeTab: 'zustellung',
		isMobileViewport: false,
		channels: ALLE_AN,
		wtVisited: true,
		zuVisited: true,
		name: 'X',
		startDate: '2026-09-01',
		stageNames: ['E1'],
		...extra
	});
	assertTabOffen(html, 'zustellung');
	return html;
}

// ─── #1743 AC-19 → #3332 AC-1: Versand-Bereich im Schritt Zustellung ─────────

describe('#1743 AC-19 / #3332 AC-1: der Versand-Bereich ist der Reiter Zustellung im Schritt Zustellung', () => {
	for (const isMobileViewport of [false, true]) {
		test(`versand_bereich_ist_reiter_zustellung__${isMobileViewport ? 'mobil' : 'desktop'}`, () => {
			const html = zeitplan({ isMobileViewport });
			const iTab = html.indexOf('data-testid="zustellung-tab"');
			const iVersand = html.indexOf('id="versand"');
			assert.notEqual(iTab, -1, 'Kein Reiter Zustellung im Schritt Zustellung');
			assert.equal(countTestid(html, 'zustellung-tab'), 1, 'Reiter Zustellung nicht genau einmal im Dokument');
			assert.equal(countTestid(html, 'versand-abschnitt'), 0, 'Alt-Panel (Versand-Abschnitt) noch im Trip-Anlegen');
			assert.ok(iVersand > iTab, 'Briefing-Zeiten (Sprungziel #versand) stehen nicht im Reiter Zustellung');
			assert.equal(html.split('id="versand"').length - 1, 1, 'Sprungziel #versand nicht genau einmal');
		});
	}
});

// ─── AC-4 ────────────────────────────────────────────────────────────────────

describe('AC-4: der Versand-Bereich kommt aus genau EINER Implementierung', () => {
	test('jede_versand_testid_erscheint_genau_einmal_im_schritt_zustellung', () => {
		const html = zeitplan();
		for (const testid of ['zustellung-morgen-schalter', 'zustellung-abend-schalter', 'zustellung-morgen-zeit', 'zustellung-abend-zeit', 'zustellung-stille-schalter']) {
			assert.equal(
				countTestid(html, testid),
				1,
				`AC-4: "${testid}" steht ${countTestid(html, testid)}x im Schritt Zustellung. Zwei Treffer ` +
					'heissen zwei parallel lebende Implementierungen bzw. Mounts — zwei ' +
					'unabhaengige Schreibpfade auf dieselben report_config-Felder (Fehlerklasse ' +
					'Fix-Loop 4).'
			);
		}
		for (const testid of ['channel-email', 'channel-telegram', 'channel-sms', 'channel-premium-sms'])
			assert.equal(countTestid(html, testid), 0, `#3332 AC-1: Kanal-Schalter "${testid}" des Alt-Panels noch im Trip-Anlegen (zweiter Schreiber).`);
	});
});

// ─── AC-5 ────────────────────────────────────────────────────────────────────

describe('AC-5: genau eine Versand-Instanz im Dokument, in jeder Ansicht', () => {
	const ANSICHTEN: Array<[string, boolean, 'desktop' | 'mobil']> = [
		['breite Ansicht', false, 'desktop'],
		['schmale Ansicht', true, 'mobil']
	];

	for (const [name, isMobileViewport, erwarteterBaum] of ANSICHTEN) {
		test(`genau_eine_versand_instanz__${erwarteterBaum}`, () => {
			const html = zeitplan({ isMobileViewport });

			assert.equal(
				countTestid(html, 'zustellung-tab'),
				1,
				`AC-5 (${name}): ${countTestid(html, 'zustellung-tab')} Zustellungs-Instanzen im Dokument. ` +
					'Zwei gleichzeitig gemountete Instanzen halten je einen eigenen Stand ' +
					'und ueberschreiben sich gegenseitig (Last-Write-Wins, ohne ' +
					'Fehlermeldung); null heisst, der Versand-Bereich fehlt ganz.'
			);

			assert.equal(
				bereichVon(html, 'zustellung-tab'),
				erwarteterBaum,
				`AC-5 (${name}): Die einzige Zustellungs-Instanz steht im falschen Markup-Baum. Die ` +
					'beiden Baeume werden per CSS umgeschaltet — im falschen Baum ist der ' +
					'Versand-Bereich in dieser Ansicht unsichtbar.'
			);
		});
	}
});

// ─── AC-6 ────────────────────────────────────────────────────────────────────

describe('AC-6 (#3332 AC-10): das Mail-Format bleibt im Anlege-Flow erreichbar — in der Karte „Was steht wo“', () => {
	test('keine_mail_inhalt_karte_mehr_der_wetter_reiter_traegt_die_karte', () => {
		const html = zeitplan();
		assert.equal(
			countTestid(html, 'report-mail-content'),
			0,
			'#3332 AC-10: Die Mail-Inhalt-Karte steht noch im Trip-Anlegen — der Hub hat keine (Anlegen = Bearbeiten), ' +
				'und das E-Mail-Format haette zwei Bedienstellen.'
		);
		assert.equal(countTestid(html, 'report-email-format-switcher'), 0, '#3332 AC-10: zweite Bedienstelle des E-Mail-Formats.');
		const wetter = zeitplan({ activeTab: 'wetter' });
		assert.equal(
			countTestid(wetter, 'wetter-tab'),
			1,
			'AC-6: Der Reiter Wetter (Traeger der Karte „Was steht wo“ mit dem E-Mail-Format) fehlt im Anlege-Flow — ' +
				'ohne ihn ist das Mail-Format beim Anlegen nicht einstellbar.'
		);
	});
});

// ─── AC-7 ────────────────────────────────────────────────────────────────────

describe('AC-7: die Laufzeit-Angabe nennt das abgeleitete Enddatum', () => {
	test('laufzeit_zeigt_enddatum_aus_startdatum_und_etappenzahl', () => {
		const html = zeitplan({
			name: 'Karnischer Hoehenweg',
			startDate: '2026-09-01',
			stageNames: ['Etappe 1', 'Etappe 2', 'Etappe 3']
		});

		const text = visibleText(outerHtml(html, 'zustellung-laufzeit-satz'));
		assert.ok(
			text.includes('1.–3. September 2026'),
			'AC-7: Die Laufzeit-Zeile des Reiters Zustellung nennt nicht den erwarteten Zeitraum 1.–3. September 2026 ' +
				'(Start 01.09.2026 + 3 Etappen), sondern: "' +
				text +
				'". Fehlt das Enddatum, erreichen die Etappen den Reiter nicht datiert — `stageDate()` ' +
				'(dd.mm. ohne Jahr) ist dafuer unbrauchbar, gebraucht wird die ISO-Ableitung aus `buildCreateTripPayload`.'
		);
	});
});
