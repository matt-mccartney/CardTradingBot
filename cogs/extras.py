from datetime import date, datetime
import discord
from discord.ext import commands
from discord import app_commands


start_time = datetime.now().replace(microsecond=0)

class Extras(commands.Cog):

    def __init__(self, bot:commands.Bot) -> None:
        self.bot = bot
        super().__init__() #Initialize inherited Cog class

    #Command with creator contact info and bot statistics
    @app_commands.guild_only()
    @app_commands.command()
    async def about(self, interaction:discord.Interaction):
        """About the bot"""

        creator = await self.bot.fetch_user(367456841241722890)

        embed = discord.Embed(
            title=f"About {self.bot.user.name}",
            description="Learn more about me.",
            color=0x4b96ea
        )

        uptime = datetime.now().replace(microsecond=0) - start_time

        embed.add_field(name="Creator", value=f"{creator}", inline=False)
        embed.add_field(name="Uptime", value=f"{uptime}")
        embed.add_field(name="Timezone", value=f"{self.bot.timezone.tzinfo}")
        embed.add_field(name="Channels", value=f"{len(list(self.bot.get_all_channels()))} total channels", inline=False)
        embed.add_field(name="Servers", value=f"{len(self.bot.guilds)}")
        embed.add_field(name="Users", value=f"{len(list(self.bot.get_all_members()))}")
        embed.set_footer(text=f"Made with ❤️ by {creator}", icon_url=self.bot.user.display_avatar.url)

        await interaction.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(Extras(bot))


async def teardown(bot):
    return
