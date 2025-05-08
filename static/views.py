# controlloqualita/views.py


from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.core.files.storage import default_storage
import os
from controlloqualita.models import ImportRecord, ScoringRule
import csv
import datetime
from datetime import timedelta
from django.utils import timezone
from io import BytesIO

from django import forms
from django.http import HttpResponse
import openpyxl
from openpyxl import Workbook
from .services.quality_report import generate_quality_report_from_qs
from django.core.paginator import Paginator
from django.forms import modelformset_factory
#from controlloqualita.models import ScoringRule
from controlloqualita.services.rules import calcola_punteggio_dynamic
from django.contrib import messages
from django.db import transaction
from django.contrib.auth.decorators import user_passes_test

class DashboardFilterForm(forms.Form):
    date_from = forms.DateField(
        required=False,
        input_formats=['%d-%m-%Y'],
        widget=forms.TextInput(attrs={
            'class': 'datepicker',
            'autocomplete': 'off',
            'placeholder': 'GG-MM-YYYY'
        }),
        label="Data evasione dal"
    )
    date_to = forms.DateField(
        required=False,
        input_formats=['%d-%m-%Y'],
        widget=forms.TextInput(attrs={
            'class': 'datepicker',
            'autocomplete': 'off',
            'placeholder': 'GG-MM-YYYY'
        }),
        label="Data evasione al"
    )
    client = forms.MultipleChoiceField(
        required=False,
        widget=forms.SelectMultiple(attrs={'class': 'form-select select2','data-placeholder': 'Cerca cliente…'}),
        label="Cliente"
    )    
    redattore = forms.MultipleChoiceField(
        required=False,
        #widget=forms.SelectMultiple(attrs={'size':5}),
        widget=forms.SelectMultiple(attrs={'class': 'form-select select2','data-placeholder': 'Cerca redattore…'}),
        label="Redattore"
    )

    def __init__(self, *args, **kwargs):
        super(DashboardFilterForm, self).__init__(*args, **kwargs)
        # Recupera i valori distinti per cliente e redattore
        clients = ImportRecord.objects.order_by('ragione_sociale_cliente') \
            .values_list('ragione_sociale_cliente', flat=True).distinct()
        redattori = ImportRecord.objects.order_by('operatore') \
            .values_list('operatore', flat=True).distinct()
        self.fields['client'].choices = [(client, client) for client in clients if client]
        self.fields['redattore'].choices = [(red, red) for red in redattori if red]

@login_required
def export_to_xlsx(request, queryset):
    """
    Genera un file XLSX con i dati contenuti in queryset.
    In questo esempio vengono esportati alcuni campi.
    """
    wb = Workbook()
    ws = wb.active
    ws.title = "Export Dashboard"

    # Intestazioni (modifica in base alle tue necessità)
    headers = [
        'IdentificativoRichiesta',
        'Codice Fiscale',
        'Ragione Sociale Cliente',
        'Servizio',
        'Data Evasione',
        'Redattore',
    ]
    ws.append(headers)

    for record in queryset:
        # Ad esempio, per data evasione formattiamo la data in stringa, se presente.
        data_evasione_str = record.data_evasione.strftime("%Y-%m-%d") if record.data_evasione else ""
        ws.append([
            record.identificativo_richiesta,
            record.codice_fiscale_attuale,
            record.ragione_sociale_cliente,
            record.servizio,
            data_evasione_str,
            record.operatore,
        ])

    # Scriviamo il workbook in un buffer in memoria
    output = BytesIO()
    wb.save(output)
    output.seek(0)

    # Risposta HTTP con l'header per l'attachment XLSX
    response = HttpResponse(
        output,
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    response['Content-Disposition'] = 'attachment; filename="dashboard_export.xlsx"'
    return response

def parse_data_aaaammgg(s):
    # Esempio: "20250121" -> 2025-01-21
    s = s.strip()
    if len(s) != 8:
        return None
    try:
        yyyy = int(s[0:4])
        mm = int(s[4:6])
        dd = int(s[6:8])
        return datetime.date(yyyy, mm, dd)
    except ValueError:
        return None

def parse_data_ddmmyyyy_hhmmss(s):
    # Esempio: "05/02/2025 00:00:00" -> 2025-02-05 (ignora orario)
    s = s.strip()
    if not s:
        return None
    parts = s.split()
    if len(parts) == 0:
        return None
    data_part = parts[0]  # "05/02/2025"
    try:
        gg, mm, yyyy = data_part.split('/')
        gg = int(gg)
        mm = int(mm)
        yyyy = int(yyyy)
        return datetime.date(yyyy, mm, gg)
    except ValueError:
        return None




@login_required
def upload_csv(request):
    if request.method == 'POST':
        csv_file = request.FILES.get('csvfile')  # il nome del campo file nel template
        if csv_file:
            # Salva il CSV in modo temporaneo
            temp_path = default_storage.save('temp.csv', csv_file)
            # Se vuoi l'intero percorso su disco, potresti fare:
            full_path = os.path.join('/data/cqenv/cq_project/media/', temp_path)

            # Qui richiami la tua logica di elaborazione CSV
            # es.: process_csv(full_path)
            process_csv(request, full_path)

            return redirect('controlloqualita:upload_ok')  # rotta definita nel urls.py
    return render(request, 'controlloqualita/upload_form.html')

@login_required
def upload_ok(request):
    return render(request, 'controlloqualita/upload_ok.html')

@login_required
def process_csv(request, file_path):
    """
    Legge il CSV dal percorso file_path e per ogni riga richiama process_csv_row.
    Il CSV è atteso avere una riga di intestazione.
    """
    with open(file_path, 'r', encoding='utf-8', newline='') as csvfile:
        reader = csv.DictReader(csvfile, delimiter=';', quotechar='"')
        for row in reader:
            process_csv_row(request,row)

@login_required
def process_csv_row(request,row):
    ident = row['IdentificativoRichiesta']
    if ImportRecord.objects.filter(identificativo_richiesta=ident).exists():
        return

    rec = ImportRecord(
        identificativo_richiesta=ident,
        codice_fiscale_richiesta=row.get('CodiceFiscaleRichiesta', ''),
        codice_fiscale_attuale =row.get('CodiceFiscaleAttuale', ''),
        ragione_sociale_cliente =row.get('RagioneSocialeCliente', ''),
        servizio                =row.get('Servizio', ''),
        data_evasione           =parse_data_aaaammgg(row.get('DataEvasione','')),
        operatore               =row.get('Operatore',''),
        raw_data                =row,  # salva il dict intero
    )
    rec.save()

@login_required
def process_csv_row_old(row):
    identificativo_richiesta = row['IdentificativoRichiesta']  # Assumendo che row sia un dict mappato dal CSV
    codice_fiscale_richiesta = row['CodiceFiscaleRichiesta']
    codice_fiscale_attuale = row['CodiceFiscaleAttuale']
    
    # gestisco gli importi
    retribuzione_str = row.get('RAL - RETRIBUZIONE LORDA ANNUA EURO', '')
    try:
        ral_retribuzione_annua_lorda = int(retribuzione_str) if retribuzione_str else None
    except ValueError:
        ral_retribuzione_annua_lorda = None  # o gestisci l'errore in maniera appropriata
    importoMensile_str = row.get('IMPORTO MENSILE LORDO EURO', '')
    try:
        importo_mensile_lordo = int(importoMensile_str) if importoMensile_str else None
    except ValueError:
        importo_mensile_lordo = None  # o gestisci l'errore in maniera appropriata
    pensione_mensile_str = row.get('PENSIONE IMPORTO MENSILE LORDO EURO', '')
    try:
        pensione_importo_mensile_lordo = int(pensione_mensile_str) if pensione_mensile_str else None
    except ValueError:
        pensione_importo_mensile_lordo = None  # o gestisci l'errore in maniera appropriata
    
    # trasformo in oggetti le date
    data_inserimento = parse_data_aaaammgg(row.get('DataInserimento', ''))
    data_evasione = parse_data_aaaammgg(row.get('DataEvasione', ''))
    data_scadenza = parse_data_ddmmyyyy_hhmmss(row.get('DataScadenza', ''))
    data_inizio_rapporto_lavoro = parse_data_ddmmyyyy_hhmmss(row.get('DATA_INIZIO_RAPPORTO_LAVORO', ''))
    data_fine_rapporto_lavoro = parse_data_ddmmyyyy_hhmmss(row.get('DATA_FINE_RAPPORTO_LAVORO', ''))
    
    # Se esiste già un record con questo identificativo, scarta il record
    if ImportRecord.objects.filter(identificativo_richiesta=identificativo_richiesta).exists():
        return  # oppure registra un log
    
    # In alternativa, se usi il campo raw_data per conservare tutti i dati:
    record = ImportRecord(
        identificativo_richiesta=identificativo_richiesta,
        codice_fiscale_richiesta=codice_fiscale_richiesta,
        codice_fiscale_attuale=codice_fiscale_attuale,
        
        ral_retribuzione_annua_lorda=ral_retribuzione_annua_lorda,
        importo_mensile_lordo=importo_mensile_lordo,
        pensione_importo_mensile_lordo=pensione_importo_mensile_lordo,
        
        data_inserimento=data_inserimento,
        data_evasione=data_evasione,
        data_scadenza=data_scadenza,
        data_inizio_rapporto_lavoro=data_inizio_rapporto_lavoro,
        data_fine_rapporto_lavoro=data_fine_rapporto_lavoro,
        
        
        identificativo_cliente=row.get('IdentificativoCliente', ''),
        ragione_sociale_cliente=row.get('RagioneSocialeCliente', ''),
        codice_servizio=row.get('CodiceServizio', ''),
        servizio=row.get('Servizio', ''),
        descrizione_servizio=row.get('DescrizioneServizio', ''),
        evasa_operatore=row.get('EvasaOperatore', ''),
        evasa_al_cliente=row.get('EvasaAlCliente', ''),
        operatore_id=row.get('IDOperatore', ''),
        operatore=row.get('Operatore', ''),
        lotto=row.get('Lotto', ''),
        nominativo=row.get('Nominativo', ''),
        cognome=row.get('Cognome', ''),
        nome=row.get('Nome', ''),
        oggetto=row.get('Oggetto', ''),
        idrichiesta=row.get('IDRICHIESTA', ''),
        decesso_flag=row.get('DECESSO_FLAG', ''),
        decesso_data=row.get('DECESSO_DATA', ''),
        telefono=row.get('TELEFONO', ''),
        consensus=row.get('CONSENSUS', ''),
        residenza_new_flag=row.get('RESIDENZA_NEW_FLAG', ''),
        residenza_new_indirizzo=row.get('RESIDENZA_NEW_INDIRIZZO', ''),
        residenza_new_cap=row.get('RESIDENZA_NEW_CAP', ''),
        residenza_new_comune=row.get('RESIDENZA_NEW_COMUNE', ''),
        residenza_new_provincia=row.get('RESIDENZA_NEW_PROVINCIA', ''),
        domicilio_new_flag=row.get('DOMICILIO_NEW_FLAG', ''),
        domicilio_new_indirizzo=row.get('DOMICILIO_NEW_INDIRIZZO', ''),
        domicilio_new_cap=row.get('DOMICILIO_NEW_CAP', ''),
        domicilio_new_comune=row.get('DOMICILIO_NEW_COMUNE', ''),
        domicilio_new_provincia=row.get('DOMICILIO_NEW_PROVINCIA', ''),
        note_residenza=row.get('NOTE_RESIDENZA', ''),
        lavoro_tipologia=row.get('LAVORO_TIPOLOGIA', ''),
        contratto_tipologia=row.get('CONTRATTO_TIPOLOGIA', ''),
        lavoro_subordinato_flag=row.get('LAVORO_SUBORDINATO_FLAG', ''),
        pensione_flag=row.get('PENSIONE_FLAG', ''),
        lavoro_datore_ragione_sociale=row.get('LAVORO_DATORE_RAGIONE_SOCIALE', ''),
        lavoro_datore_codice_fiscale=row.get('LAVORO_DATORE_CODICE_FISCALE', ''),
        lavoro_datore_partita_iva=row.get('LAVORO_DATORE_PARTITA_IVA', ''),
        lavoro_datore_indirizzo=row.get('LAVORO_DATORE_INDIRIZZO', ''),
        lavoro_datore_cap=row.get('LAVORO_DATORE_CAP', ''),
        lavoro_datore_localita=row.get('LAVORO_DATORE_LOCALITA', ''),
        lavoro_datore_provincia=row.get('LAVORO_DATORE_PROVINCIA', ''),
        lavoro_datore_telefono=row.get('LAVORO_DATORE_TELEFONO', ''),
        attivita_lavorativa=row.get("ATTIVITA' LAVORATIVA", ''),
        storico_attivita_lavorativa=row.get("STORICO ATTIVITA' LAVORATIVA", ''),
        lavoro_datore_note=row.get('DATORE DI LAVORO NOTE', ''),
        pensione_ente_ragione_sociale=row.get('PENSIONE_ENTE_RAGIONE_SOCIALE', ''),
        pensione_ente_indirizzo=row.get('PENSIONE_ENTE_INDIRIZZO', ''),
        pensione_ente_cap=row.get('PENSIONE_ENTE_CAP', ''),
        pensione_ente_localita=row.get('PENSIONE_ENTE_LOCALITA', ''),
        pensione_ente_provincia=row.get('PENSIONE_ENTE_PROVINCIA', ''),
        pensione_categoria=row.get('PENSIONE CATEGORIA', ''),
        
        pensione_note=row.get('PENSIONE_NOTE', ''),
        cessione_del_quinto=row.get('CESSIONE DEL QUINTO', ''),
        partecipazioni_societa_flag=row.get('PARTECIPAZIONI_SOCIETA_FLAG (SI/NO)', ''),
        partecipazioni_societa_note=row.get('PARTECIPAZIONI_SOCIETA_NOTE', ''),
        protesti_flag=row.get('PROTESTI_FLAG', ''),
        protesti_dettaglio=row.get('PROTESTI_DETTAGLIO', ''),
        pregiudizievoli_flag=row.get('PREGIUDIZIEVOLI_FLAG', ''),
        pregiudizievoli_dettaglio=row.get('PREGIUDIZIEVOLI_DETTAGLIO', ''),
        rapporti_bancari_postali_flag=row.get('RAPPORTI_BANCARI_POSTALI_FLAG', ''),
        banca_ragione_sociale=row.get('BANCA_RAGIONE_SOCIALE', ''),
        banca_indirizzo=row.get('BANCA_INDIRIZZO', ''),
        banca_cap=row.get('BANCA_CAP', ''),
        banca_localita=row.get('BANCA_LOCALITA', ''),
        banca_provincia=row.get('BANCA_PROVINCIA', ''),
        banca_telefono=row.get('BANCA_TELEFONO', ''),
        banca_coordinate=row.get('BANCA_COORDINATE', ''),
        banca_partita_iva=row.get('BANCA_PARTITA_IVA', ''),
        movimenti_immobiliari_flag=row.get('MOVIMENTI IMMOBILIARI FLAG', ''),
        movimenti_immobiliari=row.get('MOVIMENTI IMMOBILIARI', ''),
        immobili_proprieta_flag=row.get('IMMOBILI_PROPRIETA_FLAG', ''),
        dettaglio_immobili=row.get('DETTAGLIO_IMMOBILI', ''),
        analisi_e_raccomandazioni=row.get('ANALISI E RACCOMANDAZIONI', ''),
        beni_mobili_flag=row.get('BENI_MOBILI_FLAG', ''),
        dettaglio_beni_mobili=row.get('DETTAGLIO_BENI_MOBILI', ''),
        chiamato_eredita_1=row.get("CHIAMATO ALL'EREDITA' 1", ''),
        comune_nascita_1=row.get('COMUNE_NASCITA1', ''),
        provincia_1=row.get('PROVINCIA', ''),
        data_1=row.get('DATA1', ''),
        codice_fiscale_1=row.get('CODICE_FISCALE1', ''),
        relazione_1=row.get('RELAZIONE1', ''),
        note_1=row.get('NOTE1', ''),
        chiamato_eredita_2=row.get("CHIAMATO ALL'EREDITA' 2", ''),
        comune_nascita_2=row.get('COMUNE_NASCITA2', ''),
        provincia_2=row.get('PROVINCIA2', ''),
        data_2=row.get('DATA2', ''),
        codice_fiscale_2=row.get('CODICE_FISCALE2', ''),
        relazione_2=row.get('RELAZIONE2', ''),
        note_2=row.get('NOTE2', ''),
        chiamato_eredita_3=row.get("CHIAMATO ALL'EREDITA' 3", ''),
        comune_nascita_3=row.get('COMUNE_NASCITA3', ''),
        provincia_3=row.get('PROVINCIA3', ''),
        data_3=row.get('DATA3', ''),
        codice_fiscale_3=row.get('CODICE_FISCALE3', ''),
        relazione_3=row.get('RELAZIONE3', ''),
        note_3=row.get('NOTE3', ''),
        chiamato_eredita_4=row.get("CHIAMATO ALL'EREDITA' 4", ''),
        comune_nascita_4=row.get('COMUNE_NASCITA4', ''),
        provincia_4=row.get('PROVINCIA4', ''),
        data_4=row.get('DATA4', ''),
        codice_fiscale_4=row.get('CODICE_FISCALE4', ''),
        relazione_4=row.get('RELAZIONE4', ''),
        note_4=row.get('NOTE4', ''),
        chiamato_eredita_5=row.get("CHIAMATO ALL'EREDITA' 5", ''),
        comune_nascita_5=row.get('COMUNE_NASCITA5', ''),
        provincia_5=row.get('PROVINCIA5', ''),
        data_5=row.get('DATA5', ''),
        codice_fiscale_5=row.get('CODICE_FISCALE5', ''),
        relazione_5=row.get('RELAZIONE5', ''),
        note_5=row.get('NOTE5', ''),
        chiamato_eredita_6=row.get("CHIAMATO ALL'EREDITA' 6", ''),
        comune_nascita_6=row.get('COMUNE_NASCITA6', ''),
        provincia_6=row.get('PROVINCIA6', ''),
        data_6=row.get('DATA6', ''),
        codice_fiscale_6=row.get('CODICE_FISCALE6', ''),
        relazione_6=row.get('RELAZIONE6', ''),
        note_6=row.get('NOTE6', ''),
        esito_accettazione_eredita=row.get('ESITO_ACCETTAZIONE_EREDITA', ''),
        dettaglio_immobili_de_cuius=row.get('DETTAGLIO_IMMOBILI_DE_CUIUS', ''),
        altre_notizie=row.get('ALTRE_NOTIZIE', ''),
        note_interne=row.get('NOTE_INTERNE', ''),
        gruppo=row.get('Gruppo', ''),
        note_reddito_lavoro=row.get('NOTE_REDDITO_LAVORO', ''),
        note_reddito_pensione=row.get('NOTE_REDDITO_PENSIONE', ''),
        
        
    )
    record.save()
    
@login_required
def dashboard(request):
    """
    Vista che mostra i dati filtrati dal CSV. 
    L’utente può filtrare per range di date (campo data evasione), per cliente e per redattore.
    Se viene passato il parametro export=xlsx, viene esportato il risultato in XLSX.
    Se non sono forniti filtri, per default vengono caricati i record del giorno precedente.
    """
    # Usa GET per i filtri; puoi eventualmente usare POST se preferisci.
    form = DashboardFilterForm(request.GET or None)
    qs = ImportRecord.objects.all()
    
    
    # Se viene premuto il bottone “Scarica Report Qualità”
    if request.GET.get('export_quality') == '1':
        excel_io = generate_quality_report_from_qs(qs)
        resp = HttpResponse(
            excel_io.getvalue(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        resp['Content-Disposition'] = 'attachment; filename="report_qualita.xlsx"'
        return resp
    
    
    
    
    # Se il form è valido, applica i filtri (logica AND)
    if form.is_valid():
        date_from = form.cleaned_data.get('date_from')
        date_to = form.cleaned_data.get('date_to')
        clients = form.cleaned_data.get('client')
        redattori = form.cleaned_data.get('redattore')

        if date_from:
            qs = qs.filter(data_evasione__gte=date_from)
        if date_to:
            qs = qs.filter(data_evasione__lte=date_to)
        if clients:
            qs = qs.filter(ragione_sociale_cliente__in=clients)
        if redattori:
            qs = qs.filter(operatore__in=redattori)
    else:
        # Se il form non è valido, si può decidere di non mostrare risultati
        qs = qs.none()
    
    
    # Se non sono stati inviati filtri (cioè la querystring è vuota), mostra i record del giorno precedente
    if not request.GET:
        yesterday = timezone.now().date() - datetime.timedelta(days=1)
        qs = qs.filter(data_evasione=yesterday)

    # Se viene richiesto l'export XLSX (passando ad esempio ?export=xlsx nella query string)
    if request.GET.get('export') == 'xlsx':
        return export_to_xlsx(request, qs)

    context = {
        'form': form,
        'records': qs,
    }
    
    # --- PAGINAZIONE ---
    # numero di elementi per pagina (da GET o default a 20)
    try:
        per_page = int(request.GET.get('page_size', 50))
    except ValueError:
        per_page = 50

    paginator = Paginator(qs, per_page)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    # opzioni per quanti elementi mostrare a pagina
    page_size_options = [10, 20, 50, 100]

    context = {
        'form': form,
        # records diventa page_obj
        'records': page_obj,
        'paginator': paginator,
        'page_obj': page_obj,
        'per_page': per_page,
        # totale elementi
        'total_count': paginator.count,
        'page_size_options': page_size_options,
    }    
    
    return render(request, 'controlloqualita/dashboard.html', context)    

@login_required
def set_esiti(request):
    if not request.user.is_staff:
        return redirect('dashboard')

    # recupera tutte le categorie possibili
    category_choices = ScoringRule.CATEGORY_CHOICES

    # leggi il filtro dalla querystring
    selected_cat = request.GET.get('category', '')

    # base queryset: tutte le regole, oppure solo quelle della categoria selezionata
    qs = ScoringRule.objects.all()
    if selected_cat:
        qs = qs.filter(category=selected_cat)

    RuleFormSet = modelformset_factory(
        ScoringRule,
        fields=('category','expression','score_letter','score_value'),
        extra=0,        # nessuna riga vuota
        can_delete=True # checkbox per eliminare
    )

    if request.method == 'POST':
        formset = RuleFormSet(request.POST, queryset=qs)
        if formset.is_valid():
            formset.save()
            return redirect('set_esiti')  # rimane su quella pagina
    else:
        formset = RuleFormSet(queryset=qs)

    return render(request, 'controlloqualita/set_esiti.html', {
        'formset': formset,
        'category_choices': category_choices,
        'selected_cat': selected_cat,
    })

@user_passes_test(lambda u: u.is_staff)
@login_required
def delete_filtered(request):
    if request.method != "POST":
        return redirect('controlloqualita:dashboard')

    form = DashboardFilterForm(request.POST)     # <-- POST con hidden copiati
    qs   = ImportRecord.objects.all()

    if form.is_valid():
        cd = form.cleaned_data
        if cd['date_from']:
            qs = qs.filter(data_evasione__gte=cd['date_from'])
        if cd['date_to']:
            qs = qs.filter(data_evasione__lte=cd['date_to'])
        if cd['client']:
            qs = qs.filter(ragione_sociale_cliente__in=cd['client'])
        if cd['redattore']:
            qs = qs.filter(operatore__in=cd['redattore'])
    else:
        messages.error(request, "Filtri non validi – nessun record eliminato.")
        return redirect('controlloqualita:dashboard')

    deleted, _ = qs.delete()
    messages.success(request, f"Eliminati {deleted} record.")
    return redirect('controlloqualita:dashboard')
    
    