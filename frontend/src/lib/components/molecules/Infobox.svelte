<script lang="ts">
	// Issue #2521 S1 — Infobox „Kannst du überspringen — Standard: …“ oben in
	// jedem ueberspringbaren Anlege-Reiter. Immer sichtbar, kein Schliessen-
	// Knopf, kein Zustand, nichts gespeichert. Text je Kontext und Reiter aus
	// der Lookup-Map (shared/infoboxKeys.ts), keine Kontext-Verzweigung.
	// Spec: docs/specs/modules/begriff_erklaerung_infobox.md (Entscheidung 1-3).
	import { t } from '$lib/i18n';
	import { infoboxKey, type InfoboxKontext, type InfoboxAbschnitt } from '$lib/components/shared/infoboxKeys';

	interface Props {
		reiter: InfoboxAbschnitt;
		context: InfoboxKontext;
	}

	let { reiter, context }: Props = $props();

	const key = $derived(infoboxKey(context, reiter));
</script>

{#if key}
	<aside class="infobox" data-testid="infobox-{reiter}-{context}">{$t(key)}</aside>
{/if}

<style>
	.infobox {
		margin: 0 0 16px;
		padding: 10px 14px;
		border: 1px solid var(--g-rule);
		border-left: 3px solid var(--g-accent);
		border-radius: 6px;
		background: var(--g-card-alt);
		color: var(--g-ink-2);
		font-size: 13px;
		line-height: 1.5;
	}
</style>
