#!/usr/bin/env bash
# Shared traversal for portable package content. Prune caches before any copy.
filtered_entries() {
  find "$1" \( -type d \( -name '__pycache__' -o -name '.gitlab-ci-local' \) -prune \) -o \
    \( -type f \( -name '*.pyc' -o -name '*.pyo' \) \) -o -print0
}

copy_filtered_tree() {
  local source="${1%/}" target="${2%/}" entry relative
  mkdir -p "$target"
  filtered_entries "$source" | while IFS= read -r -d '' entry; do
    [ "$entry" = "$source" ] && continue
    relative="${entry#"$source"/}"
    if [ -d "$entry" ] && [ ! -L "$entry" ]; then
      mkdir -p "$target/$relative"
    else
      mkdir -p "$(dirname "$target/$relative")"
      if [ -f "$entry" ] || [ -L "$entry" ]; then
        cp -P "$entry" "$target/$relative"
      else
        cp -R -P "$entry" "$target/$relative"
      fi
    fi
  done
}
