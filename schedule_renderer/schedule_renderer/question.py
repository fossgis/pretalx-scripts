class Question:
    def __init__(self, question_id, question_text, response):
        self.id = question_id
        self.question = question_text
        self.response = response

    def build_from_list(questions, locale):
        return { q["question"]["id"]: Question(q["question"]["id"], q["question"]["question"][locale], q["answer"]) for q in questions }
