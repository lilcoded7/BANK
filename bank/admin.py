# admin.py
from django.contrib import admin
from django import forms
from .models import (
    Account, InvestmentPackage, Investment, 
    TradePosition, Transaction, SecurityLog,
    FingerPrint, PrestigeSettings
)

class PrestigeSettingsForm(forms.ModelForm):
    class Meta:
        model = PrestigeSettings
        fields = '__all__'
        widgets = {
            'deposit_btc_address': forms.TextInput(attrs={'size': 50}),
            'deposit_eth_address': forms.TextInput(attrs={'size': 50}),
            'deposit_usdt_address': forms.TextInput(attrs={'size': 50}),
        }

@admin.register(PrestigeSettings)
class PrestigeSettingsAdmin(admin.ModelAdmin):
    form = PrestigeSettingsForm
    list_display = ('trading_enabled', 'min_trade_amount', 'max_leverage')
    fieldsets = (
        ('Trading Settings', {
            'fields': ('trading_enabled', 'min_trade_amount', 'max_leverage')
        }),
        ('Deposit Addresses', {
            'fields': ('deposit_btc_address', 'deposit_eth_address', 'deposit_usdt_address')
        }),
    )
    
    def has_add_permission(self, request):
        # Only allow one instance to exist
        return not PrestigeSettings.objects.exists()

@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = ('account_number', 'customer', 'account_type', 'balance', 'status')
    list_filter = ('account_type', 'status')
    search_fields = ('account_number', 'customer__username', 'customer__email')
    readonly_fields = ('account_number', 'date_opened')
    fieldsets = (
        (None, {
            'fields': ('customer', 'account_type', 'balance', 'currency', 'status')
        }),
        ('Details', {
            'fields': ('account_number', 'date_opened', 'is_interoperable')
        }),
    )

class InvestmentPackageAdmin(admin.ModelAdmin):
    list_display = ('name', 'min_amount', 'max_amount', 'duration_days', 'roi_percentage')
    list_editable = ('min_amount', 'max_amount', 'duration_days', 'roi_percentage')
    search_fields = ('name',)
    prepopulated_fields = {'features': []}  # Disable prepopulation

@admin.register(Investment)
class InvestmentAdmin(admin.ModelAdmin):
    list_display = ('account', 'package', 'amount', 'start_date', 'end_date', 'status')
    list_filter = ('status', 'package')
    search_fields = ('account__account_number', 'account__customer__username')
    readonly_fields = ('expected_return',)
    date_hierarchy = 'start_date'
    fieldsets = (
        (None, {
            'fields': ('account', 'package', 'amount', 'status')
        }),
        ('Dates', {
            'fields': ('start_date', 'end_date')
        }),
        ('Returns', {
            'fields': ('expected_return', 'actual_return')
        }),
    )

@admin.register(TradePosition)
class TradePositionAdmin(admin.ModelAdmin):
    list_display = ('symbol', 'user', 'trade_type', 'amount', 'entry_price', 'current_price', 'profit_loss', 'status')
    list_filter = ('status', 'trade_type', 'symbol')
    search_fields = ('symbol', 'user__username')
    readonly_fields = ('opened_at', 'closed_at', 'profit_loss')
    date_hierarchy = 'opened_at'
    fieldsets = (
        ('Position Details', {
            'fields': ('user', 'symbol', 'trade_type', 'amount', 'leverage')
        }),
        ('Pricing', {
            'fields': ('entry_price', 'current_price', 'take_profit', 'stop_loss')
        }),
        ('Status', {
            'fields': ('status', 'profit_loss', 'opened_at', 'closed_at')
        }),
    )

@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ('transaction_id', 'transaction_type', 'amount', 'currency', 'status', 'timestamp')
    list_filter = ('transaction_type', 'status', 'currency')
    search_fields = ('transaction_id', 'account__account_number')
    readonly_fields = ('timestamp',)
    date_hierarchy = 'timestamp'
    fieldsets = (
        ('Transaction Details', {
            'fields': ('transaction_id', 'transaction_type', 'amount', 'currency', 'status')
        }),
        ('Accounts', {
            'fields': ('account', 'sender_account', 'recipient_account')
        }),
        ('Metadata', {
            'fields': ('description', 'metadata', 'timestamp')
        }),
        ('Related Objects', {
            'fields': ('investment', 'trade_position')
        }),
    )

@admin.register(SecurityLog)
class SecurityLogAdmin(admin.ModelAdmin):
    list_display = ('user', 'event_type', 'ip_address', 'timestamp')
    list_filter = ('event_type',)
    search_fields = ('user__username', 'ip_address')
    readonly_fields = ('timestamp',)
    date_hierarchy = 'timestamp'
    fieldsets = (
        (None, {
            'fields': ('user', 'event_type', 'ip_address')
        }),
        ('Details', {
            'fields': ('device_info', 'details', 'timestamp')
        }),
    )

@admin.register(FingerPrint)
class FingerPrintAdmin(admin.ModelAdmin):
    list_display = ('user', 'created_at')
    search_fields = ('user__username',)
    readonly_fields = ('created_at',)
    fieldsets = (
        (None, {
            'fields': ('user',)
        }),
        ('Biometric Data', {
            'fields': ('template_data', 'image')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )

admin.site.register(InvestmentPackage, InvestmentPackageAdmin)