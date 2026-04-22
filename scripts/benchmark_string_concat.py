import timeit

def old_way(parts):
    content = ""
    for part in parts:
        if "text" in part:
            content += part["text"]
    return content

def new_way(parts):
    return "".join(part["text"] for part in parts if "text" in part)

# Simulate a message with many parts
parts = [{"text": "some text " + str(i)} for i in range(1000)]

def run_benchmark():
    n = 10000
    t1 = timeit.timeit(lambda: old_way(parts), number=n)
    t2 = timeit.timeit(lambda: new_way(parts), number=n)

    print(f"Old way (+=): {t1:.4f}s")
    print(f"New way (join): {t2:.4f}s")
    print(f"Improvement: {(t1 - t2) / t1 * 100:.2f}%")

if __name__ == "__main__":
    run_benchmark()
