# Cafe: the checks for the stretch task. Make cafe.py in this folder, then run:  python check_stretch.py
# It runs your functions in cafe.py, with answers typed in for you, and prints PASS, FIX or a dash (not started yet)
# for every step, then one line to post in the class chat. Your code runs in a Python of its own with a time limit, so
# a loop that never stops is stopped and named. It never changes your files. Do not change this file.
import ast
import builtins
import contextlib
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


def call(fn, answers, *args):
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


NO_CAFE = "no cafe.py yet: make it in this folder (File, New File, save it as cafe.py)"
LOAD_RUNAWAY = "cafe.py runs a loop as soon as it is read, and it never stops: put the lines that run the program under if __name__ == \"__main__\":"


def load():
    path = os.path.join(HERE, "cafe.py")
    if not os.path.exists(path):
        return None, NO_CAFE
    spec = importlib.util.spec_from_file_location("cafe_checked", path)
    mod = importlib.util.module_from_spec(spec)
    _, _, e = call(spec.loader.exec_module, [], mod)
    if isinstance(e, SyntaxError):
        return None, f"cafe.py has a line Python cannot read (line {e.lineno}): run python cafe.py to see it"
    if isinstance(e, RanOut):
        return None, "cafe.py asks a question as soon as it is read: put the lines that run the program under if __name__ == \"__main__\":"
    if isinstance(e, TooLong):
        return None, LOAD_RUNAWAY
    if isinstance(e, SystemExit):
        return None, "cafe.py ends the program as soon as it is read (exit() or quit() outside a function): take it out, or put it under if __name__ == \"__main__\":"
    if e:
        return None, f"cafe.py stops with {type(e).__name__} before the checks can reach it: {e}"
    return mod, None


def said(printed):
    return [line for line in printed.split("\n") if line.strip()]


def trouble(e, typed, kind="ask"):
    """What went wrong, in words. kind: "ask" for a function that asks a question, "file" for one that reads a file."""
    if isinstance(e, TooLong):
        if kind == "file":
            return f"with {typed} it goes round and round and never stops: the loop must move on to the next line of the file"
        return f"after {typed} it goes round and round without asking again: ask again inside the loop"
    if isinstance(e, RanOut):
        if kind == "file":
            return f"with {typed} it asks a question: it should only read the file"
        return f"after {typed} it asked again: it refused an answer it should have given back"
    if isinstance(e, SystemExit):
        if kind == "file":
            return f"with {typed} it ends the whole program (exit() or quit()): give back an answer instead, so the program carries on"
        return f"{typed} ends the whole program (exit() or quit()): refuse it with a message and ask again"
    return f"{typed} makes it crash with {type(e).__name__}: {e}"


def need(mod, name):
    return getattr(mod, name, None)


def broad_try(fn):
    """True when fn has except on its own, except Exception or except BaseException: they catch your own mistakes too."""
    try:
        tree = ast.parse(inspect.getsource(fn).replace("\r\n", "\n"))
    except (OSError, TypeError, SyntaxError):
        return False
    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler):
            names = [] if node.type is None else (node.type.elts if isinstance(node.type, ast.Tuple) else [node.type])
            if node.type is None or any(isinstance(n, ast.Name) and n.id in ("Exception", "BaseException") for n in names):
                return True
    return False


def catch_only(error):
    return (f"except on its own (or except Exception) catches every error, your own mistakes too, so a slip would never "
            f"show: catch only the one you expect, except {error}:")


# ------------------------------------------------------------------ Project 1 · Recap
def step_1a(mod):
    fn = need(mod, "ask_size")
    if fn is None:
        return "-", "no ask_size yet"
    for answers, want in [(["M"], "M"), (["l"], "L"), ([" s "], "S")]:
        got, printed, e = call(fn, answers, "Size: ")
        if isinstance(e, RanOut) and answers[0] != answers[0].strip():
            return "FIX", f"{answers[0]!r} was refused: take the spaces off with strip() before you check it"
        if isinstance(e, RanOut) and answers[0].strip().islower():
            return "FIX", f"{answers[0]!r} was refused: lower case is fine, so turn the answer into capitals with upper() before you check it"
        if e:
            return "FIX", trouble(e, repr(answers[0]))
        if got != want:
            return "FIX", f"{answers[0]!r} gave back {got!r}: give back {want!r}, in capitals"
    got, printed, e = call(fn, ["", "XL", "medium", "M"], "Size: ")
    if e:
        return "FIX", trouble(e, "a blank, XL and medium, then M,")
    if got != "M" or len(said(printed)) != 3:
        return "FIX", "a blank, XL and medium must each be refused with a message, then M given back"
    return "PASS", "S, M and L come back in capitals; anything else is refused with a message"


def message_for(fn, typed):
    """ask_cups with `typed`, then 4: its first message, with the typed text taken out, so '-3 is too few' and
    '0 is too few' read alike. Gives back (the message, or None, and why not)."""
    got, printed, e = call(fn, [typed, "4"], "Cups: ")
    if e:
        return None, trouble(e, f"{typed}, then 4,")
    lines = said(printed)
    if got != 4 or not lines:
        return None, f"{typed} must be refused with a message, then 4 given back"
    return re.sub(r"(?<![\w.-])" + re.escape(typed) + r"(?![\w.])", "#", lines[0]), None


def step_1b(mod):
    fn = need(mod, "ask_cups")
    if fn is None:
        return "-", "no ask_cups yet"
    for answers, want in [(["3"], 3), (["1"], 1), (["10"], 10)]:
        got, printed, e = call(fn, answers, "Cups: ")
        if e:
            return "FIX", trouble(e, answers[0])
        if got != want:
            return "FIX", f"{answers[0]} gave back {got!r}: give back the number, {want}"
    got, printed, e = call(fn, ["", "three", "0", "11", "4"], "Cups: ")
    if e:
        return "FIX", trouble(e, "a blank, three, 0 and 11, then 4,")
    if got != 4 or len(said(printed)) != 4:
        return "FIX", "a blank, three, 0 and 11 must each be refused with a message, then 4 given back"
    word, _ = message_for(fn, "three")
    zero, _ = message_for(fn, "0")
    if word is not None and word == zero:
        return "FIX", "three and 0 get the same message: give each check its own message, saying what was wrong and what to type"
    return "PASS", "1 to 10 come back as numbers; a blank, a word, 0 and 11 are each refused, with a message for each check"


def step_1c(mod):
    fn = need(mod, "ask_cups")
    if fn is None:
        return "-", "no ask_cups yet"
    said_to = {}
    for typed in ("-3", "0", "three"):
        msg, why = message_for(fn, typed)
        if msg is None:
            return "FIX", why
        said_to[typed] = msg
    if said_to["three"] == said_to["0"]:
        return "FIX", "three and 0 get the same message: give each check its own message (step 1b)"
    if said_to["-3"] == said_to["three"]:
        return "-", "-3 gets the whole-number message, so ask_cups still checks with isdigit(): step 1c swaps it for try and except"
    if said_to["-3"] != said_to["0"]:
        return "FIX", "-3 must get the range check's message, the one 0 gets: with try and except, int() reads -3 as a number"
    got, printed, e = call(fn, ["2.5", "2"], "Cups: ")
    if isinstance(e, (TooLong, SystemExit)):
        return "FIX", trouble(e, "2.5, then 2,")
    if e or got != 2:
        return "FIX", "2.5 must be refused with a message, then 2 given back: int() raises ValueError on 2.5"
    if broad_try(fn):
        return "FIX", catch_only("ValueError")
    return "PASS", "-3 is read as a number and refused by the range check; 2.5 is refused by except ValueError"


def step_1d(mod):
    fn = need(mod, "take_order")
    if fn is None:
        return "-", "no take_order yet"
    for answers, want, line in [(["m", "3"], 7.5, "£7.50"), (["L", "2"], 6.0, "£6.00")]:
        got, printed, e = call(fn, answers)
        if e:
            return "FIX", trouble(e, f"{answers[0]} and {answers[1]}")
        if not isinstance(got, (int, float)) or abs(got - want) > 1e-6:
            return "FIX", f"{answers[1]} cups of {answers[0].upper()} gave back {got!r}: give back the total, {want}"
        if line not in printed:
            return "FIX", f"print the order with its total to two places, like {answers[1]} x {answers[0].upper()}: {line}"
    return "PASS", "each order is priced from the size and the cups, printed to two places and given back"


# ------------------------------------------------------------------ Project 2 · Extension
def in_folder(text, fn):
    """Run fn(path) with an orders file holding text (or no file at all when text is None) in a folder of its own,
    then remove the folder. Give back (what fn gave back, the lines the file holds afterwards, or None for no file)."""
    folder = tempfile.mkdtemp(prefix="checked-")
    path = os.path.join(folder, "orders-check.txt")
    try:
        if text is not None:
            with open(path, "w") as f:
                f.write(text)
        got = fn(path)
        try:
            with open(path) as f:
                after = [line.strip() for line in f if line.strip()]
        except OSError:
            after = None
        return got, after
    finally:
        shutil.rmtree(folder, ignore_errors=True)


def step_2a(mod):
    fn = need(mod, "save_order")
    if fn is None:
        return "-", "no save_order yet"

    def two_orders(path):
        for total in (7.5, 6.0):
            got, printed, e = call(fn, [], total, path)
            if e:
                return e, total
        return None, None

    (e, total), lines = in_folder(None, two_orders)
    if e:
        return "FIX", trouble(e, f"save_order({total}, filename)", "file")
    if lines is None:
        return "FIX", "save_order wrote no file: open the filename it is given with \"a\" and write the total"
    if len(lines) == 1:
        return "FIX", "the second order replaced the first: open the file with \"a\", which adds to the end"
    try:
        values = [float(x) for x in lines]
    except ValueError:
        return "FIX", f"the file holds {lines!r}: write each total on a line of its own, like 7.50"
    if values != [7.5, 6.0]:
        return "FIX", f"two orders, 7.50 then 6.00, left {lines!r} in the file"
    return "PASS", "each order's total goes on the end of the file, one a line"


def step_2b(mod):
    fn = need(mod, "day_total")
    if fn is None:
        return "-", "no day_total yet"
    (got, printed, e), _ = in_folder("7.50\n6.00\n", lambda p: call(fn, [], p))
    if e:
        return "FIX", trouble(e, "a file holding 7.50 and 6.00", "file")
    if not isinstance(got, (int, float)) or abs(got - 13.5) > 1e-6:
        return "FIX", f"a file holding 7.50 and 6.00 gave back {got!r}: give back their total, 13.5"
    (got, printed, e), _ = in_folder(None, lambda p: call(fn, [], p))
    if isinstance(e, FileNotFoundError):
        return "FIX", "no orders file yet makes it crash: try and except FileNotFoundError, and give back 0"
    if e:
        return "FIX", trouble(e, "no orders file", "file")
    if got != 0 or not said(printed):
        return "FIX", "with no orders file, say so and give back 0"
    if broad_try(fn):
        return "FIX", catch_only("FileNotFoundError")
    return "PASS", "the day's takings add up; no file yet gives 0 and a message"


def step_2c(mod):
    fn = need(mod, "day_report")
    if fn is None:
        return "-", "no day_report yet"
    (got, printed, e), _ = in_folder("7.50\n6.00\n", lambda p: call(fn, [], p))
    if e:
        return "FIX", trouble(e, "a file holding 7.50 and 6.00", "file")
    if got is None and "Today" in printed:
        return "FIX", "day_report printed its line: return it instead, so the program can use it"
    if got != "Today: 2 orders, £13.50":
        return "FIX", f"a file holding 7.50 and 6.00 gave back {got!r}: give back 'Today: 2 orders, £13.50'"
    return "PASS", "the report line comes back, ready to print or save"


STEPS = [("1a", step_1a), ("1b", step_1b), ("1c", step_1c), ("1d", step_1d), ("2a", step_2a), ("2b", step_2b), ("2c", step_2c)]


# ------------------------------------------------------------------ your code in a Python of its own, with a time limit
# A loop whose bare except: swallows the checks' own signals never stops by itself, so every check runs in a Python of
# its own and is stopped after LIMIT seconds. The usual run is ONE such Python for every step; only when it runs out of
# time is each step run on its own, all at once, to find which one never stops, and the others are still checked.
LIMIT = 8
RUNAWAY = {
    "1a": "ask_size goes round and round and never stops: read the answer inside the loop",
    "1b": "ask_cups goes round and round and never stops: read the answer inside the loop",
    "1c": "ask_cups goes round and round and never stops: read the answer inside the loop, and catch only ValueError (except ValueError:, not except: on its own, which hides the slip)",
    "1d": "take_order goes round and round and never stops: ask_size and ask_cups must each give back an answer",
    "2a": "save_order never finishes: it adds one line to the file, then stops",
    "2b": "day_total goes round and round and never stops: the loop must move on to the next line, and catch only FileNotFoundError",
    "2c": "day_report goes round and round and never stops: count each line once, then give back the line",
}


def probe(labels):
    """In the Python of its own: run the named steps' checks, and print the verdicts as one line."""
    out = {}
    cafe, why_not = load()
    if "load" in labels:
        out["load"] = ["ok" if cafe is not None else "FIX", why_not or ""]
    for label, step in STEPS:
        if label not in labels:
            continue
        if cafe is None:
            out[label] = ["-" if why_not == NO_CAFE else "FIX", why_not]
            continue
        try:
            verdict, why = step(cafe)
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
                printed, err = p.communicate(timeout=max(0.1, deadline - time.monotonic()))
            except subprocess.TimeoutExpired:
                p.kill()
                p.communicate()
                out[key] = None
                continue
            line = next((ln for ln in reversed(printed.splitlines()) if ln.startswith("PROBE ")), None)
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
    labels = [label for label, _ in STEPS]
    if not os.path.exists(os.path.join(HERE, "cafe.py")):
        return {label: ["-", NO_CAFE] for label in labels}
    first = run_probes({"all": labels})["all"]
    if first is not None:
        return first
    # Something never stopped. Run cafe.py on its own, and each step on its own, to find which.
    groups = {"load": ["load"]}
    groups.update({label: [label] for label in labels})
    got = run_probes(groups)
    verdicts = {}
    for label in labels:
        if got["load"] is None:
            verdicts[label] = ["FIX", LOAD_RUNAWAY]
        elif got[label] is None:
            verdicts[label] = ["FIX", RUNAWAY[label]]
        else:
            verdicts[label] = got[label][label]
    return verdicts


def main():
    got = results()
    verdicts = []
    for label, _ in STEPS:
        verdict, why = got.get(label) or ["FIX", "the check could not run"]
        verdicts.append(verdict)
        print(f"{verdict:<5} {label}  {why}")
    print()
    print("Post this line in the class chat:")
    print("Stretch: " + "  ".join(f"{label} {verdict}" for (label, _), verdict in zip(STEPS, verdicts)))


if __name__ == "__main__":
    if "--probe" in sys.argv:
        probe(sys.argv[sys.argv.index("--probe") + 1].split(","))
    else:
        main()
