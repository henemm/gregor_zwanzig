<script lang="ts">
	// LTChannelPicker — Issue #1232 Scheibe 3a: geteilter Kanal-Umschalter
	// des LayoutTab-Organism (context="route"|"vergleich").
	//
	// Wählt den Kanal, für den Editor + Vorschau + Kappungs-Hinweis gezeigt
	// werden. Testid-Kompatibilität: `channel-tab-{id}` UND `data-channel={id}`
	// (bestehende Compare-Selektoren überleben — Issue #681/#1097).
	//
	// Spec: docs/specs/modules/layout_tab_vergleich.md (Implementation Details §1)

	import { LT_CHANNELS, ltBadge, type ChannelId } from './ltChannels';

	interface Props {
		channel: ChannelId;
		overflow?: Partial<Record<ChannelId, number>>;
		dense?: boolean;
	}
	let { channel = $bindable('email'), overflow = {}, dense = false }: Props = $props();

	// Factory-Pattern (Safari-Closure-Schutz, CLAUDE.md).
	function makeSelectHandler(id: ChannelId) {
		return function selectLtChannel() {
			channel = id;
		};
	}
</script>

<div class="lt-channel-picker" class:dense data-testid="lt-channel-picker">
	{#each LT_CHANNELS as ch (ch.id)}
		<button
			type="button"
			class="lt-channel-tab"
			class:active={channel === ch.id}
			data-testid={`channel-tab-${ch.id}`}
			data-channel={ch.id}
			onclick={makeSelectHandler(ch.id)}
		>
			<span class="lt-ch-label">{ch.label}</span>
			<span class="lt-ch-badge mono">{ltBadge(ch.max)}</span>
			{#if overflow[ch.id]}
				<span class="lt-ch-overflow mono">−{overflow[ch.id]}</span>
			{/if}
		</button>
	{/each}
</div>

<style>
	.lt-channel-picker {
		display: flex;
		gap: 4px;
	}
	.lt-channel-picker.dense {
		gap: 6px;
	}
	.lt-channel-tab {
		flex: 0 0 auto;
		display: inline-flex;
		align-items: center;
		justify-content: center;
		gap: 6px;
		padding: 7px 12px;
		font-size: 13px;
		font-weight: 500;
		font-family: var(--g-font-sans);
		border: 1px solid var(--g-rule);
		border-radius: var(--g-radius-md, 6px);
		background: transparent;
		color: var(--g-ink-3);
		cursor: pointer;
	}
	.lt-channel-picker.dense .lt-channel-tab {
		flex: 1;
		padding: 10px 8px;
	}
	.lt-channel-tab.active {
		font-weight: 600;
		border-color: var(--g-ink);
		border-bottom: 2px solid var(--g-accent);
		background: var(--g-card);
		color: var(--g-ink);
	}
	.lt-ch-badge {
		font-size: 10.5px;
		font-weight: 600;
		color: var(--g-ink-4);
	}
	.lt-channel-tab.active .lt-ch-badge {
		color: var(--g-accent-deep);
	}
	.lt-ch-overflow {
		font-size: 9.5px;
		font-weight: 600;
		padding: 1px 5px;
		border-radius: 999px;
		background: rgba(192, 138, 26, 0.15);
		color: var(--g-warn-deep, #8a6210);
	}
</style>
