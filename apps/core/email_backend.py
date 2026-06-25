import logging
import requests
from django.core.mail.backends.base import BaseEmailBackend
from django.conf import settings

logger = logging.getLogger(__name__)


class ResendEmailBackend(BaseEmailBackend):
	"""
	Envia emails via Resend HTTP API (HTTPS 443).
	Substitui o backend SMTP — sem dependência de porta 465/587.
	"""

	API_URL = "https://api.resend.com/emails"

	def __init__(self, fail_silently=False, **kwargs):
		super().__init__(fail_silently=fail_silently, **kwargs)
		self.api_key = getattr(settings, 'RESEND_API_KEY', '')

	def send_messages(self, email_messages):
		if not self.api_key:
			if not self.fail_silently:
				raise ValueError("RESEND_API_KEY não configurada.")
			return 0

		sent = 0
		for message in email_messages:
			try:
				self._send(message)
				sent += 1
			except Exception as e:
				logger.error(f"[ResendBackend] Falha ao enviar para {message.to}: {e}")
				if not self.fail_silently:
					raise
		return sent

	def _send(self, message):
		html_body = None
		text_body = message.body

		for content, mimetype in getattr(message, 'alternatives', []):
			if mimetype == 'text/html':
				html_body = content
				break

		payload = {
			"from": message.from_email or settings.DEFAULT_FROM_EMAIL,
			"to": list(message.to),
			"subject": message.subject,
		}

		if html_body:
			payload["html"] = html_body
			if text_body:
				payload["text"] = text_body
		else:
			payload["text"] = text_body

		if message.cc:
			payload["cc"] = list(message.cc)
		if message.bcc:
			payload["bcc"] = list(message.bcc)
		if message.reply_to:
			payload["reply_to"] = list(message.reply_to)

		headers = {
			"Authorization": f"Bearer {self.api_key}",
			"Content-Type": "application/json",
		}

		response = requests.post(self.API_URL, json=payload, headers=headers, timeout=10)

		if response.status_code not in (200, 201):
			raise Exception(f"Resend API erro {response.status_code}: {response.text}")

		logger.info(f"[ResendBackend] Email enviado para {message.to} — id: {response.json().get('id')}")
