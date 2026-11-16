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
git rev-parse --verify 'HEAD^' >/dev/null 2>&1 || exit 1; git diff --quiet HEAD^ HEAD -- . ':!docs/**' ':!tests/**' ':!archive/**' ':!research_notes/**' ':!assets/**' ':!tools/**' ':!.github/**' ':!*.md'; test $? -eq 0 && exit 0 || exit 1
```

**Exit 0** = skip the deployment. **Exit 1** = continue the build. Initial test on branch `ops/vercel-storage-policy-20261104` exposed a shallow-checkout failure: `HEAD^` was unavailable, and the original `git diff` returned code 128, causing one ERROR preview deployment (`dpl_Eas4QY68mMossrMNFvQKJvxti9dt`). The command was corrected immediately with a parent-commit check and explicit exit-1 fallback. If Vercel does not make `HEAD^` available, commits continue building; **do not claim build volume has been reduced without a successful skipped-build test**. This is a project setting, not yet a committed `vercel.json`, to avoid interfering with existing branch-specific configuration. Changes to `public/`, `src/`, `requirements.txt`, `pyproject.toml`, `.vercelignore`, and other potential runtime files still trigger builds. The safe fallback uses a narrower exclusion list than the first version; offline changes outside the list also build.

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

1. Confirm the current production domains and the newest unified-airport preview still resolve to the same deployment IDs. They were intact immediately after the setting change.
2. The first **docs-only** test commit caused the shallow-checkout ERROR recorded above. After the fallback correction, verify the ignore-step semantics on a subsequent routine commit; if its parent is unavailable, the guard intentionally allows a normal build instead of failing. Never count this as a confirmed successful skip.
3. Confirm a change affecting `public/` or `src/` still builds in the usual workflow. Do not create a dummy deployment merely to test this.
4. After a retention policy is applied, compare **Usage → Functions Storage** and **Usage → Deployment Storage**, filtered by project and date; note any rolling-window or display delay.
5. Preserve A9, A10, R6 and the unified airport baseline in Git/Blendstra and keep reference deployment URLs in the release log before any manual cleanup.

**Not authorised by this document:** direct deletion of deployments, manipulation of production aliases, physics dependency removal or changes to saved Blendstra models.
