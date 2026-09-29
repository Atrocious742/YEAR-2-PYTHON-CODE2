# The Transporter Hotel: the front desk's booking system.
#
# Run it:    python hotel.py
# Check it:  python check.py   (after every step: PASS, FIX, or a dash for a step not started)
#
# The steps are in the project brief. Write each function above main(), in the order
# of the steps, and keep the lines that run the program inside main().

BOOKINGS_FILE = "bookings.json"

# The hotel's eight rooms. Each room number leads to that room's details.
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


def main():
    print("The Transporter Hotel: front desk")
    # Step 9: load the bookings, then show the menu until 0 is chosen.


if __name__ == "__main__":
    main()
