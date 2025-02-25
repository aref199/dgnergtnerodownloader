import os
import time
import sqlite3
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackQueryHandler, CallbackContext
from pytube import YouTube
import random
import string
import requests
from instaloader import Instaloader, Post
import tweepy
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
import deezer
from tiktok_downloader import TikTokDownloader

# تنظیمات اولیه
TOKEN = 'x'
ADMIN_ID = x
REQUIRED_CHANNEL = '@x'

# تنظیمات API های مختلف
SPOTIFY_CLIENT_ID = 'YOUR_SPOTIFY_CLIENT_ID'
SPOTIFY_CLIENT_SECRET = 'YOUR_SPOTIFY_CLIENT_SECRET'
TWITTER_API_KEY = 'YOUR_TWITTER_API_KEY'
TWITTER_API_SECRET = 'YOUR_TWITTER_API_SECRET'
TWITTER_ACCESS_TOKEN = 'YOUR_TWITTER_ACCESS_TOKEN'
TWITTER_ACCESS_TOKEN_SECRET = 'YOUR_TWITTER_ACCESS_TOKEN_SECRET'

# ایجاد اتصال به دیتابیس
conn = sqlite3.connect('bot_database.db')
cursor = conn.cursor()

# ایجاد جداول مورد نیاز
cursor.execute('''CREATE TABLE IF NOT EXISTS users
                  (user_id INTEGER PRIMARY KEY, username TEXT, downloads INTEGER, last_download TIMESTAMP)''')
cursor.execute('''CREATE TABLE IF NOT EXISTS banned_users
                  (user_id INTEGER PRIMARY KEY)''')
cursor.execute('''CREATE TABLE IF NOT EXISTS settings
                  (key TEXT PRIMARY KEY, value TEXT)''')
conn.commit()

# تنظیمات پیش‌فرض
default_settings = {
    'welcome_message': 'به ربات دانلود چند منظوره خوش آمدید!',
    'bot_active': 'True',
    'save_files': 'True',
    'custom_caption': ''
}

for key, value in default_settings.items():
    cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (key, value))
conn.commit()

def get_setting(key):
    cursor.execute("SELECT value FROM settings WHERE key=?", (key,))
    result = cursor.fetchone()
    return result[0] if result else None

def set_setting(key, value):
    cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
    conn.commit()

def is_admin(user_id):
    return user_id == ADMIN_ID

def is_banned(user_id):
    cursor.execute("SELECT * FROM banned_users WHERE user_id=?", (user_id,))
    return cursor.fetchone() is not None

def check_membership(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    chat_member = context.bot.get_chat_member(chat_id=REQUIRED_CHANNEL, user_id=user_id)
    return chat_member.status in ['member', 'administrator', 'creator']

def generate_captcha():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

def start(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    if is_banned(user_id):
        update.message.reply_text("شما از استفاده از این ربات محروم شده‌اید.")
        return

    if not check_membership(update, context):
        keyboard = [[InlineKeyboardButton("عضویت در کانال", url=f"https://t.me/{REQUIRED_CHANNEL[1:]}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        update.message.reply_text("لطفا ابتدا در کانال ما عضو شوید:", reply_markup=reply_markup)
        return

    welcome_message = get_setting('welcome_message')
    update.message.reply_text(welcome_message)

def process_link(update: Update, context: CallbackContext):
    if get_setting('bot_active') != 'True':
        update.message.reply_text("ربات در حال حاضر غیرفعال است.")
        return

    user_id = update.effective_user.id
    if is_banned(user_id):
        update.message.reply_text("شما از استفاده از این ربات محروم شده‌اید.")
        return

    if not check_membership(update, context):
        keyboard = [[InlineKeyboardButton("عضویت در کانال", url=f"https://t.me/{REQUIRED_CHANNEL[1:]}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        update.message.reply_text("لطفا ابتدا در کانال ما عضو شوید:", reply_markup=reply_markup)
        return

    captcha = generate_captcha()
    context.user_data['captcha'] = captcha
    update.message.reply_text(f"لطفا این کد را وارد کنید: {captcha}")

def process_captcha(update: Update, context: CallbackContext):
    user_captcha = update.message.text
    if 'captcha' not in context.user_data or user_captcha != context.user_data['captcha']:
        new_captcha = generate_captcha()
        context.user_data['captcha'] = new_captcha
        update.message.reply_text(f"کد اشتباه است. لطفا این کد جدید را وارد کنید: {new_captcha}")
        return

    del context.user_data['captcha']
    update.message.reply_text("لطفا لینک مورد نظر را ارسال کنید.")

def download_content(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    cursor.execute("SELECT downloads, last_download FROM users WHERE user_id=?", (user_id,))
    result = cursor.fetchone()
    
    if result:
        downloads, last_download = result
        if downloads >= 60 and (datetime.now() - datetime.fromisoformat(last_download)).days < 1:
            update.message.reply_text("شما به محدودیت دانلود روزانه رسیده‌اید. لطفا فردا دوباره تلاش کنید.")
            return
    else:
        cursor.execute("INSERT INTO users (user_id, downloads, last_download) VALUES (?, 0, ?)", (user_id, datetime.now().isoformat()))
        conn.commit()

    if (datetime.now() - context.user_data.get('last_download', datetime.min)).total_seconds() < 15:
        update.message.reply_text("لطفا 15 ثانیه بین هر دانلود صبر کنید.")
        return

    url = update.message.text
    progress_message = update.message.reply_text("در حال پردازش لینک...")
    
    try:
        if 'youtube.com' in url or 'youtu.be' in url:
            download_youtube(update, context, url, progress_message)
        elif 'instagram.com' in url:
            download_instagram(update, context, url, progress_message)
        elif 'twitter.com' in url or 'x.com' in url:
            download_twitter(update, context, url, progress_message)
        elif 'spotify.com' in url:
            download_spotify(update, context, url, progress_message)
        elif 'deezer.com' in url:
            download_deezer(update, context, url, progress_message)
        elif 'soundcloud.com' in url:
            download_soundcloud(update, context, url, progress_message)
        elif 'tiktok.com' in url:
            download_tiktok(update, context, url, progress_message)
        else:
            update.message.reply_text("لینک نامعتبر است. لطفا لینک معتبر از پلتفرم‌های پشتیبانی شده ارسال کنید.")
            return

        cursor.execute("UPDATE users SET downloads = downloads + 1, last_download = ? WHERE user_id = ?", (datetime.now().isoformat(), user_id))
        conn.commit()
        context.user_data['last_download'] = datetime.now()

    except Exception as e:
        error_message = f"خطا در دانلود محتوا: {str(e)}"
        update.message.reply_text(error_message)
        report_button = InlineKeyboardButton("گزارش خطا", callback_data="report_error")
        reply_markup = InlineKeyboardMarkup([[report_button]])
        update.message.reply_text("آیا می‌خواهید این خطا را گزارش دهید؟", reply_markup=reply_markup)

def download_youtube(update: Update, context: CallbackContext, url, progress_message):
    try:
        yt = YouTube(url)
        title = yt.title
        caption = yt.description

        keyboard = [
            [InlineKeyboardButton("کیفیت پایین", callback_data="yt_low"),
             InlineKeyboardButton("کیفیت متوسط", callback_data="yt_medium"),
             InlineKeyboardButton("کیفیت بالا", callback_data="yt_high")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        progress_message.edit_text(f"لطفا کیفیت دانلود را انتخاب کنید:\n\nعنوان: {title}", reply_markup=reply_markup)

        context.user_data['yt_url'] = url
        context.user_data['yt_caption'] = caption

    except Exception as e:
        raise Exception(f"خطا در دانلود ویدیو یوتیوب: {str(e)}")

def download_instagram(update: Update, context: CallbackContext, url, progress_message):
    try:
        L = Instaloader()
        post = Post.from_shortcode(L.context, url.split("/")[-2])
        
        if post.is_video:
            video_url = post.video_url
            progress_message.edit_text("در حال دانلود ویدیو از اینستاگرام...")
            context.bot.send_video(chat_id=update.effective_chat.id, video=video_url, caption=post.caption)
        else:
            photo_url = post.url
            progress_message.edit_text("در حال دانلود تصویر از اینستاگرام...")
            context.bot.send_photo(chat_id=update.effective_chat.id, photo=photo_url, caption=post.caption)
        
        progress_message.delete()
    except Exception as e:
        raise Exception(f"خطا در دانلود از اینستاگرام: {str(e)}")

def download_twitter(update: Update, context: CallbackContext, url, progress_message):
    try:
        auth = tweepy.OAuthHandler(TWITTER_API_KEY, TWITTER_API_SECRET)
        auth.set_access_token(TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_TOKEN_SECRET)
        api = tweepy.API(auth)

        tweet_id = url.split("/")[-1]
        tweet = api.get_status(tweet_id, tweet_mode="extended")

        if 'media' in tweet.entities:
            media = tweet.entities['media'][0]
            media_url = media['media_url']
            
            if media['type'] == 'photo':
                progress_message.edit_text("در حال دانلود تصویر از توییتر...")
                context.bot.send_photo(chat_id=update.effective_chat.id, photo=media_url, caption=tweet.full_text)
            elif media['type'] == 'video':
                video_info = media['video_info']
                video_url = video_info['variants'][0]['url']
                progress_message.edit_text("در حال دانلود ویدیو از توییتر...")
                context.bot.send_video(chat_id=update.effective_chat.id, video=video_url, caption=tweet.full_text)
        else:
            update.message.reply_text(tweet.full_text)
        
        progress_message.delete()
    except Exception as e:
        raise Exception(f"خطا در دانلود از توییتر: {str(e)}")

def download_spotify(update: Update, context: CallbackContext, url, progress_message):
    try:
        sp = spotipy.Spotify(auth_manager=SpotifyClientCredentials(client_id=SPOTIFY_CLIENT_ID, client_secret=SPOTIFY_CLIENT_SECRET))
        
        if 'track' in url:
            track = sp.track(url)
            preview_url = track['preview_url']
            if preview_url:
                progress_message.edit_text("در حال دانلود پیش‌نمایش آهنگ از اسپاتیفای...")
                context.bot.send_audio(chat_id=update.effective_chat.id, audio=preview_url, title=track['name'], performer=track['artists'][0]['name'])
            else:
                update.message.reply_text("پیش‌نمایش این آهنگ در دسترس نیست.")
        else:
            update.message.reply_text("لطفاً لینک یک آهنگ اسپاتیفای را ارسال کنید.")
        
        progress_message.delete()
    except Exception as e:
        raise Exception(f"خطا در دانلود از اسپاتیفای: {str(e)}")

def download_deezer(update: Update, context: CallbackContext, url, progress_message):
    try:
        client = deezer.Client()
        track_id = url.split('/')[-1]
        track = client.get_track(track_id)
        preview_url = track.preview
        progress_message.edit_text("در حال دانلود پیش‌نمایش آهنگ از دیزر...")
        context.bot.send_audio(chat_id=update.effective_chat.id, audio=preview_url, title=track.title, performer=track.artist.name)
        progress_message.delete()
    except Exception as e:
        raise Exception(f"خطا در دانلود از دیزر: {str(e)}")

def download_soundcloud(update: Update, context: CallbackContext, url, progress_message):
    # برای دانلود از ساندکلاود نیاز به API خاصی است که در اینجا پیاده‌سازی ن
