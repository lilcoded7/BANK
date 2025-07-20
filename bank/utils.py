
from datetime import datetime, timedelta
import uuid


def generate_transaction_id():
    return f"TX{datetime.now().strftime('%Y%m%d')}{uuid.uuid4().hex[:8].upper()}"

def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    return x_forwarded_for.split(',')[0] if x_forwarded_for else request.META.get('REMOTE_ADDR')

def get_device_info(request):
    # Simplified - in real implementation would gather more device details
    return {
        'user_agent': request.META.get('HTTP_USER_AGENT'),
        'device': request.user_agent.device.family if hasattr(request, 'user_agent') else 'Unknown'
    }

def get_geolocation(request):
    # Simplified - would use IP geolocation service in real implementation
    return "Ghana"  # Default for this implementation

def verify_biometric(user, biometric_data):
    # Simplified - would verify against stored biometric template in real implementation
    return True  # Always return true for this example