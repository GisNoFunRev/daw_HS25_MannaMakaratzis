"""Einrichtung des Loggings für die Ausführung im Notebook.

Warum das ein eigenes Modul ist
-------------------------------
Im Notebook stand logging.basicConfig(...) direkt zwischen den
Funktionsdefinitionen und wurde damit beim Import ausgeführt. Für
Bibliothekscode ist das ein Fehler: Ein importiertes Modul darf den
Root-Logger der Anwendung nicht umkonfigurieren, weil es damit die
Logging-Einstellungen aller anderen Beteiligten überschreibt.

Die Regel lautet deshalb:

* Module holen sich nur einen Logger (logging.getLogger(__name__))
  und konfigurieren nichts.
* Der Aufrufer — hier das Notebook — entscheidet einmalig über Format
  und Level, indem er configure_logging aufruft.
"""

import logging

# Format der Logzeilen. Gegenüber dem Notebook um %(name)s ergänzt:
# Da jedes Modul jetzt seinen eigenen Logger hat, ist am Log ablesbar,
# welcher Verarbeitungsschritt die Meldung erzeugt hat.
LOG_FORMAT = "%(asctime)s - %(levelname)s - %(name)s - %(message)s"


def configure_logging(level: int = logging.INFO) -> None:
    """Richtet das Logging für einen Notebook- oder Skriptlauf ein.

    Ist bewusst idempotent: force=True entfernt zuvor gesetzte Handler,
    bevor der neue installiert wird. Ohne das würde ein erneutes Ausführen
    der Notebook-Zelle jede Logzeile ein weiteres Mal ausgeben, und in
    Jupyter-Umgebungen mit bereits vorhandenem Root-Handler hätte
    basicConfig gar keine Wirkung.

    Args:
        level: Schwelle, ab der Meldungen ausgegeben werden. Standard
            logging.INFO, damit die Bereinigungsschritte im Bericht
            nachvollziehbar sind.
    """
    logging.basicConfig(
        level=level,
        format=LOG_FORMAT,
        handlers=[logging.StreamHandler()],
        force=True,
    )


def get_logger(name: str) -> logging.Logger:
    """Liefert den Logger eines Moduls.

    Dünner Wrapper um logging.getLogger, damit in den Modulen ein
    einheitlicher Aufruf steht. Die Module rufen ihn mit __name__ auf.

    Args:
        name: Modulname, üblicherweise __name__.

    Returns:
        Der zum Modul gehörende Logger.
    """
    return logging.getLogger(name)
