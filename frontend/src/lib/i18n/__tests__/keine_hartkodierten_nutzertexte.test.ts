// doc-compliance-test (Ratschentest: liest Svelte-Quelltexte als DATEN)
//
// Issue #2649 (i18n S4, Epic #2644) — Ratsche Frontend: kein Textknoten und
// kein beschriftendes Attribut (title|aria-label|placeholder|alt|label) in
// einer Svelte-Datei unter frontend/src/ ausser ueber den Katalog. Altbestand
// steht in ../hardcode_allowlist.json und darf nur schrumpfen; beide
// Richtungen sind rot (Treffer ohne Eintrag UND Eintrag ohne Treffer).
// Spec: docs/specs/modules/i18n_s4_ratsche_frontend_2649.md
//
// Startstand (Messung 2026-10-31 auf origin/main 4f386528a + RED-Commit 5ef721c15):
// 253 gescannte Svelte-Dateien, 115 mit Treffern, 1115 Trefferzeilen,
// 33 Allowlist-Eintraege. Erzeugt mit
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     src/lib/i18n/__tests__/hardcode_scan.ts --messen
//
//   cd frontend && npm test -- src/lib/i18n/__tests__/keine_hartkodierten_nutzertexte.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import {
	scanneMarkup,
	wirdGescannt,
	pruefeGegenAllowlist,
	pruefeVerzeichnis,
	scanneTs,
	scanneVerzeichnis,
	wirdGescanntTs,
	MINDEST_DATEIEN
} from './hardcode_scan.ts';

const HIER = dirname(fileURLToPath(import.meta.url));
const SRC = join(HIER, '..', '..', '..');
const FIXTURES = join(HIER, 'fixtures', 'hardcode');
const ALLOWLIST: string[] = JSON.parse(
	readFileSync(join(HIER, '..', 'hardcode_allowlist.json'), 'utf8')
);

function fixture(name: string) {
	return scanneMarkup(readFileSync(join(FIXTURES, name), 'utf8'));
}

describe('Scanner an Fixtures (AC-1, AC-2)', () => {
	test('AC-1: <button>Speichern</button> ist ein Textknoten-Treffer mit korrekter Zeile', () => {
		// Zeile 8 trotz 6 Zeilen <script> davor und <style> danach.
		assert.deepEqual(fixture('schlecht_button.svelte'), [
			{ zeile: 8, art: 'text', text: 'Speichern' }
		]);
	});

	test('AC-1: neue Komponente ausserhalb der Allowlist wird mit Datei:Zeile gemeldet', () => {
		const pfad = 'lib/components/neu_2649/NeueKomponente.svelte';
		const ergebnis = pruefeGegenAllowlist(
			[{ pfad, treffer: fixture('schlecht_button.svelte') }],
			ALLOWLIST
		);
		assert.deepEqual(ergebnis.ohneEintrag, [`${pfad}:8  "Speichern"`]);
	});

	test('AC-2: Katalog-Ausdruecke, Entities, Symbole und Kommentare sind keine Treffer', () => {
		assert.deepEqual(fixture('gut_button.svelte'), []);
		assert.deepEqual(fixture('gut_attribute.svelte'), []);
	});

	test('AC-2: statische placeholder/aria-label sind Attribut-Treffer, gemischte Werte nicht', () => {
		assert.deepEqual(fixture('schlecht_attribute.svelte'), [
			{ zeile: 7, art: 'attribut', text: 'Suche' },
			{ zeile: 8, art: 'attribut', text: 'Schließen' }
		]);
	});

	test('Zeilen bleiben bei mehrzeiligen Ausdruecken und Kommentaren erhalten', () => {
		const quelle = [
			'<!-- eins',
			'zwei -->',
			'{#each [1, 2] as n (n)}',
			'  <p>{n > 1 ? `{${n}}` : "}"}</p>',
			'{/each}',
			'<p>',
			'  Hallo   Welt',
			'</p>',
			'<Comp label="Ort" title=\'Karte\' aria-label="x" />'
		].join('\n');
		assert.deepEqual(scanneMarkup(quelle), [
			{ zeile: 7, art: 'text', text: 'Hallo Welt' },
			{ zeile: 9, art: 'attribut', text: 'Ort' },
			{ zeile: 9, art: 'attribut', text: 'Karte' }
		]);
	});
});

describe('Pfadauswahl (AC-6)', () => {
	test('__tests__/, routes/_design* und routes/email-preview-dev werden nicht gescannt', () => {
		for (const pfad of [
			'lib/i18n/__tests__/fixtures/hardcode/schlecht_button.svelte',
			'lib/components/shared/__tests__/Harness.svelte',
			'routes/_design/+page.svelte',
			'routes/_design-system/atoms/+page.svelte',
			'routes/email-preview-dev/+page.svelte'
		]) {
			assert.equal(wirdGescannt(pfad), false, pfad);
		}
	});

	test('alle uebrigen Svelte-Pfade (auch lib/components/ui/ und routes/) werden gescannt', () => {
		for (const pfad of [
			'lib/components/ui/button/button.svelte',
			'routes/+page.svelte',
			'routes/+layout.svelte',
			'routes/trips/[id]/+page.svelte',
			'lib/components/shared/VersandTab.svelte'
		]) {
			assert.equal(wirdGescannt(pfad), true, pfad);
		}
		assert.equal(wirdGescannt('lib/i18n/index.ts'), false);
	});
});

describe('Allowlist-Pruefung (AC-3)', () => {
	test('Verzeichnis-Eintrag mit / ist Praefix, Datei-Eintrag muss exakt passen', () => {
		const treffer = [{ zeile: 1, art: 'text' as const, text: 'Hallo' }];
		const ergebnisse = [
			{ pfad: 'routes/trips/+page.svelte', treffer },
			{ pfad: 'routes/tripsalt/+page.svelte', treffer },
			{ pfad: 'routes/+layout.svelte', treffer },
			{ pfad: 'routes/+page.svelte', treffer }
		];
		const ergebnis = pruefeGegenAllowlist(ergebnisse, ['routes/+layout.svelte', 'routes/trips/']);
		assert.deepEqual(ergebnis.ohneEintrag, [
			'routes/tripsalt/+page.svelte:1  "Hallo"',
			'routes/+page.svelte:1  "Hallo"'
		]);
		assert.deepEqual(ergebnis.eintraegeOhneTreffer, []);
	});

	test('Allowlist-Eintrag ohne Treffer ist rot und wird genannt', () => {
		const tot = 'lib/components/gibt_es_nicht_2649/';
		const ergebnis = pruefeVerzeichnis(SRC, [...ALLOWLIST, tot].sort());
		assert.deepEqual(ergebnis.ohneEintrag, []);
		assert.deepEqual(ergebnis.eintraegeOhneTreffer, [
			`Eintrag ohne Treffer: ${tot} – aus hardcode_allowlist.json streichen`
		]);
	});

	test('Allowlist ist sortiert, eindeutig und nicht leer', () => {
		assert.ok(ALLOWLIST.length > 0);
		assert.deepEqual([...new Set(ALLOWLIST)].sort(), ALLOWLIST);
	});

	test('echter Lauf ueber frontend/src: jeder Treffer liegt unter einem Eintrag, jeder Eintrag hat Treffer', () => {
		const ergebnis = pruefeVerzeichnis(SRC, ALLOWLIST);
		assert.deepEqual(
			ergebnis.ohneEintrag,
			[],
			'Hartkodierter Nutzertext ausserhalb der Allowlist — ueber den Katalog setzen ({$t(...)}):\n' +
				ergebnis.ohneEintrag.join('\n')
		);
		assert.deepEqual(ergebnis.eintraegeOhneTreffer, [], ergebnis.eintraegeOhneTreffer.join('\n'));
	});
});

describe('Messaufbau (AC-4)', () => {
	test(`weniger als ${MINDEST_DATEIEN} Dateien: leeres Verzeichnis bricht ab`, () => {
		const leer = mkdtempSync(join(tmpdir(), 'hardcode-scan-'));
		try {
			assert.throws(() => pruefeVerzeichnis(leer, ALLOWLIST), /Messaufbau leer/);
		} finally {
			rmSync(leer, { recursive: true, force: true });
		}
	});

	test('falsches Wurzelverzeichnis (nicht vorhanden bzw. zu klein) bricht ab', () => {
		assert.throws(() => pruefeVerzeichnis(join(SRC, 'gibt_es_nicht'), ALLOWLIST), /Messaufbau leer/);
		assert.throws(() => pruefeVerzeichnis(join(SRC, 'lib', 'i18n'), ALLOWLIST), /Messaufbau leer/);
	});

	test('Mindestzahl ist nicht abgesenkt', () => {
		assert.equal(MINDEST_DATEIEN, 150);
	});
});

// Issue #2660 (i18n F11): Erweiterung auf *.ts in lib/utils, lib/stores, lib/api.ts.
// Spec: docs/specs/modules/i18n_f11_bausteine_ts_2660.md (AC-6)
describe('TypeScript-Ratsche (F11, AC-6)', () => {
	const BEISPIEL = [
		"// Kommentar mit Umlaut: Änderung nicht gespeichert",
		"/* Block: bitte nicht melden */",
		"export const A = 'Änderung gespeichert';",
		'export const B = "bitte erneut versuchen";',
		'export const C = `Versand ${n} fehlgeschlagen: HTTP ${s}`;',
		"console.error('Fehler beim Laden fehlgeschlagen'); // i18n-log",
		"export const D = 'ok', E = 'Nicht', F = 'nichtig';",
		"const re = /[äöü]'nicht'/g;",
		"export const G = `a${'Größe'}b`;",
		"export const H = tr('fehler.versand.fehlgeschlagen');"
	].join('\n');

	test('Selbsttest an einer temporaeren Beispiel-Datei: Treffer mit Datei:Zeile, i18n-log und Kommentare ausgenommen', () => {
		const ordner = mkdtempSync(join(tmpdir(), 'hardcode-ts-'));
		try {
			const datei = join(ordner, 'beispiel.ts');
			writeFileSync(datei, BEISPIEL);
			const treffer = scanneTs(readFileSync(datei, 'utf8'));
			assert.deepEqual(
				treffer.map((t) => [t.zeile, t.text]),
				[
					[3, 'Änderung gespeichert'],
					[4, 'bitte erneut versuchen'],
					[5, 'fehlgeschlagen: HTTP'],
					[7, 'Nicht'],
					[9, 'Größe']
				]
			);
			const pfad = 'lib/utils/beispiel_2660.ts';
			const ergebnis = pruefeGegenAllowlist([{ pfad, treffer }], ALLOWLIST);
			assert.equal(ergebnis.ohneEintrag[0], `${pfad}:3  "Änderung gespeichert"`);
			assert.equal(ergebnis.ohneEintrag.length, 5);
		} finally {
			rmSync(ordner, { recursive: true, force: true });
		}
	});

	test('mit // i18n-log am Zeilenende bleibt die Zeile gruen', () => {
		assert.deepEqual(scanneTs("throw new Error('Fassung passt nicht'); // i18n-log"), []);
		assert.equal(scanneTs("throw new Error('Fassung passt nicht');").length, 1);
	});

	test('Pfadauswahl: utils, stores (auch .svelte.ts) und api.ts; keine Tests, keine .d.ts', () => {
		for (const pfad of ['lib/api.ts', 'lib/utils/sendOutcome.ts', 'lib/stores/saveStatusStore.svelte.ts', 'lib/utils/sub/x.ts']) {
			assert.equal(wirdGescanntTs(pfad), true, pfad);
		}
		for (const pfad of [
			'lib/utils/sendOutcome.test.ts',
			'lib/utils/__tests__/x.ts',
			'lib/stores/typen.d.ts',
			'lib/i18n/index.ts',
			'lib/apiHelfer.ts',
			'lib/components/shared/x.ts'
		]) {
			assert.equal(wirdGescanntTs(pfad), false, pfad);
		}
	});

	test('echter Quellbaum: TS-Dateien werden tatsaechlich gescannt (Messaufbau nicht leer)', () => {
		const ts = scanneVerzeichnis(SRC).filter((e) => e.pfad.endsWith('.ts'));
		assert.ok(ts.length >= 25, `nur ${ts.length} TS-Dateien gescannt`);
		assert.ok(ts.some((e) => e.pfad === 'lib/api.ts'));
		assert.ok(ts.some((e) => e.pfad === 'lib/stores/saveStatusStore.svelte.ts'));
	});

	// Issue #2652 (i18n F3, AC-7): die Dateien des Pakets stehen unter keinem Eintrag mehr.
	// Ausnahme bis zum Merge von F2 (#2651): routes/_home/EmptyKachel.svelte (Leerzustand gehoert F2).
	test('F3: kein Allowlist-Eintrag deckt Cockpit, Listen, ListTable oder tripHero', () => {
		const F3 = [
			'routes/+page.svelte',
			'routes/_home/HomeHero.svelte',
			'routes/_home/SubscriptionKachel.svelte',
			'routes/_home/StartklarCheckliste.svelte',
			'routes/trips/+page.svelte',
			'routes/compare/+page.svelte',
			'routes/locations/+page.svelte',
			'routes/archiv/+page.svelte',
			'lib/components/organisms/ListTable.svelte',
			'lib/utils/tripHero.ts',
			'lib/utils/schedulerTime.ts'
		];
		const deckt = (a: string, p: string) => (a.endsWith('/') ? p.startsWith(a) : p === a);
		assert.deepEqual(F3.filter((p) => ALLOWLIST.some((a) => deckt(a, p))), []);
		for (const alt of ['routes/_home/', 'routes/trips/', 'routes/compare/', 'routes/locations/', 'routes/archiv/']) {
			assert.ok(!ALLOWLIST.includes(alt), alt);
		}
	});

	// Issue #2653 (i18n F4, AC-7): Konto, Admin, Navigation und Speicher-Anzeige.
	test('F4: kein Allowlist-Eintrag deckt Konto, Admin, Sidebar/BottomNav/KontoSheet oder SaveIndicator', () => {
		const F4 = [
			'routes/account/+page.svelte',
			'routes/admin/+page.svelte',
			'lib/components/account/PremiumSmsLinkCard.svelte',
			'lib/components/ui/sidebar/Sidebar.svelte',
			'lib/components/ui/sidebar/BottomNav.svelte',
			'lib/components/ui/sidebar/KontoSheet.svelte',
			'lib/components/ui/SaveIndicator.svelte',
			'lib/admin.ts'
		];
		const deckt = (a: string, p: string) => (a.endsWith('/') ? p.startsWith(a) : p === a);
		assert.deepEqual(F4.filter((p) => ALLOWLIST.some((a) => deckt(a, p))), []);
		for (const alt of ['routes/account/', 'routes/admin/', 'lib/components/account/', 'lib/components/ui/sidebar/', 'lib/components/ui/SaveIndicator.svelte'])
			assert.ok(!ALLOWLIST.includes(alt), alt);
		const treffer = scanneVerzeichnis(SRC).filter((e) => F4.includes(e.pfad) && e.treffer.length > 0);
		assert.deepEqual(treffer.map((e) => e.pfad), []);
	});

	// Issue #2655 (i18n F6, AC-7): Versand-Reiter und Telegram-Kurzstil-Schalter.
	test('F6: kein Allowlist-Eintrag deckt den Versand-Reiter oder den Kurzstil-Schalter', () => {
		const F6 = [
			'lib/components/shared/VersandTab.svelte',
			'lib/components/shared/TelegramKurzstilToggle.svelte',
			'lib/components/shared/versand-tab/VTBriefingChannels.svelte',
			'lib/components/shared/versand-tab/VTSchedulePlan.svelte',
			'lib/components/shared/versand-tab/VTLaufzeitRoute.svelte',
			'lib/components/shared/versand-tab/VTLaufzeitVergleich.svelte',
			'lib/components/shared/versand-tab/VTNextBriefing.svelte'
		];
		const deckt = (a: string, p: string) => (a.endsWith('/') ? p.startsWith(a) : p === a);
		assert.deepEqual(F6.filter((p) => ALLOWLIST.some((a) => deckt(a, p))), []);
		for (const alt of ['lib/components/shared/', 'lib/components/shared/versand-tab/', 'lib/components/shared/TelegramKurzstilToggle.svelte'])
			assert.ok(!ALLOWLIST.includes(alt), alt);
		const treffer = scanneVerzeichnis(SRC).filter((e) => F6.includes(e.pfad) && e.treffer.length > 0);
		assert.deepEqual(treffer.map((e) => e.pfad), []);
		assert.ok(scanneVerzeichnis(SRC).filter((e) => F6.includes(e.pfad)).length === F6.length, 'Messaufbau: F6-Dateien nicht gescannt');
	});

	// F6 Adversary F002: auch die .ts-Helfer des Versand-Reiters stehen unter der TS-Ratsche.
	test('F6: .ts-Module unter shared/versand-tab/ werden gescannt und sind ohne Treffer', () => {
		const ts = scanneVerzeichnis(SRC).filter((e) => e.pfad.startsWith('lib/components/shared/versand-tab/') && e.pfad.endsWith('.ts'));
		for (const p of ['sendTargetLabel.ts', 'premiumSmsChannelState.ts', 'nextBriefingText.ts', 'channelConnectionStatus.ts', 'vtBriefingChannelsText.ts'])
			assert.ok(ts.some((e) => e.pfad === `lib/components/shared/versand-tab/${p}`), p);
		assert.deepEqual(ts.filter((e) => e.treffer.length > 0).map((e) => e.pfad), []);
		assert.equal(wirdGescanntTs('lib/components/shared/versand-tab/__tests__/f6VersandSsr.ts'), false);
		// Gegenprobe: ein zurueckgekehrtes deutsches Literal waere ein Treffer ohne Eintrag.
		const treffer = scanneTs("hint: 'Premium-SMS ab Level Premium verfügbar'");
		const ergebnis = pruefeGegenAllowlist([{ pfad: 'lib/components/shared/versand-tab/premiumSmsChannelState.ts', treffer }], ALLOWLIST);
		assert.equal(ergebnis.ohneEintrag.length, 1);
		// Signalwoerter „keine"/„nichts" (F6): Saetze ohne Umlaut werden ebenfalls erkannt.
		assert.equal(scanneTs("x('Im Konto ist keine E-Mail-Adresse hinterlegt — es kann nichts gesendet werden.')").length, 1);
		assert.equal(scanneTs("x('nichtig')").length, 0);
	});

	// Issue #2654 (i18n F5, AC-7): Wertebereiche-Reiter, Trip-Metrik-Namen, Vergleichs-Katalog-Loader.
	test('F5: kein Allowlist-Eintrag deckt den Wertebereiche-Reiter; Svelte- und .ts-Dateien ohne Treffer', () => {
		const deckt = (a: string, p: string) => (a.endsWith('/') ? p.startsWith(a) : p === a);
		const alle = scanneVerzeichnis(SRC);
		const F5 = alle
			.map((e) => e.pfad)
			.filter(
				(p) =>
					p === 'lib/components/shared/WeatherMetricsTab.svelte' ||
					p === 'lib/components/shared/StandardwerteSpeichernKnopf.svelte' ||
					p === 'lib/components/shared/corridor-editor/compareMetricCatalogLoader.ts' ||
					p === 'lib/i18n/metricLabel.ts' ||
					p.startsWith('lib/components/shared/weather-metrics-tab/') ||
					p.startsWith('lib/components/shared/trip-metrics/')
			);
		for (const p of [
			'lib/components/shared/WeatherMetricsTab.svelte',
			'lib/components/shared/weather-metrics-tab/WeatherV2Reihenfolge.svelte',
			'lib/components/shared/weather-metrics-tab/SavePresetDialog.svelte',
			'lib/components/shared/weather-metrics-tab/kuerzelLegende.ts',
			'lib/components/shared/trip-metrics/tripActiveMetricNames.ts',
			'lib/components/shared/corridor-editor/compareMetricCatalogLoader.ts',
			'lib/i18n/metricLabel.ts'
		])
			assert.ok(F5.includes(p), `Messaufbau: ${p} nicht gescannt`);
		assert.deepEqual(F5.filter((p) => ALLOWLIST.some((a) => deckt(a, p))), []);
		for (const alt of ['lib/components/shared/weather-metrics-tab/', 'lib/components/shared/trip-metrics/', 'lib/components/shared/WeatherMetricsTab.svelte', 'lib/components/shared/StandardwerteSpeichernKnopf.svelte'])
			assert.ok(!ALLOWLIST.includes(alt), alt);
		assert.deepEqual(alle.filter((e) => F5.includes(e.pfad) && e.treffer.length > 0).map((e) => `${e.pfad}: ${e.treffer.map((t) => t.text).join(' | ')}`), []);
		assert.equal(wirdGescanntTs('lib/components/shared/weather-metrics-tab/__tests__/f5Pruefstand.ts'), false);
		// Gegenprobe: ein zurueckgekehrtes deutsches Literal waere ein Treffer ohne Eintrag.
		const treffer = scanneTs("label: 'Böen (km/h)'");
		assert.equal(pruefeGegenAllowlist([{ pfad: 'lib/components/shared/weather-metrics-tab/channelMetricLayouts.ts', treffer }], ALLOWLIST).ohneEintrag.length, 1);
	});

	// Issue #2657 (i18n F8, AC-7): Layout-Reiter, Korridor-Editor, Ausgabe-Layout, Ausblick,
	// Mail-Inhalt und GPX-Seite stehen unter keinem Eintrag mehr; ihre .ts-Helfer unter der TS-Ratsche.
	test('F8: kein Allowlist-Eintrag deckt Layout-Reiter, Korridor-Editor, Ausgabe-Layout, Mail-Inhalt oder GPX-Seite', () => {
		const F8 = [
			'lib/components/shared/layout-tab/LayoutTab.svelte',
			'lib/components/shared/layout-tab/LTCapNote.svelte',
			'lib/components/shared/layout-tab/LTChannelPicker.svelte',
			'lib/components/shared/layout-tab/LTCutLine.svelte',
			'lib/components/shared/corridor-editor/CorridorEditor.svelte',
			'lib/components/shared/corridor-editor/CorridorEditorMobile.svelte',
			'lib/components/shared/OutputLayoutEditor.svelte',
			'lib/components/shared/OutlookLayoutControls.svelte',
			'lib/components/shared/MailInhaltCard.svelte',
			'routes/gpx-upload/+page.svelte'
		];
		const deckt = (a: string, p: string) => (a.endsWith('/') ? p.startsWith(a) : p === a);
		assert.deepEqual(F8.filter((p) => ALLOWLIST.some((a) => deckt(a, p))), []);
		for (const alt of ['lib/components/shared/layout-tab/', 'lib/components/shared/corridor-editor/', 'routes/gpx-upload/', 'lib/components/shared/MailInhaltCard.svelte', 'lib/components/shared/OutlookLayoutControls.svelte', 'lib/components/shared/OutputLayoutEditor.svelte'])
			assert.ok(!ALLOWLIST.includes(alt), alt);
		const alle = scanneVerzeichnis(SRC);
		assert.equal(alle.filter((e) => F8.includes(e.pfad)).length, F8.length, 'Messaufbau: F8-Dateien nicht gescannt');
		assert.deepEqual(alle.filter((e) => F8.includes(e.pfad) && e.treffer.length > 0).map((e) => e.pfad), []);
	});

	test('F8: .ts-Helfer von Layout-Reiter, Korridor-Editor und Mail-Inhalt werden gescannt und sind ohne Treffer', () => {
		const ts = scanneVerzeichnis(SRC).filter(
			(e) =>
				e.pfad.endsWith('.ts') &&
				(e.pfad.startsWith('lib/components/shared/layout-tab/') || e.pfad.startsWith('lib/components/shared/corridor-editor/') || e.pfad === 'lib/components/shared/mailInhaltKonstanten.ts' || e.pfad.startsWith('routes/gpx-upload/'))
		);
		for (const p of ['layout-tab/ltChannels.ts', 'corridor-editor/corridorEditorState.ts', 'mailInhaltKonstanten.ts'])
			assert.ok(ts.some((e) => e.pfad === `lib/components/shared/${p}`), p);
		assert.ok(ts.some((e) => e.pfad === 'routes/gpx-upload/gpxTrip.ts'), 'routes/gpx-upload/gpxTrip.ts');
		assert.deepEqual(ts.filter((e) => e.treffer.length > 0).map((e) => `${e.pfad}: ${e.treffer.map((t) => t.text).join(' | ')}`), []);
		assert.equal(wirdGescanntTs('lib/components/shared/layout-tab/__tests__/f8Pruefstand.ts'), false);
		assert.equal(wirdGescanntTs('lib/components/shared/corridor-editor/corridorEditorState.test.ts'), false);
		// Gegenprobe: ein zurueckgekehrtes deutsches Literal waere ein Treffer ohne Eintrag.
		const treffer = scanneTs("{ metric: 'wind_gust', label: 'Böen', note: 'Grat-kritisch' }");
		assert.equal(pruefeGegenAllowlist([{ pfad: 'lib/components/shared/corridor-editor/corridorEditorState.ts', treffer }], ALLOWLIST).ohneEintrag.length, 1);
	});

	// Issue #2658 (i18n F9, AC-8): Trip-Hub, Anlegen, Etappen-Editor, Vorschau-Rahmen,
	// SubscriptionHeader und BriefingHistory stehen unter keinem Eintrag mehr; ihre
	// .ts-Helfer (Aktionsliste, Reiter, Anlege-Logik, Trip-Loader) unter der TS-Ratsche.
	test('F9: kein Allowlist-Eintrag deckt Trip-Hub, Anlegen, Etappen-Editor, Vorschau-Rahmen, SubscriptionHeader, BriefingHistory', () => {
		const deckt = (a: string, p: string) => (a.endsWith('/') ? p.startsWith(a) : p === a);
		const alle = scanneVerzeichnis(SRC);
		const F9_PRAEFIXE = ['lib/components/trip-detail/', 'lib/components/trip-new/', 'lib/components/edit/', 'lib/components/email-preview/', 'lib/components/shared/subscription-header/', 'routes/trips/'];
		const F9_DATEIEN = ['lib/components/shared/BriefingHistory.svelte', 'lib/components/shared/subscriptionActions.ts', 'lib/components/shared/subscriptionTabs.ts'];
		const F9 = alle.map((e) => e.pfad).filter((p) => F9_DATEIEN.includes(p) || F9_PRAEFIXE.some((v) => p.startsWith(v)));
		for (const p of ['lib/components/trip-detail/TripHeader.svelte', 'lib/components/trip-detail/waypoints/WaypointCard.svelte', 'lib/components/trip-new/TripNewEditor.svelte', 'lib/components/trip-new/tripNewLogic.ts', 'lib/components/edit/EditStagesPanelNew.svelte', 'lib/components/email-preview/EmailPreviewHeader.svelte', 'routes/trips/[id]/+page.svelte', 'routes/trips/[id]/+page.server.ts', ...F9_DATEIEN])
			assert.ok(F9.includes(p), `Messaufbau: ${p} nicht gescannt`);
		assert.deepEqual(F9.filter((p) => ALLOWLIST.some((a) => deckt(a, p))), []);
		for (const alt of ['lib/components/trip-detail/', 'lib/components/trip-new/', 'lib/components/edit/', 'lib/components/email-preview/', 'lib/components/shared/BriefingHistory.svelte', 'lib/components/shared/subscription-header/', 'routes/trips/[id]/'])
			assert.ok(!ALLOWLIST.includes(alt), alt);
		assert.deepEqual(alle.filter((e) => F9.includes(e.pfad) && e.treffer.length > 0).map((e) => `${e.pfad}: ${e.treffer.map((t) => t.text).join(' | ')}`), []);
		// Gegenprobe: ein zurueckgekehrtes deutsches Literal waere ein Treffer ohne Eintrag.
		const treffer = scanneTs("{ id: 'delete', label: 'Löschen', danger: true }");
		assert.equal(pruefeGegenAllowlist([{ pfad: 'lib/components/shared/subscriptionActions.ts', treffer }], ALLOWLIST).ohneEintrag.length, 1);
		assert.equal(wirdGescanntTs('lib/components/trip-new/__tests__/f9x.ts'), false);
	});

	// Issue #2656 (i18n F7, AC-7): Alarme-Reiter, Alarm-Kanal-Picker und alerts-tab/ stehen
	// unter keinem Eintrag mehr; ihre .ts-Helfer (alarme-tab/, alerts-tab/, alertMetricLabels.ts)
	// unter der TS-Ratsche.
	test('F7: kein Allowlist-Eintrag deckt Alarme-Reiter, Alarm-Kanal-Picker oder alerts-tab/', () => {
		const F7 = [
			'lib/components/shared/AlarmeTab.svelte',
			'lib/components/shared/AlertChannelPicker.svelte',
			'lib/components/alerts-tab/AlertsTab.svelte',
			'lib/components/alerts-tab/AlertCard.svelte',
			'lib/components/alerts-tab/AlertPresetSelector.svelte',
			'lib/components/alerts-tab/AlertMetricLevelTable.svelte',
			'lib/components/alerts-tab/AlertMetricLevelRow.svelte',
			'lib/components/alerts-tab/AlertMetricRow.svelte',
			'lib/components/alerts-tab/AlertMetricTable.svelte',
			'lib/components/alerts-tab/AlertQuietHoursCard.svelte',
			'lib/components/alerts-tab/AlertCooldownCard.svelte',
			'lib/components/alerts-tab/AlertPreviewCard.svelte'
		];
		const deckt = (a: string, p: string) => (a.endsWith('/') ? p.startsWith(a) : p === a);
		assert.deepEqual(F7.filter((p) => ALLOWLIST.some((a) => deckt(a, p))), []);
		for (const alt of ['lib/components/alerts-tab/', 'lib/components/shared/AlarmeTab.svelte', 'lib/components/shared/AlertChannelPicker.svelte', 'lib/utils/alertMetricLabels.ts'])
			assert.ok(!ALLOWLIST.includes(alt), alt);
		const alle = scanneVerzeichnis(SRC);
		assert.equal(alle.filter((e) => F7.includes(e.pfad)).length, F7.length, 'Messaufbau: F7-Dateien nicht gescannt');
		assert.deepEqual(alle.filter((e) => F7.includes(e.pfad) && e.treffer.length > 0).map((e) => `${e.pfad}: ${e.treffer.map((t) => t.text).join(' | ')}`), []);
	});

	test('F7: .ts-Helfer von Alarme-Reiter und alerts-tab/ sowie alertMetricLabels.ts werden gescannt und sind ohne Treffer', () => {
		const ts = scanneVerzeichnis(SRC).filter(
			(e) =>
				e.pfad.endsWith('.ts') &&
				(e.pfad.startsWith('lib/components/shared/alarme-tab/') || e.pfad.startsWith('lib/components/alerts-tab/') || e.pfad === 'lib/utils/alertMetricLabels.ts')
		);
		for (const p of ['shared/alarme-tab/premiumSmsAlarmGate.ts', 'shared/alarme-tab/alertChannelState.ts', 'shared/alarme-tab/alarmeTabSections.ts', 'shared/alarme-tab/activeAlertMetricsFromCatalog.ts', 'shared/alarme-tab/alarmeDeliveryPayload.ts', 'alerts-tab/alertMetricTable.ts', 'alerts-tab/alertPreviewHelpers.ts'])
			assert.ok(ts.some((e) => e.pfad === `lib/components/${p}`), p);
		assert.ok(ts.some((e) => e.pfad === 'lib/utils/alertMetricLabels.ts'), 'lib/utils/alertMetricLabels.ts');
		assert.deepEqual(ts.filter((e) => e.treffer.length > 0).map((e) => `${e.pfad}: ${e.treffer.map((t) => t.text).join(' | ')}`), []);
		assert.equal(wirdGescanntTs('lib/components/alerts-tab/__tests__/f7Pruefstand.ts'), false);
		assert.equal(wirdGescanntTs('lib/components/alerts-tab/alertMetricTable.test.ts'), false);
		// Gegenprobe: ein zurueckgekehrtes deutsches Literal waere ein Treffer ohne Eintrag.
		const treffer = scanneTs("export const PREMIUM_SMS_ALARM_HINT_NO_TIER = 'Premium-SMS ab Level Premium verfügbar';");
		assert.equal(pruefeGegenAllowlist([{ pfad: 'lib/components/shared/alarme-tab/premiumSmsAlarmGate.ts', treffer }], ALLOWLIST).ohneEintrag.length, 1);
	});

	test('Allowlist enthaelt die acht F11-Praefixe nicht mehr', () => {
		const F11 = [
			'lib/components/ui/',
			'lib/components/molecules/',
			'lib/components/organisms/',
			'lib/components/atoms/',
			'lib/components/mobile/',
			'lib/utils/',
			'lib/stores/',
			'lib/api.ts'
		];
		assert.deepEqual(ALLOWLIST.filter((a) => F11.includes(a)), []);
	});
});
