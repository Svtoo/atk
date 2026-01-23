# Full Plugin

A complete test plugin with all optional fields and lifecycle scripts.

## Usage

This plugin is for testing ATK functionality. The scripts just echo messages.

## Environment Variables

- `FULL_PLUGIN_API_KEY` (required, secret): API key for the plugin
- `FULL_PLUGIN_DEBUG` (optional): Enable debug mode (default: false)

## Lifecycle

- `install.sh`: Simulates installation
- `start.sh`: Simulates starting the service
- `stop.sh`: Simulates stopping the service
- `status.sh`: Returns exit 0 (running)

