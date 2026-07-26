// Issue #758 — SaveStatus factory/class.
// KEINE modul-globalen $state-Exporte (das wäre ein geteilter Singleton → bricht AC-6).
// Jede Editor-Oberfläche erzeugt eine eigene Instanz via createSaveStatus().

export type SaveState = 'idle' | 'dirty' | 'saving' | 'error';

/**
 * Issue #1376: die Speicher-Funktion darf optional Fetch-Optionen entgegennehmen.
 * Nur so kann der Flush beim Verlassen der Seite `{ keepalive: true }` durchreichen —
 * ein normaler Request würde beim Entladen des Dokuments abgebrochen und die
 * Änderung ginge still verloren. Aufrufer, die das Argument ignorieren, bleiben
 * unverändert gültig.
 */
export type SaveFn = (init?: RequestInit) => Promise<void>;

/**
 * Bug #1389 (Adversary F002): Obergrenze für `settle()`. Ein unbegrenztes
 * Warten auf einen laufenden Request wäre ein Rückschritt — antwortet er im
 * Funkloch NIE (genau die Zielgruppe: Weitwanderer mit Netzabbrüchen), stünde
 * die Kaskaden-Bestätigung für immer still: keine Rückmeldung, kein Abbruch.
 * Nach Ablauf wird bewusst TROTZDEM geschrieben — das ist unbedenklich, weil
 * Maßnahme (a) im Normalfall gar keinen zweiten Schreibvorgang mehr erzeugt
 * (`defer()` statt `schedule()` bei offener Rückfrage); `settle()` ist nur
 * noch Rückfallschutz für Restwege. 8 s liegt deutlich über jeder normalen
 * Antwortzeit (Staging < 20 ms) und deutlich unter der Geduldsgrenze eines
 * Nutzers, der gerade auf „Alle mitverschieben" geklickt hat.
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
				this.setError(extractMessage(e));
			}
		})();
		this._inflight = run;
		await run;
		if (this._inflight === run) this._inflight = null;
	}

	/**
	 * Bug #1389: wartet, bis ein bereits abgeschickter Speichervorgang
	 * abgeschlossen ist. Ohne diesen Riegel könnte ein danach gestarteter
	 * Schreibvorgang (z.B. die Kaskaden-Bestätigung) beim Server FRÜHER ankommen
	 * als der zuvor abgeschickte — das Backend ersetzt die Etappen komplett und
	 * kennt keine Reihenfolge, der veraltete Stand gewinnt lautlos.
	 * Ohne laufenden Request kehrt die Methode sofort zurück.
	 *
	 * Adversary F002: das Warten ist auf `SETTLE_TIMEOUT_MS` gedeckelt und der
	 * Aufrufer fährt danach fort — ein hängender Request darf die Oberfläche
	 * nicht einfrieren (Begründung s. Konstante). Der Aufrufer hält die Anzeige
	 * währenddessen auf `saving`, damit die Wartezeit sichtbar ist.
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
	 *  Bug #1389: geprüft wird die ausstehende Funktion, nicht der Timer — ein
	 *  per `defer()` zurückgestellter Speichervorgang hat bewusst keinen Timer,
	 *  muss aber beim Verlassen der Seite geflusht werden (Bezug #1376). Für den
	 *  Debounce-Weg ist das unverändert (schedule setzt beides, doSave/cancel
	 *  löschen beides). */
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
	 * Bug #1389: stellt einen Speichervorgang zurück, OHNE einen Timer zu starten.
	 * Er feuert nie von selbst — nur `flush()` (Antwort auf die Rückfrage bzw.
	 * `beforeNavigate` beim Verlassen der Seite) löst ihn aus.
	 *
	 * Zweck: solange eine Rückfrage offen ist ("Folge-Etappen mitverschieben?"),
	 * darf kein Schreibvorgang mit dem halbfertigen Zwischenstand losgehen — sonst
	 * sind zwei Schreibvorgänge unterwegs und die Netz-Laufzeit entscheidet.
	 * Gleichzeitig gilt der Stand als ausstehend (`hasPending`), damit ein Reload
	 * oder Seitenwechsel ihn noch schreibt statt ihn zu verlieren (Bezug #1376).
	 *
	 * Der Zustand wird `dirty` ("Nicht gespeichert") — ehrlich, denn es wurde
	 * bewusst noch nichts geschrieben.
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
	 * Bug #1389: verwirft ebenso einen per `defer()` zurückgestellten Save.
	 *
	 * Adversary F003: `defer()` setzt bewusst KEINEN Timer — ohne den zweiten
	 * Zweig bliebe nach dem Abbruch eines zurückgestellten Saves `dirty`
	 * („Nicht gespeichert") stehen, obwohl gar nichts mehr aussteht. Der
	 * Zusatz-Riegel `_inflight === null` hält die oben beschriebene Regel
	 * ein: läuft ein echter Request im Netz, wird hier nichts zurückgesetzt.
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

export function createSaveStatus(): SaveStatus {
	return new SaveStatus();
}
