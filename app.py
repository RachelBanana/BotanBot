# external libraries
import discord
from googletrans import Translator
from PIL import Image, ImageDraw, ImageFont

import pymongo
from pymongo import MongoClient

# python built-in libraries
import os
import sys
import json
import random
from datetime import datetime as dtime
from datetime import timezone

# Customizable Settings

"""For local testing purpose"""
# config_file = "config.json"
# with open(config_file) as f:
#     config_data = json.load(f)

## discord settings
token = os.getenv("TOKEN")
owner = os.getenv("OWNER")
prefix = os.getenv("PREFIX")
embed_color = int(os.getenv("EMBED_COLOR"), 16)
log_channel = 741908598870769735
pingcord = "Pingcord#3283"
translated_tweets_ch = 741945787042496614

## database settings
db_url = "mongodb+srv://{}:{}@botan.lkk4p.mongodb.net/{}?retryWrites=true&w=majority"
db_name = "botanDB"
db_user = os.getenv("DB_USER")
db_pass = os.getenv("DB_PASS")
cluster = MongoClient(db_url.format(db_user, db_pass, db_name))

db = cluster[db_name]
db_artworks = db["artworks"]

## local files settings
img_dir = "images"
save_dir = "dumps"
fonts_dir = "fonts"
voices_dir = "voices"

# Setting up server and data
client = discord.Client()
with open("help.json") as f:
    # set up help documentation
    help_doc = json.load(f)
with open("meme.json") as f:
    # set up meme data
    meme_dict = json.load(f)

# Utility Functions

## Time tools
def days_hours_minutes(td):
    return td.days, td.seconds//3600, (td.seconds//60)%60

def time_until(dt):
    today = dtime.now(tz = timezone.utc)
    return days_hours_minutes(dt - today)

## Translating tools
gtl = Translator()
def to_jap(m):
    return gtl.translate(m, dest = "ja")

def to_eng(m):
    return gtl.translate(m)

# Main Events

## on setting up, disconnecting, and errors
@client.event
async def on_ready():
    lg_ch = client.get_channel(log_channel)
    await lg_ch.send("Botan is ready!")
    print("Botan is ready!")

@client.event
async def on_connect():
    lg_ch = client.get_channel(log_channel)
    await lg_ch.send("Botan is connected to discord as {0.user}.".format(client))
    print("Botan is connected to discord as {0.user}.".format(client))

@client.event
async def on_disconnect():
    lg_ch = client.get_channel(log_channel)
    await lg_ch.send("Botan is snoozing off from discord!")
    print("Botan is snoozing off from discord!")

@client.event
async def on_error(err):
    lg_ch = client.get_channel(log_channel)
    await lg_ch.send(err)
    print(err)

## public commands
async def help_command(res, msg):
    msg = msg.strip().lower()
    msg = aliases.get(msg, msg)
    if msg in help_doc:
        cmd_doc = help_doc[msg]
        embed = discord.Embed(title = "Help Menu: '{}' Command".format(msg), description = cmd_doc["desc"])
        embed.add_field(name = "Usage", value = cmd_doc["usage"])
        if cmd_doc["alias"]:
            embed.add_field(name = "Aliases", value = ", ".join(cmd_doc["alias"]))
    else:
        embed = discord.Embed(title = "Help Menu: Available Commands", description = "\n".join(help_doc))
        embed.add_field(name = "More Help", value = "$help {command name}")
    embed.colour = embed_color
    await res.channel.send(content = None, embed = embed)

### command message commands
async def greet(res, msg):
    await res.channel.send("やほー!\nHello!")

async def doya(res, msg):
    doya_file = os.path.join(voices_dir, "doya.mp3")
    await res.channel.send("Doyaa~! doya doya doya doya~!", file = doya_file)

async def gao(res, msg):
    ri = random.randint
    m = "G" + "a" * ri(1, 7) + "o" * ri(1, 3) + "~" + "!" * ri(2, 4) + " Rawr!" * ri(0, 1)
    await res.channel.send(m if ri(0, 5) else "*Botan's too lazy to gao now*")

async def debut(res, msg):
    m = "Botan-sama's debut was on 14th August 2020, she's achieved "
    m += "a total of 134k subscribers and a live views of 110k on Youtube when her live stream ended."
    await res.channel.send(m)

async def birthday(res, msg):
    bday = dtime(2020, 9, 8, tzinfo = timezone.utc)
    days, hours, minutes = time_until(bday)
    m = "Botan-sama's birthday is on 8th of September, just {} more day{} to go!".format(days, "s" * (days>1))
    await res.channel.send(m)

### translation commands
async def translate(res, msg):
    if not msg:
        await res.channel.send("But there's nothing to translate!")
        return
    translated = to_eng(msg).text
    embed = discord.Embed(title = "Translated to English", description = translated, colour = embed_color)
    await res.channel.send(content = None, embed = embed)

async def trans_to_jap(res, msg):
    if not msg:
        await res.channel.send("Try again, but with actual words!")
        return
    translated = to_jap(msg)
    pronunciation = translated.pronunciation
    if not isinstance(pronunciation, str):
        pronunciation = ""
    m = translated.text + "\n" + pronunciation
    embed = discord.Embed(title = "Translated to Japanese", description = m, colour = embed_color)
    await res.channel.send(content = None, embed = embed)

### meme and art commands
async def meme(res, msg):
    err_msg = "Please provide a correct meme argument! (ex: $meme woke)"

    if not msg:
        await res.channel.send(err_msg)
        return

    meme_cmd, *meme_args = [m.strip() for m in msg.split("\n") if m]

    if meme_cmd not in meme_dict:
        await res.channel.send(err_msg)
        return
    
    # get meme info from local meme.json file
    meme_info = meme_dict[meme_cmd]
    file_name = meme_info["file"]
    positions = meme_info["positions"]
    wrapsize = meme_info["wrapsize"]
    meme_font = meme_info["font"]

    if len(meme_args) < len(positions):
        await res.channel.send("You need {} more arguments!".format(len(positions)-len(meme_args)))
        return
    
    meme_file = os.path.join(img_dir, file_name)
    save_file = os.path.join(save_dir, str(random.randint(1,20)) + file_name)

    try:
        img = Image.open(meme_file)
    except IOError:
        await res.channel.send("I'm sorry! Botan can't find the meme now!\nTry again later!")
        return
    
    width, height = img.size
    wraplength = wrapsize * width

    idraw = ImageDraw.Draw(img)
    font_ttf = os.path.join(fonts_dir, meme_font["name"])
    font = ImageFont.truetype(font_ttf, size = meme_font["size"])

    for pos, arg in zip(positions, meme_args):
        m, *words = arg.split(" ")
        # wrap text if longer than wraplength
        for word in words:
            if idraw.textsize(m + " " + word, font)[0] > wraplength:
                m += "\n" + word
            else:
                m += " " + word
        txt_w, txt_h = idraw.textsize(m, font)
        idraw.text(
            (width*pos[0]-txt_w/2, height*pos[1]-txt_h/2), 
            m, 
            font = font, 
            fill = tuple(meme_font["fill"])
        )
    img.save(save_file)
    await res.channel.send(file = discord.File(save_file))

async def botan_art(res, msg):
    artwork_cursor = db_artworks.aggregate([{"$sample": {"size": 1}}])
    for a in artwork_cursor:
        await res.channel.send(a["url"])

## admin commands
async def post(res, msg):
    m = msg.split("\n")
    if len(m) < 3:
        await res.channel.send("Need more arguments!")
        return
    channel = discord.utils.get(res.guild.text_channels, name= m[0].strip()) 
    embed = discord.Embed(title = m[1], description = "\n".join(m[2:]), colour = embed_color)
    if res.attachments:
        embed.set_image(url = res.attachments[0].url)
    await channel.send(content = None , embed = embed)

async def read(res, msg):
    channel = res.channel
    if msg:
        msg = msg.strip()
        channel = discord.utils.get(res.guild.text_channels, name = msg)

    messages = await res.channel.history(limit = 2).flatten()
    for m in messages:
        for embed in m.embeds:
            embed.title = to_eng(embed.title).text
            embed.description = to_eng(embed.description).text
            await channel.send(content = None, embed = embed)

### database manipulation
async def add_art(res, msg):
    if db_artworks.find_one({"url": msg}):
        await res.channel.send("There's already an existing art with the same url!")
        return
    db_artworks.insert_one({"url": msg})
    await res.channel.send("Added one new artwork to database!")

## hidden developer commands


## command names
aliases = {
    "hi": "greet",
    "hello": "greet",
    "bday": "birthday",
    "trans": "translate",
    "jp": "japanese",
    "addart": "add_art"
}


commands = {
    "help": help_command,
    "greet": greet,
    "doya": doya,
    "gao": gao,
    "debut": debut,
    "birthday": birthday,
    "translate": translate,
    "japanese": trans_to_jap,
    "meme": meme,
    "botan": botan_art
}

admin_commands = {
    "post": post,
    "read": read,
    "add_art": add_art
}

## on messaging
@client.event
async def on_message(res):
    # read twitter tweets from botan
    if str(res.author) == pingcord:
        channel = client.get_channel(translated_tweets_ch)
        for embed in res.embeds:
            embed.title = to_eng(embed.title).text
            embed.description = to_eng(embed.description).text
            await channel.send(content = None, embed = embed)


    # checks if message needs attention (not bot, has prefix)
    if res.author == client.user or not res.content.startswith(prefix):
        return

    # get the command and message text
    cmd, *msg = res.content[len(prefix):].split(" ", 1)
    cmd = cmd.strip().lower()
    msg = msg[0] if msg else ""

    # change any command alias to original command name
    cmd = aliases.get(cmd, cmd)

    # if public command exists, perform action
    action = commands.get(cmd, None)
    if action:
        await action(res, msg)
    
    # check for permission and if admin command exists, perform action
    if not res.author.guild_permissions.administrator:
        return
    action = admin_commands.get(cmd, None)
    if action:
        await action(res, msg)

client.run(token)

