import datetime
import os
import aiosqlite

import discord
from discord import app_commands
from discord.ext import commands, tasks
from discord.ext.commands.errors import ArgumentParsingError, BadArgument, DisabledCommand, MissingPermissions
from cogs.extras import Extras


class SlashCommandBot(commands.Bot):

    def __init__(self, prefix = "!", intents = discord.Intents.default()):
        # Load intents needed.
        intents = discord.Intents.default()
        intents.members = True

        # Instanciate inherited commands.Bot object
        super().__init__(command_prefix=commands.when_mentioned_or(
            prefix), intents=intents, use_application_commands=True)

    async def setup_hook(self):
        self.timezone = datetime.datetime.now().astimezone()

        async with aiosqlite.connect("main.db") as db:
            await db.execute("CREATE TABLE IF NOT EXISTS cards (id, title, pack, img, rarity, inCirculation)")
            await db.execute("CREATE TABLE IF NOT EXISTS rolls (user, lastroll)")
            await db.execute("CREATE TABLE IF NOT EXISTS inventory (user, card, count)")
            await db.commit()

        for filename in os.listdir('./cogs'):
            if filename.endswith('.py'):
                await bot.load_extension(f'cogs.{filename[:-3]}')

    async def on_ready(self):
        await self.tree.sync()
        await self.change_presence(activity=discord.Game(name="with cards"))

    async def on_command_error(self, context: commands.Context, exception: commands.errors.CommandError) -> None:
        msg = ""

        # Identify error and form an error message
        if type(exception) == BadArgument:
            msg = "The information entered caused an error!"
        elif type(exception) == DisabledCommand:
            msg = "This command can only be used with Slash Commands!"
        elif type(exception) in [commands.errors.TooManyArguments, ArgumentParsingError]:
            msg = "Arguments couldn't be interpreted!"
        elif type(exception) == MissingPermissions or type(exception) == app_commands.errors.MissingPermissions:
            msg = "You aren't permitted to use this command!"
        elif type(exception) == app_commands.errors.CommandNotFound:
            return
        else:
            return
        await context.send(embed=discord.Embed(title="An Error Occured", description=msg, color=discord.Color.red()))

    @tasks.loop(seconds=5)
    async def commit_db(self):
        print("Saving database.")
        await self.db.commit()



intents = discord.Intents.default()
intents.members = True
bot = SlashCommandBot()


if __name__ == "__main__":
    bot.run('NTgxOTgyOTczODcyNTcwMzc5.G1DHhC.LALZMicebLQUGR0-4d48s-eAO7yQS3dp9EfJJ8')
