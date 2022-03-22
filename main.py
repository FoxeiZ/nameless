import nextcord
from nextcord.ext import commands
from config import DISCORD, MONGODB, TESTOKEN
import motor.motor_asyncio


intents = nextcord.Intents.default()
intents.members = True


class Nameless(commands.Bot):

    def __init__(self):
        super().__init__(intents=intents)
        self.token = DISCORD['token']
        self._db = None

    @property
    def db(self):
        if self._db is None:
            self._db = motor.motor_asyncio.AsyncIOMotorClient(MONGODB['uri'])
            return self._db
        else:
            return self._db

    def run(self, test=False):
        self.load_extension('cogs.music')
        self.load_extension('cogs.nhentai')
        # More module coming soon!!!

        try:
            self.loop.run_until_complete(self.start(self.token if not test else TESTOKEN))
        except KeyboardInterrupt:
            # self.loop.cancel()
            # self.close()
            # self.loop.run_until_complete(self.close())
            self.loop.close()

            print("Shutting down...")

    async def on_ready(self):
        await self.wait_until_ready()
        await self.change_presence(activity=nextcord.Game(name=DISCORD['activity']['name']))
        print(f'Logged in as {self.user} (ID: {self.user.id})')


bot = Nameless()
# change `test` to True for running with test token
bot.run(test=False)
