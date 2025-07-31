from django.contrib import admin
from bank.models import *


# Register all models

admin.site.register(Account)
admin.site.register(Transaction)

admin.site.register(SecurityLog)
admin.site.register(Investment)
admin.site.register(TradePosition)
admin.site.register(InvestmentPackage)


admin.site.register(FingerPrint)
