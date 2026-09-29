# demo-hero.tape
# Shows the killer feature: wire one MCP to multiple agents in one command.
# Records: atk plug hindsight --claude --auggie -y
#
# Prerequisites before recording:
#   - hindsight plugin installed (atk add hindsight)
#   - claude CLI on PATH (Claude Code installed)
#   - auggie CLI on PATH (Augment Code installed)
#
# Produce the GIF:
#   vhs assets/tapes/demo-hero.tape

Output assets/demo-hero.gif

Set Shell "zsh"
Set FontSize 15
Set Width 1200
Set Height 700
Set Theme "Catppuccin Mocha"
Set Padding 24
Set TypingSpeed 80ms

Sleep 500ms

# Silently reset state so the add demo is clean (hidden from the viewer)
Hide
Type "atk unplug hindsight --claude --auggie -y"
Enter
Sleep 5s
Type "clear"
Enter
Show

Type "atk plug hindsight --claude --auggie -y"
Sleep 400ms
Enter

# claude mcp add-json + skill injection, then auggie mcp add-json + skill injection.
# Both CLI calls + skill steps take ~8s total.
Sleep 12s

