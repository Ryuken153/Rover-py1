import os
import motor.motor_asyncio
from dotenv import load_dotenv

load_dotenv()

client = motor.motor_async.io.AsyncIoMotorClient(os.getenv("MONGO_URI"))
db = client["Rover"]

guilds_col = db["guilds"]

async def get_guild(guild_id: int) -> dict:
  doc = await guilds_col.find_one({"guild_id": guild_id})
  if not doc:
    doc = {"guild_id":  guild_id, "prefixes": ["!"]}
    await guil_col.insert_one(doc)
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
