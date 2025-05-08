# controlloqualita/models.py

from django.db import models

class ImportRecord(models.Model):
    # PK surrogato (id), + chiave univoca
    identificativo_richiesta = models.CharField(
        max_length=100,
        unique=True,
        help_text="Codice univoco della richiesta importata."
    )

    # Minimo di campi “fissi” per filtrare e riportare:
    codice_fiscale_richiesta = models.CharField(max_length=16, db_index=True)
    codice_fiscale_attuale  = models.CharField(max_length=16, db_index=True)
    ragione_sociale_cliente = models.CharField(max_length=255, blank=True, null=True)
    servizio                = models.CharField(max_length=255, blank=True, null=True)
    data_evasione           = models.DateField(blank=True, null=True)
    operatore               = models.CharField(max_length=100, blank=True, null=True)

    # E infine TUTTO il resto del CSV in un solo JSONField
    raw_data = models.JSONField(
        blank=True, null=True,
        help_text="Tutti i campi grezzi del CSV in JSON, per future estensioni."
    )
    # Aggiungiamo un timestamp per quando il record viene creato (utile per audit)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.identificativo_richiesta} – {self.codice_fiscale_attuale}"
        
    # --- helper usato dal KPI live ---------------------------------
    def build_det(self):
        """Restituisce il dict 'dettagli' usato da calcola_punteggio_dynamic."""
        rd = self.raw_data or {}
        return {
            "decesso_flag"       : rd.get('DECESSO_FLAG', ''),
            "posto_lavoro"       : bool(rd.get('LAVORO_DATORE_RAGIONE_SOCIALE', '').strip()),
            "pensione"           : bool(rd.get('PENSIONE_ENTE_RAGIONE_SOCIALE',  '').strip()),
            "banca"              : bool(rd.get('BANCA_RAGIONE_SOCIALE',           '').strip()),
            "telefono"           : rd.get('TELEFONO', ''),
            "note_interne"       : rd.get('NOTE_INTERNE', ''),
            "erede"              : rd.get("CHIAMATO ALL'EREDITA' 1", ''),
            "residenza_indirizzo": rd.get('RESIDENZA_NEW_INDIRIZZO', ''),
        }        
        

class ScoringRule(models.Model):
    CATEGORY_CHOICES = [
        ('DOSSIER_BACC','Dossier BACC'),
        ('DOSSIER_PL','Dossier PL'),
        ('EREDI','Eredi'),
        ('RINTRACCI','Rintracci'),
    ]
    category     = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    # qui salviamo un'espressione Python "sicura"
    expression   = models.TextField(
        blank=True,
        null=True,
        default="False",
        help_text="Espressione Python su df,lav,pen,ban,tel,note,erd,res. "
                  "Esempio: \"df=='SI' or (lav and pen and ban)\""
    )    
    
    
    
    
    score_letter = models.CharField(max_length=2)
    score_value  = models.IntegerField()

    class Meta:
        unique_together = ('category','expression')
        ordering = ('category',)

    def __str__(self):
        return f"{self.category}: {self.expression} → {self.score_letter}/{self.score_value}"
        