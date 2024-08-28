def check_index(text: str, arrlen: int) -> int | None:
    if not text.isdigit():
        return None
    index = int(text)
    if 1 <= index <= arrlen:
        return index

