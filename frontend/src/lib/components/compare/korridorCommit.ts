// Issue #2317 (AC-7, Ortsvergleich) — Speicherfunktion der Idealwerte im Hub.
// Spec: docs/specs/modules/speicherung_beim_neuladen.md § Baustein 2, AC-7
//
// Vorher lebte der Rumpf in CompareTabs.svelte `handleCorridorCommit` und fing
// einen gescheiterten PUT selbst ab. Im Speicher-Takt (`schedule` aus
// CorridorEditor/Mobile) kam der Fehler damit nie bei `SaveStatus.doSave` an:
// der meldete „gespeichert", und „Aktualisieren" lud trotz verlorener Eingabe
// neu. Jetzt wird der Fehler NACH Rollback und Fehleranzeige weitergeworfen.
// Aufrufer ausserhalb des Speicher-Takts (focusout/click/pointerup) fangen ihn
// selbst (`.catch`), die Anzeige hat der Commit dann schon gesetzt.
//
// Ablauf unveraendert aus CompareTabs.svelte (Epic #1273 S1, Fix-Loops F003/F005):
// Snapshot/Diff/Rollback werden INNERHALB der Hub-Warteschlange gelesen.
// BEWUSST svelte-frei — unter node:test ladbar.

import type { SaveStatus } from '../../stores/saveStatusStore.svelte.ts';
import { extractMessage } from '../../stores/saveStatusStore.svelte.ts';
import type { PutQueue } from './compareHubWizardBridge.ts';

export interface KorridorCommitQuelle<S, P> {
	/** Idealwerte-Reiter hydriert? Sonst No-Op. */
	bereit(): boolean;
	ctl(): SaveStatus | undefined;
	queue: PutQueue;
	put(url: string, body: unknown, init?: RequestInit): Promise<P>;
	/** Aktueller Nutzerstand. */
	snapshot(): S;
	zuletztGespeichert(): S | null;
	merkeGespeichert(s: S): void;
	/** PUT-Rumpf, oder null wenn sich nichts Persistenzrelevantes geaendert hat. */
	payload(aktuell: S, zuletzt: S | null): { url: string; body: unknown } | null;
	zuruecksetzen(vorher: S): void;
	uebernehmen(preset: P): void;
}

export function baueKorridorCommit<S, P>(q: KorridorCommitQuelle<S, P>): (init?: RequestInit) => Promise<void> {
	return async (init) => {
		if (!q.bereit()) return;
		const ctl = q.ctl();
		let fehler: unknown = null;
		let gescheitert = false;
		ctl?.setSaving();
		const ergebnis = await q.queue.enqueue(async () => {
			const aktuell = q.snapshot();
			const vorher = q.zuletztGespeichert() ?? aktuell;
			const p = q.payload(aktuell, q.zuletztGespeichert());
			if (!p) return null;
			try {
				const antwort = await q.put(p.url, p.body, init);
				q.merkeGespeichert(aktuell);
				return antwort;
			} catch (e) {
				console.error('[CompareTabs] Wertebereich-Persistenz fehlgeschlagen, Rollback:', e);
				q.zuruecksetzen(vorher);
				fehler = e;
				gescheitert = true;
				return null;
			}
		});
		if (ergebnis) {
			q.uebernehmen(ergebnis);
			ctl?.setSaved();
		} else if (gescheitert) {
			ctl?.setError(extractMessage(fehler));
			// #2317 AC-7: der Speicher-Takt muss den Fehlschlag sehen.
			throw fehler;
		} else {
			ctl?.markPristine();
		}
	};
}
