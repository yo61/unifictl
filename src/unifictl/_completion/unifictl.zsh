#compdef unifictl
# Zsh completion for unifictl. Install: copy to a dir in $fpath as `_unifictl`,
# then `autoload -U compinit; compinit`. Default install location is
# ~/.zfunc/_unifictl (unifictl completion install will set this up).
# Generated and managed by `unifictl completion install`.

_unifictl() {
    local -a candidates
    candidates=("${(@f)$(unifictl __complete zsh "${(@)words[1,$CURRENT-1]}" "${words[$CURRENT]}" 2>/dev/null)}")

    if [[ "${candidates[1]:-}" == "__UNIFICTL_COMPLETE_FILES__" ]]; then
        _files
        return
    fi

    compadd -a candidates
}

_unifictl "$@"
