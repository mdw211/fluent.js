import re
from l20n.format.lol import ast
import string

class ParserError(Exception):
    pass

class Parser():
    patterns = {
        'id': re.compile('^([a-zA-Z]\w*)'),
        'value': re.compile('^(?P<op>[\'"])(.*?)(?<!\\\)(?P=op)'),
    }
    _parse_strings = False

    def parse(self, content, parse_strings=True):
        lol = ast.LOL()
        lol._struct = True
        lol._template2 = []
        self.content = content
        self._parse_strings = parse_strings
        lol._template2.append(self.get_ws())
        while self.content:
            try:
                lol.body.append(self.get_entry())
            except IndexError:
                raise ParserError()
            lol._template2.append(self.get_ws())
        return lol

    def get_ws(self, wschars=string.whitespace):
        try:
            if self.content[0] not in wschars:
                return ''
        except IndexError:
            return ''
        content = self.content.lstrip()
        ws = self.content[:len(content)*-1 or None]
        self.content = content
        return ws

    def get_entry(self):
        if self.content[0] == '<':
            self.content = self.content[1:]
            id = self.get_identifier()
            if self.content[0] == '(':
                entry = self.get_macro(id)
            elif self.content[0] == '[':
                index = self.get_index()
                entry = self.get_entity(id, index)
            else:
                entry = self.get_entity(id)
        elif self.content[0:2] == '/*':
            entry = self.get_comment()
        else:
            raise ParserError()
        return entry

    def get_identifier(self):
        match = self.patterns['id'].match(self.content)
        if not match:
            raise ParserError()
        self.content = self.content[match.end(0):]
        return ast.Identifier(match.group(1))

    def get_entity(self, id, index=None):
        ws1 = self.get_ws()
        if self.content[0] == '>':
            self.content = self.content[1:]
            entity = ast.Entity(id, index)
            entity._template = "<%%s%s%%s%%s%%s>" % ws1
            return entity
        if ws1 == '':
            raise ParserError()
        value = self.get_value(none=True)
        ws2 = self.get_ws()
        attrs = self.get_attributes()
        entity = ast.Entity(id,
                            index,
                            value,
                            attrs)
        if index is not None:
            entity._template = "<%%(id)s[%%(index)s]%s%%(value)s%s%%(attrs)s>" % (ws1,ws2)
        else:
            entity._template = "<%%(id)s%s%%(value)s%s%%(attrs)s>" % (ws1,ws2)
        return entity

    def get_macro(self, id):
        idlist = []
        self.content = self.content[1:]
        self.get_ws()
        if self.content[0] == ')':
            self.content = self.content[1:]
        else:
            while 1:
                idlist.append(self.get_identifier())
                self.get_ws()
                if self.content[0] == ',':
                    self.content = self.content[1:]
                    self.get_ws()
                elif self.content[0] == ')':
                    self.content = self.content[1:]
                    break
                else:
                    raise ParserError()
        ws = self.get_ws()
        if ws == '':
            raise ParserError()
        if self.content[0] != '{':
            raise ParserError()
        self.content = self.content[1:]
        exp = self.get_expression()
        self.get_ws()
        if self.content[0] != '}':
            raise ParserError()
        self.content = self.content[1:]
        ws = self.get_ws()
        attrs = self.get_attributes()
        return ast.Macro(id,
                         idlist,
                         exp,
                         attrs)

    def get_value(self, none=False):
        c = self.content[0]
        if c in ('"', "'"):
            if self._parse_strings:
                value = self.get_complex_string()
            else:
                value = self.get_string()
        elif c == '[':
            value = self.get_array()
        elif c == '{':
            value = self.get_hash()
        else:
            if none is True:
                return None
            raise ParserError()
        return value

    def get_string(self):
        match = self.patterns['value'].match(self.content)
        if not match:
            raise ParserError()
        self.content = self.content[match.end(0):]
        return ast.String(match.group(2))

    def get_complex_string(self):
        str_end = self.content[0]
        literal = re.compile('^([^\\\{%s]+)' % str_end)
        obj = []
        buffer = ''
        self.content = self.content[1:]
        while self.content[0] != str_end:
            if self.content[0] == '\\':
                buffer += self.content[1]
                self.content = self.content[2:]
            if self.content[:2] == '{{':
                self.content = self.content[2:]
                if buffer:
                    obj.append(ast.String(buffer))
                    buffer = ''
                obj.append(self.get_expression())
                if self.content[:2] != '}}':
                    raise ParserError()
                self.content = self.content[2:]
            m = literal.match(self.content)
            if m:
                buffer += m.group(1)
                self.content = self.content[m.end(0):]
        if buffer or len(obj):
            string = ast.String(buffer)
            string._template = '%s%%(content)s%s' % (str_end, str_end)
            obj.append(string)
        self.content = self.content[1:]
        if len(obj) == 1 and isinstance(obj[0], ast.String):
            return obj[0]
        return ast.ComplexString(obj)

    def get_array(self):
        self.content = self.content[1:]
        ws_pre = self.get_ws()
        ws_item_pre = None
        array = []
        if self.content[0] == ']':
            self.content = self.content[1:]
            arr = ast.Array()
            arr._template = '%s%%(content)s' % ws_pre
            return arr
        while 1:
            elem = self.get_value()
            array.append(elem)
            ws_item_post = self.get_ws()
            if self.content[0] == ',':
                self.content = self.content[1:]
                if ws_item_pre is None:
                    ws_item_pre = ws_pre
                    ws_pre = ''
                elem._template = '%s%s%s' % (ws_item_pre,
                                             elem._template,
                                             ws_item_post)
                ws_item_pre = self.get_ws()
            elif self.content[0] == ']':
                elem._template = '%s%s%s' % (ws_item_pre,
                                             elem._template,
                                             ws_item_post)
                break
            else:
                raise ParserError()
        self.content = self.content[1:]
        arr = ast.Array(array)
        arr._template = '[%(content)s]'
        return arr

    def get_hash(self):
        self.content = self.content[1:]
        ws_pre = self.get_ws()
        ws_item_pre = None
        hash = []
        if self.content[0] == '}':
            self.content = self.content[1:]
            h = ast.Hash()
            h._template = '%s%%(content)s' % ws_pre
            return h
        while 1:
            kvp = self.get_kvp()
            hash.append(kvp)
            ws_item_post = self.get_ws()
            if self.content[0] == ',':
                self.content = self.content[1:]
                if ws_item_pre is None:
                    ws_item_pre = ws_pre
                    ws_pre = ''
                kvp._template = '%s%s%s' % (ws_item_pre,
                                            kvp._template,
                                            ws_item_post)
                ws_item_pre = self.get_ws()
            elif self.content[0] == '}':
                kvp._template = '%s%s%s' % (ws_item_pre,
                                            kvp._template,
                                            ws_item_post)
                break
            else:
                raise ParserError()
        self.content = self.content[1:]
        h = ast.Hash(hash)
        h._template = '{%(content)s}'
        return h

    def get_kvp(self):
        key = self.get_identifier()
        ws_post_key = self.get_ws()
        if self.content[0] != ':':
            raise ParserError()
        self.content = self.content[1:]
        ws_pre_value = self.get_ws()
        val = self.get_value()
        kvp = ast.KeyValuePair(key, val)
        kvp._template = '%%(key)s%s:%s%%(value)s' % (ws_post_key,
                                                     ws_pre_value)
        return kvp

    def get_attributes(self):
        if self.content[0] == '>':
            self.content = self.content[1:]
            return None
        hash = []
        while 1:
            kvp = self.get_kvp()
            hash.append(kvp)
            ws2 = self.get_ws()
            if self.content[0] == '>':
                self.content = self.content[1:]
                break
            elif ws2 == '':
                raise ParserError()
        return hash if len(hash) else None

    def get_index(self):
        index = []
        self.content = self.content[1:]
        ws_pre = self.get_ws()
        ws_item_pre = None
        expression = None
        if self.content[0] == ']':
            self.content = self.content[1:]
            ind = ast.Index(index)
            ind._template = '%s%%(sequence)s' % ws_pre
            return ind
        while 1:
            expression = self.get_expression()
            index.append(expression)
            ws_item_post = self.get_ws()
            if self.content[0] == ',':
                self.content = self.content[1:]
                if ws_item_pre is None:
                    ws_item_pre = ws_pre
                    ws_pre = ''
                expression._template = '%s%s%s' % (ws_item_pre,
                                                   expression._template,
                                                   ws_item_post)
                ws_item_pre = self.get_ws()
            elif self.content[0] == ']':
                expression._template = '%s%s%s' % (ws_item_pre,
                                                   expression._template,
                                                   ws_item_post)
                break
            else:
                raise ParserError()
        self.content = self.content[1:]
        ind = ast.Index(index)
        ind._template = '%(sequence)s'
        return ind


    def get_expression(self):
        return self.get_conditional_expression()

    def get_conditional_expression(self):
        or_expression = self.get_or_expression()
        if self.content[0] != '?':
            return or_expression
        self.content = self.content[1:]
        self.get_ws()
        consequent = self.get_expression()
        self.get_ws()
        if self.content[0] != ':':
            raise ParserError()
        self.content = self.content[1:]
        self.get_ws()
        alternate = self.get_expression()
        return ast.ConditionalExpression(or_expression,
                                         consequent,
                                         alternate)

    def get_prefix_expression(self, token, token_length, cl, op, nxt):
        exp = nxt()
        while self.content[:token_length] in token:
            t = self.content[:token_length]
            self.content = self.content[token_length:]
            exp = cl(op(t),
                     exp,
                     nxt())
        return exp

    def get_prefix_expression_re(self, token, cl, op, nxt):
        exp = nxt()
        m = token.match(self.content)
        while m:
            self.content = self.content[m.end(0):]
            exp = cl(op(m.group(0)),
                     exp,
                     nxt())
            m = token.match(self.content)
        return exp


    def get_postfix_expression(self, token, token_length, cl, op, nxt):
        t = self.content[0]
        if t not in token:
            return nxt()
        self.content = self.content[1:]
        return cl(op(t),
                  self.get_postfix_expression(token, token_length, cl, op, nxt))

    def get_or_expression(self,
                          token=('||',),
                          cl=ast.LogicalExpression,
                          op=ast.LogicalOperator):
        return self.get_prefix_expression(token, 2, cl, op, self.get_and_expression)

    def get_and_expression(self,
                          token=('&&',),
                          cl=ast.LogicalExpression,
                          op=ast.LogicalOperator):
        return self.get_prefix_expression(token, 2, cl, op, self.get_equality_expression)

    def get_equality_expression(self,
                          token=('==', '!='),
                          cl=ast.BinaryExpression,
                          op=ast.BinaryOperator):
        return self.get_prefix_expression(token, 2, cl, op, self.get_relational_expression)

    def get_relational_expression(self,
                          token=re.compile('^[<>]=?'),
                          cl=ast.BinaryExpression,
                          op=ast.BinaryOperator):
        return self.get_prefix_expression_re(token, cl, op, self.get_additive_expression)

    def get_additive_expression(self,
                          token=('+', '-'),
                          cl=ast.BinaryExpression,
                          op=ast.BinaryOperator):
        return self.get_prefix_expression(token, 1, cl, op, self.get_modulo_expression)

    def get_modulo_expression(self,
                          token=('%',),
                          cl=ast.BinaryExpression,
                          op=ast.BinaryOperator):
        return self.get_prefix_expression(token, 1, cl, op, self.get_multiplicative_expression)

    def get_multiplicative_expression(self,
                          token=('*',),
                          cl=ast.BinaryExpression,
                          op=ast.BinaryOperator):
        return self.get_prefix_expression(token, 1, cl, op, self.get_dividive_expression)

    def get_dividive_expression(self,
                          token=('/',),
                          cl=ast.BinaryExpression,
                          op=ast.BinaryOperator):
        return self.get_prefix_expression(token, 1, cl, op, self.get_unary_expression)

    def get_unary_expression(self,
                          token=('+', '-', '!'),
                          cl=ast.UnaryExpression,
                          op=ast.UnaryOperator):
        return self.get_postfix_expression(token, 1, cl, op, self.get_member_expression)

    def get_member_expression(self):
        exp = self.get_parenthesis_expression()
        while 1:
            if self.content[0:2] in ('[.', '..'):
                exp = self.get_attr_expression(exp)
            elif self.content[0] in ('[', '.'):
                exp = self.get_property_expression(exp)
            elif self.content[0] == '(':
                exp = self.get_call_expression(exp)
            else:
                break
        return exp

    def get_parenthesis_expression(self):
        if self.content[0] == "(":
            self.content = self.content[1:]
            ws = self.get_ws()
            pexp = ast.ParenthesisExpression(self.get_expression())
            if not hasattr(pexp, '_template'):
                pexp._template = {}
            pexp._template['ws_pre'] =  ws
            pexp._template['ws_post'] = self.get_ws()
            if self.content[0] != ')':
                raise ParserError()
            self.content = self.content[1:]
            return pexp
        return self.get_primary_expression()

    def get_primary_expression(self):
        #number
        ptr = 0
        while self.content[ptr].isdigit():
            ptr+=1
        if ptr:
            d =  int(self.content[:ptr])
            self.content = self.content[ptr:]
            return ast.Literal(d)
        #value
        if self.content[0] in ('"\'{['):
            return self.get_value()
        return self.get_identifier()

    def get_attr_expression(self, idref):
        d = self.content[0:2]
        if d == '[.':
            self.content = self.content[2:]
            self.get_ws()
            exp = self.get_expression()
            self.get_ws()
            self.content = self.content[1:]
            return ast.AttributeExpression(idref, exp, True)
        elif d == '..':
            self.content = self.content[2:]
            prop = self.get_identifier()
            return ast.AttributeExpression(idref, prop, False)
            pass
        else:
            raise ParserError()

    def get_property_expression(self, idref):
        d = self.content[0]
        if d == '[':
            self.content = self.content[1:]
            self.get_ws()
            exp = self.get_expression()
            self.get_ws()
            self.content = self.content[1:]
            return ast.PropertyExpression(idref, exp, True)
        elif d == '.':
            self.content = self.content[1:]
            prop = self.get_identifier()
            return ast.PropertyExpression(idref, prop, False)
        else:
            raise ParserError()

    def get_call_expression(self, callee):
        mcall = ast.CallExpression(callee)
        self.content = self.content[1:]
        self.get_ws()
        if self.content[0] == ')':
            self.content = self.content[1:]
            return mcall
        while 1:
            exp = self.get_expression()
            mcall.arguments.append(exp)
            self.get_ws()
            if self.content[0] == ',':
                self.content = self.content[1:]
                self.get_ws()
            elif self.content[0] == ')':
                break
            else:
                raise ParserError()
        self.content = self.content[1:]
        return mcall

    def get_comment(self):
        comment, sep, self.content = self.content[2:].partition('*/')
        if not sep:
            raise ParserError()
        return ast.Comment(comment)
