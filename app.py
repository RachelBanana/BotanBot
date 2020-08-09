# external libraries
import discord
from googletrans import Translator

# python built-in libraries
import os
import json
import random
from datetime import datetime as dtime
from datetime import timezone

# Customizable Settings

"""For local testing purpose"""
# config_file = "config.json"
# with open(config_file) as f:
#     config_data = json.load(f)

token = os.getenv("TOKEN")
owner = os.getenv("OWNER")
prefix = os.getenv("PREFIX")
embed_color = int(os.getenv("EMBED_COLOR"), 16)
to_bed_channel = 740894878019616842
log_channel = 741908598870769735

# Setting up server
client = discord.Client()
lg_ch = None

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

## on setting up and disconnecting
@client.event
async def on_ready():
    await lg_ch.send("Botan is ready!")
    print("Botan is ready!")

@client.event
async def on_connect():
    lg_ch = client.get_channel(log_channel)
    await lg_ch.send("Botan is connected to discord as {0.user}.".format(client))
    print("Botan is connected to discord as {0.user}.".format(client))

@client.event
async def on_disconnect():
    await lg_ch.send("Botan is snoozing off from discord!")
    print("Botan is snoozing off from discord!")

@client.event
async def on_error(err):
    await lg_ch.send(err)

## public commands

async def greet(res, msg):
    await res.channel.send("Hello!")

async def gao(res, msg):
    ri = random.randint
    m = "G" + "a" * ri(1, 7) + "o" * ri(1, 3) + "~" + "!" * ri(2, 4) + " Rawr!" * ri(0, 1)
    await res.channel.send(m if ri(0, 5) else "*Botan's too lazy to gao now*")

async def debut(res, msg):
    debut_day = dtime(2020, 8, 14, 12, 0, 0, 0, timezone.utc)
    days, hours, minutes = time_until(debut_day)
    m = "{} day{}, {} hour{}, and {} minute{} left until Botan-sama's Debut Stream!".format(
        days,
        "s" * (days > 1),
        hours,
        "s" * (hours > 1),
        minutes,
        "s" * (minutes > 1)
    )
    await res.channel.send(m)

async def birthday(res, msg):
    bday = dtime(2020, 9, 8, tzinfo = timezone.utc)
    days, hours, minutes = time_until(bday)
    m = "Botan-sama's birthday is on 8th of September, just {} more day {} to go!".format(days, "s" * (days>1))
    await res.channel.send(m)

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

## admin commands
async def post(res, msg):
    m = msg.split("\n")
    if len(m) < 3:
        await message.channel.send("Need more arguments!")
        return
    channel = discord.utils.get(res.guild.text_channels, name= m[0].strip()) 
    embed = discord.Embed(title = m[1], description = "\n".join(m[2:]), colour = embed_color)
    await channel.send(content = None , embed = embed)

## hidden developer commands
async def to_bed(res, msg):
    if str(res.author) != owner:
        return
    channel = client.get_channel(to_bed_channel)
    await channel.send("*Botan will sleep now*\nOyasuminasai!")

## command names
commands = {
    "hello": greet,
    "hi": greet,
    "gao": gao,
    "debut": debut,
    "bday": birthday,
    "birthday": birthday,
    "translate": translate,
    "trans": translate,
    "jp": trans_to_jap,
    "gotobed": to_bed
}

admin_commands = {
    "post": post
}

## on messaging
@client.event
async def on_message(res):
    # checks if message needs attention (not bot, has prefix)
    if res.author == client.user or not res.content.startswith(prefix):
        return

    # get the command and message text
    cmd, *msg = res.content[len(prefix):].split(" ", 1)
    cmd = cmd.strip().lower()
    msg = msg[0] if msg else ""

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

