# Time Log

## Phase 1-6 Backend Scaffold

- Start: 2026-06-09 09:29 EDT
- End: 2026-06-09 09:40 EDT
- Biggest blocker encountered: None yet
- What caused rework: The local Python runtimes did not have PyMuPDF installed,
  so verification needed a project virtual environment.
- What I would change in the spec next time: Specify whether `app.py` and
  `cli.py` should live at the repository root or inside the package; Cloud Run's
  `CMD ["python", "app.py"]` points most naturally to root-level entry points.

## Spec Rename Check

- Start: 2026-06-09 EDT
- End: 2026-06-09 EDT
- Biggest blocker encountered: None
- What caused rework: ADR/build plan renamed the public project, repo, subdomain,
  and CORS origin from pdf-print-prep to print-friendly-pdf.
- What I would change in the spec next time: Keep the starting prompt synchronized
  with ADR/build plan renames so implementation names do not drift.
