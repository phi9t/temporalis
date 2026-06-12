---
name: github-pages-release-verification
description: Use when a Temporalis change is pushed and success depends on GitHub Pages serving updated explorer data, generated JSON, static assets, or hosted documentation rather than only a clean git push.
---

# GitHub Pages Release Verification

Use this repo-local skill after pushing Temporalis explorer or generated-data changes when the acceptance criterion is hosted content.

## Start Here

Run:

```bash
make kilvin-pages-check
```

For a non-default Pages URL:

```bash
make kilvin-pages-check PAGES_URL=https://example.github.io/temporalis/data/kilvin/internals.json
```

## Verification Rule

A push is not the same as a deployed page. Verify the public URL contains the expected generated content.

The default Kilvin check looks for:

- `laptop scale`
- `uv lock --check`
- `local allocator`
- `k3s`

## Failure Modes

- HTTP failure: Pages may be unavailable or the URL may be wrong.
- Content not updated: deployment may still be propagating, or the branch/pages source did not publish.
- Partial content: generated data may be stale even when HTML assets changed.

## Related Docs

```text
docs/kilvin/proof-checklist.md
```
