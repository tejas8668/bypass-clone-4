from pymongo import MongoClient
from pyrogram import Client, filters
from pyrogram import Client, filters
from pyrogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    BotCommand,
    Message,
    CallbackQuery,
)
from os import environ, remove
from threading import Thread
from json import load
from re import search

from texts import HELP_TEXT
import bypasser
import freewall
from time import time
from db import DB
import requests
from datetime import datetime, timedelta
import os
import urllib.parse
import logging

# Add this at the top of the file
VERIFICATION_REQUIRED = os.getenv('VERIFICATION_REQUIRED', 'true').lower() == 'true'

admin_ids = [6025969005, 6018060368]

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


# MongoDB connection
MONGO_URI = os.getenv('MONGO_URI')  # Get MongoDB URI from environment variables
client = MongoClient(MONGO_URI)
db = client['terabox_bot']
users_collection = db['users']

# bot
with open("config.json", "r") as f:
    DATA: dict = load(f)


def getenv(var):
    return environ.get(var) or DATA.get(var, None)


bot_token = getenv("TOKEN")
api_hash = getenv("HASH")
api_id = getenv("ID")
app = Client("my_bot", api_id=api_id, api_hash=api_hash, bot_token=bot_token)
with app:
    app.set_bot_commands(
        [
            BotCommand("start", "Welcome Message"),
            BotCommand("help", "List of All Supported Sites"),
        ]
    )

# DB
db_api = getenv("DB_API")
db_owner = getenv("DB_OWNER")
db_name = getenv("DB_NAME")
try: database = DB(api_key=db_api, db_owner=db_owner, db_name=db_name)
except: 
    print("Database is Not Set")
    database = None


# handle index
def handleIndex(ele: str, message: Message, msg: Message):
    result = bypasser.scrapeIndex(ele)
    try:
        app.delete_messages(message.chat.id, msg.id)
    except:
        pass
    if database and result: database.insert(ele, result)
    for page in result:
        app.send_message(
            message.chat.id,
            page,
            reply_to_message_id=message.id,
            disable_web_page_preview=True,
        )


# loop thread
def loopthread(message: Message, otherss=False):

    urls = []
    if otherss:
        texts = message.caption
    else:
        texts = message.text

    if texts in [None, ""]:
        return
    for ele in texts.split():
        if "http://" in ele or "https://" in ele:
            urls.append(ele)
    if len(urls) == 0:
        return

    if bypasser.ispresent(bypasser.ddl.ddllist, urls[0]):
        msg: Message = app.send_message(
            message.chat.id, "⚡ __generating...__", reply_to_message_id=message.id
        )
    elif freewall.pass_paywall(urls[0], check=True):
        msg: Message = app.send_message(
            message.chat.id, "🕴️ __jumping the wall...__", reply_to_message_id=message.id
        )
    else:
        if "https://olamovies" in urls[0] or "https://psa.wf/" in urls[0]:
            msg: Message = app.send_message(
                message.chat.id,
                "⏳ __this might take some time...__",
                reply_to_message_id=message.id,
            )
        else:
            msg: Message = app.send_message(
                message.chat.id, "🔎 __bypassing...__", reply_to_message_id=message.id
            )

    strt = time()
    links = ""
    temp = None

    for ele in urls:
        if database: df_find = database.find(ele)
        else: df_find = None
        if df_find:
            print("Found in DB")
            temp = df_find
        elif search(r"https?:\/\/(?:[\w.-]+)?\.\w+\/\d+:", ele):
            handleIndex(ele, message, msg)
            return
        elif bypasser.ispresent(bypasser.ddl.ddllist, ele):
            try:
                temp = bypasser.ddl.direct_link_generator(ele)
            except Exception as e:
                temp = "**Error**: " + str(e)
        elif freewall.pass_paywall(ele, check=True):
            freefile = freewall.pass_paywall(ele)
            if freefile:
                try:
                    app.send_document(
                        message.chat.id, freefile, reply_to_message_id=message.id
                    )
                    remove(freefile)
                    app.delete_messages(message.chat.id, [msg.id])
                    return
                except:
                    pass
            else:
                app.send_message(
                    message.chat.id, "__Failed to Jump", reply_to_message_id=message.id
                )
        else:
            try:
                temp = bypasser.shortners(ele)
            except Exception as e:
                temp = "**Error**: " + str(e)

        print("bypassed:", temp)
        if temp != None:
            if (not df_find) and ("http://" in temp or "https://" in temp) and database:
                print("Adding to DB")
                database.insert(ele, temp)
            links = links + temp + "\n"

    end = time()
    print("Took " + "{:.2f}".format(end - strt) + "sec")

    if otherss:
        try:
            app.send_photo(
                message.chat.id,
                message.photo.file_id,
                f"__{links}__",
                reply_to_message_id=message.id,
            )
            app.delete_messages(message.chat.id, [msg.id])
            return
        except:
            pass

    try:
        final = []
        tmp = ""
        for ele in links.split("\n"):
            tmp += ele + "\n"
            if len(tmp) > 4000:
                final.append(tmp)
                tmp = ""
        final.append(tmp)
        app.delete_messages(message.chat.id, msg.id)
        tmsgid = message.id
        for ele in final:
            tmsg = app.send_message(
                message.chat.id,
                f"__{ele}__",
                reply_to_message_id=tmsgid,
                disable_web_page_preview=True,
            )
            tmsgid = tmsg.id
    except Exception as e:
        app.send_message(
            message.chat.id,
            f"__Failed to Bypass : {e}__",
            reply_to_message_id=message.id,
        )


# start command
@app.on_message(filters.command(["start"]))
async def send_start(client: Client, message: Message):
    user = message.from_user

    # Check if the start command includes a token (for verification)
    if message.command and len(message.command) > 1:
        token = message.command[1]
        user_data = users_collection.find_one({"user_id": user.id, "token": token})

        if user_data:
            # Update the user's verification status
            users_collection.update_one(
                {"user_id": user.id},
                {"$set": {"verified_until": datetime.now() + timedelta(days=1)}},
                upsert=True
            )
            await message.reply_text(
                "✅ **Verification Successful!**\n\n"
                "You can now use the bot for the next 24 hours without any ads or restrictions."
            )
        else:
            await message.reply_text(
                "❌ **Invalid Token!**\n\n"
                "Please try verifying again."
            )
        return
    
    # If no token, send the welcome message and store user ID in MongoDB
    users_collection.update_one(
        {"user_id": user.id},
        {"$set": {"username": user.username, "first_name": user.first_name, "last_name": user.last_name}},
        upsert=True
    )
    await app.send_message(
        message.chat.id,
        f"__👋 Hi **{message.from_user.mention}**, I am Link Bypasser Bot. Just send me any supported links and I will get you results.\nCheckout /help to read more.__",
        reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "Request New Sites",
                        url="https://t.me/Assistant_24_7_bot",
                    )
                ],
                [
                    InlineKeyboardButton(
                        "Supported Sites",
                        callback_data="send_help",
                    )
                ],
                [
                    InlineKeyboardButton(
                        "Dev Channel",
                        url="https://t.me/+WaXaosFDkGowYjI1",
                    )
                ],
            ]
        ),
        reply_to_message_id=message.id,
    )                


# help command
@app.on_message(filters.command(["help"]))
def send_help(
    client: Client,
    message: Message,
):
    app.send_message(
        message.chat.id,
        HELP_TEXT,
        reply_to_message_id=message.id,
        disable_web_page_preview=True,
    )

# stats command
@app.on_message(filters.command(["stats"]))
async def stats(client: Client, message: Message):
    if message.from_user.id in admin_ids:
        try:
            # Get total users
            total_users = users_collection.count_documents({})

            # Get MongoDB database stats
            db_stats = db.command("dbstats")

            # Calculate used storage
            used_storage_mb = db_stats['dataSize'] / (1024 ** 2)  # Convert bytes to MB

            # Total MongoDB storage
            total_storage_mb = 512  # Total MongoDB storage in MB
            free_storage_mb = total_storage_mb - used_storage_mb

            # Prepare the response message
            message_text = (
                f"📊 **Bot Statistics**\n\n"
                f"👥 **Total Users:** {total_users}\n"
                f"💾 **MongoDB Used Storage:** {used_storage_mb:.2f} MB\n"
                f"🆓 **MongoDB Free Storage:** {free_storage_mb:.2f} MB\n"
            )

            await message.reply_text(message_text)
        except Exception as e:
            logger.error(f"Error fetching stats: {e}")
            await message.reply_text("❌ An error occurred while fetching stats.")
    else:
        await message.reply_text("You have no rights to use my commands.")

# callback query handler
@app.on_callback_query(filters.regex("send_help"))
def callback_help(client: Client, callback_query: CallbackQuery):
    callback_query.message.edit_text(
        HELP_TEXT,
        disable_web_page_preview=True,
    )

# Define the /broadcast command handler
@app.on_message(filters.command(["broadcast"]))
async def broadcast(client: Client, message: Message):
    if message.from_user.id in admin_ids:
        reply_message = message.reply_to_message
        if reply_message:
            # Fetch all user IDs from MongoDB
            all_users = users_collection.find({}, {"user_id": 1})
            total_users = users_collection.count_documents({})
            sent_count = 0
            block_count = 0
            fail_count = 0

            for user_data in all_users:
                user_id = user_data['user_id']
                try:
                    if reply_message.photo:
                        await client.send_photo(chat_id=user_id, photo=reply_message.photo.file_id, caption=reply_message.caption)
                    elif reply_message.video:
                        await client.send_video(chat_id=user_id, video=reply_message.video.file_id, caption=reply_message.caption)
                    else:
                        await client.send_message(chat_id=user_id, text=reply_message.text)
                    sent_count += 1
                except Exception as e:
                    if 'blocked' in str(e):
                        block_count += 1
                    else:
                        fail_count += 1

            await message.reply_text(
                f"Broadcast completed!\n\n"
                f"Total users: {total_users}\n"
                f"Messages sent: {sent_count}\n"
                f"Users blocked the bot: {block_count}\n"
                f"Failed to send messages: {fail_count}"
            )
        else:
            await message.reply_text("Please reply to a message with /broadcast to send it to all users.")
    else:
        await message.reply_text("You have no rights to use my commands.")
        
# links
@app.on_message(filters.text)
async def receive(client: Client, message: Message):
    user = message.from_user

    # Check if user is admin
    if user.id in admin_ids:
        # Admin does not need verification
        pass
    else:
        # User needs verification
        if not await check_verification(user.id):
            # User needs to verify
            btn = [
                [InlineKeyboardButton("Verify", url=await get_token(user.id, (await client.get_me()).username))],
                [InlineKeyboardButton("How To Open Link & Verify", url="https://t.me/how_to_download_0011")]
            ]
            await message.reply_text(
                text="🚨 Token Expired!\n\n"
                     "Timeout: 24 hours\n\n"
                     "Your access token has expired. Verify it to continue using the bot!\n\n"
                     "🔑 Why Tokens?\n\n"
                     "Tokens unlock premium features with a quick ad process. Enjoy 24 hours of uninterrupted access! 🌟\n\n"
                     "👉 Tap below to verify your token.\n\n"
                     "Thank you for your support! ❤️",
                reply_markup=InlineKeyboardMarkup(btn)
            )
            return
    # Proceed with the bypass process
    bypass = Thread(target=lambda: loopthread(message), daemon=True)
    bypass.start()

async def check_verification(user_id: int) -> bool:
    user = users_collection.find_one({"user_id": user_id})
    if user and user.get("verified_until", datetime.min) > datetime.now():
        return True
    return False

async def get_token(user_id: int, bot_username: str) -> str:
    # Generate a random token
    token = os.urandom(16).hex()
    # Update user's verification status in database
    users_collection.update_one(
        {"user_id": user_id},
        {"$set": {"token": token, "verified_until": datetime.min}},  # Reset verified_until to min
        upsert=True
    )
    # Create verification link
    verification_link = f"https://telegram.me/{bot_username}?start={token}"
    # Shorten verification link using shorten_url_link function
    shortened_link = shorten_url_link(verification_link)
    return shortened_link

def shorten_url_link(url):
    api_url = 'https://arolinks.com/api'
    api_key = '90bcb2590cca0a2b438a66e178f5e90fea2dc8b4'
    params = {
        'api': api_key,
        'url': url
    }
    # Yahan pe custom certificate bundle ka path specify karo
    response = requests.get(api_url, params=params, verify=False)
    if response.status_code == 200:
        data = response.json()
        if data['status'] == 'success':
            logger.info(f"Adrinolinks shortened URL: {data['shortenedUrl']}")
            return data['shortenedUrl']
    logger.error(f"Failed to shorten URL with Adrinolinks: {url}")
    return url


# stats command
@app.on_message(filters.command(["stats"]))
async def stats(client: Client, message: Message):
    if message.from_user.id in admin_ids:
        try:
            # Get total users
            total_users = users_collection.count_documents({})

            # Get MongoDB database stats
            db_stats = db.command("dbstats")

            # Calculate used storage
            used_storage_mb = db_stats['dataSize'] / (1024 ** 2)  # Convert bytes to MB

            # Calculate total and free storage (if available)
            if 'fsTotalSize' in db_stats:
                total_storage_mb = db_stats['fsTotalSize'] / (1024 ** 2)  # Convert bytes to MB
                free_storage_mb = total_storage_mb - used_storage_mb
            else:
                total_storage_mb = "N/A"
                free_storage_mb = "N/A"

            # Prepare the response message
            message_text = (
                f"📊 **Bot Statistics**\n\n"
                f"👥 **Total Users:** {total_users}\n"
                f"💾 **MongoDB Used Storage:** {used_storage_mb:.2f} MB\n"
                f"🆓 **MongoDB Free Storage:** {free_storage_mb if isinstance(free_storage_mb, str) else f'{free_storage_mb:.2f} MB'}\n"
            )

            await message.reply_text(message_text)
        except Exception as e:
            logger.error(f"Error fetching stats: {e}")
            await message.reply_text("❌ An error occurred while fetching stats.")
    else:
        await message.reply_text("You have no rights to use my commands.")
        
# doc thread
def docthread(message: Message):
    msg: Message = app.send_message(
        message.chat.id, "🔎 __bypassing...__", reply_to_message_id=message.id
    )
    print("sent DLC file")
    file = app.download_media(message)
    dlccont = open(file, "r").read()
    links = bypasser.getlinks(dlccont)
    app.edit_message_text(
        message.chat.id, msg.id, f"__{links}__", disable_web_page_preview=True
    )
    remove(file)


# files
@app.on_message([filters.document, filters.photo, filters.video])
def docfile(
    client: Client,
    message: Message,
):

    try:
        if message.document.file_name.endswith("dlc"):
            bypass = Thread(target=lambda: docthread(message), daemon=True)
            bypass.start()
            return
    except:
        pass

    bypass = Thread(target=lambda: loopthread(message, True), daemon=True)
    bypass.start()


# server loop
print("Bot Starting")
app.run()
