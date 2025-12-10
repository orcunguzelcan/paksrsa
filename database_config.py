import os


def read_db_config(config_path="db_config.txt"):
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"DB config dosyası bulunamadı: {config_path}")

    config = {}
    with open(config_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, value = line.split("=", 1)
                config[key.strip()] = value.strip()

    required_keys = ["Server", "Uid", "Password", "Database"]
    for key in required_keys:
        if key not in config:
            raise ValueError(f"db_config.txt içinde eksik parametre: {key}")

    return config


# --- GERİYE UYUMLULUK ---
_cfg = read_db_config()

Server = _cfg["Server"]
Uid = _cfg["Uid"]
Password = _cfg["Password"]
Database = _cfg["Database"]