import datetime

PRETALX_DATE_FMT = "%Y-%m-%dT%H:%M:%S%z"

def transform_pretalx_date(d):
    """Remove last colon."""
    return datetime.datetime.strptime(d[:22] + d[-2:], PRETALX_DATE_FMT)

class Session:
    def __init__(self, room, talk):
        self.start = transform_pretalx_date(talk["start"])
        self.end = transform_pretalx_date(talk["end"])
        self.room = room
        self.talk = talk
        self.row_count = 1

    def set_row_count(count):
        self.row_count = count

    def __repr__(self):
        return "Session {} {} {} {} {}".format(self.start, self.end, self.room, self.talk, self.row_count)
