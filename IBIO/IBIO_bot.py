import datetime
import json
import os
import re
from random import choice
from typing import List, Tuple, Optional
from typing import Optional

import disnake
import dpath.util
import requests
import yt_dlp as youtube_dl
from disnake.ext import commands
from disnake.utils import get

commander = '*'
intents = disnake.Intents.all()
TOKEN = "ODM0Nzc1NzE0MDExOTM4ODY2.GoUssW.qihAm5kUBceqVmkEHge5Jbye4Nd_tm4hPu1ZiY"
ibio = commands.Bot(intents=intents, command_prefix=commander)
ydl_opts = {'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192'}]}
stopped = list()
p_r = False
flag_repeat = False
flag_stop = True
flag_on = False
global_number = -1
now_number = 0
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


class Confirm(disnake.ui.View):
    def __int__(self):
        super().__init__(timeout=5)
        self.value = None

    @disnake.ui.button(style=disnake.ButtonStyle.green, label="ДА!")
    async def confirm(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
        await inter.message.delete()
        await inter.send('Пропускаю')
        self.value = True
        self.stop()

    @disnake.ui.button(style=disnake.ButtonStyle.red, label="НЕТ")
    async def cancel(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
        await inter.message.delete()
        await inter.send('Тогда зачем жмал?')
        self.value = False
        self.stop()


class Platform(disnake.ui.View):
    def __int__(self):
        super().__init__(timeout=5)

    @disnake.ui.button(style=disnake.ButtonStyle.gray, label="<<")
    async def last(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
        global voice, now_number, p_r, flag_repeat
        if now_number >= 1:
            now_number -= 2
            p_r = False
            flag_repeat = False
            voice.stop()
        try:
            await inter.send(None)
        except Exception:
            pass

    @disnake.ui.button(style=disnake.ButtonStyle.gray, label="⬜")
    async def pause_resume(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
        global voice, p_r
        p_r = True if not p_r else False
        if p_r:
            voice.pause()
        else:
            voice.resume()
        try:
            await inter.send(None)
        except Exception:
            pass

    @disnake.ui.button(style=disnake.ButtonStyle.gray, label='>>')
    async def next(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
        global voice, p_r, flag_repeat
        if now_number != global_number:
            p_r = False
            flag_repeat = False
            voice.stop()
        try:
            await inter.send(None)
        except Exception:
            pass

    @disnake.ui.button(style=disnake.ButtonStyle.gray, label="повторять")
    async def repeat(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
        global flag_repeat
        flag_repeat = True if not flag_repeat else False
        try:
            await inter.send(None)
        except Exception:
            pass
        self.value = True


class Dropdown(disnake.ui.StringSelect):
    def __init__(self):
        options = [disnake.SelectOption(label='1', description='one', emoji='✨'),
                   disnake.SelectOption(label='2', description='two', emoji='😊'),
                   disnake.SelectOption(label='3', description='three', emoji='🤡')]
        super().__init__(placeholder='MENU', min_values=1, max_values=1, options=options)

    async def callback(self, inter: disnake.MessageInteraction):
        await inter.response.send_message(f'DA {self.values[0]} net')


class DropDownView(disnake.ui.View):
    def __init__(self):
        super().__init__()
        self.add_item(Dropdown())


@ibio.command()
async def order(ctx):
    await ctx.send('hahahah', view=DropDownView())


def musicon(ctx, file):
    global flag_on
    try:
        voice.play(disnake.FFmpegPCMAudio(file), after=lambda e: nextmus(ctx))
        voice.source = disnake.PCMVolumeTransformer(voice.source)
        voice.source.volume = 1
    except Exception:
        ctx.message.author.voice.channel.connect(reconnect=True)
        musicon(ctx, file)
    flag_on = True


def nextmus(ctx):
    global now_number, flag_on
    if now_number <= global_number:
        if not flag_repeat and now_number < global_number:
            now_number += 1
            musicon(ctx, f'mus/mus{now_number}.mp3')
        elif flag_repeat:
            musicon(ctx, f'mus/mus{now_number}.mp3')
    print(f'INFORMATION <nextmus>: now: {now_number} global: {global_number}')
    flag_on = False


@ibio.command()
async def information(ctx):
    emb = disnake.Embed(title='Your title', color=disnake.Color.orange())
    emb.set_author(name=ibio.user.name, icon_url=ibio.user.avatar)
    emb.set_footer(text=ctx.author.name, icon_url=ctx.author.avatar)
    emb.set_image(url=ibio.user.avatar)
    emb.add_field(name='Title:', value='dadada')
    await ctx.message.delete()
    await ctx.send(embed=emb)


@ibio.command()
async def play(ctx, *url):
    global voice, ydl_opts, flag_stop, global_number, now_number
    print(f'INFORMATION <play>: now: {now_number} global: {global_number}')
    url = ' '.join(url)
    if flag_stop:
        for i in os.listdir('./mus'):
            os.remove(f'mus/{i}')
        flag_stop = False
    try:
        await ctx.message.author.voice.channel.connect(reconnect=True)
    except Exception:
        pass
    if url:
        global_number += 1
        try:
            voice = get(ibio.voice_clients, guild=ctx.guild)
            try:
                youtube_dl.YoutubeDL(ydl_opts).download([(search_youtube(url))[0][0]])
            except Exception:
                youtube_dl.YoutubeDL(ydl_opts).download([url])
            for file in os.listdir('./'):
                if file.endswith('.mp3'):
                    os.rename(file, f'mus/mus{global_number}.mp3')
            if global_number == now_number or not flag_on:
                now_number = global_number
                musicon(ctx, f'mus/mus{global_number}.mp3')
                await ctx.send('Запускаю')
            else:
                await ctx.send('Добавлено в плейлист')
        except Exception:
            await ctx.send('Неправильная ссылка')


@ibio.command()
async def panel(ctx):
    global voice
    emb = disnake.Embed(title='Панель управления', color=disnake.Color.orange())
    emb.set_author(name=ibio.user.name, icon_url=ibio.user.avatar)
    emb.set_footer(text=ctx.author.name, icon_url=ctx.author.avatar)
    emb.set_image(url=ibio.user.avatar)
    view = Platform()
    await ctx.message.delete()
    await ctx.send('ООО! вы теперь заправляете музыкой 5 минут', embed=emb, view=view)
    await view.wait()


ibio.run(TOKEN)
