import time

import win32gui

from event_manager.event_manager import EventManager


class ActiveWindowWatcher:

    def __init__(self, event_manager: EventManager):

        self.event_manager = event_manager
        self.previous_window = ""

    def start(self):

        while True:

            window = win32gui.GetWindowText(
                win32gui.GetForegroundWindow()
            )

            if window != self.previous_window:

                self.previous_window = window

                self.event_manager.emit(
                    "WINDOW_CHANGED",
                    window
                )

            time.sleep(0.5)