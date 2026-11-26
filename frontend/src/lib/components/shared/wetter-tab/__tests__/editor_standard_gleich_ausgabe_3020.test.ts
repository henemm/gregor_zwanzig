// Issue #3020 R1 (G38): Editor-Standard = Ausgabe-Standard, Frontend-Seite der Katalogfälle D-*-frontend
// (fallliste_editor.json). Vor #3357 prüften sie WeatherMetricsTab.svelte; heute zeigt der Reiter Wetter die
// Menge (Grundauswahl) und die Karte „Was steht wo“ Folge und Haken je Stelle.
// Katalog: docs/specs/modules/feat_3047_einstellung_gleich_mail_pruefkatalog.md (AC-13, AC-16, AC-21).
//
// Eingaben: tests/fixtures/einstellung_gleich_mail/editor_standard.json. Je Eingabe zwei Nutzer mit derselben
// Abo-Kennung: A speichert sie roh (Altfelder `channel_layouts`/`outlook_metrics` wirken seit #3237 nicht, Karte
// und Ausgabe müssen sie GLEICH ignorieren), B als Tabelle „Was steht wo“.
// Soll: die Ausgabe desselben Abos aus Python (placementsOrakel.ts, dieselben Funktionen wie
// tests/tdd/test_einstellung_gleich_mail_editor_standard.py) — und, wo die Python-Seite sie auch einhält, die von
// Hand gesetzte Folge `erwartet`. Ist: `metrikenAus`/`stellenAus` auf der echten Antwort, `standAusAbo` des Reiters.
//
//   cd frontend && npm test -- src/lib/components/shared/wetter-tab/__tests__/editor_standard_gleich_ausgabe_3020.test.ts

import { test, describe, after } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import path from 'node:path';
import { pathToFileURL } from 'node:url';

import { FRONTEND, aufgeloestVon, fixture, live, liveVergleichsKatalog, type Json } from './wetterTabDaten.ts';
import { placementsOrakel, type OrakelFall, type OrakelStand } from './placementsOrakel.ts';
import { ebene1 } from './ausgabeOrakel.ts';
import { altSchluesselAusKatalog, eigenschaftenAusKatalog, vorlagenAusTemplates } from '../ampelModell.ts';
import { toCompareSelectionEntries } from '../../weather-metrics-tab/compareMetricSelection.ts';
import { metrikenAus, stellenAus } from '../wasStehtWoAnsicht.ts';
import { antwortMitHaken, mitHaken } from '../wasStehtWoStand.ts';
import { tripNutzlast } from '../wetterTabSpeicherung.ts';
import * as Z from '../wetterZustand.ts';
import { tr } from '../../../../i18n/index.ts';

const WURZEL = pathToFileURL(FRONTEND + '/').href;
register(pathToFileURL(path.join(FRONTEND, 'test-svelte-ssr-hooks.mjs')).href, WURZEL);
const ORGANISMEN = path.join(FRONTEND, 'src/lib/components/organisms');
register(pathToFileURL(path.join(ORGANISMEN, '__tests__/startzustandHook.mjs')).href, WURZEL);
const { render } = await import('svelte/server');
const { locale } = await import(pathToFileURL(path.join(FRONTEND, 'src/lib/i18n/index.ts')).href);
after(() => locale.set('de'));

type Liste = 'trip_tabellen' | 'trip_ausblick' | 'orte_vergleichstabelle';
type Zustand = { id: string; eingabe: { display_config: Json }; erwartet: string[] };
const LISTEN = fixture('einstellung_gleich_mail/editor_standard.json').listen as Record<string, { zustaende: Zustand[] }> & Json;
const zustand = (liste: Liste, id: string): Zustand => LISTEN[liste].zustaende.find((z: Zustand) => z.id === id)!;
const gespeicherte = (liste: Liste): Zustand[] => LISTEN[liste].zustaende.filter((z: Zustand) => z.id.startsWith('gespeichert'));

const KIND: Record<Liste, 'route' | 'vergleich'> = { trip_tabellen: 'route', trip_ausblick: 'route', orte_vergleichstabelle: 'vergleich' };
const STELLE: Record<Liste, 'email' | 'outlook'> = { trip_tabellen: 'email', trip_ausblick: 'outlook', orte_vergleichstabelle: 'email' };
const NUTZER = { roh: 'editor-std-a', tabelle: 'editor-std-b' } as const;
type Weg = keyof typeof NUTZER;

const LIVE = live();
const VORLAGEN = vorlagenAusTemplates(LIVE.templates);
const EIG = eigenschaftenAusKatalog(LIVE.metrics);
const ALT = altSchluesselAusKatalog(toCompareSelectionEntries(liveVergleichsKatalog()));
const menge = (a: string[]) => [...new Set(a)].sort();

// ── EIN Python-Lauf für alle Eingaben (zwei Nutzer, gleiche Kennung) ───────────────────────────
const schluessel = (liste: Liste, id: string, weg: Weg) => `${liste}/${id}/${weg}`;
const FAELLE: { key: string; fall: OrakelFall }[] = [];
for (const liste of Object.keys(KIND) as Liste[])
	for (const z of LISTEN[liste].zustaende as Zustand[])
		for (const weg of ['roh', 'tabelle'] as Weg[])
			FAELLE.push({
				key: schluessel(liste, z.id, weg),
				fall: { id: `${liste}-${z.id}`.replaceAll('_', '-'), nutzer: NUTZER[weg], kind: KIND[liste], abo: z.eingabe, alsTabelle: weg === 'tabelle' }
			});
const AUS: Record<string, OrakelStand> = Object.fromEntries(placementsOrakel(FAELLE.map((f) => f.fall)).map((s, i) => [FAELLE[i].key, s]));
const aus = (liste: Liste, id: string, weg: Weg) => AUS[schluessel(liste, id, weg)];

/** Was die Karte an einer Stelle in welcher Folge zeigt (Haken an; „keine eigene Spalte“ gehört zur Ausgabe). */
function karteFolge(antwort: Json, stelle: 'email' | 'outlook'): string[] {
	const spalten = stellenAus(antwort, { kurzstil: false, stundenverlaufAn: true, ausblickAn: true }, tr as never).map((s) => s.id);
	assert.ok(spalten.includes(stelle), `Messaufbau: die Karte hat keine Spalte ${stelle}`);
	const roh = new Map<string, Json>(antwort.rows.map((r: Json) => [r.metric_id, r]));
	return metrikenAus(antwort, tr as never)
		.filter((m) => m.zellen[stelle].zustand === 'on' || roh.get(m.id).cells[stelle].reason === 'keine_eigene_spalte')
		.map((m) => m.id);
}
/** Ausgabe im Vokabular der Karte: Orte-Zeilen (Tief/Hoch je Größe) auf die Katalog-Kennung. */
function ausgabeFolge(liste: Liste, s: OrakelStand): string[] {
	if (liste === 'trip_ausblick') return s.ausblick;
	if (liste === 'trip_tabellen') return s.mail;
	return [...new Set(s.mail.map((k) => ALT[k]?.metric_id ?? k))];
}
const imKartenVokabular = (liste: Liste, folge: string[]) => (KIND[liste] === 'route' ? folge : [...new Set(folge.map((k) => ALT[k]?.metric_id ?? k))]);

/** Der Reiter Wetter: Menge der Grundauswahl aus dem gespeicherten Abo. */
function reiterMenge(liste: Liste, abo: Json): string[] {
	return Z.standAusAbo(KIND[liste], abo, aufgeloestVon(abo), KIND[liste] === 'vergleich' ? ALT : {}, { eig: EIG }).auswahl;
}

/** Befund B9 (r1-g-belege.md): `display_config` NUR mit `placements` liest der Python-Kern als „kein display_config“
 *  (Profil-Vorgabe, loader `_nur_placements`), der Reiter Wetter zeigt den Register-Standard. Kein Katalogfall; bis
 *  zur Klärung ohne Reiter-Vergleich, Karte = Ausgabe bleibt geprüft. */
const BEFUND_B9 = schluessel('trip_tabellen', 'altbestand_ohne_metrics', 'tabelle');

/** `erwartet` gilt für diesen Weg auch auf der Python-Seite (sonst nur Karte = Ausgabe). */
function pruefe(liste: Liste, id: string, erwartetGilt: Weg | null): void {
	for (const weg of ['roh', 'tabelle'] as Weg[]) {
		const s = aus(liste, id, weg);
		const karte = karteFolge(s.antwort, STELLE[liste]);
		assert.deepEqual(karte, ausgabeFolge(liste, s), `${id} (${weg}): Karte zeigt an ${STELLE[liste]} eine andere Folge als die Ausgabe`);
		if (schluessel(liste, id, weg) !== BEFUND_B9)
			assert.deepEqual(menge(reiterMenge(liste, s.abo)), menge(s.antwort.rows.map((r: Json) => r.metric_id)), `${id} (${weg}): Reiter Wetter zeigt eine andere Menge als die Karte`);
		if (weg === erwartetGilt) assert.deepEqual(karte, imKartenVokabular(liste, zustand(liste, id).erwartet), `${id} (${weg}): andere Folge als editor_standard.json`);
	}
}

describe('#3020 G38: Editor-Standard = Ausgabe (Frontend-Seite)', () => {
	test('frontend_seite_trip_tabellen_standard', () => pruefe('trip_tabellen', 'nie_eingestellt', 'roh'));
	test('frontend_seite_trip_tabellen_altbestand', () => pruefe('trip_tabellen', 'altbestand_ohne_metrics', 'roh'));
	// #3047 H5 (#1394): leere Liste = Altbestand (Fall A); alle enabled:false = bewusst leer (Fall B)
	test('frontend_seite_trip_tabellen_leere_liste_altbestand', () => pruefe('trip_tabellen', 'altbestand_leere_liste', 'roh'));
	test('frontend_seite_trip_tabellen_bewusst_leer_alle_aus', () => pruefe('trip_tabellen', 'bewusst_leer_alle_aus', 'roh'));
	for (const z of gespeicherte('trip_tabellen'))
		test(`frontend_seite_trip_tabellen_gespeichert ${z.id}`, () => {
			const roh = aus('trip_tabellen', z.id, 'roh');
			// Altfelder: gespeichert, aber ohne Wirkung — die Karte zeigt wie die Ausgabe die Grundauswahl.
			assert.ok('channel_layouts' in roh.abo.display_config, 'Messaufbau: Eingabe ohne Altfeld');
			assert.equal(roh.antwort.stored, false);
			pruefe('trip_tabellen', z.id, z.id.startsWith('gespeichert_folge') ? 'tabelle' : z.id === 'gespeichert_totalschnitt' ? 'roh' : null);
		});

	test('frontend_seite_trip_ausblick_standard', () => pruefe('trip_ausblick', 'nie_eingestellt', 'roh'));
	for (const z of gespeicherte('trip_ausblick'))
		test(`frontend_seite_trip_ausblick_gespeichert ${z.id}`, () => {
			assert.ok('outlook_metrics' in aus('trip_ausblick', z.id, 'roh').abo.display_config, 'Messaufbau: Eingabe ohne Altfeld');
			pruefe('trip_ausblick', z.id, z.id === 'gespeichert_totalschnitt' ? 'roh' : 'tabelle');
		});
	test('frontend_seite_trip_ausblick_bewusst_leer_alle_aus', () => pruefe('trip_ausblick', 'bewusst_leer_alle_aus', 'roh'));
	test('frontend_seite_trip_ausblick_grundauswahl_ohne_ausblick', () => {
		pruefe('trip_ausblick', 'grundauswahl_ohne_ausblick', 'roh');
		// Nicht vakuum: die Zeile steht in der Karte, nur die Stelle Ausblick ist gesperrt.
		assert.ok(aus('trip_ausblick', 'grundauswahl_ohne_ausblick', 'roh').antwort.rows.length > 0);
	});

	test('frontend_seite_orte_vergleichstabelle_standard', () => pruefe('orte_vergleichstabelle', 'nie_eingestellt', 'roh'));
	test('frontend_seite_orte_vergleichstabelle_grundauswahl_bewusst_leer', () => pruefe('orte_vergleichstabelle', 'grundauswahl_bewusst_leer', 'roh'));
	for (const z of gespeicherte('orte_vergleichstabelle'))
		test(`frontend_seite_orte_vergleichstabelle_gespeichert ${z.id}`, () => pruefe('orte_vergleichstabelle', z.id, 'tabelle'));
});

// ── AC-16: Vorlage anwenden behält die Vorlagen-Folge ─────────────────────────────────────────
describe('#3047 AC-16 Vorlage anwenden (Reiter Wetter und Karte)', () => {
	test('frontend_seite_trip_vorlage_reihenfolge', () => {
		const v = LISTEN.trip_vorlage as { vorlage: { id: string; metrics: string[] }; erwartet: string[] };
		const vorlagen = {
			...VORLAGEN,
			[v.vorlage.id]: { template: v.vorlage.id, metrics: Object.fromEntries(v.vorlage.metrics.map((id) => [id, { enabled: true, alarm_ab: 'never', lower: {}, upper: {} }])) }
		} as typeof VORLAGEN;
		// Trip ohne eigene Metrik-Liste: gespeicherte Folge, Karte und Mail = Vorlagen-Folge. (Trip MIT eigener Liste:
		// bestehende Einträge behalten ihre Folge, #2794 AC-37 — Widerspruch zu #3047 AC-16, siehe r1-g-belege.md.)
		const abo = { id: 'vorlage-folge', display_config: {} as Json };
		const s = Z.mitVorlage(Z.standAusAbo('route', abo, aufgeloestVon(abo), {}, { eig: EIG }), v.vorlage.id, vorlagen, 'route', {});
		const nurVorlage = (folge: string[]) => folge.filter((id) => v.vorlage.metrics.includes(id));
		assert.deepEqual(nurVorlage(s.auswahl), v.erwartet, 'Stand des Reiters nach „Vorlage übernehmen“');
		const n = tripNutzlast({ client: null as never, stand: () => s, vorlagen: () => vorlagen, abo: () => abo as never });
		const gespeichert = { display_config: ebene1(abo.display_config, n.weatherConfig as Record<string, unknown>) };
		const folge = (gespeichert.display_config.metrics as Json[]).filter((m) => m.enabled).sort((a, b) => a.order - b.order).map((m) => m.metric_id);
		assert.deepEqual(nurVorlage(folge), v.erwartet, 'gespeicherte Folge');
		const [o] = placementsOrakel([{ id: abo.id, nutzer: NUTZER.roh, kind: 'route', abo: gespeichert }]);
		assert.deepEqual(nurVorlage(o.mail), v.erwartet, 'Mail');
		assert.deepEqual(karteFolge(o.antwort, 'email'), o.mail, 'Karte = Mail');
	});
});

// ── N1 Totalschnitt: „Aus“ wirkt auf dem angezeigten Stand ────────────────────────────────────
describe('#3047 N1 Totalschnitt: „Aus“ in der Karte wirkt auf die angezeigte Liste', () => {
	function ausWirkt(liste: 'trip_tabellen' | 'orte_vergleichstabelle', id: string, metrik: string): void {
		const start = aus(liste, id, 'roh');
		const angezeigt = karteFolge(start.antwort, 'email');
		assert.deepEqual(angezeigt, imKartenVokabular(liste, zustand(liste, id).erwartet), 'Messaufbau: die Karte zeigt die volle Grundauswahl');
		const anzeige = start.antwort.rows.map((r: Json) => r.metric_id);
		const soll = angezeigt.filter((m) => m !== metrik);
		assert.deepEqual(karteFolge(antwortMitHaken(start.antwort, metrik, 'email', false), 'email'), soll, 'Sofortanzeige');
		const placements = mitHaken(start.antwort.placements, anzeige, metrik, 'email', false);
		const gespeichert = { ...start.abo, display_config: { ...start.abo.display_config, placements } };
		const [danach] = placementsOrakel([{ id: start.abo.id, nutzer: NUTZER.roh, kind: KIND[liste], abo: gespeichert }]);
		assert.equal(danach.antwort.stored, true);
		assert.deepEqual(karteFolge(danach.antwort, 'email'), soll, 'Karte nach dem Speichern');
		assert.deepEqual(ausgabeFolge(liste, danach), soll, 'Ausgabe nach dem Speichern');
	}
	test('frontend_seite_trip_kanal_totalschnitt_aus_wirkt', () => ausWirkt('trip_tabellen', 'gespeichert_totalschnitt', 'gust'));
	test('frontend_seite_orte_kanal_totalschnitt_aus_wirkt', () => ausWirkt('orte_vergleichstabelle', 'gespeichert_kanal_totalschnitt', 'wind'));
});

// ── N2: Leertext bei bewusst leerer Grundauswahl (Karte, DE und EN) ───────────────────────────
describe('#3047 N2 Leertext bei leerer Grundauswahl (Karte)', () => {
	const DATEI = path.join(ORGANISMEN, 'wetter-tab/WasStehtWoKarte.svelte');
	const START = [
		['let antwort = $state<PlacementsAntwort | null>(null);', 'let antwort = $state<PlacementsAntwort | null>(globalThis.__esAntwort);'],
		["let phase = $state<'laedt' | 'fehler' | 'bereit'>('laedt');", "let phase = $state<'laedt' | 'fehler' | 'bereit'>('bereit');"]
	];
	async function leertext(liste: Liste, id: string, sprache: 'de' | 'en'): Promise<string | null> {
		const K = (await import(pathToFileURL(DATEI).href + `?start=${encodeURIComponent(JSON.stringify(START))}`)).default;
		(globalThis as Json).__esAntwort = aus(liste, id, 'roh').antwort;
		locale.set(sprache);
		try {
			const html: string = render(K, { props: { context: KIND[liste], id: 'x' } }).body;
			const m = /data-testid="was-steht-wo-leer"[^>]*>([\s\S]*?)<\/p>/.exec(html);
			assert.equal(html.includes('data-slot="einstell-tabelle"'), !m, 'entweder Leertext oder Tabelle');
			return m ? m[1].replace(/<[^>]+>/g, '').trim() : null;
		} finally {
			locale.set('de');
		}
	}
	const DE = 'Im Briefing steht keine Metrik. Nimm oben unter „Nicht im Briefing“ Metriken dazu.';
	const EN = 'The briefing contains no metrics. Add metrics above under “Not in the briefing”.';
	test('frontend_seite_hinweis_grundauswahl_leer_trip', async () => {
		assert.equal(await leertext('trip_tabellen', 'bewusst_leer_alle_aus', 'de'), DE);
		assert.equal(await leertext('trip_tabellen', 'bewusst_leer_alle_aus', 'en'), EN);
		assert.deepEqual(reiterMenge('trip_tabellen', zustand('trip_tabellen', 'bewusst_leer_alle_aus').eingabe), [], 'Reiter Wetter zeigt dieselbe leere Auswahl');
		assert.equal(await leertext('trip_tabellen', 'nie_eingestellt', 'de'), null);
		assert.equal(await leertext('trip_tabellen', 'altbestand_leere_liste', 'de'), null, 'metrics: [] ist Altbestand, nicht leer');
	});
	test('frontend_seite_hinweis_grundauswahl_leer_orte', async () => {
		assert.equal(await leertext('orte_vergleichstabelle', 'grundauswahl_bewusst_leer', 'de'), DE);
		assert.equal(await leertext('orte_vergleichstabelle', 'grundauswahl_bewusst_leer', 'en'), EN);
		assert.deepEqual(reiterMenge('orte_vergleichstabelle', zustand('orte_vergleichstabelle', 'grundauswahl_bewusst_leer').eingabe), []);
		assert.equal(await leertext('orte_vergleichstabelle', 'nie_eingestellt', 'de'), null, 'nie eingestellt ist nicht leer');
		assert.equal(await leertext('orte_vergleichstabelle', 'gespeichert_folge', 'de'), null);
	});
});
