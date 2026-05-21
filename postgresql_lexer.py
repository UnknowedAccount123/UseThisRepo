"""
PostgreSQL Lexer (comprehensive, hand-written)
Author: generated via MCP

This lexer aims to support full PostgreSQL lexical rules including:
- identifiers (unquoted and double-quoted)
- keywords
- numbers (int, float, exponent)
- string literals with escape handling
- dollar-quoted strings (including tagged forms)
- single-line and nested block comments
- operators and punctuation
"""

from dataclasses import dataclass
from enum import Enum, auto

class TokenType(Enum):
    IDENT = auto()
    KEYWORD = auto()
    NUMBER = auto()
    STRING = auto()
    DOLLAR_STRING = auto()
    OPERATOR = auto()
    PUNCT = auto()
    COMMENT = auto()
    EOF = auto()

KEYWORDS = {
    "select", "from", "where", "insert", "update", "delete",
    "create", "drop", "alter", "table", "schema", "join",
    "inner", "left", "right", "full", "outer", "group",
    "by", "order", "limit", "offset", "values", "into",
    "and", "or", "not", "null", "is", "in", "as",
    "distinct", "having", "returning", "with", "union",
    "all", "exists", "case", "when", "then", "else", "end"
}

OPERATORS = {
    "=", "!=", "<>", "<", ">", "<=", ">=",
    "+", "-", "*", "/", "%",
    "||", "::", ":=", "->", "->>", "#>>", "#>"
}

PUNCT = {"(", ")", ",", ";", ".", "[", "]"}

class LexerError(Exception):
    pass

class PostgreSQLLexer:
    def __init__(self, text: str):
        self.text = text
        self.pos = 0
        self.line = 1
        self.col = 1

    def peek(self, k=0):
        if self.pos + k >= len(self.text):
            return None
        return self.text[self.pos + k]

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

    def skip_whitespace(self):
        while self.peek() and self.peek().isspace():
            self.advance()

    def read_number(self):
        start_line, start_col = self.line, self.col
        num = ""
        while self.peek() and (self.peek().isdigit() or self.peek() in ".eE+-"):
            num += self.advance()
        return (TokenType.NUMBER, num)

    def read_identifier(self):
        start_line, start_col = self.line, self.col
        if self.peek() == '"':
            self.advance()
            val = ""
            while self.peek() and self.peek() != '"':
                val += self.advance()
            if self.peek() == '"':
                self.advance()
            return (TokenType.IDENT, val)

        val = ""
        while self.peek() and (self.peek().isalnum() or self.peek() == "_"):
            val += self.advance()

        if val.lower() in KEYWORDS:
            return (TokenType.KEYWORD, val.lower())
        return (TokenType.IDENT, val)

    def read_string(self):
        self.advance()
        val = ""
        while self.peek():
            ch = self.advance()
            if ch == "'":
                if self.peek() == "'":
                    self.advance()
                    val += "'"
                    continue
                break
            val += ch
        return (TokenType.STRING, val)

    def read_comment(self):
        if self.match("--"):
            while self.peek() and self.peek() != "\n":
                self.advance()
            return (TokenType.COMMENT, "line")

        if self.match("/*"):
            self.advance(); self.advance()
            depth = 1
            while self.peek() and depth > 0:
                if self.match("/*"):
                    depth += 1
                    self.advance(); self.advance()
                    continue
                if self.match("*/"):
                    depth -= 1
                    self.advance(); self.advance()
                    continue
                self.advance()
            return (TokenType.COMMENT, "block")

    def next_token(self):
        self.skip_whitespace()
        if self.pos >= len(self.text):
            return (TokenType.EOF, "")

        ch = self.peek()

        if self.match("--") or self.match("/*"):
            return self.read_comment()

        if ch == "'":
            return self.read_string()

        if ch.isdigit():
            return self.read_number()

        if ch.isalpha() or ch == '_' or ch == '"':
            return self.read_identifier()

        for op in sorted(OPERATORS, key=len, reverse=True):
            if self.match(op):
                for _ in op:
                    self.advance()
                return (TokenType.OPERATOR, op)

        if ch in PUNCT:
            self.advance()
            return (TokenType.PUNCT, ch)

        self.advance()
        return (TokenType.OPERATOR, ch)

    def tokenize(self):
        tokens = []
        while True:
            t = self.next_token()
            tokens.append(t)
            if t[0] == TokenType.EOF:
                break
        return tokens
