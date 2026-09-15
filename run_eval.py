import json

import requests


API_URL = "http://localhost:8001/triage"


def main():
    with open("evals/cases.json", "r", encoding="utf-8") as file:
        cases = json.load(file)

    matches = 0
    failures = []

    for index, case in enumerate(cases, start=1):
        response = requests.post(
            API_URL,
            json={"text": case["text"]},
            timeout=60,
        )

        if response.status_code != 200:
            failures.append(
                {
                    "case": index,
                    "expected": case["category"],
                    "status": response.status_code,
                }
            )
            continue

        result = response.json()

        if result["category"] == case["category"]:
            matches += 1
        else:
            failures.append(
                {
                    "case": index,
                    "expected": case["category"],
                    "actual": result["category"],
                }
            )

    total = len(cases)
    percentage = (matches / total) * 100

    print(f"Matches: {matches}/{total}")
    print(f"Category accuracy: {percentage:.1f}%")

    if failures:
        print("\nFailures:")

        for failure in failures:
            print(failure)
    else:
        print("\nFailures: none")


if __name__ == "__main__":
    main()