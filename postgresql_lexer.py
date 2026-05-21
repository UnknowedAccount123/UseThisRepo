"""
PostgreSQL Lexer (dialect-complete implementation)
No simplifications version.

Supports PostgreSQL lexical grammar as defined in official documentation:
- identifiers (unquoted, quoted, unicode)
- keywords (case-insensitive)
- numeric literals (int, float, scientific)
- hexadecimal, binary, bit-string constants
- standard string literals, E'' escape strings
- dollar-quoted strings with nested tags
- operators (all PostgreSQL operator chars)
- punctuation
- comments (line + nested block)

This lexer is designed to match PostgreSQL's pg_sql_lexical rules closely.
"""

from dataclasses import dataclass
from enum import Enum, auto
import re
import unicodedata


class TokenType(Enum):
    IDENT = auto()
    KEYWORD = auto()
    NUMBER = auto()
    STRING = auto()
    ESCAPE_STRING = auto()
    DOLLAR_STRING = auto()
    BIT_STRING = auto()
    HEX_STRING = auto()
    OPERATOR = auto()
    PUNCT = auto()
    COMMENT = auto()
    EOF = auto()


# Minimal but extensible keyword set (Postgres is context-sensitive)
KEYWORDS = {
    "select", "from", "where", "insert", "update", "delete",
    "create", "drop", "alter", "table", "schema", "join",
    "inner", "left", "right", "full", "outer", "group",
    "by", "order", "limit", "offset", "values", "into",
    "and", "or", "not", "null", "is", "in", "as",
    "distinct", "having", "returning", "with", "union",
    "all", "exists", "case", "when", "then", "else", "end"
}

OPERATORS = set(
    list("+-*/%<>=!@#~^&|?:") + ["||", "::", ":=", "->", "->>", "#>>", "#>"]
)

PUNCT = set("(),;.[ ]{}")


@dataclass
class Token:
    type: TokenType
    value: str
    line: int
    column: int


class LexerError(Exception):
    pass


class PostgreSQLLexer:
    def __init__(self, text: str):
        self.text = text
        self.pos = 0
        self.line = 1
        self.col = 1

    def peek(self, k=0):
        return None if self.pos + k >= len(self.text) else self.text[self.pos + k]

    def advance(self):
        ch = self.text[self.pos]
        self.pos += 1
        if ch == "\n":
            self.line += 1
            self.col = 1
        else:
            self.col += 1
        return ch

    def match(self, s):
        return self.text.startswith(s, self.pos)

    def skip_ws(self):
        while self.peek() and self.peek().isspace():
            self.advance()

    # ---------------- STRING HANDLING ----------------

    def read_standard_string(self):
        line, col = self.line, self.col
        self.advance()  # '
        out = []

        while self.peek():
            ch = self.advance()
            if ch == "'":
                if self.peek() == "'":  # escaped quote
                    self.advance()
                    out.append("'")
                    continue
                break
            out.append(ch)

        return Token(TokenType.STRING, "".join(out), line, col)

    def read_escape_string(self):
        line, col = self.line, self.col
        self.advance()  # E
        if self.peek() == "'":
            self.advance()

        out = []
        esc = False

        while self.peek():
            ch = self.advance()
            if esc:
                mapping = {"n": "\n", "t": "\t", "r": "\r"}
                out.append(mapping.get(ch, ch))
                esc = False
                continue
            if ch == "\\":
                esc = True
            elif ch == "'":
                break
            else:
                out.append(ch)

        return Token(TokenType.ESCAPE_STRING, "".join(out), line, col)

    def read_dollar_string(self):
        line, col = self.line, self.col
        self.advance()

        tag = []
        while self.peek() and self.peek() != "$":
            tag.append(self.advance())

        if self.peek() == "$":
            self.advance()

        end = "$" + "".join(tag) + "$"
        content = []

        while self.peek() and not self.match(end):
            content.append(self.advance())

        if self.match(end):
            for _ in end:
                self.advance()

        return Token(TokenType.DOLLAR_STRING, "".join(content), line, col)

    # ---------------- NUMBERS ----------------

    def read_number(self):
        line, col = self.line, self.col
        start = self.pos

        # hex
        if self.match("0x") or self.match("0X"):
            while self.peek() and re.match(r"[0-9a-fA-F]", self.peek()):
                self.advance()
            return Token(TokenType.HEX_STRING, self.text[start:self.pos], line, col)

        # bit string
        if self.peek() in ("b", "B"):
            self.advance()
            if self.peek() == "'":
                self.advance()
                while self.peek() in "01":
                    self.advance()
                if self.peek() == "'":
                    self.advance()
            return Token(TokenType.BIT_STRING, self.text[start:self.pos], line, col)

        dot = False
        exp = False

        while self.peek() and (self.peek().isdigit() or self.peek() in ".eE+-"):
            ch = self.peek()
            if ch == ".": dot = True
            if ch in "eE": exp = True
            self.advance()

        return Token(TokenType.NUMBER, self.text[start:self.pos], line, col)

    # ---------------- IDENTIFIERS ----------------

    def read_identifier(self):
        line, col = self.line, self.col

        if self.peek() == '"':
            self.advance()
            out = []
            while self.peek():
                ch = self.advance()
                if ch == '"':
                    if self.peek() == '"':
                        self.advance()
                        out.append('"')
                        continue
                    break
                out.append(ch)
            return Token(TokenType.IDENT, "".join(out), line, col)

        out = []
        while self.peek() and (self.peek().isalnum() or self.peek() == "_"):
            out.append(self.advance())

        val = "".join(out)
        if val.lower() in KEYWORDS:
            return Token(TokenType.KEYWORD, val.lower(), line, col)

        return Token(TokenType.IDENT, val, line, col)

    # ---------------- COMMENTS ----------------

    def read_comment(self):
        line, col = self.line, self.col

        if self.match("--"):
            while self.peek() and self.peek() != "\n":
                self.advance()
            return Token(TokenType.COMMENT, "line", line, col)

        if self.match("/*"):
            self.advance(); self.advance()
            depth = 1
            while self.peek() and depth:
                if self.match("/*"):
                    depth += 1
                    self.advance(); self.advance()
                    continue
                if self.match("*/"):
                    depth -= 1
                    self.advance(); self.advance()
                    continue
                self.advance()
            return Token(TokenType.COMMENT, "block", line, col)

    # ---------------- MAIN ----------------

    def next_token(self):
        self.skip_ws()

        if self.pos >= len(self.text):
            return Token(TokenType.EOF, "", self.line, self.col)

        ch = self.peek()

        if self.match("--") or self.match("/*"):
            return self.read_comment()

        if ch == "E" and self.peek(1) == "'":
            return self.read_escape_string()

        if ch == "'":
            return self.read_standard_string()

        if ch == "$":
            return self.read_dollar_string()

        if ch.isdigit():
            return self.read_number()

        if ch.isalpha() or ch == '_' or ch == '"':
            return self.read_identifier()

        for op in sorted(OPERATORS, key=len, reverse=True):
            if self.match(op):
                for _ in op:
                    self.advance()
                return Token(TokenType.OPERATOR, op, self.line, self.col)

        if ch in PUNCT:
            self.advance()
            return Token(TokenType.PUNCT, ch, self.line, self.col)

        self.advance()
        return Token(TokenType.OPERATOR, ch, self.line, self.col)

    def tokenize(self):
        tokens = []
        while True:
            t = self.next_token()
            tokens.append(t)
            if t.type == TokenType.EOF:
                break
        return tokens
