<script lang="ts">
    let { cooldown_minutes = $bindable<number | undefined>(undefined) }: {
        cooldown_minutes?: number;
    } = $props();
</script>

<div class="cooldown-card" data-testid="alert-cooldown-card">
    <h4 class="card-title">Mindestabstand zwischen Alerts</h4>
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
        <span class="unit">Minuten</span>
    </div>
    <p class="hint">
        {#if cooldown_minutes === 0}
            Kein Limit — Alerts werden immer sofort gesendet.
        {:else if cooldown_minutes}
            Nach jedem Alert werden {cooldown_minutes} Minuten gewartet.
        {:else}
            Standard: 120 Minuten (globaler Default).
        {/if}
    </p>
</div>

<style>
    .cooldown-card {
        padding: var(--g-s-4);
        border: 1px solid var(--g-ink-faint);
        border-radius: var(--g-radius-md);
        background: var(--g-surface-1, #fff);
    }
    .card-title {
        font-size: var(--g-text-sm);
        font-weight: 600;
        margin: 0 0 var(--g-s-2);
    }
    .input-row {
        display: flex;
        align-items: center;
        gap: var(--g-s-2);
    }
    .cooldown-input {
        width: 80px;
        min-height: 36px;
        padding: var(--g-s-1) var(--g-s-2);
        border: 1px solid var(--g-ink-faint);
        border-radius: var(--g-radius-sm);
    }
    .unit { font-size: var(--g-text-sm); color: var(--g-ink-muted); }
    .hint { margin: var(--g-s-2) 0 0; font-size: var(--g-text-xs); color: var(--g-ink-muted); }
</style>
