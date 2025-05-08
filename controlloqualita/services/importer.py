# controlloqualita/services/importer.py

import csv
from controlloqualita.services.quality_report import parse_aaaammgg, parse_ddmmyyyy_hhmmss
from controlloqualita.models import ImportRecord


def import_csv_file(file_path):
    """
    Legge il CSV da file_path e chiama process_row per ogni riga.
    """
    with open(file_path, 'r', encoding='utf-8', newline='') as csvfile:
        reader = csv.DictReader(csvfile, delimiter=';', quotechar='"')
        for row in reader:
            ident = row.get('IdentificativoRichiesta')
            if not ident:
                continue
            # evita duplicati
            if ImportRecord.objects.filter(identificativo_richiesta=ident).exists():
                continue
            # crea il record minimo (modifica se vuoi salvare più campi)
            rec = ImportRecord(
                identificativo_richiesta = ident,
                codice_fiscale_richiesta  = row.get('CodiceFiscaleRichiesta',''),
                codice_fiscale_attuale    = row.get('CodiceFiscaleAttuale',''),
                ragione_sociale_cliente   = row.get('RagioneSocialeCliente',''),
                servizio                  = row.get('Servizio',''),
                data_evasione             = parse_aaaammgg(row.get('DataEvasione','')),
                operatore                 = row.get('Operatore',''),
                raw_data                  = row,
            )
            rec.save()
