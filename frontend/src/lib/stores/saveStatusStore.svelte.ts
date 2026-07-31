// Issue #758 — SaveStatus factory/class.
// KEINE modul-globalen $state-Exporte (das wäre ein geteilter Singleton → bricht AC-6).
// Jede Editor-Oberfläche erzeugt eine eigene Instanz via createSaveStatus().

import { refreshTripEtag } from '../api.ts';
import type { ApiError } from '../types.js';

export type SaveState = 'idle' | 'dirty' | 'saving' | 'error' | 'conflict';

/**
 * Issue #1376: die Speicher-Funktion darf optional Fetch-Optionen entgegennehmen.
 * Nur so kann der Flush beim Verlassen der Seite `{ keepalive: true }` durchreichen —
 * ein normaler Request würde beim Entladen des Dokuments abgebrochen und die
 * Änderung ginge still verloren. Aufrufer, die das Argument ignorieren, bleiben
 * unverändert gültig.
 */
export type SaveFn = (init?: RequestInit) => Promise<void>;

/**
 * Bug #1389 (Adversary F002): Obergrenze für `settle()`. Unbegrenztes Warten
 * legte die Kaskaden-Bestätigung im Funkloch für immer still (Zielgruppe:
 * Weitwanderer mit Netzabbrüchen). Nach Ablauf wird bewusst TROTZDEM
 * geschrieben — unbedenklich, weil bei offener Rückfrage ohnehin `defer()`
 * statt `schedule()` läuft und `settle()` nur Rückfallschutz ist. 8 s liegt
 * weit über jeder normalen Antwortzeit (Staging < 20 ms) und unter der
 * Geduldsgrenze nach einem Klick auf „Alle mitverschieben".
 */
export const SETTLE_TIMEOUT_MS = 8000;

export function extractMessage(e: unknown): string {
	if (e && typeof e === 'object') {
		const obj = e as Record<string, unknown>;
		if (typeof obj.detail === 'string' && obj.detail) return obj.detail;
		if (typeof obj.error === 'string' && obj.error) return obj.error;
		if (typeof obj.message === 'string' && obj.message) return obj.message;
	}
	return 'Fehler beim Speichern';
}

export class SaveStatus {
	state = $state<SaveState>('idle');
	error = $state<string | null>(null);
	// Issue #880: Zeitpunkt des letzten erfolgreichen Speicherns (HH:MM-Anzeige im Overlay).
	savedAt: Date | null = $state(null);

	// Debounce-Internals
	private _timer: ReturnType<typeof setTimeout> | null = null;
	private _pendingFn: SaveFn | null = null;
	// Bug #1389: der gerade im Netz laufende Speichervorgang. `cancel()` kann ihn
	// nicht mehr stoppen — wer ihn überschreiben will, muss auf ihn WARTEN
	// (`settle()`), sonst entscheidet die Netz-Laufzeit, welcher Stand gewinnt.
	private _inflight: Promise<void> | null = null;
	// Issue #1395 S4: der bei einem 412 abgelehnte Speichervorgang, damit
	// `retryConflict()` ihn unveraendert wiederholen kann.
	private _lastFailed: { fn: SaveFn; init?: RequestInit } | null = null;

	private _tripId?: string;

	constructor(tripId?: string) {
		this._tripId = tripId;
	}

	setSaving(): void {
		this.state = 'saving';
		this.error = null;
	}

	setSaved(): void {
		this.savedAt = new Date();
		this.state = 'idle';
		this.error = null;
	}

	setDirty(): void {
		this.state = 'dirty';
	}

	/**
	 * Issue #1269 (b): dirty→idle OHNE savedAt neu zu stempeln — Gegenstück zu
	 * setSaved(). Fuer Faelle, in denen der Zustand ohne echten PUT wieder
	 * "clean" wird (z.B. Baseline-Korrektur einer Mount-Kanonisierung, die
	 * faelschlich dirty gesetzt hatte). savedAt bleibt unangetastet, damit nie
	 * ein frischer "Gespeichert HH:MM"-Zeitstempel ohne echten Speichervorgang
	 * vorgetaeuscht wird.
	 */
	markPristine(): void {
		this.state = 'idle';
		this.error = null;
	}

	setError(msg: string): void {
		this.state = 'error';
		this.error = msg;
	}

	async doSave(saveFn: SaveFn, init?: RequestInit): Promise<void> {
		this._pendingFn = null;
		this._timer = null;
		this.setSaving();
		const run = (async () => {
			try {
				await saveFn(init);
				this.setSaved();
			} catch (e) {
				// Issue #1395 S4: nur ein echter Nebenlaeufigkeits-Konflikt auf einer
				// bekannten Tour bekommt den eigenen Zustand mit Wiederholen-Knopf.
				if ((e as ApiError)?.status === 412 && this._tripId) {
					this._lastFailed = { fn: saveFn, init };
					this.state = 'conflict';
					this.error = extractMessage(e);
				} else {
					this.setError(extractMessage(e));
				}
			}
		})();
		this._inflight = run;
		await run;
		if (this._inflight === run) this._inflight = null;
	}

	/**
	 * Issue #1395 S4: frischt den bekannten Stand auf und wiederholt danach genau
	 * den Speichervorgang, der am Konflikt gescheitert ist. `setSaving()` steht
	 * bewusst VOR dem Refresh — ein zweiter Klick trifft dann auf `'saving'` und
	 * bricht am Guard ab, statt einen zweiten Refresh samt zweitem Sendevorgang
	 * loszuschicken.
	 */
	async retryConflict(): Promise<void> {
		if (this.state !== 'conflict' || !this._lastFailed || !this._tripId) return;
		const { fn, init } = this._lastFailed;
		this._lastFailed = null;
		this.setSaving();
		try {
			await refreshTripEtag(this._tripId);
		} catch (e) {
			this.setError(extractMessage(e));
			return;
		}
		await this.doSave(fn, init);
	}

	/**
	 * Bug #1389: wartet auf einen bereits abgeschickten Speichervorgang (ohne
	 * laufenden Request sofortige Rückkehr). Sonst könnte ein danach gestarteter
	 * Schreibvorgang FRÜHER ankommen und der veraltete Stand lautlos gewinnen —
	 * das Backend ersetzt die Etappen komplett und kennt keine Reihenfolge.
	 * Adversary F002: gedeckelt auf `SETTLE_TIMEOUT_MS` (Begründung s. Konstante),
	 * der Aufrufer hält die Anzeige derweil auf `saving`.
	 */
	async settle(): Promise<void> {
		const deadline = Date.now() + SETTLE_TIMEOUT_MS;
		// Schleife: `doSave()` kann während des Wartens erneut gefeuert haben.
		for (let i = 0; i < 5; i++) {
			const inflight = this._inflight;
			if (!inflight) return;
			const remaining = deadline - Date.now();
			if (remaining <= 0) return;
			let timer: ReturnType<typeof setTimeout> | undefined;
			const capped = new Promise<'timeout'>((resolve) => {
				timer = setTimeout(() => resolve('timeout'), remaining);
			});
			const outcome = await Promise.race([inflight.then(() => 'done' as const), capped]);
			if (timer !== undefined) clearTimeout(timer);
			if (outcome === 'timeout') return;
		}
	}

	/** Returns true if a save is pending (debounced or deferred, not yet flushed).
	 *  Bug #1389: geprüft wird die ausstehende Funktion, nicht der Timer — ein per
	 *  `defer()` zurückgestellter Save hat bewusst keinen Timer, muss aber beim
	 *  Verlassen der Seite geflusht werden (#1376). Debounce-Weg unverändert. */
	get hasPending(): boolean {
		return this._pendingFn !== null;
	}

	/** Schedule a debounced save (700ms default). Calling again cancels previous timer.
	 *  SOFORT setSaving() — damit der Indikator nie "idle" (Gespeichert ✓) zeigt,
	 *  während eine ungespeicherte Änderung im Debounce-Fenster wartet (AC-1). */
	schedule(saveFn: SaveFn, ms = 700): void {
		this.setSaving();
		this._pendingFn = saveFn;
		if (this._timer !== null) clearTimeout(this._timer);
		this._timer = setTimeout(() => { void this.doSave(saveFn); }, ms);
	}

	/** Flush any pending debounced save immediately. Returns a promise that resolves when done.
	 *  Issue #1376: `init` wird an die Speicher-Funktion durchgereicht — beim
	 *  Entladen der Seite ruft der Aufrufer `flush({ keepalive: true })`, damit
	 *  der Request das Dokument überlebt. Der Request wird dabei noch synchron
	 *  im Aufrufer-Tick abgesetzt (kein `await` vor dem `fetch`). */
	async flush(init?: RequestInit): Promise<void> {
		if (this._pendingFn !== null) {
			if (this._timer !== null) clearTimeout(this._timer);
			const fn = this._pendingFn;
			await this.doSave(fn, init);
		}
	}

	/**
	 * Bug #1389: stellt einen Speichervorgang zurück, OHNE Timer — er feuert nie
	 * von selbst, nur `flush()` (Antwort auf die Rückfrage bzw. `beforeNavigate`)
	 * löst ihn aus. Zweck: solange eine Rückfrage offen ist, darf kein
	 * Schreibvorgang mit dem halbfertigen Zwischenstand losgehen, sonst sind zwei
	 * unterwegs und die Netz-Laufzeit entscheidet. Er gilt trotzdem als ausstehend
	 * (`hasPending`), damit Reload/Seitenwechsel ihn noch schreibt (#1376).
	 * Zustand `dirty` ("Nicht gespeichert") — es wurde bewusst nichts geschrieben.
	 */
	defer(saveFn: SaveFn): void {
		if (this._timer !== null) clearTimeout(this._timer);
		this._timer = null;
		this._pendingFn = saveFn;
		this.setDirty();
	}

	/**
	 * Issue #1261 (b), Adversary F002 (CRITICAL): bricht einen noch NICHT
	 * ausgelösten debounced Save ab (Timer + pending-Fn löschen), OHNE
	 * `saveFn` aufzurufen — Gegenstück zu `flush()`, das den ausstehenden Save
	 * erzwingt statt ihn zu verwerfen. Additiv: nur Aufrufer, die `cancel()`
	 * explizit rufen, sind betroffen (der Trip-Pfad ruft `cancel()` nirgends —
	 * dort unverändertes Verhalten).
	 *
	 * Läuft ein Save bereits im Netzwerk (state 'saving', Timer bereits null,
	 * `doSave()` steckt im `await saveFn()`), kann dieser Request nicht mehr
	 * storniert werden — `cancel()` verhindert dann nur einen etwaigen noch
	 * nicht gefeuerten NACHFOLGE-Timer. Das deckt sich mit der akzeptierten
	 * Spec-Grenze (Known Limitations): vor dem Debounce-Ablauf verwirft
	 * "Verwerfen" wirklich, nach bereits erfolgtem Autosave kein Rollback.
	 *
	 * Adversary MEDIUM-Fix: der Status wird NUR zurückgesetzt, wenn tatsächlich
	 * ein noch nicht gefeuerter Timer abgebrochen wurde. Lief bereits ein
	 * echter Save im Netzwerk (Timer schon null, state 'saving' durch
	 * `doSave()`), bleibt der State unberührt — `doSave()`s eigenes
	 * `setSaved()`/`setError()` nach Abschluss ist dafür zuständig, sonst
	 * würde `cancel()` fälschlich "idle" vorgaukeln, während der Request noch
	 * offen ist (widerspricht dem eigenen "kein Rollback nach Autosave"-Zweck).
	 *
	 * Bug #1389 / Adversary F003: verwirft ebenso einen per `defer()`
	 * zurückgestellten Save. Dessen eigener Zweig ist nötig, weil `defer()` keinen
	 * Timer setzt — sonst bliebe `dirty` stehen, obwohl nichts mehr aussteht. Der
	 * Riegel `_inflight === null` wahrt die Regel oben: läuft ein echter Request
	 * im Netz, wird hier nichts zurückgesetzt.
	 */
	cancel(): void {
		const hadPendingTimer = this._timer !== null;
		const hadDeferred = !hadPendingTimer && this._pendingFn !== null;
		if (this._timer !== null) clearTimeout(this._timer);
		this._timer = null;
		this._pendingFn = null;
		const resettable = hadPendingTimer || (hadDeferred && this._inflight === null);
		if (resettable && (this.state === 'saving' || this.state === 'dirty')) {
			this.state = 'idle';
		}
	}
}

export function createSaveStatus(tripId?: string): SaveStatus {
	return new SaveStatus(tripId);
}
