# Discord Music Bot

This is a Discord bot called CyberChmonya that allows you to play music from YouTube and Spotify in your Discord server. It features commands for searching and playing individual tracks, playing playlists, and controlling the playback queue.

## Features

-   **Play from URL:** Play audio directly from YouTube or Spotify URLs.
-   **Playlists:** Play entire playlists from YouTube and Spotify.
-   **Search:** Search for tracks on YouTube by keywords and select from the top results.
-   **Queue Management:**
    -   View the current queue.
    -   Skip the current track.
    -   Pause and resume playback.
    -   Stop playback and clear the queue.
    -   Shuffle the tracks in the queue.
    -   Clear the entire queue.
-   **Interactive Controls:** Uses buttons for easy control of playback (pause/resume, stop, skip, show queue, shuffle, clear).
-   **User-Friendly Interface:** Uses Discord slash commands and embeds for a clean and intuitive experience.
-   **Welcome Message:** Sends a friendly welcome message with instructions when the bot joins a new server.
-   **Help Command:** Provides a comprehensive list of available commands.

## Prerequisites

-   Python 3.7 or higher
-   Discord.py library (`discord.py`)
-   yt-dlp library (`yt-dlp`)
-   Spotipy library (`spotipy`)
-   python-dotenv library (`python-dotenv`)
-   FFmpeg installed on your system and added to your system's PATH.
-   A Discord bot token.
-   Spotify API Client ID and Client Secret.

## Setup

1.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

2.  **Create a `.env` file:**
    In the same directory as your bot script, create a file named `.env` and add your Discord bot token and Spotify API credentials:
    ```env
    DISCORD_TOKEN=YOUR_DISCORD_BOT_TOKEN
    SPOTIFY_CLIENT_ID=YOUR_SPOTIFY_CLIENT_ID
    SPOTIFY_CLIENT_SECRET=YOUR_SPOTIFY_CLIENT_SECRET
    ```
    Replace `YOUR_DISCORD_BOT_TOKEN`, `YOUR_SPOTIFY_CLIENT_ID`, and `YOUR_SPOTIFY_CLIENT_SECRET` with your actual credentials.

3.  **Get Spotify API Credentials:**
    -   Go to the [Spotify Developer Dashboard](https://developer.spotify.com/dashboard/).
    -   Log in with your Spotify account.
    -   Create a new app.
    -   Once the app is created, you will find your Client ID and Client Secret.

4.  **Invite the Bot to Your Server:**
    -   Go to the "OAuth2" tab of your Discord application on the [Discord Developer Portal](https://discord.com/developers/applications).
    -   Under "Scopes," select `bot` and `applications.commands`.
    -   Copy the generated OAuth2 URL and paste it into your browser.
    -   Select the server you want to add the bot to and authorize it.

5.  **Run the Bot:**
    Navigate to the directory containing your bot script in your terminal and run:
    ```bash
    python script.py
    ```

## Commands

All commands are implemented as Discord slash commands.

### Main Commands

-   `/help`: Shows a list of all available commands.

### Music Playback Commands (`/play`)

-   `/play url <URL>`: Plays a track from a given YouTube or Spotify URL.
-   `/play playlist <URL>`: Plays a playlist from a given YouTube or Spotify URL.
-   `/play search <query>`: Searches for a track on YouTube based on the query and allows you to select a track to play from the results.

### Player Control Commands (`/player`)

-   `/player stop`: Stops the current playback and clears the queue.
-   `/player pause`: Pauses the current playback.
-   `/player skip`: Skips the currently playing track.
-   `/player queue`: Shows the current list of tracks in the queue.
-   `/player shuffle`: Shuffles the order of tracks in the queue.
-   `/player clear`: Clears all tracks from the queue.

## Usage

1.  Join a voice channel in your Discord server.
2.  Use the slash commands (e.g., `/play url https://www.youtube.com/watch?v=dQw4w9WgXcQ`) in a text channel.
3.  For search results, an interactive menu will appear allowing you to select the desired track.
4.  Use the `/player` commands to control the playback and manage the queue.
5.  Interactive buttons will appear below the "Now Playing" message for easy control.

## Contributing

Contributions to this project are welcome. Feel free to open issues or submit pull requests with improvements or bug fixes.
