# QuizScores: the scores from one class quiz.
# It prints each score, then the class average.

scores = [7, 9, 4, 8, 6, 10]

for score in scores:
    print(f"Score: {score}")
average = sum(scores) / len(scores)
print(f"Average: {average}")
