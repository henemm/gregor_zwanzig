// Issue #2658 (i18n F9, Epic #2644) — AC-1, AC-2, AC-4, AC-5, AC-6, AC-7: der
// Trip-Hub (Kopf, Status, Uebersicht, Etappen, Wegpunkte, Ausgabe-Layout-Bausteine,
// Vorschau-Rahmen, Seite /trips/[id]) und die geteilten Bausteine sprechen die
// Sprache des angemeldeten Nutzers. Echte SSR-Renders (svelte/server, Pruefstand
// f9Pruefstand.ts):
//   * AC-6: Deutsch ist byte-gleich zur Ausgabe VOR der Umstellung
//     (tests/golden/f9_trip_flaechen/*.de.html und funktionen.de.txt),
//   * AC-1: Reiter, Aktionen und Kopf englisch, Etappen-Daten `Wed 1 Jul`,
//     Trip- und Etappen-Namen unveraendert,
//   * AC-2: Aktionsliste Trip == Ortsvergleich je Aktion, aus `aktionen.*`,
//   * AC-4: Metrik-Namen ueber metricLabel (label_en bzw. deutsch), col_label bleibt,
//   * AC-5: zwei Nutzer (en/de) durch den ECHTEN Layout- und Trip-Loader;
//     ersetzt ist nur die Netzgrenze (fetch je Sitzungs-Cookie),
//   * AC-7: Status-Namen je Sprache.
// Jeder en-Fall rendert zuerst de und schaltet dann OHNE Neuladen auf en.
// Englische und deutsche Texte sind als feste Literale verankert (f9KatalogAnker.ts).
// Spec: docs/specs/modules/i18n_f9_trip_flaechen_2658.md
//
//   cd frontend && npm test -- src/lib/components/trip-detail/__tests__/trip_hub_sprache.test.ts

import { test, describe, before, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';
import path from 'node:path';
import { register } from 'node:module';
import * as P from './f9Pruefstand.ts';
import { F9_ANKER } from './f9KatalogAnker.ts';

const { locale, trFor } = P;
const base = pathToFileURL(P.FRONTEND + '/').href;
register(pathToFileURL(path.join(P.FRONTEND, 'src/routes/admin/__tests__/server-load-resolve.hooks.mjs')).href, base);
const layoutLoad = (await import(pathToFileURL(path.join(P.FRONTEND, 'src/routes/+layout.server.ts')).href)).load;
const tripLoad = (await import(pathToFileURL(path.join(P.FRONTEND, 'src/routes/trips/[id]/+page.server.ts')).href)).load;
const { baueTripSpeicherung } = await import(pathToFileURL(path.join(P.KOMP, 'shared/tripSpeicherung.ts')).href);

before(() => {
	// Die de-Golden sind der Ist-Stand VOR der Umstellung und werden nie neu geschrieben;
	// nur die en-Ansicht (Review-Hilfe, nicht verglichen) wird aktualisiert.
	if (process.env.GZ_GOLDEN_SCHREIBEN === 'en') P.schreibeGolden('en');
});
afterEach(() => locale.set('de'));

// Einzige Normalisierung: jede Leerraumfolge wird EIN Leerzeichen. Sonst byte-gleich.
const leerraum = (s: string) => s.replace(/\s+/g, ' ');
export const sichtbar = (html: string) =>
	leerraum(html.replace(/<style[\s\S]*?<\/style>/g, ' ').replace(/<(?:"[^"]*"|'[^']*'|[^'">])*>/g, ' ').replace(/&amp;/g, '&')).trim();
const hat = (text: string, teil: string) => assert.ok(text.includes(teil), `fehlt: „${teil}"\nin: ${text.slice(0, 2500)}`);
const hatNicht = (text: string, teil: string) => assert.ok(!text.includes(teil), `steht noch: „${teil}"`);

/** Erst de rendern, dann OHNE Neuladen auf en schalten. */
export function deDannEn<T>(f: () => T): { de: T; en: T } {
	locale.set('de');
	const de = f();
	locale.set('en');
	const en = f();
	return { de, en };
}

/** Deutsche Festteile (>= 5 Buchstaben) der Paket-Anker, die im englischen Text stehen. */
export function deutscheReste(text: string, ausnahmen: string[] = []): string[] {
	const reste: string[] = [];
	for (const [k, de, en] of F9_ANKER) {
		if (de === en || ausnahmen.some((a) => k === a || (a.endsWith('.') && k.startsWith(a)))) continue;
		const enTeile = new Set(en.split(/<[a-z0-9_]+>/).map((s) => s.trim()));
		for (const teil of de.split(/<[a-z0-9_]+>/).map((s) => s.trim())) {
			if ((teil.match(/[A-Za-zÄÖÜäöüß]/g) ?? []).length < 5 || enTeile.has(teil)) continue;
			// Als eigenes Wort (Pause ≠ Paused): kein Buchstabe direkt davor oder danach.
			const esc = teil.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
			if (new RegExp(`(?<![A-Za-zÄÖÜäöüß])${esc}(?![A-Za-zÄÖÜäöüß])`).test(text)) reste.push(`${k}: ${teil}`);
		}
	}
	return reste;
}
/**
 * Woerter, die im englischen Render als DATEN stehen (nicht als Paket-Text):
 * Trip-/Etappen-/Wegpunkt-Namen der Fixture, API-Metriknamen ohne label_en (F5),
 * und Bausteine anderer Pakete (Uebersicht-Kennzahlen F10, Versand F6 …).
 */
/** Geteilte Uebersicht-Kennzahlen (shared/hub-uebersicht/, Paket F10, noch in der Allowlist):
 *  „Bearbeiten →", „Morgen 07:00 · Abend 18:00", Status „Aktiv" stehen dort selbst deutsch. */
const FREMD_F10 = ['aktionen.edit', 'aktionen.historie.morgen', 'aktionen.historie.abend', 'trip.status.active'];
const DATEN = ['trip.wegpunkt.typ.', 'trip.etappe', 'trip.anlegen.name_beispiel', 'trip.anlegen.region_beispiel', 'trip.anlegen.etappe_beispiel'];

describe('AC-6: Deutsch byte-gleich zum Ist-Stand vor der Umstellung (Golden golden-de)', () => {
	const FAELLE = P.htmlFaelle();
	for (const fall of Object.keys(FAELLE)) {
		test(`${fall}.de.html`, () => {
			const golden = readFileSync(path.join(P.GOLDEN_DIR, `${fall}.de.html`), 'utf-8');
			const { de } = deDannEn(() => FAELLE[fall]());
			locale.set('de');
			assert.equal(leerraum(FAELLE[fall]() + '\n'), leerraum(golden));
			assert.equal(leerraum(de + '\n'), leerraum(golden));
		});
	}
	test('funktionen.de.txt: Aktionsliste, Reiter, Anlege-Kette, Etappen-Datum unveraendert (byte-gleich)', () => {
		const golden = readFileSync(path.join(P.GOLDEN_DIR, 'funktionen.de.txt'), 'utf-8');
		locale.set('en');
		P.funktionsTabelle();
		locale.set('de');
		assert.equal(P.funktionsTabelle() + '\n', golden);
	});
	test('Messaufbau: Golden enthaelt die deutschen Texte der Bausteine', () => {
		const alle = Object.keys(FAELLE).map((f) => readFileSync(path.join(P.GOLDEN_DIR, `${f}.de.html`), 'utf-8')).join('');
		for (const s of ['Tag 2', 'START IN', 'Briefing gesendet!', 'Weitere Aktionen', '1 Größe unbekannt', '2 Größen unbekannt', 'Lückenlos neu datiert', 'Neue Trip anlegen', 'Gesperrt — erst Trip-Name + Startdatum', 'Fertig', 'Archiviert', 'Versand-Historie', 'von Hand', '✂ ab hier bei', '▾ Aufklappen', 'Speichern fehlgeschlagen', 'Gespeichert ✓', 'Karte &amp; Höhenprofil', 'Fehler beim Senden', 'Name bearbeiten', 'Tour-Detail', 'Trip-Start', '01.07.'])
			assert.ok(alle.includes(s), s);
	});
});

describe('AC-1: Trip-Hub englisch, Namen unveraendert', () => {
	test('Reiterleiste und Seite: Reiter, Aktionen, Kopf, Erfolg/Fehler englisch (erst de, dann ohne Neuladen en)', () => {
		const { de, en } = deDannEn(() => P.reiterRendern() + P.seiteRendern('gesendet') + P.seiteRendern('fehler'));
		for (const s of ['Übersicht', 'Etappen &amp; Wegpunkte', 'Wetter-Metriken', 'Wertebereiche', 'Alarme', 'Briefing gesendet!', 'aria-label="Weitere Aktionen"']) hat(de, s);
		for (const s of ['data-testid="trip-detail-tab-uebersicht">Overview', 'data-testid="trip-detail-tab-etappen">Stages &amp; waypoints', 'data-testid="trip-detail-tab-wetter-metriken">Weather metrics', 'data-testid="trip-detail-tab-wertebereiche">Target ranges', 'data-testid="trip-detail-tab-alarme">Alerts', 'Briefing sent', 'Send', 'aria-label="More actions"', 'aria-label="Trip details"', 'Error while sending', 'aria-label="Edit name"', 'aria-label="Edit region"'])
			hat(en, s);
		hatNicht(en, 'Briefing gesendet');
		const sEn = sichtbar(en);
		hat(sEn, 'GR20 Nord 2026');
		hat(sEn, 'Calenzana – Ortu di u Piobbu');
		hat(sEn, 'Trips');
		// Der Fehler-Zustand der Seite traegt einen Server-Detailtext (Daten), s. f9Pruefstand.
		assert.deepEqual(deutscheReste(sEn, [...DATEN, ...FREMD_F10, 'aktionen.fehler.allgemein']), []);
	});

	test('Kopf: Tag/ETAPPE/START IN, Zahlenformat en-GB, Aktivitaeten englisch', () => {
		const { de, en } = deDannEn(() => sichtbar(P.kopfRendern()));
		for (const s of ['Tag 2', 'ETAPPE 2/3', 'START IN 70 Tg', '↑1.527 m', 'Skitour', 'Hochtour']) hat(de, s);
		for (const s of ['Day 2', 'STAGE 2/3', 'BRIEFING 07:00', 'DAY Day 2', 'STARTS IN 70 d', '↑1,527 m', 'Ski touring', 'Mountaineering', 'Via ferrata', 'Bike (15 km/h)', 'Rename', 'Cancel', 'Save']) hat(en, s);
		hatNicht(en, 'Tg');
		hatNicht(en, '1.527');
		// Fixture-Trip „Entwurf Dolomiten" (Name = Daten).
		assert.deepEqual(deutscheReste(en, [...DATEN, 'trip.status.draft']), []);
	});

	test('Etappen: Datum `Wed 1 Jul` (de unveraendert `01.07.`), Kennzahlen und Risiko englisch, Etappen-Namen gleich', () => {
		const { de, en } = deDannEn(() => sichtbar(P.etappenRendern()));
		hat(de, '01.07.');
		hat(de, 'Distanz');
		for (const s of ['Wed 1 Jul', 'Thu 2 Jul', 'Distance', 'Ascent', 'Descent', 'Waypoints', 'Medium', 'Low', 'High', 'Wind 34 km/h', 'No stages planned', 'Calenzana – Ortu di u Piobbu', 'Ortu – Carrozzu', '1350 m']) hat(en, s);
		hatNicht(en, '01.07.');
		hatNicht(en, ' Hm');
		assert.deepEqual(deutscheReste(en, DATEN), []);
	});

	test('Uebersicht: Karten, Spruenge, Plural der unbekannten Groessen exakt', () => {
		const { de, en } = deDannEn(() => sichtbar(P.uebersichtRendern()));
		hat(de, '· 1 Größe unbekannt');
		hat(de, '· 2 Größen unbekannt');
		for (const s of ['Order & profile', 'Open in editor →', 'Weather metrics could not be loaded.', 'Not set yet — the standard set applies.', 'No weather metrics selected — the briefing contains no weather table.', '· 1 metric unknown', '· 2 metrics unknown', 'Edit weather metrics →', 'Briefings running', 'Morning briefing', 'Evening briefing', 'Alert trigger', 'on Δ', 'Edit schedule →'])
			hat(en, s);
		assert.deepEqual(deutscheReste(en, DATEN), []);
	});

	test('Wegpunkt-Editor-Bausteine englisch (Streifen, Karten, Pausentag, Profil)', () => {
		const { en } = deDannEn(() => P.wegpunkteRendern());
		const s = sichtbar(en);
		for (const t of ['+ Rest day', 'STAGES · DRAG TO SORT · + REST DAY BETWEEN', '2 GPX · 1 rest day', '+ Stage', 'Rest day', '⌂ Rest day · Carrozzu', 'Hut', 'Waypoint', 'Rename', 'Move', 'Delete', 'Location: Ortu di u Piobbu', 'Next: Bocca Piccaia', 'No location set', 'Save']) hat(s, t);
		for (const t of ['aria-label="Remove stage"', 'aria-label="Rename waypoint"', 'aria-label="Move waypoint"', 'aria-label="Delete waypoint"', 'aria-label="Elevation profile with 2 waypoints"', 'aria-label="Elevation profile with 1 waypoint"', 'aria-label="Waypoint Calenzana"', 'aria-label="Waypoint 3"']) hat(en, t);
		// WaypointsPanel traegt im Golden-Zustand einen Server-Fehlertext (Daten), s. f9Pruefstand.
		assert.deepEqual(deutscheReste(s, [...DATEN, 'aktionen.speichern', 'aktionen.speichern_fehlgeschlagen']), []);
	});

	test('Geteilte Bausteine: Versand-Historie (Morgen/Abend, von Hand, Leer/Laden/Fehler) und Vorschau-Rahmen', () => {
		const { de, en } = deDannEn(() => sichtbar(P.historieRendern() + P.editFelderRendern()));
		hat(de, '01.07.2026 07:00');
		for (const s of ['Delivery history', 'Morning', 'Evening', '· sent manually', 'Wed 1 Jul 2026 07:00', 'No briefings delivered yet.', 'Loading delivery history…', 'Delivery history could not be loaded.', 'alert', 'Morning briefing · 01.07.2026', 'Evening briefing', 'Distance', 'Ascent', 'Descent', 'Max elevation', 'Segments'])
			hat(en, s);
		// Preset-Name „Wandern" der Fixture (Daten).
		assert.deepEqual(deutscheReste(en, [...DATEN, 'trip.aktivitaet.wandern']), []);
	});

	test('Fehler ohne Server-Text: Flag/Schluessel wird beim Rendern aufgeloest (nicht eingefroren)', () => {
		const { de, en } = deDannEn(() => sichtbar(P.fehlerFlagsRendern()));
		for (const s of ['Speichern fehlgeschlagen', 'Fehler beim Speichern', 'Versand-Historie konnte nicht geladen werden.', 'Aktion fehlgeschlagen, bitte später erneut versuchen.', 'Fehler beim Senden']) hat(de, s);
		for (const s of ['Saving failed', 'Error while saving', 'Delivery history could not be loaded.', 'Action failed, please try again later.', 'Error while sending']) hat(en, s);
		for (const s of ['Speichern fehlgeschlagen', 'Fehler beim Speichern', 'Aktion fehlgeschlagen']) hatNicht(en, s);
		// Wirkort je Baustein: die Meldung steht am Feld des Kopfes (nicht nur irgendwo im Render).
		const kopf = deDannEn(() => P.fehlerFlagsRendern().split('\n')[0]);
		assert.match(kopf.de, /data-testid="trip-name-save-error"[^>]*>Speichern fehlgeschlagen</);
		assert.match(kopf.en, /data-testid="trip-name-save-error"[^>]*>Saving failed</);
	});

	test('Aktionsfehler der Seite: 5xx/4xx ohne Detail/Netz → Schluessel, 4xx mit Detail → Server-Text (echte Funktion)', async () => {
		const { umgebungFuer } = await import(pathToFileURL(path.join(P.KOMP, 'shared/__tests__/svelteInstanzPruefstand.ts')).href);
		const { SubscriptionExecError } = await import(pathToFileURL(path.join(P.KOMP, 'shared/subscriptionExec.ts')).href);
		const seite = path.join(P.FRONTEND, 'src/routes/trips/[id]/+page.svelte');
		const { u } = await umgebungFuer(seite, { data: { trip: P.tripLaufend() } }, { jsAlsTs: true });
		const fall = (e: unknown) => {
			u.setzeAktionsFehler(e);
			return [u.errorKey, u.errorMsg];
		};
		const still = console.error;
		console.error = () => {};
		try {
			assert.deepEqual(fall(new SubscriptionExecError('x', 503, 'kaputt')), ['aktionen.fehler.server', null]);
			assert.deepEqual(fall(new SubscriptionExecError('x', 409)), ['aktionen.fehler.allgemein', null]);
			assert.deepEqual(fall(new SubscriptionExecError('x', 409, 'Trip ist archiviert')), [null, 'Trip ist archiviert']);
			assert.deepEqual(fall(new Error('offline')), ['aktionen.fehler.verbindung', null]);
		} finally {
			console.error = still;
		}
	});
});

describe('AC-2: Aktionsliste Trip == Ortsvergleich, Texte aus aktionen.*', () => {
	const SCHLUESSEL: Record<string, string> = {
		pause: 'aktionen.pause', resume: 'aktionen.resume', send: 'aktionen.senden', alarms: 'aktionen.alarms', weather: 'aktionen.weather',
		edit: 'aktionen.edit', archive: 'aktionen.archive', unarchive: 'aktionen.unarchive', delete: 'aktionen.delete', 'continue-setup': 'aktionen.continue_setup'
	};
	const alle = () => {
		const z: Record<string, unknown[]> = {};
		for (const kind of ['trip', 'vergleich'] as const)
			for (const status of ['draft', 'active', 'paused', 'archived'] as const)
				for (const surface of ['list', 'hub', 'mobile'] as const) z[`${kind}/${status}/${surface}`] = P.aktionen.subscriptionActions(kind, status, surface);
		return z;
	};
	test('en: jede Aktion traegt trFor(en, aktionen.*), Trip und Vergleich gleich, IDs und danger unveraendert', () => {
		const { de, en } = deDannEn(alle);
		const gesehen = new Set<string>();
		for (const [fall, liste] of Object.entries(en)) {
			const deListe = de[fall] as { id: string; danger?: boolean }[];
			assert.deepEqual((liste as { id: string }[]).map((a) => a.id), deListe.map((a) => a.id), fall);
			for (const [i, a] of (liste as { id: string; label: string; danger?: boolean }[]).entries()) {
				assert.equal(a.label, trFor('en', SCHLUESSEL[a.id]), `${fall}: ${a.id}`);
				assert.equal(a.danger, deListe[i].danger, `${fall}: danger ${a.id}`);
				gesehen.add(a.id);
			}
			const [kind, ...rest] = fall.split('/');
			if (kind === 'trip') assert.deepEqual(liste, en[['vergleich', ...rest].join('/')], `${fall}: Trip != Vergleich`);
		}
		assert.deepEqual([...gesehen].sort(), Object.keys(SCHLUESSEL).sort(), 'Messaufbau: jede Aktion kommt vor');
		const hub = en['trip/active/hub'] as { label: string }[];
		assert.deepEqual(hub.map((a) => a.label), ['Pause', 'Archive', 'Delete']);
	});
	test('Reiter und Anlege-Kette englisch, Kennungen unveraendert; Sperr-Hinweise englisch', () => {
		const { de, en } = deDannEn(() => ({ t: P.reiter.subscriptionTabs('trip'), v: P.reiter.subscriptionTabs('vergleich'), at: P.reiter.anlegeKette('trip'), av: P.reiter.anlegeKette('vergleich') }));
		assert.deepEqual(en.t.map((r: { id: string }) => r.id), de.t.map((r: { id: string }) => r.id));
		assert.deepEqual(en.t.map((r: { label: string }) => r.label), ['Overview', 'Stages & waypoints', 'Weather metrics', 'Target ranges', 'Alerts']);
		assert.deepEqual(en.v.map((r: { label: string }) => r.label), ['Overview', 'Locations', 'Weather metrics', 'Target ranges', 'Alerts']);
		assert.deepEqual(en.at.map((r: { label: string }) => r.label), ['Route', 'Stages & GPX', 'Check waypoints', 'Weather metrics', 'Target ranges', 'Alerts']);
		assert.deepEqual(en.at.map((r: { lockHint?: string }) => r.lockHint ?? null), [null, 'trip name + start date first', 'upload all GPX files first', 'upload all GPX files first', 'open Weather metrics first', 'open Target ranges first']);
		assert.deepEqual(en.av.map((r: { lockHint?: string }) => r.lockHint ?? null), [null, 'name the comparison first', 'select at least 2 locations first', 'open Weather metrics first', 'open Target ranges first']);
		assert.equal(en.av[0].label, 'Comparison');
	});
});

describe('AC-4: Metrik-Namen ueber metricLabel, col_label unveraendert', () => {
	test('Ausgabe-Layout-Bausteine und Tabellen-Vorschau: label_en bzw. deutsch ohne label_en', () => {
		const { de, en } = deDannEn(() => P.layoutRendern());
		const sEn = sichtbar(en);
		hat(sichtbar(de), 'Böen');
		for (const s of ['Wind gusts', 'Temperature', 'Bewölkung', 'Code', 'Raw', 'Simple', 'raw value only', '→ Detail', '↑ Column', 'Limit', 'Telegram 9/7', '✂ from here Telegram cuts off (max 7 columns)', 'No entries — add metrics from “Not in the briefing”.', 'Not in the briefing', '3 more metrics', '1 more metric', '· not output', '▴ Collapse', '▾ Expand', '+ Column', '+ Detail', '6 metrics', '1 metric', 'Default', 'Indicator', 'Table preview', 'TODAY — 2 METRICS', 'TOMORROW — 0 METRICS', 'No metrics enabled for this horizon.', 'Time', '·simple', 'Alert rules', 'Alert thresholds', 'No alerts configured yet', 'Edit rules →', 'all columns · no limit', 'no grid · 140 characters', 'SMS not configured —', 'set up in your account', 'Daily max for remaining metrics', '3 metrics do not fit in the table — append as a compact daily summary', 'briefing schedule', 'Temperature', 'Wind', 'Atmosphere'])
			hat(sEn, s);
		for (const s of ['title="Telegram: max 7 columns"', 'aria-label="Raw or simple"', 'aria-label="Enable Email"', 'aria-label="Wind gusts"']) hat(en, s);
		// Voller Name englisch; die Kurzform (Fallback `label.slice(0, 5)`) bleibt wie jede Kurzform (ADR-0042).
		assert.ok(!/class="(label|off-name|col-name|metric-name)[^"]*">Böen</.test(en), 'voller Name noch deutsch');
		// Fixture: Preset „Wandern" (Name = Daten), Zeitplan-Speicherstand mit Server-Text „Gespeichert.".
		assert.deepEqual(deutscheReste(sEn, [...DATEN, 'trip.aktivitaet.wandern', 'trip.gespeichert_punkt']), []);
	});
	test('Uebersicht: Namensliste englisch, col_label der Fixture steht nirgends verfaelscht', () => {
		const { en } = deDannEn(() => sichtbar(P.uebersichtRendern()));
		hat(en, 'Temperature, Wind');
		for (const c of P.COL_LABELS) assert.ok(!en.includes(`${c}s `), c);
	});
});

describe('AC-7: Trip-Status je Sprache', () => {
	const STATUS = ['Aktiv', 'Pausiert', 'Entwurf', 'Archiviert', 'Fertig', 'Geplant'];
	const EN = ['Active', 'Paused', 'Draft', 'Archived', 'Finished', 'Planned'];
	test('de unveraendert, en Draft/Planned/Active/Paused/Finished/Archived', () => {
		const { de, en } = deDannEn(() => sichtbar(P.kopfRendern()));
		const ende = (s: string) => s.slice(s.lastIndexOf('STATUS'));
		for (const s of STATUS) hat(de, s);
		const enEnde = ende(en);
		for (const s of EN) hat(enEnde, s);
		for (const s of STATUS) hatNicht(enEnde, s);
	});
});

describe('AC-5: zwei Nutzer, zwei Sprachen, eigener Trip, sprachunabhaengige Nutzlast', () => {
	const trip = (id: string, name: string) => P.tripLaufend({ id, name });
	const API: Record<string, Record<string, unknown>> = {
		A: { '/api/auth/profile': { id: 'anna', language: 'en' }, '/api/trips/anna-gr20': trip('anna-gr20', 'Anna GR20'), '/api/metrics': P.KATALOG },
		B: { '/api/auth/profile': { id: 'bert', language: 'de' }, '/api/trips/bert-hr': trip('bert-hr', 'Bert Haute Route'), '/api/metrics': P.KATALOG }
	};
	async function mitApi<T>(lauf: () => Promise<T>): Promise<T> {
		const echt = globalThis.fetch;
		globalThis.fetch = (async (u: string, init?: { headers?: Record<string, string> }) => {
			const sitzung = /gz_session=([^;]+)/.exec(init?.headers?.Cookie ?? '')?.[1] ?? '';
			const daten = API[sitzung]?.[new URL(String(u)).pathname];
			return new Response(JSON.stringify(daten ?? null), { status: daten === undefined ? 404 : 200 });
		}) as unknown as typeof fetch;
		try {
			return await lauf();
		} finally {
			globalThis.fetch = echt;
		}
	}
	const cookies = (s: string) => ({ get: (n: string) => (n === 'gz_session' ? s : undefined) });

	async function sichtFuer(sitzung: 'A' | 'B', tripId: string, fremdeId: string) {
		const locals = { userId: sitzung, lang: 'de' as 'de' | 'en' };
		const { daten, fremd } = await mitApi(async () => {
			await layoutLoad({ locals, cookies: cookies(sitzung) } as never);
			const daten = await tripLoad({ params: { id: tripId }, locals, cookies: cookies(sitzung) } as never);
			const fremd = await tripLoad({ params: { id: fremdeId }, locals, cookies: cookies(sitzung) } as never).then(
				() => null,
				(e: { status?: number; body?: { message?: string } }) => e
			);
			return { daten, fremd };
		});
		locale.set(locals.lang);
		const seite = sichtbar(P.seiteRendern('gesendet', daten.trip));
		const rumpf: unknown[] = [];
		const client = { put: async (_p: string, body: unknown) => (rumpf.push(body), { ...daten.trip, ...(body as object) }) };
		await baueTripSpeicherung(client, daten.trip.id, { name: `${daten.trip.name} 2` }, () => {}, 'kopf-name')();
		return { lang: locals.lang, seite, fremd, rumpf, trip: daten.trip };
	}

	test('A englisch, B deutsch; jeder nur eigener Trip (fremder 404 in eigener Sprache); Nutzlast ohne Anzeigetexte', async () => {
		locale.set('de');
		const a = await sichtFuer('A', 'anna-gr20', 'bert-hr');
		const b = await sichtFuer('B', 'bert-hr', 'anna-gr20');
		assert.equal(a.lang, 'en');
		assert.equal(b.lang, 'de');
		assert.equal(a.trip.name, 'Anna GR20');
		assert.equal(b.trip.name, 'Bert Haute Route');
		assert.equal(a.fremd?.status, 404, 'A liest den Trip von B');
		assert.equal(b.fremd?.status, 404, 'B liest den Trip von A');
		assert.equal(a.fremd?.body?.message, "Trip 'bert-hr' not found");
		assert.equal(b.fremd?.body?.message, "Trip 'anna-gr20' nicht gefunden");
		hat(a.seite, 'Anna GR20');
		hat(a.seite, 'Overview');
		hat(a.seite, 'Briefing sent');
		hatNicht(a.seite, 'Bert Haute Route');
		hat(b.seite, 'Bert Haute Route');
		hat(b.seite, 'Übersicht');
		hat(b.seite, 'Briefing gesendet!');
		hatNicht(b.seite, 'Anna GR20');
		assert.deepEqual(a.rumpf, [{ name: 'Anna GR20 2' }]);
		assert.deepEqual(b.rumpf, [{ name: 'Bert Haute Route 2' }]);
		assert.deepEqual(Object.keys(a.rumpf[0] as object), Object.keys(b.rumpf[0] as object));
		for (const wort of ['Overview', 'Übersicht', 'Day', 'Tag', 'label']) hatNicht(JSON.stringify(a.rumpf), wort);
	});
});

describe('Anker: jeder F9-Katalogwert ist als festes de/en-Literal verankert', () => {
	const params = (literal: string) => Object.fromEntries([...literal.matchAll(/<([a-z0-9_]+)>/g)].map((m) => [m[1], `<${m[1]}>`]));
	for (const [k, de, en] of F9_ANKER) {
		test(k, () => {
			assert.equal(trFor('de', k, params(de)), de, `de ${k}`);
			assert.equal(trFor('en', k, params(en)), en, `en ${k}`);
		});
	}

	test('statischer Gegencheck: Anker == Schluessel von trip.json; aktionen.json = Bestand (S2/F3) + F9-Anker; vergleich.anlegen.* verankert', () => {
		const MSG = path.join(P.FRONTEND, 'src', 'lib', 'i18n', 'messages');
		const BESTAND_AKTIONEN = ['aktionen.zeit.vor_minuten.one', 'aktionen.zeit.vor_minuten.other', 'aktionen.zeit.gerade_eben', 'aktionen.abbrechen', 'aktionen.weitere', 'aktionen.zurueck_zu', 'aktionen.senden', 'aktionen.schliessen'];
		const anker = (p: string) => F9_ANKER.map(([k]) => k).filter((k) => k.startsWith(p));
		for (const lang of ['de', 'en']) {
			const lies = (b: string) => Object.keys(JSON.parse(readFileSync(path.join(MSG, lang, `${b}.json`), 'utf-8')));
			assert.deepEqual(lies('trip').sort(), anker('trip.').sort(), `${lang}: trip.json`);
			assert.deepEqual(lies('aktionen').sort(), [...BESTAND_AKTIONEN, ...anker('aktionen.')].sort(), `${lang}: aktionen.json`);
			assert.deepEqual(lies('vergleich').filter((k) => k.startsWith('vergleich.anlegen.')).sort(), anker('vergleich.anlegen.').sort(), `${lang}: vergleich.anlegen.*`);
		}
		assert.equal(new Set(F9_ANKER.map(([k]) => k)).size, F9_ANKER.length, 'doppelte Anker');
	});

	test('ein Text steht in aktionen.* nie unter zwei Schluesseln (de)', () => {
		const MSG = path.join(P.FRONTEND, 'src', 'lib', 'i18n', 'messages');
		const kat = JSON.parse(readFileSync(path.join(MSG, 'de', 'aktionen.json'), 'utf-8')) as Record<string, string>;
		const werte = Object.entries(kat).filter(([k]) => !k.endsWith('.one') && !k.endsWith('.other')).map(([, v]) => v);
		assert.equal(new Set(werte).size, werte.length, werte.join(' | '));
	});

	test('Plural exakt: unbekannte Groessen, weitere Metriken, Kaskade', () => {
		assert.equal(P.trnFor('en', 'trip.uebersicht.unbekannt', 1), '1 metric unknown');
		assert.equal(P.trnFor('en', 'trip.uebersicht.unbekannt', 2), '2 metrics unknown');
		assert.equal(P.trnFor('de', 'trip.uebersicht.unbekannt', 1), '1 Größe unbekannt');
		assert.equal(P.trnFor('de', 'trip.uebersicht.unbekannt', 2), '2 Größen unbekannt');
		assert.equal(P.trnFor('en', 'trip.kaskade.frage', 1, { datum: 'X' }), 'Should the following stage follow without a gap, from X?');
		assert.equal(P.trnFor('de', 'trip.kaskade.frage', 3, { datum: 'X' }), 'Sollen die 3 folgenden Etappen lückenlos anschließen, ab X?');
	});
});
