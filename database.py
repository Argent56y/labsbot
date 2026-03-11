import aiosqlite

DB_NAME = "bot.db"

async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                is_admin BOOLEAN DEFAULT 0,
                has_accepted_agreement BOOLEAN DEFAULT 0
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS labs (
                user_id INTEGER PRIMARY KEY,
                oaip INTEGER DEFAULT 0,
                siap INTEGER DEFAULT 0,
                structures INTEGER DEFAULT 0,
                FOREIGN KEY(user_id) REFERENCES users(user_id)
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS pending_confirmations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                subject TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_resolved BOOLEAN DEFAULT 0
            )
        ''')
        # Insert admin if needed (optional)
        await db.commit()

async def add_user(user_id: int, username: str, first_name: str, last_name: str):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute('''
            INSERT OR IGNORE INTO users (user_id, username, first_name, last_name, has_accepted_agreement)
            VALUES (?, ?, ?, ?, 0)
        ''', (user_id, username, first_name, last_name))
        await db.execute('''
            INSERT OR IGNORE INTO labs (user_id) VALUES (?)
        ''', (user_id,))
        await db.commit()

async def get_user(user_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute('SELECT * FROM users WHERE user_id = ?', (user_id,)) as cursor:
            return await cursor.fetchone()

async def update_labs(user_id: int, subject: str, count: int):
    # subject must be one of 'oaip', 'siap', 'structures'
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(f'''
            UPDATE labs SET {subject} = ? WHERE user_id = ?
        ''', (count, user_id))
        await db.commit()

async def get_user_labs(user_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute('SELECT * FROM labs WHERE user_id = ?', (user_id,)) as cursor:
            return await cursor.fetchone()
            
async def get_queue(subject: str):
    # Returns a list of users ordered by the number of passed labs + any positional modifiers (ascending)
    # The actual score logic: Priority = l.{subject} + l.{subject}_modifier.
    # We negate the modifier because a "queue buyout" means we want to act like we have FEWER labs.
    # Note: to shift right by 1 pos, we subtract 0.1 from the score, so the person appears 'better'. Let's just adjust the sort order directly.
    
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(f'''
            SELECT u.user_id, u.first_name, u.last_name, u.username, l.{subject}, l.{subject}_modifier
            FROM users u
            JOIN labs l ON u.user_id = l.user_id
            ORDER BY (l.{subject} + l.{subject}_modifier) ASC, u.last_name ASC
        ''') as cursor:
            return await cursor.fetchall()
            
async def get_all_users_labs():
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute('''
            SELECT u.user_id, u.first_name, u.last_name, u.username, l.oaip, l.siap, l.structures
            FROM users u
            JOIN labs l ON u.user_id = l.user_id
            ORDER BY u.last_name ASC
        ''') as cursor:
            return await cursor.fetchall()

async def is_admin(user_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute('SELECT is_admin FROM users WHERE user_id = ?', (user_id,)) as cursor:
            row = await cursor.fetchone()
            return row and row[0]

async def add_pending_confirmation(user_id: int, subject: str):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute('''
            INSERT INTO pending_confirmations (user_id, subject) VALUES (?, ?)
        ''', (user_id, subject))
        await db.commit()

async def resolve_pending_confirmation(user_id: int, subject: str):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute('''
            UPDATE pending_confirmations SET is_resolved = 1 
            WHERE user_id = ? AND subject = ? AND is_resolved = 0
        ''', (user_id, subject))
        await db.commit()

async def accept_user_agreement(user_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute('UPDATE users SET has_accepted_agreement = 1 WHERE user_id = ?', (user_id,))
        await db.commit()

async def delete_user(user_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute('DELETE FROM labs WHERE user_id = ?', (user_id,))
        await db.execute('DELETE FROM pending_confirmations WHERE user_id = ?', (user_id,))
        await db.execute('DELETE FROM users WHERE user_id = ?', (user_id,))
        await db.commit()

async def buyout_queue(user_id: int, subject: str):
    # Buys out the queue by subtracting 0.1 from the score, artificially making them 
    # 'have fewer labs' so they go higher in the sort order. 
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(f'''
            UPDATE labs SET {subject}_modifier = {subject}_modifier - 0.1
            WHERE user_id = ?
        ''', (user_id,))
        await db.commit()

async def reset_modifiers(subject: str):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(f'UPDATE labs SET {subject}_modifier = 0')
        await db.commit()

async def get_unresolved_confirmations_older_than(hours: int = 24):
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(f'''
            SELECT * FROM pending_confirmations
            WHERE is_resolved = 0 AND datetime(created_at, '+{hours} hours') <= CURRENT_TIMESTAMP
        ''') as cursor:
            return await cursor.fetchall()
