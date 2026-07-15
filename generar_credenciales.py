"""Genera el bloque [auth] para .streamlit/secrets.toml a partir de un usuario y
contraseña introducidos de forma interactiva. La contraseña nunca se guarda ni se
imprime en texto plano en ningún archivo - solo su hash salteado.

Uso: python generar_credenciales.py
"""
import getpass
import hashlib
import os

ITERACIONES_PBKDF2 = 200_000

usuario = input("Usuario: ")
contraseña = getpass.getpass("Contraseña: ")

salt = os.urandom(16)
hash_contraseña = hashlib.pbkdf2_hmac('sha256', contraseña.encode('utf-8'), salt, ITERACIONES_PBKDF2)

print()
print("Pega esto en .streamlit/secrets.toml:")
print()
print("[auth]")
print(f'username = "{usuario}"')
print(f'password_hash = "{hash_contraseña.hex()}"')
print(f'password_salt = "{salt.hex()}"')
