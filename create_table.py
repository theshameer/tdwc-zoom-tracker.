import asyncio
import asyncpg

# This is your secret address from Railway
DATABASE_URL = "postgresql://postgres:PUDXuchiJOdhvQDRTqTpcFPQTUavSdIU@shortline.proxy.rlwy.net:17621/railway"

async def run():
    try:
        conn = await asyncpg.connect(DATABASE_URL)
        print("Connected to Railway!")
        
        # This creates your attendance notebook
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS attendance (
                id SERIAL PRIMARY KEY,
                email TEXT,
                user_name TEXT,
                session_id TEXT,
                join_time TIMESTAMPTZ,
                leave_time TIMESTAMPTZ,
                duration_minutes FLOAT DEFAULT 0
            );
        ''')
        print("Table 'attendance' created successfully!")
        await conn.close()
    except Exception as e:
        print(f"Oops, something went wrong: {e}")

asyncio.run(run())