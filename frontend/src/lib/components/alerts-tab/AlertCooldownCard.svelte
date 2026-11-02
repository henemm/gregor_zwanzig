<script lang="ts">
	// Issue #586 — Eyebrow statt h4, JSX-konformer Hint-Text, Mono-Input.
	import { Eyebrow } from '$lib/components/atoms';
	import BegriffErklaerung from '$lib/components/molecules/BegriffErklaerung.svelte';
	import { t } from '$lib/i18n';

    let { cooldown_minutes = $bindable<number | undefined>(undefined) }: {
        cooldown_minutes?: number;
    } = $props();
</script>

<div class="cooldown-card" data-testid="alert-cooldown-card">
    <!-- Issue #2521 S1 (AC-11): ⓘ an der Ueberschrift, Hinweistext unten unveraendert. -->
    <div class="eyebrow-row">
        <Eyebrow>{$t('alarme.cooldown.titel')}</Eyebrow>
        <BegriffErklaerung begriff="cooldown" />
    </div>
    <div class="input-row">
        <input
            type="number"
            min="0"
            value={cooldown_minutes ?? ''}
            oninput={(e) => {
                const v = parseInt((e.target as HTMLInputElement).value);
                cooldown_minutes = isNaN(v) ? undefined : v;
            }}
            data-testid="alert-cooldown-input"
            class="cooldown-input"
        />
        <span class="unit">{$t('alarme.cooldown.einheit')}</span>
    </div>
    <p class="hint">
        {$t('alarme.cooldown.hinweis')}
    </p>
</div>

<style>
    .cooldown-card {
        padding: var(--g-s-4);
        border: 1px solid var(--g-ink-faint);
        border-radius: var(--g-radius-md);
        background: var(--g-surface-1, #fff);
    }
    .eyebrow-row { display: flex; align-items: center; gap: 4px; }
    .input-row {
        display: flex;
        align-items: center;
        gap: var(--g-s-2);
        margin-top: var(--g-s-2);
    }
    .cooldown-input {
        width: 80px;
        padding: var(--g-s-2) var(--g-s-3);
        border: 1px solid var(--g-rule);
        border-radius: var(--g-radius-sm);
        font-size: var(--g-text-md);
        font-family: var(--g-font-mono);
    }
    .unit { font-size: var(--g-text-sm); color: var(--g-ink-muted); }
    .hint { margin: var(--g-s-2) 0 0; font-size: var(--g-text-xs); color: var(--g-ink-muted); }

    @media (max-width: 899px) {
        .cooldown-input {
            min-height: 44px;
            font-size: 16px; /* iOS-Zoom-Schutz: <16px löst Auto-Zoom aus */
            width: 100%;
        }
    }
</style>
