# VTX Vercel storage and build policy

**Recorded:** 2026-11-04. **Scope:** `SDarkVader/-vtx-flight-sim` only; project `prj_mkvyI93HIHmp9ShQBbnGpYt5FTty`.

## Findings and constraints

- Vercel reported 153 deployments during 1–4 November 2026: 128 non-production and 25 production. A large number are iterative preview branches.
- The dashboard's previously reported **11.62 GB Functions Storage** has **not** been independently attributed to individual deployments. Avoid claiming storage savings without before/after project-level usage data.
- `.vercelignore` already excludes offline Blender CAD sources, many logs, tests, tools and engineering documentation. Do **not** exclude `public/` or the live GLB assets without checking all runtime references.
- The FastAPI runtime imports MuJoCo and NumPy. Removing physics dependencies is **not** an acceptable storage shortcut without an import graph, test run and flight-model validation.
- The local operator checkout may be behind remote and contain uncommitted flight/pilot work. Do not reset, clean, rebase, merge or overwrite it as part of storage maintenance.
- The current airport preview branch and production aliases are needed for testing and rollback; never delete or disable them as an automatic cleanup.

## Active project-level ignored build step

Configured using Vercel's `commandForIgnoringBuildStep` project setting on 2026-11-04:

```sh
git diff --quiet HEAD^ HEAD -- . ':!docs/**' ':!tests/**' ':!archive/**' ':!research_notes/**' ':!scratch/**' ':!refs/**' ':!assets/**' ':!tools/**' ':!engineering/**' ':!inputs/**' ':!results/**' ':!.github/**' ':!*.md'
```

**Exit 0** = skip the deployment (only non-deployment content changed). **Nonzero** = build. If the parent commit cannot be inspected, Git exits nonzero and Vercel proceeds with a build (safe fallback). This is a project setting, not yet a committed `vercel.json`, to avoid interfering with existing branch-specific configuration. Changes to `public/`, `src/`, `requirements.txt`, `pyproject.toml`, `.vercelignore`, and other potential runtime files still trigger builds.

If the application starts reading anything from an excluded directory during runtime, revise this rule before relying on it.

## Retention — pending dashboard action (not yet applied)

The connected Vercel API does not expose the deployment-retention mutation in the available tool schema. Do not represent these proposals as changes already made.

In **Vercel project → Settings → Security → Deployment Retention Policy**, review and choose:
- **Canceled:** 1–7 days.
- **Errored:** 7 days.
- **Preview:** 3–7 days when those values are available, after identifying any historical previews required for comparisons. Keep active integration branch aliases.
- **Production:** 90 days or the longer period required for rollbacks.

Vercel documents retention exemptions for active aliases and a protected set of recent ready deployments. It may take days to mark and reclaim old deployments. Confirm exact available durations in the UI before saving. Do not delete older production builds individually.

## Verification / success criteria

1. Confirm the current production domains and the newest unified-airport preview still resolve to the same deployment IDs.
2. Make a **docs-only** commit on a temporary test branch. It should be skipped; no new READY function bundle should be created. Use the Git-linked Vercel deployment entry to confirm whether it was skipped.
3. Confirm a change affecting `public/` or `src/` still builds in the usual workflow. Do not create a dummy deployment merely to test this.
4. After a retention policy is applied, compare **Usage → Functions Storage** and **Usage → Deployment Storage**, filtered by project and date; note any rolling-window or display delay.
5. Preserve A9, A10, R6 and the unified airport baseline in Git/Blendstra and keep reference deployment URLs in the release log before any manual cleanup.

**Not authorised by this document:** direct deletion of deployments, manipulation of production aliases, physics dependency removal or changes to saved Blendstra models.
