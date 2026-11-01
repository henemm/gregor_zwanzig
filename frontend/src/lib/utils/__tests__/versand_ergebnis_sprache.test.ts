// Issue #2660 (i18n F11, Epic #2644) — AC-3 und AC-5: die Versand-Meldungen
// aus `sendOutcome.ts` werden bei JEDEM Aufruf in der dann gueltigen Sprache
// gebaut; nichts bleibt aus dem Import eingefroren. Dasselbe Modul wird zuerst
// unter `de`, dann nach `locale.set('en')` ohne Neuladen befragt.
// Deutsch: Golden-Literale aus dem Quelltext vor der Umstellung (wortgleich).
// Spec: docs/specs/modules/i18n_f11_bausteine_ts_2660.md
//
//   cd frontend && npm test -- src/lib/utils/__tests__/versand_ergebnis_sprache.test.ts

import { test, describe, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { classifySendResponse, runSend, sendBriefing } from '../sendOutcome.ts';
import { ortInUseHinweis } from '../ortLoeschenSperre.ts';
import { locale, trFor } from '../../i18n/index.ts';

afterEach(() => locale.set('de'));

const GOLDEN_DE = {
	unklar: 'Ergebnis unklar — Versand kann noch laufen, nicht erneut senden',
	laeuft: 'Versand läuft bereits',
	fehlgeschlagen: 'Versand fehlgeschlagen — Serverfehler, bitte später erneut versuchen.',
	abgelehnt: 'Versand fehlgeschlagen — bitte später erneut versuchen.',
	orte: 'Test-Briefing gesendet, aber Orte fehlten (gelöscht, 2): ort-a, ort-b. Ersetze die Orte im Ortsvergleich.',
	sperre: 'Dieser Ort wird noch in diesen Ortsvergleichen verwendet: Korsika, Alpen. Entferne ihn dort zuerst.'
};

function meldungen() {
	return {
		laeuft: classifySendResponse({ status: 409 }).message,
		unklar502: classifySendResponse({ status: 502 }).message,
		unklarNetz: classifySendResponse({ networkError: true }).message,
		fehlgeschlagen: classifySendResponse({ status: 500 }).message,
		abgelehnt: classifySendResponse({ status: 422 }).message,
		detail: classifySendResponse({ status: 422, detail: 'Servertext bleibt' }).message
	};
}

/** Ortsvergleich-Versand mit echter Response: 200 und zwei fehlende Orte. */
async function orteFehlten(): Promise<string> {
	const fetchFn = (async () =>
		new Response(JSON.stringify({ fehlende_orte: ['ort-a', 'ort-b'] }), {
			status: 200,
			headers: { 'Content-Type': 'application/json' }
		})) as unknown as typeof fetch;
	const r = await sendBriefing('vergleich', `cp-2660-${Math.random()}`, {}, fetchFn);
	assert.equal(r.kind, 'ok');
	return r.message;
}

const SPERRE = { error: 'location_in_use', compare_presets: [{ id: 'c1', name: 'Korsika' }, { id: 'c2', name: 'Alpen' }] };

describe('AC-3/AC-5: Versand-Ergebnis folgt der Sprache zum Aufrufzeitpunkt', () => {
	test('erst de (wortgleich), dann en (Katalog) — dasselbe geladene Modul', async () => {
		locale.set('de');
		const d = meldungen();
		assert.equal(d.laeuft, GOLDEN_DE.laeuft);
		assert.equal(d.unklar502, GOLDEN_DE.unklar);
		assert.equal(d.unklarNetz, GOLDEN_DE.unklar);
		assert.equal(d.fehlgeschlagen, GOLDEN_DE.fehlgeschlagen);
		assert.equal(d.abgelehnt, GOLDEN_DE.abgelehnt);
		assert.equal(d.detail, 'Servertext bleibt');
		assert.equal(await orteFehlten(), GOLDEN_DE.orte);
		assert.equal(ortInUseHinweis(SPERRE)?.text, GOLDEN_DE.sperre);

		locale.set('en');
		const e = meldungen();
		assert.equal(e.laeuft, trFor('en', 'fehler.versand.laeuft_bereits'));
		assert.equal(e.unklar502, trFor('en', 'fehler.versand.unklar'));
		assert.equal(e.unklarNetz, trFor('en', 'fehler.versand.unklar'));
		assert.equal(e.fehlgeschlagen, trFor('en', 'fehler.versand.fehlgeschlagen'));
		assert.equal(e.abgelehnt, trFor('en', 'fehler.versand.abgelehnt'));
		assert.equal(e.detail, 'Servertext bleibt');
		assert.equal(
			await orteFehlten(),
			trFor('en', 'fehler.versand.orte_fehlten', { anzahl: 2, orte: 'ort-a, ort-b' })
		);
		assert.equal(ortInUseHinweis(SPERRE)?.text, trFor('en', 'fehler.ort.in_verwendung', { namen: 'Korsika, Alpen' }));
		for (const m of [e.laeuft, e.unklar502, e.fehlgeschlagen, e.abgelehnt, await orteFehlten()]) {
			assert.doesNotMatch(m, /[äöüß]|\b(Versand|nicht|bitte|Orte)\b/, m);
		}
	});

	test('zurueck nach de: wieder die deutschen Texte (kein Zustand bleibt haengen)', () => {
		locale.set('en');
		meldungen();
		locale.set('de');
		assert.deepEqual(meldungen().laeuft, GOLDEN_DE.laeuft);
	});

	test('laufender Versand (runSend, skipped) meldet in der aktuellen Sprache', async () => {
		let freigeben: () => void = () => {};
		const haengt = new Promise<Response>((r) => (freigeben = () => r(new Response(null, { status: 204 }))));
		const key = `trip:2660-${Math.random()}`;
		const erster = runSend(key, () => haengt);
		locale.set('en');
		const zweiter = await runSend(key, () => haengt);
		assert.equal(zweiter.skipped, true);
		assert.equal(zweiter.message, trFor('en', 'fehler.versand.laeuft_bereits'));
		locale.set('de');
		assert.equal((await runSend(key, () => haengt)).message, GOLDEN_DE.laeuft);
		freigeben();
		await erster;
	});
});
