from src.kiwi_fetch import test_call

def main():
    data = test_call()
    print("OK. Type:", type(data))
    if isinstance(data, dict):
        print("Top-level keys:", list(data.keys())[:20])

if __name__ == "__main__":
    main()
