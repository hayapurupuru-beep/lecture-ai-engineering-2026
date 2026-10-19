from io import StringIO
from types import SimpleNamespace

from app import ask


class _TTYStringIO(StringIO):
    def isatty(self):
        return True


def test_read_interactive_line_enables_utf8_erase_and_restores_terminal(monkeypatch):
    import termios

    class FakeStdin(_TTYStringIO):
        def fileno(self):
            return 10

    original_attrs = [0, 1, 2, 3, 4, 5, []]
    terminal_attrs = original_attrs.copy()
    changes = []
    monkeypatch.setattr(ask.sys, "stdin", FakeStdin())

    def get_terminal_attrs(fd):
        assert fd == 10
        return original_attrs

    monkeypatch.setattr(termios, "tcgetattr", get_terminal_attrs)

    def set_terminal_attrs(fd, when, attrs):
        assert fd == 10
        assert when == termios.TCSANOW
        terminal_attrs[:] = attrs
        changes.append(attrs.copy())

    monkeypatch.setattr(termios, "tcsetattr", set_terminal_attrs)

    def read_input(prompt):
        assert prompt == "> "
        assert terminal_attrs[0] & 0o40000
        return "日本語"

    monkeypatch.setattr("builtins.input", read_input)

    assert ask._read_interactive_line() == "日本語"
    assert changes[0][0] & 0o40000
    assert changes[-1] == original_attrs


def test_interactive_chat_keeps_follow_up_questions_in_one_chat(monkeypatch, capsys):
    class FakeChat:
        def __init__(self):
            self.questions = []

        def send_message(self, question):
            self.questions.append(question)
            return SimpleNamespace(text=f"回答: {question}", usage_metadata=None)

    class FakeClient:
        def __init__(self, api_key):
            assert api_key == "test"
            self.chat = FakeChat()
            self.chats = SimpleNamespace(create=self.create_chat)

        def create_chat(self, model):
            assert model == ask.MODEL
            return self.chat

    client = FakeClient(api_key="test")

    def make_client(api_key):
        assert api_key == "test"
        return client

    monkeypatch.setattr(ask.genai, "Client", make_client)
    monkeypatch.setattr(ask, "get_api_key", lambda: "test")
    answers = iter(["LoRAとは？", "それの利点は？", "/exit"])

    def next_answer(prompt):
        assert prompt == "> "
        return next(answers)

    monkeypatch.setattr("builtins.input", next_answer)
    monkeypatch.setattr(ask.sys, "stdin", StringIO())

    ask.interactive_chat(first_question="LoRAとは何ですか？")

    assert client.chat.questions == ["LoRAとは何ですか？", "LoRAとは？", "それの利点は？"]
    output = capsys.readouterr().out
    assert "回答: LoRAとは何ですか？" in output
    assert "回答: それの利点は？" in output
    assert "[質問] LoRAとは？" not in output
    assert "[質問] それの利点は？" not in output


def test_interactive_chat_exits_on_end_of_input(monkeypatch):
    class FakeClient:
        def __init__(self, api_key):
            assert api_key == "test"

            def create_chat(model):
                assert model == ask.MODEL
                return SimpleNamespace()

            self.chats = SimpleNamespace(create=create_chat)

    monkeypatch.setattr(ask.genai, "Client", FakeClient)
    monkeypatch.setattr(ask, "get_api_key", lambda: "test")
    monkeypatch.setattr(ask.sys, "stdin", StringIO())

    def end_input(prompt):
        assert prompt == "> "
        raise EOFError

    monkeypatch.setattr("builtins.input", end_input)

    ask.interactive_chat()
