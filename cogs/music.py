from __future__ import unicode_literals

import asyncio
import itertools
from functools import partial
from random import choice, shuffle
from time import gmtime, strftime
from math import ceil
import gc

import nextcord
from nextcord import Interaction, Embed, VoiceChannel, SlashOption
from nextcord.ext import commands
from yt_dlp import YoutubeDL

ytdlopts = {
    'format': 'bestaudio/93/best',
    'outtmpl': 'downloads/%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'extract_flat': 'in_playlist',
    'no_warnings': True,
    'default_search': 'ytsearch5',
    'source_address': '0.0.0.0'
}

ffmpegopts = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn'
}

ytdl = YoutubeDL(ytdlopts)
color = choice((0xdb314b, 0xdb3a4c, 0xdb424d, 0xdb354b))

def embed_(**kwargs):

    embed = nextcord.Embed(title=kwargs['title'], color=color,
                          description=kwargs['description'])

    if isinstance(kwargs['footer'], (int, float)):
        time = timeconv(kwargs['footer'])
        embed.set_footer(text=time)
    else:
        embed.set_footer(text=kwargs['footer'])

    return embed


def timeconv(time):
    return strftime("%H:%M:%S", gmtime(time))


class VoiceConnectionError(commands.CommandError):
    """Custom Exception class for connection errors."""


class InvalidVoiceChannel(VoiceConnectionError):
    """Exception for cases of invalid Voice Channels."""


class Dropdown(nextcord.ui.Select):

    def __init__(self, data = None):
        options = (nextcord.SelectOption(label=data[0]['title'], description=data[0]['url'], value=0),
                   nextcord.SelectOption(label=data[1]['title'], description=data[1]['url'], value=1),
                   nextcord.SelectOption(label=data[2]['title'], description=data[2]['url'], value=2),
                   nextcord.SelectOption(label=data[3]['title'], description=data[3]['url'], value=3),
                   nextcord.SelectOption(label=data[4]['title'], description=data[4]['url'], value=4),
                   nextcord.SelectOption(label='Select all', value='All')
        )
        
        super().__init__(placeholder='owo', min_values=1, max_values=5, options=options)
    
    async def callback(self, interaction: Interaction):
        self._view.stop()

class YTDLSource(nextcord.PCMVolumeTransformer):

    __slots__ = ('source', 'requester', 'webpage_url', 'title', 'duration', 'thumbnail')
    
    def __init__(self, source = None, *, data, requester):

        super().__init__(source)

        self.requester = requester
        self.duration = data.get('duration')
        self.webpage_url = data.get('webpage_url')
        self.title = data.get('title')
        self.thumbnail = None  # what

    @classmethod
    async def create_source(cls, interaction, search, loop, imported=False, picker=False):
        
        loop = loop or asyncio.get_event_loop()

        to_run = partial(ytdl.extract_info, url=search, download=False)
        data = await loop.run_in_executor(None, to_run)

        data = ytdl.sanitize_info(data)

        if not picker and data['extractor'] == 'youtube:search':
            data = data['entries'][0]

        if 'entries' in data:
            if data['extractor'] == 'youtube:search':

                view = nextcord.ui.View(timeout=30)
                view.add_item(Dropdown(data['entries']))
                
                msg = await interaction.send('Chon nhac di tml', view=view)

                if await view.wait():
                    await msg.edit(content='Timeout!', view=None, delete_after=10)
                    return

                if view.children[0].values is None:
                    await msg.delete()
                    return

                if len(view.children[0].values) == 1 and view.children[0].values[0] == 'All':
                    values = (0, 1, 2, 3, 4)
                else:
                    values = view.children[0].values

                await msg.edit(view=None,
                        embed=Embed(
                            title=f'Added {len(values)} songs',
                            description=f'Requested by {interaction.user}')
                    )

                for i in values:
                    yield cls.to_value(data['entries'][int(i)], interaction.user)

        else:
            yield cls.to_value(data, interaction.user)

            if not imported:
                await interaction.send(embed=embed_(title='Song added',
                        description=f"[{data['title']}]({data.get('webpage_url') or data.get('url')})",
                        footer=data.get('duration') or 0)
                )

    @staticmethod
    def to_value(data, user):
        return {'webpage_url': data.get('webpage_url') or data.get('url'),
                'requester': user,
                'title': data['title'],
                'duration': data.get('duration') or 0
        }

    @classmethod
    async def regather_stream(cls, data, loop):
        """FUck Youtube"""

        loop = loop or asyncio.get_event_loop()
        requester = data['requester']

        to_run = partial(ytdl.extract_info, url=data['webpage_url'], download=False)
        data = await loop.run_in_executor(None, to_run)
        data = ytdl.sanitize_info(data)

        return cls(nextcord.FFmpegPCMAudio(data['url'], **ffmpegopts), data=data, requester=requester)
    

class MusicPlayer:
    """A class which is assigned to each guild using the client for Music.

    This class implements a queue and loop, which allows for different guilds to listen to different playlists
    simultaneously.

    When the client disconnects from the Voice it's instance will be destroyed.
    """
    __slots__ = ('interaction', '_loop', 'client', '_guild', '_channel', '_cog', 'queue',
                 'next', 'current', 'np', 'volume', 'totaldura', 'task', 'source')
    
    def __init__(self, interaction: Interaction, cog = None):
        self.client = interaction.client
        self._guild = interaction.guild
        self._channel = interaction.channel
        self._cog = cog
        
        self.queue = asyncio.Queue()
        self.next = asyncio.Event()
        
        self.np = None
        self.volume = 0.5
        self.current = None
        self.source = None
        self.totaldura = 0
        self._loop = False
        
        self.task = interaction.client.loop.create_task(self.player_loop())

    @property
    def loop(self):
        return self._loop

    @loop.setter
    def loop(self, value: bool):
        self._loop = value
    
    async def player_loop(self):
        """Our main player loop."""
        
        await self.client.wait_until_ready()

        while not self.client.is_closed():
            try:
                self.next.clear()

                if not self._loop or self.source is None:
                    self.current = None
                    self.source = await self.queue.get()

                self.current = await YTDLSource.regather_stream(self.source, loop=self.client.loop)
                self.current.volume = self.volume

                self._guild.voice_client.play(self.current, after=lambda _: self.client.loop.call_soon_threadsafe(self.next.set))

                if not self._loop:
                    self.np = embed_(title=f'Nowplaying', footer=f"Requested by {self.current.requester}",
                                     description=f'[{self.current.title}]({self.current.webpage_url})')
                    await self._channel.send(embed=self.np)

                self.totaldura -= self.source['duration']
            
            except AttributeError as e:
                print(self._guild.id, str(e))
                return self.destroy(self._guild)

            except Exception as e:
                return await self._channel.send(f'There was an error processing your song.\n'
                                                f'```css\n[{e}]\n```')
            
            finally:
                await self.next.wait()

                # Make sure the FFmpeg process is cleaned up.
                self.current.cleanup()
                print('release', gc.collect())

    
    def destroy(self, guild):
        """Disconnect and cleanup the player."""
        return self.client.loop.create_task(self._cog.cleanup(guild))


class Music(commands.Cog):
    """Music related commands."""

    __slots__ = ('client', 'players', 'db')
    
    def __init__(self, client):
        self.client = client
        self.players = {}
        self.db = client.db.nextcord.playlist
 
    async def cleanup(self, guild):
        try:
            await guild.voice_client.disconnect()
        except AttributeError:
            pass

        try:
            player = self.players[guild.id]
            print(player.task.cancel())
        except asyncio.CancelledError:
            pass

        try:
            del self.players[guild.id]
            print('release', gc.collect())
        except KeyError:
            pass

        print(self.players)
    
    async def __local_check(self, interaction: Interaction):
        """A local check which applies to all commands in this cog."""
        if not interaction.guild:
            raise commands.NoPrivateMessage
    
    async def __error(self, interaction: Interaction, error):
        """A local error handler for all errors arising from commands in this cog."""
        if isinstance(error, commands.NoPrivateMessage):
            try:
                return await interaction.send('This command can not be used in Private Messages.')
            except nextcord.HTTPException:
                pass
        elif isinstance(error, InvalidVoiceChannel):
            await interaction.send('Please make sure you are in a valid channel or provide me with one')
    
    def get_player(self, interaction: Interaction):
        """Retrieve the guild player, or generate one."""
        try:
            player = self.players[interaction.guild.id]
        except KeyError:
            player = MusicPlayer(interaction, self)
            self.players[interaction.guild.id] = player

        return player
    
    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        """Destroy player when no one in voice chat"""
        try:
            player = self.players[member.guild.id]
        except KeyError:
            return

        try:
            if len(player._guild.voice_client.channel.members) == 1: # If bot is alone
                await self.cleanup(player._guild)
                await player._channel.send('Hic. Don\' leave me alone :cry:')
        except AttributeError:
            await self.cleanup(player._guild)
    
    @nextcord.slash_command(name='connect', guild_ids=[890026104277057577], force_global=True)
    async def connect_(self, interaction: Interaction, 
        channel: nextcord.abc.GuildChannel = SlashOption(name='channel', description='Join where?', required=False, channel_types=[nextcord.ChannelType.voice])
    ):
        """Connect to voice.
        Parameters
        ------------
        channel: nextcord.VoiceChannel [Optional]
            The channel to connect to. If a channel is not specified, an attempt to join the voice channel you are in
            will be made.
        This command also handles moving the bot to different channels.
        """
        if not channel:
            try:
                channel = interaction.user.voice.channel
            except AttributeError:
                await interaction.send('No channel to join. Please either specify a valid channel or join one.')
                raise InvalidVoiceChannel

        vc = interaction.guild.voice_client

        if vc:
            if vc.channel.id == channel.id:
                return
            try:
                await vc.move_to(channel)
            except asyncio.TimeoutError:
                raise VoiceConnectionError(f'Moving to channel: <{channel}> timed out.')
        else:
            try:
                await channel.connect()
            except asyncio.TimeoutError:
                raise VoiceConnectionError(f'Connecting to channel: <{channel}> timed out.')

        self.get_player(interaction)
        await interaction.send(f'Connected to: **{channel}**', delete_after=20)

    @nextcord.slash_command(name='play', guild_ids=[890026104277057577], force_global=True)
    async def play_(self, interaction: Interaction,
        url = SlashOption(description='URL go brrrrr', required=True),
        picker: bool = SlashOption(description='Show a dropdown menu', required=False, default=False)
    ):

        await interaction.response.defer()
        
        vc = interaction.guild.voice_client
        try:
            if not vc:
                await self.connect_.invoke_user(interaction, member=None)
        except InvalidVoiceChannel:
            return

        player = self.get_player(interaction)

        async for source in YTDLSource.create_source(interaction, url, loop=self.client.loop, picker=picker): # async yield {'webpage_url'....}
            player.totaldura += source['duration']
            await player.queue.put(source)

    @nextcord.slash_command(name='pause', guild_ids=[890026104277057577], force_global=True)
    async def pause_(self, interaction: Interaction):
        """Pause the currently playing song."""
        vc = interaction.guild.voice_client

        if not vc:
            return await interaction.send('I am currently not in any voice chat!', delete_after=20)

        if vc.is_paused and vc.current is None:
            return await interaction.send('I am not currently playing anything!', delete_after=20)

        vc.pause()
        await interaction.send(f'**`{interaction.user}`**: Paused the song!')

    @nextcord.slash_command(name='resume', guild_ids=[890026104277057577], force_global=True)
    async def resume_(self, interaction: Interaction):
        """Resume the currently paused song."""
        vc = interaction.guild.voice_client

        if not vc or not vc.is_connected():
            await interaction.send('I am not currently playing anything!', delete_after=20)
            return
        elif not vc.is_paused():
            return

        vc.resume()
        await interaction.send(f'**`{interaction.user}`**: Resumed the song!')

    @nextcord.slash_command(name='skip', guild_ids=[890026104277057577], force_global=True)
    async def skip_(self, interaction: Interaction):
        """Skip the song."""
        vc = interaction.guild.voice_client

        if not vc or not vc.is_connected():
            return await interaction.send('I am not currently playing anything!', delete_after=20)

        if vc.is_paused():
            pass
        elif not vc.is_playing():
            return

        player = self.get_player(interaction)
        player.source = None

        vc.stop()
        await interaction.send(f'**`{interaction.user}`**: Skipped the song!')

    @nextcord.slash_command(name='loop', guild_ids=[890026104277057577], force_global=True)
    async def loop_(self, interaction: Interaction):
        """Loop the currently playing song."""
        vc = interaction.guild.voice_client

        if not vc or not vc.is_connected():
            return await interaction.send('I am not currently playing anything!', delete_after=20)

        player = self.get_player(interaction)

        if not player.loop:
            player.loop = True
            await interaction.send('Enabled looping the current song!')
        else:
            player.loop = False
            await interaction.send('Disabled looping the current song!')

    @nextcord.slash_command(name='queue', guild_ids=[890026104277057577], force_global=True, description='Retrieve a basic queue of upcoming songs')
    async def queue_info(self, interaction,
        page: int = SlashOption(required=False, default=1)
    ):
        vc = interaction.guild.voice_client

        if not vc or not vc.is_connected():
            return await interaction.send('I am not currently connected to voice!', delete_after=20)

        player = self.get_player(interaction)
        if player.queue.empty():
            return await interaction.send('There are currently no more queued songs.')

        index = (page-1)*5
        max_index = len(player.queue._queue)
        upcoming = list(itertools.islice(player.queue._queue, index, index+5))
        if not upcoming:
            await interaction.send('Out of index!')
            return

        desc = '\n'
        for i, q in enumerate(upcoming, start=index):
            if len(q['title']) > 50:
                title = q['title'][:50] + '...' + q["title"][-5:]
            else:
                title = q["title"]

            desc += (f'\n[{str(i+1) + ". " + title}]({q["webpage_url"]})\n')

        embed = nextcord.Embed(title=f'{max_index} songs in queue')
        embed.add_field(name=f'Total time: {timeconv(player.totaldura)}', value=desc)
        embed.set_footer(text=f'Page {page}/{ceil(max_index/5)}')
        await interaction.send(embed=embed)

    @nextcord.slash_command(name='move', guild_ids=[890026104277057577], force_global=True)
    async def move(self, interaction, i: int, j: int):

        vc = interaction.guild.voice_client
        if not vc or not vc.is_connected():
            return await interaction.send('I am not currently connected to voice!', delete_after=20)

        i = i-1
        j = j-1

        player = self.get_player(interaction)
        if i < len(player.queue._queue) and j < len(player.queue._queue):
            player.queue._queue[i], player.queue._queue[j] = player.queue._queue[j], player.queue._queue[i]
            await interaction.send('✅')
        else:
            await interaction.send('Out of index!')

    @nextcord.slash_command(name='shuffle', guild_ids=[890026104277057577], force_global=True)
    async def shuffle_(self, interaction: Interaction):
        vc = interaction.guild.voice_client

        player = self.get_player(interaction)
        if not vc or not vc.is_connected():
            return await interaction.send('I am not currently connected to voice!', delete_after=20)

        if player.queue.empty():
            return await interaction.send('There are no more queued songs to shuffle.')

        shuffle(player.queue._queue)
        await interaction.send('✅') # white_check_mark

    @nextcord.slash_command(name='remove', guild_ids=[890026104277057577], force_global=True)
    async def remove(self, interaction, index: int):
        """Remove song from queue"""
        player = self.get_player(interaction)
        title = player.queue._queue[index-1]['title']

        if player.queue.empty():
            return await interaction.send('There are currently no more queued songs.')

        del player.queue._queue[index-1]

        await interaction.send(f'**`{interaction.user}`**: Removed `{title}` from queue')

    @nextcord.slash_command(name='nowplaying', guild_ids=[890026104277057577], force_global=True)
    async def now_playing_(self, interaction: Interaction):
        """Display info about current song."""
        vc = interaction.guild.voice_client

        if not vc or not vc.is_connected():
            return await interaction.send('I am not currently connected to voice!', delete_after=20)

        player = self.get_player(interaction)
        if not player.current:
            return await interaction.send('I am not currently playing anything!')

        await interaction.send(embed=player.np)

    @nextcord.slash_command(name='volume', guild_ids=[890026104277057577], force_global=True)
    async def change_volume(self, interaction, *, vol: float):
        """Change the player volume.
        Parameters
        ------------
        volume: float or int [Required]
            The volume to set the player to in percentage. This must be between 1 and 200.
        """
        vc = interaction.guild.voice_client

        if not vc or not vc.is_connected():
            return await interaction.send('I am not currently connected to voice!', delete_after=10)

        if not 0 < vol < 201:
            return await interaction.send('Please enter a value between 1 and 200.')

        if vc.source:
            vc.source.volume = vol / 100

        player = self.get_player(interaction)

        player.volume = vol / 100
        await interaction.send(f'Set the volume to **{vol}%**')

    @nextcord.slash_command(name='stop', guild_ids=[890026104277057577], force_global=True)
    async def stop_(self, interaction: Interaction):

        vc = interaction.guild.voice_client

        if not vc or not vc.is_connected():
            return await interaction.send('I am not currently playing anything!', delete_after=10)

        await self.cleanup(interaction.guild)


def setup(bot):
    bot.add_cog(Music(bot))