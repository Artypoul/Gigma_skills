#!/usr/bin/env bash
# Синхронизирует Codex-копию скилов из канона plugins/ в .codex/.
# Canonical source = plugins/<plugin>/{skills,reference}; Codex reads .codex/skills + .codex/reference.
# Запуск: bash sync-codex.sh  (из любого места — скрипт сам перейдёт в корень репо).
set -euo pipefail
cd "$(dirname "$0")"
source scripts/sync-cache-filter.sh

# Пересобираем .codex с нуля, чтобы не оставлять удалённые скилы.
rm -rf .codex/skills .codex/reference
mkdir -p .codex/skills .codex/reference

for plugin in plugins/*/; do
  [ -d "${plugin}skills" ]    && copy_filtered_tree "${plugin}skills" .codex/skills
  [ -d "${plugin}reference" ] && copy_filtered_tree "${plugin}reference" .codex/reference
done

skills=$(find .codex/skills -name SKILL.md | wc -l | tr -d ' ')
refs=$(find .codex/reference -type f | wc -l | tr -d ' ')
echo "Codex sync OK: ${skills} skills, ${refs} reference files."
