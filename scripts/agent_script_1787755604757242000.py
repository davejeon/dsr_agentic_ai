
# Print the first 20 Fibonacci numbers
fib = [0, 1]
for i in range(2, 20):
    fib.append(fib[-1] + fib[-2])

print("First 20 Fibonacci numbers:")
for i, num in enumerate(fib):
    print(f"F({i}) = {num}")
