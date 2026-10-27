<script lang="ts">
	// Mobile-Shell S2 — Rücksprung-Link im Inhalt (ersetzt `leftIcon: back` der
	// abgeschafften TopAppBar). Soll: Design-Canvas „Gregor Mobile Shell",
	// Artboard „Unterseite": Mono-Caps 12 px, 36 px Touch-Höhe, Chevron links,
	// um 8 px nach links ausgerückt, damit der Text bündig mit dem Eyebrow steht.
	// Konzept: docs/design-requests/mobile_shell_ohne_topbar.md §2/§3.
	interface Props {
		href: string;
		label: string;
		ariaLabel?: string;
		// Gesetzt ⇒ <button> ohne href: der Aufrufer steuert die Navigation selbst
		// (z.B. Abbruch ohne Autosave in /trips/new).
		onclick?: () => void;
	}

	let { href, label, ariaLabel = undefined, onclick = undefined }: Props = $props();
</script>

{#snippet inhalt()}
	<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M15 6l-6 6 6 6" /></svg>
	{label}
{/snippet}

{#if onclick}
	<button
		type="button"
		data-testid="back-link"
		class="mono back-link"
		aria-label={ariaLabel ?? `Zurück: ${label}`}
		{onclick}
	>
		{@render inhalt()}
	</button>
{:else}
	<a
		{href}
		data-testid="back-link"
		class="mono back-link"
		aria-label={ariaLabel ?? `Zurück: ${label}`}
	>
		{@render inhalt()}
	</a>
{/if}

<style>
	.back-link {
		display: inline-flex;
		align-items: center;
		gap: 4px;
		align-self: flex-start;
		height: 36px;
		margin-left: -8px;
		padding: 0 10px 0 6px;
		border-radius: var(--g-r-pill);
		text-decoration: none;
		color: var(--g-ink-2); /* 8:1 auf Papier — lesbar bei schwierigem Licht */
		font-size: 12px;
		font-weight: 500;
		letter-spacing: 0.06em;
		text-transform: uppercase;
	}
	button.back-link {
		border: none;
		background: transparent;
		cursor: pointer;
		font-family: inherit;
	}
	.back-link:hover,
	.back-link:focus-visible {
		background: var(--g-accent-tint);
		color: var(--g-ink);
	}
</style>
