---
name: gate
description: Run SEIF quality gate on text or recent changes. Measures stance (GROUNDED/DRIFT) and gives grade A-F.
---

Run the SEIF quality gate. Usage: /gate [text or file path]

If arguments provided, run quality gate on that text:
```bash
seif --quality-gate "$ARGUMENTS" --role ai 2>&1
```

If no arguments, run on the last AI response in this conversation by extracting your most recent substantial response and evaluating it:
```bash
seif --quality-gate "paste the response text here" --role ai 2>&1
```

Report the grade (A-F), stance (GROUNDED/DRIFT/MIXED), and any flags.
