<script lang="ts">
	// Issue #3319 (AC-13, Spec 1.2) — Bildergalerie der oeffentlichen Funktionsseiten.
	// Baut auf dem Dialog-Grundbaustein des Projekts auf (bits-ui Dialog, wie
	// ui/dialog und ConfirmDialog): Fokusfalle, Esc, Scroll-Sperre und Portal kommen
	// von dort, nichts davon ist hier nachgebaut. Eigene Darstellung, weil die Galerie
	// den ganzen Bildschirm nutzt (Bild hoechstens Fenstergroesse).
	// Bedienung: Vor/Zurueck-Schaltflaechen, Pfeiltasten, Wischen; Schliessen per X,
	// Esc und Klick neben das Bild; danach Fokus zurueck auf das angeklickte Bild
	// (`ausloeser`). Am Rand nicht umlaufend (galerie.ts).
	// Ohne Klick ist nichts gerendert, es laedt also kein zusaetzliches Bild; die
	// Galerie zeigt dieselbe Datei wie die Seite.
	import { Dialog } from 'bits-ui';
	import { locale, t } from '$lib/i18n';
	import { bildQuelle, type Bild } from './inhalt';
	import {
		GALERIE_TEXTE,
		blaettern,
		naechsterIndex,
		tasteZuRichtung,
		vorherigerIndex,
		wischRichtung,
		zaehler,
		type Richtung
	} from './galerie';

	let {
		bilder,
		index = $bindable(null),
		ausloeser = null
	}: { bilder: readonly Bild[]; index?: number | null; ausloeser?: HTMLElement | null } = $props();

	const n = $derived(bilder.length);
	const offen = $derived(index !== null && n > 0);
	const i = $derived(Math.min(Math.max(index ?? 0, 0), Math.max(n - 1, 0)));
	const bild = $derived(bilder[i]);
	const q = $derived(bild ? bildQuelle(bild.name, $locale === 'en' ? 'en' : 'de') : null);
	const kannZurueck = $derived(vorherigerIndex(i, n) !== null);
	const kannVor = $derived(naechsterIndex(i, n) !== null);

	function gehe(r: Richtung | null): void {
		if (index !== null) index = blaettern(i, n, r);
	}
	function schliessen(): void {
		index = null;
	}
	function taste(e: KeyboardEvent): void {
		const r = tasteZuRichtung(e.key);
		if (!r) return;
		e.preventDefault();
		gehe(r);
	}
	let wischStart: { x: number; y: number } | null = null;
	function wischBeginn(e: TouchEvent): void {
		const p = e.changedTouches[0];
		wischStart = p ? { x: p.clientX, y: p.clientY } : null;
	}
	function wischEnde(e: TouchEvent): void {
		const p = e.changedTouches[0];
		if (wischStart && p) gehe(wischRichtung(p.clientX - wischStart.x, p.clientY - wischStart.y));
		wischStart = null;
	}
	/** Klick neben das Bild: nur auf die leeren Flaechen (data-daneben), nicht auf Bild/Bedienelemente/Text. */
	function klick(e: MouseEvent): void {
		if (e.target instanceof HTMLElement && e.target.dataset.daneben !== undefined) schliessen();
	}
</script>

<Dialog.Root
	open={offen}
	onOpenChange={(o) => {
		if (!o) schliessen();
	}}
>
	<Dialog.Portal>
		<Dialog.Content
			aria-label={$t(GALERIE_TEXTE.titel)}
			onkeydown={taste}
			onclick={klick}
			ontouchstart={wischBeginn}
			ontouchend={wischEnde}
			onCloseAutoFocus={(e) => {
				e.preventDefault();
				ausloeser?.focus();
			}}
		>
			{#snippet child({ props })}
				<div {...props} class="galerie" data-testid="galerie" data-daneben>
					<div class="kopf" data-daneben>
						<Dialog.Close>
							{#snippet child({ props: p })}
								<button {...p} type="button" class="knopf" data-testid="galerie-schliessen" aria-label={$t(GALERIE_TEXTE.schliessen)}>
									<span aria-hidden="true">✕</span>
								</button>
							{/snippet}
						</Dialog.Close>
					</div>
					<div class="buehne" data-daneben>
						{#if q && bild}
							<img src={q.src} alt={$t(bild.alt)} width={q.width} height={q.height} decoding="async" data-testid="galerie-bild" />
						{/if}
					</div>
					<div class="fuss" data-daneben>
						{#if bild}
							<Dialog.Description>
								{#snippet child({ props: p })}
									<p {...p} class="beschriftung" data-testid="galerie-beschriftung">{$t(bild.caption)}</p>
								{/snippet}
							</Dialog.Description>
						{/if}
						<div class="steuerung" data-daneben>
							<button
								type="button"
								class="knopf"
								data-testid="galerie-zurueck"
								aria-label={$t(GALERIE_TEXTE.zurueck)}
								disabled={!kannZurueck}
								onclick={() => gehe('zurueck')}
							>
								<span aria-hidden="true">‹</span>
							</button>
							<span
								class="zaehler"
								data-testid="galerie-zaehler"
								role="status"
								aria-label={$t(GALERIE_TEXTE.position, { n: i + 1, m: n })}>{zaehler(i, n)}</span
							>
							<button
								type="button"
								class="knopf"
								data-testid="galerie-vor"
								aria-label={$t(GALERIE_TEXTE.vor)}
								disabled={!kannVor}
								onclick={() => gehe('vor')}
							>
								<span aria-hidden="true">›</span>
							</button>
						</div>
					</div>
				</div>
			{/snippet}
		</Dialog.Content>
	</Dialog.Portal>
</Dialog.Root>

<style>
	.galerie {
		position: fixed;
		inset: 0;
		z-index: 60;
		display: flex;
		flex-direction: column;
		gap: var(--g-s-2);
		padding: var(--g-s-3);
		box-sizing: border-box;
		background: var(--g-ink);
		color: var(--g-card);
		overflow: hidden;
	}
	.kopf {
		display: flex;
		justify-content: flex-end;
	}
	.buehne {
		flex: 1;
		min-height: 0;
		min-width: 0;
		display: flex;
		align-items: center;
		justify-content: center;
	}
	.buehne img {
		display: block;
		max-width: 100%;
		max-height: 100%;
		width: auto;
		height: auto;
		object-fit: contain;
		border-radius: var(--g-r-3);
		background: var(--g-card);
	}
	.fuss {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: var(--g-s-2);
		min-width: 0;
	}
	.beschriftung {
		margin: 0;
		max-width: 70ch;
		text-align: center;
		font-size: var(--g-text-md);
		font-weight: 600;
		overflow-wrap: break-word;
	}
	.steuerung {
		display: flex;
		align-items: center;
		gap: var(--g-s-4);
	}
	.zaehler {
		min-width: var(--g-s-12);
		text-align: center;
		font-variant-numeric: tabular-nums;
	}
	.knopf {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		min-width: var(--g-tap-min);
		min-height: var(--g-tap-min);
		padding: 0 var(--g-s-3);
		border: 1px solid var(--g-card);
		border-radius: var(--g-r-pill);
		background: var(--g-card);
		color: var(--g-ink);
		font-size: var(--g-text-xl);
		line-height: 1;
		cursor: pointer;
	}
	.knopf:disabled {
		opacity: 0.35;
		cursor: default;
	}
	.knopf:focus-visible {
		outline: var(--g-size-3px) solid var(--g-card);
		outline-offset: var(--g-size-2px);
	}
</style>
