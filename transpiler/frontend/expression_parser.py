from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class Token:
    kind: str
    text: str


class ExpressionParser:
    def parse(self, text: str) -> dict[str, object]:
        tokens = _tokenize(text)
        if not tokens:
            return {"kind": "empty"}
        self.tokens = tokens
        self.index = 0
        expr = self._parse_lambda()
        if self._peek("EOF"):
            return expr
        return {"kind": "raw", "text": text.strip()}

    def _parse_lambda(self) -> dict[str, object]:
        if self._peek("IDENT") and self._peek("ARROW", 1):
            param = self._consume("IDENT").text
            self._consume("ARROW")
            body = self._parse_expression()
            return {"kind": "lambda", "params": [param], "body": body}
        if self._peek("LPAREN"):
            snapshot = self.index
            try:
                self._consume("LPAREN")
                params: list[str] = []
                if not self._peek("RPAREN"):
                    while True:
                        params.append(self._consume("IDENT").text)
                        if not self._match("COMMA"):
                            break
                self._consume("RPAREN")
                if self._match("ARROW"):
                    if self._match("LBRACE"):
                        body_tokens: list[str] = []
                        depth = 1
                        while depth and not self._peek("EOF"):
                            tok = self._consume_any()
                            if tok.kind == "LBRACE":
                                depth += 1
                            elif tok.kind == "RBRACE":
                                depth -= 1
                                if depth == 0:
                                    break
                            body_tokens.append(tok.text)
                        return {"kind": "lambda_raw", "params": params, "body": "".join(body_tokens).strip()}
                    return {"kind": "lambda", "params": params, "body": self._parse_expression()}
            except Exception:
                self.index = snapshot
        return self._parse_expression()

    def _parse_expression(self) -> dict[str, object]:
        return self._parse_ternary()

    def _parse_ternary(self) -> dict[str, object]:
        expr = self._parse_or()
        if self._match("QUESTION"):
            then_expr = self._parse_expression()
            self._consume("COLON")
            else_expr = self._parse_expression()
            return {"kind": "ternary", "condition": expr, "then": then_expr, "else": else_expr}
        return expr

    def _parse_or(self) -> dict[str, object]:
        expr = self._parse_and()
        while self._match("OR"):
            rhs = self._parse_and()
            expr = {"kind": "binary", "op": "or", "left": expr, "right": rhs}
        return expr

    def _parse_and(self) -> dict[str, object]:
        expr = self._parse_equality()
        while self._match("AND"):
            rhs = self._parse_equality()
            expr = {"kind": "binary", "op": "and", "left": expr, "right": rhs}
        return expr

    def _parse_equality(self) -> dict[str, object]:
        expr = self._parse_relational()
        while self._peek("EQ") or self._peek("NE"):
            op = self._consume_any().text
            rhs = self._parse_relational()
            expr = {"kind": "binary", "op": op, "left": expr, "right": rhs}
        return expr

    def _parse_relational(self) -> dict[str, object]:
        expr = self._parse_additive()
        while self._peek("LT") or self._peek("LE") or self._peek("GT") or self._peek("GE"):
            op = self._consume_any().text
            rhs = self._parse_additive()
            expr = {"kind": "binary", "op": op, "left": expr, "right": rhs}
        return expr

    def _parse_additive(self) -> dict[str, object]:
        expr = self._parse_multiplicative()
        while self._peek("PLUS") or self._peek("MINUS"):
            op = self._consume_any().text
            rhs = self._parse_multiplicative()
            expr = {"kind": "binary", "op": op, "left": expr, "right": rhs}
        return expr

    def _parse_multiplicative(self) -> dict[str, object]:
        expr = self._parse_unary()
        while self._peek("STAR") or self._peek("SLASH") or self._peek("PERCENT"):
            op = self._consume_any().text
            rhs = self._parse_unary()
            expr = {"kind": "binary", "op": op, "left": expr, "right": rhs}
        return expr

    def _parse_unary(self) -> dict[str, object]:
        if self._match("BANG"):
            return {"kind": "unary", "op": "not", "value": self._parse_unary()}
        if self._match("MINUS"):
            return {"kind": "unary", "op": "-", "value": self._parse_unary()}
        return self._parse_postfix()

    def _parse_postfix(self) -> dict[str, object]:
        expr = self._parse_primary()
        while True:
            if self._match("DOT"):
                name = self._consume("IDENT").text
                expr = {"kind": "member", "target": expr, "name": name}
                continue
            if self._match("METHOD_REF"):
                name = self._consume("IDENT").text
                expr = {"kind": "method_ref", "target": expr, "name": name}
                continue
            if self._match("LPAREN"):
                args: list[dict[str, object]] = []
                if not self._peek("RPAREN"):
                    while True:
                        args.append(self._parse_expression())
                        if not self._match("COMMA"):
                            break
                self._consume("RPAREN")
                expr = {"kind": "call", "target": expr, "args": args}
                continue
            if self._match("LBRACKET"):
                index = self._parse_expression()
                self._consume("RBRACKET")
                expr = {"kind": "index", "target": expr, "index": index}
                continue
            break
        return expr

    def _parse_primary(self) -> dict[str, object]:
        if self._match("NUMBER"):
            return {"kind": "number", "value": self.tokens[self.index - 1].text}
        if self._match("STRING"):
            return {"kind": "string", "value": self.tokens[self.index - 1].text}
        if self._match("TRUE"):
            return {"kind": "bool", "value": True}
        if self._match("FALSE"):
            return {"kind": "bool", "value": False}
        if self._match("NULL"):
            return {"kind": "null"}
        if self._match("THIS"):
            return {"kind": "name", "value": "this"}
        if self._match("NEW"):
            type_name = self._consume("IDENT").text
            generics = ""
            if self._match("LT"):
                depth = 1
                parts = ["<"]
                while depth and not self._peek("EOF"):
                    tok = self._consume_any()
                    parts.append(tok.text)
                    if tok.kind == "LT":
                        depth += 1
                    elif tok.kind == "GT":
                        depth -= 1
                generics = "".join(parts)
            if self._match("LPAREN"):
                args: list[dict[str, object]] = []
                if not self._peek("RPAREN"):
                    while True:
                        args.append(self._parse_expression())
                        if not self._match("COMMA"):
                            break
                self._consume("RPAREN")
                return {"kind": "new_call", "type": type_name + generics, "args": args}
            dims: list[dict[str, object]] = []
            while self._match("LBRACKET"):
                if self._peek("RBRACKET"):
                    dims.append({"kind": "empty"})
                else:
                    dims.append(self._parse_expression())
                self._consume("RBRACKET")
            return {"kind": "new_array", "type": type_name, "dims": dims}
        if self._match("IDENT"):
            return {"kind": "name", "value": self.tokens[self.index - 1].text}
        if self._match("LPAREN"):
            expr = self._parse_expression()
            self._consume("RPAREN")
            return expr
        raise ValueError("unexpected token")

    def _peek(self, kind: str, offset: int = 0) -> bool:
        return self.tokens[self.index + offset].kind == kind

    def _match(self, kind: str) -> bool:
        if self._peek(kind):
            self.index += 1
            return True
        return False

    def _consume(self, kind: str) -> Token:
        if not self._peek(kind):
            raise ValueError(f"expected {kind}, got {self.tokens[self.index].kind}")
        tok = self.tokens[self.index]
        self.index += 1
        return tok

    def _consume_any(self) -> Token:
        tok = self.tokens[self.index]
        self.index += 1
        return tok


def _tokenize(text: str) -> list[Token]:
    tokens: list[Token] = []
    i = 0
    while i < len(text):
        ch = text[i]
        if ch.isspace():
            i += 1
            continue
        if text.startswith("->", i):
            tokens.append(Token("ARROW", "->"))
            i += 2
            continue
        if text.startswith("::", i):
            tokens.append(Token("METHOD_REF", "::"))
            i += 2
            continue
        if text.startswith("&&", i):
            tokens.append(Token("AND", "&&"))
            i += 2
            continue
        if text.startswith("||", i):
            tokens.append(Token("OR", "||"))
            i += 2
            continue
        if text.startswith("==", i):
            tokens.append(Token("EQ", "=="))
            i += 2
            continue
        if text.startswith("!=", i):
            tokens.append(Token("NE", "!="))
            i += 2
            continue
        if text.startswith("<=", i):
            tokens.append(Token("LE", "<="))
            i += 2
            continue
        if text.startswith(">=", i):
            tokens.append(Token("GE", ">="))
            i += 2
            continue
        if ch == '"':
            j = i + 1
            escaped = False
            while j < len(text):
                if text[j] == '"' and not escaped:
                    break
                escaped = text[j] == "\\" and not escaped
                if text[j] != "\\":
                    escaped = False
                j += 1
            tokens.append(Token("STRING", text[i : j + 1]))
            i = j + 1
            continue
        if ch.isdigit():
            j = i + 1
            while j < len(text) and text[j].isdigit():
                j += 1
            tokens.append(Token("NUMBER", text[i:j]))
            i = j
            continue
        if ch.isalpha() or ch == "_":
            j = i + 1
            while j < len(text) and (text[j].isalnum() or text[j] == "_"):
                j += 1
            word = text[i:j]
            kind = {
                "true": "TRUE",
                "false": "FALSE",
                "null": "NULL",
                "this": "THIS",
                "new": "NEW",
            }.get(word, "IDENT")
            tokens.append(Token(kind, word))
            i = j
            continue
        kind = {
            "(": "LPAREN",
            ")": "RPAREN",
            "[": "LBRACKET",
            "]": "RBRACKET",
            "{": "LBRACE",
            "}": "RBRACE",
            ".": "DOT",
            ",": "COMMA",
            "?": "QUESTION",
            ":": "COLON",
            "+": "PLUS",
            "-": "MINUS",
            "*": "STAR",
            "/": "SLASH",
            "%": "PERCENT",
            "!": "BANG",
            "<": "LT",
            ">": "GT",
        }.get(ch)
        if kind is None:
            return [Token("RAW", text), Token("EOF", "")]
        tokens.append(Token(kind, ch))
        i += 1
    tokens.append(Token("EOF", ""))
    return tokens

