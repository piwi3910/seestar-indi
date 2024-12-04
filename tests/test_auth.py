#!/usr/bin/env python3

"""
Unit tests for Seestar authentication system
"""

import unittest
import jwt
import time
from unittest.mock import Mock, patch
from datetime import datetime, timedelta

from seestar_auth import AuthManager, require_auth

class TestAuthManager(unittest.TestCase):
    def setUp(self):
        """Set up test environment"""
        self.auth = AuthManager()
        self.test_user = "testuser"
        self.test_pass = "testpass123"
        
    def test_add_user(self):
        """Test user addition"""
        self.auth.add_user(self.test_user, self.test_pass)
        self.assertIn(self.test_user, self.auth.users)
        
    def test_verify_password(self):
        """Test password verification"""
        self.auth.add_user(self.test_user, self.test_pass)
        
        # Test valid password
        self.assertTrue(
            self.auth.verify_password(self.test_user, self.test_pass)
        )
        
        # Test invalid password
        self.assertFalse(
            self.auth.verify_password(self.test_user, "wrongpass")
        )
        
        # Test nonexistent user
        self.assertFalse(
            self.auth.verify_password("nonexistent", self.test_pass)
        )
        
    def test_token_generation_and_verification(self):
        """Test JWT token handling"""
        # Generate token
        token = self.auth.generate_token(self.test_user)
        self.assertIsNotNone(token)
        
        # Verify token
        username = self.auth.verify_token(token)
        self.assertEqual(username, self.test_user)
        
        # Test invalid token
        self.assertIsNone(self.auth.verify_token("invalid.token.here"))
        
    def test_token_expiration(self):
        """Test token expiration"""
        # Create token that expires in 1 second
        payload = {
            'username': self.test_user,
            'exp': datetime.utcnow() + timedelta(seconds=1)
        }
        token = jwt.encode(
            payload,
            self.auth.secret_key,
            algorithm='HS256'
        )
        
        # Verify token is valid initially
        username = self.auth.verify_token(token)
        self.assertEqual(username, self.test_user)
        
        # Wait for expiration
        time.sleep(2)
        
        # Verify token is now invalid
        self.assertIsNone(self.auth.verify_token(token))
        
    def test_rate_limiting(self):
        """Test rate limiting"""
        ip = "127.0.0.1"
        
        # Test within limit
        for _ in range(50):
            self.assertTrue(self.auth.check_rate_limit(ip, limit=100))
            
        # Test exceeding limit
        for _ in range(60):
            self.auth.check_rate_limit(ip, limit=100)
        self.assertFalse(self.auth.check_rate_limit(ip, limit=100))
        
        # Test rate limit window
        ip2 = "127.0.0.2"
        self.auth.check_rate_limit(ip2, limit=1, window=1)
        self.assertFalse(self.auth.check_rate_limit(ip2, limit=1, window=1))
        time.sleep(1.1)  # Wait for window to pass
        self.assertTrue(self.auth.check_rate_limit(ip2, limit=1, window=1))

class TestAuthDecorator(unittest.TestCase):
    def setUp(self):
        """Set up test environment"""
        self.auth = AuthManager()
        self.test_user = "testuser"
        self.test_pass = "testpass123"
        self.auth.add_user(self.test_user, self.test_pass)
        
    def test_require_auth_decorator(self):
        """Test authentication decorator"""
        # Create mock Flask request
        mock_request = Mock()
        mock_request.headers = {}
        mock_request.remote_addr = "127.0.0.1"
        
        # Create test endpoint
        @require_auth
        def test_endpoint():
            return "Success"
            
        # Test without token
        with patch('flask.request', mock_request):
            response = test_endpoint()
            self.assertIn('error', response[0])
            self.assertEqual(response[1], 401)
            
        # Test with invalid token
        mock_request.headers['Authorization'] = 'Bearer invalid.token'
        with patch('flask.request', mock_request):
            response = test_endpoint()
            self.assertIn('error', response[0])
            self.assertEqual(response[1], 401)
            
        # Test with valid token
        token = self.auth.generate_token(self.test_user)
        mock_request.headers['Authorization'] = f'Bearer {token}'
        with patch('flask.request', mock_request):
            response = test_endpoint()
            self.assertEqual(response, "Success")
            
        # Test rate limiting
        for _ in range(150):  # Exceed rate limit
            with patch('flask.request', mock_request):
                response = test_endpoint()
        self.assertEqual(response[1], 429)  # Too Many Requests

class TestSSLCertGeneration(unittest.TestCase):
    def setUp(self):
        """Set up test environment"""
        self.temp_dir = "test_certs"
        
    def tearDown(self):
        """Clean up test environment"""
        import shutil
        try:
            shutil.rmtree(self.temp_dir)
        except FileNotFoundError:
            pass
            
    @patch('os.environ')
    def test_certificate_generation(self, mock_environ):
        """Test SSL certificate generation"""
        from seestar_auth import init_ssl
        
        # Set certificate path to temp directory
        mock_environ.get.return_value = self.temp_dir
        
        # Generate certificates
        cert_file, key_file = init_ssl()
        
        # Verify files were created
        self.assertTrue(cert_file.endswith('cert.pem'))
        self.assertTrue(key_file.endswith('key.pem'))
        self.assertTrue(all(map(lambda f: f.exists(), map(Path, [cert_file, key_file]))))
        
        # Verify certificate contents
        from OpenSSL import crypto
        with open(cert_file, 'rb') as f:
            cert = crypto.load_certificate(crypto.FILETYPE_PEM, f.read())
            
        self.assertEqual(cert.get_subject().CN, 'localhost')
        self.assertEqual(cert.get_subject().O, 'Organization')
        
        # Verify key contents
        with open(key_file, 'rb') as f:
            key = crypto.load_privatekey(crypto.FILETYPE_PEM, f.read())
            
        self.assertEqual(key.bits(), 2048)

if __name__ == '__main__':
    unittest.main()
