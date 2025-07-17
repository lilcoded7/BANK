from django.contrib import admin
from bank.models import Account, Transaction
# Register your models here.


admin.site.site_header = "Banking Admin Portal"
admin.site.site_title = "Bank Admin"
admin.site.index_title = "Welcome to the Bank Management Dashboard"

@admin.register(Account)
class CampuseAdmin(admin.ModelAdmin):
    list_display = ('owner_name', 'account_number', 'account_type', 'balance')
    list_filter = ('account_number',)
    search_fields = ('account_number',)


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ('customer','amount', 'account', 'transaction_type')
    list_filter = ('transaction_id', 'account__account_number',)
    search_fields = ('transaction_id', 'account__account_number')