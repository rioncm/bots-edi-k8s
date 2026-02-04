#!/usr/bin/env python
"""
Simple Django development server runner for testing
"""
import os
import sys
from pathlib import Path

# Add directories to path
script_dir = Path(__file__).parent.absolute()
bots_dir = script_dir.parent / 'bots' / 'bots'
config_dir = script_dir.parent / 'bots_config'

sys.path.insert(0, str(bots_dir))
sys.path.insert(0, str(config_dir))

# Set environment
os.environ['DJANGO_SETTINGS_MODULE'] = 'test_settings'
os.environ['BOTS_CONFIG_DIR'] = str(config_dir)

# Run Django development server
if __name__ == '__main__':
    import django
    from django.core.management import execute_from_command_line
    from bots import botsglobal, botsinit
    
    django.setup()
    
    # Initialize bots config
    if botsglobal.ini is None:
        botsglobal.ini = botsinit.BotsConfig()
        config_file = config_dir / 'bots.ini'
        if config_file.exists():
            botsglobal.ini.read(str(config_file))
    
    # Get port from command line args or use default
    port = sys.argv[1] if len(sys.argv) > 1 else '8080'
    
    # Run server
    execute_from_command_line(['manage.py', 'runserver', port])
