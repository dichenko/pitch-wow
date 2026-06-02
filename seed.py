import asyncio
import sys

sys.path.insert(0, ".")

from app.db.init_db import init_db

asyncio.run(init_db())
