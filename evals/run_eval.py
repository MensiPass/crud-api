import json

import requests


API_URL = "http://localhost:8001/triage"


def main():
    with open("evals/cases.json", encoding="utf-8") as file:
        cases = json.load(file)

    correct = 0
    failures = []

    for case in cases:
        response = requests.post(
            API_URL,
            json={"text": case["text"]},
            timeout=40,
        )

        if response.status_code != 200:
            failures.append(
                {
                    "id": case["id"],
                    "error": response.text,
                }
            )
            continue

        result = response.json()

        if result["category"] == case["expected_category"]:
            correct += 1
        else:
            failures.append(
                {
                    "id": case["id"],
                    "expected": case["expected_category"],
                    "actual": result["category"],
                }
            )

    total = len(cases)
    score = correct / total * 100

    print()
    print(f"Score: {correct}/{total} ({score:.1f}%)")

    if failures:
        print("\nFailures:")

        for failure in failures:
            print(failure)


if __name__ == "__main__":
    main()