"""NUMORA Telegram bot package.

``bot.py`` stays the process entry point (``python bot.py``) so the Dockerfile and
local runs are unchanged; this file simply makes ``bot`` an importable package so
``from admin...`` resolves even when the script's own directory is first on
``sys.path``.
"""
