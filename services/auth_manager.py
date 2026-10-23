import os
import json
import hashlib
from pathlib import Path
from typing import Tuple

from services import paths


def _accounts_path() -> Path:
    return paths.data_dir() / "accounts.json"


def _load_accounts() -> dict:
    p = _accounts_path()
    if not p.exists():
        return {}
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_accounts(data: dict) -> None:
    p = _accounts_path()
    try:
        with open(p, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"[AUTH] Сохранено в {p}: {list(data.keys())}")
    except Exception as ex:
        print(f"[AUTH] Ошибка записи: {ex}")


def hash_password(password: str, salt: str) -> str:
    return hashlib.sha256((password + salt).encode('utf-8')).hexdigest()


def create_account(username: str, password: str) -> Tuple[bool, str]:
    username = username.strip().lower()

    if not username or not password:
        return False, "Логин и пароль не могут быть пустыми"

    if len(password) < 4:
        return False, "Пароль должен быть не короче 4 символов"

    accounts = _load_accounts()
    if username in accounts:
        return False, "Этот логин уже занят"

    salt = os.urandom(8).hex()
    pwd_hash = hash_password(password, salt)

    accounts[username] = {
        "salt": salt,
        "hash": pwd_hash
    }
    _save_accounts(accounts)
    return True, "OK"


def login(username: str, password: str) -> Tuple[bool, str]:
    username = username.strip().lower()

    # ВСЕГДА ЧИТАЕМ ФАЙЛ ЗАНОВО
    accounts = _load_accounts()
    print(f"[AUTH] Попытка входа. Доступные аккаунты: {list(accounts.keys())}")

    if username not in accounts:
        return False, "Неверный логин или пароль"

    acc = accounts[username]
    expected_hash = acc.get("hash", "")
    salt = acc.get("salt", "")

    if not expected_hash or not salt:
        return False, "Ошибка в данных аккаунта"

    current_hash = hash_password(password, salt)
    if current_hash == expected_hash:
        print(f"[AUTH] Успешный вход: {username}")
        return True, "OK"

    print(f"[AUTH] Неверный пароль. Ожидался хэш: {expected_hash[:10]}... Получен: {current_hash[:10]}...")
    return False, "Неверный логин или пароль"