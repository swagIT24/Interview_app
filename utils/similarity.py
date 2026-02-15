import math

def cosine_similarity(vec1,vec2):
    dot_prod = sum(a*b for a,b in zip(vec1,vec2))
    mag1 = math.sqrt(sum(a*a for a in vec1))
    mag2 = math.sqrt(sum(b*b for b in vec2))

    if mag1 == 0.0 or mag2 == 0.0:
        return 0.0
    return dot_prod/(mag1*mag2)