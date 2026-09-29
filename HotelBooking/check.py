# The checks for the Transporter Hotel. Run them after every step:  python check.py
# They run the functions in hotel.py on test bookings of their own (typing answers in for you where the program
# asks), and print PASS, FIX or a dash (not started yet) for every step, then one line to post in the class chat.
# They run your program in a separate Python of their own, so a loop that never stops cannot freeze them: it is
# stopped, and its step says FIX. They never change your files: anything saved while checking goes in a folder of
# the checks' own, which is deleted afterwards. Do not change this file.
import builtins
import contextlib
import copy
import importlib.util
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
REAL_INPUT = builtins.input
LIMIT = 15   # seconds a run of the checks may take before the step it is on is called stuck

# The rooms the checks use: the eight rooms hotel.py was given.
ROOMS = {
    101: {"type": "single", "price": 55, "sleeps": 1},
    102: {"type": "single", "price": 55, "sleeps": 1},
    103: {"type": "double", "price": 80, "sleeps": 2},
    104: {"type": "double", "price": 80, "sleeps": 2},
    105: {"type": "twin", "price": 80, "sleeps": 2},
    201: {"type": "family", "price": 110, "sleeps": 4},
    202: {"type": "family", "price": 110, "sleeps": 4},
    203: {"type": "suite", "price": 150, "sleeps": 2},
}
KEYS = ("ref", "name", "room", "check_in", "check_out", "guests")


# Not Exception: a program's own "except Exception" must not be able to catch these and carry on.
class RanOut(BaseException):
    """The program asked for another answer after the last one the check typed in."""


class TooLong(BaseException):
    """A loop that never stops."""


class Capped(io.StringIO):
    """What a program prints, kept up to a limit, so a loop printing for ever cannot fill the memory."""
    MOST = 200000

    def write(self, text):
        room = self.MOST - self.tell()
        if room > 0:
            super().write(text[:room])
        return len(text)


def no_input(prompt=""):
    raise RanOut()


def plain(e):
    return str(e).rstrip(".")


def load():
    path = os.path.join(HERE, "hotel.py")
    if not os.path.exists(path):
        return None, "there is no hotel.py beside check.py: open the HotelBooking folder itself, the one with both files in it"
    spec = importlib.util.spec_from_file_location("hotel_checked", path)
    mod = importlib.util.module_from_spec(spec)
    builtins.input = no_input
    try:
        with contextlib.redirect_stdout(Capped()):
            spec.loader.exec_module(mod)
    except SyntaxError as e:
        return None, f"hotel.py has a line Python cannot read (line {e.lineno}): run python hotel.py to see it"
    except RanOut:
        return None, "hotel.py asks a question as soon as it is read: keep the lines that run the program inside main()"
    except SystemExit:
        return None, "hotel.py ends as soon as it is read: keep the lines that run the program inside main()"
    except Exception as e:
        return None, f"hotel.py stops with {type(e).__name__} before the checks can reach it: {plain(e)}"
    finally:
        builtins.input = REAL_INPUT
    return mod, None


def call(fn, answers, *args):
    """Run fn(*args) with `answers` typed in for it.
    Gives back what it gave back, what it printed, the error it stopped with (or None) and how many answers it used."""
    todo = list(answers)
    used = [0]

    def typed(prompt=""):
        if not todo:
            raise RanOut()
        used[0] += 1
        return todo.pop(0)

    steps = [0]

    def tracer(frame, event, arg):
        if event == "line":
            steps[0] += 1
            if steps[0] > 300000:
                raise TooLong()
        return tracer

    out = Capped()
    builtins.input = typed
    sys.settrace(tracer)
    try:
        with contextlib.redirect_stdout(out):
            result = fn(*args)
        return result, out.getvalue(), None, used[0]
    except (RanOut, TooLong) as e:
        return None, out.getvalue(), e, used[0]
    except SystemExit:
        return None, out.getvalue(), None, used[0]
    except Exception as e:
        return None, out.getvalue(), e, used[0]
    finally:
        sys.settrace(None)
        builtins.input = REAL_INPUT


def said(printed):
    return [line for line in printed.split("\n") if line.strip()]


def trouble(e, what):
    if isinstance(e, TooLong):
        return f"{what} goes round and round and never stops: check the loop"
    if isinstance(e, RanOut):
        return f"{what} asked for something to be typed in: this function is given its values, and only main() uses input()"
    if isinstance(e, TypeError) and "argument" in str(e):
        return f"{what} crashed with TypeError: {plain(e)}. Give the function the parameters the brief lists, in that order"
    return f"{what} crashed with {type(e).__name__}: {plain(e)}"


def need(mod, name):
    fn = getattr(mod, name, None)
    return fn if callable(fn) else None


def booking(ref, name, room, check_in, check_out, guests=1):
    return {"ref": ref, "name": name, "room": room, "check_in": check_in, "check_out": check_out, "guests": guests}


def number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def by_ref(bookings):
    """The bookings in reference order, so a function that puts them back in another order still matches."""
    return sorted(bookings, key=lambda b: str(b.get("ref")) if isinstance(b, dict) else "")


@contextlib.contextmanager
def these_rooms(mod, rooms):
    old = getattr(mod, "ROOMS", None)
    mod.ROOMS = copy.deepcopy(rooms)
    try:
        yield
    finally:
        mod.ROOMS = old


# ------------------------------------------------------------------ the steps
def step_1(mod):
    fn = need(mod, "show_rooms")
    if fn is None:
        return "-", "no show_rooms yet"
    got, printed, e, used = call(fn, [])
    if e:
        return "FIX", trouble(e, "show_rooms()")
    lines = said(printed)
    if not lines:
        return "FIX", "show_rooms() printed nothing: print one line for each room"
    for room_number, room in ROOMS.items():
        own = re.compile(rf"(?<!\d){room_number}(?!\d)")
        mine = [line for line in lines if own.search(line)]
        if not mine:
            return "FIX", f"no line names room {room_number}: loop over ROOMS.items() and print a line for every room"
        line = mine[0]
        others = [n for n in ROOMS if n != room_number and re.search(rf"(?<!\d){n}(?!\d)", line)]
        if others:
            return "FIX", f"rooms {room_number} and {others[0]} are on the same line: give each room a line of its own"
        if room["type"] not in line.lower():
            return "FIX", f"room {room_number}'s line does not say it is a {room['type']} room"
        price = f"{room['price']:.2f}"
        if price not in line:
            return "FIX", f"show room {room_number}'s price to two places, like £{price}: an f-string with :.2f"
        rest = own.sub("", line).replace(price, "")
        if not re.search(rf"(?<!\d){room['sleeps']}(?!\d)", rest):
            return "FIX", f"room {room_number}'s line does not say how many it sleeps ({room['sleeps']})"
    # the lines must come from ROOMS: change the rooms, and the lines change
    altered = copy.deepcopy(ROOMS)
    altered[101]["price"] = 60
    altered[301] = {"type": "penthouse", "price": 240, "sleeps": 4}
    with these_rooms(mod, altered):
        got, printed, e, used = call(fn, [])
    if e:
        return "FIX", trouble(e, "show_rooms() with a room added")
    if "301" not in printed or "penthouse" not in printed.lower() or "60.00" not in printed:
        return "FIX", "with a room added to ROOMS and a price changed, show_rooms() printed the old list: print each line from ROOMS, not typed out"
    return "PASS", "every room on its own line: its number, type, price to two places and how many it sleeps"


NIGHTS = [
    ("2026-10-05", "2026-10-08", 3, "inside one month"),
    ("2026-10-30", "2026-11-02", 3, "across the end of a month"),
    ("2026-12-30", "2027-01-02", 3, "across the end of a year"),
    ("2028-02-27", "2028-03-01", 3, "across 29 February in a leap year"),
    ("2026-10-05", "2026-10-05", 0, "arriving and leaving on the same day"),
]


def step_2(mod):
    fn = need(mod, "count_nights")
    if fn is None:
        return "-", "no count_nights yet"
    for check_in, check_out, want, why in NIGHTS:
        what = f'count_nights("{check_in}", "{check_out}")'
        got, printed, e, used = call(fn, [], check_in, check_out)
        if e:
            return "FIX", trouble(e, what)
        if got is None:
            return "FIX", f"{what} gave back None: give back the number of nights with return"
        if hasattr(got, "days") and not number(got):
            return "FIX", f"{what} gave back the gap between the dates itself: give back its .days, a whole number"
        if not isinstance(got, int) or isinstance(got, bool):
            return "FIX", f"{what} gave back {got!r}: give back a whole number of nights"
        if got != want:
            return "FIX", (f"{what} ({why}) gave back {got}: it is {want} nights. Turn each date into a date with "
                           f"date.fromisoformat(), then take one from the other")
    return "PASS", "whole numbers of nights: inside a month, across a month, a year and 29 February"


def step_3(mod):
    fn = need(mod, "is_free")
    if fn is None:
        return "-", "no is_free yet"

    def ann():
        return [booking(1, "Ann Lee", 103, "2026-10-05", "2026-10-08", 2)]

    her_stay = "Ann Lee's stay in room 103 (2026-10-05 to 2026-10-08)"
    cases = [
        ([], 103, "2026-10-05", "2026-10-08", True, "with no bookings at all, the room is free"),
        (ann(), 104, "2026-10-05", "2026-10-08", True,
         "Ann Lee's booking is for room 103, so it cannot stop room 104: only bookings for the same room count"),
        (ann(), 103, "2026-10-06", "2026-10-07", False, f"those nights are inside {her_stay}, so they clash"),
        (ann(), 103, "2026-10-04", "2026-10-06", False, f"those nights overlap the start of {her_stay}, so they clash"),
        (ann(), 103, "2026-10-07", "2026-10-10", False, f"those nights overlap the end of {her_stay}, so they clash"),
        (ann(), 103, "2026-10-01", "2026-10-12", False,
         f"that stay goes right round {her_stay}, so they clash: two stays clash when each one starts before the other one ends"),
        (ann(), 103, "2026-10-05", "2026-10-08", False, "the very same nights as Ann Lee clash"),
        (ann(), 103, "2026-10-08", "2026-10-10", True,
         "arriving on 2026-10-08, the day Ann Lee leaves, is fine: the day a guest leaves is free for the next guest"),
        (ann(), 103, "2026-10-02", "2026-10-05", True,
         "leaving on 2026-10-05, the day Ann Lee arrives, is fine: the day a guest leaves is free for the next guest"),
        (ann() + [booking(2, "Ben Ng", 103, "2026-10-10", "2026-10-12")], 103, "2026-10-08", "2026-10-10", True,
         "those nights fit between Ann Lee's stay and Ben Ng's (2026-10-10 to 2026-10-12), so the room is free"),
    ]
    for bookings, room, check_in, check_out, want, why in cases:
        before = copy.deepcopy(bookings)
        what = f'is_free(bookings, {room}, "{check_in}", "{check_out}")'
        got, printed, e, used = call(fn, [], bookings, room, check_in, check_out)
        if e:
            return "FIX", trouble(e, what)
        if bookings != before:
            return "FIX", f"{what} changed the bookings list: is_free only looks at it"
        if got is None:
            return "FIX", f"{what} gave back None: give back True or False with return"
        if not isinstance(got, bool):
            return "FIX", f"{what} gave back {got!r}: give back True or False"
        if got != want:
            return "FIX", f"{what} gave back {got}: {why}"
    return "PASS", "clashes at the start, the end, inside and right round are caught; the day a guest leaves is free; other rooms do not count"


def step_4(mod):
    fn = need(mod, "free_rooms")
    if fn is None:
        return "-", "no free_rooms yet"

    def taken():
        return [booking(1, "Ann Lee", 103, "2026-10-05", "2026-10-08", 2),
                booking(2, "Cat Shah", 201, "2026-10-06", "2026-10-09", 3)]

    cases = [
        ("2026-10-06", "2026-10-07", 2, [104, 105, 202, 203], {103, 201}),
        ("2026-10-06", "2026-10-07", 1, [101, 102, 104, 105, 202, 203], {103, 201}),
        ("2026-10-06", "2026-10-07", 3, [202], {103, 201}),
        ("2026-10-10", "2026-10-12", 4, [201, 202], set()),
        ("2026-10-06", "2026-10-07", 5, [], {103, 201}),
    ]
    for check_in, check_out, guests, want, booked in cases:
        what = f'free_rooms(bookings, "{check_in}", "{check_out}", {guests})'
        got, printed, e, used = call(fn, [], taken(), check_in, check_out, guests)
        if e:
            return "FIX", trouble(e, what)
        if got is None:
            return "FIX", f"{what} gave back None: build a list of room numbers and give it back with return"
        if not isinstance(got, list):
            return "FIX", f"{what} gave back {got!r}: give back a list of room numbers"
        if any(isinstance(x, dict) for x in got):
            return "FIX", f"{what} gave back the rooms' details: give back just their numbers, like [104, 105]"
        if got == want:
            continue
        if not want:
            return "FIX", f"{what} gave back {got}: no room sleeps 5, so give back an empty list, []"
        if sorted(got) == want:
            return "FIX", f"{what} gave back {got}: put the smallest room number first, {want}"
        wrongly_in = sorted(set(got) & booked)
        if wrongly_in:
            return "FIX", f"{what} gave back {got}, with room {wrongly_in[0]}, which is booked for those nights: keep only rooms is_free says are free"
        left_out = sorted(set(want) - set(got))
        if left_out and ROOMS[left_out[0]]["sleeps"] > guests:
            return "FIX", (f"{what} gave back {got}, leaving out room {left_out[0]}, which sleeps {ROOMS[left_out[0]]['sleeps']}: "
                           f"a room that sleeps more is big enough too, so keep rooms that sleep at least {guests}")
        return "FIX", f"{what} gave back {got}: it should be {want}"
    return "PASS", "the free rooms that sleep enough, smallest first, and an empty list when none will do"


def step_5(mod):
    fn = need(mod, "make_booking")
    if fn is None:
        return "-", "no make_booking yet"
    bookings = []
    what = 'make_booking(bookings, "Ann Lee", 103, "2026-10-05", "2026-10-08", 2)'
    got, printed, e, used = call(fn, [], bookings, "Ann Lee", 103, "2026-10-05", "2026-10-08", 2)
    if isinstance(e, ValueError):
        return "FIX", f"{what} was refused ({plain(e)}), and nothing is wrong with it"
    if e:
        return "FIX", trouble(e, what)
    if len(bookings) != 1:
        return "FIX", f"{what} left {len(bookings)} bookings in the list: append the new booking to the list it is given"
    made = bookings[0]
    if not isinstance(made, dict):
        return "FIX", "each booking is a dictionary with the keys ref, name, room, check_in, check_out and guests"
    missing = [k for k in KEYS if k not in made]
    if missing:
        return "FIX", f"the new booking has no {', '.join(missing)}: give it the keys ref, name, room, check_in, check_out and guests"
    if made["check_in"] != "2026-10-05" or made["check_out"] != "2026-10-08":
        return "FIX", (f"the booking holds check_in {made['check_in']!r} and check_out {made['check_out']!r}: keep the dates as "
                       f"the text you were given, like \"2026-10-05\", so they can be saved as JSON")
    if made["room"] != 103 or made["guests"] != 2 or str(made["name"]).strip().lower() != "ann lee":
        return "FIX", f"the booking holds {made!r}: it should hold name Ann Lee, room 103 and guests 2, as they were given"
    if got is None:
        return "FIX", f"{what} gave back None: give back the new booking's reference with return"
    if isinstance(got, dict):
        return "FIX", f"{what} gave back the whole booking: give back just its reference, the number 1"
    if got != 1 or made["ref"] != 1 or isinstance(got, bool):
        return "FIX", f"{what} gave back {got!r}, and the booking's ref is {made['ref']!r}: the first booking's reference is 1"

    bookings = [booking(1, "Ann Lee", 101, "2026-10-01", "2026-10-03"), booking(3, "Ben Ng", 102, "2026-10-01", "2026-10-03")]
    got, printed, e, used = call(fn, [], bookings, "Cat Shah", 104, "2026-10-01", "2026-10-03", 1)
    if e:
        return "FIX", trouble(e, "a booking made when references 1 and 3 are in the list")
    if got != 4 or bookings[-1].get("ref") != 4:
        return "FIX", (f"with bookings 1 and 3 in the list (2 was cancelled), the new booking got reference {got!r}: "
                       f"give one more than the biggest reference in the list, 4, so no two bookings share a number")
    bookings = [booking(2, "Ben Ng", 102, "2026-10-01", "2026-10-03"), booking(3, "Cat Shah", 104, "2026-10-01", "2026-10-03"),
                booking(1, "Ann Lee", 101, "2026-10-01", "2026-10-03")]
    got, printed, e, used = call(fn, [], bookings, "Dan Roe", 105, "2026-10-01", "2026-10-03", 1)
    if e:
        return "FIX", trouble(e, "a booking made when the list holds references 2, 3 and 1, in that order,")
    if got != 4:
        return "FIX", (f"with references 2, 3 and 1 in the list, in that order, the new booking got {got!r}: give one more than "
                       f"the biggest reference in the list, 4, wherever it is in the list")

    wrongs = [
        (("   ", 103, "2026-10-12", "2026-10-14", 1), "a name of only spaces"),
        (("Dan Roe", 999, "2026-10-12", "2026-10-14", 1), "room 999, which the hotel does not have,"),
        (("Dan Roe", 103, "2026-13-01", "2026-13-04", 1), "a date that does not exist, 2026-13-01,"),
        (("Dan Roe", 103, "12/10/2026", "14/10/2026", 1), "dates typed like 12/10/2026, not 2026-10-12,"),
        (("Dan Roe", 103, "2026-10-14", "2026-10-12", 1), "check-out before check-in"),
        (("Dan Roe", 103, "2026-10-12", "2026-10-12", 1), "check-out on the check-in day (0 nights)"),
        (("Dan Roe", 103, "2026-10-12", "2026-10-14", 3), "3 guests in room 103, which sleeps 2,"),
        (("Dan Roe", 103, "2026-10-12", "2026-10-14", 0), "0 guests"),
        (("Dan Roe", 103, "2026-10-06", "2026-10-09", 1), "room 103 for nights Ann Lee already has"),
    ]
    for args, why in wrongs:
        bookings = [booking(1, "Ann Lee", 103, "2026-10-05", "2026-10-08", 2)]
        got, printed, e, used = call(fn, [], bookings, *args)
        if e is None:
            if len(bookings) > 1:
                return "FIX", f"{why} was booked: refuse it with raise ValueError(\"...\") before anything is added"
            return "FIX", f"{why} was not refused with an error: raise ValueError(\"...\") with a message saying what is wrong"
        if not isinstance(e, ValueError):
            return "FIX", f"{why} crashed it with {type(e).__name__}: {plain(e)}. Check for it first, and raise ValueError with a message"
        if len(bookings) != 1:
            return "FIX", f"{why} raised ValueError, but the booking was still added: check everything before you append"
        if not str(e).strip():
            return "FIX", f"{why} raised ValueError with no message: say what is wrong, like raise ValueError(\"There is no room 999.\")"
    return "PASS", "a good booking is added with the next reference; each wrong one is refused with ValueError and a message, and nothing added"


def step_6(mod):
    fn = need(mod, "cancel_booking")
    if fn is None:
        return "-", "no cancel_booking yet"
    bookings = [booking(1, "Ann Lee", 101, "2026-10-01", "2026-10-03"),
                booking(3, "Ben Ng", 102, "2026-10-01", "2026-10-03"),
                booking(4, "Cat Shah", 103, "2026-10-01", "2026-10-03")]
    what = "cancel_booking(bookings, 3)"
    got, printed, e, used = call(fn, [], bookings, 3)
    if e:
        return "FIX", trouble(e, what)
    refs = [b.get("ref") for b in bookings]
    if refs == [1, 3, 4]:
        return "FIX", (f"after {what}, booking 3 is still in the list it was given: take it out of that list, "
                       f"with bookings.remove(booking), rather than making a new one")
    if refs == [1, 3]:
        return "FIX", f"{what} took out booking 4: find the booking whose \"ref\" is 3. A reference is not a position in the list"
    if sorted(refs) != [1, 4]:
        return "FIX", f"{what} left the references {refs}: take out booking 3 only, leaving 1 and 4"
    if got is not True:
        return "FIX", f"{what} gave back {got!r}: give back True when it cancels a booking"
    before = copy.deepcopy(bookings)
    what = "cancel_booking(bookings, 2), with no booking 2 in the list,"
    got, printed, e, used = call(fn, [], bookings, 2)
    if e:
        return "FIX", trouble(e, what)
    if by_ref(bookings) != by_ref(before):
        return "FIX", f"{what} changed the list: when there is no such booking, change nothing"
    if got is not False:
        return "FIX", f"{what} gave back {got!r}: give back False when there is no such booking"
    return "PASS", "the booking with that reference is taken out and True given back; no such booking gives False"


BILLS = [
    (booking(1, "Ann Lee", 103, "2026-10-05", "2026-10-08", 2), 240.0, "3 nights in room 103 at £80.00 a night"),
    (booking(2, "Ben Ng", 101, "2026-10-01", "2026-10-07"), 330.0,
     "6 nights in room 101 at £55.00 a night, full price: the 10% off is for 7 nights or more"),
    (booking(3, "Cat Shah", 101, "2026-10-01", "2026-10-08"), 346.5,
     "7 nights in room 101 is £385.00, less 10%, because a stay of exactly 7 nights gets it too"),
    (booking(4, "Dan Roe", 203, "2026-10-01", "2026-10-15", 2), 1890.0, "14 nights in room 203 is £2100.00, less 10%"),
    (booking(5, "Eve Hart", 201, "2026-12-30", "2027-01-02", 4), 330.0,
     "3 nights across the end of the year in room 201 at £110.00 a night"),
]


def step_7(mod):
    fn = need(mod, "bill")
    if fn is None:
        return "-", "no bill yet"
    for made, want, why in BILLS:
        what = f"bill() for booking {made['ref']}"
        got, printed, e, used = call(fn, [], copy.deepcopy(made))
        if e:
            return "FIX", trouble(e, what)
        if got is None:
            return "FIX", f"{what} gave back None: give back the cost, a number, with return"
        if isinstance(got, str):
            return "FIX", f"{what} gave back the text {got!r}: give back the number, and let the menu show it to two places"
        if not number(got):
            return "FIX", f"{what} gave back {got!r}: give back the cost as a number"
        if abs(got - want) > 0.005:
            return "FIX", f"{what} gave back {got}, and it should be {want:.2f}: {why}"
    return "PASS", "nights times the room's price a night, with 10% off from 7 nights (7 included)"


def step_8(mod):
    save, load_back = need(mod, "save_bookings"), need(mod, "load_bookings")
    if save is None and load_back is None:
        return "-", "no save_bookings or load_bookings yet"
    if save is None:
        return "FIX", "no save_bookings yet: step 8 needs both functions"
    if load_back is None:
        return "FIX", "no load_bookings yet: step 8 needs both functions"
    folder = tempfile.mkdtemp()
    try:
        path = os.path.join(folder, "bookings-check.json")
        two = [booking(1, "Ann Lee", 103, "2026-10-05", "2026-10-08", 2), booking(2, "Ben Ng", 101, "2026-10-01", "2026-10-03")]
        got, printed, e, used = call(save, [], copy.deepcopy(two), path)
        if e:
            return "FIX", trouble(e, "save_bookings(bookings, filename)")
        if not os.path.exists(path):
            return "FIX", "save_bookings wrote no file: open the filename it is given with \"w\", and json.dump the list into it"
        try:
            with open(path) as file:
                on_disk = json.load(file)
        except ValueError:
            return "FIX", "the file save_bookings wrote is not JSON: write it with json.dump(bookings, file)"
        if on_disk != two:
            return "FIX", "the file save_bookings wrote does not hold the bookings it was given: json.dump the whole list"
        one = two[:1]
        got, printed, e, used = call(save, [], copy.deepcopy(one), path)
        if e:
            return "FIX", trouble(e, "saving a second time")
        try:
            with open(path) as file:
                on_disk = json.load(file)
        except ValueError:
            return "FIX", "saving a second time added to the end of the file, so it is no longer JSON: open it with \"w\", which starts the file again"
        if on_disk != one:
            return "FIX", "after a second save, the file does not hold just the second list: open it with \"w\""
        got, printed, e, used = call(load_back, [], path)
        if e:
            return "FIX", trouble(e, "load_bookings(filename)")
        if got != one:
            return "FIX", f"load_bookings gave back {got!r}: give back the list the file holds, with json.load"
        got, printed, e, used = call(load_back, [], os.path.join(folder, "not-there-yet.json"))
        if isinstance(e, FileNotFoundError):
            return "FIX", "with no file yet, load_bookings crashes: use try and except FileNotFoundError, and give back an empty list"
        if e:
            return "FIX", trouble(e, "load_bookings with no file yet")
        if got != []:
            return "FIX", f"with no file yet, load_bookings gave back {got!r}: give back an empty list, []"
    finally:
        shutil.rmtree(folder, ignore_errors=True)
    return "PASS", "the bookings go into a JSON file and come back out the same; no file yet gives an empty list"


def run_main(mod, fn, answers, folder):
    """main() run in `folder`, its BOOKINGS_FILE there, with `answers` typed in."""
    old_dir = os.getcwd()
    had = hasattr(mod, "BOOKINGS_FILE")
    old_file = getattr(mod, "BOOKINGS_FILE", None)
    os.chdir(folder)
    mod.BOOKINGS_FILE = "bookings.json"
    try:
        return call(fn, answers)
    finally:
        os.chdir(old_dir)
        if had:
            mod.BOOKINGS_FILE = old_file


def saved_in(folder):
    """What bookings.json in `folder` holds: (the list, None), (None, None) with no file, or (None, the problem)."""
    path = os.path.join(folder, "bookings.json")
    if not os.path.exists(path):
        return None, None
    try:
        with open(path) as file:
            return json.load(file), None
    except ValueError:
        return None, "bookings.json is not JSON after 0: save it with save_bookings"


def named(saved, who):
    return [b for b in saved if isinstance(b, dict) and str(b.get("name", "")).strip().lower() == who]


def step_9(mod):
    fn = need(mod, "main")
    if fn is None:
        return "-", "no main() yet: put it back at the bottom of hotel.py, as it was given"
    folder = tempfile.mkdtemp()
    try:
        # 1. a booking made at the menu, then 0: saved
        first = ["3", "Ann Lee", "103", "2026-10-05", "2026-10-08", "2", "0"]
        got, printed, e, used = run_main(mod, fn, first, folder)
        if e is None and used == 0:
            return "-", "main() does not ask for anything yet: step 9 builds the menu"
        if isinstance(e, RanOut):
            return "FIX", ("it asked for more than 3, then option 3's five answers, then 0: option 3 asks the name, the room, "
                           "the check-in date, the check-out date and the guests, in that order and nothing else, and 0 saves and ends the program")
        if e:
            return "FIX", trouble(e, "booking room 103 through the menu")
        if used < len(first):
            return "FIX", "it stopped before 0 was chosen: show the menu again after each choice, until 0"
        saved, problem = saved_in(folder)
        if problem:
            return "FIX", problem
        if saved is None:
            return "FIX", "after 0 there is no bookings file: 0 must save the bookings to BOOKINGS_FILE with save_bookings"
        if not saved:
            return "FIX", ("option 3 booked nothing: the file saved at 0 holds no booking. Option 3 asks all five things, turns "
                           "the room number and the guests into whole numbers with int(), calls make_booking, and prints the reference")
        made = saved[0] if isinstance(saved, list) and isinstance(saved[0], dict) else {}
        if made.get("room") != 103 or made.get("check_in") != "2026-10-05" or made.get("check_out") != "2026-10-08" or made.get("guests") != 2:
            return "FIX", f"option 3 saved {saved!r}: it should hold Ann Lee in room 103, 2026-10-05 to 2026-10-08, 2 guests"

        # 2. the next run loads it, and a clash is refused with make_booking's own message
        second = ["3", "Ben Ng", "103", "2026-10-06", "2026-10-07", "1", "0"]
        got, printed, e, used = run_main(mod, fn, second, folder)
        if isinstance(e, ValueError):
            return "FIX", (f"a booking that clashes crashed the program with ValueError: {plain(e)}. Put the booking inside try, "
                           f"and print the message in except ValueError")
        if isinstance(e, RanOut):
            return "FIX", "after a refused booking it asked again: say what is wrong, then go back to the menu"
        if e:
            return "FIX", trouble(e, "a second run, booking nights room 103 already has,")
        saved, problem = saved_in(folder)
        if problem:
            return "FIX", problem
        saved = saved if isinstance(saved, list) else []
        if not named(saved, "ann lee"):
            return "FIX", "the second run lost the first run's booking: load the saved bookings at the start of main(), before the menu"
        if len(saved) > 1:
            return "FIX", ("the second run booked room 103 on top of Ann Lee's stay: make_booking must refuse it (step 5), "
                           "and the menu prints its message")
        maker = need(mod, "make_booking")
        if maker is not None:
            _, _, refused, _ = call(maker, [], [booking(1, "Ann Lee", 103, "2026-10-05", "2026-10-08", 2)],
                                    "Ben Ng", 103, "2026-10-06", "2026-10-07", 1)
            if isinstance(refused, ValueError) and str(refused).strip() and str(refused).strip() not in printed:
                return "FIX", f"a refused booking must say what is wrong: print make_booking's message, {str(refused).strip()!r}"

        # 3. every other option on the menu does its job: what it prints is counted against a run that only chooses 0,
        # so a program that shows the rooms as it starts is not taken for one that shows them at option 1
        got, baseline, e, used = run_main(mod, fn, ["0"], folder)
        baseline = baseline.lower()
        checks = [
            (["1", "0"], ["101", "203"], "option 1 must show the rooms"),
            (["2", "2026-10-06", "2026-10-07", "2", "0"], ["104", "202"],
             "option 2, for 2026-10-06 to 2026-10-07 and 2 guests, must show the free rooms, 104 and 202 among them"),
            (["5", "1", "0"], ["240"], "option 5 for booking 1 must show its bill, 240.00"),
            (["6", "0"], ["ann lee"], "option 6 must list every booking, Ann Lee's among them"),
        ]
        for answers, wants, why in checks:
            got, printed, e, used = run_main(mod, fn, answers, folder)
            if isinstance(e, RanOut):
                return "FIX", f"{why}: after {', '.join(answers)} it asked for more. Ask only what the brief lists"
            if e:
                return "FIX", trouble(e, f"choosing {answers[0]}")
            missing = [w for w in wants if printed.lower().count(w) <= baseline.count(w)]
            if missing:
                return "FIX", f"{why}, and nothing it printed has {missing[0]!r}"

        # 4. typing mistakes get a message, never a crash (asking again, or going back to the menu: either is fine)
        for answers, why in [(["4", "abc", "0", "0"], "typing abc for a booking's reference"),
                             (["3", "Cy Doe", "abc", "101", "2026-10-20", "2026-10-21", "1", "0"], "typing abc for a room number"),
                             (["x", "99", "0"], "choosing x, then 99, which are not on the menu,")]:
            got, printed, e, used = run_main(mod, fn, answers, folder)
            if isinstance(e, RanOut):
                return "FIX", f"after {why} it asked for more than expected: refuse it with a message, then ask again or go back to the menu"
            if e:
                return "FIX", f"{why} crashed the program with {type(e).__name__}: refuse it with a message instead"
            if used < 3:
                return "FIX", f"after {why} the program stopped: say what is wrong and carry on until 0"

        # 5. option 4 cancels, and the file shows it
        got, printed, e, used = run_main(mod, fn, ["4", "1", "0"], folder)
        if e:
            return "FIX", trouble(e, "cancelling booking 1 through the menu")
        saved, problem = saved_in(folder)
        if problem:
            return "FIX", problem
        if named(saved or [], "ann lee"):
            return "FIX", "option 4 with reference 1 did not cancel Ann Lee's booking: call cancel_booking, and save the bookings"
    finally:
        shutil.rmtree(folder, ignore_errors=True)
    return "PASS", "every option does its job, a booking made at the menu is there next time, and a clash or a typing mistake gets a message, not a crash"


def step_10(mod):
    path = os.path.join(HERE, "README.md")
    if not os.path.exists(path):
        return "-", "there is no README.md beside hotel.py: it came in the zip"
    with open(path, encoding="utf-8", errors="replace") as file:
        text = file.read()
    heading = re.search(r"^##\s*A decision I made\s*$", text, re.M)
    if not heading:
        return "FIX", "README.md has lost its heading, ## A decision I made: put it back and write under it"
    body = text[heading.end():]
    after = re.search(r"^#{1,2}\s", body, re.M)     # a ### heading of your own inside the write-up is fine
    if after:
        body = body[:after.start()]
    hidden = max([len(re.findall(r"[A-Za-z0-9']+", c)) for c in re.findall(r"<!--(.*?)-->", body, re.S)] or [0])
    body = re.sub(r"<!--.*?-->", "", body, flags=re.S)
    words = re.findall(r"[A-Za-z0-9']+", body)
    if not words and hidden > 40:
        return "FIX", "your write-up is inside the <!-- and --> marks, which hide it: move it onto the lines below them"
    if not words:
        return "-", "nothing under A decision I made yet"
    if len(words) < 60:
        return "FIX", f"{len(words)} words so far: justify it in three short paragraphs, 60 words or more"
    low = body.lower()
    if not re.search(r"\bbecause\b", low):
        return "FIX", "there is no because: give the reason your choice fits a hotel's front desk"
    if not re.search(r"\b(than|instead|rather|compared|whereas|unlike|versus|alternative|other way|other option)\b", low):
        return "FIX", "say what the other way was, and why yours is more suitable than it here"
    return "PASS", (f"{len(words)} words, with a because and the other way: that is the shape, and your teacher reads "
                    f"what it says, because a check cannot mark reasoning")


def step_11(mod):
    fn = need(mod, "change_booking")
    if fn is None:
        return "-", "no change_booking yet (a step for anyone still going)"

    def three():
        return [booking(1, "Ann Lee", 103, "2026-10-05", "2026-10-08", 2),
                booking(2, "Ben Ng", 103, "2026-10-10", "2026-10-12"),
                booking(3, "Cat Shah", 201, "2026-10-06", "2026-10-09", 3)]

    bookings = three()
    what = 'change_booking(bookings, 1, "2026-10-06", "2026-10-09")'
    got, printed, e, used = call(fn, [], bookings, 1, "2026-10-06", "2026-10-09")
    if isinstance(e, ValueError):
        return "FIX", (f"moving booking 1 on by a night was refused ({plain(e)}): it clashed with its own old dates. "
                       f"Check the new dates against every booking except the one you are changing")
    if e:
        return "FIX", trouble(e, what)
    ones = [b for b in bookings if b.get("ref") == 1]
    if len(bookings) != 3 or len(ones) != 1:
        return "FIX", f"{what} left {len(bookings)} bookings: change booking 1 where it is, adding and taking out nothing"
    if (ones[0]["check_in"], ones[0]["check_out"]) != ("2026-10-06", "2026-10-09"):
        return "FIX", f"{what} did not change booking 1's dates: set its check_in and check_out to the new dates"
    if got is not True:
        return "FIX", f"{what} gave back {got!r}: give back True when it changes the booking"

    before = by_ref(copy.deepcopy(bookings))
    what = "moving booking 1 to 2026-10-09 to 2026-10-11, which clashes with booking 2,"
    got, printed, e, used = call(fn, [], bookings, 1, "2026-10-09", "2026-10-11")
    if e is None:
        return "FIX", f"{what} was allowed: refuse it with raise ValueError(\"...\")"
    if not isinstance(e, ValueError):
        return "FIX", trouble(e, what)
    if by_ref(bookings) != before:
        return "FIX", f"{what} was refused, but booking 1 was changed anyway: check first, change after"

    for args, why in [((9, "2026-10-20", "2026-10-22"), "booking 9, which does not exist,"),
                      ((2, "2026-10-14", "2026-10-12"), "check-out before check-in"),
                      ((2, "2026-10-32", "2026-11-02"), "a date that does not exist, 2026-10-32,")]:
        bookings = three()
        got, printed, e, used = call(fn, [], bookings, *args)
        if e is None:
            return "FIX", f"{why} was not refused: raise ValueError with a message"
        if not isinstance(e, ValueError):
            return "FIX", f"{why} crashed it with {type(e).__name__}: {plain(e)}. Check for it, and raise ValueError with a message"
        if by_ref(bookings) != by_ref(three()):
            return "FIX", f"{why} was refused, but the bookings were changed anyway: check first, change after"
    return "PASS", "a booking moves to new dates without clashing with itself; a clash, a missing booking and wrong dates are refused"


def step_12(mod):
    fn = need(mod, "occupancy")
    if fn is None:
        return "-", "no occupancy yet (a step for anyone still going)"

    def four():
        return [booking(1, "Ann Lee", 103, "2026-10-05", "2026-10-08", 2),
                booking(2, "Cat Shah", 201, "2026-10-06", "2026-10-09", 3),
                booking(3, "Dan Roe", 101, "2026-10-08", "2026-10-10"),
                booking(4, "Eve Hart", 202, "2026-10-07", "2026-10-09", 4)]

    cases = [
        ("2026-10-07", 37.5, "Ann Lee, Cat Shah and Eve Hart are staying, 3 rooms of 8"),
        ("2026-10-08", 37.5, "Cat Shah, Dan Roe and Eve Hart are staying, 3 rooms of 8: Ann Lee leaves that day, so her room is free that night"),
        ("2026-11-01", 0.0, "nobody is staying"),
    ]
    for night, want, why in cases:
        what = f'occupancy(bookings, "{night}")'
        got, printed, e, used = call(fn, [], four(), night)
        if e:
            return "FIX", trouble(e, what)
        if got is None:
            return "FIX", f"{what} gave back None: give back the percentage with return"
        if not number(got):
            return "FIX", f"{what} gave back {got!r}: give back the percentage as a number"
        if abs(got - want) > 0.05:
            return "FIX", f"{what} gave back {got}: {why}, so it is {want}"
    small = {n: ROOMS[n] for n in (101, 201, 202)}
    with these_rooms(mod, small):
        got, printed, e, used = call(fn, [], four(), "2026-10-09")
    what = "in a hotel of 3 rooms, with 1 booked,"
    if e:
        return "FIX", trouble(e, f"occupancy {what}")
    if not number(got):
        return "FIX", f"occupancy {what} gave back {got!r}: give back the percentage as a number"
    if abs(got - 12.5) < 0.05:
        return "FIX", f"occupancy {what} still worked out of 8: use len(ROOMS), the number of rooms, not a typed 8"
    if abs(got - 100 / 3) < 1e-6:
        return "FIX", f"occupancy {what} gave back {got}: round it to one place, 33.3"
    if abs(got - 33.3) > 1e-9:
        return "FIX", f"occupancy {what} gave back {got}: it is 33.3"
    return "PASS", "the percentage of the rooms in ROOMS booked on a night, to one place; a check-out day is not a night of the stay"


STEPS = [("1", step_1), ("2", step_2), ("3", step_3), ("4", step_4), ("5", step_5), ("6", step_6), ("7", step_7),
         ("8", step_8), ("9", step_9), ("10", step_10), ("11", step_11), ("12", step_12)]


# ------------------------------------------------------------------ running them
def emit(record):
    sys.__stdout__.write(json.dumps(record) + "\n")
    sys.__stdout__.flush()


def run_steps(first):
    """In the checks' own Python: load hotel.py, then run every step from `first`, one line of results each."""
    hotel, why_not = load()
    emit({"loaded": hotel is not None})
    for label, step in STEPS[first:]:
        if step is step_10:
            continue            # README.md only: the checks run it themselves
        if hotel is None:
            verdict, why = "FIX", why_not
        else:
            try:
                with these_rooms(hotel, ROOMS):
                    verdict, why = step(hotel)
            except (RanOut, TooLong) as e:
                verdict, why = "FIX", trouble(e, f"step {label}")
            except Exception as e:
                verdict, why = "FIX", f"the check could not run: {type(e).__name__}: {plain(e)}"
        emit({"step": label, "verdict": verdict, "why": why})


def in_own_python(first):
    """The results of the steps from `first` on, run in a Python of their own. A step that is still running after
    LIMIT seconds is stuck: the results so far come back, and whether hotel.py finished loading."""
    try:
        done = subprocess.run([sys.executable or "python", os.path.abspath(__file__), "--from", str(first)],
                              cwd=HERE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=LIMIT)
        out, err, finished = done.stdout, done.stderr, True
    except subprocess.TimeoutExpired as stuck:
        out, err, finished = (stuck.stdout or b""), (stuck.stderr or b""), False
    results, loaded = {}, None
    last = [line for line in err.decode("ascii", "replace").splitlines() if line.strip()]
    if finished and last:
        results["error"] = last[-1].strip()[:160]
    for raw in out.decode("ascii", "replace").splitlines():
        try:
            record = json.loads(raw)
        except ValueError:
            continue
        if "loaded" in record:
            loaded = record["loaded"]
        elif "step" in record:
            results[record["step"]] = (record["verdict"], record["why"])
    return results, finished, loaded


@contextlib.contextmanager
def own_bookings_kept():
    """A program that saves beside hotel.py rather than in the checks' own folder would overwrite your bookings.json:
    put it back as it was."""
    path = os.path.join(HERE, "bookings.json")
    before = None
    if os.path.exists(path):
        with open(path, "rb") as file:
            before = file.read()
    try:
        yield
    finally:
        if before is not None:
            with open(path, "wb") as file:
                file.write(before)
        elif os.path.exists(path):
            os.remove(path)


def main():
    print("Checking hotel.py ...")
    results = {"10": step_10(None)}
    order = [label for label, _ in STEPS]
    with own_bookings_kept():
        first = 0
        while first < len(STEPS):
            got, finished, loaded = in_own_python(first)
            results.update(got)
            if finished:
                break
            if not loaded:
                for label in order[first:]:
                    results.setdefault(label, ("FIX", "hotel.py never finishes being read: something outside a function "
                                                      "runs for ever. Keep the lines that run the program inside main()"))
                break
            stuck = next((i for i in range(first, len(STEPS)) if order[i] not in results and order[i] != "10"), None)
            if stuck is None:
                break
            results[order[stuck]] = ("FIX", f"step {order[stuck]} never finished: a loop that never stops. Check the loop "
                                            f"ends, and that an except in it does not catch everything and carry on")
            first = stuck + 1
    for label in order:
        verdict, why = results.get(label, ("FIX", "the check could not run" + (f": {results['error']}" if "error" in results else "")))
        print(f"{verdict:<5} {label:>2}  {why}")
    print()
    print("Post this line in the class chat:")
    print("Hotel booking: " + "  ".join(f"{label} {results.get(label, ('FIX',))[0]}" for label in order))


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--from":
        run_steps(int(sys.argv[2]))
    else:
        main()
