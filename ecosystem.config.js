module.exports = {
  apps: [
    {
      name: "telegram-post-bot",
      script: "bot.py",
      interpreter: "python3",
      autorestart: true,
      watch: false,
      max_restarts: 10,
      restart_delay: 3000,
      env: {
        PYTHONUNBUFFERED: "1"
      }
    }
  ]
};
