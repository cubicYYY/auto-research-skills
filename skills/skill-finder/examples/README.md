# Examples

Runnable walk-throughs of the common workflows.

## Offline — discovery in a fake workspace

Builds a synthetic `skill-repos/` layout with two fake vendored repos, runs
discovery + linking, and asserts the expected symlinks exist. No network.

```bash
uv run python examples/fake_workspace_offline.py
```

## Live — vendor a real upstream

Uses the GitHub search API + `git clone` to vendor a small real skill repo,
then lists what got linked. Requires network.

```bash
uv run python examples/vendor_live.py
```
