// TDD RED — Issue #2913 (Einstellungen neu, Schritt 3: Bausteine), Teil 2.
// Spec: docs/specs/modules/feat_2913_s3_bausteine.md — AC-21, Klarstellung K-4.
//
// Soll:
//   - Die Texte des Wetter-Reiters (wetter.json DE und EN) sind durch die Lieferung unverändert. Gemessen
//     gegen den Abzweigpunkt des Arbeitsstands von origin/main (git merge-base HEAD origin/main): die Datei im
//     Arbeitsbaum ist byte-gleich zur Fassung dort. Auf main selbst ist der Abzweigpunkt HEAD — der Test
//     bleibt also dauerhaft gültig und sperrt keine spätere, bewusste Textänderung in einem eigenen PR.
//     Ohne git/origin (z. B. flacher Checkout) wird der Vergleich mit Begründung übersprungen.
//   - Die neuen bzw. umgebauten Bausteine (Skelett, Einstellungszeile, ChipLeiste, Seite shared/WetterTab,
//     Organismus WetterTabInhalt) enthalten keinen hartcodierten Nutzertext (Scanner der i18n-Ratsche #2649).
//     Ein etwaiger Skelett-Standardtext liegt im Allgemein-Katalog (K-4), nicht in wetter.json.
//
// Hinweis Rote Phase: der Katalogvergleich ist reines Erhaltungsverhalten und darf heute grün sein; ROT sind
// die Scans der noch fehlenden Dateien.
//
// Quellregeln (Kataloge, Markup-Scan):
// doc-compliance-test
//
//   cd frontend && npm test -- src/lib/components/organisms/__tests__/wetter_tab_i18n.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { existsSync, readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

import { scanneMarkup } from '../../../i18n/__tests__/hardcode_scan.ts';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const KOMP = path.resolve(HERE, '..', '..'); // src/lib/components
const FRONTEND = path.resolve(KOMP, '..', '..', '..');
const REPO = path.resolve(FRONTEND, '..');

function git(args: string[]): string | null {
	try {
		return execFileSync('git', args, { cwd: REPO, encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'] });
	} catch {
		return null;
	}
}
const BASIS = git(['merge-base', 'HEAD', 'origin/main'])?.trim() || null;

// #2913 Scheibe (c) (Spec feat_2913_scheibe_c_wetter_rest.md, AC-5/AC-8): diese Lieferung ergänzt bewusst genau
// zwei neue Schlüssel. Der Erhaltungsschutz bleibt: jeder Bestandsschlüssel ist mit byte-gleichem Wert vorhanden,
// kein Schlüssel entfällt, und hinzukommen dürfen nur die hier freigegebenen Schlüssel.
// #2913 Fix Metrik-Liste (Spec fix_2913_metrikliste_mockup.md, AC-5): Untertitel-Hinweise der Metrik-Zeile.
const NEU_FREIGEGEBEN = new Set([
	// #2800 (Spec feat_2800_trip_radar_alarm.md AC-6): Radar-Hinweis im Trip „deine Etappe" / „your stage".
	'wetter.radar.deine_etappe',
	// #3430 (Spec docs/specs/fast/fix-3430-radar-ein-ort.md): Radar-Hinweis bei genau einem Ort.
	'wetter.radar.dein_ort',
	// #3122 B3b (Spec feat_3122_was_steht_wo.md Teil B Nr. 10 bis 12): Texte der Karte „Was steht wo“.
	'wetter.wsw.titel',
	'wetter.wsw.text_route',
	'wetter.wsw.text_vergleich',
	'wetter.wsw.metrik',
	'wetter.wsw.spalte.email',
	'wetter.wsw.spalte.telegram',
	'wetter.wsw.spalte.telegram_kurz',
	'wetter.wsw.spalte.sms',
	'wetter.wsw.spalte.hourly',
	'wetter.wsw.spalte.hourly_kurz',
	'wetter.wsw.spalte.outlook',
	'wetter.wsw.spalte.outlook_kurz',
	'wetter.wsw.unterzeile.stundentabelle',
	'wetter.wsw.unterzeile.uebersicht',
	'wetter.wsw.unterzeile.nachricht',
	'wetter.wsw.unterzeile.kurzstil',
	'wetter.wsw.unterzeile.und_premium_sms',
	'wetter.wsw.unterzeile.nur_email',
	'wetter.wsw.unterzeile.email_und_telegram',
	'wetter.wsw.zelle.email',
	'wetter.wsw.zelle.telegram',
	'wetter.wsw.zelle.sms',
	'wetter.wsw.zelle.hourly',
	'wetter.wsw.zelle.outlook',
	'wetter.wsw.grund.kein_stundenwert',
	'wetter.wsw.grund.keine_eigene_spalte',
	'wetter.wsw.grund.kein_tageswert',
	'wetter.wsw.grund.kein_kuerzel',
	'wetter.wsw.grund.nicht_in_email',
	'wetter.wsw.marke.passt_nicht_mehr',
	'wetter.wsw.marke.nur_tageswert',
	'wetter.wsw.warnungen.name',
	'wetter.wsw.warnungen.hinweis',
	'wetter.wsw.warnungen.grund',
	'wetter.wsw.sms.beispiel',
	'wetter.wsw.sms.zeichen',
	'wetter.wsw.sms_passt_nicht.one',
	'wetter.wsw.sms_passt_nicht.other',
	'wetter.wsw.sms_orte_passt_nicht.one',
	'wetter.wsw.sms_orte_passt_nicht.other',
	'wetter.wsw.sms.hochziehen',
	'wetter.wsw.legende.titel',
	'wetter.wsw.legende.zeit_ab_gelb',
	'wetter.wsw.legende.amtliche_warnung',
	'wetter.wsw.legende.stufe_gelb',
	'wetter.wsw.legende.stufe_orange',
	'wetter.wsw.legende.stufe_rot',
	'wetter.wsw.legende.warnung_wind',
	'wetter.wsw.legende.warnung_starkregen',
	'wetter.wsw.legende.lawinenstufe',
	'wetter.wsw.legende.warnquelle_nicht_erreichbar',
	'wetter.wsw.bloecke.titel',
	'wetter.wsw.bloecke.stundenverlauf',
	'wetter.wsw.bloecke.stundenverlauf_hinweis',
	'wetter.wsw.bloecke.stundenverlauf_hinweis_ein_ort',
	'wetter.wsw.bloecke.ausblick',
	'wetter.wsw.bloecke.ausblick_hinweis_route',
	'wetter.wsw.bloecke.ausblick_hinweis_vergleich',
	'wetter.wsw.bloecke.morgen',
	'wetter.wsw.bloecke.abend',
	'wetter.wsw.bloecke.ausblick_morgen',
	'wetter.wsw.bloecke.ausblick_abend',
	'wetter.wsw.bloecke.etappen',
	'wetter.wsw.bloecke.etappen_hinweis',
	'wetter.wsw.bloecke.vortag',
	'wetter.wsw.bloecke.vortag_hinweis',
	'wetter.wsw.bloecke.nacht',
	'wetter.wsw.bloecke.nacht_hinweis',
	// #3154: Grund der Kompakt-Sperre (Etappen-Kennzahlen, Vortag-Vergleich, Nacht-Stundentabelle).
	'wetter.wsw.bloecke.nur_ausfuehrlich',
	// #3036: Schalter Kurz-Zusammenfassung und Großwetterlage (nur Trip, ausführliche E-Mail).
	'wetter.wsw.bloecke.kurz',
	'wetter.wsw.bloecke.kurz_hinweis',
	'wetter.wsw.bloecke.grosswetterlage',
	'wetter.wsw.bloecke.grosswetterlage_hinweis',
	'wetter.wsw.kanal.titel',
	'wetter.wsw.kanal.email_format',
	'wetter.wsw.kanal.email_format_hinweis',
	'wetter.wsw.kanal.ausfuehrlich',
	'wetter.wsw.kanal.kompakt',
	'wetter.wsw.kanal.kurzstil',
	'wetter.wsw.kanal.kurzstil_hinweis',
	'wetter.wsw.kanal.kurzstil_name',
	'wetter.wsw.kanal.premium',
	'wetter.wsw.kanal.premium_hinweis',
	'wetter.wsw.laden',
	'wetter.wsw.fehler',
	'wetter.wsw.leer',
	'wetter.wsw.konflikt',
	'wetter.wsw.speicherfehler',
	'wetter.anpassen.hinweis',
	'wetter.anpassen.ueber_mitternacht',
	'wetter.untertitel.vorbote',
	'wetter.untertitel.nur_anzeige',
	// #2913 Runde 2 (Befund 1): Beschriftung der grünen Gewitter-Zone (Mockup „keins · mittel · hoch“).
	'wetter.gewitter.keins',
	...['temperature', 'temperature_night', 'wind', 'gust', 'precipitation', 'thunder', 'visibility', 'cloud_low', 'uv_index', 'freezing_level', 'snowfall_limit', 'sunshine'].map((id) => `wetter.hinweis.${id}`),
	// #2981 Vorlagennamen zweisprachig: Namen der sieben eingebauten Wetter-Vorlagen.
	...['alpen_trekking', 'wandern', 'skitouren', 'wintersport', 'radtour', 'wassersport', 'allgemein'].map((id) => `wetter.vorlage.name.${id}`),
	// #3047 Runde 7 (AC-26, Befund E6): Grund fuer gespeicherte, im Orts-Vergleich nicht ausgebbare Groessen.
	'wetter.gesperrt.grund',
	// #2955 (Spec wetter_metrik_inhalte.md AC-2): Gewitter-Satz „mittel oder hoch“, wenn schon „mittel“ die Alarmstufe erreicht.
	'wetter.gewitter.mittel_ab',
	// #2966 (Spec feat_2966_abgleich_haken.md AC-3): Warnung als zwei Absätze, Sätze 2 und 3.
	'wetter.kopf.fehler_verbindung',
	// #3111 (Spec feat_3111_wetter_dialoge_mockup.md AC-1 bis AC-7): Wetter-Dialoge nach Mockup Fassung 4.
	'wetter.grenzen.unten_1',
	'wetter.grenzen.unten_2',
	'wetter.grenzen.oben_1',
	'wetter.grenzen.oben_2',
	'wetter.vorlage.frage_titel',
	'wetter.vorlage.ersetzt_route',
	'wetter.vorlage.ersetzt_vergleich',
	'wetter.vorlage.ersetzt_vergleich_ein',
	'wetter.vorlage.aktiv_marker',
	'wetter.vorlage.eigene_unterzeile',
	...['alpen_trekking', 'wandern', 'skitouren', 'wintersport', 'radtour', 'wassersport', 'allgemein'].map((id) => `wetter.vorlage.stichworte.${id}`),
	'wetter.dialog.name_platzhalter',
	'wetter.dialog.beschreibung_platzhalter',
	// #3189 (Spec feat_3189_vorlage_herkunft.md AC-4): Unterzeile „aus {name} gespeichert“ eigener Vorlagen.
	'wetter.vorlage.eigene_aus_herkunft'
]);
// #2913 Scheibe (c) Fix-Loop 2 (Bildprüfer Runde 1, Befund 1): Label wie im Mockup mit Doppelpunkt. Bewusst geändert,
// mit genau dem erwarteten neuen Wert — jede andere Änderung bleibt rot.
// #2913 Scheibe c2 (Spec feat_2913_c2_seitenkopf.md AC-8): Rücksetz-Text mit den Anführungszeichen des Mockups.
// #2955 (Spec wetter_metrik_inhalte.md AC-5): Kopfzähler „{n} von {m}“, m = alle ausgewählten Metriken (Platzhalter umbenannt).
const GEAENDERT_FREIGEGEBEN: Record<string, Record<string, string>> = {
	de: {
		'wetter.nicht_im_briefing.titel': 'Nicht im Briefing:',
		'wetter.vorlage.zuruecksetzen': 'Auf „{vorlage}“ zurücksetzen',
		'wetter.alarm_ab.zaehler': '{ausloesend} von {ausgewaehlt} Metriken lösen einen Alarm aus. {ohne} können keinen auslösen (Vorboten und reine Anzeige).',
		// #2966 AC-3: Satz 1; Sätze 2 und 3 wortgleich in wetter.kopf.fehler_verbindung.
		'wetter.kopf.fehler': 'Die Metriken konnten nicht geladen werden.',
		// #3122 B3b (AC-32, einstellungen_neu.md §5 Punkt 6): Meldung nach „+“ seit ADR-0124.
		'wetter.nicht_im_briefing.hinzugefuegt': '{metrik} ist jetzt im Briefing und in jedem Kanal angehakt. Unter ‚Was steht wo‘ kannst du sie für einzelne Kanäle abwählen.',
		// #3111 (Mockup Fassung 4): „…“ statt ‚…‘, Label mit „(optional)“.
		'wetter.vorlage.verlust.one': 'Deine 1 Abweichung von „{alt}“ geht verloren.',
		'wetter.vorlage.verlust.other': 'Deine {count} Abweichungen von „{alt}“ gehen verloren.',
		'wetter.gewitter.keins_gruen': '„keins“ ist immer grün.',
		'wetter.grenzen.hinweis': 'Grün ist alles zwischen „gelb unten“ und „gelb oben“. Ein leeres Feld heißt: auf dieser Seite keine Grenze.',
		'wetter.grenzen.abweichend': 'Abweichend von der Vorlage „{vorlage}“.',
		'wetter.dialog.beschreibung': 'Beschreibung (optional)',
		// #3204 (Spec feat_3204_anzeige_metriken_mockup.md, AC-3): Erklärsatz wortgleich zum Mockup Fassung 4.
		'wetter.erklaer.anzeige': 'Nur Anzeige: keine Ampel und kein Alarm. Roh oder Einfach stellst du unten unter „Was steht wo“ ein.'
	},
	en: {
		'wetter.nicht_im_briefing.titel': 'Not in the briefing:',
		'wetter.vorlage.zuruecksetzen': 'Reset to “{vorlage}”',
		'wetter.alarm_ab.zaehler': '{ausloesend} of {ausgewaehlt} metrics trigger an alert. {ohne} cannot trigger one (precursors and display only).',
		'wetter.kopf.fehler': 'The metrics could not be loaded.',
		'wetter.nicht_im_briefing.hinzugefuegt': '{metrik} is now in the briefing and ticked in every channel. Under ‘What goes where’ you can deselect it for individual channels.',
		'wetter.vorlage.verlust.one': 'Your 1 change from “{alt}” will be lost.',
		'wetter.vorlage.verlust.other': 'Your {count} changes from “{alt}” will be lost.',
		'wetter.gewitter.keins_gruen': '“none” is always green.',
		'wetter.grenzen.hinweis': 'Green is everything between “yellow lower” and “yellow upper”. An empty field means: no limit on this side.',
		'wetter.grenzen.abweichend': 'Changed from the template “{vorlage}”.',
		'wetter.dialog.beschreibung': 'Description (optional)',
		// #3204 (AC-3): Abschnittsname wetter.wsw.titel statt „for each list“.
		'wetter.erklaer.anzeige': 'Display only: no traffic light and no alert. You set raw or simple below under ‘What goes where’.'
	}
};

// #3172 (ADR-0125): die Orte-SMS trägt keinen Rest-Zähler „+N“ je Ort mehr -- der Hinweissatz dazu entfällt
// ersatzlos. Bewusst entfernt; jede andere Entfernung bleibt rot.
// #3111 (Mockup Fassung 4): einzeilige Grenzen-Titel und einteilige Rückfrage entfallen, ersetzt durch
// unten_1/_2, oben_1/_2 bzw. frage_titel + ersetzt_*.
// #2988 S4: wetter.grenzen.fehler_ungueltig entfällt mit dem Spiegel `ampelFehler` (einziger Verwender).
const ENTFERNT_FREIGEGEBEN = new Set([
	'wetter.grenzen.fehler_ungueltig',
	'wetter.wsw.sms.plus_je_ort',
	'wetter.grenzen.unten',
	'wetter.grenzen.oben',
	'wetter.vorlage.frage_route',
	'wetter.vorlage.frage_vergleich'
]);

describe('AC-21: wetter.json DE/EN — Bestandstexte unverändert gegenüber dem Abzweigpunkt von origin/main', () => {
	for (const lang of ['de', 'en']) {
		const rel = `frontend/src/lib/i18n/messages/${lang}/wetter.json`;
		test(`${lang}/wetter.json: Bestandsschlüssel byte-gleich, nur freigegebene Schlüssel neu`, (t) => {
			if (!BASIS) return t.skip('git merge-base HEAD origin/main nicht verfügbar (flacher Checkout)');
			const vorherText = git(['show', `${BASIS}:${rel}`]);
			assert.ok(vorherText !== null, `${rel} fehlt am Abzweigpunkt ${BASIS}`);
			const vorher: Record<string, string> = JSON.parse(vorherText!);
			const jetzt: Record<string, string> = JSON.parse(readFileSync(path.join(REPO, rel), 'utf8'));
			for (const [k, v] of Object.entries(vorher)) {
				if (ENTFERNT_FREIGEGEBEN.has(k) && !(k in jetzt)) continue;
				const soll = GEAENDERT_FREIGEGEBEN[lang][k] !== undefined && jetzt[k] !== v ? GEAENDERT_FREIGEGEBEN[lang][k] : v;
				assert.equal(jetzt[k], soll, `${rel}: ${k} wurde gegenüber ${BASIS.slice(0, 9)} verändert oder entfernt (AC-21: Texte unverändert)`);
			}
			const neu = Object.keys(jetzt).filter((k) => !(k in vorher));
			assert.deepEqual(neu.filter((k) => !NEU_FREIGEGEBEN.has(k)), [], `${rel}: nicht freigegebene neue Schlüssel`);
		});
	}
	test('#2966 AC-3: Warnung in zwei Schlüsseln, Wortlaut DE und EN festgeschrieben', () => {
		const lies = (lang: string) => JSON.parse(readFileSync(path.join(KOMP, '..', 'i18n', 'messages', lang, 'wetter.json'), 'utf8'));
		const de = lies('de');
		const en = lies('en');
		assert.equal(de['wetter.kopf.fehler'], 'Die Metriken konnten nicht geladen werden.');
		assert.equal(de['wetter.kopf.fehler_verbindung'], 'Die Verbindung zum Server ist abgebrochen. Deine Einstellungen sind gespeichert und gehen nicht verloren.');
		assert.equal(en['wetter.kopf.fehler'], 'The metrics could not be loaded.');
		assert.equal(en['wetter.kopf.fehler_verbindung'], 'The connection to the server was lost. Your settings are saved and will not be lost.');
	});
	test('#3189 AC-4: wetter.vorlage.eigene_aus_herkunft in DE und EN, Platzhalter {name} in beiden', () => {
		const lies = (lang: string) => JSON.parse(readFileSync(path.join(KOMP, '..', 'i18n', 'messages', lang, 'wetter.json'), 'utf8'));
		const de = lies('de');
		const en = lies('en');
		assert.equal(de['wetter.vorlage.eigene_aus_herkunft'], 'aus {name} gespeichert');
		assert.equal(en['wetter.vorlage.eigene_aus_herkunft'], 'saved from {name}');
	});
	test('DE und EN haben dieselben wetter.*-Schlüssel', () => {
		const de = Object.keys(JSON.parse(readFileSync(path.join(KOMP, '..', 'i18n', 'messages', 'de', 'wetter.json'), 'utf8'))).sort();
		const en = Object.keys(JSON.parse(readFileSync(path.join(KOMP, '..', 'i18n', 'messages', 'en', 'wetter.json'), 'utf8'))).sort();
		assert.deepEqual(en, de);
	});
});

describe('AC-21: keine hartcodierten Nutzertexte in den neuen Bausteinen', () => {
	const NEU = [
		'atoms/Skelett.svelte',
		'molecules/Einstellungszeile.svelte',
		'molecules/ChipLeiste.svelte',
		'shared/WetterTab.svelte',
		'organisms/wetter-tab/WetterTabInhalt.svelte'
	];
	for (const rel of NEU) {
		test(`${rel}: kein Textknoten/beschriftendes Attribut außerhalb des Katalogs`, () => {
			const p = path.join(KOMP, rel);
			assert.ok(existsSync(p), `TDD RED: ${rel} fehlt`);
			assert.deepEqual(scanneMarkup(readFileSync(p, 'utf8')), []);
		});
	}
});
