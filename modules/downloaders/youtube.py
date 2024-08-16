from pytube import YouTube
from typing import Optional
from .shcemas import MediaDownloaded
from ..regexs import Regexs
from ..enums import YoutubeVideResoloution


class Youtube:
    
    def __init__(self, url: str) -> None:
        self.url = url
        self.save_video_address = r"./download/youtube/video"
        self.save_music_address = r"./download/youtube/music"
        self.youtube_client = YouTube(self.url)

    def get_resolutions(self) -> list:
        """get_resolutions methdo for get video resolutions
        
        >>> Youtube('url').get_resolutions()

        Returns:
            list: a list of Stream object
        """
        resolutions = self.youtube_client.streams.all()
        return resolutions

    def download_music(self):
        pass

    def download_video(self, resolution: Optional[str] = YoutubeVideResoloution.R_144P.value) -> MediaDownloaded:
        """download_video method for download vide from youtube with custom resolution
        
        >>> Youtube('url').download_video(resolution=YoutubeVideResoloution.R_144P.value)
        or
        >>> Youtube('url').download_video(resolution='720p')

        Args:
            resolution (Optional[str], optional): _description_. Defaults to "144p".

        Returns:
            MediaDownloaded: ...
        """
        
        try:
            video = self.youtube_client.streams.get_by_resolution(resolution).download(self.save_music_address)
            media = MediaDownloaded(PATH=video, TITLE=self.youtube_client.title, CAPTION=self.youtube_client.description)
        except Exception as e:
            print("Error in download_video method: ", e)
            media = MediaDownloaded()
        
        return media
