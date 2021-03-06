# external libraries
import discord
from googletrans import Translator
from PIL import Image, ImageDraw, ImageFont, ImageEnhance, ImageOps
import googleapiclient.discovery
import requests
# import pytesseract as Tess
import tesserocr

import pymongo
from pymongo import MongoClient

# python built-in libraries
import sys
import os
import re
import json
import random
import asyncio
from datetime import datetime as dtime, tzinfo
from datetime import timezone, timedelta
from collections import deque
from functools import partial

"""For local testing purpose"""
# config_file = "config.json"
# with open(config_file) as f:
#     config_data = json.load(f)


# Setting up server and data
client = discord.Client()

# Customizable Settings
## discord settings
token = os.getenv("TOKEN")
owner = os.getenv("OWNER")
prefix = os.getenv("PREFIX")
embed_color = int(os.getenv("EMBED_COLOR"), 16)
pingcord = "Pingcord#3283"

## TESSDATA_PREFIX is needed as environment variable
# ./.apt/usr/share/tesseract-ocr/4.00/tessdata
# /app/.apt/usr/share/tesseract-ocr/4.00/tessdata

## local directories
data_dir = "data"
save_dir = "dumps"
fonts_dir = "fonts"
img_dir = "images"
voices_dir = "voices"

## set up data
d = {}
for f_name in os.listdir(data_dir):
    if not f_name.endswith(".json"):
        continue
    f_path = os.path.join(data_dir, f_name)
    with open(f_path) as f:
        # example: d["blacklist"] = {blacklist data}
        d[f_name.split(".")[0]] = json.load(f)

## database settings
db_url = "mongodb+srv://{}:{}@botan.lkk4p.mongodb.net/{}?retryWrites=true&w=majority"
db_name = "botanDB"
db_user = os.getenv("DB_USER")
db_pass = os.getenv("DB_PASS")
cluster = MongoClient(db_url.format(db_user, db_pass, db_name))
db = cluster[db_name]

### preload counter for efficiency
counter = db["settings"].find_one({"name": "counter"})

## youtube api settings
yt_key = os.getenv("YT_KEY")
botan_ch_id = os.getenv("BOTAN_CH_ID")
api_service_name = "youtube"
api_version = "v3"

youtube = googleapiclient.discovery.build(
    api_service_name, api_version, developerKey = yt_key)

# Temporary storage for artworks (only urls)
temp_artwork_cursor = db["artworks"].aggregate([{"$sample": {"size": 30}}])
temp_art_deque = deque()
temp_art_set = set()
for art in temp_artwork_cursor:
    temp_art_deque.append(art["url"])
    temp_art_set.add(art["url"])

# Temporary storage for trivia
temp_trivia_cursor = db["trivia"].aggregate([{"$sample": {"size": 10}}])
temp_trivia_deque = deque()
temp_trivia_set = set()
for trivia in temp_trivia_cursor:
    temp_trivia_deque.append(trivia)
    temp_trivia_set.add(trivia["id"])

# Utility Functions
def is_integer(s):
    # check if a string is an integer (includes negative integers)
    try: 
        int(s)
        return True
    except ValueError:
        return False

def n_to_unit(n, unit):
    return (str(n) + " " + unit + "s"*(n>1) + " ")*(n>0)

def to_raw_text(msg):
    # given a message with mentions (users, channels) and emotes, convert to raw text
    def repl_username(m):
        m = m.group(1)
        return client.get_user(int(m)).name
    def repl_channel(m):
        m = m.group(1)
        return client.get_channel(int(m)).name
    msg = re.sub(r"<@!(\d+)>", repl_username, msg)
    msg = re.sub(r"<:\w+:\d+>", "", msg)
    msg = re.sub(r"<#(\d+)>", repl_channel, msg)
    return msg

## convert emoji to id
def emoji_to_id(emoji_str):
    id_match = re.match(r"<a?:\w+:(\d+)>", emoji_str)
    if not id_match:
        raise ValueError
    return int(id_match.group(1))

## Time tools
months = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]
date_patterns = [
    "(" + "|".join(months) + ") +\d{1,2},? +\d{4}", # jan 20, 2021
    "\d{1,2} +(" + "|".join(months) + ") +\d{4}", # 20 jan 2021
]
date_formats = [
    "%b %d, %Y",
    "%d %b %Y"
]

def days_hours_minutes(td):
    return td.days, td.seconds//3600, (td.seconds//60)%60

def time_until(dt):
    today = dtime.now(tz = timezone.utc)
    return days_hours_minutes(dt - today)

def time_to_string(d, h, m):
    arr = [s for s in (n_to_unit(d, "day"), n_to_unit(h, "hour"), n_to_unit(m, "minute")) if s]
    if len(arr) == 3:
        msg = "{}, {}, and {}"
    elif len(arr) == 2:
        msg = "{} and {}"
    elif len(arr) == 1:
        msg = "{}"
    else:
        return ""
    return msg.format(*arr)

def date_from_txt(s):
    # given a string, extract and return a datetime object
    s = s.lower()
    for pattern, date_format in zip(date_patterns, date_formats):
        match = re.search(pattern, s)
        if match:
            extracted_time = dtime.strptime(match.group(), date_format).replace(tzinfo = timezone.utc)
            return extracted_time

## Translating tools
# fix: https://stackoverflow.com/questions/52455774/googletrans-stopped-working-with-error-nonetype-object-has-no-attribute-group

gtl = Translator()
def to_jap(m):
    return gtl.translate(m, dest = "ja")

def to_eng(m):
    return gtl.translate(m, dest = "en")

## internal discord tools
async def _dm_member(member_id, message, embed = False, attachment_url = None):
    # dm a member, and returns a message if error occurs

    # if member_id is not integer or a string that represents integer, return error message
    if not is_integer(member_id):
        return "Please provide a valid user id!"
    target_user = client.get_user(int(member_id))

    if embed:
        # split message into title and description
        message = message.split("\n")
        if len(message) < 2:
            return "need at least 2 arguments for embed messages!"
        embed = discord.Embed(title = message[0], description = "\n".join(message[1:]), colour = embed_color)

        if attachment_url:
            embed.set_image(url = attachment_url)
        await target_user.send(content = None, embed = embed)
    else:
        await target_user.send(message)
    return None

## Membership tools
async def _check_membership_dates(res = None, msg = None):
    # Performs a mass check on membership dates and delete expired membership with a default message
    # Returns an expired_membership list {id, last_membership}

    # Get all data from bodans
    expired_memberships = []
    expired_start_date = dtime.now(tz = timezone.utc) - timedelta(days = 31)

    message_title = "Zoopass Membership Expired"
    message_desc = "Your access to our Botan's members-only channel has just expired!"
    message_desc += "\nYou may renew your membership by sending another updated verification photo using the ``verify`` command."
    message_desc += " Thank you so much for your cotinued support of our precious lioness!"
    message_image = "https://media.discordapp.net/attachments/735145401094504538/798419209112518687/botan_cat.jpg"

    for bodan in db["bodans"].find():
        # For each bodan, if membership date ended (31 days) 30 days with one day buffer
        if (not bodan["last_membership"]) or bodan["last_membership"].replace(tzinfo = timezone.utc) < expired_start_date:
            # Add to delete list
            expired_memberships.append(bodan)

            # Delete from database
            db["bodans"].delete_one(bodan)

            # Remove zoopass role from user
            botan_guild = client.get_guild(d["discord_ids"]["guild"])
            target_member = botan_guild.get_member(bodan["id"])

            zoopass_role_id = d["discord_ids"]["zoopass_role"]
            zoopass_role = botan_guild.get_role(zoopass_role_id)

            await target_member.remove_roles(zoopass_role)

            # dm expired membership
            await _dm_member(bodan["id"], "{}\n{}".format(message_title, message_desc), embed = True, attachment_url = message_image)

    # Returns expired_memberships list
    return expired_memberships

## Live Streaming tools
"""stream's data template
    "id": vid id,
    "title": vid title
    "status": "justlive", "live", "upcoming", "completed"
    "live_msg"
    "scheduled_start_time"
    "actual_start_time"
    "actual_end_time"
    "tag_count": 1
    "tags": {
        "0": {
            "author_id": author's id,
            "timestamp": datetime,
            "seconds": int
            "text": "loren itsum"
        },
        ...
    }
"""
async def process_tags(vid_id, offset = 13, overwrite = False):
    botan_guild = client.get_guild(d["discord_ids"]["guild"])
    vid_data = db["streams"].find_one({"id": vid_id})
    lg_ch = client.get_channel(d["discord_ids"]["log"])

    # if tag_count doesn't exist or is zero, return
    if not vid_data.get("tag_count"):
        return
    
    # convert tags to list (important: items in tags mutating will cause tags_dict to mutate too)
    tags_dict = vid_data["tags"]
    tags = [tags_dict[str(k)] for k in range(len(tags_dict))]

    if len(tags) == 0:
        return

    # If seconds don't exist or overwrite is true, use timestamp to calculate all seconds, store back into db["streams"]
    if (not tags[0].get("seconds")) or overwrite:
        actual_start_time = vid_data["actual_start_time"].replace(tzinfo = timezone.utc)
        for tag in tags:
            timestamp = tag["timestamp"].replace(tzinfo = timezone.utc)
            tag["seconds"] = max(int((timestamp - actual_start_time).total_seconds()) - offset, 0)
        db["streams"].update_one({"id": vid_id}, {"$set": {"tags": tags_dict}})

    # write all tags into separate messages in a list
    msg_list = []
    for tag in tags:
        author = botan_guild.get_member(tag["author_id"])
        display_name = booster_nickname(author)
        display_name = "<:Booster:751174312018575442> {}".format(display_name) if is_booster(author) else display_name

        minutes, seconds = divmod(tag["seconds"], 60)
        hours, minutes = divmod(minutes, 60)

        if hours:
            display_time = "{}:{:02d}:{:02d}".format(hours, minutes, seconds)
        else:
            display_time = "{}:{:02d}".format(minutes, seconds)

        vid_url = "https://youtu.be/{}?t={}".format(vid_id, tag["seconds"])
        msg = tag["text"]

        msg_list.append("{}\n[{}]({}) {}".format(display_name, display_time, vid_url, msg))

    # while there are still items in the list, make a new embed with a title
    title = vid_data["title"]
    embed_list = []
    i = 0
    while i < len(msg_list):
        start_index = i
        chars = len(msg_list[i])
        i+=1

        # while there are still characters left, add messages to embed
        while i < len(msg_list) and chars + 2 + len(msg_list[i]) <= 2000:
            chars += 2 + len(msg_list[i])
            i += 1
        
        m = "\n\n".join(msg_list[start_index:i])
        embed = discord.Embed(title = title, description = m, colour = embed_color)
        embed_list.append(embed)
    await lg_ch.send("here")
    # if msg_ids exist, edit messages, else send messages !!! wip
    ar_ch = client.get_channel(d["discord_ids"]["archive_stream"])
    await ar_ch.send("https://www.youtube.com/watch?v=" + vid_id)
    for embed in embed_list:
        await ar_ch.send(content = None, embed = embed)

## Art Manipulation tools
def add_corners(im, rad):
    circle = Image.new('L', (rad * 2, rad * 2), 0)
    draw = ImageDraw.Draw(circle)
    draw.ellipse((0, 0, rad * 2, rad * 2), fill=255)
    alpha = Image.new('L', im.size, 255)
    w, h = im.size
    alpha.paste(circle.crop((0, 0, rad, rad)), (0, 0))
    alpha.paste(circle.crop((0, rad, rad, rad * 2)), (0, h - rad))
    alpha.paste(circle.crop((rad, 0, rad * 2, rad)), (w - rad, 0))
    alpha.paste(circle.crop((rad, rad, rad * 2, rad * 2)), (w - rad, h - rad))
    im.putalpha(alpha)
    return im

### Tesseract text detection
async def _detect_image_text(img_url):
    # Uses Tesseract to detect text from url img 
    # return tuple of two possible text: normal and inverted

    # Set partial function for image_to_text
    tess_path = r"/app/.apt/usr/share/tesseract-ocr/4.00/tessdata"
    img_to_txt = partial(tesserocr.image_to_text, path = tess_path)

    # Get image from url
    img_response = requests.get(img_url, stream=True)
    img_response.raw.decode_content = True
    img = Image.open(img_response.raw)
    img.load()

    # sharpen image
    enhancer = ImageEnhance.Sharpness(img)
    factor = 3
    img = enhancer.enhance(factor)

    # remove alpha channel and invert image
    if img.mode == "RGBA":
        background = Image.new("RGB", img.size, (255, 255, 255))
        background.paste(img, mask=img.split()[3] if len(img.split()) >= 4 else None) # 3 is the alpha channel
        img = background

    inverted_img = ImageOps.invert(img)

    # get text (run as coroutine to not block the event loop)
    text = await client.loop.run_in_executor(None, img_to_txt, img)

    # get inverted text (run as coroutine to not block the event loop)
    inverted_text = await client.loop.run_in_executor(None, img_to_txt, inverted_img)
        
    return (text, inverted_text)

## Nsfw utility tools
def is_horny(user):
    member = db["members"].find_one({"id": user.id})
    return member and member.get("nsfw", None) and member["nsfw"].get("is_horny", None)

## Boosters utility tools
def is_booster(user):
    # checks if user is a booster and returns the booster's data
    return db["boosters"].find_one({"id": user.id})

def booster_nickname(user):
    # if user is a booster and has a booster nickname, return nickname. 
    booster = db["boosters"].find_one({"id": user.id})
    if booster and booster["nickname"]:
        return booster["nickname"]
    # else return guild nickname or user's name depending on the class type
    return user.nick if isinstance(user, discord.Member) and user.nick else user.name

## Youtube Members utility tools

# Main Events

## on setting up, disconnecting, and errors
@client.event
async def on_ready():
    lg_ch = client.get_channel(d["discord_ids"]["log"])
    await lg_ch.send("Botan is ready!")
    print("Botan is ready!")

@client.event
async def on_connect():
    print("Botan is connected to discord as {0.user}.".format(client))

@client.event
async def on_disconnect():
    lg_ch = client.get_channel(d["discord_ids"]["log"])
    await lg_ch.send("Botan is snoozing off from discord!")
    print("Botan is snoozing off from discord!")

# @client.event
# async def on_error(err, *args):
#     lg_ch = client.get_channel(d["discord_ids"]["log"])
#     await lg_ch.send(err)
#     print(err)
#     print(sys.exc_info())

## public commands
async def help_command(res, msg):
    msg = msg.strip().lower()
    msg = aliases.get(msg, msg)
    if msg in d["help"]:
        cmd_doc = d["help"][msg]
        embed = discord.Embed(title = "Help Menu: '{}' Command".format(msg), description = cmd_doc["desc"])
        for field in cmd_doc["extra_fields"]:
            field_msg = "\n".join(field["value"]) if isinstance(field["value"], list) else field["value"]
            embed.add_field(name = field["name"], value = field_msg, inline = False)
        embed.add_field(name = "Usage", value = cmd_doc["usage"])
        if cmd_doc["alias"]:
            embed.add_field(name = "Aliases", value = ", ".join(cmd_doc["alias"]))
    else:
        embed = discord.Embed(title = "Help Menu: Available Commands", description = "\n".join(d["help"]))
        embed.add_field(name = "More Help", value = "$help {command name}")
    embed.colour = embed_color
    await res.channel.send(content = None, embed = embed)

### command message commands
async def greet(res, msg):
    nickname = booster_nickname(res.mentions[0] if msg else res.author)
    m = "La Lion~! La Lioon~! Nene ni Gao Gao~ La Lion~!\nOhayou-gozaimasu, {}.".format(nickname)
    await res.channel.send(m)

async def voice(res, msg):
    if not msg:
        msg = random.choice(list(d["voices"]))
    v_file_name = random.choice(d["voices"][msg]["clips"])
    voice_file = os.path.join(voices_dir, v_file_name)
    await res.channel.send(d["voices"][msg]["quote"], file = discord.File(voice_file))

async def score_me(res, msg):
    edit_msg = await res.channel.send(":100:")
    total = 1
    for i in range(2, random.randint(2, 6)):
        total += i
        await asyncio.sleep(0.3)
        await edit_msg.edit(content = ":100: " * total)
    await asyncio.sleep(0.3)
    await edit_msg.edit(content = "[RESTRICTED]")

async def sleepy(res, msg):
    counter["sleepy"] += 1
    sleep_count = counter["sleepy"]
    await res.channel.send("<:BotanSleepy:742049916117057656>")
    await res.channel.send("{} Sleepy Bodans sleeping on the floor.".format(sleep_count))
    db["settings"].update_one({"name": "counter"}, {"$set": {"sleepy": counter["sleepy"]}})

async def shishilamy(res, msg):
    counter["shishilamy"] += 1
    sl_count = counter["shishilamy"]
    await res.channel.send("<:BotanLamyNY1:798476668733358110><:BotanLamyNY2:798476692795817994>")
    await res.channel.send("{} Bodans on the ShishiLamy Teetee ship!".format(sl_count))
    db["settings"].update_one({"name": "counter"}, {"$set": {"shishilamy": counter["shishilamy"]}})

async def poi(res, msg):
    botan_nades = [
        "<:BotanNade:766659876532256788>",
        "<:BotanNade2:797743911421870090>",
        "<:BotanNade3:797743927733387304>",
        "<:BotanNade4:797743939615719435>"
    ]
    botan_poi = "<:BotanPoi:766659519950225448>"
    blank = "<:Blank:797737605285281792>"
    edit_msg = await res.channel.send(botan_poi)
    await asyncio.sleep(0.6)
    total = 0
    for i in range(4):
        total += i
        await asyncio.sleep(0.2)
        await edit_msg.edit(content = blank * total + botan_nades[i])
    await asyncio.sleep(0.6)
    await edit_msg.edit(content = ":boom:" * 7)

async def gao(res, msg):
    ri = random.randint
    m = "G" + "a" * ri(1, 7) + "o" * ri(1, 3) + "~" + "!" * ri(2, 4) + " Rawr!" * ri(0, 1)
    await res.channel.send(m if ri(0, 5) else "*Botan's too lazy to gao now*")

async def random_choice(res, msg):
    # returns if msg is empty
    if not msg:
        m = "Sorry {}, your argument needs to be at least one choice!"
        await res.channel.send(m.format(booster_nickname(res.author)))
        return
    
    # splits msg according to commas and new lines, and strip extra spaces
    choices = [i.strip() for i in re.split(",|\n", msg) if i]
    await res.channel.send(random.choice(choices))

async def debut(res, msg):
    m = "Botan-sama's debut was on 14th August 2020, she's achieved "
    m += "a total of 134k subscribers and a live views of 110k on Youtube when her live stream ended."
    await res.channel.send(m)

async def birthday(res, msg):
    bday = dtime(2021, 9, 8, tzinfo = timezone.utc)
    days, hours, minutes = time_until(bday)
    m = "Botan-sama's birthday is on 8th of September, just {} more day{} to go!".format(days, "s" * (days>1))
    await res.channel.send(m)

async def botan_trivia(res, msg):
    # pop a trivia from temp
    trivia = temp_trivia_deque.popleft()
    temp_trivia_set.remove(trivia["id"])
    embed = discord.Embed(title = "Do You Know?", description = trivia["desc"], colour = embed_color)
    embed.set_footer(text = "#{}".format(trivia["id"]))
    await res.channel.send(content = None, embed = embed)

    # get a new trivia from database to add to temp
    new_trivia = list(db["trivia"].aggregate([{"$sample": {"size": 1}}]))[0]
    while new_trivia["id"] in temp_trivia_set:
        new_trivia = list(db["trivia"].aggregate([{"$sample": {"size": 1}}]))[0]
    temp_trivia_set.add(new_trivia["id"])
    temp_trivia_deque.append(new_trivia)

### Youtube data commands
"""stream's data template
    "id": vid id,
    "title": vid title
    "status": "justlive", "live", "upcoming", "completed"
    "live_msg"
    "scheduled_start_time"
    "actual_start_time"
    "actual_end_time"
    "tag_count": 1
    "tags": {
        "0": {
            "author_id": author's id,
            "timestamp": datetime,
            "seconds": int
            "text": "loren itsum"
        },
        ...
    }
"""
async def vid_tag(res, msg):
    # check if channel is live stream channel
    if res.channel.id != d["discord_ids"]["live_stream"]:
        await res.channel.send("This command is only available in <#740888892772712518>!")
        return

    # check if there is a livestream
    vid_data = db["streams"].find_one({"status": "live"})
    if not vid_data:
        await res.channel.send("There are no ongoing live streams now!")
        return
    
    # check if msg empty
    if not msg:
        await res.channel.send("You need to include a comment after the tag command!")
        return
    
    # return if too many characters
    chr_limit = 400 if is_booster(res.author) else 200
    if len(msg) > chr_limit:
        await res.channel.send("You have exceeded your character limit of {}! Please shorten your message.".format(chr_limit))
        
    # check if tags exist in vid data, if not, create it
    if not vid_data.get("tags"):
        vid_data["tags"] = {}
        vid_data["tag_count"] = 0

    # insert text, timestamp and author's id
    vid_data["tags"][str(vid_data["tag_count"])] = {
        "author_id": res.author.id,
        "timestamp": dtime.now(tz = timezone.utc),
        "text": msg
    }

    # increment tag count
    vid_data["tag_count"] += 1

    # update data
    db["streams"].update_one({"id": vid_data["id"]}, {"$set": {"tags": vid_data["tags"], "tag_count": vid_data["tag_count"]}})

    # add reaction to acknowledge tag
    await res.add_reaction("\U0001F4AF")

async def subscribers(res, msg):
    # Check which Vtuber channel to search for
    msg = msg.strip().lower()
    ch_id = botan_ch_id
    vtuber_name = "Shishiro Botan"

    if msg in d["vtubers"]:
        ch_id = d["vtubers"][msg]["ch_id"]
        vtuber_name = msg.capitalize()

    # Look for channel
    request = youtube.channels().list(
        part = "statistics",
        id = ch_id
    )
    yt_stats = request.execute()["items"][0]["statistics"]
    m = "{} currently has {:,} subscribers and a total of {:,} views on her YouTube channel."
    await res.channel.send(m.format(vtuber_name, int(yt_stats["subscriberCount"]), int(yt_stats["viewCount"])))

async def live_streams(res, msg):
    # Look for live streams (only return one)
    live_vid = db["streams"].find_one({
        "$or": [
            {"status": "justlive"},
            {"status": "live"}
        ]
    })
    if live_vid:
        vid_id = live_vid["id"]
        vid_url = "https://www.youtube.com/watch?v=" + vid_id
        if random.randint(0, 1):
            m = "Omg Botan-sama is live now!! What are you doing here??! Get over to the following link to send your red SC!\n{}"
        else:
            m = "Sorry, I am too busy watching Botan-sama's live stream now. Find another free bot.\n{}"
        await res.channel.send(m.format(vid_url))
        return
    
    # Look for upcoming streams if there's no live streams
    upcoming_vids = db["streams"].find({"status": "upcoming"})
    
    flag = False

    for vid in upcoming_vids:
        vid_id = vid["id"]
        vid_url = "https://www.youtube.com/watch?v=" + vid_id

        scheduled_start_time = vid["scheduled_start_time"].replace(tzinfo = timezone.utc)
        if dtime.now(tz=timezone.utc) > scheduled_start_time:
            continue
        timeleft = time_to_string(*time_until(scheduled_start_time))
        await res.channel.send("{} left until Botan sama's next stream! Link here:\n{}".format(timeleft, vid_url))
        flag = True

    # Return if there is no upcoming stream
    if not flag:
        await res.channel.send("Sorry, Botan-sama doesn't have any scheduled streams now!")

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

async def superchat(res, msg):
    # error message if there is no msg
    err_msg = "Please provide a correct superchat argument! For example:\n$sc 10000\nsimping for botan"
    if not msg:
        await res.channel.send(err_msg)
        return

    # split msg to money amount and text
    amount, *msg_args = [m.strip() for m in msg.split("\n") if m]

    # check if amount is a number
    if not amount.replace('.','',1).isdigit():
        await res.channel.send(err_msg)
        return
    
    # convert amount to int/float and round off if float
    if "." in amount:
        amount = round(float(amount), 2)
        format_string = "JP¥{:,.2f}".format(amount).rstrip("0").rstrip(".")
    else:
        amount = int(amount)
        format_string = "JP¥{:,}".format(amount)

    # determine sc backgroudn base on color
    black = (0, 0, 0, 255)
    white = (255, 255, 255, 255)
    if amount >= 10000:
        # red D00000 E62117 10000-50000yen
        sc_file_name = "red_sc.png"
        fill = white
    elif amount >= 5000:
        # magenta C2185B E91E63 5000-9999yen
        sc_file_name = "mag_sc.png"
        fill = white
    elif amount >= 2000:
        # orange E65100 F57C00 2000-4999yen
        sc_file_name = "org_sc.png"
        fill = white
    elif amount >= 1000:
        # yellow FFB300 FFCA28 1000-1999yen
        sc_file_name = "yellow_sc.png"
        fill = black
    elif amount >= 500:
        # green 00BFA5 1DE9B6 500-999yen
        sc_file_name = "green_sc.png"
        fill = black
    elif amount >= 200:
        # light blue 00B8D4 00E5FF 200-499yen
        sc_file_name = "lightblue_sc.png"
        fill = black
    elif amount >= 100:
        # blue 1565C0 100-199yen
        sc_file_name = "blue.png"
        fill = white
        msg_args = []
    else:
        # pleb
        await res.channel.send("You need more money to send a superchat!")
        return

    # format amount and msg
    amount = format_string
    msg = to_raw_text("\n".join(msg_args))

    # get avatar and resize 
    avatar_url = res.author.avatar_url
    av_img = Image.open(requests.get(avatar_url, stream=True).raw)
    av_img = av_img.resize((83, 83))

    # draw a mask to crop the ellipse
    mask_im = Image.new("L", (83, 83), 0)
    draw = ImageDraw.Draw(mask_im)
    draw.ellipse((0, 0, 83, 83), fill=255)

    # open background sc, and paste in the avatar and the cropping mask
    back_im = Image.open(os.path.join(img_dir, sc_file_name)).copy()
    back_im.paste(av_img, (15, 15), mask_im)

    # add fonts
    idraw = ImageDraw.Draw(back_im)
    name_font_ttf = os.path.join(fonts_dir, "Roboto-Light.ttf")
    name_font = ImageFont.truetype(name_font_ttf, size = 40)

    amount_font_ttf = os.path.join(fonts_dir, "Roboto-Black.ttf")
    amount_font = ImageFont.truetype(amount_font_ttf, size = 40)

    text_font_ttf = os.path.join(fonts_dir, "Roboto-Regular.ttf")
    text_font = ImageFont.truetype(text_font_ttf, size = 40)

    # write name to img
    nickname = res.author.display_name
    idraw.text(
        (118, 13),
        nickname,
        font = name_font,
        fill = fill
    )

    # write amount to img
    idraw.text(
        (118, 61),
        amount,
        font = amount_font,
        fill = fill
    )

    # write text to img
    if msg:
        wraplength = 660

        m, *words = msg.split(" ")
        ## wrap text if longer than wraplength
        for word in words:
            if idraw.textsize(m + " " + word, text_font)[0] > wraplength:
                m += "\n" + word
            else:
                m += " " + word
        txt_w, txt_h = idraw.textsize(m, text_font)
        idraw.text(
            (15, 129), 
            m, 
            font = text_font, 
            fill = fill
        )

    # crop img of excessive length
    final_height = (txt_h + 144) if msg else 114
    back_im = back_im.crop((0, 0, 690, final_height))

    # save image
    save_file = os.path.join(save_dir, str(random.randint(1,20)) + sc_file_name)
    back_im.save(save_file)

    await res.channel.send(file = discord.File(save_file))

async def meme(res, msg):
    err_msg = "Please provide a correct meme argument!! (ex: $meme woke)"

    if not msg:
        await res.channel.send(err_msg)
        return

    meme_cmd, *meme_args = [m.strip() for m in msg.split("\n") if m]

    if meme_cmd not in d["meme"]:
        await res.channel.send(err_msg)
        return
    
    # get meme info from data meme.json file
    meme_info = d["meme"][meme_cmd]
    file_name = meme_info["file"]
    positions = meme_info["positions"]
    wrapsize = meme_info["wrapsize"]
    text_align = meme_info["align"]
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
        # remove emotes, change all others mentions to raw text
        arg = to_raw_text(arg)

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
            fill = tuple(meme_font["fill"]),
            align = text_align
        )
    img.save(save_file)
    await res.channel.send(file = discord.File(save_file))

async def botan_art(res, msg):
    # pop one  from temp
    art_url = temp_art_deque.popleft()
    temp_art_set.remove(art_url)
    await res.channel.send(art_url)

    # get a new art url from database to add to temp
    new_art_url = list(db["artworks"].aggregate([{"$sample": {"size": 1}}]))[0]["url"]
    while new_art_url in temp_art_set:
        new_art_url = list(db["artworks"].aggregate([{"$sample": {"size": 1}}]))[0]["url"]
    temp_art_set.add(new_art_url)
    temp_art_deque.append(new_art_url)

## !!! Valentines Event
async def valentines_confession(res, msg):
    # retrieve user form valentines database
    participant = db["valentines"].find_one({"id": res.author.id})

    # if user not in valentines database
    if not participant:
        m = "I'm sorry {}, this command is only available to Valentine's event participant!"
        await res.channel.send(m.format(booster_nickname(res.author)))
        return
    
    # if user has already confessed
    if participant.get("already_confessed", None):
        m = "Sorry {}, it seems like you already made a confession! Contact Rachel if you wish to reset."
        await res.channel.send(m.format(booster_nickname(res.author)))
        return
    
    confession_channel = client.get_channel(d["discord_ids"]["valentines_confession"])

    # if msg is empty
    if not msg:
        # show confession method
        m = "Happy Valentine's Day {}! Do you have anything to tell your guardian or target but are just too shy to "
        m += "say in public? Or do you just want to share your feelings about this event or the server in general? "
        m += "Whatever it is, make your confession here! It is completely anonymous. You only get to confess once, so make it count."
        m += "\n``confess {{Message}}``"
        await res.channel.send(m.format(booster_nickname(res.author)))
        return
    
    # Show embed of message including photo
    embed = discord.Embed(title = "React to Send Your Confession", description = msg, colour = 0xFCE16D)
    if res.attachments:
        embed.set_image(url = res.attachments[0].url)
    edit_msg = await res.channel.send(content = None , embed = embed)

    # Ask confirmation from author through reactions
    tick_emote = u"\u2705"
    cross_emote = u"\U0001F6AB"
    await edit_msg.add_reaction(tick_emote)
    await edit_msg.add_reaction(cross_emote)

    # wait for correct reaction and record
    def check(reaction, user):
        reacted_emote = str(reaction.emoji)
        return reaction.message.id == edit_msg.id and user == res.author and (reacted_emote == tick_emote or reacted_emote == cross_emote)

    try:
        reaction, user = await client.wait_for('reaction_add', timeout = 60.0, check=check)
    except asyncio.TimeoutError:
        # if overtime, send timeout message and return
        m = "The pending message has been cancelled, you may use the confess command again for a new message."
        timeout_embed = discord.Embed(title = "Timeout", description = m, colour = 0xFF0000)
        await res.channel.send(content = None, embed = timeout_embed)
        return

    # if cancelled, send cancellation message and return
    if str(reaction.emoji) == cross_emote:
        m = "The pending message has been cancelled, you may use the confess command again for a new message."
        timeout_embed = discord.Embed(title = "Cancelled Letter", description = m, colour = 0xFF0000)
        await res.channel.send(content = None, embed = timeout_embed)
        return

    # else, send message to target including photo
    target_embed = discord.Embed(title = None, description = msg, colour = 0xFFB6B6)
    if res.attachments:
        target_embed.set_image(url = res.attachments[0].url)
    await confession_channel.send(content = None, embed = target_embed)

    # tell that message is successfully sent, and to wait 2 hours for next send
    await res.channel.send("We have sent your confession to the channel! Please contact Rachel if you need to change anything.")

    # update last sent to now in database
    db["valentines"].update_one({"id": res.author.id}, {"$set": {"already_confessed" : True}})

async def send_valentines_message(res, msg):
    # retrieve user form valentines database
    participant = db["valentines"].find_one({"id": res.author.id})

    # if user not in valentines database
    if not participant:
        m = "I'm sorry {}, it seems like you are not assigned a match for the Valentine's event yet!"
        m += "\nTo participate in the event, kindly refer to the announcement channel of Botan's fan server or contact a mod."
        m += "\nIf you have already reacted to the Secret Guardian role in the server, please note that it may take a while to match new people."
        m += "\nWe will notify you again upon matching."
        await res.channel.send(m.format(booster_nickname(res.author)))
        return

    botan_guild = client.get_guild(d["discord_ids"]["guild"])
    target = botan_guild.get_member(participant["target"])
    # If target is  empty or not in guild, return error and ask member to contact mod
    if not target:
        m = "I'm sorry {}, I can't find your secret match in the server anymore!"
        m += " It is possible that they may have left the server. Please contact a mod for manual reassignment."
        await res.channel.send(m.format(booster_nickname(res.author)))
        return

    # if msg is empty
    if not msg:
        # show secret match name and command details
        m = "Your Valentine's secret match is {}, use the same command again along with a message to send them an anonymous letter!"
        m += " You may even attach a photo!"
        m += "\n``valentines {{Message}}``"
        await res.channel.send(m.format(str(target)))
        return

    # if last sent exists and is not more than 2 hours ago
    last_sent = participant.get("last_sent", None)
    if last_sent:
        last_sent = last_sent.replace(tzinfo = timezone.utc)
    time_now = dtime.now(tz = timezone.utc)
    if last_sent and (time_now - last_sent) < timedelta(hours = 2):
        # tell the remaining time left till next available send and return
        timeleft_str = time_to_string(*days_hours_minutes(timedelta(hours = 2) - (time_now - last_sent)))
        m = "Sorry {}, you still need to wait for another {} before you can send {} another anonymous letter!"
        await res.channel.send(m.format(booster_nickname(res.author), timeleft_str, target.name))
        return

    # Show embed of message including photo
    embed = discord.Embed(title = "React to Send Your Message", description = msg, colour = embed_color)
    if res.attachments:
        embed.set_image(url = res.attachments[0].url)
    edit_msg = await res.channel.send(content = None , embed = embed)
    
    # Ask confirmation from author through reactions
    tick_emote = u"\u2705"
    cross_emote = u"\U0001F6AB"
    await edit_msg.add_reaction(tick_emote)
    await edit_msg.add_reaction(cross_emote)

    # wait for correct reaction and record
    def check(reaction, user):
        reacted_emote = str(reaction.emoji)
        return reaction.message.id == edit_msg.id and user == res.author and (reacted_emote == tick_emote or reacted_emote == cross_emote)

    try:
        reaction, user = await client.wait_for('reaction_add', timeout = 60.0, check=check)
    except asyncio.TimeoutError:
        # if overtime, send timeout message and return
        m = "The pending message has been cancelled, you may use the valentines command again for a new message."
        timeout_embed = discord.Embed(title = "Timeout", description = m, colour = 0xFF0000)
        await res.channel.send(content = None, embed = timeout_embed)
        return

    # if cancelled, send cancellation message and return
    if str(reaction.emoji) == cross_emote:
        m = "The pending message has been cancelled, you may use the valentines command again for a new message."
        timeout_embed = discord.Embed(title = "Cancelled Letter", description = m, colour = 0xFF0000)
        await res.channel.send(content = None, embed = timeout_embed)
        return

    # else, send message to target including photo
    target_embed = discord.Embed(title = "Your Secret Guardian has just sent you a letter!", description = msg, colour = 0xFFB6B6)
    if res.attachments:
        target_embed.set_image(url = res.attachments[0].url)
    await target.send(content = None, embed = target_embed)

    # tell that message is successfully sent, and to wait 2 hours for next send
    await res.channel.send("We have sent your letter to {}! You may send a new one after 2 hours.".format(target.name))

    # update last sent to now in database
    db["valentines"].update_one({"id": res.author.id}, {"$set": {"last_sent" : time_now}})

async def push_new_valentines_batch(res, msg):
    botan_guild = client.get_guild(d["discord_ids"]["guild"])
    guardian_role = botan_guild.get_role(805774276618878977)

    # get new participants with unassigned match
    all_participants = set(member.id for member in guardian_role.members)
    existing_participants = set(member["id"] for member in db["valentines"].find({}, projection = {"id": True, "_id": False}))
    new_participants = list(all_participants - existing_participants)
    random.shuffle(new_participants)

    m = [
            "Ohayou {}!\n\nThe Secret Guardian Event is currently underway",
            " and the person you will be ~~stalking~~ protecting for the next few weeks is {}.",
            " Keep your identity anonymous and use the secret command ``valentines`` here",
            " to send secret love letters to your new date. There is an 8-hour cooldown between messages,",
            " so choose your words wisely! But don't worry about testing the command, BOTan will double confirm with you before sending a message.",
            "\n\nImportant Note: Your personal secret guardian is different from the person you are protecting."
    ]
    title = "Cupid Alert!!"

    # match each member to a target and guardian
    for i in range(len(new_participants)):
        new_participant = {
            "id": new_participants[i],
            "guardian": new_participants[i-1],
            "target": new_participants[(i+1)%len(new_participants)]
        }
        db["valentines"].insert_one(new_participant)

        # send new participant instructions
        participant = client.get_user(new_participant["id"])
        target = client.get_user(new_participant["target"])

        if not (participant and target):
            print(new_participant)
            continue

        msg = "".join(m).format(booster_nickname(participant), str(target))
        embed = discord.Embed(title = title, description = msg, colour = embed_color)
        embed.set_thumbnail(url = target.avatar_url)
        await participant.send(content = None, embed = embed)
    
    await res.channel.send("Done pushing!")

# remove inactive guardians
async def remove_valentines_inactive(res, msg):
    pass

# temp valentines mass dm command
async def valentines_dm(res, msg):
    # retrieve db participants
    participants = db["valentines"].find()

    # craft message content
    m = [
            "Ohayou {}!\n\nThe Secret Guardian Event is currently underway",
            " and the person you will be ~~stalking~~ protecting for the next few weeks is {}.",
            " Keep your identity anonymous and use the secret command ``valentines`` here",
            " to send secret love letters to your new date. There is an 8-hour cooldown between messages,",
            " so choose your words wisely! But don't worry about testing the command, BOTan will double confirm with you before sending a message.",
            "\n\nImportant Note: Your personal secret guardian is different from the person you are protecting."
    ]
    title = "Cupid Alert!!"

    # for each participant, send content
    for participant_data in participants:
        participant = client.get_user(participant_data["id"])
        target = client.get_user(participant_data["target"])

        if not (participant and target):
            print(participant_data)
            continue

        msg = "".join(m).format(booster_nickname(participant), str(target))
        embed = discord.Embed(title = title, description = msg, colour = embed_color)
        embed.set_thumbnail(url = target.avatar_url)
        await participant.send(content = None, embed = embed)

    await res.channel.send("Done sending!")

## !!! Valentines Event (End)

## admin commands

"""reactions
{
    "msg_id": int,
    "ch_id": int,
    "reactions": {
        emoji_str (in str): role_id (as int)
    }
}
"""
### add role reaction to existing message
async def new_role_reaction(res, msg):
    if (not res.author.guild_permissions.administrator) and str(res.author) != owner:
        return

    # $role_reaction {channel id}\n{message id}\n{emoji_str}\n{role id}
    args = msg.split("\n")

    # if arguments num is less than 4, return error
    if len(args) < 4:
        await res.channel.send("Need {} more arguments!".format(4 - len(args)))
        return

    # convert variables
    ch_id, msg_id, emoji_str, role_id = [x.strip() for x in args]
    try:
        ch_id, msg_id, role_id = int(ch_id), int(msg_id), int(role_id)
    except ValueError:
        await res.channel.send("Please insert valid ids for the arguments!")
        return
    
    try:
        emoji_id = emoji_to_id(emoji_str)
    except ValueError:
        await res.channel.send("Please insert a valid emoji for the argument!")
        return
    
    # retrieve variables objects
    target_channel = client.get_channel(ch_id)
    target_message = await target_channel.fetch_message(msg_id)
    target_emoji = client.get_emoji(emoji_id)
    target_role = target_channel.guild.get_role(role_id)

    # return error if any of the objects is empty
    if not all((target_channel, target_message, target_emoji, target_role)):
        await res.channel.send("Can't find some of the ids, please check your arguments!")
        return

    # add reaction to message
    try:
        await target_message.add_reaction(target_emoji)
    except discord.NotFound:
        await res.channel.send("Failed to find targeted emoji, please try another one.")
        return
    
    # store role reaction to database
    reaction_data = db["reactions"].find_one({"msg_id": msg_id})

    # if reaction data doesn't exist, create data
    if not reaction_data:
        reaction_data = {
            "msg_id": msg_id,
            "ch_id": ch_id,
            "reactions": {
                emoji_str: role_id
            }
        }
        db["reactions"].insert_one(reaction_data)
    elif reaction_data["reactions"].get(emoji_str, None):
        # if reaction role already exists, return error
        await res.channel.send("Reaction role already exists, please try another emote or message.")
        return
    else:
        # else update data
        db["reactions"].update_one(reaction_data, {"$set": {"reactions.{}".format(emoji_str): role_id}})
    
    await res.channel.send("Successfully added reaction role!")

### remove role reaction from a message
async def remove_role_reaction(res, msg):
    if (not res.author.guild_permissions.administrator) and str(res.author) != owner:
        return
    
    # $del_rolreact {msg_id} {emoji_str}
    args = msg.split(" ")

    # if arguments not at least 2, return
    if len(args) < 2:
        await res.channel.send("Need at least 2 arguments!")
        return

    # convert variables
    msg_id, emoji_str = args
    try:
        msg_id = int(msg_id)
    except ValueError:
        await res.channel.send("First argument needs to be a valid message id!")
        return
    
    # find database with msg_id and emoji_str
    reaction_data = db["reactions"].find_one({"msg_id": msg_id})
    if (not reaction_data) or (not reaction_data["reactions"].get(emoji_str, None)):
        await res.channel.send("This reaction role doesn't exist in database! Please check your arguments.")
        return
    
    # if more than one reaction in reaction data, update field, else remove document
    if len(reaction_data["reactions"]) > 1:
        db["reactions"].update_one({"msg_id": msg_id}, {"$unset": {"reactions.{}".format(emoji_str): None}})
    else:
        db["reactions"].delete_one(reaction_data)
    
    # if message still exists in channel with the bot reaction, remove it.
    ch_id = reaction_data.get("ch_id", None)
    target_channel = client.get_channel(ch_id)
    if target_channel:
        try:
            target_message = await target_channel.fetch_message(msg_id)
            for reaction in target_message.reactions:
                if str(reaction.emoji) == emoji_str:
                    await reaction.remove(client.user)
        except discord.NotFound:
            await res.channel.send("The specified Discord Message or Reaction Emoji is no longer found.")

    # reply
    await res.channel.send("Role reaction removed from detabase!")

### get the ban list
async def get_bans(res, msg):
    ban_list = await res.guild.bans()
    m = ""
    for ban_entry in ban_list:
        user_id = ban_entry.user.id
        reason = ban_entry.reason
        entry_str = "{}: {}\n".format(user_id, reason)
        if len(m) + len(entry_str) <= 2000:
            m += entry_str
        else:
            await res.channel.send(m)
            m = entry_str
    await res.channel.send(m)

### get members count based on role
async def get_members_count(res, msg):
    if not is_integer(msg):
        await res.channel.send("Not a valid role id!")
        return

    target_role = res.guild.get_role(int(msg))

    if not target_role:
        await res.channel.send("Not a valid role id!")
        return
    
    await res.channel.send(len(target_role.members))

async def post(res, msg):
    m = msg.split("\n")
    if len(m) < 3:
        await res.channel.send("Need more arguments!")
        return
    channel = discord.utils.get(res.guild.text_channels, name= m[0].strip()) 
    embed = discord.Embed(title = m[1], description = "\n".join(m[2:]), colour = embed_color)
    embed.set_footer(text="message by {}".format(str(res.author)))
    if res.attachments:
        embed.set_image(url = res.attachments[0].url)
    await channel.send(content = None , embed = embed)

### test functions to check read messages
async def system_read(res, msg):
    if not msg.isdigit():
        return
    ann_ch = client.get_channel(d["discord_ids"]["announcements"])
    m = await ann_ch.fetch_message(int(msg))
    await res.channel.send(m.author.name)

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

### detect image text and log two texts (normal and inverted img)
async def detect_image_text(res, msg):
    # use tesseract to detect text from attachments
    # img_to_str = partial(Tess.image_to_string, timeout=60)
    await res.channel.send("Processing image...")
    for attachment in res.attachments:
        
        text, inverted_text = await _detect_image_text(attachment.url)

        m = "```{}```\n```{}```".format(text, inverted_text)
        await res.channel.send(m)

### database manipulation
async def add_trivia(res, msg):
    counter["trivia"] += 1
    db["trivia"].insert_one({"id": counter["trivia"], "desc": msg})
    db["settings"].update_one({"name": "counter"}, {"$set": {"trivia": counter["trivia"]}})
    await res.channel.send("Added one new trivia to database with an id of {}.".format(counter["trivia"]))

async def del_trivia(res, msg):
    if not msg or not msg.isdigit():
        await res.channel.send("Please provide the trivia id that you wish to delete!")
        return
    target_trivia = db["trivia"].find_one({"id": int(msg)})
    if not target_trivia:
        await res.channel.send("Can't find anything similar in the database!")
        return
    await res.channel.send("Found trivia, deleting...")
    db["trivia"].delete_one(target_trivia)
    await res.channel.send("Trivia successfully deleted.")

async def add_art(res, msg):
    if db["artworks"].find_one({"url": msg}):
        await res.channel.send("There's already an existing art with the same url!")
        return
    db["artworks"].insert_one({"url": msg})
    await res.channel.send("Added one new artwork to database!")

async def del_art(res, msg):
    target_art = db["artworks"].find_one({"url": msg})
    if not target_art:
        await res.channel.send("Can't find anything similar in the database!")
        return
    await res.channel.send("Found artwork, deleting now!")
    db["artworks"].delete_one(target_art)
    await res.channel.send("Artwork successfully deleted.")

### Membership (Zoopass)

async def view_membership(res, msg):
    # if msg is empty, show all members
    if not msg:
        m = ""
        for bodan in db["bodans"].find():
            member_id = bodan["id"]
            membership_date = bodan["last_membership"].replace(tzinfo = timezone.utc).strftime("%d/%m/%Y")
            new_line = "{}: {}\n".format(member_id, membership_date)
            if len(m) + len(new_line) > 2000:
                await res.channel.send(m)
                m = ""
            m += new_line
        await res.channel.send(m)
        return

    # if msg is not empty
    member_id = msg

    # Check if msg is numeric
    if not member_id.isnumeric():
        await res.channel.send("Please provide a valid id!")
        return
    
    member_id = int(member_id)

    # Check if zoopass in database and delete
    target_membership = db["bodans"].find_one({"id": member_id})
    if not target_membership:
        await res.channel.send("Can't find membership id in the database!")
        return
    
    # Send information about membership
    botan_guild = client.get_guild(d["discord_ids"]["guild"])
    target_member = botan_guild.get_member(member_id)

    membership_date = target_membership["last_membership"].replace(tzinfo = timezone.utc)
    expiration_date = membership_date + timedelta(days = 30)

    ## change dates to strings
    membership_date = membership_date.strftime("%d/%m/%Y, %H:%M:%S")
    expiration_date = expiration_date.strftime("%d/%m/%Y, %H:%M:%S")

    m = "Name: {}\nID: {}\nMembership Date: {}\nMembership End Date: {}"
    m = m.format(str(target_member), member_id, membership_date, expiration_date)
    embed = discord.Embed(title = "Zoopass Membership", description = m)

    await res.channel.send(content=None, embed = embed)
    

async def set_membership(res, msg):
    msg = msg.split(" ")
    if len(msg) < 2:
        await res.channel.send("Please include at least two arguments!\n``$``")
        return
    
    member_id, adjustment = msg
    # Check if member_id is valid
    if not is_integer(member_id):
        await res.channel.send("Please provide a valid id.")
        return
    
    member_id = int(member_id)
    
    # Check if id exists
    target_membership = db["bodans"].find_one({"id": member_id})
    if not target_membership:
        await res.channel.send("Can't find membership id in the database!")
        return
    
    # Adjust membership date
    if is_integer(adjustment):
        new_date = target_membership["last_membership"].replace(tzinfo = timezone.utc) + timedelta(days = int(adjustment))
    else:
        dates = adjustment.split("/")
        if len(dates)!=3 or any(not is_integer(date) for date in dates):
            await res.channel.send("Please provide a valid date (dd/mm/yyyy) or integer days (+/- integer).")
            return
        new_date = dtime(year = int(dates[2]), month = int(dates[1]), day = int(dates[0]), tzinfo = timezone.utc)
    db["bodans"].update_one({"id": member_id}, {"$set": {"last_membership": new_date}})

    await res.channel.send("New membership date for {} set at {}!".format(member_id, new_date.strftime("%d/%m/%Y, %H:%M:%S")))
    

async def del_membership(res, msg):
    member_id = msg.split("\n")[0].split(" ")[0]

    # Check if msg is numeric
    if not member_id.isnumeric():
        await res.channel.send("Please provide a valid id!")
        return
    
    member_id = int(member_id)

    # Check if zoopass in database and delete
    target_membership = db["bodans"].find_one({"id": member_id})
    if not target_membership:
        await res.channel.send("Can't find membership id in the database!")
        return
    await res.channel.send("Found membership in database, deleting now!")
    db["bodans"].delete_one(target_membership)

    # Remove zoopass role from user
    botan_guild = client.get_guild(d["discord_ids"]["guild"])
    target_member = botan_guild.get_member(member_id)

    zoopass_role_id = d["discord_ids"]["zoopass_role"]
    zoopass_role = botan_guild.get_role(zoopass_role_id)

    await target_member.remove_roles(zoopass_role)
    
    await res.channel.send("Membership successfully deleted.")

    # If msg has extra lines, send dm to target user to notify the zoopass deletion
    if len(msg.split("\n")) > 1:
        await direct_dm(res, msg, override=True)

### youtube
async def add_upcoming_stream(res, msg):
    vid_id = msg
    if not vid_id:
        return
    # check if vid already exists in database
    if db["streams"].find_one({"id": vid_id}):
        await res.channel.send("{} already exists in database!".format(vid_id))
        return
    # else store video's id, status and scheduled start time
    vid_req = youtube.videos().list(
        part = "snippet,liveStreamingDetails",
        id = vid_id
    )
    vid_res = vid_req.execute()["items"][0]

    title = vid_res["snippet"]["title"]

    dt_string = vid_res["liveStreamingDetails"]["scheduledStartTime"]
    scheduled_start_time = dtime.strptime(dt_string, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo = timezone.utc)

    vid_data = {
        "id": vid_id,
        "title": title,
        "status": "upcoming",
        "scheduled_start_time": scheduled_start_time
    }
    db["streams"].insert_one(vid_data)
    await res.channel.send("New upcoming video logged!\n{}\n{}".format(vid_id, scheduled_start_time))

async def end_live_stream(res, msg):
    vid_id = msg
    # Check if stream exists
    if not db["streams"].find_one({"id": vid_id}):
        await res.channel.send("Stream {} does not exist in the database!".format(vid_id))
        return
    
    # Tag stream with ending tag to end it early
    db["streams"].update_one({"id": vid_id}, {"$set": {
                    "end": "Stream ended manually at " + str(dtime.now(tz = timezone.utc))
                }})
    await res.channel.send("Ending stream {} manually!".format(vid_id))

async def delete_stream(res, msg):
    vid_id = msg
    target_vid = db["streams"].find_one({"id": vid_id})
    # Check if stream exists
    if not target_vid:
        await res.channel.send("Stream {} does not exist in the database!".format(vid_id))
        return
    
    await res.channel.send("Found stream, deleting now!")
    db["streams"].delete_one(target_vid)
    await res.channel.send("Targeted stream successfully deleted.")

## booster commands
"""booster's data template
    "id": res.author.id,
    "nickname": "",
    "boosts_count": 1,
    "custom_role": -1
"""
async def booster_help(res, msg):
    msg = msg.strip().lower()
    msg = aliases.get(msg, msg)
    if msg in d["help_booster"]:
        cmd_doc = d["help_booster"][msg]
        embed = discord.Embed(title = "Lion Tamer's Help Menu: '{}' Command".format(msg), description = cmd_doc["desc"])
        for field in cmd_doc["extra_fields"]:
            field_msg = "\n".join(field["value"]) if isinstance(field["value"], list) else field["value"]
            embed.add_field(name = field["name"], value = field_msg, inline = False)
        embed.add_field(name = "Usage", value = cmd_doc["usage"])
        if cmd_doc["alias"]:
            embed.add_field(name = "Aliases", value = ", ".join(cmd_doc["alias"]))
    else:
        embed = discord.Embed(title = "Lion Tamer's Help Menu: Available Commands", description = "\n".join(d["help_booster"]))
        embed.add_field(name = "More Help", value = "help {command name}")
    embed.colour = embed_color
    await res.channel.send(content = None, embed = embed)

async def new_booster_nickname(res, msg):
    if not msg:
        await res.channel.send("Your current nickname is {}. If you wish to change it, please provide an argument for the ``nickname`` command!".format(booster_nickname(res.author)))
        return
    db["boosters"].update_one({"id": res.author.id}, {"$set": {"nickname": msg}})
    await res.channel.send("Noted, I will refer to you as {} from now on.".format(booster_nickname(res.author)))

async def new_booster_color_role(res, msg):
    # parse msg into role name and color code
    err_msg = "Please provide the correct arguments required for creating a color role!"
    match = re.fullmatch(r"(\"(?P<name>.+)\")? ?(#(?P<color>[0-9a-fA-F]{6}))?", msg)

    if not match:
        await res.channel.send(err_msg)
        return

    role_name, color = match.group("name", "color")
    if not (role_name or color):
        await res.channel.send(err_msg)
        return
    
    if color:
        color = discord.Colour(int(color, 16))

    # retrieve booster data
    custom_role_id = db["boosters"].find_one({"id": res.author.id})["custom_role"]
    botan_guild = client.get_guild(d["discord_ids"]["guild"])
    author = botan_guild.get_member(res.author.id)

    # if there is no existing color role
    if custom_role_id == -1:
        try:
            new_custom_role = await botan_guild.create_role(
                name = role_name if role_name else "Custom Color Role",
                colour = color if color else discord.Colour.default(),
                reason = "{} created new custom booster role".format(str(res.author))
            )
            await new_custom_role.edit(position = 22)
        except discord.InvalidArgument:
            await res.channel.send("Something went wrong when I was trying to create the role, please contact an admin or try another name!")
            return

        # update new custom role id
        await author.add_roles(new_custom_role)
        custom_role_id = new_custom_role.id
        db["boosters"].update_one({"id": res.author.id}, {"$set": {"custom_role": custom_role_id}})
        await res.channel.send("New custom role created!")

    # if there is an existing color role
    else:
        custom_role = botan_guild.get_role(custom_role_id)
        
        # if role not found, return message
        if not custom_role:
            await res.channel.send("I can't seem to find your existing role! Please contact an admin for troubleshooting.")
            return

        try:
            await custom_role.edit(
                name = role_name if role_name else custom_role.name,
                colour = color if color else custom_role.colour
            )
        except discord.InvalidArgument:
            await res.channel.send("Something went wrong when I was trying to edit the role, please contact an admin or try another name!")
            return
        await res.channel.send("Custom role edited!")

async def del_booster_color_role(res, msg):
    # retrieve booster data
    custom_role_id = db["boosters"].find_one({"id": res.author.id})["custom_role"]
    botan_guild = client.get_guild(d["discord_ids"]["guild"])

    if custom_role_id == -1:
        await res.channel.send("You don't seem to own a custom role yet! Please contact an admin if otherwise!")
        return
    
    custom_role = botan_guild.get_role(custom_role_id)
    await custom_role.delete(reason = "{} requested a custom role deletion".format(str(res.author)))
    db["boosters"].update_one({"id": res.author.id}, {"$set": {"custom_role": -1}})
    await res.channel.send("Role deletion successful! You may add a custom role again anytime you want.")

### Removed code of booster news
# async def booster_news(res, msg):
#     up_news_ch = client.get_channel(d["discord_ids"]["upcoming_news"])
#     last_news = await up_news_ch.fetch_message(up_news_ch.last_message_id)
#     embed =  last_news.embeds[0] if last_news.embeds else None
#     await res.channel.send(content = last_news.content, embed = embed)

## dm commands
"""
{
    "id": int
    "last_membership": datetime
}
"""
async def verify_membership(res, msg):
    # Check if there is a valid attachment
    if not res.attachments:
        await res.channel.send("I'm sorry {}, you need to provide a valid photo along with the ``verify`` command to complete the verification process.".format(booster_nickname(res.author)))
        return
    
    # Get membership time
    new_membership_date = dtime.now(tz = timezone.utc)

    # if member exists, update date
    bodan = db["bodans"].find_one({"id": res.author.id})

    # check date
    try:
        text, inverted_text = await asyncio.wait_for(_detect_image_text(res.attachments[0].url), timeout = 30)
        img_date = date_from_txt(text) or date_from_txt(inverted_text)
        if img_date:
            new_membership_date = img_date - timedelta(days = 30)
    except asyncio.TimeoutError:
        print("timeout error detecting image!")
    except:
        print("date detection fail!!")

    if bodan:
        last_membership = bodan["last_membership"].replace(tzinfo = timezone.utc)
        db["bodans"].update_one({"id": res.author.id}, {"$set": {"last_membership": max(new_membership_date, last_membership)}})

    # if not, create data
    else:
        db["bodans"].insert_one({
            "id": res.author.id,
            "last_membership": new_membership_date
        })

    # Send attachment and message to membership verification channel
    member_veri_ch = client.get_channel(d["discord_ids"]["membership_verification"])
    title = res.author.id
    desc = "{}\n{}".format(str(res.author), new_membership_date.strftime("%d/%m/%Y, %H:%M:%S"))
    embed = discord.Embed(title = title, description = None, colour = embed_color)
    embed.set_image(url = res.attachments[0].url)
    await member_veri_ch.send(content = "```\n{}\n```".format(desc), embed = embed)

    # add role
    botan_guild = client.get_guild(d["discord_ids"]["guild"])
    author = botan_guild.get_member(res.author.id)

    zoopass_role_id = d["discord_ids"]["zoopass_role"]
    zoopass_role = botan_guild.get_role(zoopass_role_id)

    await author.add_roles(zoopass_role)

    # DM user that the verification process is complete
    m = "Membership applied! You now have temporary access to members-excusive content in the server."
    m += "\nPlease note that our staff will double-confirm the verification photo and may revoke it on a case-by-case basis."
    m += "\nIf you have encountered any issue with accessing the channels or have a separate enquiry, please contact a mod."
    await res.channel.send(m)
    

## nsfw dm commands
async def add_contr(res, msg, contr = 1):
    member = db["members"].find_one({"id": res.author.id})
    if not member:
        await res.channel.send("Can't find member!")
        return
    old_contr = member["nsfw"]["contributions"]
    new_contr = old_contr + contr

    db["members"].update_one({"id": res.author.id}, {"$set": {"nsfw.contributions": new_contr}})
    m = "You have received one new horny point!\n```\nTotal Horny Points: {}\n```"
    await res.channel.send(m.format(new_contr))

    # if contributions are at least 10 and first digit changes, add a ticket
    if new_contr >= 10 and str(new_contr)[0] != str(old_contr)[0]:
        await add_tick(res, msg)

async def add_tick(res, msg, tick = 1):
    member = db["members"].find_one({"id": res.author.id})
    if not member:
        await res.channel.send("Can't find member!")
        return
    new_tick = member["nsfw"]["horny_tickets"] + tick
    db["members"].update_one({"id": res.author.id}, {"$set": {"nsfw.horny_tickets": new_tick}})
    m = "Congratulations! You have proven yourself enough to the Horny Cult! You earned a horny ticket."
    m += "\nYou may use a horny ticket to invite new horny cultists. Use the command ``invite_horny {user id}`` to grant your friend access to the cult!"
    m += "\n```\nHorny Ticket Count: {}\n```".format(new_tick)
    await res.channel.send(m)

async def invite_horny(res, msg):
    if not is_horny(res.author):
        m = "I'm sorry {}, you have stumbled upon a hidden command!\nTry coming back again once you get the appropriate access."
        await res.channel.send(m.format(booster_nickname(res.author)))
        return
    member = db["members"].find_one({"id": res.author.id})
    tick_count = member["nsfw"]["horny_tickets"]
    if not tick_count:
        await res.channel.send("I'm sorry {}, you don't have enough horny tickets to invite someone! Earn more horny points to get them!")
        return
    
    if not msg or not msg.isdigit():
        await res.channel.send("Please provide a valid user id!")

    new_member = client.get_user(int(msg))

    if not new_member:
        await res.channel.send("Please provide a valid user id!")
    
    new_member_data = db["members"].find_one({"id": new_member.id})
    if not new_member_data:
        db["members"].insert_one({
            "id": new_member.id,
            "nsfw": {
                "is_horny": True,
                "contributions": 0,
                "horny_tickets": 0
            }
        })
    elif new_member_data["nsfw"]["is_horny"] == False:
        db["members"].update_one({"id": new_member.id}, {"$set": {"nsfw.is_horny": True}})
    else:
        m = "Oh mys, this is embarrassing. {} seems to be either too horny or seiso to be able to receive your invitation. Try someone else!"
        await res.channel.send(m.format(new_member.name))
        return
    
    db["members"].update_one({"id": res.author.id}, {"$set": {"nsfw.horny_tickets": tick_count - 1}})
    m = "A shady figure in hoodie took your horny ticket and blended back into the darkness."
    m += " The cult always delivers, you know for sure {} will receive the invitation, but whether or not they will join the dark side is another story."
    m += "\n```\nHorny Ticket Count: {}\n```"
    await res.channel.send(m.format(new_member.name, tick_count - 1))

    # send message to new member
    new_m = [
        "You were walking down a dark alleyway when a hooded figure approached you.",
        " \"The Order wants you to have this,\" the person said under their breath as they passed you a ticket.",
        "\n\n```\nCongratulations, you have gained access to the Horny Cult!!\nAvailable commands:\n\n",
        "nsfw: see forbidden artworks unearthed by your fellow cultists.\n",
        "add_nsfw {twitter url}: contribute to the order with artworks you find and gain horny points!\n",
        "invite_horny {member id}: corrupt a friend and make the cult stronger! [Requires Horny Tickets]\n",
        "no_horny: you might want to opt out of being horny before it is too late.\n```",
        "\n\n\"Welcome to the cult, and we know how to find you shall the need arises,\" and the hooded figure was gone."
    ]
    embed = discord.Embed(title = "An Invitation: The Horny Cult", description = "".join(new_m), colour = embed_color)
    await new_member.send(content = None , embed = embed)

async def no_horny(res, msg):
    if not is_horny(res.author):
        m = "I'm sorry {}, you have stumbled upon a hidden command!\nTry coming back again once you get the appropriate access."
        await res.channel.send(m.format(booster_nickname(res.author)))
        return
    if msg != "SEISO":
        m = "Warning: This is an irreversible action, continuing the action will opt you out from all nsfw commands unless someone from the nsfw cult sends you another horny ticket."
        m += " To continue, type ``no_horny SEISO`` to stop seeing any future nsfw content."
        await res.channel.send(m)
        return
    db["members"].update_one({"id": res.author.id}, {"$set": {"nsfw.is_horny": False}})
    await res.channel.send("*You left the cult's secret entrance with a heavy heart.\nYou don't want to be horny anymore, you promised yourself.*")

async def add_nsfw_art(res, msg):
    if not is_horny(res.author):
        m = "I'm sorry {}, you have stumbled upon a hidden command!\nTry coming back again once you get the appropriate access."
        await res.channel.send(m.format(booster_nickname(res.author)))
        return
    match = re.search(r"https://twitter.com/[a-zA-Z0-9_]+/status/[0-9]+", msg)
    if match:
        if db["nsfws"].find_one({"url": match.group()}):
            await res.channel.send("There's already an existing nsfw art with the same url!")
            return
        db["nsfws"].insert_one({
            "url": match.group(),
            "tag": "other"
        })
        await res.channel.send("Added one new nsfw artwork to database!")

        # add contribution point for getting new nsfw art
        await add_contr(res, msg)
    else:
        await res.channel.send("I'm sorry, nsfw art command currently only accepts twitter urls.")


async def nsfw_art(res, msg):
    if not is_horny(res.author):
        m = "I'm sorry {}, you have stumbled upon a hidden command!\nTry coming back again once you get the appropriate access."
        await res.channel.send(m.format(booster_nickname(res.author)))
        return
    nsfw_url = list(db["nsfws"].aggregate([{"$sample": {"size": 1}}]))[0]["url"]
    await res.channel.send(nsfw_url)

## hidden developer commands
async def cross_server_post(res, msg):
    if str(res.author) != owner:
        return
    m = msg.split("\n")
    if len(m) < 2:
        await res.channel.send("Need at least {} more arguments!".format(2 - len(m)))
        return
    target_channel = client.get_channel(int(m[0]))
    embed = discord.Embed(title = m[1], description = "\n".join(m[2:]), colour = embed_color)
    if res.attachments:
        embed.set_image(url = res.attachments[0].url)
    await target_channel.send(content = None, embed = embed)

async def cross_server_message(res, msg):
    if str(res.author) != owner:
        return
    m = msg.split("\n", 1)
    if len(m) < 2:
        await res.channel.send("Need at least {} more arguments!".format(2 - len(m)))
        return
    target_channel = client.get_channel(int(m[0]))
    attachment = discord.File(res.attachments[0]) if res.attachments else None
    await target_channel.send(content = m[1], file = attachment)
        

async def direct_dm(res, msg, override = False):
    if str(res.author) != owner and not override:
        return
    m = msg.split("\n", 1)
    if len(m) < 2:
        await res.channel.send("Need at least {} more arguments!".format(2 - len(m)))
        return

    instr, message = m
    instr = instr.split(" ")

    # get target_user
    target_user = client.get_user(int(instr[0]))

    if len(instr) > 1:
        # if embed, send embed message
        if instr[1].lower() == "embed":
            # split message into title and description
            message = message.split("\n")
            if len(message) < 2:
                await res.channel.send("need at least {} more arguments for embed message!".format(2 - len(message)))
            
            embed = discord.Embed(title = message[0], description = "\n".join(message[1:]), colour = embed_color)
            
            if res.attachments:
                embed.set_image(url = res.attachments[0].url)

            await target_user.send(content = None , embed = embed)
    else:
        # else send normal message
        await target_user.send(message)

async def mass_dm(res, msg):
    # mass dm with id
    ids, message = msg.split("=", 1)
    ids = ids.split("\n")

    for member_id in ids:
        await _dm_member(member_id, message, True)

async def mass_role_dm(res, msg):
    # currently only works with botan guild's roles
    botan_guild = client.get_guild(d["discord_ids"]["guild"])

    if str(res.author) != owner:
        return
    m = msg.split("\n", 1)
    if len(m) < 2:
        await res.channel.send("Need at least {} more arguments!".format(2 - len(m)))
        return

    instr, message = m
    instr = instr.split(" ")

    # get target_role
    target_role = botan_guild.get_role(int(instr[0]))

    if len(instr) > 1:
        # if embed, send embed message
        if instr[1].lower() == "embed":
            # split message into title and description
            message = message.split("\n")
            if len(message) < 2:
                await res.channel.send("need at least {} more arguments for embed message!".format(2 - len(message)))
            
            embed = discord.Embed(title = message[0], description = "\n".join(message[1:]), colour = embed_color)
            
            if res.attachments:
                embed.set_image(url = res.attachments[0].url)

            for member in target_role.members:
                await member.send(content = None, embed = embed)
    else:
        # else send normal message
        for member in target_role.members:
            await member.send(message)

async def manual_close_tags(res, msg):
    if str(res.author) != owner:
        return
    await res.channel.send("starting")
    await process_tags(msg)
    await res.channel.send("processing complete!")

## command names
aliases = {
    "hi": "greet",
    "hello": "greet",
    "lalion": "greet",
    "pick": "choice",
    "bday": "birthday",
    "tl": "translate",
    "trans": "translate",
    "jp": "japanese",
    "addart": "add_art",
    "delart": "del_art",
    "addtrivia": "add_trivia",
    "deltrivia": "del_trivia",
    "addvid": "add_vid",
    "endvid": "end_vid",
    "delvid": "del_vid",
    "viewpass": "view_zoopass",
    "view_pass": "view_zoopass",
    "setpass": "set_zoopass",
    "setzoopass": "set_zoopass",
    "delpass": "del_zoopass",
    "delzoopass": "del_zoopass",
    "rolreact": "role_reaction",
    "delrolreact": "delete_role_reaction",
    "del_rolreact": "delete_role_reaction",
    "subs": "subscribers",
    "subscriber": "subscribers",
    "live": "stream",
    "v": "voice",
    "sc": "superchat",
    "t": "tag",
    "addnsfw": "add_nsfw",
    "nohorny": "no_horny",
    "invhorny": "invite_horny",
    "invitehorny": "invite_horny",
    "inv_horny": "invite_horny"
}

commands = {
    "help": help_command,
    "greet": greet,
    "gao": gao,
    "choice": random_choice,
    "debut": debut,
    "birthday": birthday,
    "translate": translate,
    "japanese": trans_to_jap,
    "meme": meme,
    "botan": botan_art,
    "100": score_me,
    "poi": poi,
    "sleepy": sleepy,
    "shishilamy": shishilamy,
    "subscribers": subscribers,
    "stream": live_streams,
    "voice": voice,
    "superchat": superchat,
    "tag": vid_tag,
    "trivia": botan_trivia
}

dm_commands = {
    "verify": verify_membership,
    "valentines": send_valentines_message,
    "confess": valentines_confession,
    # horny exclusive commands
    "nsfw": nsfw_art,
    "add_nsfw": add_nsfw_art,
    "no_horny": no_horny,
    "invite_horny": invite_horny
}

booster_commands = {
    "greet": greet,
    "nickname": new_booster_nickname,
    "role": new_booster_color_role,
    "help": booster_help,
    "delrole": del_booster_color_role
}

admin_commands = {
    # mods
    "post": post,
    "read": read, # redundant
    "xread": system_read, # redundant
    "add_art": add_art,
    "del_art": del_art,
    "add_trivia": add_trivia,
    "del_trivia": del_trivia,
    "add_vid": add_upcoming_stream,
    "end_vid": end_live_stream,
    "del_vid": delete_stream,
    "view_zoopass": view_membership,
    "set_zoopass": set_membership,
    "del_zoopass": del_membership,
    "img_txt": detect_image_text,
    "get_bans": get_bans,
    "members_count": get_members_count,
    # admins
    "role_reaction": new_role_reaction,
    "delete_role_reaction": remove_role_reaction,
    # dev commands
    "xvpush": push_new_valentines_batch,
    "xvannounce": valentines_dm,
    "xpost": cross_server_post,
    "xmessage": cross_server_message,
    "xdm": direct_dm,
    "xroledm": mass_role_dm,
    "xclosetag": manual_close_tags,
    "xmassdm": mass_dm # all mods
}

## on messaging
@client.event
async def on_message(res):
    # checks if bot
    if res.author == client.user:
        return
    
    # checks if system message
    if res.is_system():
        mt = discord.MessageType
        boosted_types = {
            mt.premium_guild_subscription,
            mt.premium_guild_tier_1,
            mt.premium_guild_tier_2,
            mt.premium_guild_tier_3
        }
        # check if system message is a nitro boost
        if res.type in boosted_types:
            # make a server announcement of boost
            ann_ch = res.guild.get_channel(d["discord_ids"]["announcements"])

            ## randomly chooses one msg as boosting announcement
            m_choices = (
                "{} just fed the lioness! But Botan is still hungry... Run!!!",
                "{} tried to tame our lion goddess!\n...\n[Task Failed]\n...\nWell...At least they will make a good meal...\n\"Itadakimasu~!\"",
                "Thank you for boosting the server, {}!\nWe give you a perfect score!\n\n" + ":100: :100: :100: :100: :100:\n" * 5,
                "{} has just pledged their eternal loyalty to Botan's Gamer's Clan [SSRB], and swear in the name of our lion goddess that they will never be a C in games (cheater).\n\n\"Comrade!\" *Salutes*",
                "{} starts using \"poi\" as their new battle roar cry whenever they throw grenades in COD, truly a Bodan!",
                "{} has just purchased one month's worth of ~~Weed~~ Shiso Leaves from our ~~drug dealing~~ botanist lion, thank you for your support!"
            )
            m = random.choice(m_choices).format(res.author.mention)

            if res.type != mt.premium_guild_subscription:
                m += " {} has achieved **Level {}**!\nThank you so much, we could never make it without your selfless contribution!".format(res.guild.name, res.guild.premium_tier)
            embed = discord.Embed(title = "New Nitro Boost", description = m, colour = 0xf47fff)
            await ann_ch.send(content = None, embed = embed)

            # check if user exists in boosters collections, if not create a new one, else update boosts count
            booster_data = db["boosters"].find_one({"id": res.author.id})
            if booster_data:
                booster_data["boosts_count"] += 1
                db["boosters"].update_one({"id": res.author.id}, {"$set": {"boosts_count": booster_data["boosts_count"]}})
            else:
                booster_data = {
                    "id": res.author.id,
                    "nickname": "",
                    "boosts_count": 1,
                    "custom_role": -1
                }
                db["boosters"].insert_one(booster_data)
            return

    # check if dm
    if isinstance(res.channel, discord.DMChannel):
        # log content to dm log channel for record
        dm_lg_ch = client.get_channel(d["discord_ids"]["dm_log"])
        await dm_lg_ch.send("{}\n{}".format(str(res.author),res.content))
        for attachment in res.attachments:
            await dm_lg_ch.send(attachment.url)

        # get command and message text (don't need prefix)
        cmd, *msg = res.content.split(" ", 1)
        cmd = cmd.strip().lower()
        msg = msg[0] if msg else ""

        # change any command alias to original command name
        cmd = aliases.get(cmd, cmd)
        
        # get guild and author member info in botan guild
        botan_guild = client.get_guild(d["discord_ids"]["guild"])
        author = botan_guild.get_member(res.author.id)

        # if cmd is in dm_commands
        action = dm_commands.get(cmd, None)
        if action:
            await action(res, msg)
            return

        # return if not nitro booster or owner
        if not (d["discord_ids"]["booster_role"] in (role.id for role in author.roles) or str(res.author) == owner):
            # if previous booster, use different message
            if db["boosters"].find_one({"id": res.author.id}):
                m = "Hi {}! Thanks again for supporting me in the past!\n".format(booster_nickname(author))
                m += "I'm sorry but you need the Lion Tamer role again to use any of my commands here...*cries*"
            else:
                m = "*A horny person appears! Botan flees.*"
            await res.channel.send(m)
            return

        # if public command exists, perform action
        action = booster_commands.get(cmd, None)
        if action:
            await action(res, msg)
            return

        # else, send a generic message 
        m = "Sorry {}, I didn't quite catch what you said! Can you say it again in a different way?\nOr use the ``help`` menu to find out more about what I can do!"
        await res.channel.send(m.format(booster_nickname(author)))
        return

    # check for banned links
    if any(True for ban_link in d["blacklist"]["ban_links"] if ban_link in res.content):
        admin_logs = discord.utils.get(res.guild.text_channels, name = "admin-logs")
        await res.delete()
        m = "\n".join([
            "**User**",
            str(res.author),
            "**Channel**",
            res.channel.name,
            "**Action**",
            "immediate message deletion",
            "**Message**",
            res.content
        ])
        embed = discord.Embed(title = "Suspicious Link Detected", description = m)
        await admin_logs.send(content = None, embed = embed)
        return

    # read twitter tweets from botan (is pingcord and is in tweets channel)
    if str(res.author) == pingcord and res.channel.id == d["discord_ids"]["tweets"]:
        channel = client.get_channel(d["discord_ids"]["translated_tweets"])
        for embed in res.embeds:
            embed.title = to_eng(embed.title).text
            embed.description = to_eng(embed.description).text
            await channel.send(content = None, embed = embed)
    
    # # check for mp4 links and suppress embeds
    # if ".mp4" in res.content:
    #     await res.edit(suppress = True)
        
    # if channel is fanart channel, automatically detects new tweets artwork.
    if res.channel.id == d["discord_ids"]["fanart"] and not res.content.startswith(prefix):
        match = re.search(r"https://twitter.com/[a-zA-Z0-9_]+/status/[0-9]+", res.content)
        if match:
            await add_art(res, match.group())
        return
    
    # !!! valentines
    """
    {
        time: datetime
        name: str
        avatar: avatar_url
        message: None or str
        image: None or attachment
    }
    """
    if res.channel.id == d["discord_ids"]["shishilamy"] and not res.content.startswith(prefix):
        image_url = None
        if res.attachments:
            image_url = res.attachments[0].url
        db["shishilamy"].insert_one({
            "time": dtime.now(tz = timezone.utc),
            "name": res.author.nick if res.author.nick else res.author.name,
            "avatar": str(res.author.avatar_url),
            "message": res.clean_content,
            "image": image_url
        })

    # !!! valentines

    # checks if message needs attention (has prefix)
    if not res.content.startswith(prefix):
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

    # check for admin/mod permission and if admin command exists, perform action
    if not (res.author.guild_permissions.administrator or any(role.id == d["discord_ids"]["mod_role"] for role in res.author.roles)):
        return
    action = admin_commands.get(cmd, None)
    if action:
        await action(res, msg)

# On message deleted
@client.event
async def on_message_delete(message):
    ## if message from other servers, return
    if (not message.guild) or message.guild.id != d["discord_ids"]["guild"]:
        return

    ## if message is from a bot, return
    if (message.author == client.user) or message.author.bot:
        return

    ## send message deletion info to mods logs
    server_logs_ch = client.get_channel(d["discord_ids"]["server_log"])
    member = message.author
    
    m = "**Author:** {}\n**Channel:** {}\n**Content:** {}".format(str(member), str(message.channel), message.content)
    if message.attachments:
        m += "\n**Attachments:** {}".format("\n".join(attachment.url for attachment in message.attachments))

    embed = discord.Embed(title = "Message Deleted", description = m, colour = 0xFF9D5C)
    embed.set_thumbnail(url = member.avatar_url)
    embed.set_footer(text = "ID: {}".format(member.id))

    await server_logs_ch.send(content = None, embed = embed)

# On member reacting to a message
@client.event
async def on_raw_reaction_add(payload):
    # user needs to be Member
    # if dm, return
    member = payload.member

    # return if reaction is botan bot
    if client.user == member:
        return

    # get message id and reaction id
    msg_id = payload.message_id
    emoji_str = str(payload.emoji)

    # get reaction data from database
    reaction_data = db["reactions"].find_one({"msg_id": msg_id})

    # if reaction_data doesn't exist or emoji_str doesnt exist, return
    if (not reaction_data) or (not reaction_data["reactions"].get(emoji_str, None)):
        return

    # check if user has role
    role_id = reaction_data["reactions"][emoji_str]
    user_roles = set(role.id for role in member.roles)
    target_role = member.guild.get_role(role_id)

    # remove role
    if role_id in user_roles:
        await member.remove_roles(target_role)
    # else add role
    else:
        await member.add_roles(target_role)

    # remove emoji reaction
    ch_id = reaction_data["ch_id"]
    target_channel = client.get_channel(ch_id)
    target_message = await target_channel.fetch_message(msg_id)
    await target_message.remove_reaction(payload.emoji, member)

# On members joining the server
@client.event
async def on_member_join(member):
    # welcome message (only for botan server)
    if member.guild.id != d["discord_ids"]["guild"]:
        return
    
    ## get data for welcome message
    wc_ch = client.get_channel(d["discord_ids"]["welcome"])
    r_ch = client.get_channel(d["discord_ids"]["rules"])
    member_count  = member.guild.member_count
    m = "Paao~! Welcome to Shishiro Botan's Den, {}!\nPlease be sure to read the rules in {} and support our lion goddess Botan. ☀️"
    m = m.format(member.mention, r_ch.mention)

    ## get avatar and resize
    avatar_url = member.avatar_url
    av_img = Image.open(requests.get(avatar_url, stream=True).raw)
    av_img = av_img.resize((250, 250))

    ## draw a mask to crop the ellipse
    mask_im = Image.new("L", (250, 250), 0)
    draw = ImageDraw.Draw(mask_im)
    draw.ellipse((0, 0, 250, 250), fill=255)

    ## open background image, paste in the avatar and the cropping mask
    bg_file_name = "welcome_background.png"
    back_im = Image.open(os.path.join(img_dir, bg_file_name)).copy()
    back_im.paste(av_img, (385, 50), mask_im)    

    ## add fonts
    lg_ch = client.get_channel(d["discord_ids"]["log"])
    idraw = ImageDraw.Draw(back_im)

    font_name = "uni-sans.heavy-caps.otf"
    font_ttf = os.path.join(fonts_dir, font_name)

    welcome_font = ImageFont.truetype(font_ttf, size = 76)
    name_font = ImageFont.truetype(font_ttf, size = 37)
    count_font = ImageFont.truetype(font_ttf, size = 30)

    ## shadow layer
    shadow_fill = (0, 0, 0, 20)
    shadow_layer = Image.new('RGBA', back_im.size, (255,255,255,0))
    s_layer = ImageDraw.Draw(shadow_layer)

    ## write messages to image
    width, height = back_im.size
    fonts = (welcome_font, name_font, count_font)
    y_positions = (354, 406, 450)
    msgs = ("WELCOME", str(member).upper(), "{}th MEMBER!".format(member_count))

    for font, y_pos, msg in zip(fonts, y_positions, msgs):
        txt_w, txt_h = idraw.textsize(msg, font)
        pos = ((width-txt_w)/2, y_pos - txt_h/2)

        ## add shadow
        s_layer.text((pos[0] - 2, pos[1]), msg, font = font, fill = shadow_fill)
        s_layer.text((pos[0] + 3, pos[1]), msg, font = font, fill = shadow_fill)
        s_layer.text((pos[0], pos[1] - 3), msg, font = font, fill = shadow_fill)
        s_layer.text((pos[0], pos[1] + 2), msg, font = font, fill = shadow_fill)

        ## draw text over
        idraw.text(
            pos,
            msg,
            font = font,
            fill = (255, 255, 255, 255)
        )
    
    combined_im = Image.alpha_composite(back_im, shadow_layer)

    ## save image
    save_file = os.path.join(save_dir, str(random.randint(1,20)) + "wc_bg.png")
    combined_im.save(save_file)

    await wc_ch.send(m, file = discord.File(save_file))

    ## send member's join info to mods logs
    server_logs_ch = client.get_channel(d["discord_ids"]["server_log"])
    
    m = "{} {}".format(member.mention, str(member))

    embed = discord.Embed(title = "Member Joined", description = m, colour = 0xE2FAB5)
    embed.set_thumbnail(url = member.avatar_url)
    embed.add_field(name = "Account Creation Date", value = member.created_at, inline = False)
    embed.set_footer(text = "ID: {}".format(member.id))

    await server_logs_ch.send(content = None, embed = embed)

# On members leaving the server
@client.event
async def on_member_remove(member):
    # Only for botan server
    if member.guild.id != d["discord_ids"]["guild"]:
        return

    # Check if member is banned
    try:
        await member.guild.fetch_ban(member)
        return
    except discord.NotFound:
        pass

    ## send member's join info to mods logs
    server_logs_ch = client.get_channel(d["discord_ids"]["server_log"])
    
    t = "Member left the server"
    m = "{} {}".format(member.mention, str(member))

    embed = discord.Embed(title = t, description = m, colour = 0xFF6600)
    embed.set_thumbnail(url = member.avatar_url)
    embed.add_field(name = "Account Creation Date", value = member.created_at, inline = False)
    embed.set_footer(text = "ID: {}".format(member.id))

    await server_logs_ch.send(content = None, embed = embed)

# On members getting banned
@client.event
async def on_member_ban(guild, user):
    # Only for botan server
    if guild.id != d["discord_ids"]["guild"]:
        return

    ## send member's join info to mods logs
    server_logs_ch = client.get_channel(d["discord_ids"]["server_log"])
    
    t = "Member Banned"
    m = "{} {}".format(user.mention, str(user))

    embed = discord.Embed(title = t, description = m, colour = 0xFF0000)
    embed.set_thumbnail(url = user.avatar_url)
    embed.add_field(name = "Account Creation Date", value = user.created_at, inline = False)
    embed.set_footer(text = "ID: {}".format(user.id))

    await server_logs_ch.send(content = None, embed = embed)

# On members updating their profiles
@client.event
async def on_member_update(before, after):
    # If member has a role change (role added or deleted)
    if len(before.roles) != len(after.roles):
        old_roles = set(role.id for role in before.roles)
        new_roles = set(role.id for role in after.roles)
        # If member gets server booster (Lion Tamer) role
        if d["discord_ids"]["booster_role"] in (new_roles - old_roles) or 748842249030336542 in (new_roles - old_roles):
            # Send dm introducing the perks
            title = "New Lion Tamer"
            m = [
                "Thank you for boosting the server, {}!".format(after.name),
                " As a token of appreciation from us, you are now granted access to the top secret **Lion Tamer**'s role privileges!",
                " Here are some commands you may use in this DM channel with me (prefix not required):",
                "\n\n``nickname``: Change your nickname so I can refer to you differently!",
                "\n``role``: Create a custom color role for yourself in the server. Use the 'help role' command to for more information!",
                "\n``help``: I can do more things! Use this command to find out.",
                "\n\nStay tune for more exclusive features in the foreseeable future, and thanks again for your patronage!"
            ]
            m = "".join(m)
            
            embed = discord.Embed(title = title, description = m, colour = embed_color)
            embed.set_image(url = "https://pbs.twimg.com/media/Ef2UpVQXgAApSxP?format=jpg&name=large")
            embed.set_footer(text = "image taken from @Shuuzo3 Twitter")
            await after.send(content = None, embed = embed)
            return
        # If member loses Lion Tamer role
        elif d["discord_ids"]["booster_role"] in (old_roles - new_roles) or 748842249030336542 in (old_roles - new_roles):
            # Get booster data
            custom_role_id = db["boosters"].find_one({"id": after.id})["custom_role"]
            botan_guild = client.get_guild(d["discord_ids"]["guild"])

            # If custom role id is not -1, remove existing custom role
            if custom_role_id != -1:
                custom_role = botan_guild.get_role(custom_role_id)
                await custom_role.delete(reason = "{}'s lion tamer's subscription expired".format(str(after)))
                db["boosters"].update_one({"id": after.id}, {"$set": {"custom_role": -1}})          

            # Send dm informing the expiration
            title = "Lion Tamer's subscription expired"
            m = "Hi {}, I would like to inform you that your **Lion Tamer**'s role privileges have just expired.".format(booster_nickname(after))
            m += " You may renew this subscription by boosting the server again, but regardless of your decision, it has been great to have you with me!"
            m += " Thank you so much for your patronage!"
            embed = discord.Embed(title = title, description = m, colour = embed_color)
            await after.send(content = None, embed = embed)
            return   

# Coroutine Functions
async def jst_clock():
    while not client.is_closed():
        now = dtime.now(tz = timezone.utc) + timedelta(hours = 9)
        timestr = now.strftime("%H:%M JST, %d/%m/%Y")
        await client.change_presence(activity=discord.Game(name=timestr))
        await asyncio.sleep(60)        

"""stream data template
    "id": vid id,
    "title": vid title
    "status": "justlive", "live", "upcoming", "completed"
    "live_msg"
    "scheduled_start_time"
    "actual_start_time"
    "actual_end_time"
    "tag_count": 1
    "tags": {
        "0": {
            "author_id": author's id,
            "timestamp": datetime,
            "seconds": int
            "text": "loren itsum"
        },
        ...
    }
"""
async def update_streams():
    lg_ch = client.get_channel(d["discord_ids"]["log"])
    live_ch = client.get_channel(d["discord_ids"]["live_stream"])
    botan_guild = client.get_guild(d["discord_ids"]["guild"])
    stream_role_mention = botan_guild.get_role(d["discord_ids"]["stream_role"]).mention

    while not client.is_closed():
        now = dtime.now(tz = timezone.utc)
        # check live streams, see if any is finishing
        for vid in db["streams"].find({"status": "live"}):
            # get live vid data
            vid_id = vid["id"]
            vid_req = youtube.videos().list(
                part = "liveStreamingDetails,statistics",
                id = vid_id
            )
            vid_res = vid_req.execute()["items"][0]

            # if vid is ending, send message and update status to completed
            live_streaming_details = vid_res["liveStreamingDetails"]
            actual_end_time_str = live_streaming_details.get("actualEndTime", None)
            if actual_end_time_str or vid.get("end", None):
                actual_start_time_str = live_streaming_details["actualStartTime"]
                try:
                    actual_start_time = dtime.strptime(actual_start_time_str.split(".")[0], "%Y-%m-%dT%H:%M:%S").replace(tzinfo = timezone.utc)
                except:
                    actual_start_time = dtime.strptime(actual_start_time_str.split(".")[0], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo = timezone.utc)
                if vid.get("end", None):
                    actual_end_time = dtime.strptime(actual_end_time_str, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo = timezone.utc)
                else:
                    actual_end_time = None
                db["streams"].update_one({"id": vid_id}, {"$set": {
                    "status": "completed", 
                    "actual_start_time": actual_start_time,
                    "actual_end_time": actual_end_time
                }})

                # send an embed message
                embed = discord.Embed(description = "Live stream ended! You may refer to <#751210778278756375> for any tagged comments.", colour = embed_color)
                await live_ch.send(content = None, embed = embed)

                # unpin stream on ending
                live_msg = await live_ch.fetch_message(vid["live_msg"])
                await live_msg.unpin(reason = "Unpin stream after ended.")

                # process tags
                await process_tags(vid_id)
                continue

            # else, update live message statistics
            concurrent_viewers = live_streaming_details.get("concurrentViewers", 0)
            statistics = vid_res.get("statistics", None)
            if statistics:
                like_count = statistics.get("likeCount", 0)
                dislike_count = statistics.get("dislikeCount", 0)
                view_count = statistics.get("viewCount", 0)
            else:
                like_count, dislike_count, view_count = 0, 0, 0
            vid_url = "https://www.youtube.com/watch?v=" + vid_id
            m = "{} Botan is now live!\n```\nLive Views: {}\nTotal Views: {}\nLikes: {}\n Dislikes: {}\n```\nLink: {}"
            m = m.format(stream_role_mention, concurrent_viewers, view_count, like_count, dislike_count, vid_url)

            live_msg = await live_ch.fetch_message(vid["live_msg"])
            await live_msg.edit(content = m)

        # check upcoming streams, see if there's any live ones in 1 minute
        for vid in db["streams"].find({
            "$or": [
                {"status": "upcoming"},
                {"status": "justlive"}
            ]
        }):
            # if scheduled time's not reached, skip vid
            scheduled_start_time = vid["scheduled_start_time"].replace(tzinfo = timezone.utc)
            if now + timedelta(minutes = 1) < scheduled_start_time:
                continue
            await lg_ch.send("vid live! Starting operation")
            # if live, get live vid data
            vid_id = vid["id"]
            vid_req = youtube.videos().list(
                part = "liveStreamingDetails,statistics",
                id = vid_id
            )
            vid_res = vid_req.execute()["items"][0]
            await lg_ch.send("successfully received vid's data from youtube")

            # double confirm if the vid is live, else reschedule
            live_streaming_details = vid_res.get("liveStreamingDetails", None)
            await lg_ch.send(live_streaming_details)
            dt_string = live_streaming_details.get("scheduledStartTime", None)
            await lg_ch.send(dt_string)
            new_scheduled_time = dtime.strptime(dt_string, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo = timezone.utc)
            if new_scheduled_time > scheduled_start_time + timedelta(minutes = 1):
                db["streams"].update_one({"id": vid_id}, {"$set": {"scheduled_start_time": new_scheduled_time}})
                await lg_ch.send("{} has been rescheduled to {}".format(vid_id, new_scheduled_time))
                continue

            # send a message to stream channel announcing live 
            concurrent_viewers = live_streaming_details.get("concurrentViewers", 0)
            statistics = vid_res.get("statistics", None)
            if statistics:
                like_count = statistics.get("likeCount", 0)
                dislike_count = statistics.get("dislikeCount", 0)
                view_count = statistics.get("viewCount", 0)
            else:
                like_count, dislike_count, view_count = 0, 0, 0
            vid_url = "https://www.youtube.com/watch?v=" + vid_id
            m = "{} Botan is now live!\n```\nLive Views: {}\nTotal Viewss: {}\nLikes: {}\n Dislikes: {}\n```\nLink: {}"
            m = m.format(stream_role_mention, concurrent_viewers, view_count, like_count, dislike_count, vid_url)
            live_msg = await live_ch.send(m)
            await live_msg.pin(reason = "pin stream.")

            # add an embed notifying about tagging system
            embed = discord.Embed(description = "Tracking stream for tags! Please use ``$t`` to tag a comment.", colour = embed_color)
            await live_ch.send(content = None, embed = embed)

            # update the status to live, record message id
            db["streams"].update_one({"id": vid_id}, {"$set": {"status": "live", "live_msg": live_msg.id}})
            await lg_ch.send("{} is now live".format(vid_id))
        await asyncio.sleep(30)

async def find_streams():
    lg_ch = client.get_channel(d["discord_ids"]["log"])
    while not client.is_closed():
        # get data of last checked timestamp
        stream_check = db["settings"].find_one({"name": "stream"})
        last_checked = stream_check.get("last_checked", None)
        now = dtime.now(tz = timezone.utc)
        await lg_ch.send("Checking if live stream check is needed, time: {}".format(now))
        # if there is no last checked, or last checked is more than 1 hour ago, do new check
        if last_checked:
            # add utc to last checked (mongodb always naive)
            last_checked = last_checked.replace(tzinfo = timezone.utc)
        if not last_checked or (now - last_checked >= timedelta(hours = 1)):
            await lg_ch.send("Performing live stream check, last check was {}".format(last_checked))
            # check for live streams
            live_req = youtube.search().list(
                part = "snippet",
                channelId = botan_ch_id,
                eventType = "live",
                maxResults = 25,
                type = "video"
            )
            live_res = live_req.execute()["items"]
            for vid in live_res:
                vid_id = vid["id"]["videoId"]
                # check if vid already exists in database
                if db["streams"].find_one({"id": vid_id}):
                    continue
                # else store video's id, status and scheduled start time
                vid_req = youtube.videos().list(
                    part = "snippet,liveStreamingDetails",
                    id = vid_id
                )
                try:
                    vid_res = vid_req.execute()["items"][0]
                except:
                    continue

                title = vid_res["snippet"]["title"]

                dt_string = vid_res["liveStreamingDetails"]["scheduledStartTime"]
                scheduled_start_time = dtime.strptime(dt_string, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo = timezone.utc)

                vid_data = {
                    "id": vid_id,
                    "title": title,
                    "status": "justlive",
                    "scheduled_start_time": scheduled_start_time
                }
                db["streams"].insert_one(vid_data)
                await lg_ch.send("New live video logged!\n{}\n{}".format(vid_id, scheduled_start_time))

            # check for upcoming streams
            upcoming_req = youtube.search().list(
                part = "snippet",
                channelId = botan_ch_id,
                eventType = "upcoming",
                maxResults = 25,
                type = "video"
            )
            upcoming_res = upcoming_req.execute()["items"]
            for vid in upcoming_res:
                vid_id = vid["id"]["videoId"]
                # check if vid already exists in database
                if db["streams"].find_one({"id": vid_id}):
                    continue
                # else store video's id, status and scheduled start time
                vid_req = youtube.videos().list(
                    part = "snippet,liveStreamingDetails",
                    id = vid_id
                )
                try:
                    vid_res = vid_req.execute()["items"][0]
                except:
                    continue

                title = vid_res["snippet"]["title"]

                dt_string = vid_res["liveStreamingDetails"]["scheduledStartTime"]
                scheduled_start_time = dtime.strptime(dt_string, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo = timezone.utc)
                
                # if vid is already starting (completed), skip vid
                if now > scheduled_start_time:
                    continue

                vid_data = {
                    "id": vid_id,
                    "title": title,
                    "status": "upcoming",
                    "scheduled_start_time": scheduled_start_time
                }
                db["streams"].insert_one(vid_data)
                await lg_ch.send("New upcoming video logged!\n{}\n{}".format(vid_id, scheduled_start_time))            
            # add wait time
            db["settings"].update_one({"name": "stream"}, {"$set": {"last_checked": now}})
            wait_time = 3600
        else:
            # else wait for the remaining time left
            wait_time = 3600 - (now - last_checked).total_seconds()
            await lg_ch.send("Waiting for {} seconds from now for next check".format(wait_time))
        await asyncio.sleep(wait_time)

async def delete_expired_memberships():
    lg_ch = client.get_channel(d["discord_ids"]["log"])
    while not client.is_closed():
        # get data of last checked timestamp
        now = dtime.now(tz = timezone.utc)
        zoopass_check = db["settings"].find_one({"name": "zoopass"})
        last_checked = zoopass_check.get("last_checked", None)
        await lg_ch.send("Checking if **membership** check is needed, time: {}".format(now))
        # if there is no last checked, or last checked is more than 12 hours ago, do new check
        if last_checked:
            # add utc to last checked (mongodb always naive)
            last_checked = last_checked.replace(tzinfo = timezone.utc)
        if not last_checked or (now - last_checked >= timedelta(hours = 12)):
            await lg_ch.send("Performing membership check, last check was {}".format(last_checked))
            
            # perform check
            expired_memberships = await _check_membership_dates()
            m = ["{}: {}".format(d["id"], d["last_membership"]) for d in expired_memberships]
            m = "\n".join(m)
            if m:
                await lg_ch.send(m)

            # add wait time
            db["settings"].update_one({"name": "zoopass"}, {"$set": {"last_checked": now}})
            wait_time = 12 * 3600
            await lg_ch.send("Set new wait time to {}".format(now))
        else:
            # else wait for the remaining time left
            wait_time = 12 * 3600 - (now - last_checked).total_seconds()
            await lg_ch.send("Waiting for {} seconds from now for next **membership** check".format(wait_time))
        await asyncio.sleep(wait_time)

# List Coroutines to be executed
coroutines = (
    jst_clock(),
    update_streams(),
    find_streams(),
    delete_expired_memberships()
)

# Main Coroutine
async def background_main():
    await client.wait_until_ready()
    await asyncio.gather(*coroutines)

client.loop.create_task(background_main())
client.run(token)

