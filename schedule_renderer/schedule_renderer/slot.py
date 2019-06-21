class Slot:
    def __init__(self, start, end):
        self.start = start
        self.end = end
        self.sessions = []

    def add_session(self, session):
        self.sessions.append(session)

    def is_break(self):
        has_break = False
        for s in self.sessions:
            if s is not None:
                has_break = has_break or s.is_break
        return has_break

    def rendering_required(self):
        count = 0
        for s in self.sessions:
            if s is not None and s.render_content:
                count += 1
        return count > 0 

    def sort_sessions(self):
        self.sessions.sort(key=lambda s: s.room.order_key())

    def fill_gaps(self, day):
        self.sort_sessions()
        tmp_sessions = []
        sessions_idx = 0
        if len(day.rooms) < len(self.sessions):
            print(day.rooms)
            print("-------------")
            for s in self.sessions:
                print(s)
                print(",,,,,,,,,,,,,,,,,,,,,")
            raise Exception("More sessions than rooms")
        for rooms_idx in range(0, len(day.rooms)):
            if len(self.sessions) <= sessions_idx:
                tmp_sessions.append(None)
            elif self.sessions[sessions_idx].room.id != day.rooms[rooms_idx].id:
                tmp_sessions.append(None)
            else:
                tmp_sessions.append(self.sessions[sessions_idx])
                sessions_idx += 1
        self.sessions = tmp_sessions
