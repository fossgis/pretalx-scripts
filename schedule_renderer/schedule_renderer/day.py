class Day:
    def __init__(self, date, room):
        self.date = date
        self.rooms = [room]

    def is_same_day(self, other):
        """Check if other is the same day (time does not matter)."""
        return other.year == self.date.year and other.month == self.date.month and other.day == self.date.day

    def add_room(self, room):
        if room not in self.rooms:
            self.rooms.append(room)

    def sort_rooms(self):
        self.rooms.sort(key=lambda r: r.order_key())

    def weekday(d):
        return d.date.strftime("%A")

    def strftime(self, fmt):
        return self.date.strftime(fmt)
