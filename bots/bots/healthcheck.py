"""
Health check endpoints for Kubernetes probes

Provides three types of health checks:
- /health/live    - Liveness probe (is container alive?)
- /health/ready   - Readiness probe (ready to accept traffic?)
- /health/startup - Startup probe (has initialization completed?)
"""

import os
import logging
from django.http import JsonResponse, HttpResponse
from django.db import connection
from django.conf import settings

from . import botsglobal


logger = logging.getLogger(__name__)


def health_live(request):
    """
    Liveness probe - indicates if the container is alive
    
    Returns 200 if the process is running.
    This is a simple check - if this endpoint responds, the container is alive.
    
    Kubernetes will restart the container if this fails.
    """
    return JsonResponse({
        'status': 'ok',
        'check': 'liveness',
        'message': 'Container is alive'
    }, status=200)


def health_ready(request):
    """
    Readiness probe - indicates if the container is ready to accept traffic
    
    Checks:
    - Database connectivity
    - Critical paths exist
    
    Returns 200 if ready, 503 if not ready.
    Kubernetes will remove pod from service endpoints if this fails.
    """
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
        logger.error(f"Health check - database error: {e}")
    
    # Check botssys directory exists
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
    
    # Check usersys directory exists
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
    
    # All checks must pass
    all_passed = all(checks.values())
    
    response_data = {
        'status': 'ready' if all_passed else 'not_ready',
        'check': 'readiness',
        'checks': checks,
    }
    
    if errors:
        response_data['errors'] = errors
    
    status_code = 200 if all_passed else 503
    
    if not all_passed:
        logger.warning(f"Health check failed: {response_data}")
    
    return JsonResponse(response_data, status=status_code)


def health_startup(request):
    """
    Startup probe - indicates if initial startup has completed
    
    Checks:
    - Database is accessible
    - Required tables exist
    - Bots directories are set up
    
    Returns 200 if startup complete, 503 if still starting.
    Kubernetes will wait for this before starting liveness/readiness probes.
    """
    checks = {
        'database': False,
        'tables': False,
        'botssys': False,
        'usersys': False,
        'config': False,
    }
    errors = []
    
    # Check database and required tables
    try:
        with connection.cursor() as cursor:
            # Check database connection
            cursor.execute("SELECT 1")
            checks['database'] = True
            
            # Check if critical tables exist
            table_names = connection.introspection.table_names(cursor)
            required_tables = ['channel', 'routes', 'ta', 'mutex']
            
            if all(table in table_names for table in required_tables):
                checks['tables'] = True
            else:
                missing = [t for t in required_tables if t not in table_names]
                errors.append(f"Missing tables: {', '.join(missing)}")
    except Exception as e:
        errors.append(f"Database check failed: {str(e)[:100]}")
        logger.error(f"Startup check - database error: {e}")
    
    # Check botssys exists and has required subdirectories
    try:
        if botsglobal.ini is None:
            raise RuntimeError("botsglobal.ini not initialized")
        
        botssys = botsglobal.ini.get('directories', 'botssys')
        if os.path.isdir(botssys):
            # Check for data directory
            data_dir = os.path.join(botssys, 'data')
            if os.path.isdir(data_dir) or os.path.isdir(botsglobal.ini.get('directories', 'data')):
                checks['botssys'] = True
            else:
                errors.append(f"botssys data directory not found")
        else:
            errors.append(f"botssys directory not found: {botssys}")
    except Exception as e:
        errors.append(f"botssys check failed: {str(e)[:100]}")
    
    # Check usersys exists
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
    
    # Check config is loaded
    try:
        # Check if ini is loaded and has at least some configuration
        if botsglobal.ini and botsglobal.ini.has_section('directories'):
            checks['config'] = True
        else:
            errors.append("Config not loaded or invalid")
    except Exception as e:
        errors.append(f"Config check failed: {str(e)[:100]}")
    
    # All checks must pass
    all_passed = all(checks.values())
    
    response_data = {
        'status': 'started' if all_passed else 'starting',
        'check': 'startup',
        'checks': checks,
    }
    
    if errors:
        response_data['errors'] = errors
    
    status_code = 200 if all_passed else 503
    
    if not all_passed:
        logger.warning(f"Startup check failed: {response_data}")
    
    return JsonResponse(response_data, status=status_code)


def health_ping(request):
    """
    Simple ping endpoint - minimal overhead
    Returns plain text "ok" with 200 status
    """
    return HttpResponse("ok", content_type="text/plain", status=200)
