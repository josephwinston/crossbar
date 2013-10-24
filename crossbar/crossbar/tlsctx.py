###############################################################################
##
##  Copyright (C) 2011-2013 Tavendo GmbH
##
##  This program is free software: you can redistribute it and/or modify
##  it under the terms of the GNU Affero General Public License, version 3,
##  as published by the Free Software Foundation.
##
##  This program is distributed in the hope that it will be useful,
##  but WITHOUT ANY WARRANTY; without even the implied warranty of
##  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
##  GNU Affero General Public License for more details.
##
##  You should have received a copy of the GNU Affero General Public License
##  along with this program. If not, see <http://www.gnu.org/licenses/>.
##
###############################################################################


import tempfile

from OpenSSL import crypto, SSL
from twisted.internet.ssl import DefaultOpenSSLContextFactory

# monkey patch missing constants
# https://bugs.launchpad.net/pyopenssl/+bug/1244201
SSL.SSL_OP_NO_COMPRESSION = 0x00020000L
SSL.SSL_OP_CIPHER_SERVER_PREFERENCE = 0x00400000L

# http://hynek.me/articles/hardening-your-web-servers-ssl-ciphers/
CHIPERS = 'ECDH+AESGCM:DH+AESGCM:ECDH+AES256:DH+AES256:ECDH+AES128:DH+AES:ECDH+3DES:DH+3DES:RSA+AES:RSA+3DES:!ADH:!AECDH:!MD5:!DSS'


class TlsContextFactory(DefaultOpenSSLContextFactory):
   """
   TLS context factory for use with Twisted.

   Like the default

      http://twistedmatrix.com/trac/browser/tags/releases/twisted-11.1.0/twisted/internet/ssl.py#L42

   but loads key/cert from string, not file and supports chained certificates.

   See also:

      http://pyopenssl.sourceforge.net/pyOpenSSL.html/openssl-context.html
      http://www.openssl.org/docs/ssl/SSL_CTX_use_certificate.html

   Chained certificates:
      The certificates must be in PEM format and must be sorted starting with
      the subject's certificate (actual client or server certificate), followed
      by intermediate CA certificates if applicable, and ending at the
      highest level (root) CA.

   Hardening:
      http://hynek.me/articles/hardening-your-web-servers-ssl-ciphers/
      https://www.ssllabs.com/ssltest/analyze.html?d=www.example.com
   """

   def __init__(self, privateKeyString, certificateString, chainedCertificate = True):
      self.privateKeyString = str(privateKeyString)
      self.certificateString = str(certificateString)
      self.chainedCertificate = chainedCertificate

      ## do a SSLv2-compatible handshake even for TLS
      ##
      self.sslmethod = SSL.SSLv23_METHOD

      self._contextFactory = SSL.Context
      self.cacheContext()

   def cacheContext(self):
      if self._context is None:
         ctx = self._contextFactory(self.sslmethod)

         ## SSL hardening
         ##
         ctx.set_options(SSL.OP_NO_SSLv2 | SSL.OP_NO_SSLv3 | SSL.OP_NO_COMPRESSION | SSL.OP_CIPHER_SERVER_PREFERENCE)
         ctx.set_cipher_list(CHIPERS)

         ## load certificate (chain) into context
         ##
         if not self.chainedCertificate:
            cert = crypto.load_certificate(crypto.FILETYPE_PEM, self.certificateString)
            ctx.use_certificate(cert)
         else:
            # http://pyopenssl.sourceforge.net/pyOpenSSL.html/openssl-context.html
            # there is no "use_certificate_chain" function, so we need to create
            # a temporary file writing the certificate chain file
            f = tempfile.NamedTemporaryFile(delete = False)
            f.write(self.certificateString)
            f.close()
            ctx.use_certificate_chain_file(f.name)

         ## load private key into context
         ##
         key = crypto.load_privatekey(crypto.FILETYPE_PEM, self.privateKeyString)
         ctx.use_privatekey(key)
         ctx.check_privatekey()

         ## set cached context
         ##
         self._context = ctx