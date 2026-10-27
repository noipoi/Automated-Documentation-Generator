"""Text helper functions."""


def slugify(title: str, separator: str = "-") -> str:
    """Turn ``title`` into a lowercase, URL-friendly string."""
    return separator.join(title.lower().split())


def shout(message: str) -> str:
    return message.upper() + "!"
