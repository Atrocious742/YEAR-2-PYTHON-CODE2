# Type answers into ask_count and see what it gives back. Press Ctrl+C to stop.
from delivery import ask_count

while True:
    print("Given back:", ask_count("How many arrived? ", 1, 50))
