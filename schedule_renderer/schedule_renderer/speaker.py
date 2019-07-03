from .question import Question

class Speaker:
    def __init__(self, name, code):
        self.name = name
        self.code = code
        self.questions = {}
        self.biography = None

    def set_questions(self, questions_raw, locale):
        self.questions = Question.build_from_list(questions_raw, locale)

    def update(self, data, locale):
        self.biography = data["biography"]
        self.name = data["name"]
        self.set_questions(data.get("answers", []), locale)

    def __repr__(self):
        return "Speaker(name='{}', biography='{}', questions='{}')".format(self.name, self.biography, self.questions)
