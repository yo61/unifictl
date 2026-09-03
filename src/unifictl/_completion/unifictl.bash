# Bash completion for unifictl. Install: copy to
# ~/.local/share/bash-completion/completions/unifictl
# Generated and managed by `unifictl completion install`.

_unifictl_complete() {
  # bash splits COMP_WORDS on COMP_WORDBREAKS, which contains ':' -- so a
  # partially typed MAC arrives as `70 : a7` and every candidate would be
  # filtered out. `_init_completion -n :` rebuilds the line with ':' left
  # joined; `words`/`cword`/`cur` are those repaired values, and reading
  # COMP_WORDS directly instead would reintroduce the split.
  #
  # `prev` is unused but must be declared: _init_completion assigns to all
  # four by name, and an undeclared one would leak into the global scope.
  # shellcheck disable=SC2034
  local cur prev words cword
  _init_completion -n : || return

  local response_raw
  local -a response_lines

  response_raw="$(unifictl __complete bash "${words[@]:0:$cword}" "${words[$cword]}" 2> /dev/null)"

  mapfile -t response_lines <<< "$response_raw"

  if [[ "${response_lines[0]:-}" == "__UNIFICTL_COMPLETE_FILES__" ]]; then
    COMPREPLY=()
    compopt -o default 2> /dev/null || true
    compopt -o filenames 2> /dev/null || true
    return
  fi

  COMPREPLY=()
  local cand
  for cand in "${response_lines[@]}"; do
    [[ -z "$cand" ]] && continue
    [[ "$cand" == "$cur"* ]] || continue
    COMPREPLY+=("$(printf '%q' "$cand")")
  done

  # readline still uses the real COMP_WORDBREAKS when deciding how much of the
  # line a completion replaces, so colon-bearing candidates must be trimmed to
  # the part after the last ':' or they insert doubled.
  if declare -F _comp_ltrim_colon_completions > /dev/null; then
    _comp_ltrim_colon_completions "$cur"
  else
    __ltrim_colon_completions "$cur"
  fi

  compopt -o nospace 2> /dev/null || true
}

complete -F _unifictl_complete unifictl
