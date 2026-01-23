"""Exit codes for ATK CLI commands.

All commands use consistent exit codes as defined in atk-commands-spec.md.
"""

# Success
SUCCESS = 0

# Errors
GENERAL_ERROR = 1
INVALID_ARGS = 2
HOME_NOT_INITIALIZED = 3
PLUGIN_NOT_FOUND = 4
PLUGIN_INVALID = 5
DOCKER_ERROR = 6
GIT_ERROR = 7

