#!/bin/bash
set -e

echo "Waiting for PostgreSQL to accept connections..."
python - << 'EOF'
import sys
import time
import os
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

db_url = os.getenv("DATABASE_URL", "postgresql+asyncpg://jobagent:password@postgres:5432/jobagent")

async def wait_db():
    start = time.time()
    while time.time() - start < 30:
        try:
            engine = create_async_engine(db_url, pool_pre_ping=True)
            async with engine.begin() as conn:
                await conn.execute(text("SELECT 1;"))
            await engine.dispose()
            print("PostgreSQL is available.")
            return True
        except Exception as e:
            time.sleep(1)
    print("PostgreSQL connection timed out.")
    return False

if not asyncio.run(wait_db()):
    sys.exit(1)
EOF

# If running as the web backend, apply migrations
if [ "$1" = "uvicorn" ] || [ "$2" = "app.main:app" ]; then
    echo "Running database migrations..."
    alembic upgrade head
fi

exec "$@"
