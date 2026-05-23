import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()
engine = create_engine(os.getenv("DATABASE_URL"))
with engine.connect() as conn:
    try:
        r = conn.execute(text("SELECT version_num FROM alembic_version"))
        print("alembic_version:", r.fetchall())
    except Exception as e:
        print("alembic_version:", e)
    r = conn.execute(
        text(
            "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename"
        )
    )
    print("tables:", [x[0] for x in r.fetchall()])
