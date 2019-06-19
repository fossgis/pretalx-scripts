class Slot:
    def __init__(self, start, end):
        self.start = start
        self.end = end
        self.sessions = {}

    def add_session(self, session):
        self.sessions[session.room] = session

    def sort_sessions_and_fill_gaps(self):
        self.sessions = [ v for k,v in self.sessions.items() ]
        self.sessions.sort(key=lambda k: k.room.position)
