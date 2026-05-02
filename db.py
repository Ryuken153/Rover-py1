import os
import time
import motor.motor_asyncio
from dotenv import load_dotenv

load_dotenv()

client = motor.motor_asyncio.AsyncIOMotorClient(os.getenv("MONGO_URI"))
db = client["Rover"]

guilds_col = db["guilds"]

async def get_guild(guild_id: int) -> dict:
    doc = await guilds_col.find_one({"guild_id": guild_id})
    if not doc:
        doc = {"guild_id": guild_id, "prefixes": ["!"]}
        await guilds_col.insert_one(doc)
    return doc

async def update_guild(guild_id: int, data: dict) -> None:
    await guilds_col.update_one(
        {"guild_id": guild_id},
        {"$set": data},
        upsert=True
    )

async def get_prefixes(guild_id: int) -> list:
    doc = await get_guild(guild_id)
    return doc.get("prefixes", ["!"])

async def set_prefix(guild_id: int, prefix: str) -> None:
    await update_guild(guild_id, {"prefixes": [prefix]})

async def add_prefix(guild_id: int, prefix: str) -> list:
    prefixes = await get_prefixes(guild_id)
    if prefix not in prefixes:
        prefixes.append(prefix)
        await update_guild(guild_id, {"prefixes": prefixes})
    return prefixes

async def remove_prefix(guild_id: int, prefix: str) -> list:
    prefixes = await get_prefixes(guild_id)
    if prefix in prefixes:
        prefixes.remove(prefix)
        await update_guild(guild_id, {"prefixes": prefixes if prefixes else ["!"]})
    return prefixes
    
# Reminders----------------------------------------------------------------------------------------------------------
reminders_col= db["reminders"]

async def add_reminder(user_id: int, channel_id: int, reminder: str, remind_at: float):
    result = await reminders_col.insert_one({
        "user_id": user_id,
        "channel_id": channel_id,
        "reminder": reminder,
        "remind_at": remind_at
    })
    return result.inserted_id

async def get_user_reminders(user_id: int):
    return await reminders_col.find({"user_id": user_id}).to_list(None)

async def get_all_reminders():
    return await reminders_col.find().to_list(None)

async def delete_reminder(reminder_id):
    await reminders_col.delete_one({"_id": reminder_id})

