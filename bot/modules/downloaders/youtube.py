import requests
import aiohttp
from uuid import uuid4
from pydantic import BaseModel
from .shcemas import MediaDownloaded
from .base import BaseDownloader



class DownloadResponseMedia(BaseModel):
    formatId: int | str | None = None
    label: str
    type: str
    ext: str
    quality: str | None = None
    width: int | None = None
    height: int | None = None
    url: str
    bitrate: int
    fps: int | None = None
    audioQuality: str | None = None
    audioSampleRate: str | None = None
    mimeType: str
    duration: int
    
    
class DownloadResponseMedias(BaseModel):

    formats: list[DownloadResponseMedia] | None = None
    thumbnailUrl: str
    defaultFormatId: int
    duration: str
    title: str


class Youtube(BaseDownloader):
    
    def __init__(self, url: str) -> None:
        super().__init__(url)
        self.__api_url = "https://submagic-free-tools.fly.dev/api/youtube-info"
        self.__data = {
            "url": str(self.url)
        }
        
        self.__headers = {
            # "content-type": "application/json",
            # # "Content-Length": "<calculated when request is sent>",
            # # "Host": "<calculated when request is sent>",
            # "user-agent": "Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Mobile Safari/537.36",
            # "accept": "*/*",
            # "accept-language": "en-US,en;q=0.9",
            # "accept-encoding": "gzip, deflate, br",
            # "connection": "keep-alive",
            
            # "accept": "*/*",
            # "accept-encoding": "gzip, deflate, br, zstd",
            # "accept-language": "en-US,en;q=0.9",
            # # content-length: 53
            # "content-type": "application/json",
            # "origin": "https://submagic-free-tools.fly.dev",
            # "priority": "u=1, i",
            # "referer": "https://submagic-free-tools.fly.dev/youtube-downloader",
            # "sec-ch-ua": '"Chromium";v="128", "Not;A=Brand";v="24", "Google Chrome";v="128"',
            # "sec-ch-ua-mobile": "?1",
            # "sec-ch-ua-platform": '"Android"',
            # "sec-fetch-dest": "empty",
            # "sec-fetch-mode": "cors",
            # "sec-fetch-site": "same-origin",
            "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_9_5) AppleWebKit/600.7.12 (KHTML, like Gecko) Version/7.1.7 Safari/537.85.16",
        }
                
    async def download_video(self) -> MediaDownloaded:
        
        try:
                    
            async with aiohttp.ClientSession() as session:
                    
                async with session.post(url=self.__api_url, data=self.__data, headers=self.__headers) as response:
                
                    if response.status == 200:
                                                    
                        data = await response.json()
                        medias = DownloadResponseMedias(**data)
                        
                        for media in medias.formats:
                            if media.type == 'video_with_audio':
                                title = medias.title
                                url = media.url
                                del medias
                                async with session.get(url) as video:

                                    if video.status == 200:
                                        file_path = fr"./download/video/{uuid4()}.mp4"
                                        with open(file_path, "wb") as file:
                                            file.write(await video.read())
                                        del video
                                        return MediaDownloaded(MEDIA=file_path, TITLE=title, RESULT=True)
                                    else:
                                        return MediaDownloaded(MEDIA=url, TITLE=title, RESULT=True)
                                
                                break
                            
                            return MediaDownloaded(RESULT=None)
                                        
        except Exception as e:
            print("Error is Youtube download media :", e)
        
        return MediaDownloaded(RESULT=False)
        
