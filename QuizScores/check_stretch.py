# QuizScores: the checks for the stretch task. Run it in the terminal with:  python check_stretch.py
# It reads your repository and prints PASS, FIX or a dash (not started yet) for each step,
# then one line to post in the class chat. It never changes anything. Do not change this file.
import os
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
FIRST = [7, 9, 4, 8, 6, 10]
FOLDER = "QuizScores"
OWN = {"scores.py", "check_stretch.py", ".gitignore", ".vscode"}   # what the first commit may hold


def git(*args):
    """Run one git command in this folder. Give back (exit code, what it printed), or (None, "") with no Git."""
    try:
        done = subprocess.run(["git", *args], cwd=HERE, capture_output=True, text=True,
                              encoding="utf-8", errors="replace")
    except FileNotFoundError:
        return None, ""
    return done.returncode, done.stdout.replace("\r\n", "\n")


def commits():
    code, out = git("rev-list", "--reverse", "HEAD")
    return out.split() if code == 0 else []


def subject(sha):
    return git("log", "-1", "--format=%s", sha)[1].strip()


def file_at(sha, name):
    if not sha:
        return None
    code, out = git("show", f"{sha}:{name}")
    return out if code == 0 else None


def says_what_changed(sha):
    return len(subject(sha).split()) >= 3


def run_version(sha, scores_txt=None):
    """Run one version of scores.py in a scratch folder. Give back (what it printed, report.txt or None)."""
    source = file_at(sha, "scores.py")
    if source is None:
        return "", None
    saved = file_at(sha, "scores.txt")
    with tempfile.TemporaryDirectory() as tmp:
        with open(os.path.join(tmp, "scores.py"), "w", encoding="utf-8") as f:
            f.write(source)
        if scores_txt is not None or saved is not None:
            with open(os.path.join(tmp, "scores.txt"), "w", encoding="utf-8") as f:
                f.write(scores_txt if scores_txt is not None else saved)
        try:
            run = subprocess.run([sys.executable, "scores.py"], cwd=tmp, capture_output=True, text=True,
                                 encoding="utf-8", errors="replace", timeout=10)
            printed = run.stdout.replace("\r\n", "\n")
        except subprocess.TimeoutExpired:
            printed = ""
        report = os.path.join(tmp, "report.txt")
        text = open(report, encoding="utf-8").read() if os.path.exists(report) else None
    return printed, text


def scores_in(printed):
    return [int(n) for n in re.findall(r"^Score: (\d+)\s*$", printed, re.M)]


def average_line(printed):
    found = re.search(r"^Average: (\S+)\s*$", printed, re.M)
    return found.group(1) if found else None


def one_place(printed):
    return bool(re.fullmatch(r"\d+\.\d", average_line(printed) or ""))


def first_change(history, test):
    """The first commit after the first version where test() turns true, or None."""
    results = [test(sha) for sha in history]
    for i in range(1, len(history)):
        if results[i] and not results[i - 1]:
            return history[i]
    return None


def check_1a(history):
    if os.path.basename(os.path.realpath(HERE)).lower() != FOLDER.lower():
        return "FIX", (f"these files are in {HERE}, not in a folder called {FOLDER}: they came out of the zip loose. "
                       "Tell your teacher before you go on")
    if not git("config", "user.name")[1].strip() or not git("config", "user.email")[1].strip():
        return "FIX", "Git does not know your name and email in this repository yet"
    if not history:
        return "FIX", "no commit yet"
    stray = sorted(n for n in git("ls-tree", "--name-only", history[0])[1].split("\n") if n and n not in OWN)
    if stray:
        return "FIX", f"the first commit holds {stray[0]}, which did not come in the zip: tell your teacher before you go on"
    if file_at(history[-1], "scores.py") is None:
        return "FIX", "scores.py is not in a commit yet: git add scores.py, then git commit"
    return "PASS", "the program is saved in a commit"


def check_1b(history):
    sha = first_change(history, lambda s: one_place(run_version(s)[0]))
    if sha is None:
        return "-", "not started yet"
    if not says_what_changed(sha):
        return "FIX", f'the message "{subject(sha)}" does not say what changed: use at least three words'
    return "PASS", "the average prints to one decimal place, in a commit of its own"


def check_1c(history):
    sha = first_change(history, lambda s: scores_in(run_version(s)[0]) == FIRST + [3])
    if sha is None:
        return "-", "not started yet"
    if not says_what_changed(sha):
        return "FIX", f'the message "{subject(sha)}" does not say what changed: use at least three words'
    return "PASS", "the score of 3 is added, in a commit of its own"


def check_1d(history):
    added = first_change(history, lambda s: scores_in(run_version(s)[0]) == FIRST + [3])
    reverts = [sha for sha in history if subject(sha).startswith("Revert ")]
    if added is None:
        if reverts:
            return "FIX", "the revert undid a different commit: the one to undo is the commit that added the 3"
        return "-", "not started yet"
    later = history[history.index(added) + 1:]
    wanted = f'Revert "{subject(added)}"'
    undone = [sha for sha in later if subject(sha) == wanted]
    if not undone:
        if any(sha in later for sha in reverts):
            return "FIX", "the revert undid a different commit: the one to undo is the commit that added the 3"
        if any(scores_in(run_version(sha)[0]) == FIRST for sha in later):
            return "FIX", "the 3 was taken out by hand: undo the commit with git revert, so the history shows it"
        return "-", "not started yet"
    if scores_in(run_version(undone[-1])[0]) != FIRST:
        return "FIX", "after the revert the program should print the six first scores again"
    return "PASS", "the added score is undone by a revert"


def check_2a(history):
    last = history[-1]
    if file_at(last, "scores.txt") is None:
        return "-", "not started yet"
    printed = run_version(last, "2\n4\n")[0]
    if scores_in(printed) != [2, 4] or average_line(printed) != "3.0":
        return "FIX", "scores.py should read its scores from scores.txt: change scores.txt and the output should change"
    if scores_in(run_version(last)[0]) != FIRST:
        return "FIX", "scores.txt should hold the six first scores, one on each line"
    sha = first_change(history, lambda s: file_at(s, "scores.txt") is not None)
    if sha and not says_what_changed(sha):
        return "FIX", f'the message "{subject(sha)}" does not say what changed: use at least three words'
    return "PASS", "the scores come from scores.txt"


def check_2b(history):
    has_function = lambda s: bool(re.search(r"^def average_of\(", file_at(s, "scores.py") or "", re.M))
    last = history[-1]
    if not has_function(last):
        return "-", "not started yet"
    source = file_at(last, "scores.py")
    if not re.search(r"^\s+return\b", source, re.M):
        return "FIX", "average_of should return the average, not print it"
    if average_line(run_version(last, "2\n4\n")[0]) != "3.0":
        return "FIX", "the average is wrong: run it with two scores you can check by hand"
    sha = first_change(history, has_function)
    if sha and not says_what_changed(sha):
        return "FIX", f'the message "{subject(sha)}" does not say what changed: use at least three words'
    return "PASS", "average_of returns the average"


def check_2c(history):
    writes = lambda s: "Average: 3.0" in (run_version(s, "2\n4\n")[1] or "")
    last = history[-1]
    if not writes(last):
        if run_version(last, "2\n4\n")[1] is None:
            return "-", "not started yet"
        return "FIX", "report.txt should hold the same lines the program prints, the average included"
    sha = first_change(history, writes)
    if sha and not says_what_changed(sha):
        return "FIX", f'the message "{subject(sha)}" does not say what changed: use at least three words'
    return "PASS", "the report is saved in report.txt"


STEPS = [("1a", check_1a), ("1b", check_1b), ("1c", check_1c), ("1d", check_1d),
         ("2a", check_2a), ("2b", check_2b), ("2c", check_2c)]


def main():
    verdicts = []
    if git("--version")[0] is None:
        print("Git was not found on this PC.")
        verdicts = ["-"] * len(STEPS)
    elif not os.path.isdir(os.path.join(HERE, ".git")):
        code, top = git("rev-parse", "--show-toplevel")
        verdicts = ["-"] * len(STEPS)
        if code == 0 and top.strip():
            verdicts[0] = "FIX"
            print(f"FIX   1a: the repository was made too high up, in {top.strip()}, not in {FOLDER}: tell your teacher before you go on")
        elif os.path.basename(os.path.realpath(HERE)).lower() != FOLDER.lower():
            print(f"These files are not in a folder called {FOLDER}: they came out of the zip loose. "
                  "Tell your teacher before you run git init.")
        else:
            print("There is no repository in this folder yet. Open the QuizScores folder itself in VS Code, then git init.")
    else:
        history = commits()
        for label, check in STEPS:
            if label != "1a" and not history:
                verdict, why = "-", "not started yet"
            else:
                verdict, why = check(history)
            verdicts.append(verdict)
            print(f"{verdict:<5} {label}: {why}")
    print()
    print("Post this line in the class chat:")
    print("Stretch: " + "  ".join(f"{label} {verdict}" for (label, _), verdict in zip(STEPS, verdicts)))


main()
