import sys
  
# append the path of the parent directory
sys.path.append("..")

from etc import rettich_encrypt

password = "INSERT_PASSWORD_HERE" # insert password here
token = "INSERT_TOKEN_HERE" # insert token here

print("password: " + password)
print("Token: " + token)

print ("##########################################")
print("Encoded token: ", rettich_encrypt.encode(password, token))
print ("Add this encoded token to /data/unique_identifier.json. If token is \"b'XYZ'\", then copy \"XYZ\".")
print ("##########################################")

print("Validation: Decoded token is", rettich_encrypt.decode(password, rettich_encrypt.encode(password, token)), "(should be", token, ")")