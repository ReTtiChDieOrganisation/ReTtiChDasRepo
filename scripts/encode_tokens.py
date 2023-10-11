# vigenere cipher
# https://stackoverflow.com/a/2490718/1675586
import six, base64

# use to generate new passwords or encode new access tokens
def encode(key, string):
    encoded_chars = []
    for i in range(len(string)):
        key_c = key[i % len(key)]
        encoded_c = chr(ord(string[i]) + ord(key_c) % 256)
        encoded_chars.append(encoded_c)
    encoded_string = ''.join(encoded_chars)
    encoded_string = encoded_string.encode('latin') if six.PY3 else encoded_string
    return base64.urlsafe_b64encode(encoded_string).rstrip(b'=')

def decode(key, string):
    string = base64.urlsafe_b64decode(string + b'===')
    string = string.decode('latin') if six.PY3 else string
    encoded_chars = []
    for i in range(len(string)):
        key_c = key[i % len(key)]
        encoded_c = chr((ord(string[i]) - ord(key_c) + 256) % 256)
        encoded_chars.append(encoded_c)
    encoded_string = ''.join(encoded_chars)
    return encoded_string

password = "INSERT_PASSWORD_HERE" # insert password here
token = "INSERT_TOKEN_HERE" # insert token here

print("password: " + password)
print("Token: " + token)

print ("##########################################")
print("Encoded token: ", encode(password, token))
print ("Add this encoded token to /data/unique_identifier.json. If token is \"b'XYZ'\", then copy \"XYZ\".")
print ("##########################################")

print("Validation: Decoded token is", decode(password, encode(password, token)), "(should be", token, ")")