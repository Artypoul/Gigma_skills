#!/usr/bin/env bash
# Синхронизирует личную папку скилов Claude из канона plugins/.
# Canonical source = plugins/<plugin>/{skills,reference}; Claude читает
# ~/.claude/skills + ~/.claude/reference (скилы резолвят ../../reference/).
#
# Запуск: bash sync-claude.sh [--dest ПУТЬ] [--plugin ИМЯ]... [--adopt ИМЯ]... [--prune]
#   --dest    корень Claude (по умолчанию ~/.claude или $CLAUDE_HOME)
#   --plugin  синхронизировать только указанные плагины; можно повторять
#   --adopt   взять под управление чужой скил или reference-файл (перезаписать)
#   --prune   удалить управляемые скилы, которых больше нет в каноне
#
# ЛИЧНЫЕ СКИЛЫ НЕПРИКОСНОВЕННЫ. Имена в каноне и в личной папке пересекаются
# (например `feature`), поэтому скрипт ведёт реестр того, что создал сам, и
# отказывается перезаписывать директорию, которой в реестре нет. Исключение —
# директория, побайтно совпадающая с каноном: это результат прежней синхрони-
# зации, её можно принять молча.
set -euo pipefail
cd "$(dirname "$0")"
source scripts/sync-cache-filter.sh

dest="${CLAUDE_HOME:-$HOME/.claude}"
plugins=()
adopt=()
prune=0

while [ $# -gt 0 ]; do
  case "$1" in
    --dest)   dest="$2"; shift 2 ;;
    --plugin) plugins+=("$2"); shift 2 ;;
    --adopt)  adopt+=("$2"); shift 2 ;;
    --prune)  prune=1; shift ;;
    *) echo "Неизвестный аргумент: $1" >&2; exit 2 ;;
  esac
done

# Полный канон нужен всегда: --prune сверяется с ним, а не с выборкой,
# иначе `--plugin X --prune` снёс бы управляемые скилы всех остальных плагинов.
canon_all=()
for plugin in plugins/*/; do
  [ -d "${plugin}skills" ] || continue
  for skill in "${plugin}skills"/*/; do
    [ -f "${skill}SKILL.md" ] && canon_all+=("$(basename "$skill")")
  done
done

# Все имена плагинов проверяем ДО первой записи: иначе опечатка во втором
# аргументе оставила бы половину скилов скопированной, но не внесённой в реестр.
if [ ${#plugins[@]} -eq 0 ]; then
  for plugin in plugins/*/; do
    [ -d "${plugin}skills" ] && plugins+=("$(basename "$plugin")")
  done
else
  for name in "${plugins[@]}"; do
    [ -d "plugins/$name" ] || { echo "Нет такого плагина: $name" >&2; exit 2; }
  done
fi

manifest="$dest/.gigma-managed-skills"
ref_manifest="$dest/.gigma-managed-reference"
mkdir -p "$dest/skills" "$dest/reference"
touch "$manifest" "$ref_manifest"

is_managed()     { grep -Fxq "$1" "$manifest"; }
is_ref_managed() { grep -Fxq "$1" "$ref_manifest"; }
is_adopted()     { for a in ${adopt+"${adopt[@]}"}; do [ "$a" = "$1" ] && return 0; done; return 1; }
in_canon()       { for c in ${canon_all+"${canon_all[@]}"}; do [ "$c" = "$1" ] && return 0; done; return 1; }

file_list() { (cd "$1" && find . -type d \( -name __pycache__ -o -name .gitlab-ci-local \) -prune -o -type f ! -name '*.pyc' ! -name '*.pyo' -print | sort); }

# Неуправляемую копию можно принять только при полном совпадении файлов.
looks_like_our_copy() {
  local canon="$1" target="$2" rel
  [ ! -L "$target" ] && [ -f "$target/SKILL.md" ] || return 1
  # Non-regular entries cannot be proven identical by the regular-file comparison.
  [ -z "$(find "$target" \( ! -type d ! -type f -print -quit \))" ] || return 1
  [ -z "$(find "$canon" \( ! -type d ! -type f -print -quit \))" ] || return 1
  [ "$(file_list "$canon")" = "$(file_list "$target")" ] || return 1
  while IFS= read -r rel; do
    cmp -s "$canon/$rel" "$target/$rel" || return 1
  done < <(file_list "$canon")
}

synced=()
copied_refs=0
conflicts=()
ref_conflicts=()

for name in "${plugins[@]}"; do
  plugin="plugins/$name"

  if [ -d "$plugin/skills" ]; then
    for skill in "$plugin/skills"/*/; do
      [ -f "${skill}SKILL.md" ] || continue
      skill_name="$(basename "$skill")"
      target="$dest/skills/$skill_name"

      if { [ -e "$target" ] || [ -L "$target" ]; } && ! is_managed "$skill_name" && ! is_adopted "$skill_name" \
         && ! looks_like_our_copy "$skill" "$target"; then
        conflicts+=("$skill_name")
        continue
      fi

      # Пересоздаём скил целиком, чтобы не оставлять файлы, удалённые в каноне.
      rm -rf "$target"
      copy_filtered_tree "$skill" "$target"
      synced+=("$skill_name")
    done
  fi

  # Reference копируем пофайлово: у части плагинов он разложен по подпапкам, а
  # рядом может лежать личный файл с тем же путём — рекурсивное `cp -r` затёрло
  # бы его так же молча, как раньше затирался личный скил.
  if [ -d "$plugin/reference" ]; then
    while IFS= read -r rel; do
      rel="${rel#./}"
      src="$plugin/reference/$rel"
      dst="$dest/reference/$rel"
      if [ -e "$dst" ] && ! is_ref_managed "$rel" && ! is_adopted "$rel" \
         && ! cmp -s "$src" "$dst"; then
        ref_conflicts+=("$rel")
        continue
      fi
      mkdir -p "$(dirname "$dst")"
      cp "$src" "$dst"
      echo "$rel" >> "$ref_manifest"
      copied_refs=$((copied_refs + 1))
    done < <(cd "$plugin/reference" && find . -type d \( -name __pycache__ -o -name .gitlab-ci-local \) -prune -o -type f ! -name '*.pyc' ! -name '*.pyo' -print | sort)
  fi
done

if [ ${#conflicts[@]} -gt 0 ] || [ ${#ref_conflicts[@]} -gt 0 ]; then
  echo "ОТКАЗ: в $dest уже есть файлы, принадлежность которых не подтверждена:" >&2
  for c in ${conflicts+"${conflicts[@]}"};         do echo "  - skills/$c" >&2; done
  for c in ${ref_conflicts+"${ref_conflicts[@]}"}; do echo "  - reference/$c" >&2; done
  echo "Перезаписать осознанно: --adopt ИМЯ (повторять для каждого). Остальное синхронизировано." >&2
fi

# Удаляем только управляемое, чего больше нет в ПОЛНОМ каноне: скил другого
# плагина, не выбранного через --plugin, из канона никуда не делся.
removed=0
if [ "$prune" = "1" ]; then
  while IFS= read -r known; do
    [ -n "$known" ] || continue
    in_canon "$known" && continue
    if [ -d "$dest/skills/$known" ]; then
      rm -rf "$dest/skills/$known"
      removed=$((removed + 1))
    fi
  done < "$manifest"
fi

# Реестр = прежние управляемые (за вычетом удалённых) + синхронизированные сейчас.
{
  while IFS= read -r known; do
    [ -n "$known" ] || continue
    if [ "$prune" = "1" ] && ! in_canon "$known"; then continue; fi
    echo "$known"
  done < "$manifest"
  for s in ${synced+"${synced[@]}"}; do echo "$s"; done
} | sort -u > "$manifest.tmp"
mv "$manifest.tmp" "$manifest"
sort -u "$ref_manifest" -o "$ref_manifest"

echo "Claude sync OK: ${#synced[@]} skills, ${copied_refs} reference files -> ${dest}"
[ "$removed" -gt 0 ] && echo "Удалено устаревших управляемых скилов: ${removed}"
{ [ ${#conflicts[@]} -gt 0 ] || [ ${#ref_conflicts[@]} -gt 0 ]; } && exit 3
exit 0
