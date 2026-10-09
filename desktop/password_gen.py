import secrets
import string

class PasswordGenerator:
    """
    Cryptographically secure password and passphrase generator.
    """
    UPPERCASE = string.ascii_uppercase
    LOWERCASE = string.ascii_lowercase
    DIGITS = string.digits
    SYMBOLS = "!@#$%^&*()-_=+[]{}|;:,.<>?"

    @classmethod
    def generate(cls, length: int = 16, use_upper: bool = True, use_lower: bool = True,
                 use_digits: bool = True, use_symbols: bool = True, avoid_ambiguous: bool = True) -> str:
        pool = ""
        guaranteed = []

        ambiguous_chars = set("il1Lo0O")

        def filter_pool(chars: str) -> str:
            if avoid_ambiguous:
                return "".join(c for c in chars if c not in ambiguous_chars)
            return chars

        upper_pool = filter_pool(cls.UPPERCASE) if use_upper else ""
        lower_pool = filter_pool(cls.LOWERCASE) if use_lower else ""
        digit_pool = filter_pool(cls.DIGITS) if use_digits else ""
        sym_pool = filter_pool(cls.SYMBOLS) if use_symbols else ""

        if upper_pool:
            pool += upper_pool
            guaranteed.append(secrets.choice(upper_pool))
        if lower_pool:
            pool += lower_pool
            guaranteed.append(secrets.choice(lower_pool))
        if digit_pool:
            pool += digit_pool
            guaranteed.append(secrets.choice(digit_pool))
        if sym_pool:
            pool += sym_pool
            guaranteed.append(secrets.choice(sym_pool))

        if not pool:
            pool = cls.LOWERCASE + cls.DIGITS
            guaranteed = [secrets.choice(pool)]

        # Fill remaining length
        remaining = max(0, length - len(guaranteed))
        chars = guaranteed + [secrets.choice(pool) for _ in range(remaining)]
        
        # Cryptographic shuffle
        for i in range(len(chars) - 1, 0, -1):
            j = secrets.randbelow(i + 1)
            chars[i], chars[j] = chars[j], chars[i]

        return "".join(chars)

    @classmethod
    def calculate_strength(cls, password: str) -> dict:
        """Calculates password entropy and score (0-4)."""
        if not password:
            return {"score": 0, "label": "Empty", "color": "#888888"}

        length = len(password)
        pool_size = 0
        if any(c.isupper() for c in password): pool_size += 26
        if any(c.islower() for c in password): pool_size += 26
        if any(c.isdigit() for c in password): pool_size += 10
        if any(c in cls.SYMBOLS for c in password): pool_size += len(cls.SYMBOLS)

        import math
        entropy = length * math.log2(max(pool_size, 2))

        if entropy < 30:
            return {"score": 1, "label": "Very Weak", "color": "#f44336"}
        elif entropy < 50:
            return {"score": 2, "label": "Weak", "color": "#ff9800"}
        elif entropy < 70:
            return {"score": 3, "label": "Moderate", "color": "#ffeb3b"}
        elif entropy < 90:
            return {"score": 4, "label": "Strong", "color": "#4caf50"}
        else:
            return {"score": 5, "label": "Very Strong", "color": "#00e676"}
