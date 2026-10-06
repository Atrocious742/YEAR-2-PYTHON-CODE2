# Deliveries: the checks for Task 2. Run it in the terminal with:  python check.py
# It runs your functions in delivery.py, with answers typed in for you, and reads your test plan. It prints PASS,
# FIX or a dash (not started yet) for each part of Task 2, then your RESULTS LINE, which the exit ticket asks you
# to paste. Your code runs in a Python of its own with a time limit, so a loop that never stops is stopped and named.
# It never changes your files. Do not change this file.
import ast
import builtins
import contextlib
import hashlib
import importlib.util
import inspect
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
REAL_INPUT = builtins.input

# Each function as the zip gave it, so a part nobody has touched shows a dash rather than a FIX.
STARTER = {
    "ask_item": "e11fc5862b8c",
    "ask_shelf": "f57b038e0700",
    "ask_code": "db07258349f0",
    "ask_price": "8690ea251f1d",
    "load_stock": "dd8096a32515",
}


# The checks' own signals. They are BaseException, not Exception, so except Exception: in your code cannot catch them;
# a bare except: still can, and the time limit below is there for that.
class RanOut(BaseException):
    """It asked again after the last answer: it refused something it should have given back."""


class TooLong(BaseException):
    """A loop that never stops."""


class Capped(io.StringIO):
    """What your code prints, up to a limit: a loop that prints for ever stops here rather than filling the memory."""

    def write(self, text):
        if self.tell() > 200000:
            raise TooLong()
        return super().write(text)


def fingerprint(fn):
    lines = [line.rstrip() for line in inspect.getsource(fn).replace("\r\n", "\n").split("\n")]
    return hashlib.sha256("\n".join(lines).strip().encode("utf-8")).hexdigest()[:12]


def untouched(mod, name):
    fn = getattr(mod, name, None)
    return fn is not None and fingerprint(fn) == STARTER[name]


# Task 2f changes the top of load_stock and Task 2g its for loop, so 2g is "not started" while the loop is still the
# zip's, line for line, even after 2f is done.
STARTER_LOOP = ["    for line in lines:", '        item, count = line.strip().split(",")', "        stock[item] = int(count)"]


def loop_untouched(mod):
    fn = getattr(mod, "load_stock", None)
    if fn is None:
        return False
    src = [line.rstrip() for line in inspect.getsource(fn).replace("\r\n", "\n").split("\n")]
    n = len(STARTER_LOOP)
    return any(src[i:i + n] == STARTER_LOOP for i in range(len(src) - n + 1))


def call(fn, answers, *args):
    """Run fn(*args) with the answers typed in, one each time it asks. Give back (result, what it printed, error)."""
    todo = list(answers)

    def typed(prompt=""):
        if not todo:
            raise RanOut()
        return todo.pop(0)

    steps = [0]

    def tracer(frame, event, arg):
        if event == "line":
            steps[0] += 1
            if steps[0] > 200000:
                raise TooLong()
        return tracer

    out = Capped()
    builtins.input = typed
    sys.settrace(tracer)
    try:
        with contextlib.redirect_stdout(out):
            result = fn(*args)
        return result, out.getvalue(), None
    except BaseException as e:            # exit() and quit() too: they raise SystemExit
        if isinstance(e, KeyboardInterrupt):
            raise
        return None, out.getvalue(), e
    finally:
        sys.settrace(None)
        builtins.input = REAL_INPUT


def load(name):
    """Read one of the task's files as Python. Give back (the module, None) or (None, why not)."""
    path = os.path.join(HERE, f"{name}.py")
    if not os.path.exists(path):
        return None, f"{name}.py is not in this folder"
    spec = importlib.util.spec_from_file_location(f"{name}_checked", path)
    mod = importlib.util.module_from_spec(spec)
    _, _, e = call(spec.loader.exec_module, [], mod)
    if isinstance(e, SyntaxError):
        return None, (f"{name}.py has a line Python cannot read (line {e.lineno}): run python {name}.py to see it, "
                      "then finish that line, or put # in front of the lines you have not finished")
    if isinstance(e, RanOut):
        return None, f"{name}.py asks a question as soon as it is read: put the lines that run the program under if __name__ == \"__main__\":"
    if isinstance(e, TooLong):
        return None, LOAD_RUNAWAY.format(name=name)
    if isinstance(e, SystemExit):
        return None, (f"{name}.py ends the program as soon as it is read (exit() or quit() outside a function): take it out, "
                      "or put it under if __name__ == \"__main__\":")
    if e:
        return None, f"{name}.py stops with {type(e).__name__} before the checks can reach it: {e}"
    return mod, None


def lines_of(printed):
    return [line for line in printed.split("\n") if line.strip()]


def crashed(e, typed, kind="ask"):
    """What went wrong, in words. kind: "ask" for a function that asks a question, "file" for load_stock."""
    if isinstance(e, TooLong):
        if kind == "file":
            return f"with {typed} it goes round and round and never stops: each time round, the loop must move on to the next line of the file"
        return f"after {typed} it goes round and round without asking again: ask again inside the loop (the example's first line after while True)"
    if isinstance(e, RanOut):
        if kind == "file":
            return f"with {typed} it asks a question: load_stock reads the file and asks nothing"
        return f"after {typed} it asked again: it refused an answer it should have given back"
    if isinstance(e, SystemExit):
        if kind == "file":
            return f"with {typed} it ends the whole program (exit() or quit()): carry on instead, so the rest of the program still runs"
        return f"{typed} ends the whole program (exit() or quit()): refuse it with a message and ask again, as the example does"
    return f"{typed} makes it crash with {type(e).__name__}: {e}"


# ------------------------------------------------------------------ catch only the error you expect (the harder run)
def tree_of(fn):
    try:
        return ast.parse(inspect.getsource(fn).replace("\r\n", "\n"))
    except (OSError, TypeError, SyntaxError):
        return None


def broad(handler):
    """True for except: on its own, except Exception: or except BaseException:, which catch your own mistakes too."""
    t = handler.type
    if t is None:
        return True
    names = t.elts if isinstance(t, ast.Tuple) else [t]
    return any(isinstance(n, ast.Name) and n.id in ("Exception", "BaseException") for n in names)


def opens_a_file(node):
    return any(isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "open" for n in ast.walk(node))


def broad_tries(fn, where="anywhere"):
    """The try blocks in fn with a catch-all handler. where: "anywhere", "open" (a try round open()), "loop" (a try
    inside a for or while loop)."""
    tree = tree_of(fn)
    if tree is None:
        return []
    inside = set()
    if where == "loop":
        for loop in ast.walk(tree):
            if isinstance(loop, (ast.For, ast.While)):
                inside.update(id(n) for n in ast.walk(loop) if isinstance(n, ast.Try) and n is not loop)
    found = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Try) or not any(broad(h) for h in node.handlers):
            continue
        if where == "open" and not any(opens_a_file(s) for s in node.body):
            continue
        if where == "loop" and id(node) not in inside:
            continue
        found.append(node)
    return found


def catch_only(error, slip="the slip"):
    return (f"except on its own (or except Exception) catches every error, your own mistakes too, so {slip} would never "
            f"show (the harder run): catch only the one you expect, except {error}:")


# ------------------------------------------------------------------ Part 1
def check_2a(mod, _):
    if untouched(mod, "ask_item"):
        return "-", "not started yet"
    fn = mod.ask_item
    for answers, want, what in [(["Milk"], "Milk", "Milk"), (["  Semi skimmed milk  "], "Semi skimmed milk", "a name with spaces round it"),
                                (["A" * 20], "A" * 20, "a name of exactly 20 characters")]:
        got, printed, e = call(fn, answers, "Item: ")
        if e:
            if isinstance(e, RanOut) and len(answers[0]) == 20:
                return "FIX", "a name of exactly 20 characters was refused: 20 is allowed, so refuse only more than 20 (> 20, not >= 20)"
            return "FIX", crashed(e, what)
        if got != want:
            return "FIX", f"{what} gave back {got!r}: give back the name, as the example gives back its answer"
    got, printed, e = call(fn, ["", "Milk"], "Item: ")
    if e:
        return "FIX", crashed(e, "a blank, then Milk,")
    if got != "Milk" or not lines_of(printed):
        return "FIX", "a blank answer must still be refused with its message, then the next answer given back: keep the blank check first"
    got, printed, e = call(fn, ["A" * 21, "Milk"], "Item: ")
    if e:
        return "FIX", crashed(e, "a name of 21 characters, then Milk,")
    if got != "Milk":
        return "FIX", "a name of 21 characters got in: add the length check, len(text) > 20, before the else"
    said = lines_of(printed)
    if not said or "20" not in said[0]:
        return "FIX", "a name of 21 characters must be refused with a message that says the limit: Use 20 characters or fewer."
    if broad_tries(fn):
        return "FIX", catch_only("ValueError", "a slip in ask_item")
    return "PASS", "a blank and a name of 21 characters are refused, each with its message; 20 characters get in"


KINDS = ["valid", "valid extreme", "invalid", "invalid extreme", "erroneous"]
PLAN = {"12": ("accepted", "valid"), "50": ("accepted", "valid extreme"), "51": ("rejected", "invalid extreme"),
        "1": ("accepted", "valid extreme"), "0": ("rejected", "invalid extreme"), "200": ("rejected", "invalid"),
        "ten": ("rejected", "erroneous")}
WHY_KIND = {
    "50": "50 is on the edge of 1 to 50 and still allowed: valid extreme",
    "51": "51 is a number, just past the edge: invalid extreme",
    "1": "1 is on the edge of 1 to 50 and still allowed: valid extreme",
    "0": "0 is a number, just past the edge: invalid extreme",
    "200": "200 is a number, well outside 1 to 50: invalid",
    "ten": "ten is not a number at all, the wrong type of data: erroneous",
}


def check_2b(_mod, plan):
    if plan is None:
        return "FIX", "test_plan.py is not in this folder, or Python cannot read it: run python test_plan.py to see why"
    rows = getattr(plan, "TESTS", None)
    if not isinstance(rows, list):
        return "FIX", "test_plan.py has no TESTS list: take the file from the zip again"
    typed = {}
    for row in rows:
        if not (isinstance(row, tuple) and len(row) == 3):
            return "FIX", f"{row!r} is not three things in brackets: (what is typed, accepted or rejected, kind)"
        typed[str(row[0])] = (str(row[1]).strip().lower(), " ".join(str(row[2]).lower().split()))
    if all(typed.get(k, ("", ""))[0] == "" and typed.get(k, ("", ""))[1] == "" for k in PLAN if k != "12"):
        return "-", "not started yet"
    for value, (result, kind) in PLAN.items():
        if value not in typed:
            return "FIX", f"the row for {value!r} is missing: take the file from the zip again"
        got_result, got_kind = typed[value]
        if got_result not in ("accepted", "rejected"):
            return "FIX", f"the row for {value!r} says {got_result!r} in the middle: write accepted or rejected"
        if got_result != result:
            why = "it passes every check" if result == "accepted" else "it fails a check"
            return "FIX", f"{value!r} is {result}, because {why}: run python try_count.py and type it in"
        if got_kind not in KINDS:
            return "FIX", f"the row for {value!r} says {got_kind!r}: use one of valid, valid extreme, invalid, invalid extreme, erroneous"
        if got_kind != kind:
            return "FIX", WHY_KIND[value]
    return "PASS", "every row right: what ask_count does with it, and the kind of test data it is"


def check_2c(mod, _):
    if untouched(mod, "ask_shelf"):
        return "-", "not started yet"
    fn = mod.ask_shelf
    got, printed, e = call(fn, ["twelve", "7"], "Shelf: ")
    if e and not isinstance(e, (RanOut, TooLong, SystemExit)):
        return "FIX", f"typing twelve makes it crash with {type(e).__name__}: the type check has to come before int() runs"
    if e:
        return "FIX", crashed(e, "twelve, then 7,")
    if got != 7 or not lines_of(printed):
        return "FIX", "twelve must be refused with a message, and 7 given back"
    got, printed, e = call(fn, ["12"], "Shelf: ")
    if isinstance(e, (TooLong, SystemExit)):
        return "FIX", crashed(e, "12")
    if e or got != 12:
        return "FIX", "shelf 12 is refused: it is valid extreme, on the edge, so the range check must let it in (<= 12)"
    got, printed, e = call(fn, ["13", "0", "", "1"], "Shelf: ")
    if e:
        return "FIX", crashed(e, "13, 0, a blank, then 1,")
    if got != 1 or len(lines_of(printed)) != 3:
        return "FIX", "13, 0 and a blank must each be refused with a message, and 1 given back"
    if broad_tries(fn):
        return "FIX", catch_only("ValueError", "a slip in ask_shelf")
    return "PASS", "twelve is refused without a crash, 12 gets in, 13 and 0 are refused"


def first_message(printed, typed):
    """The first thing it printed, with the typed text taken out, so 'MLK12 is too short' and 'M1K012 is too short'
    read alike."""
    said = lines_of(printed)
    if not said:
        return ""
    return re.sub(re.escape(typed), "#", said[0], flags=re.I) if typed else said[0]


def check_2d(mod, _):
    if untouched(mod, "ask_code"):
        return "-", "not started yet"
    fn = mod.ask_code
    for answers, want, what in [(["MLK012"], "MLK012", "MLK012"), (["mlk012"], "MLK012", "mlk012"), (["  BRD104  "], "BRD104", "a code with spaces round it")]:
        got, printed, e = call(fn, answers, "Product code: ")
        if e:
            return "FIX", crashed(e, what)
        if got != want:
            hint = "give it back in capitals: text.upper()" if got == answers[0] else "give back the code that passed"
            return "FIX", f"{what} gave back {got!r}, and it should give back {want!r}: {hint}"
    messages = {}
    for bad, word, rule in [("MLK12", "6", "a code of 5 characters must be refused with a message that says 6 characters"),
                            ("MLK0123", "6", "a code of 7 characters must be refused with a message that says 6 characters"),
                            ("M1K012", "letters", "M1K012 must be refused with a message that says it starts with 3 letters"),
                            ("MLK01A", "digits", "MLK01A must be refused with a message that says it ends with 3 digits"),
                            ("", "blank", "a blank must be refused with its own message")]:
        got, printed, e = call(fn, [bad, "MLK012"], "Product code: ")
        if e:
            return "FIX", crashed(e, f"{bad or 'a blank'}, then MLK012,")
        said = lines_of(printed)
        if got != "MLK012" or not said:
            return "FIX", rule
        if word != "blank" and word not in said[0].lower():
            return "FIX", rule
        messages[bad] = first_message(printed, bad)
    if messages[""] == messages["MLK12"]:
        return "FIX", "a blank gets the same message as a code of the wrong length: check for a blank first, with a message of its own"
    if len({messages["MLK12"], messages["M1K012"], messages["MLK01A"]}) < 3:
        return "FIX", ("the wrong length, a digit in the letters and a letter in the digits must each get their own message, "
                       "one check and one message each, every message saying its rule")
    if broad_tries(fn):
        return "FIX", catch_only("ValueError", "a slip in ask_code")
    return "PASS", "good codes come back in capitals; a blank, the wrong length, a digit in the letters and a letter in the digits are each refused with their own message"


# ------------------------------------------------------------------ Part 2
def check_2e(mod, _):
    if untouched(mod, "ask_price"):
        return "-", "not started yet"
    fn = mod.ask_price
    loose = broad_tries(fn)
    got, printed, e = call(fn, ["2.50"], "Price each: £")
    if isinstance(e, RanOut):
        return "FIX", "2.50 is still refused: use float() in place of int(), so a price with pence gets in"
    if e:
        return "FIX", crashed(e, "2.50") + (", and catch only ValueError: except on its own hides the slip" if loose else "")
    if not isinstance(got, float) or abs(got - 2.5) > 1e-9:
        return "FIX", f"2.50 gave back {got!r}: give back float(text)"
    got, printed, e = call(fn, ["two", "1.25"], "Price each: £")
    if e and not isinstance(e, (RanOut, TooLong, SystemExit)):
        return "FIX", f"typing two makes it crash with {type(e).__name__}: keep the try and except round float()"
    if e:
        return "FIX", crashed(e, "two, then 1.25,") + (", and catch only ValueError: except on its own hides the slip" if loose else "")
    said = lines_of(printed)
    if got is None or abs(got - 1.25) > 1e-9 or not said:
        return "FIX", "two must be refused with a message, and 1.25 given back"
    if "2.50" not in said[0]:
        return "FIX", "the message for two must say what to type: Type a price, like 2.50"
    if loose:
        return "FIX", catch_only("ValueError", "a typo in ask_price")
    return "PASS", "2.50 comes back as a number with pence; two is refused with a message that says what to type"


STOCK_GOOD = "Milk,10\nBread,4\n"
STOCK_MIXED = "Milk,10\nBread,ten\nCrisps\nApples,5\n"


def with_file(text, fn):
    """Run fn(path) with a stock file holding text (or no file at all when text is None) in a folder of its own, then
    remove the folder. Give back (what fn gave back, the file's name)."""
    folder = tempfile.mkdtemp(prefix="checked-")
    path = os.path.join(folder, "stock-check.txt")
    try:
        if text is not None:
            with open(path, "w") as f:
                f.write(text)
        return fn(path), os.path.basename(path)
    finally:
        shutil.rmtree(folder, ignore_errors=True)


def check_2f(mod, _):
    if untouched(mod, "load_stock"):
        return "-", "not started yet"
    (got, printed, e), name = with_file(None, lambda p: call(mod.load_stock, [], p))
    if isinstance(e, FileNotFoundError):
        return "FIX", "a missing stock file still crashes it: put try round the with open() block, and except FileNotFoundError after it"
    if e:
        return "FIX", crashed(e, "a missing stock file", "file")
    if got != {}:
        return "FIX", f"with no stock file it gave back {got!r}: give back an empty dictionary, {{}}"
    said = lines_of(printed)
    if not said or name not in said[0]:
        return "FIX", "with no stock file, say so, naming the file: print(f\"{filename} was not found: starting with no stock.\")"
    (got, printed, e), _ = with_file(STOCK_GOOD, lambda p: call(mod.load_stock, [], p))
    if e or got != {"Milk": 10, "Bread": 4}:
        return "FIX", "with a stock file there, it must still read every line: Milk,10 and Bread,4 give back {'Milk': 10, 'Bread': 4}"
    if broad_tries(mod.load_stock, "open"):
        return "FIX", catch_only("FileNotFoundError", "a slip in load_stock")
    return "PASS", "a missing file gives an empty stock and a message naming the file; a good file is still read"


def check_2g(mod, _):
    if untouched(mod, "load_stock") or loop_untouched(mod):
        return "-", "not started yet"
    (got, printed, e), _ = with_file(STOCK_MIXED, lambda p: call(mod.load_stock, [], p))
    if isinstance(e, ValueError):
        return "FIX", "a wrong line (Bread,ten) still crashes it: put try and except ValueError round the two lines that read one line, inside the for loop"
    if e:
        return "FIX", crashed(e, "two wrong lines in the file", "file")
    if got == {} or got == {"Milk": 10}:
        return "FIX", f"one wrong line lost the rest of the file (it gave back {got!r}): the try goes inside the for loop, so only the wrong line is skipped"
    if got != {"Milk": 10, "Apples": 5}:
        return "FIX", f"Milk,10 / Bread,ten / Crisps / Apples,5 gave back {got!r}: it should give back {{'Milk': 10, 'Apples': 5}}"
    said = " ".join(lines_of(printed)).lower()
    if "line 2" not in said or "line 3" not in said:
        return "FIX", "say which line was skipped, like Line 2 skipped: Bread,ten (count the lines as the loop reads them)"
    if broad_tries(mod.load_stock, "loop"):
        return "FIX", catch_only("ValueError", "a typo in the loop")
    return "PASS", "Bread,ten and Crisps are skipped, each named by its line number, and Milk and Apples are still loaded"


PARTS = [
    ("2a", "Check the name's length", check_2a),
    ("2b", "Plan the tests", check_2b),
    ("2c", "Fix the shelf check", check_2c),
    ("2d", "Build the product code check", check_2d),
    ("2e", "Read a price", check_2e),
    ("2f", "Carry on without the file", check_2f),
    ("2g", "Skip a wrong line", check_2g),
]


# ------------------------------------------------------------------ your code in a Python of its own, with a time limit
# A loop whose bare except: swallows the checks' own signals never stops by itself, so every check runs in a Python of
# its own and is stopped after LIMIT seconds. The usual run is ONE such Python for every part; only when it runs out of
# time is each part run on its own, all at once, to find which one never stops, and the others are still checked.
LIMIT = 8
LOAD_RUNAWAY = "{name}.py runs a loop as soon as it is read, and it never stops: put the lines that run the program under if __name__ == \"__main__\":"
ASK_AGAIN = "it goes round and round and never stops: read the answer inside the loop, as the example does"
RUNAWAY = {
    "2a": ASK_AGAIN,
    "2b": "test_plan.py never finishes being read: take it from the zip again, then fill in its gaps",
    "2c": ASK_AGAIN,
    "2d": ASK_AGAIN,
    "2e": ASK_AGAIN + ", and catch only ValueError (except ValueError:, not except: on its own, which hides the slip)",
    "2f": "load_stock goes round and round and never stops: catch only FileNotFoundError (except FileNotFoundError:, not except: on its own), and let every loop end",
    "2g": "load_stock goes round and round and never stops: each time round, the loop must move on to the next line, and catch only ValueError (except ValueError:, not except: on its own)",
}


def probe(labels):
    """In the Python of its own: run the named parts' checks, and print the verdicts as one line."""
    out = {}
    delivery, why_not = load("delivery") if any(label != "2b" for label in labels) else (None, None)
    plan = load("test_plan")[0] if "2b" in labels else None
    if "load" in labels:
        out["load"] = ["ok" if delivery is not None else "FIX", why_not or ""]
    for label, name, check in PARTS:
        if label not in labels:
            continue
        if label != "2b" and delivery is None:
            out[label] = ["FIX", why_not]
            continue
        try:
            verdict, why = check(delivery, plan)
        except KeyboardInterrupt:
            raise
        except BaseException as e:            # a check that cannot run says so rather than stopping the others
            verdict, why = "FIX", (RUNAWAY[label] if isinstance(e, TooLong) else f"the check could not run: {type(e).__name__}: {e}")
        out[label] = [verdict, why]
    sys.stdout = sys.__stdout__
    print("PROBE " + json.dumps(out))
    sys.stdout.flush()


def run_probes(groups):
    """Run each group of labels in a Python of its own, all at once. Give back {group: verdicts, or None if it ran out of time}."""
    procs, out = {}, {}
    try:
        for key, labels in groups.items():
            procs[key] = subprocess.Popen([sys.executable, "-B", os.path.abspath(__file__), "--probe", ",".join(labels)],
                                          cwd=HERE, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                          stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace")
        deadline = time.monotonic() + LIMIT
        for key, p in procs.items():
            try:
                said, err = p.communicate(timeout=max(0.1, deadline - time.monotonic()))
            except subprocess.TimeoutExpired:
                p.kill()
                p.communicate()
                out[key] = None
                continue
            line = next((ln for ln in reversed(said.splitlines()) if ln.startswith("PROBE ")), None)
            if line is None:
                last = (err.strip().splitlines() or ["no answer"])[-1]
                out[key] = {label: ["FIX", f"the check could not run: {last}"] for label in groups[key]}
            else:
                out[key] = json.loads(line[len("PROBE "):])
    finally:
        for p in procs.values():
            if p.poll() is None:
                p.kill()
    return out


def results():
    labels = [label for label, _, _ in PARTS]
    first = run_probes({"all": labels})["all"]
    if first is not None:
        return first
    # Something never stopped. Run delivery.py on its own, and each part on its own, to find which.
    groups = {"load": ["load"]}
    groups.update({label: [label] for label in labels})
    got = run_probes(groups)
    stuck_reading = got["load"] is None
    verdicts = {}
    for label in labels:
        if label != "2b" and stuck_reading:
            verdicts[label] = ["FIX", LOAD_RUNAWAY.format(name="delivery")]
        elif got[label] is None:
            verdicts[label] = ["FIX", RUNAWAY[label]]
        else:
            verdicts[label] = got[label][label]
    return verdicts


def main():
    got = results()
    verdicts = []
    for label, name, _ in PARTS:
        verdict, why = got.get(label) or ["FIX", "the check could not run"]
        verdicts.append(verdict)
        print(f"{verdict:<5} {label}  {name}: {why}")
    print()
    print("Your results line (copy it into the exit ticket, question two):")
    print("  ".join(f"{label} {verdict}" for (label, _, _), verdict in zip(PARTS, verdicts)))


if __name__ == "__main__":
    if "--probe" in sys.argv:
        probe(sys.argv[sys.argv.index("--probe") + 1].split(","))
    else:
        main()
