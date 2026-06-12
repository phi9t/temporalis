# Release Checklist

Run this before publishing a release branch or verifying GitHub Pages.

CI runs fresh-clone-safe checks. Maintainers run `make verify-release` when the managed upstream Temporal checkouts are present and source-grounded data needs regeneration.

```bash
make quickstart
make verify-release
make explorer-build
```

When local docker/Colima/k3s prerequisites are available, also run:

```bash
make kilvin-doctor
kilvin-py/infra/up.sh
make runtime-proof
```

After pushing `phi9t-mainline`, verify hosted Pages content:

```bash
make kilvin-pages-check
```

Confirm:

- README and docs describe Tier 0, Tier 1, and Tier 2.
- The explorer does not advertise a visible Hacker's Guide tab.
- Generated Lifecycle and Control Path refs are pinned to upstream commits.
- `.agent/` contains no durable release knowledge.
- Unrelated local artifacts are not staged.
