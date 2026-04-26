#!/usr/bin/env bash
set -euo pipefail

usage() {
    cat <<'USAGE'
Usage:
  ./scripts/upload-patch-notes.sh <topic-name> <file-or-directory> [...]

Examples:
  ./scripts/upload-patch-notes.sh agent-notes ~/notes/agent/*.md
  ./scripts/upload-patch-notes.sh devops-checklist ~/notes/devops/
USAGE
}

if [ "$#" -lt 2 ]; then
    usage
    exit 1
fi

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
topic_raw="$1"
shift

# Keep topic names path-safe: replace slashes/spaces with hyphens, then trim edge hyphens.
topic="$(printf '%s' "$topic_raw" | sed -E 's#[/[:space:]]+#-#g; s#^-+##; s#-+$##')"

if [ -z "$topic" ] || [ "$topic" = "." ] || [ "$topic" = ".." ]; then
    echo "Error: topic name must not be empty, '.', or '..'." >&2
    exit 1
fi

target_dir="$repo_root/_patch/$topic"
index_file="$target_dir/00-index.md"
mkdir -p "$target_dir"

if [ ! -f "$index_file" ]; then
    cat >"$index_file" <<EOF
# $topic 原始笔记处理清单

- 目标分类：
- 预期输出：
- 处理状态：待整理

## 资料列表
EOF
fi

unique_destination() {
    local source_file="$1"
    local base
    local name
    local ext
    local candidate
    local counter

    base="$(basename "$source_file")"
    name="${base%.*}"
    ext=""
    if [ "$name" != "$base" ]; then
        ext=".${base##*.}"
    fi

    candidate="$target_dir/$base"
    counter=1
    while [ -e "$candidate" ]; do
        candidate="$target_dir/${name}-${counter}${ext}"
        counter=$((counter + 1))
    done

    printf '%s\n' "$candidate"
}

copy_one_file() {
    local source_file="$1"
    local destination
    local uploaded_date

    if [ ! -f "$source_file" ]; then
        return
    fi

    destination="$(unique_destination "$source_file")"
    cp -p "$source_file" "$destination"
    uploaded_date="$(date +%Y-%m-%d)"
    printf -- '- [ ] `%s` - uploaded %s\n' "$(basename "$destination")" "$uploaded_date" >>"$index_file"
    echo "Uploaded: $source_file -> ${destination#$repo_root/}"
}

for input_path in "$@"; do
    if [ -d "$input_path" ]; then
        while IFS= read -r -d '' file_path; do
            copy_one_file "$file_path"
        done < <(find "$input_path" -type f ! -name '.DS_Store' ! -path '*/.git/*' -print0 | sort -z)
    elif [ -f "$input_path" ]; then
        copy_one_file "$input_path"
    else
        echo "Warning: skipped missing path: $input_path" >&2
    fi
done

echo
echo "Patch topic ready: _patch/$topic"
echo "Next step: review files, then commit and push _patch/$topic."
