class Room:
    def __init__(self, room_id, name, position):
        self.id = room_id 
        self.name = name
        if position:
            self.position = position
        else:
            self.position = 999
        self.occupied = 0.0
        self.video = True

    def build(pretalx_room, locale, novideo):
        """Build a Room instance from a Pretalx serialised room."""
        r = Room(pretalx_room["id"], pretalx_room["name"][locale], pretalx_room["position"])
        r.video = not novideo
        return r

    def occupy(self, duration):
        self.occupied += duration/30.0

    def __repr__(self):
        return "Room {} {} {} {} {}".format(self.id, self.name, self.position, self.occupied, self.video)
