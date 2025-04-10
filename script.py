import discord
import yt_dlp
import spotipy
from discord.ext import commands
from spotipy.oauth2 import SpotifyClientCredentials
from urllib.parse import quote
from dotenv import load_dotenv
import os
import random  # Add at the beginning of the file

# Loading environment variables
load_dotenv()

bot = discord.Bot()
music = discord.SlashCommandGroup("play", "Music player related commands")
player = discord.SlashCommandGroup("player", "Player control commands")

# Spotify credentials from environment variables
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
            placeholder="Select a track to play",
            options=[
                discord.SelectOption(
                    label=f"{track['title'][:80]}...",
                    description=f"by {track['uploader'][:80]}",
                    value=str(i)
                ) for i, track in enumerate(tracks[:25])
            ]
        )
        
        async def select_callback(interaction):
            await interaction.response.defer(ephemeral=True)
            
            if interaction.user != self.ctx.author:
                await interaction.followup.send("You cannot use this menu!", ephemeral=True)
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
                
                embed = discord.Embed(description=f"🎵 **Track added to queue!**", color=discord.Color.green())
                await interaction.followup.send(embed=embed, ephemeral=True)
                
                if not interaction.guild.voice_client.is_playing():
                    await play_next_track(interaction.guild)
                
                try:
                    await interaction.message.delete()
                except discord.NotFound:
                    pass
                except Exception as e:
                    print(f"Error deleting message: {e}")
                    
            except Exception as e:
                print(f"Error processing track: {e}")
                await interaction.followup.send("Error processing track", ephemeral=True)
        
        select.callback = select_callback
        self.add_item(select)

@music.command(name="search", description="Search and play track by name")
async def search(ctx, query: str):
    """Search and play track by name"""
    if not ctx.author.voice:
        embed = discord.Embed(description="Please join a voice channel!", color=discord.Color.red())
        await ctx.respond(embed=embed)
        return

    voice_channel = ctx.author.voice.channel
    if ctx.voice_client is None:
        await voice_channel.connect()

    embed_loading = discord.Embed(description="Searching for tracks, please wait...", color=discord.Color.yellow())
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
                embed_error = discord.Embed(description="Nothing found!", color=discord.Color.red())
                await ctx.edit(embed=embed_error)
                return
                
            tracks = []
            for entry in search_results['entries']:
                if entry:
                    track = {
                        "webpage_url": entry.get('url', ''),
                        "title": entry.get('title', 'Unknown Title'),
                        "uploader": entry.get('uploader', 'Unknown Artist'),
                        "thumbnail": entry.get('thumbnail', None),
                    }
                    tracks.append(track)
            
            embed = discord.Embed(
                title="Search Results",
                description="Select a track to play from the list below:",
                color=discord.Color.blue()
            )
            
            view = SongSelectView(tracks, ctx)
            await ctx.edit(embed=embed, view=view)

    except Exception as e:
        embed_error = discord.Embed(description=f"Error while searching: {str(e)}", color=discord.Color.red())
        await ctx.edit(embed=embed_error)

class SongButtonView(discord.ui.View):
    def __init__(self, guild_id):
        super().__init__(timeout=None)
        self.guild_id = guild_id

    @discord.ui.button(emoji="⏯️", row=0, style=discord.ButtonStyle.success)
    async def pause_resume(self, button: discord.ui.Button, interaction: discord.Interaction):
        try:
            vc = interaction.guild.voice_client
            if not vc:
                await interaction.response.send_message("Bot is not connected to a voice channel!", ephemeral=True)
                return
                
            if vc.is_playing():
                vc.pause()
                embed = discord.Embed(description="Pause", color=discord.Color.orange())
                await interaction.response.send_message(embed=embed, ephemeral=True)
            elif vc.is_paused():
                vc.resume()
                embed = discord.Embed(description="Resumed", color=discord.Color.green())
                await interaction.response.send_message(embed=embed, ephemeral=True)
            else:
                await interaction.response.send_message("Nothing is playing right now!", ephemeral=True)
        except Exception as e:
            print(f"Error processing pause/resume button: {e}")
            await interaction.response.send_message("Error executing command", ephemeral=True)

    @discord.ui.button(emoji="⏹️", row=0, style=discord.ButtonStyle.danger)
    async def stop(self, button: discord.ui.Button, interaction: discord.Interaction):
        vc = interaction.guild.voice_client
        if vc.is_playing() or vc.is_paused():
            vc.stop()
            queues[self.guild_id] = []
            embed = discord.Embed(description="Stopped", color=discord.Color.red())
            await interaction.response.send_message(embed=embed, ephemeral=True)
            try:
                await interaction.message.delete()
            except discord.NotFound:
                pass
            except Exception as e:
                print(f"Error deleting message: {e}")

    @discord.ui.button(emoji="⏭️", style=discord.ButtonStyle.secondary)
    async def skip(self, button: discord.ui.Button, interaction: discord.Interaction):
        if not interaction.guild.voice_client:
            await interaction.response.send_message("Bot is not connected to a voice channel!", ephemeral=True)
            return
            
        if not interaction.guild.voice_client.is_playing():
            await interaction.response.send_message("Nothing is playing right now!", ephemeral=True)
            return
            
        interaction.guild.voice_client.stop()
        await interaction.response.send_message("Track skipped!", ephemeral=True)

    @discord.ui.button(label="📝 Current Queue", row=1, style=discord.ButtonStyle.primary)
    async def show_queue(self, button: discord.ui.Button, interaction: discord.Interaction):
        if interaction.guild:
            guild = interaction.guild
            if guild.id in queues and queues[guild.id]:
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
                            title="Current Queue",
                            description=f"Page {page + 1}/{total_pages}",
                            color=discord.Color.blue()
                        )
                        
                        for idx, track in enumerate(queue_tracks[start_idx:end_idx], start=start_idx + 1):
                            track_title = track['title']
                            track_uploader = track['uploader']
                            
                            if len(track_title) > 50:
                                track_title = track_title[:47] + "..."
                            if len(track_uploader) > 30:
                                track_uploader = track_uploader[:27] + "..."
                            
                            embed.add_field(
                                name=f"{idx}. {track_title}",
                                value=f"Artist: {track_uploader}",
                                inline=False
                            )
                        
                        embed.set_footer(text=f"Total tracks: {total_tracks}")
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
                await interaction.response.send_message("Queue is empty.", ephemeral=True)
        else:
            await interaction.response.send_message("This command is only available in a guild (server).", ephemeral=True)

    @discord.ui.button(emoji="🔀", row=1, style=discord.ButtonStyle.secondary)
    async def shuffle(self, button: discord.ui.Button, interaction: discord.Interaction):
        if self.guild_id not in queues or not queues[self.guild_id]:
            await interaction.response.send_message("Queue is empty.", ephemeral=True)
            return
            
        random.shuffle(queues[self.guild_id])
            
        embed = discord.Embed(description="Queue shuffled!", color=discord.Color.blue())
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(emoji="🗑️", row=1, style=discord.ButtonStyle.secondary)
    async def clear(self, button: discord.ui.Button, interaction: discord.Interaction):
        if self.guild_id not in queues or not queues[self.guild_id]:
            await interaction.response.send_message("Queue is already empty!", ephemeral=True)
            return
            
        queues[self.guild_id] = []
            
        embed = discord.Embed(description="Queue cleared!", color=discord.Color.blue())
        await interaction.response.send_message(embed=embed, ephemeral=True)

@player.command(name="stop", description="Stop playback")
async def stop_command(ctx):
    if not ctx.voice_client:
        await ctx.respond("Bot is not connected to a voice channel!", ephemeral=True)
        return
        
    vc = ctx.voice_client
    if vc.is_playing() or vc.is_paused():
        vc.stop()
        queues[ctx.guild.id] = []
        embed = discord.Embed(description="Playback stopped", color=discord.Color.red())
        await ctx.respond(embed=embed, ephemeral=True)
    else:
        await ctx.respond("Nothing is playing right now!", ephemeral=True)

@player.command(name="pause", description="Pause/Resume playback")
async def pause_resume_command(ctx):
    if not ctx.voice_client:
        await ctx.respond("Bot is not connected to a voice channel!", ephemeral=True)
        return
        
    vc = ctx.voice_client
    if vc.is_playing():
        vc.pause()
        embed = discord.Embed(description="Pause", color=discord.Color.orange())
        await ctx.respond(embed=embed, ephemeral=True)
    elif vc.is_paused():
        vc.resume()
        embed = discord.Embed(description="Playback resumed", color=discord.Color.green())
        await ctx.respond(embed=embed, ephemeral=True)
    else:
        await ctx.respond("Nothing is playing right now!", ephemeral=True)

@player.command(name="skip", description="Skip current track")
async def skip_command(ctx):
    if not ctx.voice_client:
        await ctx.respond("Bot is not connected to a voice channel!", ephemeral=True)
        return
        
    vc = ctx.voice_client
    if vc.is_playing():
        vc.stop()
        embed = discord.Embed(description="Track skipped", color=discord.Color.blue())
        await ctx.respond(embed=embed, ephemeral=True)
        await play_next_track(ctx.guild)
    else:
        await ctx.respond("Nothing is playing right now!", ephemeral=True)

@player.command(name="queue", description="Show playback queue")
async def queue_command(ctx):
    if ctx.guild.id in queues and queues[ctx.guild.id]:
        embed = discord.Embed(
            title="Current track queue",
            description="Track list in queue:",
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
        await ctx.respond("Queue is empty.", ephemeral=True)

@player.command(name="shuffle", description="Shuffle tracks in queue")
async def shuffle_command(ctx):
    if ctx.guild.id not in queues or not queues[ctx.guild.id]:
        await ctx.respond("Queue is empty.", ephemeral=True)
        return
    
    random.shuffle(queues[ctx.guild.id])
    
    embed = discord.Embed(description="Queue shuffled!", color=discord.Color.blue())
    await ctx.respond(embed=embed, ephemeral=True)

@player.command(name="clear", description="Clear playback queue")
async def clear_command(ctx):
    if ctx.guild.id not in queues or not queues[ctx.guild.id]:
        await ctx.respond("Queue is already empty!", ephemeral=True)
        return
    
    queues[ctx.guild.id] = []
    
    embed = discord.Embed(description="Queue cleared!", color=discord.Color.blue())
    await ctx.respond(embed=embed, ephemeral=True)

@bot.event
async def on_ready():
    print(f"Bot {bot.user.name} successfully launched!")

@bot.event
async def on_guild_join(guild):
    embed = discord.Embed(
        title="Hello!",
        description=f"Thanks for adding me to server **{guild.name}**! 🎉",
        color=discord.Color.green()
    )
    embed.add_field(
        name="What can I do?",
        value="I can help you play music from YouTube and Spotify. Just use the commands below:",
        inline=False
    )
    embed.add_field(
        name="Commands:",
        value="`/play url <URL>` - Play track from YouTube or Spotify.\n`/play playlist <URL>` - Play playlist from YouTube or Spotify.\n`/play search <query>` - Search and play track by name.",
        inline=False
    )
    embed.set_footer(text="Hope you'll enjoy working with me! 🎶")

    target_channel = None
    if guild.system_channel and guild.system_channel.permissions_for(guild.me).send_messages:
        target_channel = guild.system_channel
    else:
        for channel in guild.text_channels:
            if channel.permissions_for(guild.me).send_messages:
                target_channel = channel
                break

    if target_channel:
        try:
            await target_channel.send(embed=embed)
        except Exception as e:
            print(f"Error sending message on server {guild.name}: {e}")
    else:
        print(f"Couldn't find available channel to send message on server {guild.name}")

@bot.slash_command(name="help", description="Shows the list of available commands.")
async def help_command(ctx: discord.ApplicationContext):
    embed = discord.Embed(
        title="Command Help",
        description="Here's the list of available commands:",
        color=discord.Color.blue()
    )

    embed.add_field(name="📋    Main Commands", value="_ _", inline=False)
    embed.add_field(name="/help", value="Shows this message.", inline=False)
    
    embed.add_field(name="🎵    Playback", value="_ _", inline=False)
    embed.add_field(name="/play url <URL>", value="Play track from YouTube or Spotify.", inline=False)
    embed.add_field(name="/play playlist <URL>", value="Play playlist from YouTube or Spotify.", inline=False)
    embed.add_field(name="/play search <query>", value="Search and play track by name.", inline=False)
    
    embed.add_field(name="⚙️    Player Controls", value="_ _", inline=False)
    embed.add_field(name="/player stop", value="Stop playback.", inline=False)
    embed.add_field(name="/player pause", value="Pause/Resume playback.", inline=False)
    embed.add_field(name="/player skip", value="Skip current track.", inline=False)
    embed.add_field(name="/player queue", value="Show playback queue.", inline=False)
    embed.add_field(name="/player shuffle", value="Shuffle tracks in queue.", inline=False)
    embed.add_field(name="/player clear", value="Clear playback queue.", inline=False)

    embed.set_footer(text="Hope you'll enjoy working with me! 🎶")

    await ctx.respond(embed=embed)

async def play_next_track(guild):
    if not guild.id in queues or not queues[guild.id]:
        return

    vc = guild.voice_client
    if not vc or not vc.is_connected():
        return

    try:
        next_track = queues[guild.id].pop(0)
        
        if next_track.get("needs_processing"):
            try:
                ydl_opts = {
                    'format': 'bestaudio/best',
                    'quiet': True,
                    'no_warnings': True,
                }
                
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    if "search_query" in next_track:
                        info = ydl.extract_info(f"ytsearch:{next_track['search_query']}", download=False)
                        if 'entries' in info:
                            video_info = info['entries'][0]
                    else:
                        video_info = ydl.extract_info(next_track['webpage_url'], download=False)
                    
                    next_track['url'] = video_info['url']
                    
            except Exception as e:
                print(f"Error getting track URL: {e}")
                await play_next_track(guild)
                return

        FFMPEG_OPTIONS = {
            'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 -probesize 200M',
            'options': '-vn'
        }
        
        source = discord.FFmpegPCMAudio(next_track["url"], **FFMPEG_OPTIONS)
        source = discord.PCMVolumeTransformer(source)
        
        def after_playing(error):
            if error:
                print(f"Playback error: {error}")
            
            async def cleanup():
                if "message" in next_track and next_track["message"]:
                    try:
                        await next_track["message"].delete()
                    except:
                        pass
                await play_next_track(guild)
            
            bot.loop.create_task(cleanup())
        
        vc.play(source, after=after_playing)
        
        embed = discord.Embed(title="Now Playing 🎶", color=discord.Color.blue())
        embed.add_field(name="Title", value=next_track["title"], inline=False)
        embed.add_field(name="Artist", value=next_track["uploader"], inline=False)
        if next_track.get("thumbnail"):
            embed.set_thumbnail(url=next_track["thumbnail"])
        
        next_track["message"] = await next_track["channel"].send(
            embed=embed,
            view=SongButtonView(guild.id)
        )

    except Exception as e:
        print(f"Playback error: {e}")
        await play_next_track(guild)

def get_spotify_track_url(spotify_url):
    sp = spotipy.Spotify(auth_manager=SpotifyClientCredentials(client_id=spotify_client_id, client_secret=spotify_client_secret))
    track_info = sp.track(spotify_url)
    track_name = track_info['name']
    artist_name = track_info['artists'][0]['name']
    search_query = f"{track_name} {artist_name}"
    thumbnail_url = track_info['album']['images'][0]['url']

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
    if not ctx.author.voice:
        embed = discord.Embed(description="Please join a voice channel!", color=discord.Color.red())
        await ctx.respond(embed=embed)
        return

    voice_channel = ctx.author.voice.channel
    if ctx.voice_client is None:
        await voice_channel.connect()

    guild_id = ctx.guild.id
    if guild_id not in queues:
        queues[guild_id] = []

    embed_loading = discord.Embed(description="Loading track, please wait...", color=discord.Color.yellow())
    await ctx.respond(embed=embed_loading, ephemeral=True)

    try:
        if "spotify.com" in link:
            if "open.spotify.com" not in link:
                embed_error = discord.Embed(description="Invalid Spotify link! Please provide a correct link.", color=discord.Color.red())
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
                embed_error = discord.Embed(description="Invalid link! Please provide a correct YouTube or Spotify link.", color=discord.Color.red())
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

        embed_added = discord.Embed(description=f"🎵 **Track {track['title']} added to queue!**", color=discord.Color.green())
        await ctx.edit(embed=embed_added)

    except Exception as e:
        embed_error = discord.Embed(description=f"Error loading track: {e}", color=discord.Color.red())
        await ctx.edit(embed=embed_error)

@music.command()
async def playlist(ctx, link: str):
    if not ctx.author.voice:
        embed = discord.Embed(description="Please join a voice channel!", color=discord.Color.red())
        await ctx.respond(embed=embed)
        return

    voice_channel = ctx.author.voice.channel
    if ctx.voice_client is None:
        await voice_channel.connect()

    guild_id = ctx.guild.id
    if guild_id not in queues:
        queues[guild_id] = []

    embed_loading = discord.Embed(description="Loading playlist, please wait...", color=discord.Color.yellow())
    await ctx.respond(embed=embed_loading, ephemeral=True)

    try:
        if "spotify.com" in link:
            if "open.spotify.com" not in link:
                embed_error = discord.Embed(description="Invalid Spotify link! Please provide a correct link.", color=discord.Color.red())
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
                        "needs_processing": True
                    }
                    queues[guild_id].append(track_data)

        else:
            if "youtube.com" not in link and "youtu.be" not in link:
                embed_error = discord.Embed(description="Invalid link! Please provide a correct YouTube or Spotify link.", color=discord.Color.red())
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
                            "webpage_url": entry['url'],
                            "title": entry.get('title', 'Unknown Title'),
                            "uploader": entry.get('uploader', 'Unknown Artist'),
                            "thumbnail": entry.get('thumbnail', None),
                            "channel": ctx.channel,
                            "needs_processing": True
                        }
                        queues[guild_id].append(track)

        total_tracks = len(queues[guild_id])
        embed_added = discord.Embed(
            description=f"Playlist added to queue! Added {total_tracks} tracks.",
            color=discord.Color.green()
        )
        await ctx.edit(embed=embed_added)

        if not ctx.voice_client.is_playing():
            await play_next_track(ctx.guild)

    except Exception as e:
        embed_error = discord.Embed(description=f"Error loading playlist: {e}", color=discord.Color.red())
        await ctx.edit(embed=embed_error)

bot.add_application_command(music)
bot.add_application_command(player)

bot.run(os.getenv('DISCORD_TOKEN'))
