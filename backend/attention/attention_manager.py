class AttentionManager:

    def __init__(self):

        self.ignored_apps = [
            "Spotify",
            "Calculator"
        ]

    def should_observe(self, window_title):

        if not window_title.strip():
            return False

        for app in self.ignored_apps:

            if app.lower() in window_title.lower():
                return False

        return True