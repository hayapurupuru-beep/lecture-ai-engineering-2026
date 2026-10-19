"""第1回: 素のLLMに質問するスクリプト。

使い方:
    uv run python -m app.ask "LoRAとは何ですか？"
    uv run python -m app.ask            # 質問を省略すると、講座に固有の質問をする
    uv run python -m app.ask --interactive
    uv run python -m app.ask --interactive "LoRAとは何ですか？"

通常モードは1回だけ質問する。--interactive では同じチャットを使い続けるため、
起動中の会話履歴を保ったまま追加の質問ができる。
ツールを持たない「素の」呼び出し。
講座に固有のことを聞くと、「分からない」と答えるか、一般論でもっともらしく答える
（講座の実際とは違う）ことを確かめよう。
（第3回で、用語集を検索できるエージェントにして改善する）
"""

import argparse
import sys

from google import genai
from google.genai.chats import Chat
from google.genai import errors

from app.config import MODEL, api_error_message, get_api_key

# 講座に固有の質問。正しい答えは data/glossary.json の homework-levels にある
DEFAULT_QUESTION = "AIE2026の講座の宿題にある「3レベル」とは何ですか？"


def _print_usage(response) -> None:
    usage = response.usage_metadata
    if usage is None:
        print("[トークン数] 使用量情報を取得できませんでした")
    else:
        print(f"[入力トークン数] {usage.prompt_token_count}")
        print(f"[出力トークン数] {usage.candidates_token_count}")


def ask(question: str) -> str:
    client = genai.Client(api_key=get_api_key())
    response = client.models.generate_content(model=MODEL, contents=question)
    _print_usage(response)

    return response.text


def _ask_chat(chat: Chat, question: str) -> str:
    response = chat.send_message(question)
    _print_usage(response)
    return response.text


def _read_interactive_line() -> str:
    if not sys.stdin.isatty() or not sys.platform.startswith("linux"):
        return input("> ")

    import termios

    fd = sys.stdin.fileno()
    original_attrs = termios.tcgetattr(fd)
    attrs = original_attrs.copy()
    # Linux IUTF8 enables UTF-8-aware erase handling in the terminal line discipline.
    attrs[0] |= getattr(termios, "IUTF8", 0o40000)
    termios.tcsetattr(fd, termios.TCSANOW, attrs)
    try:
        return input("> ")
    finally:
        termios.tcsetattr(fd, termios.TCSANOW, original_attrs)


def interactive_chat(first_question: str | None = None) -> None:
    client = genai.Client(api_key=get_api_key())
    chat = client.chats.create(model=MODEL)

    if first_question:
        print(f"[質問] {first_question}\n")
        print(_ask_chat(chat, first_question))

    while True:
        print("\n質問（/exit で終了）")
        try:
            raw_question = _read_interactive_line()
        except EOFError:
            print()
            break

        question = raw_question.strip()
        if question.lower() in {"/exit", "/quit", "exit", "quit", "終了"}:
            break
        if not question:
            continue

        print(_ask_chat(chat, question))


def main() -> None:
    parser = argparse.ArgumentParser(description="素のLLMに質問する")
    parser.add_argument("question", nargs="?")
    parser.add_argument(
        "-i",
        "--interactive",
        action="store_true",
        help="起動中の会話履歴を保って続けて質問する",
    )
    args = parser.parse_args()

    print(f"[model] {MODEL}")
    try:
        if args.interactive:
            interactive_chat(args.question)
        else:
            question = args.question or DEFAULT_QUESTION
            print(f"[質問] {question}\n")
            print(ask(question))
    except errors.APIError as e:
        print(api_error_message(e.code, e.message))
        raise SystemExit(1)


if __name__ == "__main__":
    main()
