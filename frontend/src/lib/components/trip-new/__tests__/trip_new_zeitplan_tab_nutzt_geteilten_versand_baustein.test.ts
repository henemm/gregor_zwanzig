// TDD RED — Issue #1738, Struktur-Zusicherungen der Migration.
// Spec: docs/specs/modules/fix_1738_trips_new_versand_tab.md — AC-4, AC-5, AC-6, AC-7.
//
// Die Trip-Anlage soll ihren Versand-Bereich aus dem geteilten Baustein
// `shared/VersandTab.svelte` (context="route") beziehen statt aus einer zweiten
// Kanal-Implementierung (Teilungsregel CLAUDE.md, Epic #1230, #1199). Gemessen
// wird am serverseitigen Render der echten Anlege-Komponente — nicht am
// Quelltext. Renderharness + Test-Seam: ./tripNewSsr.ts.
//
// RED heute:
//   - AC-4: der Kanal-Block kommt aus EditReportConfigSection, die zweimal
//     gleichzeitig gemountet ist (TripNewEditor.svelte:800/:1036, CSS-only
//     umgeschaltet) — Testids stehen doppelt bzw. (metrik-gegated) gar nicht.
//   - AC-5: `versand-tab` existiert auf /trips/new ueberhaupt nicht.
//   - AC-6: `report-mail-content` steht doppelt im Dokument (derselbe
//     Doppel-Mount) statt genau einmal.
//   - AC-7: die Laufzeit-Anzeige gibt es nicht; `stubTrip.stages` ist zudem
//     fest leer (TripNewEditor.svelte:86-93), sodass `computeTripEnd` auch nach
//     dem Einbau kein Datum faende, wenn die Etappen nicht befuellt werden.
//
// Ausfuehrung:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/components/trip-new/__tests__/trip_new_zeitplan_tab_nutzt_geteilten_versand_baustein.test.ts

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
		activeTab: 'zeitplan',
		isMobileViewport: false,
		channels: ALLE_AN,
		...extra
	});
	assertTabOffen(html, 'zeitplan');
	return html;
}

// ─── AC-4 ────────────────────────────────────────────────────────────────────

describe('AC-4: der Kanal-Block kommt aus genau EINER Implementierung', () => {
	test('jede_kanal_testid_erscheint_genau_einmal_im_zeitplan_tab', () => {
		const html = zeitplan();
		for (const testid of [
			'channel-email',
			'channel-telegram',
			'channel-sms',
			'channel-premium-sms'
		]) {
			assert.equal(
				countTestid(html, testid),
				1,
				`AC-4: "${testid}" steht ${countTestid(html, testid)}x im Zeitplan-Tab. Zwei Treffer ` +
					'heissen zwei parallel lebende Kanal-Implementierungen bzw. Mounts — zwei ' +
					'unabhaengige Schreibpfade auf dieselben report_config-Felder (Fehlerklasse ' +
					'Fix-Loop 4).'
			);
		}
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
				countTestid(html, 'versand-tab'),
				1,
				`AC-5 (${name}): ${countTestid(html, 'versand-tab')} Versand-Instanzen im Dokument. ` +
					'Zwei gleichzeitig gemountete Instanzen halten je einen eigenen Schnappschuss von ' +
					'report_config und ueberschreiben sich gegenseitig (Last-Write-Wins, ohne ' +
					'Fehlermeldung); null heisst, der Versand-Bereich fehlt ganz.'
			);

			assert.equal(
				bereichVon(html, 'versand-tab'),
				erwarteterBaum,
				`AC-5 (${name}): Die einzige Versand-Instanz steht im falschen Markup-Baum. Die ` +
					'beiden Baeume werden per CSS umgeschaltet — im falschen Baum ist der ' +
					'Versand-Bereich in dieser Ansicht unsichtbar.'
			);
		});
	}
});

// ─── AC-6 ────────────────────────────────────────────────────────────────────

describe('AC-6: die Mail-Inhalt-Karte bleibt im Anlege-Flow erreichbar', () => {
	test('mail_inhalt_karte_steht_genau_einmal_im_zeitplan_tab', () => {
		const html = zeitplan();

		assert.equal(
			countTestid(html, 'report-mail-content'),
			1,
			`AC-6: Die Mail-Inhalt-Karte steht ${countTestid(html, 'report-mail-content')}x im ` +
				'Zeitplan-Tab. Sie darf durch die Migration weder verschwinden (im Metriken-Tab ist ' +
				'sie im createMode ausgeblendet, WeatherMetricsTab.svelte:1737) noch doppelt ' +
				'erscheinen.'
		);
		assert.equal(
			countTestid(html, 'report-email-format-switcher'),
			1,
			'AC-6: Die Format-Umschaltung full/compact fehlt (oder steht doppelt) — ohne sie ist ' +
				'das Mail-Format beim Anlegen nicht einstellbar.'
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

		const text = visibleText(outerHtml(html, 'briefings-laufzeit'));
		assert.ok(
			text.includes('03.09.2026'),
			'AC-7: Die Laufzeit-Zeile nennt nicht das erwartete Enddatum 03.09.2026 (Start ' +
				'01.09.2026 + 3 Etappen), sondern: "' +
				text +
				'". Ein "endet —" heisst, dass die Etappen den geteilten Baustein nicht datiert ' +
				'erreichen — `stageDate()` (dd.mm. ohne Jahr) ist dafuer unbrauchbar, gebraucht wird ' +
				'die ISO-Ableitung aus `buildCreateTripPayload`.'
		);
	});
});
