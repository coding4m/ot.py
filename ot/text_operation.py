class Retain(object):
    """Skips a given number of characters at the current cursor position."""

    def __init__(self, n):
        self.n = n

    def __eq__(self, other):
        return isinstance(other, Retain) and self.n == other.n

    def __len__(self):
        return self.n

    def len_difference(self):
        return 0

    def shorten(self, n):
        return Retain(self.n - n)

    def merge(self, other):
        return Retain(self.n + other.n)


class Insert(object):
    """Inserts the given string at the current cursor position."""

    def __init__(self, str):
        self.str = str

    def __eq__(self, other):
        return isinstance(other, Insert) and self.str == other.str

    def __len__(self):
        return len(self.str)

    def len_difference(self):
        return len(self)

    def shorten(self, n):
        return Insert(self.str[n:])

    def merge(self, other):
        return Insert(self.str + other.str)


class Delete(object):
    """Deletes a given number of characters at the current cursor position."""

    def __init__(self, n):
        self.n = n

    def __eq__(self, other):
        return isinstance(other, Delete) and self.n == other.n

    def __len__(self):
        return self.n

    def len_difference(self):
        return -len(self)

    def shorten(self, n):
        return Delete(self.n - n)

    def merge(self, other):
        return Delete(self.n + other.n)


def _shorten_ops(a, b):
    """Shorten two ops by the part that cancels each other out."""

    len_a = len(a)
    len_b = len(b)
    if len_a == len_b:
        return (None, None)
    if len_a > len_b:
        return (a.shorten(len_b), None)
    return (None, b.shorten(len_a))


class TextOperation(object):
    """Diff between two strings."""

    def __init__(self, ops=[]):
        self.ops = ops[:]

    def __eq__(self, other):
        return isinstance(other, TextOperation) and self.ops == other.ops

    def __iter__(self):
        return self.ops.__iter__()

    def __add__(self, other):
        return self.compose(other)

    def len_difference(self):
        """Returns the difference in length between the input and the output
        string when this operations is applied.
        """
        return sum([op.len_difference() for op in self])

    def append(self, op):
        """Appends an op at the end of the operation. Merges operations if possible."""

        if len(op) == 0:
            return
        if len(self.ops) > 0 and self.ops[-1].__class__ == op.__class__:
            op = self.ops.pop().merge(op)
        self.ops.append(op)

    def __call__(self, doc):
        """Apply this operation to a string, returning a new string."""

        i = 0
        parts = []

        for op in self:
            if isinstance(op, Retain):
                if i + len(op) > len(doc):
                    raise Exception("Cannot apply operation: operation is too long.")
                parts.append(doc[i:(i + len(op))])
                i += len(op)
            elif isinstance(op, Insert):
                parts.append(op.str)
            else:
                if i + len(op) > len(doc):
                    raise IncompatibleOperationError("Cannot apply operation: operation is too long.")
                i += len(op)

        if i != len(doc):
            raise IncompatibleOperationError("Cannot apply operation: operation is too short.")

        return ''.join(parts)

    def invert(self, doc):
        """Make an operation that does the opposite. When you apply an operation
        to a string and then the operation generated by this operation, you
        end up with your original string. This method can be used to implement
        undo.
        """

        i = 0
        inverse = TextOperation()

        for op in self:
            if isinstance(op, Retain):
                inverse.append(op)
                i += len(op)
            elif isinstance(op, Insert):
                inverse.append(Delete(len(op)))
            else:
                inverse.append(Insert(doc[i:(i + len(op))]))
                i += len(op)

        return inverse

    def compose(self, other):
        """Combine two consecutive operations into one that has the same effect
        when applied to a document.
        """

        iter_a = iter(self)
        iter_b = iter(other)
        operation = TextOperation()

        a = b = None
        while True:
            if a == None:
                a = next(iter_a, None)
            if b == None:
                b = next(iter_b, None)

            if a == b == None:
                # end condition: both operations have been processed
                break

            if isinstance(a, Delete):
                operation.append(a)
                a = None
                continue
            if isinstance(b, Insert):
                operation.append(b)
                b = None
                continue

            if a == None:
                raise IncompatibleOperationError("Cannot compose operations: first operation is too short")
            if b == None:
                raise IncompatibleOperationError("Cannot compose operations: first operation is too long")

            min_len = min(len(a), len(b))
            if isinstance(a, Retain) and isinstance(b, Retain):
                operation.append(Retain(min_len))
            elif isinstance(a, Insert) and isinstance(b, Retain):
                operation.append(Insert(a.str[:min_len]))
            elif isinstance(a, Retain) and isinstance(b, Delete):
                operation.append(Delete(min_len))
            # remaining case: isinstance(a, Insert) and isinstance(b, Delete)
            # in this case the delete op deletes the text that has been added
            # by the insert operation and we don't need to do anything

            (a, b) = _shorten_ops(a, b)

        return operation

    @staticmethod
    def transform(operation_a, operation_b):
        """Transform two operations a and b to a' and b' such that b' applied
        after a yields the same result as a' applied after b. Try to preserve
        the operations' intentions in the process.
        """

        iter_a = iter(operation_a)
        iter_b = iter(operation_b)
        a_prime = TextOperation()
        b_prime = TextOperation()
        a = b = None

        while True:
            if a == None:
                a = next(iter_a, None)
            if b == None:
                b = next(iter_b, None)

            if a == b == None:
                # end condition: both operations have been processed
                break

            if isinstance(a, Insert):
                a_prime.append(a)
                b_prime.append(Retain(len(a)))
                a = None
                continue
            if isinstance(b, Insert):
                a_prime.append(Retain(len(b)))
                b_prime.append(b)
                b = None
                continue

            min_len = min(len(a), len(b))
            if isinstance(a, Retain) and isinstance(b, Retain):
                min_retain = Retain(min_len)
                a_prime.append(min_retain)
                b_prime.append(min_retain)
            elif isinstance(a, Delete) and isinstance(b, Retain):
                a_prime.append(Delete(min_len))
            elif isinstance(a, Retain) and isinstance(b, Delete):
                b_prime.append(Delete(min_len))
            # remaining case: isinstance(a, Delete) and isinstance(b, Delete)
            # in this case both operations delete the same string and we don't
            # need to do anything

            (a, b) = _shorten_ops(a, b)

        return (a_prime, b_prime)


class IncompatibleOperationError(Exception):
    """Two operations or an operation and a string have different lengths."""
    pass
