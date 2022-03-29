import aiohttp
from typing import Optional
import reprlib


class nhentaiException(Exception):
    """idk"""
    pass


class nhentaiNoContent(Exception):
    """self explain sooo..."""
    pass


class TheForbiddenTag(Exception):
    """If the tag is blacklisted, this expectation will be called."""
    pass


class nhentaiContainer:

    __slots__ = ('url', 'id', 'tags', 'title', 'title_jpn', 'title_prt',
                 'media_id', 'images', 'pages', 'cover', 'scanlator', 'thumbnail', 
                 'artists', 'lang', 'favorites', 'parody', 'num_pages')

    def __init__(self, payload: dict):
        self.url       = 'https://nhentai.net/g/' + str(payload['id'])
        self.id        = payload['id']
        self.title     = payload['title']['english']
        self.title_jpn = payload['title']['japanese']  # Sometime this is empty
        self.title_prt = payload['title']['pretty']    # Short title of the doujin
        self.media_id  = payload['media_id']
        self.pages     = payload['images']['pages']
        self.num_pages = payload['num_pages']
        self.cover     = payload['images']['cover']
        self.thumbnail = payload['images']['thumbnail']
        self.scanlator = payload['scanlator']
        self.favorites = payload['num_favorites']
        self.tags      = []
        self.artists   = []
        self.lang      = None

        self.cover['url'] = "https://t.nhentai.net/galleries/" + self.media_id + "/cover.jpg"

        for i in range(0, self.num_pages):
            if self.pages[i]['t'] == 'p':
                type = 'png'
            else:
                type = 'jpg'
            self.pages[i]['url'] = f"https://i.nhentai.net/galleries/{self.media_id}/{i+1}.{type}"

        for tag in payload['tags']:
            if tag['type'] == 'artist':
                self.artists.append(tag)
            elif tag['type'] == 'language':
                self.lang = tag
            elif tag['type'] == 'parody':
                self.parody = tag
            else:
                if tag['name'] == 'lolicon':
                    continue
                self.tags.append(tag)

    def __str__(self) -> str:
        return self.title

    def __int__(self) -> int:
        return self.id

    def __repr__(self):
        rep = reprlib.Repr()
        return f"<nhentaiContainer(id={self.id}, media_id={self.media_id}, title={rep.repr(self.title)})>"


class nhentai:

    __slots__ = ('baseURL', 'response', 'http')
    def __init__(self):

        self.baseURL  = 'https://nhentai.net/api'
        self.response = None

    async def getByID(self, id: int = None):
        self.response = await self._request(url=f"{self.baseURL}/gallery/{str(id)}")
        return nhentaiContainer(self.response)

    async def getCover(self, id: int):
        if not self.response or id != self.response['id']:
            self.response = await self.getByID(id=id)

        return self.response.cover['url']

    async def getPageImage(self, id: int):
        """
        Get a list of image URLs for the doujin.
        """
        if not self.response or id != self.response['id']:
            self.response = await self.getByID(id=id)

        return self.response.pages

    async def searchByTitle(self, title: str = None, page = 1, sort='popular'):
        """
        Arguments:
            title[str]: Search using doujin title.

            page[int]: Page number. (Default: 1)

            sort[str]: popular, popular-year, popular-month, popular-week, popular-today, date (Default: popular)
        """
        payload = {'query': 'title:' + title,
                   'page': page,
                   'sort': sort}

        response = await self._request(url=f"{self.baseURL}/galleries/search", payload=payload)

        if response['result'] == 0:
            raise nhentaiException(f"No results found for {title}")

        if isinstance(response['result'], list):
            result = [nhentaiContainer(_) for _ in response['result']]
        else:
            result = nhentaiContainer(response['result'])

        return result

    async def searchByTag(self, tags: list, page = 1, sort='popular'):
        """
        Arguments:
            tags[list]: List of tags.

            page[int]: Page number. (Default: 1)

            sort[str]: popular, popular-year, popular-month, popular-week, popular-today, date (Default: popular)
        """
        tags = '+'.join(tags)  # Convert list to string
        payload = {'query': f'tag:{tags}',
                   'page': page,
                   'sort': sort}

        response = await self._request(url=f"{self.baseURL}/galleries/search", payload=payload)

        if response['result'] == 0:
            raise nhentaiException(f"No results found for {tags}")

        if isinstance(response['result'], list):
            result = [nhentaiContainer(_) for _ in response['result']]
        else:
            result = nhentaiContainer(response['result'])

        return result

    async def searchByPayload(self, payloadType, payload: dict):
        """
        Arguments:
            payloadType[str]: Type of payload. (ex: search)
            payload[dict]: Payload.

        """
        response = await self._request(url=f"{self.baseURL}/galleries/{payloadType}", payload=payload)

        if response['result'] == 0:
            raise nhentaiException(f"No results found")

        if isinstance(response['result'], list):
            result = [nhentaiContainer(_) for _ in response['result']]
        else:
            result = nhentaiContainer(response['result'])

        return result

    async def getLatest(self):

        payload = {'query': 'pages:>0',
                   'page': 2,
                   'sort': 'date'}
        return (await self.searchByPayload(payloadType='search', payload=payload))[0]

    async def _request(self, url, payload: Optional[dict] = None):
        async with aiohttp.ClientSession() as session:
            async with session.get(url=url, params=payload) as resp:
                if resp.status == 200:
                    response = await resp.json()
                    return response
                elif resp.status == 404:
                    raise nhentaiNoContent(f'Nothing found for this sauce (404):\n{await resp.json()}')
                else:
                    raise nhentaiException(f"_request({resp.status}): Failed to get respone from server\n{await resp.json()}")


if __name__ == "__main__":
    pass

# https://nhentai.net/api/galleries/search?page=1&sort=date&query=pages:%3E0 # get latest
