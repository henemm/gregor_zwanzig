// Issue #758 — SaveStatus factory/class.
// KEINE modul-globalen $state-Exporte (das wäre ein geteilter Singleton → bricht AC-6).
// Jede Editor-Oberfläche erzeugt eine eigene Instanz via createSaveStatus().

export type SaveState = 'idle' | 'dirty' | 'saving' | 'error';

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
	private _pendingFn: (() => Promise<void>) | null = null;

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

	setError(msg: string): void {
		this.state = 'error';
		this.error = msg;
	}

	async doSave(saveFn: () => Promise<void>): Promise<void> {
		this._pendingFn = null;
		this._timer = null;
		this.setSaving();
		try {
			await saveFn();
			this.setSaved();
		} catch (e) {
			this.setError(extractMessage(e));
		}
	}

	/** Returns true if a debounced save is pending (not yet flushed). */
	get hasPending(): boolean {
		return this._timer !== null;
	}

	/** Schedule a debounced save (700ms default). Calling again cancels previous timer.
	 *  SOFORT setSaving() — damit der Indikator nie "idle" (Gespeichert ✓) zeigt,
	 *  während eine ungespeicherte Änderung im Debounce-Fenster wartet (AC-1). */
	schedule(saveFn: () => Promise<void>, ms = 700): void {
		this.setSaving();
		this._pendingFn = saveFn;
		if (this._timer !== null) clearTimeout(this._timer);
		this._timer = setTimeout(() => { void this.doSave(saveFn); }, ms);
	}

	/** Flush any pending debounced save immediately. Returns a promise that resolves when done. */
	async flush(): Promise<void> {
		if (this._timer !== null && this._pendingFn !== null) {
			clearTimeout(this._timer);
			const fn = this._pendingFn;
			await this.doSave(fn);
		}
	}
}

export function createSaveStatus(): SaveStatus {
	return new SaveStatus();
}
