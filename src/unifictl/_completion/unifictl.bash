# Bash completion for unifictl. Install: copy to
# ~/.local/share/bash-completion/completions/unifictl
# Generated and managed by `unifictl completion install`.

_unifictl_complete() {
    local cur prev words cword
    _init_completion -n : || return

    local response_raw
    local -a response_lines

    response_raw="$(unifictl __complete bash "${COMP_WORDS[@]:0:$COMP_CWORD}" "${COMP_WORDS[$COMP_CWORD]}" 2>/dev/null)"

    mapfile -t response_lines <<< "$response_raw"

    if [[ "${response_lines[0]:-}" == "__UNIFICTL_COMPLETE_FILES__" ]]; then
        COMPREPLY=()
        compopt -o default 2>/dev/null || true
        compopt -o filenames 2>/dev/null || true
        return
    fi

    local current="${COMP_WORDS[$COMP_CWORD]}"
    COMPREPLY=()
    local cand
    for cand in "${response_lines[@]}"; do
        [[ -z "$cand" ]] && continue
        [[ "$cand" == "$current"* ]] || continue
        COMPREPLY+=("$(printf '%q' "$cand")")
    done

    compopt -o nospace 2>/dev/null || true
}

complete -F _unifictl_complete unifictl
