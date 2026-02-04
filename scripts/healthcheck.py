#!/usr/bin/env python3
"""
CLI Health Check for Bots-EDI Services

This script provides health check functionality for non-web services
(engine, jobqueueserver, dirmonitor) that can be used in Kubernetes
exec probes or for manual health verification.

Usage:
    python healthcheck.py [--check TYPE] [--config-dir DIR]

Exit codes:
    0 - Healthy
    1 - Unhealthy
    2 - Error/Exception

Check types:
    live     - Basic liveness (default)
    ready    - Readiness (database + paths)
    startup  - Startup (full initialization check)
"""

import os
import sys
import argparse
import json
from pathlib import Path


def setup_django_environment(config_dir=None):
    """Set up Django environment for health checks"""
    
    # Add bots directory to path
    script_dir = Path(__file__).parent.absolute()
    bots_dir = script_dir.parent / 'bots'
    sys.path.insert(0, str(bots_dir))
    
    # Set config directory if provided
    if config_dir:
        config_path = Path(config_dir).absolute()
        os.environ['BOTS_CONFIG_DIR'] = str(config_path)
        # Also add config directory to path for settings module
        sys.path.insert(0, str(config_path))
    
    # Set Django settings module
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
    
    # Import Django and setup
    import django
    django.setup()
    
    # Initialize bots configuration
    from bots import botsglobal, botsinit
    if botsglobal.ini is None:
        botsglobal.ini = botsinit.BotsConfig()
        config_dir_path = config_dir if config_dir else os.environ.get('BOTS_CONFIG_DIR', '../bots_config')
        config_file = os.path.join(config_dir_path, 'bots.ini')
        if os.path.exists(config_file):
            botsglobal.ini.read(config_file)


def check_liveness():
    """
    Basic liveness check - process is running
    Always returns success if we got this far
    """
    return {
        'status': 'ok',
        'check': 'liveness',
        'message': 'Process is alive'
    }, 0


def check_readiness():
    """
    Readiness check - can accept work
    
    Checks:
    - Database connectivity
    - Critical paths exist
    """
    from django.db import connection
    from bots import botsglobal
    
    checks = {
        'database': False,
        'botssys': False,
        'usersys': False,
    }
    errors = []
    
    # Check database connection
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            checks['database'] = True
    except Exception as e:
        errors.append(f"Database check failed: {str(e)[:100]}")
    
    # Check botssys directory
    try:
        if botsglobal.ini is None:
            raise RuntimeError("botsglobal.ini not initialized")
        
        botssys = botsglobal.ini.get('directories', 'botssys')
        if os.path.isdir(botssys):
            checks['botssys'] = True
        else:
            errors.append(f"botssys directory not found: {botssys}")
    except Exception as e:
        errors.append(f"botssys check failed: {str(e)[:100]}")
    
    # Check usersys directory
    try:
        if botsglobal.ini is None:
            raise RuntimeError("botsglobal.ini not initialized")
        
        # Try usersysabs first (set after full initialization)
        try:
            usersys = botsglobal.ini.get('directories', 'usersysabs')
        except:
            # Fall back to usersys (relative path)
            usersys = botsglobal.ini.get('directories', 'usersys', 'usersys')
            # Make it absolute if relative
            if not os.path.isabs(usersys):
                config_dir = botsglobal.ini.get('directories', 'config', '.')
                usersys = os.path.join(os.path.dirname(config_dir), usersys)
        
        if os.path.isdir(usersys):
            checks['usersys'] = True
        else:
            errors.append(f"usersys directory not found: {usersys}")
    except Exception as e:
        errors.append(f"usersys check failed: {str(e)[:100]}")
    
    all_passed = all(checks.values())
    
    result = {
        'status': 'ready' if all_passed else 'not_ready',
        'check': 'readiness',
        'checks': checks,
    }
    
    if errors:
        result['errors'] = errors
    
    exit_code = 0 if all_passed else 1
    return result, exit_code


def check_startup():
    """
    Startup check - initialization complete
    
    Checks:
    - Database accessible with required tables
    - Bots directories set up
    - Configuration loaded
    """
    from django.db import connection
    from bots import botsglobal
    
    checks = {
        'database': False,
        'tables': False,
        'botssys': False,
        'usersys': False,
        'config': False,
    }
    errors = []
    
    # Check database and tables
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            checks['database'] = True
            
            table_names = connection.introspection.table_names(cursor)
            required_tables = ['channel', 'routes', 'ta', 'mutex']
            
            if all(table in table_names for table in required_tables):
                checks['tables'] = True
            else:
                missing = [t for t in required_tables if t not in table_names]
                errors.append(f"Missing tables: {', '.join(missing)}")
    except Exception as e:
        errors.append(f"Database check failed: {str(e)[:100]}")
    
    # Check botssys and data directory
    try:
        if botsglobal.ini is None:
            raise RuntimeError("botsglobal.ini not initialized")
        
        botssys = botsglobal.ini.get('directories', 'botssys')
        if os.path.isdir(botssys):
            data_dir = os.path.join(botssys, 'data')
            if os.path.isdir(data_dir) or os.path.isdir(botsglobal.ini.get('directories', 'data')):
                checks['botssys'] = True
            else:
                errors.append("botssys data directory not found")
        else:
            errors.append(f"botssys directory not found: {botssys}")
    except Exception as e:
        errors.append(f"botssys check failed: {str(e)[:100]}")
    
    # Check usersys
    try:
        if botsglobal.ini is None:
            raise RuntimeError("botsglobal.ini not initialized")
        
        # Try usersysabs first (set after full initialization)
        try:
            usersys = botsglobal.ini.get('directories', 'usersysabs')
        except:
            # Fall back to usersys (relative path)
            usersys = botsglobal.ini.get('directories', 'usersys', 'usersys')
            # Make it absolute if relative
            if not os.path.isabs(usersys):
                config_dir = botsglobal.ini.get('directories', 'config', '.')
                usersys = os.path.join(os.path.dirname(config_dir), usersys)
        
        if os.path.isdir(usersys):
            checks['usersys'] = True
        else:
            errors.append(f"usersys directory not found: {usersys}")
    except Exception as e:
        errors.append(f"usersys check failed: {str(e)[:100]}")
    
    # Check config
    try:
        # Check if ini is loaded and has at least some configuration
        if botsglobal.ini and botsglobal.ini.has_section('directories'):
            checks['config'] = True
        else:
            errors.append("Config not loaded or invalid")
    except Exception as e:
        errors.append(f"Config check failed: {str(e)[:100]}")
    
    all_passed = all(checks.values())
    
    result = {
        'status': 'started' if all_passed else 'starting',
        'check': 'startup',
        'checks': checks,
    }
    
    if errors:
        result['errors'] = errors
    
    exit_code = 0 if all_passed else 1
    return result, exit_code


def main():
    parser = argparse.ArgumentParser(
        description='Health check for Bots-EDI services',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Liveness check (default)
  python healthcheck.py
  
  # Readiness check
  python healthcheck.py --check ready
  
  # Startup check
  python healthcheck.py --check startup
  
  # With custom config directory
  python healthcheck.py --check ready --config-dir /path/to/config

Exit codes:
  0 - Healthy
  1 - Unhealthy
  2 - Error/Exception
        """
    )
    
    parser.add_argument(
        '--check',
        choices=['live', 'ready', 'startup'],
        default='live',
        help='Type of health check to perform (default: live)'
    )
    
    parser.add_argument(
        '--config-dir',
        help='Path to bots configuration directory (containing bots.ini and settings.py)'
    )
    
    parser.add_argument(
        '--json',
        action='store_true',
        help='Output result as JSON'
    )
    
    parser.add_argument(
        '--quiet',
        action='store_true',
        help='Suppress output (exit code only)'
    )
    
    args = parser.parse_args()
    
    try:
        # Setup Django environment
        setup_django_environment(args.config_dir)
        
        # Run appropriate check
        if args.check == 'live':
            result, exit_code = check_liveness()
        elif args.check == 'ready':
            result, exit_code = check_readiness()
        elif args.check == 'startup':
            result, exit_code = check_startup()
        else:
            print(f"Unknown check type: {args.check}", file=sys.stderr)
            return 2
        
        # Output result
        if not args.quiet:
            if args.json:
                print(json.dumps(result, indent=2))
            else:
                status = result['status']
                check_type = result['check']
                print(f"Health Check: {check_type}")
                print(f"Status: {status}")
                
                if 'checks' in result:
                    print("\nChecks:")
                    checks = result['checks']
                    if isinstance(checks, dict):
                        for check_name, check_passed in checks.items():
                            symbol = '✓' if check_passed else '✗'
                            print(f"  {symbol} {check_name}")
                
                if 'errors' in result:
                    print("\nErrors:")
                    for error in result['errors']:
                        print(f"  - {error}")
        
        return exit_code
        
    except Exception as e:
        if not args.quiet:
            print(f"Health check error: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc(file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
