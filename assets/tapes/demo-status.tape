# demo-status.tape
# Shows atk status: the live table of running services with port health checks.
# Records: atk status
#
# Best recorded with at least one service running (openmemory, langfuse, etc.)
# so the table has real rows to show.
#
# Produce the GIF:
#   vhs assets/tapes/demo-status.tape

Output assets/demo-status.gif

Set Shell "zsh"
Set FontSize 15
Set Width 1200
Set Height 500
Set Theme "Catppuccin Mocha"
Set Padding 24
Set TypingSpeed 80ms

Sleep 800ms

Type "atk status"
Sleep 400ms
Enter

# Port checks are near-instant. 3s is plenty.
Sleep 3s

