from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import (
    User,
    Account,
    DigitalAssetAccount,
    Transaction,
    SmartContract,
    SecurityLog,
    AIChatSession,
    AIChatMessage
)

# Custom User Admin
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'phone_number', 'first_name', 'last_name', 'is_staff', 'is_biometric_enabled')
    list_filter = ('is_staff', 'is_superuser', 'is_active', 'is_biometric_enabled', 'gender')
    search_fields = ('username', 'first_name', 'last_name', 'email', 'phone_number', 'national_id')
    ordering = ('-date_joined',)
    
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Personal Info', {'fields': ('first_name', 'last_name', 'email', 'phone_number', 
                                    'gender', 'date_of_birth', 'national_id', 'gh_card_number')}),
        ('Biometric Info', {'fields': ('biometric_data', 'voice_print', 'is_biometric_enabled', 
                                     'last_biometric_update')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 
                                   'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'email', 'phone_number', 'password1', 'password2'),
        }),
    )

# Account Admin
class AccountAdmin(admin.ModelAdmin):
    list_display = ('account_number', 'user', 'account_type', 'balance', 'currency', 'status', 'date_opened')
    list_filter = ('account_type', 'status', 'currency', 'is_interoperable', 'mobile_money_linked')
    search_fields = ('account_number', 'user__username', 'user__first_name', 'user__last_name', 'bvn')
    raw_id_fields = ('user',)
    readonly_fields = ('date_opened', 'last_activity')
    list_per_page = 20

# Digital Asset Account Admin
class DigitalAssetAccountAdmin(admin.ModelAdmin):
    list_display = ('wallet_address_short', 'user', 'asset_type', 'balance', 'equivalent_ghs', 'is_active')
    list_filter = ('asset_type', 'is_active', 'blockchain')
    search_fields = ('wallet_address', 'user__username', 'account__account_number')
    raw_id_fields = ('user', 'account')
    
    def wallet_address_short(self, obj):
        return f"{obj.wallet_address[:6]}...{obj.wallet_address[-4:]}"
    wallet_address_short.short_description = 'Wallet Address'

# Transaction Admin
class TransactionAdmin(admin.ModelAdmin):
    list_display = ('transaction_id_short', 'transaction_type', 'amount', 'currency', 
                   'sender_account', 'status', 'timestamp')
    list_filter = ('transaction_type', 'status', 'currency', 'is_interoperable', 'biometric_verified')
    search_fields = ('transaction_id', 'sender_account__account_number', 
                    'recipient_account__account_number', 'recipient_number')
    raw_id_fields = ('sender_account', 'recipient_account')
    readonly_fields = ('timestamp', 'completed_at')
    date_hierarchy = 'timestamp'
    list_per_page = 50
    
    def transaction_id_short(self, obj):
        return f"{obj.transaction_id[:6]}...{obj.transaction_id[-4:]}"
    transaction_id_short.short_description = 'Transaction ID'

# Smart Contract Admin
class SmartContractAdmin(admin.ModelAdmin):
    list_display = ('contract_id_short', 'contract_type', 'creator', 'status', 'created_at')
    list_filter = ('contract_type', 'status', 'is_self_executing')
    search_fields = ('contract_id', 'creator__username', 'terms')
    filter_horizontal = ('parties',)
    readonly_fields = ('created_at', 'activated_at', 'executed_at')
    
    def contract_id_short(self, obj):
        return f"{obj.contract_id[:6]}...{obj.contract_id[-4:]}"
    contract_id_short.short_description = 'Contract ID'

# Security Log Admin
class SecurityLogAdmin(admin.ModelAdmin):
    list_display = ('user', 'event_type', 'ip_address', 'is_suspicious', 'timestamp')
    list_filter = ('event_type', 'is_suspicious')
    search_fields = ('user__username', 'ip_address', 'location')
    readonly_fields = ('timestamp',)
    date_hierarchy = 'timestamp'
    list_per_page = 100

# AI Chat Session Admin
class AIChatMessageInline(admin.TabularInline):
    model = AIChatMessage
    extra = 0
    readonly_fields = ('timestamp',)
    fields = ('message_type', 'content', 'timestamp')

class AIChatSessionAdmin(admin.ModelAdmin):
    list_display = ('session_id_short', 'user', 'started_at', 'last_activity', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('session_id', 'user__username')
    readonly_fields = ('started_at', 'last_activity')
    inlines = [AIChatMessageInline]
    
    def session_id_short(self, obj):
        return f"{obj.session_id[:6]}...{obj.session_id[-4:]}"
    session_id_short.short_description = 'Session ID'

# AI Chat Message Admin
class AIChatMessageAdmin(admin.ModelAdmin):
    list_display = ('session', 'message_type', 'content_short', 'timestamp')
    list_filter = ('message_type',)
    search_fields = ('content', 'session__session_id')
    readonly_fields = ('timestamp',)
    
    def content_short(self, obj):
        return obj.content[:50] + '...' if len(obj.content) > 50 else obj.content
    content_short.short_description = 'Content'

# Register all models
admin.site.register(User, CustomUserAdmin)
admin.site.register(Account, AccountAdmin)
admin.site.register(DigitalAssetAccount, DigitalAssetAccountAdmin)
admin.site.register(Transaction, TransactionAdmin)
admin.site.register(SmartContract, SmartContractAdmin)
admin.site.register(SecurityLog, SecurityLogAdmin)
admin.site.register(AIChatSession, AIChatSessionAdmin)
admin.site.register(AIChatMessage, AIChatMessageAdmin)