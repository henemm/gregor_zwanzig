/* Screen: Compare-Wizard (Desktop) — 5 Schritte
 * ─────────────────────────────────────────────────────────────────────
 * Reaktion auf PO-Feedback (2026-05-28): Der vorherige Single-Page-Editor
 * (compare v2) verdeckt den Flow. Die User-Story beschreibt eine lineare
 * Einrichtung — und genau die kriegt sie jetzt, parallel zum Trip-Wizard.
 *
 *  1. Vergleich   — Name + Aktivitätsprofil + Region
 *  2. Orte        — Smart-Import + Liste der Kandidaten (3–5)
 *  3. Idealwerte  — was bedeutet "gut" für dich pro Metrik
 *  4. Layout      — was steht im täglichen Briefing, pro Kanal
 *  5. Versand     — Kanäle + Versandzeit + Aktivierung
 *
 * Atomic-Design-Disziplin (CLAUDE.md):
 *   • Verwendet Sidebar, Card, Btn, Input, Switch, Pill, Eyebrow, TopoBg,
 *     Field, ChannelRow aus atoms/molecules/sidebar.
 *   • Lokale Helper sind alle mit Prefix "CW_" benannt (Babel-Scope-Falle:
 *     gleichnamige Funktionen in mehreren <script type="text/babel"> Files
 *     überschreiben einander auf window).
 */

const CW_STEPS = [
  { n: 1, label: "Vergleich",  sub: "Name & Profil" },
  { n: 2, label: "Orte",       sub: "3–5 Kandidaten" },
  { n: 3, label: "Idealwerte", sub: "Was ist gut?" },
  { n: 4, label: "Layout",     sub: "Was steht im Briefing" },
  { n: 5, label: "Versand",    sub: "Kanäle & Aktivierung" },
];

const CW_TITLES = {
  1: "Vergleich — wie heißt dein Briefing?",
  2: "Orte — welche Kandidaten sollen täglich verglichen werden?",
  3: `Idealwerte — was bedeutet für dich „gute Bedingungen“?`,
  4: "Layout — was steht im täglichen Briefing?",
  5: "Versand — wann und wohin?",
};

const CW_CHANNELS = [
  { id: "email",    label: "Email",    maxCols: Infinity, hint: "alles · Empfehlung + Tabelle + Detail" },
  { id: "telegram", label: "Telegram", maxCols: 8,        hint: "max 8 Spalten" },
  { id: "signal",   label: "Signal",   maxCols: 6,        hint: "max 6 Spalten" },
  { id: "sms",      label: "SMS",      maxCols: 0,        hint: "flach · ≤ 140 Zeichen" },
];

function ScreenCompareWizard({ initialStep = 1, prefilled = false, activated = false, mode = "create", editingName }) {
  const isEdit = mode === "edit";
  const [step, setStep] = React.useState(initialStep);
  const [name, setName] = React.useState(
    isEdit ? (editingName || "Skitouren Hochkönig") :
    (prefilled || initialStep > 1 ? "Skitouren Hochkönig" : "")
  );
  const [region, setRegion] = React.useState(isEdit || prefilled || initialStep > 1 ? "Hochkönig · Salzburger Land" : "");
  const [profileId, setProfileId] = React.useState("wintersport");

  // Orte ab Schritt 2 vorgefüllt. Schritt 1 zeigt leeren Setup. Im Edit-Mode immer prefilled.
  const initialPicks = (isEdit || initialStep >= 2) ? ["loc-01", "loc-07", "loc-08", "loc-09", "loc-10"] : [];
  const [pickedIds, setPickedIds] = React.useState(initialPicks);

  // Im Edit-Mode sind ALLE Steps frei navigierbar. Im Create-Mode nur passierte + aktueller + nächster.
  const goto = (n) => {
    if (isEdit) setStep(n);
    else if (n <= step || n === step + 1) setStep(n);
  };
  const next = () => setStep(Math.min(5, step + 1));
  const prev = () => setStep(Math.max(1, step - 1));

  const canAdvance =
    step === 1 ? (name.trim().length > 0) :
    step === 2 ? (pickedIds.length >= 2) :
    true;

  return (
    <div style={{ display: "flex", minHeight: "100%", background: "var(--g-paper)" }}>
      <Sidebar active="compare"/>
      <main style={{ flex: 1, position: "relative" }}>
        <TopoBg opacity={0.14}/>

        <div style={{ position: "relative", padding: "32px 80px 60px", maxWidth: 1180, margin: "0 auto" }}>
          {isEdit ? (
            <CW_EditHeader name={name} step={step} activated={activated}/>
          ) : (
            <React.Fragment>
              <Eyebrow style={{ marginBottom: 8 }}>Schritt {step} von 5 · Neuer Orts-Vergleich</Eyebrow>
              <div style={{
                fontSize: 30, fontWeight: 600, letterSpacing: "-0.02em",
                marginBottom: 28, color: "var(--g-ink)",
                textWrap: "balance",
              }}>
                {CW_TITLES[step]}
              </div>
            </React.Fragment>
          )}

          <CW_Stepper step={step} onStep={goto} allFree={isEdit}/>

          {isEdit && (
            <div style={{
              marginTop: 24, marginBottom: 4,
              fontSize: 22, fontWeight: 600, letterSpacing: "-0.02em",
              color: "var(--g-ink)", textWrap: "balance",
            }}>{CW_TITLES[step]}</div>
          )}

          <div style={{ marginTop: isEdit ? 24 : 40 }}>
            {step === 1 && <CW_StepName name={name} onName={setName} region={region} onRegion={setRegion} profileId={profileId} onProfile={setProfileId}/>}
            {step === 2 && <CW_StepLocations pickedIds={pickedIds} setPickedIds={setPickedIds}/>}
            {step === 3 && <CW_StepIdeals profileId={profileId}/>}
            {step === 4 && <CW_StepLayout pickedIds={pickedIds}/>}
            {step === 5 && <CW_StepSending name={name} pickedIds={pickedIds} activated={activated} editMode={isEdit}/>}
          </div>

          <CW_Footer
            step={step}
            totalSteps={5}
            onPrev={prev}
            onNext={next}
            canAdvance={canAdvance}
            isEdit={isEdit}
          />
        </div>
      </main>
    </div>
  );
}

/* Header für Edit-Mode — Vergleichs-Name als H1, Stepper darunter */
function CW_EditHeader({ name, step, activated }) {
  return (
    <div style={{
      display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 24,
      paddingBottom: 18, marginBottom: 20, borderBottom: "1px solid var(--g-rule-soft)",
    }}>
      <div style={{ minWidth: 0, flex: 1 }}>
        <Eyebrow style={{ marginBottom: 6 }}>
          Orts-Vergleich · bearbeiten
        </Eyebrow>
        <div style={{
          display: "flex", alignItems: "baseline", gap: 12, flexWrap: "wrap",
        }}>
          <div style={{
            fontSize: 30, fontWeight: 600, letterSpacing: "-0.02em", color: "var(--g-ink)",
          }}>{name || "Unbenannter Vergleich"}</div>
          <span className="mono" style={{
            padding: "3px 9px", fontSize: 10.5, letterSpacing: "0.08em",
            textTransform: "uppercase", fontWeight: 600,
            background: activated ? "var(--g-good)" : "var(--g-card)",
            color: activated ? "#fff" : "var(--g-ink-3)",
            border: activated ? "none" : "1px solid var(--g-rule)",
            borderRadius: "var(--g-r-pill)",
          }}>{activated ? "aktiv" : "pausiert"}</span>
        </div>
      </div>
      <div style={{ display: "flex", gap: 8, flexShrink: 0 }}>
        <Btn variant="ghost" size="sm">Briefing-Vorschau</Btn>
        <Btn variant="ghost" size="sm">{activated ? "Pausieren" : "Aktivieren"}</Btn>
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════════
 * STEPPER + FOOTER (Pattern entspricht Trip-Wizard 1:1)
 * ═══════════════════════════════════════════════════════════════════ */

function CW_Stepper({ step, onStep, allFree = false }) {
  return (
    <div style={{ display: "flex", alignItems: "flex-start", gap: 0, padding: "8px 0" }}>
      {CW_STEPS.map((s, i) => {
        // Im Edit-Mode sind alle Schritte gleichwertig: aktueller = current, alle anderen = done (also klickbar + neutral).
        let state;
        if (allFree) state = s.n === step ? "current" : "done";
        else state = s.n < step ? "done" : s.n === step ? "current" : "upcoming";
        return (
          <React.Fragment key={s.n}>
            <CW_Step step={s} state={state} onClick={() => onStep(s.n)} allFree={allFree}/>
            {i < CW_STEPS.length - 1 && (
              <div style={{
                flex: 1, height: 1, marginTop: 21,
                background: (allFree || s.n < step) ? "var(--g-ink-3)" : "var(--g-rule)",
                opacity: (allFree || s.n < step) ? 0.5 : 1, minWidth: 24,
              }}/>
            )}
          </React.Fragment>
        );
      })}
    </div>
  );
}

function CW_Step({ step, state, onClick, allFree = false }) {
  const clickable = state !== "upcoming";
  const cfg = {
    done:     { bg: "var(--g-paper)", border: "1.5px solid var(--g-ink-3)", color: "var(--g-ink-2)" },
    current:  { bg: "var(--g-paper)", border: "2px solid var(--g-accent)",  color: "var(--g-accent)" },
    upcoming: { bg: "var(--g-paper)", border: "1.5px solid var(--g-rule)",  color: "var(--g-ink-4)" },
  }[state];
  // Im Edit-Mode keine ✓-Häkchen — alle Schritte sind Konfiguration, kein Fortschritt.
  const showCheck = state === "done" && !allFree;
  return (
    <div onClick={clickable ? onClick : undefined} style={{
      display: "flex", flexDirection: "column", alignItems: "center", gap: 6,
      cursor: clickable ? "pointer" : "default",
      flexShrink: 0, width: 112, textAlign: "center",
    }}>
      <div style={{
        width: 40, height: 40, borderRadius: "50%",
        display: "flex", alignItems: "center", justifyContent: "center",
        background: cfg.bg, border: cfg.border, color: cfg.color,
        fontSize: showCheck ? 15 : 14, fontWeight: 600,
        fontFamily: showCheck ? "var(--g-font-sans)" : "var(--g-font-mono)",
      }}>{showCheck ? "✓" : step.n}</div>
      <div style={{
        fontSize: 13, fontWeight: 600, marginTop: 2,
        color: state === "current" ? "var(--g-ink)" : state === "done" ? "var(--g-ink-2)" : "var(--g-ink-4)",
      }}>{step.label}</div>
      <div className="mono" style={{
        fontSize: 10, letterSpacing: "0.04em",
        color: state === "current" ? "var(--g-ink-3)" : "var(--g-ink-4)",
      }}>{step.sub}</div>
    </div>
  );
}

function CW_Footer({ step, totalSteps, onPrev, onNext, canAdvance, isEdit = false }) {
  const isFirst = step === 1;
  const isLast = step === totalSteps;

  // Edit-Mode: Speichern jederzeit verfügbar, Zurück/Weiter optional zum Steppern.
  if (isEdit) {
    return (
      <div style={{
        marginTop: 36, paddingTop: 20, borderTop: "1px solid var(--g-rule)",
        display: "grid", gridTemplateColumns: "1fr auto 1fr", alignItems: "center", gap: 12,
      }}>
        <div style={{ display: "flex", gap: 8 }}>
          {!isFirst && <Btn variant="ghost" size="md" onClick={onPrev}>← Zurück</Btn>}
          {!isLast  && <Btn variant="ghost" size="md" onClick={onNext}>Weiter →</Btn>}
        </div>
        <div className="mono" style={{ fontSize: 11, color: "var(--g-ink-4)", letterSpacing: "0.06em" }}>
          Änderungen werden beim Speichern übernommen
        </div>
        <div style={{ display: "flex", justifyContent: "flex-end", gap: 10 }}>
          <Btn variant="quiet" size="md">Verwerfen</Btn>
          <Btn variant="accent" size="md">Speichern</Btn>
        </div>
      </div>
    );
  }

  return (
    <div style={{
      marginTop: 36, paddingTop: 20, borderTop: "1px solid var(--g-rule)",
      display: "grid", gridTemplateColumns: "1fr auto 1fr", alignItems: "center", gap: 12,
    }}>
      <div>{!isFirst && <Btn variant="ghost" size="md" onClick={onPrev}>← Zurück</Btn>}</div>
      <div/>
      <div style={{ display: "flex", justifyContent: "flex-end", gap: 10 }}>
        <Btn variant="quiet" size="md">Abbrechen</Btn>
        {isLast ? (
          <Btn variant="accent" size="md">Briefing aktivieren →</Btn>
        ) : (
          <Btn variant="accent" size="md" onClick={onNext}
            style={canAdvance ? null : { opacity: 0.4, cursor: "not-allowed" }}>
            Weiter →
          </Btn>
        )}
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════════
 * STEP 1 — VERGLEICH BENENNEN
 * ═══════════════════════════════════════════════════════════════════ */

function CW_StepName({ name, onName, region, onRegion, profileId, onProfile }) {
  return (
    <div style={{ maxWidth: 720, margin: "0 auto" }}>
      <CW_Intro>
        Du legst hier einen <strong>Orts-Vergleich</strong> an. Vor dem Urlaub
        einmalig eingerichtet, bekommst du dann jeden Morgen eine Mail mit der
        klaren Empfehlung „Heute ist Ort X am besten — weil …".
      </CW_Intro>

      <Eyebrow style={{ marginBottom: 14, marginTop: 28 }}>Eckdaten</Eyebrow>

      <Field label="Name des Vergleichs" hint="Erscheint im Mail-Betreff. Kurz & wiedererkennbar.">
        <Input value={name} onChange={(e) => onName(e.target.value)}
          placeholder="z.B. Skitouren Hochkönig" size="lg"/>
      </Field>

      <Field label="Region" hint="Optional — gemeinsame Klammer der Orte">
        <Input value={region} onChange={(e) => onRegion(e.target.value.slice(0, 60))}
          placeholder="z.B. Hochkönig · Salzburger Land" size="lg"/>
      </Field>

      <Eyebrow style={{ marginBottom: 14, marginTop: 28 }}>Aktivitätsprofil</Eyebrow>
      <div style={{ fontSize: 13, color: "var(--g-ink-3)", marginBottom: 12 }}>
        Bestimmt, welche Wetter-Metriken im Vergleich auftauchen. Die Idealwerte legst du im nächsten Schritt fest.
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
        {LOCATION_ACTIVITY_PROFILES.map(p => (
          <CW_ProfileTile key={p.id} profile={p} active={profileId === p.id}
            onClick={() => onProfile(p.id)}/>
        ))}
      </div>
    </div>
  );
}

function CW_ProfileTile({ profile, active, onClick }) {
  return (
    <button onClick={onClick} style={{
      textAlign: "left", cursor: "pointer",
      padding: "14px 16px",
      background: active ? "var(--g-accent-tint)" : "var(--g-card)",
      border: active ? "1.5px solid var(--g-accent)" : "1px solid var(--g-rule)",
      borderRadius: "var(--g-r-3)",
      fontFamily: "var(--g-font-sans)",
    }}>
      <div style={{
        fontSize: 14, fontWeight: 600,
        color: active ? "var(--g-accent-deep)" : "var(--g-ink)",
        marginBottom: 4,
      }}>{profile.label}</div>
      <div className="mono" style={{ fontSize: 10.5, color: "var(--g-ink-3)", letterSpacing: "0.02em" }}>
        Metriken · {profile.metrics.join(" · ")}
      </div>
    </button>
  );
}

function CW_Intro({ children }) {
  return (
    <div style={{
      padding: "14px 18px",
      background: "var(--g-card-alt)",
      borderLeft: "3px solid var(--g-accent)",
      borderRadius: "0 var(--g-r-2) var(--g-r-2) 0",
      fontSize: 13.5, color: "var(--g-ink-2)", lineHeight: 1.55,
    }}>{children}</div>
  );
}

/* ═══════════════════════════════════════════════════════════════════
 * STEP 2 — ORTE SAMMELN
 * ═══════════════════════════════════════════════════════════════════ */

function CW_StepLocations({ pickedIds, setPickedIds }) {
  const picked = pickedIds.map(id => MOCK_LOCATIONS.find(l => l.id === id)).filter(Boolean);
  const remove = (id) => setPickedIds(pickedIds.filter(x => x !== id));

  return (
    <div style={{ maxWidth: 880, margin: "0 auto" }}>
      <CW_Intro>
        3–5 Kandidaten genügen üblicherweise. Du kannst Orte aus deinen
        gespeicherten Locations wählen oder neue über Smart-Import anlegen.
      </CW_Intro>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 24, marginTop: 28 }}>
        {/* Linke Spalte: Smart-Import */}
        <div>
          <Eyebrow style={{ marginBottom: 14 }}>Neuen Ort hinzufügen</Eyebrow>
          <CW_SmartImport/>
        </div>

        {/* Rechte Spalte: Picked Locations */}
        <div>
          <div style={{
            display: "flex", justifyContent: "space-between", alignItems: "baseline",
            marginBottom: 14,
          }}>
            <Eyebrow>Im Vergleich · {picked.length}</Eyebrow>
            <span className="mono" style={{ fontSize: 10.5, color: "var(--g-ink-4)", letterSpacing: "0.04em" }}>
              {picked.length < 2 ? "min. 2" : picked.length > 5 ? "viel — Empfehlung 3–5" : "passt"}
            </span>
          </div>
          {picked.length === 0 ? (
            <CW_EmptyPicks/>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              {picked.map((l, i) => (
                <CW_PickedRow key={l.id} loc={l} idx={i + 1} onRemove={() => remove(l.id)}/>
              ))}
            </div>
          )}
        </div>
      </div>

      <Eyebrow style={{ marginTop: 32, marginBottom: 12 }}>… oder aus gespeicherten Orten wählen</Eyebrow>
      <CW_LocationLibrary pickedIds={pickedIds} onToggle={(id) => {
        setPickedIds(pickedIds.includes(id) ? pickedIds.filter(x => x !== id) : [...pickedIds, id]);
      }}/>
    </div>
  );
}

function CW_SmartImport() {
  return (
    <div style={{
      padding: "16px 16px 14px", background: "var(--g-card)",
      border: "1px solid var(--g-rule)", borderRadius: "var(--g-r-3)",
    }}>
      <Field label="Smart-Import" hint="URL aus Komoot/Google Maps oder Koordinaten direkt einfügen" dense>
        <div style={{
          display: "flex", alignItems: "center", gap: 10,
          padding: "10px 12px",
          background: "var(--g-card-alt)",
          border: "1.5px solid var(--g-accent)",
          borderRadius: "var(--g-r-2)",
        }}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--g-accent)" strokeWidth="2">
            <path d="M10 13a5 5 0 0 0 7.07 0l3-3a5 5 0 0 0-7.07-7.07l-1.5 1.5"/>
            <path d="M14 11a5 5 0 0 0-7.07 0l-3 3a5 5 0 0 0 7.07 7.07l1.5-1.5"/>
          </svg>
          <span className="mono" style={{ fontSize: 12, color: "var(--g-ink)", flex: 1, minWidth: 0,
            whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
            komoot.com/de-de/highlight/2049832
          </span>
          <Pill tone="good">erkannt</Pill>
        </div>
      </Field>

      <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBottom: 14 }}>
        {[
          { l: "Komoot",      e: "komoot.com/highlight/…" },
          { l: "Google Maps", e: "goo.gl/maps/…" },
          { l: "DMS",         e: "47°04'44\"N 11°41'08\"E" },
          { l: "Dezimal",     e: "47.0789, 11.6856" },
          { l: "UTM",         e: "33T 296000 5215000" },
        ].map((f, i) => (
          <span key={i} title={f.e} style={{
            padding: "3px 8px", fontFamily: "var(--g-font-mono)", fontSize: 10,
            border: "1px solid var(--g-rule)", borderRadius: "var(--g-r-pill)",
            color: "var(--g-ink-3)", letterSpacing: "0.04em",
          }}>{f.l}</span>
        ))}
      </div>

      <div style={{
        padding: "10px 12px", background: "var(--g-paper-deep)",
        borderRadius: "var(--g-r-2)", fontSize: 12, lineHeight: 1.5,
      }}>
        <div className="mono" style={{ fontSize: 10, color: "var(--g-ink-4)", letterSpacing: "0.06em",
          textTransform: "uppercase", marginBottom: 4 }}>Erkannt</div>
        <div style={{ fontSize: 13, fontWeight: 600, color: "var(--g-ink)" }}>Aberg-Karbachalm</div>
        <div className="mono" style={{ fontSize: 11, color: "var(--g-ink-3)", marginTop: 2 }}>
          47.4380, 13.0421 · 1893 m · Hochkönig
        </div>
      </div>
      <Btn variant="primary" size="sm" style={{ marginTop: 12, width: "100%", justifyContent: "center" }}>
        ＋ Zum Vergleich hinzufügen
      </Btn>
    </div>
  );
}

function CW_PickedRow({ loc, idx, onRemove }) {
  return (
    <div style={{
      display: "flex", alignItems: "center", gap: 10, padding: "10px 12px",
      background: "var(--g-card)", border: "1px solid var(--g-rule)",
      borderRadius: "var(--g-r-2)",
    }}>
      <span className="mono" style={{
        width: 22, height: 22, borderRadius: 4,
        background: "var(--g-ink)", color: "#fff",
        display: "inline-flex", alignItems: "center", justifyContent: "center",
        fontSize: 10, fontWeight: 700,
      }}>{idx}</span>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 13, fontWeight: 600, color: "var(--g-ink)",
          whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{loc.name}</div>
        <div className="mono" style={{ fontSize: 10.5, color: "var(--g-ink-4)", marginTop: 1 }}>
          {loc.group} · {loc.elev} m
        </div>
      </div>
      <button onClick={onRemove} style={{
        background: "transparent", border: "none", padding: 6,
        color: "var(--g-ink-4)", cursor: "pointer", fontSize: 12,
      }}>✕</button>
    </div>
  );
}

function CW_EmptyPicks() {
  return (
    <div style={{
      padding: "28px 18px",
      border: "1px dashed var(--g-rule)",
      borderRadius: "var(--g-r-2)",
      textAlign: "center",
      color: "var(--g-ink-3)",
      fontSize: 13, lineHeight: 1.5,
    }}>
      Noch keine Orte ausgewählt.<br/>
      <span className="mono" style={{ fontSize: 11, color: "var(--g-ink-4)" }}>
        füge links neue hinzu oder wähle unten aus
      </span>
    </div>
  );
}

function CW_LocationLibrary({ pickedIds, onToggle }) {
  const groups = MOCK_LOCATIONS.filter(l => l.group !== "Test").reduce((acc, l) => {
    (acc[l.group] = acc[l.group] || []).push(l);
    return acc;
  }, {});
  return (
    <div style={{
      background: "var(--g-card)", border: "1px solid var(--g-rule)",
      borderRadius: "var(--g-r-3)", padding: "14px 18px",
    }}>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 18 }}>
        {Object.entries(groups).map(([group, items]) => (
          <div key={group}>
            <div className="mono" style={{
              fontSize: 10, letterSpacing: "0.10em", textTransform: "uppercase",
              color: "var(--g-ink-3)", fontWeight: 600,
              padding: "0 0 8px", marginBottom: 4,
              borderBottom: "1px solid var(--g-rule-soft)",
            }}>{group} · {items.length}</div>
            <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
              {items.map(l => {
                const on = pickedIds.includes(l.id);
                return (
                  <button key={l.id} onClick={() => onToggle(l.id)} style={{
                    display: "flex", alignItems: "center", gap: 8,
                    padding: "6px 8px",
                    background: on ? "var(--g-accent-tint)" : "transparent",
                    border: "none", borderRadius: "var(--g-r-2)",
                    cursor: "pointer", textAlign: "left",
                    fontFamily: "var(--g-font-sans)",
                  }}>
                    <span style={{
                      width: 14, height: 14, borderRadius: 3,
                      border: `1.5px solid ${on ? "var(--g-accent)" : "var(--g-rule)"}`,
                      background: on ? "var(--g-accent)" : "transparent",
                      display: "flex", alignItems: "center", justifyContent: "center",
                      flexShrink: 0,
                    }}>
                      {on && <svg width="9" height="9" viewBox="0 0 12 12" fill="none" stroke="#fff" strokeWidth="2.5"><path d="M2 6l3 3 5-6"/></svg>}
                    </span>
                    <span style={{ flex: 1, fontSize: 12.5, color: "var(--g-ink)",
                      whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{l.name}</span>
                  </button>
                );
              })}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════════
 * STEP 3 — IDEALWERTE
 * ═══════════════════════════════════════════════════════════════════ */

const CW_IDEALS_BY_PROFILE = {
  "wintersport": [
    { label: "Schneehöhe",      ideal: "≥ 80 cm",       pos: [0.55, 1.0], notes: "Mindestauflage Piste",   scale: ["0 cm", "300+ cm"] },
    { label: "Neuschnee 24 h",  ideal: "+ je mehr je besser", pos: [0.30, 1.0], notes: "Pulver-Bonus",     scale: ["0", "40 cm"] },
    { label: "Wind (Mittel)",   ideal: "≤ 30 km/h",     pos: [0.0, 0.40], notes: "Lift kritisch ab 50",    scale: ["0", "Sturm"] },
    { label: "Temperatur gef.", ideal: "−8 bis +2 °C",  pos: [0.30, 0.65], notes: "pulvrig & griffig",     scale: ["−20°", "+15°"] },
    { label: "Niederschlag",    ideal: "Schnee ok · Regen aus", pos: [0.0, 0.25], notes: "Regen → Abbruch", scale: ["trocken", "Starkregen"] },
    { label: "Sichtweite",      ideal: "≥ 5 km",        pos: [0.50, 1.0], notes: "Nebel = Abbruch",        scale: ["0", "klar"] },
  ],
  "wintersport-glacier": [
    { label: "Schneehöhe",      ideal: "≥ 150 cm",      pos: [0.65, 1.0], notes: "Gletscher braucht Auflage", scale: ["0", "400+ cm"] },
    { label: "Wind (Mittel)",   ideal: "≤ 25 km/h",     pos: [0.0, 0.35], notes: "Höhenwind kritisch",    scale: ["0", "Sturm"] },
    { label: "Temperatur gef.", ideal: "−15 bis −2 °C", pos: [0.20, 0.55], notes: "kalt = stabil",        scale: ["−30°", "+10°"] },
    { label: "0°-Linie",        ideal: "≤ 2000 m",      pos: [0.0, 0.40], notes: "tief = sicher",         scale: ["500 m", "4000 m"] },
  ],
  "alpine-touring": [
    { label: "Wind (Mittel)",   ideal: "≤ 30 km/h",     pos: [0.0, 0.40], notes: "Gratwege",              scale: ["0", "Sturm"] },
    { label: "Lawinenstufe",    ideal: "≤ Stufe 2",     pos: [0.0, 0.40], notes: "ab 3 Vorsicht",         scale: ["1", "5"] },
    { label: "Sichtweite",      ideal: "≥ 1 km",        pos: [0.20, 1.0], notes: "Spaltenrisiko",         scale: ["Nebel", "klar"] },
    { label: "Sonnenstunden",   ideal: "≥ 3 h",         pos: [0.40, 1.0], notes: "Aufstiegs-Komfort",     scale: ["0 h", "8 h"] },
  ],
  "hiking": [
    { label: "Niederschlag",    ideal: "≤ 2 mm/h",      pos: [0.0, 0.25], notes: "trocken bevorzugt",     scale: ["trocken", "Starkregen"] },
    { label: "Wind (Mittel)",   ideal: "≤ 25 km/h",     pos: [0.0, 0.40], notes: "Grat-Tauglichkeit",     scale: ["0", "Sturm"] },
    { label: "Gewitter-Risiko", ideal: "kein Risiko",   pos: [0.0, 0.15], notes: "Abbruch bei Gewitter",  scale: ["niedrig", "hoch"] },
    { label: "Temperatur",      ideal: "+8 bis +22 °C", pos: [0.40, 0.75], notes: "angenehm",             scale: ["−5°", "+35°"] },
  ],
  "trail-running": [
    { label: "Temperatur",      ideal: "+8 bis +18 °C", pos: [0.40, 0.70], notes: "Wettkampf-Temp",       scale: ["0°", "+30°"] },
    { label: "UV-Index",        ideal: "≤ 6",           pos: [0.0, 0.55], notes: "kein Sonnenbrand",      scale: ["0", "extrem"] },
    { label: "Niederschlag",    ideal: "≤ 1 mm/h",      pos: [0.0, 0.20], notes: "trocken",               scale: ["trocken", "Starkregen"] },
  ],
};

function CW_StepIdeals({ profileId }) {
  const profile = LOCATION_ACTIVITY_PROFILES.find(p => p.id === profileId);
  const ideals = CW_IDEALS_BY_PROFILE[profileId] || CW_IDEALS_BY_PROFILE["wintersport"];
  return (
    <div style={{ maxWidth: 820, margin: "0 auto" }}>
      <CW_Intro>
        Diese Werte definieren, wie der tägliche Score berechnet wird. Wir starten
        mit sinnvollen Defaults für <strong>{profile.label}</strong> — passe sie an,
        wo es für dich anders aussieht.
      </CW_Intro>

      <div style={{
        marginTop: 28,
        background: "var(--g-card)", border: "1px solid var(--g-rule)",
        borderRadius: "var(--g-r-3)", overflow: "hidden",
      }}>
        <div style={{
          padding: "12px 20px", borderBottom: "1px solid var(--g-rule-soft)",
          display: "flex", justifyContent: "space-between", alignItems: "center",
          background: "var(--g-card-alt)",
        }}>
          <div>
            <Eyebrow style={{ marginBottom: 2 }}>Idealwerte · {profile.label}</Eyebrow>
            <div style={{ fontSize: 12, color: "var(--g-ink-3)" }}>{ideals.length} Metriken</div>
          </div>
          <Btn variant="ghost" size="sm">＋ Metrik hinzufügen</Btn>
        </div>
        <div style={{ display: "flex", flexDirection: "column" }}>
          {ideals.map((it, i) => <CW_IdealRow key={i} {...it} last={i === ideals.length - 1}/>)}
        </div>
      </div>
    </div>
  );
}

function CW_IdealRow({ label, ideal, pos, notes, scale, last }) {
  const [start, end] = pos;
  return (
    <div style={{
      padding: "16px 20px",
      borderBottom: last ? "none" : "1px solid var(--g-rule-soft)",
      display: "grid", gridTemplateColumns: "200px 1fr 180px 28px",
      gap: 20, alignItems: "center",
    }}>
      <div>
        <div style={{ fontSize: 13.5, fontWeight: 600, color: "var(--g-ink)" }}>{label}</div>
        <div style={{ fontSize: 11, color: "var(--g-ink-4)", marginTop: 2, fontStyle: "italic" }}>{notes}</div>
      </div>
      <div>
        <div style={{
          position: "relative", height: 8, background: "var(--g-rule-soft)",
          borderRadius: 4, overflow: "hidden",
        }}>
          <div style={{
            position: "absolute", top: 0, bottom: 0,
            left: `${start * 100}%`, width: `${(end - start) * 100}%`,
            background: "var(--g-accent)", opacity: 0.85,
          }}/>
          {/* Knob start + end */}
          <div style={{ position: "absolute", top: -3, left: `${start * 100}%`, width: 14, height: 14, marginLeft: -7, background: "#fff", border: "2px solid var(--g-accent)", borderRadius: "50%" }}/>
          <div style={{ position: "absolute", top: -3, left: `${end * 100}%`, width: 14, height: 14, marginLeft: -7, background: "#fff", border: "2px solid var(--g-accent)", borderRadius: "50%" }}/>
        </div>
        <div className="mono" style={{
          display: "flex", justifyContent: "space-between", marginTop: 6,
          fontSize: 10, color: "var(--g-ink-4)", letterSpacing: "0.04em",
        }}>
          <span>{scale[0]}</span>
          <span>{scale[1]}</span>
        </div>
      </div>
      <span className="mono" style={{
        fontSize: 12.5, fontWeight: 600, color: "var(--g-accent-deep)",
        textAlign: "right", fontVariantNumeric: "tabular-nums",
      }}>{ideal}</span>
      <button style={{
        background: "transparent", border: "none", padding: 4,
        color: "var(--g-ink-4)", cursor: "pointer", fontSize: 12,
      }}>✕</button>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════════
 * STEP 4 — LAYOUT (was steht im Briefing)
 * ═══════════════════════════════════════════════════════════════════ */

function CW_StepLayout({ pickedIds }) {
  const [channel, setChannel] = React.useState("email");
  const channelDef = CW_CHANNELS.find(c => c.id === channel);
  return (
    <div style={{ maxWidth: 1000, margin: "0 auto" }}>
      <CW_Intro>
        Die Empfehlung (Sieger + „weil …") steht immer ganz oben — das ist der
        Kern des Briefings. Hier wählst du, welche Spalten in der Vergleichs-Tabelle
        landen — pro Kanal anders, weil SMS, Signal & Telegram Platz-Limits haben.
      </CW_Intro>

      <div style={{ marginTop: 28, display: "grid", gridTemplateColumns: "1fr 1.2fr", gap: 24 }}>
        {/* Linke Spalte: Kanal-Wahl + Spalten-Auswahl */}
        <div>
          <Eyebrow style={{ marginBottom: 12 }}>Kanal wählen</Eyebrow>
          <div style={{ display: "flex", flexDirection: "column", gap: 6, marginBottom: 22 }}>
            {CW_CHANNELS.map(c => (
              <CW_ChannelTab key={c.id} channel={c} active={channel === c.id} onClick={() => setChannel(c.id)}/>
            ))}
          </div>

          <Eyebrow style={{ marginBottom: 12 }}>Spalten im Vergleich</Eyebrow>
          <div style={{
            background: "var(--g-card)", border: "1px solid var(--g-rule)",
            borderRadius: "var(--g-r-3)", overflow: "hidden",
          }}>
            {[
              { label: "Score (Gesamt)",   on: true,  pinned: true },
              { label: "Schneehöhe",       on: true },
              { label: "Neuschnee 24 h",   on: true },
              { label: "Wind / Böen",      on: true },
              { label: "Temperatur gef.",  on: true },
              { label: "Sonnenstunden",    on: channel === "email" },
              { label: "Bewölkung",        on: false },
              { label: "0°-Linie",         on: false },
            ].map((col, i, arr) => (
              <CW_ColumnRow key={i} col={col} last={i === arr.length - 1} overLimit={channelDef.maxCols !== Infinity && i >= channelDef.maxCols + 1}/>
            ))}
          </div>
          <div className="mono" style={{ marginTop: 10, fontSize: 11, color: "var(--g-ink-4)", letterSpacing: "0.04em" }}>
            {channelDef.maxCols === Infinity
              ? "Email zeigt alles · keine Begrenzung"
              : channelDef.maxCols === 0
                ? "SMS hat keine Tabelle — nur Empfehlung + Top-3 als Fließtext"
                : `Maximal ${channelDef.maxCols} Spalten passen ins Layout für ${channelDef.label}`}
          </div>
        </div>

        {/* Rechte Spalte: Live-Vorschau */}
        <div>
          <Eyebrow style={{ marginBottom: 12 }}>Vorschau · {channelDef.label}</Eyebrow>
          <CW_LayoutPreview channel={channel} pickedIds={pickedIds}/>
        </div>
      </div>
    </div>
  );
}

function CW_ChannelTab({ channel, active, onClick }) {
  return (
    <button onClick={onClick} style={{
      display: "flex", justifyContent: "space-between", alignItems: "center",
      padding: "10px 14px",
      background: active ? "var(--g-accent-tint)" : "var(--g-card)",
      border: active ? "1.5px solid var(--g-accent)" : "1px solid var(--g-rule)",
      borderRadius: "var(--g-r-2)",
      cursor: "pointer", textAlign: "left", fontFamily: "var(--g-font-sans)",
    }}>
      <div>
        <div style={{ fontSize: 13.5, fontWeight: 600,
          color: active ? "var(--g-accent-deep)" : "var(--g-ink)" }}>{channel.label}</div>
        <div className="mono" style={{ fontSize: 10.5, color: "var(--g-ink-3)", marginTop: 2 }}>{channel.hint}</div>
      </div>
      <span className="mono" style={{
        fontSize: 11, color: active ? "var(--g-accent-deep)" : "var(--g-ink-4)",
        fontWeight: 600,
      }}>{channel.maxCols === Infinity ? "∞" : channel.maxCols === 0 ? "—" : `${channel.maxCols}`}</span>
    </button>
  );
}

function CW_ColumnRow({ col, last, overLimit }) {
  const dimmed = overLimit && col.on;
  return (
    <div style={{
      display: "flex", alignItems: "center", gap: 10, padding: "9px 14px",
      borderBottom: last ? "none" : "1px solid var(--g-rule-soft)",
      opacity: dimmed ? 0.55 : 1,
      background: dimmed ? "rgba(192,138,26,0.05)" : "transparent",
    }}>
      <span style={{ color: "var(--g-ink-4)", fontFamily: "var(--g-font-mono)", fontSize: 11, cursor: "grab" }}>⋮⋮</span>
      <span style={{ flex: 1, fontSize: 13, color: "var(--g-ink-2)" }}>{col.label}</span>
      {col.pinned && (
        <span className="mono" style={{ fontSize: 9, color: "var(--g-ink-4)", letterSpacing: "0.06em",
          textTransform: "uppercase" }}>fix</span>
      )}
      {dimmed && (
        <span className="mono" style={{ fontSize: 9.5, color: "var(--g-warn)", fontWeight: 600,
          letterSpacing: "0.06em", textTransform: "uppercase" }}>↳ Detail</span>
      )}
      <Switch checked={col.on} tone="good"/>
    </div>
  );
}

function CW_LayoutPreview({ channel, pickedIds }) {
  const rows = MOCK_COMPARE_ROWS.filter(r => pickedIds.includes(r.id))
    .sort((a, b) => b.score - a.score).slice(0, 5);
  const winner = MOCK_LOCATIONS.find(l => l.id === rows[0]?.id);
  if (!winner) return <CW_EmptyPreview/>;

  if (channel === "sms") return <CW_SmsPreview winner={winner} row={rows[0]} rows={rows}/>;

  const cols = channel === "email"
    ? ["Score", "Schnee", "Neuschnee", "Wind/Böen", "Temp", "Sonne"]
    : channel === "telegram"
      ? ["Score", "Schnee", "Neuschnee", "Wind", "Temp"]
      : ["Score", "Schnee", "Wind", "Temp"];

  return (
    <div style={{
      background: "var(--g-card)", border: "1px solid var(--g-rule)",
      borderRadius: "var(--g-r-3)", overflow: "hidden",
    }}>
      {/* Empfehlung */}
      <div style={{
        padding: "14px 16px",
        background: "linear-gradient(135deg, rgba(61,107,58,0.10), rgba(61,107,58,0.02))",
        borderBottom: "1px solid rgba(61,107,58,0.20)",
        borderLeft: "3px solid var(--g-good)",
      }}>
        <Eyebrow style={{ color: "var(--g-good)", marginBottom: 4 }}>Empfehlung · Sa 09.05.</Eyebrow>
        <div style={{ fontSize: 16, fontWeight: 600, lineHeight: 1.2 }}>{winner.name}</div>
        <div style={{ fontSize: 12, color: "var(--g-ink-2)", marginTop: 4, lineHeight: 1.5 }}>
          <span style={{ color: "var(--g-good)", fontWeight: 600 }}>weil</span>{" "}
          {rows[0].snow} cm Schnee · +{rows[0].newSnow} cm neu ·{" "}
          {rows[0].wind} km/h Wind · gefühlt {rows[0].feels >= 0 ? "+" : ""}{rows[0].feels}°C
        </div>
      </div>
      {/* Tabelle */}
      <div style={{ overflowX: "auto" }}>
        <table style={{ width: "100%", borderCollapse: "collapse",
          fontFamily: "var(--g-font-mono)", fontVariantNumeric: "tabular-nums" }}>
          <thead>
            <tr style={{ borderBottom: "1px solid var(--g-rule-soft)" }}>
              <th style={{ padding: "8px 10px", textAlign: "left", fontSize: 9.5, color: "var(--g-ink-4)",
                letterSpacing: "0.08em", textTransform: "uppercase", fontWeight: 600 }}>Ort</th>
              {cols.map(c => (
                <th key={c} style={{ padding: "8px 8px", textAlign: "center", fontSize: 9.5, color: "var(--g-ink-4)",
                  letterSpacing: "0.08em", textTransform: "uppercase", fontWeight: 600 }}>{c}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => {
              const l = MOCK_LOCATIONS.find(x => x.id === r.id);
              const top = i === 0;
              return (
                <tr key={r.id} style={{
                  borderBottom: "1px solid var(--g-rule-soft)",
                  background: top ? "rgba(61,107,58,0.04)" : "transparent",
                }}>
                  <td style={{ padding: "8px 10px", fontSize: 12, color: "var(--g-ink)",
                    fontFamily: "var(--g-font-sans)", fontWeight: top ? 600 : 500 }}>
                    <span className="mono" style={{
                      display: "inline-block", marginRight: 8,
                      width: 18, height: 14, lineHeight: "14px", textAlign: "center", borderRadius: 2,
                      background: top ? "var(--g-good)" : "var(--g-ink)", color: "#fff",
                      fontSize: 9, fontWeight: 600,
                    }}>#{i+1}</span>
                    {l.name}
                  </td>
                  {cols.includes("Score")     && <td style={cwTd(top)}>{r.score}</td>}
                  {cols.includes("Schnee")    && <td style={cwTd()}>{r.snow != null ? r.snow + "cm" : "—"}</td>}
                  {cols.includes("Neuschnee") && <td style={cwTd()}>{r.newSnow != null ? "+" + r.newSnow : "—"}</td>}
                  {cols.includes("Wind/Böen") && <td style={cwTd()}>{r.wind}/{r.gust} {r.dir}</td>}
                  {cols.includes("Wind")      && <td style={cwTd()}>{r.wind} {r.dir}</td>}
                  {cols.includes("Temp")      && <td style={cwTd()}>{r.feels >= 0 ? "+" : ""}{r.feels}°</td>}
                  {cols.includes("Sonne")     && <td style={cwTd()}>~{r.sun}h</td>}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <div style={{ padding: "8px 14px", background: "var(--g-paper-deep)",
        fontFamily: "var(--g-font-mono)", fontSize: 10, color: "var(--g-ink-4)", letterSpacing: "0.04em" }}>
        {channel === "email"
          ? "Email · alle Spalten + Detail-Block je Ort darunter"
          : `${CW_CHANNELS.find(c => c.id === channel).label} · ${cols.length} Spalten passen`}
      </div>
    </div>
  );
}

const cwTd = (top) => ({
  padding: "8px 8px", textAlign: "center", fontSize: 11.5,
  color: "var(--g-ink)", fontWeight: top ? 600 : 500,
});

function CW_SmsPreview({ winner, row, rows }) {
  return (
    <div style={{
      background: "var(--g-card)", border: "1px solid var(--g-rule)",
      borderRadius: "var(--g-r-3)", padding: "18px 18px 16px",
    }}>
      <Eyebrow style={{ marginBottom: 10 }}>SMS · 1 Nachricht · ≤ 140 Z.</Eyebrow>
      <div style={{
        padding: "12px 14px", background: "var(--g-paper-deep)",
        borderRadius: "var(--g-r-2)",
        fontFamily: "var(--g-font-mono)", fontSize: 12.5, lineHeight: 1.5,
        color: "var(--g-ink)",
      }}>
        <strong>SA 09.05 · Skitouren Hochkönig</strong><br/>
        #1 {winner.name.slice(0, 22)} · {row.score}p<br/>
        Schnee {row.snow}cm +{row.newSnow} · gef {row.feels >= 0 ? "+" : ""}{row.feels}° · {row.wind}/{row.gust}{row.dir}<br/>
        #2 {MOCK_LOCATIONS.find(l => l.id === rows[1]?.id)?.name.slice(0, 18)} {rows[1]?.score}p
      </div>
      <div className="mono" style={{
        marginTop: 8, fontSize: 10, color: "var(--g-ink-4)", letterSpacing: "0.04em",
      }}>SMS hat keine Tabelle — die Spalten werden zu „· · ·"-Fließtext zusammengezogen.</div>
    </div>
  );
}

function CW_EmptyPreview() {
  return (
    <div style={{
      padding: "40px 20px", border: "1px dashed var(--g-rule)",
      borderRadius: "var(--g-r-3)", textAlign: "center", color: "var(--g-ink-4)",
    }}>Keine Orte ausgewählt — zurück zu Schritt 2.</div>
  );
}

/* ═══════════════════════════════════════════════════════════════════
 * STEP 5 — VERSAND + AKTIVIERUNG
 * ═══════════════════════════════════════════════════════════════════ */

function CW_StepSending({ name, pickedIds, activated, editMode = false }) {
  return (
    <div style={{ maxWidth: 820, margin: "0 auto" }}>
      <CW_Intro>
        Letzter Schritt. Schalte die Kanäle ein, an die das tägliche Briefing geht.
        Versandzeit + Forecast-Horizont gelten für alle Kanäle gemeinsam.
      </CW_Intro>

      {/* Versandzeit */}
      <Eyebrow style={{ marginTop: 28, marginBottom: 12 }}>Versandzeit</Eyebrow>
      <div style={{
        display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 10,
      }}>
        <CW_TimeChoice label="Versand"    value="06:30 Uhr"  sub="täglich"/>
        <CW_TimeChoice label="Zeitfenster" value="09–16 Uhr" sub="bewertet"/>
        <CW_TimeChoice label="Horizont"    value="+48 h"     sub="morgen + übermorgen"/>
      </div>

      {/* Kanäle */}
      <Eyebrow style={{ marginTop: 28, marginBottom: 12 }}>Versand-Kanäle</Eyebrow>
      <Card padding={0}>
        <div style={{ padding: "4px 18px" }}>
          <ChannelRow kind="Email"    target="gregor_zwanzig@henemm.com" active={true}  sub="Layout · alle Spalten + Detail" dense/>
          <ChannelRow kind="Signal"   target="+49 151 12345 678"          active={true}  sub="Layout · 6 Spalten" dense/>
          <ChannelRow kind="Telegram" target="@henemm"                    active={false} sub="Layout · 8 Spalten" dense/>
          <ChannelRow kind="SMS"      target="+49 151 12345 678"          active={false} sub="Layout · flach, ≤140 Z." dense last/>
        </div>
      </Card>

      {/* Zusammenfassung + Aktivierung — nur im Create-Mode. Im Edit-Mode ist der Status oben im Header. */}
      {!editMode && (
        <div style={{ marginTop: 32 }}>
          {activated
            ? <CW_ActivatedBanner name={name} pickedCount={pickedIds.length}/>
            : <CW_SummaryBanner name={name} pickedCount={pickedIds.length}/>}
        </div>
      )}
    </div>
  );
}

function CW_TimeChoice({ label, value, sub }) {
  return (
    <button style={{
      padding: "12px 14px", background: "var(--g-card)",
      border: "1px solid var(--g-rule)", borderRadius: "var(--g-r-2)",
      textAlign: "left", cursor: "pointer", fontFamily: "var(--g-font-sans)",
      display: "flex", flexDirection: "column", gap: 4,
    }}>
      <span className="mono" style={{ fontSize: 10, color: "var(--g-ink-4)",
        letterSpacing: "0.10em", textTransform: "uppercase" }}>{label}</span>
      <span style={{ fontSize: 17, fontWeight: 600, color: "var(--g-ink)",
        fontVariantNumeric: "tabular-nums" }}>{value}</span>
      <span style={{ fontSize: 11, color: "var(--g-ink-3)" }}>{sub}</span>
    </button>
  );
}

function CW_SummaryBanner({ name, pickedCount }) {
  return (
    <div style={{
      padding: "18px 22px", background: "var(--g-ink)",
      borderRadius: "var(--g-r-3)", color: "#fff",
      display: "flex", justifyContent: "space-between", alignItems: "center", gap: 20,
    }}>
      <div>
        <div className="mono" style={{
          fontSize: 10, letterSpacing: "0.12em", textTransform: "uppercase",
          color: "rgba(255,255,255,0.55)", marginBottom: 4,
        }}>Bereit zum Aktivieren</div>
        <div style={{ fontSize: 15, fontWeight: 600 }}>
          „{name || "Neuer Vergleich"}" · {pickedCount} Orte
        </div>
        <div style={{ fontSize: 12.5, color: "rgba(255,255,255,0.75)", marginTop: 4, lineHeight: 1.5 }}>
          Versand morgen früh 06:30 an gregor_zwanzig@henemm.com und Signal-Account.
          Du kannst alles jederzeit hier wieder anpassen.
        </div>
      </div>
    </div>
  );
}

function CW_ActivatedBanner({ name, pickedCount }) {
  return (
    <div style={{
      padding: "20px 24px", background: "var(--g-good)",
      borderRadius: "var(--g-r-3)", color: "#fff",
      display: "flex", alignItems: "center", gap: 16,
    }}>
      <div style={{
        width: 44, height: 44, borderRadius: "50%",
        background: "rgba(255,255,255,0.15)",
        display: "flex", alignItems: "center", justifyContent: "center",
        fontSize: 22, fontWeight: 700,
      }}>✓</div>
      <div style={{ flex: 1 }}>
        <div className="mono" style={{
          fontSize: 10, letterSpacing: "0.12em", textTransform: "uppercase",
          color: "rgba(255,255,255,0.7)", marginBottom: 4,
        }}>Briefing aktiv</div>
        <div style={{ fontSize: 16, fontWeight: 600 }}>
          „{name}" läuft · {pickedCount} Orte · täglich 06:30
        </div>
        <div style={{ fontSize: 12.5, color: "rgba(255,255,255,0.85)", marginTop: 4, lineHeight: 1.5 }}>
          Erstes Briefing geht morgen früh raus. Die Webseite musst du im Urlaub
          nicht öffnen — alles kommt automatisch in dein Postfach.
        </div>
      </div>
      <Btn variant="ghost" size="sm" style={{ color: "#fff", borderColor: "rgba(255,255,255,0.30)" }}>
        Briefing-Beispiel ansehen →
      </Btn>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════════
 * Export
 * ═══════════════════════════════════════════════════════════════════ */

window.ScreenCompareWizard = ScreenCompareWizard;
