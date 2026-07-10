# Fish completion for unifictl. Install: copy to
# ~/.config/fish/completions/unifictl.fish (auto-loaded by fish).
# Generated and managed by `unifictl completion install`.

function __unifictl_complete
    set -l prev (commandline -opc)
    set -l current (commandline -ct)
    set -l result (unifictl __complete fish $prev "$current" 2>/dev/null)
    if test (count $result) -gt 0; and test $result[1] = "__UNIFICTL_COMPLETE_FILES__"
        __fish_complete_path "$current"
        return
    end
    for line in $result
        echo $line
    end
end

complete -c unifictl -f -a "(__unifictl_complete)"
