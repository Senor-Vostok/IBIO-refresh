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
musics = list()
commander = '*'
intents = disnake.Intents.all()
TOKEN = ""
ibio = commands.Bot(intents=intents, command_prefix=commander)
ydl_opts = {'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
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


class Platform(disnake.ui.View):
    def __int__(self):
        super().__init__()

    @disnake.ui.button(style=disnake.ButtonStyle.gray, label="<<")
    async def last(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
        global vo, now_number, p_r, flag_repeat
        if now_number >= 1:
            now_number -= 2
            p_r = False
            flag_repeat = False
            vo.stop()
        await inter.send('Назад', ephemeral=True)

    @disnake.ui.button(style=disnake.ButtonStyle.gray, label="||")
    async def pause_resume(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
        global vo, p_r
        p_r = True if not p_r else False
        if p_r:
            vo.pause()
        else:
            vo.resume()
        await inter.send('пауза', ephemeral=True)

    @disnake.ui.button(style=disnake.ButtonStyle.gray, label='>>')
    async def next(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
        global vo, p_r, flag_repeat
        if now_number != global_number:
            p_r = False
            flag_repeat = False
            vo.stop()
        await inter.send('Вперёд', ephemeral=True)

    @disnake.ui.button(style=disnake.ButtonStyle.gray, label="повторять")
    async def repeat(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
        global flag_repeat
        flag_repeat = True if not flag_repeat else False
        if flag_repeat:
            await inter.send('теперь ваш трек будет повторяться', ephemeral=True)
        else:
            await inter.send('снимаю повторение трека', ephemeral=True)
        self.value = True

    @disnake.ui.button(style=disnake.ButtonStyle.red, label='❤')
    async def like(self, button: disnake.ui.Button, ctx: disnake.CommandInteraction):
        await ctx.send(musics[now_number], ephemeral=True)
        fib = os.listdir('./data')
        if f'{ctx.author.id}.txt' in fib:
            with open(f'data/{ctx.author.id}.txt', mode='rt', encoding='utf-8') as file:
                file = (file.read()).split('\n')
                if musics[now_number] not in file:
                    with open(f'data/{ctx.author.id}.txt', mode='a', encoding='utf-8') as file:
                        file.write(f'\n{musics[now_number]}')
        else:
            with open(f'data/{ctx.author.id}.txt', mode='w', encoding='utf-8') as file:
                file.write(f'{musics[now_number]}')


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


def musicon(ctx, file):
    global flag_on
    vo.play(disnake.FFmpegPCMAudio(file), after=lambda e: nextmus(ctx))
    vo.source = disnake.PCMVolumeTransformer(vo.source)
    vo.source.volume = 1
    flag_on = True


def nextmus(ctx):
    global now_number, flag_on
    flag_on = False
    if now_number <= global_number:
        if not flag_repeat and now_number < global_number:
            now_number += 1
            musicon(ctx, f'mus/mus{now_number}.mp3')
        elif flag_repeat:
            musicon(ctx, f'mus/mus{now_number}.mp3')
    print(f'INFORMATION <nextmus>: now: {now_number} global: {global_number}')


@ibio.command()
async def information(ctx):
    emb = disnake.Embed(title='Your title', color=disnake.Color.from_rgb(57, 47, 44))
    emb.set_author(name=ibio.user.name, icon_url=ibio.user.avatar)
    emb.set_image(url=ibio.user.avatar)
    emb.add_field(name='Title:', value='dadada')
    await ctx.message.delete()
    await ctx.send(embed=emb)


@ibio.slash_command(name='play', description='запускает вашу музыку')
async def play(ctx: disnake.CommandInteraction, url):
    global vo, ydl_opts, flag_stop, global_number, now_number, p_r
    print(url)
    if flag_stop:
        for i in os.listdir('./mus'):
            os.remove(f'mus/{i}')
        flag_stop = False
    if url:
        vo = get(ibio.voice_clients, guild=ctx.guild)
        chanel = ctx.author.voice.channel
        if vo and vo.is_connected():
            await vo.move_to(chanel)
        else:
            vo = await chanel.connect()
        print(f'INFORMATION <play>: now: {now_number} global: {global_number}')
        await ctx.send('подождите пару секунд', ephemeral=True)
        if 'https://' in url:
            youtube_dl.YoutubeDL(ydl_opts).download([url])
        else:
            youtube_dl.YoutubeDL(ydl_opts).download([(search_youtube(url))[0][0]])
        for file in os.listdir('./'):
            if file.endswith('.opus'):
                global_number += 1
                musics.append((((file.split('.opus'))[0]).split('['))[0])
                os.rename(file, f'mus/mus{global_number}.mp3')
        if global_number == now_number or not flag_on:
            p_r = False
            now_number = global_number
            musicon(ctx, f'mus/mus{global_number}.mp3')
        emb = disnake.Embed(title='Плейлист', color=disnake.Color.from_rgb(250, 235, 214))
        emb.set_author(name=ctx.author.name, icon_url=ctx.author.avatar)
        output = []
        ch = len(musics) - 5 if len(musics) >= 5 else 0
        for i in range(ch, len(musics)):
            if i == now_number:
                output.append(f'{i + 1}.**{musics[i]}** <-- сейчас играет')
            else:
                output.append(f'{i + 1}. {musics[i]}')
        output = '\n'.join(output)
        emb.add_field(name='', value=output)
        await ctx.channel.send(embed=emb)


@ibio.slash_command(name='panel', description='открывает панель управления ботом')
async def panel(ctx: disnake.CommandInteraction):
    global vo
    emb = disnake.Embed(title='Панель управления', color=disnake.Color.from_rgb(57, 47, 44))
    emb.set_author(name=ibio.user.name, icon_url=ibio.user.avatar)
    emb.set_footer(text=ctx.author.name, icon_url=ctx.author.avatar)
    emb.set_image(url=ibio.user.avatar)
    view = Platform()
    await ctx.send(embed=emb, view=view)
    await view.wait()


ibio.run(TOKEN)
