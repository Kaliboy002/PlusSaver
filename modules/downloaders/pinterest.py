from shcemas import MediaDownloaded
from base import BaseDownloader

class Pinterest(BaseDownloader):
    
    def __init__(self, url: str) -> None:
        super().__init__(url)
        
    def download_image(self) -> MediaDownloaded:
        pass