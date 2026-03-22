from hashlib import sha256


def build_embedding_vector(text: str, dimensions: int = 12) -> list[float]:
    digest = sha256(text.encode("utf-8")).digest()
    values: list[float] = []

    for index in range(dimensions):
        byte = digest[index % len(digest)]
        values.append(round((byte / 255.0) * 2 - 1, 6))

    return values
