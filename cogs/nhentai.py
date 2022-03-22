from functools import partial
import nextcord
from nextcord import SlashOption, Interaction, Embed
from nextcord.ui import Button
from nextcord.ext import commands
from core.nhentai import nhentai, nhentaiNoContent


class Paginator(nextcord.ui.View):

    __slots__ = ('pages', 'id_', 'page_num', 'current')
    
    def __init__(self, doujin = None):
        super().__init__(timeout=10)

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

    @nextcord.ui.button(style=nextcord.ButtonStyle.primary, emoji='⏮️')
    async def prev(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
        self.id_ = 0
        await self.msg.edit(embed=self.pages[self.id_])

    @nextcord.ui.button(style=nextcord.ButtonStyle.primary, emoji='⏭️')
    async def next_(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
        self.id_ = self.page_num
        await self.msg.edit(embed=self.pages[self.id_])

    @nextcord.ui.button(style=nextcord.ButtonStyle.primary, emoji='❌')
    async def close(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
        self.stop()


class Nhentai(commands.Cog):
    
    def __init__(self, client):
        self.client = client

    @nextcord.slash_command(name='nhentai', guild_ids=[890026104277057577])
    async def nhentai(interaction: Interaction):
        pass

    @nhentai.subcommand(description='huh')
    async def read(self, interaction: Interaction,
        sauce: int = SlashOption(description='Give me da sauce', required=True)
    ):
        await interaction.response.defer()

        try:
            ret = await nhentai().getByID(sauce)
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

    @nhentai.subcommand(description='huh')
    async def info(self, interaction: Interaction,
        sauce: int = SlashOption(description='Give me da sauce', required=True)
    ):
        ...

def setup(bot):
    bot.add_cog(Nhentai(bot))