from app import BotApp

if __name__ == "__main__":
    app = BotApp(filename="data/profil_1.geo", 
                 config_filename = "bot_config.toml")
    app.run() 