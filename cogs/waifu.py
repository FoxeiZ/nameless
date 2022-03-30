import nextcord
from nextcord.ext import commands
import asyncio
import gc


class UserInteraction(nextcord.ui.View):

    __slots__ = ('embed', 'db', 'waifu_id', 'action')

    def __init__(self, embed, waifu_id, db):
        super().__init__(timeout=20)
        self.action = None
        self.embed = embed
        self.waifu_id = waifu_id
        self.db = db

    async def interaction_check(self, interaction: nextcord.Interaction):
        await interaction.response.defer()
        return True

    @nextcord.ui.button(style=nextcord.ButtonStyle.primary, emoji='❤️')
    async def fav(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
        await self.db.update_one({'discord_id': interaction.user.id}, {'$push': {'waifu': self.waifu_id}}, upsert=True)

        self.embed.set_footer(text=f"Owned by {interaction.user.name}")
        await interaction.edit_original_message(view=None, embed=self.embed)
        
        self.action = 'fav'
        self.stop()

    @nextcord.ui.button(style=nextcord.ButtonStyle.primary, emoji='🔄')
    async def reroll(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
        self.action = 'reroll'
        self.stop()


class Paginator(nextcord.ui.View):

    __slots__ = ('pages', 'id_', 'page_num', 'current')

    def __init__(self, embeds=None):
        super().__init__(timeout=60)

        self.id_ = 0
        self.page_num = len(embeds) - 1
        self.pages = embeds
        for index, page in enumerate(self.pages, start=1):
            page.set_footer(text=f'{index}/{len(embeds)}')

        self.current = None
        self.msg = None

    def set_message(self, message):
        self.msg = message

    async def interaction_check(self, interaction):
        await interaction.response.defer()
        return True

    @nextcord.ui.button(style=nextcord.ButtonStyle.primary, emoji='⏮️')
    async def prev(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
        self.id_ = 0
        await self.msg.edit(embed=self.pages[self.id_])

    @nextcord.ui.button(style=nextcord.ButtonStyle.primary, emoji='◀️')
    async def backward(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
        if self.id_ == 0:
            self.id_ = self.page_num
        else:
            self.id_ -= 1

        await self.msg.edit(embed=self.pages[self.id_])

    @nextcord.ui.button(style=nextcord.ButtonStyle.primary, emoji='▶️')
    async def forward(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
        if self.id_ == self.page_num:
            self.id_ = 0
        else:
            self.id_ += 1

        await self.msg.edit(embed=self.pages[self.id_])

    @nextcord.ui.button(style=nextcord.ButtonStyle.primary, emoji='⏭️')
    async def next_(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
        self.id_ = self.page_num
        await self.msg.edit(embed=self.pages[self.id_])


class Waifu(commands.Cog):

    __slots__ = ('client', 'db', 'user')

    def __init__(self, client):
        self.client  = client
        self.db   = client.db.gacha.waifu
        self.user = client.db.gacha.user

    @nextcord.slash_command(name='waifu', guild_ids=[890026104277057577], force_global=True)
    async def waifu(interaction: nextcord.Interaction):
        pass

    async def display(self, waifu_resp):
        embed = nextcord.Embed(title=waifu_resp['name'],
                              description=f"Rank: #{waifu_resp['like_rank']} \
                              \n{waifu_resp['likes']}:diamonds:")

        embed.set_image(url=waifu_resp['display_picture'])

        owned = await self.user.find_one({'waifu': {'$all': [waifu_resp['id']]}})
        if owned:
            user = self.client.get_user(owned['discord_id'])
            embed.set_footer(text=f"Owned by {user.name}")

        return embed

    @waifu.subcommand(description='Roll em up!')
    async def roll(self, interaction: nextcord.Interaction):

        await interaction.response.defer()
        message = await interaction.send('Please wait...')

        async for waifu in self.db.aggregate([{'$sample': {'size': 5}}]):

            embed = await self.display(waifu_resp=waifu)
            menu = UserInteraction(embed, waifu['id'], self.user)
            await message.edit(content=None, embed=embed, view=menu)

            if await menu.wait():
                return await message.edit(view=None)

            if menu.action == 'fav':
                break
            elif menu.action == 'reroll':
                continue

        await message.edit(view=None)
        del message, embed, menu  # cleanup stuff?
        gc.collect()

    @waifu.subcommand(name='list', description='Roll em up!')
    async def list_(self, interaction: nextcord.Interaction):

        await interaction.response.defer()

        data = await self.user.find_one({'discord_id': interaction.user.id})

        waifuList = []
        for index in data['waifu']:
            waifu = await self.db.find_one({'id': index})
            waifuList.append(await self.display(waifu))

        paginator = Paginator(waifuList)
        message = await interaction.send(embed=paginator.pages[0], view=paginator)
        paginator.set_message(message)

        await paginator.wait()
        await message.edit(view=None)
        del data, waifuList, waifu, paginator, message  # cleanup stuff?
        gc.collect()


def setup(client):
    client.add_cog(Waifu(client))
