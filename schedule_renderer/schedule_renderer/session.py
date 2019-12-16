import datetime
from .question import Question
from .speaker import Speaker
from .resource import Resource

PRETALX_DATE_FMT = "%Y-%m-%dT%H:%M:%S%z"

def transform_pretalx_date(d):
    """Remove last colon."""
    return datetime.datetime.strptime(d[:22] + d[-2:], PRETALX_DATE_FMT)

def url_to_code(u):
    parts = u.split("/")
    if parts[-1] == "":
        parts = parts[:-1]
    return parts[-1]


def escape_yaml_value_quote(text):
    """
    Escape text to be inserted into the YAML headers of markdown files.
    """
    # replace quotation mark by escaped quotation mark
    if text == "" or text is None:
        return ""
    return text.replace("\"", "\\\"")


class AbstractSession:
    def __init__(self, start, end, room):
        self.start = start
        self.end = end
        self.room = room
        self.render_content = True
        self.is_break = False
        self.render_abstract = True
        self.resources = []
        self.code = ""

    def mergeable(self):
        return False


class ContinuedSession(AbstractSession):
    """second/third part of a session spanning over more than one slot"""
    def __init__(self, start, end, room):
        super(ContinuedSession, self).__init__(start, end, room)
        self.render_content = False
        self.is_a_talk = True
        self.render_abstract = False


class Break(AbstractSession):
    def __init__(self, start, end, room, name, url):
        super(Break, self).__init__(start, end, room)
        self.title = name
        self.url = url
        self.is_break = True
        self.render_abstract = False

    def import_config(breaks, days, locale):
        result = []
        utc = datetime.timezone(datetime.timedelta(hours=0))
        for b in breaks:
            start = transform_pretalx_date(b["start"]).astimezone(utc)
            end = transform_pretalx_date(b["end"]).astimezone(utc)
            url = b.get("url")
            rooms = []
            for d in days:
                if d.is_same_day(start):
                    rooms = d.rooms
                    break
            name = b["name"][locale]
            for r in rooms:
                result.append(Break(start, end, r, name, url))
        return result

    def __repr__(self):
        return "Break {} {} {}".format(self.start, self.end, self.room)


class ExtraSession(AbstractSession):
    """Session which is not managed by Pretalx but provided via a configuration file. This is intended for conference photos, social events and parallel conferences/tracks."""
    def __init__(self, start, end, room, title, url):
        super(ExtraSession, self).__init__(start, end, room)
        self.title = title
        self.url = url
        self.render_content = True
        self.render_abstract = False

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
        return ExtraSession(start, end, rooms[kwargs["room_id"]], kwargs["title"][locale], kwargs.get("url", ""))

    def import_config(sessions, locale, rooms):
        return [ ExtraSession.build(locale, rooms, **s) for s in sessions ]

    def __repr__(self):
        return "ExtraSession {} {} {} {}".format(self.start, self.end, self.title, self.room)


class MetaSession(AbstractSession):
    """Session hosting multiple children sessions which is not managed by Pretalx but provided via a configuration file. This is intended for lightning talk sessions and similar short talks which would impair the overview table."""
    def __init__(self, start, end, room, title, code):
        super(MetaSession, self).__init__(start, end, room)
        self.talk = {"title": title}
        self.recording = True
        self.code = code
        self.children = []
        self.is_a_talk = True

    def add_child_session(self, child):
        self.children.append(child)
        self.recording = self.recording and self.recording

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
        return MetaSession(start, end, rooms[kwargs["room_id"]], kwargs["title"][locale], kwargs.get("code", ""))

    def import_config(sessions, locale, rooms):
        return [ MetaSession.build(locale, rooms, **s) for s in sessions ]

    def __repr__(self):
        return "MetaSession {} {} {} {}".format(self.start, self.end, self.title, self.room)



class Session(AbstractSession):
    def __init__(self, room, talk, locale, url_prefix):
        super(Session, self).__init__(transform_pretalx_date(talk["start"]), transform_pretalx_date(talk["end"]), room)
        self.room = room
        self.talk = talk
        self.title = talk["title"]
        self.short_abstract = talk.get("abstract")
        self.long_abstract = talk.get("description")
        self.speakers = [ Speaker(s["name"], s["code"]) for s in talk.get("speakers", []) ]
        self.duration = talk.get("duration")
        self.questions = Question.build_from_list(talk.get("answers", []), locale)
        if "url" in talk and "code" not in talk:
            self.code = url_to_code(talk["url"])
        else:
            self.code = talk.get("code", "")
        self.row_count = 1
        self.col_count = 1
        self.render_content = True
        self.is_a_talk = True
        self.recording = not talk.get("do_not_record", True)
        self.resources = Resource.from_list(talk.get("resources", []), self.code, url_prefix)

    def set_row_count(count):
        self.row_count = count

    def add_speaker_details(self, speakers_dict, locale):
        """
        Args
        ----
        speakers_dict : dict
            dictionary of all speakers mapping code to Speaker
        """
        for s in self.speakers:
            s.update(speakers_dict[s.code], locale)

    def set_speaker_names(self, affiliation_question_id=None):
        parts = []
        parts_with_affiliations = []
        for s in self.speakers:
            parts.append(s.name)
            if affiliation_question_id and s.questions.get(affiliation_question_id):
                if s.questions[affiliation_question_id].response:
                    parts_with_affiliations.append("{} ({})".format(s.name, s.questions[affiliation_question_id].response))
                else:
                    parts_with_affiliations.append(s.name)
            else:
                parts_with_affiliations.append(s.name)
        self.speaker_names_with_affiliations = [escape_yaml_value_quote(p) for p in parts_with_affiliations]
        self.speaker_names = ", ".join(parts)

    def __repr__(self):
        return "Session {} {} {} {} {}".format(self.start, self.end, self.room, self.talk, self.row_count)
