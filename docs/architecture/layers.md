# Layering Guardrails

This document captures the practical guardrails behind the six-phase roadmap so that every contributor can see **why** the new CI checks exist and how to work with them.

## Goals

- **One-way dependencies:** Domain models (`core/domain`) and contracts (`core/event_topics`, future protocols) flow downward into adapters. Engines never import Discord, and cogs never reach back into engines directly.
- **Centralized wiring:** `integrations/integration_loader.py` owns object creation / injection. Cogs receive services through setup hooks or `bot.ctx`.
- **Async-only I/O:** Engines and adapters interact with Discord or storage through injected async facades so we can test them in isolation.

## Layering Check (`scripts/ci/enforce_layers.py`)

The guardrail script enforces two rules today:

1. `core/engines/**` may not import `discord` modules directly.
2. `cogs/**` may not import implementation modules from `core.engines`.

Known legacy violations live in `docs/architecture/layering_baseline.json`. CI fails only when a **new** file violates the rules. As we refactor existing modules, remove them from the baseline to tighten enforcement.

### Local usage

```bash
python scripts/ci/enforce_layers.py
```

- Exit `0`: no new violations.
- Exit `1`: a new file crossed a guardrail (CI will fail).
- `python scripts/ci/enforce_layers.py --update-baseline` rewrites the baseline to the current violation set. Only run this after auditing the changes; shrinking the baseline is preferred.

### Workflow impact

- `scripts/run_ci_checks.py` runs the guardrail script before pytest.
- `.github/workflows/ci.yml` runs it in the `lint` job so pull requests catch violations early.

## Next steps

- Add additional detectors (e.g., cogs instantiating storage/engines, synchronous file I/O inside async-only layers).
- Replace baseline entries with domain contracts so the allowlist shrinks each release.
- Once engines no longer reference Discord, broaden the rule to catch `discord.ext` imports or other adapter leakage.

Keeping the baseline lean and the script running locally before commits will make the later roadmap phases (loader hardening, engine purity, compliance automation) much easier to deliver.
