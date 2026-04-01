---
name: sync
description: Sync SEIF context — re-scan project and update .seif/ modules
---

Synchronize SEIF context for the current project:

```bash
seif --sync 2>&1
```

After sync, show what changed:
```bash
seif --status 2>&1 | head -20
```

If .seif/ doesn't exist yet, suggest running `seif --init` first.
