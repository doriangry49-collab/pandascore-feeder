import os
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

def run_migrations():
    # Get database URL from environment
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        raise ValueError("DATABASE_URL environment variable is required")

    # Connect to database
    conn = psycopg2.connect(database_url)
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cur = conn.cursor()

    try:
        # Read and execute migration file
        with open('migrations/001_create_analysis_tables.sql', 'r') as f:
            migration_sql = f.read()
            # Split and execute statements individually
            statements = migration_sql.split(';')
            for statement in statements:
                if statement.strip():
                    cur.execute(statement)
        print("Migration completed successfully")
    
    except Exception as e:
        print(f"Error running migration: {str(e)}")
        raise
    
    finally:
        cur.close()
        conn.close()

if __name__ == '__main__':
    run_migrations()