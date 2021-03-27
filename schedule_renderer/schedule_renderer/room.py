class Room:
    def __init__(self, room_id, name, position):
        self.id = room_id 
        self.name = name
        if position is not None:
            self.position = position
        else:
            self.position = 999
        self.occupied = 0.0
        self.video = True

    def build(pretalx_room, locale, has_video):
        """Build a Room instance from a Pretalx serialised room."""
        r = Room(pretalx_room["id"], pretalx_room["name"][locale], pretalx_room["position"])
        r.video = has_video
        return r

    def order_key(self):
        return (self.position, self.name)

    def occupy(self, duration):
        self.occupied += duration/30.0

    def __repr__(self):
        return "Room(id={}, name={}, position={}, occupied={}, video={})".format(self.id, self.name, self.position, self.occupied, self.video)
