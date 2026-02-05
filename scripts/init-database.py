#!/usr/bin/env python
"""
Database initialization script for Bots-EDI

This script initializes the database schema including:
- Django managed tables (via migrations)
- Unmanaged tables (ta, mutex, persist, uniek) via SQL files

Can be run multiple times safely (idempotent).

Usage:
    python scripts/init-database.py [--config-dir=/path/to/config]
"""

import os
import sys
import argparse
import logging

# Add bots to Python path
bots_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(bots_root, 'bots'))

# Import after path setup
import django
from django.conf import settings as django_settings
from django.core.management import call_command
from django.db import connection, connections

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description='Initialize Bots-EDI database schema'
    )
    parser.add_argument(
        '--config-dir',
        '-c',
        default=None,
        help='Path to configuration directory (absolute or relative to project root)'
    )
    parser.add_argument(
        '--verbose',
        '-v',
        action='store_true',
        help='Enable verbose output'
    )
    return parser.parse_args()


def setup_django(configdir=None):
    """Initialize Django settings"""
    from bots import botsinit
    
    logger.info("Initializing Bots environment...")
    botsinit.generalinit(configdir)
    
    if not django_settings.configured:
        django.setup()
    
    logger.info(f"Using database: {django_settings.DATABASES['default']['ENGINE']}")
    return django_settings.DATABASES['default']


def get_db_type(db_config):
    """Determine database type from Django config"""
    engine = db_config['ENGINE']
    
    if 'sqlite' in engine:
        return 'sqlite'
    elif 'mysql' in engine:
        return 'mysql'
    elif 'postgresql' in engine:
        return 'postgresql'
    else:
        raise ValueError(f"Unsupported database engine: {engine}")


def table_exists(table_name, db_connection=None):
    """Check if a table exists in the database"""
    if db_connection is None:
        db_connection = connection
    
    with db_connection.cursor() as cursor:
        # Get list of tables
        table_names = db_connection.introspection.table_names(cursor)
        return table_name in table_names


def execute_sql_file(sql_file_path, db_connection=None):
    """Execute SQL statements from a file"""
    if db_connection is None:
        db_connection = connection
    
    if not os.path.exists(sql_file_path):
        logger.error(f"SQL file not found: {sql_file_path}")
        return False
    
    logger.info(f"Executing SQL file: {os.path.basename(sql_file_path)}")
    
    try:
        with open(sql_file_path, 'r', encoding='utf-8') as f:
            sql_content = f.read()
        
        # Split by semicolon and execute each statement
        statements = [stmt.strip() for stmt in sql_content.split(';') if stmt.strip()]
        
        with db_connection.cursor() as cursor:
            for statement in statements:
                if statement:
                    try:
                        cursor.execute(statement)
                        logger.debug(f"Executed: {statement[:50]}...")
                    except Exception as e:
                        # Log but continue - might be duplicate index/table
                        logger.warning(f"SQL statement failed (may already exist): {str(e)[:100]}")
        
        db_connection.commit()
        return True
        
    except Exception as e:
        logger.error(f"Error executing SQL file {sql_file_path}: {e}")
        db_connection.rollback()
        return False


def initialize_unmanaged_tables(db_type):
    """Initialize unmanaged tables (ta, mutex, persist, uniek)"""
    logger.info("Initializing unmanaged tables...")
    
    # Get SQL directory from installed bots package
    try:
        import bots
        bots_path = bots.__path__[0]
        sql_dir = os.path.join(bots_path, 'sql')
    except (ImportError, AttributeError):
        # Fallback to relative path (for development)
        bots_path = os.path.join(os.path.dirname(__file__), '..', 'bots', 'bots')
        sql_dir = os.path.join(bots_path, 'sql')
    
    if not os.path.exists(sql_dir):
        logger.error(f"SQL directory not found: {sql_dir}")
        return False
    
    # Define unmanaged tables and their SQL files
    unmanaged_tables = {
        'ta': f'ta.{db_type}.sql',
        'mutex': f'mutex.{db_type}.sql',
        'persist': f'persist.{db_type}.sql',
        'uniek': 'uniek.sql',  # Shared across all DB types
    }
    
    success = True
    for table_name, sql_file in unmanaged_tables.items():
        # Check if table already exists
        if table_exists(table_name):
            logger.info(f"Table '{table_name}' already exists, skipping creation")
            continue
        
        # Execute SQL file
        sql_path = os.path.join(sql_dir, sql_file)
        if not execute_sql_file(sql_path):
            logger.error(f"Failed to create table '{table_name}'")
            success = False
        else:
            logger.info(f"✓ Created table '{table_name}'")
    
    return success


def run_django_migrations():
    """Run Django migrations to create managed tables"""
    logger.info("Running Django migrations...")
    
    try:
        # Show migrations
        call_command('showmigrations', '--list', verbosity=1)
        
        # Run migrations
        call_command('migrate', '--noinput', verbosity=1)
        
        logger.info("✓ Django migrations completed")
        return True
        
    except Exception as e:
        logger.error(f"Django migrations failed: {e}")
        return False


def verify_database():
    """Verify that all required tables exist"""
    logger.info("Verifying database schema...")
    
    # List of all tables that should exist
    required_tables = [
        # Managed tables (from Django models)
        'channel', 'chanpar', 'partner', 'routes', 'translate',
        'confirmrule', 'ccode', 'ccodetrigger', 'filereport', 'report',
        # Unmanaged tables
        'ta', 'mutex', 'persist', 'uniek',
    ]
    
    missing_tables = []
    for table in required_tables:
        if not table_exists(table):
            missing_tables.append(table)
    
    if missing_tables:
        logger.error(f"Missing tables: {', '.join(missing_tables)}")
        return False
    
    logger.info(f"✓ All {len(required_tables)} required tables exist")
    return True


def main():
    """Main execution function"""
    args = parse_args()
    
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    
    logger.info("=" * 60)
    logger.info("Bots-EDI Database Initialization")
    logger.info("=" * 60)
    
    try:
        # Convert relative config path to absolute if needed
        config_dir = args.config_dir
        if config_dir and not os.path.isabs(config_dir):
            # Make relative to project root (parent of scripts dir)
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            config_dir = os.path.abspath(os.path.join(project_root, config_dir))
            logger.debug(f"Resolved config_dir to: {config_dir}")
        
        # Setup Django and get database config
        db_config = setup_django(config_dir)
        db_type = get_db_type(db_config)
        logger.info(f"Database type: {db_type}")
        
        # Step 1: Run Django migrations (managed tables)
        logger.info("")
        logger.info("Step 1: Creating managed tables via Django migrations")
        logger.info("-" * 60)
        if not run_django_migrations():
            logger.error("Failed to run Django migrations")
            return 1
        
        # Step 2: Create unmanaged tables via SQL files
        logger.info("")
        logger.info("Step 2: Creating unmanaged tables via SQL files")
        logger.info("-" * 60)
        if not initialize_unmanaged_tables(db_type):
            logger.error("Failed to initialize unmanaged tables")
            return 1
        
        # Step 3: Verify all tables exist
        logger.info("")
        logger.info("Step 3: Verifying database schema")
        logger.info("-" * 60)
        if not verify_database():
            logger.error("Database verification failed")
            return 1
        
        logger.info("")
        logger.info("=" * 60)
        logger.info("✓ Database initialization completed successfully!")
        logger.info("=" * 60)
        return 0
        
    except Exception as e:
        logger.error(f"Fatal error during database initialization: {e}", exc_info=True)
        return 1


if __name__ == '__main__':
    sys.exit(main())
