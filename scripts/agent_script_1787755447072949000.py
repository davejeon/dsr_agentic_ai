fib = [0, 1]
for i in range(2, 20):
    fib.append(fib[-1] + fib[-2])

for i, n in enumerate(fib, start=1):
    print(f"{i}: {n}")
