"""
Drop and recreate the edu_forms database (fresh start).
WARNING: Deletes all existing data in edu_forms.
"""
import os
import sys

from dotenv import load_dotenv

load_dotenv()

try:
    import psycopg2
    from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
except ImportError:
    print("Install psycopg2-binary: pip install psycopg2-binary")
    sys.exit(1)


def main():
    database_url = os.getenv("DATABASE_URL")
    if not database_url or not database_url.startswith("postgresql://"):
        print("DATABASE_URL must be a PostgreSQL URL")
        sys.exit(1)

    parts = database_url.replace("postgresql://", "").split("/")
    db_name = parts[-1]
    conn_part = parts[0]
    user_pass, host_port = conn_part.split("@")
    user, password = user_pass.split(":")
    host, port = host_port.split(":")

    conn = psycopg2.connect(
        dbname="postgres",
        user=user,
        password=password,
        host=host,
        port=port,
    )
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cur = conn.cursor()

    cur.execute(
        """
        SELECT pg_terminate_backend(pid)
        FROM pg_stat_activity
        WHERE datname = %s AND pid <> pg_backend_pid()
        """,
        (db_name,),
    )
    cur.execute(f'DROP DATABASE IF EXISTS "{db_name}"')
    print(f"Dropped database '{db_name}'.")
    cur.execute(f'CREATE DATABASE "{db_name}"')
    print(f"Created database '{db_name}'.")
    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
