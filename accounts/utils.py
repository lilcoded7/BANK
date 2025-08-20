from django.contrib.auth import get_user_model
from django.template.loader import render_to_string
from django.core.mail import EmailMessage
from django.shortcuts import get_object_or_404




class EmailSender:
    def send_email(self, data):
        email = EmailMessage(
            subject    = data['email_subject'],
            body       = data['email_body'],
            to         = [data['to_email']],
        )
        email.content_subtype = 'html'
        email.send()

    def send_reset_password_code(self, user):
        message = render_to_string('mails/reset_password_code.html', {'user':user})
        data = {
            'email_subject':'Verification Code',
            'email_body': message,
            'to_email':user.email
            }
        self.send_email(data)

    def send_reset_password_success_message(self, user):
        message = render_to_string('mails/reset_pws_success.html', {'user':user})
        data = {
            'email_subject':'Verification Code',
            'email_body': message,
            'to_email':user.email
            }
        self.send_email(data)





        