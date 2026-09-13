// Update erst auf Nachfrage (Issue #2128, AC-8/AC-9/AC-10) + aktive
// Update-Erkennung (Issue #2316, Epic #2127, Scheibe B).
// Spec: docs/specs/modules/pwa_installierbar_offline_start.md,
//       docs/specs/modules/pwa_update_erkennung.md · ADR-0061
//
// Gekapselt, damit der Ablauf ohne Layout und ohne Browser-Neustart pruefbar
// ist. `registration`/`container` und (#2316) `document`/`window`/`uhr`/
// `timer` werden hereingereicht statt aus den globalen Objekten gegriffen --
// so kann der Nachweis echte EventTarget-Doppel und eine vorgestellte Uhr
// einsetzen (kein Mock: echte Ereignisse, echtes Verhalten).

const DROSSEL_MS = 60_000;
const INTERVALL_MS = 30 * 60_000;
const RUECKFALL_MS = 4_000;

/**
 * #2316 „Später": modul-interner Zustand, KEIN Store, KEINE Persistenz.
 * Setzt sich nur bei einem echten Kaltstart zurueck (Modul-Neuinitialisierung
 * -- ein frischer Seitenaufruf laedt dieses Modul neu und damit dieses `let`
 * neu). Ein zweiter `initServiceWorkerUpdate()`-Aufruf INNERHALB derselben
 * Modul-Instanz teilt sich bewusst denselben Zustand (mehrere Aufrufer in
 * einer Sitzung sollen dieselbe "Später"-Entscheidung sehen).
 */
let spaeterAktiv = false;

export interface Uhr {
	now(): number;
}
export interface Zeitgeber {
	setTimeout(fn: () => void, ms: number): number;
	clearTimeout(id: number): void;
	setInterval(fn: () => void, ms: number): number;
	clearInterval(id: number): void;
}
export interface SichtbarkeitsQuelle {
	readonly visibilityState: string;
	addEventListener(type: string, listener: () => void): void;
}
export interface EreignisQuelle {
	addEventListener(type: string, listener: () => void): void;
}

export interface ServiceWorkerUpdateOptions {
	registration: ServiceWorkerRegistration;
	container: ServiceWorkerContainer;
	/** Wird gerufen, wenn eine NEUE Fassung bereitliegt (nicht bei Erstinstallation). */
	onUpdateReady: () => void;
	/** Neuladen nach dem Wechsel der Kontrolle (oder dem 4s-Rueckfall). */
	reload: () => void;
	/** #2316 — Pruef-Ausloeser/Drossel/Intervall: alle vier zusammen gesetzt. */
	document?: SichtbarkeitsQuelle;
	window?: EreignisQuelle;
	uhr?: Uhr;
	timer?: Zeitgeber;
	/** #2316 — der Worker meldet einen gescheiterten Download vor skipWaiting(). */
	onUpdateFailed?: () => void;
}

export interface ServiceWorkerUpdateSteuerung {
	/** Uebernahme anstossen: der wartende Worker bekommt SKIP_WAITING. */
	applyUpdate: () => void;
	/** #2316 — Hinweis bis zum naechsten Kaltstart ausblenden. */
	spaeter: () => void;
}

export function initServiceWorkerUpdate({
	registration,
	container,
	onUpdateReady,
	reload,
	document: dok,
	window: fenster,
	uhr,
	timer,
	onUpdateFailed
}: ServiceWorkerUpdateOptions): ServiceWorkerUpdateSteuerung {
	let bereitsNeugeladen = false;
	let uebernahmeAngestossen = false;
	/** Lief beim Laden dieser Seite schon eine Fassung? */
	const liefSchonEineFassung = !!container.controller;

	function benachrichtigeFallsErlaubt(): void {
		if (spaeterAktiv) return;
		onUpdateReady();
	}

	// #2316 — Rueckfall-Timer (activated ohne controllerchange -> 4s -> reload).
	let fallbackTimerId: number | null = null;
	function klareFallbackTimer(): void {
		if (fallbackTimerId === null) return;
		timer?.clearTimeout(fallbackTimerId);
		fallbackTimerId = null;
	}

	container.addEventListener('controllerchange', () => {
		// Mehrfachschutz: ohne ihn koennte ein zweites controllerchange eine
		// Neulade-Schleife ausloesen.
		if (bereitsNeugeladen) return;
		// Neu geladen wird nur bei einem echten VERSIONSWECHSEL -- also wenn hier
		// schon eine Fassung lief oder der Nutzer die Uebernahme angestossen hat.
		// Beide Bedingungen sind noetig: beim Erstbesuch uebernimmt der frisch
		// aktivierte Worker die Seite ebenfalls (clients.claim), und eine Seite,
		// die dabei uebernommen wird, war beim Dokumentstart gemessen noch
		// unkontrolliert (#2128, Chromium) -- die erste Bedingung allein wuerde
		// deshalb ausgerechnet den Wechsel nach dem Antippen verschlucken.
		if (!liefSchonEineFassung && !uebernahmeAngestossen) return;
		klareFallbackTimer();
		bereitsNeugeladen = true;
		reload();
	});

	if (onUpdateFailed) {
		container.addEventListener('message', (event: MessageEvent) => {
			const daten = event.data as { type?: string } | undefined;
			if (daten?.type === 'UPDATE_FEHLGESCHLAGEN') onUpdateFailed();
		});
	}

	function beobachte(worker: ServiceWorker | null): void {
		if (!worker) return;
		let gemeldet = false;
		const pruefe = () => {
			// Ohne `controller` ist es die Erstinstallation -- da gibt es keine
			// alte Fassung, ein Update-Hinweis waere falsch.
			if (gemeldet || worker.state !== 'installed' || !container.controller) return;
			gemeldet = true;
			benachrichtigeFallsErlaubt();
		};
		worker.addEventListener('statechange', pruefe);
		pruefe();
	}

	registration.addEventListener('updatefound', () => beobachte(registration.installing));

	// Beim Einhaengen kann bereits eine Fassung warten (Update in einem frueheren
	// Besuch bemerkt) -- dann ist `updatefound` laengst gefeuert.
	if (registration.waiting && container.controller) benachrichtigeFallsErlaubt();

	// #2316 — Pruef-Ausloeser (sichtbar/pageshow/Intervall) + 60s-Drossel + das
	// 30-Minuten-Intervall nur, solange die Seite sichtbar ist.
	let letzterPruef = -Infinity;
	let intervallId: number | null = null;

	function pruefeFallsFaellig(): void {
		// Wartet schon ein Worker, waere ein weiterer Check wirkungslos (und
		// wuerde ihn nur unnoetig erneut anfragen) -- gilt fuer JEDEN Ausloeser
		// hier, auch das Intervall.
		if (registration.waiting) return;
		const jetzt = uhr!.now();
		if (jetzt - letzterPruef < DROSSEL_MS) return;
		letzterPruef = jetzt;
		void registration.update();
	}

	function starteIntervall(): void {
		if (intervallId !== null) return;
		intervallId = timer!.setInterval(pruefeFallsFaellig, INTERVALL_MS);
	}
	function stoppeIntervall(): void {
		if (intervallId === null) return;
		timer!.clearInterval(intervallId);
		intervallId = null;
	}

	if (dok && fenster && uhr && timer) {
		fenster.addEventListener('pageshow', pruefeFallsFaellig);
		dok.addEventListener('visibilitychange', () => {
			if (dok.visibilityState === 'visible') {
				starteIntervall();
				pruefeFallsFaellig();
			} else {
				stoppeIntervall();
			}
		});
		if (dok.visibilityState === 'visible') starteIntervall();
	}

	// #2316 — Rueckfall: sobald der uebernommene Worker `activated` erreicht,
	// 4s auf `controllerchange` warten; bleibt es aus, GENAU EINMAL neu laden.
	// Haengt der Worker in `installed` (Download im Worker gescheitert), wird
	// dieser Zweig nie erreicht -- kein blinder Reload.
	let entferneAktivierungsBeobachtung: (() => void) | null = null;
	function beobachteAktivierung(worker: ServiceWorker): void {
		// Ein erneutes applyUpdate() (Wiederholung nach Fehlschlag) darf keinen
		// zweiten Beobachter auf demselben Worker anhaeufen.
		entferneAktivierungsBeobachtung?.();
		const handler = () => {
			if (worker.state !== 'activated') return;
			worker.removeEventListener('statechange', handler);
			entferneAktivierungsBeobachtung = null;
			klareFallbackTimer();
			fallbackTimerId = timer!.setTimeout(() => {
				fallbackTimerId = null;
				if (bereitsNeugeladen) return;
				bereitsNeugeladen = true;
				reload();
			}, RUECKFALL_MS);
		};
		worker.addEventListener('statechange', handler);
		entferneAktivierungsBeobachtung = () => worker.removeEventListener('statechange', handler);
		handler();
	}

	return {
		applyUpdate() {
			uebernahmeAngestossen = true;
			const wartend = registration.waiting ?? registration.installing;
			wartend?.postMessage({ type: 'SKIP_WAITING' });
			if (wartend && timer) beobachteAktivierung(wartend);
		},
		spaeter() {
			spaeterAktiv = true;
		}
	};
}
