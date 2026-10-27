# PatchPilot — Evaluation & Benchmarking

## Methodology

PatchPilot measures coding agent effectiveness using deterministic verification rather than soft conversational assertions.

### Benchmark Metrics

1. **Verified Repair Rate:**
   Percentage of tasks where:
   - Target failing tests pass.
   - All previously passing baseline tests continue to pass.
   - The test suite returns exit code 0.
2. **Regression Rate:**
   Percentage of repair attempts where previously passing tests are broken by the agent's patch.
3. **Attempt & Step Efficiency:**
   Average number of repair attempts (1–3) and tool invocations required to converge on a verified fix.
4. **Execution Latency:**
   Total wall-clock duration from task submission to verified patch generation.
5. **Original Repository Invariance:**
   Hard binary check (100% required) verifying zero mutations leaked into original repositories.

## Running the Smoke Benchmark

Benchmark evaluation runs against `evals/cases/manifest.json`. By default, cases execute safely inside isolated Docker containers:

```powershell
# Safe containerized benchmark execution (default)
patchpilot eval --suite smoke

# Explicit unsafe host execution (prints warning)
patchpilot eval --suite smoke --allow-host-execution
```

Results are reported in a structured summary table and appended to `.patchpilot-data/events.jsonl`.
