#!/usr/bin/env python3

"""
Authentication and security module for Seestar INDI driver
"""

import os
import jwt
import bcrypt
import secrets
from datetime import datetime, timedelta
from functools import wraps
from typing import Optional, Dict, Callable
from flask import request, jsonify, current_app
from seestar_config import config_manager
from seestar_logging import get_logger

logger = get_logger("SeestarAuth")

class AuthManager:
    """Authentication manager"""
    
    def __init__(self):
        self.users: Dict[str, str] = {}  # username -> hashed_password
        self.tokens: Dict[str, str] = {}  # token -> username
        self.rate_limits: Dict[str, list] = {}  # ip -> [timestamps]
        self.secret_key = os.environ.get('SEESTAR_SECRET_KEY', secrets.token_hex(32))
        
        # Load users from config
        self._load_users()
        
    def _load_users(self):
        """Load users from configuration"""
        if hasattr(config_manager.config, 'auth'):
            for username, password in config_manager.config.auth.users.items():
                self.add_user(username, password)
                
    def add_user(self, username: str, password: str):
        """Add or update user"""
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password.encode(), salt)
        self.users[username] = hashed.decode()
        
    def verify_password(self, username: str, password: str) -> bool:
        """Verify password for user"""
        if username not in self.users:
            return False
        return bcrypt.checkpw(
            password.encode(),
            self.users[username].encode()
        )
        
    def generate_token(self, username: str) -> str:
        """Generate JWT token"""
        payload = {
            'username': username,
            'exp': datetime.utcnow() + timedelta(days=1)
        }
        token = jwt.encode(payload, self.secret_key, algorithm='HS256')
        self.tokens[token] = username
        return token
        
    def verify_token(self, token: str) -> Optional[str]:
        """Verify JWT token and return username"""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=['HS256'])
            return payload['username']
        except jwt.ExpiredSignatureError:
            logger.warning("Expired token")
            return None
        except jwt.InvalidTokenError:
            logger.warning("Invalid token")
            return None
            
    def check_rate_limit(self, ip: str, limit: int = 100, window: int = 60) -> bool:
        """Check rate limit for IP"""
        now = datetime.now()
        if ip not in self.rate_limits:
            self.rate_limits[ip] = []
            
        # Remove old timestamps
        self.rate_limits[ip] = [
            ts for ts in self.rate_limits[ip]
            if (now - ts).total_seconds() < window
        ]
        
        # Check limit
        if len(self.rate_limits[ip]) >= limit:
            logger.warning(f"Rate limit exceeded for {ip}")
            return False
            
        # Add new timestamp
        self.rate_limits[ip].append(now)
        return True

# Global auth manager instance
auth_manager = AuthManager()

def require_auth(f: Callable):
    """Decorator to require authentication"""
    @wraps(f)
    def decorated(*args, **kwargs):
        # Check rate limit
        if not auth_manager.check_rate_limit(request.remote_addr):
            return jsonify({'error': 'Rate limit exceeded'}), 429
            
        # Check auth token
        token = request.headers.get('Authorization')
        if not token:
            return jsonify({'error': 'No authorization token'}), 401
            
        token = token.replace('Bearer ', '')
        username = auth_manager.verify_token(token)
        if not username:
            return jsonify({'error': 'Invalid token'}), 401
            
        return f(*args, **kwargs)
    return decorated

def init_ssl():
    """Initialize SSL context"""
    cert_path = os.environ.get('SEESTAR_CERT_PATH', '/etc/seestar/ssl')
    cert_file = os.path.join(cert_path, 'cert.pem')
    key_file = os.path.join(cert_path, 'key.pem')
    
    # Generate self-signed certificate if needed
    if not (os.path.exists(cert_file) and os.path.exists(key_file)):
        from OpenSSL import crypto
        
        # Create key
        k = crypto.PKey()
        k.generate_key(crypto.TYPE_RSA, 2048)
        
        # Create certificate
        cert = crypto.X509()
        cert.get_subject().C = "US"
        cert.get_subject().ST = "State"
        cert.get_subject().L = "City"
        cert.get_subject().O = "Organization"
        cert.get_subject().OU = "Organizational Unit"
        cert.get_subject().CN = "localhost"
        cert.set_serial_number(1000)
        cert.gmtime_adj_notBefore(0)
        cert.gmtime_adj_notAfter(365*24*60*60)  # Valid for one year
        cert.set_issuer(cert.get_subject())
        cert.set_pubkey(k)
        cert.sign(k, 'sha256')
        
        # Save certificate and key
        os.makedirs(cert_path, exist_ok=True)
        with open(cert_file, "wb") as f:
            f.write(crypto.dump_certificate(crypto.FILETYPE_PEM, cert))
        with open(key_file, "wb") as f:
            f.write(crypto.dump_privatekey(crypto.FILETYPE_PEM, k))
            
        logger.info(f"Generated self-signed certificate in {cert_path}")
        
    return (cert_file, key_file)
