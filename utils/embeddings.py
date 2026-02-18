import hashlib

def fake_embedding(text, dimension=10):
    # Create hash of text
    hash_object = hashlib.md5(text.encode())
    hash_bytes = hash_object.digest()

    # Convert bytes to numbers
    vector = [b for b in hash_bytes[:dimension]]

    # Normalize vector to smaller scale
    return [v / 255.0 for v in vector]
