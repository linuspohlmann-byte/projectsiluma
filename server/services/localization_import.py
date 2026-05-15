import csv

from server.db import upsert_localization_entry


def import_excel_to_database(file_path: str) -> bool:
    """
    Import localization data from CSV file to database.

    Expected CSV format:
    key,language,text
    welcome,en,Welcome
    welcome,de,Willkommen
    ...
    """
    try:
        imported_count = 0

        with open(file_path, "r", encoding="utf-8") as csvfile:
            sample = csvfile.read(1024)
            csvfile.seek(0)
            sniffer = csv.Sniffer()
            delimiter = sniffer.sniff(sample).delimiter

            reader = csv.DictReader(csvfile, delimiter=delimiter)

            for row in reader:
                if not any(row.values()):
                    continue

                key = row.get("key", "").strip()
                language = row.get("language", "").strip()
                text = row.get("text", "").strip()

                if not key or not language or not text:
                    print(f"Skipping row with missing data: {row}")
                    continue

                payload = {
                    "reference_key": key,
                    "language": language,
                    "text": text,
                }
                upsert_localization_entry(payload)
                imported_count += 1

        print(f"Successfully imported {imported_count} localization entries")
        return True

    except Exception as e:
        print(f"Error importing localization data: {e}")
        return False
