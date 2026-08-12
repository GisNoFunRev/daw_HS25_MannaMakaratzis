"""Kommandozeilen-Einstieg: python -m running_data

Die Pipeline ohne Notebook und ohne Python-Kenntnisse ausführbar zu machen
ist der Sinn dieses Moduls. Ein einzelner Befehl liest die Rohexporte und
schreibt den bereinigten Datensatz.

    python -m running_data
    python -m running_data --output ergebnisse/
    python -m running_data --garmin "daten/garmin/*/Activities.csv"

Hier — und nur hier — wird das Logging eingerichtet: Die Kommandozeile ist
die Anwendung, die Module sind Bibliothek (siehe running_data.logging_setup).
"""

import argparse
import logging
import sys
from pathlib import Path

from .logging_setup import configure_logging
from .paths import APPLE_GLOB, GARMIN_GLOB, PROCESSED_DIR
from .pipeline.run import run_pipeline


def build_parser() -> argparse.ArgumentParser:
    """Baut den Argumentparser.

    Als eigene Funktion, damit die Argumente im Test geprüft werden können,
    ohne die Pipeline auszuführen.

    Returns:
        Der fertig konfigurierte Parser.
    """
    parser = argparse.ArgumentParser(
        prog="python -m running_data",
        description=(
            "Liest die Garmin- und Apple-Rohexporte, bereinigt sie und "
            "schreibt den kombinierten Datensatz als Parquet und CSV."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--garmin",
        default=GARMIN_GLOB,
        metavar="MUSTER",
        help="Glob-Muster der Garmin-CSV-Exporte",
    )
    parser.add_argument(
        "--apple",
        default=APPLE_GLOB,
        metavar="MUSTER",
        help="Glob-Muster der Apple-XML-Exporte",
    )
    parser.add_argument(
        "--output",
        default=str(PROCESSED_DIR),
        metavar="ORDNER",
        help="Zielordner für die Ausgabedateien",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Alles berechnen, aber nichts schreiben",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Nur Warnungen und Fehler protokollieren",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Führt die Pipeline mit den Argumenten der Kommandozeile aus.

    Args:
        argv: Argumentliste. None verwendet sys.argv.

    Returns:
        0 bei Erfolg, 1 wenn keine Daten gefunden wurden.
    """
    args = build_parser().parse_args(argv)
    configure_logging(logging.WARNING if args.quiet else logging.INFO)

    try:
        result = run_pipeline(
            garmin_path=args.garmin,
            apple_path=args.apple,
            output_dir=None if args.dry_run else Path(args.output),
        )
    except ValueError as error:
        # Der häufigste Fall ist ein Pfad, der auf nichts passt. Dafür ist
        # ein Traceback die falsche Antwort.
        print(f"Fehler: {error}", file=sys.stderr)
        return 1

    for source, summary in result.summaries.items():
        print(f"{source + ':':8s} {summary['final_rows']:3d} Laeufe bereinigt")

    print(f"Kombiniert: {len(result.data)} Zeilen, {result.data.shape[1]} Spalten")

    if result.outputs:
        print("Geschrieben:")
        for kind, path in result.outputs.items():
            print(f"  {kind:7s}  {path}")
    else:
        print("Nichts geschrieben (--dry-run)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
