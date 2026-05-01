import os
import re
import yt_dlp
import requests
import json
import glob
import shutil
import asyncio
from instaloader import Instaloader, Post
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto, ReactionTypeEmoji
from telegram.ext import ApplicationBuilder, MessageHandler, CallbackQueryHandler, ContextTypes, filters, CommandHandler

TOKEN = os.getenv("TOKEN")
OWNER_ID = 5057151278
LOADING_GIF = "CgACAgUAAxkBAAIBMGnz9xZHqMJ7lsjGCWNW7dPgCjmEAAJkHwAC56SgV_m6bQ8dFShxOwQ"
EFFECT_ID = "5159385139981059251"

url_regex = re.compile(r'https?://')
loader = Instaloader(download_video_thumbnails=False, save_metadata=False, post_metadata_txt_pattern='')

IG_USERNAME = os.getenv("IG_USERNAME")
IG_PASSWORD = os.getenv("IG_PASSWORD")

try:
    if IG_USERNAME and IG_PASSWORD:
        loader.login(IG_USERNAME, IG_PASSWORD)
except Exception as e:
    print("فشل تسجيل الدخول ❌", e)

class TikTokDownloader:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        self.api_url = "https://tikwm.com/api/"

    def get_data(self, url: str):
        try:
            response = self.session.get(self.api_url, params={"url": url}, timeout=15)
            response.raise_for_status()
            data = response.json()
            if data.get('code') == 0:
                return data.get('data')
            return None
        except Exception as e:
            print(f"خطأ في جلب بيانات تيك توك: {e}")
            return None

    def download_file(self, file_url: str, filename: str):
        try:
            resp = self.session.get(file_url, stream=True, timeout=30)
            resp.raise_for_status()
            with open(filename, 'wb') as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    f.write(chunk)
            return True
        except Exception as e:
            print(f"خطأ في تحميل ملف تيك توك: {e}")
            return False

tiktok_downloader = TikTokDownloader()

def fix_tiktok_url(url):
    try:
        r = requests.get(url, allow_redirects=True)
        url = r.url
    except: pass
    if "/photo/" in url: url = url.replace("/photo/", "/video/")
    return url

def extract_shortcode(url):
    match = re.search(r'(?:p|reel|tv)/([^/?#&]+)', url)
    return match.group(1) if match else None

def save_user(user_id):
    try:
        with open("users.json", "r") as f: users = json.load(f)
    except: users = []
    if user_id not in users:
        users.append(user_id)
        with open("users.json", "w") as f: json.dump(users, f)

async def set_reaction(message, emoji):
    try:
        await message.set_reaction(reaction=[ReactionTypeEmoji(emoji=emoji)])
    except:
        pass

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID: return
    text = update.message.text
    message = text[len("/allm"):].strip()
    if not message:
        message = "تنبيه للكل يرجى انضمام الى قناة التحديثات من فضلكم 🤍\nhttps://t.me/SADOWNLOADER"
    try:
        with open("users.json", "r") as f: users = json.load(f)
    except: users = []
    for user_id in users:
        try: await context.bot.send_message(chat_id=user_id, text=message)
        except: pass
    await update.message.reply_text("تم ارسال الرسالة لجميع المستخدمين ✅")

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    save_user(update.effective_user.id)
    text = update.message.text

    if not url_regex.search(text):
        await update.message.reply_text("حبيبي حط رابط تضحك عليه انت ههههههههههههههههههههههههههههههههه ")
        return

    await set_reaction(update.message, "✅")

    if "instagram.com" in text:
        shortcode = extract_shortcode(text)
        if not shortcode:
            await update.message.reply_text("غلط بالرابط تأكد منه")
            return

        loading_msg = await update.message.reply_animation(animation=LOADING_GIF)
        target_dir = f"folder_{shortcode}"

        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, lambda: loader.download_post(Post.from_shortcode(loader.context, shortcode), target=target_dir))

            files = sorted(glob.glob(os.path.join(target_dir, "*")))
            video_files = [f for f in files if f.lower().endswith('.mp4')]
            image_files = [f for f in files if f.lower().endswith('.jpg')]

            sent_msg = None
            if video_files:
                video_file = video_files[0]
                markup = InlineKeyboardMarkup([[InlineKeyboardButton("🎵 تحميل كـ مقطع صوتي ( mp3 )", callback_data=f"instamp3|{shortcode}")]])
                with open(video_file, 'rb') as video:
                    sent_msg = await update.message.reply_video(video=video, reply_markup=markup)
            elif image_files:
                if len(image_files) == 1:
                    with open(image_files[0], 'rb') as photo:
                        sent_msg = await update.message.reply_photo(photo=photo)
                else:
                    for i in range(0, len(image_files), 10):
                        batch = image_files[i:i+10]
                        media_group = [InputMediaPhoto(open(img, 'rb')) for img in batch]
                        messages = await update.message.reply_media_group(media=media_group)
                        sent_msg = messages[0]

            await loading_msg.delete()
            if os.path.exists(target_dir): shutil.rmtree(target_dir)

            if sent_msg:
                try:
                    await sent_msg.reply_text("اتمنى البوت قد ينال اعجابكم يرجى تقييم البوت هنا @SARATETBOT", message_effect_id=EFFECT_ID)
                except:
                    pass

        except Exception as e:
            print(f"Insta Error: {e}")
            await loading_msg.edit_text("صارت مشكلة تاكد الحساب مال فيديو عام")
            if os.path.exists(target_dir): shutil.rmtree(target_dir)
        return

    url = fix_tiktok_url(text)
    context.user_data["url"] = url
    buttons = [
        [InlineKeyboardButton("📷 تحميل كصورة", callback_data="image")],
        [InlineKeyboardButton("🎙 تحميل كبصمة", callback_data="voice")],
        [InlineKeyboardButton("🎧 تحميل كمقطع صوتي ( mp3 )", callback_data="audio_mp3")],
        [InlineKeyboardButton("🎥 تحميل كفيديو", callback_data="video")]
    ]
    keyboard = InlineKeyboardMarkup(buttons)
    await update.message.reply_text("اختر نوع التحميل", reply_markup=keyboard)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data.startswith("instamp3|"):
        shortcode = query.data.split("|")[1]
        temp_dir = f"audio_work{shortcode}"
        status_msg = await query.message.reply_animation(animation=LOADING_GIF, caption="جاي احول المقطع الى مقطع صوتي اصبر يحلو 😉")

        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, lambda: loader.download_post(Post.from_shortcode(loader.context, shortcode), target=temp_dir))
            files = glob.glob(os.path.join(temp_dir, "*"))
            video_file = next((f for f in files if f.lower().endswith('.mp4')), None)

            if video_file:
                with open(video_file, 'rb') as audio:
                    sent_audio = await query.message.reply_audio(audio=audio, title="SA_INSTAGRAM")
                    try:
                        await sent_audio.reply_text("اتمنى البوت قد ينال اعجابكم يرجى تقييم البوت هنا @SARATETBOT", message_effect_id=EFFECT_ID)
                    except:
                        pass
            else:
                await query.message.reply_text("صارت مشكلة على حظك ههههههههههههههههههههههههههههههههه ")

            await status_msg.delete()
            shutil.rmtree(temp_dir)

        except Exception as e:
            print(f"Insta MP3 Error: {e}")
            await status_msg.edit_text("صارت مشكلة على حظك ههههههههههههههههههههههههههههههههه ")
            if os.path.exists(temp_dir): shutil.rmtree(temp_dir)
        return

    url = context.user_data.get("url")
    if not url:
        await query.edit_message_text("غلط بالرابط تأكد منه")
        return

    rocket = await query.message.reply_animation(animation=LOADING_GIF)

    try:
        sent_msg = None

        if query.data == "image":
            if "tiktok.com" in url:
                data = tiktok_downloader.get_data(url)
                if data:
                    images = data.get("images", [])
                    if images:
                        for img in images:
                            sent_msg = await query.message.reply_photo(photo=img)
                    else:
                        cover = data.get("cover")
                        if cover:
                            sent_msg = await query.message.reply_photo(photo=cover)

            if not sent_msg and ("youtube.com" in url or "youtu.be" in url):
                ydl_opts = {"quiet": True}
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=False)
                    thumb = info.get("thumbnail")
                if thumb:
                    sent_msg = await query.message.reply_photo(photo=thumb)

        elif query.data == "video":
            if "tiktok.com" in url:
                data = tiktok_downloader.get_data(url)
                if data:
                    video_url = data.get("hdplay") or data.get("play")
                    if video_url:
                        filename = "tiktok_video.mp4"
                        if tiktok_downloader.download_file(video_url, filename):
                            with open(filename, "rb") as f:
                                sent_msg = await query.message.reply_video(video=f)
                            os.remove(filename)

            if not sent_msg:
                ydl_opts = {"format": "mp4", "outtmpl": "video.%(ext)s", "quiet": True}
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    filename = ydl.prepare_filename(info)
                with open(filename, "rb") as f:
                    sent_msg = await query.message.reply_video(video=f)
                os.remove(filename)

        elif query.data == "voice":
            if "tiktok.com" in url:
                data = tiktok_downloader.get_data(url)
                if data:
                    music_url = data.get("music")
                    if music_url:
                        filename = "tiktok_audio.mp3"
                        if tiktok_downloader.download_file(music_url, filename):
                            with open(filename, "rb") as f:
                                sent_msg = await query.message.reply_voice(voice=f)
                            os.remove(filename)

            if not sent_msg:
                ydl_opts = {"format": "bestaudio/best", "outtmpl": "voice.%(ext)s", "quiet": True}
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    filename = ydl.prepare_filename(info)
                with open(filename, "rb") as f:
                    sent_msg = await query.message.reply_voice(voice=f)
                os.remove(filename)

        elif query.data == "audio_mp3":
            if "tiktok.com" in url:
                data = tiktok_downloader.get_data(url)
                if data:
                    music_url = data.get("music")
                    if music_url:
                        filename = "tiktok_audio.mp3"
                        if tiktok_downloader.download_file(music_url, filename):
                            with open(filename, "rb") as f:
                                sent_msg = await query.message.reply_audio(audio=f, title="SA_DOWNLOADER")
                            os.remove(filename)

            if not sent_msg:
                ydl_opts = {"format": "bestaudio/best", "outtmpl": "audio.%(ext)s", "quiet": True}
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    filename = ydl.prepare_filename(info)
                with open(filename, "rb") as f:
                    sent_msg = await query.message.reply_audio(audio=f, title="SA_DOWNLOADER")
                os.remove(filename)

        if sent_msg:
            try:
                await sent_msg.reply_text("اتمنى البوت قد ينال اعجابكم يرجى تقييم البوت هنا @SARATETBOT", message_effect_id=EFFECT_ID)
            except:
                pass

    except Exception as e:
        print(f"General Error: {e}")
        await query.message.reply_text("غلط بالرابط تاكد منه")

    await rocket.delete()

app = ApplicationBuilder().token(TOKEN).build()
app.add_handler(CommandHandler("allm", broadcast))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
app.add_handler(CallbackQueryHandler(button_handler))

print("البوت يعمل بنجاح... ✅")
app.run_polling()
