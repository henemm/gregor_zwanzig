<script lang="ts">
    import { Checkbox } from '$lib/components/ui/checkbox';

    let {
        quiet_from = $bindable<string | undefined>(undefined),
        quiet_to   = $bindable<string | undefined>(undefined),
    }: { quiet_from?: string; quiet_to?: string } = $props();

    let enabled = $state(quiet_from !== undefined && quiet_to !== undefined);

    function toggleEnabled() {
        enabled = !enabled;
        if (!enabled) {
            quiet_from = undefined;
            quiet_to = undefined;
        }
    }

    let midnightWrap = $derived(
        enabled && !!quiet_from && !!quiet_to && quiet_from > quiet_to
    );
</script>

<div class="quiet-card" data-testid="alert-quiet-hours-card">
    <div class="header-row">
        <h4 class="card-title">Stille Stunden</h4>
        <Checkbox
            checked={enabled}
            onchange={toggleEnabled}
            data-testid="alert-quiet-hours-toggle"
        >Aktiv</Checkbox>
    </div>
    {#if enabled}
        <div class="time-row">
            <label>
                Von
                <input
                    type="time"
                    bind:value={quiet_from}
                    data-testid="alert-quiet-from"
                    class="time-input"
                />
            </label>
            <label>
                Bis
                <input
                    type="time"
                    bind:value={quiet_to}
                    data-testid="alert-quiet-to"
                    class="time-input"
                />
            </label>
        </div>
        {#if midnightWrap}
            <p class="midnight-hint" data-testid="alert-quiet-midnight-hint">
                Stille Stunden über Mitternacht ({quiet_from} bis {quiet_to} des nächsten Tages).
            </p>
        {/if}
    {/if}
</div>

<style>
    .quiet-card {
        padding: 1rem;
        border: 1px solid var(--g-ink-faint);
        border-radius: 0.5rem;
        background: var(--g-surface-1, #fff);
    }
    .header-row {
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: 0.5rem;
    }
    .card-title { font-size: 0.875rem; font-weight: 600; margin: 0; }
    .toggle-label { display: inline-flex; align-items: center; gap: 0.375rem; font-size: 0.875rem; cursor: pointer; }
    .time-row { display: flex; gap: 1rem; flex-wrap: wrap; }
    .time-row label { display: flex; align-items: center; gap: 0.5rem; font-size: 0.875rem; }
    .time-input { min-height: 36px; padding: 0.25rem 0.5rem; border: 1px solid var(--g-ink-faint); border-radius: 0.25rem; }
    .midnight-hint { margin: 0.5rem 0 0; font-size: 0.8125rem; color: var(--g-ink-muted); font-style: italic; }
</style>
