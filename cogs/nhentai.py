from random import randint
from functools import partial

import nextcord
from nextcord import SlashOption, Interaction, Embed
from nextcord.ui import Button
from nextcord.ext import commands
from core.nhentai import nhentai, nhentaiNoContent


class Paginator(nextcord.ui.View):

    __slots__ = ('pages', 'id_', 'page_num', 'current')

    def __init__(self, doujin=None):
        super().__init__(timeout=60)

        self.id_ = 0
        self.pages = []
        for index, page in enumerate(doujin.pages, start=1):
            self.pages.append(Embed(title=doujin.title_prt, description=doujin.id, url=doujin.url
                              ).set_image(url=page['url']
                              ).set_footer(text=f'{index}/{doujin.num_pages}'))
        self.page_num = doujin.num_pages - 1
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
            return None

        self.id_ -= 1
        await self.msg.edit(embed=self.pages[self.id_])

    @nextcord.ui.button(style=nextcord.ButtonStyle.primary, emoji='▶️')
    async def forward(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
        if self.id_ == self.page_num:
            return None

        self.id_ += 1
        await self.msg.edit(embed=self.pages[self.id_])

    @nextcord.ui.button(style=nextcord.ButtonStyle.primary, emoji='⏭️')
    async def next_(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
        self.id_ = self.page_num
        await self.msg.edit(embed=self.pages[self.id_])

    @nextcord.ui.button(style=nextcord.ButtonStyle.primary, emoji='❌')
    async def close(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
        self.stop()


class InfoView(nextcord.ui.View):

    __slots__ = ('value', 'user')

    def __init__(self, user):
        super().__init__(timeout=60)
        self.value = None
        self.user = user

    async def interaction_check(self, interaction: Interaction):
        await interaction.response.defer()

        if interaction.user.id == self.user.id:
            return True
        
        return False

    @nextcord.ui.button(style=nextcord.ButtonStyle.primary, emoji='📖')
    async def read(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
        self.value = 'read'
        self.stop()

    @nextcord.ui.button(style=nextcord.ButtonStyle.primary, emoji='❤️')
    async def fav(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
        self.value = 'fav'

    @nextcord.ui.button(style=nextcord.ButtonStyle.primary, emoji='🗑️')
    async def close(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
        self.value = 'close'
        self.stop()


class Dropdown(nextcord.ui.Select):

    def __init__(self, data = None):

        options = []
        for item in data[:5]:
            if len(item.title_prt) > 100:
                item.title_prt = item.title_prt[:97] + '...'
            options.append(nextcord.SelectOption(label=item.title_prt, description=item.id, value=item.id))

        super().__init__(placeholder='owo', min_values=1, max_values=1, options=options)

    async def callback(self, interaction: Interaction):
        self._view.stop()


class Nhentai(commands.Cog):

    def __init__(self, client):
        self.client = client
        self.api = nhentai()

    @nextcord.slash_command(name='nhentai', guild_ids=[890026104277057577], force_global=True)
    async def nhentai(interaction: Interaction):
        pass

    @nhentai.subcommand(description='coom')
    async def read(self, interaction: Interaction,
        sauce: int = SlashOption(description='Give me da sauce', required=True)
    ):
        try:
            await interaction.response.defer()
        except nextcord.InteractionResponded:
            pass

        try:
            ret = await self.api.getByID(sauce)
        except nhentaiNoContent:
            await interaction.send('Can\'t find any !!')
            return

        paginator = Paginator(ret)
        message = await interaction.send(embed=paginator.pages[0], view=paginator)
        paginator.set_message(message)

        if await paginator.wait():
            await message.edit(view=None)
        else:
            await message.delete()

    @nhentai.subcommand(description='preload da coom')
    async def info(self, interaction: Interaction,
        sauce: int = SlashOption(description='Give me da sauce', required=True)
    ):

        try:
            await interaction.response.defer()
        except nextcord.InteractionResponded:
            pass
        message = await interaction.send('Please wait...')

        doujin = await self.api.getByID(id=sauce)

        embed = Embed(title=doujin.title_prt, description=f'sauceid: {doujin.id}', url=doujin.url, color=0x00ff00)
        embed.set_image(url=doujin.cover['url'])
        embed.add_field(name='Artist', value=', '.join(_['name'].title() for _ in doujin.artists), inline=True)
        embed.add_field(name='Language', value=doujin.lang['name'], inline=True)
        embed.add_field(name='Pages', value=doujin.num_pages)
        embed.add_field(name='Tags', value=' '.join(f"`{_['name'].title()}`" for _ in doujin.tags))

        menu = InfoView(interaction.user)
        await message.edit(content=None, embed=embed, view=menu)

        await menu.wait()
        if menu.value == 'read':
            await message.delete()
            await self.read.invoke_slash(interaction, sauce=sauce)
        elif menu.value == 'close':
            await message.delete()

    @nhentai.subcommand(description='get random sauce for you to coom')
    async def random(self, interaction: Interaction):

        try:
            await interaction.response.defer()
        except nextcord.InteractionResponded:
            pass

        resp  = await self.api.getLatest()
        sauce = randint(1, int(resp.id))
        await self.info.invoke_slash(interaction, sauce=sauce)
        
    @nhentai.subcommand(description='want to coom?')
    async def search(self, interaction: Interaction,
        tags: str = SlashOption(required=True, description='Seperate each tag using a comma')
    ):
        try:
            await interaction.response.defer()
        except nextcord.InteractionResponded:
            pass
        message = await interaction.send('Please wait...')

        tags = tags.replace(' ,', ',').replace(', ', ',')
        tags = tags.split(',')

        resp = await self.api.searchByTag(tags)
        if len(resp) == 0:
            return await message.edit(content='Nothing found for this sauce. Sorry', delete_after=20)

        if len(resp) > 1:
            view = nextcord.ui.View(timeout=30)
            view.add_item(Dropdown(resp))
            await message.edit(content='Here are the results. Select one', view=view)
            
            if await view.wait():
                return await message.edit(content='Timeout!', view=None, delete_after=20)
            
            if view.children[0].values is None:
                return await message.delete()

            resp = view.children[0].values[0]
        else:
            resp = resp[0].id

        await message.delete()
        await self.info.invoke_slash(interaction, sauce=int(resp))
        

def setup(bot):
    bot.add_cog(Nhentai(bot))