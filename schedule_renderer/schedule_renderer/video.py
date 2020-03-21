import schedule_renderer.resource

class Video:
    def __init__(self, **kwargs):
        self.slug = kwargs["slug"]
        self.thumb_url = kwargs["thumb_url"]
        self.poster_url = kwargs["poster_url"]
        self.frontend_link = kwargs["frontend_link"]
        link = kwargs["link"]
        link = link.rstrip("/")
        self.code = link.split("/")[-1]
        if len(self.code) != 6:
            raise Exception("Session code in link property seems to be invalid, got \"{}\" but expected 6 alphanumeric characters.".format(self.code))

    def load_media_ccc_de_json(data):
        videos = {}
        for e in data["events"]:
            v = Video(**e)
            videos[v.code] = v
        return videos

    def thumb_filename(self):
        return schedule_renderer.resource.clean_filename(self.thumb_url)

    def poster_filename(self):
        return schedule_renderer.resource.clean_filename(self.poster_url)
