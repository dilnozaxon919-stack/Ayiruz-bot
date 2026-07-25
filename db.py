import asyncpg
from config import DATABASE_URL

pool: asyncpg.Pool | None = None


async def init_db():
    """Ulanish pool'ini ochadi va jadvallarni (agar yo'q bo'lsa) yaratadi."""
    global pool
    pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=5)

    async with pool.acquire() as conn:
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                username TEXT,
                full_name TEXT,
                balance NUMERIC(10, 2) NOT NULL DEFAULT 0,
                ref_id BIGINT,
                ref_count INTEGER NOT NULL DEFAULT 0,
                verified BOOLEAN NOT NULL DEFAULT FALSE,
                created_at TIMESTAMP NOT NULL DEFAULT NOW()
            );

            CREATE TABLE IF NOT EXISTS channels (
                id SERIAL PRIMARY KEY,
                chat_id TEXT NOT NULL UNIQUE,
                title TEXT
            );

            CREATE TABLE IF NOT EXISTS withdrawals (
                id SERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                amount NUMERIC(10, 2) NOT NULL,
                pubg_id TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TIMESTAMP NOT NULL DEFAULT NOW()
            );
            """
        )


# ---------- USERS ----------

async def get_user(user_id: int):
    async with pool.acquire() as conn:
        return await conn.fetchrow("SELECT * FROM users WHERE user_id = $1", user_id)


async def create_user_if_not_exists(user_id: int, username: str, full_name: str, ref_id: int | None):
    async with pool.acquire() as conn:
        existing = await conn.fetchrow("SELECT user_id FROM users WHERE user_id = $1", user_id)
        if existing:
            return False
        # o'zini-o'zi referal qilishning oldini olamiz
        if ref_id == user_id:
            ref_id = None
        await conn.execute(
            """
            INSERT INTO users (user_id, username, full_name, ref_id)
            VALUES ($1, $2, $3, $4)
            """,
            user_id, username, full_name, ref_id,
        )
        return True


async def mark_verified_and_reward(user_id: int, referral_bonus: float):
    """Foydalanuvchi majburiy obunadan birinchi marta o'tganda chaqiriladi:
    verified=True qilinadi va agar referal orqali kelgan bo'lsa, taklif qilgan odamga bonus beriladi."""
    async with pool.acquire() as conn:
        async with conn.transaction():
            user = await conn.fetchrow(
                "SELECT verified, ref_id FROM users WHERE user_id = $1", user_id
            )
            if not user or user["verified"]:
                return None  # allaqachon tasdiqlangan yoki topilmadi

            await conn.execute("UPDATE users SET verified = TRUE WHERE user_id = $1", user_id)

            ref_id = user["ref_id"]
            if ref_id:
                referrer = await conn.fetchrow("SELECT user_id FROM users WHERE user_id = $1", ref_id)
                if referrer:
                    await conn.execute(
                        """
                        UPDATE users
                        SET balance = balance + $1, ref_count = ref_count + 1
                        WHERE user_id = $2
                        """,
                        referral_bonus, ref_id,
                    )
                    return ref_id
    return None


async def get_balance(user_id: int) -> float:
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT balance FROM users WHERE user_id = $1", user_id)
        return float(row["balance"]) if row else 0.0


async def change_balance(user_id: int, delta: float):
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE users SET balance = balance + $1 WHERE user_id = $2", delta, user_id
        )


# ---------- CHANNELS (majburiy obuna) ----------

async def add_channel(chat_id: str, title: str):
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO channels (chat_id, title) VALUES ($1, $2) ON CONFLICT (chat_id) DO NOTHING",
            chat_id, title,
        )


async def remove_channel(channel_id: int):
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM channels WHERE id = $1", channel_id)


async def list_channels():
    async with pool.acquire() as conn:
        return await conn.fetch("SELECT * FROM channels ORDER BY id")


# ---------- WITHDRAWALS ----------

async def create_withdrawal(user_id: int, amount: float, pubg_id: str) -> int:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO withdrawals (user_id, amount, pubg_id)
            VALUES ($1, $2, $3)
            RETURNING id
            """,
            user_id, amount, pubg_id,
        )
        return row["id"]


async def get_withdrawal(withdrawal_id: int):
    async with pool.acquire() as conn:
        return await conn.fetchrow("SELECT * FROM withdrawals WHERE id = $1", withdrawal_id)


async def set_withdrawal_status(withdrawal_id: int, status: str):
    async with pool.acquire() as conn:
        await conn.execute("UPDATE withdrawals SET status = $1 WHERE id = $2", status, withdrawal_id)


# ---------- STATISTIKA ----------

async def get_stats():
    async with pool.acquire() as conn:
        total_users = await conn.fetchval("SELECT COUNT(*) FROM users")
        total_paid = await conn.fetchval(
            "SELECT COALESCE(SUM(amount), 0) FROM withdrawals WHERE status = 'approved'"
        )
        pending = await conn.fetchval(
            "SELECT COUNT(*) FROM withdrawals WHERE status = 'pending'"
        )
        return {
            "total_users": total_users or 0,
            "total_paid": float(total_paid or 0),
            "pending": pending or 0,
        }
