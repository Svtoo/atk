# demo-search.tape
# Shows the ATK registry: 11 vetted plugins with installed-status markers.
# Records: atk search
#
# Note: atk search does a live git sparse-clone from GitHub — allow 15s.
# For faster recording on repeat runs, the network call is the only delay.
#
# Produce the GIF:
#   vhs assets/tapes/demo-search.tape

Output assets/demo-search.gif

Set Shell "zsh"
Set FontSize 15
Set Width 1200
Set Height 700
Set Theme "Catppuccin Mocha"
Set Padding 24
Set TypingSpeed 80ms

Sleep 800ms

Type "atk search"
Sleep 400ms
Enter

# Network fetch + display. Budget 20s to be safe on a slow connection.
Sleep 20s

