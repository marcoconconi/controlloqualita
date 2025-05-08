from django.contrib import admin
from .models import ScoringRule

# Register your models here.
from controlloqualita.models import *
admin.site.register(ImportRecord) 
#admin.site.register(ScoringRule) 

#@admin.register(ScoringRule)
#class ScoringRuleAdmin(admin.ModelAdmin):
#    list_display = ('category','condition','score_letter','score_value')
#    list_filter = ('category',)
@admin.register(ScoringRule)
class ScoringRuleAdmin(admin.ModelAdmin):
    list_display = ('category','expression','score_letter','score_value')
    list_filter  = ('category',)
    ordering     = ('category','id')