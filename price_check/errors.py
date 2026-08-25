class PlatformError(Exception):
    def __init__(self, message: str, screenshot: bytes | None = None, url: str | None = None):
        super().__init__(message)
        self.screenshot = screenshot
        self.url = url
