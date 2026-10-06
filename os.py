def welcomeMessageData():
    print("1 sign up")
    print("2 login")
    print("3 driving log")

welcomeMessageData()
def test():
    print("test")
def handleWelcomeInput():
    while True:
        try:
            userInput = int(input("> "))
            if userInput-1 in range(0, 3):
                test()
            else:
                raise IndexError("Please enter a number between 1 to 3")
            break
        except ValueError, IndexError:
            print("\033[A\033[2K\033[A\033[2K", end="", flush=True)
            print(f"\x1b[31mPlease only enter a number from 1 to {3}.\x1b[0m")

handleWelcomeInput()
