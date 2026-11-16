<script lang="ts">
	// Issue #758 — SaveIndicator Atom.
	// #2954 (ADR-0120): schlichter Inline-Text in der Kopfleiste (HubKopf .hub-actions, vor dem
	// Drei-Punkte-Menü) statt festem Overlay unten rechts. Stabile aria-live-Region, bleibt immer
	// im DOM; nur der Inhalt wechselt.
	// Prop: controller — eine SaveStatus-Instanz (nie global singleton — AC-6).
	import type { SaveStatus } from '$lib/stores/saveStatusStore.svelte';
	// Issue #2653 (i18n F4): Zustandstexte aus dem Katalog (nav.*); die Uhrzeit
	// bleibt ein eigenes <span class="save-time"> (Spec A1).
	import { t } from '$lib/i18n';
	import Dot from '$lib/components/ui/dot/Dot.svelte';

	interface Props {
		controller: SaveStatus;
	}
	let { controller }: Props = $props();

	/** #2954 AC-3: „Gespeichert" steht 5 s nach dem Speichern, dann wird die Region leer. */
	const ERFOLG_MS = 5000;
	let abgelaufen = $state(false);

	// Jeder neue Speichervorgang (neues savedAt) startet den Timer neu; gemessen ab savedAt,
	// damit ein späterer Rückfall dirty → idle (ohne neues savedAt) den Text nicht verlängert.
	// Timer wird bei jedem Neulauf und beim Abbau aufgeräumt. SSR: Effekte laufen nicht.
	$effect(() => {
		const gespeichert = controller.savedAt;
		const zustand = controller.state;
		abgelaufen = false;
		if (zustand !== 'idle' || !gespeichert) return;
		const rest = ERFOLG_MS - (Date.now() - gespeichert.getTime());
		if (rest <= 0) {
			abgelaufen = true;
			return;
		}
		const id = setTimeout(() => (abgelaufen = true), rest);
		return () => clearTimeout(id);
	});

	/** #2954 Fix-Loop 1 (F002): Region ohne sichtbaren Text — bleibt im DOM, nimmt aber keinen Platz. */
	const leer = $derived(controller.state === 'idle' && !(controller.savedAt && !abgelaufen));

	// Issue #880: SSR-sichere HH:MM-Formatierung (keine Locale-abhängigen Date-Methoden).
	function formatTime(d: Date): string {
		const h = d.getHours();
		const m = d.getMinutes();
		return String(h).padStart(2, '0') + ':' + String(m).padStart(2, '0');
	}
</script>

<span
	data-testid="save-indicator"
	data-state={controller.state}
	aria-live="polite"
	class="save-indicator"
	class:save-indicator--idle={controller.state === 'idle'}
	class:save-indicator--dirty={controller.state === 'dirty'}
	class:save-indicator--saving={controller.state === 'saving'}
	class:save-indicator--error={controller.state === 'error'}
	class:save-indicator--leer={leer}
>
	{#if controller.state === 'idle'}
		<!-- #2954 AC-4: beim Öffnen ohne Speichern leer — Text erst nach echtem Speichern (savedAt). -->
		{#if controller.savedAt && !abgelaufen}
			<!-- #2881 R3 (ADR-0111 Punkt 7): Dot + Text statt ✓ -->
			<Dot tone="good" size="xs" />
			<span>{$t('nav.gespeichert')}</span>
			<span class="save-time">{formatTime(controller.savedAt)}</span>
		{/if}
	{:else if controller.state === 'dirty'}
		<span class="save-indicator__icon" aria-hidden="true">●</span>
		<span>{$t('nav.nicht_gespeichert')}</span>
	{:else if controller.state === 'saving'}
		<span class="save-indicator__spinner" aria-hidden="true"></span>
		<span>{$t('nav.speichere')}</span>
	{:else if controller.state === 'conflict'}
		<span class="save-indicator__icon" aria-hidden="true">!</span>
		<span>{controller.error ?? $t('nav.konflikt')}</span>
		<button type="button" class="save-indicator__retry" onclick={() => controller.retryConflict()}>
			{$t('nav.nochmal_speichern')}
		</button>
	{:else if controller.state === 'error'}
		<span class="save-indicator__icon" aria-hidden="true">!</span>
		<span>{controller.error ? $t('nav.speicherfehler_mit', { fehler: controller.error }) : $t('nav.speicherfehler')}</span>
	{/if}
</span>

<style>
	/* #2954 (ADR-0120): Inline-Text in der Kopfleiste, kein Overlay, kein Hintergrund.
	   Ausblenden des Erfolgs per JS-Timer (5 s) statt Abblend-Animation; Fehler/Konflikt
	   bleiben dauerhaft. Bricht bei Platzmangel innerhalb der Aktionen um (#2837 AC-8). */
	.save-indicator {
		display: inline-flex;
		align-items: center;
		flex-wrap: wrap;
		gap: 5px;
		font-size: 12.5px;
		font-family: var(--g-font-mono, ui-monospace, monospace);
		letter-spacing: 0.02em;
		font-weight: 500;
		min-width: 0;
	}
	/* #2954 Fix-Loop 1 (F002): leere Region aus dem Fluss nehmen — kein Flex-Kind, also kein
	   gap-Abstand neben dem Kebab und keine leere Zusatzzeile am Handy. Sie bleibt im DOM
	   (aria-live, data-state), hat aber keine Größe. */
	.save-indicator--leer {
		position: absolute;
	}

	.save-indicator--idle {
		color: var(--g-good);
	}
	.save-time {
		color: var(--g-ink-3);
		font-weight: 400;
	}
	.save-indicator--dirty {
		color: var(--g-warn-fg);
	}
	.save-indicator--saving {
		color: var(--g-ink-3);
	}
	/* Fehler-Zustand: dauerhaft sichtbar (#880 AC-4 bleibt gültig). */
	.save-indicator--error {
		color: var(--g-danger-fg);
	}

	/* Konflikt-Zustand: gleiche Signalfarbe wie der Fehler, dauerhaft sichtbar. */
	.save-indicator[data-state='conflict'] {
		color: var(--g-danger-fg);
	}

	.save-indicator__retry {
		font: inherit;
		color: inherit;
		background: transparent;
		border: 1px solid currentColor;
		border-radius: 3px;
		padding: 1px 6px;
		cursor: pointer;
	}

	.save-indicator__icon {
		font-size: 11px;
		line-height: 1;
	}

	/* Spinner: CSS-only, no bits-ui dependency */
	.save-indicator__spinner {
		display: inline-block;
		width: 10px;
		height: 10px;
		border: 1.5px solid var(--g-ink-4);
		border-top-color: var(--g-ink-3);
		border-radius: 50%;
		animation: gz-spin 600ms linear infinite;
		flex-shrink: 0;
	}
	@keyframes gz-spin {
		to { transform: rotate(360deg); }
	}
</style>
