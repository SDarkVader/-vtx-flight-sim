# Unified dashboard candidate

The cockpit and flight-test dashboard are served by the same Python process.
The cockpit is at / and the dashboard at /dashboard/. The dashboard reads
/api/observe and /api/runs from that process, and can prefill a run assessment.
Assessments remain in the existing Site's versioned /api/data store; the proxy
forwards its conflict responses. It requires network access to that Site.

dashboard-page.tsx is the dashboard React source. The compiled browser bundle
and stylesheet are in public/dashboard/. It was built with React 19.2.6 and
esbuild using --bundle --minify --format=esm --jsx=automatic; the entry mounts
Page into #root. The original stylesheet comes from the existing Site.

Run an isolated candidate with a separate data directory and an unused port:
  set PYTHONPATH=src
  set VTX_DATA_ROOT=<separate test directory>
  python -m uvicorn vtx.dashboard_site:app --host 127.0.0.1 --port 18903

This candidate is not a replacement for the protected running flight. The
existing hosted Site is still a separate deployment. Secure remote access,
mobile device acceptance, automatic experiment execution, full control checks
and live-flight promotion remain unverified.
