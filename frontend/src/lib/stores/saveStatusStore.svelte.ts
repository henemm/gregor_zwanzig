// Issue #758 — SaveStatus factory/class.
// KEINE modul-globalen $state-Exporte (das wäre ein geteilter Singleton → bricht AC-6).
// Jede Editor-Oberfläche erzeugt eine eigene Instanz via createSaveStatus().

import { refreshResourceEtagMitTrip } from '../api.ts';
import { getKnownEtag, loescheKonflikt, markiereKonflikt, setKnownEtag } from '../etagRegistry.ts';
import type { NachladeKennung } from '../pwa/geraetespeicher.ts';
import type { ApiError } from '../types.js';
import { nutzlastVon, wendeNutzlastenAn } from './nutzlastStand.ts';

/** F502: Stempel, der zu keinem Server-Stand passt (Go `ifMatchAllows` ⇒ 412). */
const KEIN_STEMPEL_PLATZHALTER = '"gz-kein-stempel-vor-dem-holen"';

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
 * Issue #1433: Eintrag der Liste gescheiterter Speichervorgaenge. Der Rumpf ist
 * eine Funktion (kein Verweis auf eine Komponenteninstanz) und haelt nur die
 * Eigenfelder seines Reiters — das Wiederholen ist daher idempotent.
 */
interface FehlgeschlagenerEintrag {
	fn: SaveFn;
	init?: RequestInit;
	/**
	 * Fix-Loop 3 (F201): die zuletzt GESENDETE Eigenfeld-Nutzlast als Daten — damit die
	 * Seite sie in ihren Stand fortschreiben kann (Seitenstand = Server ⊕ Nutzlasten).
	 */
	nutzlast?: unknown;
}

/**
 * Dedup-Schluessel einer Speicherfunktion (ein Eintrag je Reiter/Schreiber, gesetzt
 * ueber `mitKonfliktSchluessel` in `components/shared/tripSpeicherung.ts`). Fehlt er,
 * gilt die Funktion selbst als Schluessel (kein Dedup).
 */
function schluesselVon(fn: SaveFn): unknown {
	return (fn as SaveFn & { konfliktSchluessel?: string }).konfliktSchluessel ?? fn;
}

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
	// nicht mehr stoppen — der Merker dient `cancel()`s Guard als Grundlage, damit
	// dort nichts zurückgesetzt wird, solange ein Request noch unterwegs ist.
	private _inflight: Promise<void> | null = null;
	// Issue #1395 S4 / #1433: die bei einem 412 abgelehnten Speichervorgaenge
	// (deduplizierte Liste, ein Eintrag je Reiter/Schreiber), damit
	// `retryConflict()` sie alle wiederholen kann. `null`/`undefined` = leer
	// (Testinstanzen entstehen ohne Konstruktor).
	private _lastFailed: FehlgeschlagenerEintrag[] | null = null;

	/**
	 * Fix-Loop 1 (#1433, F001/AC-19): die Seite uebernimmt den per GET geholten Trip
	 * (`'geholt'`, BEVOR die Eintraege erneut gesendet werden — Trip und Stempel
	 * gemeinsam) und erfaehrt den vollstaendigen Erfolg (`'wiederholt'`, damit die
	 * Reiter den dann gespeicherten Stand neu anzeigen). Wird von der Seite gesetzt.
	 */
	onAdopt: ((trip: unknown, phase: 'geholt' | 'wiederholt') => void) | null = null;

	/** true, solange `retryConflict()` die Eintraege wiederholt (s. dort). */
	imWiederholen = false;

	/**
	 * Fix-Loop 3 (#1433, F201): bei einem 412 wird die abgelehnte Eigenfeld-Nutzlast der
	 * Seite gemeldet, damit sie ihren Stand lokal fortschreibt (kein Stempelwechsel).
	 * Eigener Platz neben `onAdopt` — die Seite und ein Reiter-Organisator koennen
	 * unabhaengig voneinander registrieren, ohne einander abzuhaengen.
	 */
	onAbgelehnt: ((nutzlast: unknown) => void) | null = null;

	/** Setzt `onAbgelehnt`; liefert die Abmeldung. */
	registriereAbgelehnt(cb: (nutzlast: unknown) => void): () => void {
		this.onAbgelehnt = cb;
		return () => {
			if (this.onAbgelehnt === cb) this.onAbgelehnt = null;
		};
	}

	/** Setzt `onAdopt`; liefert die Abmeldung (setzt es zurueck). */
	registriereUebernahme(cb: (trip: unknown, phase: 'geholt' | 'wiederholt') => void): () => void {
		this.onAdopt = cb;
		return () => {
			if (this.onAdopt === cb) this.onAdopt = null;
		};
	}

	private _tripId?: string;
	// Issue #2276 S1: die Ressourcenart der Kennung ('trip' | 'vergleich'). Eigenes
	// Feld NEBEN `_tripId` statt eines gemeinsamen `_kennung`-Objekts: mehrere
	// bestehende Testdateien bauen Instanzen per `Object.create(SaveStatus.prototype)`
	// und setzen nur `_tripId` — ein zusammengefasstes Feld haette sie unbemerkt
	// gebrochen.
	private _resourceKind?: NachladeKennung['typ'];

	// Issue #1703 S8 (Staging-Befund BROKEN): die Meldung des letzten ECHTEN
	// Speicherversuchs, solange sie NICHT durch einen erfolgreichen ersetzt
	// wurde. Eigenes Feld statt `error`, weil `setSaving()` `error` bewusst
	// leert — ein zweiter, folgenloser Commit derselben Geste (Diff-Guard
	// liefert keinen Payload) darf den Fehlschlag trotzdem nicht vergessen.
	private _unresolvedError: string | null = null;

	// Issue #2215: ein nicht speicherbarer Zwischenstand steht auf dem Bildschirm.
	// Ein vorgemerkter/laufender Save des letzten GUELTIGEN Stands wird trotzdem
	// geschrieben (kein Datenverlust), meldet aber nie „Gespeichert". Truthy
	// pruefen — Testinstanzen ohne Konstruktor haben hier `undefined`.
	private _offenerZwischenstand = false;

	constructor(kennung?: NachladeKennung) {
		this._tripId = kennung?.id;
		this._resourceKind = kennung?.typ;
	}

	// Issue #1433: `conflict` ist STICKY — er endet nur durch `retryConflict()`
	// (oder Neuladen der Seite). Alle uebrigen Zustandswechsel laufen an ihm vorbei.
	private get _imKonflikt(): boolean {
		return this.state === 'conflict';
	}

	setSaving(): void {
		if (this._imKonflikt) return;
		this.state = 'saving';
		this.error = null;
	}

	setSaved(): void {
		if (this._imKonflikt) return;
		this.error = null;
		// Erst ein ECHTER Erfolg loescht den offenen Fehlschlag (s. markPristine).
		this._unresolvedError = null;
		if (this._offenerZwischenstand) {
			// #2215: Daten sind gesichert, der Bildschirm zeigt aber einen anderen Stand.
			this.state = 'dirty';
			return;
		}
		this.savedAt = new Date();
		this.state = 'idle';
	}

	setDirty(): void {
		if (this._imKonflikt) return;
		this.state = 'dirty';
	}

	/**
	 * Issue #2215: wie setDirty(), aber der Bildschirm zeigt einen NICHT speicherbaren
	 * Zwischenstand. Ein vorgemerkter Save laeuft weiter (Timer/_pendingFn unberuehrt),
	 * setSaved() haelt die Anzeige dann auf `dirty`, bis schedule()/cancel()/markPristine()
	 * den Zwischenstand abloesen.
	 */
	setUnsavedInput(): void {
		if (this._imKonflikt) return;
		this.state = 'dirty';
		this._offenerZwischenstand = true;
	}

	/**
	 * Issue #1269 (b): dirty→idle OHNE savedAt neu zu stempeln — Gegenstück zu
	 * setSaved(). Fuer Faelle, in denen der Zustand ohne echten PUT wieder
	 * "clean" wird (z.B. Baseline-Korrektur einer Mount-Kanonisierung, die
	 * faelschlich dirty gesetzt hatte). savedAt bleibt unangetastet, damit nie
	 * ein frischer "Gespeichert HH:MM"-Zeitstempel ohne echten Speichervorgang
	 * vorgetaeuscht wird.
	 *
	 * Issue #1703 S8 (Staging-Befund BROKEN, Rollback-Klickpfad): "nichts zu
	 * speichern" heisst NICHT "gespeichert", solange der letzte echte Versuch
	 * gescheitert ist. Eine Geste kann mehrere Commits ausloesen (direkter
	 * `onCompareCommit` + Wrapper-Ereignis in CompareTabs.svelte). Auf dem
	 * Fehlerpfad faellt der Zustand durch den Rollback wieder mit dem
	 * gespeicherten Stand zusammen — der zweite Commit findet dann keinen Diff
	 * und landete hier, wodurch er den gerade gesetzten Fehler mit "Gespeichert"
	 * ueberschrieb. Der Nutzer las Erfolg, obwohl der PUT mit 500 scheiterte.
	 */
	markPristine(): void {
		if (this._imKonflikt) return;
		this._offenerZwischenstand = false; // #2215
		// Truthy-Pruefung (nicht `!== null`): Testinstanzen entstehen im Repo per
		// `Object.create(SaveStatus.prototype)` ohne Konstruktor, das Feld ist dort
		// `undefined` — und "kein Fehlschlag bekannt" muss dort dasselbe heissen.
		if (this._unresolvedError) {
			this.state = 'error';
			this.error = this._unresolvedError;
			return;
		}
		this.state = 'idle';
		this.error = null;
	}

	setError(msg: string): void {
		this._unresolvedError = msg;
		if (this._imKonflikt) return;
		this.state = 'error';
		this.error = msg;
		this._unresolvedError = msg;
	}

	async doSave(saveFn: SaveFn, init?: RequestInit): Promise<void> {
		this._pendingFn = null;
		this._timer = null;
		this.setSaving();
		const run = this._ausfuehren(saveFn, init);
		this._inflight = run;
		await run;
		if (this._inflight === run) this._inflight = null;
	}

	private async _ausfuehren(saveFn: SaveFn, init?: RequestInit, imRetry = false): Promise<void> {
		try {
			await saveFn(init);
			this._erledigt(saveFn);
			this.setSaved();
		} catch (e) {
			// Issue #1395 S4: nur ein echter Nebenlaeufigkeits-Konflikt auf einer
			// bekannten Trip bekommt den eigenen Zustand mit Wiederholen-Knopf.
			if ((e as ApiError)?.status === 412 && this._tripId) {
				this.meldeKonflikt(saveFn, e, init);
			} else if (imRetry && this._tripId) {
				// Fix-Loop 1 (F004): eine gescheiterte Wiederholung geht nicht verloren —
				// Eintrag zurueck in die Liste, der Nutzer kann erneut „Nochmal speichern".
				this._merke(saveFn, init);
				markiereKonflikt(this._tripId);
				this.state = 'conflict';
				this.error = extractMessage(e);
			} else {
				this.setError(extractMessage(e));
			}
		}
	}

	/**
	 * Issue #1433: ein Schreiber, der den Controller nicht selbst benutzt (Kopf,
	 * Aktivitaet), meldet seinen 412 hierher. Der Rumpf landet in der Liste und
	 * wird bei „Nochmal speichern" wiederholt.
	 */
	meldeKonflikt(saveFn: SaveFn, e: unknown, init?: RequestInit): void {
		this._merke(saveFn, init);
		const nutzlast = nutzlastVon(saveFn);
		if (nutzlast !== undefined) this.onAbgelehnt?.(nutzlast);
		this.state = 'conflict';
		this.error = extractMessage(e);
	}

	/**
	 * Fix-Loop 2 (#1433, F101/Regel 2): ein erfolgreiches Speichern unter dem Schluessel K
	 * ist die NEUERE Wahrheit dieses Reiters — ein noch offener Eintrag K (aelterer Rumpf)
	 * wird verworfen, sonst spielte „Nochmal speichern" ihn spaeter ueber die neuere Eingabe.
	 * Leert das die Liste im Konflikt, ist nichts mehr zu wiederholen: Markierung loeschen,
	 * Zustand idle (der Server hat den Stand der Eingabe bestaetigt).
	 */
	private _erledigt(saveFn: SaveFn): void {
		const liste = this._lastFailed;
		if (!liste || liste.length === 0) return;
		const key = schluesselVon(saveFn);
		const rest = liste.filter((x) => schluesselVon(x.fn) !== key);
		if (rest.length === liste.length) return;
		this._lastFailed = rest;
		if (rest.length === 0 && this._imKonflikt && this._tripId) {
			loescheKonflikt(this._tripId);
			this.state = 'idle';
		}
	}

	/** Eintrag in die deduplizierte Liste (ein Eintrag je Reiter, der neueste Rumpf gewinnt). */
	private _merke(saveFn: SaveFn, init?: RequestInit): void {
		const liste = (this._lastFailed ??= []);
		const key = schluesselVon(saveFn);
		const idx = liste.findIndex((x) => schluesselVon(x.fn) === key);
		const eintrag = { fn: saveFn, init, nutzlast: nutzlastVon(saveFn) };
		if (idx >= 0) liste[idx] = eintrag;
		else liste.push(eintrag);
	}

	/**
	 * Issue #1395 S4 / #1433: holt den Trip frisch (GET) und wiederholt danach ALLE
	 * gescheiterten Speichervorgaenge. Jeder Rumpf traegt nur seine Eigenfelder.
	 * Der Zustand springt vor dem GET auf `saving` — ein zweiter Klick trifft dann
	 * auf `'saving'` und bricht am Guard ab. Die Konflikt-Markierung der Registry
	 * wird erst nach dem GET gehoben; scheitert ein Eintrag erneut, landet er
	 * wieder in der Liste (Zustand `conflict`).
	 */
	async retryConflict(): Promise<void> {
		const eintraege = this._lastFailed ?? [];
		if (this.state !== 'conflict' || eintraege.length === 0 || !this._tripId || !this._resourceKind) return;
		this._lastFailed = [];
		this.state = 'saving';
		this.error = null;
		// Fix-Loop 4 (F301a): der Stempel von VOR dem GET. Scheitert der Retry, wird er
		// zurueckgelegt — der frische GET-Stempel gehoert zu Daten, die kein offener oder
		// spaeter geoeffneter Reiter hat (Compare: Hub haelt Altstand; Trip: offener Reiter).
		const stempelVorGet = getKnownEtag(this._tripId);
		const lauf = (async () => {
			let geholt: unknown;
			try {
				geholt = await refreshResourceEtagMitTrip(this._tripId!, this._resourceKind!);
			} catch (e) {
				// Die Eingaben (auch die nicht mehr gemounteter Reiter) duerfen nicht
				// verloren gehen: Liste zurueck, Konflikt-Anzeige und -Markierung bleiben
				// (Fix-Loop 1, F004) — der Nutzer kann erneut „Nochmal speichern".
				this._lastFailed = eintraege;
				this.state = 'conflict';
				this.error = extractMessage(e);
				return;
			}
			// AC-19: Trip und Stempel (hat der GET bereits in die Registry gelegt) gemeinsam
			// an die Seite, BEVOR die Konflikt-Markierung faellt und gesendet wird.
			// Fix-Loop 3 (F201): der Stand ist GET ⊕ alle ausstehenden Nutzlasten — nur so
			// zeigt ein spaeter gemounteter Reiter die Eingabe, die gleich gesendet wird.
			this.onAdopt?.(wendeNutzlastenAn(geholt, eintraege), 'geholt');
			loescheKonflikt(this._tripId!);
			// `imWiederholen`: die Speicherfunktionen des Ortsvergleichs setzen bei einem
			// Nicht-412-Fehler ihre Anzeige zurueck — beim Wiederholen darf das nicht
			// passieren, sonst findet der naechste Versuch keinen Unterschied mehr (F101).
			this.imWiederholen = true;
			try {
				for (const { fn, init } of eintraege) await this._ausfuehren(fn, init, true);
			} finally {
				this.imWiederholen = false;
			}
			if ((this._lastFailed?.length ?? 0) > 0) {
				// Gescheiterter (auch nur teilweise gescheiterter) Retry: einfachste sichere
				// Variante — IMMER der Stempel von vor dem GET, auch wenn ein Teil-PUT einen
				// neueren geliefert hat. Jeder Save aus einem Reiter mit veraltetem Stand
				// bekommt so 412; erst der naechste „Nochmal speichern" holt frisch.
				if (stempelVorGet !== undefined) setKnownEtag(this._tripId!, stempelVorGet);
				// F502: kein Stempel vor dem GET => NICHT verwerfen (ein Save ginge sonst ohne
				// If-Match raus). Platzhalter, der nie zu einem Server-Stand passt => 412.
				else setKnownEtag(this._tripId!, KEIN_STEMPEL_PLATZHALTER);
				markiereKonflikt(this._tripId!);
				this.state = 'conflict';
				return;
			}
			// Nur nach VOLLEM Erfolg (idle, nichts ausstehend, Liste leer); sonst bleibt der
			// offene Reiter unangetastet (F101: kein Neuaufbau ueber sichtbare Eingabe).
			if (this.state === 'idle' && !this.hasPending && (this._lastFailed?.length ?? 0) === 0) {
				this.onAdopt?.(geholt, 'wiederholt');
			}
		})();
		this._inflight = lauf;
		await lauf;
		if (this._inflight === lauf) this._inflight = null;
	}

	/** Returns true if a save is pending (debounced or deferred, not yet flushed).
	 *  Bug #1389: geprüft wird die ausstehende Funktion, nicht der Timer — ein per
	 *  `defer()` zurückgestellter Save hat bewusst keinen Timer, muss aber beim
	 *  Verlassen der Seite geflusht werden (#1376). Debounce-Weg unverändert. */
	get hasPending(): boolean {
		return this._pendingFn !== null;
	}

	/** Issue #2317 (AC-6): der gerade im Netz laufende Speichervorgang, oder null.
	 *  „Aktualisieren" wartet ihn ab, bevor die neue Fassung die Seite neu laedt —
	 *  sonst bricht das Neuladen einen regulaeren PUT ab. */
	get laufendeSpeicherung(): Promise<void> | null {
		return this._inflight ?? null;
	}

	/** Schedule a debounced save (700ms default). Calling again cancels previous timer.
	 *  SOFORT setSaving() — damit der Indikator nie "idle" (Gespeichert ✓) zeigt,
	 *  während eine ungespeicherte Änderung im Debounce-Fenster wartet (AC-1). */
	schedule(saveFn: SaveFn, ms = 700): void {
		this._offenerZwischenstand = false; // #2215: neue gueltige Eingabe ueberholt den Zwischenstand
		this.setSaving(); // bei offenem Konflikt ein No-op (#1433)
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
		this._offenerZwischenstand = false; // #2215
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

export function createSaveStatus(kennung?: NachladeKennung): SaveStatus {
	return new SaveStatus(kennung);
}
