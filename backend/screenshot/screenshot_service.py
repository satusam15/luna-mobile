import mss


import mss


class ScreenshotService:

    def capture(self, filename="screenshot.png"):

        with mss.mss() as sct:

            sct.shot(
                mon=1,
                output=filename
            )

        return filename