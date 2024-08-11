import json
import os
import re
from typing import List, Tuple
from typing import Optional
from pytube import YouTube
import disnake
import dpath.util
import requests
import yt_dlp as youtube_dl
from disnake.ext import commands
from disnake.utils import get
import asyncio
import time


last_call_time = 0
CALL_LIMIT = 10  # Минимальный интервал между вызовами в секундах


def rate_limited(func):
    async def wrapper(*args, **kwargs):
        global last_call_time
        current_time = time.time()
        if current_time - last_call_time < CALL_LIMIT:
            await asyncio.sleep(CALL_LIMIT - (current_time - last_call_time))
        last_call_time = time.time()
        return await func(*args, **kwargs)
    return wrapper


musics = dict()
commander = '*'
intents = disnake.Intents.all()
TOKEN = ""
ibio = commands.Bot(intents=intents, command_prefix=commander)
USER_AGENT = 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:45.0) Gecko/20100101 Firefox/45.0'
PATTERNS = [
    re.compile(r'window\["ytInitialData"\] = (\{.+?\});'),
    re.compile(r'var ytInitialData = (\{.+?\});'),
]
session = requests.Session()
session.headers['User-Agent'] = USER_AGENT


def get_ytInitialData(url: str) -> Optional[dict]:
    rs = session.get(url)
    for pattern in PATTERNS:
        m = pattern.search(rs.text)
        if m:
            data_str = m.group(1)
            return json.loads(data_str)


def search_youtube(text_or_url: str) -> List[Tuple[str, str]]:
    if text_or_url.startswith('http'):
        url = text_or_url
    else:
        text = text_or_url
        url = f'https://www.youtube.com/results?search_query={text}'
    items = []
    data = get_ytInitialData(url)
    if not data:
        return items
    videos = dpath.util.values(data, '**/videoRenderer')
    if not videos:
        videos = dpath.util.values(data, '**/playlistVideoRenderer')
    for video in videos:
        if 'videoId' not in video:
            continue
        url = 'https://www.youtube.com/watch?v=' + video['videoId']
        try:
            title = dpath.util.get(video, 'title/runs/0/text')
        except KeyError:
            title = dpath.util.get(video, 'title/simpleText')
        items.append((url, title))
    return items


ytdl_format_options = {
    'format': 'bestaudio',
    'postprocessors': [{
        'key': 'FFmpegExtractAudio',
        'preferredcodec': 'mp3',
        'preferredquality': '192',
    }],
    'socket_timeout': 120,
}

ffmpeg_options = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn'
}

ytdl = youtube_dl.YoutubeDL(ytdl_format_options)


class YTDLSource(disnake.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get('title')
        self.url = data.get('url')

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=True):
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=False))

        if 'entries' in data:
            data = data['entries'][0]

        filename = data['url'] if stream else ytdl.prepare_filename(data)
        return cls(disnake.FFmpegPCMAudio(filename, **ffmpeg_options), data=data)


class Platform(disnake.ui.View):
    def __int__(self):
        super().__init__()

    @disnake.ui.button(style=disnake.ButtonStyle.gray, emoji="⏹")
    async def skip(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
        vo = get(ibio.voice_clients, guild=inter.guild)
        vo.stop()
        await inter.send('Скип', ephemeral=True)

    @disnake.ui.button(style=disnake.ButtonStyle.gray, emoji="🛂")
    async def list(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
        with open(f'data/{inter.author.id}.txt', mode='rt', encoding='utf-8') as file:
            opt = list()
            file = file.read().split('\n')
            for i in file:
                opt.append(disnake.SelectOption(label=YouTube(i).title, value=i))
            await inter.send(view=DropDownView(opt), ephemeral=True)

    @disnake.ui.button(style=disnake.ButtonStyle.gray, emoji="🔃")
    async def repeat(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
        global flag_repeat
        flag_repeat = True if not flag_repeat else False
        if flag_repeat:
            await inter.send('теперь ваш трек будет повторяться', ephemeral=True)
        else:
            await inter.send('снимаю повторение трека', ephemeral=True)

    @disnake.ui.button(style=disnake.ButtonStyle.red, label='❤')
    async def like(self, button: disnake.ui.Button, ctx: disnake.CommandInteraction):
        await ctx.send(YouTube(musics[ctx.guild.id][0]).title, ephemeral=True)
        fib = os.listdir('./data')
        if f'{ctx.author.id}.txt' in fib:
            with open(f'data/{ctx.author.id}.txt', mode='rt', encoding='utf-8') as file:
                file = (file.read()).split('\n')
                if musics[ctx.guild.id][0] not in file:
                    with open(f'data/{ctx.author.id}.txt', mode='a', encoding='utf-8') as file:
                        file.write(f'\n{musics[ctx.guild.id][0]}')
        else:
            with open(f'data/{ctx.author.id}.txt', mode='w', encoding='utf-8') as file:
                file.write(f'{musics[ctx.guild.id][0]}')


@ibio.slash_command(name='favorites', description='ваши любимы треки')
async def favorites(ctx: disnake.CommandInteraction):
    with open(f'data/{ctx.author.id}.txt', mode='rt', encoding='utf-8') as file:
        opt = list()
        file = (file.read()).split('\n')
        print(file)
        for i in file:
            opt.append(disnake.SelectOption(label=i))
        await ctx.send(view=DropDownView(opt), ephemeral=True)


class Dropdown(disnake.ui.StringSelect):
    def __init__(self, pool):
        super().__init__(placeholder='Ваши песни', min_values=1, max_values=1, options=pool)

    async def callback(self, ctx: disnake.CommandInteraction):
        await play(ctx, self.values[0])


class DropDownView(disnake.ui.View):
    def __init__(self, pool):
        super().__init__()
        self.add_item(Dropdown(pool))


def next_mus(ctx):
    async def mus():
        musics[ctx.guild.id] = musics[ctx.guild.id][1:]
        vo = get(ibio.voice_clients, guild=ctx.guild)
        if not musics[ctx.guild.id]:
            await vo.disconnect()
            return
        url = musics[ctx.guild.id][0]
        player = await YTDLSource.from_url(url, loop=asyncio.get_event_loop(), stream=True)
        vo.play(player, after=lambda e: next_mus(ctx))
    asyncio.run_coroutine_threadsafe(mus(), ibio.loop)


def add_server(ctx):
    server = ctx.guild
    if server.id not in musics:
        musics[ctx.guild.id] = list()


@ibio.slash_command(name='dis', description='kfdsf')
async def dis(ctx: disnake.CommandInteraction):
    vo = get(ibio.voice_clients, guild=ctx.guild)
    musics[ctx.guild.id] = list()
    await vo.disconnect()


@ibio.slash_command(name='play', description='запускает вашу музыку')
async def play(ctx: disnake.CommandInteraction, url):
    add_server(ctx)
    if 'http' not in url:
        url = (search_youtube(url))[0][0]
    musics[ctx.guild.id].append(url)
    if len(musics[ctx.guild.id]) > 1:
        await ctx.send("Ваш трек добавлен в очередь", ephemeral=True)
    else:
        await ctx.send("Запуск...", ephemeral=True)
        chanel = ctx.author.voice.channel
        if not chanel:
            await ctx.send("Вы не подключены к голосовому каналу.")
            return
        vo = get(ibio.voice_clients, guild=ctx.guild)
        if vo and vo.is_connected():
            await vo.move_to(chanel)
        else:
            vo = await chanel.connect()
        player = await YTDLSource.from_url(url, loop=asyncio.get_event_loop(), stream=True)
        vo.play(player, after=lambda e: next_mus(ctx))
    emb = disnake.Embed(title=f'{YouTube(musics[ctx.guild.id][-1]).title}', color=disnake.Color.from_rgb(250, 235, 214))
    emb.set_author(name=ctx.author.name, icon_url=ctx.author.avatar)
    view = Platform(timeout=None)
    output = '\n'.join([YouTube(mus).title for mus in musics[ctx.guild.id][-3:]])
    emb.add_field(name='', value=output)
    await ctx.channel.send(embed=emb, view=view)


@ibio.slash_command(name='panel', description='открывает панель управления ботом')
async def panel(ctx: disnake.CommandInteraction):
    emb = disnake.Embed(title='Панель управления', color=disnake.Color.from_rgb(57, 47, 44))
    emb.set_author(name=ibio.user.name, icon_url=ibio.user.avatar)
    emb.set_footer(text=ctx.author.name, icon_url=ctx.author.avatar)
    view = Platform(timeout=None)
    await ctx.send(embed=emb, view=view)
    await view.wait()


# @ibio.event
# async def on_command_error(ctx, error):
#     if isinstance(error, commands.CommandInvokeError) and isinstance(error.original, disnake.errors.HTTPException):
#         if error.original.status == 429:
#             retry_after = int(error.original.response.headers.get('Retry-After', 1))
#             await ctx.send(f"Rate limit exceeded. Retrying after {retry_after} seconds.")
#             await asyncio.sleep(retry_after)
#             await ctx.reinvoke()
#         else:
#             await ctx.send(f"An error occurred: {error.original}")
#     else:
#         await ctx.send(f"An error occurred: {error}")
#
#
# async def start_bot():
#     try:
#         await ibio.start(TOKEN)
#     except disnake.errors.HTTPException as e:
#         if e.status == 429:
#             retry_after = int(e.response.headers.get('Retry-After', 1))
#             print(f'Rate limit exceeded. Retrying after {retry_after} seconds.')
#             await asyncio.sleep(retry_after)
#             await start_bot()
#
#
# asyncio.run(start_bot())
ibio.run(TOKEN)
