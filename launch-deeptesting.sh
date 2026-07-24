#!/usr/bin/env bash
set -u

project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
python_bin="$project_dir/.venv/bin/python"

if [[ ! -x "$python_bin" ]]; then
  message="DeepTest 2.0 is not set up yet. Create the .venv and install the project first."
  if command -v zenity >/dev/null 2>&1; then
    zenity --error --title="DeepTest 2.0" --text="$message"
  else
    printf '%s\n' "$message" >&2
  fi
  exit 1
fi

cd "$project_dir"
exec "$python_bin" -m deeptesting.gui
