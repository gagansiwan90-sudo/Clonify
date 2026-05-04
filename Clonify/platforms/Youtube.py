import asyncio
import glob
import os
import re
from pathlib import Path
from typing import Optional, Union

import aiohttp
from pyrogram.enums import MessageEntityType
from pyrogram.types import Message
from youtubesearchpython.__future__ import VideosSearch

from Clonify.utils.formatters import time_to_seconds

YOUTUBE_API_URL = "https://shrutibots.site"


# ─── YouTubeAPI ──────────────────────────────────────────────────────────────

class YouTubeAPI:
    def __init__(self):
        self.base     = "https://www.youtube.com/watch?v="
        self.listbase = "https://youtube.com/playlist?list="
        self.api_url  = YOUTUBE_API_URL

        # Matches videos, shorts, playlists, youtu.be, music.youtube.com
        self.regex = re.compile(
            r"(https?://)?(www\.|m\.|music\.)?"
            r"(youtube\.com/(watch\?v=|shorts/|playlist\?list=)|youtu\.be/)"
            r"([A-Za-z0-9_-]{11}|PL[A-Za-z0-9_-]+)([&?][^\s]*)?"
        )

        # Search cache — 10-minute TTL, max 100 entries
        # Format: { cache_key: (result_dict, timestamp) }
        self._search_cache: dict = {}

        # Max 5 concurrent downloads to avoid bandwidth saturation
        self._download_semaphore = asyncio.Semaphore(5)

    # ── Internal helpers ─────────────────────────────────────────────────────

    def _clean_link(self, link: str) -> str:
        """Strip &si= / ?si= / extra & tracking params from URL."""
        return link.split("&si")[0].split("?si")[0].split("&")[0]

    def _ensure_downloads_dir(self):
        Path("downloads").mkdir(parents=True, exist_ok=True)

    def _locate_download_file(self, video_id: str, video: bool = False) -> Optional[str]:
        """Find an already-downloaded file for a given video ID."""
        pattern = f"downloads/{video_id}*"
        candidates = sorted([
            p for p in glob.glob(pattern)
            if not p.endswith((".part", ".ytdl", ".info.json", ".temp"))
            and not os.path.isdir(p)
        ])
        video_exts = {".mp4", ".mkv", ".webm", ".mov"}
        audio_exts = {".m4a", ".webm", ".opus", ".mp3", ".ogg", ".wav", ".flac"}
        target_exts = video_exts if video else audio_exts
        for p in candidates:
            if Path(p).suffix.lower() in target_exts:
                return p
        return candidates[0] if candidates else None

    # ── URL helpers ──────────────────────────────────────────────────────────

    def valid(self, url: str) -> bool:
        """Check if a URL is a valid YouTube URL."""
        return bool(re.match(self.regex, url))

    async def exists(self, link: str, videoid: Union[bool, str] = None) -> bool:
        """Return True if the link/video-id is a valid YouTube URL."""
        if videoid:
            link = self.base + link
        return bool(re.search(self.regex, link))

    def url(self, message_1: Message) -> Union[str, None]:
        """Extract and clean a YouTube URL from a Pyrogram message or its reply."""
        messages = [message_1]
        if message_1.reply_to_message:
            messages.append(message_1.reply_to_message)

        for message in messages:
            text = message.text or message.caption or ""

            if message.entities:
                for entity in message.entities:
                    if entity.type == MessageEntityType.URL:
                        raw = text[entity.offset: entity.offset + entity.length]
                        return self._clean_link(raw)

            if message.caption_entities:
                for entity in message.caption_entities:
                    if entity.type == MessageEntityType.TEXT_LINK:
                        return self._clean_link(entity.url)

        return None

    # ── Search & metadata ────────────────────────────────────────────────────

    async def _search_yt(self, query: str) -> Optional[dict]:
        """
        Search YouTube with 10-minute in-memory cache.
        Returns first result dict or None on failure.
        """
        loop = asyncio.get_running_loop()
        now = loop.time()

        if query in self._search_cache:
            cached, ts = self._search_cache[query]
            if now - ts < 600:
                return cached

        try:
            _search = VideosSearch(query, limit=1)
            results = await _search.next()
        except Exception as e:
            print(f"⚠️ YouTube search failed for '{query}': {e}")
            return None

        if not results or not results.get("result"):
            return None

        result = results["result"][0]

        # Evict oldest entry if cache is full
        if len(self._search_cache) >= 100:
            oldest = min(self._search_cache, key=lambda k: self._search_cache[k][1])
            del self._search_cache[oldest]

        self._search_cache[query] = (result, now)
        return result

    async def details(self, link: str, videoid: Union[bool, str] = None):
        """Return (title, duration_min, duration_sec, thumbnail, vidid)."""
        if videoid:
            link = self.base + link
        result = await self._search_yt(self._clean_link(link))
        if not result:
            return None, None, 0, None, None
        duration_min = result.get("duration")
        duration_sec = 0 if not duration_min else int(time_to_seconds(duration_min))
        return (
            result["title"],
            duration_min,
            duration_sec,
            result["thumbnails"][0]["url"].split("?")[0],
            result["id"],
        )

    async def title(self, link: str, videoid: Union[bool, str] = None) -> Optional[str]:
        if videoid:
            link = self.base + link
        result = await self._search_yt(self._clean_link(link))
        return result["title"] if result else None

    async def duration(self, link: str, videoid: Union[bool, str] = None) -> Optional[str]:
        if videoid:
            link = self.base + link
        result = await self._search_yt(self._clean_link(link))
        return result.get("duration") if result else None

    async def thumbnail(self, link: str, videoid: Union[bool, str] = None) -> Optional[str]:
        if videoid:
            link = self.base + link
        result = await self._search_yt(self._clean_link(link))
        if not result:
            return None
        return result["thumbnails"][0]["url"].split("?")[0]

    async def track(self, link: str, videoid: Union[bool, str] = None):
        """Return (track_details dict, vidid)."""
        if videoid:
            link = self.base + link
        result = await self._search_yt(self._clean_link(link))
        if not result:
            return {}, None
        track_details = {
            "title": result["title"],
            "link": result["link"],
            "vidid": result["id"],
            "duration_min": result.get("duration"),
            "thumb": result["thumbnails"][0]["url"].split("?")[0],
        }
        return track_details, result["id"]

    async def slider(
        self,
        link: str,
        query_type: int,
        videoid: Union[bool, str] = None,
    ):
        """Fetch up to 10 results and return the one at query_type index."""
        if videoid:
            link = self.base + link
        link = self._clean_link(link)
        a = VideosSearch(link, limit=10)
        results = (await a.next()).get("result", [])
        if not results or query_type >= len(results):
            return None, None, None, None
        r = results[query_type]
        return (
            r["title"],
            r.get("duration"),
            r["thumbnails"][0]["url"].split("?")[0],
            r["id"],
        )

    # ── Playlist ─────────────────────────────────────────────────────────────

    async def playlist(self, link: str, limit: int, user_id) -> list:
        """Return list of track dicts from a YouTube playlist (up to limit)."""
        from youtubesearchpython.__future__ import Playlist as YTPlaylist
        try:
            plist = await YTPlaylist.get(link)
            tracks = []

            if not plist or "videos" not in plist or not plist["videos"]:
                return []

            for data in plist["videos"][:limit]:
                try:
                    thumbnails = data.get("thumbnails", [])
                    thumb = thumbnails[-1].get("url", "").split("?")[0] if thumbnails else ""

                    video_link = data.get("link", "")
                    if "&list=" in video_link:
                        video_link = video_link.split("&list=")[0]

                    duration = data.get("duration", "0:00")
                    tracks.append({
                        "title": data.get("title", "Unknown")[:25],
                        "link": video_link,
                        "vidid": data.get("id", ""),
                        "duration_min": duration,
                        "duration_sec": int(time_to_seconds(duration)) if duration else 0,
                        "thumb": thumb,
                        "channel": data.get("channel", {}).get("name", ""),
                    })
                except Exception:
                    continue

            return tracks

        except KeyError:
            raise Exception("Failed to parse playlist. YouTube may have changed their structure.")
        except Exception:
            raise

    # ── API Download ─────────────────────────────────────────────────────────

    async def _download_via_api(self, video_id: str, video: bool = False) -> Optional[str]:
        """Download audio/video via external API (no yt-dlp, no cookies)."""
        file_type = "video" if video else "audio"
        ext = "mp4" if video else "mp3"
        file_path = os.path.join("downloads", f"{video_id}.{ext}")

        # Return cached file if already exists
        if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
            return file_path

        self._ensure_downloads_dir()

        try:
            async with aiohttp.ClientSession() as session:

                # Step 1: Get download token from API
                async with session.get(
                    f"{self.api_url}/download",
                    params={"url": video_id, "type": file_type},
                    timeout=aiohttp.ClientTimeout(total=7),
                ) as resp:
                    if resp.status != 200:
                        print(f"❌ API token request failed: HTTP {resp.status}")
                        return None
                    data = await resp.json()
                    token = data.get("download_token")
                    if not token:
                        print("❌ No download token received from API")
                        return None

                # Step 2: Stream & save the file
                stream_url = f"{self.api_url}/stream/{video_id}?type={file_type}&token={token}"
                async with session.get(
                    stream_url,
                    timeout=aiohttp.ClientTimeout(total=300),
                ) as file_resp:

                    if file_resp.status == 302:
                        redirect = file_resp.headers.get("Location")
                        if redirect:
                            async with session.get(redirect) as final:
                                if final.status != 200:
                                    print(f"❌ Redirect failed: HTTP {final.status}")
                                    return None
                                with open(file_path, "wb") as f:
                                    async for chunk in final.content.iter_chunked(16384):
                                        f.write(chunk)

                    elif file_resp.status == 200:
                        with open(file_path, "wb") as f:
                            async for chunk in file_resp.content.iter_chunked(16384):
                                f.write(chunk)
                    else:
                        print(f"❌ Download failed: HTTP {file_resp.status}")
                        return None

                # Verify download completed
                if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
                    print(f"✅ Downloaded: {video_id}.{ext}")
                    return file_path
                else:
                    print(f"❌ File empty or missing: {file_path}")
                    return None

        except asyncio.TimeoutError:
            print(f"❌ Download timeout for {video_id}")
            return None
        except Exception as e:
            print(f"❌ Download error for {video_id}: {e}")
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except Exception:
                    pass
            return None

    # ── Live stream ───────────────────────────────────────────────────────────

    async def download_live(self, video_id: str) -> str:
        """Get live stream URL via API, fallback to direct YouTube URL."""
        yt_url = self.base + video_id
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.api_url}/live",
                    params={"url": video_id, "type": "live"},
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        stream_url = data.get("stream_url")
                        if stream_url:
                            return stream_url
        except Exception as e:
            print(f"⚠️ Failed to get live stream URL: {e}")
        return yt_url

    # ── Main download entry point ─────────────────────────────────────────────

    async def download(
        self,
        link: str,
        mystic,
        video: Union[bool, str] = None,
        videoid: Union[bool, str] = None,
        songaudio: Union[bool, str] = None,
        songvideo: Union[bool, str] = None,
        format_id: Union[bool, str] = None,
        title: Union[bool, str] = None,
    ) -> Optional[str]:
        """
        Download audio or video via external API.

        Modes (checked in order):
          songvideo  → video via API
          songaudio  → audio via API
          video      → mp4 via API (fallback: YouTube URL)
          (default)  → mp3 via API
        """
        if videoid:
            link = self.base + link

        # Extract video ID from full URL
        match = re.search(r"(?:v=|youtu\.be/|shorts/)([A-Za-z0-9_-]{11})", link)
        video_id = match.group(1) if match else link

        async with self._download_semaphore:

            if songvideo:
                return await self._download_via_api(video_id, video=True)

            elif songaudio:
                return await self._download_via_api(video_id, video=False)

            elif video:
                result = await self._download_via_api(video_id, video=True)
                if result:
                    return result, True
                # Fallback: return stream URL directly
                return self.base + video_id, None

            else:
                result = await self._download_via_api(video_id, video=False)
                if result:
                    return result, True
                return None
    
