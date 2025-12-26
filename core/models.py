from django.db import models
import uuid
from django.contrib.auth.models import User
from django.utils.translation import gettext_lazy as _
from cryptography.fernet import Fernet
import os
from cryptography.fernet import Fernet
import base64
from dotenv import load_dotenv
import json
from django.utils import timezone
from decimal import Decimal

load_dotenv()

class UserWallet(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='wallet')
    fiat_balance = models.DecimalField(max_digits=9, decimal_places=2, default=0)
    public_key = models.CharField(max_length=256, blank=True, null=True)
    private_key = models.CharField(max_length=256, blank=True, null=True, editable=False)
    recipient_id = models.CharField(max_length=100, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        """Encrypt private keys before saving."""
        if self.private_key:
            key_str = str(self.private_key)
            if not key_str.startswith("gAAAA"):  # Avoid double encryption
                self.private_key = self.encrypt_key(key_str)
        super().save(*args, **kwargs)

    def encrypt_key(self, key: str) -> str:
        """
        Encrypt the private key using Fernet.
        """
        try:
            secret_key = os.getenv('SECRET_KEY')
            if not secret_key:
                raise ValueError("Missing SECRET_KEY in environment variables")
            
            key_bytes = secret_key.encode()
            key_base64 = base64.urlsafe_b64encode(key_bytes.ljust(32)[:32])
            f = Fernet(key_base64)
            return f.encrypt(key.encode()).decode()
        except Exception as e:
            raise ValueError(f"Encryption error: {e}")

    def decrypt_key(self) -> str:
        """
        Decrypt the private key using Fernet.
        """
        try:
            secret_key = os.getenv('SECRET_KEY')
            if not secret_key:
                raise ValueError("Missing SECRET_KEY in environment variables")
            
            key_bytes = secret_key.encode()
            key_base64 = base64.urlsafe_b64encode(key_bytes.ljust(32)[:32])
            f = Fernet(key_base64)
            return f.decrypt(self.private_key.encode()).decode()
        except Exception as e:
            raise ValueError(f"Decryption error: {e}")

    def __str__(self):
        return f"{self.user.username} Wallet"