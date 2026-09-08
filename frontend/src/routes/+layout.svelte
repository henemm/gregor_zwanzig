<script lang="ts">
	import '../app.css';
	import { page } from '$app/state';
	import { browser } from '$app/environment';
	import { Sidebar } from '$lib/components/ui/sidebar';
	import TopAppBar from '$lib/components/ui/sidebar/TopAppBar.svelte';
	import BottomNav from '$lib/components/ui/sidebar/BottomNav.svelte';
	// Issue #1256 Scheibe 8d — Seiten befüllen die EINE globale Design-Kopfleiste
	// über diesen Store (title/eyebrow/leftIcon/backHref/right); Default (leer)
	// = unverändertes Wordmark/Bell/Plus-Erscheinungsbild auf allen Seiten.
	import { topAppBarStore } from '$lib/stores/topAppBar.svelte';
	// Issue #2128 — die beiden app-weiten Systemhinweise der PWA. Sie haengen
	// BEWUSST ausserhalb des Chrome-Blocks: der Update-Hinweis gehoert auch auf
	// die Anmeldeseite, die ohne TopAppBar/Sidebar/BottomNav rendert.
	import Toast from '$lib/components/mobile/Toast.svelte';
	import { initServiceWorkerUpdate } from '$lib/pwa/serviceWorkerUpdate';
	// Issue #2131 — Offline-Ansicht mit Stand-Kennzeichnung.
	import { afterNavigate } from '$app/navigation';
	import { initOfflineStand, standAnwenden } from '$lib/pwa/offlineStand';
	import OfflineSperre from '$lib/components/shared/OfflineSperre.svelte';

	let { children, data } = $props();

	let updateBereit = $state(false);
	let updateUebernehmen: (() => void) | null = null;
	let iosHinweisSichtbar = $state(false);

	/** Geraeteweiter Merker (keine nutzerbezogene Angabe, ADR-0003 unberuehrt). */
	const IOS_HINWEIS_MERKER = 'gz-ios-install-hint';

	/** Nur Safari auf iOS und nur, wenn die App NICHT vom Startbildschirm laeuft. */
	function iosHinweisFaellig(): boolean {
		if (localStorage.getItem(IOS_HINWEIS_MERKER) === 'gesehen') return false;
		const ua = navigator.userAgent;
		const istIos = /iPad|iPhone|iPod/.test(ua);
		const istSafari = /Safari/.test(ua) && !/CriOS|FxiOS|EdgiOS|OPiOS/.test(ua);
		const vomStartbildschirm =
			window.matchMedia('(display-mode: standalone)').matches ||
			(navigator as Navigator & { standalone?: boolean }).standalone === true;
		return istIos && istSafari && !vomStartbildschirm;
	}

	function iosHinweisSchliessen() {
		iosHinweisSichtbar = false;
		localStorage.setItem(IOS_HINWEIS_MERKER, 'gesehen');
	}

	const darkVars: Record<string, string> = {
		'--color-background': 'oklch(0.145 0 0)',
		'--color-foreground': 'oklch(0.95 0 0)',
		'--color-popover': 'oklch(0.18 0 0)',
		'--color-popover-foreground': 'oklch(0.95 0 0)',
		'--color-card': 'oklch(0.18 0 0)',
		'--color-card-foreground': 'oklch(0.95 0 0)',
		'--color-muted': 'oklch(0.22 0 0)',
		'--color-muted-foreground': 'oklch(0.60 0 0)',
		'--color-border': 'oklch(0.28 0 0)',
		'--color-input': 'oklch(0.28 0 0)',
		'--color-ring': 'oklch(0.55 0 0)',
		'--color-primary': 'oklch(0.92 0 0)',
		'--color-primary-foreground': 'oklch(0.15 0 0)',
		'--color-accent': 'oklch(0.22 0 0)',
		'--color-accent-foreground': 'oklch(0.92 0 0)',
		'--color-sidebar': 'oklch(0.12 0 0)',
		'--color-sidebar-foreground': 'oklch(0.90 0 0)',
		'--color-sidebar-accent': 'oklch(0.20 0 0)',
	};

	let darkMode = $state(false);
	let mobileMenuOpen = $state(false);

	function applyDarkMode(dark: boolean) {
		const el = document.documentElement;
		if (dark) {
			for (const [key, value] of Object.entries(darkVars)) {
				el.style.setProperty(key, value);
			}
		} else {
			for (const key of Object.keys(darkVars)) {
				el.style.removeProperty(key);
			}
		}
	}

	// Issue #2131: die Stand-Zeile des DOKUMENTS steht schon im ausgelieferten
	// Bytestrom (der Worker schreibt sie beim Ablegen ein). Hier wird sie nur
	// bei einer Client-Navigation nachgefuehrt — dort entsteht kein neues
	// Dokument, und der Stand der vorigen Ansicht bliebe sonst stehen (AC-5).
	if (browser) initOfflineStand();
	afterNavigate(() => standAnwenden());

	if (browser) {
		darkMode = localStorage.getItem('gz-dark') === '1';
		if (darkMode) applyDarkMode(true);

		iosHinweisSichtbar = iosHinweisFaellig();

		// SvelteKit registriert den Worker selbst (config.kit.serviceWorker.register
		// = true) -- hier wird NICHT registriert, sondern nur zugehoert.
		if ('serviceWorker' in navigator) {
			navigator.serviceWorker.ready
				.then((registration) => {
					updateUebernehmen = initServiceWorkerUpdate({
						registration,
						container: navigator.serviceWorker,
						onUpdateReady: () => {
							updateBereit = true;
						},
						reload: () => location.reload()
					}).applyUpdate;
				})
				.catch(() => {});
		}
	}

	function toggleDark() {
		darkMode = !darkMode;
		applyDarkMode(darkMode);
		localStorage.setItem('gz-dark', darkMode ? '1' : '0');
	}

	const publicPages = ['/login', '/register', '/forgot-password', '/reset-password', '/verify-email'];
	const isLogin = $derived(publicPages.includes(page.url.pathname));
	const isWizard = $derived(page.url.pathname.startsWith('/trips/new'));
	// Showcase-Route (#370): ohne App-Chrome (TopAppBar/Sidebar/BottomNav), damit
	// die Brand-Demos die einzigen App-Bausteine auf der Seite sind.
	const isShowcase = $derived(page.url.pathname === '/_design');
</script>

{#if isLogin || isShowcase}
	{@render children()}
{:else}
	<TopAppBar
		bind:mobileMenuOpen
		{darkMode}
		ontoggleDark={toggleDark}
		title={topAppBarStore.fill.title}
		eyebrow={topAppBarStore.fill.eyebrow}
		leftIcon={topAppBarStore.fill.leftIcon}
		backHref={topAppBarStore.fill.backHref}
		right={topAppBarStore.fill.right}
	/>
	<!-- Issue #2131 — sichtbare Begruendung der Bearbeitungssperre; sperrt
	     zugleich die Bedienelemente der Ansicht (ADR-0034: gesperrt und
	     begruendet, nicht versteckt). -->
	<OfflineSperre />
	<div class="flex h-screen">
		<Sidebar
			userId={data.userId}
			displayName={data.displayName}
			currentPath={page.url.pathname}
			{darkMode}
			ontoggleDark={toggleDark}
			bind:mobileMenuOpen
		/>
		<main class="mobile-scroll-pad flex-1 overflow-auto px-4 desktop:p-6 desktop:pt-6">
			{@render children()}
		</main>
	</div>
	{#if !isWizard}
		<BottomNav />
	{/if}
{/if}

<!-- Issue #2128 — Systemhinweise, app-weit und ausserhalb des Chrome-Blocks.
     Der feste Rahmen ist nur der Bezugspunkt fuer die absolut positionierte
     Toast-Optik; er hat selbst keine Hoehe und faengt daher keine Klicks ab. -->
{#if updateBereit}
	<div style="position: fixed; left: 0; right: 0; bottom: 0; z-index: 60;">
		<Toast
			kind="info"
			msg="Neue Version verfügbar"
			hint="Wird erst auf Antippen geladen."
			action="Jetzt aktualisieren"
			onaction={() => updateUebernehmen?.()}
		/>
	</div>
{/if}

{#if iosHinweisSichtbar}
	<div
		data-testid="ios-install-hint"
		role="status"
		style="position: fixed; left: 16px; right: 16px; bottom: 76px; z-index: 61;
		       display: flex; align-items: center; gap: 12px; padding: 12px 16px;
		       border-radius: var(--g-radius-lg, 0.75rem); background: var(--g-ink, #1a1a18);
		       color: var(--g-paper, #f6f4ee); box-shadow: var(--g-elev-3, 0 8px 24px rgba(26,26,24,0.16));
		       font-size: 14px; line-height: 1.4;"
	>
		<div style="flex: 1; min-width: 0;">
			Auf den Startbildschirm legen: unten „Teilen“ antippen, dann „Zum Home-Bildschirm“.
		</div>
		<button
			type="button"
			onclick={iosHinweisSchliessen}
			style="background: transparent; border: none; color: inherit; font-size: 13px;
			       font-weight: 600; text-transform: uppercase; letter-spacing: 0.06em;
			       font-family: var(--g-font-data); cursor: pointer; min-height: 44px; padding: 0 4px;"
		>Schließen</button>
	</div>
{/if}
