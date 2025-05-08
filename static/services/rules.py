# controlloqualita/services/rules.py
import ast

from controlloqualita.models import ScoringRule

class UnsafeExpression(Exception):
    pass

def eval_rule_expression(expr, context):
    """
    Valuta un'espressione booleana in modo 'safe':
    - parse AST, consentendo solo booleani, comparazioni, variable names, and/or/not
    """
    node = ast.parse(expr, mode='eval')

    # ricorriamo sull'albero per verificare che non ci siano chiamate, attributi, import ecc.
    for sub in ast.walk(node):
        if isinstance(sub, (ast.Call, ast.Attribute, ast.Import, ast.ImportFrom)):
            raise UnsafeExpression(f"Espressione non sicura: {expr}")

    code = compile(node, '<string>', 'eval')
    return bool(eval(code, {}, context))


def calcola_punteggio_dynamic(detail):
    """
    Cerca tutte le regole per la categoria detail['categoria'],
    valuta l'espressione in un context di variabili, ritorna
    la prima corrispondenza.
    """
    cat = detail['categoria']
    # prepara il context
    ctx = {
        'df': detail['dettagli']['decesso_flag'] == 'SI',
        'lav': bool(detail['dettagli']['posto_lavoro']),
        'pen': bool(detail['dettagli']['pensione']),
        'ban': bool(detail['dettagli']['banca']),
        'tel': bool(detail['dettagli']['telefono']),
        'note': detail['dettagli']['note_interne'].lower(),
        'erd': bool(detail['dettagli']['erede']),
        'res': bool(detail['dettagli']['residenza_indirizzo']),
        'contattato': 'contattato' in detail['dettagli']['note_interne'].lower()
    }

    # recupera le regole ordinate (in admin potrai riordinare, oppure aggiungi un campo 'priority')
    rules = ScoringRule.objects.filter(category=cat).order_by('id')
    for rule in rules:
        try:
            if eval_rule_expression(rule.expression, ctx):
                return rule.score_letter, rule.score_value
        except UnsafeExpression:
            continue

    # fallback
    return ('N2', 3)
