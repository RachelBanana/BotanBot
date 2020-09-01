# external libraries
import discord
from googletrans import Translator
from PIL import Image, ImageDraw, ImageFont
import googleapiclient.discovery
import requests

import pymongo
from pymongo import MongoClient

# python built-in libraries
import os
import sys
import re
import json
import random
import asyncio
from datetime import datetime as dtime
from datetime import timezone, timedelta
from collections import deque

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
guild_id = 740886590716510280
log_channel = 741908598870769735
dm_log_channel = 749264565958737930
pingcord = "Pingcord#3283"
tweets_ch = 740896881827381259
translated_tweets_ch = 741945787042496614
fanart_ch = 740888816268738630
booster_role = 741427676409233430
announcement_ch = 740887547651162211
welcome_ch = 740888968089829447
rules_ch = 740887522044805141
upcoming_news_channel = 749905915339210824

## database settings
db_url = "mongodb+srv://{}:{}@botan.lkk4p.mongodb.net/{}?retryWrites=true&w=majority"
db_name = "botanDB"
db_user = os.getenv("DB_USER")
db_pass = os.getenv("DB_PASS")
cluster = MongoClient(db_url.format(db_user, db_pass, db_name))

db = cluster[db_name]
db_artworks = db["artworks"]
db_settings = db["settings"]
db_boosters = db["boosters"]

counter = db_settings.find_one({"name": "counter"})

## youtube api settings
yt_key = os.getenv("YT_KEY")
botan_ch_id = os.getenv("BOTAN_CH_ID")
api_service_name = "youtube"
api_version = "v3"

youtube = googleapiclient.discovery.build(
    api_service_name, api_version, developerKey = yt_key)

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
with open("blacklist.json") as f:
    # set up blacklist
    blacklist = json.load(f)
with open("vtubers.json") as f:
    # set up vtubers information other than botan
    vtubers = json.load(f)
with open("voices.json") as f:
    # set up voice clips data
    voices_dict = json.load(f)
with open("help_booster.json") as f:
    # set up booster help doc
    booster_help_doc = json.load(f)

# Temporary storage for artworks (only urls)
temp_artwork_cursor = db_artworks.aggregate([{"$sample": {"size": 30}}])
temp_art_deque = deque()
temp_art_set = set()
for art in temp_artwork_cursor:
    temp_art_deque.append(art["url"])
    temp_art_set.add(art["url"])

# Utility Functions
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

## Time tools
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

## Translating tools
gtl = Translator()
def to_jap(m):
    return gtl.translate(m, dest = "ja")

def to_eng(m):
    return gtl.translate(m)

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

## Boosters utility tools
def booster_nickname(user):
    # if user is a booster and has a booster nickname, return nickname. 
    booster = db_boosters.find_one({"id": user.id})
    if booster and booster["nickname"]:
        return booster["nickname"]
    # else return guild nickname or user's name depending on the class type
    return user.nick if isinstance(user, discord.Member) else user.name

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
        for field in cmd_doc["extra_fields"]:
            field_msg = "\n".join(field["value"]) if isinstance(field["value"], list) else field["value"]
            embed.add_field(name = field["name"], value = field_msg, inline = False)
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

async def voice(res, msg):
    if not msg:
        msg = random.choice(list(voices_dict))
    v_file_name = random.choice(voices_dict[msg]["clips"])
    voice_file = os.path.join(voices_dir, v_file_name)
    await res.channel.send(voices_dict[msg]["quote"], file = discord.File(voice_file))

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
    db_settings.update_one({"name": "counter"}, {"$set": {"sleepy": counter["sleepy"]}})

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

### Youtube data commands
async def subscribers(res, msg):
    # Check which Vtuber channel to search for
    msg = msg.strip().lower()
    ch_id = botan_ch_id
    vtuber_name = "Shishiro Botan"

    if msg in vtubers:
        ch_id = vtubers[msg]["ch_id"]
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

    # Check which VTuber channel to search for
    msg = msg.strip().lower()
    ch_id = botan_ch_id
    vtuber_name = "Botan-sama"

    if msg in vtubers:
        ch_id = vtubers[msg]["ch_id"]
        vtuber_name = msg.capitalize()
    
    # Look for live streams
    live_req = youtube.search().list(
        part = "snippet",
        channelId = ch_id,
        eventType = "live",
        maxResults = 25,
        type = "video"
    )
    live_res = live_req.execute()["items"]
    if live_res:
        vid_id = live_res[0]["id"]["videoId"]
        vid_url = "https://www.youtube.com/watch?v=" + vid_id
        if vtuber_name == "Botan-sama":
            if random.randint(0,1):
                m = "Omg {} is live now!! What are you doing here??! Get over to the following link to send your red SC!\n{}"
            else:
                m = "Sorry, I am too busy watching {}'s live stream now. Find another free bot.\n{}"
        else:
            m = "{} is live now. Link here:\n{}"
        await res.channel.send(m.format(vtuber_name, vid_url))
        return

    # Look for upcoming streams
    req_list = youtube.search().list(
        part = "snippet",
        channelId = ch_id,
        eventType = "upcoming",
        maxResults = 25,
        type = "video"
    )
    res_list = req_list.execute()["items"]

    no_stream_msg  = "Sorry, {} doesn't have any scheduled live streams now!".format(vtuber_name)
    if not res_list:
        await res.channel.send(no_stream_msg)
        return

    stream_flag = False
    for vid in res_list:
        vid_id = vid["id"]["videoId"]
        req_vid = youtube.videos().list(
            part="liveStreamingDetails",
            id=vid_id
        )
        res_vid = req_vid.execute()
        dt_string = res_vid["items"][0]["liveStreamingDetails"]["scheduledStartTime"]
        d1 = dtime.strptime(dt_string,"%Y-%m-%dT%H:%M:%SZ").replace(tzinfo = timezone.utc)
        if dtime.now(tz = timezone.utc) > d1:
            continue
        stream_flag = True
        vid_url = "https://www.youtube.com/watch?v=" + vid_id
        timeleft = time_to_string(*time_until(d1))
        await res.channel.send("{} left until {}'s next stream! Link here:\n{}".format(timeleft, vtuber_name, vid_url))
    if not stream_flag:
        await res.channel.send(no_stream_msg)

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
        format_string = "JP¥{:,.2f}"
        amount = round(float(amount), 2)
    else:
        format_string = "JP¥{:,}"
        amount = int(amount)

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
    amount = format_string.format(amount).rstrip("0").rstrip(".")
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
    save_file = os.path.join(save_dir, str(random.randint(1,20)) + "sc.png")
    back_im.save(save_file)

    await res.channel.send(file = discord.File(save_file))

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
    new_art_url = list(db_artworks.aggregate([{"$sample": {"size": 1}}]))[0]["url"]
    while new_art_url in temp_art_set:
        new_art_url = list(db_artworks.aggregate([{"$sample": {"size": 1}}]))[0]["url"]
    temp_art_set.add(new_art_url)
    temp_art_deque.append(new_art_url)

## admin commands
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

### a test function to check how system messages work
async def system_read(res, msg):
    if not msg.isdigit():
        return
    ann_ch = client.get_channel(announcement_ch)
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

### database manipulation
async def add_art(res, msg):
    if db_artworks.find_one({"url": msg}):
        await res.channel.send("There's already an existing art with the same url!")
        return
    db_artworks.insert_one({"url": msg})
    await res.channel.send("Added one new artwork to database!")

async def del_art(res, msg):
    target_art = db_artworks.find_one({"url": msg})
    if not target_art:
        await res.channel.send("Can't find anything similar in the database!")
        return
    await res.channel.send("Found artwork, deleting now!")
    db_artworks.delete_one(target_art)
    await res.channel.send("Artwork successfully deleted.")
    pass

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
    if msg in booster_help_doc:
        cmd_doc = booster_help_doc[msg]
        embed = discord.Embed(title = "Lion Tamer's Help Menu: '{}' Command".format(msg), description = cmd_doc["desc"])
        for field in cmd_doc["extra_fields"]:
            field_msg = "\n".join(field["value"]) if isinstance(field["value"], list) else field["value"]
            embed.add_field(name = field["name"], value = field_msg, inline = False)
        embed.add_field(name = "Usage", value = cmd_doc["usage"])
        if cmd_doc["alias"]:
            embed.add_field(name = "Aliases", value = ", ".join(cmd_doc["alias"]))
    else:
        embed = discord.Embed(title = "Lion Tamer's Help Menu: Available Commands", description = "\n".join(booster_help_doc))
        embed.add_field(name = "More Help", value = "help {command name}")
    embed.colour = embed_color
    await res.channel.send(content = None, embed = embed)

async def new_booster_nickname(res, msg):
    if not msg:
        await res.channel.send("Your current nickname is {}. If you wish to change it, please provide an argument for the ``nickname`` command!".format(booster_nickname(res.author)))
        return
    db_boosters.update_one({"id": res.author.id}, {"$set": {"nickname": msg}})
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
    custom_role_id = db_boosters.find_one({"id": res.author.id})["custom_role"]
    botan_guild = client.get_guild(guild_id)
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
        db_boosters.update_one({"id": res.author.id}, {"$set": {"custom_role": custom_role_id}})
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
    custom_role_id = db_boosters.find_one({"id": res.author.id})["custom_role"]
    botan_guild = client.get_guild(guild_id)

    if custom_role_id == -1:
        await res.channel.send("You don't seem to own a custom role yet! Please contact an admin if otherwise!")
        return
    
    custom_role = botan_guild.get_role(custom_role_id)
    await custom_role.delete(reason = "{} requested a custom role deletion".format(str(res.author)))
    db_boosters.update_one({"id": res.author.id}, {"$set": {"custom_role": -1}})
    await res.channel.send("Role deletion successful! You may add a custom role again anytime you want.")

async def booster_news(res, msg):
    up_news_ch = client.get_channel(upcoming_news_channel)
    last_news = await up_news_ch.fetch_message(up_news_ch.last_message_id)
    embed =  last_news.embeds[0] if last_news.embeds else None
    await res.channel.send(content = last_news.content, embed = embed)

## hidden developer commands
async def cross_server_post(res, msg):
    if str(res.author) != owner:
        return
    m = msg.split("\n", 1)
    if len(m) < 2:
        await res.channel.send("Need at least {} more arguments!".format(2 - len(m)))
        return
    target_channel = client.get_channel(int(m[0]))
    await target_channel.send(m[1])

async def direct_dm(res, msg):
    if str(res.author) != owner:
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

async def mass_role_dm(res, msg):
    # currently only works with botan guild's roles
    botan_guild = client.get_guild(guild_id)

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

## command names
aliases = {
    "hi": "greet",
    "hello": "greet",
    "bday": "birthday",
    "trans": "translate",
    "jp": "japanese",
    "addart": "add_art",
    "delart": "del_art",
    "subs": "subscribers",
    "subscriber": "subscribers",
    "live": "stream",
    "v": "voice",
    "sc": "superchat"
}


commands = {
    "help": help_command,
    "greet": greet,
    "gao": gao,
    "debut": debut,
    "birthday": birthday,
    "translate": translate,
    "japanese": trans_to_jap,
    "meme": meme,
    "botan": botan_art,
    "100": score_me,
    "sleepy": sleepy,
    "subscribers": subscribers,
    "stream": live_streams,
    "voice": voice,
    "superchat": superchat
}

booster_commands = {
    "greet": greet,
    "nickname": new_booster_nickname,
    "role": new_booster_color_role,
    "news": booster_news,
    "help": booster_help,
    "delrole": del_booster_color_role
}

admin_commands = {
    "post": post,
    "read": read,
    "xread": system_read,
    "add_art": add_art,
    "del_art": del_art,
    # dev commands
    "xpost": cross_server_post,
    "xdm": direct_dm,
    "xroledm": mass_role_dm
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
            ann_ch = res.guild.get_channel(announcement_ch)

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
            booster_data = db_boosters.find_one({"id": res.author.id})
            if booster_data:
                booster_data["boosts_count"] += 1
                db_boosters.update_one({"id": res.author.id}, {"$set": {"boosts_count": booster_data["boosts_count"]}})
            else:
                booster_data = {
                    "id": res.author.id,
                    "nickname": "",
                    "boosts_count": 1,
                    "custom_role": -1
                }
                db_boosters.insert_one(booster_data)
            return

    # check if dm
    if isinstance(res.channel, discord.DMChannel):
        # log content to dm log channel for record
        dm_lg_ch = client.get_channel(dm_log_channel)
        await dm_lg_ch.send("{}\n{}".format(str(res.author),res.content))
        
        # get guild and author member info in botan guild
        botan_guild = client.get_guild(guild_id)
        author = botan_guild.get_member(res.author.id)

        # return if not nitro booster or owner
        if not (booster_role in (role.id for role in author.roles) or str(res.author) == owner):
            # if previous booster, use different message
            if db_boosters.find_one({"id": res.author.id}):
                m = "Hi {}! Thanks again for supporting me in the past!\n".format(booster_nickname(author))
                m += "I'm sorry but you need the Lion Tamer role again to use any of my commands here...*cries*"
            else:
                m = "*A horny person appears! Botan flees.*"
            await res.channel.send(m)
            return

        # get command and message text (don't need prefix)
        cmd, *msg = res.content.split(" ", 1)
        cmd = cmd.strip().lower()
        msg = msg[0] if msg else ""

        # change any command alias to original command name
        cmd = aliases.get(cmd, cmd)

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
    if any(True for ban_link in blacklist["ban_links"] if ban_link in res.content):
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
    if str(res.author) == pingcord and res.channel.id == tweets_ch:
        channel = client.get_channel(translated_tweets_ch)
        for embed in res.embeds:
            embed.title = to_eng(embed.title).text
            embed.description = to_eng(embed.description).text
            await channel.send(content = None, embed = embed)
        
    # if channel is fanart channel, automatically detects new tweets artwork.
    if res.channel.id == fanart_ch and not res.content.startswith(prefix):
        match = re.search(r"https://twitter.com/[a-zA-Z0-9_]+/status/[0-9]+", res.content)
        if match:
            await add_art(res, match.group())
        return

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
    
    # check for permission and if admin command exists, perform action
    if not res.author.guild_permissions.administrator:
        return
    action = admin_commands.get(cmd, None)
    if action:
        await action(res, msg)

# On members joining the server
@client.event
async def on_member_join(member):
    # welcome message (only for botan server)
    if member.guild.id != guild_id:
        return
    
    # get data for welcome message
    wc_ch = client.get_channel(welcome_ch)
    r_ch = client.get_channel(rules_ch)
    member_count  = member.guild.member_count
    m = "Paao~ Welcome to Shishiro Botan's Den, {}!\nPlease be sure to read the rules in {} and support our lion goddess Botan. ☀️"
    m = m.format(member.mention, r_ch.mention)

    # get avatar and resize
    avatar_url = member.avatar_url
    av_img = Image.open(requests.get(avatar_url, stream=True).raw)
    av_img = av_img.resize((250, 250))

    # draw a mask to crop the ellipse
    mask_im = Image.new("L", (250, 250), 0)
    draw = ImageDraw.Draw(mask_im)
    draw.ellipse((0, 0, 250, 250), fill=255)

    # open background image, paste in the avatar and the cropping mask
    bg_file_name = "welcome_background.png"
    back_im = Image.open(os.path.join(img_dir, bg_file_name)).copy()
    back_im.paste(av_img, (385, 50), mask_im)    

    # add fonts
    lg_ch = client.get_channel(log_channel)
    idraw = ImageDraw.Draw(back_im)

    font_name = "uni-sans.heavy-caps.otf"
    font_ttf = os.path.join(fonts_dir, font_name)

    welcome_font = ImageFont.truetype(font_ttf, size = 76)
    name_font = ImageFont.truetype(font_ttf, size = 37)
    count_font = ImageFont.truetype(font_ttf, size = 30)

    # shadow layer
    shadow_fill = (0, 0, 0, 20)
    shadow_layer = Image.new('RGBA', back_im.size, (255,255,255,0))
    s_layer = ImageDraw.Draw(shadow_layer)

    # write messages to image
    width, height = back_im.size
    fonts = (welcome_font, name_font, count_font)
    y_positions = (354, 406, 450)
    msgs = ("WELCOME", str(member).upper(), "{}th MEMBER!".format(member_count))

    for font, y_pos, msg in zip(fonts, y_positions, msgs):
        txt_w, txt_h = idraw.textsize(msg, font)
        pos = ((width-txt_w)/2, y_pos - txt_h/2)

        # add shadow
        s_layer.text((pos[0] - 2, pos[1]), msg, font = font, fill = shadow_fill)
        s_layer.text((pos[0] + 3, pos[1]), msg, font = font, fill = shadow_fill)
        s_layer.text((pos[0], pos[1] - 3), msg, font = font, fill = shadow_fill)
        s_layer.text((pos[0], pos[1] + 2), msg, font = font, fill = shadow_fill)

        # draw text over
        idraw.text(
            pos,
            msg,
            font = font,
            fill = (255, 255, 255, 255)
        )
    
    combined_im = Image.alpha_composite(back_im, shadow_layer)

    # save image
    save_file = os.path.join(save_dir, str(random.randint(1,20)) + "wc_bg.png")
    combined_im.save(save_file)

    await wc_ch.send(m, file = discord.File(save_file))

# On members updating their profiles
@client.event
async def on_member_update(before, after):
    # If member has a role change (role added or deleted)
    if len(before.roles) != len(after.roles):
        old_roles = set(role.id for role in before.roles)
        new_roles = set(role.id for role in after.roles)
        # If member gets server booster (Lion Tamer) role
        if booster_role in (new_roles - old_roles) or 748842249030336542 in (new_roles - old_roles):
            # Send dm introducing the perks
            title = "New Lion Tamer"
            m = [
                "Thank you for boosting the server, {}!".format(after.name),
                " As a token of appreciation from us, you are now granted access to the top secret **Lion Tamer**'s role privileges!",
                " Here are some commands you may use in this DM channel with me (prefix not required):",
                "\n\n``nickname``: Change your nickname so I can refer to you differently!",
                "\n``role``: Create a custom color role for yourself in the server. Use the 'help role' command to for more information!",
                "\n``news``: Sneak peek on any upcoming events, server updates that are yet to be announced to the public!",
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
        elif booster_role in (old_roles - new_roles) or 748842249030336542 in (old_roles - new_roles):
            # Get booster data
            custom_role_id = db_boosters.find_one({"id": after.id})["custom_role"]
            botan_guild = client.get_guild(guild_id)

            # If custom role id is not -1, remove existing custom role
            if custom_role_id != -1:
                custom_role = botan_guild.get_role(custom_role_id)
                await custom_role.delete(reason = "{}'s lion tamer's subscription expired".format(str(after)))
                db_boosters.update_one({"id": after.id}, {"$set": {"custom_role": -1}})          

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

# List Coroutines to be executed
coroutines = (
    jst_clock()
)

# Main Coroutine
async def background_main():
    await client.wait_until_ready()
    await asyncio.gather(coroutines)

client.loop.create_task(background_main())
client.run(token)

