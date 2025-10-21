import telebot
import os
import subprocess
from telebot import types

# 🔑 Укажи свой токен
TOKEN = "8260387239:AAHWHq2vHruonwosdGLZ3uG4KXFtZJKL6po"
bot = telebot.TeleBot(TOKEN)

# Создаём выходную папку
os.makedirs("output", exist_ok=True)

# 📁 Путь к папке с музыкой
MUSIC_DIR = "music"

# Хранилище выбора пользователя
user_voice = {}
user_music = {}
user_uploading = {}  # Для отслеживания загрузки музыки


@bot.message_handler(commands=['start'])
def start(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    bot.send_message(message.chat.id, "Привет! Отправь голосовое сообщение 👇", reply_markup=markup)


@bot.message_handler(content_types=['voice'])
def handle_voice(message):
    user_id = message.from_user.id

    # Скачиваем голосовое
    file_info = bot.get_file(message.voice.file_id)
    downloaded = bot.download_file(file_info.file_path)

    voice_path_ogg = f"output/{user_id}_voice.ogg"
    voice_path_mp3 = f"output/{user_id}_voice.mp3"
    with open(voice_path_ogg, 'wb') as f:
        f.write(downloaded)

    # Конвертация в mp3
    subprocess.run(["ffmpeg", "-y", "-i", voice_path_ogg, voice_path_mp3], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    user_voice[user_id] = voice_path_mp3

    # Меню выбора музыки
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    for music_file in os.listdir(MUSIC_DIR):
        if music_file.endswith(".mp3"):
            markup.add(types.KeyboardButton(music_file))
    markup.add(types.KeyboardButton("➕ Добавить музыку"))
    bot.send_message(message.chat.id, "Теперь выбери музыку для фона 🎵 или добавь новую", reply_markup=markup)


@bot.message_handler(func=lambda message: message.text and message.text.endswith(".mp3"))
def handle_music_choice(message):
    user_id = message.from_user.id
    music_file = os.path.join(MUSIC_DIR, message.text)
    if not os.path.exists(music_file):
        bot.send_message(message.chat.id, "Такой музыки нет 😢")
        return

    if user_id not in user_voice:
        bot.send_message(message.chat.id, "Сначала отправь голосовое сообщение 🎤")
        return

    user_music[user_id] = music_file
    bot.send_message(message.chat.id, "🎧 Соединяю голос и музыку...")

    voice_path = user_voice[user_id]
    output_path = f"output/{user_id}_final.ogg"

    # Узнаём длину голосового
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", voice_path],
        capture_output=True, text=True
    )
    duration = float(result.stdout.strip())

    # Музыка начинается после голоса
    subprocess.run([
        "ffmpeg", "-y",
        "-i", voice_path,
        "-i", music_file,
        "-filter_complex",
        f"[1:a]adelay={int(duration * 1000)}|{int(duration * 1000)}[delayed];[0:a][delayed]amix=inputs=2",
        "-c:a", "libopus",
        output_path
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    with open(output_path, 'rb') as audio:
        bot.send_voice(message.chat.id, audio)

    # Очистка
    del user_voice[user_id]
    del user_music[user_id]
    os.remove(voice_path)
    os.remove(output_path)


@bot.message_handler(func=lambda message: message.text == "➕ Добавить музыку")
def handle_add_music_button(message):
    user_id = message.from_user.id
    user_uploading[user_id] = True
    bot.send_message(message.chat.id, "Отправь MP3 файл с музыкой 🎵")


@bot.message_handler(content_types=['document'])
def handle_document(message):
    user_id = message.from_user.id
    
    if user_id not in user_uploading or not user_uploading[user_id]:
        return
    
    if not message.document.file_name.lower().endswith('.mp3'):
        bot.send_message(message.chat.id, "Пожалуйста, отправь MP3 файл 🎵")
        return
    
    # Скачиваем файл
    file_info = bot.get_file(message.document.file_id)
    downloaded = bot.download_file(file_info.file_path)
    
    # Сохраняем в папку music
    music_path = os.path.join(MUSIC_DIR, message.document.file_name)
    with open(music_path, 'wb') as f:
        f.write(downloaded)
    
    # Убираем флаг загрузки
    del user_uploading[user_id]
    
    bot.send_message(message.chat.id, f"✅ Музыка '{message.document.file_name}' добавлена в библиотеку! 🎵")


bot.polling(none_stop=True)
