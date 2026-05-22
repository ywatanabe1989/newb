#!/bin/bash
# Run every numbered newb example and capture stdout into <stem>_out/.
# Both examples are offline (no Anthropic / Docker spend).
#
#   $ ./examples/00_run_all.sh

LOG_FILE=".$(basename "$0").log"

main() {
    local here
    here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    cd "$here" || return 1

    local py="python"
    [ -x "$here/../.venv/bin/python" ] && py="$here/../.venv/bin/python"

    for ex in 0[1-9]_*.py 1[0-9]_*.py; do
        [ -f "$ex" ] || continue
        local stem="${ex%.py}"
        local out_dir="${stem}_out"
        mkdir -p "$out_dir"
        echo "==> $ex"
        "$py" "$ex" | tee "$out_dir/stdout.txt" || {
            echo "Error: $ex failed."
            return 1
        }
    done

    echo "All examples finished successfully."
    return 0
}

{ main "$@"; } 2>&1 | tee "$LOG_FILE"
