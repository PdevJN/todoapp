from collections.abc import Callable
from pathlib import Path
from typing import Any

from nicegui import events, ui


class FullCalendar(ui.element, component='fullcalendar.js'):

    def __init__(
        self,
        options: dict[str, Any],
        on_click: Callable | None = None,
        on_change: Callable | None = None,
    ) -> None:
        """FullCalendar

        An element that integrates the FullCalendar library (https://fullcalendar.io/) to create an interactive calendar display.
        For an example of the FullCalendar library with plugins see https://github.com/dorel14/NiceGui-FullCalendar_more_Options

        :param options: dictionary of FullCalendar properties for customization, such as "initialView", "slotMinTime", "slotMaxTime", "allDaySlot", "timeZone", "height", and "events".
        :param on_click: callback that is called when a calendar event is clicked.
        :param on_change: callback that is called when an event is dragged or resized. `e.args` is
            `{"id", "kind": "move" | "resize", "edge": "start" | "end" | None, "start", "end"}` with local ISO times.
            The dragged position is reverted on the client, so the callback must update `events` to move it.
        """
        super().__init__()
        self.add_resource(Path(__file__).parent / 'lib')
        self._props['options'] = options
        self._update_method = 'update_calendar'

        if on_click:
            self.on('click', lambda e: events.handle_event(on_click, e))
        if on_change:
            self.on('event_change', lambda e: events.handle_event(on_change, e))

    def add_event(self, title: str, start: str, end: str, **kwargs) -> None:
        """Add an event to the calendar.

        :param title: title of the event
        :param start: start time of the event
        :param end: end time of the event
        """
        event_dict = {'title': title, 'start': start, 'end': end, **kwargs}
        self._props['options']['events'].append(event_dict)

    def remove_event(self, title: str, start: str, end: str) -> None:
        """Remove an event from the calendar.

        :param title: title of the event
        :param start: start time of the event
        :param end: end time of the event
        """
        for event in self._props['options']['events']:
            if event['title'] == title and event['start'] == start and event['end'] == end:
                self._props['options']['events'].remove(event)
                break

    @property
    def events(self) -> list[dict]:
        """List of events currently displayed in the calendar."""
        return self._props['options']['events']
