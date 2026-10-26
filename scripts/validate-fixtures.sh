#!/usr/bin/env bash
set -euo pipefail

# 校验合成 fixtures 的最低规模和 JSON 格式，不访问真实业务系统。
knowledge_count=$(find fixtures/knowledge -maxdepth 1 -type f -name '*.md' | wc -l | tr -d ' ')
[ "$knowledge_count" -ge 6 ]
python3 - <<'PY'
import json
from pathlib import Path
for path in Path('fixtures').glob('*/*.json'):
    json.loads(path.read_text())
print('fixture json: ok')
PY
printf 'fixture validation passed: knowledge=%s\n' "$knowledge_count"
