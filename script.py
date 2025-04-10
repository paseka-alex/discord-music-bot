import discord
import yt_dlp
import spotipy
from discord.ext import commands
from spotipy.oauth2 import SpotifyClientCredentials
from urllib.parse import quote
from dotenv import load_dotenv
import os
import random  # Добавьте в начало файла

# Загрузка переменных окружения
load_dotenv()

bot = discord.Bot()
testGuild = 1208821228845006918
music = discord.SlashCommandGroup("play", "Music player related commands")
player = discord.SlashCommandGroup("player", "Player control commands")

# Spotify credentials из переменных окружения
spotify_client_id = os.getenv('SPOTIFY_CLIENT_ID')
spotify_client_secret = os.getenv('SPOTIFY_CLIENT_SECRET')

# A dictionary to store queues for each guild
queues = {}

class SongSelectView(discord.ui.View):
    def __init__(self, tracks, ctx):
        super().__init__(timeout=60)
        self.tracks = tracks
        self.ctx = ctx
        
        select = discord.ui.Select(
            placeholder="Выберите трек для воспроизведения",
            options=[
                discord.SelectOption(
                    label=f"{track['title'][:80]}...",
                    description=f"by {track['uploader'][:80]}",
                    value=str(i)
                ) for i, track in enumerate(tracks[:25])
            ]
        )
        
        async def select_callback(interaction):
            # Сразу отправляем отложенный ответ
            await interaction.response.defer(ephemeral=True)
            
            if interaction.user != self.ctx.author:
                await interaction.followup.send("Вы не можете использовать это меню!", ephemeral=True)
                return
            
            selected_track = self.tracks[int(select.values[0])]
            guild_id = interaction.guild_id
            
            if guild_id not in queues:
                queues[guild_id] = []
            
            try:
                ydl_opts = {
                    'format': 'bestaudio/best',
                    'quiet': True,
                    'no_warnings': True,
                    'extract_flat': False,
                }
                
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(selected_track["webpage_url"], download=False)
                    track_data = {
                        "url": info['url'],
                        "title": info.get('title', selected_track["title"]),
                        "uploader": info.get('uploader', selected_track["uploader"]),
                        "thumbnail": info.get('thumbnail', selected_track.get("thumbnail")),
                        "channel": self.ctx.channel
                    }
                
                queues[guild_id].append(track_data)
                
                embed = discord.Embed(description=f"🎵 **Трек {track_data['title']} добавлен в очередь!**", color=discord.Color.green())
                await interaction.followup.send(embed=embed, ephemeral=True)
                
                if not interaction.guild.voice_client.is_playing():
                    await play_next_track(interaction.guild)
                
                try:
                    await interaction.message.delete()
                except discord.NotFound:
                    pass
                except Exception as e:
                    print(f"Ошибка при удалении сообщения: {e}")
                    
            except Exception as e:
                print(f"Ошибка при получении информации о треке: {e}")
                await interaction.followup.send("❌ Произошла ошибка при обработке трека", ephemeral=True)
        
        select.callback = select_callback
        self.add_item(select)

@music.command(name="search", description="Поиск и воспроизведение трека по названию")
async def search(ctx, query: str):
    """Поиск и воспроизведение трека по названию"""
    if not ctx.author.voice:
        embed = discord.Embed(description="❌ **Пожалуйста, подключитесь к голосовому каналу!**", color=discord.Color.red())
        await ctx.respond(embed=embed)
        return

    voice_channel = ctx.author.voice.channel
    if ctx.voice_client is None:
        await voice_channel.connect()

    embed_loading = discord.Embed(description="🔄 **Поиск треков, пожалуйста, подождите...**", color=discord.Color.yellow())
    await ctx.respond(embed=embed_loading, ephemeral=True)

    try:
        ydl_opts = {
            'format': 'bestaudio/best',
            'quiet': True,
            'extract_flat': True,
            'no_warnings': True,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            search_results = ydl.extract_info(f"ytsearch10:{query}", download=False)
            
            if not search_results.get('entries'):
                embed_error = discord.Embed(description="❌ **Ничего не найдено!**", color=discord.Color.red())
                await ctx.edit(embed=embed_error)
                return
                
            tracks = []
            for entry in search_results['entries']:
                if entry:
                    track = {
                        "webpage_url": entry.get('url', ''),  # URL страницы видео
                        "title": entry.get('title', 'Unknown Title'),
                        "uploader": entry.get('uploader', 'Unknown Artist'),
                        "thumbnail": entry.get('thumbnail', None),
                    }
                    tracks.append(track)
            
            embed = discord.Embed(
                title="🔍 Результаты поиска",
                description="Выберите трек для воспроизведения из списка ниже:",
                color=discord.Color.blue()
            )
            
            view = SongSelectView(tracks, ctx)
            await ctx.edit(embed=embed, view=view)

    except Exception as e:
        embed_error = discord.Embed(description=f"❌ **Ошибка при поиске: {str(e)}**", color=discord.Color.red())
        await ctx.edit(embed=embed_error)

class SongButtonView(discord.ui.View):
    def __init__(self, guild_id):
        # Устанавливаем timeout=None для бесконечного времени жизни кнопок
        super().__init__(timeout=None)
        self.guild_id = guild_id

    @discord.ui.button(emoji="⏯️", row=0, style=discord.ButtonStyle.success)
    async def pause_resume(self, button: discord.ui.Button, interaction: discord.Interaction):
        try:
            vc = interaction.guild.voice_client
            if not vc:
                await interaction.response.send_message("❌ Бот не подключен к голосовому каналу!", ephemeral=True)
                return
                
            if vc.is_playing():
                vc.pause()
                embed = discord.Embed(description="⏸️ **Пауза**", color=discord.Color.orange())
                await interaction.response.send_message(embed=embed, ephemeral=True)
            elif vc.is_paused():
                vc.resume()
                embed = discord.Embed(description="▶️ **Возобновлено**", color=discord.Color.green())
                await interaction.response.send_message(embed=embed, ephemeral=True)
            else:
                await interaction.response.send_message("❌ Сейчас ничего не воспроизводится!", ephemeral=True)
        except Exception as e:
            print(f"Ошибка при обработке кнопки pause/resume: {e}")
            await interaction.response.send_message("❌ Произошла ошибка при выполнении команды", ephemeral=True)

    @discord.ui.button(emoji="⏹️", row=0, style=discord.ButtonStyle.danger)
    async def stop(self, button: discord.ui.Button, interaction: discord.Interaction):
        vc = interaction.guild.voice_client
        if vc.is_playing() or vc.is_paused():
            vc.stop()
            queues[self.guild_id] = []  # Clear the queue
            embed = discord.Embed(description="⏹️ **Остановлено**", color=discord.Color.red())
            await interaction.response.send_message(embed=embed, ephemeral=True)
            try:
                await interaction.message.delete()
            except discord.NotFound:
                pass  # Игнорируем ошибку, если сообщение уже удалено
            except Exception as e:
                print(f"Ошибка при удалении сообщения: {e}")

    @discord.ui.button(emoji="⏭️", style=discord.ButtonStyle.secondary)
    async def skip(self, button: discord.ui.Button, interaction: discord.Interaction):
        if not interaction.guild.voice_client:
            await interaction.response.send_message("❌ Бот не подключен к голосовому каналу!", ephemeral=True)
            return
            
        if not interaction.guild.voice_client.is_playing():
            await interaction.response.send_message("❌ Сейчас ничего не играет!", ephemeral=True)
            return
            
        # Останавливаем текущий трек
        interaction.guild.voice_client.stop()
        
        # Отправляем сообщение о пропуске трека
        await interaction.response.send_message("⏭️ **Трек пропущен!**", ephemeral=True)
        
        # НЕ вызываем play_next_track здесь, так как он будет вызван в callback after_playing

    @discord.ui.button(label="📝 Очередь треков", row=1, style=discord.ButtonStyle.primary)
    async def show_queue(self, button: discord.ui.Button, interaction: discord.Interaction):
        if interaction.guild:
            guild = interaction.guild
            if guild.id in queues and queues[guild.id]:
                # Создаем список страниц
                tracks_per_page = 10
                queue_tracks = queues[guild.id]
                total_tracks = len(queue_tracks)
                total_pages = (total_tracks + tracks_per_page - 1) // tracks_per_page
                
                class QueueView(discord.ui.View):
                    def __init__(self):
                        super().__init__(timeout=60)
                        self.current_page = 0
                    
                    def create_embed(self, page):
                        start_idx = page * tracks_per_page
                        end_idx = min(start_idx + tracks_per_page, total_tracks)
                        
                        embed = discord.Embed(
                            title="Текущая очередь треков",
                            description=f"Страница {page + 1}/{total_pages}",
                            color=discord.Color.blue()
                        )
                        
                        for idx, track in enumerate(queue_tracks[start_idx:end_idx], start=start_idx + 1):
                            track_title = track['title']
                            track_uploader = track['uploader']
                            
                            # Обрезаем длинные названия
                            if len(track_title) > 50:
                                track_title = track_title[:47] + "..."
                            if len(track_uploader) > 30:
                                track_uploader = track_uploader[:27] + "..."
                            
                            embed.add_field(
                                name=f"{idx}. {track_title}",
                                value=f"Артист: {track_uploader}",
                                inline=False
                            )
                        
                        embed.set_footer(text=f"Всего треков: {total_tracks}")
                        return embed
                    
                    @discord.ui.button(emoji="◀️", style=discord.ButtonStyle.secondary)
                    async def previous_page(self, button: discord.ui.Button, interaction: discord.Interaction):
                        self.current_page = (self.current_page - 1) % total_pages
                        await interaction.response.edit_message(embed=self.create_embed(self.current_page), view=self)
                    
                    @discord.ui.button(emoji="▶️", style=discord.ButtonStyle.secondary)
                    async def next_page(self, button: discord.ui.Button, interaction: discord.Interaction):
                        self.current_page = (self.current_page + 1) % total_pages
                        await interaction.response.edit_message(embed=self.create_embed(self.current_page), view=self)
                
                queue_view = QueueView()
                await interaction.response.send_message(
                    embed=queue_view.create_embed(0),
                    view=queue_view if total_pages > 1 else None,
                    ephemeral=True
                )
            else:
                await interaction.response.send_message("Очередь пуста.", ephemeral=True)
        else:
            await interaction.response.send_message("Данная команда доступна только в гильдии (сервере).", ephemeral=True)

    @discord.ui.button(emoji="🔀", row=1, style=discord.ButtonStyle.secondary)
    async def shuffle(self, button: discord.ui.Button, interaction: discord.Interaction):
        if self.guild_id not in queues or not queues[self.guild_id]:
            await interaction.response.send_message("❌ Очередь пуста!", ephemeral=True)
            return
            
        random.shuffle(queues[self.guild_id])
            
        embed = discord.Embed(description="🔀 **Очередь перемешана!**", color=discord.Color.blue())
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(emoji="🗑️", row=1, style=discord.ButtonStyle.secondary)
    async def clear(self, button: discord.ui.Button, interaction: discord.Interaction):
        if self.guild_id not in queues or not queues[self.guild_id]:
            await interaction.response.send_message("❌ Очередь уже пуста!", ephemeral=True)
            return
            
        queues[self.guild_id] = []
            
        embed = discord.Embed(description="🗑️ **Очередь очищена!**", color=discord.Color.blue())
        await interaction.response.send_message(embed=embed, ephemeral=True)

@player.command(name="stop", description="Остановить воспроизведение")
async def stop_command(ctx):
    if not ctx.voice_client:
        await ctx.respond("❌ Бот не подключен к голосовому каналу!", ephemeral=True)
        return
        
    vc = ctx.voice_client
    if vc.is_playing() or vc.is_paused():
        vc.stop()
        queues[ctx.guild.id] = []  # Clear the queue
        embed = discord.Embed(description="⏹️ **Воспроизведение остановлено**", color=discord.Color.red())
        await ctx.respond(embed=embed, ephemeral=True)
    else:
        await ctx.respond("❌ Сейчас ничего не воспроизводится!", ephemeral=True)

@player.command(name="pause", description="Поставить на паузу/возобновить воспроизведение")
async def pause_resume_command(ctx):
    if not ctx.voice_client:
        await ctx.respond("❌ Бот не подключен к голосовому каналу!", ephemeral=True)
        return
        
    vc = ctx.voice_client
    if vc.is_playing():
        vc.pause()
        embed = discord.Embed(description="⏸️ **Пауза**", color=discord.Color.orange())
        await ctx.respond(embed=embed, ephemeral=True)
    elif vc.is_paused():
        vc.resume()
        embed = discord.Embed(description="▶️ **Воспроизведение возобновлено**", color=discord.Color.green())
        await ctx.respond(embed=embed, ephemeral=True)
    else:
        await ctx.respond("❌ Сейчас ничего не воспроизводится!", ephemeral=True)

@player.command(name="skip", description="Пропустить текущий трек")
async def skip_command(ctx):
    if not ctx.voice_client:
        await ctx.respond("❌ Бот не подключен к голосовому каналу!", ephemeral=True)
        return
        
    vc = ctx.voice_client
    if vc.is_playing():
        vc.stop()
        embed = discord.Embed(description="⏭️ **Трек пропущен**", color=discord.Color.blue())
        await ctx.respond(embed=embed, ephemeral=True)
        await play_next_track(ctx.guild)
    else:
        await ctx.respond("❌ Сейчас ничего не воспроизводится!", ephemeral=True)

@player.command(name="queue", description="Показать очередь воспроизведения")
async def queue_command(ctx):
    if ctx.guild.id in queues and queues[ctx.guild.id]:
        embed = discord.Embed(
            title="Текущая очередь треков",
            description="Список треков в очереди:",
            color=discord.Color.blue()
        )
        
        for idx, track in enumerate(queues[ctx.guild.id]):
            embed.add_field(
                name=f"{idx + 1}. {track['title']}",
                value=f"Uploader: {track['uploader']}",
                inline=False
            )
            
        await ctx.respond(embed=embed, ephemeral=True)
    else:
        await ctx.respond("Очередь пуста.", ephemeral=True)

@player.command(name="shuffle", description="Перемешать треки в очереди")
async def shuffle_command(ctx):
    """Перемешать треки в очереди"""
    if ctx.guild.id not in queues or not queues[ctx.guild.id]:
        await ctx.respond("❌ Очередь пуста!", ephemeral=True)
        return
    
    # Перемешиваем оставшиеся треки
    random.shuffle(queues[ctx.guild.id])
    
    embed = discord.Embed(description="🔀 **Очередь перемешана!**", color=discord.Color.blue())
    await ctx.respond(embed=embed, ephemeral=True)

@player.command(name="clear", description="Очистить очередь воспроизведения")
async def clear_command(ctx):
    """Очистить очередь воспроизведения"""
    if ctx.guild.id not in queues or not queues[ctx.guild.id]:
        await ctx.respond("❌ Очередь уже пуста!", ephemeral=True)
        return
    
    queues[ctx.guild.id] = []  # Полностью очищаем очередь
    
    embed = discord.Embed(description="🗑️ **Очередь очищена!**", color=discord.Color.blue())
    await ctx.respond(embed=embed, ephemeral=True)

@bot.event
async def on_ready():
    print(f"Бот {bot.user.name} успешно запущен!")

@bot.event
async def on_guild_join(guild):
    embed = discord.Embed(
        title="Привет!",
        description=f"Спасибо за добавление меня на сервер **{guild.name}**! 🎉",
        color=discord.Color.green()
    )
    embed.add_field(
        name="Что я могу сделать?",
        value="Я могу помочь вам с воспроизведением музыки с YouTube и Spotify. Просто используйте команды ниже:",
        inline=False
    )
    embed.add_field(
        name="Команды:",
        value="`/play url <URL>` - Воспроизвести трек с YouTube или Spotify.\n`/play playlist <URL>` - Воспроизвести плейлист с YouTube или Spotify.\n`/play search <query>` - Поиск и воспроизведение трека по названию",
        inline=False
    )
    embed.set_footer(text="Надеюсь, вам понравится со мной работать! 🎶")

    # Проверяем системный канал
    target_channel = None
    if guild.system_channel and guild.system_channel.permissions_for(guild.me).send_messages:
        target_channel = guild.system_channel
    else:
        # Ищем первый доступный текстовый канал
        for channel in guild.text_channels:
            if channel.permissions_for(guild.me).send_messages:
                target_channel = channel
                break

    # Отправляем сообщение в выбранный канал
    if target_channel:
        try:
            await target_channel.send(embed=embed)
        except Exception as e:
            print(f"Ошибка при отправке сообщения на сервере {guild.name}: {e}")
    else:
        print(f"Не удалось найти доступный канал для отправки сообщения на сервере {guild.name}")

# Создание slash-команды
@bot.slash_command(name="help", description="Показывает список доступных команд.")
async def help_command(ctx: discord.ApplicationContext):
    embed = discord.Embed(
        title="Помощь по командам",
        description="Вот список доступных команд:",
        color=discord.Color.blue()
    )

    # Основные команды
    embed.add_field(name="📋    Основные команды", value="_ _", inline=False)
    embed.add_field(name="/help", value="Показывает это сообщение.", inline=False)
    
    # Команды воспроизведения
    embed.add_field(name="🎵    Воспроизведение", value="_ _", inline=False)
    embed.add_field(name="/play url <URL>", value="Воспроизвести трек с YouTube или Spotify.", inline=False)
    embed.add_field(name="/play playlist <URL>", value="Воспроизвести плейлист с YouTube или Spotify.", inline=False)
    embed.add_field(name="/play search <query>", value="Поиск и воспроизведение трека по названию.", inline=False)
    
    # Управление плеером
    embed.add_field(name="⚙️    Управление плеером", value="_ _", inline=False)
    embed.add_field(name="/player stop", value="Остановить воспроизведение.", inline=False)
    embed.add_field(name="/player pause", value="Поставить на паузу/возобновить воспроизведение.", inline=False)
    embed.add_field(name="/player skip", value="Пропустить текущий трек.", inline=False)
    embed.add_field(name="/player queue", value="Показать очередь воспроизведения.", inline=False)
    embed.add_field(name="/player shuffle", value="Перемешать треки в очереди.", inline=False)
    embed.add_field(name="/player clear", value="Очистить очередь воспроизведения.", inline=False)

    embed.set_footer(text="Надеюсь, вам понравится работать с ботом! 🎶")

    await ctx.respond(embed=embed)

async def play_next_track(guild):
    """Play the next track in the queue for a guild."""
    if not guild.id in queues or not queues[guild.id]:
        return

    vc = guild.voice_client
    if not vc or not vc.is_connected():
        return

    try:
        next_track = queues[guild.id].pop(0)
        
        # Если трек требует обработки, получаем прямую ссылку
        if next_track.get("needs_processing"):
            try:
                ydl_opts = {
                    'format': 'bestaudio/best',
                    'quiet': True,
                    'no_warnings': True,
                }
                
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    if "search_query" in next_track:  # Для треков Spotify
                        info = ydl.extract_info(f"ytsearch:{next_track['search_query']}", download=False)
                        if 'entries' in info:
                            video_info = info['entries'][0]
                    else:  # Для треков YouTube
                        video_info = ydl.extract_info(next_track['webpage_url'], download=False)
                    
                    next_track['url'] = video_info['url']
                    
            except Exception as e:
                print(f"Ошибка при получении URL трека: {e}")
                await play_next_track(guild)  # Пропускаем проблемный трек
                return

        FFMPEG_OPTIONS = {
            'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 -probesize 200M',
            'options': '-vn'
        }
        
        source = discord.FFmpegPCMAudio(next_track["url"], **FFMPEG_OPTIONS)
        source = discord.PCMVolumeTransformer(source)
        
        def after_playing(error):
            if error:
                print(f"Ошибка воспроизведения: {error}")
            
            async def cleanup():
                if "message" in next_track and next_track["message"]:
                    try:
                        await next_track["message"].delete()
                    except:
                        pass
                await play_next_track(guild)
            
            bot.loop.create_task(cleanup())
        
        vc.play(source, after=after_playing)
        
        embed = discord.Embed(title="Сейчас играет 🎶", color=discord.Color.blue())
        embed.add_field(name="Название", value=next_track["title"], inline=False)
        embed.add_field(name="Артист", value=next_track["uploader"], inline=False)
        if next_track.get("thumbnail"):
            embed.set_thumbnail(url=next_track["thumbnail"])
        
        next_track["message"] = await next_track["channel"].send(
            embed=embed,
            view=SongButtonView(guild.id)
        )

    except Exception as e:
        print(f"Ошибка при воспроизведении трека: {e}")
        await play_next_track(guild)


# Spotify search function to get the YouTube link
def get_spotify_track_url(spotify_url):
    sp = spotipy.Spotify(auth_manager=SpotifyClientCredentials(client_id=spotify_client_id, client_secret=spotify_client_secret))
    track_info = sp.track(spotify_url)
    track_name = track_info['name']
    artist_name = track_info['artists'][0]['name']
    search_query = f"{track_name} {artist_name}"
    thumbnail_url = track_info['album']['images'][0]['url']

    # Use yt_dlp to find YouTube video
    ydl_opts = {
        'format': 'bestaudio/best',
        'quiet': True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        search_result = ydl.extract_info(f"ytsearch:{search_query}", download=False)
        if 'entries' in search_result:
            video_url = search_result['entries'][0]['url']
            return video_url, track_name, artist_name, thumbnail_url
    return None, None, None

@music.command()
async def url(ctx, link: str):
    """Добавить и воспроизвести трек с YouTube или Spotify"""
    if not ctx.author.voice:
        embed = discord.Embed(description="❌ **Пожалуйста, подключитесь к голосовому каналу!**", color=discord.Color.red())
        await ctx.respond(embed=embed)
        return

    voice_channel = ctx.author.voice.channel
    if ctx.voice_client is None:
        await voice_channel.connect()

    guild_id = ctx.guild.id
    if guild_id not in queues:
        queues[guild_id] = []

    embed_loading = discord.Embed(description="🔄 **Загрузка трека, пожалуйста, подождите...**", color=discord.Color.yellow())
    await ctx.respond(embed=embed_loading, ephemeral=True)

    try:
        if "spotify.com" in link:
            if "open.spotify.com" not in link:
                embed_error = discord.Embed(description="❌ **Неверная ссылка на Spotify! Пожалуйста, отправьте правильную ссылку.**", color=discord.Color.red())
                await ctx.edit(embed=embed_error)
                return
                
            video_url, track_name, artist_name, thumbnail = get_spotify_track_url(link)
            if video_url:
                track = {
                    "url": video_url,
                    "title": track_name,
                    "uploader": artist_name,
                    "thumbnail": thumbnail,
                    "channel": ctx.channel
                }
        else:
            if "youtube.com" not in link and "youtu.be" not in link and "music.youtube.com" not in link:
                embed_error = discord.Embed(description="❌ **Неверная ссылка! Пожалуйста, отправьте правильную ссылку YouTube или Spotify.**", color=discord.Color.red())
                await ctx.edit(embed=embed_error)
                return
                
            ydl_opts = {
                'format': 'bestaudio/best',
                'quiet': True,
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(link, download=False)
                track = {
                    "url": info['url'],
                    "title": info.get('title', 'Unknown Title'),
                    "uploader": info.get('uploader', 'Unknown Artist'),
                    "thumbnail": info.get('thumbnail', None),
                    "channel": ctx.channel
                }

        queues[guild_id].append(track)

        if not ctx.voice_client.is_playing():
            await play_next_track(ctx.guild)

        embed_added = discord.Embed(description=f"🎵 **Трек {track['title']} добавлен в очередь!**", color=discord.Color.green())
        await ctx.edit(embed=embed_added)

    except Exception as e:
        embed_error = discord.Embed(description=f"❌ **Ошибка загрузки трека: {e}**", color=discord.Color.red())
        await ctx.edit(embed=embed_error)

@music.command()
async def playlist(ctx, link: str):
    """Добавить и воспроизвести плейлист с YouTube или Spotify"""
    if not ctx.author.voice:
        embed = discord.Embed(description="❌ **Пожалуйста, подключитесь к голосовому каналу!**", color=discord.Color.red())
        await ctx.respond(embed=embed)
        return

    voice_channel = ctx.author.voice.channel
    if ctx.voice_client is None:
        await voice_channel.connect()

    guild_id = ctx.guild.id
    if guild_id not in queues:
        queues[guild_id] = []

    embed_loading = discord.Embed(description="🔄 **Загрузка плейлиста, пожалуйста, подождите...**", color=discord.Color.yellow())
    await ctx.respond(embed=embed_loading, ephemeral=True)

    try:
        if "spotify.com" in link:
            if "open.spotify.com" not in link:
                embed_error = discord.Embed(description="❌ **Неверная ссылка на Spotify! Пожалуйста, отправьте правильную ссылку.**", color=discord.Color.red())
                await ctx.edit(embed=embed_error)
                return

            sp = spotipy.Spotify(auth_manager=SpotifyClientCredentials(client_id=spotify_client_id, client_secret=spotify_client_secret))
            
            if "playlist" in link:
                playlist_id = link.split('playlist/')[1].split('?')[0]
                results = sp.playlist_tracks(playlist_id)
                tracks = results['items']
                
                for track in tracks:
                    track_info = track['track']
                    track_data = {
                        "search_query": f"{track_info['name']} {track_info['artists'][0]['name']}",
                        "title": track_info['name'],
                        "uploader": track_info['artists'][0]['name'],
                        "thumbnail": track_info['album']['images'][0]['url'] if track_info['album']['images'] else None,
                        "channel": ctx.channel,
                        "needs_processing": True  # Флаг, указывающий что нужно получить URL
                    }
                    queues[guild_id].append(track_data)

        else:
            if "youtube.com" not in link and "youtu.be" not in link:
                embed_error = discord.Embed(description="❌ **Неверная ссылка! Пожалуйста, отправьте правильную ссылку YouTube или Spotify.**", color=discord.Color.red())
                await ctx.edit(embed=embed_error)
                return

            ydl_opts = {
                'format': 'bestaudio/best',
                'quiet': True,
                'extract_flat': True,
                'ignoreerrors': True,
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                playlist_info = ydl.extract_info(link, download=False)
                if 'entries' in playlist_info:
                    for entry in playlist_info['entries']:
                        if entry is None:
                            continue
                        track = {
                            "webpage_url": entry['url'],  # URL страницы видео
                            "title": entry.get('title', 'Unknown Title'),
                            "uploader": entry.get('uploader', 'Unknown Artist'),
                            "thumbnail": entry.get('thumbnail', None),
                            "channel": ctx.channel,
                            "needs_processing": True  # Флаг, указывающий что нужно получить прямую ссылку
                        }
                        queues[guild_id].append(track)

        total_tracks = len(queues[guild_id])
        embed_added = discord.Embed(
            description=f"🎵 **Плейлист добавлен в очередь! Добавлено {total_tracks} треков.**",
            color=discord.Color.green()
        )
        await ctx.edit(embed=embed_added)

        # Начинаем воспроизведение, если ничего не играет
        if not ctx.voice_client.is_playing():
            await play_next_track(ctx.guild)

    except Exception as e:
        embed_error = discord.Embed(description=f"❌ **Ошибка загрузки плейлиста: {e}**", color=discord.Color.red())
        await ctx.edit(embed=embed_error)

bot.add_application_command(music)
bot.add_application_command(player)

bot.run(os.getenv('DISCORD_TOKEN'))
