from django.contrib import admin
from bank.models import *




# Register all models

admin.site.register(Account)
admin.site.register(Transaction)
admin.site.register(Customer)
admin.site.register(SecurityLog)

