"""
Django management command to initialize Bots-EDI database

Usage:
    python manage.py initdb
    python manage.py initdb --verbose
"""

import os
import logging
from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.conf import settings


logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Initialize Bots-EDI database schema (managed and unmanaged tables)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Enable verbose output',
        )

    def handle(self, *args, **options):
        """Main command handler"""
        verbose = options.get('verbose', False)
        
        if verbose:
            logger.setLevel(logging.DEBUG)
        
        self.stdout.write(self.style.MIGRATE_HEADING('=' * 60))
        self.stdout.write(self.style.MIGRATE_HEADING('Bots-EDI Database Initialization'))
        self.stdout.write(self.style.MIGRATE_HEADING('=' * 60))
        
        try:
            # Get database type
            db_type = self.get_db_type()
            self.stdout.write(f"Database type: {db_type}")
            
            # Step 1: Run Django migrations
            self.stdout.write("")
            self.stdout.write(self.style.MIGRATE_HEADING('Step 1: Creating managed tables via Django migrations'))
            self.stdout.write('-' * 60)
            self.run_migrations()
            
            # Step 2: Create unmanaged tables
            self.stdout.write("")
            self.stdout.write(self.style.MIGRATE_HEADING('Step 2: Creating unmanaged tables via SQL files'))
            self.stdout.write('-' * 60)
            self.initialize_unmanaged_tables(db_type)
            
            # Step 3: Verify database
            self.stdout.write("")
            self.stdout.write(self.style.MIGRATE_HEADING('Step 3: Verifying database schema'))
            self.stdout.write('-' * 60)
            self.verify_database()
            
            self.stdout.write("")
            self.stdout.write(self.style.SUCCESS('=' * 60))
            self.stdout.write(self.style.SUCCESS('✓ Database initialization completed successfully!'))
            self.stdout.write(self.style.SUCCESS('=' * 60))
            
        except Exception as e:
            raise CommandError(f'Database initialization failed: {e}')

    def get_db_type(self):
        """Determine database type from Django settings"""
        engine = settings.DATABASES['default']['ENGINE']
        
        if 'sqlite' in engine:
            return 'sqlite'
        elif 'mysql' in engine:
            return 'mysql'
        elif 'postgresql' in engine:
            return 'postgresql'
        else:
            raise CommandError(f"Unsupported database engine: {engine}")

    def run_migrations(self):
        """Run Django migrations"""
        from django.core.management import call_command
        
        try:
            call_command('migrate', '--noinput', verbosity=1)
            self.stdout.write(self.style.SUCCESS('✓ Django migrations completed'))
        except Exception as e:
            raise CommandError(f'Django migrations failed: {e}')

    def table_exists(self, table_name):
        """Check if a table exists"""
        with connection.cursor() as cursor:
            table_names = connection.introspection.table_names(cursor)
            return table_name in table_names

    def execute_sql_file(self, sql_file_path):
        """Execute SQL statements from a file"""
        if not os.path.exists(sql_file_path):
            raise CommandError(f"SQL file not found: {sql_file_path}")
        
        self.stdout.write(f"Executing: {os.path.basename(sql_file_path)}")
        
        try:
            with open(sql_file_path, 'r', encoding='utf-8') as f:
                sql_content = f.read()
            
            # Split by semicolon and execute each statement
            statements = [stmt.strip() for stmt in sql_content.split(';') if stmt.strip()]
            
            with connection.cursor() as cursor:
                for statement in statements:
                    if statement:
                        try:
                            cursor.execute(statement)
                        except Exception as e:
                            # Log but continue - might be duplicate
                            self.stdout.write(
                                self.style.WARNING(f"  Warning: {str(e)[:80]}...")
                            )
            
            connection.commit()
            
        except Exception as e:
            connection.rollback()
            raise CommandError(f"Error executing SQL file: {e}")

    def initialize_unmanaged_tables(self, db_type):
        """Initialize unmanaged tables (ta, mutex, persist, uniek)"""
        # Get SQL directory
        from bots import botsglobal
        
        if botsglobal.ini is None:
            raise CommandError("botsglobal.ini not initialized - call django.setup() first")
        
        sql_dir = os.path.join(
            botsglobal.ini.get('directories', 'botspath'),
            'sql'
        )
        
        if not os.path.exists(sql_dir):
            raise CommandError(f"SQL directory not found: {sql_dir}")
        
        # Define unmanaged tables and their SQL files
        unmanaged_tables = {
            'ta': f'ta.{db_type}.sql',
            'mutex': f'mutex.{db_type}.sql',
            'persist': f'persist.{db_type}.sql',
            'uniek': 'uniek.sql',
        }
        
        for table_name, sql_file in unmanaged_tables.items():
            # Check if table already exists
            if self.table_exists(table_name):
                self.stdout.write(f"Table '{table_name}' already exists, skipping")
                continue
            
            # Execute SQL file
            sql_path = os.path.join(sql_dir, sql_file)
            self.execute_sql_file(sql_path)
            self.stdout.write(self.style.SUCCESS(f"✓ Created table '{table_name}'"))

    def verify_database(self):
        """Verify that all required tables exist"""
        # List of all required tables
        required_tables = [
            # Managed tables
            'channel', 'chanpar', 'partner', 'routes', 'translate',
            'confirmrule', 'ccode', 'ccodetrigger', 'filereport', 'report',
            # Unmanaged tables
            'ta', 'mutex', 'persist', 'uniek',
        ]
        
        missing_tables = []
        for table in required_tables:
            if not self.table_exists(table):
                missing_tables.append(table)
        
        if missing_tables:
            raise CommandError(f"Missing tables: {', '.join(missing_tables)}")
        
        self.stdout.write(
            self.style.SUCCESS(f"✓ All {len(required_tables)} required tables exist")
        )
