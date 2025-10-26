# import asyncpg
# import config

# async def create_pool():
#     return await asyncpg.create_pool(
#         user=config.DB_USER,
#         password=config.DB_PASS,
#         database=config.DB_NAME,
#         host=config.DB_HOST,
#         port=config.DB_PORT
#     )

# async def init_db(pool):
#     async with pool.acquire() as conn:
#         await conn.execute("""
#         CREATE TABLE IF NOT EXISTS users (
#             user_id BIGINT PRIMARY KEY,
#             username TEXT,
#             subscription BOOLEAN DEFAULT FALSE
#         )
#         """)
#         await conn.execute("""
#         CREATE TABLE IF NOT EXISTS photos (
#             id SERIAL PRIMARY KEY,
#             user_id BIGINT REFERENCES users(user_id),
#             file_id TEXT,
#             created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
#         )
#         """)

# async def add_user(pool, user_id, username):
#     async with pool.acquire() as conn:
#         await conn.execute(
#             "INSERT INTO users(user_id, username) VALUES($1, $2) ON CONFLICT DO NOTHING",
#             user_id, username
#         )

# async def add_photo(pool, user_id, file_id):
#     async with pool.acquire() as conn:
#         await conn.execute(
#             "INSERT INTO photos(user_id, file_id) VALUES($1, $2)",
#             user_id, file_id
#         )

# async def set_subscription(pool, user_id, value: bool):
#     async with pool.acquire() as conn:
#         await conn.execute(
#             "UPDATE users SET subscription=$1 WHERE user_id=$2",
#             value, user_id
#         )
import asyncpg
import config
import json

async def create_pool():
    return await asyncpg.create_pool(
        user=config.DB_USER,
        password=config.DB_PASS,
        database=config.DB_NAME,
        host=config.DB_HOST,
        port=config.DB_PORT
    )

async def init_db(pool):
    async with pool.acquire() as conn:
        # Таблица пользователей
        await conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id BIGINT PRIMARY KEY,
            username TEXT,
            full_name TEXT DEFAULT '',
            subscription BOOLEAN DEFAULT FALSE,
            subscription_start TIMESTAMP,
            subscription_end TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        
        # Таблица фотографий
        await conn.execute("""
        CREATE TABLE IF NOT EXISTS photos (
            id SERIAL PRIMARY KEY,
            user_id BIGINT REFERENCES users(user_id),
            file_id TEXT NOT NULL,
            file_path TEXT,
            original_filename TEXT,
            status TEXT DEFAULT 'pending',
            result_text TEXT,
            processing_time INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP
        )
        """)
        
        # Таблица для аналитики
        await conn.execute("""
        CREATE TABLE IF NOT EXISTS user_actions (
            id SERIAL PRIMARY KEY,
            user_id BIGINT REFERENCES users(user_id),
            action_type TEXT NOT NULL,
            details TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

async def add_user(pool, user_id, username, full_name=""):
    """Добавление/обновление пользователя"""
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO users(user_id, username, full_name) 
            VALUES($1, $2, $3) 
            ON CONFLICT (user_id) 
            DO UPDATE SET 
                username = EXCLUDED.username,
                full_name = EXCLUDED.full_name,
                last_active = CURRENT_TIMESTAMP
            """,
            user_id, username, full_name
        )

async def add_photo(pool, user_id, file_id, original_filename=None):
    """Добавление информации о фото"""
    async with pool.acquire() as conn:
        photo_id = await conn.fetchval(
            """
            INSERT INTO photos(user_id, file_id, original_filename) 
            VALUES($1, $2, $3) 
            RETURNING id
            """,
            user_id, file_id, original_filename
        )
        
        # Записываем действие
        details_str = json.dumps({"file_id": file_id, "photo_id": photo_id})
        await conn.execute(
            "INSERT INTO user_actions(user_id, action_type, details) VALUES($1, $2, $3)",
            user_id, "photo_uploaded", details_str
        )
        
        return photo_id

async def set_subscription(pool, user_id, value: bool, duration_days=30):
    """Установка подписки"""
    async with pool.acquire() as conn:
        if value:
            # Активируем подписку
            await conn.execute(
                """
                UPDATE users 
                SET subscription = true, 
                    subscription_start = CURRENT_TIMESTAMP,
                    subscription_end = CURRENT_TIMESTAMP + INTERVAL '1 day' * $1
                WHERE user_id = $2
                """,
                duration_days, user_id
            )
        else:
            # Отключаем подписку
            await conn.execute(
                "UPDATE users SET subscription = false, subscription_end = NULL WHERE user_id = $1",
                user_id
            )
        
        # Записываем действие
        details_str = json.dumps({"new_status": value, "duration_days": duration_days})
        await conn.execute(
            "INSERT INTO user_actions(user_id, action_type, details) VALUES($1, $2, $3)",
            user_id, "subscription_changed", details_str
        )

async def get_user_info(pool, user_id):
    """Получение информации о пользователе"""
    async with pool.acquire() as conn:
        user = await conn.fetchrow(
            "SELECT * FROM users WHERE user_id = $1", user_id
        )
        return dict(user) if user else None

async def get_user_photos_count(pool, user_id):
    """Количество фото пользователя"""
    async with pool.acquire() as conn:
        count = await conn.fetchval(
            "SELECT COUNT(*) FROM photos WHERE user_id = $1", user_id
        )
        return count

async def get_user_stats(pool, user_id):
    """Полная статистика пользователя"""
    async with pool.acquire() as conn:
        user = await get_user_info(pool, user_id)
        photos_count = await get_user_photos_count(pool, user_id)
        return user, photos_count

async def check_subscription(pool, user_id):
    """Проверка активной подписки"""
    async with pool.acquire() as conn:
        user = await get_user_info(pool, user_id)
        if user and user['subscription']:
            # Проверяем не истекла ли подписка
            if user['subscription_end']:
                # Получаем текущее время из БД и приводим к тому же типу
                current_time = await conn.fetchval("SELECT CURRENT_TIMESTAMP")
                
                # Приводим оба времени к offset-naive для сравнения
                subscription_end = user['subscription_end'].replace(tzinfo=None) if user['subscription_end'].tzinfo else user['subscription_end']
                current_time_naive = current_time.replace(tzinfo=None) if current_time.tzinfo else current_time
                
                if subscription_end < current_time_naive:
                    await set_subscription(pool, user_id, False)
                    return False
            return True
        return False

# Функция для отладки - просмотр таблиц
async def show_tables(pool):
    """Просмотр содержимого таблиц (для отладки)"""
    async with pool.acquire() as conn:
        print("=== USERS ===")
        users = await conn.fetch("SELECT * FROM users")
        for user in users:
            print(dict(user))
        
        print("\n=== PHOTOS ===")
        photos = await conn.fetch("SELECT * FROM photos")
        for photo in photos:
            print(dict(photo))
        
        print("\n=== USER_ACTIONS ===")
        actions = await conn.fetch("SELECT * FROM user_actions")
        for action in actions:
            print(dict(action))