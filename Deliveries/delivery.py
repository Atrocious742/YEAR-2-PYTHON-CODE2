# Deliveries: the college shop's delivery log.
# The manager types in each delivery: the item, its product code, how many came, the shelf and the price.
# Every answer is checked where it comes in, so the rest of the program can trust it.
#
# Try it:          python delivery.py
# Check your work: python check.py

STOCK_FILE = "Deliveries\stock.txt"


# ------------------------------------------------------------------ Part 1: the worked example
# Ask until the answer passes every check, in order, then give it back.
def ask_count(prompt, low, high):
    while True:
        text = input(prompt).strip()
        if not text.isdigit():
            print("Type a whole number, like 12.")
        elif not low <= int(text) <= high:
            print(f"Type a number from {low} to {high}.")
        else:
            return int(text)


# ------------------------------------------------------------------ Task 2a
# The item's name. It already refuses a blank answer.
def ask_item(prompt):
    while True:
        text = input(prompt).strip()
        if text == "":
            print("You left it blank. Type the item's name.")
        elif len(text) > 20:
            print("Type a name of 20 characters or fewer.")
        else:
            return text


# ------------------------------------------------------------------ Task 2c
# Shelves are numbered 1 to 12.
def ask_shelf(prompt):
    while True:
        text = input(prompt).strip()
        if not text.isdigit():
            print("Type a whole number, like 7.")
        elif text == "":
            print("You left it blank. Type a shelf number.")
        elif not 1 <= int(text) <= 12:
            print("Type a shelf number from 1 to 12.")
        elif not text.isdigit():
            print("Type a whole number, like 7.")
        else:
            return int(text)


# ------------------------------------------------------------------ Task 2d
# A product code is 3 letters, then 3 digits, like MLK012.
def ask_code(prompt):
    while True:
        # Write this function. Delete the line below first.
        text = input(prompt).strip().upper()        
        if len(text) != 6:
            print("Type a product code of 3 letters, then 3 digits, like MLK012.")
        elif not text[:3].isalpha() or not text[3:].isdigit():
            
            print("Type a product code of 3 letters, then 3 digits, like MLK012.")
        else:
            return text
        



# ------------------------------------------------------------------ Part 2: the worked example
# try runs the line that might fail. If it raises ValueError, except runs instead, and the loop asks again.
def ask_whole(prompt):
    while True:
        text = input(prompt).strip()
        try:
            return int(text)
        except ValueError:
            print(f"'{text}' is not a whole number. Type digits.")


# ------------------------------------------------------------------ Task 2e
# A copy of ask_whole, so it refuses a price like 2.50.
def ask_price(prompt):
    while True:
        text = input(prompt).strip()
        try:
            return int(text)
        except ValueError:
            print(f"'{text}' is not a whole number. Type digits.")


# ------------------------------------------------------------------ Tasks 2f and 2g
# Each line of the stock file is an item and its count, like this: Milk,10
def load_stock(filename):
    stock = {}
    with open(filename) as file:
        lines = file.readlines()
    for line in lines:
        item, count = line.strip().split(",")
        stock[item] = int(count)
    return stock


def save_stock(stock, filename):
    with open(filename, "w") as file:
        for item, count in stock.items():
            file.write(f"{item},{count}\n")


# ------------------------------------------------------------------ the program
def main():
    stock = load_stock(STOCK_FILE)
    print("Delivery log: type in one delivery.")
    item = ask_item("Item: ")
    code = ask_code("Product code: ")
    count = ask_count("How many arrived? ", 1, 51)
    shelf = ask_shelf("Shelf: ")
    price = ask_price("Price each: £")
    stock[item] = stock.get(item, 0) + count
    save_stock(stock, STOCK_FILE)
    print(f"{count} x {item} ({code}), shelf {shelf}, £{price:.2f} each. {item} in stock now: {stock[item]}")


# This line runs main() when you run this file, and not when check.py reads it.
if __name__ == "__main__":
    main()
