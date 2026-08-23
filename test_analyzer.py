import json
from pathlib import Path

from analyzer import analyse_dataset, parse_dataset

BASE = Path(__file__).parent

SAMPLES = {
    "sample.csv": b"id,label,text,value\n1,yes,Bonjour le monde,10\n2,no,Hello world,12\n2,no,Hello world,12\n3,yes,,999\n4,,Test sample,11\n",
    "sample.json": json.dumps([
        {"id": 1, "label": "A", "text": "Bonjour les donnees", "value": 10},
        {"id": 2, "label": "B", "text": "The data is ready", "value": 12},
        {"id": 3, "label": "A", "text": "", "value": 11},
    ]).encode(),
    "sample.jsonl": b'{"id": 1, "label": "A", "text": "Bonjour"}\n{"id": 2, "label": "B", "text": "Hello"}\n',
    "sample.txt": "Bonjour le monde\nThe data is ready\nUne autre ligne\n".encode(),
}


def main():
    for filename, data in SAMPLES.items():
        parsed = parse_dataset(filename, data)
        report = analyse_dataset(parsed)
        assert report["dataset"]["rows"] > 0, filename
        assert 0 <= report["dfs"]["score"] <= 100, filename
        assert set(report["dfs"]["components"]) == {"quality", "coverage", "diversity", "rare_cases", "consistency", "integrity"}, filename
        assert report["provenance"]["simulated"] is False, filename
        assert report["provenance"]["source"] == "uploaded_file", filename
        print(filename, parsed.format, report["dfs"]["score"])

    parsed = parse_dataset("sample.csv", SAMPLES["sample.csv"])
    report = analyse_dataset(parsed)
    assert report["quality"]["duplicate_rows"] == 1
    assert report["quality"]["missing_cells"] > 0
    assert report["quality"]["outlier_values"] > 0
    assert report["integrity"]["suspicious_count"] > 0

    changed = SAMPLES["sample.csv"].replace(b"4,,Test sample,11", b"4,yes,Test sample,11")
    changed_report = analyse_dataset(parse_dataset("sample.csv", changed))
    assert changed_report["dfs"]["score"] != report["dfs"]["score"], "Le score doit dépendre des valeurs importées."
    assert report["provenance"]["calculation_note"].startswith("Toutes les métriques")
    print("metric assertions: ok")


if __name__ == "__main__":
    main()
