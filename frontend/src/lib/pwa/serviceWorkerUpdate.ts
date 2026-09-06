// Update erst auf Nachfrage (Issue #2128, AC-8/AC-9/AC-10).
// Spec: docs/specs/modules/pwa_installierbar_offline_start.md · ADR-0061
//
// Gekapselt, damit der Ablauf ohne Layout und ohne Browser-Neustart pruefbar
// ist. `registration` und `container` werden hereingereicht statt aus
// `navigator` gegriffen -- so kann der Nachweis echte EventTarget-Doppel
// einsetzen (kein Mock: echte Ereignisse, echtes Verhalten).

export interface ServiceWorkerUpdateOptions {
	registration: ServiceWorkerRegistration;
	container: ServiceWorkerContainer;
	/** Wird gerufen, wenn eine NEUE Fassung bereitliegt (nicht bei Erstinstallation). */
	onUpdateReady: () => void;
	/** Neuladen nach dem Wechsel der Kontrolle. */
	reload: () => void;
}

export interface ServiceWorkerUpdateSteuerung {
	/** Uebernahme anstossen: der wartende Worker bekommt SKIP_WAITING. */
	applyUpdate: () => void;
}

export function initServiceWorkerUpdate({
	registration,
	container,
	onUpdateReady,
	reload
}: ServiceWorkerUpdateOptions): ServiceWorkerUpdateSteuerung {
	let bereitsNeugeladen = false;
	let uebernahmeAngestossen = false;
	/** Lief beim Laden dieser Seite schon eine Fassung? */
	const liefSchonEineFassung = !!container.controller;

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
		bereitsNeugeladen = true;
		reload();
	});

	function beobachte(worker: ServiceWorker | null): void {
		if (!worker) return;
		let gemeldet = false;
		const pruefe = () => {
			// Ohne `controller` ist es die Erstinstallation -- da gibt es keine
			// alte Fassung, ein Update-Hinweis waere falsch.
			if (gemeldet || worker.state !== 'installed' || !container.controller) return;
			gemeldet = true;
			onUpdateReady();
		};
		worker.addEventListener('statechange', pruefe);
		pruefe();
	}

	registration.addEventListener('updatefound', () => beobachte(registration.installing));

	// Beim Einhaengen kann bereits eine Fassung warten (Update in einem frueheren
	// Besuch bemerkt) -- dann ist `updatefound` laengst gefeuert.
	if (registration.waiting && container.controller) onUpdateReady();

	return {
		applyUpdate() {
			uebernahmeAngestossen = true;
			const wartend = registration.waiting ?? registration.installing;
			wartend?.postMessage({ type: 'SKIP_WAITING' });
		}
	};
}
