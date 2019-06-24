import datetime

PRETALX_DATE_FMT = "%Y-%m-%dT%H:%M:%S%z"

def transform_pretalx_date(d):
    """Remove last colon."""
    return datetime.datetime.strptime(d[:22] + d[-2:], PRETALX_DATE_FMT)

def url_to_code(u):
    parts = u.split("/")
    if parts[-1] == "":
        parts = parts[:-1]
    return parts[-1]


class AbstractSession:
    def __init__(self, start, end, room):
        self.start = start
        self.end = end
        self.room = room
        self.render_content = True
        self.is_break = False
        self.is_a_talk = False


class ContinuedSession(AbstractSession):
    """second/third part of a session spanning over more than one slot"""
    def __init__(self, start, end, room):
        super(ContinuedSession, self).__init__(start, end, room)
        self.render_content = False
        self.is_a_talk = True


class Break(AbstractSession):
    def __init__(self, start, end, room, name):
        super(Break, self).__init__(start, end, room)
        self.title = name
        self.is_break = True

    def import_config(breaks, days, locale):
        result = []
        utc = datetime.timezone(datetime.timedelta(hours=0))
        for b in breaks:
            start = transform_pretalx_date(b["start"]).astimezone(utc)
            end = transform_pretalx_date(b["end"]).astimezone(utc)
            rooms = []
            for d in days:
                if d.is_same_day(start):
                    rooms = d.rooms
                    break
            name = b["name"][locale]
            for r in rooms:
                result.append(Break(start, end, r, name))
        return result

    def __repr__(self):
        return "Break {} {} {}".format(self.start, self.end, self.room)


class ExtraSession(AbstractSession):
    """Session which is not managed by Pretalx but provided via a configuration file. This is intended for conference photos, social events and parallel conferences/tracks."""
    def __init__(self, start, end, room, title):
        super(ExtraSession, self).__init__(start, end, room)
        self.title = title
        self.render_content = True

    def build(locale, rooms, **kwargs):
        """Factory function for ExtraSession class.

        Parameters
        ----------
        locale : string
            locale, e.g. 'en'
        rooms : dict of int,Room
            rooms
        """
        start = transform_pretalx_date(kwargs["start"])
        end = transform_pretalx_date(kwargs["end"])
        return ExtraSession(start, end, rooms[kwargs["room_id"]], kwargs["title"][locale])

    def import_config(sessions, locale, rooms):
        return [ ExtraSession.build(locale, rooms, **s) for s in sessions ]

    def __repr__(self):
        return "ExtraSession {} {} {} {}".format(self.start, self.end, self.title, self.room)


class Session(AbstractSession):
    def __init__(self, room, talk):
        super(Session, self).__init__(transform_pretalx_date(talk["start"]), transform_pretalx_date(talk["end"]), room)
        self.room = room
        self.talk = talk
        if "url" in talk and "code" not in talk:
            self.code = url_to_code(talk["url"])
        else:
            self.code = talk.get("code", "")
        self.speaker_names = ", ".join([ s["name"] for s in talk["speakers"] ])
        self.row_count = 1
        self.col_count = 1
        self.render_content = True
        self.is_a_talk = True
        self.recording = not talk.get("do_not_record", False)

    def set_row_count(count):
        self.row_count = count

    def __repr__(self):
        return "Session {} {} {} {} {}".format(self.start, self.end, self.room, self.talk, self.row_count)
