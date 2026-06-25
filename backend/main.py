from event_manager.event_manager import EventManager
from system.active_window import ActiveWindowWatcher


event_manager = EventManager()


def on_window_changed(window):

    print(f"\n🪟 Active Window")

    print(window)


event_manager.subscribe(
    "WINDOW_CHANGED",
    on_window_changed
)


watcher = ActiveWindowWatcher(
    event_manager
)

watcher.start()