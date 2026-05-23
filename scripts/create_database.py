"""
Create PostgreSQL database 'edu_forms' if it does not exist.
Run: python scripts/create_database.py
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
    database_url = os.getenv(
        "DATABASE_URL",
        "postgresql://postgres:postgres@localhost:5432/edu_forms",
    )
    # postgresql://user:pass@host:port/dbname
    if not database_url.startswith("postgresql://"):
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
    cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (db_name,))
    if cur.fetchone():
        print(f"Database '{db_name}' already exists.")
    else:
        cur.execute(f'CREATE DATABASE "{db_name}"')
        print(f"Database '{db_name}' created.")
    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
