from pathlib import Path

from services.preprocessing import preprocess_csv

INPUT = Path(r"F:\RSV\wastewater_aggregate(in).csv")
OUTPUT = Path(__file__).resolve().parent / "outputs" / "weekly_wastewater.csv"


def main() -> None:
    result = preprocess_csv(
        file_bytes=INPUT.read_bytes(),
        filename=INPUT.name,
        data_type="wastewater",
        min_location_confidence=0.55,
        ontario_only=True,
    )

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(result["weekly_csv"], encoding="utf-8")

    print(f"Original rows: {result['original_rows']}")
    print(f"Ontario matched rows: {result['ontario_rows']}")
    print(f"Weekly rows: {result['weekly_rows']}")
    print(f"Frequency: {result['frequency_detection']}")
    print(f"Rule: {result['aggregation_rule']}")
    print("Top matched locations:")
    for row in result["location_summary"][:10]:
        print(f"  {row['matched_city']} | {row['matched_region']} -> {row['rows']}")
    print(f"Saved: {OUTPUT}")


if __name__ == "__main__":
    main()
