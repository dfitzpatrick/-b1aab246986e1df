import discord
import os
from discord.ext import commands
import asyncio
import logging
import dotenv

dotenv.load_dotenv()
log = logging.getLogger(__name__)

extensions = (
    'bot.core',
    'bot.example',
)


class MissingConfigurationException(Exception):
    pass


def assert_envs_exist():
    envs = (
        ('TOKEN', 'The Bot Token', str),
    )
    for e in envs:
        ident = f"{e[0]}/{e[1]}"
        value = os.environ.get(e[0])
        if value is None:
            raise MissingConfigurationException(f"{ident} needs to be- defined")
        try:
            _ = e[2](value)
        except ValueError:
            raise MissingConfigurationException(f"{ident} is not the required type of {e[2]}")


async def run_bot():
    assert_envs_exist()
    token = os.environ['TOKEN']
    intents = discord.Intents.none()
    intents.messages = True
    intents.guilds = True
    bot = commands.Bot(
        intents=intents,
        command_prefix=commands.when_mentioned,
        slash_commands=True,
    )
    try:
        for ext in extensions:
            await bot.load_extension(ext)
            log.debug(f"Extension {ext} loaded")

        await bot.start(token)
    finally:
        await bot.close()

asyncio.run(run_bot())
