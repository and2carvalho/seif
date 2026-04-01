---
name: status
description: Show SEIF protocol status — loaded modules, classification, quality metrics
---

Show current SEIF protocol status:

1. Check if .seif/ exists in current directory or parents
2. Show loaded modules and their relevance scores:
```bash
python3 -c "
import json, os

# Find .seif/
d = os.getcwd()
while d != '/':
    if os.path.isdir(os.path.join(d, '.seif')):
        break
    d = os.path.dirname(d)

seif_dir = os.path.join(d, '.seif')
if not os.path.isdir(seif_dir):
    print('No .seif/ found. Run: seif --init')
    exit()

# Config
cfg_path = os.path.join(seif_dir, 'config.json')
if os.path.isfile(cfg_path):
    cfg = json.load(open(cfg_path))
    print(f'Autonomous: {cfg.get(\"autonomous_context\", False)}')
    print(f'Quality threshold: {cfg.get(\"quality_threshold\", \"C\")}')
    print()

# Mapper
m_path = os.path.join(seif_dir, 'mapper.json')
if os.path.isfile(m_path):
    m = json.load(open(m_path))
    modules = m.get('modules', {})
    print(f'Total modules: {len(modules)}')
    by_class = {}
    for name, info in modules.items():
        c = info.get('classification', 'PUBLIC')
        by_class[c] = by_class.get(c, 0) + 1
    for c, n in sorted(by_class.items()):
        print(f'  {c}: {n}')
    print()
    top = sorted(modules.items(), key=lambda x: x[1].get('relevance', 0), reverse=True)[:5]
    print('Top 5 by relevance:')
    for name, info in top:
        print(f'  {name} (relevance={info.get(\"relevance\",0):.2f}, {info.get(\"category\",\"?\")})')
" 2>&1
```

3. Show any pending observations or issues.
