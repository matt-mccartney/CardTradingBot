import discord
from discord.ext import commands
from discord import app_commands
from discord.app_commands import Choice
from typing import Literal
from hashlib import sha256
import time
import aiosqlite
import os
import random




class Trading(commands.Cog):


    def __init__(self, bot:commands.Bot) -> None:
        self.bot = bot
        self.rarity_percents = {
            "Exotic": 2,
            "Ultra Rare": 8,
            "Rare": 15,
            "Uncommon": 25,
            "Common": 50,
        }
        super().__init__() #Initialize inherited Cog class


    async def get_cards(self, key: Literal["name", "id"] = "id"):
        async with aiosqlite.connect("main.db") as db:
            query = await db.execute("SELECT * FROM cards")
            cards = await query.fetchall()

        if key == "id":
            k = 0
        elif key == "name":
            k = 1

        card_dict = {}
        for card in cards:
            card_dict[card[k]] = {
                "id": card[0],
                "name": card[1],
                "pack": card[2],
                "image_url": card[3],
                "rarity": card[4],
            }

        return card_dict


    @app_commands.command()
    @app_commands.guild_only()
    ## @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(
        title='The name of the card',
        image='image of the card to be displayed',
        pack='Select an existing pack or create a new one.',
        rarity='Rarity for the card. Affects rolling. Pack-specific.'
    )
    async def upload(self, interaction: discord.Interaction, title: str, pack: str, image: discord.Attachment, rarity: Literal["Common", "Uncommon", "Rare", "Ultra Rare", "Exotic"]):
        """Upload a new card for users to use."""
        card_id = "c" + sha256((title + pack + rarity + str(time.time())).encode("utf-8")).hexdigest()[:25]
        img_hash = sha256((image.filename + str(int(time.time())) + str(interaction.user.id)).encode("utf-8")).hexdigest()
        if not image.content_type.startswith("image/"):
            return await interaction.response.send_message(
                embed=discord.Embed(
                    description='Command failed! Parameter `image` must be an image.',
                    color=discord.Color.red()
                ),
                ephemeral=True
            )
        async with aiosqlite.connect("main.db") as db:
            await db.execute("INSERT INTO cards VALUES(?, ?, ?, ?, ?, 1)", (card_id, title, pack, f"{img_hash}.{image.content_type.split('/')[1]}", rarity))
            await db.commit()
        if not pack in os.listdir("./assets/card_packs"):
            os.makedirs(f"./assets/card_packs/{pack}")
        await image.save(f"./assets/card_packs/{pack}/{img_hash}.{image.content_type.split('/')[1]}")
        await interaction.response.send_message(embed=discord.Embed(description="Card Uploaded!", color=discord.Color.green()), ephemeral=True)


    @app_commands.command()
    @app_commands.guild_only()
    async def open(self, interaction: discord.Interaction, pack:str):
        """Reveal a card from one of the available packs."""
        async with aiosqlite.connect("main.db") as db:
            query = await db.execute("SELECT DISTINCT pack FROM cards WHERE inCirculation = 1")
            active_packs = [pack[0] for pack in await query.fetchall()]
        if pack not in active_packs:
            return await interaction.response.send_message("Pack not found!", ephemeral=True)
        async with aiosqlite.connect("main.db") as db:
            last_roll = (await (await db.execute('SELECT lastroll FROM rolls WHERE user = ?', (interaction.user.id,))).fetchone())
            if last_roll != None:
                last_roll = last_roll[0]
            else:
                last_roll = -1
            cooldown = time.time() - last_roll
            ## if not cooldown >= 300:
            ##     return await interaction.response.send_message(embed=discord.Embed(description=f'You\'re on cooldown! Come back in **{round(((300 + last_roll) - time.time()) / 60, 1)}** minutes.', color=discord.Color.yellow()), ephemeral=True)

            await db.execute('DELETE FROM rolls WHERE user = ?', (interaction.user.id,))
            await db.execute('INSERT INTO rolls VALUES(?, ?)', (interaction.user.id, time.time()))
            sorted_cards = [
                await (await db.execute('SELECT * FROM cards WHERE pack = ? AND rarity = ?', (pack, rarity))).fetchall()
                for rarity
                in ["Common", "Uncommon", "Rare", "Ultra Rare", "Exotic"]
            ]

            await db.commit()

        while True:
            roll = random.randint(1, 100)
            rarity_index = -1
            if 0 <= roll <= 50:
                rarity_index = 0
            if 51 <= roll <= 75:
                rarity_index = 1
            elif 76 <= roll <= 90:
                rarity_index = 2
            elif 91 <= roll <= 98:
                rarity_index = 3
            elif 99 <= roll <= 100:
                rarity_index = 4

            if bool(sorted_cards[rarity_index]):
                break

        card = random.choice(sorted_cards[rarity_index])

        async with aiosqlite.connect("main.db") as db:
            query = await db.execute("SELECT * FROM inventory WHERE user = ? AND card = ?", (interaction.user.id, card[0]))
            if await query.fetchone() != None:
                old = await db.execute(f"SELECT count FROM inventory WHERE user = ? AND card = ?", (interaction.user.id, card[0]))
                await db.execute(f"UPDATE inventory SET count = ? WHERE user = ? AND card = ?", ((await old.fetchone())[0] + 1, interaction.user.id, card[0]))
            else:
                await db.execute(f"INSERT INTO inventory VALUES(?, ?, 1)", (interaction.user.id, card[0]))
            await db.commit()

        e = discord.Embed(
            title = card[1],
            color=discord.Color.blurple()
        )
        e.set_footer(text=f'Serial: {card[0]} | Rarity: {card[4]}')
        img = discord.File(f"./assets/card_packs/{card[2]}/{card[3]}", filename="card.png")
        e.set_image(url="attachment://card.png")

        await interaction.response.send_message(embed=e, file=img)


    @app_commands.command()
    async def inventory(self, interaction: discord.Interaction, user: discord.User = None, pack: str = None):
        """View a user's available cards."""
        if user == None:
            user = interaction.user

        async with aiosqlite.connect("main.db") as db:
            query = await db.execute("SELECT DISTINCT pack FROM cards")
            packs = [pack[0] for pack in await query.fetchall()]

            query = await db.execute("SELECT * FROM inventory WHERE user = ?", (user.id,))
            rows = await query.fetchall()
            if rows == []:
                return await interaction.response.send_message("No items.")

        cards = await self.get_cards()
        sorted_inv = {}
        for count, row in enumerate(rows, start=0):
            user_id, card_id, amount = row
            card_pack = cards[card_id]["pack"]
            if card_pack in sorted_inv:
                if amount > 0:
                    sorted_inv[card_pack].append((cards[card_id]["name"], amount, cards[card_id]["rarity"]))
            else:
                if amount > 0:
                    sorted_inv[card_pack] = [(cards[card_id]["name"], amount, cards[card_id]["rarity"])]

        if sorted_inv == {}:
            return await interaction.response.send_message("No items.")

        nl = '\n'
        collections = {key:f"__**{key}**__\n{nl.join([f'{i[0]} ({i[2]}) — {i[1]}' for i in value if i[1] > 0])}" for key, value in sorted_inv.items()}
        if pack != None:
            collections = {pack: collections[pack]}

        embed_descs = []
        char_ct = 0
        current = ""
        for collection in collections:
            chars = len("\n\n" + collections[collection])
            if chars + char_ct >= 4096:
                embed_descs.append(current)
                char_ct = 0
                current = ""
            else:
                current += "\n\n" + collections[collection]
                char_ct += len("\n\n" + collections[collection])
        embed_descs.append(current)

        embeds = [
            discord.Embed(
                title="Collected Cards",
                description=i,
                color=discord.Color.blurple()
            )
            for i in embed_descs
        ]

        for embed in embeds:
            embed.set_author(name=str(user), icon_url=user.avatar.url)

        await interaction.response.send_message(embeds=embeds)


    @app_commands.command()
    @app_commands.guild_only()
    async def gift(self, interaction: discord.Interaction, user: discord.User, card: str, quantity: int = 1):
        """Gift a user a card from your inventory"""
        async with aiosqlite.connect("main.db") as db:
            card_entry = await db.execute("SELECT * FROM cards WHERE id = ?", (card,))
            card_tuple = await card_entry.fetchone()

            if card_tuple == None:
                return await interaction.response.send_message("Card not found.", ephemeral=True)

            query = await db.execute("SELECT * FROM inventory WHERE user = ? and card = ?", (user.id, card))

            old = await db.execute(f"SELECT count FROM inventory WHERE user = ? AND card = ?", (interaction.user.id, card))
            old_data = await old.fetchone()
            if old_data == None:
                return await interaction.response.send_message("You don't own this item!", ephemeral=True)
            if old_data[0] < quantity:
                return await interaction.response.send_message("You don't have enough of this item!", ephemeral=True)
            await db.execute(f"UPDATE inventory SET count = ? WHERE user = ?", (old_data[0] - quantity, interaction.user.id,))
            if await query.fetchone() != None:
                old = await db.execute(f"SELECT count FROM inventory WHERE user = ? AND card = ?", (user.id, card))
                await db.execute(f"UPDATE inventory SET count = ? WHERE user = ? AND card = ?", ((await old.fetchone())[0] + quantity, user.id, card))
            else:
                await db.execute(f"INSERT INTO inventory VALUES(?, ?, ?)", (user.id, card, quantity))
            await db.commit()

        embed = discord.Embed(
            title=f"Gift sent!",
            description=f"You sent {user.mention} {quantity} of **{card_tuple[1]} ({card_tuple[4]})** from *{card_tuple[2]}*.",
            color=discord.Color.blurple()
        )
        embed.set_thumbnail(url="attachment://card.png")
        img = discord.File(f"./assets/card_packs/{card_tuple[2]}/{card_tuple[3]}", filename="card.png")
        await interaction.response.send_message(embed=embed, file=img)


    @app_commands.command()
    async def view(self, interaction: discord.Interaction, card: str):
        """View a card from a pack."""
        async with aiosqlite.connect("main.db") as db:
            card_entry = await db.execute("SELECT * FROM cards WHERE id = ?", (card,))
            card_tuple = await card_entry.fetchone()
            if card_tuple == None:
                return await interaction.response.send_message("Not a valid card serial!", ephemeral=True)

        embed = discord.Embed(
            title=card_tuple[1],
            color=discord.Color.blurple()
        )
        embed.set_image(url="attachment://card.png")
        embed.set_footer(text=f'Serial: {card_tuple[0]} | Rarity: {card_tuple[4]}')
        img = discord.File(f"./assets/card_packs/{card_tuple[2]}/{card_tuple[3]}", filename="card.png")
        await interaction.response.send_message(embed=embed, file=img)


    @app_commands.command()
    @app_commands.guild_only()
    ## @app_commands.checks.has_permissions(administrator=True)
    async def archive(self, interaction: discord.Interaction, action: Literal["Archive", "Unarchive"], pack: str):
        """Remove or enable the ability to open a pack"""
        if pack not in os.listdir("./assets/card_packs"):
            return await interaction.response.send_message("Pack not found!", ephemeral=True)
        async with aiosqlite.connect("main.db") as db:
            await db.execute(f"UPDATE cards SET inCirculation = {0 if action == 'Archive' else 1} WHERE pack = ?", (pack,))
            await db.commit()
        embed = discord.Embed(
            description=f"Pack {action}d and is now {'un' if action == 'Archive' else ''}available for opening.",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed)


    async def delete_card_helper(self, cid):
        async with aiosqlite.connect("main.db") as db:
            card_query = await db.execute(f"SELECT * FROM cards WHERE id = ?", (cid,))
            card_tuple = await card_query.fetchone()
            await db.execute(f"DELETE FROM inventory WHERE card = ?", (cid,))
            await db.execute(f"DELETE FROM cards WHERE id = ?", (cid,))
            await db.commit()
        os.remove(f"./assets/card_packs/{card_tuple[2]}/{card_tuple[3]}")
        return card_tuple


    @app_commands.command()
    @app_commands.guild_only()
    ## @app_commands.checks.has_permissions(administrator=True)
    async def delete_card(self, interaction: discord.Interaction, card: str):
        """Permanently delete a card from the pack."""
        card_info = await self.delete_card_helper(card)
        embed = discord.Embed(
            title="Card deleted!",
            description=f"Removed **{card_info[1]}** from *{card_info[2]}*",
            color=discord.Color.green()
        )
        return await interaction.response.send_message(embed=embed)


    @app_commands.command()
    @app_commands.guild_only()
    ## @app_commands.checks.has_permissions(administrator=True)
    async def delete_pack(self, interaction: discord.Interaction, pack: str):
        """Permanently delete a pack."""
        if pack not in os.listdir("./assets/card_packs"):
            return await interaction.response.send_message("Pack not found!", ephemeral=True)
        async with aiosqlite.connect("main.db") as db:
            pack_query = await db.execute(f"SELECT * FROM cards WHERE pack = ?", (pack,))
            pack_cards = await pack_query.fetchall()
        for card in pack_cards:
            cid = card[0]
            await self.delete_card_helper(cid)
        os.rmdir(f"./assets/card_packs/{pack}")
        embed = discord.Embed(
            title="Pack Removed",
            description=f"Removed *{pack}*",
            color=discord.Color.green()
        )
        return await interaction.response.send_message(embed=embed)


    @delete_card.autocomplete('card')
    @view.autocomplete('card')
    @gift.autocomplete('card')
    async def card_search(self, interaction: discord.Interaction, current: str):
        cards = await self.get_cards(key="name")
        return [Choice(name=key, value=value["id"]) for key, value in cards.items() if current in key]


    @open.autocomplete('pack')
    @upload.autocomplete('pack')
    async def pack_search(self, interaction: discord.Interaction, current: str):
        async with aiosqlite.connect("main.db") as db:
            query = await db.execute("SELECT DISTINCT pack FROM cards WHERE inCirculation = 1")
            active_packs = await query.fetchall()
        return [Choice(name=i[0], value=i[0]) for i in active_packs if current in i[0]]


    @archive.autocomplete('pack')
    @delete_pack.autocomplete('pack')
    @inventory.autocomplete('pack')
    async def archive_search(self, interaction: discord.Interaction, current: str):
        return [Choice(name=i, value=i) for i in os.listdir("./assets/card_packs") if current in i]


async def setup(bot):
    await bot.add_cog(Trading(bot))


async def teardown(bot):
    return